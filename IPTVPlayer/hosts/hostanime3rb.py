# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# Coding: BY MOHAMED_OS
# 08.10.2026 - ported to the python3 framework / host standard
#   - Anime3rb (anime3rb.com, Arabic-subtitled anime, Laravel/Livewire site): latest episodes, anime list, TV
#     series, movies, OVA, ONA, specials, genres and search; the lists come from the page's schema.org
#     ItemList (ld+json), First page / Jump / Next page over ?page=N
#   - Cloudflare challenges every request there (curl-impersonate included, 08.10.2026): pages go through
#     getPageCFProtection (MyE2i solve on the box), covers (images.anime3rb.com) get the same cf_clearance cookie
#     and the User-Agent that passed the check
#   - title -> episodes (VIDEO rows keyed on the episode page url, local paging over 100); a movie is one VIDEO
#     row; links: the episode's video objects (one per subtitle group) -> signed /embed (302) -> the site's own
#     player on video.vid3rb.com (repeated query keys dropped, it answers 403 otherwise), its MP4 qualities
#     (video_sources, premium ones left out) are played directly, best first
#   - watched flag (title -> episode), downloaded flag, favourites, name normalisation ("Title (Year)",
#     "Show - SxxExx", the season taken from "2nd Season" / "Season 2" in the title), sidecar, INFO via moviemeta
#     + the title page's ld+json and info table
# 09.10.2026 - covers: the first usable candidate (ld+json image string / list / ImageObject, card img
#     data-src / src / srcset), empty values, data: URIs and template leftovers skipped
import os
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.botprotection import remembered_user_agent
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import LATIN_ONLY, getMeta, isLatinTitle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://anime3rb.com/"


LOCAL_PAGE_SIZE = 100
LDJSON_RE = re.compile(r'(?s)<script type="application/ld\+json">(.*?)</script>')
# " - Anime3rb أنمي عرب" behind every name of the structured data
SITE_TAIL_RE = re.compile(r"\s+-\s+Anime3rb.*$")
EPISODE_RE = re.compile(r"الحلقة\s*(\d+)")
# "Kingdom 6th Season" / "Spy x Family Season 3": the season number for the episode names
SEASON_RE = re.compile(r"(?i)[\s:-]*(?:(\d+)(?:st|nd|rd|th) season|season ?(\d+))\b")
# episode list of a title page: <a href=".../episode/<slug>/<n>" ...> .. <div class="video-data"> .. </a>
EPISODE_LINK_RE = re.compile(r'(?s)<a\s+href="(https?://[^"]+/episode/[^"]+/\d+)"[^>]*>(.*?)</a>')
# the player's sources: {src: '...mp4', type: 'video/mp4', label: '720p', res: '720'}
VIDEO_SOURCES_RE = re.compile(r"var video_sources = (\[\{.*?\}\]);")
SOURCE_RE = re.compile(r"""(?s)src:\s*['"]([^'"]+)['"]\s*,\s*type:\s*['"]([^'"]*)['"]\s*,\s*label:\s*['"]([^'"]*)['"](?:\s*,\s*res:\s*['"]?(\d+))?""")
VIDEO_URL_RE = re.compile(r"&quot;video_url&quot;:&quot;(https?:[^&]+?(?:&amp;[^&]+?)*)&quot;")
# info table rows of a title page
TABLE_KEYS = (("status", "الحالة"), ("released", "إصدار"), ("production", "الاستديو"), ("director", "المخرج"))
VIDEO_CATEGORIES = ("r3_video",)
FOLDER_CATEGORIES = ("r3_show",)


def _splitSeason(name):
    # "Jigokuraku 2nd Season" -> ("Jigokuraku", 2); no season word -> (name, 1)
    match = SEASON_RE.search(name or "")
    if not match:
        return name, 1
    base = (name[:match.start()] + name[match.end():]).strip(" :-")
    return (base or name), int(match.group(1) or match.group(2))


def _siteName(name):
    return SITE_TAIL_RE.sub("", name or "").strip()


def _cover(candidates):
    # first usable cover of the candidates (ld+json "image" as string, list or ImageObject, or the img
    # attributes of a card); empty values, data: URIs and template leftovers ("#", "{{", "${") are skipped
    if not isinstance(candidates, (list, tuple)):
        candidates = [candidates]
    for value in candidates:
        if isinstance(value, dict):
            value = value.get("url") or value.get("contentUrl") or ""
        if isinstance(value, (list, tuple)):
            value = _cover(value)
        value = value.strip().replace("&amp;", "&") if hasattr(value, "strip") else ""
        if value and not value.startswith("data:") and not any(mark in value for mark in ("#", "{{", "${")):
            return value
    return ""


def _imgCover(body):
    # cover of a card: lazy-load attributes first, then src, then the first srcset entry
    img = re.search(r"(?s)<img\b[^>]*>", body or "")
    if not img:
        return ""
    tag = img.group(0)
    candidates = []
    for attr in ("data-src", "data-lazy-src", "src"):
        match = re.search(r'\s%s="([^"]*)"' % attr, tag)
        if match:
            candidates.append(match.group(1))
    srcset = re.search(r'\s(?:data-)?srcset="([^"]*)"', tag)
    if srcset:
        candidates.append(srcset.group(1).split(",")[0].strip().split(" ")[0])
    return _cover(candidates)


class Anime3rb(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode",
                  "show_url", "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "anime3rb", "cookie": "anime3rb.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/anime3rb135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("anime3rb")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        sts, data = self.cm.getPageCFProtection(self.getFullUrl((baseUrl or "").replace("&amp;", "&")), addParams, post_data)
        if not sts:
            # otherwise the list just stays empty: the site's rate limit (HTTP 429 "طلبات كثيرة جدًا", seen on the
            # search after a few quick requests) or a Cloudflare check that was not solved
            meta = getattr(data, "meta", None) or {}
            if meta.get("status_code") == 429 or (isinstance(data, str) and "طلبات كثيرة جدًا" in data):
                SetIPTVPlayerLastHostError(_("Too many requests. Please try again later."))
            else:
                SetIPTVPlayerLastHostError(_("The site's browser check could not be passed."))
        return sts, data

    def _path(self, url):
        # domain independent identity of a page
        return re.sub(r"^https?://[^/]+", "", url or "").split("?")[0].rstrip("/").lower()

    def _cfMeta(self):
        # cf_clearance + the User-Agent that passed the check, for downloads outside getPage (covers)
        meta = {"Referer": self.MAIN_URL}
        try:
            # getCookieHeader logs a traceback for a cookie file that does not exist yet
            cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE, ["cf_clearance"]).rstrip("; ") if os.path.isfile(self.COOKIE_FILE) else ""
            if cookieHeader:
                meta.update({"User-Agent": remembered_user_agent(self.COOKIE_FILE) or self.HEADER.get("User-Agent"), "Cookie": cookieHeader})
        except Exception:
            printExc()
        return meta

    def getFullIconUrl(self, url, currUrl=None):
        # the covers (anime3rb.com/storage, images.anime3rb.com) sit behind the same Cloudflare check as the pages
        url = CBaseHostClass.getFullIconUrl(self, url, currUrl)
        if not url.startswith("http") or not self.up.getDomain(url).endswith("anime3rb.com"):
            return url
        return strwithmeta(url, self._cfMeta())

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in VIDEO_CATEGORIES + FOLDER_CATEGORIES + ("r3_list",):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            path = self._path(cItem.get("url", ""))
            if not path:
                return ""
            category = cItem.get("category", "")
            if category in VIDEO_CATEGORIES:
                return "video:%s" % path
            if category in FOLDER_CATEGORIES:
                return "folder:%s" % path
        except Exception:
            printExc()
        return ""

    @staticmethod
    def _episodeTitle(show, season, episode, label):
        if IsMediaNamingNormalized() and episode:
            return "%s - %s" % (show, formatSxxExx(season or 1, episode))
        return label

    def _ldJson(self, data, kind=None):
        # the schema.org objects of a page (the first of that @type when kind is given)
        found = []
        for block in LDJSON_RE.findall(data or ""):
            try:
                obj = json_loads(block)
            except Exception:
                printExc()
                continue
            if kind is None or obj.get("@type") == kind:
                found.append(obj)
        if kind is None:
            return found
        return found[0] if found else {}

    @staticmethod
    def _pageUrl(baseUrl, page):
        return baseUrl if page <= 1 else "%s%spage=%d" % (baseUrl, "&" if "?" in baseUrl else "?", page)

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self):
        menu = [
            {"category": "r3_latest", "title": _("Latest episodes"), "url": self.getMainUrl()},
            {"category": "r3_list", "title": _("Anime list"), "url": self.getFullUrl("/titles/list")},
            {"category": "r3_list", "title": _("Series"), "url": self.getFullUrl("/titles/list/tv")},
            {"category": "r3_list", "title": _("Movies"), "url": self.getFullUrl("/titles/list/movie")},
            {"category": "r3_list", "title": "OVA", "url": self.getFullUrl("/titles/list/ova")},
            {"category": "r3_list", "title": "ONA", "url": self.getFullUrl("/titles/list/ona")},
            {"category": "r3_list", "title": _("Specials"), "url": self.getFullUrl("/titles/list/special")},
            {"category": "r3_genres", "title": _("Genres"), "url": self.getFullUrl("/titles/list")},
        ]
        self.listsTab(menu + self.searchItems(), {"name": "category"})

    def listGenres(self, cItem):
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        seen = set()
        for href, label in re.findall(r'(?s)<a\s+href="(https?://[^"]+/genre/[^"]+)"[^>]*>(.*?)</a>', data):
            if href in seen:
                continue
            seen.add(href)
            count = self.cm.ph.getSearchGroups(label, r'(?s)<span class="badge">\s*(\d+)')[0]
            title = self.cleanHtmlStr(re.sub(r"(?s)<span.*?</span>", "", label))
            if title:
                self.addDir({"name": "category", "category": "r3_list", "good_for_fav": True, "title": title, "url": href,
                             "desc": "%s: %s" % (_("Titles"), count) if count else ""})

    def _addTitle(self, entry):
        # one ItemList entry -> title folder, or a VIDEO row for a movie with one episode
        url = entry.get("url", "")
        name = _siteName(entry.get("name", ""))
        if not url or not name:
            return False
        kind = entry.get("@type", "")
        year = self.cm.ph.getSearchGroups(entry.get("datePublished", ""), r"((?:19|20)\d{2})")[0]
        rating = (entry.get("aggregateRating") or {}).get("ratingValue", "")
        genres = entry.get("genre") or []
        genres = ", ".join(genres) if isinstance(genres, list) else str(genres)
        episodes = entry.get("numberOfEpisodes", "")
        fields = " | ".join("%s: %s" % (label, value) for label, value in ((_("Year"), year), (_("Rating"), rating), (_("Episodes"), episodes), (_("Genre"), genres)) if value)
        story = entry.get("description", "")
        desc = "%s[/br]%s" % (fields, story) if fields and story else (fields or story)
        show, season = _splitSeason(name)
        icon = _cover(entry.get("image"))
        self.addDir({"name": "category", "category": "r3_show", "good_for_fav": True, "url": url, "title": name, "desc": desc,
                     "icon": self.getFullIconUrl(icon) if icon else "", "s_title": show, "s_season": season,
                     "meta_type": "movie" if kind == "Movie" else "tv", "meta_title": show, "meta_year": year})
        return True

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or cItem["url"]
        url = self._pageUrl(baseUrl, page)
        printDBG("Anime3rb.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        listObj = self._ldJson(data, "ItemList")
        count = 0
        for element in listObj.get("itemListElement") or []:
            if self._addTitle((element or {}).get("item") or {}):
                count += 1
        hasNext = bool(count) and bool((listObj.get("potentialAction") or {}).get("target"))
        listItem = dict(cItem, base_url=baseUrl, url=baseUrl)
        pageTpl = baseUrl.replace("{", "{{").replace("}", "}}") + ("&" if "?" in baseUrl else "?") + "page={page}"
        addPagingItems(self, listItem, page, hasNext, 0, pageTpl)

    def listLatest(self, cItem):
        # video cards of the home page: show, episode number, episode page
        page = cItem.get("page", 1)
        url = self._pageUrl(self.getMainUrl(), page)
        printDBG("Anime3rb.listLatest [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        seen = set()
        # the "latest episodes" grid (id="videos"); the pinned-anime slider above it repeats on every page
        grid = data.split('id="videos"', 1)[-1]
        for href, body in re.findall(r'(?s)<a\s+href="([^"]+/episode/[^"]+)"\s+class="[^"]*video-card[^"]*">(.*?)</a>', grid):
            show = self.cleanHtmlStr(self.cm.ph.getSearchGroups(body, r'(?s)<h3 class="title-name"[^>]*>(.*?)</h3>')[0])
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(body, r'(?s)<p class="number">(.*?)</p>')[0])
            if not show or href in seen:
                continue
            seen.add(href)
            number = EPISODE_RE.search(label) or re.search(r"/(\d+)$", href)
            episode = number.group(1) if number else ""
            name, season = _splitSeason(show)
            icon = _imgCover(body)
            self.addVideo({"name": "category", "category": "r3_video", "good_for_fav": True, "url": href,
                           "title": self._episodeTitle(name, season, episode, "%s - %s" % (show, label) if label else show),
                           "icon": self.getFullIconUrl(icon) if icon else "", "desc": label, "s_title": name, "s_season": season,
                           "s_episode": episode, "meta_type": "tv", "meta_title": name,
                           "show_url": self.getFullUrl("/titles/%s" % href.rstrip("/").split("/")[-2])})
        hasNext = bool(seen) and ("page=%d" % (page + 1)) in data
        addPagingItems(self, dict(cItem), page, hasNext, 0, self.getMainUrl() + "?page={page}")

    def listShow(self, cItem):
        # title page: the episode list (a movie with one episode -> one VIDEO row "Title (Year)")
        printDBG("Anime3rb.listShow [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        show = cItem.get("s_title") or _splitSeason(cItem.get("title", ""))[0]
        season = cItem.get("s_season", 1)
        episodes, seen = [], set()
        for href, body in EPISODE_LINK_RE.findall(data):
            if href in seen or 'class="video-data"' not in body:
                continue
            seen.add(href)
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(body, r"(?s)<span>(.*?)</span>")[0])
            subtitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(body, r'(?s)<p class="font-light[^"]*">(.*?)</p>')[0])
            duration = self.cleanHtmlStr(self.cm.ph.getSearchGroups(body, r"(?s)<span class=\"rounded[^\"]*\">(.*?)</span>")[0])
            number = EPISODE_RE.search(label) or re.search(r"/(\d+)$", href)
            icon = _imgCover(body)
            episodes.append((int(number.group(1)) if number else len(episodes) + 1, href, label, subtitle, duration, icon))
        if not episodes:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return
        episodes.sort(key=lambda e: e[0])
        # the heading carries the kind: "<span dir="ltr">Name</span> <span ..>( فيلم )</span>"
        heading = self.cm.ph.getSearchGroups(data, r"(?s)<h1[^>]*>(.*?)</h1>")[0]
        if (cItem.get("meta_type") == "movie" or "فيلم" in heading) and len(episodes) == 1:
            year = cItem.get("meta_year", "")
            withYear = year and IsMediaNamingNormalized()
            params = stripPagerKeys(dict(cItem))
            params.update({"category": "r3_video", "url": episodes[0][1], "title": "%s (%s)" % (show, year) if withYear else cItem.get("title", show),
                           "show_url": cItem["url"], "meta_type": "movie"})
            self.addVideo(params)
            return
        page = cItem.get("page", 1)
        start = (page - 1) * LOCAL_PAGE_SIZE
        for episode, href, label, subtitle, duration, icon in episodes[start:start + LOCAL_PAGE_SIZE]:
            rawTitle = "%s - %s" % (cItem.get("title", show), label or episode)
            if subtitle:
                rawTitle = "%s - %s" % (rawTitle, subtitle)
            self.addVideo({"name": "category", "category": "r3_video", "good_for_fav": True, "url": href,
                           "title": self._episodeTitle(show, season, episode, rawTitle), "icon": self.getFullIconUrl(icon) if icon else cItem.get("icon", ""),
                           "desc": " | ".join(x for x in (subtitle, duration) if x), "show_url": cItem["url"], "s_title": show,
                           "s_season": season, "s_episode": str(episode), "meta_type": "tv", "meta_title": cItem.get("meta_title", show)})
        if len(episodes) > LOCAL_PAGE_SIZE:
            lastPage = (len(episodes) + LOCAL_PAGE_SIZE - 1) // LOCAL_PAGE_SIZE
            addPagingItems(self, dict(cItem), page, page < lastPage, lastPage)

    def listSearchResult(self, cItem, searchPattern, searchType):
        pattern = cItem.get("s_pattern") or searchPattern.strip()
        printDBG("Anime3rb.listSearchResult [%s]" % pattern)
        cItem = dict(cItem)
        base = self.getFullUrl("/search?q=%s" % urllib_quote_plus(pattern))
        cItem.update({"category": "r3_list", "s_pattern": pattern, "url": base, "base_url": base})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        url = cItem.get("url", "")
        printDBG("Anime3rb.getLinksForVideo [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return []
        episode = self._ldJson(data, "Episode")
        urltab, seen = [], set()
        for video in episode.get("video") or []:
            embed = (video or {}).get("embedUrl", "").replace("&amp;", "&")
            if not self.cm.isValidUrl(embed) or embed in seen:
                continue
            seen.add(embed)
            # "<show> الحلقة 7 بترجمة Crunchyroll - Anime3rb ..." -> "بترجمة Crunchyroll"
            group = self.cm.ph.getSearchGroups(_siteName(video.get("name", "")), r"(بترجمة.*)$")[0].strip()
            urltab.append({"name": "Anime3rb - %s" % group if group else "Anime3rb", "url": strwithmeta(embed, {"Referer": url}), "need_resolve": 1})
        if not urltab:
            # the default player of the page (Livewire state)
            player = VIDEO_URL_RE.search(data)
            if player:
                link = player.group(1).replace("\\/", "/").replace("&amp;", "&")
                urltab.append({"name": "Anime3rb", "url": strwithmeta(link, {"Referer": url}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def _playerSources(self, data, referer):
        # MP4 qualities of the vid3rb player page, best first: "var video_sources = [{src, type, label, res,
        # premium}]" (08.10.2026), older players wrote "{src: '..', type: '..', label: '..', res: '..'}"
        sources = []
        for block in VIDEO_SOURCES_RE.findall(data or ""):
            try:
                sources.extend(s for s in json_loads(block) if isinstance(s, dict))
            except Exception:
                printExc()
        if not sources:
            sources = [{"src": src, "type": mime, "label": label, "res": res} for src, mime, label, res in SOURCE_RE.findall(data or "")]
        header = {"Referer": referer, "User-Agent": self.HEADER.get("User-Agent")}
        links = []
        for source in sources:
            src = str(source.get("src") or "").replace("\\/", "/").replace("&amp;", "&")
            if source.get("premium") or not self.cm.isValidUrl(src):
                continue  # premium: only for the site's paying members
            res = str(source.get("res") or "")
            links.append((int(res) if res.isdigit() else 0, {"name": source.get("label") or source.get("type", ""), "url": strwithmeta(src, header)}))
        links.sort(key=lambda x: -x[0])
        return [link for _res, link in links]

    def _embedTarget(self, embedUrl, referer):
        # the signed embed url of the site (Cloudflare) answers a 302 to the vid3rb player and repeats its own
        # expires/signature behind the player's query - the player refuses that (403): first value of each key only
        params = dict(self.defaultParams, header=dict(self.HEADER, Referer=referer), no_redirection=True)
        sts, data = self.getPage(embedUrl, params)
        if not sts:
            return ""
        target = self.cm.meta.get("location", "") or \
            self.cm.ph.getSearchGroups(data, r"""http-equiv="refresh"\s+content="0;\s*url='([^']+)'""")[0] or \
            self.cm.ph.getSearchGroups(data, r"""<iframe[^>]+src=['"]([^'"]+)['"]""")[0]
        target = target.replace("&amp;", "&")
        if "?" not in target:
            return target
        base, query = target.split("?", 1)
        seen, kept = set(), []
        for part in query.split("&"):
            key = part.split("=", 1)[0]
            if part and key not in seen:
                seen.add(key)
                kept.append(part)
        return "%s?%s" % (base, "&".join(kept))

    def getVideoLinks(self, videoUrl):
        printDBG("Anime3rb.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        referer = strwithmeta(videoUrl).meta.get("Referer", self.MAIN_URL)
        playerUrl = str(videoUrl)
        if self.up.getDomain(playerUrl).endswith("anime3rb.com"):
            playerUrl = self._embedTarget(playerUrl, referer)
            if not self.cm.isValidUrl(playerUrl):
                return []
        sts, data = self.cm.getPage(playerUrl, {"header": dict(self.HEADER, Referer=self.MAIN_URL)})
        if not sts:
            return []
        links = self._playerSources(data, "https://%s/" % self.up.getDomain(playerUrl))
        if not links:
            links = self.up.getVideoLinkExt(playerUrl)
        return decorateResolvedLinkItems(links, sidecar)

    ###################################################
    # INFO
    ###################################################
    def _siteInfo(self, data):
        # (story, poster, {INFO fields}) of a title page
        obj = {}
        for candidate in self._ldJson(data):
            if candidate.get("@type") in ("TVSeries", "Movie", "Episode") and candidate.get("description"):
                obj = candidate
                break
        info = {}
        genres = obj.get("genre") or []
        genres = ", ".join(genres) if isinstance(genres, list) else str(genres)
        if genres:
            info["genres"] = genres
        if obj.get("numberOfEpisodes"):
            info["episodes"] = str(obj["numberOfEpisodes"])
        rating = (obj.get("aggregateRating") or {}).get("ratingValue", "")
        if rating:
            info["rating"] = str(rating)
        year = self.cm.ph.getSearchGroups(obj.get("datePublished", ""), r"((?:19|20)\d{2})")[0]
        if year:
            info["year"] = year
        for key, label in TABLE_KEYS:
            value = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<td class="px-6 py-2">\s*%s:?\s*</td>\s*<td[^>]*>(.*?)</td>' % label)[0])
            if value:
                info[key] = value
        age = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)>\s*التصنيف العمري\s*</p>\s*<p[^>]*>(.*?)</p>')[0])
        if age:
            info["age_limit"] = age
        poster = _cover(obj.get("image"))
        return obj.get("description", ""), poster, info

    def getArticleContent(self, cItem):
        printDBG("Anime3rb.getArticleContent [%s]" % cItem.get("url", ""))
        story, poster, info = "", "", {}
        sts, data = self.getPage(cItem.get("show_url") or cItem.get("url", ""))
        if sts:
            story, poster, info = self._siteInfo(data)
        mediaType = cItem.get("meta_type") or "tv"
        title = cItem.get("meta_title") or cItem.get("s_title") or cItem.get("title", "")
        meta = {}
        try:
            meta = getMeta(mediaType, title, cItem.get("meta_year") or info.get("year", ""), () if isLatinTitle(title) else LATIN_ONLY)
        except Exception:
            printExc()
        siteInfo = dict(info)
        info.update(meta.get("info", {}))
        info.update(dict((k, v) for k, v in siteInfo.items() if k in ("episodes", "status", "production")))
        plot = meta.get("plot", "")
        text = story or plot or cItem.get("desc", "")
        if plot and story and plot != story:
            text = "%s[/br][/br]%s" % (story, plot)
        icon = (self.getFullIconUrl(poster) if poster else "") or meta.get("poster") or cItem.get("icon", "")
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": info}]

    ###################################################
    # service
    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("Anime3rb.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu()
        elif category == "r3_list":
            self.listItems(self.currItem)
        elif category == "r3_latest":
            self.listLatest(self.currItem)
        elif category == "r3_genres":
            self.listGenres(self.currItem)
        elif category == "r3_show":
            self.listShow(self.currItem)
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
        CHostBase.__init__(self, Anime3rb(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("anime3rb")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in VIDEO_CATEGORIES + FOLDER_CATEGORIES
