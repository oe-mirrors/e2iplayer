# -*- coding: utf-8 -*-
# Last Modified: 03.10.2026 - brought to the current host standard
#   (iFilm Arabic, ar.ifilmtv.ir - originally by Mohamed Elsafty)
#   - live channels over http:// (the https certificate of live.presstv.ir is the one of
#     presstv.co.uk); every HLS variant offered, best first - the live master lists a
#     2 Mbps variant that answers 404, so live variants are checked before they are offered
#   - movies are VIDEO rows keyed on their /Film/Content/<id> page, the MP4 is read from the
#     page in getLinksForVideo; series/programs -> episode rows keyed on the content page
#     (+ ?ep=<n> / ?att=<id>), the HLS / MP4 address rides along in "media_url"
#   - series/movies paging from the site's item counter (First page / Jump / Next page),
#     programs, clips and artists paged through their JSON/page APIs
#   - watched flag, favourites, sidecar, INFO (site story/cast/poster + moviemeta), name
#     normalisation ("Title (Year)", "Show - SxxExx"), no colour codes in titles
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://ar.ifilmtv.ir/"


LIVE_URL = "http://live.presstv.ir/hls/"  # NOSONAR - the live HLS is served over plain http only
VOD_HLS = "https://vod.ifilmtv.ir/hls/%s%s/,%s,%s_320,.mp4.urlset/master.m3u8"
VIDEO_BASE = "https://video.ifilmtv.ir/ifilm/"
PER_PAGE = 18  # cards per page of /Series and /Film (the site's own divisor of its item counter)
JSON_PAGE = 30
TITLE_YEAR_RE = re.compile(r"^(.*?)\s*\(\s*((?:19|20)\d{2})\s*\)\s*$")
HTTP_HOSTS_RE = re.compile(r"^https://((?:ar|fa|fa2)\.ifilmtv\.ir)/", re.I)


class IFilmArabicHost(GenericFolderWatchedScraperMixin, CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "ifilmarabic", "cookie": "ifilmarabic.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = self._plainHttp(self.MAIN_URL + "img/colorize-logo-final.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.HEADER.update({"Referer": self.MAIN_URL, "Accept-Language": "ar-SA,ar;q=0.9,en;q=0.8"})
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({"X-Requested-With": "XMLHttpRequest", "Accept": "application/json, text/javascript, */*; q=0.01"})
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MENU = [
            {"category": "if_live", "title": _("Live")},
            {"category": "if_list", "title": _("Series"), "url": self.MAIN_URL + "Series"},
            {"category": "if_list", "title": _("Movies"), "url": self.MAIN_URL + "Film"},
            {"category": "if_programs", "title": _("Programmes")},
            {"category": "if_kids", "title": _("Children"), "url": self.MAIN_URL + "News/Tag?id=18379&page=1"},
            {"category": "if_clips", "title": _("Clips")},
            {"category": "if_artists_main", "title": _("Artists")},
        ] + self.searchItems()
        self.LIVE_STREAMS = [
            {"title": "iFilm Arabic", "url": LIVE_URL + "ifilmar.m3u8"},
            {"title": "iFilm Persian", "url": LIVE_URL + "ifilmfa.m3u8"},
            {"title": "iFilm 2 Persian", "url": LIVE_URL + "ifilm2.m3u8", "icon": "https://fa2.ifilmtv.ir/img/Logoifilm2.png"},
            {"title": "iFilm English", "url": LIVE_URL + "ifilmen.m3u8"},
        ]
        self.watchedHelper = IPTVWatchedHelper("ifilm")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(self._plainHttp(self._fullUrl(url)), addParams, post_data)

    @staticmethod
    def _plainHttp(url):
        # the *.ifilmtv.ir certificate expired on 02.10.2026 and a box with certificate checks on refuses it;
        # the site, its images and the MP4s (fa.ifilmtv.ir) are also served over plain http (no redirect), the
        # row urls themselves (watched / favourite keys) stay https. vod.ifilmtv.ir redirects http to https, so
        # the series HLS cannot avoid it.
        return HTTP_HOSTS_RE.sub(r"http://\1/", url or "")  # NOSONAR - expired certificate, see above

    def _iconUrl(self, url):
        return self._plainHttp(self._fullUrl(url))

    def getFullIconUrl(self, url, currUrl=None):
        # also covers icons stored in older favourites
        return self._plainHttp(CBaseHostClass.getFullIconUrl(self, url, currUrl))

    def getJson(self, url):
        params = dict(self.defaultParams)
        params["header"] = self.AJAX_HEADER
        sts, data = self.getPage(url, params)
        if not sts:
            return None
        try:
            return json_loads(data)
        except Exception:
            printExc()
        return None

    def _fullUrl(self, url):
        # the site links raw-Arabic paths and image names with spaces - one ASCII form
        url = (url or "").replace("&amp;", "&").strip()
        if not url:
            return ""
        if url.startswith("//"):
            url = "https:" + url
        url = self.getFullUrl(url)
        try:
            url = urllib_quote(urllib_unquote(url), safe=":/?&=#+,;@%")
        except Exception:
            printExc()
        return url

    @staticmethod
    def _contentId(url):
        # ("film"|"series"|"program", "<id>") of a content page url
        m = re.search(r"/(film|series|program)/Content/(\d+)", url or "", re.I)
        return (m.group(1).lower(), m.group(2)) if m else ("", "")

    def _contentUrl(self, kind, cid):
        return self.MAIN_URL + {"film": "Film", "series": "Series", "program": "Program"}.get(kind, "Series") + "/Content/" + cid

    @staticmethod
    def _splitYear(title):
        # "العقيق (2017)" / "المنافق(2021)" -> ("العقيق", "2017")
        title = re.sub(r"\s+", " ", title or "").strip()
        m = TITLE_YEAR_RE.match(title)
        if m and m.group(1).strip():
            return m.group(1).strip(), m.group(2)
        return title, ""

    def _dispTitle(self, title):
        if not IsMediaNamingNormalized():
            return title
        name, year = self._splitYear(title)
        return "%s (%s)" % (name, year) if year else name

    def _addContent(self, kind, cid, title, icon, desc=""):
        # one movie (VIDEO) or series/program (DIR) row
        name, year = self._splitYear(title)
        params = {"name": "category", "good_for_fav": True, "url": self._contentUrl(kind, cid), "icon": self._iconUrl(icon), "desc": desc,
                  "if_kind": kind, "if_id": cid, "s_title": name, "meta_title": name, "meta_year": year}
        if kind == "film":
            params.update({"category": "if_movie", "title": self._dispTitle(title), "meta_type": "movie"})
            self.addVideo(params)
        else:
            params.update({"category": "if_series", "title": self._dispTitle(title), "meta_type": "tv" if kind == "series" else ""})
            self.addDir(params)

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            category = cItem.get("category", "")
            if category in ("if_movie", "if_series"):
                return "%s:%s" % (cItem.get("if_kind", ""), cItem.get("if_id", "")) if cItem.get("if_id") else ""
            if category == "if_episode":
                return cItem.get("if_ep_key", "")
            if category == "if_clip":
                return "clip:%s" % cItem["if_id"] if cItem.get("if_id") else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listLive(self, cItem):
        for stream in self.LIVE_STREAMS:
            self.addVideo({"name": "category", "category": "if_live_video", "good_for_fav": True, "title": stream["title"], "url": stream["url"],
                           "icon": self._iconUrl(stream.get("icon", self.DEFAULT_ICON_URL)), "desc": _("Live"), "is_live": True})

    def listItems(self, cItem):
        # /Series and /Film cards ("content-all-film" block, 18 per page)
        page = int(cItem.get("page", 1) or 1)
        base = cItem.get("base_url") or cItem["url"].split("?")[0]
        tpl = base + "?order=1&page={page}"
        sts, data = self.getPage(tpl.format(page=page))
        if not sts:
            return
        block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="content-all-film">', '<ul id="pagination-demo"', False)[1] or data
        seen = set()
        for item in self.cm.ph.getAllItemsBeetwenMarkers(block, "<a ", "</a>"):
            kind, cid = self._contentId(self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0])
            if not cid or cid in seen:
                continue
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, "<h6>", "</h6>", False)[1])
            if not title:
                continue
            seen.add(cid)
            icon = self.cm.ph.getSearchGroups(item, r"""src=['"]?([^'">\s]+)""")[0]
            self._addContent(kind, cid, title, icon)
        total = self.cm.ph.getSearchGroups(data, r"Counter2\s*=\s*parseInt\((\d+)\)")[0]
        lastPage = (int(total) + PER_PAGE - 1) // PER_PAGE if total.isdigit() else 0
        params = dict(cItem, base_url=base)
        addPagingItems(self, params, page, bool(seen) and (page < lastPage if lastPage else len(seen) >= PER_PAGE), lastPage, tpl)

    def listPrograms(self, cItem):
        page = int(cItem.get("page", 1) or 1)
        tpl = self.MAIN_URL + "Home/PageingItem?category=7&page={page}&size=%d&orderby=1" % JSON_PAGE
        result = self.getJson(tpl.format(page=page))
        if not isinstance(result, list):
            return
        for item in result:
            cid = str(item.get("Id", "") or "")
            title = self.cleanHtmlStr(item.get("Title", "") or "")
            if cid and title:
                self._addContent("program", cid, title, item.get("ImageAddress_M", "") or item.get("ImageAddress_S", ""))
        addPagingItems(self, cItem, page, len(result) >= JSON_PAGE, 0, tpl)

    def listKids(self, cItem):
        # one page: the slider + the cards (page 2 of the tag page is empty on the site)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        seen = set()
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, "<a ", "</a>"):
            if "panel-inner-small" not in item and "Jashnvarh-slider-item" not in item:
                continue
            kind, cid = self._contentId(self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, "<h4>", "</h4>", False)[1])
            if not cid or cid in seen or not title:
                continue
            seen.add(cid)
            self._addContent(kind, cid, title, self.cm.ph.getSearchGroups(item, r"""src=['"]?([^'">\s]+)""")[0])

    def listClips(self, cItem):
        page = int(cItem.get("page", 1) or 1)
        tpl = self.MAIN_URL + "Music/GetTracksBy?type=15&size=%d&page={page}&id=" % JSON_PAGE
        result = self.getJson(tpl.format(page=page))
        if not isinstance(result, list):
            return
        for item in result:
            video = item.get("VideoAddress", "") or ""
            title = self.cleanHtmlStr(item.get("Caption", "") or item.get("Title", "") or "")
            if not video or not title:
                continue
            self.addVideo({"name": "category", "category": "if_clip", "good_for_fav": True, "title": title, "url": self._fullUrl(video),
                           "icon": self._iconUrl(item.get("ImageAddress_M", "")), "desc": self.cleanHtmlStr(item.get("Discription", "") or ""),
                           "if_id": str(item.get("Id", "") or "")})
        addPagingItems(self, cItem, page, len(result) >= JSON_PAGE, 0, tpl)

    def listArtistsMain(self, cItem):
        for kindId, title in (("1", _("Directors")), ("2", _("Actors"))):
            self.addDir(dict(cItem, category="if_artists", title=title, url=self.MAIN_URL + "artist/Index?id=%s&sort=0&page=1" % kindId, good_for_fav=True))

    def listArtists(self, cItem):
        page = int(cItem.get("page", 1) or 1)
        tpl = re.sub(r"page=\d+", "page={page}", cItem["url"])
        if "{page}" not in tpl:
            tpl += "&page={page}"
        sts, data = self.getPage(tpl.format(page=page))
        if not sts:
            return
        count = 0
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, '<a href="/artist/Content/', "</a>"):
            url = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, "<h3>", "</h3>", False)[1])
            if not url or not title:
                continue
            count += 1
            self.addDir({"name": "category", "category": "if_artist", "good_for_fav": True, "title": title, "url": self._fullUrl(url),
                         "icon": self._iconUrl(self.cm.ph.getSearchGroups(item, r'src="([^"]+)"')[0])})
        lastPage = self.cm.ph.getSearchGroups(data, r"totalPages:\s*(\d+)")[0]
        lastPage = int(lastPage) if lastPage.isdigit() else 0
        addPagingItems(self, cItem, page, count > 0 and page < lastPage, lastPage, tpl)

    def listArtist(self, cItem):
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        bio = self.cm.ph.getDataBeetwenMarkers(data, '<div id="wrapper"', "</div>", False)[1]
        bio = self.cleanHtmlStr(bio.replace("</p>", "[/br]"))
        works = self.cm.ph.getDataBeetwenMarkers(data, '<div class="artist-movies-panel">', "</footer>", False)[1]
        found = False
        for block, title in re.findall(r'<div class="panel-inner-movies">(.*?)<a class="neme-movie">([^<]*)</a>', works, re.S):
            kind, cid = self._contentId(self.cm.ph.getSearchGroups(block, r'href="([^"]+)"')[0])
            title = self.cleanHtmlStr(title)
            if not cid or not title:
                continue
            found = True
            self._addContent(kind, cid, title, self.cm.ph.getSearchGroups(block, r"""src=['"]?([^'">\s]+)""")[0], bio[:600])
        if not found:
            self.addMarker({"title": _("No matching entries found."), "desc": bio})

    def _seriesPage(self, cItem):
        url = self._contentUrl(cItem.get("if_kind", ""), cItem.get("if_id", "")) if cItem.get("if_id") else cItem.get("url", "").split("?")[0]
        sts, data = self.getPage(url)
        return url, (data if sts else "")

    def _siteInfo(self, data):
        story = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div id="wrapper"', "</div>", False)[1].replace("</p>", "[/br]"))
        story = re.sub(r"^>\s*", "", story).strip()
        if not story:
            story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r"""og:description['"] content=['"]([^'"]*)""")[0])
        poster = self.cm.ph.getSearchGroups(data, r"""og:image['"] content=['"]([^'"]+)""")[0]
        cast = []
        panel = self.cm.ph.getDataBeetwenMarkers(data, "Film-Artists-panel", "<footer", False)[1]
        for name in re.findall(r"<span>([^<]+)</span>", panel):
            name = self.cleanHtmlStr(name)
            if name and name not in cast:
                cast.append(name)
        return story, (self._fullUrl(poster) if poster else ""), cast

    def listEpisodes(self, cItem):
        # series / program page: trailer (series) + episodes (HLS by number, or the attachment API)
        url, data = self._seriesPage(cItem)
        if not data:
            return
        kind, cid = cItem.get("if_kind", ""), cItem.get("if_id", "")
        if not cid:
            kind, cid = self._contentId(url)
        show = cItem.get("s_title") or self._splitYear(cItem.get("title", ""))[0]
        story = self._siteInfo(data)[0]
        normalize = IsMediaNamingNormalized()
        page = int(cItem.get("page", 1) or 1)
        base = {"name": "category", "category": "if_episode", "good_for_fav": True, "s_title": show, "if_kind": kind, "if_id": cid,
                "meta_type": cItem.get("meta_type", ""), "meta_title": cItem.get("meta_title", show), "meta_year": cItem.get("meta_year", ""), "desc": story}

        trailer = self.cm.ph.getSearchGroups(data, r'<source[^>]+src="([^"]+\.mp4)"')[0]
        if trailer and page == 1 and kind == "series":
            self.addVideo(dict(base, title="%s - %s" % (show, _("Trailer")) if normalize else _("Trailer"), url=url + "?trailer=1",
                               media_url=self._fullUrl(trailer), icon=cItem.get("icon", ""), if_ep_key="trailer:%s" % cid))

        extra = self.cm.ph.getSearchGroups(data, r'var\s+extrafild\s*=\s*"([^"]*)"')[0]
        count = self.cm.ph.getSearchGroups(data, r"var\s+inter_\s*=\s*(\d+)")[0]
        lang = self.cm.ph.getSearchGroups(data, r'var\s+langE\s*=\s*"([^"]*)"')[0]
        if lang == "fa":
            lang = ""
        found = False
        if extra and count.isdigit() and int(count) > 0:
            for num in range(1, int(count) + 1):
                found = True
                self.addVideo(dict(base, title=("%s - %s" % (show, formatSxxExx(1, num))) if normalize else "%s %d" % (_("Episode"), num),
                                   url="%s?ep=%d" % (url, num), media_url=VOD_HLS % (lang, cid, num, num), s_episode=num,
                                   icon="https://preview.presstv.co.uk/ifilm/%s%s/%d.png" % (lang, cid, num),
                                   if_ep_key="ep:%s:%d" % (cid, num)))
        else:
            # programs have hundreds of episodes (newest first, paged); a series is listed whole, oldest first
            size = JSON_PAGE if kind == "program" else 500
            tpl = self.MAIN_URL + "Home/PageingAttachmentItem?id=%s&page={page}&size=%d" % (cid, size)
            result = self.getJson(tpl.format(page=page if kind == "program" else 1))
            result = result if isinstance(result, list) else []
            if kind != "program":
                try:
                    result.sort(key=lambda x: int(x.get("Episode", 0) or 0))
                except Exception:
                    printExc()
            seenNames = {}
            for item in result:
                video = item.get("VideoAddress", "") or ""
                attId = str(item.get("Id", "") or "")
                if not video or not attId:
                    continue
                num = str(item.get("Episode", "") or "")
                caption = self.cleanHtmlStr(item.get("Caption", "") or "")
                if normalize and num.isdigit():
                    title = "%s - %s" % (show, formatSxxExx(1, num))
                else:
                    title = ("%s %s" % (_("Episode"), num)) if num else (caption or show)
                if title in seenNames:
                    seenNames[title] += 1
                    title = "%s (%d)" % (title, seenNames[title])
                else:
                    seenNames[title] = 1
                found = True
                media = video if video.startswith("http") else VIDEO_BASE + video
                self.addVideo(dict(base, title=title, url="%s?att=%s" % (url, attId), media_url=self._fullUrl(media), s_episode=num,
                                   icon=self._iconUrl(item.get("ImageAddress_M", "")) or cItem.get("icon", ""),
                                   desc=self.cleanHtmlStr(item.get("Discription", "") or "") or story, if_ep_key="att:%s" % attId))
            if kind == "program":
                addPagingItems(self, cItem, page, len(result) >= size, 0, "")
        if not found and page == 1:
            self.addMarker({"title": _("No episodes available yet."), "desc": story})

    def listSearchResult(self, cItem, searchPattern, searchType):
        result = self.getJson(self.MAIN_URL + "Home/Search?searchstring=" + urllib_quote_plus(searchPattern))
        if not isinstance(result, list):
            return
        kinds = {3: "series", 5: "film", 7: "program"}
        seen = set()
        for item in result:
            kind = kinds.get(item.get("CategoryId", 0))
            cid = str(item.get("Id", "") or "")
            title = self.cleanHtmlStr(item.get("Title", "") or "")
            if not kind or not cid or not title or cid in seen:
                continue
            seen.add(cid)
            self._addContent(kind, cid, title, item.get("ImageAddress_M", "") or item.get("ImageAddress_S", ""))

    ###################################################
    # links
    ###################################################
    def _hlsLinks(self, url, label, checkVariants=False):
        meta = {"User-Agent": self.HEADER["User-Agent"], "Referer": self.MAIN_URL}
        links = []
        try:
            playlist = getDirectM3U8Playlist(strwithmeta(url, meta), checkExt=False, variantCheck=True, sortWithMaxBitrate=999999999)
        except Exception:
            printExc()
            playlist = []
        names = set()
        for item in playlist:
            if checkVariants and item.get("bitrate") != "unknown":
                # the live master lists variants that do not exist (404)
                sts, data = self.cm.getPage(item["url"], {"header": meta})
                if not sts or "#EXT" not in data:
                    printDBG("IFilm: variant not available [%s]" % item["url"])
                    continue
            height = item.get("height", 0) or 0
            try:
                kbps = int(item.get("bitrate", 0)) // 1000
            except Exception:
                kbps = 0
            name = "%s %dp" % (label, height) if height else ("%s %d kbps" % (label, kbps) if kbps else "%s HLS" % label)
            if name in names:
                name = "%s (%d kbps)" % (name, kbps)
            names.add(name)
            links.append({"name": name, "url": item["url"], "need_resolve": 0})
        return links

    def getLinksForVideo(self, cItem):
        printDBG("IFilm.getLinksForVideo [%s]" % cItem.get("url", ""))
        category = cItem.get("category", "")
        url = cItem.get("url", "")
        meta = {"User-Agent": self.HEADER["User-Agent"], "Referer": self.MAIN_URL}
        if category == "if_live_video" or url.startswith(LIVE_URL):
            return self._hlsLinks(url, "iFilm", True)
        story = ""
        media = cItem.get("media_url", "")
        if category == "if_movie" or (not media and "/Film/Content/" in url):
            sts, data = self.getPage(url)
            if not sts:
                return []
            story = self._siteInfo(data)[0]
            media = self.cm.ph.getSearchGroups(data, r'<source[^>]+src="([^"]+)"')[0] or self.cm.ph.getSearchGroups(data, r"""og:video['"] content=['"]([^'"]+)""")[0]
            media = self._fullUrl(media) if media else ""
        elif not media:
            if category == "if_clip":
                media = url
            else:
                # an old favourite without media_url: rebuild the HLS address of a numbered episode
                epNum = self.cm.ph.getSearchGroups(url, r"[?&]ep=(\d+)")[0]
                _kind, cid = self._contentId(url)
                if epNum and cid:
                    media = VOD_HLS % ("ar", cid, epNum, epNum)
        if not media:
            return []
        if ".m3u8" in media:
            links = self._hlsLinks(media, "iFilm")
        else:
            links = [{"name": "iFilm MP4", "url": strwithmeta(self._plainHttp(media), meta), "need_resolve": 0}]
        return applySidecarToLinks(links, buildSidecarFromItem(cItem, IsSidecarEnabled(), story))

    def getVideoLinks(self, videoUrl):
        printDBG("IFilm.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecarFromUrlMeta(videoUrl, IsSidecarEnabled()))
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("IFilm.getArticleContent [%s]" % cItem.get("url", ""))
        meta = {}
        if cItem.get("meta_type") and cItem.get("meta_title"):
            try:
                meta = getMeta(cItem["meta_type"], cItem["meta_title"], cItem.get("meta_year", ""))
            except Exception:
                printExc()
        story, poster, info = "", "", {}
        data = self._seriesPage(cItem)[1]
        if data:
            story, poster, cast = self._siteInfo(data)
            if cast:
                info["actors"] = ", ".join(cast[:8])
        if cItem.get("meta_year"):
            info["year"] = cItem["meta_year"]
        info.update(meta.get("info", {}))
        plot = meta.get("plot", "")
        text = plot or story or cItem.get("desc", "")
        if plot and story and story != plot:
            text = "%s[/br][/br]%s" % (plot, story)
        icon = meta.get("poster") or poster or cItem.get("icon", "")
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": self._plainHttp(icon)}] if icon else [], "other_info": info}]

    ###################################################
    # service
    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("IFilm.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "if_live":
            self.listLive(self.currItem)
        elif category == "if_list":
            self.listItems(self.currItem)
        elif category == "if_programs":
            self.listPrograms(self.currItem)
        elif category == "if_kids":
            self.listKids(self.currItem)
        elif category == "if_clips":
            self.listClips(self.currItem)
        elif category == "if_artists_main":
            self.listArtistsMain(self.currItem)
        elif category == "if_artists":
            self.listArtists(self.currItem)
        elif category == "if_artist":
            self.listArtist(self.currItem)
        elif category == "if_series":
            self.listEpisodes(self.currItem)
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category"})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc")
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, IFilmArabicHost(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("ifilm")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("if_movie", "if_series", "if_episode")
