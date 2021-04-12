# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, GetIPTVNotify
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts, rm, GetCookieDir, ReadTextFile, WriteTextFile
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
from Plugins.Extensions.IPTVPlayer.libs import ph
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.demjson import decode as demjson_loads
###################################################

###################################################
# FOREIGN import
###################################################
from binascii import hexlify
from hashlib import md5
import urllib
import re
from datetime import datetime
from Components.config import config, ConfigText, getConfigListEntry
###################################################

###################################################
# E2 GUI COMMPONENTS 
###################################################
from Screens.MessageBox import MessageBox
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.dixmax_login     = ConfigText(default = "", fixed_size = False)
config.plugins.iptvplayer.dixmax_password  = ConfigText(default = "", fixed_size = False)

def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("login"), config.plugins.iptvplayer.dixmax_login))
    optionList.append(getConfigListEntry(_("password"), config.plugins.iptvplayer.dixmax_password))
    return optionList
###################################################

def gettytul():
    return 'https://www.dixmax.io/'
    
class SuggestionsProvider:
    MAIN_URL = 'https://www.dixmax.io/'
    COOKIE_FILE = ''
    def __init__(self):
        self.cm = common()
        self.HTTP_HEADER = {'User-Agent':self.cm.getDefaultHeader(browser='chrome')['User-Agent'], 'X-Requested-With':'XMLHttpRequest'}
        self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'cookiefile': self.COOKIE_FILE}

    def getName(self):
        return _("DixMax Suggestions")

    def getSuggestions(self, text, locale):
        url = self.MAIN_URL + 'api/private/get/search?query=%s&limit=10&f=0' % (urllib.quote(text))
        sts, data = self.cm.getPage(url, self.defaultParams)
        if sts:
            retList = []
            for item in json_loads(data)['result']['ficha']['fichas']:
                retList.append(item['title'])
            return retList 
        return None

class DixMax(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'dixmax.com', 'cookie':'dixmax.com.cookie'})
        SuggestionsProvider.COOKIE_FILE = self.COOKIE_FILE

        self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.MAIN_URL    = 'https://dixmax.it/'
        self.SESSION_URL = self.MAIN_URL + "session.php?action=1"
        self.GETLINKS_URL = self.MAIN_URL + "api/private/get_links.php"
        self.DEFAULT_ICON_URL = "https://www.dixmax.io/img/logor.png"
        self.cacheFilters  = {}
        self.cacheFiltersKeys = []
        self.cacheLinks = {}
        self.loggedIn = None
        self.login    = ''
        self.password = ''
        self.dbApiKey = ''

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def getPageCF(self, baseUrl, params = {}, post_data = None):
        if params == {}: 
            params = self.defaultParams
        params['cloudflare_params'] = {'domain':'dixmax.com', 'cookie_file':self.COOKIE_FILE}
        return self.cm.getPageCFProtection(baseUrl, params, post_data)

    def setMainUrl(self, url):
        CBaseHostClass.setMainUrl(self, url)
        SuggestionsProvider.MAIN_URL = self.getMainUrl()

    def getFullIconUrl(self, url, baseUrl=None):
        if url.startswith('/'): 
            return 'https://image.tmdb.org/t/p/w185' + url
        return CBaseHostClass.getFullIconUrl(self, url, baseUrl)

    def tryToLogin(self):
        printDBG("DixMax.tryToLogin")
        
        if not (config.plugins.iptvplayer.dixmax_login.value and config.plugins.iptvplayer.dixmax_password.value):
            msg = _('The host %s requires subscription.\nPlease fill your login and password in the host configuration - available under blue button.') % self.getMainUrl()
            GetIPTVNotify().push(msg, 'info', 10)
            return False

        params = dict(self.defaultParams)
        params['header'].update({'Content-Type':'application/x-www-form-urlencoded'})
        
        postData = {'username': config.plugins.iptvplayer.dixmax_login.value.strip() , 'password': config.plugins.iptvplayer.dixmax_password.value.strip(), 'remember':'on' }
        sts, data = self.getPage(self.SESSION_URL, params, post_data = postData)
        
        if not sts:
            return False

        printDBG("---------------")
        printDBG(data)
        printDBG("---------------")
        
        if 'Error' in data:
            msg = data
            GetIPTVNotify().push(msg, 'info', 10)
            return False
        else:
            self.loggedIn = True
            return True
    
    def listMain(self, cItem):
        printDBG("DixMax.listMain")
        
        sts, data = self.getPage(self.MAIN_URL)
        if not sts: 
            return
        
        # check if login is required or it is a normal
        url = self.cm.meta['url']

        if 'login' in url:
            # try to login
            success = self.tryToLogin()
            #reload page
            sts, data = self.getPage(self.MAIN_URL)
            url = self.setMainUrl(self.cm.meta['url'])
        else:
            self.loggedIn = True

        if self.loggedIn: 
            
            # show menu of page     
            tmp = ph.findall(data, "<li class=\"header__nav-item\">", '</li>')
            
            for t in tmp:
                url = self.cm.ph.getSearchGroups(t, "href=['\"]([^\"^']+?)['\"]")[0]
                if url in ["series", "movies", "listas"]:
                    url = "https://dixmax.cc/v2/" + url
                title = self.cleanHtmlStr(t)
                params = {'title': title, 'category':'list_items', 'url': url, 'icon': self.DEFAULT_ICON_URL}
                printDBG(str(params))
                self.addDir(params)

            self.fillCacheFilters(cItem, data)

            MAIN_CAT_TAB = [
                            {'category':'list_items',     'title': _("Your lists") ,    'url': "https://dixmax.cc/v2/listas/youself" },
                            {'category':'list_filters',   'title': _("Filters") ,     'url': self.MAIN_URL},
                            {'category':'search',         'title': _('Search'),       'search_item':True       },
                            {'category':'search_history', 'title': _('Search history'),                        }]
            self.listsTab(MAIN_CAT_TAB, cItem)

    def fillCacheFilters(self, cItem, data):
        printDBG("DixMax.fillCacheFilters")
        self.cacheFilters = {}
        self.cacheFiltersKeys = []

        todosUrl = self.cm.ph.getSearchGroups(data, "<script src=\"([^\"]+todos[^\"]+?)\"")[0]
        if todosUrl:
            todosUrl = "https://dixmax.cc/v2/" + todosUrl

        sts, todosData = self.getPage(todosUrl)
        
        if sts:
            # type
            self.cacheFiltersKeys.append('f_type')
            self.cacheFilters['f_type'] = [
                            {'title': _('Movies'), 'f_type': "movies", 'f_type_t': _('Movies')},
                            {'title': _('Series'), 'f_type': "series", 'f_type_t': _('Series')},
                            ]
            
            # genres
            genre_code = re.findall("function _getGenreCode\(genre\)\{(.*?)\}", todosData)
            if genre_code:
                genre_code = genre_code[0]
                
                genreCodes = re.findall("case '([^']+?)':code=([0-9]+?);",genre_code)
                
                self.cacheFilters['f_genre'] = []
                for g in genreCodes:
                    self.cacheFilters['f_genre'].append({'title': g[0], 'f_genre': g[1], 'f_genre_t': g[0]})

                if self.cacheFilters['f_genre']:
                    self.cacheFilters['f_genre'].insert(0, {'title':_('--All--')})
                    self.cacheFiltersKeys.append('f_genre')
            
            # year
            key = 'f_year'
            self.cacheFilters['f_year'] = [{'title':_('--All--')}]
            currYear = datetime.now().year
            for year in range(currYear, currYear-20, -1):
                self.cacheFilters['f_year'].append({'title':'%d-%d' % (year-1, year), 'f_year':year})
            self.cacheFiltersKeys.append('f_year')
        
        printDBG(json_dumps(self.cacheFilters))

    def listFilters(self, cItem, nextCategory):
        printDBG("DixMax.listFilters")
        cItem = dict(cItem)

        f_idx = cItem.get('f_idx', 0)
        if f_idx >= len(self.cacheFiltersKeys):
            return

        filter = self.cacheFiltersKeys[f_idx]
        f_idx += 1
        cItem['f_idx'] = f_idx
        if f_idx  == len(self.cacheFiltersKeys):
            cItem['category'] = nextCategory
        self.listsTab(self.cacheFilters.get(filter, []), cItem)

    def listSubItems(self, cItem):
        printDBG("DixMax.listSubItems")
        self.currList = cItem['sub_items']

    def listItems(self, cItem, nextCategory):
        printDBG("DixMax.listItems")
        
        url = cItem.get('url','')
        if not url:
            return
        
        if 'f_type' in cItem:
            if cItem['f_type'] == 'movies' and 'movie' not in url:
                url = self.MAIN_URL  + "v2/movies"
            
            if cItem['f_type'] == 'series' and 'serie' not in url:
                url = self.MAIN_URL  + "v2/series"
        
        page = cItem.get('page', 1)
        if not '/page/' in url:
            url = url + "/page/%s" % page

        filters = []        
        if 'f_genre' in cItem: 
            filters.append('genre=%s' % cItem['f_genre'])
        if 'f_year' in cItem: 
            filters.append('year_from=%s&year_to=%s' % (cItem['f_year']-1, cItem['f_year']))

        if filters:
            url = url + "?" + "&".join(filters) 
        
        sts, data = self.getPage(self.getFullUrl(url))
        if not sts: 
            return

        items = data.split("<div class=\"card\">")
        if items:
            del(items[0])

        #items
        for item in items:
            h3 = self.cm.ph.getDataBeetwenMarkers(item, ("<h3",">"), "</h3>")[1]
            url = self.cm.ph.getSearchGroups(h3, "href=\"([^\"^']+?)\"")[0]
            if url:
                url = self.getFullUrl(url)
                title = self.cleanHtmlStr(h3)
                icon = self.cm.ph.getSearchGroups(item, "data-src-lazy=\"([^\"^']+?)\"")[0]
                params = dict(cItem)
                params.update({'title':title, 'url': url, 'icon': icon, 'category': nextCategory})
                if '/listas' in url:
                    params.update({'category':'list_items'})
                printDBG(str(params))
                self.addDir(params)
        
        #next page
        next_page = self.cm.ph.getSearchGroups(data, "href=\"([^\"^']+?)\">%s</a>" % (page+1))[0]
        if not next_page:
            next_page = self.cm.ph.getSearchGroups(data, "href=\"([^\"^']+?)\">\s?<i class=\"icon ion-ios-arrow-forward\"></i>\s?</a>" )[0]
        if next_page:
            params = dict(cItem)
            params.update({'title': _('Next page'), 'page': page + 1})
            self.addMore(params)
        
    def exploreItem(self, cItem, nextCategory):
        printDBG("DixMax.exploreItem")
        self.cacheLinks = {}

        url = cItem.get('url','')
        if not url:
            return
            
        sts, data = self.getPage(url)
        
        if sts:
            #printDBG("-----------------")
            #printDBG(data)
            #printDBG("-----------------")
            
            # info
            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, ("<div",">", "card__description"), "</div>")[1])
            
            # trailer
            trailerData = self.cm.ph.getSearchGroups(data, "YT\.Player\('ytplayer',\s?\{([^\}]+?)\\}")[0]
            if trailerData:
                try:
                    trailerJson = demjson_loads("{" + trailerData + "}")
                    printDBG(json_dumps(trailerJson))
                    videoId = trailerJson.get("videoId", "")
                    if videoId:
                        youtubeUrl = "https://www.youtube.com/watch?v=%s" % videoId
                        params = {'title' : cItem['title'] + " - trailer", 'url': youtubeUrl, 'icon': cItem['icon'], 'desc': desc}
                        printDBG(str(params))
                        self.addVideo(params)
                    
                except:
                    printExc()

            f_id = url.split("/")[-1]
            if f_id:
                if 'serie' in url.split("/"):
                    #it is a series
                    seasons = self.cm.ph.getAllItemsBeetwenMarkers(data, ("<div", ">",  "accordion__card"), "</table>")
                    for s in seasons:
                        sTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(s, ("<span",">"), "</span>")[1])
                        tmp = re.findall("setMarkedSeasonModal\(([0-9]+?)\s?,\s?([0-9]+?)\s?,\s?([0-9]+?)\);", s)
                        if tmp:
                            sNum = tmp[0][0]
                            numEpisodes = tmp[0][2]
                            sTitle = sTitle + " [ %s episodios]" % numEpisodes 
                        else:
                            sNum = 1
                        #sNum = str(seasonData['season'])
                        #sEpisodes = ''
                        subItems = []
                        episodes = self.cm.ph.getAllItemsBeetwenMarkers(s, ("<tr",">","row"), "</tr")

                        for ep in episodes:
                            epTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(ep, ("<td",">","col-4"), "</td>")[1])
                            epNum = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(ep, ("<th",">","col-1"), "</th>")[1])
                            epNum = epNum.strip()
                            if epTitle and epNum:
                                epTitle = 's%se%s %s' % (sNum.zfill(2), epNum.zfill(2), epTitle)
                            params = {'f_type': 'tv', 'f_isepisode': 1, 'f_id': f_id, 'f_season': sNum, 'f_episode': epNum}
                            params = MergeDicts(cItem, {'good_for_fav':True, 'type': 'video', 'title': epTitle}, params) 
                            key =  '%sx%sx%s' % ('f_id', params['f_episode'].zfill(2), params['f_season'].zfill(2))
                            
                            printDBG(str(params))
                            subItems.append( params )

                        if len(subItems):
                            params = {'f_type':_('Season'), 'f_isseason':1, 'title': sTitle,  'f_season':sNum, 'f_id' : f_id , 'category':nextCategory, 'sub_items':subItems}
                            self.addDir(MergeDicts(dict(cItem), params))
                        
                else:
                    params = MergeDicts(dict(cItem), {'desc': desc, 'f_id' : f_id})
                    printDBG(str(params))
                    self.addVideo(params)
            
    def listSearchResult(self, cItem, searchPattern, searchType):

        url = self.MAIN_URL + "?view=search&q=%s" % urllib.quote(searchPattern)
        
        sts, data = self.getPageCF(url)
        
        if not sts:
            return
        
        # add code when cloudflare protection will be bypassed
        

    def _getLinks(self, key, cItem):
        printDBG("DixMax._getLinks [%s]" % cItem['f_id'])

        post_data={'id':cItem['f_id']}
        
        isSeries =  cItem.get('f_isepisode') or cItem.get('f_isserie')
        if isSeries:
            post_data.update({'i':'true', 't':cItem.get('f_season'), 'e':cItem.get('f_episode')})
        else:
            post_data.update({'i':'false'})

        sts, data = self.getPage(self.GETLINKS_URL, post_data=post_data)
        if not sts: 
            return
        printDBG(data)

        try:
            data = json_loads(data)
            for item in data:
                if key not in self.cacheLinks:
                    self.cacheLinks[key] = []
                name = '[%s] %s | %s (%s) | %s | %s | %s ' % (item['host'], item['calidad'], item['audio'], item['sonido'], item['sub'], item['fecha'], item['autor_name'])
                url = self.getFullUrl(item['link'])
                self.cacheLinks[key].append({'name':name, 'url':strwithmeta(url, {'Referer':self.getMainUrl()}), 'need_resolve':1})
        except Exception:
            printExc()

    def getLinksForVideo(self, cItem):
        url = cItem.get('url', '')
        if 0 != self.up.checkHostSupport(url): 
            return self.up.getVideoLinkExt(url)

        if 'f_isepisode' in cItem:
            key =  '%sx%sx%s' % (cItem['f_id'], cItem['f_episode'].zfill(2), cItem['f_season'].zfill(2))
        else:
            key = cItem['f_id']
        
        linksTab = self.cacheLinks.get(key, [])
        if not linksTab:
            self._getLinks(key, cItem)
            linksTab = self.cacheLinks.get(key, [])

        return linksTab

    def getVideoLinks(self, videoUrl):
        printDBG("DixMax.getVideoLinks [%s]" % videoUrl)
        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if videoUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name']

        if 0 != self.up.checkHostSupport(videoUrl): 
            return self.up.getVideoLinkExt(videoUrl)

        return []

    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('handleService start')
        
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name     = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG( "handleService: ||| name[%s], category[%s] " % (name, category) )
        
        self.currList = []


        #MAIN MENU
        if name == None:
            self.listMain({'name':'category', 'type':'category'})

        elif category == 'list_filters':
            self.listFilters(self.currItem, 'list_items')

        elif category == 'sub_items':
            self.listSubItems(self.currItem)

        elif category == 'list_items':
            self.listItems(self.currItem, 'explore_item')

        elif category == 'explore_item':
            self.exploreItem(self.currItem, 'sub_items')

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

    def getSuggestionsProvider(self, index):
        printDBG('DixMax.getSuggestionsProvider')
        return SuggestionsProvider()

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, DixMax(), True, [])
    
    def withArticleContent(self, cItem):
        if 'f_id' in cItem:
            return True
        else:
            return False
