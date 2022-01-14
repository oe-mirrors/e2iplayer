# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib
try:
    import json
except Exception:
    import simplejson as json
###################################################


def gettytul():
    return 'http://seriale.co/'


class SerialeCO(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'seriale.co', 'cookie': 'seriale.co.cookie'})
        self.DEFAULT_ICON_URL = 'https://www.alekinoplus.pl/images/2015/sierpien/kino-mowi/km-seriale-logo.png'
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.MAIN_URL = 'http://seriale.co/'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate', 'Referer': self.getMainUrl(), 'Origin': self.getMainUrl()}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding': 'gzip, deflate', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json, text/javascript, */*; q=0.01'})

        self.defaultParams = {'header': self.HTTP_HEADER, 'with_metadata': True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.MAIN_CAT_TAB = [{'category': 'list_items', 'title': 'START', 'url': self.getMainUrl()},
                             {'category': 'list_series', 'title': 'SPIS ALFABETYCZNY', 'url': self.getMainUrl()},

                             {'category': 'search', 'title': _('Search'), 'search_item': True},
                             {'category': 'search_history', 'title': _('Search history')},
                            ]
        self.playerData = {}
        self.cacheLinks = {}

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        origBaseUrl = baseUrl
        baseUrl = self.cm.iriToUri(baseUrl)
        addParams['cloudflare_params'] = {'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def listMainMenu(self, cItem):
        printDBG("SerialeCO.listMainMenu")
        self.listsTab(self.MAIN_CAT_TAB, cItem)

    def listSeries(self, cItem, nextCategory):
        printDBG("SerialeCO.listSeries [%s]" % cItem)

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'flexible-posts'), ('</ul', '>'))[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url})
            self.addDir(params)

    def listItems(self, cItem, nextCategory):
        printDBG("SerialeCO.listItems [%s]" % cItem)
        page = cItem.get('page', 1)
        marker = cItem.get('f_marker', 'block-span')

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'page-nav'), ('</div', '>'))[1]
        nextPage = self.getFullUrl(self.cm.ph.getSearchGroups(nextPage, '''href=['"]([^'^"]+?/page/%s/[^'^"]*?)['"]''' % (page + 1))[0])

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', marker), ('<div', '>', 'main-sidebar'))[1]
        data = re.compile('''<div[^>]*?%s[^>]*?>''' % re.escape(marker)).split(data)
        if len(data):
            del data[0]
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''[\s\-]src=['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h3', '</h3>')[1])
            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'excerpt'), ('</div', '>'))[1])

            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'icon': icon, 'desc': desc})
            self.addDir(params)

        if self.cm.isValidUrl(nextPage):
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _("Next page"), 'url': nextPage, 'page': cItem.get('page', 1) + 1})
            self.addDir(params)

    def listSeasons(self, cItem, nextCategory):
        printDBG("SerialeCO.listSeasons [%s]" % cItem)

        self.playerData = {}

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        cUrl = data.meta['url']

        data = self.cm.ph.getDataBeetwenNodes(data, ('<script', '>', 'player.js'), ('<header', '>'))[1]
        playerUrl = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''src=['"]([^'^"]+?)['"]''')[0])

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<input', '>')
        self.playerData = {}
        for item in data:
            id = self.cm.ph.getSearchGroups(item, '''id=['"]([^'^"]+?)['"]''')[0]
            val = self.cm.ph.getSearchGroups(item, '''value=['"]([^'^"]+?)['"]''')[0]
            self.playerData[id] = val

        sts, data = self.getPage(playerUrl)
        if not sts:
            return

        # function pobierz_info_o_odcinkach
        ajaxInfoData = self.cm.ph.getDataBeetwenMarkers(data, 'function pobierz_info_o_odcinkach', '});')[1]
        ajaxInfoVarName = self.cm.ph.getSearchGroups(ajaxInfoData, '''var\s+?([A-Za-z0-9]+?)\s*?=''')[0]
        ajaxInfoData = self.cm.ph.getDataBeetwenMarkers(ajaxInfoData, '$.ajax(', ').', False)[1]
        printDBG('ajaxInfoData: [%s]' % ajaxInfoData)
        printDBG('ajaxInfoVarName: [%s]' % ajaxInfoVarName)

        playerUrl = self.cm.ph.getDataBeetwenMarkers(data, 'function seriale_search', 'function')[1]
        playerUrl = self.cm.ph.getSearchGroups(playerUrl, '''['"]?url['"]?\s*:\s*['"](http[^'^"]+?)['"]''')[0]
        if not self.cm.isValidUrl(playerUrl):
            printDBG("No valid playerUrl")
            return

        self.playerData['player_url'] = playerUrl

        seasonUrl = self.cm.ph.getDataBeetwenMarkers(data, 'function pokaz_odcinki', 'function')[1]
        seasonUrl = self.cm.ph.getSearchGroups(seasonUrl, '''['"]?url['"]?\s*:\s*['"](http[^'^"]+?)['"]''')[0]
        if not self.cm.isValidUrl(seasonUrl):
            printDBG("No valid playerUrl")
            return

        httpParams = dict(self.defaultParams)
        httpParams['header'] = dict(httpParams['header'])
        httpParams['header']['Referer'] = cItem['url']
        httpParams['header']['Origin'] = self.getMainUrl()[:-1]

        sts, seasons = self.getPage(seasonUrl, httpParams, {'nazwa': self.playerData.get('fid', '')})
        if sts:
            printDBG(">>>>>>>\n%s\n>>>>>>>" % seasons)
            self.playerData['odc'] = seasons

        seasons = self.playerData.get('odc', '').split(',')
        for idx in range(len(seasons)):
            if seasons[idx] == '':
                continue
            sNum = str(idx + 1)
            params = dict(cItem)
            params.update({'good_for_fav': False, 'category': nextCategory, 'title': _('Season %s') % sNum.zfill(2), 's_title': cItem['title'], 's_num': sNum, 'e_count': seasons[idx]})
            self.addDir(params)

        if 0 == len(self.currList) and ajaxInfoVarName != '' and ajaxInfoData != '':
            ret = js_execute('{0}="{1}";\n'.format(ajaxInfoVarName, self.playerData.get(ajaxInfoVarName, '')) + 'print(JSON.stringify({0}));\n'.format(ajaxInfoData))
            if ret['sts'] and 0 == ret['code']:
                data = ret['data'].strip()
                printDBG('DECODED DATA -> \n[%s]\n' % data)
                try:
                    data = byteify(json.loads(data))
                    searchUrl = self.getFullUrl(data['url'], cUrl)
                    post_data = data['data']

                    sts, data = self.getPage(searchUrl, httpParams, post_data)
                    if not sts:
                        return

                    printDBG('DATA -> \n[%s]\n' % data)

                    data = byteify(json.loads(data))
                    for sKey in data:
                        sNum = sKey.strip()
                        eItems = []
                        for eKey in data[sKey]:
                            eNum = eKey.strip()
                            title = _('%s s%se%s') % (cItem['title'], sNum.zfill(2), eNum.zfill(2))
                            if data[sKey][eKey].get('title', '') != '':
                                title += ' ' + data[sKey][eKey]['title']
                            desc = data[sKey][eKey].get('data', '')
                            params = {'good_for_fav': False, 'title': title, 'desc': desc, 's_num': sNum, 'e_num': eNum}
                            eItems.append(params)
                        if len(eItems):
                            params = dict(cItem)
                            params.update({'good_for_fav': False, 'category': nextCategory, 'title': _('Season %s') % sNum.zfill(2), 's_title': cItem['title'], 's_num': sNum, 'e_items': eItems})
                            self.addDir(params)
                except Exception:
                    printExc()

        if len(self.currList) == 1:
            cItem = self.currList[0]
            self.currList = []
            self.listEpisodes(cItem)

    def listEpisodes(self, cItem):
        printDBG("SerialeCO.listEpisodes [%s]" % cItem)
        self.cacheLinks = {}

        if 'e_items' in cItem:
            for item in cItem['e_items']:
                params = dict(cItem)
                params.update(item)
                self.addVideo(params)
        else:
            sNum = cItem.get('s_num', '')
            try:
                eCount = int(cItem.get('e_count', '0'))
            except Exception:
                eCount = 0
            for idx in range(eCount):
                eNum = str(idx + 1)
                params = dict(cItem)
                params.update({'good_for_fav': False, 'title': _('%s s%se%s') % (cItem['s_title'], sNum.zfill(2), eNum.zfill(2)), 's_num': sNum, 'e_num': eNum})
                self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("SerialeCO.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('?s=') + urllib.quote_plus(searchPattern)
        cItem['category'] = 'list_items'
        cItem['f_marker'] = 'td_module_'

        self.listItems(cItem, 'list_seasons')

    def getLinksForVideo(self, cItem):
        printDBG("SerialeCO.getLinksForVideo [%s]" % cItem)

        playerUrl = self.playerData['player_url']
        fid = self.playerData.get('fid', '')
        sNum = cItem['s_num']
        eNum = cItem['e_num']

        cacheKey = '%s_%s_%s' % (fid, sNum, eNum)
        urlTab = self.cacheLinks.get(cacheKey, [])
        if len(urlTab):
            return urlTab

        httpParams = dict(self.defaultParams)
        httpParams['header'] = dict(httpParams['header'])
        httpParams['header']['Referer'] = cItem['url']
        httpParams['header']['Origin'] = self.getMainUrl()[:-1]

        sts, data = self.getPage(playerUrl, httpParams, {'fid_name': fid, 'sezon': sNum, 'odcinek': eNum, 'title': fid, 'blocked': ''})
        if not sts:
            return []

        printDBG(data)
        verMap = {'1': 'ENG', '2': 'NAPISY', '3': 'PL'}
        urlTab = []
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'host'), ('</div', '>'))
        for item in data:
            url = self.cm.ph.getSearchGroups(item, '''url=['"]([^'^"]+?)['"]''')[0]
            if not self.cm.isValidUrl(url) and '?' not in url:
                url = '/frame.php?src=' + url
            name = self.cm.ph.getSearchGroups(item, '''host=['"]([^'^"]+?)['"]''')[0]
            ver = self.cm.ph.getSearchGroups(item, '''wersja=['"]([^'^"]+?)['"]''')[0]
            name = '[%s] %s' % (verMap.get(ver, ver), name)
            urlTab.append({'name': name, 'url': strwithmeta(self.getFullUrl(url), {'Referer': cItem['url']}), 'need_resolve': 1})

        if len(urlTab):
            self.cacheLinks[cacheKey] = urlTab
        return urlTab

    def getVideoLinks(self, baseUrl):
        printDBG("SerialeCO.getVideoLinks [%s]" % baseUrl)

        key = strwithmeta(baseUrl).meta.get('cache_key', '')
        for key in self.cacheLinks:
            for idx in range(len(self.cacheLinks[key])):
                if baseUrl in self.cacheLinks[key][idx]['url']:
                    if not self.cacheLinks[key][idx]['name'].startswith('*'):
                        self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name']
                    break

        if 1 != self.up.checkHostSupport(baseUrl):
            referer = strwithmeta(baseUrl).meta.get('Referer', '')
            httpParams = dict(self.defaultParams)
            httpParams['header'] = dict(httpParams['header'])
            httpParams['header']['Referer'] = referer
            httpParams['header']['Origin'] = self.getMainUrl()[:-1]
            sts, data = self.getPage(baseUrl, httpParams)
            if not sts:
                return []
            baseUrl = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0])

        return self.up.getVideoLinkExt(self.getFullUrl(baseUrl))

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG(">> handleService: name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listMainMenu({'name': 'category'})
        elif category == 'list_series':
            self.listSeries(self.currItem, 'list_seasons')
        elif category == 'list_items':
            self.listItems(self.currItem, 'list_seasons')
        elif category == 'list_seasons':
            self.listSeasons(self.currItem, 'list_episodes')
        elif category == 'list_episodes':
            self.listEpisodes(self.currItem)
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
        CHostBase.__init__(self, SerialeCO(), True, [])
