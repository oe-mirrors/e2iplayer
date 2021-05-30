# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, CSearchHistoryHelper, printExc, byteify
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common, CParsingHelper
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib
try:
    import json
except Exception:
    import simplejson
###################################################

###################################################
# Config options for HOST
###################################################
# None


def GetConfigList():
    optionList = []
    # None
    return optionList
###################################################


def gettytul():
    return 'http://ninateka.pl/'


class Ninateka(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'ninateka', 'cookie': 'ninateka.cookie'})
        self.DEFAULT_ICON_URL = 'http://ninateka.pl/Content/images/ninateka_logo.png'

        self.menuHTML = ''
        self.refresh = False
        self.cm = common()
        self.history = CSearchHistoryHelper('ninateka')

        self.MAIN_URL = 'http://ninateka.pl/'
        self.VIDEOS_URL = self.getFullUrl('filmy?MediaType=video&Paid=False&CategoryCodenames=')
        self.SEARCH_URL = self.VIDEOS_URL + '&SearchQuery='

        #DEFAULT_GET_PARAM = 'MediaType=video&Paid=False'

        self.MAIN_CAT_TAB = [{'category': 'list_all', 'title': 'Wszystkie', 'url': self.VIDEOS_URL},
                             {'category': 'list_cats', 'title': 'Kategorie', 'url': self.MAIN_URL},

                             {'category': 'search', 'title': _('Search'), 'search_item': True, },
                             {'category': 'search_history', 'title': _('Search history'), }
                            ]

    def getMenuHTML(self):
        printDBG("getMenuHTML start")

        if True == self.refresh or '' == self.menuHTML:
            self.menuHTML = ''
            sts, data = self.cm.getPage(self.MAIN_URL)
            if sts:
                self.menuHTML = CParsingHelper.getDataBeetwenMarkers(data, '<div class="nav-collapse collapse">', '<!--/.nav-collapse -->', False)[1]
        return self.menuHTML

    def getMainCategory(self):
        menuHTML = self.getMenuHTML()

        match = re.compile('<li data-codename="([^"]+?)"><a href="/filmy/([^"^,^/]+?)">([^<]+?)</a>').findall(menuHTML)
        if len(match) > 0:
            for i in range(len(match)):
                params = {'name': 'main-category', 'page': match[i][0], 'title': match[i][2]}
                self.addDir(params)

    def getSubCategory(self, cat):
        menuHTML = self.getMenuHTML()

        pattern = '<li data-codename="([^"]+?)"><a href="/filmy/(%s,[^"^,^/]+?)">([^<]+?)</a></li>' % cat
        match = re.compile(pattern).findall(menuHTML)
        if len(match) > 0:
            for i in range(len(match)):
                params = {'name': 'sub-category', 'page': self.VIDEOS_URL + (match[i][1]).replace(',', '%2C'), 'title': match[i][2]}
                self.addDir(params)

    def getLinksForVideo(self, cItem):
        printDBG("getVideoUrl url[%s]" % cItem)
        linksTab = []
        url = cItem['url']
        sts, data = self.cm.getPage(url)
        if not sts:
            printDBG("getVideoUrl except")
            return linksTab

        try:
            arg = self.cm.ph.getDataBeetwenMarkers(data, '(playerOptionsWithMainSource,', ')', False)[1].strip()
            arg = int(arg)

            def _repFun(item):
                url = ''
                if not self.cm.isValidUrl(item):
                    for c in item:
                        url += chr(arg ^ ord(c))
                else:
                    url = item
                printDBG(">>>> " + url)
                return url
            data = self.cm.ph.getDataBeetwenMarkers(data, 'playerOptionsWithMainSource =', '};', False)[1]
            printDBG(data)
            data = byteify(json.loads(data + '}'))
            for item in data['sources']:
                type = item.get('type', '').lower()
                if '/mp4' in type:
                    url = _repFun(item['src'])
                    linksTab.append({'name': 'mp4', 'url': url, 'need_resolve': 0})
                if '/x-mpegurl' in type:
                    url = _repFun(item['src'])
                    linksTab.extend(getDirectM3U8Playlist(url))
            printDBG(data)
        except Exception:
            printExc()
        return linksTab

    def getVideosList(self, url):
        printDBG("getVideosList url[%s]" % url)
        sts, data = self.cm.getPage(url)
        if not sts:
            printDBG("getVideosList except")
            return

        # get pagination HTML part
        nextPageData = CParsingHelper.getDataBeetwenMarkers(data, 'class="pager"', '</div>', False)[1]
        # get Video HTML part
        data = CParsingHelper.getDataBeetwenMarkers(data, '<!-- ************ end user menu ************ -->', '</ul>', False)[1].split('<li>')
        del data[0]

        for videoItemData in data:
            printDBG('videoItemData')
            icon = ''
            duration = ''
            gatunek = ''
            desc = ''
            title = ''
            url = ''

            if 'class="playIcon"' in videoItemData:
                # get icon src
                match = re.search('src="(http://[^"]+?)"', videoItemData)
                if match:
                    icon = match.group(1).replace('&amp;', '&')
                # get duration
                duration = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(videoItemData, '<span class="duration">', '</span>')[1])
                # get gatunek
                gatunek = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(videoItemData, '<a class="gatunek" ', '</a>')[1])
                # get desc
                match = re.search('class="text"[^>]*?>([^<]+?)<', videoItemData)
                if match:
                    desc = match.group(1)
                # get title and url
                match = re.search('<a href="([^"]+?)" class="title"[^>]*?>([^<]+?)</a>', videoItemData)
                if match:
                    url = self.MAIN_URL + match.group(1)
                    title = match.group(2)
                    params = {'good_for_fav': True, 'url': url, 'title': title, 'icon': icon, 'desc': ' | '.join([duration, gatunek]) + '[/br]' + desc}
                    self.addVideo(params)

        # check next page
        nextPageUrl = ''
        match = re.search('href="([^"]+?)" class="nextPage"', nextPageData)
        if match:
            nextPageUrl = match.group(1)
        else:
            match = re.search('href="([^"]+?)" class="lastPage"', nextPageData)
            if match:
                nextPageUrl = match.group(1)

        if '' != nextPageUrl:
            params = {'name': 'sub-category', 'page': self.MAIN_URL + nextPageUrl.replace('&amp;', '&'), 'title': 'Następna strona'}
            self.addDir(params)
    # end getVideosList

    def getFavouriteData(self, cItem):
        printDBG('getFavouriteData')
        return json.dumps(cItem)

    def getLinksForFavourite(self, fav_data):
        printDBG('getLinksForFavourite')
        links = []
        try:
            cItem = byteify(json.loads(fav_data))
            links = self.getLinksForVideo(cItem)
        except Exception:
            printExc()
        return links

    def setInitListFromFavouriteItem(self, fav_data):
        printDBG('setInitListFromFavouriteItem')
        try:
            params = byteify(json.loads(fav_data))
        except Exception:
            params = {}
            printExc()
        self.addDir(params)
        return True

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        self.getVideosList(self.SEARCH_URL + urllib.quote_plus(searchPattern))

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')
        page = self.currItem.get("page", '')

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})
    #WSZYSTKIE
        elif category == 'list_all':
            self.getVideosList(self.currItem['url'])
    #KATEGORIE
        elif category == 'list_cats':
            self.getMainCategory()
    #SUB-KATEGORIE
        elif name == 'main-category':
            self.getSubCategory(page)
        elif name == 'sub-category':
            self.getVideosList(page)
    #SEARCH
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category'})
            self.listSearchResult(cItem, searchPattern, searchType)
    #HISTORIA SEARCH
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _("Type: "))
    #WRONG WAY
        else:
            printDBG('handleService WRONG WAY')


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Ninateka(), True, [])
