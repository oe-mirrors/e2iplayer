# -*- coding: utf-8 -*-
# Last Modified: 10.10.2026
###################################################
# 2026-08-28 - add automatic videa-quality - by Blindspot
# 2026-09-05 - add VideaKid + VideaTon - by Blindspot
# 10.10.2026 - host standard: no requests to figyelmeztetes.hu any more (usage counter with the box's
#   /etc/issue id, remote uploader filter list) and the "id:" option that drove them; py2 runs again (no
#   urllib.parse), plain requests instead of the Cloudflare path (the site has none), links are the
#   videa player url of the video id (no page request; resolved by urlparser parserVIDEA, also for Videa
#   Kid and the Videaton audio), covers from the list's background image, First/Jump/Next paging for
#   categories, "Next page" with First page for channels and search (lazy lists), Videaton (one page with
#   ~1000 entries) paged locally, watched flag (channel -> video), favourites, sidecar, INFO from the
#   video page (description, length, upload date, views, uploader), English menu texts
# 10.10.2026 - review: favourites of the old version (any row could be saved then) reopen - channels and their
#   sort tabs / lazy "Next page" rows as the channel, search rows as the search
###################################################
HOST_VERSION = "1.9"
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
###################################################
# FOREIGN import
###################################################
from Components.config import config, ConfigYesNo, getConfigListEntry
import re
###################################################

###################################################
# Config options for HOST
###################################################
# also read by urlparser.parserVIDEA (only the best quality as link)
config.plugins.iptvplayer.videa_quality = ConfigYesNo(default=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Select best available quality"), config.plugins.iptvplayer.videa_quality))
    return optionList


###################################################


def gettytul():
    return "Videa"


LAZY_PER_PAGE = 36  # a channel page / one lazy request answers 36 videos
LOCAL_PER_PAGE = 100  # Videaton: the whole catalogue (~1000 entries) on one page


class videa(GenericFolderWatchedScraperMixin, CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "videa", "cookie": "videa.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.DEFAULT_ICON_URL = "https://videa.hu/static/uis/redesign/images/product-logos/videa-logo-footer.png"
        self.MAIN_URL = "https://videa.hu"
        self.defaultParams = {"header": self.HEADER, "use_cookie": False, "load_cookie": False, "save_cookie": False}
        self.watchedHelper = IPTVWatchedHelper("videa")
        self.wfInitFolderCache()
        self.localCache = ("", [])  # (url, item blocks) of the last Videaton page

    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    def getFullIconUrl(self, url, currUrl=None):
        return CBaseHostClass.getFullIconUrl(self, url.replace("&amp;", "&"), currUrl)

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict) or cItem.get("search_item"):
                return ""
            if cItem.get("type") in ("video", "audio"):
                vid = cItem.get("vid", "") or self._videoId(cItem.get("url", ""))
                return "video:%s" % vid if vid else ""
            if cItem.get("category") == "list_items" and cItem.get("channel_mode") and cItem.get("ch_url"):
                return "folder:channel:%s" % cItem["ch_url"]
        except Exception:
            printExc()
        return ""

    @staticmethod
    def _videoId(url):
        # https://videa.hu/videok/<cat>/<slug>-<16 char id> | .../player?v=<id>
        m = re.search(r"(?:[-/]|v=)([A-Za-z0-9]{16})(?:[?#&]|$)", url or "")
        return m.group(1) if m else ""

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self, cItem):
        MAIN_CAT_TAB = [
            {"category": "list_main", "title": _("Categories"), "tab_id": "videa_kategoriak"},
            {"category": "list_main", "title": _("Channels"), "tab_id": "videa_csatornak"},
            {"category": "list_items", "title": "Videa Kid", "url": "https://videakid.hu/", "icon": "https://videakid.hu/static/uis/redesign/images/product-logos/videakid-logo.png", "single_page": True, "good_for_fav": True},
            {"category": "list_items", "title": "Videaton", "url": self.MAIN_URL + "/videaton", "icon": "https://videa.hu/static/uis/redesign/images/product-logos/videaton-logo.png", "videaton_mode": True, "good_for_fav": True},
        ] + self.searchItems()
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listMainItems(self, cItem):
        sts, data = self.getPage(self.MAIN_URL)
        if not sts:
            return
        if cItem.get("tab_id") == "videa_kategoriak":
            blocks = data.split('class="category-item">')[1:]
            nextCategory = "list_second"
        else:
            data = self.cm.ph.getDataBeetwenMarkers(data, 'list-opener">Channels', "</ul>", False)[1] or self.cm.ph.getDataBeetwenMarkers(data, 'title list-opener">', "</ul>")[1]
            blocks = data.split("<li>")[1:]
            nextCategory = "list_items"
        for item in blocks:
            url = self.cm.ph.getSearchGroups(item, r"href=['\"]([^\"']+?)['\"]")[0]
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'class="menu-text">([^<]+)<')[0])
            if not url or not title:
                continue
            url = self.getFullUrl(url)
            icon = self.cm.ph.getSearchGroups(item, r"background-image:url\('([^']+)'\)")[0]
            params = {"name": "category", "good_for_fav": True, "category": nextCategory, "title": title[:1].upper() + title[1:], "url": url, "icon": self.getFullIconUrl(icon.replace("http://", "https://")) if icon else ""}
            if nextCategory == "list_items":
                params.update({"channel_mode": True, "ch_url": url})
            self.addDir(params)

    def listSecondItems(self, cItem):
        url = cItem["url"].split("?")[0]
        sortTab = [{"title": _("Most recent"), "page_tpl": url + "?page={page}"},
                   {"title": _("Most viewed"), "page_tpl": url + "?popular&page={page}"},
                   {"title": "Oldest first", "page_tpl": url + "?oldest&page={page}"}]
        for item in sortTab:
            params = dict(cItem)
            params.update({"category": "list_items", "good_for_fav": True, "page": 1, "url": item["page_tpl"].format(page=1)})
            params.update(item)
            self.addDir(params)

    def _addItem(self, cItem, item):
        url = self.cm.ph.getSearchGroups(item, r'<h2 class="title"><a href="([^"]+)"')[0] or self.cm.ph.getSearchGroups(item, r"<a\shref=['\"]([^\"']+?)['\"]\saria-label")[0]
        if not self.cm.isValidUrl(url):
            return
        title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<h2 class="title"><a [^>]*title="([^"]*)"')[0] or self.cm.ph.getSearchGroups(item, r'aria-label="([^"]+)"')[0])
        title = title.replace("<unknown> - ", "")
        if not title:
            return
        icon = self.cm.ph.getSearchGroups(item, r'data-image="([^"]+)"')[0] or self.cm.ph.getSearchGroups(item, r"background-image:url\('([^']+)'\)")[0]
        length = self.cm.ph.getSearchGroups(item, r'class="length">([0-9:]+)<')[0]
        hd = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<div class="hd">', "</div>", False)[1])
        uploader = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<a href="/tagok/[^"]+"\s*>([^<]+)</a>')[0])
        views = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'class="view-count">([^<]+)<')[0])
        uploaded = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'class="uploaded-at">([^<]+)<')[0])
        desc = " | ".join(x for x in (length, hd.upper(), views, uploaded) if x)
        if uploader:
            desc += "[/br]" + _("Channel: %s") % uploader
        params = stripPagerKeys(dict(cItem), ("page_tpl", "lazy_url", "search_pattern", "ch_url", "channel_mode", "search_mode", "videaton_mode", "single_page", "tab_id"))
        params.update({"good_for_fav": True, "title": title, "url": url, "vid": self._videoId(url), "icon": self.getFullIconUrl(icon) if icon else self.DEFAULT_ICON_URL,
                       "desc": desc, "uploader": uploader, "category": "video"})
        if 'videa-list-item podcast"' in item:
            self.addAudio(params)
        else:
            self.addVideo(params)

    def _itemBlocks(self, data):
        blocks = []
        for block in data.split('class="col video-item">')[1:]:
            itemId = self.cm.ph.getSearchGroups(block, r'data-item-id="([^"]+)"')[0]
            blocks.append((itemId, block))
        return blocks

    def listItems(self, cItem):
        if not cItem.get("search_mode") and not cItem.get("ch_url") and "/csatornak/" in cItem.get("url", ""):
            # channel rows saved by the old version: ".../csatornak/<name>?page=1" or its lazy "Next page" url
            chUrl = cItem["url"].split("?")[0].replace("/lazy/", "/")
            cItem = dict(cItem, category="list_items", channel_mode=True, ch_url=chUrl, url=chUrl, page=1)
        page = max(1, int(cItem.get("page", 1) or 1))
        if cItem.get("videaton_mode"):
            self._listLocal(cItem, page)
            return
        lazy = cItem.get("lazy_url", "") if page > 1 else ""
        if lazy:
            url = lazy
        elif cItem.get("page_tpl"):
            url = cItem["page_tpl"].format(page=page)
        elif not cItem.get("search_mode") and not cItem.get("channel_mode") and re.search(r"[?&]page=\d+", cItem.get("url", "")):
            # favourites of the old version (any row could be saved then): "<category>?popular&page=1"
            cItem = dict(cItem, page_tpl=re.sub(r"([?&]page=)\d+", r"\g<1>{page}", cItem["url"].replace("{", "{{").replace("}", "}}")))
            url = cItem["page_tpl"].format(page=page)
        elif cItem.get("search_mode"):
            url = "%s/kereses/%s" % (self.MAIN_URL, urllib_quote_plus(cItem.get("search_pattern", "")))
        else:
            url = cItem.get("ch_url") or cItem["url"]
        sts, data = self.getPage(url)
        if not sts:
            return
        blocks = self._itemBlocks(data)
        if cItem.get("channel_mode") and not lazy:
            blocks = blocks[:LAZY_PER_PAGE]  # the channel page also lists shorts and podcasts after the videos
        for _itemId, block in blocks:
            self._addItem(cItem, block)
        if cItem.get("single_page") or "videakid.hu" in url or not blocks:
            return
        lastId = blocks[-1][0]
        if cItem.get("page_tpl"):
            hasNext = bool(re.search(r'rel="next"', data))
            addPagingItems(self, cItem, page, hasNext, 0, cItem["page_tpl"])
        elif lastId and len(blocks) >= LAZY_PER_PAGE:
            if cItem.get("search_mode"):
                pattern = urllib_quote_plus(cItem.get("search_pattern", ""))
                lazyUrl = "%s/lazy/kereses/%s?cacheId=%s&lastItemId=%s&itemCount=432&sort=0" % (self.MAIN_URL, pattern, pattern, urllib_quote_plus(lastId))
            else:
                chUrl = (cItem.get("ch_url") or cItem["url"]).split("?")[0].replace("/csatornak/", "/lazy/csatornak/")
                lazyUrl = "%s?cacheId=&lastItemId=%s&itemCount=%d&sort=0" % (chUrl, urllib_quote_plus(lastId), page * LAZY_PER_PAGE)
            addPagingItems(self, cItem, page, True, 0, "", {"lazy_url": lazyUrl})

    def _listLocal(self, cItem, page):
        url = cItem["url"]
        if self.localCache[0] != url or not self.localCache[1]:
            sts, data = self.getPage(url)
            if not sts:
                return
            self.localCache = (url, self._itemBlocks(data))
        blocks = self.localCache[1]
        lastPage = (len(blocks) + LOCAL_PER_PAGE - 1) // LOCAL_PER_PAGE
        for _itemId, block in blocks[(page - 1) * LOCAL_PER_PAGE:page * LOCAL_PER_PAGE]:
            self._addItem(cItem, block)
        if lastPage > 1:
            addPagingItems(self, cItem, page, page < lastPage, lastPage, url.replace("{", "{{").replace("}", "}}"))

    def listSearchResult(self, cItem, searchPattern, searchType):
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "url": "%s/kereses/%s" % (self.MAIN_URL, urllib_quote_plus(searchPattern)), "search_pattern": searchPattern, "search_mode": True})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("Videa.getLinksForVideo [%s]" % cItem)
        vid = cItem.get("vid", "") or self._videoId(cItem.get("url", ""))
        if not vid:
            # a video url without the id in it: the page names its player
            sts, data = self.getPage(cItem.get("url", ""))
            vid = self._videoId(self.cm.ph.getSearchGroups(data, r'"embedURL":\s*"([^"]+)"')[0].split("?")[0]) if sts else ""
        if not vid:
            SetIPTVPlayerLastHostError(_("Content not available"))
            return []
        urlTab = [{"name": "Videa", "url": "%s/player?v=%s" % (self.MAIN_URL, vid), "need_resolve": 1}]
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def getVideoLinks(self, videoUrl):
        printDBG("Videa.getVideoLinks [%s]" % videoUrl)
        urlTab = self.up.getVideoLinkExt(videoUrl) if self.cm.isValidUrl(videoUrl) else []
        if not urlTab:
            SetIPTVPlayerLastHostError(_("Content not available"))
        return decorateResolvedLinkItems(urlTab, sidecarFromUrlMeta(videoUrl, IsSidecarEnabled()))

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("Videa.getArticleContent [%s]" % cItem)
        title = cItem.get("title", "")
        text = cItem.get("desc", "")
        icon = cItem.get("icon", "")
        other = {}
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta property="og:title" content="([^"]*)"')[0]) or title
            desc = self.cm.ph.getSearchGroups(data, r'<meta property="og:description" content="([^"]*)"')[0]
            if desc:
                text = self.cleanHtmlStr(desc.replace("\n", "[/br]")) or text
            icon = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0] or icon
            m = re.search(r'"duration":\s*"PT(\d+)H(\d+)M(\d+)S"', data)
            if m:
                hours, minutes, seconds = int(m.group(1)), int(m.group(2)), int(m.group(3))
                other["duration"] = "%d:%02d:%02d" % (hours, minutes, seconds) if hours else "%d:%02d" % (minutes, seconds)
            date = self.cm.ph.getSearchGroups(data, r'"uploadDate":\s*"([^"]+)"')[0]
            if date:
                other["released"] = date
            views = self.cm.ph.getSearchGroups(data, r'<meta name="description" content="[^"]*?(\d+) alkalommal')[0]
            if views:
                other["views"] = views
        if cItem.get("uploader"):
            other["station"] = cItem["uploader"]
        return [{"title": title, "text": text, "images": [{"title": "", "url": self.getFullIconUrl(icon)}] if icon else [], "other_info": other}]

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("Videa.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "list_main":
            self.listMainItems(self.currItem)
        elif category == "list_second" and "/csatornak/" in self.currItem.get("url", ""):
            self.listItems(self.currItem)  # a channel saved by the old version (it had sort tabs too)
        elif category == "list_second":
            self.listSecondItems(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category in ("search", "search_next_page"):
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category"})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search", "tab_id": ""}, "desc", _("Type:") + " ")
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, videa(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("videa")

    def withArticleContent(self, cItem):
        return cItem.get("type") in ("video", "audio") and self.host.cm.isValidUrl(cItem.get("url", ""))
