# -*- coding: utf-8 -*-
LAST_MODIFIED = "31.10.2026"
# France.tv: live channels and replay without DRM. Replay and some live channels need a French IP.
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, getMPDLinksWithMeta
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import normalizeMediathekTitle
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
###################################################
# FOREIGN import
###################################################
from datetime import timedelta
import re

try:
    from urlparse import urljoin
except ImportError:
    from urllib.parse import urljoin
###################################################


def GetConfigList():
    return []


def gettytul():
    return "https://www.france.tv/"


# /directs/ names the channels by their programme only
LIVE_NAMES = {"france-2": "France 2", "france-3": "France 3", "france-4": "France 4", "france-5": "France 5", "franceinfo": "franceinfo",
              "arte": "Arte", "tv5-monde": "TV5 Monde", "france-24": "France 24", "mieux": "Mieux", "sport": "Sport",
              "documentaire": "Documentaire", "serie": "Série", "ina": "INA", "lcp-public-senat": "LCP / Public Sénat",
              "la-chaine-des-maternelles": "La Chaîne des Maternelles"}
LIVE_FALLBACK = ["france-2", "france-3", "france-4", "france-5", "franceinfo"]
CHANNELS = [("France 2", "france-2"), ("France 3", "france-3"), ("France 4", "france-4"), ("France 5", "france-5"),
            ("franceinfo", "franceinfo"), ("Arte", "arte"), ("France 24", "france-24"), ("TV5 Monde", "tv5-monde"),
            ("LCP", "lcp"), ("Public Sénat", "public-senat"), ("INA", "ina")]
SECTIONS = [("Séries et fictions", "series-et-fictions"), ("Films", "films"), ("Documentaires", "documentaires"),
            ("Info", "info"), ("Société", "societe"), ("Sport", "sport"), ("Enfants", "enfants"),
            ("Spectacles et culture", "spectacles-et-culture"), ("Jeux et divertissements", "jeux-et-divertissements"),
            ("Mieux", "mieux")]
# page parts without anything to play
SKIPPED_PARTS = ("En direct", "Catégories", "À propos", "Nos partenaires", "Parcourir la catégorie")
BADGES = ("Direct", "Sponsorisé")
TOKEN_URL = "https://hdfauth.ftven.fr/esi/TA?format=json"
CARD_RE = r'<a\b[^>]*data-card-link="true"[^>]*>.*?</a>'


class FranceTV(GenericFolderWatchedScraperMixin, CBaseHostClass):

    def __init__(self):
        printDBG("FranceTV.__init__")
        CBaseHostClass.__init__(self, {"history": "francetv", "cookie": "francetv.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/francetv135.png")
        self.USER_AGENT = self.cm.getDefaultUserAgent()
        self.HEADER = {"User-Agent": self.USER_AGENT, "Accept": "text/html,application/xhtml+xml,application/json",
                       "Referer": self.MAIN_URL, "Accept-Language": "fr-FR,fr;q=0.9"}
        self.pageCache = ("", "")
        self.watchedHelper = IPTVWatchedHelper("francetv")
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
            if cItem.get("category", "") == "ftv_page" and re.search(r"france\.tv/.+/.+/", url):
                return "folder:%s" % url
        except Exception:
            printExc()
        return ""

    ###################################################
    # helpers
    ###################################################
    def getPage(self, url):
        return self.cm.getPage(url, {"header": dict(self.HEADER)})

    def _html(self, url):
        # the section rows of a page and their lists come from the same page
        if self.pageCache[0] != url:
            sts, data = self.getPage(url)
            printDBG("FranceTV._html [%s] sts[%s] len[%s]" % (url, sts, len(data) if data else 0))
            if not sts or not data:
                return ""
            self.pageCache = (url, data)
        return self.pageCache[1]

    def _spans(self, card):
        spans = [self.cleanHtmlStr(x) for x in re.findall(r"<span\b[^>]*>(.*?)</span>", card, re.S)]
        return [x for x in spans if x and x not in BADGES and not x.startswith("Progression en cours")]

    def _parseCard(self, card):
        """A card of a page as a dict: path, spans (title first, badges removed), icon; None for other links."""
        m = re.search(r'href="([^"#?]+)', card)
        if not m:
            return None
        path = re.sub(r"^https?://www\.france\.tv", "", m.group(1))
        if not path.startswith("/") or path.endswith("/direct.html"):
            return None
        if not path.endswith("/") and not re.search(r"/\d+-[^/]+\.html$", path):
            return None
        spans = self._spans(card)
        if not spans:
            return None
        icon = re.search(r'<img\b[^>]*?\ssrc="([^"]+)"', card)
        icon = icon.group(1).replace("&amp;", "&") if icon else ""
        return {"path": path, "spans": spans, "icon": "" if icon.startswith("data:") else icon}

    def _parseCards(self, html):
        cards = [self._parseCard(x) for x in re.findall(CARD_RE, html, re.S)]
        return [x for x in cards if x]

    def _parseSections(self, html):
        """[(title of the page part, cards)] for the <h2> parts with something to play."""
        heads = list(re.finditer(r"<h2\b[^>]*>(.*?)</h2>", html, re.S))
        sections = []
        for i, head in enumerate(heads):
            title = self.cleanHtmlStr(head.group(1))
            if not title or title in SKIPPED_PARTS:
                continue
            end = heads[i + 1].start() if i + 1 < len(heads) else len(html)
            cards = self._parseCards(html[head.end():end])
            if cards:
                sections.append((title, cards))
        return sections

    @staticmethod
    def _showOfPath(path):
        # /france-3/meurtres-a/meurtres-a-saison-9/123-x.html, /france-3/alex-hugo/saison-11/123-x.html
        segs = [x for x in path.split("/") if x]
        if len(segs) >= 3:
            m = re.match(r"(.*?)-?saison-\d+$", segs[-2])
            if m:
                return (m.group(1) or segs[-3]).replace("-", " ").capitalize()
        return ""

    def _showOfPage(self, html):
        # a programme's page and its "all videos" page
        m = re.search(r"<h1\b[^>]*>(.*?)</h1>", html, re.S)
        return self.cleanHtmlStr(m.group(1)).replace("Toutes les vidéos", "").strip() if m else ""

    @staticmethod
    def _setMovieMeta(params, path, name):
        # the site's own paths tell films and series apart; the rows below a series keep its fields from the listed item
        ofSeriesPage = params.pop("f_series", False)
        if path.startswith("/collection/"):
            params.pop("meta_type", None)
            params.pop("meta_title", None)
        elif params.get("meta_type"):
            return
        elif path.startswith("/films/") or "/films-tv/" in path:
            params.update({"meta_type": "movie", "meta_title": name})
        elif path.endswith("/") and (ofSeriesPage or path.startswith("/series-et-fictions/")):
            params.update({"meta_type": "tv", "meta_title": name})

    def _addCard(self, cItem, card, show=""):
        try:
            spans = card["spans"]
            title = spans[0]
            desc = spans[1:]
            if show and title == show and desc:
                # the rows of a programme's own page: programme, episode
                title = "%s - %s" % (show, desc[0])
                desc = desc[1:]
            params = stripPagerKeys(dict(cItem), ("section", "show", "live"))
            params.update({"name": "category", "url": self.MAIN_URL.rstrip("/") + card["path"], "icon": card["icon"],
                           "desc": "[/br]".join(desc), "good_for_fav": True})
            self._setMovieMeta(params, card["path"], spans[0])
            if card["path"].endswith("/"):
                params.update({"category": "ftv_page", "title": title})
                self.addDir(params)
                return
            sxe = re.match(r"(?:(.*) - )?S(\d+)\s*E(\d+)(?:\s*-\s*(.*))?$", title)
            if sxe:
                # the heading of a programme's own page, on other pages it is only the name of that page
                ofPage = show if show.lower().replace(" ", "-") in card["path"] else ""
                parts = (sxe.group(1) or ofPage or self._showOfPath(card["path"]) or show or cItem.get("title", ""), sxe.group(4))
                title = normalizeMediathekTitle(" - ".join([x for x in parts if x]), sxeHint="S%02dE%02d" % (int(sxe.group(2)), int(sxe.group(3))))
            else:
                title = normalizeMediathekTitle(title)
            params.update({"category": "ftv_video", "title": title})
            self.addVideo(params)
        except Exception:
            printExc()

    ###################################################
    # menus
    ###################################################
    def listMainMenu(self, cItem):
        tab = [{"category": "ftv_live", "title": _("Live"), "good_for_fav": True},
               {"category": "ftv_channels", "title": _("Channels"), "good_for_fav": True}]
        for title, slug in SECTIONS:
            tab.append({"category": "ftv_page", "title": title, "url": "%s%s/" % (self.MAIN_URL, slug), "f_series": slug == "series-et-fictions", "good_for_fav": True})
        self.listsTab(tab, cItem)

    def listChannels(self, cItem):
        for title, slug in CHANNELS:
            self.addDir({"name": "category", "category": "ftv_page", "title": title, "url": "%s%s/" % (self.MAIN_URL, slug), "good_for_fav": True})

    def listLive(self, cItem):
        rows = []
        for card in re.findall(CARD_RE, self._html(self.MAIN_URL + "directs/"), re.S):
            m = re.search(r'href="/([^/"]+)/direct\.html"', card)
            if m and m.group(1) not in [x[0] for x in rows]:
                rows.append((m.group(1), self._spans(card)))
        for slug, spans in rows or [(x, []) for x in LIVE_FALLBACK]:
            self.addVideo({"name": "category", "category": "ftv_video", "title": LIVE_NAMES.get(slug, slug.replace("-", " ").title()),
                           "url": "%s%s/direct.html" % (self.MAIN_URL, slug), "desc": "[/br]".join(spans), "live": True, "good_for_fav": True})

    def listPage(self, cItem):
        printDBG("FranceTV.listPage [%s]" % cItem.get("url", ""))
        html = self._html(cItem.get("url", ""))
        if not html:
            return
        sections = self._parseSections(html)
        show = self._showOfPage(html)
        allVideos = re.search(r'href="(/[^"]*/toutes-les-videos/)"', html)
        if allVideos:
            params = stripPagerKeys(dict(cItem), ("section", "show"))
            params.update({"category": "ftv_all", "title": _("All videos"), "url": self.MAIN_URL.rstrip("/") + allVideos.group(1), "desc": "", "good_for_fav": True})
            self.addDir(params)
        if len(sections) == 1 and not allVideos:
            for card in sections[0][1]:
                self._addCard(cItem, card, show)
            return
        for title, cards in sections:
            params = stripPagerKeys(dict(cItem))
            params.update({"category": "ftv_section", "title": title, "section": title, "show": show, "icon": cards[0]["icon"], "desc": "", "good_for_fav": True})
            self.addDir(params)

    def listSection(self, cItem):
        pageUrl = cItem.get("url", "")
        for title, cards in self._parseSections(self._html(pageUrl)):
            if title == cItem.get("section"):
                for card in cards:
                    # a programme lists itself below its episodes
                    if self.MAIN_URL.rstrip("/") + card["path"] != pageUrl:
                        self._addCard(cItem, card, cItem.get("show", ""))
                break

    def listAllVideos(self, cItem):
        base = cItem.get("url", "").split("?", 1)[0]
        page = int(cItem.get("page", 1) or 1)
        html = self._html("%s?page=%d" % (base, page) if page > 1 else base)
        if not html:
            return
        show = self._showOfPage(html)
        for card in self._parseCards(html):
            self._addCard(cItem, card, show)
        pages = [int(x) for x in re.findall(r'href="[^"]*[?&]page=(\d+)"', html)]
        lastPage = max(pages + [page])
        addPagingItems(self, dict(cItem, url=base), page, page < lastPage, lastPage, base + "?page={page}")

    ###################################################
    # links
    ###################################################
    def _videoInfo(self, pageUrl):
        """The player data of a page: k7 "video" and "meta" of the first device with a stream, error message.
        The page's own player ("options") first: a live channel's page also holds the id of a replay."""
        data = self._html(pageUrl)
        m = re.search(r'\\?"options\\?"\s*:\s*\{\s*\\?"id\\?"\s*:\s*\\?"([0-9a-f-]{36})', data) or \
            re.search(r'playerReplayId\\?"\s*:\s*\\?"([0-9a-f-]{36})', data)
        if not m:
            return {}, {}, ""
        # safari gets HLS, chrome DASH
        video, meta, error = {}, {}, ""
        for device, browser in (("mobile", "safari"), ("desktop", "chrome")):
            api = "https://k7.ftven.fr/videos/%s?country_code=FR&w=1920&h=1080&domain=www.france.tv&device_type=%s&browser=%s" % (m.group(1), device, browser)
            sts, text = self.getPage(api)
            try:
                j = json_loads(text) if sts else {}
            except Exception:
                printExc()
                continue
            meta = j.get("meta") or meta
            error = j.get("message") or error
            video = j.get("video") or {}
            if video.get("url") and not video.get("drm"):
                return video, meta, ""
        return video, meta, error

    def _sign(self, video):
        tokenUrl = (video.get("token") or {}).get("akamai") or TOKEN_URL
        sts, data = self.getPage("%s&url=%s" % (tokenUrl, urllib_quote_plus(video["url"])))
        if sts:
            try:
                return json_loads(data).get("url") or video["url"]
            except Exception:
                printExc()
        return video["url"]

    def _segmentsBlocked(self, master, masterUrl):
        # outside France most live playlists still answer, only their segments are refused (403)
        try:
            uris = [x.strip() for x in master.splitlines() if x.strip() and not x.startswith("#")]
            playlistUrl = urljoin(masterUrl, uris[0]) if uris else ""
            sts, playlist = self.getPage(playlistUrl) if playlistUrl else (False, "")
            segments = [x.strip() for x in (playlist or "").splitlines() if x.strip() and not x.startswith("#")]
            if segments:
                sts, _data = self.cm.getPage(urljoin(playlistUrl, segments[-1]), {"header": dict(self.HEADER, Range="bytes=0-0"), "max_data_size": 65536})
                return not sts and self.cm.meta.get("status_code") == 403
        except Exception:
            printExc()
        return False

    def getLinksForVideo(self, cItem):
        printDBG("FranceTV.getLinksForVideo [%s]" % cItem.get("url", ""))
        video, meta, error = self._videoInfo(cItem.get("url", ""))
        if not video.get("url") or video.get("drm"):
            SetIPTVPlayerLastHostError(_("Video with DRM protection.") if video.get("drm") else (error or _("No stream available")))
            return []
        url = self._sign(video)
        live = bool(video.get("is_live"))
        urlMeta = {"User-Agent": self.USER_AGENT, "Referer": self.MAIN_URL, "iptv_livestream": live}
        subs = [{"title": "Français", "url": s["url"], "lang": "fr", "format": "vtt"} for s in (meta.get("subtitles") or []) if s.get("url")]
        if subs:
            urlMeta["external_sub_tracks"] = subs
        urlTab = []
        if ".mpd" in url.split("?", 1)[0]:
            urlTab = getMPDLinksWithMeta(strwithmeta(url, urlMeta), False)
        else:
            sts, master = self.getPage(url)
            if not sts or "#EXTM3U" not in (master or "") or self._segmentsBlocked(master, url):
                SetIPTVPlayerLastHostError(_("Not available in your country (geo-blocking)."))
                return []
            hlsMeta = dict(urlMeta, iptv_proto="m3u8")
            for item in getDirectM3U8Playlist(strwithmeta(url, hlsMeta), checkExt=False, checkContent=not live, sortWithMaxBitrate=99999999):
                if strwithmeta(item["url"]).meta.get("audio_url"):
                    # separate audio and video renditions are muxed with ffmpeg
                    extraMeta = {"iptv_use_ffmpeg": True}
                    if not live:
                        extraMeta.update({"ff_out_container": "matroska", "iptv_format": "mkv"})
                    item["url"] = self.up.decorateUrl(item["url"], extraMeta)
                item["need_resolve"] = 0
                urlTab.append(item)
            if live:
                # last: buffered through hlsdl it loses the separate audio, unbuffered the player takes the lowest quality
                urlTab.append({"name": "HLS (auto)", "url": strwithmeta(url, hlsMeta), "need_resolve": 0})
        if not urlTab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        if live:
            return urlTab
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled(), self.cleanHtmlStr(meta.get("description") or "")))

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("FranceTV.getArticleContent [%s]" % cItem.get("url", ""))
        info = {"station": "France.tv"}
        title, text, icon = "", cItem.get("desc", ""), cItem.get("icon", "")
        if cItem.get("category") == "ftv_page":
            html = self._html(cItem.get("url", ""))
            m = re.search(r"""<meta[^>]+name=["']description["'][^>]+content=["']([^"']+)""", html)
            text = self.cleanHtmlStr(m.group(1)) if m else text
        else:
            video, meta, _error = self._videoInfo(cItem.get("url", ""))
            title = " - ".join([x for x in (self.cleanHtmlStr(meta.get("title") or ""), self.cleanHtmlStr(meta.get("additional_title") or "")) if x])
            text = self.cleanHtmlStr(meta.get("description") or "") or text
            icon = meta.get("image_url") or icon
            if video.get("is_live"):
                info["status"] = _("On Air")
            try:
                if video.get("duration"):
                    info["duration"] = str(timedelta(seconds=int(video["duration"])))
            except (TypeError, ValueError):
                printExc()
            if meta.get("broadcasted_at"):
                info["broadcast"] = meta["broadcasted_at"][:10]
        if cItem.get("meta_type") and cItem.get("meta_title"):
            try:
                # the site's text and picture first, the service adds what the site does not have
                found = getMeta(cItem["meta_type"], cItem["meta_title"])
                for key, value in (found.get("info") or {}).items():
                    info.setdefault(key, value)
                text = text or found.get("plot", "")
                icon = icon or found.get("poster", "")
            except Exception:
                printExc()
        return [{"title": title or cItem.get("title", ""), "text": text or title or cItem.get("title", ""),
                 "images": [{"title": "", "url": icon}] if icon else [], "other_info": info}]

    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("FranceTV.handleService start")
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if refresh:
            self.pageCache = ("", "")
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", None)
        category = self.currItem.get("category", "")
        printDBG("FranceTV.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "ftv_live":
            self.listLive(self.currItem)
        elif category == "ftv_channels":
            self.listChannels(self.currItem)
        elif category == "ftv_page":
            self.listPage(self.currItem)
        elif category == "ftv_section":
            self.listSection(self.currItem)
        elif category == "ftv_all":
            self.listAllVideos(self.currItem)
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, FranceTV(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("francetv")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("ftv_video", "ftv_page")
