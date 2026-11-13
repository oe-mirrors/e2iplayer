# -*- coding: utf-8 -*-
LAST_MODIFIED = "13.11.2026"
# KinoGo (Russian films, series, cartoons, anime, DLE): kinogo2026.com mirror (the kinogo.ec / .biz / .luxury
# front doors sit behind a Cloudflare challenge), playback through the Nextembed player of a title page: HLS
# master with the voice-over audio groups and VTT subtitles, series from the player's seasons / episodes JSON
import datetime
import re

from Components.config import ConfigSelection, ConfigText, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import GetAlternativeProxyChoices, GetAlternativeProxyUrl, IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta, sidecarMetaQuery
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import GetIconDir, MergeDicts, printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.kinogo_proxy = ConfigSelection(default="None", choices=GetAlternativeProxyChoices())
config.plugins.iptvplayer.kinogo_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.kinogo_proxy))
    if config.plugins.iptvplayer.kinogo_proxy.value == "None":
        optionList.append(getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.kinogo_alt_domain))
    return optionList
###################################################


def gettytul():
    return "https://kinogo2026.com/"


SITE_URL_RE = re.compile(r"^https?://(?:www\.)?kinogo[0-9]*\.[a-z]+/", re.I)
# https://kinogo2026.com/18337--matrica.html
ITEM_URL_RE = re.compile(r"/(\d+)-[^/]*\.html$", re.I)
ITEM_SPLIT_RE = re.compile(r'<div id="\d+" class="shortstory">')
# "Матрица (1999)" / "История его служанки (1-2 сезон)"
TITLE_YEAR_RE = re.compile(r"^(.*?)\s*\(((?:19|20)\d\d)\)\s*$")
TITLE_SEASON_RE = re.compile(r"^(.*?)\s*\([^)]*сезон[^)]*\)\s*$", re.I)
NEXTEMBED_RE = re.compile(r'(?:data-src|src)="(https?://api\.nextembed\.[a-z]+/embed/[^"]+)"')
# the Collaps / HDVB player: https://vid<n>.<domain>/movie/<hash>/iframe?d=kinogo.biz (serial/ for series)
COLLAPS_RE = re.compile(r'(?:data-src|src)="(https?://vid\d*\.[^"/]+/(?:movie|serial)/[0-9a-f]+/iframe[^"]*)"')
# the third player, cinemar.cc/embed/<id>/+<token> (older films often have only this one): urlparser parserCINEMAR
CINEMAR_RE = re.compile(r'(?:data-src|src)="(https?://cinemar\.[a-z]+/embed/[^"]+)"')
# labels of the info rows of a list card / title page -> INFO key
INFO_LABELS = (("year", "Год выпуска"), ("year", "Вышел в"), ("country", "Страна"), ("country", "Сняли в"), ("genres", "Жанры"), ("genres", "Жанр"),
               ("duration", "Длительность"), ("duration", "Продолжительность"), ("released", "Премьера"), ("quality", "Лучшее качество"),
               ("quality", "Качество"), ("translation", "Озвучки для вас"))
# genre lists the cards of the first pages may not show (site labels)
EXTRA_GENRES = (("istoricheskie", "Исторические"), ("voennye", "Военные"), ("dokumentalnye", "Документальные"), ("sport", "Спорт"),
                ("vestern", "Вестерн"), ("russkie-serialy", "Русские сериалы"), ("zarubezhnye-serialy", "Зарубежные сериалы"))
CATEGORY_SLUGS = ("filmy", "serialy", "multfilmy", "multserialy", "anime", "tv-shou", "v1new")
SERIES_SLUGS = ("serialy", "multserialy", "tv-shou", "russkie-serialy", "zarubezhnye-serialy")
FIRST_YEAR = 1950
LOCAL_PAGE_SIZE = 100


class KinoGo(GenericFolderWatchedScraperMixin, CBaseHostClass):
    DOMAIN_CACHE = None
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "group", "s_title", "s_year", "s_season", "s_episode", "meta_type")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "kinogo", "cookie": "kinogo.cookie"})
        self.MAIN_URL = None
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/kinogo135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("kinogo")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getProxy(self):
        return GetAlternativeProxyUrl(config.plugins.iptvplayer.kinogo_proxy.value) or None

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        proxy = self.getProxy()
        if proxy and "http_proxy" not in addParams:
            addParams = MergeDicts(addParams, {"http_proxy": proxy})
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def selectDomain(self):
        if KinoGo.DOMAIN_CACHE:
            self.MAIN_URL = KinoGo.DOMAIN_CACHE
            return
        domain = config.plugins.iptvplayer.kinogo_alt_domain.value.strip()
        self.MAIN_URL = domain.rstrip("/") + "/" if self.cm.isValidUrl(domain) else gettytul()
        sts, _data = self.getPage(self.MAIN_URL)
        finalUrl = self.cm.meta.get("url", self.MAIN_URL)
        if sts and SITE_URL_RE.match(finalUrl):
            # the mirror moves on (kinogo2025 -> kinogo2026 ...): the domain the old one redirects to
            self.MAIN_URL = self.cm.getBaseUrl(finalUrl)
            KinoGo.DOMAIN_CACHE = self.MAIN_URL

    def _rebase(self, url):
        # urls of favourites / older lists on a previous mirror -> the current one
        if self.MAIN_URL is None:
            self.selectDomain()
        url = (url or "").replace("&amp;", "&").strip()
        if not url.startswith("http"):
            url = CBaseHostClass.getFullUrl(self, url)
        return SITE_URL_RE.sub(self.MAIN_URL, url)

    def _pageUrl(self, url):
        return self._rebase(url).split("#")[0]

    @staticmethod
    def _path(url):
        # domain independent identity of a page, the #s<season>e<episode> fragment kept
        return re.sub(r"^https?://[^/]+", "", (url or "").split("?")[0]).rstrip("/").lower()

    @staticmethod
    def _slug(url):
        # https://kinogo2026.com/serialy/page/2/ -> "serialy"
        return re.sub(r"^https?://[^/]+/", "", (url or "").split("?")[0]).split("/")[0].lower()

    @staticmethod
    def _pageUrlTpl(url):
        # .../filmy/page/{page}/ ; DLE search: ...&search_start={page}
        base, query = (url.split("?", 1) + [""])[:2]
        if "do=search" in query:
            query = re.sub(r"&search_start=\d+", "", query).replace("{", "{{").replace("}", "}}")
            return base + "?" + query + "&search_start={page}"
        base = re.sub(r"/page/\d+/?$", "/", base).rstrip("/").replace("{", "{{").replace("}", "}}")
        query = query.replace("{", "{{").replace("}", "}}")
        return base + "/page/{page}/" + ("?" + query if query else "")

    @staticmethod
    def _page(cItem):
        try:
            return max(1, int(cItem.get("page", 1) or 1))
        except (TypeError, ValueError):
            return 1

    @staticmethod
    def _splitTitle(rawTitle):
        # -> (title, year); "Title (1-2 сезон)" loses the season note, the year then comes from the info row
        m = TITLE_YEAR_RE.match(rawTitle)
        if m:
            return m.group(1).strip(), m.group(2)
        m = TITLE_SEASON_RE.match(rawTitle)
        if m:
            return m.group(1).strip(), ""
        return rawTitle.strip(), ""

    @staticmethod
    def _jsBlock(data, start, openChar, closeChar):
        # the balanced {...} / [...] literal that starts at data[start] (strings skipped)
        depth, i, inStr, esc = 0, start, "", False
        while i < len(data):
            ch = data[i]
            if inStr:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == inStr:
                    inStr = ""
            elif ch in "\"'":
                inStr = ch
            elif ch == openChar:
                depth += 1
            elif ch == closeChar:
                depth -= 1
                if depth == 0:
                    return data[start:i + 1]
            i += 1
        return ""

    def getFavouriteData(self, cItem):
        try:
            return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
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
            path = self._path(cItem.get("url", ""))
            if not path:
                return ""
            if cItem.get("type", "") == "video":
                return "video:%s" % path
            prefix = {"list_seasons": "series", "list_episodes": "season"}.get(cItem.get("category", ""), "")
            return "%s:%s" % (prefix, path) if prefix else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def _infoRows(self, block):
        # {INFO key: text} of the "<b>Label:</b>value" rows of a list card / title page
        info = {}
        for label, value in re.findall(r"(?s)<b[^>]*>([^<]+?):?</b>\s*(.*?)</(?:span|div)>", block):
            label = self.cleanHtmlStr(label).rstrip(":")
            for key, name in INFO_LABELS:
                if label.startswith(name):
                    if key == "genres":
                        value = " / ".join(self.cleanHtmlStr(x) for x in re.findall(r">([^<]+)</a>", value)) or self.cleanHtmlStr(value)
                    else:
                        value = self.cleanHtmlStr(value)
                    if value and value.lower() != "неизвестно" and key not in info:
                        info[key] = value
                    break
        return info

    def _isSeries(self, block, rawTitle, url):
        slug = self._slug(url)
        if slug in SERIES_SLUGS:
            return True
        if "сезон" in rawTitle.lower() or "Жанр сериала" in block:
            return True
        return bool(re.search(r'href="[^"]*/(?:serialy|multserialy|tv-shou)/"', block))

    def _addCard(self, cItem, block, itemUrl, normalize):
        rawTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r"(?s)<h2[^>]*>(.*?)</h2>")[0]) or self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'alt="([^"]+)"')[0])
        if not rawTitle:
            return
        title, year = self._splitTitle(rawTitle)
        info = self._infoRows(block)
        year = year or self.cm.ph.getSearchGroups(info.get("year", ""), r"((?:19|20)\d\d)")[0]
        icon = self.cm.ph.getSearchGroups(block, r'(?s)class="shortstory__poster".*?data-src="([^"]+)"')[0]
        lenta = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)<div class="cont"[^>]*>(.*?)</div>')[0])
        rating = " ".join(self.cleanHtmlStr(x) for x in re.findall(r'(?s)<span class="(?:kp|imdb)"[^>]*>(.*?)</span>', block))
        excerpt = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)<div class="excerpt">(.*?)</div>')[0])
        rows = [(_("Year"), year), ("", lenta), (_("Country"), info.get("country", "")), (_("Genres"), info.get("genres", "")),
                (_("Duration"), info.get("duration", "")), (_("Quality"), info.get("quality", "")), (_("Rating"), rating)]
        desc = " | ".join(("%s: %s" % (label, value)) if label else value for label, value in rows if value)
        if excerpt:
            desc = "%s[/br]%s" % (desc, excerpt) if desc else excerpt
        params = stripPagerKeys(dict(cItem), ("search_story", "first_url"))
        params.update({"name": "category", "good_for_fav": True, "url": self._rebase(itemUrl), "icon": self.getFullIconUrl(icon) if icon else "",
                       "desc": desc, "s_title": title, "s_year": year})
        if self._isSeries(block, rawTitle, cItem.get("first_url") or cItem.get("url", "")):
            params.update({"category": "list_seasons", "group": "series", "meta_type": "tv", "title": title})
            self.addDir(params)
        else:
            params.update({"category": "kg_video", "group": "movies", "meta_type": "movie", "title": "%s (%s)" % (title, year) if (normalize and year) else rawTitle})
            self.addVideo(params)

    def listItems(self, cItem):
        printDBG("KinoGo.listItems [%s]" % cItem.get("url", ""))
        page = self._page(cItem)
        firstUrl = cItem.get("first_url") or cItem.get("url", "")
        pageUrlTpl = self._pageUrlTpl(self._pageUrl(firstUrl))
        sts, data = self.getPage(pageUrlTpl.format(page=page) if page > 1 else self._pageUrl(firstUrl))
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        seen = set()
        for block in ITEM_SPLIT_RE.split(data)[1:]:
            # the last card would run on into the sidebar (its series links made a film a series folder)
            block = block.split('class="shortstory__meta"', 1)[0]
            itemUrl = self.cm.ph.getSearchGroups(block, r'href="(https?://[^"]+\.html)"')[0]
            if not itemUrl or not ITEM_URL_RE.search(itemUrl) or itemUrl in seen:
                continue
            seen.add(itemUrl)
            self._addCard(cItem, block, itemUrl, normalize)
        if not seen:
            # empty category / page or no search hits: a marker instead of an empty list
            self.addMarker({"title": _("No items found"), "desc": ""})
            return
        pager = self.cm.ph.getDataBeetwenMarkers(data, ("<div", ">", "navigation"), "</div>", False)[1] or data
        pages = [int(n) for n in re.findall(r'href="[^"]*/page/(\d+)/[^"]*"', pager) + re.findall(r"search_start=(\d+)", pager) + re.findall(r"list_submit\((\d+)\)", pager)]
        lastPage = max(pages + [page])
        hasNext = lastPage > page or 'class="pnext"' in pager or 'class="next"' in pager
        addPagingItems(self, dict(cItem, category="list_items", url=firstUrl, first_url=firstUrl), page, hasNext, lastPage, pageUrlTpl)
        for item in self.currList:
            # "First page" back to the list the user opened
            if item.get("image_type") == "FIRST":
                item["url"] = firstUrl

    def listGenres(self, cItem):
        printDBG("KinoGo.listGenres")
        # the genre links of the cards of the film and series lists (the site renders its menu by script)
        genres = {}
        for slug in ("filmy", "serialy"):
            sts, data = self.getPage(self.getFullUrl(slug + "/"))
            if not sts:
                continue
            for block in re.findall(r"(?s)<b>Жанр:?</b>(.*?)</span>", data):
                for url, name in re.findall(r'href="(https?://[^"]+/[a-z0-9-]+/)">([^<]+)</a>', block):
                    slugName = self._slug(url)
                    if slugName and slugName not in CATEGORY_SLUGS and slugName not in genres:
                        genres[slugName] = self.cleanHtmlStr(name)
        for slug, name in EXTRA_GENRES:
            genres.setdefault(slug, name)
        for slug, name in sorted(genres.items(), key=lambda x: x[1].lower()):
            params = stripPagerKeys(dict(cItem))
            params.update({"name": "category", "good_for_fav": True, "category": "list_items", "title": name, "url": self.getFullUrl(slug + "/")})
            self.addDir(params)

    def listYears(self, cItem):
        printDBG("KinoGo.listYears")
        for year in range(datetime.date.today().year, FIRST_YEAR - 1, -1):
            params = stripPagerKeys(dict(cItem))
            params.update({"name": "category", "good_for_fav": True, "category": "list_items", "title": str(year),
                           "url": self.getFullUrl("xfsearch/year-teg-xfsearch/%d/" % year)})
            self.addDir(params)

    ###################################################
    # players: Nextembed (HLS master with audio groups + VTT) and Collaps / HDVB (urlparser parserCOLLAPS, HLS per voice-over)
    ###################################################
    def _players(self, pageUrl):
        # -> ({"nextembed": url, "collaps": [urls]}, page html) of the players of a title page
        sts, data = self.getPage(self._pageUrl(pageUrl))
        if not sts:
            return {"nextembed": "", "collaps": []}, ""
        nextembed = NEXTEMBED_RE.search(data)
        collaps = []
        for url in COLLAPS_RE.findall(data):
            url = url.replace("&amp;", "&")
            if url not in collaps:
                collaps.append(url)
        return {"nextembed": nextembed.group(1).replace("&amp;", "&") if nextembed else "", "collaps": collaps}, data

    def _embedPage(self, embedUrl):
        params = dict(self.defaultParams)
        params["header"] = MergeDicts(self.HEADER, {"Referer": self.MAIN_URL or gettytul()})
        sts, data = self.getPage(embedUrl, params)
        return data if sts else ""

    def _collapsUrl(self, iframeUrl, extraMeta=None):
        # a Collaps iframe for urlparser (parserCOLLAPS / getCollapsPlaylist): the site as referer, the host's proxy
        meta = {"Referer": self.MAIN_URL or gettytul()}
        proxy = self.getProxy()
        if proxy:
            meta["http_proxy"] = proxy
        meta.update(extraMeta or {})
        return strwithmeta(iframeUrl, meta)

    def _embedSeasons(self, data):
        # [{"season": n, "episodes": [{"episode", "id", "hls", "dash", "audio", "cc"}]}] of a series player
        start = data.find("seasons:[")
        if start < 0:
            return []
        try:
            seasons = json_loads(self._jsBlock(data, start + len("seasons:"), "[", "]"))
        except Exception:
            printExc()
            return []
        return [s for s in seasons if isinstance(s, dict) and s.get("episodes")]

    def _embedSource(self, data):
        # {"hls", "audio", "cc"} of a film player (a JS literal: keys unquoted, values JSON)
        start = data.find("source: {")
        if start < 0:
            start = data.find("source:{")
        if start < 0:
            return {}
        block = self._jsBlock(data, data.find("{", start), "{", "}")
        source = {"hls": self.cm.ph.getSearchGroups(block, r'hls:\s*"([^"]+)"')[0]}
        for key in ("audio", "cc"):
            m = re.search(r"%s:\s*([\[{])" % key, block)
            if m:
                literal = self._jsBlock(block, m.start(1), m.group(1), "]" if m.group(1) == "[" else "}")
                try:
                    source[key] = json_loads(literal)
                except Exception:
                    pass
        return source

    @staticmethod
    def _episodeKey(episode):
        try:
            return (0, float(str(episode.get("episode", "")).replace(",", ".")))
        except ValueError:
            return (1, str(episode.get("episode", "")))

    def _seasonList(self, pageUrl):
        # -> (seasons, film source, page html): the Nextembed seasons (episode dicts with hls / audio / cc) merged
        # with the Collaps playlist (episode "collaps" voice-over list), or the film sources of both players
        players, data = self._players(pageUrl)
        seasons, source = [], {}
        if players["nextembed"]:
            embed = self._embedPage(players["nextembed"])
            seasons = self._embedSeasons(embed)
            if not seasons:
                source = self._embedSource(embed)
        for iframeUrl in players["collaps"]:
            playlist = self.up.getCollapsPlaylist(self._collapsUrl(iframeUrl))
            if not playlist:
                continue
            if not playlist.get("film"):
                for item in playlist.get("seasons", []):
                    target = None
                    for season in seasons:
                        if str(season.get("season", "")) == str(item["season"]):
                            target = season
                    if target is None:
                        seasons.append(item)
                        continue
                    for ep in item["episodes"]:
                        known = [x for x in target["episodes"] if str(x.get("episode", "")) == ep["episode"]]
                        if known:
                            known[0].setdefault("collaps", []).extend(ep["collaps"])
                        else:
                            target["episodes"].append(ep)
            else:
                source.setdefault("collaps", []).append(iframeUrl)
        for season in seasons:
            season["episodes"].sort(key=self._episodeKey)
        seasons.sort(key=lambda s: s.get("season", 0))
        return seasons, source, data

    def listSeasons(self, cItem):
        printDBG("KinoGo.listSeasons [%s]" % cItem.get("url", ""))
        seasons, source, data = self._seasonList(cItem.get("url", ""))
        if not seasons:
            if source.get("hls") or source.get("collaps"):
                # a film (search hit / mixed list): its video row
                title = cItem.get("s_title") or cItem.get("title", "")
                year = cItem.get("s_year", "")
                self.addVideo(MergeDicts(cItem, {"category": "kg_video", "group": "movies", "meta_type": "movie",
                                                 "title": "%s (%s)" % (title, year) if (IsMediaNamingNormalized() and year) else title}))
            else:
                SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return
        page = self._pageUrl(cItem.get("url", ""))
        if len(seasons) == 1:
            season = seasons[0].get("season", 1)
            self.listEpisodes(dict(cItem, url="%s#s%s" % (page, season), s_season=season), seasons)
            return
        show = cItem.get("s_title") or cItem.get("title", "")
        normalize = IsMediaNamingNormalized()
        for item in seasons:
            season = item.get("season", 0)
            params = stripPagerKeys(dict(cItem))
            params.update({"name": "category", "category": "list_episodes", "good_for_fav": True, "url": "%s#s%s" % (page, season), "s_title": show, "s_season": season,
                           "title": "%s - %s" % (show, formatSxxExx(season)) if normalize else "%s %s" % (_("Season"), season),
                           "desc": "%s: %d" % (_("Episodes"), len(item["episodes"])), "meta_type": "tv"})
            self.addDir(params)

    def listEpisodes(self, cItem, seasons=None):
        printDBG("KinoGo.listEpisodes [%s]" % cItem.get("url", ""))
        page = self._pageUrl(cItem.get("url", ""))
        season = cItem.get("s_season") or self.cm.ph.getSearchGroups(cItem.get("url", ""), r"#s([^e]+)")[0]
        if seasons is None:
            seasons = self._seasonList(page)[0]
        episodes = []
        for item in seasons:
            if str(item.get("season", "")) == str(season):
                episodes = item["episodes"]
        if not episodes:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return
        normalize = IsMediaNamingNormalized()
        show = cItem.get("s_title") or cItem.get("title", "")
        pageNo = self._page(cItem)
        start = (pageNo - 1) * LOCAL_PAGE_SIZE
        for episode in episodes[start:start + LOCAL_PAGE_SIZE]:
            number = str(episode.get("episode", ""))
            try:
                title = "%s - %s" % (show, formatSxxExx(season, int(number))) if normalize else "%s - %s %s - %s %s" % (show, _("Season"), season, _("Episode"), number)
            except ValueError:
                title = "%s - %s %s - %s %s" % (show, _("Season"), season, _("Episode"), number)
            audio = episode.get("audio") or {}
            voices = list(audio.get("names", []) if isinstance(audio, dict) else []) + [v[0] for v in episode.get("collaps", []) if v[0]]
            params = stripPagerKeys(dict(cItem))
            params.update({"name": "category", "category": "kg_video", "good_for_fav": True, "title": title, "url": "%s#s%se%s" % (page, season, number),
                           "s_title": show, "s_season": season, "s_episode": number, "meta_type": "tv", "desc": ", ".join(voices)})
            self.addVideo(params)
        if len(episodes) > LOCAL_PAGE_SIZE:
            lastPage = (len(episodes) + LOCAL_PAGE_SIZE - 1) // LOCAL_PAGE_SIZE
            addPagingItems(self, dict(cItem, category="list_episodes"), pageNo, pageNo < lastPage, lastPage)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("KinoGo.listSearchResult [%s]" % searchPattern)
        story = searchPattern.strip()
        url = self.getFullUrl("index.php?do=search&subaction=search&story=%s" % urllib_quote_plus(story))
        cItem = dict(cItem)
        cItem.pop("group", None)
        cItem.update({"category": "list_items", "page": 1, "url": url, "first_url": url, "search_story": story})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    @staticmethod
    def _subTracks(cc):
        tracks = []
        for track in cc if isinstance(cc, list) else []:
            url, name = track.get("url", ""), track.get("name", "") or _("Subtitles")
            if not url:
                continue
            lower = name.lower()
            if lower.startswith(("eng", "англ")):
                code = "en"
            elif lower.startswith(("рус", "rus")):
                code = "ru"
            elif lower.startswith(("укр", "ukr")):
                code = "uk"
            else:
                code = "und"
            tracks.append({"title": name, "url": url, "lang": code, "format": "vtt" if ".vtt" in url else "srt"})
        return tracks

    def _link(self, source, embedUrl):
        hls = source.get("hls", "")
        if not self.cm.isValidUrl(hls):
            return None
        audio = source.get("audio") or {}
        names = [n for n in (audio.get("names", []) if isinstance(audio, dict) else []) if n]
        meta = {"User-Agent": self.HEADER.get("User-Agent"), "Referer": self.cm.getBaseUrl(embedUrl), "iptv_proto": "m3u8"}
        tracks = self._subTracks(source.get("cc"))
        if tracks:
            meta["external_sub_tracks"] = tracks
        return {"name": "HLS [%s]" % ", ".join(names) if names else "HLS", "url": strwithmeta(hls, meta), "need_resolve": 0}

    def getLinksForVideo(self, cItem):
        url = cItem.get("url", "")
        printDBG("KinoGo.getLinksForVideo [%s]" % url)
        match = re.search(r"#s([^e]+)e(.+)$", url)
        season, episode = match.groups() if match else ("", "")
        seasons, source, data = self._seasonList(url)
        urltab = []
        if season:
            source = {}
            for item in seasons:
                if str(item.get("season", "")) != str(season):
                    continue
                for ep in item["episodes"]:
                    if str(ep.get("episode", "")) == str(episode):
                        source = ep
        nextembedUrl = NEXTEMBED_RE.search(data)
        link = self._link(source, nextembedUrl.group(1) if nextembedUrl else self.MAIN_URL)
        if link:
            urltab.append(link)
        # Collaps (urlparser parserCOLLAPS): the film iframe, or the series iframe + episode + voice-over position as url meta
        collapsFrames = [x.replace("&amp;", "&") for x in COLLAPS_RE.findall(data)]
        serialFrame = [x for x in collapsFrames if "/serial/" in x]
        for idx, (voice, _token) in enumerate(source.get("collaps", []) if season and serialFrame else []):
            url = self._collapsUrl(serialFrame[0], {"collaps_season": str(season), "collaps_episode": str(episode), "collaps_voice": str(idx)})
            urltab.append({"name": "Collaps [%s]" % voice if voice else "Collaps", "url": url, "need_resolve": 1})
        for iframeUrl in (source.get("collaps", []) if not season else []):
            urltab.append({"name": "Collaps", "url": self._collapsUrl(iframeUrl), "need_resolve": 1})
        if not season:
            # films: the cinemar player through urlparser (series playlists of it are folders it does not handle)
            seen = set()
            for cinemarUrl in CINEMAR_RE.findall(data):
                cinemarUrl = cinemarUrl.replace("&amp;", "&")
                if cinemarUrl not in seen and self.up.checkHostSupport(cinemarUrl) == 1:
                    seen.add(cinemarUrl)
                    urltab.append({"name": "Cinemar", "url": strwithmeta(cinemarUrl, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        info, plot, year = self._siteInfo(data)
        mediaType = cItem.get("meta_type", "") or ("tv" if season else "movie")
        metaQuery = sidecarMetaQuery(mediaType, cItem.get("s_title", "") or cItem.get("title", ""), cItem.get("s_year", "") or year, skip=(), maxYearDiff=1)
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), plot, metaQuery=metaQuery))

    def getVideoLinks(self, videoUrl):
        printDBG("KinoGo.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        # Collaps and cinemar players: urlparser
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)

    ###################################################
    # INFO
    ###################################################
    def _siteInfo(self, data):
        # -> (info, plot, year) of a title page
        block = self.cm.ph.getDataBeetwenMarkers(data, ("<div", ">", "movie__info"), ("<div", ">", "cast-block"), False)[1] or data[:60000]
        info = self._infoRows(block)
        year = self.cm.ph.getSearchGroups(info.pop("year", ""), r"((?:19|20)\d\d)")[0]
        if year:
            info["year"] = year
        imdb = self.cm.ph.getSearchGroups(block, r'class="rate imdb">[^<\d]*([\d.]+)')[0]
        if imdb and imdb != "0":
            info["imdb_rating"] = "%s/10" % imdb
        kp = self.cm.ph.getSearchGroups(block, r'class="rate kp">[^<\d]*([\d.]+)')[0]
        if kp and kp != "0":
            info["rating"] = "KP %s/10" % kp
        plot = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)class="description__block">(.*?)</div>')[0])
        return info, plot, year

    def getArticleContent(self, cItem):
        printDBG("KinoGo.getArticleContent [%s]" % cItem.get("url", ""))
        info, plot, year = {}, "", cItem.get("s_year", "")
        sts, data = self.getPage(self._pageUrl(cItem.get("url", "")))
        if sts:
            info, plot, siteYear = self._siteInfo(data)
            year = year or siteYear
        mediaType = cItem.get("meta_type", "") or ("tv" if "#s" in cItem.get("url", "") else "movie")
        title = cItem.get("s_title", "") or cItem.get("title", "")
        meta = {}
        try:
            meta = getMeta(mediaType, title, year, maxYearDiff=1)
        except Exception:
            printExc()
        for key, value in meta.get("info", {}).items():
            info.setdefault(key, value)
        metaPlot = meta.get("plot", "")
        text = plot or cItem.get("desc", "")
        if metaPlot and text and metaPlot != text:
            text = "%s[/br][/br]%s" % (text, metaPlot)
        else:
            text = text or metaPlot
        icon = cItem.get("icon", "") or meta.get("poster", "") or self.DEFAULT_ICON_URL
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}], "other_info": info}]

    ###################################################
    # service
    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if self.MAIN_URL is None:
            self.selectDomain()
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("KinoGo.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            menu = [{"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("filmy/"), "group": "movies"},
                    {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("serialy/"), "group": "series"},
                    {"category": "list_items", "title": _("Cartoons"), "url": self.getFullUrl("multfilmy/"), "group": "movies"},
                    {"category": "list_items", "title": _("Animated series"), "url": self.getFullUrl("multserialy/"), "group": "series"},
                    {"category": "list_items", "title": _("Anime"), "url": self.getFullUrl("anime/")},
                    {"category": "list_items", "title": _("TV Shows"), "url": self.getFullUrl("tv-shou/"), "group": "series"},
                    {"category": "list_items", "title": _("New"), "url": self.getFullUrl("v1new/")},
                    {"category": "list_genres", "title": _("Genres")},
                    {"category": "list_years", "title": _("Year")}]
            self.listsTab(menu + self.searchItems(), {"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "list_genres":
            self.listGenres(self.currItem)
        elif category == "list_years":
            self.listYears(self.currItem)
        elif category == "list_seasons":
            self.listSeasons(self.currItem)
        elif category == "list_episodes":
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
        CHostBase.__init__(self, KinoGo(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("kinogo")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video" or cItem.get("category", "") in ("list_seasons", "list_episodes")
