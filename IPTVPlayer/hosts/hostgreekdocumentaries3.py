# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem, RetHost, CUrlItem, ArticleContent
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetLogoDir
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
    return 'http://greekdocumentaries2.blogspot.com/'

class GreekDocumentaries3(CBaseHostClass):
    HEADER = {'User-Agent': 'Mozilla/5.0', 'Accept': 'text/html'}
    AJAX_HEADER = dict(HEADER)
    AJAX_HEADER.update( {'X-Requested-With': 'XMLHttpRequest'} )
    
    MAIN_URL      = 'http://greekdocumentaries2.blogspot.com/'
    SEARCH_URL    = MAIN_URL + '/search?sitesearch=http%3A%2F%2Fjohny-jossbanget.blogspot.com&q='
    DEFAULT_ICON  = "http://3.bp.blogspot.com/-s80VMsgUq0w/VsYj0rd4nrI/AAAAAAAAAAw/y-ix9jhy1Gg/s1600-r/%25CF%2586%25CE%25BF%25CF%2584%25CE%25BF%2Bblog%2BHeader.png"
    
    MAIN_CAT_TAB = [{'category':'list_items', 'title': _('Recent'),      'url':MAIN_URL,  'icon':DEFAULT_ICON},
                    {'category':'list_items', 'title': _('Recommended'),  'url':MAIN_URL + 'search/label/%CE%A0%CE%A1%CE%9F%CE%A4%CE%95%CE%99%CE%9D%CE%9F%CE%9C%CE%95%CE%9D%CE%91',  'icon':DEFAULT_ICON},
                    {'category':'list_items', 'title': _('TV series'),   'url':MAIN_URL + 'search/label/TV-Series', 'icon':DEFAULT_ICON},
                    {'category':'categories', 'title': _('Categories'),    'url':MAIN_URL,  'icon':DEFAULT_ICON, 'filter':'categories'},
                    {'category':'categories', 'title': _('History'),      'url':MAIN_URL,  'icon':DEFAULT_ICON, 'filter':'history'},
                    {'category':'search',          'title': _('Search'), 'search_item':True, 'icon':DEFAULT_ICON},
                    {'category':'search_history',  'title': _('Search history'),             'icon':DEFAULT_ICON} ]
 
    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'  GreekDocumentaries3.tv', 'cookie':'GreekDocumentaries3tv.cookie'})
        self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.cacheFilters = {}
        self.cacheLinks = {}
        
    def _getFullUrl(self, url):
        if url.startswith('//'):
            url = 'http:' + url
        else:
            if 0 < len(url) and not url.startswith('http'):
                url =  self.MAIN_URL + url
            if not self.MAIN_URL.startswith('https://'):
                url = url.replace('https://', 'http://')
                
        url = self.cleanHtmlStr(url)
        url = self.replacewhitespace(url)

        return url
        
    def cleanHtmlStr(self, data):
        data = data.replace('&nbsp;', ' ')
        data = data.replace('&nbsp', ' ')
        return CBaseHostClass.cleanHtmlStr(data)
        
    def replacewhitespace(self, data):
        data = data.replace(' ', '%20')
        return CBaseHostClass.cleanHtmlStr(data)

    def listsTab(self, tab, cItem, type='dir'):
        printDBG("GreekDocumentaries3.listsTab")
        for item in tab:
            params = dict(cItem)
            params.update(item)
            params['name']  = 'category'
            if type == 'dir':
                self.addDir(params)
            else: self.addVideo(params)
            
    def fillCategories(self):
        printDBG("GreekDocumentaries3.fillCategories")
        self.cacheFilters = {}
        sts, data = self.cm.getPage(self.MAIN_URL)
        if not sts: return
        
        for cat in  [('categories', 'ΚΑΤΗΓΟΡΙΕΣ', '</ul>'), \
                     ('history', ">TV-Series</a></li>", '>Follow Us<')]:
            self.cacheFilters[cat[0]] = [] 
            tmp = self.cm.ph.getDataBeetwenMarkers(data, cat[1], cat[2], False)[1]
            # printDBG('=============================================================')
            # printDBG(tmp)
            # printDBG('=============================================================')
            tmp = re.compile('''<a[^>]+?href=['"]([^'^"]+?)['"][^>]*?>([^<]+?)<''').findall(tmp)
            for item in tmp:
                self.cacheFilters[cat[0]].append({'title':self.cleanHtmlStr(item[1]), 'url':item[0]})
        
    def listCategories(self, cItem, nextCategory):
        printDBG("GreekDocumentaries3.listCategories")
        filter = cItem.get('filter', '')
        tab = self.cacheFilters.get(filter, [])
        if 0 == len(tab):
            self.fillCategories()
        tab = self.cacheFilters.get(filter, [])
            
        cItem = dict(cItem)
        cItem['category'] = nextCategory
        self.listsTab(tab, cItem)
            
    def listItems(self, cItem, nextCategory='explore_item'):
        printDBG("GreekDocumentaries3.listItems")
        page = cItem.get('page', 1)
        url = cItem['url'] 
        
        if 'url_suffix' in cItem:
            url += cItem['url_suffix']
        
        sts, data = self.cm.getPage(url) #, {'header':self.AJAX_HEADER}
        if not sts: return
        
        nextPageUrl = self.cm.ph.getDataBeetwenMarkers(data, "<span id='blog-pager-older-link'>", '</span>', False)[1]
        nextPageUrl = self.cm.ph.getSearchGroups(nextPageUrl, '<a[^<]+?href=\'([^"]+?)\'')[0]
        
        m1 = "<div class='post bar hentry'>"
        data = self.cm.ph.getDataBeetwenMarkers(data, m1, "<div class='blog-pager'", False)[1]
        data = data.split(m1)
        for item in data:
            tmp   = self.cm.ph.getSearchGroups(item, '''<a[^>]+?href=['"]([^'^"]+?)['"][^>]*?>([^<]+?)<''', 2)
            url   = self._getFullUrl( tmp[0] )
            title = self.cleanHtmlStr( tmp[1] )
            icon  = self._getFullUrl( self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''')[0] )
            desc  = self.cleanHtmlStr(item.split('<br />\n<br />')[0])
            if url.startswith('http'):
                params = dict(cItem)
                params.update({'title':title, 'url':url, 'icon':icon, 'desc':desc})
                params['category'] = nextCategory
                self.addDir(params)
        if nextPageUrl != '':
            params = dict(cItem)
            params.update({'title':_('Next page'), 'page':cItem.get('page', 1)+1, 'url':self._getFullUrl(nextPageUrl)})
            self.addDir(params)
            
    def exploreItem(self, cItem):
        printDBG("GreekDocumentaries3.exploreItem")
        sts, data = self.cm.getPage(cItem['url'])
        if not sts: return
        
        data = data.split('</button>')
        
        # trailer
        if 2 == len(data):
            tmp = self.cm.ph.getDataBeetwenMarkers(data[0], '<iframe', 'Watch Trailer', True)[1]
            videoUrl = self.cm.ph.getSearchGroups(tmp, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0]
            videoUrl = self._getFullUrl(videoUrl)
            if videoUrl.startswith('http'):
                params = dict(cItem)
                params.update({'title':_('Watch Trailer'), 'url':videoUrl})
                self.addVideo(params)
            del data[0]
        data = data[0]
        
        added = False 
        for m in [('<span style="color: ', '</iframe>', False, True),\
                  ('</iframe>', '<b>', True, True),\
                  ('<iframe ', '</iframe>', False, False)]:
                  
            #"<div style='clear: both;'>"
            if 1 == m[3]:
                idx = data.find('Γλώσσα:')
            else: idx = -1
            if idx > -1:
                tmp = data[idx:]
            else:
                tmp = data
                    
            if 0 == m[2]:
                tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, m[0], m[1])
            else:
                tmp = self.cm.ph.rgetAllItemsBeetwenMarkers(tmp, m[0], m[1])
            
            #printDBG('=============================================================')
            #printDBG(tmp)
            #printDBG('=============================================================')
            
            for item in tmp:
                title = self.cleanHtmlStr(self.cleanHtmlStr(item).replace('\r', ' ').replace('\n', ' '))
                idx = title.find('Επεισόδιο')
                if idx > -1:
                    title = title[idx:]
                if title == "": title = cItem['title']
                videoUrl = self.cm.ph.getSearchGroups(item, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0]
                videoUrl = self._getFullUrl(videoUrl)
                if not videoUrl.startswith('http'): continue
                params = dict(cItem)
                params.update({'title':title, 'url':videoUrl})
                self.addVideo(params)
                added = True
            if added:
                break
    
    def getLinksForVideo(self, cItem):
        printDBG("GreekDocumentaries3.getLinksForVideo [%s]" % cItem)
        urlTab = [{'name':'', 'url':cItem['url'], 'need_resolve':1}]
        return urlTab
        
    def getVideoLinks(self, videoUrl):
        printDBG("GreekDocumentaries3.getVideoLinks [%s]" % videoUrl)
        urlTab = []
        if videoUrl.startswith('http'):
            urlTab = self.up.getVideoLinkExt(videoUrl)
        return urlTab
        
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("GreekDocumentaries3.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.SEARCH_URL + urllib.quote(searchPattern)
        self.listItems(cItem)

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
        elif category == 'categories':
            self.listCategories(self.currItem, 'list_items')
        elif category == 'list_items':
                self.listItems(self.currItem)
    #EXPLORE ITEM
        elif category == 'explore_item':
            self.exploreItem(self.currItem)
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
        # for now we must disable favourites due to problem with links extraction for types other than movie
        CHostBase.__init__(self, GreekDocumentaries3(), True, favouriteTypes=[]) #, [CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO])

    def getLogoPath(self):
        return RetHost(RetHost.OK, value = [GetLogoDir('greekdocumentaries3logo.png')])
    
    def getLinksForVideo(self, Index = 0, selItem = None):
        retCode = RetHost.ERROR
        retlist = []
        if not self.isValidIndex(Index): return RetHost(retCode, value=retlist)
        
        urlList = self.host.getLinksForVideo(self.host.currList[Index])
        for item in urlList:
            retlist.append(CUrlItem(item["name"], item["url"], item['need_resolve']))

        return RetHost(RetHost.OK, value = retlist)
    # end getLinksForVideo
    
    def getResolvedURL(self, url):
        # resolve url to get direct url to video file
        retlist = []
        urlList = self.host.getVideoLinks(url)
        for item in urlList:
            need_resolve = 0
            retlist.append(CUrlItem(item["name"], item["url"], need_resolve))

        return RetHost(RetHost.OK, value = retlist)
        
    #def getArticleContent(self, Index = 0):
    #    retCode = RetHost.ERROR
    #    retlist = []
    #    if not self.isValidIndex(Index): return RetHost(retCode, value=retlist)
    #
    #    hList = self.host.getArticleContent(self.host.currList[Index])
    #    for item in hList:
    #        title      = item.get('title', '')
    #        text       = item.get('text', '')
    #        images     = item.get("images", [])
    #        othersInfo = item.get('other_info', '')
    #        retlist.append( ArticleContent(title = title, text = text, images =  images, richDescParams = othersInfo) )
    #    return RetHost(RetHost.OK, value = retlist)
    
    def converItem(self, cItem):
        hostList = []
        searchTypesOptions = [] # ustawione alfabetycznie
        #searchTypesOptions.append((_("Movies"),   "movie"))
        #searchTypesOptions.append((_("TV Shows"), "tv_shows"))
        
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
