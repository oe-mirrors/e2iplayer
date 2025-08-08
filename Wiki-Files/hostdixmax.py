# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts, rm, GetCookieDir, ReadTextFile, WriteTextFile
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
from Plugins.Extensions.IPTVPlayer.libs import ph
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
###################################################

###################################################
# FOREIGN import
###################################################
from binascii import hexlify
from hashlib import md5
import urllib
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
config.plugins.iptvplayer.dixmax_login     = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.dixmax_password  = ConfigText(default="", fixed_size=False)

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
        self.DEFAULT_ICON_URL = 'https://tuelectronica.es/wp-content/uploads/2018/09/dixmax-portada.jpg'

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
        if self.dbApiKey:
            return self.dbApiKey
        sts, data = self.getPage(self.getFullUrl('/index.php'))
        if not sts:
            return
        data = ph.find(data, 'filterCat(', ')', 0)[1].split(',')
        self.dbApiKey = data[-1].strip()[1:-1]

    def listMain(self, cItem):
        printDBG("DixMax.listMain")
        sts, data = self.getPage(self.getFullUrl('/index.php'))
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        tmp = ph.findall(data, ('<li', '>', 'tooltip'), '</li>', limits=2)
        title1 = self.cleanHtmlStr(tmp[0]) if len(tmp) > 0 else _("Popular")
        title2 = self.cleanHtmlStr(tmp[1]) if len(tmp) > 1 else _("Browse")

        self.fillCacheFilters(cItem, data)
        self.getDBApiKey(data)

        MAIN_CAT_TAB = [{'category':'list_popular',   'title': title1,        'url':self.getFullUrl('/api/private/get/popular')},
                        {'category':'list_filters',   'title': title2,        'url':self.getFullUrl('/api/private/get/popular')},
                        {'category':'search',         'title': _('Search'),       'search_item':True       },
                        {'category':'search_history', 'title': _('Search history'),                        }]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def fillCacheFilters(self, cItem, data):
        printDBG("DixMax.fillCacheFilters")
        self.cacheFilters = {}
        self.cacheFiltersKeys = []

        keys = ('f_type', 'f_genre') #('genres[]', 'fichaType[]')
        tmp = ph.findall(data, ('<select', '>', 'b-multiple'), '</select>', limits=2)
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
        if not sts:
            return
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
            if title2 and title2 != title:
                title  += ' (%s)' % title2

            type = item['type']
            desc = [type]
            desc.append(item['year'])

            duration = _('%s minutes') % item['duration']
            desc.append(duration)

            rating = '%s (%s)' % (item['rating'], item['votes']) if int(item['votes']) else ''
            if rating:
                desc.append(rating)
            desc.append(item['country'])
            desc.append(item['genres'])
            desc.append(item['popularity'])
            desc = ' | '.join(desc) + '[/br]' + item['sinopsis']

            article = {'f_type':type, 'f_isserie':int(item['isSerie']), 'f_year':item['year'], 'f_duration':duration, 'f_rating':rating, 'f_country':item['country'], 'f_genres':item['genres'], 'f_sinopsis':item['sinopsis'], 'f_popularity':item['popularity']}
            if article['f_isserie']:
                article.update({'f_seasons':item['seasons'], 'f_episodes':item['episodes']})
            params = MergeDicts(cItem, {'good_for_fav':True, 'category':nextCategory, 'title':title, 'icon':icon, 'desc':desc, 'f_id':item['id']}, article) 
            retList.append( params )
        return retList

    def listItems(self, cItem, nextCategory):
        printDBG("DixMax.listItems")
        ITEMS_NUM = 40
        page = cItem.get('page', 0)
        url = 'api/private/get/explore'
        url += '?limit=%s&order=3&start=%s' % (ITEMS_NUM, page*ITEMS_NUM)

        if 'f_genre' in cItem:
            url += '&genres[]=%s' % cItem['f_genre_t']
        if 'f_type' in cItem:
            url += '&fichaType[]=%s' % cItem['f_type']
        if 'f_year' in cItem:
            url += '&fromYear=%s&toYear=%s' % (cItem['f_year']-1, cItem['f_year'])

        sts, data = self.getPage(self.getFullUrl(url))
        if not sts:
            return

        try:
            data = json_loads(data)
            for key in data['result']:
                subItems = self._listItems(cItem, nextCategory, data['result'][key])
                if subItems:
                    self.addDir(MergeDicts(cItem, {'title':key.title(), 'category':'sub_items', 'sub_items':subItems}))
        except Exception:
            printExc()

        if len(self.currList) == 1:
            self.currList = self.currList[0]['sub_items']

        if ITEMS_NUM == len(self.currList):
            self.addDir(MergeDicts(cItem, {'title':_('Next page'), 'page':page + 1}))

    def exploreItem(self, cItem, nextCategory):
        printDBG("DixMax.exploreItem")
        self.cacheLinks = {}
        apiKey = self.getDBApiKey()

        type = 'tv' if cItem['f_isserie'] else 'movie'
        url = 'https://api.themoviedb.org/3/%s/%s/videos?api_key=%s' % (type, cItem['f_id'], apiKey)

        sts, data = self.getPage(url)
        if not sts:
            return
        try:
            data = json_loads(data)
            for item in data['results']:
                if item['site'].lower() == 'youtube':
                    title = '[%s][%s] %s ' % (item['iso_3166_1'], item['size'], item['name'])
                    url = 'https://www.youtube.com/watch?v=%s' % item['key']
                    self.addVideo(MergeDicts(cItem, {'good_for_fav': True, 'title':title, 'url':url}))
        except Exception:
            printExc()

        if type == 'tv':
            url = self.getFullUrl('/serie/%s' % cItem['f_id'])
            sts, data = self.getPage(url)
            if not sts:
                return
            try:
                data = ph.find(data, 'gotoFuchaCrazy', '</script>', flags=0)[1]
                data = data[data.find('{'):data.rfind('}')+1]
                data = json_loads(data)
                sTitle = data['result']['info']['title']
                sIcon = self.getFullIconUrl(data['result']['info']['cover'])

                for seasonData in data['result']['episodes']:
                    sNum = str(seasonData['season'])
                    sEpisodes = ''
                    subItems = []
                    for item in seasonData['episodesList']:
                        eNum = str(item['episode'])
                        sEpisodes = str(item['episodes'])

                        icon = self.getFullIconUrl(item['cover'])
                        if not icon:
                            icon = sIcon

                        title = '%s: s%se%s %s' % (sTitle, sNum.zfill(2), eNum.zfill(2), item['name'])
                        type = _('Episode')
                        desc = [type]
                        desc.append(item['dateText'])
                        desc = ' | '.join(desc) + '[/br]' + item['sinopsis']

                        params = {'f_type':type, 'f_isepisode':1, 'f_date':item['dateText'], 'f_sinopsis':item['sinopsis'], 'f_season':sNum, 'f_episode':eNum}
                        params = MergeDicts(cItem, {'good_for_fav':True, 'type':'video', 'title':title, 'icon':icon, 'desc':desc, 'f_eid':item['id']}, params) 
                        params.pop('f_seasons')
                        params.pop('f_episodes')

                        key =  '%sx%sx%s' % (cItem['f_id'], params['f_episode'].zfill(2), params['f_season'].zfill(2))
                        subItems.append( params )

                    if len(subItems):
                        params = {'f_type':_('Season'), 'f_isseason':1, 'f_season':sNum}
                        params = MergeDicts(cItem, {'good_for_fav':False, 'category':nextCategory, 'sub_items':subItems, 'title':_('Season %s (%s)') % (sNum.zfill(2), sEpisodes), 'icon':sIcon}, params) 
                        self.addDir( params )
            except Exception:
                printExc()
        else:
            self.addVideo( MergeDicts(cItem) )

    def listSearchResult(self, cItem, searchPattern, searchType):
        self.tryTologin()

        url = self.getFullUrl('/api/private/get/search?query=%s&limit=100&f=1' % urllib.quote(searchPattern))
        sts, data = self.getPage(url)
        if not sts:
            return
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

        url = self.getFullUrl('/get_links.php') #get_all_links
        sts, data = self.getPage(url, post_data=post_data)
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
        self.tryTologin()

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

        if title == '':
            title = cItem['title']
        if icon == '':
            icon  = cItem.get('icon', self.DEFAULT_ICON_URL)
        if desc == '':
            desc  = cItem.get('desc', '')
        
        return [{'title':self.cleanHtmlStr( title ), 'text': self.cleanHtmlStr( desc ), 'images':[{'title':'', 'url':self.getFullUrl(icon)}], 'other_info':otherInfo}]
        
    def tryTologin(self):
        printDBG('tryTologin start')
        
        if None == self.loggedIn or self.login != config.plugins.iptvplayer.dixmax_login.value or\
            self.password != config.plugins.iptvplayer.dixmax_password.value:

            loginCookie = GetCookieDir('dixmax.com.login')
            self.login = config.plugins.iptvplayer.dixmax_login.value
            self.password = config.plugins.iptvplayer.dixmax_password.value

            sts, data = self.getPage(self.getMainUrl())
            if sts:
                self.setMainUrl(self.cm.meta['url'])

            freshSession = False
            if sts and 'logout.php' in data:
                printDBG("Check hash")
                hash = hexlify(md5('%s@***@%s' % (self.login, self.password)).digest())
                prevHash = ReadTextFile(loginCookie)[1].strip()

                printDBG("$hash[%s] $prevHash[%s]" % (hash, prevHash))
                if hash == prevHash:
                    self.loggedIn = True
                    return
                else:
                    freshSession = True

            rm(loginCookie)
            rm(self.COOKIE_FILE)
            if freshSession:
                sts, data = self.getPage(self.getMainUrl(), MergeDicts(self.defaultParams, {'use_new_session':True}))

            self.loggedIn = False
            if '' == self.login.strip() or '' == self.password.strip():
                msg = _('The host %s requires registration. \nPlease fill your login and password in the host configuration. Available under blue button.' % self.getMainUrl())
                self.sessionEx.waitForFinishOpen(MessageBox, msg, type=MessageBox.TYPE_INFO, timeout=10)
                return False

            msgTab = [_('Login failed.')]
            if sts:
                actionUrl = self.getFullUrl('/session.php?action=1')
                post_data = {'username':self.login, 'password':self.password, 'remember':'1'}

                httpParams = dict(self.defaultParams)
                httpParams['header'] = MergeDicts(httpParams['header'], {'Referer':self.cm.meta['url'], 'Accept':'*/*'})

                sts, data = self.getPage(actionUrl, httpParams, post_data)
                printDBG(data)
                if sts:
                    msgTab.append(self.cleanHtmlStr(data))
                sts, data = self.getPage(self.getMainUrl())

            if sts and 'logout.php' in data:
                printDBG('tryTologin OK')
                self.loggedIn = True
            else:
                printDBG(data)
                self.sessionEx.waitForFinishOpen(MessageBox, '\n'.join(msgTab), type=MessageBox.TYPE_ERROR, timeout=10)
                printDBG('tryTologin failed')

            if self.loggedIn:
                hash = hexlify(md5('%s@***@%s' % (self.login, self.password)).digest())
                WriteTextFile(loginCookie, hash)

        return self.loggedIn

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')
        
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name     = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG( "handleService: ||| name[%s], category[%s] " % (name, category) )
        self.currList = []

        self.tryTologin()

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
