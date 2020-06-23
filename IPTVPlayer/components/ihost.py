## @file  ihost.py
#

###################################################
# E2 GUI COMMPONENTS 
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, GetIPTVNotify
from Plugins.Extensions.IPTVPlayer.components.asynccall import MainSessionWrapper
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common, CParsingHelper
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import CSearchHistoryHelper, GetCookieDir, printDBG, printExc, GetLogoDir, byteify
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps

from Components.config import config
from skin import parseColor

from urlparse import urljoin

class CUrlItem:
    def __init__(self, name = "", url = "", urlNeedsResolve = 0):
        if isinstance(name, basestring): self.name = name
        else: self.name = str(name)
        
        # used only for TYPE_VIDEO item 
        if isinstance(url, basestring): self.url = url
        else: self.url = str(url)
        
        self.urlNeedsResolve = urlNeedsResolve #  additional request to host is needed to resolv this url (url is not direct link)
## class CDisplayListItem
# define attribiutes for item of diplay list
# communicate display layer with host
#
class CDisplayListItem:
    TYPE_CATEGORY  = "CATEGORY"
    TYPE_VIDEO     = "VIDEO"
    TYPE_AUDIO     = "AUDIO"
    TYPE_SEARCH    = "SEARCH"
    TYPE_ARTICLE   = "ARTICLE"
    TYPE_PICTURE   = "PICTURE"
    TYPE_DATA      = "DATA"
    TYPE_MORE      = "MORE"
    TYPE_MARKER    = "MARKER"
    
    TYPE_SUBTITLE      = "SUBTITLE"
    TYPE_SUB_PROVIDER  = "SUB_PROVIDER"
    TYPE_UNKNOWN       = "UNKNOWN"
    
    def __init__(self, name = "", \
                description = "", \
                type = TYPE_UNKNOWN, \
                urlItems = [], \
                urlSeparateRequest = 0, \
                iconimage = '', \
                possibleTypesOfSearch = None, \
                pinLocked = False, \
                isGoodForFavourites = False, \
                isWatched = False, \
                textColor = '', \
                pinCode = ''):
                
        if isinstance(name, basestring): self.name = name
        else: self.name = str(name)
        
        if isinstance(description, basestring): self.description = description
        else: self.description = str(description)
        
        if isinstance(type, basestring): self.type = type
        else: self.type = str(type)
        
        if isinstance(iconimage, basestring): self.iconimage = iconimage
        else: self.iconimage = str(iconimage)
        
        if pinLocked: self.pinLocked = True
        else: self.pinLocked = False
        
        self.pinCode = str(pinCode)
        
        if isGoodForFavourites: self.isGoodForFavourites = True
        else: self.isGoodForFavourites = False
        
        if isWatched: self.isWatched = True
        else: self.isWatched = False
        
        self.textColor = str(textColor)
        
        # used only for TYPE_VIDEO item
        self.urlItems = urlItems # url to VIDEO
        # links are not available the separate request is needed to get links
        self.urlSeparateRequest = urlSeparateRequest
        # used only for TYPE_SEARCH item
        self.possibleTypesOfSearch = possibleTypesOfSearch
        self.privateData = None
        self.itemIdx = -1
        
    def getDisplayTitle(self):
        if self.isWatched:
            return '*' + self.name
        else:
            return self.name
        
    def getTextColor(self):
        try:
            if self.textColor != '':
                return parseColor(self.textColor).argb()
            if self.isWatched:
                return parseColor(config.plugins.iptvplayer.watched_item_color.value).argb()
        except Exception:
            printExc()
        return None

class ArticleContent:
    VISUALIZER_DEFAULT = 'DEFAULT'
    # Posible args and values for richDescParams:
    RICH_DESC_PARAMS        = ["alternate_title", "original_title", "station", "price", "age_limit", "views", "status", "type", "first_air_date", "last_air_date", "seasons", "episodes", "country", "language", "duration", "quality", "subtitles", "year", "imdb_rating", "tmdb_rating",\
                               "released", "broadcast", "remaining", "rating", "rated", "genre", "genres", "category", "categories", "production", "director", "directors", "writer", "writers", \
                               "creator", "creators", "cast", "actors", "stars", "awards", "budget", "translation",]
    # labels here must be in english language 
    # translation should be done before presentation using "locals" mechanism
    RICH_DESC_LABELS = {"alternate_title":   "Alternate Title:",
                        "original_title":    "Original Title:",
                        "station":           "Station:",
                        "price":             "Price:",
                        "status":            "Status:",
                        "type":              "Type:",
                        "age_limit":         "Age limit:",
                        "first_air_date":    "First air date:",  
                        "last_air_date":     "Last air date:", 
                        "seasons":           "Seasons:",
                        "episodes":          "Episodes:",
                        "quality":           "Quality:",
                        "subtitles":         "Subtitles:",
                        "country":           "Country:", 
                        "language":          "Language",
                        "year":              "Year:", 
                        "released":          "Released:",
                        "broadcast":         "Broadcast:",
                        "remaining":         "Remaining:",
                        "imdb_rating":       "IMDb Rating:",
                        "tmdb_rating":       "TMDb Rating:",
                        "rating":            "Rating:", 
                        "rated":             "Rated:",
                        "duration":          "Duration:", 
                        "genre":             "Genre:", 
                        "genres":            "Genres:", 
                        "category":          "Category:",
                        "categories":        "Categories:",
                        "production":        "Production:",
                        "director":          "Director:",
                        "directors":         "Directors:",
                        "writer":            "Writer:",
                        "writers":           "Writers:",
                        "creator":           "Creator:",
                        "creators":          "Creators:",
                        "cast":              "Cast:",
                        "actors":            "Actors:", 
                        "stars":             "Stars:",
                        "awards":            "Awards:",
                        "views":             "Views:",
                        "budget":            "Budget:",
                        "translation":       "Translation:"
                        }
    def __init__(self, title = '', text = '', images = [], trailers = [], richDescParams = {}, visualizer=None):
        self.title    = title
        self.text     = text
        self.images   = images
        self.trailers = trailers
        self.richDescParams = richDescParams
        if None == visualizer: 
            self.visualizer = ArticleContent.VISUALIZER_DEFAULT
        else:
            self.visualizer = visualizer
        
class CFavItem:
    RESOLVER_DIRECT_LINK = 'DIRECT_LINK'
    RESOLVER_SELF        = 'SELF'
    RESOLVER_URLLPARSER  = 'URLLPARSER'
    TYPE_UNKNOWN = CDisplayListItem.TYPE_UNKNOWN
    def __init__( self, name         = '', \
                  description        = '', \
                  type               = TYPE_UNKNOWN, \
                  iconimage          = '', \
                  data               = '', \
                  resolver           = RESOLVER_SELF ):
        self.name        = name
        self.description = description
        self.type        = type
        self.iconimage   = iconimage 
        self.data        = data
        self.resolver    = resolver
        self.hostName    = ''
        
    def fromDisplayListItem(self, dispItem):
        self.name        = dispItem.name
        self.description = dispItem.description
        self.type        = dispItem.type
        self.iconimage   = dispItem.iconimage
        return self
    
    def setFromDict(self, data):
        for key in data:
            setattr(self, key, data[key])
        return self
        
    def getAsDict(self):
        return vars(self)
        
class CHostsGroupItem:
    def __init__( self, name = '', title = ''):
        self.name = name
        self.title = title
       
class RetHost:
    OK = "OK"
    ERROR = "ERROR"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    def __init__(self, status , value, message = ''):
        self.status = status
        self.value = value  
        self.message = message

## class IHost
# interface base class with method used to
# communicate display layer with host
#
class IHost:

    def isProtectedByPinCode(self):
        return False
    
    # return list of types which can be added as favourite
    def getSupportedFavoritesTypes(self):
        return RetHost(RetHost.NOT_IMPLEMENTED, value = [])
    
    # get favourite item CFavItem for item with given index
    def getFavouriteItem(self, Index=0):
        return RetHost(RetHost.NOT_IMPLEMENTED, value = [])
        
    # similar as getLinksForItem, returns links 
    # for given CFavItem
    def getLinksForFavourite(self, favItem):
        return RetHost(RetHost.NOT_IMPLEMENTED, value = [])
    
    def setInitFavouriteItem(self, favItem):
        return RetHost(RetHost.NOT_IMPLEMENTED, value = [])

    # return firs available list of item category or video or link
    def getInitList(self):
        return RetHost(RetHost.NOT_IMPLEMENTED, value = [])
    
    # return List of item from current List
    # for given Index
    # 1 == refresh - force to read data from 
    #                server if possible 
    # server instead of cache 
    # item - object of CDisplayListItem for selected item
    def getListForItem(self, Index = 0, refresh = 0, item = None):
        return RetHost(RetHost.NOT_IMPLEMENTED, value = [])
        
    # return prev requested List of item 
    # for given Index
    # 1 == refresh - force to read data from 
    #                server if possible
    def getPrevList(self, refresh = 0):
        return RetHost(RetHost.NOT_IMPLEMENTED, value = [])
        
    # return current List
    # for given Index
    # 1 == refresh - force to read data from 
    #                server if possible
    def getCurrentList(self, refresh = 0):
        return RetHost(RetHost.NOT_IMPLEMENTED, value = [])
        
    # return current List
    # for given Index
    def getMoreForItem(self, Index=0):
        return RetHost(RetHost.NOT_IMPLEMENTED, value = [])
        
    def getLinksForVideo(self, Index = 0, item = None):
        return self.getLinksForItem(Index, item)
        
    # return list of links for AUDIO, VIDEO, PICTURE
    # for given Index, 
    # item - object of CDisplayListItem for selected item
    def getLinksForItem(self, Index = 0, item = None):
        return RetHost(RetHost.NOT_IMPLEMENTED, value = [])
        
    def getArticleContent(self, Index = 0):
        return RetHost(RetHost.NOT_IMPLEMENTED, value = [])
        
    # return resolved url
    # for given url
    def getResolvedURL(self, url):
        return RetHost(RetHost.NOT_IMPLEMENTED, value = [])
        
    # return full path to player logo
    def getLogoPath(self):
        return RetHost(RetHost.OK, value = [GetLogoDir(getattr(self, '__module__').split('.')[-1][4:] + 'logo.png')])
        
    def getSearchResults(self, pattern, searchType = None):
        return RetHost(RetHost.NOT_IMPLEMENTED, value = [])

    # !!! NON BLOCKING !!!
    # return list of custom actions 
    # for given Index
    def getCustomActions(self, Index = 0):
        return RetHost(RetHost.NOT_IMPLEMENTED, value = [])

    # !!! NON BLOCKING !!!
    # return list with search suggestions providers
    # for given Index
    def getSuggestionsProvider(self, Index = 0):
        return RetHost(RetHost.NOT_IMPLEMENTED, value = [])

    def performCustomAction(self, privateData):
        return RetHost(RetHost.NOT_IMPLEMENTED, value = [])
        
    def markItemAsViewed(self, Index = 0):
        return RetHost(RetHost.NOT_IMPLEMENTED, value = [])
    
'''
CHostBase implements some typical methods
          from IHost interface
'''
class CHostBase(IHost):
    def __init__( self, host, withSearchHistrory, favouriteTypes=[] ):
        self.host = host
        self.withSearchHistrory = withSearchHistrory
        self.favouriteTypes     = favouriteTypes

        self.currIndex = -1
        self.listOfprevList = [] 
        self.listOfprevItems = [] 
        
        self.searchPattern = ''
        self.searchType = ''
        
    def getSupportedFavoritesTypes(self):
        return RetHost(RetHost.OK, value = self.favouriteTypes)
        
    def isValidIndex(self, Index, validTypes=None):
        listLen = len(self.host.currList)
        if listLen <= Index or Index < 0:
            printDBG( "ERROR isValidIndex - current list is to short len: %d, Index: %d" % (listLen, Index) )
            return False
        if None != validTypes and self.converItem(self.host.currList[Index]).type not in validTypes:
            printDBG( "ERROR isValidIndex - current item has wrong type" )
            return False
        return True
        
    def withArticleContent(self, cItem):
        return False
    
    def getArticleContent(self, Index = 0):
        retCode = RetHost.ERROR
        retlist = []
        if not self.isValidIndex(Index): return RetHost(retCode, value=retlist)
        cItem = self.host.currList[Index]
        
        if not self.withArticleContent(cItem):
            return RetHost(retCode, value=retlist)
        hList = self.host.getArticleContent(cItem)
        if None == hList:
            return RetHost(retCode, value=retlist)
        for item in hList:
            title      = item.get('title', '')
            text       = item.get('text', '')
            images     = item.get("images", [])
            othersInfo = item.get('other_info', '')
            retlist.append( ArticleContent(title = title, text = text, images =  images, richDescParams = othersInfo) )
        if len(hList): retCode = RetHost.OK
        return RetHost(retCode, value = retlist)
    # end getArticleContent
    
    def getLinksForItem(self, Index = 0, selItem = None):
        retCode = RetHost.ERROR
        retlist = []
        if not self.isValidIndex(Index): return RetHost(retCode, value=retlist)
        
        urlList = self.host.getLinksForItem(self.host.currList[Index])
        if isinstance(urlList, list):
            for item in urlList:
                need_resolve = item.get("need_resolve", 0)
                retlist.append(CUrlItem(item["name"], item["url"], need_resolve))

        return RetHost(RetHost.OK, value = retlist)
    # end getLinksForVideo
    
    def getResolvedURL(self, url):
        # resolve url to get direct url to video file
        retlist = []
        urlList = self.host.getVideoLinks(url)
        if isinstance(urlList, list):
            for item in urlList:
                need_resolve = 0
                retlist.append(CUrlItem(item["name"], item["url"], need_resolve))

        return RetHost(RetHost.OK, value = retlist)
    # end getResolvedURL
        
    def getFavouriteItem(self, Index=0):
        retCode = RetHost.ERROR
        retlist = []
        if not self.isValidIndex(Index, self.favouriteTypes): RetHost(retCode, value=retlist)
        
        cItem = self.host.currList[Index]
        data = self.host.getFavouriteData(cItem)
        if None != data:
            favItem = CFavItem(data=data)
            favItem.fromDisplayListItem(self.converItem(cItem))
            
            retlist = [favItem]
            retCode = RetHost.OK

        return RetHost(retCode, value=retlist)
    # end getFavouriteItem
    
    def getLinksForFavourite(self, favItem):
        retlist = []
        urlList = self.host.getLinksForFavourite(favItem.data)
        if isinstance(urlList, list):
            for item in urlList:
                need_resolve = item.get("need_resolve", 0)
                name = self.host.cleanHtmlStr( item["name"] )
                url  = item["url"]
                retlist.append(CUrlItem(name, url, need_resolve))
        return RetHost(RetHost.OK, value = retlist)
        
    def setInitFavouriteItem(self, favItem):
        self.currIndex = -1
        self.listOfprevList = [] 
        self.listOfprevItems = []
        
        self.host.setCurrList([])
        self.host.setCurrItem({})
        
        if self.host.setInitListFromFavouriteItem(favItem.data):
            return RetHost(RetHost.OK, value = None)
        return RetHost(RetHost.ERROR, value = None)
    
    # return firs available list of item category or video or link
    def getInitList(self):
        self.currIndex = -1
        self.listOfprevList = [] 
        self.listOfprevItems = []
        
        self.host.handleService(self.currIndex)
        convList = self.convertList(self.host.getCurrList())
        
        return RetHost(RetHost.OK, value = convList)
    
    def getListForItem(self, Index = 0, refresh = 0, selItem = None):
        self.listOfprevList.append(self.host.getCurrList())
        self.listOfprevItems.append(self.host.getCurrItem())
        
        self.currIndex = Index
        if self.withSearchHistrory:
            self.setSearchPattern()
            try:
                if len(self.searchPattern):
                    sts, prevPattern = CSearchHistoryHelper.loadLastPattern()
                    if sts and prevPattern != self.searchPattern:
                        CSearchHistoryHelper.saveLastPattern(self.searchPattern)
            except Exception:
                printExc()
        
        self.host.handleService(Index, refresh, self.searchPattern, self.searchType)
        convList = self.convertList(self.host.getCurrList())
        
        return RetHost(RetHost.OK, value = convList)

    def getPrevList(self, refresh = 0):
        if(len(self.listOfprevList) > 0):
            hostList = self.listOfprevList.pop()
            hostCurrItem = self.listOfprevItems.pop()
            self.host.setCurrList(hostList)
            self.host.setCurrItem(hostCurrItem)
            
            convList = self.convertList(hostList)
            return RetHost(RetHost.OK, value = convList)
        else:
            return RetHost(RetHost.ERROR, value = [])

    def getCurrentList(self, refresh = 0):
        if refresh == 1:
            self.host.handleService(self.currIndex, refresh, self.searchPattern, self.searchType)
        convList = self.convertList(self.host.getCurrList())
        return RetHost(RetHost.OK, value = convList)
        
    def getMoreForItem(self, Index=0):
        self.host.handleService(Index, 2, self.searchPattern, self.searchType)
        convList = self.convertList(self.host.getCurrList())
        return RetHost(RetHost.OK, value = convList)

    def getSuggestionsProvider(self, Index = 0):
        getProvider = getattr(self.host, "getSuggestionsProvider", None)
        if callable(getProvider):
            val = getProvider(Index)
            return RetHost(RetHost.OK, value = [val])
        return RetHost(RetHost.NOT_IMPLEMENTED, value = [])

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
    
    def convertList(self, cList):
        hostList = []
        for cItem in cList:
            hostItem = self.converItem(cItem)
            if None != hostItem: hostList.append(hostItem)
        return hostList
    # end convertList
    
    def getSearchTypes(self):
        searchTypesOptions = []
        #searchTypesOptions.append((_("Movies"),   "movie"))
        #searchTypesOptions.append((_("TV Shows"), "series"))
        return searchTypesOptions
        
    def getDefaulIcon(self, cItem):
        return self.host.getDefaulIcon(cItem)
        
    def getFullIconUrl(self, url, currUrl=None):
        if currUrl != None: return self.host.getFullIconUrl(url, currUrl)
        else: return self.host.getFullIconUrl(url)
    
    def converItem(self, cItem, needUrlResolve=1, needUrlSeparateRequest=1):
        hostList = []
        hostLinks = []
        type = CDisplayListItem.TYPE_UNKNOWN
        possibleTypesOfSearch = None

        if 'category' == cItem['type']:
            if cItem.get('search_item', False):
                type = CDisplayListItem.TYPE_SEARCH
                possibleTypesOfSearch = self.getSearchTypes()
            else:
                type = CDisplayListItem.TYPE_CATEGORY
        elif cItem['type'] == 'video':
            type = CDisplayListItem.TYPE_VIDEO
        elif 'audio' == cItem['type']:
            type = CDisplayListItem.TYPE_AUDIO
        elif 'picture' == cItem['type']:
            type = CDisplayListItem.TYPE_PICTURE
        elif 'article' == cItem['type']:
            type = CDisplayListItem.TYPE_ARTICLE
        elif 'more' == cItem['type']:
            type = CDisplayListItem.TYPE_MORE
        elif 'marker' == cItem['type']:
            type = CDisplayListItem.TYPE_MARKER
        elif 'data' == cItem['type']:
            type = CDisplayListItem.TYPE_DATA
        
        if type in [CDisplayListItem.TYPE_AUDIO, CDisplayListItem.TYPE_VIDEO, \
                    CDisplayListItem.TYPE_PICTURE, CDisplayListItem.TYPE_ARTICLE, \
                    CDisplayListItem.TYPE_DATA]:
            url = cItem.get('url', '')
            if '' != url: hostLinks.append(CUrlItem("Link", url, needUrlResolve))
            
        title       =  cItem.get('title', '')
        description =  cItem.get('desc', '')
        icon        =  self.getFullIconUrl( cItem.get('icon', '') )
        if icon == '': icon = self.getDefaulIcon(cItem)
        isGoodForFavourites = cItem.get('good_for_fav', False)
        pinLocked = cItem.get('pin_locked', False)
        pinCode   = cItem.get('pin_code', '')
        textColor = cItem.get('text_color', '')
        
        return CDisplayListItem(name = title,
                                    description = description,
                                    type = type,
                                    urlItems = hostLinks,
                                    urlSeparateRequest = needUrlSeparateRequest,
                                    iconimage = icon,
                                    possibleTypesOfSearch = possibleTypesOfSearch,
                                    pinLocked = pinLocked,
                                    isGoodForFavourites = isGoodForFavourites,
                                    textColor = textColor,
                                    pinCode = pinCode)
    # end converItem

    def getSearchResults(self, searchpattern, searchType = None):
        retList = []
        if self.withSearchHistrory:
            self.host.history.addHistoryItem( searchpattern, searchType )

        self.searchPattern = searchpattern
        self.searchType = searchType
        
        # Find 'Wyszukaj' item
        list = self.host.getCurrList()
        
        searchItemIdx = self.getSearchItemInx()
        if searchItemIdx > -1:
            return self.getListForItem( searchItemIdx )
        else:
            return RetHost(RetHost.ERROR, value = [])
            
    # end getSearchResults
    

class CBaseHostClass:
    def __init__(self, params={}):
        self.sessionEx = MainSessionWrapper() 
        self.up = urlparser()
        
        proxyURL = params.get('proxyURL', '')
        useProxy = params.get('useProxy', False)
        self.cm = common(proxyURL, useProxy)

        self.currList = []
        self.currItem = {}
        if '' != params.get('history', ''):
            self.history = CSearchHistoryHelper(params['history'], params.get('history_store_type', False))
        if '' != params.get('cookie', ''):
            self.COOKIE_FILE = GetCookieDir(params['cookie'])
        self.moreMode = False
        
    def informAboutGeoBlockingIfNeeded(self, country, onlyOnce=True):
        try: 
            if onlyOnce and self.isGeoBlockingChecked: return
        except Exception: 
            self.isGeoBlockingChecked = False
        sts, data = self.cm.getPage('https://dcinfos.abtasty.com/geolocAndWeather.php')
        if not sts: 
            return
        try:
            data = json_loads(data)
            mycountry = data.get('country','')
            if mycountry != country:
                if not mycountry:
                    mycountry = '?'
                message = _('%s uses "geo-blocking" measures to prevent you from accessing the services from abroad.\n Host country: %s, your country: %s') 
                GetIPTVNotify().push(message % (self.getMainUrl(), country, mycountry ), 'info', 5)
            self.isGeoBlockingChecked = True
        except Exception: printExc()
    
    def listsTab(self, tab, cItem, type='dir'):
        defaultType = type
        for item in tab:
            params = dict(cItem)
            params.update(item)
            params['name']  = 'category'
            type = item.get('type', defaultType)
            if type == 'dir': self.addDir(params)
            elif type == 'marker': self.addMarker(params)
            else: self.addVideo(params)

    def listSubItems(self, cItem):
        printDBG("CBaseHostClass.listSubItems")
        self.currList = cItem['sub_items']

    def listToDir(self, cList, idx):
        return self.cm.ph.listToDir(cList, idx)
    
    def getMainUrl(self):
        return self.MAIN_URL
    
    def setMainUrl(self, url):
        if self.cm.isValidUrl(url):
            self.MAIN_URL = self.cm.getBaseUrl(url)
            return True
        return False
    
    def getFullUrl(self, url, currUrl=None):
        if currUrl == None or not self.cm.isValidUrl(currUrl):
            try:
                currUrl = self.getMainUrl()
            except Exception:
                currUrl = None
            if currUrl == None or not self.cm.isValidUrl(currUrl):
                currUrl = 'http://fake/'
        return self.cm.getFullUrl(url, currUrl)

    def getFullIconUrl(self, url, currUrl=None):
        if currUrl != None: return self.getFullUrl(url, currUrl)
        else: return self.getFullUrl(url)
        
    def getDefaulIcon(self, cItem=None):
        try:
            return self.DEFAULT_ICON_URL
        except Exception:
            pass
        return ''

    @staticmethod 
    def cleanHtmlStr(str):
        return CParsingHelper.cleanHtmlStr(str)

    @staticmethod 
    def getStr(v, default=''):
        if type(v) == type(u''): return v.encode('utf-8')
        elif type(v) == type(''):  return v
        return default
            
    def getCurrList(self):
        return self.currList

    def setCurrList(self, list):
        self.currList = list
        
    def getCurrItem(self):
        return self.currItem

    def setCurrItem(self, item):
        self.currItem = item

    def addDir(self, params):
        params['type'] = 'category'
        self.currList.append(params)
        return
        
    def addMore(self, params):
        params['type'] = 'more'
        self.currList.append(params)
        return
        
    def addVideo(self, params):
        params['type'] = 'video'
        self.currList.append(params)
        return
        
    def addAudio(self, params):
        params['type'] = 'audio'
        self.currList.append(params)
        return
    
    def addPicture(self, params):
        params['type'] = 'picture'
        self.currList.append(params)
        return
        
    def addData(self, params):
        params['type'] = 'data'
        self.currList.append(params)
        return
  
    def addArticle(self, params):
        params['type'] = 'article'
        self.currList.append(params)
        return
    
    def addMarker(self, params):
        params['type'] = 'marker'
        self.currList.append(params)
        return
    
    def listsHistory(self, baseItem={'name': 'history', 'category': 'Wyszukaj'}, desc_key='plot', desc_base=(_("Type: ")) ):
        list = self.history.getHistoryList()
        for histItem in list:
            plot = ''
            try:
                if type(histItem) == type({}):
                    pattern     = histItem.get('pattern', '')
                    search_type = histItem.get('type', '')
                    if '' != search_type: plot = desc_base + _(search_type)
                else:
                    pattern     = histItem
                    search_type = None
                params = dict(baseItem)
                params.update({'title': pattern, 'search_type': search_type,  desc_key: plot})
                self.addDir(params)
            except Exception: printExc()
            
    def getFavouriteData(self, cItem):
        try:
            return json_dumps(cItem)
        except Exception: 
            printExc()
        return ''
        
    def getLinksForFavourite(self, fav_data):
        try:
            if self.MAIN_URL == None:
                self.selectDomain()
        except Exception: 
            printExc()
        links = []
        try:
            cItem = json_loads(fav_data)
            links = self.getLinksForItem(cItem)
        except Exception: printExc()
        return links
        
    def setInitListFromFavouriteItem(self, fav_data):
        try:
            if self.MAIN_URL == None:
                self.selectDomain()
        except Exception: 
            printExc()
        try:
            params = json_loads(fav_data)
        except Exception: 
            params = {}
            printExc()
            return False
        self.currList.append(params)
        return True
        
    def getLinksForItem(self, cItem):
        return self.getLinksForVideo(cItem)
    
    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        self.moreMode = False
        if 0 == refresh:
            if len(self.currList) <= index:
                return
            if -1 == index:
                self.currItem = { "name": None }
            else:
                self.currItem = self.currList[index]
        if 2 == refresh: # refresh for more items
            printDBG(">> endHandleService index[%s]" % index)
            # remove item more and store items before and after item more
            self.beforeMoreItemList = self.currList[0:index]
            self.afterMoreItemList = self.currList[index+1:]
            self.moreMode = True
            if -1 == index:
                self.currItem = { "name": None }
            else:
                self.currItem = self.currList[index]
    
    def endHandleService(self, index, refresh):
        if 2 == refresh: # refresh for more items
            currList = self.currList
            self.currList = self.beforeMoreItemList
            for item in currList:
                if 'more' == item['type'] or (item not in self.beforeMoreItemList and item not in self.afterMoreItemList):
                    self.currList.append(item)
            self.currList.extend(self.afterMoreItemList)
            self.beforeMoreItemList = []
            self.afterMoreItemList  = []
        self.moreMode = False
    
