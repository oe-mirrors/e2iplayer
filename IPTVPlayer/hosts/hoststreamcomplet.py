# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib
import base64
try:
    import json
except Exception:
    import simplejson as json
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import unpackJSPlayerParams, VIDEOMEGA_decryptPlayerParams, SAWLIVETV_decryptPlayerParams
###################################################


def gettytul():
    return 'https://streamcomplet.me/'


class StreamComplet(CBaseHostClass):
    MAIN_URL = 'https://www.streamcomplet.me/'
    SRCH_URL = MAIN_URL + '?s='
    DEFAULT_ICON_URL = 'https://streamcomplet.me/wp-content/themes/streaming/logo/logo.png'

    MAIN_CAT_TAB = [{'category': 'categories', 'title': _('Categories'), 'icon': DEFAULT_ICON_URL, 'filters': {}},
                    {'category': 'search', 'title': _('Search'), 'icon': DEFAULT_ICON_URL, 'search_item': True},
                    {'category': 'search_history', 'title': _('Search history'), 'icon': DEFAULT_ICON_URL}
                   ]

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'StreamComplet', 'cookie': 'StreamComplet.cookie'})
        self.cacheFilters = {}
        self.USER_AGENT = "Mozilla/5.0 (Windows NT 6.1; WOW64; Trident/7.0; rv:11.0) like Gecko"
        self.USER_AGENT2 = "Mozilla/5.0 (X11; Linux x86_64; rv:10.0) Gecko/20150101 Firefox/44.0 (Chrome)"
        self.HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'text/html'}
        self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

    def listCategories(self, cItem, category):
        printDBG("StreamComplet.listCategories")
        sts, data = self.cm.getPage(self.MAIN_URL)
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenMarkers(data, '<ul id="menu-menu" class="menu">', '</ul>', False)[1]

        data = re.compile('<a href="([^"]+?)"[^>]*?>([^<]+?)<').findall(data)
        for item in data:
            params = dict(cItem)
            params.update({'category': category, 'title': item[1].strip(), 'url': self.getFullUrl(item[0])})
            self.addDir(params)

    def listItems(self, cItem):
        printDBG("StreamComplet.listItems")

        tmp = cItem['url'].split('?')
        url = tmp[0]
        if len(tmp) > 1:
            arg = tmp[1]
        else:
            arg = ''

        page = cItem.get('page', 1)
        if page > 1:
            url += 'page/%s/' % page
        if '' != arg:
            url += '?' + arg

        sts, data = self.cm.getPage(url)
        if not sts:
            return

        nextPage = False
        if ('/page/%s/' % (page + 1)) in data:
            nextPage = True
        m1 = '<div class="moviefilm">'
        data = self.cm.ph.getDataBeetwenMarkers(data, m1, '<div class="filmborder">', False)[1]
        data = data.split(m1)
        for item in data:
            params = dict(cItem)
            params = dict(cItem)
            url = self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0]
            title = self.cm.ph.getSearchGroups(item, 'alt="([^"]+?)"')[0]
            title = self.cleanHtmlStr(title)
            if title == '':
                continue
            icon = self.cm.ph.getSearchGroups(item, 'src="([^"]+?)"')[0]
            desc = self.cleanHtmlStr(item)
            params.update({'title': title, 'icon': self.getFullUrl(icon), 'desc': desc, 'url': self.getFullUrl(url)})
            self.addVideo(params)

        if nextPage:
            params = dict(cItem)
            params.update({'title': _('Next page'), 'page': cItem.get('page', 1) + 1})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        searchPattern = urllib.quote_plus(searchPattern)
        cItem = dict(cItem)
        cItem['url'] = self.SRCH_URL + searchPattern
        self.listItems(cItem)

    def _unpackJS(self, data, name):
        try:
            vGlobals = {"__builtins__": None, 'str': str, 'chr': chr, 'list': list}
            vLocals = {name: None}
            exec(data, vGlobals, vLocals)
        except Exception:
            printExc('_unpackJS exec code EXCEPTION')
            return ''
        try:
            return vLocals[name]
        except Exception:
            printExc('_unpackJS EXCEPTION')
        return ''

    def _decodeData(self, baseData):
        data = baseData
        fullDecData = ''
        decData = ''
        for idx in range(3):
            if 'eval(' not in data:
                break
            tmpTab = self.cm.ph.getAllItemsBeetwenMarkers(data, "eval(", '</script>')
            for tmpData in tmpTab:
                tmp = tmpData.split('eval(')
                if len(tmp):
                    del tmp[0]
                for tmpItem in tmp:
                    tmpDec = ''
                    for decFun in [VIDEOMEGA_decryptPlayerParams, SAWLIVETV_decryptPlayerParams]:
                        tmpDec = unpackJSPlayerParams('eval(' + tmpItem, decFun, 0)
                        if '' != tmpDec:
                            break
                    decData += tmpDec
            fullDecData += decData
            data = decData

        # ++++++++++++++++++++
        codeData = 'def go123():\n'
        tmp = self.cm.ph.getSearchGroups(baseData, '''document\[([^\]]+?)\[[0-9]\]\]\(([^)]+?)\)''', 2)
        mainVar = tmp[0]
        mainVal = self.cm.ph.getSearchGroups(baseData, '''var\s+?%s\s*=\s*(\[[^\]]+?\])''' % mainVar)[0]
        mainVal = mainVal.replace('"', '\\"').replace('[\\', '[').replace('\\"]', '"]').replace(',\\"', ',"').replace('\\",', '",')

        subTab = re.compile('''\+([^\+]+?)\+''').findall(tmp[1])
        for item in subTab:
            var = item.strip()
            val = self.cm.ph.getSearchGroups(fullDecData, '''var\s*%s\s*=\s*(['"][^'^"]+?['"])''' % var)[0]
            codeData += '\t%s = %s\n' % (var, val)
        codeData += '\t%s = %s\n' % (mainVar, mainVal)
        codeData += '\treturn ' + tmp[1]
        codeData += '\nkoteczek = go123()'
        codeData = self._unpackJS(codeData, 'koteczek')
        # ++++++++++++++++++++

        if codeData != '':
            return codeData

        subTab = re.compile('''(['"]\s*\+[^\+]+?\+\s*['"])''').findall(fullDecData)
        for item in subTab:
            var = self.cm.ph.getSearchGroups(item, '''\+([^\+]+?)\+''')[0].strip()
            val = self.cm.ph.getSearchGroups(fullDecData, '''var\s*%s\s*=\s*['"]([^'^"]+?)['"]''' % var)[0]
            fullDecData = fullDecData.replace(item, val)
        fullData = baseData + fullDecData
        fullData = fullData.replace('\\"', '"').replace('\\/', '/')
        return fullData

    def getLinksForVideo(self, cItem):
        printDBG("StreamComplet.getLinksForVideo [%s]" % cItem)
        urlTab = []

        rm(self.COOKIE_FILE)

        params = dict(self.defaultParams)
        header = dict(self.HEADER)
        header['Referer'] = cItem['url']
        params['header'] = header

        frameUrlsTab = [cItem['url']]

        for idx in range(3):
            newFrameUrlsTab = []
            for frameUrl in frameUrlsTab:
                sts, data = self.cm.getPage(frameUrl, params)
                printDBG("============================ start ============================")
                printDBG(data)
                printDBG("============================ end ============================")
                if not sts:
                    continue
                enc1 = self.cm.ph.getDataBeetwenMarkers(data, 'enc1|', '|', False)[1].strip()
                data = self._decodeData(data)
                printDBG("============================ start ============================")
                printDBG(data)
                printDBG("============================ end ============================")
                tryLinksTab = re.compile('<iframe[^>]+?src="([^"]+?)"').findall(data)
                tryLinksTab.extend(re.compile('\s(https?:[^\s]+?)\s').findall(data))
                try:
                    if enc1 != '':
                        tryLinksTab.append('http://hqq.tv/player/embed_player.php?vid=' + base64.b64decode(enc1))
                except Exception:
                    printExc()

                for item in tryLinksTab:
                    item = item.replace('\\/', '/')
                    if '' == item.strip():
                        continue
                    if 'facebook' in item:
                        continue
                    if 'wp-content' in item:
                        continue
                    if not self.cm.isValidUrl(item):
                        if item.startswith('../'):
                            item = self.up.getDomain(frameUrl, False) + item.replace('../', '')
                        elif item.startswith('//'):
                            item = 'http://' + item
                        elif item.startswith('/'):
                            item = self.up.getDomain(frameUrl, False) + item[1:]
                        else:
                            item = self.up.getDomain(frameUrl, False) + item[1:]
                    if 1 == self.up.checkHostSupport(item):
                        urlTab.append({'name': self.up.getHostName(item), 'url': item, 'need_resolve': 1})
                    else:
                        newFrameUrlsTab.append(item)
            frameUrlsTab = newFrameUrlsTab

        return urlTab

    def getVideoLinks(self, videoUrl):
        printDBG("StreamComplet.getVideoLinks [%s]" % videoUrl)
        return self.up.getVideoLinkExt(videoUrl)

    def getFavouriteData(self, cItem):
        return cItem['url']

    def getLinksForFavourite(self, fav_data):
        return self.getLinksForVideo({'url': fav_data})

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})
        elif category == 'categories':
            self.listCategories(self.currItem, 'items')
    #ITEMS
        elif category == 'items':
            self.listItems(self.currItem)
    #SEARCH
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
        CHostBase.__init__(self, StreamComplet(), True, [CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO])
