# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.utils import unescapeHTML
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
###################################################

###################################################
# FOREIGN import
###################################################
import urlparse
import re
import urllib
try:    import json
except Exception: import simplejson as json
###################################################


def gettytul():
    return 'https://3filmy.com/'

class _3Filmy(CBaseHostClass):
    
    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'3filmy.com', 'cookie':'3filmy.com.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.MAIN_URL = 'https://3filmy.com/'
        self.DEFAULT_ICON_URL = 'https://scontent.fktw1-1.fna.fbcdn.net/v/t1.0-9/70780985_108079223927052_8895609768098398208_o.png?_nc_cat=109&_nc_ohc=s2ROC7XpdhgAQnJUJwfuz-tOgR6MR_LRD12UzlQn2C261HBVYhgz8CYXA&_nc_ht=scontent.fktw1-1.fna&oh=ecce9cfad83908608f84b318154961de&oe=5E684FA2'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT':'1', 'Accept': 'text/html', 'Accept-Encoding':'gzip, deflate', 'Referer':self.getMainUrl(), 'Origin':self.getMainUrl()}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update( {'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding':'gzip, deflate', 'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8', 'Accept':'application/json, text/javascript, */*; q=0.01'} )
        
        self.defaultParams = {'header':self.HTTP_HEADER, 'with_metadata':True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.ajaxParams = {'header':self.AJAX_HEADER, 'with_metadata':True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.MAIN_CAT_TAB = [{'category':'list_g',             'title': 'Filmy',           'url':self.getFullUrl('/filmy/')},
                             {'category':'slist_g',            'title': 'Seriale',         'url':self.getFullUrl('/seriale/')},
                             {'category':'search',             'title': _('Search'),       'search_item':True},
                             {'category':'search_history',     'title': _('Search history')} ]

        self.cacheMovieFilters = {'a':[], 'm':[], 'g':[], 'y':[], 'v':[]}
        
    def getPage(self, baseUrl, addParams = {}, post_data = None):
        if addParams == {}: addParams = dict(self.defaultParams)
        origBaseUrl = baseUrl
        baseUrl = self.cm.iriToUri(baseUrl)
        def _getFullUrl(url):
            if self.cm.isValidUrl(url): return url
            else: return urlparse.urljoin(baseUrl, url)
        addParams['cloudflare_params'] = {'domain':self.up.getDomain(baseUrl), 'cookie_file':self.COOKIE_FILE, 'User-Agent':self.USER_AGENT, 'full_url_handle':_getFullUrl}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)
    
    def _fillMovieFilters(self, cItem):
        self.cacheMovieFilters = { 'a':[], 'm':[], 'g':[], 'y':[], 'v':[]}

        sts, data = self.getPage(cItem['url'])
        if not sts: return
        
        # fill a
        dat = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="menu-left list-inline alfanu center">', '</ul>', False)[1]
        dat = re.compile('<li[^>]+?data-id="([^"]+?)"[^>]*?>(.+?)</li>').findall(dat)
        for item in dat:
            self.cacheMovieFilters['a'].append({'title': self.cleanHtmlStr(item[1]), 'a': item[0]})

        # fill g
        dat = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="menu-left list-inline genres center">', '</ul>', False)[1]
        dat = re.compile('<li[^>]+?data-id="([^"]+?)"[^>]*?>(.+?)</li>').findall(dat)
        for item in dat:
            self.cacheMovieFilters['g'].append({'title': self.cleanHtmlStr(item[1]), 'g': item[0]})
            
        # fill v
        dat = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="menu-left list-inline">', '</ul>', False)[1]
        dat = re.compile('<li[^>]+?data-id="([^"]+?)"[^>]*?>(.+?)</li>').findall(dat)
        for item in dat:
            self.cacheMovieFilters['v'].append({'title': self.cleanHtmlStr(item[1]), 'v': item[0]})
            
        # fill y
        dat = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="menu-left list-inline years">', '</ul>', False)[1]
        dat = re.compile('<li[^>]+?data-id="([^"]+?)"[^>]*?>(.+?)</li>').findall(dat)
        for item in dat:
            self.cacheMovieFilters['y'].append({'title': self.cleanHtmlStr(item[1]), 'y': item[0]})
            
        # fill m
        dat = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="menu-left list-inline genres main-sort ">', '</ul>', False)[1]
        dat = re.compile('<li[^>]+?data-id="([^"]+?)"[^>]*?>(.+?)</li>').findall(dat)
        for item in dat:
            self.cacheMovieFilters['m'].append({'title': self.cleanHtmlStr(item[1]), 'm': item[0]})    

    def listMovieFilters(self, cItem, category):
        printDBG("3filmy.listMovieFilters")
        
        filter = cItem['category'].split('_')[-1]
        if 0 == len(self.cacheMovieFilters[filter]):
            self._fillMovieFilters(cItem)
        if len(self.cacheMovieFilters[filter]) > 0:
            if filter != 'm':
                filterTab = [{'title':'--Wszystkie--'}]
            else:
                filterTab = []
            filterTab.extend(self.cacheMovieFilters[filter])
            self.listsTab(filterTab, cItem, category)

    def listsTab(self, tab, cItem, category=None):
        printDBG("3filmy.listsTab")
        for item in tab:
            params = dict(cItem)
            if None != category:
                params['category'] = category
            params.update(item)
            self.addDir(params)

    def listMovies(self, cItem):
        printDBG("3filmy.listMovies [%s]" % cItem)

        http_params = dict(self.defaultParams)
        http_params['header'] = self.AJAX_HEADER

        page = cItem.get('page', 1)

        load = '{"a":[],"m":[],"g":[],"y":[],"v":[]}'
        for item in ['a', 'm', 'g', 'y', 'v']:
            if item in cItem:
                load = load.replace('"'+item+'":[]','"'+item+'":["'+cItem[item][1:]+'"]')
        if 'serial' in cItem['url']: type = 1
        else: type = 0
        post_data = {'load':load, 'page':page, 'type':type}
        sts, data = self.getPage('https://3filmy.com/ajax/load.videos', http_params, post_data)
        if not sts: return

        nextPage = re.findall('^(\d+)<div',data)
        printDBG("3filmy.listMovies nextPage[%s]" % nextPage)

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<img', '>'), ('</div></div></div></div></div', '>'))
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<a', '>'), ('</a', '>'), False)[1])
            desc = self.cleanHtmlStr(item)
            params = dict(cItem)
            if type == 1:
                params = {'good_for_fav':True, 'name':'category', 'category':'list_series', 'url':url, 'title':title, 'desc':desc, 'icon':icon}
                self.addDir(params)
            else:
                params = {'good_for_fav':True, 'url':url, 'title':title, 'desc':desc, 'icon':icon}
                self.addVideo(params)
            
        if nextPage != '0':
            params = dict(cItem)
            params.update({'title':_('Next page'), 'url':nextPage, 'page':page + 1})
            self.addDir(params)

    def listSeries(self, cItem):
        printDBG("3filmy.listSeries [%s]" % cItem)
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        self.setMainUrl(data.meta['url'])

        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'player-ajax'), ('</div', '>'))[1]
        printDBG("3filmy.listSeries tmp [%s]" % tmp)
        hash = self.cm.ph.getSearchGroups(tmp, '''data\-hash=['"]([^"^']+?)['"]''')[0]

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<li', '>', 'data-id'), ('</li', '>'))
        for item in data:
            printDBG("3filmy.listSeries item %s" % item)
            url   = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            title = self.cm.ph.getSearchGroups(item, '''data\-title=['"]([^"^']+?)['"]''')[0]
            id    = self.cm.ph.getSearchGroups(item, '''data\-id=['"]([^"^']+?)['"]''')[0]
            params = {'good_for_fav':True, 'url':url, 'title':title, 'data-hash':hash, 'data-id':id}
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern):
        printDBG("3filmy.listSearchResult cItem[%s], searchPattern[%s]" % (cItem, searchPattern))
        url = self.getFullUrl('/ajax/search?q=%s') % urllib.quote_plus(searchPattern)
        http_params = dict(self.defaultParams)
        sts, data = self.getPage(url, http_params)
        if not sts: return
        printDBG("3filmy.listSearchResult data[%s]" % data)

        try:
            jsond = json_loads(data)
            for item in jsond:
                printDBG("3filmy.getLinksForVideo oitem %s" % item)
                url = self.getFullUrl(item['link'])
                icon = item['img']
                title = item['t']
                params = dict(cItem)
                if 'serial' in url:
                    params = {'good_for_fav':True, 'name':'category', 'category':'list_series', 'url':url, 'title':title, 'icon':icon}
                    self.addDir(params)
                else:
                    params = {'good_for_fav':True, 'url':url, 'title':title, 'icon':icon}
                    self.addVideo(params)
        except Exception:
            printExc()
       
    def getLinksForVideo(self, cItem):
        printDBG("3filmy.getLinksForVideo [%s]" % cItem)

        def _link(link):
            idx = 0
            st  = ''
            while idx < len(link):
                st  += chr(ord(link[idx]) ^ 0x5d)
                idx += 1
            return st
        
        params = dict(self.ajaxParams)
        params['header'] = dict(params['header'])
        
        cUrl = cItem['url']
        
        params['header']['Referer'] = cUrl
        if 'data-hash' not in cItem:
            sts, data = self.getPage(cUrl, params)
            if not sts: return []
            tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'player-ajax'), ('</div', '>'))[1]
            printDBG("3filmy.getLinksForVideo tmp [%s]" % tmp)
            hash = self.cm.ph.getSearchGroups(tmp, '''data\-hash=['"]([^"^']+?)['"]''')[0]
            id   = self.cm.ph.getSearchGroups(tmp, '''data\-id=['"]([^"^']+?)['"]''')[0]
            post_data = {'id':id, 'hash':hash, 'd':'-1', 'q':'-1', 'w':'-1'}
        else:
            post_data = {'id':cItem['data-id'], 'hash':cItem['data-hash'], 'd':'-1', 'q':'-1', 'w':'-1', 'ep':'true'}
        
        sts, data = self.getPage('https://3filmy.com/ajax/video.details', params, post_data)
        if not sts: return []
        printDBG("3filmy.getLinksForVideo data[%s]" % data)
        
        retTab = []
        
        try:
            jsond = json_loads(data)
            qual = jsond['q_avb']
            opts = [jsond['ch']]
            opts.extend(jsond['opts'])
#            printDBG("3filmy.getLinksForVideo qual: %s opts: %s" % (qual, opts))
            for qitem in qual:
                post_data.update({'q':qitem})
                for oitem in opts:
#                    printDBG("3filmy.getLinksForVideo oitem %s" % oitem)
                    post_data.update({'d':oitem[0]})
                    sts, data = self.getPage('https://3filmy.com/ajax/video.details', params, post_data)
                    if not sts: return []
                    jsond = json_loads(data)
                    link = urllib.unquote(jsond['link'])
                    url = _link(link)
                    retTab.append({'name':str(qitem) + ' - ' +  oitem[1], 'url':strwithmeta(url, {'Referer':url}), 'need_resolve':0})
        except Exception:
            printExc()
        
        return retTab
        
    def getVideoLinks(self, baseUrl):
        printDBG("3filmy.getVideoLinks [%s]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
                        
        return self.up.getVideoLinkExt(baseUrl)

    def tryTologin(self):
        printDBG('tryTologin start')
        
        return        

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('3filmy.handleService start')
        
#        self.tryTologin()
                
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        
        name     = self.currItem.get("name", None)
        category = self.currItem.get("category", '')
        printDBG( "3filmy.handleService: ---------> name[%s], category[%s] " % (name, category) )
        searchPattern = self.currItem.get("search_pattern", searchPattern)
        self.currList = []
        
        if None == name:
            self.listsTab(self.MAIN_CAT_TAB, {'name':'category'})
    #FILMS CATEGORIES
        elif 'list_g' == category:
            self.listMovieFilters(self.currItem, 'list_v')
        elif 'list_v' == category:
            self.listMovieFilters(self.currItem, 'list_y')
        elif 'list_y' == category:
            self.listMovieFilters(self.currItem, 'list_m')
        elif 'list_m' == category:
            self.listMovieFilters(self.currItem, 'list_movies')
        elif 'list_movies' == category:
            self.listMovies(self.currItem)
    #LIST SERIALS
        elif 'slist_g' == category:
            self.listMovieFilters(self.currItem, 'slist_a')
        elif 'slist_a' == category:
            self.listMovieFilters(self.currItem, 'slist_y')
        elif 'slist_y' == category:
            self.listMovieFilters(self.currItem, 'slist_m')
        elif 'slist_m' == category:
            self.listMovieFilters(self.currItem, 'slist_movies')
        elif 'slist_movies' == category:
            self.listMovies(self.currItem)
        elif 'list_series' == category:
            self.listSeries(self.currItem)
    #SEARCH
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item':False, 'name':'category'}) 
            self.listSearchResult(cItem, searchPattern)
    #HISTORIA SEARCH
        elif category == "search_history":
            self.listsHistory({'name':'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, _3Filmy(), True, [])

