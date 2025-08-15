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
# E2 GUI COMMPONENTS 
###################################################
from Screens.MessageBox import MessageBox
###################################################
# FOREIGN import
###################################################
import urlparse
import re
import urllib
from Components.config import config, ConfigText, ConfigSelection, getConfigListEntry
###################################################


def gettytul():
    return 'https://zalukaj.vip/'

class ZalukajVip(CBaseHostClass):
    
    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'zalukaj.vip', 'cookie':'zalukaj.vip.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.MAIN_URL = 'https://zalukaj.vip/'
        self.DEFAULT_ICON_URL = 'https://zalukaj.vip/wp-content/uploads/2019/12/logo_fit.png'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT':'1', 'Accept': 'text/html', 'Accept-Encoding':'gzip, deflate', 'Referer':self.getMainUrl(), 'Origin':self.getMainUrl()}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update( {'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding':'gzip, deflate', 'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8', 'Accept':'application/json, text/javascript, */*; q=0.01'} )
        
        self.defaultParams = {'header':self.HTTP_HEADER, 'with_metadata':True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.ajaxParams = {'header':self.AJAX_HEADER, 'with_metadata':True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.MAIN_CAT_TAB = [{'category':'list_g',             'title': 'Filmy',           'url':self.getFullUrl('/movies/')},
                             {'category':'slist_a',            'title': 'Seriale',         'url':self.getFullUrl('/tv-shows-2/')},
                             {'category':'search',             'title': _('Search'),       'search_item':True},
                             {'category':'search_history',     'title': _('Search history')} ]

        self.cacheMovieFilters = {'a':[], 'm':[], 'g':[], 'y':[], 'v':[]}
        self.loggedIn = None
        self.login    = ''
        self.password = ''
        self.loginMessage = ''
        
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
        dat = self.cm.ph.getDataBeetwenMarkers(data, '<div id="vodi_tv_shows_letter_filter-1"', '</ul>', False)[1]
        dat = re.compile('<li[^>]*?><a[^>]*?letter_filter=([^"]+?)"[^>]*?>(.+?)</span>').findall(dat)
        for item in dat:
            self.cacheMovieFilters['a'].append({'title': self.cleanHtmlStr(item[1]), 'a': item[0]})

        # fill g
        dat = self.cm.ph.getDataBeetwenMarkers(data, '<div id="masvideos_movies_filter_widget-1"', '</ul>', False)[1]
        dat = re.compile('<li[^>]*?><a[^>]*?filter_genre=([^&]+?)&[^>]*?>(.+?)</li>').findall(dat)
        for item in dat:
            self.cacheMovieFilters['g'].append({'title': self.cleanHtmlStr(item[1]), 'g': item[0]})
            
        # fill v
#        dat = self.cm.ph.getDataBeetwenMarkers(data, '<div id="masvideos_movies_year_filter-1"', '</ul>', False)[1]
#        dat = re.compile('<li[^>]*?><a[^>]*?filter_genre=([^"]+?)"[^>]*?>(.+?)</li>').findall(dat)
#        for item in dat:
#            self.cacheMovieFilters['v'].append({'title': self.cleanHtmlStr(item[1]), 'v': item[0]})
            
        # fill y
        dat = self.cm.ph.getDataBeetwenMarkers(data, '<div id="masvideos_movies_year_filter-1"', '</ul>', False)[1]
        dat = re.compile('<li[^>]*?><a[^>]*?year_filter=([^"]+?)"[^>]*?>(.+?)</li>').findall(dat)
        for item in dat:
            self.cacheMovieFilters['y'].append({'title': self.cleanHtmlStr(item[1]), 'y': item[0]})
            
        # fill m
        dat = self.cm.ph.getDataBeetwenMarkers(data, '<select name="orderby"', '</select>', False)[1]
        dat = re.compile('<option[^>]+?value="([^"]+?)"[^>]*?>(.+?)</option>').findall(dat)
        for item in dat:
            self.cacheMovieFilters['m'].append({'title': self.cleanHtmlStr(item[1]), 'm': item[0]})    

    def listMovieFilters(self, cItem, category):
        printDBG("zalukaj.vip.listMovieFilters cItem[%s]" % cItem)
        
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
        printDBG("zalukaj.vip.listsTab")
        for item in tab:
            params = dict(cItem)
            if None != category:
                params['category'] = category
            params.update(item)
            self.addDir(params)

    def listMovies(self, cItem):
        printDBG("zalukaj.vip.listMovies [%s]" % cItem)

        http_params = dict(self.defaultParams)
        http_params['header'] = self.HTTP_HEADER

        page = cItem.get('page', 1)

        load = {}
        for item in ['a', 'm', 'g', 'y', 'v']:
            if item in cItem:
                load[item] = cItem[item]
            else:
                load[item] = ''

        if '?s=' in cItem['url']:
            sts, data = self.getPage(cItem['url'] % page, http_params)
        else:
            sts, data = self.getPage(cItem['url'] + 'page/%s/?orderby=%s&year_filter=%s&filter_genre=%s&query_type_genre=or&letter_filter=%s' % (page, load['m'], load['y'], load['g'], load['a']), http_params)
        if not sts: return

        nextPage = self.cm.ph.getDataBeetwenMarkers(data, '<a class="next page-numbers"', '</a>', False)[1]

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'vodi-archive-wrapper'), ('<div', '>', 'page-control-bar-bottom'))[1]
        tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'movie__poster'), ('<div', '>', 'dropdown-menu'))
        if len(tmp) == 0: tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', '--poster'), ('<div', '>', 'dropdown-menu'))
        for item in tmp:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<h3', '>'), ('</h3', '>'), False)[1])
            desc = self.cleanHtmlStr(item)
            params = dict(cItem)
            if '/tv-show/' in url:
                params = {'good_for_fav':True, 'name':'category', 'category':'list_series', 'url':url, 'title':title, 'desc':desc, 'icon':icon}
                self.addDir(params)
            else:
                params = {'good_for_fav':True, 'url':url, 'title':title, 'desc':desc, 'icon':icon}
                self.addVideo(params)

        if nextPage:
            params = dict(cItem)
            params.update({'title':_('Next page'), 'url':cItem['url'], 'page':page + 1})
            self.addDir(params)

    def listSeries(self, cItem):
        printDBG("zalukaj.vip.listSeries [%s]" % cItem)
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        self.setMainUrl(data.meta['url'])

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'episode__poster'), ('</h3', '>'))
        for item in data:
#            printDBG("zalukaj.vip.listSeries item %s" % item)
            url   = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<h3', '>'), ('</h3', '>'), False)[1])
            params = {'good_for_fav':True, 'url':url, 'title':title, 'icon':icon}
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("zalukaj.vip.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        
        cItem = dict(cItem)
        if searchType == 'movies':
            cItem['url'] = self.getFullUrl('page/%s/?s={0}&post_type=movie'.format(searchPattern))
        else:
            cItem['url'] = self.getFullUrl('page/%s/?s={0}&post_type=tv_show'.format(searchPattern))
        cItem['category'] = 'list_movies'
        self.listMovies(cItem)
       
    def getLinksForVideo(self, cItem):
        printDBG("zalukaj.vip.getLinksForVideo [%s]" % cItem)
        urlTab = []
        
        sts, data = self.getPage(cItem['url'])
        if not sts: return

        tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<iframe', '>'), ('</iframe', '>'))
        for item in tmp:
            url  = self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0]
            urlTab.append({'name':'name', 'url':self.getFullUrl(url), 'need_resolve':1})

        return urlTab
        
    def getVideoLinks(self, baseUrl):
        printDBG("zalukaj.vip.getVideoLinks [%s]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
                        
        return self.up.getVideoLinkExt(baseUrl)

    def getArticleContent(self, cItem):
        printDBG("zalukaj.vip.getArticleContent [%s]" % cItem)
        itemsList = []

        sts, data = self.cm.getPage(cItem['url'])
        if not sts: return []

        title = ''
        icon  = ''

        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div class="movie__description">', '</div>', False)[1])
        itemsList.append((_('Info'), self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<span class="movie__meta--genre">', '</span>', False)[1])))

        if title == '': title = cItem['title']
        if icon  == '': icon  = cItem.get('icon', '')
        if desc  == '': desc  = cItem.get('desc', '')

        return [{'title':self.cleanHtmlStr( title ), 'text': self.cleanHtmlStr( desc ), 'images':[{'title':'', 'url':self.getFullUrl(icon)}], 'other_info':{'custom_items_list':itemsList}}]

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('zalukaj.vip.handleService start')
        
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        
        name     = self.currItem.get("name", None)
        category = self.currItem.get("category", '')
        printDBG( "zalukaj.vip.handleService: ---------> name[%s], category[%s] " % (name, category) )
        searchPattern = self.currItem.get("search_pattern", searchPattern)
        self.currList = []
        
        if None == name:
            self.listsTab(self.MAIN_CAT_TAB, {'name':'category'})
    #FILMS CATEGORIES
        elif 'list_g' == category:
#            self.listMovieFilters(self.currItem, 'list_v')
#        elif 'list_v' == category:
            self.listMovieFilters(self.currItem, 'list_y')
        elif 'list_y' == category:
            self.listMovieFilters(self.currItem, 'list_m')
        elif 'list_m' == category:
            self.listMovieFilters(self.currItem, 'list_movies')
        elif 'list_movies' == category:
            self.listMovies(self.currItem)
    #LIST SERIALS
#        elif 'slist_g' == category:
#            self.listMovieFilters(self.currItem, 'slist_a')
        elif 'slist_a' == category:
#            self.listMovieFilters(self.currItem, 'slist_y')
#        elif 'slist_y' == category:
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
            self.listSearchResult(cItem, searchPattern, searchType)
    #HISTORIA SEARCH
        elif category == "search_history":
            self.listsHistory({'name':'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, ZalukajVip(), True, [])

    def getSearchTypes(self):
        searchTypesOptions = []
        searchTypesOptions.append((_("Movies"), "movies"))
        searchTypesOptions.append((_("Series"), "series"))
        return searchTypesOptions

    def withArticleContent(self, cItem):
        return True

