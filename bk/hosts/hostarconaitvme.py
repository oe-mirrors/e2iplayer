# -*- coding: utf-8 -*-

#
#
# @Codermik release, based on @Samsamsam's E2iPlayer public.
# Released with kind permission of Samsamsam.
# All code developed by Samsamsam is the property of the Samsamsam and the E2iPlayer project,  
# all other work is ï¿½ E2iStream Team, aka Codermik.  TSiPlayer is ï¿½ Rgysoft, his group can be
# found here:  https://www.facebook.com/E2TSIPlayer/
#
# https://www.facebook.com/e2iStream/
#
#

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib
import base64
try:    import json
except Exception: import simplejson as json
###################################################

###################################################
# Config options for HOST
###################################################

def GetConfigList():
    optionList = []
    return optionList
###################################################


def gettytul():
    return 'http://arconaitv.us/'

class ArconaitvME(CBaseHostClass):
 
    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'  ArconaitvME.tv', 'cookie':'ArconaitvME.cookie'})
        self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.HEADER = {'User-Agent': 'Mozilla/5.0', 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update( {'X-Requested-With': 'XMLHttpRequest'} )
        
        self.MAIN_URL      = 'https://www.arconaitv.us/'
        self.DEFAULT_ICON_URL  = "https://raw.githubusercontent.com/piplongrun/arconaitv.bundle/master/Contents/Resources/icon-default.jpg"

        self.MAIN_CAT_TAB = [{'category':'list_main',      'title': _('Main'),      'url':self.MAIN_URL},
                             {'category':'list_shows',     'title': _('Shows'),     'url':self.MAIN_URL},
                             {'category':'list_cabletv',   'title': _('Cable'),     'url':self.MAIN_URL},
                             {'category':'list_movies',    'title': _('Movies'),    'url':self.MAIN_URL},
                             
                             {'category':'search',            'title': _('Search'), 'search_item':True,},
                             {'category':'search_history',    'title': _('Search history'),            } 
                            ]
        self.proxyUrl = 'http://myproxysite.ga/browse.php?u={0}&b=4&f=norefer'
        
    def isProxyNeeded(self, url):
        return False #'arconai.tv' in url
        
    def getDefaulIcon(self, cItem=None):
        return self.getFullIconUrl(self.DEFAULT_ICON_URL)
        
    def getPage(self, url, params={}, post_data=None):
        HTTP_HEADER= dict(self.HEADER)
        if post_data != None: HTTP_HEADER['Content-Type'] = 'application/x-www-form-urlencoded'
        params.update({'header':HTTP_HEADER})
        if self.isProxyNeeded( url ):
            proxy = self.proxyUrl.format(urllib.quote(url, ''))
            params['header']['Referer'] = proxy
            #params['header']['Cookie'] = 'flags=2e5;'
            url = proxy
        sts, data = self.cm.getPage(url, params, post_data)
        if sts and None == data:
            sts = False
        return sts, data
    
    def getFullIconUrl(self, url):
        url = self.getFullUrl(url)
        if self.isProxyNeeded( url ):
            proxy = self.proxyUrl.format(urllib.quote(url, ''))
            params = {}
            params['User-Agent'] = self.HEADER['User-Agent'],
            params['Referer'] = proxy
            #params['Cookie'] = 'flags=2e5;'
            url = strwithmeta(proxy, params) 
        return url
        
    def getFullUrl(self, url):
        if self.up.getDomain(self.proxyUrl) in url:
            url = urllib.unquote( self.cm.ph.getSearchGroups(url+'&', '''\?u=(http[^&]+?)&''')[0] )
        return CBaseHostClass.getFullUrl(self, url)
    
    def listItems(self, cItem, m1, m2, post_data=None):
        printDBG("ArconaitvME.listItems")
        sts, data = self.getPage(cItem['url'], post_data=post_data)
        if not sts: return
        
        data = self.cm.ph.getDataBeetwenReMarkers(data, re.compile(m1), re.compile(m2))[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a ', '</a>', False)
        
        for item in data:
            icon  = self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0]
            url = self.getFullUrl( self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0] )
            if url == '': continue
            title = self.cleanHtmlStr( self.cm.ph.getSearchGroups(item, '''title=['"]([^'^"]+?)['"]''')[0] )
            
            params = dict(cItem)
            params.update({'title':title, 'url':url, 'icon':self.getFullIconUrl( icon )})
            self.addVideo(params)
        
    def listMain(self, cItem):
        printDBG("ArconaitvME.listMain")
        self.listItems(cItem, '''<div[^>]+?class=['"]content['"][^>]*?>''', '''<div[^>]+?class=['"]stream-category['"][^>]*?>Shows</div>''')
    
    def listShows(self, cItem):
        printDBG("ArconaitvME.listShows")
        self.listItems(cItem, '''<div[^>]+?class=['"]stream-category['"][^>]*?>Shows</div>''', '''<div[^>]+?class=['"]acontainer['"][^>]*?>''')
        
    def listCableTv(self, cItem):
        printDBG("ArconaitvME.listCableTv")
        self.listItems(cItem, '''<div[^>]+?class=['"]stream-category['"][^>]*?>Cable</div>''', '''<div[^>]+?class=['"]acontainer['"][^>]*?>''')
        
    def listMovies(self, cItem):
        printDBG("ArconaitvME.listMovies")
        self.listItems(cItem, '''<div[^>]+?class=['"]stream-category['"][^>]*?>Movies</div>''', '''<div[^>]+?class=['"]acontainer['"][^>]*?>''')
        
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("ArconaitvME.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        url = self.getFullUrl('/search.php')
        cItem = dict(cItem)
        cItem['url'] = url
        self.listItems(cItem, '<div class="searchresults">', '<div class="acontainer">', post_data={'q':searchPattern})
        
    def getLinksForVideo(self, cItem):
        printDBG("ArconaitvME.getLinksForVideo [%s]" % cItem)
        urlsTab = []
        sts, data = self.getPage(cItem['url'])
        if not sts: return urlsTab
        
        playerUrl = self.cm.ph.getSearchGroups(data, '''<source[^>]*?src=['"](https?:[^"^']+?\.m3u8[^"^']*?)['"]''', 1, ignoreCase=True)[0]
        try: playerUrl = byteify(json.loads('"%s"' % playerUrl))
        except Exception: printExc()
        if not self.cm.isValidUrl(playerUrl): playerUrl = self.cm.ph.getSearchGroups(data, '''"sources"\s*:\s*[^\]]*?"src"\s*:\s*"(https?:[^"]+?\.m3u8[^"]*?)"''', 1, ignoreCase=True)[0]
        try: playerUrl = byteify(json.loads('"%s"' % playerUrl))
        except Exception: printExc()
        if not self.cm.isValidUrl(playerUrl): playerUrl = self.cm.ph.getSearchGroups(data, '''"(https?:[^"]+?\.m3u8[^"]*?)"''', 1, ignoreCase=True)[0]
        try: playerUrl = byteify(json.loads('"%s"' % playerUrl))
        except Exception: printExc()
        
        if not self.cm.isValidUrl(playerUrl):
            scripts = []
            tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<script', '>'), ('</script', '>'), False)
            for item in tmp:
                if 'eval(' not in item and 'ï¾Ïï¾ï¾=' not in item: continue
                scripts.append(item.strip())
            try:
                jscode = base64.b64decode('''dmFyIGRvY3VtZW50PXt9LHdpbmRvdz10aGlzLGVsZW1lbnQ9ZnVuY3Rpb24oZSl7dGhpcy5fbmFtZT1lLHRoaXMuc2V0QXR0cmlidXRlPWZ1bmN0aW9uKGUsdCl7InNyYyI9PWUmJih0aGlzLnNyYz10KX0sT2JqZWN0LmRlZmluZVByb3BlcnR5KHRoaXMsInNyYyIse2dldDpmdW5jdGlvbigpe3JldHVybiB0aGlzLl9zcmN9LHNldDpmdW5jdGlvbihlKXt0aGlzLl9zcmM9ZSxwcmludChlKX19KX0sJD1mdW5jdGlvbihlKXtyZXR1cm4gbmV3IGVsZW1lbnQoZSl9O2RvY3VtZW50LmdldEVsZW1lbnRCeUlkPWZ1bmN0aW9uKGUpe3JldHVybiBuZXcgZWxlbWVudChlKX0sZG9jdW1lbnQuZ2V0RWxlbWVudHNCeVRhZ05hbWU9ZnVuY3Rpb24oZSl7cmV0dXJuW25ldyBlbGVtZW50KGUpXX07''')
                ret = js_execute( jscode + '\nvar videojs={Hls:{xhr:{}}};function eval(data){print(data);}\n' + '\n'.join(scripts))
                decoded = self.cm.ph.getSearchGroups(ret['data'], '''['"]([^'^"]+?\.m3u8(?:\?[^'^"]*?)?)['"]''')[0].replace('\\/', '/')
                decoded = self.cm.getFullUrl(decoded, self.cm.meta['url'])
                if decoded.split('?', 1)[0].endswith('.m3u8'):
                    playerUrl = decoded
            except Exception:
                printExc()
        playerUrl = strwithmeta(playerUrl, {'User-Agent':self.HEADER['User-Agent'], 'Referer':cItem['url'], 'Origin':self.getMainUrl()})
        
        if self.cm.isValidUrl(playerUrl):
            tmp = getDirectM3U8Playlist(playerUrl, checkContent=True)
            for item in tmp:
                item['need_resolve'] = 0
                urlsTab.append(item)
        return urlsTab
        
    def getFavouriteData(self, cItem):
        return cItem['url']
        
    def getLinksForFavourite(self, fav_data):
        return self.getLinksForVideo({'url':fav_data})
        
    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('handleService start')
        
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name     = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode     = self.currItem.get("mode", '')
        filter   = self.currItem.get("filter", '')
        
        printDBG( "handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category) )
        self.currList = []
        
    #MAIN MENU
        if name == None:
            self.listsTab(self.MAIN_CAT_TAB, {'name':'category'})
        elif category == 'list_main':
            self.listMain(self.currItem)
        elif category == 'list_shows':
            self.listShows(self.currItem)
        elif category == 'list_cabletv':
            self.listCableTv(self.currItem)
        elif category == 'list_movies':
            self.listMovies(self.currItem)
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
        CHostBase.__init__(self, ArconaitvME(), True, favouriteTypes=[CDisplayListItem.TYPE_VIDEO])
    