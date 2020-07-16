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
    return 'https://dixmax.com/'
    
class SuggestionsProvider:
    MAIN_URL = 'https://dixmax.com/'
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

        self.MAIN_URL    = 'https://dixmax.com/'
        self.SESSION_URL = self.MAIN_URL + "session.php?action=1"
        self.GETLINKS_URL = self.MAIN_URL + "api/private/get_links.php"
        self.DEFAULT_ICON_URL = "https://dixmax.com/img/logor.png"
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

    def setMainUrl(self, url):
        CBaseHostClass.setMainUrl(self, url)
        SuggestionsProvider.MAIN_URL = self.getMainUrl()

    def getFullIconUrl(self, url, baseUrl=None):
        if url.startswith('/'): 
            return 'https://image.tmdb.org/t/p/w185' + url
        return CBaseHostClass.getFullIconUrl(self, url, baseUrl)

    def getDBApiKey(self, data=None):
        printDBG("DixMax.listMain")
        if self.dbApiKey: return self.dbApiKey
        sts, data = self.getPage(self.getFullUrl('/index.php'))
        if not sts: 
            return
        
        data = ph.find(data, 'filterCat(', ')', 0)[1].split(',')
        self.dbApiKey = data[-1].strip()[1:-1]

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
                    url = "https://dixmax.com/v2/" + url
                title = self.cleanHtmlStr(t)
                params = {'title': title, 'category':'list_items', 'url': url, 'icon': self.DEFAULT_ICON_URL}
                printDBG(str(params))
                self.addDir(params)

            self.fillCacheFilters(cItem, data)
            #self.getDBApiKey(data)

            MAIN_CAT_TAB = [
                            {'category':'list_filters',   'title': _("Filters") ,     'url':self.getFullUrl('/api/private/get/popular')},
                            {'category':'search',         'title': _('Search'),       'search_item':True       },
                            {'category':'search_history', 'title': _('Search history'),                        }]
            self.listsTab(MAIN_CAT_TAB, cItem)

    def fillCacheFilters(self, cItem, data):
        printDBG("DixMax.fillCacheFilters")
        self.cacheFilters = {}
        self.cacheFiltersKeys = []

        keys = ('f_type', 'filter-genre')


        '''
        keys = ('f_type', 'f_genre') #('genres[]', 'fichaType[]')
        for section in tmp:
            key = keys[len( self.cacheFiltersKeys)]
            self.cacheFilters[key] = []
            section = ph.findall(section, ('<option', '>'), '</option>', ph.START_S)
            for idx in range(1, len(section), 2):
                title = self.cleanHtmlStr(section[idx])
                value = ph.getattr(section[idx-1], 'value')
                self.cacheFilters[key].append({'title':title, key:value, key + '_t':title})
            if len(self.cacheFilters[key]):
                self.cacheFilters[key].insert(0, {'title':_('--All--')})
                self.cacheFiltersKeys.append(key)

        key = 'f_year'
        self.cacheFilters[key] = [{'title':_('--All--')}]
        currYear = datetime.now().year
        for year in range(currYear, currYear-20, -1):
            self.cacheFilters[key].append({'title':'%d-%d' % (year-1, year), key:year})
        self.cacheFiltersKeys.append(key)
        '''
        printDBG(self.cacheFilters)

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

    def listPopular(self, cItem):
        printDBG("DixMax.listPopular")
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        self.setMainUrl(self.cm.meta['url'])

        try:
            data = json_loads(data)
            for item in (('series','Series mas populares'), ('movie','Peliculas mas populares'), ('latest','Ultimas fichas agregadas')):
                subItems = self._listItems(cItem, 'explore_item', data['result'][item[0]])
                if subItems:
                    self.addDir(MergeDicts(cItem, {'title':item[1], 'category':'sub_items', 'sub_items':subItems}))
        except Exception:
            printExc()

    def listSubItems(self, cItem):
        printDBG("DixMax.listSubItems")
        self.currList = cItem['sub_items']

    def _listItems(self, cItem, nextCategory, data):
        printDBG("DixMax._listItems")
        retList = []
        
        for item in data:
            item = item['info']

            icon = self.getFullIconUrl(item['cover'])

            title = self.cleanHtmlStr( item['title'] )
            title2 = self.cleanHtmlStr( item['originalTitle'] )
            if title2 and title2 != title: title  += ' (%s)' % title2

            type = item['type']
            desc = [type]
            desc.append(item['year'])

            duration = _('%s minutes') % item['duration']
            desc.append(duration)

            rating = '%s (%s)' % (item['rating'], item['votes']) if int(item['votes']) else ''
            if rating: desc.append(rating)
            desc.append(item['country'])
            desc.append(item['genres'])
            desc.append(item['popularity'])
            desc = ' | '.join(desc) + '[/br]' + item['sinopsis']

            article = {'f_type':type, 'f_isserie':int(item['isSerie']), 'f_year':item['year'], 'f_duration':duration, 'f_rating':rating, 'f_country':item['country'], 'f_genres':item['genres'], 'f_sinopsis':item['sinopsis'], 'f_popularity':item['popularity']}
            if article['f_isserie']:  article.update({'f_seasons':item['seasons'], 'f_episodes':item['episodes']})
            params = MergeDicts(cItem, {'good_for_fav':True, 'category':nextCategory, 'title':title, 'icon':icon, 'desc':desc, 'f_id':item['id']}, article) 
            retList.append( params )
        return retList

    def listItems(self, cItem, nextCategory):
        printDBG("DixMax.listItems")
        
        url = cItem.get('url','')
        if not url:
            return
            
        page = cItem.get('page', 1)
        
        if not '/page/' in url:
            url = url + "/page/%s" % page
                
        #url = 'api/private/get/explore'
        #url += '?limit=%s&order=3&start=%s' % (ITEMS_NUM, page*ITEMS_NUM)

        #if 'f_genre' in cItem: url += '&genres[]=%s' % cItem['f_genre_t']
        #if 'f_type' in cItem: url += '&fichaType[]=%s' % cItem['f_type']
        #if 'f_year' in cItem: url += '&fromYear=%s&toYear=%s' % (cItem['f_year']-1, cItem['f_year'])

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
            printDBG("-----------------")
            printDBG(data)
            printDBG("-----------------")
            
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
        self.tryTologin()

        url = self.getFullUrl('/api/private/get/search?query=%s&limit=100&f=1' % urllib.quote(searchPattern))
        sts, data = self.getPage(url)
        if not sts: return
        self.setMainUrl(self.cm.meta['url'])

        try:
            data = json_loads(data)
            for key in data['result']:
                subItems = self._listItems(cItem, 'explore_item', data['result'][key])
                if subItems:
                    self.addDir(MergeDicts(cItem, {'title':key.title(), 'category':'sub_items', 'sub_items':subItems}))
        except Exception:
            printExc()

        if len(self.currList) == 1:
            self.currList = self.currList[0]['sub_items']

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

    def getArticleContent(self, cItem, data=None):
        printDBG("DixMax.getArticleContent [%s]" % cItem)
        retTab = []

        title = cItem['title']
        icon  = cItem.get('icon', self.DEFAULT_ICON_URL)
        desc  = cItem.get('f_sinopsis', '')

        otherInfo = {}

        for key in ('f_season', 'f_episode', 'f_seasons','f_episodes', 'f_year','f_duration', 'f_rating', 'f_genres', 'f_country', 'f_popularity'):
            if key in cItem:
                otherInfo[key[2:]] = cItem[key]

        if title == '': title = cItem['title']
        if icon == '':  icon  = cItem.get('icon', self.DEFAULT_ICON_URL)
        if desc == '':  desc  = cItem.get('desc', '')
        
        return [{'title':self.cleanHtmlStr( title ), 'text': self.cleanHtmlStr( desc ), 'images':[{'title':'', 'url':self.getFullUrl(icon)}], 'other_info':otherInfo}]

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

        elif category == 'list_popular':
            self.listPopular(self.currItem)

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
