# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib
try:    import json
except Exception: import simplejson as json
###################################################

def gettytul():
    return 'https://tantifilm.eu/'

class TantiFilmOrg(CBaseHostClass):
    REMOVE_COOKIE = True
    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'TantiFilmOrg.tv', 'cookie':'tantifilmorg.cookie'})
        self.USER_AGENT = 'Mozilla/5.0'
        self.HEADER = {'User-Agent':self.USER_AGENT, 'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Encoding':'gzip, deflate'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update( {'X-Requested-With': 'XMLHttpRequest'} )
        self.cm.HEADER = self.HEADER # default header
        self.defaultParams = {'header':self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        
        self.MAIN_URL = 'https://tantifilm.eu/'
        self.DEFAULT_ICON_URL = 'https://raw.githubusercontent.com/Zanzibar82/images/master/posters/tantifilm.png'
        
        self.MAIN_CAT_TAB = [{'category':'list_categories',    'title': _('Categories'),                           'url':self.MAIN_URL  },
                             {'category':'search',             'title': _('Search'), 'search_item':True,         },
                             {'category':'search_history',     'title': _('Search history'),                     } 
                            ]
        
        self.cacheCollections = {}
        self.cookieHeader = ''
        self.cacheFilters = {}
        self.cacheLinks = {}
        self.cacheSeries = {}
        
    def getPage(self, baseUrl, addParams = {}, post_data = None):
        if addParams == {}: addParams = dict(self.defaultParams)
        
        origBaseUrl = baseUrl
        baseUrl = self.cm.iriToUri(baseUrl)
        
        addParams['cloudflare_params'] = {'cookie_file':self.COOKIE_FILE, 'User-Agent':self.USER_AGENT}
        sts, data = self.cm.getPageCFProtection(baseUrl, addParams, post_data)
        if sts and 'aes.min.js' in data:
            jscode = ['var document={};document.location={};']
            tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<script', '>'), ('</script', '>'))
            for item in tmp:
                scriptUrl = self.cm.getFullUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0], self.cm.meta['url'])
                if scriptUrl != '':
                    sts2, item = self.cm.getPage(scriptUrl, addParams, post_data)
                    if sts2: jscode.append(item)
                else:
                    item = self.cm.ph.getDataBeetwenNodes(item, ('<script', '>'), ('</script', '>'), False)[1]
                    if item != '': jscode.append(item)
            jscode.append('print(JSON.stringify(document));')
            ret = ret = js_execute('\n'.join(jscode), {'timeout_sec':15})
            if ret['sts'] and 0 == ret['code']:
                try:
                    tmp = byteify(json.loads(ret['data']))
                    item = tmp['cookie'].split(';', 1)[0].split('=', 1)
                    self.defaultParams['cookie_items'] = {item[0]:item[1]}
                    addParams['cookie_items'] = self.defaultParams['cookie_items']
                    sts, data = self.cm.getPage(baseUrl, addParams, post_data)
                except Exception:
                    printExc()
        return sts, data
        
    def refreshCookieHeader(self):
        self.cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE)
        
    def getFullIconUrl(self, url, refreshCookieHeader=True):
        url = CBaseHostClass.getFullIconUrl(self, url)
        if url == '': return ''
        if refreshCookieHeader: self.refreshCookieHeader()
        return strwithmeta(url, {'Cookie':self.cookieHeader, 'User-Agent':self.USER_AGENT})

    def listMainMenu(self, cItem, nextCategory):
        printDBG("TantiFilmOrg.listMainMenu")
        
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        self.setMainUrl(self.cm.meta['url'])
        
        #params = dict(cItem)
        #params.update({'category':nextCategory, 'title':'Film', 'url':self.getFullUrl('/film/')})
        #self.addDir(params)
        printDBG(data)
        data = self.cm.ph.getDataBeetwenNodes(data, ('<nav', '>', 'ddmenu'), ('</ul', '>'), False)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>', withMarkers=True)
        printDBG(data)
        for item in data:
            title = self.cleanHtmlStr(item)
            if title.upper() == 'HOME': continue # not items on home page
            url   = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            if self.cm.getBaseUrl(self.getMainUrl(), True) != self.cm.getBaseUrl(url, True) or '/supporto/' in url:
                continue
            params = dict(cItem)
            if 'elenco-saghe' not in url:
                params.update({'category':nextCategory, 'title':title, 'url':url})
                self.addDir(params)
            else:
                params.update({'category':'list_collections', 'title':title, 'url':url})
                self.addDir(params)
                break
                
    def listCategories(self, cItem, nextCategory):
        printDBG("TantiFilmOrg.listCategories")
        
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        data = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="table-list">', '</ul>', withMarkers=False)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, "<li", '</li>', withMarkers=True)
        for item in data:
            title = self.cleanHtmlStr(item)
            url   = self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0]
            params = dict(cItem)
            params.update({'category':nextCategory, 'title':title, 'url':self.getFullUrl(url)})
            self.addDir(params)
            
    def listCollections(self, cItem, nextCategory):
        printDBG("TantiFilmOrg.listCollections")
        self.cacheCollections = {}
        
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        sp = '<img class="alignnone'
        data = self.cm.ph.getDataBeetwenMarkers(data, sp, '<div id="footer"', withMarkers=False)[1]
        data = data.split(sp)
        for item in data:
            icon = self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0]
            if icon == '': continue
            tmpTab = []
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(item, "<a", '</a>', withMarkers=True)
            for tmpItem in tmp:
                url   = self.cm.ph.getSearchGroups(tmpItem, '''href=['"]([^'^"]+?)['"]''')[0]
                title = self.cleanHtmlStr(tmpItem)
                params= {'good_for_fav': True, 'title':title, 'url':self.getFullUrl(url), 'icon':self.getFullIconUrl(icon)}
                tmpTab.append(params)
            
            if len(tmpTab):
                self.cacheCollections[icon] = tmpTab
                title = icon.split('/')[-1].replace('png-', '').replace('.png', '').replace('-', ' ').title()
                params = dict(cItem)
                params.update({'category':nextCategory, 'title':title, 'icon':self.getFullIconUrl(icon)})
                self.addDir(params)
            
    def listColectionItems(self, cItem, nextCategory):
        printDBG("TantiFilmOrg.listColectionItems")
        tab = self.cacheCollections.get(cItem.get('icon', ''), [])
        self.listsTab(tab, {'category':nextCategory})
    
    def listItems(self, cItem, nextCategory):
        printDBG("TantiFilmOrg.listItems")
        
        url  = cItem['url']
        page = cItem.get('page', 1)
        if page > 1:
            tmp = url.split('?')
            url = tmp[0]
            if not url.endswith('/'): url += '/'
            url += 'page/%s/' % (page)
            if len(tmp) == 2: url += '?' + tmp[1]
        
        sts, data = self.getPage(url)
        if not sts: return
        
        if 'page/{0}/'.format(page+1) in data:
            nextPage = True
        else:
            nextPage = False
        
        if '?s=' in url:
            data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'film film-2'), ('<div', '</div>', 'class="descriere"'))
        else:
            if page == 1:
                tmp = self.cm.ph.getDataBeetwenMarkers(data, '<h1 class="page-title">', '</body>', withMarkers=False)[1]
            else:
                tmp = self.cm.ph.rgetDataBeetwenMarkers2(data, '</body>', '<h1 class="page-title">', withMarkers=False)[1]
            if tmp == '':
                tmp = data
            data = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<div class="mediaWrap', '</span>', withMarkers=True)
        for item in data:
            idx = item.find('</h2>')
            if idx > 0: item = item[:idx]
            url   = self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0]
            if '/film-di-natale-streaming/' in url: continue
            if 'saghe/' in url: continue
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<div class="title-film', '</a>')[1])
            if title.endswith('streaming'): title = title[:-9].strip()
            icon  = self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0]
            desc  = self.cleanHtmlStr(item.replace('</p>', '[/br]'))
            
            try:
                raiting = str(int(((float(self.cm.ph.getSearchGroups(item, '''data\-rateit\-value=['"]([^'^"]+?)['"]''')[0]) * 5) / 3)*10)/10.0) + '/5'
                desc = raiting + ' | ' + desc
            except Exception:
                pass
            
            params = {'good_for_fav': True, 'category':nextCategory, 'title':title, 'url':self.getFullUrl(url), 'icon':self.getFullIconUrl(icon), 'desc':desc}
            self.addDir(params)
        
        if nextPage:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title':_('Next page'), 'page':page+1})
            self.addDir(params)
            
            
    def listContent(self, cItem, nextCategory):
        printDBG("TantiFilmOrg.listContent")
        
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        
        # trailer
        trailerUrls = []
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="trailer"', '</div>')
        for item in tmp:
            url = self.cm.ph.getSearchGroups(item, '''<iframe[^>]+?src=['"]([^'^"]+?)['"]''', ignoreCase=True)[0]
            if self.cm.isValidUrl(url) and url not in trailerUrls:
                params = dict(cItem)
                params.pop('category', None)
                trailerUrls.append(url)
                title = cItem['title'] + ' - ' + self.cleanHtmlStr(item)
                self.addVideo({'good_for_fav': True, 'title':title, 'url':url, 'video_type':'trailer', 'icon':cItem.get('icon', '')})
        
        # desc
        desc = []
        
        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div class="keywords-film-left">', '</p>')[1])
        if tmp != '': desc.append(tmp)
        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div class="content-left-film">', '</p>')[1])
        if tmp != '': desc.append(tmp)
        desc = '[/br][/br]'.join(desc)
        
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<div id="wpwm-movie-links">', '<div class="film-left">', False)[1]
        tmp = re.compile('''<iframe[^>]+?src=['"]([^'^"]+?)['"]''', re.IGNORECASE).findall(tmp)
        if len(tmp) == 1 and '/serietv/' in tmp[0] and self.cm.isValidUrl(tmp[0]): 
            # series
            cItem = dict(cItem)
            cItem['url'] = tmp[0]
            cItem['desc'] = desc
            self.listSeasons(cItem, nextCategory)
        elif len(tmp) > 0:
            # movie
            # add this item as video item
            params = dict(cItem)
            params.pop('category', None)
            params.update({'good_for_fav': True, 'video_type':'movie', 'desc':desc})
            self.addVideo(params)
            
    def listSeasons(self, cItem, nextCategory):
        printDBG("TantiFilmOrg.listSeasons")
        
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<nav class="', '</select>')
        if len(data) < 2: 
            printDBG("!!!!!!!!!!!! wrong makers for series TV -> url[%s]" % cItem['url'])
            return
        
        # get seasons
        data = data[0]
        seasonName = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data.split('<ul')[0], '<a', '</a>')[1])
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<option', '</option>')
        printDBG(data)
        for item in data:
            url   = self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0]
            if not self.cm.isValidUrl(url): continue
            seasonTitle = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'good_for_fav': False, 'category':nextCategory, 'title': '%s %s' % (seasonName, seasonTitle), 'season_id':seasonTitle, 'series_title':cItem['title'], 'url':url})
            self.addDir(params)
        
    def listEpisodes(self, cItem):
        printDBG("TantiFilmOrg.listEpisodes")
        
        seriesTitle = cItem['series_title']
        try: seasonNum = str(int(cItem['season_id']))
        except Exception: seasonNum = ''
        
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<nav class="', '</select>')
        if len(data) < 2: 
            printDBG("!!!!!!!!!!!! wrong makers for series TV -> url[%s]" % cItem['url'])
            return
        
        # get seasons
        data = data[1]
        episodeName = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data.split('<ul')[0], '<a', '</a>')[1])
        
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<option', '</option>')
        for item in data:
            url = self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0]
            if not self.cm.isValidUrl(url): continue
            episodeTitle = self.cleanHtmlStr(item)
            try: episodeNum = str(int(episodeTitle))
            except Exception: episodeNum = ''
            
            if '' != episodeNum and '' != seasonNum:
                title = seriesTitle + ' - ' + 's%se%s'% (seasonNum.zfill(2), episodeNum.zfill(2))
            else: 
                title = seriesTitle + ' - ' +  cItem['title'] + ' ' + '%s %s' % (episodeName, episodeTitle)
           
            params = {'good_for_fav': False, 'title': title, 'video_type':'episode', 'url':url, 'icon':cItem.get('icon', ''), 'desc':cItem.get('desc', '')}
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("TantiFilmOrg.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        
        baseUrl = self.getFullUrl('?s=' + urllib.quote_plus(searchPattern))
        cItem = dict(cItem)
        cItem['url'] = baseUrl
        self.listItems(cItem, 'list_content')

    
    def getLinksForVideo(self, cItem):
        printDBG("TantiFilmOrg.getLinksForVideo [%s]" % cItem)
        urlTab = []
        
        if len(self.cacheLinks.get(cItem['url'], [])):
            return self.cacheLinks[cItem['url']]
            
        type = cItem['video_type']
        if type == 'trailer':
            return self.up.getVideoLinkExt(cItem['url'])
        else:
            sts, data = self.getPage(cItem['url'])
            if not sts: return []
        
        urlTab = []
        if type == 'movie':
            tmp = self.cm.ph.getDataBeetwenMarkers(data, '<div id="wpwm-movie-links">', '<div class="film-left">', False)[1]
            tmp = tmp.split('</ul>')
            printDBG(tmp)
            for item in tmp:
                url = self.cm.ph.getSearchGroups(item, '''<iframe[^>]+?src=['"]([^'^"]+?)['"]''', ignoreCase=True)[0]
                if not self.cm.isValidUrl(url): continue
                id = self.cm.ph.getSearchGroups(item, '''id=['"]([^'^"]+?)['"]''', ignoreCase=True)[0]
                title = self.cm.ph.getDataBeetwenReMarkers(data, re.compile('''<a[^>]+?href=['"]\#%s['"][^>]*?>''' % re.escape(id)), re.compile('</a>'))[1]
                title = self.cleanHtmlStr(title)
                if title == '': title = self.up.getDomain(url)
                urlTab.append({'name':title, 'url':strwithmeta(url, {'url':cItem['url']}), 'need_resolve':1})
        elif type == 'episode':
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<nav class="', '</select>')
            if len(data) < 3: 
                printDBG("!!!!!!!!!!!! wrong makers for links TV series -> url[%s]" % cItem['url'])
                return []
            
            data = data[2]
            seasonName = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data.split('<ul')[0], '<a', '</a>')[1])
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<option', '</option>')
            printDBG(data)
            for item in data:
                url   = self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0]
                if not self.cm.isValidUrl(url): continue
                title = self.cleanHtmlStr(item)
                if title == '': continue
                urlTab.append({'name':title, 'url':strwithmeta(url, {'url':cItem['url']}), 'need_resolve':1})
        
        self.cacheLinks[cItem['url']] = urlTab
        return urlTab
        
    def getVideoLinks(self, videoUrl):
        printDBG("TantiFilmOrg.getVideoLinks [%s]" % videoUrl)
        urlTab = []
        
        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            key = self.cacheLinks.keys()[0]
            for idx in range(len(self.cacheLinks[key])):
                if videoUrl in self.cacheLinks[key][idx]['url']:
                    if not self.cacheLinks[key][idx]['name'].startswith('*'):
                        self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name']
                    break
        tries = 0
        while tries < 4:
            tries += 1
            printDBG(">> tries [%d]" % tries)
            if not self.cm.isValidUrl(videoUrl):
                break
            if 1 != self.up.checkHostSupport(videoUrl):
                addParams = dict(self.defaultParams)
                addParams['with_metadata'] = True
                sts, data = self.getPage(videoUrl, addParams)
                if sts:
                    videoUrl = data.meta['url']
                    jscode = ['var document={},window=this;function typeOf(r){return{}.toString.call(r).match(/\s(\w+)/)[1].toLowerCase()}function jQuery(){return"function"==typeOf(arguments[0])&&arguments[0](),jQuery}jQuery.ready=jQuery,jQuery.attr=function(r,t){"src"==r&&print(t)},$=jQuery;']
                    tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<script', '>'), ('</script', '>'), False)
                    for item in tmp:
                        jscode.append(item)
                    ret = js_execute( '\n'.join(jscode) )
                    if ret['sts'] and 0 == ret['code']:
                        data = ret['data'].strip()
                        if self.cm.isValidUrl(data):
                            videoUrl = data
            
            if 'hostvid.xyz' in self.up.getDomain(videoUrl):
                sts, data = self.getPage(videoUrl)
                if not sts: return []
                videoUrl = self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^'^"]+?)['"]''', ignoreCase=True)[0]
            if self.cm.isValidUrl(videoUrl):
                urlTab = self.up.getVideoLinkExt(videoUrl)
                if len(urlTab):
                    break
            try:
                data = self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^'^"]+?)['"]''', ignoreCase=True)[0]
                if self.cm.isValidUrl(data):
                    videoUrl = data
            except Exception: 
                printExc()
                break
        return urlTab

    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('handleService start')
        
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name     = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode     = self.currItem.get("mode", '')
        
        printDBG( "handleService: || name[%s], category[%s] " % (name, category) )
        self.currList = []
        
    #MAIN MENU
        if name == None:
            if TantiFilmOrg.REMOVE_COOKIE:
                TantiFilmOrg.REMOVE_COOKIE = False
                rm(self.COOKIE_FILE)
            self.listMainMenu({'name':'category', 'url':self.MAIN_URL}, 'list_items')
            self.listsTab(self.MAIN_CAT_TAB, {'name':'category'})
        elif 'list_categories' == category:
            self.listCategories(self.currItem, 'list_items')
        elif 'list_collections' == category:
            self.listCollections(self.currItem, 'list_colection_items')
        elif 'list_colection_items' == category:
            self.listColectionItems(self.currItem, 'list_content')
        elif 'list_items' == category:
            self.listItems(self.currItem, 'list_content')
        elif 'list_content' == category:
            self.listContent(self.currItem, 'list_episodes')
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
        CHostBase.__init__(self, TantiFilmOrg(), True, [])

    
