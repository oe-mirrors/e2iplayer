# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
###################################################

###################################################
# FOREIGN import
###################################################
import re
try:
    import json
except Exception:
    import simplejson as json
###################################################


def gettytul():
    return 'https://altadefinizione01.film/'


class Altadefinizione(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'altadefinizione01.zone', 'cookie': 'altadefinizione01.zone.cookie'})

        self.USER_AGENT = 'Mozilla/5.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'})

        self.MAIN_URL = 'https://www.altadefinizione01.film/'
        self.DEFAULT_ICON_URL = 'https://previews.123rf.com/images/yusufsangdes89/yusufsangdes891507/yusufsangdes89150700042/42557652-cinema-camera-icon-movie-lover-series-icon.jpg'

        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)

        def _getFullUrl(url):
            if self.cm.isValidUrl(url):
                return url
            else:
                return urljoin(baseUrl, url)
        addParams['cloudflare_params'] = {'domain': self.up.getDomain(baseUrl), 'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT, 'full_url_handle': _getFullUrl}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def listMainMenu(self, cItem):
        printDBG("Altadefinizione.listMainMenu")

        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'before_widget'), ('<div', '>', 'before_widget'), False)[1]
        tmp = re.compile('''<div[^>]+?tab\-content[^>]*?>''').split(data)
        if len(tmp) == 2:
            tabs = []
            mainTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(tmp[0], ('<div', '>', 'widget-title'), ('</div', '>'))[1])
            tmp[0] = self.cm.ph.getAllItemsBeetwenMarkers(tmp[0], '<li', '</li>')
            for tabItem in tmp[0]:
                tabTitle = self.cleanHtmlStr(tabItem)
                key = self.cm.ph.getSearchGroups(tabItem, '''href=['"]\#([^"^']+?)['"]''')[0]
                if key == '':
                    continue
                categories = []
                tmp[1] = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', key), ('</ul', '>'), False)[1]
                tmp[1] = self.cm.ph.getAllItemsBeetwenMarkers(tmp[1], '<li', '</li>')
                for item in tmp[1]:
                    url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
                    title = self.cleanHtmlStr(item)
                    params = dict(cItem)
                    params.update({'name': 'category', 'category': 'list_items', 'title': title, 'url': url})
                    categories.append(params)

                if len(categories):
                    params = dict(cItem)
                    params.update({'name': 'category', 'category': 'sub_items', 'title': tabTitle, 'sub_items': categories})
                    tabs.append(params)

            if len(tabs):
                params = dict(cItem)
                params.update({'name': 'category', 'category': 'sub_items', 'title': mainTitle, 'sub_items': tabs})
                self.addDir(params)

        data = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'menu-menu'), ('</ul', '>'), False)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
        for item in data:
            url = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0]
            if 'attori' in url or '/domande' in url or '/richiedi' in url or '/player' in url:
                continue
            title = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'name': 'category', 'title': title, 'url': self.getFullUrl(url)})
            if '/catalog' in url:
                params['category'] = 'list_abc'
            else:
                params['category'] = 'list_items'
            self.addDir(params)

        MAIN_CAT_TAB = [{'category': 'search', 'title': _('Search'), 'search_item': True},
                        {'category': 'search_history', 'title': _('Search history')}]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listItems(self, cItem, nextCategory):
        printDBG("Altadefinizione.listItems")
        page = cItem.get('page', 1)
        postData = cItem.get('post_data')

        sts, data = self.getPage(cItem['url'], post_data=postData)
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'page_nav'), ('</div', '>'), False)[1]
        nextPage = self.cm.ph.getSearchGroups(nextPage, '''<a[^>]+?href=['"]([^'^"]+?)['"][^>]*?>%s<''' % (page + 1))[0]

        data = re.compile('''<div[^>]+?dle\-content[^>]+?>''').split(data, 1)
        data[-1] = re.compile('''<div[^>]+?right_bar[^>]+?>''').split(data[-1], 1)[0]
        if len(data) > 1 and page > 1:
            del data[0]

        for dataItem in data:
            if len(self.currList):
                self.addMarker({'title': ''})
            dataItem = self.cm.ph.rgetAllItemsBeetwenNodes(dataItem, ('</div', '>'), ('<div', '>', 'boxgrid_shadow'), False)
            for item in dataItem:
                tmp = self.cm.ph.getDataBeetwenNodes(item, ('<h', '>'), ('</h', '>'), False)[1]

                icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''<img[^>]+?src=['"]([^"^']+?)['"]''')[0])
                url = self.getFullUrl(self.cm.ph.getSearchGroups(tmp, '''href=['"]([^"^']+?)['"]''')[0])
                title = self.cleanHtmlStr(tmp)

                desc = []
                t = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'trdublaj'), ('</div', '>'), False)[1])
                if t != '':
                    desc.append(t)
                item = item.split('list-inline', 1)[-1]
                tmp = self.cm.ph.getAllItemsBeetwenNodes(item, ('<li', '>'), ('</li', '>'), False)
                for t in tmp:
                    t = self.cleanHtmlStr(t)
                    if t != '':
                        desc.append(t)

                desc = [' | '.join(desc)]
                tmp = self.cm.ph.getAllItemsBeetwenNodes(item, ('<p', '>'), ('</p', '>'), False)
                for t in tmp:
                    t = self.cleanHtmlStr(t)
                    if t != '':
                        desc.append(t)

                params = dict(cItem)
                params.update({'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'icon': icon, 'desc': '[/br]'.join(desc)})
                self.addDir(params)

        if nextPage != '':
            params = dict(cItem)
            params.update({'title': _("Next page"), 'page': page + 1})
            if nextPage != '#':
                params['url'] = self.getFullUrl(nextPage)
                self.addDir(params)
            elif postData != {}:
                postData = dict(postData)
                postData.pop('titleonly', None)
                postData.update({'search_start': page + 1, 'full_search': '0', 'result_from': 10 * page + 1})
                params['post_data'] = postData
                self.addDir(params)
            else:
                printDBG("NextPage [%s] not handled!!!" % nextPage)

    def listABC(self, cItem, nextCategory):
        printDBG("Altadefinizione.listABC")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'alphabet'), ('</div', '>'), False)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
        for item in data:
            title = self.cleanHtmlStr(item)
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0])
            params = dict(cItem)
            params.update({'good_for_fav': False, 'category': nextCategory, 'title': title, 'url': url})
            self.addDir(params)

    def listABCItems(self, cItem, nextCategory):
        printDBG("Altadefinizione.listABCItems")
        page = cItem.get('page', 1)

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'page_nav'), ('</div', '>'), False)[1]
        nextPage = self.cm.ph.getSearchGroups(nextPage, '''<a[^>]+?href=['"]([^'^"]+?)['"][^>]*?>%s<''' % (page + 1))[0]

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<tr', '>', 'mlnew'), ('</tr', '>'), False)
        for item in data:
            tmp = self.cm.ph.getDataBeetwenNodes(item, ('<h', '>'), ('</h', '>'), False)[1]

            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''<img[^>]+?src=['"]([^"^']+?)['"]''')[0].replace('/40x59-', '/203x293-'))
            url = self.getFullUrl(self.cm.ph.getSearchGroups(tmp, '''href=['"]([^"^']+?)['"]''')[0])
            title = self.cleanHtmlStr(tmp)
            if url == '':
                continue

            desc = []
            tmp = self.cm.ph.getAllItemsBeetwenNodes(item, ('<td', '>'), ('</td', '>'), False)[3:]
            for t in tmp:
                t = self.cleanHtmlStr(t)
                if t != '':
                    desc.append(t)

            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'icon': icon, 'desc': ' | '.join(desc)})
            self.addDir(params)

        if nextPage != '':
            params = dict(cItem)
            params.update({'title': _("Next page"), 'url': self.getFullUrl(nextPage), 'page': page + 1})
            self.addDir(params)

    def exploreItem(self, cItem):
        printDBG("Altadefinizione.exploreItem")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        cItem = dict(cItem)
        cItem['prev_url'] = cItem['url']

        trailer = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'btn_trailer'), ('</div', '>'), False)[1]
        url = self.getFullUrl(self.cm.ph.getSearchGroups(trailer, '''href=['"]([^"^']+?)['"]''', 1, True)[0])
        if self.cm.isValidUrl(url):
            title = self.cleanHtmlStr(trailer)
            params = dict(cItem)
            params.update({'good_for_fav': False, 'url': url, 'title': '%s %s' % (title, cItem['title'])})
            self.addVideo(params)

        urlTab = []
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<ul', '>', 'host'), ('</ul', '>'), False)
        for idx in range(len(data)):
            data[idx] = self.cm.ph.getAllItemsBeetwenMarkers(data[idx], '<a', '</a>')
            for item in data[idx]:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''data\-link=['"]([^"^']+?)['"]''', 1, True)[0])
                if 1 == self.up.checkHostSupport(url):
                    name = self.cleanHtmlStr(item)
                    url = strwithmeta(url, {'Referer': cItem['url']})
                    urlTab.append({'name': name, 'url': url, 'need_resolve': 1})

        if len(urlTab):
            params = dict(cItem)
            params.update({'good_for_fav': False, 'urls_tab': urlTab})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Altadefinizione.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('index.php?do=search')
        cItem['post_data'] = {'do': 'search', 'subaction': 'search', 'titleonly': '3', 'story': searchPattern}
        cItem['category'] = 'list_items'
        self.listItems(cItem, 'explore_item')

    def getLinksForVideo(self, cItem):
        printDBG("Altadefinizione.getLinksForVideo [%s]" % cItem)
        if 1 == self.up.checkHostSupport(cItem['url']):
            return self.up.getVideoLinkExt(cItem['url'])
        return cItem.get('urls_tab', [])

    def getVideoLinks(self, videoUrl):
        printDBG("Altadefinizione.getVideoLinks [%s]" % videoUrl)
        return self.up.getVideoLinkExt(videoUrl)

    def getArticleContent(self, cItem):
        printDBG("Altadefinizione.getVideoLinks [%s]" % cItem)
        retTab = []
        itemsList = []

        if 'prev_url' in cItem:
            url = cItem['prev_url']
        else:
            url = cItem['url']

        sts, data = self.cm.getPage(url)
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 's_left'), ('<div', '>', 'comment'), False)[1]

        icon = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'imagen'), ('</div', '>'), False)[1]
        icon = self.getFullUrl(self.cm.ph.getSearchGroups(icon, '''<img[^>]+?src=['"]([^'^"]+?)['"]''')[0])
        title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<p', '>', 'title'), ('</p', '>'), False)[1])
        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'entry-content'), ('</div', '>'), False)[1])

        tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<p', '>', 'meta_dd'), ('</p', '>'), False)
        for item in tmp:
            if 'title' in item:
                item = [self.cm.ph.getSearchGroups(item, '''title=['"]([^'^"]+?)['"]''')[0], item]
            else:
                item = item.split('</b>', 1)
                if len(item) < 2:
                    continue
            key = self.cleanHtmlStr(item[0])
            val = self.cleanHtmlStr(item[1])
            if key == '' or val == '':
                continue
            itemsList.append((key, val))

        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<span', '>', 'dato'), ('</span', '>'), False)[1])
        if tmp != '':
            itemsList.append((_('Rating'), tmp))

        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<p', '>', 'views'), ('</p', '>'), False)[1])
        if tmp != '':
            itemsList.append((_('Views'), tmp))
        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<p', '>', 'date'), ('</p', '>'), False)[1])
        if tmp != '':
            itemsList.append((_('Relese'), tmp))

        if title == '':
            title = cItem['title']
        if icon == '':
            icon = cItem.get('icon', self.DEFAULT_ICON_URL)
        if desc == '':
            desc = cItem.get('desc', '')

        return [{'title': self.cleanHtmlStr(title), 'text': self.cleanHtmlStr(desc), 'images': [{'title': '', 'url': self.getFullUrl(icon)}], 'other_info': {'custom_items_list': itemsList}}]

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: || name[%s], category[%s] " % (name, category))
        self.currList = []
        self.currItem = dict(self.currItem)
        self.currItem.pop('good_for_fav', None)

    #MAIN MENU
        if name == None:
            self.listMainMenu({'name': 'category', 'type': 'category'})
        elif category == 'list_items':
            self.listItems(self.currItem, 'explore_item')
        elif category == 'explore_item':
            self.exploreItem(self.currItem)
        elif category == 'list_abc':
            self.listABC(self.currItem, 'list_abc_items')
        elif category == 'list_abc_items':
            self.listABCItems(self.currItem, 'explore_item')
        elif category == 'sub_items':
            self.currList = self.currItem.get('sub_items', [])
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
        CHostBase.__init__(self, Altadefinizione(), True, favouriteTypes=[])

    def withArticleContent(self, cItem):
        if 'prev_url' in cItem or cItem.get('category', '') == 'explore_item':
            return True
        else:
            return False
