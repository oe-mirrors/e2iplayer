# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify
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
    return 'http://tvproart.pl/'


class TVProart(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'TVProart', 'cookie': 'tvproart.cookie'})
        self.DEFAULT_ICON_URL = 'http://www.ostrowwlkp.info/images/firmy-i-instytucje/39/logo.jpg'
        self.MAIN_URL = 'http://tvproart.pl/'
        self.API_URL = self.getFullUrl('ajaxVod/')
        self.SEARCH_URL = self.getFullUrl('search?q=')

        self.MAIN_CAT_TAB = [{'category': 'categories', 'title': 'VOD'},
                             {'category': 'search', 'title': _('Search'), 'search_item': True},
                             {'category': 'search_history', 'title': _('Search history')}]
        self.categories = {}

    def addNextPage(self, cItem, nextPage, page):
        if nextPage:
            params = dict(cItem)
            params.update({'title': _('Next page'), 'page': page + 1})
            self.addDir(params)

    def listCategories(self, cItem, category):
        printDBG("TVProart.listCategories [%s]" % cItem)
        if self.categories == {}:
            sts, data = self.cm.getPage(self.API_URL + 'categories')
            if not sts:
                return
            try:
                data = byteify(json.loads(data))
                if data['status'] != '200':
                    return
                self.categories = data['content']
            except Exception:
                printExc()
        try:
            for item in self.categories['cats']:
                params = dict(cItem)
                params.update({'title': item['title'], 'id': item['id'], 'slug': item['slug'], 'icon': self.getFullUrl(item['image']), 'category': category})
                self.addDir(params)
        except Exception:
            printExc()

    def listVideos(self, cItem):
        printDBG("TVProart.listVideos [%s]" % cItem)
        page = cItem.get('page', 1)
        url = self.API_URL + 'movies?type=cats&crit_id={0}'.format(cItem['slug'])
        sts, data = self.cm.getPage(url + '&page={0}'.format(page))
        if not sts:
            return
        nextPage = False
        try:
            data = json.loads(data)
            if data['status'] != '200':
                return
            for item in data['content']:
                icon = self.getFullUrl(item['thumb'].encode('utf-8'))
                item = item['data']
                url = self.API_URL + 'video?id={0}&slug={1}'.format(str(item['id']), item['slug'].encode('utf-8'))
                title = item['title'].encode('utf-8')
                date = item['date'].encode('utf-8')
                if date not in title:
                    title += ' [%s]' % date
                params = {'title': title, 'url': url, 'icon': icon, 'desc': date}
                self.addVideo(params)
        except Exception:
            printExc()

        nextPage = False
        try:
            sts, data = self.cm.getPage(url + '&page={0}'.format(page + 1))
            data = byteify(json.loads(data))
            if len(data['content']) > 0:
                nextPage = True
        except Exception:
            pass
        self.addNextPage(cItem, nextPage, page)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("TVProart.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        page = cItem.get('page', 0)
        url = self.SEARCH_URL + urllib.quote(searchPattern)
        sts, data = self.cm.getPage(url + '&page={0}'.format(page))
        if not sts:
            return
        nextPage = False
        try:
            data = byteify(json.loads(data))
            if data['status'] != '200':
                return
            for item in data['content']['movies']:
                tmp = item['href'].split('/')
                url = self.API_URL + 'video?id={0}&slug={1}'.format(tmp[-2], tmp[-1])
                params = {'title': item['text'], 'url': url}
                self.addVideo(params)
        except Exception:
            printExc()

    def getLinksForVideo(self, cItem):
        printDBG("TVProart.getLinksForVideo [%s]" % cItem)
        urlTab = []
        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return []
        try:
            data = byteify(json.loads(data))
            urlTab.append({'name': 'vod', 'url': data['content']['video']['movieFile'], 'need_resolve': 0})
        except Exception:
            pass
        return urlTab

    def getFavouriteData(self, cItem):
        return cItem['url']

    def getLinksForFavourite(self, fav_data):
        return self.getLinksForVideo({'url': fav_data})

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("handleService: || name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})
    #CATEGORIES
        elif category == 'categories':
            self.listCategories(self.currItem, 'category')
    #CATEGORY
        elif category == 'category':
            self.listVideos(self.currItem)
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
        CHostBase.__init__(self, TVProart(), True, [CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO])
