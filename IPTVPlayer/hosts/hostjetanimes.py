# -*- coding: utf-8 -*-
# Last Modified: 07.10.2026
#   - JetAnimes (French anime movies and series, VF / VOSTFR, DooPlay site); the content lives on
#     on.jetanimes.com, the address is read from the jetanimes.com portal, favourites of an older
#     address are moved over
#   - latest episodes, movies, series, genres, years, search
#   - First page / Jump / Next page on every list (/page/N/) and the search (last page known)
#   - series -> seasons -> episodes (one season: the episodes directly)
#   - links: the DooPlay player options (admin-ajax), secured.lol short links followed to the hoster
#     -> urlparser; players of hosters urlparser does not know are left out
#   - watched flag, downloaded flag, favourites, name normalisation ("Title (Year)", "Show - SxxExx"),
#     sidecar, INFO via moviemeta + the site's fields
###################################################
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://on.jetanimes.com/"


PORTAL_URL = "https://jetanimes.com/"
# paths of the site: urls of an older address (favourites) are moved to the current one
SITE_PATH_RE = re.compile(r"^https?://[^/]+/((?:films|serie|episodes|genre|annee|page)/.*|\?s=.*|wp-admin/.*)$")
# <article ...class="item movies|tvshows|se episodes"...>..</article> - the class is checked on the tag text
ARTICLE_RE = re.compile(r"(?s)<article([^>]*)>(.*?)</article>")
ARTICLE_CLASS_RE = re.compile(r'class="item (movies|tvshows|se episodes)"')
SEARCH_RE = re.compile(r'(?s)<div class="result-item">(.*?)</article>')
TITLE_DIV_RE = re.compile(r'(?s)<div class="title">\s*(<a [^>]+>.*?</a>)\s*</div>')
# <li id="player-option-N" ...data-type= ..data-post= ..data-nume=...>..</li> - the attributes are read from the tag text
PLAYER_RE = re.compile(r"""(?s)<li id=['"]player-option-\d+['"]([^>]*)>(.*?)</li>""")
PLAYER_TYPE_RE = re.compile(r"""data-type=['"](\w+)['"]""")
PLAYER_POST_RE = re.compile(r"""data-post=['"](\d+)['"]""")
PLAYER_NUME_RE = re.compile(r"""data-nume=['"](\w+)['"]""")
# <b class="variante">label</b> <span class="valor">value</span>
FIELD_START = '<b class="variante">'
FIELD_VALUE_RE = re.compile(r'</b>\s*<span class="valor">')
VIDEO_CATEGORIES = ("jet_video",)
FOLDER_CATEGORIES = ("jet_series", "jet_season")


def _articles(data):
    # (attrs before the class, kind, body) of the list articles, scanned like a regex findall
    out = []
    pos = 0
    while True:
        m = ARTICLE_RE.search(data, pos)
        if not m:
            return out
        attrs = m.group(1)
        found = [c for c in ARTICLE_CLASS_RE.finditer(attrs) if c.start() > 0]
        if found:
            out.append((attrs[:found[-1].start()], found[-1].group(1), m.group(2)))
            pos = m.end()
        else:
            pos = m.start() + 1


def _playerAttrs(attrs):
    # (type, post, nume) in this order in the tag, each after at least one other char - None when missing
    types = [t for t in PLAYER_TYPE_RE.finditer(attrs) if t.start() > 0]
    posts = list(PLAYER_POST_RE.finditer(attrs))
    numes = list(PLAYER_NUME_RE.finditer(attrs))
    for t in reversed(types):
        for p in reversed(posts):
            if p.start() <= t.end():
                break
            for n in reversed(numes):
                if n.start() <= p.end():
                    break
                return t.group(1), p.group(1), n.group(1)
    return None


def _players(data):
    # (type, post, nume, body) of the player options, scanned like a regex findall
    out = []
    pos = 0
    while True:
        m = PLAYER_RE.search(data, pos)
        if not m:
            return out
        found = _playerAttrs(m.group(1))
        if found:
            out.append(found + (m.group(2),))
            pos = m.end()
        else:
            pos = m.start() + 1


def _fieldPairs(data):
    # (label, value) of the <b class="variante">..</b> <span class="valor">..</span> rows
    out = []
    pos = 0
    while True:
        s = data.find(FIELD_START, pos)
        if s < 0:
            return out
        a = s + len(FIELD_START)
        m = FIELD_VALUE_RE.search(data, a)
        e = data.find("</span>", m.end()) if m else -1
        if e >= 0:
            out.append((data[a:m.start()], data[m.end():e]))
            pos = e + len("</span>")
        else:
            pos = s + 1


def _dropNewMark(title):
    # "Title NOUVEAU" -> "Title"
    s = title.rstrip()
    if len(s) > 7 and s[-7:].lower() == "nouveau" and s[-8].isspace():
        return s[:-7].rstrip()
    return title


class JetAnimes(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode",
                  "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "jetanimes", "cookie": "jetanimes.cookie"})
        self.MAIN_URL = None
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.cacheLinks = {}
        self.watchedHelper = IPTVWatchedHelper("jetanimes")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def selectDomain(self):
        # the portal links its menu (films / serie / episodes) to the address the content lives on
        url = ""
        sts, data = self.cm.getPage(PORTAL_URL, dict(self.defaultParams))
        if sts:
            url = self.cm.ph.getSearchGroups(data, r'href="(https?://[^/"]+/)films/"')[0]
        if not self.setMainUrl(url):
            self.MAIN_URL = gettytul()
        printDBG("JetAnimes.selectDomain [%s]" % self.MAIN_URL)

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if self.MAIN_URL is None:
            self.selectDomain()
        if addParams is None:
            addParams = dict(self.defaultParams)
        match = SITE_PATH_RE.match(baseUrl or "")
        if match:
            baseUrl = self.getMainUrl() + match.group(1)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(baseUrl.split("#")[0], addParams, post_data)

    def _key(self, url):
        return re.sub(r"^https?://[^/]+", "", url or "").rstrip("/")

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in VIDEO_CATEGORIES + FOLDER_CATEGORIES + ("jet_list",):
                return json_dumps({key: cItem[key] for key in self.FAV_FIELDS if key in cItem})
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            key = self._key(cItem.get("url", ""))
            if not key:
                return ""
            category = cItem.get("category", "")
            if category in VIDEO_CATEGORIES:
                return "video:%s" % key
            if category in FOLDER_CATEGORIES:
                return "folder:%s" % key
        except Exception:
            printExc()
        return ""

    def _episodeTitle(self, show, season, episode, label=""):
        if IsMediaNamingNormalized():
            return "%s - %s" % (show, formatSxxExx(season, episode))
        title = "%s - %s %d - %s %d" % (show, _("Season"), season, _("Episode"), episode)
        if label and not re.match(r"^\S*pisode\s+\d+$", label):
            title = "%s - %s" % (title, label)
        return title

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self):
        menu = [
            {"category": "jet_list", "title": _("Latest episodes"), "url": self.getFullUrl("episodes/")},
            {"category": "jet_list", "title": _("Movies"), "url": self.getFullUrl("films/")},
            {"category": "jet_list", "title": _("Series"), "url": self.getFullUrl("serie/")},
            {"category": "jet_genres", "title": _("Genres")},
            {"category": "jet_years", "title": _("Year")},
        ]
        self.listsTab(menu + self.searchItems(), {"name": "category"})

    def listGenres(self, cItem):
        sts, data = self.getPage(self.getFullUrl("wp-json/wp/v2/genres?per_page=100&_fields=name,slug,count"))
        if not sts:
            return
        try:
            genres = json_loads(data)
        except Exception:
            printExc()
            return
        for genre in genres:
            if not genre.get("count") or not genre.get("slug"):
                continue
            self.addDir({"name": "category", "category": "jet_list", "good_for_fav": True, "title": self.cleanHtmlStr(genre.get("name", "")),
                         "url": self.getFullUrl("genre/%s/" % genre["slug"]), "desc": "%s: %s" % (_("Titles"), genre["count"])})

    def listYears(self, cItem):
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        years = sorted(set(re.findall(r'href="https?://[^"]+/annee/(\d{4})/"', data)), reverse=True)
        for year in years:
            self.addDir({"name": "category", "category": "jet_list", "good_for_fav": True, "title": year, "url": self.getFullUrl("annee/%s/" % year)})

    def _addArticle(self, kind, block, normalize):
        url = self.cm.ph.getSearchGroups(block, r'<h3><a href="([^"]+)"')[0] or self.cm.ph.getSearchGroups(block, r'<a href="([^"]+)"')[0]
        title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r"(?s)<h3>(.*?)</h3>")[0])
        if not url or not title:
            return False
        icon = self.cm.ph.getSearchGroups(block, r'<img[^>]+src="([^"]+)"')[0]
        params = {"name": "category", "good_for_fav": True, "url": url, "icon": self.getFullIconUrl(icon) if icon else ""}
        if kind == "se episodes":
            show = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)<span class="serie">(.*?)</span>')[0])
            numbers = re.search(r"S(\d+)\s*E(\d+)", block)
            season, episode = (int(numbers.group(1)), int(numbers.group(2))) if numbers else (1, 0)
            label = _dropNewMark(title)
            params.update({"category": "jet_video", "title": self._episodeTitle(show, season, episode, label) if show and episode else label,
                           "s_title": show, "s_season": season, "s_episode": episode, "meta_type": "tv", "meta_title": show,
                           "desc": self._versions(block)})
            self.addVideo(params)
            return True
        year = self.cm.ph.getSearchGroups(block, r'<span(?: class="year")?>((?:19|20)\d{2})</span>')[0]
        plot = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)<div class="(?:texto|contenido)">(.*?)</div>')[0])
        genres = ", ".join(self.cleanHtmlStr(x) for x in re.findall(r'rel="tag">([^<]+)</a>', block))
        desc = " | ".join("%s: %s" % (label, value) for label, value in ((_("Year"), year), (_("Genre"), genres), (_("Version"), self._versions(block))) if value)
        if plot:
            desc = "%s[/br]%s" % (desc, plot) if desc else plot
        params["desc"] = desc
        if kind == "tvshows":
            params.update({"category": "jet_series", "title": title, "s_title": title, "meta_type": "tv", "meta_title": title, "meta_year": year})
            self.addDir(params)
        else:
            withYear = year and normalize and not title.endswith("(%s)" % year)
            params.update({"category": "jet_video", "title": "%s (%s)" % (title, year) if withYear else title,
                           "meta_type": "movie", "meta_title": title, "meta_year": year})
            self.addVideo(params)
        return True

    def _versions(self, block):
        # "VF / VOSTFR" from the quality badge of a tile ("<star> HD FR<star> HD vostfr")
        quality = self.cm.ph.getSearchGroups(block, r'(?s)<span class="quality">(.*?)</span>')[0]
        versions = []
        for version in re.findall(r"(?i)\b(vostfr|vf|fr)\b", quality):
            version = "VF" if version.lower() in ("vf", "fr") else "VOSTFR"
            if version not in versions:
                versions.append(version)
        return " / ".join(versions)

    def _lastPage(self, data):
        last = self.cm.ph.getSearchGroups(data, r"<span>Page\s+\d+\s+de\s+(\d+)</span>")[0]
        return int(last) if last else 0

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or cItem["url"]
        pageTpl = baseUrl.replace("{", "{{").replace("}", "}}") + "page/{page}/"
        url = baseUrl if page <= 1 else pageTpl.format(page=page)
        printDBG("JetAnimes.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        # the "Featured" slider on top of every list page repeats the same titles on each page - left out
        seen, count = set(), 0
        for attrs, kind, block in _articles(data):
            if "post-featured-" in attrs:
                continue
            itemUrl = self.cm.ph.getSearchGroups(block, r'<a href="([^"]+)"')[0]
            if itemUrl in seen:
                continue
            seen.add(itemUrl)
            if self._addArticle(kind, block, normalize):
                count += 1
        lastPage = self._lastPage(data)
        listItem = dict(cItem, base_url=baseUrl, url=baseUrl)
        addPagingItems(self, listItem, page, bool(count) and lastPage > page, lastPage, pageTpl)

    def listSearchResult(self, cItem, searchPattern, searchType):
        page = cItem.get("page", 1)
        pattern = cItem.get("s_pattern") or searchPattern.strip()
        pageTpl = self.getFullUrl("page/{page}/?s=%s" % urllib_quote_plus(pattern))
        url = pageTpl.format(page=page)
        printDBG("JetAnimes.listSearchResult [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        count = 0
        for block in SEARCH_RE.findall(data):
            kind = "tvshows" if '<span class="tvshows">' in block else "movies"
            # same fields as a list tile under other class names
            block = TITLE_DIV_RE.sub(r"<h3>\1</h3>", block, 1)
            if self._addArticle(kind, block, normalize):
                count += 1
        lastPage = self._lastPage(data)
        listItem = dict(cItem, category="search_next_page", s_pattern=pattern)
        addPagingItems(self, listItem, page, bool(count) and lastPage > page, lastPage, pageTpl)

    def _seasons(self, data):
        # [(season, [(episode, url, label, icon)])] of a series page
        seasons = []
        for block in data.split("<div class='se-c'>")[1:]:
            season = self.cm.ph.getSearchGroups(block, r"<span class='se-t[^']*'>(\d+)</span>")[0]
            episodes = []
            for li in re.findall(r"(?s)<li class='mark-\d+'>(.*?)</li>", block):
                numbers = re.search(r"<div class='numerando'>\s*(\d+)\s*-\s*(\d+)", li)
                url = self.cm.ph.getSearchGroups(li, r"<a href='([^']+)'")[0]
                if not numbers or not url:
                    continue
                label = _dropNewMark(self.cleanHtmlStr(self.cm.ph.getSearchGroups(li, r"(?s)<a href='[^']+'>(.*?)</a>")[0]))
                icon = self.cm.ph.getSearchGroups(li, r"<img src='([^']+)'")[0]
                episodes.append((int(numbers.group(2)), url, label, icon))
            if season and episodes:
                seasons.append((int(season), episodes))
        return seasons

    def listSeasons(self, cItem):
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        seasons = self._seasons(data)
        if not seasons:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return
        if len(seasons) == 1:
            self._addEpisodes(cItem, seasons[0][0], seasons[0][1])
            return
        show = cItem.get("s_title") or cItem.get("title", "")
        base = cItem["url"].split("#")[0]
        for season, episodes in seasons:
            params = stripPagerKeys(dict(cItem))
            params.update({"name": "category", "category": "jet_season", "good_for_fav": True, "url": "%s#s%d" % (base, season),
                           "title": "%s - %s" % (show, formatSxxExx(season)) if IsMediaNamingNormalized() else "%s - %s %d" % (show, _("Season"), season),
                           "s_title": show, "s_season": season, "desc": "%s: %d" % (_("Episodes"), len(episodes))})
            self.addDir(params)

    def listSeasonEpisodes(self, cItem):
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        season = cItem.get("s_season", 1)
        for number, episodes in self._seasons(data):
            if number == season:
                self._addEpisodes(cItem, season, episodes)
                return
        SetIPTVPlayerLastHostError(_("No stream available"))

    def _addEpisodes(self, cItem, season, episodes):
        show = cItem.get("s_title") or cItem.get("title", "")
        for episode, url, label, icon in episodes:
            params = stripPagerKeys(dict(cItem))
            params.update({"name": "category", "category": "jet_video", "good_for_fav": True, "url": url,
                           "title": self._episodeTitle(show, season, episode, label), "icon": icon or cItem.get("icon", ""),
                           "s_title": show, "s_season": season, "s_episode": episode, "meta_type": "tv", "meta_title": show, "desc": label})
            self.addVideo(params)

    ###################################################
    # links
    ###################################################
    def _siteInfo(self, data):
        # (story, poster, {INFO fields}, original title) of a movie / series / episode page
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<div itemprop="description" class="wp-content">(.*?)<div id=.dt_galery')[0]) or \
            self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<div class="wp-content">(.*?)</div>')[0])
        poster = self.cm.ph.getSearchGroups(data, r'<div class="poster">\s*<img itemprop="image" src="([^"]+)"')[0]
        fields = {self.cleanHtmlStr(label).lower(): self.cleanHtmlStr(value) for label, value in _fieldPairs(data)}
        info = {}
        for key, label in (("seasons", "saisons"), ("episodes", "episodes"), ("duration", "average duration"), ("rating", "imdb note")):
            if fields.get(label):
                info[key] = fields[label]
        # the series field is "Premiere date d'air" with an accent - matched on its ASCII part
        date = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r"<span class='date' itemprop='dateCreated'>([^<]+)</span>")[0]) or \
            "".join(value for label, value in fields.items() if "date d" in label and "air" in label)
        year = self.cm.ph.getSearchGroups(date, r"((?:19|20)\d{2})")[0]
        if year:
            info["year"] = year
        runtime = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r"class='runtime'>([^<]+)</span>")[0])
        if runtime:
            info["duration"] = runtime
        genres = ", ".join(self.cleanHtmlStr(x) for x in re.findall(r'genre/[^"]+" rel="tag">([^<]+)</a>',
                                                                   self.cm.ph.getDataBeetwenMarkers(data, '<div class="sgeneros">', "</div>", False)[1]))
        if genres:
            info["genres"] = genres
        return story, poster, info, fields.get("titre original", "")

    def _players(self, data, pageUrl):
        # [(label, hoster url)] from the DooPlay player options of a page
        players = []
        for dtype, post, nume, body in _players(data):
            if nume == "trailer":
                continue
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(body, r"<span class='title'>(.*?)</span>")[0])
            flag = self.cm.ph.getSearchGroups(body, r"/flags/([a-z]+)\.png")[0]
            params = dict(self.defaultParams, header=dict(self.HEADER, Referer=pageUrl, **{"X-Requested-With": "XMLHttpRequest"}))
            sts, ret = self.getPage(self.getFullUrl("wp-admin/admin-ajax.php"), params, {"action": "doo_player_ajax", "post": post, "nume": nume, "type": dtype})
            if not sts:
                continue
            try:
                url = json_loads(ret).get("embed_url", "")
            except Exception:
                printExc()
                continue
            url = self.cm.ph.getSearchGroups(url, r"""<iframe[^>]+src=['"]([^'"]+)['"]""")[0] or url
            url = self.getFullUrl(url.strip())
            if "secured.lol/" in url:
                # short link of the site, a 301 to the hoster
                sts = self.cm.getPage(url, dict(self.defaultParams, header=dict(self.HEADER, Referer=pageUrl), no_redirection=True))[0]
                url = self.cm.meta.get("location", "") if sts else ""
            if self.cm.isValidUrl(url):
                players.append(("%s [%s]" % (label, flag.upper()) if flag else label, url))
        return players

    def getLinksForVideo(self, cItem):
        url = cItem.get("url", "")
        printDBG("JetAnimes.getLinksForVideo [%s]" % url)
        if self.cacheLinks.get(url):
            return self.cacheLinks[url]
        sts, data = self.getPage(url)
        if not sts:
            return []
        urltab, seen = [], set()
        for label, playerUrl in self._players(data, url):
            if playerUrl in seen:
                continue
            seen.add(playerUrl)
            if self.up.checkHostSupport(playerUrl) != 1:
                printDBG("JetAnimes.getLinksForVideo unsupported hoster [%s]" % playerUrl)
                continue
            urltab.append({"name": "%s - %s" % (self.up.getHostName(playerUrl), label) if label else self.up.getHostName(playerUrl),
                           "url": strwithmeta(playerUrl, {"Referer": self.getMainUrl()}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        urltab.sort(key=self._linkRank)  # fix 071026: reliable servers first
        story = self._siteInfo(data)[0]
        urltab = applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), story))
        self.cacheLinks[url] = urltab
        return urltab

    def _linkRank(self, item):
        # fix 071026: Byse (hdsplay2) and ok.ru first; the VidHide/FileLions/StreamWish family (hdsplay) last:
        # its hls2 CDN (acek-cdn & co.) has edges that crawl at ~100 kbit/s and drop the connection
        parser = getattr(self.up.getParser(item["url"]), "__name__", "")
        if parser in ("parserBYSE", "parserOKRU"):
            return 0
        return 2 if parser == "parserJWPLAYER" else 1

    def getVideoLinks(self, videoUrl):
        printDBG("JetAnimes.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("JetAnimes.getArticleContent [%s]" % cItem.get("url", ""))
        story, poster, info, original = "", "", {}, ""
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            story, poster, info, original = self._siteInfo(data)
        mediaType = cItem.get("meta_type") or "movie"
        metaTitle = cItem.get("meta_title") or cItem.get("s_title") or cItem.get("title", "")
        year = "" if cItem.get("s_episode") else (cItem.get("meta_year") or info.get("year", ""))
        meta = {}
        try:
            meta = getMeta(mediaType, metaTitle, year)
            if not meta and original:
                meta = getMeta(mediaType, original, year)
        except Exception:
            printExc()
        siteInfo = dict(info)
        info.update(meta.get("info", {}))
        # the episode page knows the episode, moviemeta the show
        if cItem.get("s_episode"):
            info.update(siteInfo)
        plot = meta.get("plot", "")
        text = story or plot or cItem.get("desc", "")
        if plot and story and plot != story:
            text = "%s[/br][/br]%s" % (story, plot)
        icon = (self.getFullIconUrl(poster) if poster and cItem.get("s_episode") else "") or meta.get("poster") or \
            (self.getFullIconUrl(poster) if poster else cItem.get("icon", ""))
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": info}]

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
        printDBG("JetAnimes.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu()
        elif category == "jet_genres":
            self.listGenres(self.currItem)
        elif category == "jet_years":
            self.listYears(self.currItem)
        elif category == "jet_list":
            self.listItems(self.currItem)
        elif category == "jet_series":
            self.listSeasons(self.currItem)
        elif category == "jet_season":
            self.listSeasonEpisodes(self.currItem)
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
        CHostBase.__init__(self, JetAnimes(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("jetanimes")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video" or cItem.get("category", "") in FOLDER_CATEGORIES
