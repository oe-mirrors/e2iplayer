# -*- coding: utf-8 -*-
LAST_MODIFIED = "31.10.2026"
# RTP Play: live TV and radio, programmes and episodes of the Portuguese public broadcaster.
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import normalizeMediathekTitle
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
###################################################
# FOREIGN import
###################################################
import base64
import re

try:
    from urlparse import urljoin
except ImportError:
    from urllib.parse import urljoin
###################################################


def GetConfigList():
    return []


def gettytul():
    return "https://www.rtp.pt/play/"


# /play/direto shows the running programme instead of the channel
LIVE_NAMES = [("rtp1", "RTP1"), ("rtp2", "RTP2"), ("rtp3", "RTP3"), ("rtpmemoria", "RTP Memória"),
              ("rtpinternacional", "RTP Internacional"), ("rtpmadeira", "RTP Madeira"), ("rtpacores", "RTP Açores"),
              ("rtpafrica", "RTP África"), ("rtpdesporto1", "RTP Desporto 1"), ("rtpdesporto2", "RTP Desporto 2"),
              ("rtpdesporto3", "RTP Desporto 3"), ("rtpdesporto4", "RTP Desporto 4"), ("antena1", "Antena 1"),
              ("antena2", "Antena 2"), ("antena3", "Antena 3"), ("rdpinternacional", "RDP Internacional"),
              ("rdpafrica", "RDP África"), ("antena1madeira", "Antena 1 Madeira"), ("antena3madeira", "Antena 3 Madeira"),
              ("antena1acores", "Antena 1 Açores"), ("antena1fado", "RTP Fado"), ("radiolusitania", "RTP Lusitânia"),
              ("antena2jazzin", "RTP Jazz In"), ("antena2opera", "RTP Ópera")]
LIVE_NAME = dict(LIVE_NAMES)
RADIO_SLUG = re.compile(r"^(?:antena|rdp|radio)", re.I)
# title, path, what the programmes of the hub are for the movie metadata
HUBS = [("Séries", "hub/series", "tv"), ("Documentários", "hub/documentarios", ""), ("Desporto", "hub/rtpdesporto", ""),
        ("Infantil (ZigZag)", "zigzag/", ""), ("Palco (cultura)", "palco/", "")]
CATALOGS = [("Podcasts", "podcasts", "bg_l_pd"), ("Todos os programas", "programas", "bg_l_pg")]
# the other shelf types are live channels, link tiles or belong to a login
SHELF_TYPES = ("highlights", "most-popular", "last-programas")
THEME_RE = re.compile(r'''<a\b[^>]*href=['"]([^'"]*/play/(?:programas|podcasts)/[a-z-]+/canal)['"][^>]*>.*?<h4>(.*?)</h4>''', re.S | re.I)
LIST_PAGE_SIZE = 12
PROG_RE = re.compile(r'''<a\b([^>]*?)href=['"]([^'"]*?/play/(?:[a-z]+/)?p(\d+)(?:/e\d+)?(?:/(?!e\d*/)[^/'"?#]*)?/?)['"]([^>]*)>(.*?)</a>''', re.S | re.I)
EPISODE_RE = re.compile(r'''<a\b[^>]*href=['"]([^'"]*?/play/(?:[a-z]+/)?p\d+/e(\d+)/[^'"]*)['"]([^>]*)>(.*?)</a>''', re.S | re.I)
SEASON_TAIL = r"\s*\|\s*temporada \d+.*$"
MONTHS = {"jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6, "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12}


def isoDate(text):
    # "30 out. 2026" -> "2026-10-30", "" for anything else
    m = re.search(r"(\d{1,2})\s+([a-z]{3})\S*\s+(\d{4})", (text or "").lower())
    if m and m.group(2) in MONTHS:
        return "%s-%02d-%02d" % (m.group(3), MONTHS[m.group(2)], int(m.group(1)))
    return ""


def shelfType(title, default=""):
    # a shelf's own name tells more than the hub it is on
    if re.search(r"cinema|filme", title, re.I):
        return "movie"
    if re.search(r"s(?:e|é)ries?", title, re.I):
        return "tv"
    return default


class RTPPlay(GenericFolderWatchedScraperMixin, CBaseHostClass):

    def __init__(self):
        printDBG("RTPPlay.__init__")
        CBaseHostClass.__init__(self, {"history": "rtpplay", "cookie": "rtpplay.cookie"})
        self.MAIN_URL = "https://www.rtp.pt"
        self.PLAY_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/rtpplay135.png")
        self.USER_AGENT = self.cm.getDefaultUserAgent()
        self.HEADER = {"User-Agent": self.USER_AGENT, "Accept": "text/html,application/xhtml+xml", "Referer": self.PLAY_URL,
                       # answers the site's privacy and parental-control questions
                       "Cookie": "rtp_cookie_parental=0; rtp_privacy=666; rtp_cookie_privacy=permit 1,2,3,4; googlepersonalization=1"}
        self.pagePeek = {}
        self.watchedHelper = IPTVWatchedHelper("rtpplay")
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict) or cItem.get("live"):
                return ""
            url = self.wfNormalizeUrlKey(cItem.get("url", ""))
            if not url:
                return ""
            if cItem.get("type", "") == "video":
                return "video:%s" % url
            if cItem.get("category", "") == "rtp_episodes":
                return "folder:%s" % url
        except Exception:
            printExc()
        return ""

    ###################################################
    # helpers
    ###################################################
    def getPage(self, url):
        return self.cm.getPage(url, {"header": dict(self.HEADER)})

    def _clean(self, txt):
        return self.cleanHtmlStr(txt).strip()

    def _img(self, block):
        for attr in ("data-src", "data-original", "data-lazy-src", "src"):
            m = re.search(r"""<img[^>]+%s=['"]([^'"]+)['"]""" % attr, block, re.I)
            if m and "blank" not in m.group(1) and not m.group(1).startswith("data:"):
                return self.getFullUrl(m.group(1).replace("&amp;", "&"))
        m = re.search(r"""(?:data-srcset|srcset)=['"]\s*([^\s'",]+)""", block, re.I)
        if m and not m.group(1).startswith("data:"):
            return self.getFullUrl(m.group(1).replace("&amp;", "&"))
        return ""

    def _attrTitle(self, attrs):
        m = re.search(r"""title=(["'])(.*?)\1""", attrs, re.S)
        if not m:
            return ""
        return self._clean(re.sub(r"^\s*Aceder a:?\s*", "", m.group(2)))

    def _parsePrograms(self, data):
        progs, seen = [], set()
        for m in PROG_RE.finditer(data):
            pre, href, pid, post, inner = m.groups()
            if pid in seen:
                continue
            # a card of a programme's latest episode: its title without the episode, the link without it
            epTitle = re.search(r"episode-title[^>]*>(.*?)</", inner, re.S)
            title = (self._clean(epTitle.group(1)) if epTitle else "") or self._attrTitle(pre + " " + post)
            if not title:
                alt = re.search(r"""alt=["'](?:Imagem do Programa / Episi[óo]dio - |Imagem de\s*)?([^"']+)["']""", inner)
                title = self._clean(alt.group(1)) if alt else self._clean(inner)
            if title.startswith("-"):
                # "- Vasco Cordeiro | PS": only the episode part, the programme is in the link
                title = href.rstrip("/").rsplit("/", 1)[-1].replace("-", " ").capitalize()
            title = re.sub(SEASON_TAIL, "", title)
            if not title or title.lower() in ("ver mais", "ver todos"):
                continue
            seen.add(pid)
            progs.append({"title": title, "url": self.getFullUrl(re.sub(r"/e\d+(?=/|$)", "", href)), "icon": self._img(inner)})
        return progs

    def _parseEpisodes(self, data):
        """The episode cards of a list: name (of the link), date, episode part, url, icon."""
        rows = []
        for art in re.findall(r"<article\b.*?</article>", data, re.S | re.I):
            link = re.search(r"""<a\b[^>]*href=['"]([^'"]+)['"][^>]*>""", art)
            if not link:
                continue
            date = re.search(r"episode-date[^>]*>(.*?)</", art, re.S)
            date = re.sub(SEASON_TAIL, "", self._clean(date.group(1))) if date else ""
            if not date:
                date = re.search(r"""<meta content=["'][^"']*?(\d{1,2} [a-z]{3}\.? \d{4})["']""", art)
                date = date.group(1) if date else ""
            title = re.search(r"episode-title[^>]*>(.*?)</", art, re.S)
            title = self._clean(title.group(1)) if title else ""
            # the search cards: programme in the title, episode in the lead
            leadTag = re.search(r"episode-lead[^>]*>(.*?)</", art, re.S)
            lead = self._clean(leadTag.group(1)) if leadTag else ""
            # some leads only are the text of the programme, starting with its name
            lead = "" if lead.startswith(title) else lead
            part = re.findall(r"<b[^>]*text-dark-gray[^>]*>(.*?)</b>", art, re.S)
            number = re.search(r"""class=['"]episode['"][^>]*>(.*?)</""", art, re.S)
            sub = lead or title or (self._clean(part[1]) if len(part) > 1 else "") or (self._clean(number.group(1)) if number else "")
            name = title if leadTag else re.sub(SEASON_TAIL, "", self._attrTitle(link.group(0)))
            rows.append({"name": name, "date": date, "sub": sub, "url": self.getFullUrl(link.group(1)), "icon": self._img(art)})
        return rows

    def _nextRows(self, key, rows, load):
        # the lists have no end marker, a full page can be the last one: the next page is read now and kept for when it opens
        nextRows = load()
        self.pagePeek = {key: nextRows}
        return bool(nextRows) and nextRows[0]["url"] != rows[0]["url"]

    def _pageDesc(self, data):
        m = re.search(r"""<meta[^>]+name=["']description["'][^>]+content=["']([^"']+)""", data)
        return self._clean(m.group(1)) if m else ""

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self, cItem):
        tab = [{"category": "rtp_shelves", "title": "Destaques", "url": self.PLAY_URL, "good_for_fav": True},
               {"category": "rtp_live", "title": "TV em direto", "kind": "tv", "good_for_fav": True},
               {"category": "rtp_live", "title": "Rádio em direto", "kind": "radio", "good_for_fav": True}]
        for title, path, metaType in HUBS:
            tab.append({"category": "rtp_shelves", "title": title, "url": self.PLAY_URL + path, "f_type": metaType, "good_for_fav": True})
        for title, path, endpoint in CATALOGS:
            tab.append({"category": "rtp_themes", "title": title, "url": self.PLAY_URL + path, "f_endpoint": endpoint, "good_for_fav": True})
        self.listsTab(tab + self.searchItems(), cItem)

    def listLive(self, cItem):
        printDBG("RTPPlay.listLive [%s]" % cItem.get("kind", ""))
        kind = cItem.get("kind", "tv")
        found, seen = [], set()
        sts, data = self.getPage(self.PLAY_URL + "direto")
        if sts:
            for m in re.finditer(r"""<a[^>]+href=['"][^'"]*?/play/direto/([^/'"?#]+)['"][^>]*>(.*?)</a>""", data, re.S | re.I):
                slug, inner = m.group(1), m.group(2)
                if slug not in seen:
                    seen.add(slug)
                    found.append((slug, self._clean(re.sub(r"(?i)^\s*imagem de\s*", "", self._clean(inner))), self._img(inner)))
        if not found:
            found = [(slug, "", "") for slug, _name in LIVE_NAMES]
        for slug, programme, icon in found:
            if (kind == "radio") != bool(RADIO_SLUG.match(slug)):
                continue
            title = LIVE_NAME.get(slug, slug.upper())
            self.addVideo({"name": "category", "category": "rtp_video", "title": title, "icon": icon, "good_for_fav": True, "live": True,
                           "url": "%sdireto/%s" % (self.PLAY_URL, slug), "desc": "" if programme == title else programme})

    def _addProgram(self, prog, metaType=""):
        params = {"name": "category", "category": "rtp_episodes", "title": prog["title"], "show": prog["title"],
                  "url": prog["url"], "icon": prog["icon"], "good_for_fav": True}
        if metaType:
            params.update({"meta_type": metaType, "meta_title": prog["title"]})
        self.addDir(params)

    def listShelves(self, cItem):
        # the page only names its shelves, the site's script loads each one when it scrolls into view
        url = cItem.get("url", "")
        printDBG("RTPPlay.listShelves [%s]" % url)
        sts, data = self.getPage(url)
        m = re.search(r"homepageShelfs\s*=\s*(\[.*?\]);", data or "", re.S) if sts else None
        if not m:
            return
        loader = re.search(r"""url:\s*['"]([^'"]*/shelf/)['"]""", data)
        base = self.getFullUrl(loader.group(1)) if loader else self.PLAY_URL + "shelf/"
        try:
            shelves = json_loads(m.group(1))
        except Exception:
            printExc()
            return
        for shelf in shelves:
            title = self._clean(shelf.get("title") or "")
            if title and shelf.get("type") in SHELF_TYPES:
                query = "&".join("%s=%s" % (key, urllib_quote_plus(str(shelf.get(key, "")))) for key in ("title", "display_type", "filtertype", "key"))
                self.addDir({"name": "category", "category": "rtp_shelf", "title": title, "url": "%s%s?%s" % (base, shelf["type"], query),
                             "f_type": shelfType(title, cItem.get("f_type", "")), "good_for_fav": True})

    def listShelf(self, cItem):
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            for prog in self._parsePrograms(data):
                self._addProgram(prog, cItem.get("f_type", ""))

    def listThemes(self, cItem):
        sts, data = self.getPage(cItem.get("url", ""))
        if not sts:
            return
        seen = set()
        for href, title in THEME_RE.findall(data):
            if href not in seen:
                seen.add(href)
                self.addDir({"name": "category", "category": "rtp_theme", "title": self._clean(title), "url": self.getFullUrl(href) + "/a-z",
                             "f_endpoint": cItem.get("f_endpoint", ""), "f_type": "tv" if "/ficcao/" in href else "", "good_for_fav": True})

    def _themeRows(self, cItem, page):
        # pages after the first, the first is in the page of the theme
        sts, data = self.getPage("%s%s/?listcategory=%s&listtype=az&page=%s&type=all" % (self.PLAY_URL, cItem.get("f_endpoint", ""), cItem.get("f_cat", ""), page))
        return self._parsePrograms(data) if sts else []

    def listTheme(self, cItem):
        printDBG("RTPPlay.listTheme [%s]" % cItem.get("url", ""))
        url = cItem.get("url", "")
        page = int(cItem.get("page", 1) or 1)
        key = ("theme", url, page)
        if key in self.pagePeek:
            rows = self.pagePeek.pop(key)
        elif page == 1:
            sts, data = self.getPage(url)
            data = data if sts else ""
            m = re.search(r"currentHPListCategory\s*=\s*'([^']*)'", data)
            cItem = dict(cItem, f_cat=m.group(1) if m else "")
            rows = self._parsePrograms(data[max(data.find("<main"), 0):])
        else:
            rows = self._themeRows(cItem, page)
        for prog in rows:
            self._addProgram(prog, cItem.get("f_type", ""))
        hasNext = len(rows) >= LIST_PAGE_SIZE and self._nextRows(("theme", url, page + 1), rows, lambda: self._themeRows(cItem, page + 1))
        addPagingItems(self, cItem, page, hasNext, 0, url)

    def _episodeRows(self, pid, page):
        sts, data = self.getPage("%sbg_l_ep/?listProgram=%s&listtype=recent&page=%s&type=all" % (self.PLAY_URL, pid, page))
        return self._parseEpisodes(data) if sts else []

    def _addEpisode(self, cItem, row):
        show = cItem.get("show") or cItem.get("title", "")
        sub = row["sub"] if row["sub"] != show else ""
        plain = "%s - %s" % (show, sub) if sub else show
        named = normalizeMediathekTitle(plain, date=isoDate(row["date"]))
        # the only thing telling the rows of a daily programme apart when the names are not normalized
        classic = " - ".join([x for x in (show, row["date"], sub) if x])
        params = {"name": "category", "category": "rtp_video", "title": named if named != plain else classic, "url": row["url"],
                  "icon": row["icon"] or cItem.get("icon", ""), "desc": row["date"], "good_for_fav": True}
        if cItem.get("meta_type"):
            params.update({"meta_type": cItem["meta_type"], "meta_title": cItem.get("meta_title", "")})
        self.addVideo(params)

    def listEpisodes(self, cItem):
        printDBG("RTPPlay.listEpisodes [%s]" % cItem.get("url", ""))
        url = cItem.get("url", "")
        page = int(cItem.get("page", 1) or 1)
        m = re.search(r"/play/(?:[a-z]+/)?p(\d+)", url)
        pid = m.group(1) if m else ""
        key = ("episodes", pid, page)
        rows = self.pagePeek.pop(key) if key in self.pagePeek else (self._episodeRows(pid, page) if pid else [])
        for row in rows:
            self._addEpisode(cItem, row)
        if rows or page > 1:
            hasNext = len(rows) >= LIST_PAGE_SIZE and self._nextRows(("episodes", pid, page + 1), rows, lambda: self._episodeRows(pid, page + 1))
            addPagingItems(self, cItem, page, hasNext, 0, url)
            return
        # no list for this programme: the episodes on its own page
        sts, data = self.getPage(url)
        if sts:
            seen = set()
            for href, eid, attrs, inner in EPISODE_RE.findall(data):
                if eid not in seen:
                    seen.add(eid)
                    label = self._clean(re.sub(r"(?i)^\s*imagem de\s*", "", self._clean(inner))) or self._attrTitle(attrs)
                    self._addEpisode(cItem, {"sub": label, "date": "", "url": self.getFullUrl(href), "icon": self._img(inner)})

    def _searchRows(self, query, page):
        # pages after the first, the first is in the search page
        sts, data = self.getPage("%sbg_l_s/?listQuery=%s&listtype=recent&page=%s&type=all" % (self.PLAY_URL, urllib_quote_plus(query), page))
        return self._parseEpisodes(data) if sts else []

    def _addSearchRows(self, cItem, rows, page):
        for row in rows:
            self._addEpisode({"show": row["name"]}, row)
        query = cItem.get("f_query", "")
        hasNext = bool(rows) and self._nextRows(("search", query, page + 1), rows, lambda: self._searchRows(query, page + 1))
        addPagingItems(self, cItem, page, hasNext, 0, cItem.get("url", ""))

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("RTPPlay.listSearchResult [%s]" % searchPattern)
        url = "%spesquisa?q=%s" % (self.PLAY_URL, urllib_quote_plus(searchPattern))
        sts, data = self.getPage(url)
        if not sts:
            return
        # the page's menus also link programmes: only the two result parts
        start = data.rfind("Programas</h")
        if start < 0:
            return
        split = data.find("Epis&oacute;dios</h", start)
        split = split if split > 0 else len(data)
        for prog in self._parsePrograms(data[start:split]):
            self._addProgram(prog)
        self._addSearchRows(dict(cItem, category="rtp_search", f_query=searchPattern, url=url), self._parseEpisodes(data[split:]), 1)

    def listSearchPage(self, cItem):
        query = cItem.get("f_query", "")
        page = int(cItem.get("page", 1) or 1)
        key = ("search", query, page)
        self._addSearchRows(cItem, self.pagePeek.pop(key) if key in self.pagePeek else self._searchRows(query, page), page)

    ###################################################
    # links
    ###################################################
    def _deobfuscate(self, data):
        # file: {hls: atob(decodeURIComponent(["aHR0", "cHM6", ...].join("")))}
        def repl(m):
            try:
                raw = base64.b64decode(urllib_unquote("".join(json_loads(m.group(1)))))
                if not isinstance(raw, str):
                    raw = raw.decode("iso-8859-1")
                return json_dumps(raw)
            except Exception:
                printExc()
                return m.group(0)
        return re.sub(r"""(?xs)atob\s*\(\s*decodeURIComponent\s*\(\s*(\[[0-9A-Za-z%,'"\s]*\])\s*\.\s*join\(\s*(?:""|'')\s*\)\s*\)\s*\)""", repl, data)

    def _mediaUrls(self, url):
        """(urls of the page's player without preview clips and DRM streams, whether the programme's own stream has DRM, text of the page)"""
        sts, data = self.getPage(url)
        if not sts:
            return [], False, ""
        desc = self._pageDesc(data)
        data = self._deobfuscate(data).replace("\\/", "/")
        # the page also holds the player of a station promo, a video of another programme's folder
        m = re.search(r"/play/(?:[a-z]+/)?(p\d+)/", url)
        folder = "/%s/" % m.group(1) if m else ""
        urls, drm = [], False
        for media in re.findall(r"""https?:[^"'\s<>\\]+?\.(?:m3u8|mp4|mp3)[^"'\s<>\\]*""", data):
            if "/drm-" in media:
                drm = drm or bool(folder and folder in media)
            elif "/preview/" not in media and ".mpd" not in media and media not in urls:
                urls.append(media)
        if folder:
            own = [x for x in urls if folder in x or not re.search(r"/p\d+/", x)]
            urls = own or ([] if drm else urls)
        return urls, drm, desc

    def _hlsVariants(self, master, meta):
        """The HLS variants best first (the player would start on the lowest one), then the master itself."""
        links = []
        sts, text = self.getPage(master)
        if not sts or "#EXTM3U" not in (text or ""):
            return links
        try:
            # the variants need the token of the master
            query = master.split("?", 1)[1] if "?" in master else ""
            lines = text.splitlines()
            variants = []
            for i, line in enumerate(lines):
                if not line.startswith("#EXT-X-STREAM-INF"):
                    continue
                res = re.search(r"RESOLUTION=(\d+)x(\d+)", line)
                bw = re.search(r"BANDWIDTH=(\d+)", line)
                uri = ""
                for nxt in lines[i + 1:]:
                    if nxt.strip() and not nxt.startswith("#"):
                        uri = nxt.strip()
                        break
                if not uri:
                    continue
                url = urljoin(master, uri)
                if query and "?" not in url:
                    url += "?" + query
                w, h = (int(res.group(1)), int(res.group(2))) if res else (0, 0)
                variants.append((h, int(bw.group(1)) if bw else 0, w, url))
            variants.sort(reverse=True)
            for h, bw, w, url in variants:
                name = "%sx%s  %s kbps" % (w, h, bw // 1000) if h else "%s kbps" % (bw // 1000)
                links.append({"name": name, "url": strwithmeta(url, dict(meta)), "need_resolve": 0})
        except Exception:
            printExc()
        links.append({"name": "HLS (auto)", "url": strwithmeta(master, dict(meta)), "need_resolve": 0})
        return links

    def getLinksForVideo(self, cItem):
        printDBG("RTPPlay.getLinksForVideo [%s]" % cItem.get("url", ""))
        live = bool(cItem.get("live"))
        meta = {"User-Agent": self.USER_AGENT, "Referer": self.PLAY_URL, "iptv_livestream": live}
        linksTab = []
        urls, drm, desc = self._mediaUrls(cItem.get("url", ""))
        for url in urls:
            if ".m3u8" in url:
                linksTab.extend(self._hlsVariants(url, dict(meta, iptv_proto="m3u8")))
            else:
                linksTab.append({"name": url.rsplit(".", 1)[-1].split("?", 1)[0].upper(), "url": strwithmeta(url, meta), "need_resolve": 0})
        if not linksTab:
            if drm:
                SetIPTVPlayerLastHostError(_("Video with DRM protection."))
            elif urls and self.cm.meta.get("status_code") == 403:
                # streams for Portugal only: their folder is /pt/
                SetIPTVPlayerLastHostError(_("Not available in your country (geo-blocking)."))
            else:
                SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return linksTab if live else applySidecarToLinks(linksTab, buildSidecarFromItem(cItem, IsSidecarEnabled(), desc))

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("RTPPlay.getArticleContent [%s]" % cItem.get("url", ""))
        title, text, icon = cItem.get("title", ""), cItem.get("desc", ""), cItem.get("icon", "")
        info = {"station": "RTP Play"}
        if cItem.get("live"):
            info["status"] = _("On Air")
            text = "%s - %s" % (title, text) if text else "%s - %s" % (title, _("Live"))
        else:
            sts, data = self.getPage(cItem.get("url", ""))
            if sts:
                text = self._pageDesc(data) or text
                m = re.search(r"""<meta[^>]+property=["']og:image["'][^>]+content=["']([^"']+)""", data)
                icon = m.group(1) if m else icon
            if cItem.get("meta_type") and cItem.get("meta_title"):
                try:
                    # the site's text and picture first, the service adds what the site does not have
                    meta = getMeta(cItem["meta_type"], cItem["meta_title"])
                    for key, value in (meta.get("info") or {}).items():
                        info.setdefault(key, value)
                    text = text or meta.get("plot", "")
                    icon = icon or meta.get("poster", "")
                except Exception:
                    printExc()
        return [{"title": title, "text": text or title, "images": [{"title": "", "url": icon}] if icon else [], "other_info": info}]

    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("RTPPlay.handleService start")
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", None)
        category = self.currItem.get("category", "")
        printDBG("RTPPlay.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "rtp_live":
            self.listLive(self.currItem)
        elif category == "rtp_shelves":
            self.listShelves(self.currItem)
        elif category == "rtp_shelf":
            self.listShelf(self.currItem)
        elif category == "rtp_themes":
            self.listThemes(self.currItem)
        elif category == "rtp_theme":
            self.listTheme(self.currItem)
        elif category == "rtp_episodes":
            self.listEpisodes(self.currItem)
        elif category == "search":
            self.listSearchResult(self.currItem, searchPattern, searchType)
        elif category == "rtp_search":
            self.listSearchPage(self.currItem)
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc", _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, RTPPlay(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("rtpplay")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("rtp_video", "rtp_episodes")
