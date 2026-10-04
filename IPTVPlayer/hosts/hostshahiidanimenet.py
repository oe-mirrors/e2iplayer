# -*- coding: utf-8 -*-
# Last Modified: 03.10.2026 - revived for the current shahiid-anime.net (bare domain, WordPress theme
#   "shahiidanime-220px"): uniform "one-poster" archives for series / films / dubbed / latest episodes,
#   /series/<slug>/ -> /seasons/?serie=<id> season list, season pages list the episodes; First page /
#   Jump / Next page over .../page/N/ and ?epp=N (pager rows keep the season's watched key),
#   server buttons -> embed iframe (films inline, episodes via admin-ajax codecanal_ajax_request),
#   genre/year filters from the archive filter form, unpaged search; watched flag, downloaded flag,
#   name normalisation, sidecar, moviemeta INFO combined with the site's own details.
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus, urllib_urlencode
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://shahiid-anime.net/"


# first path segment of a card url -> what the row is
SERIES_TYPES = ("series", "seriesdubbed", "serieses")
SEASON_TYPES = ("seasons", "seasonsdubbed", "seasonses")
MOVIE_TYPES = ("anime", "movies")
EPISODE_TYPES = ("episodes", "episodesdubbed", "episodeses")
# paging state of a list that must not reach the rows listed in it
LIST_STATE_KEYS = ("base_url", "wf_key")

_ARABIC = re.compile(u"[؀-ۿ]")
# "the first" .. "the tenth" as the site writes season numbers
_ORDINALS = {u"الأول": 1, u"الاول": 1, u"الثاني": 2,
             u"الثالث": 3, u"الرابع": 4, u"الخامس": 5,
             u"السادس": 6, u"السابع": 7, u"الثامن": 8,
             u"التاسع": 9, u"العاشر": 10}
_SEASON_WORD = u"الموسم"      # "season"
_EPISODE_WORD = u"الحلقة"     # "episode"
_DUB_WORD = u"مدبلج"               # "dubbed" (also matches the feminine form)
_SPECIAL_WORD = u"خاصة"           # "special" (episodes / OVAs)
_KEY_ENGLISH = u"الإنجليزي"    # "English (name)"
_KEY_EPISODES = u"عدد الحلقات"   # "number of episodes"
_KEY_DURATION = u"مدة"                       # "duration"
_KEY_STATUS = u"حالة"                   # "status"
_JUNK_LATIN = re.compile(r"(?i)(?:^|\s)(?:online|full\s*hd|fhd|hd|bluray|blu-ray|bd|1080p|720p|480p|\+)(?=\s|$)")


def _uni(text):
    if isinstance(text, bytes):
        return text.decode("utf-8", "ignore")
    return text


class ShahiidAnime(GenericFolderWatchedScraperMixin, CBaseHostClass):
    FAV_FIELDS = ("name", "category", "type", "url", "icon", "raw_title", "s_title", "season", "kind", "is_dub",
                  "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "shahiid-anime.net", "cookie": "shahiid-anime.net.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.MAIN_URL = gettytul()
        self.HEADER.update({"Referer": self.MAIN_URL})
        self.DEFAULT_ICON_URL = self.MAIN_URL + "wp-content/uploads/shahiid-anime-1.png"
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MENU = [{"category": "list_items", "title": _("Newest Episodes"), "url": self.getFullUrl("episodes/")},
                     {"category": "list_items", "title": _("Anime TV series"), "url": self.getFullUrl("series/")},
                     {"category": "list_items", "title": _("Anime movies"), "url": self.getFullUrl("anime/")},
                     {"category": "list_items", "title": _("Dubbed anime"), "url": self.getFullUrl("seriesDubbed/")},
                     {"category": "list_items", "title": _("Latest dubbed episodes"), "url": self.getFullUrl("episodesDubbed/")},
                     {"category": "list_items", "title": _("Live-action series episodes"), "url": self.getFullUrl("episodeses/")},
                     {"category": "list_filter", "title": _("Series by genre"), "url": self.getFullUrl("series/"), "f_key": "genre[]"},
                     {"category": "list_filter", "title": _("Series by year"), "url": self.getFullUrl("series/"), "f_key": "years[]"},
                     {"category": "list_filter", "title": _("Films by genre"), "url": self.getFullUrl("anime/"), "f_key": "genre[]"},
                     ] + self.searchItems()

        self.watchedHelper = IPTVWatchedHelper("shahiidanimenet")
        self.wfInitFolderCache()

    ###################################################
    # watched flag / favourites
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            if cItem.get("wf_key"):
                # "Next page" of a season / series: same key as its first page
                return cItem["wf_key"]
            if not cItem.get("kind"):
                return ""
            url = str(cItem.get("url", "") or "").strip()
            if not url:
                return ""
            if cItem.get("type", "") in ("video", "audio"):
                return "video:%s" % url
            category = cItem.get("category", "")
            if category == "list_seasons":
                return "series:%s" % url
            if category == "list_episodes":
                return "season:%s" % url
        except Exception:
            printExc()
        return ""

    def getFavouriteData(self, cItem):
        # only what identifies the row: the same title comes with other desc / titles from the different lists
        try:
            if cItem.get("kind"):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(self.cm.iriToUri(baseUrl), addParams, post_data)

    def _urlType(self, url):
        try:
            path = url.split("://", 1)[-1].split("/", 2)
            return path[1].lower() if len(path) > 1 else ""
        except Exception:
            return ""

    def _iconMeta(self, icon):
        icon = self.getFullIconUrl(icon.replace("&amp;", "&")) if icon else ""
        # the meta replaces the whole download header: without a User-Agent of its own the request goes out
        # with the client's default one, which i0.wp.com (the site's image CDN) answers with 404 for urllib
        return strwithmeta(icon, {"Referer": self.MAIN_URL, "User-Agent": self.HEADER["User-Agent"]}) if icon else ""

    def _latinTitle(self, label):
        # the English / romaji part of an Arabic label ("<film> X <subbed>" -> "X")
        u = _uni(label)
        words = [w for w in u.split() if not _ARABIC.search(w)]
        out = _JUNK_LATIN.sub(" ", " ".join(words))
        out = re.sub(r"\s+", " ", out).strip(u" -:|–,.")
        return ensure_str(out) if out else ensure_str(u.strip())

    def _isDub(self, label, url=""):
        return _DUB_WORD in _uni(label) or "dubbed" in url.lower()

    def _seasonFromLabel(self, label):
        # season number and the label without the season marker
        u = _uni(label)
        season = 0
        for pat in (r"(?i)\bseason\s*(\d+)", r"(?i)\b(\d+)(?:st|nd|rd|th)\s+season", r"\bS(\d+)\b"):
            m = re.search(pat, u)
            if m:
                season = int(m.group(1))
                u = u[:m.start()] + u[m.end():]
                break
        m = re.search(_SEASON_WORD + u"\\s+(\\S+)", u)
        if m:
            word = m.group(1)
            if not season:
                season = int(word) if word.isdigit() else _ORDINALS.get(word, 0)
            u = u[:m.start()] + u[m.end():]
        return season, ensure_str(u)

    def _episodeFromLabel(self, label, url=""):
        # (episode number, text before, text after the episode marker)
        u = _uni(label)
        m = re.search(_EPISODE_WORD + u"\\s*(\\d+)", u)
        if m:
            return int(m.group(1)), ensure_str(u[:m.start()]), ensure_str(u[m.end():])
        m = re.search(r"-ep-(\d+)", url)
        if m:
            return int(m.group(1)), label, ""
        return 0, label, ""

    def _showName(self, label):
        season, rest = self._seasonFromLabel(label)
        return season, self._latinTitle(rest)

    def _episodeTitle(self, rawLabel, url, showTitle="", season=0):
        if not IsMediaNamingNormalized():
            return rawLabel
        epNum, before, after = self._episodeFromLabel(rawLabel, url)
        sSeason, show = self._showName(before)
        if not _uni(show).strip() or _ARABIC.search(_uni(show)):
            # old style "<arabic name> episode 01 Latin Name ..."
            sSeason2, show = self._showName(re.sub(r"^\s*\d+\s*", "", after))
            sSeason = sSeason or sSeason2
        if showTitle:
            show = showTitle
        season = season or sSeason or 1
        if not epNum:
            return show or rawLabel
        title = "%s - %s" % (show or rawLabel, formatSxxExx(season, epNum))
        if self._isDub(rawLabel, url):
            title += " [Dub]"
        return title

    def _titleFor(self, rawLabel, url, kind):
        if not IsMediaNamingNormalized():
            return rawLabel
        if kind == "episode":
            return self._episodeTitle(rawLabel, url)
        if kind in ("series", "season"):
            season, title = self._showName(rawLabel)
            if kind == "season" and season:
                title = "%s - %s" % (title, formatSxxExx(season))
        else:
            title = self._latinTitle(rawLabel)
        if _SPECIAL_WORD in _uni(rawLabel):
            title += " [Specials]"
        if self._urlType(url) in ("serieses", "seasonses"):
            title += " [Live action]"
        if self._isDub(rawLabel, url):
            title += " [Dub]"
        return title

    ###################################################
    # listings
    ###################################################
    def _addCards(self, cItem, data):
        seen = set()
        cnt = 0
        for item in re.findall(r'<div class="one-poster[^"]*">(.*?)</h2>', data, re.DOTALL):
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, r'<h2><a href="([^"]+)"')[0])
            if not url or url in seen:
                continue
            seen.add(url)
            raw = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<h2><a[^>]*>(.*?)</a>')[0])
            if not raw:
                continue
            icon = self._iconMeta(self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0])
            ptype = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'class="poster-type[^"]*">([^<]*)<')[0])
            rating = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'class="rated-poster">(.*?)</span>')[0])
            desc = " | ".join([x for x in (ptype, ("MAL %s" % rating) if rating else "") if x])
            utype = self._urlType(url)
            params = stripPagerKeys(dict(cItem), LIST_STATE_KEYS + ("f_key", "s_title", "season"))
            params.update({"good_for_fav": True, "url": url, "icon": icon, "desc": desc, "raw_title": raw,
                           "is_dub": self._isDub(raw, url), "meta_title": self._showName(raw)[1], "meta_year": ""})
            if utype in SERIES_TYPES:
                params.update({"category": "list_seasons", "kind": "series", "meta_type": "tv", "title": self._titleFor(raw, url, "series")})
                self.addDir(params)
            elif utype in SEASON_TYPES:
                params.update({"category": "list_episodes", "kind": "season", "meta_type": "tv", "season": self._seasonFromLabel(raw)[0],
                               "s_title": params["meta_title"], "title": self._titleFor(raw, url, "season")})
                self.addDir(params)
            elif utype in MOVIE_TYPES:
                params.update({"category": "video", "kind": "movie", "meta_type": "movie", "meta_title": self._latinTitle(raw),
                               "title": self._titleFor(raw, url, "movie")})
                self.addVideo(params)
            elif utype in EPISODE_TYPES:
                params.update({"category": "video", "kind": "episode", "meta_type": "tv",
                               "meta_title": self._showName(self._episodeFromLabel(raw, url)[1])[1], "title": self._titleFor(raw, url, "episode")})
                self.addVideo(params)
            else:
                continue
            cnt += 1
        return cnt

    def _addPaging(self, cItem, page, hasNext, lastPage, pageUrlTpl, **extra):
        # the pager rows are no content rows (no kind) but key like the folder they page through (wf_key),
        # so the episodes of page 2+ propagate their watched state to the same season / series
        params = dict(cItem)
        for key in ("kind", "raw_title"):
            params.pop(key, None)
        params.update(extra)
        params["wf_key"] = self._getWatchedKeyForItem(cItem)
        addPagingItems(self, params, page, hasNext, lastPage, pageUrlTpl)

    @staticmethod
    def _pageUrlTpl(url):
        base, sep, query = url.partition("?")
        if not base.endswith("/"):
            base += "/"
        return "%spage/{page}/%s%s" % (base, sep, query)

    def listItems(self, cItem):
        printDBG("ShahiidAnime.listItems |%s|" % cItem)
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or cItem["url"]
        pageUrlTpl = self._pageUrlTpl(baseUrl)
        sts, data = self.getPage(baseUrl if page <= 1 else pageUrlTpl.format(page=page))
        if not sts:
            return
        pagination = self.cm.ph.getDataBeetwenMarkers(data, "id='pagination'", "</div>", False)[1]
        hasNext = bool(self._addCards(cItem, data)) and ("/page/%d/" % (page + 1)) in pagination
        lastPage = max([int(n) for n in re.findall(r"/page/(\d+)/", pagination)] + [page])
        self._addPaging(cItem, page, hasNext, lastPage, pageUrlTpl, base_url=baseUrl, url=baseUrl, category="list_items")

    def listFilter(self, cItem):
        printDBG("ShahiidAnime.listFilter |%s|" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        form = self.cm.ph.getDataBeetwenMarkers(data, 'id="anime-filter-form"', "</form>", False)[1]
        hidden = []
        for tag in re.findall(r"<input[^>]+>", form):
            if "hidden" not in tag:
                continue
            name = self.cm.ph.getSearchGroups(tag, r'name="([^"]+)"')[0]
            if name:
                hidden.append((name, self.cm.ph.getSearchGroups(tag, r'value="([^"]*)"')[0]))
        key = cItem["f_key"]
        select = self.cm.ph.getDataBeetwenMarkers(form, 'name="%s"' % key, "</select>", False)[1]
        options = re.findall(r'<option value="([^"]+)"[^>]*>([^<]+)</option>', select)
        if key == "years[]":
            options.reverse()
        for value, title in options:
            params = dict(cItem)
            params.pop("f_key", None)
            params.update({"good_for_fav": True, "category": "list_items", "title": self.cleanHtmlStr(title),
                           "url": "%s?%s" % (cItem["url"], urllib_urlencode(hidden + [(key, value)]))})
            self.addDir(params)

    def listSeasons(self, cItem):
        printDBG("ShahiidAnime.listSeasons |%s|" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        if 'class="one-poster' not in data:
            # live-action series pages only carry the id of their season list
            serie = self.cm.ph.getSearchGroups(data, r"serie=(\d+)")[0]
            utype = self._urlType(cItem["url"])
            seasonsPath = "seasonsDubbed" if utype == "seriesdubbed" else utype.replace("series", "seasons")
            if serie and seasonsPath:
                sts, data = self.getPage(self.getFullUrl("%s/?serie=%s" % (seasonsPath, serie)))
                if not sts:
                    return
        cards = []
        seen = set()
        for item in re.findall(r'<div class="one-poster[^"]*">(.*?)</h2>', data, re.DOTALL):
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, r'<h2><a href="([^"]+)"')[0])
            if url and self._urlType(url) in SEASON_TYPES and url not in seen:
                seen.add(url)
                cards.append((url, item))
        if not cards:
            # announced series: the page exists, its seasons do not yet
            SetIPTVPlayerLastHostError(_("No episodes available yet."))
            return
        if len(cards) == 1:
            # a single season: its episodes right away
            raw = self.cleanHtmlStr(self.cm.ph.getSearchGroups(cards[0][1], r'<h2><a[^>]*>(.*?)</a>')[0])
            params = dict(cItem)
            params.update({"season": self._seasonFromLabel(raw)[0], "s_title": cItem.get("meta_title", "") or self._showName(raw)[1]})
            self.listEpisodes(params, seasonUrl=cards[0][0])
            return
        self._addCards(cItem, "".join(['<div class="one-poster">%s</h2>' % x[1] for x in cards]))

    def listEpisodes(self, cItem, seasonUrl=None):
        printDBG("ShahiidAnime.listEpisodes |%s|" % cItem)
        page = cItem.get("page", 1)
        baseUrl = seasonUrl or cItem.get("base_url") or cItem["url"]
        pageUrlTpl = baseUrl + ("&" if "?" in baseUrl else "?") + "epp={page}"
        sts, data = self.getPage(baseUrl if page <= 1 else pageUrlTpl.format(page=page))
        if not sts:
            return
        showTitle = cItem.get("s_title", "") or cItem.get("meta_title", "")
        season = cItem.get("season", 0) or 0
        cnt = 0
        seen = set()
        for epUrl, raw in re.findall(r'fa-arrow-alt-circle-left"></i>(?:&nbsp;)*\s*<a href="([^"]+)"[^>]*>([^<]+)</a>', data):
            epUrl = self.getFullUrl(epUrl)
            if epUrl in seen:
                continue
            seen.add(epUrl)
            raw = self.cleanHtmlStr(raw)
            params = stripPagerKeys(dict(cItem), LIST_STATE_KEYS)
            params.update({"good_for_fav": True, "category": "video", "kind": "episode", "url": epUrl, "raw_title": raw,
                           "title": self._episodeTitle(raw, epUrl, showTitle, season), "meta_type": "tv", "meta_title": showTitle})
            self.addVideo(params)
            cnt += 1
        if not cnt and page == 1:
            # announced titles: the season page exists, the episodes do not yet
            SetIPTVPlayerLastHostError(_("No episodes available yet."))
        pagination = self.cm.ph.getDataBeetwenMarkers(data, "id='pagination'", "</div>", False)[1]
        hasNext = bool(cnt) and ("epp=%d" % (page + 1)) in pagination
        lastPage = max([int(n) for n in re.findall(r"epp=(\d+)", pagination)] + [page])
        # a single season listed straight from its series row: the pager rows open the season page
        self._addPaging(cItem, page, hasNext, lastPage, pageUrlTpl, base_url=baseUrl, url=baseUrl, category="list_episodes")

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("ShahiidAnime.listSearchResult [%s]" % searchPattern)
        # the site's search is not paged: all hits come on one page
        sts, data = self.getPage(self.MAIN_URL + "?s=" + urllib_quote_plus(searchPattern))
        if not sts:
            return
        self._addCards(dict(cItem), data)

    ###################################################
    # links
    ###################################################
    def _serverEmbed(self, attrs, referer):
        frame = self.cm.ph.getSearchGroups(attrs, r"""data-frameserver=['"]([^'"]*)['"]""")[0]
        frame = frame.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&amp;", "&")
        if "<iframe" in frame or "://" in frame:
            # films: the button holds the whole iframe
            src = self.cm.ph.getSearchGroups(frame, r'''src=["']([^"']+)["']''')[0] or frame
        else:
            # episodes: server post id + video code, the iframe comes from admin-ajax
            post = self.cm.ph.getSearchGroups(attrs, r"""data-post=['"]([^'"]*)['"]""")[0]
            serv = self.cm.ph.getSearchGroups(attrs, r"""data-serv=['"]([^'"]*)['"]""")[0]
            isFilm = self.cm.ph.getSearchGroups(attrs, r"""data-is_film=['"]([^'"]*)['"]""")[0]
            if not post or not frame:
                return ""
            query = urllib_urlencode([("action", "codecanal_ajax_request"), ("post", post), ("_server_code_", ""),
                                      ("frameserver", frame), ("is_film", isFilm), ("serv", serv)])
            params = dict(self.defaultParams)
            params["header"] = dict(self.HEADER)
            params["header"].update({"Referer": referer, "X-Requested-With": "XMLHttpRequest"})
            sts, data = self.getPage(self.MAIN_URL + "wp-admin/admin-ajax.php?" + query, params)
            if not sts:
                return ""
            src = self.cm.ph.getSearchGroups(data, r'''<iframe[^>]+src=["']([^"']+)["']''')[0]
        src = src.strip()
        if src.startswith("//"):
            src = "https:" + src
        return src if self.cm.isValidUrl(src) else ""

    def _story(self, data):
        story = self.cm.ph.getDataBeetwenMarkers(data, 'class="head-s-story', 'class="head-s-meta-last', False)[1]
        return self.cleanHtmlStr(re.sub(r"^.*?</b>", "", story, flags=re.DOTALL))

    def getLinksForVideo(self, cItem):
        printDBG("ShahiidAnime.getLinksForVideo [%s]" % cItem)
        urltab = []
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return []
        sidecarTxt = self._story(data) or cItem.get("desc", "")
        seen = set()
        for attrs, label in re.findall(r'<a class="buttosn"([^>]*)>(.*?)</a>', data, re.DOTALL)[:12]:
            url = self._serverEmbed(attrs, cItem["url"])
            if not url or url in seen:
                continue
            seen.add(url)
            if 1 != self.up.checkHostSupport(url):
                printDBG("ShahiidAnime: hoster not supported by urlparser [%s]" % url)
                continue
            name = self.cleanHtmlStr(label) or self.up.getHostName(url)
            urltab.append({"name": name, "url": strwithmeta(url, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("This video is only on hosters E2iPlayer cannot play."))
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), sidecarTxt))

    def getVideoLinks(self, videoUrl):
        printDBG("ShahiidAnime.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("ShahiidAnime.getArticleContent [%s]" % cItem)
        otherInfo = {}
        story = ""
        icon = cItem.get("icon", "")
        title = cItem.get("meta_title", "") or cItem.get("title", "")
        english = ""
        year = cItem.get("meta_year", "")
        sts, data = self.getPage(cItem["url"])
        if sts:
            head = self.cm.ph.getDataBeetwenMarkers(data, 'class="head-single-movie', 'class="head-s-meta-end', False)[1]
            if head:
                img = self.cm.ph.getSearchGroups(head, r'<img[^>]+src="([^"]+)"')[0]
                if img:
                    icon = self._iconMeta(img)
                for span in re.findall(r"<span><i[^>]*></i>(.*?)</span></span>", head, re.DOTALL):
                    key, _sep, value = span.partition(":")
                    key = _uni(self.cleanHtmlStr(key))
                    value = self.cleanHtmlStr(value)
                    if not value:
                        continue
                    if _KEY_ENGLISH in key:
                        english = value
                    elif "myanimelist" in key.lower():
                        otherInfo["rating"] = value
                    elif _KEY_EPISODES in key:
                        otherInfo["episodes"] = value
                    elif _KEY_DURATION in key:
                        otherInfo["duration"] = value
                    elif _KEY_STATUS in key:
                        otherInfo["status"] = value
                genres = re.findall(r'href="[^"]+-cats/[^"]+" rel="tag">([^<]+)<', head)
                if genres:
                    otherInfo["genres"] = ", ".join([self.cleanHtmlStr(x) for x in genres])
                studios = re.findall(r'href="[^"]+/studio/[^"]+">([^<]+)<', head)
                if studios:
                    otherInfo["production"] = ", ".join([self.cleanHtmlStr(x) for x in studios])
                story = self._story(head + 'class="head-s-meta-last')
            year = year or self.cm.ph.getSearchGroups(data, r"_years?/(\d{4})/")[0]
        if year:
            otherInfo["year"] = year
        if english:
            otherInfo["alternate_title"] = english
        meta = {}
        if cItem.get("meta_type") in ("movie", "tv"):
            try:
                meta = getMeta(cItem["meta_type"], english or title, year)
                if not meta and english and title and title != english:
                    meta = getMeta(cItem["meta_type"], title, year)
            except Exception:
                printExc()
        for key, value in meta.get("info", {}).items():
            if key not in otherInfo:
                otherInfo[key] = value
        icon = meta.get("poster") or icon or self.DEFAULT_ICON_URL
        text = meta.get("plot") or story or cItem.get("desc", "")
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}], "other_info": otherInfo}]

    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("ShahiidAnime.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "list_filter":
            self.listFilter(self.currItem)
        elif category == "list_seasons":
            self.listSeasons(self.currItem)
        elif category == "list_episodes":
            self.listEpisodes(self.currItem)
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category"})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc", _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):
    def __init__(self):
        CHostBase.__init__(self, ShahiidAnime(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("shahiidanimenet")

    def withArticleContent(self, cItem):
        return cItem.get("kind", "") in ("series", "season", "movie", "episode")
