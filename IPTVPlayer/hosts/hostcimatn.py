# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# CimaTN (سيما تونس, www.cimatn.com): Blogger site with Tunisian films and series (Ramadan series up to 2026)
#   - catalogue from the Blogger JSON feeds: "Latest", Tunisian films, Tunisian series, Ramadan series, short
#     films and search, First page / Jump / Next page (count from openSearch$totalResults)
#   - a film post only carries the trailer; the film itself is a Blogger page - on cimatn.com or on one of the
#     site's helper blogs (cimatunisaaaa / cimatnwatchingg.blogspot.com) - found like the site's own script
#     does it: the page whose slug matches the post (pageUrl.includes(...) / the post slug)
#   - a series post -> folder; its episodes are the pages "<slug>-ep-N" (epSlugBase / baseLink / episodeSlug /
#     watchPageSlug of the post) or one page with all episodes (seriesData.episodes)
#   - links: the page's server list (vkvideo, YouTube, ok.ru, uqload, dailymotion ...) handed to urlparser;
#     films that the site only offers on the paid artify.tn platform or on Telegram have the trailer only
#   - watched flag (series -> episode), downloaded flag, favourites, name normalisation ("Title (Year)",
#     "Show - SxxExx"), sidecar, INFO via moviemeta (Latin title) + the post's story/cast/poster
import re
import sys

from Components.config import ConfigSelection, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import GetAlternativeProxyChoices, GetAlternativeProxyUrl, IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import LATIN_ONLY, getMeta, isLatinTitle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts, GetIconDir, E2ColoR, StripColorCodes
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.cimatn_proxy = ConfigSelection(default="None", choices=GetAlternativeProxyChoices())


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.cimatn_proxy))
    return optionList
###################################################


def gettytul():
    return "https://www.cimatn.com/"


PER_PAGE = 24
LABEL_FILMS = "أفلام تونسية"
LABEL_SERIES = "مسلسلات تونسية"
LABEL_RAMADAN = "مسلسلات رمضان"
LABEL_SHORT = "أفلام قصيرة"
SERIES_LABELS = (LABEL_SERIES, LABEL_RAMADAN)
# the JS variables of a post that name the Blogger page(s) with the video
VAR_HINT_RE = re.compile(r"""(?:epSlugBase|episodeSlug|baseLink|watchPageSlug)\s*[:=]\s*[`"']([^`"'$]{2,80})[`"']""")
INCLUDES_HINT_RE = re.compile(r"""pageUrl\.includes\(\s*[`"']([^`"'$]{2,80})[`"']""")
FEED_HOST_RE = re.compile(r"https?://([a-z0-9.-]+)/feeds/pages")
PAGE_LINK_RE = re.compile(r"""["'](?:https?://www\.cimatn\.com)?/p/([a-z0-9_-]+)\.html["']""")
FIRST_EPISODE_RE = re.compile(r"(?<=-)1(?:_\d+)?$")
EPISODE_REST_RE = re.compile(r"-?(\d+)(?:_\d+)?$")
EPISODE_TAIL_RE = re.compile(r"-(?:ep|episode)-(\d+)(?:_\d+)?$")
GENERIC_HINTS = ("waiting", "watch-options", "episode", "ep-")
# the left-to-right mark some titles end with (U+200E, "Film El Naffoura" + LRM); py2 strings are utf-8 bytes
LRM = "\xe2\x80\x8e" if sys.version_info[0] < 3 else chr(0x200E)
SERVER_URL_RE = re.compile(r"""url\s*:\s*["']((?:https?:)?//[^"'$]+)["']""")
TAG_IFRAME_RE = re.compile(r"<iframe\s([^>]*)>")
SRC_RE = re.compile(r"""src=["']([^"'$]+)["']""")
YEAR_LABEL_RE = re.compile(r"^(?:19|20)\d{2}$")
ASCII_LETTER_RE = re.compile(r"[A-Za-z]")
KIND_WORDS_RE = re.compile(r"(?i)(?:^|\s)(?:film|serie|série|sitcom|complet|فيلم|مسلسل|سلسلة|سيتكوم|تونسي|كامل|الرعب)(?=\s|$)")
SEASON_RE = re.compile(r"(?i)(?:\bS(\d+)\b|الجزء\s+(الأول|الاول|الثاني|الثالث))")
SEASON_WORDS = {"الأول": 1, "الاول": 1, "الثاني": 2, "الثالث": 3}
# not playable here: the paid platform, Telegram, ad redirects, dead uploads
SKIP_HOSTERS = ("artify.tn", "t.me/", "listeamed.net", "player.mediadelivery.net", "app.videas.fr", "up-4ever", "mega.nz", "youtube.com/embed/example")


def _slug(url):
    # "https://www.cimatn.com/p/accident-ep-1.html" -> "accident-ep-1"
    return (url or "").rstrip("/").rsplit("/", 1)[-1].split("?", 1)[0].rsplit(".html", 1)[0].lower()


class CimaTN(GenericFolderWatchedScraperMixin, CBaseHostClass):
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "post_id", "page_host", "page_id", "episode",
                  "s_title", "s_season", "s_episode", "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "cimatn", "cookie": "cimatn.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/cimatn135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.pagesCache = {}
        self.watchedHelper = IPTVWatchedHelper("cimatn")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getProxy(self):
        return GetAlternativeProxyUrl(config.plugins.iptvplayer.cimatn_proxy.value) or None

    def _params(self, extra=None):
        params = dict(self.defaultParams)
        if extra:
            params.update(extra)
        proxy = self.getProxy()
        if proxy and "http_proxy" not in params:
            params = MergeDicts(params, {"http_proxy": proxy})
        return params

    def _json(self, url):
        sts, data = self.cm.getPage(url, self._params())
        if not sts:
            return {}
        try:
            return json_loads(data)
        except Exception:
            printExc()
        return {}

    def getFullIconUrl(self, url, currUrl=None):
        url = CBaseHostClass.getFullIconUrl(self, (url or "").strip(), currUrl)
        proxy = self.getProxy()
        if url and proxy:
            url = strwithmeta(url, {"iptv_http_proxy": proxy})
        return url

    @staticmethod
    def _entryId(entry):
        # "tag:blogger.com,1999:blog-1035...page-6901..." -> "6901..."
        return (entry.get("id") or {}).get("$t", "").rsplit("-", 1)[-1]

    @staticmethod
    def _entryLink(entry):
        for link in entry.get("link", []):
            if link.get("rel") == "alternate":
                return link.get("href", "")
        return ""

    def _names(self, title):
        # "فيلم سامحني Film Samhani" -> ("سامحني Samhani", "Samhani")
        name = re.sub(r"\s+", " ", KIND_WORDS_RE.sub(" ", title)).strip(" -:|")
        # words with a Latin letter ("Arriére el goddem 2") - the Arabic words have none
        latin = " ".join([w for w in name.split() if ASCII_LETTER_RE.search(w)]).strip(" -:|")
        return name or title, latin

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in ("tn_film", "tn_series", "tn_episode"):
                return json_dumps({key: cItem[key] for key in self.FAV_FIELDS if key in cItem})
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            category = cItem.get("category", "")
            if category in ("tn_film", "tn_series") and cItem.get("post_id"):
                return "post:%s" % cItem["post_id"]
            if category == "tn_episode" and cItem.get("page_id"):
                return "page:%s|%s" % (cItem["page_id"], cItem.get("episode", ""))
        except Exception:
            printExc()
        return ""

    ###################################################
    # feeds
    ###################################################
    def _pages(self, host):
        # [(slug, page id, url)] of every Blogger page of host (cached)
        if host not in self.pagesCache:
            pages = []
            start = 1
            while True:
                feed = self._json("https://%s/feeds/pages/summary?alt=json&max-results=150&start-index=%d" % (host, start)).get("feed") or {}
                entries = feed.get("entry") or []
                for entry in entries:
                    url = self._entryLink(entry)
                    if url:
                        pages.append((_slug(url), self._entryId(entry), url))
                if len(entries) < 150:
                    break
                start += 150
            self.pagesCache[host] = pages
        return self.pagesCache[host]

    def _pageContent(self, host, pageId):
        entry = self._json("https://%s/feeds/pages/default/%s?alt=json" % (host, pageId)).get("entry") or {}
        return (entry.get("content") or {}).get("$t", "")

    def _postContent(self, postId):
        entry = self._json(self.getFullUrl("/feeds/posts/default/%s?alt=json" % postId)).get("entry") or {}
        return (entry.get("content") or {}).get("$t", "")

    def _hints(self, content, postUrl):
        # (hosts, slug hints) of the page(s) a post points to
        hosts = []
        for host in FEED_HOST_RE.findall(content) + ["www.cimatn.com"]:
            if host not in hosts:
                hosts.append(host)
        hints = []
        found = VAR_HINT_RE.findall(content) + INCLUDES_HINT_RE.findall(content)
        # "/p/rafel-ep-1.html" (link to the first episode) -> "rafel-ep-"
        found += [FIRST_EPISODE_RE.sub("", slug) for slug in PAGE_LINK_RE.findall(content)]
        for hint in found + [_slug(postUrl)]:
            hint = hint.lower().strip("/").replace("/p/", "")
            # generic parts of the site's scripts ("episode", "?episode", "waiting") name no page
            if len(hint) > 3 and hint[0] != "?" and hint not in hints and hint not in GENERIC_HINTS:
                hints.append(hint)
        return hosts, hints

    @staticmethod
    def _episodeNumber(slug, hint):
        # "accident-ep-3" with "accident-ep-" / "el-khotifa-ep-3" with "khotifa-ep-" / "baraa-ep-1_26" -> 3 / 3 / 1;
        # "arriere-el-goddem-ep-2" with "arriere-el-goddem" -> 2, but not "arriere-el-goddem-2" (season 2)
        pos = slug.find(hint)
        if pos < 0 or (pos and slug[pos - 1] != "-"):
            return 0
        rest = slug[pos + len(hint):]
        pattern = EPISODE_REST_RE if hint.endswith(("-", "ep", "episode")) else EPISODE_TAIL_RE
        m = pattern.match(rest)
        return int(m.group(1)) if m else 0

    @staticmethod
    def _urlList(content, name):
        # the quoted urls of "const <name> = [ "...", ... ]"
        pos = content.find(name)
        start = content.find("[", pos) if pos >= 0 else -1
        end = content.find("]", start) if start >= 0 else -1
        if end < 0:
            return []
        return re.findall(r"""["']((?:https?:)?//[^"'$]+)["']""", content[start:end])

    def _servers(self, content):
        # [url] of the players of a page: "servers = [{name, url}]" and the iframes
        urls = SERVER_URL_RE.findall(content)
        for attrs in TAG_IFRAME_RE.findall(content):
            urls.extend(SRC_RE.findall(attrs))
        out = []
        for url in urls:
            url = url.replace("&amp;", "&").strip()
            url = "https:" + url if url.startswith("//") else url.replace("https:///", "https://")
            if self.cm.isValidUrl(url) and url not in out and not any(h in url for h in SKIP_HOSTERS):
                out.append(url)
        return out

    @staticmethod
    def _seriesEpisodes(content):
        # {episode: block} of "seriesData = {... episodes: { 1: [ {...}, ... ], 2: [...] } }"
        pos = content.find("episodes:")
        if pos < 0:
            return {}
        episodes = {}
        for m in re.finditer(r"(\d+)\s*:\s*\[", content[pos:]):
            start = pos + m.end()
            end = content.find("]", start)
            if end < 0:
                break
            episodes.setdefault(int(m.group(1)), content[start:end])
        return episodes

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self, cItem):
        tab = [
            {"category": "tn_list", "title": _("Latest"), "good_for_fav": True},
            {"category": "tn_list", "title": _("Movies"), "label": LABEL_FILMS, "good_for_fav": True},
            {"category": "tn_list", "title": _("Series"), "label": LABEL_SERIES, "good_for_fav": True},
            {"category": "tn_list", "title": _("Ramadan"), "label": LABEL_RAMADAN, "good_for_fav": True},
            {"category": "tn_list", "title": _("Short films"), "label": LABEL_SHORT, "good_for_fav": True},
        ]
        self.listsTab(tab + self.searchItems(), cItem)

    def listPosts(self, cItem):
        page = cItem.get("page", 1)
        url = self.getFullUrl("/feeds/posts/summary")
        if cItem.get("label"):
            url += "/-/" + urllib_quote(cItem["label"])
        url += "?alt=json&max-results=%d&start-index=%d" % (PER_PAGE, (page - 1) * PER_PAGE + 1)
        if cItem.get("search"):
            url += "&q=" + urllib_quote_plus(cItem["search"])
        printDBG("CimaTN.listPosts [%s]" % url)
        feed = self._json(url).get("feed") or {}
        normalize = IsMediaNamingNormalized()
        for entry in feed.get("entry") or []:
            rawTitle = self.cleanHtmlStr((entry.get("title") or {}).get("$t", "")).replace(LRM, "").strip()
            link = self._entryLink(entry)
            if not rawTitle or not link:
                continue
            labels = [c.get("term", "") for c in entry.get("category", [])]
            years = sorted([lb for lb in labels if YEAR_LABEL_RE.match(lb)])
            year = years[0] if years else ""
            icon = (entry.get("media$thumbnail") or {}).get("url", "")
            icon = self.getFullIconUrl(re.sub(r"/s\d+(?:-c)?/", "/s400/", icon)) if icon else ""
            name, latin = self._names(rawTitle)
            genres = ", ".join([lb for lb in labels if not YEAR_LABEL_RE.match(lb) and not ASCII_LETTER_RE.search(lb) and lb not in SERIES_LABELS + (LABEL_FILMS,)])
            fields = ((_("Year"), year, "cyan"), (_("Genre"), genres, "green"))
            desc = " | ".join(["%s%s:%s %s" % (E2ColoR(color), label, E2ColoR("white"), value) for label, value, color in fields if value])
            params = {"name": "category", "good_for_fav": True, "url": link, "icon": icon, "desc": desc, "post_id": self._entryId(entry),
                      "meta_title": latin or name, "meta_year": year}
            if any(lb in SERIES_LABELS for lb in labels):
                season = 1
                m = SEASON_RE.search(rawTitle)
                if m:
                    season = int(m.group(1)) if m.group(1) else SEASON_WORDS.get(m.group(2), 1)
                params.update({"category": "tn_series", "title": rawTitle, "s_title": latin or name, "s_season": season, "meta_type": "tv"})
                self.addDir(params)
            else:
                title = rawTitle
                if normalize:
                    title = "%s (%s)" % (latin or name, year) if year else (latin or name)
                params.update({"category": "tn_film", "title": title, "meta_type": "movie"})
                self.addVideo(params)
        try:
            total = int((feed.get("openSearch$totalResults") or {}).get("$t", 0))
        except (TypeError, ValueError):
            total = 0
        lastPage = (total + PER_PAGE - 1) // PER_PAGE
        listItem = dict(cItem)
        # the feed pages by "start-index" built from cItem["page"]: the url is only the template the Jump row needs
        listItem.update({"category": "tn_list", "url": self.getFullUrl("/feeds/posts/summary")})
        addPagingItems(self, listItem, page, page < lastPage, lastPage, self.getFullUrl("/feeds/posts/summary#page={page}"))

    def _findEpisodes(self, content, postUrl):
        # {number: (page host, page id, url, episode key)}; page host "" = the episode list of the post itself
        inline = self._urlList(content, "episodeLinks")
        if inline:
            return {num: ("", "", "%s#ep-%d" % (postUrl, num), num) for num in range(1, len(inline) + 1)}
        hosts, hints = self._hints(content, postUrl)
        for hint in hints:
            episodes = {}
            for host in hosts:
                for slug, pageId, url in self._pages(host):
                    num = self._episodeNumber(slug, hint)
                    if num:
                        episodes.setdefault(num, (host, pageId, url, ""))
                    elif slug == hint:
                        # one page with all episodes (seriesData)
                        for num in sorted(self._seriesEpisodes(self._pageContent(host, pageId))):
                            episodes.setdefault(num, (host, pageId, "%s#ep-%d" % (url, num), num))
                if episodes:
                    return episodes
        return {}

    def listEpisodes(self, cItem):
        printDBG("CimaTN.listEpisodes [%s]" % cItem.get("url", ""))
        content = self._postContent(cItem.get("post_id", ""))
        if not content:
            return
        episodes = self._findEpisodes(content, cItem.get("url", ""))
        normalize = IsMediaNamingNormalized()
        show = cItem.get("s_title", "")
        season = cItem.get("s_season", 1)
        for num in sorted(episodes):
            host, pageId, url, episode = episodes[num]
            title = "%s - %s" % (show, formatSxxExx(season, num)) if normalize else "%s - %s %d" % (cItem.get("title", show), _("Episode"), num)
            self.addVideo({"name": "category", "category": "tn_episode", "good_for_fav": True, "title": title, "url": url, "icon": cItem.get("icon", ""),
                           "desc": cItem.get("desc", ""), "post_id": cItem.get("post_id", ""), "page_host": host, "page_id": pageId, "episode": episode,
                           "s_title": show, "s_season": season, "s_episode": num, "meta_type": "tv", "meta_title": cItem.get("meta_title", show)})
        if not episodes:
            SetIPTVPlayerLastHostError(_("No stream available"))

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("CimaTN.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem.update({"category": "tn_list", "search": searchPattern.strip(), "page": 1})
        self.listPosts(cItem)

    ###################################################
    # links
    ###################################################
    def _filmLinks(self, cItem):
        content = self._postContent(cItem.get("post_id", ""))
        if not content:
            return []
        hosts, hints = self._hints(content, cItem.get("url", ""))
        urls = []
        for host in hosts:
            for slug, pageId, _url in self._pages(host):
                if any(hint == slug or (hint.startswith("film") and hint in slug) for hint in hints):
                    urls = self._servers(self._pageContent(host, pageId))
                    if urls:
                        break
            if urls:
                break
        links = [{"name": "%s %d (%s)" % (_("Server"), i + 1, self.cm.ph.getSearchGroups(url, r"https?://(?:www\.)?([^/:]+)")[0]), "url": url} for i, url in enumerate(urls)]
        # the trailer of the post (the film itself may only be on the paid platform)
        trailer = self.cm.ph.getDataBeetwenMarkers(content, 'class="trailer-cont"', "</section>", False)[1]
        for url in self._servers(trailer):
            if url not in urls:
                links.append({"name": _("Trailer"), "url": url})
        return links

    def getLinksForVideo(self, cItem):
        printDBG("CimaTN.getLinksForVideo [%s]" % cItem.get("url", ""))
        links = []
        if cItem.get("category") == "tn_episode" and not cItem.get("page_host"):
            # one url per episode in the post itself ("episodeLinks")
            inline = self._urlList(self._postContent(cItem.get("post_id", "")), "episodeLinks")
            num = int(cItem.get("episode") or 0)
            content = 'url: "%s"' % inline[num - 1] if 0 < num <= len(inline) else ""
            for i, url in enumerate(self._servers(content)):
                links.append({"name": "%s %d (%s)" % (_("Server"), i + 1, self.cm.ph.getSearchGroups(url, r"https?://(?:www\.)?([^/:]+)")[0]), "url": url})
        elif cItem.get("category") == "tn_episode":
            content = self._pageContent(cItem.get("page_host", ""), cItem.get("page_id", ""))
            if cItem.get("episode"):
                content = self._seriesEpisodes(content).get(int(cItem["episode"]), "")
            for i, url in enumerate(self._servers(content)):
                links.append({"name": "%s %d (%s)" % (_("Server"), i + 1, self.cm.ph.getSearchGroups(url, r"https?://(?:www\.)?([^/:]+)")[0]), "url": url})
        else:
            links = self._filmLinks(cItem)
        # direct files (video.wixstatic.com/.../file.mp4) play as they are
        urltab = [{"name": link["name"], "url": strwithmeta(link["url"], {"Referer": self.getMainUrl()}),
                   "need_resolve": 0 if link["url"].split("?", 1)[0].endswith(".mp4") else 1} for link in links]
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(dict(cItem, desc=StripColorCodes(cItem.get("desc", ""))), IsSidecarEnabled()))

    def getVideoLinks(self, videoUrl):
        printDBG("CimaTN.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("CimaTN.getArticleContent [%s]" % cItem.get("url", ""))
        meta = {}
        if cItem.get("meta_title") and isLatinTitle(cItem["meta_title"]):
            try:
                meta = getMeta(cItem.get("meta_type", "movie"), cItem["meta_title"], cItem.get("meta_year", ""), LATIN_ONLY)
            except Exception:
                printExc()
        content = self._postContent(cItem.get("post_id", ""))
        story = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(content, 'class="StoryArea"', "</div>", False)[1])
        info = {}
        actors = [self.cleanHtmlStr(a) for a in re.findall(r"<a[^>]*>([^<]+)</a>", self.cm.ph.getDataBeetwenMarkers(content, 'class="actor"', "</li>", False)[1])]
        if actors:
            info["actors"] = ", ".join([a for a in actors if a])
        director = self.cm.ph.getDataBeetwenMarkers(content, 'class="director"', "</li>", False)[1]
        director = ", ".join([self.cleanHtmlStr(a) for a in re.findall(r"<a[^>]*>([^<]+)</a>", director)])
        if director:
            info["director"] = director
        if cItem.get("meta_year"):
            info["year"] = cItem["meta_year"]
        info.update(meta.get("info", {}))
        plot = meta.get("plot", "")
        text = story or plot or StripColorCodes(cItem.get("desc", ""))
        if plot and story and story != plot:
            text = "%s[/br][/br]%s" % (story, plot)
        poster = self.cm.ph.getSearchGroups(self.cm.ph.getDataBeetwenMarkers(content, 'id="poster"', "</div>", False)[1], SRC_RE.pattern)[0]
        icon = poster or meta.get("poster") or cItem.get("icon", "")
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
        printDBG("CimaTN.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "tn_list":
            self.listPosts(self.currItem)
        elif category == "tn_series":
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
        CHostBase.__init__(self, CimaTN(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("cimatn")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("tn_film", "tn_series", "tn_episode")
