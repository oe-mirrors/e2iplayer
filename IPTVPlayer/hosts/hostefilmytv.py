# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetTmpDir, byteify, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute
###################################################

###################################################
# FOREIGN import
###################################################
import urlparse
import time
import re
from copy import deepcopy
try:    import json
except Exception: import simplejson as json
from Components.config import config, ConfigText, getConfigListEntry
###################################################


###################################################
# E2 GUI COMMPONENTS 
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvmultipleinputbox import IPTVMultipleInputBox
from Screens.MessageBox import MessageBox
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.efilmytv_login    = ConfigText(default = "", fixed_size = False)
config.plugins.iptvplayer.efilmytv_password = ConfigText(default = "", fixed_size = False)

def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("login")+":", config.plugins.iptvplayer.efilmytv_login))
    optionList.append(getConfigListEntry(_("password")+":", config.plugins.iptvplayer.efilmytv_password))
    return optionList
###################################################

def gettytul():
    return 'http://www.efilmy.tv/'

class EFilmyTv(CBaseHostClass):
    
    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'efilmy.tv', 'cookie':'efilmy.tv.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.MAIN_URL = 'http://www.efilmy.tv/'
        self.DEFAULT_ICON_URL = 'https://superrepo.org/static/images/icons/original/xplugin.video.efilmy.png.pagespeed.ic.ISN8CDQxwg.png'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT':'1', 'Accept': 'text/html', 'Accept-Encoding':'gzip, deflate', 'Referer':self.getMainUrl(), 'Origin':self.getMainUrl()}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update( {'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding':'gzip, deflate', 'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8', 'Accept':'application/json, text/javascript, */*; q=0.01'} )
        
        self.defaultParams = {'header':self.HTTP_HEADER, 'with_metadata':True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.login = ''
        self.password = ''
        self.loggedIn = None
        self.loginMessage = ''
        
        self.cacheSeries = {}
        self.cacheMovies = {}
        self.cacheSort = []
        self.cacheABC = {}
        
    def getPage(self, baseUrl, addParams = {}, post_data = None):
        if addParams == {}: addParams = dict(self.defaultParams)
        origBaseUrl = baseUrl
        baseUrl = self.cm.iriToUri(baseUrl)
        def _getFullUrl(url):
            if self.cm.isValidUrl(url): return url
            else: return urlparse.urljoin(baseUrl, url)
        addParams['cloudflare_params'] = {'domain':self.up.getDomain(baseUrl), 'cookie_file':self.COOKIE_FILE, 'User-Agent':self.USER_AGENT, 'full_url_handle':_getFullUrl}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)
        
    def listMainMenu(self, cItem, nextCategory):
        printDBG("EFilmyTv.listMainMenu")
        
        CAT_TAB = [{'category':'movies',         'title': _('Movies'),     'url':self.getFullUrl('/filmy.html')  },
                   {'category':'series',         'title': _('Series'),     'url':self.getFullUrl('/seriale.html')},
                   {'category':'search',         'title': _('Search'),          'search_item':True}, 
                   {'category':'search_history', 'title': _('Search history')},]
        params = dict(cItem)
        params['desc'] = self.loginMessage
        self.listsTab(CAT_TAB, params)
        
    def listHeadModuleItems(self, cItem, nextCategory, baseUrl, marker):
        sts, data = self.getPage(self.getMainUrl())
        if not sts: return
        
        cUrl = self.cm.getBaseUrl(data.meta['url'])
        data = self.cm.ph.getDataBeetwenNodes(data, ('<h1>', '</h1>', marker), ('</div', '>'))[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
        for item in data:
            url = self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0]
            id = self.cm.ph.getSearchGroups(item, '''\sid=['"]([^'^"]+?)['"]''')[0]
            if url != '#' or id == '': continue
            url = self.getFullUrl(baseUrl.format(id), cUrl)
            title = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'good_for_fav':False, 'category':nextCategory, 'title':title, 'url':url, 'desc':''})
            self.addDir(params)
            
    def listMoviesCats(self, cItem, nextCategory):
        printDBG("EFilmyTv.listSeriesCats")
        CAT_TAB = [{'category':'movies_all',   'title': _('--All--')},
                   {'category':'movies_top',   'title': _('Top')    },]
        cItem = dict(cItem)
        cItem['desc'] = ''
        self.listsTab(CAT_TAB, cItem)
        self.listHeadModuleItems(cItem, nextCategory, '/filmy.php?cmd={0}', 'filmy.html')
        
    def listSeriesCats(self, cItem, nextCategory):
        printDBG("EFilmyTv.listSeriesCats")
        CAT_TAB = [{'category':'series_all',         'title': _('--All--')},
                   {'category':'series_abc',         'title': 'ABC'       },
                   {'category':'series_top',         'title': _('Top')    },
                   {'category':'series_last',        'title': 'Ostatnio Aktualizowane'},]
        cItem = dict(cItem)
        cItem['desc'] = ''
        self.listsTab(CAT_TAB, cItem)
        self.listHeadModuleItems(cItem, nextCategory, '/seriale.php?cmd={0}', 'seriale.html')
        
    def listTopItems(self, cItem, nextCategory, baseUrl):
        sts, data = self.getPage(self.getMainUrl())
        if not sts: return
        
        cUrl = self.cm.getBaseUrl(data.meta['url'])
        data = self.cm.ph.getDataBeetwenMarkers(data, '<h3>', '</h3>')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
        for item in data:
            url = self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0]
            id = self.cm.ph.getSearchGroups(item, '''\sid=['"]([^'^"]+?)['"]''')[0].split('_')[-1]
            if url != '#' or id == '': continue
            url = self.getFullUrl(baseUrl.format(id), cUrl)
            title = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'good_for_fav':False, 'category':nextCategory, 'title':title, 'url':url, 'desc':''})
            if nextCategory == 'video': self.addVideo(params)
            else: self.addDir(params)
        
    def listSeriesTop(self, cItem, nextCategory):
        printDBG("EFilmyTv.listSeriesTop")
        self.listTopItems(cItem, nextCategory, '/seriale.php?cmd=popularne&dni={0}')
        
    def listMoviesTop(self, cItem, nextCategory):
        printDBG("EFilmyTv.listMoviesTop")
        self.listTopItems(cItem, nextCategory, '/filmy.php?cmd=popularne&dni={0}')
        
    def listCmdItems(self, cItem, nextCategory):
        printDBG("EFilmyTv.listCmdItems")
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        cUrl = self.cm.getBaseUrl(data.meta['url'])
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', '-item'), ('</div', '>'))
        for item in data:
            item = item.split('</script>', 1)[-1]
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0], cUrl)
            if ',odcinek' in url: 
                isEpisode = True
                titleLen = 2
            else: 
                isEpisode = False
                titleLen = 1
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''\ssrc=['"]([^'^"]+?)['"]''')[0])
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(item, '<a', '</a>')
            tmp.extend(self.cm.ph.getAllItemsBeetwenMarkers(item, '<span', '</span>'))
            title = []
            desc = []
            for t in tmp:
                t = self.cleanHtmlStr(t)
                if t == '': continue
                if len(title) < titleLen: title.append(t)
                else: desc.append(t)
            
            params = dict(cItem)
            params.update({'good_for_fav':True, 'category':nextCategory, 'title':' - '.join(title), 'url':url, 'icon':icon, 'desc':'[/br]'.join(desc)})
            if isEpisode or nextCategory == 'video': self.addVideo(params)
            else: self.addDir(params)
        
    def listSeriesAll(self, cItem, nextCategory):
        printDBG("EFilmyTv.listSeriesAll")
        url = self.getFullUrl('/seriale.php?cmd=slist')
        page = cItem.get('page', 0)
        url += '&page=%s' % page
        
        sts, data = self.getPage(url)
        if not sts: return
        
        cUrl = self.cm.getBaseUrl(data.meta['url'])
        
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
        for item in data:
            title = self.cleanHtmlStr(item.split('<script', 1)[0])
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0], cUrl)
            params = dict(cItem)
            params.update({'good_for_fav':True, 'category':nextCategory, 'title':title, 'url':url, 'icon':url + '?fake=need_resolve.jpeg', 'desc':''})
            self.addDir(params)
        
        if len(self.currList):
            params = dict(cItem)
            params.update({'good_for_fav':False, 'title':_('Next page'), 'page':page+1, 'desc':''})
            self.addDir(params)
            
    def fillSeriesCache(self, url):
        printDBG("EFilmyTv.fillSeriesCache")
        self.cacheSeries = {}
        sts, data = self.getPage(url)
        if not sts: return
        cUrl = self.cm.getBaseUrl(data.meta['url'])
        url = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<script[^>]+?src=['"]([^'^"]+?menu\.js[^'^"]*?)['"]''')[0], cUrl)
        sts, data = self.getPage(url)
        if not sts: return
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'var serials_', '];', False)
        try:
            parseObj = {}
            for item in data:
                item = item.split('=', 1)
                key = item[0].strip()
                parseObj[key] = byteify(json.loads(item[1].strip() + ']'))
            self.cacheSeries = parseObj
        except Exception:
            printExc()
            
    def listSeriesAbc(self, cItem, nextCategory):
        printDBG("EFilmyTv.listSeriesAbc")
        letters = self.cacheABC.get('f_keys', [])
        if len(letters) == 0:
            self.cacheABC['f_keys'] = []
            sts, data = self.getPage(cItem['url'])
            if not sts: return
            cUrl = self.cm.getBaseUrl(data.meta['url'])
            url = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<script[^>]+?src=['"]([^'^"]+?menu\.js[^'^"]*?)['"]''')[0], cUrl)
            sts, data = self.getPage(url)
            if not sts: return
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'var serials_', '];', False)
            try:
                if self.cacheSeries == {}:
                    self.fillSeriesCache(cItem['url'])
                keysTab = []
                for idx in range(len(self.cacheSeries['seo'])):
                    tmp = self.cacheSeries['seo'][idx].split(',', 1)[-1]
                    letter = tmp[0].upper()
                    if letter == '-' and len(tmp) > 1: letter = tmp[1].upper()
                    if letter in "0123456789*?#-!": letter = '#'
                    title = self.cleanHtmlStr(self.cacheSeries['pl'][idx])
                    url = self.getFullUrl('/serial,%s.html' % self.cacheSeries['seo'][idx], cUrl)
                    if letter not in keysTab:
                        keysTab.append(letter)
                        self.cacheABC[letter] = []
                    self.cacheABC[letter].append({'title':title, 'url':url, 'icon':url + '?fake=need_resolve.jpeg', 'desc':''})
                keysTab.sort()
                self.cacheABC['f_keys'] = keysTab
            except Exception:
                printExc()
        
        letters = self.cacheABC.get('f_keys', [])
        for letter in letters:
            params = dict(cItem)
            params.update({'good_for_fav':False, 'category':nextCategory, 'title':letter, 'f_letter':letter, 'desc':'', 'icon':''})
            self.addDir(params)
            
    def listSeriesByLetter(self, cItem, nextCategory):
        printDBG("EFilmyTv.listSeriesByLetter")
        letter = cItem['f_letter']
        tabItems = self.cacheABC.get(letter, [])
        cItem = dict(cItem)
        cItem['category'] = nextCategory
        self.listsTab(tabItems, cItem)
        
    def fillMoviesCache(self, cItem):
        printDBG("EFilmyTv.fillMoviesCache")
        self.cacheMovies = {'f_keys':[]}
        
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        
        cUrl = self.cm.getBaseUrl(data.meta['url'])
        
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<ul', '>', 'movie-'), ('</ul', '>'))
        for secItem in data:
            filterName = self.cm.ph.getSearchGroups(secItem, '''['"]movie\-([^'^"]+?)['"]''')[0]
            tab = []
            secItem = self.cm.ph.getAllItemsBeetwenMarkers(secItem, '<li', '</li>')
            printDBG(secItem)
            for item in secItem:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0], cUrl)
                title = self.cleanHtmlStr(item)
                tab.append({'title':title, 'url':url})
            if len(tab):
                tab.insert(0, {'title':_('--All--')})
                self.cacheMovies[filterName] = tab
                self.cacheMovies['f_keys'].append(filterName) 
        
    def listMoviesFilters(self, cItem, nextCategory):
        printDBG("EFilmyTv.listMoviesFilters")
        cItem = dict(cItem)
        
        f_idx = cItem.get('f_idx', 0)
        if f_idx == 0: self.fillMoviesCache(cItem)
        filters = self.cacheMovies.get('f_keys', [])
        if f_idx >= len(filters): return
        tabItems = self.cacheMovies.get(filters[f_idx], [])
        f_idx += 1
        cItem['f_idx'] = f_idx
        if f_idx >= len(filters): cItem['category'] = nextCategory
        self.listsTab(tabItems, cItem)
        
    def listSort(self, cItem, nextCategory):
        printDBG("EFilmyTv.listSort")
        
        if self.cacheSort == []:
            sts, data = self.getPage(cItem['url'])
            if not sts: return
            
            sortTabe = []
            data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'sort'), ('</div', '>'))[1]
            data = re.compile('''(<a[^>]+?sort\-[^>]+?>)''').findall(data)
            for item in data:
                tmp = self.cm.ph.getSearchGroups(item, '''sort\-([A-Za-z]+?)\-([A-Za-z]+?)[^A-Za-z]''', 2)
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''\stitle=['"]([^'^"]+?)['"]''')[0])
                title = title.split(',', 1)[-1].strip()
                sortTabe.append({'title':title, 'f_sort_key':tmp[0], 'f_sort_dir':tmp[1]})
            self.cacheSort = sortTabe
        
        cItem = dict(cItem)
        cItem['category'] = nextCategory
        self.listsTab(self.cacheSort, cItem)
        
    def listMovies(self, cItem):
        printDBG("EFilmyTv.listMovies")
        paramsUrl = dict(self.defaultParams)
        if 'f_sort_key' in cItem and 'f_sort_dir' in cItem:
            paramsUrl['cookie_items'] = {'uart_sort':'%s+%s' % (cItem['f_sort_key'], cItem['f_sort_dir'])}
        
        post_data = cItem.get('post_data', None)
        sts, data = self.getPage(cItem['url'], paramsUrl, post_data)
        if not sts: return
        
        cUrl = self.cm.getBaseUrl(data.meta['url'])
        
        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'pagin'), ('</div', '>'))[1]
        nextPage = self.getFullUrl(self.cm.ph.getSearchGroups(nextPage, '''<a[^>]+?href=['"]([^'^"]+?)['"][^>]+?>&raquo;''')[0], cUrl)
        
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'list-item'), ('</div', '>'))
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''\ssrc=['"]([^'^"]+?)['"]''')[0])
            
            desc  = []
            title = ''
            tmp = self.cm.ph.getAllItemsBeetwenNodes(item, ('<a', '>', 'title_'), ('</a', '>'), False)
            for t in tmp:
                t = self.cleanHtmlStr(t)
                if t == '': continue
                if title == '': title = t
                else: desc.append(t)
            
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(item, '<span', '</span>')
            for t in tmp:
                t = self.cleanHtmlStr(t)
                if t == '': continue
                desc.append(t)
            desc.append(self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<p', '</p>')[1]))
            params = dict(cItem)
            params.update({'good_for_fav':True, 'title':title, 'url':url, 'icon':icon, 'desc':'[/br]'.join(desc)})
            self.addVideo(params)
            
        if nextPage != '':
            params = dict(cItem)
            params.update({'title':_('Next page'), 'url':nextPage})
            self.addDir(params)
    
    def listSeriesUpdated(self, cItem, nextCategory):
        printDBG("EFilmyTv.listSeriesUpdated")
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        
        cUrl = self.cm.getBaseUrl(data.meta['url'])
        
        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'pagin'), ('</div', '>'))[1]
        nextPage = self.getFullUrl(self.cm.ph.getSearchGroups(nextPage, '''<a[^>]+?href=['"]([^'^"]+?)['"][^>]+?>&raquo;''')[0], cUrl)
        
        data = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'actual'), ('</ul', '>'))[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''\ssrc=['"]([^'^"]+?)['"]''')[0])
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(item, '<a', '</a>')
            title = self.cleanHtmlStr(tmp[0])
            desc = self.cleanHtmlStr(tmp[-1].replace('<br>', '[/br]'))
            params = dict(cItem)
            params.update({'good_for_fav':True, 'category':nextCategory, 'title':title, 'url':url, 'icon':icon, 'desc':desc})
            self.addDir(params)
            
        if nextPage != '':
            params = dict(cItem)
            params.update({'title':_('Next page'), 'url':nextPage})
            self.addDir(params)
            
    def listSeriesSeasons(self, cItem, nextCategory):
        printDBG("EFilmyTv.listSeriesSeasons")
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        cUrl = self.cm.getBaseUrl(data.meta['url'])
        serieTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'module-head'), ('</h1>', '>'))[1])
        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'holder'), ('</div', '>'))[1]
        data = re.sub("<!--[\s\S]*?-->", "", data)
        serieDesc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<p', '>', 'dsc'), ('</p', '>'))[1])
        
        serieIcon = self.getFullIconUrl(self.cm.ph.getSearchGroups(data, '''\ssrc=['"]([^'^"]+?)['"]''')[0])
        
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<h2', '</ul>')
        for sItem in data:
            sTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(sItem, '<h2', '</h2>')[1])
            sItem = self.cm.ph.getAllItemsBeetwenMarkers(sItem, '<li', '</li>')
            tabItems = []
            for item in sItem:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0])
                title = self.cleanHtmlStr(item)
                tabItems.append({'title':'%s - %s' % (serieTitle, title), 'url':url, 'icon':serieIcon, 'desc':''})
            if len(tabItems):
                params = dict(cItem)
                params.update({'good_for_fav':False, 'category':nextCategory, 'title':sTitle, 'episodes':tabItems, 'icon':serieIcon, 'desc':serieDesc})
                self.addDir(params)
                
    def listSeriesEpisodes(self, cItem):
        printDBG("EFilmyTv.listSeriesEpisodes")
        episodes = cItem.get('episodes', [])
        cItem = dict(cItem)
        cItem.update({'good_for_fav':True})
        self.listsTab(episodes, cItem, 'video')
    
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("EFilmyTv.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        
        if searchType == 'movies':
            cItem = dict(cItem)
            cItem['url'] = self.getFullUrl('/szukaj.html')
            cItem['category'] = 'list_movies'
            cItem['post_data'] = {'word':searchPattern, 'as_values_movie_title':'hidden'}
            self.listMovies(cItem)
        else:
            try:
                if self.cacheSeries == {}:
                    self.fillSeriesCache(self.getFullUrl('/seriale.html'))
                for idx in range(len(self.cacheSeries['pl'])):
                    if searchPattern.decode('utf-8').lower() in self.cacheSeries['pl'][idx].decode('utf-8').lower():
                        title = self.cleanHtmlStr(self.cacheSeries['pl'][idx])
                        url = self.getFullUrl('/serial,%s.html' % self.cacheSeries['seo'][idx])
                        params = dict(cItem)
                        params.update({'good_for_fav':True, 'category':'list_seasons', 'title':title, 'url':url, 'icon':url + '?fake=need_resolve.jpeg', 'desc':''})
                        self.addDir(params)
            except Exception:
                printExc()
        
    def getLinksForVideo(self, cItem):
        printDBG("EFilmyTv.getLinksForVideo [%s]" % cItem)
        self.tryTologin()
        
        retTab = []
        cacheKey = cItem['url']
        cacheTab = self.cacheLinks.get(cacheKey, [])
        if len(cacheTab): return cacheTab
        
        sts, data = self.getPage(cItem['url'])
        if not sts: return []
        
        cUrl = data.meta['url']
        
        errorMessage = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'deleted'), ('<div', '>'))[1])
        SetIPTVPlayerLastHostError(errorMessage)
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<span', '>', 'playername'), ('</div></div', '>'))
        printDBG("EFilmyTv.getLinksForVideo playername[%s]" % data)
        for item in data:
            movieId = self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'embedbg'), ('</div', '>'))[1]
            movieId = self.cm.ph.getSearchGroups(movieId, '''\sid=['"]([0-9]+?(?:_s)?)['"]''')[0]
            if movieId == '': continue
            if movieId.endswith('_s'): baseUrl = '/seriale.php'
            else: baseUrl = '/filmy.php'
            
#            item = item.split('</div>', 1)
            name = self.cleanHtmlStr(item).replace('Odtwarzacz', '').replace('Wersja', '')

            item = self.cm.ph.getAllItemsBeetwenMarkers(item, '<input', '>')
            for it in item:
                val = self.cm.ph.getSearchGroups(it, '''\svalue=['"]([^'^"]+?)['"]''')[0]
                if 'bez' in val.lower(): 
                    if not self.loggedIn: continue
                    type = 'show_premium'
                else: 
                    type = 'show_player'
                url = self.getFullUrl(baseUrl + '?cmd=%s&id=%s' % (type, movieId), cUrl)
                retTab.append({'name':'%s - %s' % (name, val), 'url':strwithmeta(url, {'Referer':cUrl, 'f_type':type}), 'need_resolve':1})
        if len(retTab):
            self.cacheLinks[cacheKey] = retTab
        return retTab
        
    def getVideoLinks(self, videoUrl):
        printDBG("EFilmyTv.getVideoLinks [%s]" % videoUrl)
        self.tryTologin()
        
        videoUrl = strwithmeta(videoUrl)
        urlTab = []
        
        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if videoUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name']
                        break
        
        paramsUrl = dict(self.defaultParams)
        paramsUrl['header'] = dict(paramsUrl['header'])
        paramsUrl['header']['Referer'] = videoUrl.meta.get('Referer', self.getMainUrl())
        sts, data = self.getPage(videoUrl, paramsUrl)
        if not sts: return urlTab
        cUrl = data.meta['url']
        
        ##############################################################################################
        while sts and 'generate_captcha' in data:
            captchaTitle = self.cm.ph.getAllItemsBeetwenMarkers(data, '<p', '</p>')
            
            if len(captchaTitle):
                captchaTitle = self.cleanHtmlStr(captchaTitle[-1])
            
            # parse form data
            data = self.cm.ph.getDataBeetwenMarkers(data, '<form', '</form>')[1]
            imgUrl = self.getFullUrl('/mirrory.php?cmd=generate_captcha&time=%s' % time.time(), cUrl)
            actionUrl = self.getFullUrl(self.cm.ph.getSearchGroups(data, 'action="([^"]+?)"')[0], cUrl)
            tmp = re.compile('''<input[^>]+?>''').findall(data)
            printDBG(tmp)
            captcha_post_data = {}
            for it in tmp:
                val = self.cm.ph.getSearchGroups(it, '''\svalue=['"]?([^'^"^\s]+?)['"\s]''')[0].strip()
                name = self.cm.ph.getSearchGroups(it, '''\sname=['"]([^'^"]+?)['"]''')[0]
                captcha_post_data[name] = val
            
            header = dict(self.HTTP_HEADER)
            header['Accept'] = 'image/png,image/*;q=0.8,*/*;q=0.5'
            params = dict(self.defaultParams)
            params.update( {'maintype': 'image', 'subtypes':['jpeg', 'png'], 'check_first_bytes':['\xFF\xD8','\xFF\xD9','\x89\x50\x4E\x47'], 'header':header} )
            filePath = GetTmpDir('.iptvplayer_captcha.jpg')
            rm(filePath)
            ret = self.cm.saveWebFile(filePath, imgUrl.replace('&amp;', '&'), params)
            if not ret.get('sts'):
                SetIPTVPlayerLastHostError(_('Fail to get "%s".') % imgUrl)
                return urlTab
            params = deepcopy(IPTVMultipleInputBox.DEF_PARAMS)
            params['accep_label'] = _('Send')
            params['title'] = _('Captcha')
            params['status_text'] = captchaTitle
            params['with_accept_button'] = True
            params['list'] = []
            item = deepcopy(IPTVMultipleInputBox.DEF_INPUT_PARAMS)
            item['label_size'] = (160,75)
            item['input_size'] = (480,25)
            item['icon_path'] = filePath
            item['title'] = _('Answer')
            item['input']['text'] = ''
            params['list'].append(item)

            ret = 0
            retArg = self.sessionEx.waitForFinishOpen(IPTVMultipleInputBox, params)
            printDBG(retArg)
            if retArg and len(retArg) and retArg[0]:
                printDBG(retArg[0])
                captcha_post_data['captcha'] = retArg[0][0]
                paramsUrl['header']['Referer'] = cUrl
                sts, data = self.cm.getPage(actionUrl, paramsUrl, captcha_post_data)
                if sts: cUrl = data.meta['url'] 
                else: return urlTab
            else:
                return urlTab
        ##############################################################################################
        
        jscode = []
        tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<script', '>'), ('</script', '>'), False)
        for item in tmp:
            if 'eval(' in item:
                jscode.append(item)
        
        if len(jscode) > 0:
            jscode.insert(0, 'var document={write:function(e){print(e)}};Base64={},Base64.decode=function(e){e.length%4==3&&(e+="="),e.length%4==2&&(e+="=="),e=Duktape.dec("base64",e),decText="";for(var t=0;t<e.byteLength;t++)decText+=String.fromCharCode(e[t]);return decText};')
            ret = js_execute('\n'.join(jscode))
            if ret['sts'] and 0 == ret['code']:
                data = ret['data'].strip()
        if 'premium' in videoUrl.meta['f_type']:
            printDBG(data)
            errorMessage = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'toomany'), ('</div', '>'))[1].replace('<br>', '\n'))
            SetIPTVPlayerLastHostError(errorMessage)
            data = self.cm.ph.getDataBeetwenMarkers(data, 'clip:', '}')[1]
            videoUrl = self.cm.ph.getSearchGroups(data, '''\surl\s*?:\s*?['"](https?://[^'^"]+?)['"]''', 1, True)[0]
            if videoUrl != '': urlTab.append({'name':'direct_link', 'url':strwithmeta(videoUrl, {'Referer':cUrl})})
        else:
            videoUrl = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0], cUrl)
            urlTab = self.up.getVideoLinkExt(strwithmeta(videoUrl, {'Referer':cUrl}))
        
        return urlTab
        
    def getArticleContent(self, cItem):
        printDBG("EFilmyTv.getArticleContent [%s]" % cItem)
        self.tryTologin()
        retTab = []
        
        url = cItem.get('url', '')
        if ',odcinek' in url: type = 'episode'
        elif 'serial,' in url: type = 'series'
        elif 'film,' in url: type = 'movie'  
        else: return []
        
        sts, data = self.getPage(url)
        if not sts: return []
        
        otherInfo = {}
        retTab = []
        desc = []
        
        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<p', '</p>')[1])
        icon = self.cm.ph.getDataBeetwenNodes(data, ('<meta', '>', 'image'), ('<', '>'))[1]
        icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(icon, '''content=['"]([^'^"]+?)['"]''')[0])
        
        title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'prawo-kontener'), ('</div', '>'), False)[1].replace('&laquo;', '').replace('&raquo;', ''))
        if type == 'episode':
            sTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'movieinfo'), ('</h', '>'), False)[1])
            title = '%s - %s' % (sTitle, title)
        
        if title == '': title = cItem['title']
        if desc == '':  desc = cItem.get('desc', '')
        if icon == '':  icon = cItem.get('icon', self.DEFAULT_ICON_URL)
        
        return [{'title':self.cleanHtmlStr( title ), 'text': self.cleanHtmlStr( desc ), 'images':[{'title':'', 'url':self.getFullIconUrl(icon)}], 'other_info':otherInfo}]
        
    def tryTologin(self):
        printDBG('EFilmyTv.tryTologin start')
        
        if self.login == config.plugins.iptvplayer.efilmytv_login.value and \
           self.password == config.plugins.iptvplayer.efilmytv_password.value:
           return 
        
        self.login = config.plugins.iptvplayer.efilmytv_login.value
        self.password = config.plugins.iptvplayer.efilmytv_password.value
        
        #rm(self.COOKIE_FILE)
        self.loggedIn = False
        
        if '' == self.login.strip() or '' == self.password.strip():
            self.cm.clearCookie(self.COOKIE_FILE, ['__cfduid', 'cf_clearance'])
            return False
        
        sts, data = self.getPage(self.getMainUrl())
        if not sts: return False
        
        nick = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<a', '>', 'nick'), ('</a', '>'))[1])
        loginMarker = 'logout.html'
        if loginMarker not in data or nick != self.login:
            self.cm.clearCookie(self.COOKIE_FILE, ['__cfduid', 'cf_clearance'])
            sts, data = self.cm.ph.getDataBeetwenNodes(data, ('<form', '>', 'user'), ('</form', '>'))
            if not sts: return False
            
            actionUrl = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''action=['"]([^'^"]+?)['"]''')[0])
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<input', '>')
            post_data = {}
            for item in data:
                name  = self.cm.ph.getSearchGroups(item, '''name=['"]([^'^"]+?)['"]''')[0]
                value = self.cm.ph.getSearchGroups(item, '''value=['"]([^'^"]+?)['"]''')[0]
                post_data[name] = value
            
            post_data.update({'ga10':self.login, 'gb10':self.password, 'gautolog':'t'})
            
            httpParams = dict(self.defaultParams)
            httpParams['header'] = dict(httpParams['header'])
            httpParams['header']['Referer'] = self.getMainUrl()
            sts, data = self.cm.getPage(actionUrl, httpParams, post_data)
        if sts and loginMarker in data:
            self.loggedIn = True
            data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'po-zalogowaniu'), ('<a', '>', 'logout.html'))[1]
            data = data.split('</a>')
            self.loginMessage =  []
            for t in data:
                t = self.cleanHtmlStr(t)
                if t not in ['', '>']: self.loginMessage.append(t)
            self.loginMessage = '[/br]'.join(self.loginMessage)
        else:
            message = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'warn'), ('</div', '>'))[1])
            self.sessionEx.open(MessageBox, _('Login failed.') + '\n' + message, type = MessageBox.TYPE_ERROR, timeout = 10)
            printDBG('tryTologin failed')
        return self.loggedIn
    
    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('handleService start')
        
        self.tryTologin()
        
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name     = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode     = self.currItem.get("mode", '')
        
        printDBG( "handleService: |||| name[%s], category[%s] " % (name, category) )
        self.cacheLinks = {}
        self.currList = []
        
    #MAIN MENU
        if name == None:
            self.listMainMenu({'name':'category'}, 'sub_menu')
    #MOVIES
        elif category == 'movies':
            self.listMoviesCats(self.currItem, 'list_movies_cmd')
        elif category == 'movies_top':
            self.listMoviesTop(self.currItem, 'list_movies_cmd')
        elif category == 'list_movies_cmd':
            self.listCmdItems(self.currItem, 'video')
        elif category == 'movies_all':
            self.listMoviesFilters(self.currItem, 'list_sorts')
        elif category == 'list_sorts':
            self.listSort(self.currItem, 'list_movies')
        elif category == 'list_movies':
            self.listMovies(self.currItem)
    #SERIES
        elif category == 'series':
            self.listSeriesCats(self.currItem, 'list_series_cmd')
        elif category == 'series_top':
            self.listSeriesTop(self.currItem, 'list_series_cmd')
        elif category == 'list_series_cmd':
            self.listCmdItems(self.currItem, 'list_seasons')
        elif category == 'series_last':
            self.listSeriesUpdated(self.currItem, 'list_seasons')
        elif category == 'series_abc':
            self.listSeriesAbc(self.currItem, 'series_by_letter')
        elif category == 'series_by_letter':
            self.listSeriesByLetter(self.currItem, 'list_seasons')
        elif category == 'series_all':
            self.listSeriesAll(self.currItem, 'list_seasons')
        elif category == 'list_seasons':
            self.listSeriesSeasons(self.currItem, 'list_episodes')
        elif category == 'list_episodes':
            self.listSeriesEpisodes(self.currItem)
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
        CHostBase.__init__(self, EFilmyTv(), True, [])
    
    def getSearchTypes(self):
        searchTypesOptions = []
        searchTypesOptions.append((_("Movies"), "movies"))
        searchTypesOptions.append((_("Series"), "series"))
        return searchTypesOptions
        
    def withArticleContent(self, cItem):
        url = cItem.get('url', '')
        if 'serial,' in url or ',odcinek' in url or 'film,' in url:
            return True
        return False