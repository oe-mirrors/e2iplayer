# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute
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
    return 'https://watch-movies.pl/'

class watchMovies(CBaseHostClass):
    
    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'watch-movies', 'cookie':'watch-movies.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.MAIN_URL = 'https://watch-movies.pl/'
#        self.DEFAULT_ICON_URL = 'https://watch-movies.pl/'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT':'1', 'Accept': 'text/html', 'Accept-Encoding':'gzip, deflate', 'Referer':self.getMainUrl(), 'Origin':self.getMainUrl()}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update( {'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding':'gzip, deflate', 'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8', 'Accept':'application/json, text/javascript, */*; q=0.01'} )

        self.cacheMovieFilters = {'cats':[], 'sort':[], 'years':[], 'az':[]}        
        self.cacheLinks    = {}
        self.defaultParams = {'header':self.HTTP_HEADER, 'with_metadata':True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

    def getPage(self, baseUrl, addParams = {}, post_data = None):
        if addParams == {}: addParams = dict(self.defaultParams)
        origBaseUrl = baseUrl
        baseUrl = self.cm.iriToUri(baseUrl)
        def _getFullUrl(url):
            if self.cm.isValidUrl(url): return url
            else: return urlparse.urljoin(baseUrl, url)
        addParams['cloudflare_params'] = {'domain':self.up.getDomain(baseUrl), 'cookie_file':self.COOKIE_FILE, 'User-Agent':self.USER_AGENT, 'full_url_handle':_getFullUrl}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)
        
    def setMainUrl(self, url):
        if self.cm.isValidUrl(url):
            self.MAIN_URL = self.cm.getBaseUrl(url)
    
    def listMainMenu(self, cItem):
        printDBG("watchMovies.listMainMenu")

        MAIN_CAT_TAB = [{'category':'list_items',     'title': _('Movies'),          'url':self.getFullUrl('/?post_type=movies')},
                        {'category':'list_items',     'title': _('Series'),          'url':self.getFullUrl('/?post_type=tvshows')},
                        {'category':'list_years',     'title': _('Movies by year'),  'url':self.MAIN_URL},
                        {'category':'list_cats',      'title': _('Movies genres'),   'url':self.MAIN_URL},
#                        {'category':'list_top',       'title': _('Top rated'),       'url':self.getFullUrl('/imdb/')},
#                        {'category':'list_az',        'title': _('Alphabetically'), 'url':self.MAIN_URL},
                        {'category':'search',         'title': _('Search'),         'search_item':True}, 
                        {'category':'search_history', 'title': _('Search history')},]
        self.listsTab(MAIN_CAT_TAB, cItem)
    
    ###################################################
    def _fillMovieFilters(self):
        self.cacheMovieFilters = { 'cats':[], 'sort':[], 'years':[], 'az':[]}

        sts, data = self.getPage(self.MAIN_URL)
        if not sts: return
        
        # fill cats
        dat = self.cm.ph.getDataBeetwenMarkers(data, '<nav class="genres">', '</nav>', False)[1]
        dat = re.compile('<a[^>]+?href="([^"]+?)"[^>]*?>(.+?)</a>').findall(dat)
        for item in dat:
            self.cacheMovieFilters['cats'].append({'title': self.cleanHtmlStr(item[1]), 'url': item[0]})
            
        # fill years
        dat = self.cm.ph.getDataBeetwenMarkers(data, '<nav class="releases">', '</nav>', False)[1]
        dat = re.compile('<a[^>]+?href="([^"]+?)"[^>]*?>(.+?)</a>').findall(dat)
        for item in dat:
            self.cacheMovieFilters['years'].append({'title': self.cleanHtmlStr(item[1]), 'url': item[0]})

        # fill az
        dat = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="glossary">', '</ul>', False)[1]
        dat = re.compile('<a[^>]+?href="([^"]+?)"[^>]*?>(.+?)</a>').findall(dat)
        for item in dat:
            self.cacheMovieFilters['az'].append({'title': self.cleanHtmlStr(item[1]), 'url': item[0]})
    
    ###################################################
    def listMovieFilters(self, cItem, category):
        printDBG("watchMovies.listMovieFilters")
        
        filter = cItem['category'].split('_')[-1]
        if 0 == len(self.cacheMovieFilters[filter]):
            self._fillMovieFilters()
        if len(self.cacheMovieFilters[filter]) > 0:
            filterTab = []
            filterTab.extend(self.cacheMovieFilters[filter])
            self.listsTab(filterTab, cItem, category)
        
    def listsTab(self, tab, cItem, category=None):
        printDBG("watchMovies.listsTab")
        for item in tab:
            params = dict(cItem)
            if None != category:
                params['category'] = category
            params.update(item)
            self.addDir(params)

    def listItems(self, cItem):
        printDBG("watchMovies.listItems %s" % cItem)
        page = cItem.get('page', 1)

        url  = cItem['url']

        sts, data = self.getPage(url)
        if not sts: return
        self.setMainUrl(data.meta['url'])
            
        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'pagination'), ('</div', '>'))[1]
        nextPage = self.cm.ph.getSearchGroups(nextPage, '''<a[^>]+?href=['"]([^'^"]+?)['"][^>]*?>%s</a>''' % (page + 1))[0]
        
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<article', '>'), ('</article', '>'))

        for item in data:
#            printDBG("watchMovies.listItems item %s" % item)
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'title'), ('</div', '>'), False)[1])
            if 'post-featured' in item:
#                title = '[' + _('Featured') + '] ' + self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<h3', '>'), ('</h3', '>'), False)[1])
                continue
            desc = self.cleanHtmlStr(item)
            if 'tvshows' in url:
                params = {'good_for_fav':True,'category':'list_series', 'url':url, 'title':title, 'desc':desc, 'icon':icon}
                self.addDir(params)
            else:
                params = {'good_for_fav':True, 'url':url, 'title':title, 'desc':desc, 'icon':icon}
                self.addVideo(params)
            
        if nextPage != '':
            params = dict(cItem)
            params.update({'title':_('Next page'), 'url':self.getFullUrl(nextPage), 'page':page + 1})
            self.addDir(params)

    def listTop(self, cItem):
        printDBG("watchMovies.listTop %s" % cItem)

        url  = cItem['url']

        sts, data = self.getPage(url)
        if not sts: return
        self.setMainUrl(data.meta['url'])
            
#        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'top-imdb-item'), ('</a></div></div', '>'))
        data = self.cm.ph.getDataBeetwenMarkers(data, '<header class="top_imdb">', '<div class="sidebar scrolling">')[1]
        data = data.split("<div class='image'>")

        for item in data:
#            printDBG("watchMovies.listItems item %s" % item)
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            if url == '': continue
            icon   = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''')[0])
            title  = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'title'), ('</div', '>'), False)[1])
            rating = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'rating'), ('</div', '>'), False)[1])
            desc = _('Rating') + ' ' + rating + '[/br]' + title
            if '/tvshows/' in url:
                params = {'good_for_fav':True,'category':'list_series', 'url':url, 'title':title, 'desc':desc, 'icon':icon}
                self.addDir(params)
            else:
                params = {'good_for_fav':True, 'url':url, 'title':title, 'desc':desc, 'icon':icon}
                self.addVideo(params)

    def listSeries(self, cItem):
        printDBG("watchMovies.listSeries %s" % cItem)
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        self.setMainUrl(data.meta['url'])

#        data = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'episodios'), ('</ul', '>'))[1]
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<li', '>', 'mark-'), ('</li', '>'))
        for item in data:
#            printDBG("watchMovies.listSeries item %s" % item)
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''')[0])
            if url == '': continue
            title = self.cleanHtmlStr(item)
            params = {'good_for_fav':True, 'url':url, 'title':title, 'icon':icon}
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("watchMovies.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        url = self.getFullUrl('/?s=%s') % urllib.quote_plus(searchPattern)
        params = {'name':'category', 'category':'list_items', 'good_for_fav':False, 'url':url}
        self.listItems(params)
        
    def getLinksForVideo(self, cItem):
        printDBG("watchMovies.getLinksForVideo [%s]" % cItem)
                
        cacheKey = cItem['url']
        cacheTab = self.cacheLinks.get(cacheKey, [])
        if len(cacheTab): return cacheTab
        
        self.cacheLinks = {}
        
        params = dict(self.defaultParams)
        params['header'] = dict(params['header'])
        
        cUrl = cItem['url']
        url = cItem['url']
        
        retTab = []
            
        params['header']['Referer'] = cUrl
        sts, data = self.getPage(url, params)
        if not sts: return []

#        sts, jscode = self.getPage('https://watch-movies.pl/js/bootstrap.php', params)
#        if not sts: return []

        cUrl = data.meta['url']
        self.setMainUrl(cUrl)

        data = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'playeroptionsul'), ('</ul', '>'))[1]
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<li', '>'),  ('</li', '>'))
    
        for item in data:
            printDBG("watchMovies.getLinksForVideo item[%s]" % item)
            data_type = self.cm.ph.getSearchGroups(item, '''data-type=['"]([^"^']+?)['"]''', 1, True)[0]
            data_post = self.cm.ph.getSearchGroups(item, '''data-post=['"]([^"^']+?)['"]''', 1, True)[0]
            data_nume = self.cm.ph.getSearchGroups(item, '''data-nume=['"]([^"^']+?)['"]''', 1, True)[0]
            post_data = {'action':'doo_player_ajax', 'post':data_post, 'nume':data_nume, 'type':data_type}
            sts, data = self.getPage('https://watch-movies.pl/wp-admin/admin-ajax.php', params, post_data)
            if not sts: return []
            printDBG("watchMovies.getLinksForVideo data ajax[%s]" % item)
            playerUrl = self.cm.ph.getSearchGroups(data, '''src=['"]([^"^']+?)['"]''', 1, True)[0]
            retTab.append({'name':self.up.getHostName(playerUrl), 'url':strwithmeta(playerUrl, {'Referer':url}), 'need_resolve':1})
            
        if len(retTab):
            self.cacheLinks[cacheKey] = retTab
        return retTab
        
    def getVideoLinks(self, baseUrl):
        printDBG("watchMovies.getVideoLinks [%s]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
        urlTab = []
        
        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if baseUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name'] + '*'
                        break
                        
        return self.up.getVideoLinkExt(baseUrl)

    def getArticleContent(self, cItem):
        printDBG("watchMovies.getArticleContent [%s]" % cItem)
        itemsList = []

        sts, data = self.cm.getPage(cItem['url'])
        if not sts: return []

        title = cItem['title']
        icon = cItem.get('icon', '')
        desc = cItem.get('desc', '')

        title = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'sheader'), ('</h1', '>'), False)[1]
        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<span class="valor">', '</span>', True)[1])
        if tmp != '': title = title + ' - Org: ' + tmp
        icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(title, '''src=['"]([^"^']+?)['"]''', 1, True)[0])
        desc = self.cm.ph.getDataBeetwenMarkers(data, '<div id="info"', '</p>', True)[1]
        desc = self.cm.ph.getDataBeetwenMarkers(desc, '<p>', '</p>', True)[1]
        itemsList.append((_('Info'), self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div class="extra">', '</div>', True)[1])))
        itemsList.append((_('Author'), self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div class="person">', '<div class="caracter">', True)[1])))
        itemsList.append((_('Genres'), self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div class="sgeneros">', '</div>', True)[1])))

        if title == '': title = cItem['title']
        if icon  == '': icon  = cItem.get('icon', '')
        if desc  == '': desc  = cItem.get('desc', '')

        return [{'title':self.cleanHtmlStr( title ), 'text': self.cleanHtmlStr( desc ), 'images':[{'title':'', 'url':self.getFullUrl(icon)}], 'other_info':{'custom_items_list':itemsList}}]
        
    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('handleService start')
        
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name     = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode     = self.currItem.get("mode", '')
        
        printDBG( "handleService: |||| name[%s], category[%s] " % (name, category) )
        self.cacheLinks = {}
        self.currList = []
        
    #MAIN MENU
        if name == None and category == '':
            rm(self.COOKIE_FILE)
            self.listMainMenu({'name':'category'})
        elif 'list_cats' == category:
            self.listMovieFilters(self.currItem, 'list_items')
        elif 'list_years' == category:
            self.listMovieFilters(self.currItem, 'list_items')
        elif 'list_az' == category:
            self.listMovieFilters(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem)            
        elif 'list_top' == category:
            self.listTop(self.currItem)
        elif category == 'list_series':
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
        CHostBase.__init__(self, watchMovies(), True, [])
    
    def withArticleContent(self, cItem):
        return True
