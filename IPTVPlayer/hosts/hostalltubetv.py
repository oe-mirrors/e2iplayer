# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify
from Plugins.Extensions.IPTVPlayer.libs.pCommon import  CParsingHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
###################################################

###################################################
# FOREIGN import
###################################################
import re
import base64
###################################################

def gettytul():
    return 'http://alltube.pl/'

class AlltubeTV(CBaseHostClass):
    USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
    MAIN_URL    = 'http://alltube.pl/'
    SRCH_URL    = MAIN_URL + 'szukaj'
    DEFAULT_ICON_URL = 'http://alltube.pl/static/main/newlogoall.png'
    #{'category':'latest_added',       'title': _('Latest added'),  'url':MAIN_URL,                   'icon':DEFAULT_ICON},
    MAIN_CAT_TAB = [{'category':'genres_movies',      'title': _('Movies'),        'url':MAIN_URL+'filmy-online/',   },
                    {'category':'cat_series',         'title': _('Series'),        'url':MAIN_URL+'seriale-online/', },
                    {'category':'list_movies',        'title': _('Junior'),        'url':MAIN_URL+'dla-dzieci/',     },
                    {'category':'search',             'title': _('Search'), 'search_item':True, },
                    {'category':'search_history',     'title': _('Search history'), } ]
                      
    SERIES_CAT_TAB = [{'category':'list_series_list', 'title': _('List'),                       'url':MAIN_URL+'seriale-online/', },
                      {'category':'list_series_abc',  'title': _('ABC'),                        'url':MAIN_URL+'seriale-online/', },
                      {'category':'list_series',      'title': _('All'), 'letter':'all',        'url':MAIN_URL+'seriale-online/', } ]
 
    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'AlltubeTV', 'cookie':'alltubetv.cookie'})
        self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        
        self.filterCache = {}
        self.seriesCache = {}
        self.seriesLetters = []
        self.episodesCache = []
        self.cacheLinks = {}
        self._myFun = None

    def getPage(self, baseUrl, params={}, post_data=None):
        if params == {}: params = dict(self.defaultParams)
        params['cloudflare_params'] = {'domain':'alltube.pl', 'cookie_file':self.COOKIE_FILE, 'User-Agent':self.USER_AGENT, 'full_url_handle':self.getFullUrl}
        return self.cm.getPageCFProtection(baseUrl, params, post_data)
        
    def getFullIconUrl(self, url):
        url = CBaseHostClass.getFullIconUrl(self, url.strip())
        if url == '': return ''
        cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE, ['PHPSESSID', 'cf_clearance'])
        return strwithmeta(url, {'Cookie':cookieHeader, 'User-Agent':self.USER_AGENT})
        
    def _listFilters(self, cItem, data):
        printDBG("AlltubeTV._listFilters")
        ret = False
        data = self.cm.ph.getDataBeetwenMarkers(data, '<form id="filter"', '</form>', False)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<button', '</button>')
        for item in data:
            filter = self.cm.ph.getSearchGroups(item, 'value="([^"]+?)"')[0]
            title  = self.cleanHtmlStr(item)
            if filter != '' and title != '':
                ret = True
                params = dict(cItem)
                params.update({'title':title, 'check_filter':False, 'post_data':{'filter':filter}})
                self.addDir(params)
        return ret
            
    def _listItemsTab(self, cItem, m1, m2, sp, category='video'):
        printDBG("AlltubeTV._listItemsTab >>>>>>> cItem[%r]" % cItem)
        
        url = cItem['url']
        if '' != cItem.get('cat', ''):
            url += 'kategoria[%s]+' % cItem['cat']
        if '' != cItem.get('ver', ''):
            url += 'wersja[%s]+' % cItem['ver']
        if '' != cItem.get('year', ''):
            url += 'rok[%s]+' % cItem['year']
        page = cItem.get('page', 1)
        if page > 1:
            if category == 'video':
                url += 'strona[%s]+' % page
            else: url += '/%s' % page
            
        if 'filter' in cItem:
            filter = cItem['filter']
        else: filter = None
            
        post_data = cItem.get('post_data', None)
        
        sts, data = self.getPage(url, {}, post_data)
        if not sts: return 
        
        if cItem.get('check_filter', True):
            if self._listFilters(cItem, data): return
            else: cItem['check_filter'] = False
            
        pageM1 = '<div id="pager"'
        
        if ('strona[%s]+' % (page + 1)) in data or 'Następna strona' in data:
            nextPage = True
        else: nextPage = False
        
        data = self.cm.ph.getDataBeetwenMarkers(data, m1, m2, False)[1]
        data = data.split(sp)
        if len(data) and m1 != sp: del data[0]
        if len(data): data[-1] = data[-1].split(pageM1)[0]
        for item in data:
            url    = self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0]
            icon   = self.cm.ph.getSearchGroups(item, 'src="([^"]+?)"')[0]
            title  = self.cm.ph.getDataBeetwenMarkers(item, '<div class="title">', '</div>', False)[1]
            if '' == title: 
                title = self.cm.ph.getDataBeetwenMarkers(item, '<h3>', '</h3>', False)[1]
            if '' == title: 
                title = self.cm.ph.getSearchGroups(item, 'alt="([^"]+?)"')[0]
            desc   = self.cm.ph.getDataBeetwenMarkers(item, '<div class="description">', '</div>', False)[1]
            if '' == desc:
                desc = item.split('<p>')[-1]
            
            params = dict(cItem)
            params.update( {'good_for_fav': True, 'title': self.cleanHtmlStr( title ), 'url':self.getFullUrl(url), 'desc': self.cleanHtmlStr( desc ), 'icon':self.getFullUrl(icon)} )
            if category != 'video': #or '/serial/' in params['url']:
                params['category'] = category
                self.addDir(params)
            else: self.addVideo(params)
            
        if nextPage:
            params = dict(cItem)
            params.update( {'title':_('Next page'), 'page':page+1} )
            self.addDir(params)
    
    def fillFilterCache(self, url):
        sts, data = self.getPage(url)
        if not sts: return
        def _getFilters(m1, m2, key):
            tab = []
            dat = self.cm.ph.getDataBeetwenMarkers(data, m1, m2, False)[1]
            dat = re.compile('<li[^>]*?data-id="([^>]+?)"[^>]*?>([^>]+?)</li>').findall(dat)
            for item in dat:
                tab.append({key:item[0], 'title':item[1]})
            if len(tab):
                tab.insert(0, {'title':_('All')})
            return tab
        self.filterCache['category'] = _getFilters('filter-category">', '</ul>', 'cat')
        self.filterCache['version']  = _getFilters('id="filter-version">', '</ul>', 'ver')
        self.filterCache['year']     = _getFilters('id="filter-year">', '</ul>', 'year')
        
    def listFilters(self, cItem, filter, category):
        printDBG("AlltubeTV.listFilters")
        tab = self.filterCache.get(filter, [])
        if 0 == len(tab):
            self.fillFilterCache(self.MAIN_URL + 'filmy-online/')
            tab = self.filterCache.get(filter, [])
        cItem = dict(cItem)
        cItem['category'] = category
        self.listsTab(tab, cItem)
         
    def listMovies(self, cItem):
        printDBG("AlltubeTV.listMovies")
        self._listItemsTab(cItem, '<div class="item-block clearfix">', '<script>', '<div class="item-block clearfix">', category='video')
        
    def listSeriesList(self, cItem, category):
        printDBG("AlltubeTV.listSeriesList")
        self._listItemsTab(cItem, '<div class="item-block clearfix">', '<script>', '<div class="item-block clearfix">', category=category)
        
    def fillSeriesCache(self, url):
        printDBG("AlltubeTV.fillSeriesCache")
        self.seriesCache = {}
        self.seriesLetters = []
        sts, data = self.getPage(url)
        if not sts: return
        data = CParsingHelper.getDataBeetwenMarkers(data, 'term-list clearfix">', '</ul>', False)[1]
        data = re.compile('<li[^>]*?data-letter="([^"]+)"[^>]*?>[^<]*?<a[^>]*?href="([^"]+?)"[^>]*?>([^<]+?)<').findall(data)
        for item in data:
            letter = item[0]
            url    = item[1]
            title  = item[2]
            if letter not in self.seriesCache:
                self.seriesCache[letter] = []
                self.seriesLetters.append({'title':letter,  'letter':letter})
            self.seriesCache[letter].append({'good_for_fav':True, 'title': self.cleanHtmlStr( title ), 'url':self.getFullUrl(url)})
        for idx in range(len(self.seriesLetters)):
            letter = self.seriesLetters[idx]['letter']
            self.seriesLetters[idx]['title'] = letter + ' [%d]' % len(self.seriesCache[letter]) 
            
    def listSeriesABC(self, cItem, category):
        printDBG("AlltubeTV.listSeriesABC")
        if 0 == len(self.seriesLetters):
            self.fillSeriesCache(self.MAIN_URL + 'seriale-online/')
        cItem = dict(cItem)
        cItem['category'] = category
        self.listsTab(self.seriesLetters, cItem)
        
    def listSeries(self, cItem, category):
        printDBG("AlltubeTV.listSeries")
        
        if 0 == len(self.seriesLetters):
            self.fillSeriesCache(self.MAIN_URL + 'seriale-online/')
        
        if 'all' == cItem['letter']:
            letters = self.seriesLetters
        else:
            letters = [cItem]
        for item in letters:
            letter = item['letter']
            tab = self.seriesCache.get(letter, [])
            cItem = dict(cItem)
            cItem['category'] = category
            self.listsTab(tab, cItem)
        
    def listAllSeries(self, category):
        sts, data = self.getPage(cItem['url'])
        if not sts: return 

        data = CParsingHelper.getDataBeetwenMarkers(data, '<ul class="term-list">', '</ul>', False)[1]
        data = data.split('</li>')
        if len(data): del data[-1]

        for item in data:
            url    = self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0]
            icon   = ''
            params = dict(cItem)
            params.update( {'title': self.cleanHtmlStr( item ), 'url':self.getFullUrl(url), 'desc': '', 'icon':self.getFullUrl(icon)} )
            params['category'] = category
            self.addDir(params)
            
    def listSeasons(self, cItem, category):
        printDBG("AlltubeTV.listSeasons")
        self.episodesCache = []
        
        sts, data = self.getPage(cItem['url'])
        if not sts: return 
        
        if 'episode-list' in data:
            tmp = self.cm.ph.getDataBeetwenNodes(data, ('<h2', '>', 'headline'), ('</h2', '>'), False)[1]
            tmp = self.cm.ph.getSearchGroups(tmp, '''<a[^>]+?href=['"]([^'^"^#]+?)['"]''')[0]
            if tmp != '':
                tmp = self.getFullUrl(tmp)
                sts, tmp = self.getPage(tmp)
                if sts: data = tmp 
        
        seriesTitle =  self.cleanHtmlStr( self.cm.ph.getDataBeetwenMarkers(data, '<div class="col-xs-12 col-sm-9">', '</h3>', False)[1] )
        if '' == seriesTitle: seriesTitle = cItem['title']    
        
        desc = self.cm.ph.getDataBeetwenMarkers(data, '<div class="custome-panel clearfix">', '</div>', False)[1]
        icon = self.cm.ph.getSearchGroups(desc, 'src="([^"]+?)"')[0]
        desc = self.cleanHtmlStr( desc )
        icon = self.getFullUrl( icon )
        
        if '' == icon: icon = cItem.get('icon', '')
        if '' == desc: desc = cItem.get('desc', '')
        
        data = self.cm.ph.getDataBeetwenMarkers(data, 'ta odcin', '<script>', False)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<h3 class="headline">', '</div>')
        for season in data:
            seasonTitle = self.cleanHtmlStr( self.cm.ph.getDataBeetwenMarkers(season, '<h3', '</h3>')[1] )
            episodes = re.compile('<li[^>]*?class="episode"[^>]*?><a[^>]*?href="([^"]+?)">([^<]+?)</a>').findall( season )
            sort = True
            episodesList = []
            for item in episodes:
                try:
                    tmp = self.cm.ph.getSearchGroups(item[0], 'odcinek-([0-9]+?)-sezon-([0-9]+?)[^0-9]', 2)
                    season  = int(tmp[1])
                    episode = int(tmp[0])
                except Exception:
                    printExc()
                    season  = 0
                    episode = 0
                    sort    = False
                episodesList.append( {'good_for_fav': True, 'title': seriesTitle + ': ' + self.cleanHtmlStr( item[1] ), 'url':self.getFullUrl(item[0]), 'desc':  desc, 'icon':icon, 'season':season, 'episode':episode})
            if sort:
                episodesList.sort(key=lambda item: item['season']*1000 + item['episode'])#, reverse=True)
                #episodesList.reverse()
            if len(episodesList):
                params = dict(cItem)
                params.update({'good_for_fav': False, 'category':category, 'season_idx':len(self.episodesCache), 'title':seasonTitle, 'desc':  desc, 'icon':icon})
                self.addDir(params)
                self.episodesCache.append(episodesList)
        
    def listEpisodes(self, cItem):
        printDBG("AlltubeTV.listEpisodes")
        seasonIdx = cItem.get('season_idx', -1)
        
        if seasonIdx >= 0 and seasonIdx < len(self.episodesCache):
            episodesList = self.episodesCache[seasonIdx]
            self.listsTab(episodesList, cItem, 'video')
        
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("AlltubeTV.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        
        params = dict(self.defaultParams)
        params['header'] = {'User-Agent':self.USER_AGENT, 'Content-Type':'application/x-www-form-urlencoded'}
        sts, data = self.getPage(self.SRCH_URL, params, post_data={'search':searchPattern})
        if not sts: return
        
        printDBG(data)
        
        data = self.cm.ph.rgetDataBeetwenMarkers(data, '<div class="container-fluid">', 'Kontakt')[1]
        data = data.split('<h2 class="headline">')
        if len(data): del data[0]
        
        if searchType == 'series':
            marker = 'Seriale'
        elif searchType == 'movies':
            marker = 'Filmy'
        else:
            return
        
        found = False
        for idx in range(len(data)):
            if data[idx].startswith(marker):
                found = True
                break
                
        if not found: return
        data = data[idx]
        data = data.split('<div class="item-block clearfix">')
        if len(data): del data[0]

        for item in data:
            url    = self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0]
            icon   = self.cm.ph.getSearchGroups(item, 'src="([^"]+?)"')[0]
            title  = self.cm.ph.getDataBeetwenMarkers(item, '<div class="title">', '</div>', False)[1]
            if '' == title: title = self.cm.ph.getDataBeetwenMarkers(item, '<h3>', '</h3>', False)[1]
            if '' == title:  title = self.cm.ph.getSearchGroups(item, 'alt="([^"]+?)"')[0]
            desc   = self.cm.ph.getDataBeetwenMarkers(item, '<div class="description">', '</div>', False)[1]
            if '' == desc: desc = item.split('<p>')[-1]
            
            params = dict(cItem)
            params.update({'good_for_fav': True, 'title':self.cleanHtmlStr( title ), 'url':self.getFullUrl( url ), 'icon':self.getFullUrl( icon ), 'desc':self.cleanHtmlStr( desc )})
            if searchType == 'series':
                params['category'] = 'list_seasons'
                self.addDir(params)
            else:
                self.addVideo(params)
    
    def getLinksForVideo(self, cItem):
        printDBG("AlltubeTV.getLinksForVideo [%s]" % cItem)
        urlTab = []
        
        cacheKey = cItem['url']
        urlTab = self.cacheLinks.get(cacheKey, [])
        if len(urlTab):
            return urlTab
        
        sts, data = self.getPage(cItem['url'])
        if not sts: return urlTab
        
        data = self.cm.ph.getDataBeetwenNodes(data, ('<table', '>'), ('</table', '>'), False)[1]
        data = data.split('</tr>')
        if len(data): del data[-1]
        for item in data:
            try:
                url  = self.cm.ph.getSearchGroups(item, '''data\-iframe=['"]([^"^']+?)['"]''')[0]
                if url != '': url  = base64.b64decode(url)
                else: url = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']*?link/[^"^']+?)['"]''')[0]
                name = self.cleanHtmlStr(item)
                urlTab.append({'name':name, 'url':strwithmeta(url, {'cache_key':cacheKey}), 'need_resolve':1})
            except Exception:
                printExc()
                
        if len(urlTab):
            self.cacheLinks[cacheKey] = urlTab
        
        return urlTab
        
    def getVideoLinks(self, baseUrl):
        printDBG("AlltubeTV.getVideoLinks [%s]" % baseUrl)
        
        key = strwithmeta(baseUrl).meta.get('cache_key', '')
        for key in self.cacheLinks:
            for idx in range(len(self.cacheLinks[key])):
                if baseUrl in self.cacheLinks[key][idx]['url']:
                    if not self.cacheLinks[key][idx]['name'].startswith('*'):
                        self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name']
                    break
        
        if self._myFun == None:
            try:
                tmp = 'ZGVmIHphcmF6YShpbl9hYmMpOg0KICAgIGRlZiByaGV4KGEpOg0KICAgICAgICBoZXhfY2hyID0gJzAxMjM0NTY3ODlhYmNkZWYnDQogICAgICAgIHJldCA9ICcnDQogICAgICAgIGZvciBpIGluIHJhbmdlKDQpOg0KICAgICAgICAgICAgcmV0ICs9IGhleF9jaHJbKGEgPj4gKGkgKiA4ICsgNCkpICYgMHgwRl0gKyBoZXhfY2hyWyhhID4+IChpICogOCkpICYgMHgwRl0NCiAgICAgICAgcmV0dXJuIHJldA0KICAgIGRlZiBoZXgodGV4dCk6DQogICAgICAgIHJldCA9ICcnDQogICAgICAgIGZvciBpIGluIHJhbmdlKGxlbih0ZXh0KSk6DQogICAgICAgICAgICByZXQgKz0gcmhleCh0ZXh0W2ldKQ0KICAgICAgICByZXR1cm4gcmV0DQogICAgZGVmIGFkZDMyKGEsIGIpOg0KICAgICAgICByZXR1cm4gKGEgKyBiKSAmIDB4RkZGRkZGRkYNCiAgICBkZWYgY21uKGEsIGIsIGMsIGQsIGUsIGYpOg0KICAgICAgICBiID0gYWRkMzIoYWRkMzIoYiwgYSksIGFkZDMyKGQsIGYpKTsNCiAgICAgICAgcmV0dXJuIGFkZDMyKChiIDw8IGUpIHwgKGIgPj4gKDMyIC0gZSkpLCBjKQ0KICAgIGRlZiBmZihhLCBiLCBjLCBkLCBlLCBmLCBnKToNCiAgICAgICAgcmV0dXJuIGNtbigoYiAmIGMpIHwgKCh+YikgJiBkKSwgYSwgYiwgZSwgZiwgZykNCiAgICBkZWYgZ2coYSwgYiwgYywgZCwgZSwgZiwgZyk6DQogICAgICAgIHJldHVybiBjbW4oKGIgJiBkKSB8IChjICYgKH5kKSksIGEsIGIsIGUsIGYsIGcpDQogICAgZGVmIGhoKGEsIGIsIGMsIGQsIGUsIGYsIGcpOg0KICAgICAgICByZXR1cm4gY21uKGIgXiBjIF4gZCwgYSwgYiwgZSwgZiwgZykNCiAgICBkZWYgaWkoYSwgYiwgYywgZCwgZSwgZiwgZyk6DQogICAgICAgIHJldHVybiBjbW4oYyBeIChiIHwgKH5kKSksIGEsIGIsIGUsIGYsIGcpDQogICAgZGVmIGNyeXB0Y3ljbGUodGFiQSwgdGFiQik6DQogICAgICAgIGEgPSB0YWJBWzBdDQogICAgICAgIGIgPSB0YWJBWzFdDQogICAgICAgIGMgPSB0YWJBWzJdDQogICAgICAgIGQgPSB0YWJBWzNdDQogICAgICAgIGEgPSBmZihhLCBiLCBjLCBkLCB0YWJCWzBdLCA3LCAtNjgwODc2OTM2KTsNCiAgICAgICAgZCA9IGZmKGQsIGEsIGIsIGMsIHRhYkJbMV0sIDEyLCAtMzg5NTY0NTg2KTsNCiAgICAgICAgYyA9IGZmKGMsIGQsIGEsIGIsIHRhYkJbMl0sIDE3LCA2MDYxMDU4MTkpOw0KICAgICAgICBiID0gZmYoYiwgYywgZCwgYSwgdGFiQlszXSwgMjIsIC0xMDQ0NTI1MzMwKTsNCiAgICAgICAgYSA9IGZmKGEsIGIsIGMsIGQsIHRhYkJbNF0sIDcsIC0xNzY0MTg4OTcpOw0KICAgICAgICBkID0gZmYoZCwgYSwgYiwgYywgdGFiQls1XSwgMTIsIDEyMDAwODA0MjYpOw0KICAgICAgICBjID0gZmYoYywgZCwgYSwgYiwgdGFiQls2XSwgMTcsIC0xNDczMjMxMzQxKTsNCiAgICAgICAgYiA9IGZmKGIsIGMsIGQsIGEsIHRhYkJbN10sIDIyLCAtNDU3MDU5ODMpOw0KICAgICAgICBhID0gZmYoYSwgYiwgYywgZCwgdGFiQls4XSwgNywgMTc3MDAzNTQxNik7DQogICAgICAgIGQgPSBmZihkLCBhLCBiLCBjLCB0YWJCWzldLCAxMiwgLTE5NTg0MTQ0MTcpOw0KICAgICAgICBjID0gZmYoYywgZCwgYSwgYiwgdGFiQlsxMF0sIDE3LCAtNDIwNjMpOw0KICAgICAgICBiID0gZmYoYiwgYywgZCwgYSwgdGFiQlsxMV0sIDIyLCAtMTk5MDQwNDE2Mik7DQogICAgICAgIGEgPSBmZihhLCBiLCBjLCBkLCB0YWJCWzEyXSwgNywgMTgwNDYwMzY4Mik7DQogICAgICAgIGQgPSBmZihkLCBhLCBiLCBjLCB0YWJCWzEzXSwgMTIsIC00MDM0MTEwMSk7DQogICAgICAgIGMgPSBmZihjLCBkLCBhLCBiLCB0YWJCWzE0XSwgMTcsIC0xNTAyMDAyMjkwKTsNCiAgICAgICAgYiA9IGZmKGIsIGMsIGQsIGEsIHRhYkJbMTVdLCAyMiwgMTIzNjUzNTMyOSk7DQogICAgICAgIGEgPSBnZyhhLCBiLCBjLCBkLCB0YWJCWzFdLCA1LCAtMTY1Nzk2NTEwKTsNCiAgICAgICAgZCA9IGdnKGQsIGEsIGIsIGMsIHRhYkJbNl0sIDksIC0xMDY5NTAxNjMyKTsNCiAgICAgICAgYyA9IGdnKGMsIGQsIGEsIGIsIHRhYkJbMTFdLCAxNCwgNjQzNzE3NzEzKTsNCiAgICAgICAgYiA9IGdnKGIsIGMsIGQsIGEsIHRhYkJbMF0sIDIwLCAtMzczODk3MzAyKTsNCiAgICAgICAgYSA9IGdnKGEsIGIsIGMsIGQsIHRhYkJbNV0sIDUsIC03MDE1NTg2OTEpOw0KICAgICAgICBkID0gZ2coZCwgYSwgYiwgYywgdGFiQlsxMF0sIDksIDM4MDE2MDgzKTsNCiAgICAgICAgYyA9IGdnKGMsIGQsIGEsIGIsIHRhYkJbMTVdLCAxNCwgLTY2MDQ3ODMzNSk7DQogICAgICAgIGIgPSBnZyhiLCBjLCBkLCBhLCB0YWJCWzRdLCAyMCwgLTQwNTUzNzg0OCk7DQogICAgICAgIGEgPSBnZyhhLCBiLCBjLCBkLCB0YWJCWzldLCA1LCA1Njg0NDY0MzgpOw0KICAgICAgICBkID0gZ2coZCwgYSwgYiwgYywgdGFiQlsxNF0sIDksIC0xMDE5ODAzNjkwKTsNCiAgICAgICAgYyA9IGdnKGMsIGQsIGEsIGIsIHRhYkJbM10sIDE0LCAtMTg3MzYzOTYxKTsNCiAgICAgICAgYiA9IGdnKGIsIGMsIGQsIGEsIHRhYkJbOF0sIDIwLCAxMTYzNTMxNTAxKTsNCiAgICAgICAgYSA9IGdnKGEsIGIsIGMsIGQsIHRhYkJbMTNdLCA1LCAtMTQ0NDY4MTQ2Nyk7DQogICAgICAgIGQgPSBnZyhkLCBhLCBiLCBjLCB0YWJCWzJdLCA5LCAtNTE0MDM3ODQpOw0KICAgICAgICBjID0gZ2coYywgZCwgYSwgYiwgdGFiQls3XSwgMTQsIDE3MzUzMjg0NzMpOw0KICAgICAgICBiID0gZ2coYiwgYywgZCwgYSwgdGFiQlsxMl0sIDIwLCAtMTkyNjYwNzczNCk7DQogICAgICAgIGEgPSBoaChhLCBiLCBjLCBkLCB0YWJCWzVdLCA0LCAtMzc4NTU4KTsNCiAgICAgICAgZCA9IGhoKGQsIGEsIGIsIGMsIHRhYkJbOF0sIDExLCAtMjAyMjU3NDQ2Myk7DQogICAgICAgIGMgPSBoaChjLCBkLCBhLCBiLCB0YWJCWzExXSwgMTYsIDE4MzkwMzA1NjIpOw0KICAgICAgICBiID0gaGgoYiwgYywgZCwgYSwgdGFiQlsxNF0sIDIzLCAtMzUzMDk1NTYpOw0KICAgICAgICBhID0gaGgoYSwgYiwgYywgZCwgdGFiQlsxXSwgNCwgLTE1MzA5OTIwNjApOw0KICAgICAgICBkID0gaGgoZCwgYSwgYiwgYywgdGFiQls0XSwgMTEsIDEyNzI4OTMzNTMpOw0KICAgICAgICBjID0gaGgoYywgZCwgYSwgYiwgdGFiQls3XSwgMTYsIC0xNTU0OTc2MzIpOw0KICAgICAgICBiID0gaGgoYiwgYywgZCwgYSwgdGFiQlsxMF0sIDIzLCAtMTA5NDczMDY0MCk7DQogICAgICAgIGEgPSBoaChhLCBiLCBjLCBkLCB0YWJCWzEzXSwgNCwgNjgxMjc5MTc0KTsNCiAgICAgICAgZCA9IGhoKGQsIGEsIGIsIGMsIHRhYkJbMF0sIDExLCAtMzU4NTM3MjIyKTsNCiAgICAgICAgYyA9IGhoKGMsIGQsIGEsIGIsIHRhYkJbM10sIDE2LCAtNzIyNTIxOTc5KTsNCiAgICAgICAgYiA9IGhoKGIsIGMsIGQsIGEsIHRhYkJbNl0sIDIzLCA3NjAyOTE4OSk7DQogICAgICAgIGEgPSBoaChhLCBiLCBjLCBkLCB0YWJCWzldLCA0LCAtNjQwMzY0NDg3KTsNCiAgICAgICAgZCA9IGhoKGQsIGEsIGIsIGMsIHRhYkJbMTJdLCAxMSwgLTQyMTgxNTgzNSk7DQogICAgICAgIGMgPSBoaChjLCBkLCBhLCBiLCB0YWJCWzE1XSwgMTYsIDUzMDc0MjUyMCk7DQogICAgICAgIGIgPSBoaChiLCBjLCBkLCBhLCB0YWJCWzJdLCAyMywgLTk5NTMzODY1MSk7DQogICAgICAgIGEgPSBpaShhLCBiLCBjLCBkLCB0YWJCWzBdLCA2LCAtMTk4NjMwODQ0KTsNCiAgICAgICAgZCA9IGlpKGQsIGEsIGIsIGMsIHRhYkJbN10sIDEwLCAxMTI2ODkxNDE1KTsNCiAgICAgICAgYyA9IGlpKGMsIGQsIGEsIGIsIHRhYkJbMTRdLCAxNSwgLTE0MTYzNTQ5MDUpOw0KICAgICAgICBiID0gaWkoYiwgYywgZCwgYSwgdGFiQls1XSwgMjEsIC01NzQzNDA1NSk7DQogICAgICAgIGEgPSBpaShhLCBiLCBjLCBkLCB0YWJCWzEyXSwgNiwgMTcwMDQ4NTU3MSk7DQogICAgICAgIGQgPSBpaShkLCBhLCBiLCBjLCB0YWJCWzNdLCAxMCwgLTE4OTQ5ODY2MDYpOw0KICAgICAgICBjID0gaWkoYywgZCwgYSwgYiwgdGFiQlsxMF0sIDE1LCAtMTA1MTUyMyk7DQogICAgICAgIGIgPSBpaShiLCBjLCBkLCBhLCB0YWJCWzFdLCAyMSwgLTIwNTQ5MjI3OTkpOw0KICAgICAgICBhID0gaWkoYSwgYiwgYywgZCwgdGFiQls4XSwgNiwgMTg3MzMxMzM1OSk7DQogICAgICAgIGQgPSBpaShkLCBhLCBiLCBjLCB0YWJCWzE1XSwgMTAsIC0zMDYxMTc0NCk7DQogICAgICAgIGMgPSBpaShjLCBkLCBhLCBiLCB0YWJCWzZdLCAxNSwgLTE1NjAxOTgzODApOw0KICAgICAgICBiID0gaWkoYiwgYywgZCwgYSwgdGFiQlsxM10sIDIxLCAxMzA5MTUxNjQ5KTsNCiAgICAgICAgYSA9IGlpKGEsIGIsIGMsIGQsIHRhYkJbNF0sIDYsIC0xNDU1MjMwNzApOw0KICAgICAgICBkID0gaWkoZCwgYSwgYiwgYywgdGFiQlsxMV0sIDEwLCAtMTEyMDIxMDM3OSk7DQogICAgICAgIGMgPSBpaShjLCBkLCBhLCBiLCB0YWJCWzJdLCAxNSwgNzE4Nzg3MjU5KTsNCiAgICAgICAgYiA9IGlpKGIsIGMsIGQsIGEsIHRhYkJbOV0sIDIxLCAtMzQzNDg1NTUxKTsNCiAgICAgICAgdGFiQVswXSA9IGFkZDMyKGEsIHRhYkFbMF0pOw0KICAgICAgICB0YWJBWzFdID0gYWRkMzIoYiwgdGFiQVsxXSk7DQogICAgICAgIHRhYkFbMl0gPSBhZGQzMihjLCB0YWJBWzJdKTsNCiAgICAgICAgdGFiQVszXSA9IGFkZDMyKGQsIHRhYkFbM10pDQogICAgZGVmIGNyeXB0YmxrKHRleHQpOg0KICAgICAgICByZXQgPSBbXQ0KICAgICAgICBmb3IgaSBpbiByYW5nZSgwLCA2NCwgNCk6DQogICAgICAgICAgICByZXQuYXBwZW5kKG9yZCh0ZXh0W2ldKSArIChvcmQodGV4dFtpKzFdKSA8PCA4KSArIChvcmQodGV4dFtpKzJdKSA8PCAxNikgKyAob3JkKHRleHRbaSszXSkgPDwgMjQpKQ0KICAgICAgICByZXR1cm4gcmV0DQogICAgZGVmIGpjc3lzKHRleHQpOg0KICAgICAgICB0eHQgPSAnJzsNCiAgICAgICAgdHh0TGVuID0gbGVuKHRleHQpDQogICAgICAgIHJldCA9IFsxNzMyNTg0MTkzLCAtMjcxNzMzODc5LCAtMTczMjU4NDE5NCwgMjcxNzMzODc4XQ0KICAgICAgICBpID0gNjQNCiAgICAgICAgd2hpbGUgaSA8PSBsZW4odGV4dCk6DQogICAgICAgICAgICBjcnlwdGN5Y2xlKHJldCwgY3J5cHRibGsodGV4dFsnc3Vic3RyaW5nJ10oaSAtIDY0LCBpKSkpDQogICAgICAgICAgICBpICs9IDY0DQogICAgICAgIHRleHQgPSB0ZXh0W2kgLSA2NDpdDQogICAgICAgIHRtcCA9IFswLCAwLCAwLCAwLCAwLCAwLCAwLCAwLCAwLCAwLCAwLCAwLCAwLCAwLCAwLCAwXQ0KICAgICAgICBpID0gMA0KICAgICAgICB3aGlsZSBpIDwgbGVuKHRleHQpOg0KICAgICAgICAgICAgdG1wW2kgPj4gMl0gfD0gb3JkKHRleHRbaV0pIDw8ICgoaSAlIDQpIDw8IDMpDQogICAgICAgICAgICBpICs9IDENCiAgICAgICAgdG1wW2kgPj4gMl0gfD0gMHg4MCA8PCAoKGkgJSA0KSA8PCAzKQ0KICAgICAgICBpZiBpID4gNTU6DQogICAgICAgICAgICBjcnlwdGN5Y2xlKHJldCwgdG1wKTsNCiAgICAgICAgICAgIGZvciBpIGluIHJhbmdlKDE2KToNCiAgICAgICAgICAgICAgICB0bXBbaV0gPSAwDQogICAgICAgIHRtcFsxNF0gPSB0eHRMZW4gKiA4Ow0KICAgICAgICBjcnlwdGN5Y2xlKHJldCwgdG1wKTsNCiAgICAgICAgcmV0dXJuIHJldA0KICAgIGRlZiByZXplZG93YSh0ZXh0KToNCiAgICAgICAgcmV0dXJuIGhleChqY3N5cyh0ZXh0KSkNCiAgICByZXR1cm4gcmV6ZWRvd2EoaW5fYWJjKQ0K'
                tmp = base64.b64decode(tmp).replace('\r', '')
                _myFun = compile(tmp, '', 'exec')
                vGlobals = {"__builtins__": None, 'len': len, 'list': list, 'ord':ord, 'range':range}
                vLocals = { 'zaraza': '' }
                exec _myFun in vGlobals, vLocals
                self._myFun = vLocals['zaraza']
            except Exception:
                printExc()
        
        url  = self.getFullUrl('/jsverify.php?op=tag')
        sts, data = self.getPage(url)
        try:
            data = json_loads(data)
            cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE, ['PHPSESSID'])
            d = {};
            for i in range(len(data['key'])):
                d[data['key'][i]] = data['hash'][i]
            tmp = '';
            for k in sorted(d.keys()):
                tmp += d[k]
            cookieHeader += ' tmvh=%s;' % self._myFun(tmp)
            params = {'header':{'Cookie':cookieHeader, 'User-Agent':self.USER_AGENT}}
        except Exception:
            params = {}
            printExc()
        
        urlTab = []
        url = ''
        if 'alltube' in self.up.getDomain(baseUrl):
            sts, data = self.getPage(baseUrl, params)
            if not sts: return []
            data = self.cm.ph.getDataBeetwenNodes(data, ('<section', '>', 'player'), ('</section', '>'), False)[1]
            url = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0])
            #url = self.cm.ph.getDataBeetwenMarkers(data, 'src="', '"', False, False)[1]
        else:
            url = baseUrl
        
        if '' != url: 
            videoUrl = url
            if url.startswith('//'):
                videoUrl = 'http:' + videoUrl
            from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser 
            videoUrl = urlparser.decorateUrl(videoUrl, {'Referer': baseUrl}) 
            urlTab = self.up.getVideoLinkExt(videoUrl)

        return urlTab

    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('handleService start')
        
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name     = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG( "handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category) )
        self.currList = []
        
        self.cm.clearCookie(self.COOKIE_FILE, ['PHPSESSID', '__cfduid', 'cf_clearance'])
    #MAIN MENU
        if name == None:
            self.listsTab(self.MAIN_CAT_TAB, {'name':'category'})
    #MOVIES
        elif category == 'genres_movies':
            self.listFilters(self.currItem, 'category', 'list_version_filter')
        elif category == 'list_version_filter':
            self.listFilters(self.currItem, 'version', 'list_yer_filter')
        elif category == 'list_yer_filter':
            self.listFilters(self.currItem, 'year', 'list_movies')
        elif category == 'list_movies':
            self.listMovies(self.currItem)
    #SERIES
        elif category == 'cat_series':
            self.listsTab(self.SERIES_CAT_TAB, {'name':'category'})
        elif category == 'list_series_abc':
            self.listSeriesABC(self.currItem, 'list_series')
        elif category == 'list_series':
            self.listSeries(self.currItem, 'list_seasons')
        elif category == 'list_series_list':
            self.listSeriesList(self.currItem, 'list_seasons')
        elif category == 'list_seasons':
            self.listSeasons(self.currItem, 'list_episodes')
        elif category == 'list_episodes':
            self.listEpisodes(self.currItem)
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
        CHostBase.__init__(self, AlltubeTV(), True)

    def getSearchTypes(self):
        searchTypesOptions = []
        searchTypesOptions.append(("Filmy", "movies"))
        searchTypesOptions.append(("Seriale", "series"))
        return searchTypesOptions
