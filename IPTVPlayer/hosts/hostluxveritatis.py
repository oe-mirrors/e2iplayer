# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, getMPDLinksWithMeta
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs import ph
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib
###################################################


def gettytul():
    return 'https://luxveritatis.pl/'


class LuxVeritatisPL(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'luxveritatis.pl', 'cookie': 'luxveritatis.pl.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.MAIN_URL_T = 'http://tv-trwam.pl/'
        self.MAIN_URL_R = 'http://www.radiomaryja.pl/'
        self.MAIN_URL = None
        self.DEFAULT_ICON_URL = 'https://luxveritatis.pl/sites/all/themes/luxveritatis/img/logo.png'
        self.ICON_URL_R = 'https://mir-s3-cdn-cf.behance.net/projects/404/84c55124983499.551bd47bd2b6a.png'
        self.ICON_URL_T = 'http://archidiecezjalubelska.pl/wp-content/uploads/2016/07/trwam.jpg'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate'}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding': 'gzip, deflate', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': '*/*'})

        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def getFullUrl(self, url, curUrl=None):
        url = CBaseHostClass.getFullUrl(self, url, curUrl)
        return url.replace('&amp;', '&')

    def listMainMenu(self, cItem):
        printDBG("LuxVeritatisPL.listMainMenu")

        MAIN_CAT_TAB = [{'category': 'tv_trwam', 'title': 'TV Trwam', 'url': self.MAIN_URL_T, 'desc': self.MAIN_URL_T, 'icon': self.ICON_URL_T},
                        {'category': 'radio', 'title': 'Radio Maryja', 'url': self.MAIN_URL_R, 'desc': self.MAIN_URL_R, 'icon': self.ICON_URL_R},
                        {'category': 'search', 'title': _('Search'), 'search_item': True},
                        {'category': 'search_history', 'title': _('Search history')}, ]

        self.listsTab(MAIN_CAT_TAB, cItem)

    def listRadio(self, cItem, nextCategory):
        printDBG("LuxVeritatisPL.listRadio [%s]" % cItem)

        self.MAIN_URL = self.MAIN_URL_R

        desc = ''
        sts, data = self.getPage(self.getFullUrl('/wp-admin/admin-ajax.php'), post_data={'action': 'terazNaAntenie'})
        if sts:
            try:
                data = json_loads(data)
                desc = '%s, %s[/br]%s' % (data.get('godz', ''), data.get('goscie', ''), data.get('opis', ''))
            except Exception:
                printExc()

        params = dict(cItem)
        params.update({'good_for_fav': True, 'title': 'Słuchaj - Radio Maryja', 'desc': desc, 'url': self.getFullUrl('/live/')})
        self.addAudio(params)

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenNodes(data, ('<section ', '>', 'widget_nav_menu'), ('<footer', '>'))[1]
        audioData = self.cm.ph.getDataBeetwenNodes(data, ('<a', '<', 'Audio'), ('</ul', '>'))[1]
        videoData = self.cm.ph.getDataBeetwenNodes(data, ('<a', '<', 'Video'), ('</ul', '>'))[1]
        data = [audioData, videoData]
        for sectionItem in data:
            idx = sectionItem.find('<ul')
            if idx == -1:
                continue
            sTitle = self.cleanHtmlStr(sectionItem[:idx])
            tabItems = []
            sectionItem = self.cm.ph.getAllItemsBeetwenMarkers(sectionItem, '<a', '</a>')
            for idx in range(len(sectionItem)):
                url = self.getFullUrl(self.cm.ph.getSearchGroups(sectionItem[idx], '''\shref=['"]([^'^"]+?)['"]''')[0])
                title = self.cleanHtmlStr(sectionItem[idx])
                if idx == 0:
                    title = '--Wszystkie--'
                tabItems.append({'title': title, 'url': url})
            if len(tabItems):
                params = dict(cItem)
                params.update({'good_for_fav': False, 'category': nextCategory, 'title': sTitle, 'items': tabItems})
                self.addDir(params)

    def listRadioCats(self, cItem, nextCategory):
        printDBG("LuxVeritatisPL.listRadioCats [%s]" % cItem)

        cItem = dict(cItem)
        itemsTab = cItem.pop('items', [])
        cItem.update({'good_for_fav': True, 'category': nextCategory})
        self.listsTab(itemsTab, cItem)

    def listRadioItems(self, cItem, nextCategory):
        printDBG("LuxVeritatisPL.listRadioItems [%s]" % cItem)

        self.MAIN_URL = self.MAIN_URL_R

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenMarkers(data, '<main', '</main>')[1]
        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<a', '<', '&rsaquo;'), ('/a', '>'))[1]
        nextPage = self.cm.ph.getSearchGroups(nextPage, '''\shref=['"]([^'^"]+?)['"]''')[0]

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<article', '</article>')
        for item in data:
            tmp = self.cm.ph.getDataBeetwenMarkers(item, '<header', '</header>')[1].split('</h2>', 1)
            title = self.cleanHtmlStr(tmp[0])
            desc = []
            desc.append(self.cleanHtmlStr(tmp[-1]))
            desc.append(self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'text'), ('</div', '>'))[1]))
            url = self.getFullUrl(self.cm.ph.getSearchGroups(tmp[0], '''\shref=['"]([^'^"]+?)['"]''')[0])
            if '/multimedia/' not in url:
                continue
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''<img[^>]+?src=['"]([^'^"]+?)['"]''')[0])

            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'icon': icon, 'desc': '[/br]'.join(desc)})
            self.addDir(params)

        if nextPage != '':
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _('Next page'), 'url': self.getFullUrl(nextPage)})
            self.addDir(params)

    def exploreRadioItem(self, cItem):
        printDBG("LuxVeritatisPL.listRadioItems [%s]" % cItem)

        self.MAIN_URL = self.MAIN_URL_R

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        tmp = self.cm.ph.getAllItemsBeetwenMarkers(data, '<iframe', '>')
        for item in tmp:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''', 1, True)[0])
            if 1 != self.up.checkHostSupport(url):
                continue
            params = dict(cItem)
            params.update({'good_for_fav': True, 'title': '[%s] %s' % ('wideo', cItem['title']), 'url': url})
            self.addVideo(params)

        addedLinks = []
        tmp = re.compile('''['"]?soundFile['"]?\s*?:\s*?['"]([^'^"]+?\.mp3(?:\?[^'^"]*?)?)['"]''').findall(data)
        for url in tmp:
            if url in addedLinks:
                continue
            addedLinks.append(url)
            params = dict(cItem)
            params.update({'good_for_fav': True, 'title': '[%s] %s' % ('audio', cItem['title']), 'url': url})
            self.addAudio(params)

    ###########################################################################################
    ###########################################################################################
    def listTVTrwam(self, cItem, nextCategory1, nextCategory2):
        printDBG("LuxVeritatisPL.listTVTrwam [%s]" % cItem)

        self.MAIN_URL = self.MAIN_URL_T

        params = dict(cItem)
        params.update({'good_for_fav': True, 'title': 'Transmisja live - TV Trwam', 'url': self.getFullUrl('/na-zywo')})
        self.addVideo(params)

        params = dict(cItem)
        params.update({'good_for_fav': False, 'category': nextCategory2, 'title': 'Polecane', 'url': self.getFullUrl('/filmy?Filter.Sort=Recommended')})
        self.addDir(params)

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        sectionItem = self.cm.ph.getDataBeetwenNodes(data, ('<a', '<', 'Audycje'), ('</ul', '>'))[1]
        idx = sectionItem.find('<ul')
        if idx == -1:
            return
        sTitle = self.cleanHtmlStr(sectionItem[:idx])
        tabItems = []
        sectionItem = self.cm.ph.getAllItemsBeetwenMarkers(sectionItem, '<a', '</a>')
        for idx in range(len(sectionItem)):
            url = self.getFullUrl(self.cm.ph.getSearchGroups(sectionItem[idx], '''\shref=['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(sectionItem[idx])
            if idx == 0:
                title = '--Wszystkie--'
            tabItems.append({'title': title, 'url': url})
        if len(tabItems):
            params = dict(cItem)
            params.update({'good_for_fav': False, 'category': nextCategory1, 'title': sTitle, 'items': tabItems})
            self.addDir(params)

    def listTVTrwamCats(self, cItem, nextCategory):
        printDBG("LuxVeritatisPL.listTVTrwamCats [%s]" % cItem)

        cItem = dict(cItem)
        itemsTab = cItem.pop('items', [])
        cItem.update({'good_for_fav': True, 'category': nextCategory})
        self.listsTab(itemsTab, cItem)

    def listTVTrwamSort(self, cItem, nextCategory):
        printDBG("LuxVeritatisPL.listTVTrwamSort [%s]" % cItem)

        self.MAIN_URL = self.MAIN_URL_T

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '<', 'sort-list'), ('</ul', '>'))[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
        for item in data:
            title = self.cleanHtmlStr(item)
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0])
            params = dict(cItem)
            params.update({'good_for_fav': False, 'category': nextCategory, 'title': title.title(), 'url': url})
            self.addDir(params)

    def listTVTrwamItems(self, cItem):
        printDBG("LuxVeritatisPL.listTVTrwamItems [%s]" % cItem)

        self.MAIN_URL = self.MAIN_URL_T

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenMarkers(data, '<main', '</main>')[1]
        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<a', '</a>', '&rsaquo;'), ('<', '>'))[1]
        nextPage = self.cm.ph.getSearchGroups(nextPage, '''\shref=['"]([^'^"]+?)['"]''')[0]

        data = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'movie-grid__list'), ('</ul', '>'))[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<article', '</article>')
        for item in data:
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h1', '</h1>')[1])
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''\ssrc=['"]([^'^"]+?)['"]''')[0])

            desc = []
            t1 = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<', '>', '_description'), ('</', '>'))[1])
            desc.append(t1)
            t1 = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<time', '</time>')[1])
            t2 = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<', '>', '_duration'), ('</', '>'))[1])
            desc.append('%s / %s' % (t1, t2))

            params = dict(cItem)
            params.update({'good_for_fav': True, 'title': title, 'url': url, 'icon': icon, 'desc': '[/br]'.join(desc)})
            self.addVideo(params)

        if nextPage != '':
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _('Next page'), 'url': self.getFullUrl(nextPage)})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("LuxVeritatisPL.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        if searchType == 'radio':
            self.MAIN_URL = self.MAIN_URL_R
            cItem['category'] = 'list_radio_items'
            cItem['url'] = self.getFullUrl('/?s=') + urllib.quote_plus(searchPattern)
            cItem['icon'] = self.ICON_URL_R
            self.listRadioItems(cItem, 'explore_radio_item')
        elif searchType == 'tv':
            self.MAIN_URL = self.MAIN_URL_T
            cItem['category'] = 'list_tv_trwam_items'
            cItem['url'] = self.getFullUrl('/filmy?Filter.Query=') + urllib.quote_plus(searchPattern)
            cItem['icon'] = self.ICON_URL_T
            self.listTVTrwamItems(cItem)

    def getLinksForVideo(self, cItem):
        printDBG("LuxVeritatisPL.getLinksForVideo [%s]" % cItem)
        linksTab = []
        url = cItem['url']
        if 'radiomaryja.pl' in url and url.endswith('/live/'):
            sts, data = self.getPage(url)
            if not sts:
                return
            url = ph.search(data, '''<a[^>]+?href=['"](https?://[^>]+?\.pls(?:\?[^'^"]*?)?)['"]''')[0]
            if url:
                sts, tmp = self.getPage(url)
                if sts:
                    tmp = re.compile('''(File[0-9]+?)=(https?://.+)''').findall(tmp)
                    for item in tmp:
                        linksTab.append({'name': item[0], 'url': item[1], 'need_resolve': 0})
            url = ph.find(data, ('<a', '>', '/live2'))[1]
            url = self.getFullUrl(ph.getattr(url, 'href'))
            if url:
                sts, data = self.getPage(url)
                if not sts:
                    return linksTab
            url = ph.search(data, '''<a[^>]+?href=['"](https?://[^>]+?\.m3u8(?:\?[^'^"]*?)?)['"]''')[0]
            linksTab.extend(getDirectM3U8Playlist(url, checkContent=True))
        elif 'tv-trwam' in url:
            sts, data = self.getPage(url)
            if not sts:
                return
            data = self.cm.ph.getSearchGroups(data, '''sources\s*?:\s*?(\[[^\]]+?\])''')[0]
            try:
                data = json_loads(data)
                hlsTab = []
                dashTab = []
                mp4Tab = []
                for item in data:
                    vidUrl = item['src']
                    type = item['type'].lower()
                    if 'dash' in type:
                        dashTab.extend(getMPDLinksWithMeta(vidUrl, checkExt=False, cookieParams=self.defaultParams, sortWithMaxBandwidth=999999999))
                    elif 'x-mpegurl' in type:
                        hlsTab.extend(getDirectM3U8Playlist(vidUrl, checkExt=False, checkContent=True, cookieParams=self.defaultParams, sortWithMaxBitrate=999999999))
                    elif 'mp4' in type:
                        mp4Tab.append({'name': '[mp4] %s' % vidUrl.split('/')[-1].split('_', 1)[-1].split('.', 1)[0], 'url': vidUrl})
                linksTab.extend(hlsTab)
                linksTab.extend(dashTab)
                linksTab.extend(mp4Tab)
            except Exception:
                printExc()
        elif 1 == self.up.checkHostSupport(url):
            return self.up.getVideoLinkExt(url)
        elif url.split('?', 1)[0].endswith('.mp3'):
            return [{'name': 'MP3', 'url': url}]

        return linksTab

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: |||| name[%s], category[%s] " % (name, category))
        self.cacheLinks = {}
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listMainMenu({'name': 'category'})
    # RADIO MARYJA
        elif category == 'radio':
            self.listRadio(self.currItem, 'list_radio_cats')
        elif category == 'list_radio_cats':
            self.listRadioCats(self.currItem, 'list_radio_items')
        elif category == 'list_radio_items':
            self.listRadioItems(self.currItem, 'explore_radio_item')
        elif category == 'explore_radio_item':
            self.exploreRadioItem(self.currItem)
    # TV TRWAM
        elif category == 'tv_trwam':
            self.listTVTrwam(self.currItem, 'list_tv_trwam_cats', 'list_tv_trwam_items')
        elif category == 'list_tv_trwam_cats':
            self.listTVTrwamCats(self.currItem, 'list_tv_trwam_sorts')
        elif category == 'list_tv_trwam_sorts':
            self.listTVTrwamSort(self.currItem, 'list_tv_trwam_items')
        elif category == 'list_tv_trwam_items':
            self.listTVTrwamItems(self.currItem)
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
        CHostBase.__init__(self, LuxVeritatisPL(), True, [])

    def getSearchTypes(self):
        searchTypesOptions = []
        searchTypesOptions.append(("TV Trwam", "tv"))
        searchTypesOptions.append(("Radio Maryja", "radio"))
        return searchTypesOptions
