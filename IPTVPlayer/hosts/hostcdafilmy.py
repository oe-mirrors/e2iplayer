# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.utils import unescapeHTML
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
    return 'https://cda-filmy.online/'

class CdaFilmy(CBaseHostClass):
    
    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'cda-filmy.online', 'cookie':'cda-filmy.online.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.MAIN_URL = 'https://cda-filmy.online/'
        self.DEFAULT_ICON_URL = 'https://cda-filmy.online/wp-content/uploads/cda-filmy.png'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT':'1', 'Accept': 'text/html', 'Accept-Encoding':'gzip, deflate', 'Referer':self.getMainUrl(), 'Origin':self.getMainUrl()}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update( {'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding':'gzip, deflate', 'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8', 'Accept':'application/json, text/javascript, */*; q=0.01'} )
        
        self.cacheLinks    = {}
        self.defaultParams = {'header':self.HTTP_HEADER, 'with_metadata':True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        
        self.cacheSeriesLetter = []
        self.cacheSetiesByLetter = {}
        self.cacheFilters = {}
        self.cacheFiltersKeys = []
        
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
        printDBG("cda-filmy.listMainMenu")
        #sts, data = self.getPage(self.getMainUrl())
        #if not sts: return
        #self.setMainUrl(data.meta['url'])
        MAIN_CAT_TAB = [{'category':'list_items',     'title': 'Filmy',             'url':self.getFullUrl('/filmy-online/')},
                        {'category':'list_items',     'title': 'Seriale',           'url':self.getFullUrl('/seriale-online/')},
                        {'category':'list_items',     'title': 'Premiery',          'url':self.getFullUrl('/gatunek/premiery/')},
                        {'category':'list_items',     'title': 'Popularne',         'url':self.getFullUrl('/najpopularniejsze-filmy-online/')},
                        {'category':'list_items',     'title': 'Najlepiej oceniane','url':self.getFullUrl('/najwyzej-oceniane-filmy-online/')},
#                        {'category':'a_z',            'title': _('By years'),       'url':self.getMainUrl()},
                        {'category':'cats',           'title': _('Categories'),     'url':self.getMainUrl()},
                        {'category':'search',         'title': _('Search'),         'search_item':True}, 
                        {'category':'search_history', 'title': _('Search history')},]
        self.listsTab(MAIN_CAT_TAB, cItem)
    

    def listCats(self, cItem, nextCategory):
        printDBG("cda-filmy.listCats")
 
        sts, data = self.getPage(cItem['url'])
        if not sts: return

        printDBG("cda-filmy.listCats data1[%s]" % data)            
        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'Wdgt widget_categories'), ('</ul', '>'))[1]
        printDBG("cda-filmy.listCats data2[%s]" % data)
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            if url == '': continue
            title = self.cleanHtmlStr(item)
            if title == '': continue
            params = dict(cItem)
            params.update({'good_for_fav':False, 'category':nextCategory, 'title':title, 'desc':'', 'url':url})
            self.addDir(params)
                    
    def listItems(self, cItem):
        printDBG("cda-filmy.listItems")
        page = cItem.get('page', 1)
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        self.setMainUrl(data.meta['url'])
            
        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'wp-pagenavi'), ('</div', '>'))[1]
        nextPage = self.cm.ph.getSearchGroups(nextPage, '''<a[^>]+?href=['"]([^'^"]+?)['"][^>]*?>%s</a>''' % (page + 1))[0]
        
        data = self.cm.ph.getDataBeetwenMarkers(data, '<section>', '</section>')[1]
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<li', '>'), ('</li', '>'))
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<h3', '>'), ('</h3', '>'), False)[1])
#            tmp = self.cm.ph.getDataBeetwenNodes(data, ('<p', '>', 'Info'), ('</p', '>'))[1]
            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'Description'), ('</p', '>'))[1])
            if 'serial' in cItem['url']:
                params = {'good_for_fav':True,'category':'list_series', 'url':url, 'title':title, 'desc':desc, 'icon':icon}
                self.addDir(params)
            else:
                params = {'good_for_fav':True, 'url':url, 'title':title, 'desc':desc, 'icon':icon}
                self.addVideo(params)
            
        if nextPage != '':
            params = dict(cItem)
            params.update({'title':_('Next page'), 'url':nextPage, 'page':page + 1})
            self.addDir(params)

    def listSeries(self, cItem):
        printDBG("cda-filmy.listSeries")
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        self.setMainUrl(data.meta['url'])

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'Wdgt AABox'), ('</table', '>'))
        for sitem in data:
            season = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(sitem, ('<div', '>', 'Title AA-Season'), ('</div', '>'))[1])
            tmp = self.cm.ph.getDataBeetwenMarkers(sitem, '<table>', '</tbody>')[1]
            tmp = self.cm.ph.getAllItemsBeetwenNodes(sitem, ('<tr', '>'), ('</tr', '>'))
            for item in tmp:
#                item = unescapeHTML(item)
                printDBG("cda-filmy.listSeries item %s" % item)
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
                if url == '': continue
                icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(unescapeHTML(item), '''src=['"]([^"^']+?)['"]''')[0])
                title = season + ' - ' + self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<td', '>', 'MvTbTtl'), ('</td', '>'))[1])
                params = {'good_for_fav':True, 'url':url, 'title':title, 'icon':icon}
                self.addVideo(params)

    def listAZ(self, cItem, nextCategory):
        printDBG("cda-filmy.listAZ")

        sts, data = self.getPage(cItem['url'])
        if not sts: return
        self.setMainUrl(data.meta['url'])
           
        data = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'AZList'), ('</ul', '>'))[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            if url == '': continue
            title = self.cleanHtmlStr(item)
            if title == '': continue
            params = dict(cItem)
            params.update({'good_for_fav':False, 'category':nextCategory, 'title':letter, 'desc':'', 'url':url})
            self.addDir(params)
        
    def listByLetter(self, cItem, nextCategory):
        printDBG("cda-filmy.listByLetter")
        letter = cItem['f_letter']
        tab = self.cacheSetiesByLetter[letter]
        cItem = dict(cItem)
        cItem.update({'good_for_fav':True, 'category':nextCategory, 'desc':''})
        self.listsTab(tab, cItem)
        
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("cda-filmy.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        url = self.getFullUrl('/?s=%s') % urllib.quote_plus(searchPattern)
        params = {'name':'category', 'category':'list_items', 'good_for_fav':False, 'url':url}
        self.listItems(params)
        
    def getLinksForVideo(self, cItem):
        printDBG("cda-filmy.getLinksForVideo [%s]" % cItem)
                
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
        
        cUrl = data.meta['url']
        self.setMainUrl(cUrl)
        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'TPlayerTb'), ('<span', '>'))[1]
        data = unescapeHTML(data).replace('#038;', '')
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div', '</div>')
    
        for item in data:
            printDBG("cda-filmy.getLinksForVideo item[%s]" % item)
            url = self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''', 1, True)[0]
            sts, data = self.getPage(url, params)
            if not sts: continue
            playerUrl = self.cm.ph.getSearchGroups(data, '''src=['"]([^"^']+?)['"]''', 1, True)[0]
            retTab.append({'name':self.up.getHostName(playerUrl), 'url':strwithmeta(playerUrl, {'Referer':url}), 'need_resolve':1})
             
        if len(retTab):
            self.cacheLinks[cacheKey] = retTab
        return retTab
        
    def getVideoLinks(self, baseUrl):
        printDBG("cda-filmy.getVideoLinks [%s]" % baseUrl)
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
        printDBG("cda-filmy.getArticleContent [%s]" % cItem)
        itemsList = []

        sts, data = self.cm.getPage(cItem['url'])
        if not sts: return []

        title = cItem['title']
        icon = cItem.get('icon', '')
        desc = cItem.get('desc', '')

        title = self.cm.ph.getDataBeetwenMarkers(data, '<h1 class="Title">', '</h1>', True)[1]
#        icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(title, '''this\.src=['"]([^"^']+?)['"]''', 1, True)[0])
        desc = self.cm.ph.getDataBeetwenMarkers(data, '<div class="Description">', '</div>', False)[1]
        itemsList.append((_('Info'), self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<p class="Info">', '</p>', False)[1])))
        itemsList.append((_('Genres'), self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<strong>Gatunek:', '</li>', False)[1])))

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
        elif category == 'list_items':
            self.listItems(self.currItem)            
        elif category == 'list_series':
            self.listSeries(self.currItem)

        elif category == 'cats':
            self.listCats(self.currItem, 'list_items')
            
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
