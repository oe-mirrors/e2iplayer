# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, GetIPTVNotify
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib
import time
from binascii import hexlify
from hashlib import md5
###################################################

def gettytul():
    return 'https://videopenny.net/'

class VideoPenny(CBaseHostClass):
 
    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'video.penny.ie', 'cookie':'video.penny.ie.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:56.0) Gecko/20100101 Firefox/56.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Language':'pl,en-US;q=0.7,en;q=0.3', 'Accept-Encoding':'gzip, deflate', 'Upgrade-Insecure-Requests':'1', 'Connection':'keep-alive'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update( {'X-Requested-With': 'XMLHttpRequest'} )
        
        self.DEFAULT_ICON_URL = 'https://www1.videopenny.net/wp-content/uploads/icons/VideoPennyNet-logo_126x30.png'
        self.MAIN_URL = None
        self.cacheSeries = []
        self.cachePrograms = []
        self.cacheLast = {}

        self.defaultParams = {'header':self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self._getHeaders = None
        self.mainPageReceived = False
        self.timestam = 0
        
    def _getPage(self, baseUrl, addParams = {}, post_data = None):
        if addParams == {}: addParams = dict(self.defaultParams)
        
        if 'cookie_items' in addParams:
            timestamp = int(time.time())
            if timestamp > self.timestam:
                timestamp += 180
                hash = hexlify(md5(str(timestamp)).digest())
                addParams['cookie_items']['token'] = '%s,%s' % (timestamp, hash)
        
        addParams['cloudflare_params'] = {'cookie_file':self.COOKIE_FILE, 'User-Agent':self.USER_AGENT}
        sts, data = self.cm.getPageCFProtection(baseUrl, addParams, post_data)
        if sts and 'zablokowany.html' in self.cm.meta['url']:
            messages = self.cleanHtmlStr(data)
            GetIPTVNotify().push(messages, 'error', 40, self.cm.meta['url'], 40)
        return sts, data
        
    def getPage(self, baseUrl, addParams = {}, post_data = None):
        if not self.mainPageReceived:
            rm(self.COOKIE_FILE)
            requestUrl = self.getMainUrl()
            sts, data = self._getPage(self.getMainUrl(), addParams, post_data)
            if sts:
                self.setMainUrl(self.cm.meta['url'])
                self.defaultParams['cookie_items'] = {'retina':'1'}
            self.mainPageReceived = True
            #cUrl = self.cm.meta['url']
            #elements = re.compile(r'''src=(['"])([^\1]+?)(?:\1)''', re.I).findall(data)
            #for it in elements:
            #    it = self.cm.getFullUrl(it[1], cUrl)
            #    self._getPage(it, addParams)

            if baseUrl == requestUrl:
                return  sts, data
        return self._getPage(baseUrl, addParams, post_data)

    def getFullUrl(self, url, curUrl=None):
        url = CBaseHostClass.getFullUrl(self, url, curUrl)
        try: url.encode('ascii')
        except Exception: url = urllib.quote(url, safe="/:&?%@[]()*$!+-=|<>;")
        return url

    def getFullIconUrl(self, url):
        url = self.getFullUrl(url)
        cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE)
        return strwithmeta(url, {'Cookie':cookieHeader, 'User-Agent':self.USER_AGENT})
        
    def selectDomain(self):
        self.MAIN_URL = 'https://www1.videopenny.net/'
        sts, data = self.getPage(self.getMainUrl())

        self.MAIN_CAT_TAB = [{'category':'list_sort_filter',    'title': 'Seriale',           'url':self.getFullUrl('/kat/seriale-pol'),           'icon':self.getFullIconUrl('/wp-content/uploads/2014/05/Seriale-tv.png')},
                             {'category':'list_sort_filter',    'title': 'Programy online',   'url':self.getFullUrl('/kat/programy-rozrywkowe_pol'),  'icon':self.getFullIconUrl('/wp-content/uploads/2014/05/Programy-online.png')},
                             {'category':'list_sort_filter',    'title': 'Filmy',             'url':self.getFullUrl('/kat/filmy-pol'),               'icon':self.getFullIconUrl('/wp-content/uploads/2014/05/Filmy.png')},
                             {'category':'list_sort_filter',    'title': 'Bajki',             'url':self.getFullUrl('/kat/bajki_pol'),                  'icon':self.getFullIconUrl('/wp-content/uploads/2014/05/Bajki-tv.png')},
                             {'category':'list_last',           'title': 'Ostatnio dodane',   'url':self.getFullUrl('/ostatnio-dodane')},
                             
                             {'category':'search',          'title': _('Search'), 'search_item':True, },
                             {'category':'search_history',  'title': _('Search history'),             } 
                            ]
            
    def listSortFilters(self, cItem, nextCategory):
        printDBG("VideoPenny.listSortFilters")
        
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        
        data = self.cm.ph.getDataBeetwenMarkers(data, 'video-listing-filter', '</div>')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a ', '</a>')
        for item in data:
            url   = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            if not self.cm.isValidUrl(url): continue
            title = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'good_for_fav':False, 'title':title, 'url':url, 'category':nextCategory})
            self.addDir(params)
                
    def listItems(self, cItem, nextCategory=None):
        printDBG("VideoPenny.listItems")
        
        uniqueTab = []
        dirsTab = []
        
        page = cItem.get('page', 1)
        
        sts, data = self.getPage(cItem['url'])
        if not sts: return

        nextPage = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<a[^>]+?class=["']nextpostslink['"][^>]+?href=['"]([^"^']+?)['"]''')[0])
        
        data = self.cm.ph.getDataBeetwenMarkers(data, 'listing-content', '</section>')[1]
        data = data.split('<div id="post')
        for item in data:
            if 'item-head"' not in item: continue
            
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            if not self.cm.isValidUrl(url): continue
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h3>', '</h3>')[1])
            if title == '': title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''title=['"]([^'^"]+?)['"]''')[0])
            icon  = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''data-lazy-src=['"]([^'^"]+?)['"]''')[0])
            if icon == '': icon = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\ssrc=['"]([^'^"]+?)['"]''')[0])
            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<p>', '</p>')[1])
            
            params = dict(cItem)
            params.update({'good_for_fav':True, 'title':title, 'url':url, 'icon':icon, 'desc':desc})
#            if nextCategory != None and ('/seriale' in url or '/programy' in url) and not cItem.get('was_explored', False):
            if nextCategory != None and ('/seriale' in url or '/programy' in url) and not 'fa-play' in item and not cItem.get('was_explored', False):
                params['category'] = nextCategory
                self.addDir(params)
            else:
                self.addVideo(params)


        if self.cm.isValidUrl(nextPage):
            params = dict(cItem)
            params.update({'good_for_fav':False, 'title':_('Next page'), 'url':nextPage, 'page':page+1})
            self.addDir(params)
            
    def exploreItem(self, cItem, nextCategory):
        printDBG("VideoPenny.exploreItem")

#        params = dict(cItem)
#        self.addVideo(params)
#        
#        sts, data = self.getPage(cItem['url'])
#        if not sts: return
#        
#        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'breadcrumbs'), ('</div', '>'))[1]
#        data = self.cm.ph.rgetDataBeetwenNodes(data, ('</a', '>'), ('<a', '>'))[1]
#        url = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''\shref=['"]([^'^"]+?)['"]''')[0])
#        title = self.cleanHtmlStr(data)
#        printDBG("VideoPenny.exploreItem url [%s] title [%s]" % (url, title))
#        if url != '':
#            params = dict(cItem)
#            params.update({'title':title, 'url':url, 'category':nextCategory, 'was_explored':True})
#            self.addDir(params)
        page = cItem.get('page', 1)
        
        sts, data = self.getPage(cItem['url'])
        if not sts: return

        nextPage = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<a[^>]+?class=["']nextpostslink['"][^>]+?href=['"]([^"^']+?)['"]''')[0])
        
        data = self.cm.ph.getDataBeetwenMarkers(data, 'listing-content', '</section>')[1]
        data = data.split('<div id="post')
        for item in data:
            if 'item-head"' not in item: continue

            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            if not self.cm.isValidUrl(url): continue
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h3>', '</h3>')[1])
            if title == '': title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''title=['"]([^'^"]+?)['"]''')[0])
            icon  = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''data-lazy-src=['"]([^'^"]+?)['"]''')[0])
            if icon == '': icon = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\ssrc=['"]([^'^"]+?)['"]''')[0])
            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<p>', '</p>')[1])

            params = dict(cItem)
            params.update({'good_for_fav':True, 'title':title, 'url':url, 'icon':icon, 'desc':desc})
            self.addVideo(params)

        if self.cm.isValidUrl(nextPage):
            params = dict(cItem)
            params.update({'good_for_fav':False, 'title':_('Next page'), 'url':nextPage, 'page':page+1})
            self.addDir(params)

    def listLast(self, cItem, nextCategory):
        printDBG("VideoPenny.listLast")
        self.cacheLast = {}
        
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        
        data = self.cm.ph.getDataBeetwenMarkers(data, '<article', '</article>')[1]
        data = data.split('<div class="smart-box-head"')
        if len(data): del data[0]
        for section in data:
            sectionTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(section, '<h2', '</h2>')[1])
            if sectionTitle == '': sectionTitle = 'Inne'
            section = section.split('<div class="video-item format')
            if len(section): del section[0]
            itemsTab = []
            for item in section:
                url   = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
                if not self.cm.isValidUrl(url): continue
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h3>', '</h3>')[1])
                if title == '': title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''title=['"]([^'^"]+?)['"]''')[0])
                icon  = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''data-lazy-src=['"]([^'^"]+?)['"]''')[0])
                if icon == '': icon = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\ssrc=['"]([^'^"]+?)['"]''')[0])
                desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<p>', '</p>')[1])
                itemsTab.append({'good_for_fav':True, 'title':title, 'url':url, 'icon':icon, 'desc':desc})
            
            if len(itemsTab):
                self.cacheLast[sectionTitle] = itemsTab
                params = dict(cItem)
                params.update({'good_for_fav':False, 'category':nextCategory, 'title':sectionTitle, 'cache_key':sectionTitle})
                self.addDir(params)
    
    def listLastItems(self, cItem):
        printDBG("VideoPenny.listLastItems")
        cacheKey = cItem.get('cache_key', '')
        tab = self.cacheLast.get(cacheKey, [])
        for item in tab:
            params = dict(cItem)
            params.update(item)
            self.addVideo(params)
        
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("VideoPenny.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        page = cItem.get('page', 1)
        
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('page/%s/?s="%s"' % (page, urllib.quote_plus(searchPattern)))
        self.listItems(cItem, 'explore_item')
    
    def getLinksForVideo(self, cItem):
        printDBG("VideoPenny.getLinksForVideo [%s]" % cItem)
        
        sts, data = self.getPage(cItem['url'])
        if not sts: return []
        self.setMainUrl(self.cm.meta['url'])
        
        urlTab = []
        uniqueTab = set()
        
        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'multilink-table'), ('</div', '>'))[1]
        printDBG(tmp)
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<tr', '</tr>')
        for mainItem in tmp:
            linkVer = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(mainItem, ('<td', '>', 'multilink-title'), ('</td', '>'), False)[1])
            mainItem = self.cm.ph.getAllItemsBeetwenMarkers(mainItem, '<a', '</a>')
            for nameItem in mainItem:
                url = self.cm.getFullUrl(self.cm.ph.getSearchGroups(nameItem, '''href=['"]([^'^"]+?)['"]''')[0])
                name = self.cleanHtmlStr(nameItem)
                playerId = self.cm.ph.getSearchGroups(nameItem, '''id=['"]([^'^"]+?)['"]''')[0]
                embedData = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', playerId), ('</div', '>'))
                for item in embedData:
                    if not self.cm.ph.getSearchGroups(item, '''class=['"](%s)['"]''' % playerId)[0]: continue

                    playerUrl = self.cm.getFullUrl(self.cm.ph.getSearchGroups(item, '''['"]((?:https?:)?//[^'^"]+?)['"]''')[0])
                    if not self.cm.isValidUrl(playerUrl): continue
                    if 1 != self.up.checkHostSupport(playerUrl) and '/player.php' not in playerUrl: continue 
                    if playerUrl in uniqueTab: continue
                    uniqueTab.add(playerUrl)
                    urlTab.append({'name':'%s - %s' % (linkVer, name), 'url':strwithmeta(playerUrl, {'Referer':self.cm.meta['url']}), 'need_resolve':1})
        
        tmp = self.cm.ph.getDataBeetwenMarkers(data, 'player-embed', '</div>')[1]
        tmp += '\n'.join(self.cm.ph.getAllItemsBeetwenNodes(data, ('<', '>', 'multilink'), ('</a', '>')))
        data = tmp
        printDBG(data)
        tmp = re.compile('''['"](\s*https?://[^"^']+?)\s*['"]''').findall(data)
        printDBG(tmp)
        for item in tmp:
            playerUrl = item.strip()
            if not self.cm.isValidUrl(playerUrl): continue
            if 1 != self.up.checkHostSupport(playerUrl) and '/player.php' not in playerUrl: continue 
            if playerUrl in uniqueTab: continue
            uniqueTab.add(playerUrl)
            urlTab.append({'name':self.up.getDomain(playerUrl, False), 'url':strwithmeta(playerUrl, {'Referer':self.cm.meta['url']}), 'need_resolve':1})
        
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<video', '</video>')[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<source', '>')
        for item in tmp:
            if 'video/mp4' not in item and 'video/x-flv' not in item: continue
            type  = self.cm.ph.getSearchGroups(item, '''type=['"]([^'^"]+?)['"]''')[0].replace('video/', '')
            url   = self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0]
            label = self.cm.ph.getSearchGroups(item, '''label=['"]([^'^"]+?)['"]''')[0]
            if label == '': label = self.cm.ph.getSearchGroups(item, '''res=\s*([^\s]+?)[\s>]''')[0]
            printDBG(url)
            if self.cm.isValidUrl(url):
                urlTab.append({'name':'[%s] %s' % (type, label), 'url':strwithmeta(url, {'Referer':self.cm.meta['url']})})
        
        return urlTab
        
    def getVideoLinks(self, videoUrl):
        printDBG("VideoPenny.getVideoLinks [%s]" % videoUrl)
        urlTab = []
        
        if 0 == self.up.checkHostSupport(videoUrl): # 'rodzinnekino' not in self.cm.getBaseUrl(videoUrl):
            params = dict(self.defaultParams)
            params['header'] = dict(params['header'])
            params['header']['Referer'] = videoUrl.meta['Referer']
            params['max_data_size'] = 0
            params['save_cookie'] = False
            sts, data = self.getPage(videoUrl, params)
            if not sts: return []
            videoUrl = strwithmeta(self.cm.meta['url'], videoUrl.meta)

        if self.cm.isValidUrl(videoUrl):
            urlTab = self.up.getVideoLinkExt(videoUrl)
        return urlTab

    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('handleService start')
        
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if self.MAIN_URL == None:
            rm(self.COOKIE_FILE)
            self.selectDomain()

        name     = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode     = self.currItem.get("mode", '')
        
        printDBG( "handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category) )
        self.currList = []
        
    #MAIN MENU
        if name == None:
            self.listsTab(self.MAIN_CAT_TAB, {'name':'category'})
        elif category == 'list_sort_filter':
            self.listSortFilters(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem, 'explore_item')
        elif category == 'list_last':
            self.listLast(self.currItem, 'list_last_items')
        elif category == 'list_last_items':
            self.listLastItems(self.currItem)
        elif category == 'explore_item':
            self.exploreItem(self.currItem, 'list_sort_filter')
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
        CHostBase.__init__(self, VideoPenny(), True, [])
    