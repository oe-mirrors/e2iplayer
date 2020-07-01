# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.utils import unescapeHTML
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps

###################################################

###################################################
# FOREIGN import
###################################################
import urlparse
import re
import urllib
#try:    
#    import json
#except Exception: 
#    import simplejson as json
###################################################


def gettytul():
    return 'https://cda-filmy.online/'

class CdaFilmy(CBaseHostClass):
    
    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'cda-filmy.online', 'cookie':'cda-filmy.online.cookie'})
        
        self.MAIN_URL = 'https://cda-filmy.online/'
        self.DEFAULT_ICON_URL = 'https://cda-filmy.online/wp-content/uploads/cda-filmy.png'

        self.USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.61 Safari/537.36'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT':'1', 'Accept': 'text/html', 'Accept-Encoding':'gzip, deflate', 'Referer':self.getMainUrl(), 'Origin':self.getMainUrl()}

        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update( {'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding':'gzip, deflate', 'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8', 'Accept':'application/json, text/javascript, */*; q=0.01'} )
        
        self.defaultParams = {'header':self.HTTP_HEADER, 'with_metadata':True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.cacheLinks    = {}
        self.cacheSeriesLetter = []
        self.cacheSetiesByLetter = {}
        self.cacheFilters = {}
        self.cacheFiltersKeys = []
        
    def getPage(self, baseUrl, addParams = {}, post_data = None):
        if addParams == {}: 
            addParams = dict(self.defaultParams)
        
        origBaseUrl = baseUrl
        baseUrl = self.cm.iriToUri(baseUrl)
        
        def _getFullUrl(url):
            if self.cm.isValidUrl(url): 
                return url
            else: return urlparse.urljoin(baseUrl, url)
        
        addParams['cloudflare_params'] = {'domain':self.up.getDomain(baseUrl), 'cookie_file':self.COOKIE_FILE, 'User-Agent':self.USER_AGENT, 'full_url_handle':_getFullUrl}
        
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)
        
    def listMainMenu(self, cItem):
        printDBG("cda-filmy.listMainMenu")

        MAIN_CAT_TAB = [{'category':'list_items',     'title': _('Movies'),            'url':self.getFullUrl('/filmy-online/')},
                        {'category':'list_items',     'title': _('Series'),            'url':self.getFullUrl('/seriale-online/')},
                        {'category':'list_items',     'title': _('Releases'),          'url':self.getFullUrl('/gatunek/premiery/')},
                        {'category':'list_items',     'title': _('Popular'),           'url':self.getFullUrl('/najpopularniejsze-filmy-online/')},
                        {'category':'list_items',     'title': _('Top rated'),         'url':self.getFullUrl('/najwyzej-oceniane-filmy-online/')},
                        {'category':'cats',           'title': _('Categories'),        'url':self.getMainUrl()},
                        {'category':'search',         'title': _('Search'),            'search_item':True}, 
                        {'category':'search_history', 'title': _('Search history')},]
        self.listsTab(MAIN_CAT_TAB, cItem)
    

    def listCategories(self, cItem, nextCategory):
        printDBG("cda-filmy.listCategories")
 
        sts, data = self.getPage(cItem['url'])
        if not sts: 
            return

        #printDBG("----------------------------")
        #printDBG(data)
        #printDBG("----------------------------")

        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'Wdgt widget_categories'), ('</ul', '>'))[1]
        items = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li', '</li>')
        
        for item in items:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            title = self.cleanHtmlStr(item)

            if url and title: 
                params = dict(cItem)
                params.update({'good_for_fav':False, 'category':nextCategory, 'title':title, 'desc':'', 'url':url})
                printDBG(str(params))
                self.addDir(params)
                    
    def listItems(self, cItem):
        printDBG("cda-filmy.listItems")
        page = cItem.get('page', 1)
        
        pageUrl = cItem['url']
        if page > 1 and '/page/' not in pageUrl:
            pageUrl = "%s/page/%d" % (cItem['url'],page)
            
        sts, data = self.getPage(pageUrl)
        if not sts: 
            return
        
        section = self.cm.ph.getDataBeetwenMarkers(data, '<section>', '</section>')[1]
        items = self.cm.ph.getAllItemsBeetwenNodes(section, ('<li', '>'), ('</li', '>'))
        for item in items:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<h3', '>'), ('</h3', '>'), False)[1])
            desc = [self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'Description'), ('</p', '>'))[1])]
            
            spans = self.cm.ph.getAllItemsBeetwenNodes(item, ('<span', '>'), ('</span', '>'))
            for sp in spans:
                sp2 = self.cleanHtmlStr(sp)
                if sp2.lower() not in ['filmy online','cda','cda filmy']:
                    desc.append(sp2)
            
            if desc:
                desc = "|".join(desc)
            else:
                desc = ''
                    
            params = {'good_for_fav':True, 'url':url, 'title':title, 'desc':desc, 'icon':icon}
            if 'serial' in cItem['url']:
                params.update({'category':'list_series'})
                printDBG(str(params))
                self.addDir(params)
            else:
                self.addVideo(params)

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'wp-pagenavi'), ('</div', '>'))[1]
        nextPage = self.cm.ph.getSearchGroups(nextPage, '''<a[^>]+?href=['"]([^'^"]+?)['"][^>]*?>%s</a>''' % (page + 1))[0]
            
        if nextPage != '':
            params = dict(cItem)
            params.update({'title':_('Next page'), 'url':nextPage, 'page':page + 1})
            self.addMore(params)

    def listSeries(self, cItem):
        printDBG("cda-filmy.listSeries")
        
        sts, data = self.getPage(cItem['url'])
        if not sts: 
            return

        items = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'Wdgt AABox'), ('</table', '>'))
        
        for sitem in items:
            #printDBG("----------------------")
            #printDBG(sitem)
            season = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(sitem, ('<div', '>', 'Title AA-Season'), ('</div', '>'))[1])
            if 'Sezon' in season:
                season = season.replace('Sezon', _('Season'))
            
            printDBG("---------------")
            printDBG(season)
            seasonEpisodes = []
            tmp = self.cm.ph.getDataBeetwenMarkers(sitem, '<table>', '</tbody>')[1]
            tmp = self.cm.ph.getAllItemsBeetwenNodes(tmp, ('<tr', '>'), ('</tr', '>'))
            for item in tmp:
                printDBG("cda-filmy.listSeries item %s" % item)
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
                if url:
                    icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(unescapeHTML(item), '''src=['"]([^"^']+?)['"]''')[0])
                    if not icon:
                        icon = cItem.get('icon','')
                    number= self.cm.ph.getDataBeetwenNodes(item, '<span class="Num">', ('</span', '>'), False)[1]
                    
                    title = self.cm.ph.getDataBeetwenNodes(item, ('<td', '>', 'MvTbTtl'), ('</td', '>'))[1]
                    title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(title, ('<a', '>'), ('</a', '>'))[1])
                    if number:
                        title = "%s. %s" % (number, title)
                    params = {'good_for_fav':True, 'url':url, 'title':title, 'icon':icon}
                    printDBG(str(params))
                    seasonEpisodes.append(params)
             
            if seasonEpisodes:        
                params = dict(cItem)
                params.update({ 'good_for_fav':True, 'title' : season, 'category':'season', 'episodes' : seasonEpisodes})
                
                self.addDir(params)

    def listEpisodes(self,cItem):
        printDBG("cda-filmy.listEpisodes")
        
        episodes = cItem.get('episodes',[])
        
        for ep in episodes:
            title = ep.get('title','').lower()
            if 'odcinek' in title:
                title = title.replace('odcinek', _('Episode'))
                ep.update({'title' : title})
                 
            printDBG(str(ep))
            self.addVideo(ep)
        
        
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("cda-filmy.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        url = self.getFullUrl('/?s=%s') % urllib.quote_plus(searchPattern)
        params = {'name':'category', 'category':'list_items', 'good_for_fav':False, 'url':url}
        self.listItems(params)
        
    def getLinksForVideo(self, cItem):
        printDBG("cda-filmy.getLinksForVideo [%s]" % cItem)

        url = cItem['url']
        if not url:
            return []
                            
        cacheKey = url
        cacheTab = self.cacheLinks.get(cacheKey, [])
        if cacheTab: 
            return cacheTab
        
        self.cacheLinks = {}
        urlsTab = []
        
        params = dict(self.defaultParams)
        params['header']['Referer'] = url
        
        sts, data = self.getPage(url, params)
        if not sts: 
            return []
        
        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'TPlayerTb'), ('<span', '>'))[1]
        tmp = unescapeHTML(tmp).replace('#038;', '')
        items = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<div', '</div>')
    
        for item in items:
            printDBG("cda-filmy.getLinksForVideo item[%s]" % item)
            url = self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''', 1, True)[0]
            
            sts, dataLink = self.getPage(url, params)
            if sts: 
                playerUrl = self.cm.ph.getSearchGroups(dataLink, '''src=['"]([^"^']+?)['"]''', 1, True)[0]
                params = {'name':self.up.getHostName(playerUrl), 'url':strwithmeta(playerUrl, {'Referer':url}), 'need_resolve':1}
                printDBG(str(params))
                urlsTab.append(params)
             
        if urlsTab:
            self.cacheLinks[cacheKey] = urlsTab
        
        return urlsTab
        
    def getVideoLinks(self, baseUrl):
        printDBG("cda-filmy.getVideoLinks [%s]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
        
        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if baseUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name'] + '*'
                        break
                        
        return self.up.getVideoLinkExt(baseUrl)

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
        elif category == 'list_items':
            self.listItems(self.currItem)            
        elif category == 'list_series':
            self.listSeries(self.currItem)
        elif category == 'season':
            self.listEpisodes(self.currItem)
        elif category == 'cats':
            self.listCategories(self.currItem, 'list_items')
            
        elif category == 'a_z':
            self.listAZ(self.currItem, 'list_by_letter')
           
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
        CHostBase.__init__(self, CdaFilmy(), True, [])
        
    def withArticleContent(self, cItem):
        return True
