# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# Coding: BY MOHAMED_OS
# 06.10.2026 - ported to the python3 host standard (torrent playback through TorrServer)
#   - arabp2p.net is an xbtit tracker: every list, search and details page needs an account
#     (login / password in the host configuration); without them the lists tell the user so
#   - the session cookie is re-used, a logged-out answer logs in again once
#   - torrents are VIDEO rows keyed on their details page; the magnet link of the details page
#     (plus the YouTube trailer when there is one) goes to urlparser -> TorrServer
#   - paging (First page / Jump / Next page), INFO via moviemeta (IMDb id of the details page
#     when there is one) + the site's poster, watched / downloaded flags, favourites, sidecar,
#     name normalisation ("Title (Year)", "Show - SxxExx", also from Arabic season/episode labels)
import re

from Components.config import ConfigSelection, ConfigText, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.configsecret import ConfigLogin, ConfigSecret
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import GetAlternativeProxyChoices, GetAlternativeProxyUrl, IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta, getMetaByImdbId
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx, parseSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import GetIconDir, printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.arabp2p_proxy = ConfigSelection(default="None", choices=GetAlternativeProxyChoices())
config.plugins.iptvplayer.arabp2p_alt_domain = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.arabp2p_login = ConfigLogin(default="", fixed_size=False)
config.plugins.iptvplayer.arabp2p_password = ConfigSecret(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Username:"), config.plugins.iptvplayer.arabp2p_login))
    optionList.append(getConfigListEntry(_("Password:"), config.plugins.iptvplayer.arabp2p_password))
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.arabp2p_proxy))
    if config.plugins.iptvplayer.arabp2p_proxy.value == "None":
        optionList.append(getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.arabp2p_alt_domain))
    return optionList
###################################################


def gettytul():
    return "https://www.arabp2p.net/"


SITE_HOST_RE = re.compile(r"^https?://(?:www\.)?arabp2p\.net/", re.I)
NOT_ALLOWED = "غير مصرح لك"  # "you are not allowed" (no account / membership level too low)
QUALITY_RE = re.compile(r"(?<![a-z0-9])(2160p|1080p|720p|576p|480p|360p|4K|UHD)(?![a-z0-9])", re.I)
SOURCE_RE = re.compile(r"(?<![a-z0-9])(WEB-?DL|WEB-?Rip|BluRay|Blu-Ray|BDRip|BRRip|HDRip|DVDRip|DVD|HDTV|HDCAM|CAM|x264|x265|H\.?264|H\.?265|HEVC|AVC|10bit|HDR|DV)(?![a-z0-9])", re.I)
YEAR_RE = re.compile(r"(?<![0-9a-z])((?:19|20)\d{2})(?![0-9a-z])", re.I)
SIZE_RE = re.compile(r"(\d{1,9}(?:[.,]\d{1,9})?)\s*([KMGT]i?B)\b", re.I)
# pager links: the tag, then the page number as its text; the href must carry "pages=<n>"
PAGE_LINK_RE = re.compile(r"""<a\b([^>]*)>\s*(\d{1,6})\s*<""")
PAGES_PARAM_RE = re.compile(r"pages=\d")
AR_ORDINALS = (("الأول", 1), ("الاول", 1), ("الثاني", 2), ("الثانى", 2), ("الثالث", 3), ("الرابع", 4), ("الخامس", 5),
               ("السادس", 6), ("السابع", 7), ("الثامن", 8), ("التاسع", 9), ("العاشر", 10))
AR_SEASON_RE = re.compile(r"الموسم\s*(\d+|%s)" % "|".join(o[0] for o in AR_ORDINALS))
AR_EPISODE_RE = re.compile(r"(?:الحلقة|الحلقه)\s*(\d+)")
SXX_RE = re.compile(r"(?<![a-z0-9])S(\d{1,2})(?:\s*E\d{1,3})?(?![a-z0-9])", re.I)
JUNK_RE = re.compile(r"(?:^|\s)(?:فيلم|مسلسل|برنامج|مسرحية|مترجم|مترجمة|مدبلج|مدبلجة|كامل|كاملة|انمي|أنمي)(?=\s|$)")
# the quality label of titles and links: resolution, source, codec (one each, like the other torrent hosts)
LABEL_SOURCE_RE = re.compile(r"(?<![a-z0-9])(Remux|BluRay|Blu-Ray|BDRip|BRRip|WEB-?DL|WEB-?Rip|WEB|HDTV|HDRip|DVDRip|DVD|HDCAM|CAM)(?![a-z0-9])", re.I)
LABEL_CODEC_RE = re.compile(r"(?<![a-z0-9])(x265|x264|HEVC|H\.?265|H\.?264|AVC|AV1|XviD)(?![a-z0-9])", re.I)


def _qualityLabel(title):
    # "1080p WEB-DL x264" from a torrent name
    parts = []
    for regex in (QUALITY_RE, LABEL_SOURCE_RE, LABEL_CODEC_RE):
        match = regex.search(title or "")
        if match:
            parts.append(match.group(1))
    return " ".join(parts)


def _arNum(value):
    return int(value) if value.isdigit() else dict(AR_ORDINALS).get(value, 0)


def parseRelease(title):
    """a torrent name -> {name, year, season, episode, quality, tags}"""
    title = re.sub(r"\s+", " ", title or "").strip()
    season, episode = parseSxxExx(title)
    arSeason = AR_SEASON_RE.search(title)
    arEpisode = AR_EPISODE_RE.search(title)
    if not episode and arEpisode:
        episode = arEpisode.group(1)
        season = str(_arNum(arSeason.group(1))) if arSeason else "1"
    elif not season:
        packSeason = SXX_RE.search(title)
        if packSeason:
            season = packSeason.group(1)
        elif arSeason:
            season = str(_arNum(arSeason.group(1)))
    quality = QUALITY_RE.search(title)
    tags = []
    for tag in ([quality.group(1)] if quality else []) + SOURCE_RE.findall(title):
        if tag.lower() not in [t.lower() for t in tags]:
            tags.append(tag)
    # the name ends where the year / SxxExx / quality / Arabic season or episode label starts
    cut = len(title)
    for match in (quality, SXX_RE.search(title), re.search(r"S\s*\d+\s*E\s*\d+", title, re.I), arSeason, arEpisode, SOURCE_RE.search(title)):
        if match and match.start() > 0:
            cut = min(cut, match.start())
    # fix 091026: not a year at the start ("1917 2019 1080p") and the last one before the tags ("Blade Runner 2049 2017")
    years = [m for m in YEAR_RE.finditer(title) if 0 < m.start() < cut]
    year = years[-1] if years else None
    if year:
        cut = year.start()
    else:
        year = YEAR_RE.search(title, cut)  # "Name 1080p 2023"
    name = re.sub(r"[._]+", " ", title[:cut])
    name = re.sub(r"[\[\](){}]", " ", name)
    name = re.sub(r"\s+", " ", JUNK_RE.sub(" ", name)).strip(" -:|")
    return {"name": name or title, "year": year.group(1) if year else "", "season": season, "episode": episode,
            "quality": quality.group(1) if quality else "", "tags": tags}


class ArabP2P(GenericFolderWatchedScraperMixin, CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "arabp2p", "cookie": "arabp2p.cookie"})
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/arabp2p135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.loggedIn = None
        self.loginFailed = None  # (login, password) that the site refused - not tried again until they change
        self.cacheLinks = {}
        self.watchedHelper = IPTVWatchedHelper("arabp2p")
        self.wfInitFolderCache()
        # fix 091026: here, not in handleService - INFO and watched keys of favourite rows run before any list
        # (login and _canon need the main url)
        self.selectDomain()

    ###################################################
    # helpers
    ###################################################
    def selectDomain(self):
        domain = config.plugins.iptvplayer.arabp2p_alt_domain.value.strip()
        if config.plugins.iptvplayer.arabp2p_proxy.value != "None" or not self.cm.isValidUrl(domain):
            domain = gettytul()
        self.setMainUrl(domain if domain.endswith("/") else domain + "/")

    def getProxy(self):
        return GetAlternativeProxyUrl(config.plugins.iptvplayer.arabp2p_proxy.value) or None

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        proxy = self.getProxy()
        if proxy is not None:
            addParams = dict(addParams, http_proxy=proxy)
        return self.cm.getPage(self._canon(baseUrl), addParams, post_data)

    def _canon(self, url):
        # one host for everything: the session cookie belongs to the domain it was set on
        url = self.getFullUrl((url or "").strip().replace("&amp;", "&").replace(" ", "%20"))
        if self.MAIN_URL and SITE_HOST_RE.match(url):
            url = SITE_HOST_RE.sub(self.MAIN_URL, url)
        return url

    def getFullIconUrl(self, url, currUrl=None):
        url = CBaseHostClass.getFullIconUrl(self, (url or "").strip(), currUrl)
        if not url or url.startswith("file://"):
            return url
        meta = {"Referer": self.getMainUrl(), "User-Agent": self.HEADER.get("User-Agent", "")}
        if SITE_HOST_RE.match(url):
            meta["Cookie"] = self.cm.getCookieHeader(self.COOKIE_FILE)
        proxy = self.getProxy()
        if proxy is not None:
            meta["iptv_http_proxy"] = proxy
        return strwithmeta(url, meta)

    @staticmethod
    def _isLoggedIn(data):
        return "logout.php" in (data or "")

    def _credentials(self):
        return config.plugins.iptvplayer.arabp2p_login.value.strip(), config.plugins.iptvplayer.arabp2p_password.value.strip()

    def tryTologin(self):
        login, password = self._credentials()
        if not login or not password:
            SetIPTVPlayerLastHostError(_("%s needs a free account. Enter login and password in the host configuration.") % "ArabP2P")
            return False
        if self.loginFailed == (login, password):
            SetIPTVPlayerLastHostError(_('Failed to log in user "%s". Please check your login and password.') % login)
            return False
        printDBG("ArabP2P.tryTologin [%s]" % login)
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Referer=self.getMainUrl(), Origin=self.getMainUrl().rstrip("/"))
        params["header"]["Content-Type"] = "application/x-www-form-urlencoded"
        sts, data = self.getPage(self.getFullUrl("/index.php?page=login&returnto=index.php"), params, {"uid": login, "pwd": password})
        self.loggedIn = bool(sts and self._isLoggedIn(data))
        if not self.loggedIn:
            if sts:
                self.loginFailed = (login, password)
            SetIPTVPlayerLastHostError(_('Failed to log in user "%s". Please check your login and password.') % login)
        return self.loggedIn

    def getSitePage(self, url):
        """a page that needs the account: logs in when the session is missing or expired"""
        login, password = self._credentials()
        if not login or not password:
            return self.tryTologin(), ""
        sts, data = self.getPage(url) if self.loggedIn is not False else (False, "")
        if not (sts and self._isLoggedIn(data)):
            if not self.tryTologin():
                return False, ""
            sts, data = self.getPage(url)
            if not sts:
                # fix 091026: logged in, but the page does not load - like the other torrent hosts
                SetIPTVPlayerLastHostError(_("Failed to connect to host."))
                return False, ""
        if NOT_ALLOWED in data and "torrents_list_p" not in data and "magnet:" not in data:
            # the account may not see this page (membership level)
            msg = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, NOT_ALLOWED, "<br", True)[1])
            SetIPTVPlayerLastHostError(msg or _("Login needed"))
            return False, ""
        return sts, data

    def _getWatchedKeyForItem(self, cItem):
        try:
            if isinstance(cItem, dict) and cItem.get("category") == "ap_torrent" and cItem.get("url"):
                # without the domain: the same torrent after a change of the alternative domain
                return "video:" + re.sub(r"^https?://[^/]+", "", self._canon(cItem["url"]))
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def _cat(self, catId):
        return self.getFullUrl("/index.php?page=torrents&category=%d" % catId)

    def listMainMenu(self, cItem):
        menu = [
            {"category": "ap_tab", "title": _("Movies"), "tab": "movies"},
            {"category": "ap_tab", "title": _("Series"), "tab": "series"},
            {"category": "ap_list", "title": _("TV Shows"), "url": self._cat(90), "media": "tv", "good_for_fav": True},
            {"category": "ap_list", "title": _("Plays"), "url": self._cat(52), "media": "movie", "good_for_fav": True},
            {"category": "ap_list", "title": _("Latest"), "url": self.getFullUrl("/index.php?page=torrents"), "good_for_fav": True},
        ]
        self.listsTab(menu + self.searchItems(), cItem)

    def listTab(self, cItem):
        if cItem.get("tab") == "movies":
            media = "movie"
            tab = ((_("Foreign movies"), 42), (_("Arabic Movies"), 41), (_("Asian movies"), 59), (_("Turkish Movies"), 116),
                   (_("Indian Movies"), 86), (_("Latin American movies"), 114), (_("Dubbed anime"), 98), (_("Subbed anime"), 99))
        else:
            media = "tv"
            tab = ((_("Foreign series"), 45), (_("Arabic Series"), 44), (_("Asian TV series"), 57), (_("Turkish Series"), 115),
                   (_("Dubbed series"), 71), (_("Latin American series"), 113), (_("Dubbed anime"), 100), (_("Subbed anime"), 101))
        for title, catId in tab:
            self.addDir({"name": "category", "category": "ap_list", "title": title, "url": self._cat(catId), "media": media, "good_for_fav": True})

    def _pager(self, data, page):
        """(lastPage, page url template with {page} or '', url of the next page or '')"""
        block = self.cm.ph.getDataBeetwenMarkers(data, ("<form", ">", "change_pagepages"), ("</form", ">"), False)[1] or data
        lastPage, tpl, nextUrl = page, "", ""
        for attrs, num in PAGE_LINK_RE.findall(block):
            href = self.cm.ph.getSearchGroups(attrs, r"""\bhref=['"]([^'"]*)['"]""")[0]
            if not PAGES_PARAM_RE.search(href):
                continue
            href, num = self._canon(href), int(num)
            lastPage = max(lastPage, num)
            if num == page + 1:
                nextUrl = href
            param = int(self.cm.ph.getSearchGroups(href, r"[?&]pages=(\d+)")[0] or 0)
            if not tpl and param == num:
                tpl = re.sub(r"([?&]pages=)\d+", r"\g<1>{page}", href)
        for num in re.findall(r"""<option[^>]+value=['"][^'"]*pages=(\d+)""", block):
            lastPage = max(lastPage, int(num))
        return lastPage, tpl, nextUrl

    def listItems(self, cItem):
        page = int(cItem.get("page", 1) or 1)
        baseUrl = cItem.get("base_url") or cItem["url"]
        url = baseUrl if page <= 1 else cItem["url"]
        printDBG("ArabP2P.listItems [%s]" % url)
        sts, data = self.getSitePage(url)
        if not sts:
            return
        table = self.cm.ph.getDataBeetwenMarkers(data, ("<table", ">", "torrents_list_p"), ("</table", ">"), False)[1]
        normalize = IsMediaNamingNormalized()
        seen = set()
        for item in table.split("file-header")[1:]:  # one torrent: file-header (poster, link, name) + file-meta
            href = self.cm.ph.getSearchGroups(item, r"""href=['"]([^'"]*page=torrent-details[^'"]*)['"]""")[0] or self.cm.ph.getSearchGroups(item, r"""<a[^>]+href=['"]([^'"]+)['"]""")[0]
            if not href:
                continue
            url = self._canon(href)
            if url in seen:
                continue
            seen.add(url)
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ("<span", ">"), ("</a", ">"), False)[1])
            if not title:
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r"""(?s)href=['"]%s['"][^>]*>(.*?)</a>""" % re.escape(href))[0])
            if not title:
                continue
            release = parseRelease(title)
            meta = self.cm.ph.getDataBeetwenNodes(item, ("<div", ">", "file-meta"), ("</div", ">"), False)[1]
            size = SIZE_RE.search(self.cleanHtmlStr(meta))
            seeds = self.cm.ph.getSearchGroups(meta, r"""class=['"][^'"]*seed[^'"]*['"][^>]*>(?:\s*<[^>]+>)*\s*(\d+)""")[0]
            peers = self.cm.ph.getSearchGroups(meta, r"""class=['"][^'"]*leech[^'"]*['"][^>]*>(?:\s*<[^>]+>)*\s*(\d+)""")[0]
            isTv = cItem.get("media") == "tv" or bool(release["season"] or release["episode"])
            dispTitle = title
            if normalize:
                if isTv and release["season"]:
                    sxe = formatSxxExx(release["season"], release["episode"] or None)
                    dispTitle = "%s - %s" % (release["name"], sxe)
                elif not isTv:
                    dispTitle = "%s (%s)" % (release["name"], release["year"]) if release["year"] else release["name"]
                # the quality of the release, like the other torrent hosts ("Name (2024) - 1080p WEB-DL x264")
                label = _qualityLabel(title)
                if dispTitle != title and label:
                    dispTitle = "%s - %s" % (dispTitle, label)
            descLines = [title] if dispTitle != title else []
            if release["tags"]:
                descLines.append("%s: %s" % (_("Quality"), " ".join(release["tags"])))
            if size:
                descLines.append("%s %s" % size.groups())
            if seeds or peers:
                descLines.append("S:%s P:%s" % (seeds or "0", peers or "0"))
            icon = self.cm.ph.getSearchGroups(item, r"""rel=['"]([^'"]+\.(?:jpe?g|png|gif|webp)[^'"]*)['"]""", ignoreCase=True)[0]
            self.addVideo({"name": "category", "category": "ap_torrent", "good_for_fav": True, "title": dispTitle, "url": url,
                           "icon": self.getFullIconUrl(icon) if icon else self.DEFAULT_ICON_URL, "desc": "[/br]".join(descLines),
                           "s_release": title, "s_size": "%s %s" % size.groups() if size else "", "s_seeds": seeds, "s_peers": peers,
                           "meta_type": "tv" if isTv else "movie", "meta_title": release["name"], "meta_year": release["year"]})
        lastPage, tpl, nextUrl = self._pager(data, page)
        listItem = dict(cItem, base_url=baseUrl)
        listItem.pop("page", None)
        addPagingItems(self, listItem, page, bool(seen) and bool(nextUrl or lastPage > page), lastPage, tpl,
                       {"url": nextUrl} if nextUrl and not tpl else None)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("ArabP2P.listSearchResult [%s]" % searchPattern)
        url = self.getFullUrl("/index.php?page=torrents&search=%s&category=0&active=0" % urllib_quote(searchPattern.strip(), safe=""))
        self.listItems(dict(cItem, category="ap_list", url=url, base_url=url, page=1))

    ###################################################
    # links
    ###################################################
    def _details(self, data):
        """(magnet, trailer, imdb id, poster, story, size, seeds, peers) of a details page"""
        magnet = self.cm.ph.getSearchGroups(data, r"""href=['"](magnet:\?[^'"]+)['"]""")[0].replace("&amp;", "&")
        trailer = self.cm.ph.getSearchGroups(data, r"""['"](https?://(?:www\.|m\.)?(?:youtube\.com/(?:watch\?v=|embed/)|youtu\.be/)[A-Za-z0-9_-]{11})""")[0]
        imdbId = self.cm.ph.getSearchGroups(data, r"imdb\.com/title/(tt\d+)")[0]
        poster = self.cm.ph.getSearchGroups(data, r"""<img[^>]+class=['"][^'"]*poster[^'"]*['"][^>]+src=['"]([^'"]+)['"]""")[0] or \
            self.cm.ph.getSearchGroups(data, r"""<img[^>]+src=['"]([^'"]+)['"][^>]+class=['"][^'"]*poster""")[0]
        story = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", "tor_desc"), ("</div", ">"), False)[1])
        size = self.cm.ph.getSearchGroups(self.cleanHtmlStr(data), r"الحجم\s*:?\s*(\d+(?:[.,]\d+)?\s*[KMGT]i?B)")[0]
        seeds = self.cm.ph.getSearchGroups(data, r"""class=['"]seeds['"][^>]*>(?:\s*<[^>]+>)*\s*(\d+)""")[0]
        peers = self.cm.ph.getSearchGroups(data, r"""class=['"]leechers['"][^>]*>(?:\s*<[^>]+>)*\s*(\d+)""")[0]
        return magnet, trailer, imdbId, poster, story, size, seeds, peers

    def getLinksForVideo(self, cItem):
        url = cItem.get("url", "")
        printDBG("ArabP2P.getLinksForVideo [%s]" % url)
        # add 091026: like the other torrent hosts - no new login-protected request when the links are opened again
        if self.cacheLinks.get(url):
            return self.cacheLinks[url]
        sts, data = self.getSitePage(url)
        if not sts:
            return []
        magnet, trailer, _imdb, poster, story, size, seeds, peers = self._details(data)
        if not magnet:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        title = cItem.get("title", "")
        release = cItem.get("s_release") or title
        # fix 091026: a local file:// default icon is no cover for TorrServer
        icon = self.getFullIconUrl(poster) if poster else cItem.get("icon", "")
        if not icon.startswith("http"):
            icon = ""
        if "&dn=" not in magnet:
            magnet += "&dn=" + urllib_quote(release, safe="")
        seeds, peers = seeds or cItem.get("s_seeds", ""), peers or cItem.get("s_peers", "")
        parts = [_qualityLabel(release) or "Torrent", size or cItem.get("s_size", "")]
        if seeds or peers:
            parts.append("S:%s P:%s" % (seeds or "0", peers or "0"))
        urltab = [{"name": " - ".join(p for p in parts if p), "url": strwithmeta(magnet, {"title": title, "icon": str(icon)}), "need_resolve": 1}]
        if trailer:
            urltab.append({"name": _("Trailer"), "url": trailer, "need_resolve": 1})
        urltab = applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), story))
        self.cacheLinks[url] = urltab
        return urltab

    def getVideoLinks(self, videoUrl):
        printDBG("ArabP2P.getVideoLinks [%s]" % videoUrl)
        if not (videoUrl.startswith("magnet:?") or self.cm.isValidUrl(videoUrl)):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("ArabP2P.getArticleContent [%s]" % cItem.get("url", ""))
        imdbId, poster, story, info = "", "", "", {}
        sts, data = self.getSitePage(cItem.get("url", ""))
        if sts:
            imdbId, poster, story = self._details(data)[2:5]
        tags = parseRelease(cItem.get("s_release") or cItem.get("title", ""))["tags"]
        if tags:
            info["quality"] = " ".join(tags)
        mediaType = cItem.get("meta_type", "movie")
        meta = {}
        try:
            if imdbId:
                meta = getMetaByImdbId(mediaType, imdbId)
            if not meta and cItem.get("meta_title"):
                meta = getMeta(mediaType, cItem["meta_title"], cItem.get("meta_year", ""))
        except Exception:
            printExc()
        if cItem.get("meta_year"):
            info.setdefault("year", cItem["meta_year"])
        info.update(meta.get("info", {}))
        plot = meta.get("plot", "")
        text = plot or story or cItem.get("desc", "")
        if plot and story and story != plot:
            text = "%s[/br][/br]%s" % (plot, story)
        icon = meta.get("poster") or (self.getFullIconUrl(poster) if poster else cItem.get("icon", ""))
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
        printDBG("ArabP2P.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "ap_tab":
            self.listTab(self.currItem)
        elif category == "ap_list":
            self.listItems(self.currItem)
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
        CHostBase.__init__(self, ArabP2P(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("arabp2p")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") == "ap_torrent"
