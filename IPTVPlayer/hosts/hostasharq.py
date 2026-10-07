# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026
# 03.10.2026 - rewrite for the Next.js "NOW Asharq" site (old version: MOHAMED_OS)
#   Everything comes from the JSON API behind now.asharq.com (api-now.asharq.com/api):
#   /dynamic-pages/<channel> (rails), /dynamic-pages/components/<slug>/?page= (full rail),
#   /categories/<slug>?page=, /shows/<slug> (seasons), /episodes/show/<slug>?page=&seasonId=,
#   /episodes|movies|clips/<id> (HLS sources + Arabic VTT captions), /search?q=&page=,
#   /channels/sources (live HLS) + watched flag / downloaded flag / name normalisation /
#   sidecar / favourites. INFO uses the site's own description (news / documentaries, no moviemeta).
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads_safe as json_loads_safe
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
from Plugins.Extensions.IPTVPlayer.p2p3.pVer import isPY2
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx, normalizeMediathekTitle
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://now.asharq.com/"


API_URL = "https://api-now.asharq.com/api"
PAGE_LIMIT = 12
SEARCH_LIMIT = 15  # /search ignores "limit"

# VOD row urls (the site's own page urls): ids are what the API needs
VIDEO_URL_RE = re.compile(r'/videos/[^/]+/(?:movies|shows/[^/]+)/(\d+)/|/clips/(\d+)/')

CHANNELS = (("documentary", "الشرق الوثائقية"),
            ("discovery", "الشرق Discovery"),
            ("thaqafeyah", "الثقافية"),
            ("podcast", "بودكاست الشرق"),
            ("news", "الشرق للأخبار"),
            ("business", "الشرق Bloomberg"))

# /channels/sources only carries the type; names as the site shows them
LIVE_NAMES = (("business", "الشرق Bloomberg"),
              ("discovery", "الشرق Discovery"),
              ("documentary", "الشرق الوثائقية"),
              ("thaqafeyah", "الثقافية"),
              ("radio", "راديو الشرق مع Bloomberg"))
LIVE_FALLBACK = {"business": "https://live-news.asharq.com/asharq.m3u8",
                 "discovery": "https://svs.itworkscdn.net/asharqdiscoverylive/asharqd.smil/playlist_dvr.m3u8",
                 "documentary": "https://svs.itworkscdn.net/asharqdocumentarylive/asharqdocumentary.smil/playlist_dvr.m3u8",
                 "thaqafeyah": "https://live-thaqafeyah.asharq.com/asharq.m3u8",
                 "radio": "https://svs.itworkscdn.net/asharqradiovlive/asharqradiov/playlist.m3u8"}

# rails that are no content lists (user state, banners, live player, ...)
SKIP_COMPONENTS = ("continueWatching", "signup", "liveStream", "channels", "radio", "categories", "topContent")


def _s(value):
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return str(value)
    return ensure_str(value)


def _q(text):
    # percent-encode an (Arabic) slug for an url path
    text = _s(text)
    if isPY2() and not isinstance(text, bytes):  # Python 2 unicode leftover
        text = text.encode("utf-8")
    return urllib_quote(text, safe="-_.~")


class Asharq(GenericFolderWatchedScraperMixin, CBaseHostClass):
    # what identifies a row and is needed to open it again (desc carries the date / duration only)
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "aq_type", "aq_id", "show_slug", "show_title",
                  "season_id", "season_title", "channel")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "asharq", "cookie": "asharq.cookie"})
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.HEADER.update({"Accept": "application/json, text/plain, */*", "Origin": "https://now.asharq.com", "Referer": "https://now.asharq.com/"})
        self.defaultParams = {"header": self.HEADER}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "https://now.asharq.com/assets/logo.png"
        self.MENU = [{"category": "aq_live", "title": _("Live")},
                     {"category": "aq_top", "title": _("Top 10")}]
        for slug, name in CHANNELS:
            self.MENU.append({"category": "aq_page", "title": name, "page_slug": slug, "channel": slug})
        self.MENU.append({"category": "aq_page", "title": "الشرق NOW", "page_slug": "home"})
        self.MENU.append({"category": "aq_cats", "title": _("Categories")})
        self.MENU.extend(self.searchItems())

        self.watchedHelper = IPTVWatchedHelper("asharq")
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict) or cItem.get("is_live"):
                return ""
            url = str(cItem.get("url", "") or "").strip()
            if not url:
                return ""
            if cItem.get("type", "") in ("video", "audio"):
                return "video:%s" % url
            category = cItem.get("category", "")
            if category == "aq_show" or (category == "aq_episodes" and not cItem.get("season_id")):
                # aq_episodes = page 2+ of a show / season: keyed like page 1
                return "folder:%s" % url
            if category in ("aq_season", "aq_episodes"):
                return "folder:%s|%s" % (url, cItem.get("season_id", ""))
        except Exception:
            printExc()
        return ""

    ###################################################
    # api helpers
    ###################################################
    def _api(self, path):
        sts, data = self.cm.getPage(API_URL + path, dict(self.defaultParams))
        if not sts:
            return None
        ret = json_loads_safe(data)
        if isinstance(ret, dict) and "data" in ret:
            return ret.get("data")
        return ret

    def _image(self, item, ratios):
        images = item.get("image") or {}
        if not isinstance(images, dict):
            return ""
        for ratio in ratios:
            img = images.get(ratio)
            if isinstance(img, dict):
                for size in ("large", "medium", "x-large", "small"):
                    url = _s(img.get(size))
                    if self.cm.isValidUrl(url) and not url.endswith("/"):
                        return url
        return ""

    def _desc(self, item, long=False):
        descr = item.get("description") or {}
        text = ""
        if isinstance(descr, dict):
            text = descr.get("long") if long else ""
            text = text or descr.get("short") or descr.get("long") or ""
        return self.cleanHtmlStr(_s(text))

    def _channelSlug(self, item, default=""):
        for src in (item.get("channel"), (item.get("show") or {}).get("channel"), (item.get("movie") or {}).get("channel")):
            if isinstance(src, dict) and src.get("slug"):
                return _s(src.get("slug"))
        return default or "news"

    ###################################################
    # rows
    ###################################################
    def _episodeTitle(self, title, showTitle, episodeNumber, seasonTitle, date):
        if not IsMediaNamingNormalized():
            return title
        classic = title
        if showTitle and showTitle not in title:
            classic = "%s - %s" % (showTitle, title)
        sxeHint = ""
        if episodeNumber:
            season = seasonTitle if (seasonTitle.isdigit() and int(seasonTitle) < 100) else ("1" if not seasonTitle else "")
            if season:
                sxeHint = formatSxxExx(season, episodeNumber)
        return normalizeMediathekTitle(classic, date=date if not sxeHint else "", sxeHint=sxeHint)

    def _addEntry(self, cItem, item):
        itemType = _s(item.get("type"))
        itemId = _s(item.get("id"))
        slug = _s(item.get("slug"))
        title = self.cleanHtmlStr(_s(item.get("title")))
        if not itemType or not itemId or not slug or not title:
            return False
        channel = self._channelSlug(item, cItem.get("channel", ""))
        params = {"name": cItem.get("name", "category"), "good_for_fav": True, "channel": channel, "aq_type": itemType, "aq_id": itemId}
        if itemType == "show":
            total = item.get("totalEpisodes")
            desc = []
            if total:
                desc.append("%s: %s" % (_("Episodes"), total))
            text = self._desc(item)
            if text:
                desc.append(text)
            params.update({"category": "aq_show", "title": title, "show_slug": slug, "show_title": title,
                           "url": "%s%s/shows/%s/" % (self.MAIN_URL, channel, _q(slug)),
                           "icon": self._image(item, ("2-3", "16-9", "1-1")), "desc": "[/br]".join(desc)})
            self.addDir(params)
            return True
        if itemType not in ("movie", "episode", "clip"):
            return False
        video = item.get("video") or {}
        date = _s(item.get("publishedAt"))[:10]
        desc = [x for x in (_s(video.get("duration")) if isinstance(video, dict) else "", date) if x]
        desc = [" | ".join(desc)] if desc else []
        text = self._desc(item)
        if text:
            desc.append(text)
        show = item.get("show") or {}
        showTitle = self.cleanHtmlStr(_s(show.get("title"))) if isinstance(show, dict) else ""
        showSlug = _s(show.get("slug")) if isinstance(show, dict) else ""
        if itemType == "movie":
            url = "%svideos/%s/movies/%s/%s/" % (self.MAIN_URL, channel, itemId, _q(slug))
            rowTitle = title
        elif itemType == "episode":
            showTitle = showTitle or cItem.get("show_title", "")
            showSlug = showSlug or cItem.get("show_slug", "")
            url = "%svideos/%s/shows/%s/%s/%s/" % (self.MAIN_URL, channel, _q(showSlug or "show"), itemId, _q(slug))
            rowTitle = self._episodeTitle(title, showTitle, _s(item.get("episodeNumber")), cItem.get("season_title", ""), date)
        else:
            url = "%sclips/%s/%s/" % (self.MAIN_URL, itemId, _q(slug))
            rowTitle = normalizeMediathekTitle(title, date=date)
        params.update({"category": "aq_video", "title": rowTitle, "url": url, "show_title": showTitle, "show_slug": showSlug,
                       "icon": self._image(item, ("16-9", "2-3", "1-1")), "desc": "[/br]".join(desc)})
        self.addVideo(params)
        return True

    def _addEntries(self, cItem, items):
        cnt = 0
        seen = set()
        for item in items or []:
            if not isinstance(item, dict):
                continue
            key = (item.get("type"), item.get("id"))
            if key in seen:
                continue
            seen.add(key)
            if self._addEntry(cItem, item):
                cnt += 1
        return cnt

    @staticmethod
    def _page(cItem):
        try:
            return max(1, int(cItem.get("page", 1) or 1))
        except (TypeError, ValueError):
            return 1

    def _addPaging(self, cItem, hasNext, pageUrlTpl):
        # the API sends no page count: First page / Jump / Next page; the template only feeds "Jump"
        # (rows that key on "url" pass their own constant url)
        addPagingItems(self, cItem, self._page(cItem), hasNext, 0, pageUrlTpl)

    ###################################################
    # lists
    ###################################################
    def listLive(self, cItem):
        printDBG("Asharq.listLive")
        sources = {}
        data = self._api("/channels/sources")
        for entry in data if isinstance(data, list) else []:
            try:
                streams = ((entry.get("sources") or {}).get("horizontal") or [])
                for stream in streams:
                    url = _s(stream.get("file") or stream.get("src"))
                    if ".m3u8" in url:
                        sources.setdefault(_s(entry.get("type")), url)
                        break
            except Exception:
                printExc()
        for liveType, name in LIVE_NAMES:
            url = sources.get(liveType) or LIVE_FALLBACK.get(liveType, "")
            if not url:
                continue
            params = {"name": "category", "good_for_fav": True, "category": "aq_live_item", "is_live": True,
                      "title": name, "url": url, "icon": self.DEFAULT_ICON_URL, "desc": _("Live")}
            self.addVideo(params)

    def listTop(self, cItem):
        printDBG("Asharq.listTop")
        self._addEntries(cItem, self._api("/top-content"))

    def listPage(self, cItem):
        printDBG("Asharq.listPage [%s]" % cItem.get("page_slug", ""))
        data = self._api("/dynamic-pages/%s" % _q(cItem["page_slug"]))
        if not isinstance(data, dict):
            return
        for comp in data.get("components") or []:
            try:
                if not isinstance(comp, dict) or _s(comp.get("name")) in SKIP_COMPONENTS:
                    continue
                content = [x for x in (comp.get("content") or []) if isinstance(x, dict)]
                slug = _s(comp.get("slug"))
                title = self.cleanHtmlStr(_s(comp.get("title")))
                if not content:
                    continue
                if not slug and len(content) == 1:
                    # hero rails with a single show: open the show directly
                    self._addEntry(cItem, content[0])
                    continue
                params = dict(cItem)
                params.update({"good_for_fav": True, "title": title or _("Featured"), "comp_id": comp.get("id")})
                if slug:
                    params.update({"category": "aq_component", "comp_slug": slug})
                else:
                    params.update({"category": "aq_inline"})
                self.addDir(params)
            except Exception:
                printExc()

    def listInline(self, cItem):
        printDBG("Asharq.listInline [%s] %s" % (cItem.get("page_slug", ""), cItem.get("comp_id")))
        data = self._api("/dynamic-pages/%s" % _q(cItem["page_slug"]))
        if not isinstance(data, dict):
            return
        for comp in data.get("components") or []:
            if isinstance(comp, dict) and comp.get("id") == cItem.get("comp_id"):
                self._addEntries(cItem, comp.get("content"))
                break

    def listComponent(self, cItem):
        page = self._page(cItem)
        printDBG("Asharq.listComponent [%s] page %s" % (cItem.get("comp_slug", ""), page))
        tpl = API_URL + "/dynamic-pages/components/%s/?page={page}&limit=%d" % (_q(cItem["comp_slug"]), PAGE_LIMIT)
        data = self._api(tpl.format(page=page)[len(API_URL):])
        if not isinstance(data, dict):
            return
        cnt = self._addEntries(cItem, data.get("content"))
        self._addPaging(cItem, cnt > 0 and len(data.get("content") or []) >= PAGE_LIMIT, tpl)

    def listCategories(self, cItem):
        printDBG("Asharq.listCategories")
        data = self._api("/search-filters")
        for group in data if isinstance(data, list) else []:
            if not isinstance(group, dict) or group.get("key") != "categories":
                continue
            for cat in group.get("content") or []:
                name = self.cleanHtmlStr(_s(cat.get("name")))
                if not name:
                    continue
                params = dict(cItem)
                params.update({"good_for_fav": True, "category": "aq_category", "title": name, "cat_slug": name.replace(" ", "-")})
                self.addDir(params)

    def listCategory(self, cItem):
        page = self._page(cItem)
        printDBG("Asharq.listCategory [%s] page %s" % (cItem.get("cat_slug", ""), page))
        tpl = API_URL + "/categories/%s?page={page}&limit=%d" % (_q(cItem["cat_slug"]), PAGE_LIMIT)
        data = self._api(tpl.format(page=page)[len(API_URL):])
        if not isinstance(data, dict):
            return
        cnt = self._addEntries(cItem, data.get("content"))
        self._addPaging(cItem, cnt > 0 and len(data.get("content") or []) >= PAGE_LIMIT, tpl)

    def listShow(self, cItem):
        printDBG("Asharq.listShow [%s]" % cItem.get("show_slug", ""))
        data = self._api("/shows/%s" % _q(cItem["show_slug"]))
        seasons = []
        if isinstance(data, dict):
            seasons = [x for x in (data.get("seasons") or []) if isinstance(x, dict) and x.get("id")]
        if len(seasons) > 1:
            showTitle = cItem.get("show_title", cItem.get("title", ""))
            for season in seasons:
                seasonTitle = self.cleanHtmlStr(_s(season.get("title")))
                label = seasonTitle if not seasonTitle.isdigit() or int(seasonTitle) > 99 else "%s %s" % (_("Season"), seasonTitle)
                params = dict(cItem)
                params.update({"good_for_fav": True, "category": "aq_season", "title": "%s - %s" % (showTitle, label),
                               "season_id": _s(season.get("id")), "season_title": seasonTitle})
                self.addDir(params)
            return
        params = dict(cItem)
        if len(seasons) == 1:
            params.update({"season_title": self.cleanHtmlStr(_s(seasons[0].get("title")))})
        params["page"] = 1
        self.listEpisodes(params)

    def listEpisodes(self, cItem):
        page = self._page(cItem)
        printDBG("Asharq.listEpisodes [%s] season %s page %s" % (cItem.get("show_slug", ""), cItem.get("season_id", ""), page))
        path = "/episodes/show/%s?page=%d&limit=%d" % (_q(cItem["show_slug"]), page, PAGE_LIMIT)
        if cItem.get("season_id"):
            path += "&seasonId=%s" % cItem["season_id"]
        data = self._api(path)
        items = data if isinstance(data, list) else []
        cnt = self._addEntries(cItem, items)
        # the show url is the watched key of the pages: constant "Jump" template
        self._addPaging(dict(cItem, category="aq_episodes"), cnt > 0 and len(items) >= PAGE_LIMIT, cItem.get("url", "").replace("{", "").replace("}", ""))

    def listSearchResult(self, cItem, searchPattern, searchType):
        page = self._page(cItem)
        printDBG("Asharq.listSearchResult [%s] page %s" % (searchPattern, page))
        data = self._api("/search?q=%s&page=%d" % (_q(searchPattern), page))
        items = data if isinstance(data, list) else []
        cnt = self._addEntries(cItem, items)
        self._addPaging(dict(cItem, category="search_next_page", search_pattern=searchPattern), cnt > 0 and len(items) >= SEARCH_LIMIT, "")

    ###################################################
    # links
    ###################################################
    def _videoRef(self, cItem):
        itemType = cItem.get("aq_type", "")
        itemId = cItem.get("aq_id", "")
        if not itemId:
            match = VIDEO_URL_RE.search(cItem.get("url", ""))
            if match:
                itemId = match.group(1) or match.group(2)
                url = cItem.get("url", "")
                itemType = "movie" if "/movies/" in url else ("clip" if "/clips/" in url else "episode")
        return itemType, itemId

    def _details(self, cItem):
        itemType, itemId = self._videoRef(cItem)
        if itemType not in ("movie", "episode", "clip") or not itemId:
            return {}
        data = self._api("/%ss/%s" % (itemType, itemId))
        return data if isinstance(data, dict) else {}

    def _liveLinks(self, cItem):
        url = cItem.get("url", "")
        urltab = []
        try:
            urltab = getDirectM3U8Playlist(url, checkExt=False, checkContent=True, sortWithMaxBitrate=999999999)
        except Exception:
            printExc()
        # the news/thaqafeyah masters end with an audio-only variant (no resolution)
        withVideo = [item for item in urltab if re.search(r"\d+x\d+", item.get("name", ""))]
        urltab = withVideo or urltab
        if not urltab:
            urltab = [{"name": "HLS", "url": url}]
        ret = []
        for item in urltab:
            ret.append({"name": item.get("name", "").strip() or "HLS", "need_resolve": 0,
                        "url": self.up.decorateUrl(item["url"], {"iptv_livestream": True, "iptv_proto": "m3u8", "User-Agent": self.HEADER.get("User-Agent")})})
        return ret

    def getLinksForVideo(self, cItem):
        printDBG("Asharq.getLinksForVideo [%s]" % cItem.get("url", ""))
        if cItem.get("is_live") or cItem.get("category") == "aq_live_item":
            return self._liveLinks(cItem)
        details = self._details(cItem)
        video = details.get("video") or {}
        if not isinstance(video, dict):
            return []
        subTracks = []
        for track in video.get("tracks") or []:
            subUrl = _s(track.get("file")) if isinstance(track, dict) else ""
            if self.cm.isValidUrl(subUrl):
                lang = _s(track.get("label")).lower() or "ar"
                subTracks.append({"title": _s(track.get("label")) or "AR", "url": subUrl, "lang": lang, "format": "vtt"})
        variants = []
        master = ""
        for src in ((video.get("sources") or {}).get("HLS") or []):
            if not isinstance(src, dict):
                continue
            link = _s(src.get("Link"))
            if not self.cm.isValidUrl(link):
                continue
            label = _s(src.get("Name"))
            height = re.search(r"(\d{3,4})p", label)
            if height:
                variants.append((int(height.group(1)), label, link))
            elif not master:
                master = link
        variants.sort(key=lambda x: -x[0])
        urltab = []
        seen = set()
        for _height, label, link in variants:
            if link not in seen:
                seen.add(link)
                urltab.append((label, link))
        if master and master not in seen:
            urltab.append(("Auto (HLS)", master))
        ret = []
        for label, link in urltab:
            meta = {"iptv_proto": "m3u8", "User-Agent": self.HEADER.get("User-Agent")}
            if subTracks:
                meta["external_sub_tracks"] = subTracks
            ret.append({"name": label, "url": self.up.decorateUrl(link, meta), "need_resolve": 0})
        return applySidecarToLinks(ret, buildSidecarFromItem(cItem, IsSidecarEnabled(), self._desc(details, True)))

    ###################################################
    # info / favourites
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("Asharq.getArticleContent [%s]" % cItem.get("url", ""))
        otherInfo = {}
        text = ""
        icon = cItem.get("icon", "")
        if cItem.get("category") == "aq_video":
            data = self._details(cItem)
        elif cItem.get("show_slug"):
            data = self._api("/shows/%s" % _q(cItem["show_slug"]))
            data = data if isinstance(data, dict) else {}
        else:
            data = {}
        if data:
            text = self._desc(data, True)
            icon = self._image(data, ("16-9", "2-3")) or icon
            video = data.get("video") or {}
            if isinstance(video, dict) and video.get("duration"):
                otherInfo["duration"] = _s(video.get("duration"))
            date = _s(data.get("publishedAt"))[:10]
            if date and data.get("type") != "show":
                otherInfo["released"] = date
            if data.get("totalEpisodes"):
                otherInfo["episodes"] = _s(data.get("totalEpisodes"))
            category = data.get("category") or {}
            if isinstance(category, dict) and category.get("name"):
                otherInfo["category"] = self.cleanHtmlStr(_s(category.get("name")))
            channel = data.get("channel") or (data.get("show") or {}).get("channel") or {}
            if isinstance(channel, dict) and channel.get("name"):
                otherInfo["station"] = self.cleanHtmlStr(_s(channel.get("name")))
            show = data.get("show") or {}
            if isinstance(show, dict) and show.get("title"):
                otherInfo["alternate_title"] = self.cleanHtmlStr(_s(show.get("title")))
            if (video.get("tracks") if isinstance(video, dict) else None):
                otherInfo["subtitles"] = "AR"
        text = text or cItem.get("desc", "").replace("[/br]", "\n")
        return [{"title": cItem.get("title", ""), "text": text,
                 "images": [{"title": "", "url": icon}] if icon else [],
                 "other_info": otherInfo}]

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("aq_type") or cItem.get("is_live"):
                fields = self.FAV_FIELDS + ("is_live",)
                return json_dumps(dict((key, cItem[key]) for key in fields if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("Asharq.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "aq_live":
            self.listLive(self.currItem)
        elif category == "aq_top":
            self.listTop(self.currItem)
        elif category == "aq_page":
            self.listPage(self.currItem)
        elif category == "aq_inline":
            self.listInline(self.currItem)
        elif category == "aq_component":
            self.listComponent(self.currItem)
        elif category == "aq_cats":
            self.listCategories(self.currItem)
        elif category == "aq_category":
            self.listCategory(self.currItem)
        elif category == "aq_show":
            self.listShow(self.currItem)
        elif category in ("aq_season", "aq_episodes"):
            self.listEpisodes(self.currItem)
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category"})
            self.listSearchResult(cItem, cItem.get("search_pattern") or searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc", _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):
    def __init__(self):
        CHostBase.__init__(self, Asharq(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("asharq")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("aq_video", "aq_show", "aq_season")
