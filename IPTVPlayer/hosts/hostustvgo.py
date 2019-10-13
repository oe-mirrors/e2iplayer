# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm, byteify
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute
###################################################

###################################################
# FOREIGN import
###################################################
import re
import base64
try:    import json
except Exception: import simplejson as json
from Components.config import config, ConfigText, getConfigListEntry
from copy import deepcopy
###################################################

###################################################
# E2 GUI COMMPONENTS
###################################################
from Screens.MessageBox import MessageBox
###################################################

def gettytul():
    return 'http://ustvgo.tv/'

class ustvgo(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'ustvgo.org', 'cookie':'ustvgo.cookie'})
        
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'DNT':'1', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Language':'pl,en-US;q=0.7,en;q=0.3', 'Accept-Encoding':'gzip, deflate'}
        self.MAIN_URL = 'http://ustvgo.tv/'
        self.defaultParams = {'with_metadata':True, 'header':self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

    def getPage(self, baseUrl, addParams = {}, post_data = None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
            
        def _getFullUrl(url):
            if url == '': return ''
            
            if self.cm.isValidUrl(url):
                return url
            else:
                return urlparse.urljoin(baseUrl, url)
            
        addParams['cloudflare_params'] = {'domain':self.up.getDomain(baseUrl), 'cookie_file':self.COOKIE_FILE, 'User-Agent':self.USER_AGENT, 'full_url_handle':_getFullUrl}
        
        url = baseUrl
        urlParams = deepcopy(addParams)
        urlData = deepcopy(post_data)
        unloadUrl = None #
        tries = 0
        removeCookieItems = False
        while tries < 20:
            tries += 1
            sts, data = self.cm.getPageCFProtection(url, urlParams, urlData)
            if not sts: return sts, data

            if unloadUrl != None:
                self.cm.getPageCFProtection(unloadUrl, urlParams)
                unloadUrl = None
            
            if 'sucuri_cloudproxy' in data:
                cookieItems = {}
                jscode = self.cm.ph.getDataBeetwenNodes(data, ('<script', '>'), ('</script', '>'), False)[1]
                if 'eval' in jscode:
                    jscode = '%s\n%s' % (base64.b64decode('''dmFyIGlwdHZfY29va2llcz1bXSxkb2N1bWVudD17fTtPYmplY3QuZGVmaW5lUHJvcGVydHkoZG9jdW1lbnQsImNvb2tpZSIse2dldDpmdW5jdGlvbigpe3JldHVybiIifSxzZXQ6ZnVuY3Rpb24obyl7bz1vLnNwbGl0KCI7IiwxKVswXS5zcGxpdCgiPSIsMiksb2JqPXt9LG9ialtvWzBdXT1vWzFdLGlwdHZfY29va2llcy5wdXNoKG9iail9fSk7dmFyIHdpbmRvdz10aGlzLGxvY2F0aW9uPXt9O2xvY2F0aW9uLnJlbG9hZD1mdW5jdGlvbigpe3ByaW50KEpTT04uc3RyaW5naWZ5KGlwdHZfY29va2llcykpfTs='''), jscode)
                    ret = js_execute( jscode )
                    if ret['sts'] and 0 == ret['code']:
                        try:
                            cookies = byteify(json.loads(ret['data'].strip()))
                            for cookie in cookies: cookieItems.update(cookie)
                        except Exception:
                            printExc()
                self.defaultParams['cookie_items'] = cookieItems
                urlParams['cookie_items'] = cookieItems
                removeCookieItems = False
                sts, data = self.cm.getPageCFProtection(url, urlParams, urlData)
            
            # remove not needed used cookie
            if removeCookieItems:
                self.defaultParams.pop('cookie_items', None)
            self.cm.clearCookie(self.COOKIE_FILE, removeNames=['___utmvc'])
            #printDBG(data)
            return sts, data
        
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)
        
    def listMainMenu(self, cItem):
        MAIN_CAT_TAB = [{'category':'list_items',          'title': _('All')       ,   'url':self.getFullUrl('/')                         },
                        {'category':'list_category',       'title': 'Home'          ,   'url':self.getFullUrl('/')                         },
                        {'category':'list_category',       'title': 'Entertainment' ,   'url':self.getFullUrl('/category/entertainment/')  },
                        {'category':'list_category',       'title': 'News'          ,   'url':self.getFullUrl('/category/news/')           },
                        {'category':'list_category',       'title': 'Sports'        ,   'url':self.getFullUrl('/category/sports/')         },
                        {'category':'list_category',       'title': 'Kids'          ,   'url':self.getFullUrl('/category/kids/')           },]
        self.listsTab(MAIN_CAT_TAB, cItem)
    
    def listItems(self, cItem):
        printDBG("ustvgo.listItems")

        sts, data = self.getPage(cItem['url'])
        if not sts: return

        data = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'ul_pis_posts_in_sidebar-2'), ('</ul', '>'))[1]
        data = self.cm.ph.rgetAllItemsBeetwenNodes(data, ('</li', '>'), ('<li', '>', 'pis-li'))
        for item in data:
            url = self.getFullUrl( self.cm.ph.getSearchGroups(item, '''\shref=['"]([^"^']+?)['"]''')[0] )
            title = self.cleanHtmlStr(item)
            params = dict(cItem)
            params = {'good_for_fav': True, 'title':title, 'url':url}
            self.addVideo(params)

    def listCategory(self, cItem):
        printDBG("ustvgo.listCategory")

        page = cItem.get('page', 1)
        
        sts, data = self.getPage(cItem['url'])
        if not sts: return

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'nav-links'), ('</div', '>'), False)[1]
        nextPage = self.cm.ph.getDataBeetwenNodes(nextPage, ('<span', '>', 'aria-current'), ('</a', '>'), False)[1]
        nextPage = self.cm.ph.getSearchGroups(nextPage, '''href=['"]([^"^']+?)['"]''')[0]

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<article', '>', 'mh-posts'), ('</article', '>'))
        for item in data:
            tmp = self.cm.ph.getDataBeetwenNodes(item, ('<h3', '>'), ('</h3', '>'))[1]
            url = self.getFullUrl( self.cm.ph.getSearchGroups(tmp, '''\shref=['"]([^"^']+?)['"]''')[0] )
            title  = self.cleanHtmlStr(tmp)
            if not self.cm.isValidUrl(url): continue
            icon = self.getFullIconUrl( self.cm.ph.getSearchGroups(item, '''\ssrc=['"]([^"^']+?)['"]''')[0] )
            params = dict(cItem)
            params = {'good_for_fav': True, 'title':title, 'url':url, 'icon':icon}
            self.addVideo(params)

        if nextPage != '':
            params = dict(cItem)
            params.update({'title':_("Next page"), 'url':self.getFullUrl(nextPage), 'page':page+1})
            self.addDir(params)
        
    def getLinksForVideo(self, cItem):
        printDBG("ustvgo.getLinksForVideo [%s]" % cItem)
        
        sts, data = self.getPage(cItem['url'])
        if not sts: return

        data = self.cm.ph.getDataBeetwenMarkers(data, 'player.setup({', '})', False)[1]
        url  = self.cm.ph.getSearchGroups(data, '''(https?://[^'^"]+?)['"]''')[0] 

        return getDirectM3U8Playlist(url)
    
    def getVideoLinks(self, videoUrl):
        printDBG("ustvgo.getVideoLinks [%s]" % videoUrl)
        urlTab = []
        if 1 == self.up.checkHostSupport(videoUrl): 
            urlTab = self.up.getVideoLinkExt(videoUrl)
        return urlTab

    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name     = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode     = self.currItem.get("mode", '')
        
        printDBG( "handleService: >> name[%s], category[%s] " % (name, category) )
        self.currList = []
        
    #MAIN MENU
        if name == None:
            self.listMainMenu({'name':'category'})
        elif category == 'list_category':
            self.listCategory(self.currItem)
        elif category == 'list_items':
            self.listItems(self.currItem)
        else:
            printExc()
        
        CBaseHostClass.endHandleService(self, index, refresh)

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, ustvgo(), True, [])
    