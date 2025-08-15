# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify
from Plugins.Extensions.IPTVPlayer.libs.unshortenit import unshorten
###################################################

###################################################
# FOREIGN import
###################################################
import urllib
try:
    import json
except Exception:
    import simplejson as json
###################################################


def gettytul():
    return 'http://iitvx.pl/'


class IITVPL(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'IITVPL.tv', 'cookie': 'iitvpl.cookie'})
        self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.HEADER = {'User-Agent': 'Mozilla/5.0', 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})

        self.MAIN_URL = 'http://iitvx.pl/'
        self.DEFAULT_ICON_URL = self.MAIN_URL + 'assets/img/logo-iitvx.png'

        self.MAIN_CAT_TAB = [{'category': 'list_abc', 'title': 'Lista ABC', 'url': self.MAIN_URL, 'icon': self.DEFAULT_ICON_URL},
                             {'category': 'list_series2', 'title': 'Popularne seriale', 'url': self.MAIN_URL, 'icon': self.DEFAULT_ICON_URL},
                             {'category': 'list_series1', 'title': 'Wszystkie seriale', 'url': self.MAIN_URL, 'icon': self.DEFAULT_ICON_URL},

                             #{'category':'search',            'title': _('Search'), 'search_item':True,         'icon':self.DEFAULT_ICON_URL},
                             #{'category':'search_history',    'title': _('Search history'),                     'icon':self.DEFAULT_ICON_URL}
                            ]

        self.cacheLinks = {}
        self.cacheSeries = {}

    def getSeriesInfo(self, data):
        printDBG("IITVPL.getSeriesInfo")
        info = {}
        data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="group series-info"', '</div>')[1]
        info['title'] = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<h1', '</h1>')[1])
        info['icon'] = self.getFullUrl(self.cm.ph.getSearchGroups(data, 'src="([^"]+?)"')[0])
        info['desc'] = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<p class="description"', '</p>')[1].split('</strong>')[-1])
        info['full_desc'] = self.cleanHtmlStr(data.split('</h1>')[-1])
        keysMap = {'Gatunek:': 'genre', 'Stacja:': 'station'}
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<strong>', '</strong>'), ('<', '>', '/'), withNodes=True)
        for item in data:
            tmp = item.split('</strong>', 1)
            key = self.cleanHtmlStr(tmp[0])
            value = self.cleanHtmlStr(tmp[-1])
            if key in keysMap:
                info[keysMap[key]] = value
        return info

    def listABC(self, cItem, nextCategory):
        printDBG("IITVPL.listABC")
        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenMarkers(data, '<ul id="list">', '</ul>')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>', withMarkers=True)
        for item in data:
            title = self.cleanHtmlStr(item)
            url = self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0]

            if url.startswith('http://') or url.startswith('https://'):
                letter = title.decode('utf-8')[0].encode('utf-8').upper()
                if letter.isdigit():
                    letter = '0-9'
                if letter not in self.cacheSeries:
                    self.cacheSeries[letter] = []
                self.cacheSeries[letter].append({'title': title, 'url': url})

        letterTab = ["0-9", "a", "A", "ą", "Ą", "b", "B", "c", "C", "ć", "Ć", "d", "D", "e", "E", "ę", "Ę", "f", "F", "g", "G", "h", "H", "i", "I", "j", "J", "k", "K", "l", "L", "ł", "Ł", "m", "M", "n", "N", "ń", "Ń", "o", "O", "ó", "Ó", "p", "P", "q", "Q", "r", "R", "s", "S", "ś", "Ś", "t", "T", "u", "U", "v", "V", "w", "W", "x", "X", "y", "Y", "z", "Z", "ź", "Ź", "ż", "Ż"]
        for letter in letterTab:
            if 0 == len(self.cacheSeries.get(letter, [])):
                continue
            params = dict(cItem)
            params.update({'category': nextCategory, 'title': letter, 'letter': letter})
            self.addDir(params)
        for letter in self.cacheSeries:
            if letter in letterTab:
                continue
            params = dict(cItem)
            params.update({'category': nextCategory, 'title': letter, 'letter': letter})
            self.addDir(params)

    def listSeriesByLetter(self, cItem, nextCategory):
        printDBG("IITVPL.listSeriesByLetter")
        tab = self.cacheSeries.get(cItem.get('letter'), [])
        params = dict(cItem)
        params.update({'category': nextCategory, 'good_for_fav': True})
        self.listsTab(tab, params)

    def listSeries(self, cItem, nextCategory, m1):
        printDBG("IITVPL.listSeries")
        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenMarkers(data, m1, '</ul>')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>', withMarkers=True)
        for item in data:
            title = self.cleanHtmlStr(item)
            url = self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0]
            if url.startswith('http://') or url.startswith('https://'):
                params = dict(cItem)
                params.update({'category': nextCategory, 'good_for_fav': True, 'title': title, 'url': url})
                self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("IITVPL.listEpisodes")

        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return

        info = self.getSeriesInfo(data)

        data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="episodes-list">', '<footer>')[1]
        data = data.split('</ul>')
        if len(data):
            del data[-1]

        for sItem in data:
            season = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(sItem, '<h2', '</h2>')[1])
            eDataTab = self.cm.ph.getAllItemsBeetwenMarkers(sItem, '<li', '</li>', withMarkers=True)
            for item in eDataTab:
                title = info['title'] + ': ' + self.cleanHtmlStr(item)
                url = self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0]
                if url.startswith('http://') or url.startswith('https://'):
                    params = dict(cItem)
                    params.update({'good_for_fav': True, 'title': title, 'url': url, 'desc': info['full_desc'], 'icon': info['icon']})
                    self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("IITVPL.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.SEARCH_URL + '/' + urllib.quote_plus(searchPattern)
        self.listItems(cItem, 'list_episodes')

    def getLinksForVideo(self, cItem):
        printDBG("IITVPL.getLinksForVideo [%s]" % cItem)

        urlTab = self.cacheLinks.get(cItem['url'], [])
        if len(urlTab):
            return urlTab
        self.cacheLinks = {}

        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return []

        tabsTitles = {}
        tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<a', '>', 'tab-selector'), ('</a', '>'))
        for item in tmp:
            tabId = self.cm.ph.getSearchGroups(item, '''<a[^>]+?data\-tab=['"]\#([^'^"]+?)['"]''')[0]
            tabsTitles[tabId] = self.cleanHtmlStr(item)

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<ul', '>', 'tab-content'), ('</ul', '>'))
        tabs = []
        links = {}
        for tItem in data:
            tabId = self.cm.ph.getSearchGroups(tItem, '''<ul[^>]+?id=['"]([^'^"]+?)['"]''')[0]
            tabTitle = tabsTitles.get(tabId, tabId)
            links[tabTitle] = []
            tabs.append(tabTitle)
            lData = self.cm.ph.getAllItemsBeetwenMarkers(tItem, '<li', '</li>', withMarkers=True)
            for item in lData:
                item = self.cm.ph.getAllItemsBeetwenMarkers(item, '<a', '</a>')
                for it in item:
                    if 'data-link-id' not in it and 'class="_?video-link"' not in it:
                        continue
                    tmp = self.cm.ph.getSearchGroups(it, '<a[^>]+?href="([^"]+?)"[^>]*?>([^<]+?)<', 2)
                    if self.cm.isValidUrl(tmp[0]):
                        links[tabTitle].append({'name': '[{0}] '.format(tabTitle) + self.cleanHtmlStr(tmp[1]), 'url': tmp[0], 'need_resolve': 1})

        keys = ['Lektor', 'Napisy PL', 'Oryginał']
        keys.extend(links.keys())
        for key in keys:
            for item in links.get(key, []):
                urlTab.append(item)
            links.pop(key, None)

        self.cacheLinks[cItem['url']] = urlTab
        return urlTab

    def getVideoLinks(self, videoUrl):
        printDBG("IITVPL.getVideoLinks [%s]" % videoUrl)
        urlTab = []

        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            key = self.cacheLinks.keys()[0]
            for idx in range(len(self.cacheLinks[key])):
                if videoUrl in self.cacheLinks[key][idx]['url']:
                    if not self.cacheLinks[key][idx]['name'].startswith('*'):
                        self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name']
                    break

        url = self.getFullUrl('ajax/getLinkInfo')
        if 'link=' in videoUrl:
            linkID = videoUrl.split('link=')[-1].strip()
            post_data = {'link_id': linkID}
            HEADER = dict(self.AJAX_HEADER)
            HEADER['Referer'] = videoUrl
            sts, data = self.cm.getPage(url, {'header': HEADER}, post_data)
            if not sts:
                return []
            try:
                data = byteify(json.loads(data))
                data = data['results']
                printDBG(data)
                if 'embed_code' in data:
                    videoUrl = self.cm.ph.getSearchGroups(data['embed_code'], 'src="([^"]+?)"')[0]
                elif 'link' in data:
                    videoUrl = str(data['link'])
            except Exception:
                printExc()
        else:
            uri, sts = unshorten(videoUrl)
            if sts == 'OK':
                subUri = self.cm.ph.getSearchGroups(uri, '''/(https?://[^'"]+?)$''')[0]
                if self.cm.isValidUrl(subUri):
                    videoUrl = subUri
                elif self.up.checkHostSupport(uri):
                    videoUrl = uri

        if 1 != self.up.checkHostSupport(videoUrl):
            self.cm.getPage(videoUrl, {'max_data_size': 0})
            videoUrl = self.cm.meta.get('url', videoUrl)

        if videoUrl.startswith('http://') or videoUrl.startswith('https://'):
            return self.up.getVideoLinkExt(videoUrl)

        return urlTab

    def getArticleContent(self, cItem):
        printDBG("IITVPL.getArticleContent [%s]" % cItem)
        retTab = []
        url = cItem.get('url', '')

        if cItem['type'] == 'video':
            url = '/'.join(url.split('/')[:-1])

        sts, data = self.cm.getPage(url)
        if not sts:
            return retTab

        info = self.getSeriesInfo(data)

        otherInfo = {}
        if 'genre' in info:
            otherInfo['genre'] = info['genre']
        if 'station' in info:
            otherInfo['station'] = info['station']

        return [{'title': self.cleanHtmlStr(info['title']), 'text': self.cleanHtmlStr(info['desc']), 'images':[{'title': '', 'url': info['icon']}], 'other_info':otherInfo}]

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})
        elif category == 'list_abc':
            self.listABC(self.currItem, 'list_by_letter')
        elif category == 'list_by_letter':
            self.listSeriesByLetter(self.currItem, 'list_episodes')
        elif category == 'list_series1':
            self.listSeries(self.currItem, 'list_episodes', '<ul id="list">')
        if category == 'list_series2':
            self.listSeries(self.currItem, 'list_episodes', '<ul id="popular-list">')
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
        CHostBase.__init__(self, IITVPL(), True, [])

    def withArticleContent(self, cItem):
        if cItem['type'] != 'video' and cItem['category'] != 'list_episodes':
            return False
        return True
