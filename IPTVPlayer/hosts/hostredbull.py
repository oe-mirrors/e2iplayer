# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Components.config import config, ConfigSelection, ConfigYesNo, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts, rm, formatBytes, CSelOneLink
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.libs import ph
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
###################################################
# FOREIGN import
###################################################
import re
import time
from datetime import timedelta
###################################################
###################################################
# Config options for HOST
###################################################


def GetConfigList():
    optionList = []
    return optionList
###################################################


def gettytul():
    return 'http://redbull.tv/'


class Redbull(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'redbull.tv', 'cookie': 'redbull.tv.cookie'})

        self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.defaultParams = {'header': self.HTTP_HEADER}
        self.REDBULL_API = "https://appletv.redbull.tv/"
        self.MAIN_URL = 'http://redbull.tv/'
        self.DEFAULT_ICON_URL = 'https://www.redbull.com/v3/resources/images/appicon/android-chrome-192.png'

    def listMain(self, cItem, nextCategory):
        printDBG("Redbull.listMain")

        MAIN_CAT_TAB = [{'category': 'explore_item', 'title': _('Discover'), 'url': self.REDBULL_API + "products/discover"},
                         {'category': 'explore_item', 'title': _('TV'), 'url': self.REDBULL_API + "products/tv"},
                         {'category': 'explore_item', 'title': _('Channels'), 'url': self.REDBULL_API + "products/channels"},
                         {'category': 'explore_item', 'title': _('Calendar'), 'url': self.REDBULL_API + "products/calendar"},
                         {'category': 'search', 'title': _('Search'), 'search_item': True, },
                         {'category': 'search_history', 'title': _('Search history'), }
                        ]

        self.listsTab(MAIN_CAT_TAB, cItem)

    def handleSection(self, cItem, nextCategory, section):
        printDBG("Redbull.handleSection")
        section = ph.STRIP_HTML_COMMENT_RE.sub("", section)

        tmp = section.split('</table>', 1)
        sTitle = self.cleanHtmlStr(tmp[0])
        if sTitle.lower() in ('linki',): #'kategorie'
            return
        sIcon = self.getFullUrl(ph.search(section, ph.IMAGE_SRC_URI_RE)[1])

        subItems = []
        uniques = set()
        iframes = ph.findall(section, '<center>', '</iframe>')
        if iframes:
            for iframe in iframes:
                title = self.cleanHtmlStr(iframe).split('Video Platform', 1)[0].strip()
                iframe = ph.search(iframe, ph.IFRAME_SRC_URI_RE)[1]
                if iframe in uniques:
                    continue
                uniques.add(iframe)
                if not title:
                    title = sTitle
                subItems.append(MergeDicts(cItem, {'category': nextCategory, 'title': title, 'url': iframe}))

        iframes = ph.IFRAME_SRC_URI_RE.findall(section)
        if iframes:
            for iframe in iframes:
                iframe = iframe[1]
                if iframe in uniques:
                    continue
                uniques.add(iframe)
                subItems.append(MergeDicts(cItem, {'category': nextCategory, 'title': sTitle, 'url': iframe}))
        section = ph.findall(section, ('<a', '>', ph.check(ph.any, ('articles.php', 'readarticle.php'))), '</a>')
        for item in section:
            url = self.getFullUrl(ph.search(item, ph.A_HREF_URI_RE)[1])
            icon = self.getFullUrl(ph.search(item, self.reImgObj)[1])
            title = self.cleanHtmlStr(item)
            if not title:
                title = icon.rsplit('/', 1)[-1].rsplit('.', 1)[0]
                #title = self.titlesMap.get(title, title.upper())
            subItems.append(MergeDicts(cItem, {'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'icon': icon}))

        if len(subItems) > 1:
            self.addDir(MergeDicts(cItem, {'category': 'sub_items', 'title': sTitle, 'icon': sIcon, 'sub_items': subItems}))
        elif len(subItems) == 1:
            params = subItems[0]
            params.update({'title': sTitle})
            self.addDir(params)

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def getFullUrl(self, url, currUrl=None):
        return CBaseHostClass.getFullUrl(self, url.replace('&amp;', '&'), currUrl)

    def listSubItems(self, cItem):
        printDBG("Redbull.listSubItems")
        self.currList = cItem['sub_items']

    def exploreItem(self, cItem):
        printDBG("Redbull.exploreItem")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return []
        printDBG("hostredbull.exploreItem.data2 |%s|" % data)

        if '<mediaURL>' in data:
            icon = self.getFullIconUrl(ph.search(data, '''src720=['"]([^'^"]+?)['"]''')[0])
            url = self.getFullUrl(ph.search(data, '''onPlay="loadPage\(['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(ph.search(data, '''<label2>([^>]+?)</label2>''')[0])
            if not title:
                title = self.cleanHtmlStr(ph.search(data, '''<title>([^>]+?)</title>''')[0])
            params = {'title': title, 'icon': icon, 'desc': '', 'url': cItem['url']}
            self.addVideo(params)

        data2 = ph.findall(data, '<sixteenByNinePoster', '</sixteenByNinePoster>')
        for item in data2:
            icon = self.getFullIconUrl(ph.search(item, '''src720=['"]([^'^"]+?)['"]''')[0])
            url = self.getFullUrl(ph.search(item, '''onPlay="loadPage\(['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(ph.search(item, '''<label2>([^>]+?)</label2>''')[0])
            if not title:
                title = self.cleanHtmlStr(ph.search(item, '''<title>([^>]+?)</title>''')[0])
            if not title:
                title = self.cleanHtmlStr(ph.search(item, '''accessibilityLabel=['"]([^'^"]+?)['"]''')[0])
            time = self.cleanHtmlStr(ph.search(item, '''Duration: ([^'^"]+?)<''')[0])
            if 'page_stream' in url:
                params = {'title': title, 'icon': icon, 'desc': '', 'url': url}
                self.addVideo(params)
            else:
                params = dict(cItem)
                params.update({'good_for_fav': True, 'category': 'explore_item', 'title': title, 'url': url, 'desc': url, 'icon': icon})
                self.addDir(params)

        data2 = ph.findall(data, '<showcasePoster', '</showcasePoster>')
        for item in data2:
            icon = self.getFullIconUrl(ph.search(item, '''src720=['"]([^'^"]+?)['"]''')[0])
            url = self.getFullUrl(ph.search(item, '''onPlay="loadPage\(['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(ph.search(item, '''Label=['"]([^'^"]+?)['"]''')[0])
            params = {'title': title, 'icon': icon, 'desc': '', 'url': url}
            self.addVideo(params)

        data2 = ph.findall(data, '<twoLine', '</twoLine')
        for item in data2:
            icon = self.getFullIconUrl(ph.search(item, '''src720=['"]([^'^"]+?)['"]''')[0])
            url = self.getFullUrl(ph.search(item, '''onPlay="loadPage\(['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(ph.search(item, '''<label2>([^>]+?)</label2>''')[0])
            if not title:
                title = self.cleanHtmlStr(ph.search(item, '''<title>([^>]+?)</title>''')[0])
            time = self.cleanHtmlStr(ph.search(item, '''Duration: ([^'^"]+?)<''')[0])
            params = {'title': title, 'icon': icon, 'desc': '[' + time + ']', 'url': url}
            self.addVideo(params)

        data2 = ph.findall(data, '<moviePoster', '</moviePoster>')
        for item in data2:
            icon = self.getFullIconUrl(ph.search(item, '''src720=['"]([^'^"]+?)['"]''')[0])
            url = self.getFullUrl(ph.search(item, '''onPlay="loadPage\(['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(ph.search(item, '''<label2>([^>]+?)</label2>''')[0])
            if not title:
                title = self.cleanHtmlStr(ph.search(item, '''<title>([^>]+?)</title>''')[0])
            time = self.cleanHtmlStr(ph.search(item, '''Duration: ([^'^"]+?)<''')[0])
            params = {'title': title, 'icon': icon, 'desc': '[' + time + ']', 'url': url}
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):

        url = self.REDBULL_API + "search?q=%s" % urllib_quote_plus(searchPattern)
        cItem = MergeDicts(cItem, {'category': 'list_search', 'url': url})
        self.listSearchItems(cItem)

    def listSearchItems(self, cItem):
        printDBG("Redbull.listSearchItems")
        page = cItem.get('page', 1)

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])
        printDBG("hostredbull.listSearchItems |%s|" % data)

        data2 = ph.findall(data, '<twoLine', '</twoLine')
        for item in data2:
            icon = self.getFullIconUrl(ph.search(item, '''src720=['"]([^'^"]+?)['"]''')[0])
            url = self.getFullUrl(ph.search(item, '''onPlay="loadPage\(['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(ph.search(item, '''<label2>([^>]+?)</label2>''')[0])
            if not title:
                title = self.cleanHtmlStr(ph.search(item, '''<title>([^>]+?)</title>''')[0])
            if not title:
                title = self.cleanHtmlStr(ph.search(item, '''<label>([^>]+?)</label>''')[0])
            if not title:
                title = self.cleanHtmlStr(ph.search(item, '''Label=['"]([^'^"]+?)['"]''')[0])
            time = self.cleanHtmlStr(ph.search(item, '''Duration: ([^'^"]+?)<''')[0])
            params = {'title': title, 'icon': icon, 'desc': '[' + time + ']', 'url': url}
            self.addVideo(params)

    def getLinksForVideo(self, cItem):
        urlsTab = []

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return []
        printDBG("hostredbull.getLinksForVideo.data |%s|" % data)
        videoUrl = ph.search(data, '''<mediaURL>([^"]+?)<''')[0]
        if videoUrl:
            tmp = getDirectM3U8Playlist(videoUrl, checkExt=True, checkContent=True)
            for item in tmp:
                name = '%sx%s  , bitrate: %s' % (item['width'], item['height'], item['bitrate'])
                urlsTab.append({'name': name, 'url': item['url'], 'need_resolve': 0, 'bitrate': item['bitrate'], 'original': ''})
            urlsTab.sort(key=lambda x: x['bitrate'], reverse=True)
            return urlsTab
        else:
            url = self.getFullUrl(ph.search(data, '''onPlay="loadPage\(['"]([^'^"]+?)['"]''')[0])
            sts, data = self.getPage(url)
            if not sts:
                return []
            printDBG("hostredbull.getLinksForVideo.data |%s|" % data)
            videoUrl = ph.search(data, '''<mediaURL>([^"]+?)<''')[0]
            tmp = getDirectM3U8Playlist(videoUrl, checkExt=True, checkContent=True)
            for item in tmp:
                name = '%sx%s  , bitrate: %s' % (item['width'], item['height'], item['bitrate'])
                urlsTab.append({'name': name, 'url': item['url'], 'need_resolve': 0, 'bitrate': item['bitrate'], 'original': ''})
            urlsTab.sort(key=lambda x: x['bitrate'], reverse=True)
            return urlsTab

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("handleService: ||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listMain({'name': 'category', 'type': 'category'}, 'explore_item')

        elif category == 'explore_item':
            self.exploreItem(self.currItem)

        elif category == 'sub_items':
            self.listSubItems(self.currItem)

    #SEARCH
        elif category == 'list_search':
            self.listSearchItems(self.currItem)
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category'})
            self.listSearchResult(cItem, searchPattern, searchType)
    #HISTORIA SEARCH
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Redbull(), True, [])
