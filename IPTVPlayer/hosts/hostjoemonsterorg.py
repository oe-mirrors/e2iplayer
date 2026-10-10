# -*- coding: utf-8 -*-
# Last Modified: 10.10.2026
# 10.10.2026 - host standard: the site sits behind a Cloudflare check - pages via getPageCFProtection (MyE2i),
#   covers / logo on joemonster.org with its cookie + the UA that passed it (img.joemonster.org is free),
#   main menu icon from the plugin; lists and player for the current markup (entity-encoded links, YouTube
#   link / <video> / iframe players, "Dłuższy materiał" YouTube link as a second link), First / Jump / Next
#   page with the last page of the pager, watched flag, downloaded marker on the clip url, favourites,
#   sidecar, INFO with the site's data (description, date, length, views), "Title (YYYY-MM-DD)" names;
#   login only with the user's own account (both fields set) and again after a change, default user agent
import os
import re

from Components.config import config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.configsecret import ConfigLogin, ConfigSecret
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.botprotection import remembered_user_agent
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import normalizeMediathekTitle
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import GetIconDir, printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper

config.plugins.iptvplayer.joemonsterorg_login = ConfigLogin(default="", fixed_size=False)
config.plugins.iptvplayer.joemonsterorg_password = ConfigSecret(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("login") + ":", config.plugins.iptvplayer.joemonsterorg_login))
    optionList.append(getConfigListEntry(_("password") + ":", config.plugins.iptvplayer.joemonsterorg_password))
    return optionList


def gettytul():
    return "https://joemonster.org/"


class JoeMonster(GenericFolderWatchedScraperMixin, CBaseHostClass):
    FAV_FIELDS = ("name", "category", "type", "url", "title", "raw_title", "icon", "desc", "date")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "joemonster.org", "cookie": "joemonster.cookie"})
        self.MAIN_URL = gettytul()
        # the site logo sits behind Cloudflare and is asked for before the check is solved: the plugin's tile
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/joemonsterorg135.png")
        self.HEADER = self.cm.getDefaultHeader()
        self.USER_AGENT = self.HEADER.get("User-Agent", "")
        self.HEADER["Referer"] = self.MAIN_URL
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MENU = [{"category": "list_items", "title": "Monster TV - Najnowsze filmy", "url": self.getFullUrl("/filmy"), "good_for_fav": True},
                     {"category": "list_items", "title": "Monster TV - Najlepsze filmy", "url": self.getFullUrl("/filmy/ulubione"), "good_for_fav": True},
                     {"category": "list_items", "title": "Monster TV - Poczekalnia", "url": self.getFullUrl("/filmy/poczekalnia"), "good_for_fav": True},
                     {"category": "list_items", "title": "Monster TV - Kolejka", "url": self.getFullUrl("/filmy/kolejka"), "good_for_fav": True}]
        self.loggedIn = None
        self.login = ""
        self.password = ""
        self.watchedHelper = IPTVWatchedHelper("joemonsterorg")
        self.wfInitFolderCache()

    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPageCFProtection(url, addParams, post_data)

    def _cfMeta(self, referer):
        # joemonster.org and its file hosts (vader.joemonster.org mp4s, older thumbnails) sit behind the same
        # Cloudflare check as the pages: cf_clearance + the UA that passed it (403 without both)
        meta = {"Referer": referer, "User-Agent": self.USER_AGENT}
        try:
            # getCookieHeader logs tracebacks for a cookie file that does not exist yet
            cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE, ["cf_clearance"]).rstrip("; ") if os.path.isfile(self.COOKIE_FILE) else ""
            if cookieHeader:
                meta.update({"User-Agent": remembered_user_agent(self.COOKIE_FILE) or self.USER_AGENT, "Cookie": cookieHeader})
        except Exception:
            printExc()
        return meta

    @staticmethod
    def _behindCF(url):
        # img.joemonster.org needs nothing, every other joemonster.org host the clearance
        host = re.sub(r"^https?://([^/:?#]+).*$", r"\1", url).lower()
        return (host == "joemonster.org" or host.endswith(".joemonster.org")) and host != "img.joemonster.org"

    def getFullIconUrl(self, url, currUrl=None):
        url = CBaseHostClass.getFullIconUrl(self, url, currUrl)
        if not url.startswith("http") or not self._behindCF(url):
            return url
        return strwithmeta(url, self._cfMeta(self.MAIN_URL))

    ###################################################
    # watched flag / favourites
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if isinstance(cItem, dict) and cItem.get("type") == "video":
                url = str(cItem.get("url", "") or "").strip()
                return "video:%s" % url if url else ""
        except Exception:
            printExc()
        return ""

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("type") == "video":
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # lists
    ###################################################
    def _clipUrl(self, url):
        # "/filmy/138480/Amerykansko_iranski_koncert" - the id is the clip, the name part may change
        url = self.getFullUrl(self.cleanHtmlStr(url))
        return url.split("?", 1)[0]

    def _pager(self, data, page):
        # <div id="pagerNav"> ... <a href="/filmy/najnowsze/2" title="Strona 2">2</a> ... title="last page">[4344]</a>
        pager = self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", "pagerNav"), ("</div", ">"), False)[1]
        tpl = ""
        for href in re.findall(r'href="([^"]+?/\d+)"', pager):
            href = self.getFullUrl(self.cleanHtmlStr(href))
            tpl = re.sub(r"/\d+$", "/{page}", href.replace("{", "{{").replace("}", "}}"))
            break
        lastPage = int(self.cm.ph.getSearchGroups(pager, r'title="last page">\s*\[(\d+)\]')[0] or 0)
        numbers = [int(n) for n in re.findall(r'href="[^"]+?/(\d+)"', pager)]
        if not lastPage and numbers:
            lastPage = max(numbers + [page])
        hasNext = "Następna strona" in pager or bool(numbers and max(numbers) > page)
        return hasNext, lastPage, tpl

    def listItems(self, cItem):
        printDBG("JoeMonster.listItems [%s]" % cItem)
        try:
            page = max(1, int(cItem.get("page", 1) or 1))
        except (TypeError, ValueError):
            page = 1
        base = cItem.get("base_url") or cItem["url"]
        tpl = cItem.get("jm_tpl", "")
        url = tpl.format(page=page) if (page > 1 and tpl) else base
        sts, data = self.getPage(url)
        if not sts:
            return
        hasNext, lastPage, pagerTpl = self._pager(data, page)
        tpl = pagerTpl or tpl
        seen = set()
        # Najnowsze / Najlepsze: <div id="mtv138480" class="mtv-row">; Poczekalnia / Kolejka: class="mtvPoczekalniaFilm"
        for block in re.split(r'<div[^>]+class="(?:mtv-row|mtvPoczekalniaFilm[^"]*)"', data)[1:]:
            block = block.split("<!-- .mtvPoczekalniaFilm -->", 1)[0]
            href = self.cm.ph.getSearchGroups(block, r'href="([^"]*?filmy[^"]*?\d+[^"]*)"')[0]
            if not href:
                continue
            clipUrl = self._clipUrl(href)
            if clipUrl in seen:
                continue
            seen.add(clipUrl)
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)class="(?:title|movie-title-link)"[^>]*>(.*?)</a>')[0]) or \
                self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r"(?s)<h2[^>]*>(.*?)</h2>")[0])
            if not title:
                continue
            icon = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'<img[^>]+src="([^"]+)"')[0])
            length = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)<time[^>]*video-time[^>]*>(.*?)</time>')[0])
            date = self.cm.ph.getSearchGroups(block, r'<span title="(\d{4}-\d{2}-\d{2})[ \d:]*">')[0]
            text = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)class="mtv-desc-text">(.*?)</div>')[0])
            views = self.cm.ph.getSearchGroups(block, r"([\d ]+)x\s*(?:&middot;|<|\*|$)")[0].strip()
            descTab = [x for x in (date, length, _("%s views") % views if views else "") if x]
            params = stripPagerKeys(dict(cItem), ("base_url", "jm_tpl"))
            params.update({"good_for_fav": True, "category": "video", "title": normalizeMediathekTitle(title, date=date), "raw_title": title,
                           "url": clipUrl, "icon": self.getFullIconUrl(icon) if icon else self.DEFAULT_ICON_URL, "date": date,
                           "desc": " | ".join(descTab) + ("[/br]" + text if text else "")})
            self.addVideo(params)
        params = dict(cItem, base_url=base, jm_tpl=tpl)
        addPagingItems(self, params, page, bool(seen) and hasNext, lastPage, tpl)

    ###################################################
    # links
    ###################################################
    def _parseClipPage(self, data):
        info = {"links": [], "extra": [], "title": "", "text": "", "icon": ""}
        player = self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", "mtv-player-wrapper"), ("<div", ">", "mtvRightColumn"), False)[1]
        sub = ""
        if "playerSubDescription" in player:
            player, sub = player.split("playerSubDescription", 1)
        for src in re.findall(r'<source[^>]+src="([^"]+)"', player):
            info["links"].append(("MP4", self.getFullUrl(self.cleanHtmlStr(src)), 0))
        for src in re.findall(r'<iframe[^>]+src="([^"]+)"', player):
            src = self.cleanHtmlStr(src)
            if "embed.html" in src:
                # the site's own wrapper: embed.html?v=<hoster url>
                src = urllib_unquote(self.cm.ph.getSearchGroups(src + "&", r"[?&]v=([^&]+?)&")[0]) or src
            info["links"].append(("", self.getFullUrl(src), 1))
        for src in re.findall(r'href="([^"]+)"', player):
            # <a href="https&#x3A;&#x2F;&#x2F;www.youtube.com&#x2F;watch&#x3F;v&#x3D;...">link yt</a>
            src = self.cleanHtmlStr(src)
            if re.search(r"youtube\.com/watch|youtu\.be/", src):
                info["links"].append(("YouTube", src, 1))
        for src in re.findall(r'"file"\s*:\s*"(https?:[^"]+?\.(?:mp4|m3u8)[^"]*)"', player):
            info["links"].append(("MP4" if ".mp4" in src else "HLS", src.replace("\\/", "/"), 0))
        # "Dłuższy materiał": the full video the clip comes from
        for src in re.findall(r'href="(https?://(?:www\.)?(?:youtube\.com/watch|youtu\.be/)[^"]+)"', sub):
            info["extra"].append(("YouTube", self.cleanHtmlStr(src), 1))
        info["title"] = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<h1[^>]*playerTitle[^>]*>(.*?)</h1>')[0]) or \
            self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta property="og:title" content="([^"]*)"')[0])
        info["text"] = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<div id="mtvDescription"[^>]*>(.*?)</div>')[0].replace("<br>", "[/br]")) or \
            self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta property="og:description" content="([^"]*)"')[0])
        info["icon"] = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0])
        return info

    def getLinksForVideo(self, cItem):
        printDBG("JoeMonster.getLinksForVideo [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem.get("url", ""))
        if not sts:
            return []
        info = self._parseClipPage(data)
        urltab, seen = [], set()
        for name, url, needResolve in info["links"] + info["extra"]:
            if not self.cm.isValidUrl(url) or url in seen:
                continue
            seen.add(url)
            if (name, url, needResolve) in info["extra"]:
                name = "%s (full video)" % name
            if needResolve:
                urltab.append({"name": name or self.up.getHostName(url).capitalize(), "url": strwithmeta(url, {"Referer": cItem["url"]}), "need_resolve": 1})
            else:
                meta = self._cfMeta(cItem["url"]) if self._behindCF(url) else {"Referer": cItem["url"], "User-Agent": self.USER_AGENT}
                urltab.append({"name": name, "url": strwithmeta(url, meta), "need_resolve": 0})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), info["text"] or cItem.get("desc", "")))

    def getVideoLinks(self, videoUrl):
        printDBG("JoeMonster.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("JoeMonster.getArticleContent [%s]" % cItem.get("url", ""))
        title = cItem.get("raw_title", "") or cItem.get("title", "")
        text, icon, otherInfo = cItem.get("desc", ""), cItem.get("icon", ""), {}
        if cItem.get("date"):
            otherInfo["released"] = cItem["date"]
        length = self.cm.ph.getSearchGroups(cItem.get("desc", ""), r"\|\s*(\d+:\d\d(?::\d\d)?)\b")[0]
        if length:
            otherInfo["duration"] = length
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            info = self._parseClipPage(data)
            title = info["title"] or title
            text = info["text"] or text
            if info["icon"]:
                icon = self.getFullIconUrl(info["icon"])
        return [{"title": title, "text": text, "images": [{"title": "", "url": icon or self.DEFAULT_ICON_URL}], "other_info": otherInfo}]

    ###################################################
    # login (own account only)
    ###################################################
    def tryTologin(self):
        login = config.plugins.iptvplayer.joemonsterorg_login.value.strip()
        password = config.plugins.iptvplayer.joemonsterorg_password.value.strip()
        if not login or not password:
            self.loggedIn = None
            return
        if self.loggedIn is not None and login == self.login and password == self.password:
            return
        self.login, self.password = login, password
        printDBG("JoeMonster.tryTologin")
        sts, data = self.getPage(self.getFullUrl("/user.php"))
        if sts:
            sts, data = self.getPage(self.getFullUrl("/login_check"), None, {"_username": login, "_password": password, "op": "login"})
        self.loggedIn = bool(sts and "logout" in data)
        if not self.loggedIn:
            SetIPTVPlayerLastHostError(_("Login failed!"))

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("JoeMonster.handleService name[%s], category[%s]" % (name, category))
        self.currList = []
        self.tryTologin()
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category in ("list_items", "list_poczekalnia"):
            # list_poczekalnia: favourites of the old version
            self.listItems(self.currItem)
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):
    def __init__(self):
        CHostBase.__init__(self, JoeMonster(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("joemonsterorg")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video"
