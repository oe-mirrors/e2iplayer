# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute
###################################################

###################################################
# FOREIGN import
###################################################
import re
try:
    import json
except Exception:
    import simplejson as json
###################################################

def gettytul():
    return 'https://forja.tn/'

class ForjaTN(CBaseHostClass):
    
    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'forja.tn', 'cookie':'forja.tn.cookie'})
        self.DEFAULT_ICON_URL = 'https://forja.tn/logoHeader.png'
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.MAIN_URL = 'https://forja.tn/'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT':'1', 'Accept': 'text/html', 'Accept-Encoding':'gzip, deflate'}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update( {'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding':'gzip, deflate', 'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8', 'Accept':'application/json, text/javascript, */*; q=0.01'} )
        
        self.cacheFilters  = {}
        self.cacheFiltersKeys = []
        self.cacheEpisodes = {}
        self.defaultParams = {'header':self.HTTP_HEADER, 'with_metadata':True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        
        self.MAIN_CAT_TAB = [{'category':'list_filters',   'title': _('Movies'),  'f_type':'movies',      'url':self.getFullUrl('/movies')},
                             {'category':'list_filters',   'title': _('Series'),  'f_type':'series',      'url':self.getFullUrl('/series')},
                             
                             {'category':'search',         'title': _('Search'),          'search_item':True}, 
                             {'category':'search_history', 'title': _('Search history')},
                            ]
        
    def getPage(self, baseUrl, addParams = {}, post_data = None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        origBaseUrl = baseUrl
        baseUrl = self.cm.iriToUri(baseUrl)
        addParams['cloudflare_params'] = {'cookie_file':self.COOKIE_FILE, 'User-Agent':self.USER_AGENT}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)
        
    def fillCacheFilters(self, cItem):
        printDBG("ForjaTN.fillCacheFilters")
        self.cacheFilters = {}
        self.cacheFiltersKeys = []
        
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        
        printDBG("==============================================================")
        
        data = re.sub("<!--[\s\S]*?-->", "", data)
        
        def addFilter(data, itemMarker, valMarker, key, allTitle=None):
            self.cacheFilters[key] = []
            for item in data:
                value = self.cm.ph.getSearchGroups(item, valMarker + '''="([^"]+?)"''')[0]
                title = self.cm.ph.rgetDataBeetwenMarkers2(item, '</%s>' % itemMarker, '>', False)[1]
                title = self.cleanHtmlStr(title)
                if value == '': 
                    if allTitle == None:
                        allTitle = title
                    continue
                self.cacheFilters[key].append({'title':title.title(), key:value})
                
            if len(self.cacheFilters[key]):
                if allTitle != None:
                    self.cacheFilters[key].insert(0, {'title':allTitle, key:''})
                self.cacheFiltersKeys.append(key)
                
        # genres
        key = 'f_genre'
        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<select', '>', 'genre-input'), ('</select', '>'), False)[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<option', '</option>')
        addFilter(tmp, 'option', 'value', key)
        
        # sortby
        key = 'f_sortby'
        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<select', '>', 'sort-input'), ('</select', '>'), False)[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<option', '</option>')
        addFilter(tmp, 'option', 'value', key)
        
        printDBG(self.cacheFilters)
        
    def listFilters(self, cItem, nextCategory):
        printDBG("ForjaTN.listFilters")
        cItem = dict(cItem)
        
        f_idx = cItem.get('f_idx', 0)
        if f_idx == 0:
            self.fillCacheFilters(cItem)
        
        if f_idx >= len(self.cacheFiltersKeys):
            return
        
        filter = self.cacheFiltersKeys[f_idx]
        f_idx += 1
        cItem['f_idx'] = f_idx
        if f_idx  == len(self.cacheFiltersKeys):
            cItem['category'] = nextCategory
        self.listsTab(self.cacheFilters.get(filter, []), cItem)
    
    def listMainMenu(self, cItem, nextCategory):
        printDBG("ForjaTN.listMainMenu")
        self.listsTab(self.MAIN_CAT_TAB, cItem)
        
    def listItems(self, cItem, nextCategory):
        printDBG("ForjaTN.listItems [%s]" % cItem)
        page = cItem.get('page', 1)
        type = cItem['f_type']
        
        post_data = {'page':page}
        post_data['title']  = cItem.get('f_title', '')
        post_data['genre']  = cItem.get('f_genre', '')
        post_data['sortby'] = cItem.get('f_sortby', '')
        
        url = '/api/' + type
        if type == 'movies':
            url += '?extended=short'
        else:
            post_data['no_data'] = 'true'
        
        params = dict(self.defaultParams)
        params['header'] = dict(self.AJAX_HEADER)
        params['header']['Referer'] = cItem['url']
        
        url = self.getFullUrl(url)
        sts, data = self.getPage(url, params, post_data)
        if not sts:
            return
        
        try:
            data = byteify(json.loads(data), '', True)
            for item in data[type]:
                icon   = self.getFullIconUrl(item.get('Poster', ''))
                title  = self.cleanHtmlStr(item.get('Title', ''))
                desc = []
                for t in ['Year', 'imdbRating', 'Genre']:
                    t = self.cleanHtmlStr(item.get(t, ''))
                    if t != '':
                        desc.append(t)
                desc = ' | '.join(desc) + '[/br]' + self.cleanHtmlStr(item.get('Plot', ''))
                id   = item.get('_id', '') 
                imdbID = item.get('imdbID', '') 
                url = self.getFullUrl('/%s/%s/' % (type[:-1], imdbID) )
                params = dict(cItem)
                params.update({'good_for_fav':True, 'category':nextCategory, 'title':title, 'url':url, '_id':id, 'imdb_id':imdbID, 'icon':icon, 'desc':desc})
                self.addDir(params)
        except Exception:
            printExc()
        
        if len(self.currList) >= 50:
            params = dict(cItem)
            params.update({'good_for_fav':False, 'title':_("Next page"), 'page':page+1})
            self.addDir(params)
        
    def exploreItem(self, cItem, nextCategory):
        printDBG("ForjaTN.exploreItem")
        self.cacheEpisodes = {}
        
        type = cItem['f_type']
        imdbID = cItem['imdb_id']
        
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        
        SetIPTVPlayerLastHostError( self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'medias_container'), ('</div', '>'), False)[1]) )
        
        if type == 'series':
            seasonsTab = []
            data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'episode-container'), ('</div', '>'))
            printDBG(data)
            for item in data:
                season = self.cm.ph.getSearchGroups(item, '''season=['"]([^'^"]+?)['"]''')[0]
                icon   = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''data\-original=['"]([^'^"]+?)['"]''')[0])
                url    = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''episode\-url=['"]([^'^"]+?)['"]''')[0])
                title  = '%s - %s' % (cItem['title'], self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''episode\-name=['"]([^'^"]+?)['"]''')[0]))
                if season not in seasonsTab:
                    self.cacheEpisodes[season] = []
                    seasonsTab.append(season)
                self.cacheEpisodes[season].append({'url':url, 'title':title, 'icon':icon})
            for season in seasonsTab:
                params = dict(cItem)
                params.update({'good_for_fav':False, 'category':nextCategory, 'title':season, 's_num':season})
                self.addDir(params)
        else:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"](https?://[^"^']*?youtube[^"^']+?)['"]''', 1, True)[0])
            if url != '':
                title = '%s - %s' % (cItem['title'], _("TRAILER"))
                params = dict(cItem)
                params.update({'good_for_fav':True, 'title':title, 'url':url, 'prev_url':cItem['url']})
                self.addVideo(params)
            
            if 'player.src' in data or 'streamSources' in data:
                params = dict(cItem)
                params.update({'good_for_fav':True, 'url':cItem['url']})
                self.addVideo(params)
            
    def listEpisodes(self, cItem):
        printDBG("ForjaTN.listEpisodes")
        
        sNum = cItem.get('s_num', '')
        tab = self.cacheEpisodes.get(sNum, [])
        for item in tab:
            params = dict(cItem)
            params.update({'good_for_fav':True, 'f_type':'episode'})
            params.update(item)
            self.addVideo(params)
        
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("ForjaTN.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['f_type'] = searchType
        cItem['f_title'] = searchPattern
        cItem['url'] = self.getFullUrl(searchType)
        self.listItems(cItem, 'explore_item')
        
    def getLinksForVideo(self, cItem):
        printDBG("ForjaTN.getLinksForVideo [%s]" % cItem)
        
        if 1 == self.up.checkHostSupport(cItem.get('url', '')):
            videoUrl = cItem['url'].replace('youtu.be/', 'youtube.com/watch?v=')
            return self.up.getVideoLinkExt(videoUrl)
        
        retTab = []
        subTracksTab = []
        
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return []
        
        cUrl = data.meta['url']
        
        if cItem.get('f_type', '') == 'episode':
            episodeId = cItem['url']
            if episodeId.endswith('/'):
                episodeId = episodeId[-1]
            episodeId = '/'.join(episodeId.split('/')[-2:])
            
            data = self.cm.ph.getDataBeetwenReMarkers(data, re.compile('''episodes\s*='''), re.compile('''];'''), False)[1]
            data = data.strip() + ']'
            ret = js_execute( 'print(JSON.stringify(%s));' % data)
            if ret['sts'] and 0 == ret['code']:
                try:
                    data = byteify(json.loads(ret['data']), '', True)
                    for eItem in data:
                        if episodeId not in eItem.get('poster', ''):
                            continue
                        for item in eItem['sources']:
                            vidType = item['type'].lower()
                            vidUrl  = self.getFullUrl(item['src'], cUrl).replace(' ', '%20')
                            name    = self.cleanHtmlStr(item['label'])
                            tmpTab = []
                            if 'x-mpegurl' in vidType:
                                tmpTab = getDirectM3U8Playlist(vidUrl, checkExt=False, checkContent=True, cookieParams=self.defaultParams)
                            elif 'mp4' in vidType:
                                tmpTab.append({'name':'mp4', 'url':vidUrl})
                            
                            for idx in range(len(tmpTab)):
                                tmpTab[idx]['name'] = '[%s] %s' % (name, tmpTab[idx]['name'])
                            retTab.extend(tmpTab)
                        
                        for item in eItem['textTracks']:
                            if item.get('kind', '') != 'captions':
                                continue
                            subTracksTab.append({'title':item['label'], 'url':self.getFullUrl(item['src']), 'lang':item['language'], 'format':'vtt'})
                        
                        break
                except Exception:
                    printExc()
        else:
            tmp = self.cm.ph.getDataBeetwenMarkers(data, 'player.src(', ')')[1]
            if tmp == '':
                tmp = self.cm.ph.getDataBeetwenNodes(data, ('[', ']', '.m3u8'), (';', ' '))[1]
            tmpTab = tmp.split('},')
            for tmp in tmpTab:
                vidType = self.cm.ph.getSearchGroups(tmp, '''type['"]?\s*:\s*['"]([^'^"]+?)['"]''')[0].lower()
                vidLabel = self.cm.ph.getSearchGroups(tmp, '''label['"]?\s*:\s*['"]([^'^"]+?)['"]''')[0]
                vidUrl  = self.getFullUrl(self.cm.ph.getSearchGroups(tmp, '''src['"]?\s*:\s*['"]([^'^"]+?)['"]''')[0], cUrl)
                
                if not self.cm.isValidUrl(vidUrl):
                    return []
                
                if 'x-mpegurl' in vidType:
                    retTab = getDirectM3U8Playlist(vidUrl, checkExt=False, checkContent=True, cookieParams=self.defaultParams)
                elif 'mp4' in vidType:
                    retTab.append({'name':'mp4 %s' % vidLabel, 'url':vidUrl})
            
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<video', '</video>')
            for tmp in data:
                tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<track', '>')
                for item in tmp:
                    if 'caption' not in item:
                        continue
                    url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0])
                    if not self.cm.isValidUrl(url):
                        continue
                    lang  = self.cm.ph.getSearchGroups(item, '''srclang=['"]([^'^"]+?)['"]''')[0]
                    title = self.cm.ph.getSearchGroups(item, '''label=['"]([^'^"]+?)['"]''')[0]
                    subTracksTab.append({'title':title, 'url':url, 'lang':lang, 'format':'vtt'})
        
        cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE)
        for idx in range(len(retTab)):
            retTab[idx]['url'] = strwithmeta(retTab[idx]['url'], {'User-Agent':self.USER_AGENT, 'Referer':cItem['url'], 'Cookie':cookieHeader, 'external_sub_tracks':subTracksTab})
        return retTab
    
    def getArticleContent(self, cItem, data=None):
        printDBG("ForjaTN.getArticleContent [%s]" % cItem)
        
        retTab = []
        
        otherInfo = {}
        
        if data == None:
            sts, data = self.getPage(cItem.get('prev_url', cItem['url']))
            if not sts:
                return []
            
        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'row desc'), ('<div', '>', 'row'), False)[1]
        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<p', '</p>')[1])
        title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<h4', '</h4>')[1])
        icon  = self.getFullIconUrl(self.cm.ph.getSearchGroups(data, '''\ssrc=['"]([^'^"]+?)['"]''')[0])
        
        keysMap = {'runtime':   'duration',
                   'genre':     'genres',
                   'actors':    'actors',
                   'rating':    'rating',
                   'released':  'released',
                   'language':  'language',
                   }
        data = self.cm.ph.getAllItemsBeetwenNodes(data.split('</h4>', 1)[-1], ('<strong', '</strong'), ('<', '>'))
        for item in data:
            item = item.split(':', 1)
            if len(item) != 2:
                continue
            
            marker = self.cleanHtmlStr(item[0]).lower()
            if marker not in keysMap:
                continue
            
            if marker == 'rating':
                value = self.cm.ph.getSearchGroups(item[1], '''stars\-([0-9\-]+?)\.png''')[0].replace('-', '.') + '/5.0'
            else:
                value  = self.cleanHtmlStr(item[1])
            
            otherInfo[keysMap[marker]] = value
        
        if title == '':
            title = cItem['title']
        if desc == '':
            desc = cItem.get('desc', '')
        if icon == '':
            icon = cItem.get('icon', self.DEFAULT_ICON_URL)
        
        return [{'title':self.cleanHtmlStr( title ), 'text': self.cleanHtmlStr( desc ), 'images':[{'title':'', 'url':self.getFullUrl(icon)}], 'other_info':otherInfo}]
    
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
            self.listMainMenu({'name':'category'}, 'list_genres')
        elif category == 'list_filters':
            self.listFilters(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem, 'explore_item')
        elif category == 'explore_item':
            self.exploreItem(self.currItem, 'list_episodes')
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
        CHostBase.__init__(self, ForjaTN(), True, [])
        
    def withArticleContent(self, cItem):
        return cItem.get('good_for_fav', False)
    
    def getSearchTypes(self):
        searchTypesOptions = []
        searchTypesOptions.append((_("Movies"), "movies"))
        searchTypesOptions.append((_("Seriale"), "series"))
        return searchTypesOptions
    
