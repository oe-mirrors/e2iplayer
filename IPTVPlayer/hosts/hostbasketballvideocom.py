# -*- coding: utf-8 -*-
# Last Modified: 04.01.2026 - Panda555
import re
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta


def GetConfigList():
    return []


def gettytul():
    return 'https://basketball-video.com/'


class BasketballVideo(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'basketball-video.com', 'cookie': 'basketball-video.cookie'})
        self.DEFAULT_ICON_URL = gettytul() + '_pu/75/37346371.png'
        self.MAIN_URL = 'https://basketball-video.com/'
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {'with_metadata': True, "header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MENU = [
            {'category': 'sub_menu', 'title': 'Basketball-Video', 'url': 'https://basketball-video.com/', 'desc': 'https://basketball-video.com/'},
            {'category': 'sub_menu', 'title': 'MLBLive', 'url': 'https://mlblive.net/', 'desc': 'https://mlblive.net/'},
            {'category': 'sub_menu', 'title': 'NFL-Video', 'url': 'https://nfl-video.com/', 'desc': 'https://nfl-video.com/'},
            {'category': 'sub_menu', 'title': 'FullRaces', 'url': 'https://fullraces.com/', 'desc': 'https://fullraces.com/'}]

    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    def listSubMenu(self, cItem):
        printDBG("BasketballVideo.listSubMenu [%s]" % cItem)
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return []
        cUrl = data.meta['url']
        self.setMainUrl(cUrl)
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<nav', '</nav')[0]
        data = re.compile(r'a href="([^"]+)"\s*?>([^<]+)', re.DOTALL).findall(data)
        for url, title in data:
            params = dict(cItem)
            params.update({'category': 'list_items', 'title': title, 'url': url})
            self.addDir(params)

    def listItems(self, cItem):
        printDBG("BasketballVideo.listItems")
        url = cItem['url']
        sts, data = self.getPage(url)
        if not sts:
            return []
        nextPage = self.cm.ph.getSearchGroups(data, 'swchItem" href="([^"]+)')[0]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="poster">', 'block_elem"')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, r'href="([^"]+)')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<h3', '>'), ('</h3', '>'), False)[1])
            icon = self.getFullUrl(self.cm.ph.getSearchGroups(item, r'img src="([^"]+)')[0])
            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'short_descr'), ('</div', '>'), False)[1]).replace('&nbsp;', ' ')
            params = dict(cItem)
            params = {'good_for_fav': True, 'title': title, 'url': url, 'icon': icon, 'desc': desc}
            self.addVideo(params)
        if nextPage:
            params = dict(cItem)
            params.update({'title': _("Next page"), 'url': self.MAIN_URL[:-1] + nextPage})
            self.addDir(params)

    def getLinksForVideo(self, cItem):
        printDBG("BasketballVideo.getLinksForVideo [%s]" % cItem)
        urltab = []
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return []
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="fullstory block_elem"', 'class="full_info block_elem"')[0]
        data = re.compile(r'''(?:src|href)=['"]([^'^"]+?)['"]\s(?:width|rel)''', re.DOTALL).findall(data)
        for url in data:
            url = 'https:' + url if url.startswith('//') else url
            if any(d in url for d in ("gamesontvtoday.com", "nfl-video.com", "guidedesgemmes.com")):
                sts, d = self.getPage(url)
                if not sts:
                    continue
                url = self.cm.ph.getSearchGroups(d, 'src="([^"]+)" w')[0]
                url = "https:" + url if url.startswith("//") else url
            urltab.append({"name": self.up.getHostName(url).capitalize(), "url": strwithmeta(url, {"Referer": cItem['url']}), "need_resolve": 1})
        return urltab

    def getVideoLinks(self, url):
        printDBG("BasketballVideo.getVideoLinks [%s]" % url)
        if self.cm.isValidUrl(url):
            return self.up.getVideoLinkExt(url)
        return []

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("handleService start\nhandleService: name[%s], category[%s] " % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == 'sub_menu':
            self.listSubMenu(self.currItem)
        elif category == 'list_items':
            self.listItems(self.currItem)
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, BasketballVideo(), True, [])
