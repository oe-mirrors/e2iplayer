# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem, RetHost, CUrlItem
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetLogoDir, byteify
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib
try:    import json
except Exception: import simplejson as json
###################################################


def gettytul():
    return 'http://filmydokumentalne.eu/'

class FilmyDokumentalneEU(CBaseHostClass):
    HTTP_HEADER = {'User-Agent': 'Mozilla/5.0', 'Accept': 'text/html'}
    MAIN_URL = 'http://www.filmydokumentalne.eu/'
    DEFAULT_ICON = 'http://www.filmydokumentalne.eu/wp-content/themes/filmy/images/b_logo.png'
    MAIN_CAT_TAB = [{'category':'list_items',      'title':'Główna',    'url':MAIN_URL,             'icon':DEFAULT_ICON},
                    {'category':'list_items',      'title':'Polecane',  'url':MAIN_URL+'polecane/', 'icon':DEFAULT_ICON},
                    {'category':'list_cats',       'title':'Kanały',    'key':'kanaly',             'icon':DEFAULT_ICON},
                    {'category':'list_cats',       'title':'Kategorie', 'key':'kategorie',          'icon':DEFAULT_ICON},
                    {'category':'list_cats',       'title':'Serwery',   'key':'serwery',            'icon':DEFAULT_ICON},
                    {'category':'list_cats',       'title':'Archiwum',  'key':'archiwum',           'icon':DEFAULT_ICON},
                    {'category':'search',          'title': _('Search'), 'search_item':True, 'icon':DEFAULT_ICON},
                    {'category':'search_history',  'title': _('Search history'),             'icon':DEFAULT_ICON} ]
    
    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'filmydokumentalne.eu', 'cookie':'filmydokumentalne.eu.cookie'})
        self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.cacheCats = {}
        
    def _getFullUrl(self, url, api=True):
        baseUrl = self.MAIN_URL
        if 0 < len(url):
            if url.startswith('//'):
                url = 'http:' + url
            elif not url.startswith('http'):
                url =  baseUrl + url
        if not baseUrl.startswith('https://'):
            url = url.replace('https://', 'http://')
        return url
        
    def cleanHtmlStr(self, data):
        data = data.replace('&nbsp;', ' ')
        data = data.replace('&nbsp', ' ')
        return CBaseHostClass.cleanHtmlStr(data)

    def listsTab(self, tab, cItem, type='dir'):
        printDBG("FilmyDokumentalneEU.listsTab")
        for item in tab:
            params = dict(cItem)
            params.update(item)
            params['name']  = 'category'
            if type == 'dir':
                self.addDir(params)
            else: self.addVideo(params)
            
    def fillCats(self):
        printDBG("FilmyDokumentalneEU.fillCats")
        self.cacheCats = {}
        sts, data = self.cm.getPage(self.MAIN_URL)
        if not sts: return
        archData = self.cm.ph.getDataBeetwenMarkers(data, 'Archiwum', 'Strony')[1]
        data = self.cm.ph.getDataBeetwenMarkers(data, '/kanaly/"', 'Archiwum')[1]
        for cat in ['kanaly', 'kategorie', 'serwery']:
            tmp = re.compile('href="([^"]+?/%s/[^"]+?)"[^>]*?>([^<]+?)<''' % cat).findall(data)
            self.cacheCats[cat] = []
            for item in tmp:
                self.cacheCats[cat].append({'url':item[0], 'title':item[1]})
        cat = 'archiwum'
        self.cacheCats[cat] = []
        tmp = re.compile('''href=['"]([^"^']+?)['"][^>]*?>([^<]+?)<''').findall(archData)
        for item in tmp:
            self.cacheCats[cat].append({'url':item[0], 'title':item[1]})
            
    def listCategories(self, cItem, category):
        printDBG("FilmyDokumentalneEU.listCategories")
        key = cItem['key']
        tab = self.cacheCats.get(key, [])
        if 0 == len(tab):
            self.fillCats()
            tab = self.cacheCats.get(key, [])
        
        for item in tab:
            params = dict(cItem)
            params.update({'category':category, 'url':item['url'], 'title':item['title']})
            self.addDir(params)
    
    def listItems(self, cItem):
        printDBG("FilmyDokumentalneEU.listItems")
        
        page = cItem.get('page', 1)
        url = cItem['url'] + '?json=1&page=%d' % page
        sts, data = self.cm.getPage(url)
        if not sts: return
        
        nextPage = False
        try:
            data = byteify(json.loads(data))
            if page < data.get('pages', 0):
                nextPage = True
            else: nextPage = False
            for item in data['posts']:
                url = item['url']
                title = self.cleanHtmlStr(item['title'])
                desc = self.cleanHtmlStr(item.get('excerpt', ''))
                icon = item.get('thumbnail', '')
                if '' == icon: icon = self.DEFAULT_ICON
                params = dict(cItem)
                params.update({ 'url':url, 'title':title, 'icon':icon, 'desc':desc})
                self.addVideo(params)
        except Exception:
            printExc()
            
        if nextPage:
            params = dict(cItem)
            params.update({'title':_("Next page"), 'page':page+1})
            self.addDir(params)
    
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("FilmyDokumentalneEU.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        url = self.MAIN_URL + '?s=' + urllib.quote(searchPattern)
        sts, data = self.cm.getPage(url)
        if not sts: return
        #data = self.cm.ph.getDataBeetwenMarkers(data, 'Episodes', '</div>')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div id="news">', '</div>')
        for item in data:
            url   = self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0]
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h1>', '</h1>')[1])
            desc  = self.cleanHtmlStr(item.split('</h1>')[-1])
            params = dict(cItem)
            params.update({'url':url, 'title':title, 'desc':desc})
            self.addVideo(params)
    
    def getLinksForVideo(self, cItem):
        printDBG("FilmyDokumentalneEU.getLinksForVideo [%s]" % cItem)
        urlTab = []
        
        url = cItem['url'] 
        if '?' in url: url += '&json=1'
        else: url += '?json=1'
        sts, data = self.cm.getPage(url)
        if not sts: return []
        try:
            data = byteify(json.loads(data))['post']['content']
            videoUrl = self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^'^"]+?)['"]''')[0]
            tmpTab = self.up.getVideoLinkExt(videoUrl)
            for item in tmpTab:
                item['need_resolve'] = 0
                urlTab.append(item)
        except Exception:
            printExc()
        return urlTab
        
    def getFavouriteData(self, cItem):
        return cItem['url']
        
    def getLinksForFavourite(self, fav_data):
        return self.getLinksForVideo({'url':fav_data})
        
    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('handleService start')
        
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name     = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode     = self.currItem.get("mode", '')
        
        printDBG( "handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category) )
        self.currList = []
        
    #MAIN MENU
        if name == None:
            self.listsTab(self.MAIN_CAT_TAB, {'name':'category'})
        elif category == 'list_cats':
            self.listCategories(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem)
    #SEARCH
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item':False, 'name':'category'}) 
            self.listSearchResult(cItem, searchPattern, searchType)
    #HISTORIA SEARCH
        elif category == "search_history":
            self.listsHistory({'name':'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()
        
        CBaseHostClass.endHandleService(self, index, refresh)
class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, FilmyDokumentalneEU(), True, [CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO])

    def getLogoPath(self):
        return RetHost(RetHost.OK, value = [GetLogoDir('filmydokumentalneeulogo.png')])
    
    def getLinksForVideo(self, Index = 0, selItem = None):
        retCode = RetHost.ERROR
        retlist = []
        if not self.isValidIndex(Index): return RetHost(retCode, value=retlist)
        
        urlList = self.host.getLinksForVideo(self.host.currList[Index])
        for item in urlList:
            retlist.append(CUrlItem(item["name"], item["url"], item['need_resolve']))

        return RetHost(RetHost.OK, value = retlist)
    # end getLinksForVideo
    
    def converItem(self, cItem):
        hostList = []
        searchTypesOptions = [] # ustawione alfabetycznie
        
        hostLinks = []
        type = CDisplayListItem.TYPE_UNKNOWN
        possibleTypesOfSearch = None

        if 'category' == cItem['type']:
            if cItem.get('search_item', False):
                type = CDisplayListItem.TYPE_SEARCH
                possibleTypesOfSearch = searchTypesOptions
            else:
                type = CDisplayListItem.TYPE_CATEGORY
        elif cItem['type'] == 'video':
            type = CDisplayListItem.TYPE_VIDEO
        elif 'more' == cItem['type']:
            type = CDisplayListItem.TYPE_MORE
        elif 'audio' == cItem['type']:
            type = CDisplayListItem.TYPE_AUDIO
            
        if type in [CDisplayListItem.TYPE_AUDIO, CDisplayListItem.TYPE_VIDEO]:
            url = cItem.get('url', '')
            if '' != url:
                hostLinks.append(CUrlItem("Link", url, 1))
            
        title       =  cItem.get('title', '')
        description =  cItem.get('desc', '')
        icon        =  cItem.get('icon', '')
        
        return CDisplayListItem(name = title,
                                    description = description,
                                    type = type,
                                    urlItems = hostLinks,
                                    urlSeparateRequest = 1,
                                    iconimage = icon,
                                    possibleTypesOfSearch = possibleTypesOfSearch)
    # end converItem

    def getSearchItemInx(self):
        try:
            list = self.host.getCurrList()
            for i in range( len(list) ):
                if list[i]['category'] == 'search':
                    return i
        except Exception:
            printDBG('getSearchItemInx EXCEPTION')
            return -1

    def setSearchPattern(self):
        try:
            list = self.host.getCurrList()
            if 'history' == list[self.currIndex]['name']:
                pattern = list[self.currIndex]['title']
                search_type = list[self.currIndex]['search_type']
                self.host.history.addHistoryItem( pattern, search_type)
                self.searchPattern = pattern
                self.searchType = search_type
        except Exception:
            printDBG('setSearchPattern EXCEPTION')
            self.searchPattern = ''
            self.searchType = ''
        return
