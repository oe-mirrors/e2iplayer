# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
###################################################
# FOREIGN import
###################################################
from Components.config import config, ConfigSelection
import re
try:
    import simplejson as json
except Exception:
    import json
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.hitbox_iconssize = ConfigSelection(default="medium", choices=[("large", _("large")), ("medium", _("medium")), ("small", _("small"))])


def GetConfigList():
    optionList = []
    return optionList
###################################################


def gettytul():
    return 'https://pinkbike.com/'


class Pinkbike(CBaseHostClass):

    MAIN_URL = 'http://www.pinkbike.com/'
    VID_MAIN_URL = MAIN_URL + 'video/'
    VID_SRCH_URL = VID_MAIN_URL + 'search/?q='
    DEFAULT_ICON_URL = 'http://ep1.pinkbike.org/p2pb10472249/p2pb10472249.jpg'

    MAIN_CAT_TAB = [{'category': 'best_video_categories', 'title': _('Best Pinkbike Videos')},
                    {'category': 'video_categories', 'title': _('Categories')},
                    {'category': 'search', 'title': _('Search'), 'search_item': True},
                    {'category': 'search_history', 'title': _('Search history')}]

    def __init__(self):
        printDBG("Pinkbike.__init__")
        CBaseHostClass.__init__(self, {'history': 'Pinkbike.tv'})
        self.best = []
        self.categories = []
        self.catItems = {}

    def _fillCategories(self):
        printDBG("Pinkbike._fillCategories")
        if len(self.best):
            return
        sts, data = self.cm.getPage(Pinkbike.VID_MAIN_URL)
        if not sts:
            return
        bestData = self.cm.ph.getDataBeetwenMarkers(data, 'Best Pinkbike Videos', '</div>', False)[1]
        bestData = re.compile('href="([^"]+?)"[^>]*?>([^<]+?)</a>').findall(bestData)
        for item in bestData:
            self.best.append({'url': item[0], 'title': item[1]})

        if len(self.categories):
            return

        data = self.cm.ph.getDataBeetwenMarkers(data, '<td valign="top" width="25%">', '</div>', False)[1]
        data = data.split('</table>')
        if len(data):
            del data[-1]
        for item in data:
            title = self.cm.ph.getDataBeetwenMarkers(item, '<h3>', '</h3>', False)[1]
            desc = self.cm.ph.getDataBeetwenMarkers(item, '<h5>', '</h5>', False)[1]

            catItems = []
            tmp = re.compile('<td>(.+?)</td>').findall(item)
            for cat in tmp:
                url = self.cm.ph.getSearchGroups(cat, 'href="([^"]+?)"')[0]
                tit = self.cleanHtmlStr(cat)
                if url.startswith('http'):
                    catItems.append({'title': tit, 'url': url})

            if len(tmp):
                self.categories.append({'title': title, 'desc': desc})
                self.catItems[title] = catItems

    def listBestCategories(self, cItem, category):
        printDBG("Pinkbike.listBestCategories")
        self._fillCategories()
        for item in self.best:
            params = dict(cItem)
            params.update(item)
            params['category'] = category
            self.addDir(params)

    def listCategories(self, cItem, category):
        printDBG("Pinkbike.listCategories")
        self._fillCategories()
        for item in self.categories:
            params = dict(cItem)
            params.update(item)
            params['category'] = category
            self.addDir(params)

    def listCatItems(self, cItem, category):
        printDBG("Pinkbike.listSubCategories")
        for item in self.catItems[cItem['title']]:
            params = dict(cItem)
            params.update(item)
            params['category'] = category
            self.addDir(params)

    def listVideos(self, cItem):
        printDBG("Pinkbike.listVideos")
        page = cItem.get('page', 1)
        if '?' in cItem['url']:
            url = cItem['url'] + '&'
        else:
            url = cItem['url'] + '?'
        url = url + 'page=' + str(page)
        sts, data = self.cm.getPage(url)
        if not sts:
            return
        if ('page=%d"' % (page + 1)) in data:
            nextPage = True
        else:
            nextPage = False

        if '<table class="paging-container">' in data:
            marker = '<table class="paging-container">'
        else:
            marker = '<div class="foot f11">'
        data = self.cm.ph.getDataBeetwenMarkers(data, '<div id="inList" class="fullview">', marker, False)[1]
        data = data.split('</ul>')
        if len(data):
            del data[-1]
        for item in data:
            item = item.split('</li>')
            icon = self.cm.ph.getSearchGroups(item[0], 'src="([^"]+?)"')[0]
            desc = self.cleanHtmlStr(item[1])
            url = self.cm.ph.getSearchGroups(item[1], 'href="([^"]+?)"')[0]
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item[1], 'title="([^"]+?)"')[0] + ' ' + self.cm.ph.getSearchGroups(item[1], '<a [^>]+?>(.+?)</a>')[0])
            self.addVideo({'title': title, 'url': self.getFullUrl(url), 'icon': self.getFullUrl(icon), 'desc': desc})

        if nextPage:
            params = dict(cItem)
            params.update({'title': _('Next page'), 'page': page + 1})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Pinkbike.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        searchPattern = urllib_quote_plus(searchPattern)
        item = dict(cItem)
        item['category'] = 'list_videos'
        item['url'] = Pinkbike.VID_SRCH_URL + searchPattern
        self.listVideos(item)

    def getLinksForVideo(self, cItem):
        printDBG("Pinkbike.getLinksForVideo [%s]" % cItem)
        urlTab = []
        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return urlTab
        data = self.cm.ph.getDataBeetwenMarkers(data, '<video', '</video>', False)[1].replace('\\"', '"')
        data = re.compile('data-quality="([^"]+?)"[^>]+?src="([^"]+?)"').findall(data)
        for item in data:
            urlTab.append({'name': item[0], 'url': self.getFullUrl(item[1])})
        return urlTab

    def getFavouriteData(self, cItem):
        return cItem['url']

    def getLinksForFavourite(self, fav_data):
        return self.getLinksForVideo({'url': fav_data})

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('Pinkbike.handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", None)
        category = self.currItem.get("category", '')
        printDBG("Pinkbike.handleService: ---------> name[%s], category[%s] " % (name, category))
        searchPattern = self.currItem.get("search_pattern", searchPattern)
        self.currList = []

        if None == name:
            self.listsTab(Pinkbike.MAIN_CAT_TAB, {'name': 'category'})
        elif 'best_video_categories' == category:
            self.listBestCategories(self.currItem, 'list_videos')
        elif 'video_categories' == category:
            self.listCategories(self.currItem, 'list_sub_video_categories')
        elif 'list_sub_video_categories' == category:
            self.listCatItems(self.currItem, 'list_videos')
        elif 'list_videos' == category:
            self.listVideos(self.currItem)
    #WYSZUKAJ
        elif category in ["search"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category'})
            self.listSearchResult(cItem, searchPattern, searchType)
    #HISTORIA WYSZUKIWANIA
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Pinkbike(), True, [CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO])
