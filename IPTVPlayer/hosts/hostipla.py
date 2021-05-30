# -*- coding: utf-8 -*-

####################################################################
# IPLA privacy policy
# Pobieranie i udostępnianie danych ze źródła ipla przez
# podmioty nieuprawnione grozi sankcjami karnymi na
# podstawie obowiązujących przepisów karnych (grzywna,
# kara ograniczenia wolności albo kara pozbawienia wolności)
# oraz konsekwencjami przewidzianymi w przepisach prawa
# cywilnego (odszkodowanie w wysokości zasądzonej przez sąd).
# Zabronione jest pobieranie danych i udostępniania ich na
# urządzeniach lub aplikacjach innych niż przygotowane i
# wspierane oficjalnie przez Redefine Sp. z o.o.
####################################################################

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem, RetHost, CUrlItem
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, CSelOneLink, GetLogoDir, byteify
from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.utils import clean_html
###################################################

###################################################
# FOREIGN import
###################################################
# from xml.etree import cElementTree - I would not recommend this XML parser or any other from python
# XML will be parser using regular expressions due to problem with memory leak, if we use
# cElementTree event if memory is free using clear method and removing instances by del,
# the memory using still grows with each parsing, probably due to fragmentation of memory.
# The XML is devil's invention :)

from Components.config import config, ConfigYesNo, ConfigSelection, getConfigListEntry
from time import time
from os import path as os_path
import urllib
import re

try:
    import json
except Exception:
    import simplejson as json
###################################################


###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.iplacachexml = ConfigSelection(default="12", choices=[("0", "nigdy"), ("6", "przez 6 godzin"), ("12", "przez 12 godzin"), ("24", "przez dzień")])
config.plugins.iptvplayer.iplaDefaultformat = ConfigSelection(default="1900", choices=[("200", "bitrate: 200"), ("400", "bitrate: 400"), ("900", "bitrate: 900"), ("1900", "bitrate: 1900")])
config.plugins.iptvplayer.iplaUseDF = ConfigYesNo(default=True)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry("Używaj danych z pamięci podręcznej:", config.plugins.iptvplayer.iplacachexml))
    optionList.append(getConfigListEntry("Domyślny format video:", config.plugins.iptvplayer.iplaDefaultformat))
    optionList.append(getConfigListEntry("Używaj domyślnego format video:", config.plugins.iptvplayer.iplaUseDF))
    return optionList
###################################################


def gettytul():
    return 'https://ipla.tv/'


class Ipla(CBaseHostClass):
    HOST = 'mipla/23'
    IDENTITY = 'ver=600&login=common_user&cuid=-11033141'
    MAIN_URL = 'http://getmedia.redefine.pl'
    CAT_URL = MAIN_URL + '/r/l_x_35_ipla/categories/list/?' + IDENTITY
    MOV_URL = MAIN_URL + '/action/2.0/vod/list/?' + IDENTITY + '&category='
    SEARCH_URL = MAIN_URL + '/vods/search/?vod_limit=150&' + IDENTITY + '&page=0&keywords='

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'ipla'})
        self.categoryXMLTree = None
        self.cacheFilePath = os_path.join(config.plugins.iptvplayer.SciezkaCache.value, "iplaxml.cache")
        self.cm.HEADER = {'User-Agent': self.HOST, 'DNT': '1', 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate'}

    def getStr(self, v, default=''):
        if None == v:
            return default
        elif type(v) == type(u''):
            return v.encode('utf-8')
        elif type(v) == type(''):
            return v

    def __getAttribs(self, data):
        re_compile = re.compile('([^= ]+?)="([^"]+?)"')
        item = {}
        attribs = re_compile.findall(data)
        for attrib in attribs:
            item[attrib[0]] = attrib[1]
        return item

    def getVideosList(self, url):
        printDBG("Ipla.getVideosList url[%s]" % url)

        sts, videosXMLTree = self.cm.getPage(url, {'host': Ipla.HOST})
        if sts:
            videosXMLTree = self.getStr(videosXMLTree).split('</vod>')
            del videosXMLTree[-1]
            re_compile_vod = re.compile('<vod ([^>]+?)>')
            re_compile_thumbs = re.compile('<thumb ([^>]+?)>')
            try:
                vodList = []
                for vod in videosXMLTree:
                    try:
                        val = re_compile_vod.search(vod)
                        if not val:
                            continue
                        val = self.__getAttribs(val.group(1))
                        title = val.get('title', '')
                        plot = val.get('descr', '')
                        icon = val.get('thumbnail', '')
                        try:
                            thumbs = re_compile_thumbs.findall(vod)
                            thumbSizePrev = 9999
                            for thumb in thumbs:
                                attrib = self.__getAttribs(thumb)
                                thumbSize = int(attrib['size'].split('x')[0])
                                if thumbSizePrev > thumbSize:
                                    thumbSizePrev = thumbSize
                                    icon = attrib['url']
                        except Exception:
                            printExc()
                        urls = self._getVideoUrls(vod)
                        sortNum = self.cm.ph.getSearchGroups(title, '''odcinek\s*?([0-9]+?)(?:^0-9|$)''', 1, True)[0]
                        if sortNum != '':
                            sortNum = int(sortNum)
                        params = {'category': 'video', 'sort_num': sortNum, 'title': self.cleanHtmlStr(title), 'plot': plot, 'icon': icon, 'urls': urls, 'fav_item': {'url': url, 'vod_id': val.get('id', '')}}
                        vodList.append(params)
                    except Exception:
                        printExc()
                vodList.sort(key=lambda item: item['sort_num'])
                for params in vodList:
                    self.addVideo(params)
            except Exception:
                printExc()
    # end getVideosList

    def _getVideoUrls(self, vodData):
        urls = []
        re_compile_srcreq = re.compile('<srcreq ([^>]+?)>')
        max_bitrate = int(config.plugins.iptvplayer.iplaDefaultformat.value)

        def __getLinkQuality(itemLink):
            return int(itemLink['bitrate'])
        try:
            links = re_compile_srcreq.findall(vodData)
            for link in links:
                attrib = self.__getAttribs(link)
                drm = attrib['drmtype']
                if drm == '0':
                    if config.plugins.iptvplayer.ZablokujWMV.value and attrib['format'] == '0':
                        continue
                    name = "Jakość: %s\t format: %s\t  bitrate: %s" % (attrib['quality'], attrib['format'], attrib['bitrate'])
                    urls.append({'name': name, 'url': attrib['url'], 'bitrate': attrib['bitrate']})
        except Exception:
            printExc()
        urls = CSelOneLink(urls, __getLinkQuality, max_bitrate).getSortedLinks()
        if config.plugins.iptvplayer.iplaUseDF.value:
            urls = [urls[0]]
        return urls

    def __writeCategoryCache(self, data):
        printDBG("__writeCategoryCache ")
        try:
            if "0" == config.plugins.iptvplayer.iplacachexml.value:
                return
            data = str({"timestamp": int(time()), "data": data})
            with open(self.cacheFilePath, 'w') as f:
                f.write(str(data))
        except Exception:
            printExc()

    def __readCategoryCache(self):
        printDBG("__readCategoryCache ")
        try:
            data = None
            if "0" == config.plugins.iptvplayer.iplacachexml.value:
                return
            from ast import literal_eval
            with open(self.cacheFilePath, 'r') as f:
                data = f.read()
            data = literal_eval(data)
            currTimestamp = int(time())
            saveTimestamp = data["timestamp"]

            if (currTimestamp - saveTimestamp) / 3600 < int(config.plugins.iptvplayer.iplacachexml.value):
                data = data["data"]
                printDBG("__readCategoryCache data from cache valid")
            else:
                data = None
        except Exception:
            printExc()
            data = None
        return data

    def getCatXmlTree(self, refresh=False):
        printDBG("setCatXmlTree refresh[%r]" % refresh)

        def _fromUrl():
            sts, data = self.cm.getPage(Ipla.CAT_URL, {'host': Ipla.HOST})
            if not sts:
                data = ''
            return data

        if None == self.categoryXMLTree or refresh:
            try:
                bFromCache = True
                data = None
                if not refresh:
                    data = self.__readCategoryCache()
                if None == data:
                    bFromCache = False
                    data = _fromUrl()
                self.categoryXMLTree = self.__simpleCategoryParser(data)
                if bFromCache and 100 > len(self.categoryXMLTree):
                    data = _fromUrl()
                    self.categoryXMLTree = self.__simpleCategoryParser(data)
                    bFromCache = False
                if not bFromCache:
                    self.__writeCategoryCache(data)
            except Exception:
                printExc()
                self.categoryXMLTree = None
        return self.categoryXMLTree

    def __simpleCategoryParser(self, data):
        printDBG("__simpleCategoryParser start")
        data = re.compile('<cat ([^>]+?)>').findall(data)
        printDBG("__simpleCategoryParser step 1 finished")
        for idx in range(len(data)):
            data[idx] = self.__getAttribs(data[idx])
        printDBG("__simpleCategoryParser step 2 finished")
        return data

    def getCategories(self, parentCatId, refresh):
        printDBG("getCategories parentCatId[%s]" % parentCatId)
        xmlTree = self.getCatXmlTree(refresh)
        if xmlTree:
            try:
                #cats = xmlTree.findall("cat")
                cats = xmlTree
                listVideo = False
                numOfSubCat = 0
                for cat in cats:
                    #val = cat.attrib
                    val = cat
                    try:
                        listVideo = True
                        pid = self.getStr(val.get('pid', ''), '')
                        catId = self.getStr(val.get('id', ''), '')
                        if '' in [pid, catId]:
                            continue
                        if pid == parentCatId:
                            numOfSubCat += 1
                            title = self.getStr(val.get('title', ''), '')
                            plot = self.getStr(val.get('descr', ''), '')
                            icon = self.getStr(val.get('thumbnail', ''), '')
                            #check if this is only link to diffrent category
                            try:
                                link = self.getStr(val.get('action', ''), '')
                                linkMarker = "ipla://cmd-cmd=gotocat&catid="
                                if linkMarker in link:
                                    # if this is only linkt to another category, update category id
                                    catId = link.replace(linkMarker, "")
                            except Exception:
                                pass
                            params = {'category': 'category', 'title': self.cleanHtmlStr(title), 'plot': plot, 'icon': icon, 'catId': catId, 'pCatId': pid}
                            self.addDir(params)
                        #printDBG("||||||||||||||||: %s" %pid)
                    except Exception:
                        printDBG("getCategories except")
                        printExc()
                if listVideo and numOfSubCat < 2:
                    self.getVideosList(Ipla.MOV_URL + parentCatId)
            except Exception:
                printExc()
        return

    def listsMainMenu(self, refresh=False):
        printDBG('listsMainMenu')
        self.getCategories('0', refresh)
        self.addDir({'category': 'Wyszukaj', 'title': 'Wyszukaj'})
        self.addDir({'category': 'search_history', 'title': 'Historia wyszukiwania'})

    def getFavouriteData(self, cItem):
        return json.dumps(cItem['fav_item'])

    def getLinksForFavourite(self, fav_data):
        links = []
        try:
            favItem = byteify(json.loads(fav_data))
            printDBG(favItem)
            sts, data = self.cm.getPage(favItem['url'], {'host': Ipla.HOST})
            if sts:
                sts, data = self.cm.ph.getDataBeetwenReMarkers(data, re.compile('<vod[^>]+?id="%s"[^>]*?>' % favItem['vod_id']), re.compile('</vod>'), False)
                if sts:
                    links = self._getVideoUrls(data)
        except Exception:
            printExc()
        return links

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        if 0 == refresh:
            refresh = False
        else:
            refresh = True

        title = self.currItem.get("title", '')
        category = self.currItem.get("category", None)
        catId = self.currItem.get("catId", '')
        pCatId = self.currItem.get("pCatId", '')
        icon = self.currItem.get("icon", '')
        url = self.currItem.get("url", '')
        plot = self.currItem.get("plot", '')
        printDBG("handleService: |||||||||||||||||||||||||||||||||||| category[%r] " % (category))
        self.currList = []

    #MAIN MENU
        if category == None:
            self.listsMainMenu(refresh)
    #GET SUB CATEGORY
        elif category == 'category':
            self.getCategories(catId, refresh)
    #WYSZUKAJ
        elif category == 'Wyszukaj':
            pattern = urllib.quote_plus(searchPattern)
            self.getVideosList(Ipla.SEARCH_URL + pattern)
    #HISTORIA WYSZUKIWANIA
        elif category == "search_history":
            self.listsHistory()


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Ipla(), True, [CDisplayListItem.TYPE_VIDEO]) # with search history, can generate favorite item

    def getLogoPath(self):
        return RetHost(RetHost.OK, value=[GetLogoDir('iplalogo.png')])

    def converItem(self, cItem):
        searchTypesOptions = [] # ustawione alfabetycznie
        hostLinks = []
        type = CDisplayListItem.TYPE_UNKNOWN
        possibleTypesOfSearch = None

        if cItem['type'] == 'category':
            if cItem['title'] == 'Wyszukaj':
                type = CDisplayListItem.TYPE_SEARCH
                possibleTypesOfSearch = searchTypesOptions
            else:
                type = CDisplayListItem.TYPE_CATEGORY
        elif cItem['type'] == 'video':
            type = CDisplayListItem.TYPE_VIDEO
            urls = cItem.get('urls', [])
            for urlItem in urls:
                hostLinks.append(CUrlItem(urlItem['name'], urlItem['url'], 0))

        title = clean_html(cItem.get('title', ''))
        description = clean_html(cItem.get('plot', ''))
        icon = cItem.get('icon', '')
        hostItem = CDisplayListItem(name=title,
                                    description=description,
                                    type=type,
                                    urlItems=hostLinks,
                                    urlSeparateRequest=0,
                                    iconimage=icon,
                                    possibleTypesOfSearch=possibleTypesOfSearch)
        return hostItem

    def getSearchItemInx(self):
        # Find 'Wyszukaj' item
        try:
            list = self.host.getCurrList()
            for i in range(len(list)):
                if list[i]['category'] == 'Wyszukaj':
                    return i
        except Exception:
            printDBG('getSearchItemInx EXCEPTION')
            return -1

    def setSearchPattern(self):
        try:
            list = self.host.getCurrList()
            if 'history' == list[self.currIndex].get('name'):
                pattern = list[self.currIndex]['title']
                search_type = None
                self.host.history.addHistoryItem(pattern, search_type)
                self.searchPattern = pattern
                self.searchType = search_type
        except Exception:
            printDBG('setSearchPattern EXCEPTION')
            self.searchPattern = ''
            self.searchType = ''
        return
