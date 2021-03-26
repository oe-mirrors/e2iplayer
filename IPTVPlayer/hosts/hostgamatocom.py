# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify
###################################################

###################################################
# FOREIGN import
###################################################
import urllib
try:    import json
except Exception: import simplejson as json
from datetime import datetime
###################################################


def gettytul():
    return 'https://gamato-movies.com/'
    
class GamatoMovies(CBaseHostClass):
 
    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'GamatoMovies.tv', 'cookie':'gamatomoviescom.cookie'})
        self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        
        self.HEADER = {'User-Agent': 'Mozilla/5.0', 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update( {'X-Requested-With': 'XMLHttpRequest'} )
        
        self.MAIN_URL = 'http://gamato-movies.com/'
        
        self.DEFAULT_ICON_URL = self.MAIN_URL + 'assets/uploads/images/aaw81QHKtm.png'
        
        self.MAIN_CAT_TAB = [{'category':'movies',            'title': _('Movies'),                       'priv_type':'movie',  'url':self.getFullUrl('movies'),  'icon':self.DEFAULT_ICON_URL},
                             {'category':'series',            'title': _('Series'),                       'priv_type':'series', 'url':self.getFullUrl('series'),  'icon':self.DEFAULT_ICON_URL},
                             {'category':'search',            'title': _('Search'), 'search_item':True,         'icon':self.DEFAULT_ICON_URL},
                             {'category':'search_history',    'title': _('Search history'),                     'icon':self.DEFAULT_ICON_URL} 
                            ]
        
        self.cacheFilters = {}
        self.cacheLinks = {}
        self.cacheSeries = {}
        
    def getStr(self, item, key):
        if key not in item: return ''
        if item[key] == None: return ''
        return str(item[key])
        
    def fillFilters(self, cItem):
        self.cacheFilters = {}
        sts, data = self.cm.getPage(cItem['url'])
        if not sts: return
        self.cacheFilters['token'] = self.cm.ph.getSearchGroups(data, '''token\s*:\s*['"]([^'^"]+?)['"]''')[0]
        
        def addFilter(data, key, addAny, titleBase):
            self.cacheFilters[key] = []
            for item in data:
                value = self.cm.ph.getSearchGroups(item, '''value=['"]([^'^"]+?)['"]''')[0]
                if value == '': continue
                title = self.cleanHtmlStr(item)
                self.cacheFilters[key].append({'title':titleBase + title, key:value})
            if addAny and len(self.cacheFilters[key]):
                self.cacheFilters[key].insert(0, {'title':titleBase + _('any')})
        
        # genres
        tmpData = self.cm.ph.getDataBeetwenMarkers(data, '<select name="genres"', '</select')[1]
        tmpData = self.cm.ph.getAllItemsBeetwenMarkers(tmpData, '<option', '</option>', withMarkers=True)
        addFilter(tmpData, 'genres', True, _('Genre: '))
        
        # order
        tmpData = self.cm.ph.getDataBeetwenMarkers(data, '<select name="sort" ', '</select>')[1]
        tmpData = self.cm.ph.getAllItemsBeetwenMarkers(tmpData, '<option ', '</option>', withMarkers=True)
        addFilter(tmpData, 'order', False, _('Order by: '))
        
        # year
        if cItem['priv_type'] == 'movie':
            self.cacheFilters['year'] = []
            year = datetime.now().year
            while year >= 1978:
                self.cacheFilters['year'].append({'title': _('Year: ') + str(year), 'year': year})
                year -= 1
            if len(self.cacheFilters['year']):
                self.cacheFilters['year'].insert(0, {'title':_('Year: ') + _('any')})

        # Rating
        tmpData = self.cm.ph.getDataBeetwenMarkers(data, '<select name="minRating"', '</select>')[1]
        tmpData = self.cm.ph.getAllItemsBeetwenMarkers(tmpData, '<option ', '</option>', withMarkers=True)
        addFilter(tmpData, 'min_rating', True, _('Score at least: '))
        
    def listFilter(self, cItem, filters):
        params = dict(cItem)
        idx = params.get('f_idx', 0)
        params['f_idx'] = idx + 1
        
        if idx == 0:
            self.fillFilters(cItem)
        
        tab = self.cacheFilters.get(filters[idx], [])
        self.listsTab(tab, params)
        
    def listItems(self, cItem, nextCategory):
        printDBG("GamatoMovies.listItems")
        perPage = 18
        page = cItem.get('page', 1)
        baseUrl = 'titles/paginate?_token=' + self.cacheFilters['token'] + '&perPage={0}'.format(perPage) + '&type={0}'.format(cItem['priv_type']) + '&availToStream=true' + '&page={0}'.format(page)
        if 'genres' in cItem:
            baseUrl += '&genres%5B%5D={0}'.format(urllib.quote(cItem['genres']))
        if 'order' in cItem:
            baseUrl += '&order={0}'.format(cItem['order'])
        if 'year' in cItem:
            baseUrl += '&after={0}-12-31'.format(cItem['year']-1)
            baseUrl += '&before={0}-1-1'.format(cItem['year']+1)
        if 'min_rating' in cItem:
            baseUrl += '&minRating={0}'.format(cItem['min_rating'])
        if 'query' in cItem:
            baseUrl += '&query={0}'.format(cItem['query'])
            
        sts, data = self.cm.getPage(self.getFullUrl(baseUrl), {'header':self.AJAX_HEADER})
        if not sts: return
        try:
            data = byteify(json.loads(data))
            for item in data['items']:
                try:
                    if item['type'] == 'movie':
                        url = 'movies'
                    else: url = item['type']
                    url   = self.getFullUrl(url + '/'  + str(item['id']))
                    title = '{0} ({1})'.format(self.getStr(item, 'title'), self.getStr(item, 'year'))
                    desc  = '{0}/10|{1}[/br]{2}'.format(self.getStr(item, 'imdb_rating'), self.getStr(item, 'genre'), self.getStr(item, 'plot'))
                    params = dict(cItem)
                    params.update({'good_for_fav': True, 'title':title, 'url':url, 'priv_type':self.getStr(item, 'type'), 'priv_id':self.getStr(item, 'id'), 'icon':self.getStr(item, 'poster'), 'desc':desc})
                    if item['type'] == 'movie':
                        self.addVideo(params)
                    else:
                        params['category'] = nextCategory
                        self.addDir(params)
                except Exception:
                    printExc()
            if data['totalItems'] > page * perPage:
                params = dict(cItem)
                params.update({'title':_('Next page'), 'page':page+1})
                self.addDir(params)
        except Exception:
            printExc()
     
    def getSeriesInfo(self, data):
        printDBG("GamatoMovies.getSeriesInfo")
        info = {}
        data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="group series-info"', '</div>')[1]
        info['title'] = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<h1', '</h1>')[1])
        info['icon']  = self.getFullUrl( self.cm.ph.getSearchGroups(data, 'src="([^"]+?)"')[0] )
        info['desc']  = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<p class="description"', '</p>')[1].split('</strong>')[-1])
        info['full_desc']  = self.cleanHtmlStr(data.split('</h1>')[-1])
        keysMap = {'Gatunek:':'genre'}
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<strong>', '<br/>', withMarkers=True)
        for item in data:
            tmp   = item.split('</strong>')
            key   = self.cleanHtmlStr(tmp[0])
            value = self.cleanHtmlStr(tmp[-1])
            if key in keysMap:
                info[keysMap[key]] = value
        return info
        
    def listSeasons(self, cItem, nextCategory):
        printDBG("GamatoMovies.listSeasons")
        sts, data = self.cm.getPage(cItem['url'])
        if not sts: return
        
        data = self.cm.ph.getDataBeetwenMarkers(data, 'vars.title =', '};', False)[1].strip() + '}'
        
        try:
            trailerUrl = self.cm.ph.getSearchGroups(data, '''"trailer"\s*:\s*(['"]http[^'^"]+?['"])''')[0] 
            trailerUrl = byteify(json.loads(trailerUrl))
            if self.cm.isValidUrl(trailerUrl):
                params = dict(cItem)
                params.update({'good_for_fav': True, 'title':cItem['title'] + ' - ' + _('trailer'), 'priv_type':'trailer', 'url':trailerUrl})
                self.addVideo(params)
        except Exception:
            printExc()
                
        try:
            data = byteify(json.loads(data))
            for item in data['season']:
                title = self.getStr(item, 'title')
                if '' == title: title = _('Season {0}'.format(item['number']))
                url   = self.getFullUrl(cItem['url'] + '/seasons/'  + str(item['number']))
                overview = self.getStr(item, 'overview')
                if overview == '':
                    desc = cItem['desc']
                else:
                    desc  = '{0}[/br]{1}'.format(self.getStr(item, 'release_date'), overview)
                params = {'good_for_fav': True, 'category':nextCategory, 'priv_type':cItem['priv_type'], 'title':title, 'url':url, 'priv_stitle':cItem['title'], 'priv_snum':self.getStr(item, 'number'), 'priv_id':self.getStr(item, 'id'), 'icon':self.getStr(item, 'poster'), 'desc':desc}
                self.addDir(params)
        except Exception:
            printExc()
        
    def listEpisodes(self, cItem):
        printDBG("GamatoMovies.listEpisodes")
        sts, data = self.cm.getPage(cItem['url'])
        if not sts: return
        
        sNum = cItem['priv_snum']
        
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li class="media">', '</li>', withMarkers=True)
        for item in data:
            url    = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            status = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<a', '</a>')[1])
            title  = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h4', '</h4>')[1])
            icon   = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0])
            desc   = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<strong', '</div>')[1].replace('</strong>', '[/br]'))
            eNum   = url.split('/')[-1]
            title  = cItem['priv_stitle'] + ': s{0}e{1} {2}'.format(sNum.zfill(2), eNum.zfill(2), title)
            params = {'good_for_fav': True, 'priv_type':cItem['priv_type'], 'title':title, 'url':url, 'icon':icon, 'desc':status + '[/br]' + desc}
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("GamatoMovies.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        if 'token' not in self.cacheFilters:
            sts, data = self.cm.getPage(self.MAIN_URL)
            if not sts: return
            self.cacheFilters['token'] = self.cm.ph.getSearchGroups(data, '''token\s*:\s*['"]([^'^"]+?)['"]''')[0]
        cItem = dict(cItem)
        cItem.update({'priv_type':searchType, 'query':urllib.quote_plus(searchPattern)})
        self.listItems(cItem, 'list_seasons')
                		
    def getLinksForVideo(self, cItem):
        printDBG("GamatoMovies.getLinksForVideo [%s]" % cItem)
        urlTab = []
        
        if 'trailer' == cItem['priv_type']:
            return self.up.getVideoLinkExt(cItem['url'])
            
        urlTab = self.cacheLinks.get(cItem['url'],  [])
        if len(urlTab): return urlTab
        self.cacheLinks = {}
        
        sts, data = self.cm.getPage(cItem['url'])
        if not sts: return []
        
        jsonData = self.cm.ph.getDataBeetwenMarkers(data, 'vars.title =', '};', False)[1].strip() + '}'
        if 'movie' == cItem['priv_type']:
            try:
                trailerUrl = self.cm.ph.getSearchGroups(jsonData, '''"trailer"\s*:\s*(['"]http[^'^"]+?['"])''')[0] 
                trailerUrl = byteify(json.loads(trailerUrl))
                if self.cm.isValidUrl(trailerUrl):
                    urlTab.append({'name':_('Trailer'), 'url':trailerUrl, 'need_resolve':1})
            except Exception:
                printExc()
        
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<tr data-id=', '</tr>', withMarkers=True)
        for item in data:
            name = self.cleanHtmlStr(item)
            url  = self.cm.ph.getSearchGroups(item, '''playVideo[^'^"]+?['"](http[^'^"]+?)['"]''')[0].strip()
            urlTab.append({'name':name, 'url':url, 'need_resolve':1})
        #try:
        #    data = '[' + self.cm.ph.getDataBeetwenMarkers(data, '"link":[', ']', False)[1] + ']'
        #    printDBG(data)
        #    data = byteify(json.loads(data))
        #    for item in data:
        #        url = self.getStr(item, 'url')
        #        if not self.cm.isValidUrl(url): continue
        #        name = '{0} {1} - {2}'.format(self.getStr(item, 'created_at'), self.getStr(item, 'quality').lower(), self.getStr(item, 'label').lower())
        #        urlTab.append({'name':name, 'url':url, 'need_resolve':1})
        #except Exception:
        #    printExc()
        #    return []
        
        self.cacheLinks[cItem['url']] = urlTab
        return urlTab
        
    def getVideoLinks(self, videoUrl):
        printDBG("GamatoMovies.getVideoLinks [%s]" % videoUrl)
        urlTab = []
        
        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            key = self.cacheLinks.keys()[0]
            for idx in range(len(self.cacheLinks[key])):
                if videoUrl in self.cacheLinks[key][idx]['url']:
                    if not self.cacheLinks[key][idx]['name'].startswith('*'):
                        self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name']
                    break
        
        shortUri = videoUrl
        domain = self.up.getDomain(videoUrl)
        sts, data = self.cm.getPage(videoUrl)
        if sts and 'gosfd.eu' in data:
            videoUrl = videoUrl.replace(domain, 'gosfd.eu')
            domain = 'gosfd.eu'
        
        if 'gosfd.eu' in domain or 'streamtape.net' in domain:
            from Plugins.Extensions.IPTVPlayer.libs.unshortenit import unshorten
            uri, sts = unshorten(videoUrl)
            videoUrl = str(uri)
            if not self.cm.isValidUrl(videoUrl):
                SetIPTVPlayerLastHostError(str(sts))
            else:
                # set resolved uri in cache
                if len(self.cacheLinks.keys()):
                    key = self.cacheLinks.keys()[0]
                    for idx in range(len(self.cacheLinks[key])):
                        if shortUri in self.cacheLinks[key][idx]['url']:
                            self.cacheLinks[key][idx]['url'] = videoUrl
                            break
        if self.cm.isValidUrl(videoUrl):
            return self.up.getVideoLinkExt(videoUrl)
        
        return urlTab
        
    def getFavouriteData(self, cItem):
        printDBG('GamatoMovies.getFavouriteData')
        return json.dumps(cItem) 
        
    def getLinksForFavourite(self, fav_data):
        printDBG('GamatoMovies.getLinksForFavourite')
        links = []
        try:
            cItem = byteify(json.loads(fav_data))
            links = self.getLinksForVideo(cItem)
        except Exception: printExc()
        return links
        
    def setInitListFromFavouriteItem(self, fav_data):
        printDBG('GamatoMovies.setInitListFromFavouriteItem')
        try:
            params = byteify(json.loads(fav_data))
        except Exception: 
            params = {}
            printExc()
        self.addDir(params)
        return True
        
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
        elif category in ['movies', 'series']:
            if category == 'movies': filtersTab = ['genres', 'order', 'year'] #min_rating
            else: filtersTab = ['genres', 'order']
            idx = self.currItem.get('f_idx', 0)
            if idx < len(filtersTab):
                self.listFilter(self.currItem, filtersTab)
            else:
                self.listItems(self.currItem, 'list_seasons')
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
        CHostBase.__init__(self, GamatoMovies(), True, []) #[CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO]


