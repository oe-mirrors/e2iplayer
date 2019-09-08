# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute
###################################################

###################################################
# FOREIGN import
###################################################
import re
from Components.config import config, ConfigText, getConfigListEntry
###################################################

###################################################
# E2 GUI COMMPONENTS 
###################################################
from Screens.MessageBox import MessageBox
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.nuteczki_login      = ConfigText(default = "", fixed_size = False)
config.plugins.iptvplayer.nuteczki_password   = ConfigText(default = "", fixed_size = False)

def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("login"), config.plugins.iptvplayer.nuteczki_login))
    optionList.append(getConfigListEntry(_("password"), config.plugins.iptvplayer.nuteczki_password))
    return optionList
###################################################


def gettytul():
    return 'https://nuteczki.eu/'

class NuteczkiEU(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'nuteczki.eu', 'cookie':'nuteczki.eu.cookie'})
        
        self.USER_AGENT = 'Mozilla/5.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update( {'X-Requested-With':'XMLHttpRequest', 'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8'} )
        
        self.MAIN_URL = 'https://nuteczki.eu/'
        self.DEFAULT_ICON_URL = 'https://i.pinimg.com/736x/2d/07/83/2d0783d156a48860691667dadd8de458--note-music-music-wallpaper.jpg'
        
        self.defaultParams = {'header':self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.cacheFilters = {}
        self.cacheFiltersKeys = []
        
        self.loggedIn = None
        self.login    = ''
        self.password = ''
    
    def getPage(self, baseUrl, addParams = {}, post_data = None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)
    
    def listMainMenu(self, cItem):
        printDBG("NuteczkiEU.listMainMenu")
        
        sts, data = self.getPage(self.getMainUrl())
        if not sts: return
        self.setMainUrl(self.cm.meta['url'])
        
        
        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'drop-cat'), ('</span', '>'), False)[1]
        tmp = re.compile('(<li[^>]*?>|</li>|<ul[^>]*?>|</ul>)').split(tmp)
        if len(data) > 1:
            try:
                cTree = self.listToDir(tmp[1:-1], 0)[0]
                tmpList = []
                for item in cTree['list']:
                    tmpList.extend(item['list'])
                cTree = {'data':'', 'list':tmpList}
                
                params = dict(cItem)
                params.update({'category':'categories', 'title':_('Main menu'), 'c_tree':cTree})
                self.addDir(params)
            except Exception:
                printExc()
        
        MAIN_CAT_TAB = [
                        {'category':'top10',           'title': _('TOP 10'),      'url':self.getFullUrl('/top10/') },
                        {'category':'filters',         'title': _('Filters'),     'url':self.getFullUrl('/muzyka/'), 'post_data':{}},
                        {'category':'search',          'title': _('Search'), 'search_item':True},
                        {'category':'search_history',  'title': _('Search history')} ]
        self.listsTab(MAIN_CAT_TAB, cItem)
        
       
    def listCategories(self, cItem, nextCategory):
        printDBG("NuteczkiEU.listCategories")
        try:
            cTree = cItem['c_tree']
            for item in cTree['list']:
                title = self.cleanHtmlStr(item['dat'])
                url = self.cm.ph.getSearchGroups(item['dat'], '''href=['"]([^'^"]+?)['"]''')[0]
                if url == '#': url = ''
                else: url = self.getFullUrl(url)
                if 'list' not in item:
                    if self.cm.isValidUrl(url) and title != '':
                        params = dict(cItem)
                        params.update({'good_for_fav':False, 'category':nextCategory, 'title':title, 'url':url})
                        self.addDir(params)
                elif len(item['list']) == 1 and title != '':
                    obj = item['list'][0]
                    if url != '' and 'list' in obj:
                        obj['list'].insert(0, {'dat':'<a href="%s">%s</a>' % (url, _('--All--'))})
                    params = dict(cItem)
                    params.update({'good_for_fav':False, 'c_tree':obj, 'title':title, 'url':url})
                    self.addDir(params)
        except Exception:
            printExc()
        
    def top10Types(self, cItem, nextCategory):
        printDBG("NuteczkiEU.top10Types")
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        
        data = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'nav-top10'), ('<footer', '>'))[1]
        
        # main tabs
        mainMap = {}
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<ul', '</ul>')[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li', '</li>')
        
        for item in tmp:
            title = self.cleanHtmlStr(item)
            marker = self.cm.ph.getSearchGroups(item, '''href=['"]\#([^'^"]+?)['"]''')[0]
            if marker != '': mainMap[marker] = title
        
        data = re.compile('''<div[^>]+?id=['"](%s)['"][^>]*?>''' % '|'.join(mainMap.keys())).split(data)
        for mainIdx in range(1, len(data), 2):
            mainTitle = mainMap[data[mainIdx]]
            
            subMap = {}
            tmp = self.cm.ph.getDataBeetwenMarkers(data[mainIdx+1], '<ul', '</ul>')[1]
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li', '</li>')
            for item in tmp:
                title = self.cleanHtmlStr(item)
                marker = self.cm.ph.getSearchGroups(item, '''href=['"]\#([^'^"]+?)['"]''')[0]
                if marker != '': subMap[marker] = title
            
            subItems = []
            subData = re.compile('''<div[^>]+?id=['"](%s)['"][^>]*?>''' % '|'.join(subMap.keys())).split(data[mainIdx+1])
            for subIdx in range(1, len(subData), 2):
                subTitle = subMap[subData[subIdx]]
                
                items = []
                tmp = self.cm.ph.rgetAllItemsBeetwenNodes(subData[subIdx+1], ('</div', '>'), ('<div', '>', 'row'), False)
                for item in tmp:
                    icon = self.getFullIconUrl( self.cm.ph.getSearchGroups(item, '''<img[^>]+?src=['"]([^"^']+?)['"]''')[0] )
                    url = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0]
                    if url == '#': 
                        url = self.cm.ph.getSearchGroups(item, '''(<div[^>]+?getPlayer[^>]+?>)''')[0]
                        url = self.cm.ph.getSearchGroups(url, '''\sid=['"]([^"^']+?)['"]''')[0]
                        if url != '': url = '/getPlayer.php?id=' + url
                    url = self.getFullUrl( url )
                    
                    title = self.cleanHtmlStr( self.cm.ph.getSearchGroups(item, '''alt="([^"]+?)"''')[0] )
                    desc = self.cleanHtmlStr( self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'news-meta'), ('</div', '>'), False)[1] )
                    params = dict(cItem)
                    params.update({'good_for_fav': True, 'title':title, 'url':url, 'desc':desc, 'icon':icon})
                    if url != '':
                        params['type'] = 'audio'
                    else:
                        params['title'] = _('[Logged-in-only] ') + params['title']
                        params['type'] = 'article'
                    items.append(params)
                
                if len(items):
                    params = dict(cItem)
                    params.update({'good_for_fav': False, 'category':nextCategory, 'title':subTitle, 'sub_items':items})
                    subItems.append(params)
            if len(subItems):
                params = dict(cItem)
                params.update({'good_for_fav': False, 'category':nextCategory, 'title':mainTitle, 'sub_items':subItems})
                self.addDir(params)
        
    def fillCacheFilters(self, cItem):
        printDBG("NuteczkiEU.listCategories")
        self.cacheFilters = {}
        self.cacheFiltersKeys = []
        
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        self.setMainUrl(self.cm.meta['url'])
        
        def addFilter(data, marker, baseKey):
            self.cacheFilters[key] = []
            for item in data:
                value = self.cm.ph.getSearchGroups(item, marker + '''="([^"]+?)"''')[0]
                if value == '': continue
                title = self.cleanHtmlStr(item)
                self.cacheFilters[key].append({'title':title, 'post_data':{key:value}})
                
            if len(self.cacheFilters[key]):
                self.cacheFiltersKeys.append(key)
        
        data = self.cm.ph.getDataBeetwenNodes(data, ('<form', '>', 'filter'), ('</form', '>'), False)[1]
        filtersData = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'form-group'), ('</div', '>'))
        
        for tmp in filtersData:
            key = self.cm.ph.getSearchGroups(tmp, '''name="([^"]+?)"''')[0]
            if key == '': continue
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<option', '</option>')
            addFilter(tmp, 'value', key)
        
        printDBG(self.cacheFilters)
        
    def listFilters(self, cItem, nextCategory):
        printDBG("NuteczkiEU.listFilters")
        cItem = dict(cItem)
        
        f_idx = cItem.get('f_idx', 0)
        if f_idx == 0: self.fillCacheFilters(cItem)
        
        if f_idx >= len(self.cacheFiltersKeys): return
        
        filter = self.cacheFiltersKeys[f_idx]
        f_idx += 1
        cItem['f_idx'] = f_idx
        if f_idx  == len(self.cacheFiltersKeys):
            cItem['category'] = nextCategory
            
        for item in self.cacheFilters.get(filter, []):
            params = dict(cItem)
            params['post_data'] = dict(params['post_data'])
            params['post_data'] .update(item['post_data'])
            params['post_data']['filter-enable-category'] = 105 # no idea what this is
            params['title'] = item['title']
            self.addDir(params)

    def listItems(self, cItem):
        printDBG("NuteczkiEU.listItems")
        page = cItem.get('page', 1)

        postData = cItem.get('post_data')
        sts, data = self.getPage(cItem['url'], post_data = postData)
        if not sts: return

        nextPage = ''
        tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'pagination'), ('</div', '>'), False)
        for item in tmp:
            nextPage = self.cm.ph.getSearchGroups(item, '''<a[^>]+?href=['"]([^'^"]+?)['"][^>]*?>%s</a>''' % (page + 1))[0]
            if nextPage != '': break

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'dle-content'), ('<div', '>', 'clearfix'), False)[1]
        data = self.cm.ph.rgetAllItemsBeetwenNodes(data, ('</div', '>'), ('<div', '>', 'row'), False)
        for item in data:
            icon = self.getFullIconUrl( self.cm.ph.getSearchGroups(item, '''<img[^>]+?src=['"]([^"^']+?)['"]''')[0] )

            tmp = self.cm.ph.getDataBeetwenNodes(item, ('<h2', '>', 'news-title'), ('</h2', '>'))[1]
            if tmp == '': 
                tmp = self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'short-result'), ('</div', '>'))[1]
                title = self.cleanHtmlStr( self.cm.ph.getSearchGroups(tmp, '''alt="([^"]+?)"''')[0] )
            else:
                title = self.cleanHtmlStr( tmp )
            
            url = self.cm.ph.getSearchGroups(tmp, '''href=['"]([^"^']+?)['"]''')[0]
            if url == '#': 
                url = self.cm.ph.getSearchGroups(item, '''(<div[^>]+?getPlayer[^>]+?>)''')[0]
                url = self.cm.ph.getSearchGroups(url, '''\sid=['"]([^"^']+?)['"]''')[0]
                if url != '': url = '/getPlayer.php?id=' + url
            url = self.getFullUrl( url )
            
            desc = []
            tmp = self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'news-meta'), ('</div', '>'))[1]
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<span', '</span>')
            for t in tmp:
                label = self.cm.ph.getSearchGroups(t, '''fa\-([a-zA-Z]+?)\s''')[0]
                t = self.cleanHtmlStr(t)
                if t != '':
                    try:
                        desc.append('%s: %s' % (label.title(), int(t)))
                    except Exception:
                        desc.append(t.replace(' , ', ', '))

            params = dict(cItem)
            params.update({'good_for_fav': True, 'title':title, 'url':url, 'desc':'[/br]'.join(desc), 'icon':icon})
            if url != '':
                self.addAudio(params)
            elif 'playerMask' in item:
                params['title'] = _('[Logged-in-only] ') + params['title']
                self.addArticle(params)

        if nextPage != '':
            params = dict(cItem)
            params.pop('desc', None)
            
            if 'post_data' in params and 'do=search' in cItem['url']:
                nextPage = cItem['url']
                params['post_data'] = dict(params['post_data'])
                params['post_data'].update({'search_start':page+1, 'full_search':'0', 'result_from':params['post_data'].get('result_from', 1) + len(self.currList)})
            
            params.update({'title':_("Next page"), 'url':self.getFullUrl(nextPage), 'page':page+1})
            self.addDir(params)
        
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("NuteczkiEU.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('/index.php?do=search')
        cItem['post_data'] = {'do':'search', 'subaction':'search', 'story':searchPattern}
        cItem['category'] = 'list_items'
        self.listItems(cItem)
    
    def getLinksForVideo(self, cItem):
        printDBG("NuteczkiEU.getLinksForVideo [%s]" % cItem)
        self.tryTologin()
        
        urlTab = []
        
        sts, data = self.getPage(cItem['url'])
        if not sts: return []
        self.setMainUrl(self.cm.meta['url'])
        
        tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'frame-fixer'), ('</div', '>'), caseSensitive=False)
        for idx in range(len(tmp)):
            url = self.getFullUrl(self.cm.ph.getSearchGroups(tmp[idx], '''\sdata\-url=['"]([^"^']+?)['"]''', 1, True)[0])
            if 1 != self.up.checkHostSupport(url):
                jscode = []
                jsData = self.cm.ph.getAllItemsBeetwenNodes(tmp[idx], ('<script', '>'), ('</script', '>'), caseSensitive=False)
                for jsItem in jsData:
                    if 'src=' in jsItem.lower():
                        scriptUrl = self.getFullUrl(self.cm.ph.getSearchGroups(jsItem, '''<script[^>]+?src=['"]([^'^"]*?krakenfiles[^'^"]+?)['"]''', 1, True)[0], self.cm.meta['url'])
                        sts, jsItem = self.getPage(scriptUrl)
                        if sts and jsItem != '': jscode.append(jsItem)
                    else:
                        sts, jsItem = self.cm.ph.getDataBeetwenNodes(jsItem, ('<script', '>'), ('</script', '>'), False, caseSensitive=False)
                        if sts: jscode.append(jsItem)
                if len(jscode):
                    jscode.insert(0, 'window={}; window.location={}; window.location.protocol="%s"; var document={}; document.write=function(txt){print(txt);}' % self.getMainUrl().split('//', 1)[0])
                    ret = js_execute('\n'.join(jscode), {'timeout_sec':15})
                    if ret['sts'] and 0 == ret['code']:
                        printDBG(ret['data'])
                        data += ret['data'].strip()
                    
            elif 'facebook' not in url.lower(): 
                name = _('Player %s: %s') % (idx+1, self.up.getHostName(url))
                urlTab.append({'url':url, 'name':name, 'need_resolve':1})
        
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(data, '<iframe', '</iframe>', caseSensitive=False)
        for idx in range(len(tmp)):
            url = self.getFullUrl(self.cm.ph.getSearchGroups(tmp[idx], '''\ssrc=['"]([^"^']+?)['"]''', 1, True)[0])
            if url == '' or 'facebook' in url.lower(): continue
            name = _('Player %s') % (idx + 1)
            urlTab.append({'url':url, 'name':name, 'need_resolve':1})
        
        return urlTab
        
    def getVideoLinks(self, videoUrl):
        printDBG("NuteczkiEU.getVideoLinks [%s]" % videoUrl)

        if 1 == self.up.checkHostSupport(videoUrl):
            return self.up.getVideoLinkExt(videoUrl)

        urlTab = []
        sts, data = self.getPage(videoUrl)
        if not sts: return []

        printDBG(data)

        urls = []
        data = re.compile('''['"]([^'^"]*?/music[^'^"]+?\.mp3(?:\?[^'^"]*?)?)['"]''', re.I).findall(data)
        for url in data:
            url = self.getFullUrl(url)
            if url == '' or url in urls: continue
            urls.append(url)
            name = self.cm.ph.getSearchGroups(url, '''/music([^'^"]*?)/''')[0]
            if name == '': name = 'SD'
            urlTab.append({'name':name, 'url':url})
        urlTab.sort(key=lambda item: item['name'])
        return urlTab
        
    def tryTologin(self):
        printDBG('tryTologin start')
        
        if None == self.loggedIn or self.login != config.plugins.iptvplayer.nuteczki_login.value or\
            self.password != config.plugins.iptvplayer.nuteczki_password.value:
        
            self.login = config.plugins.iptvplayer.nuteczki_login.value
            self.password = config.plugins.iptvplayer.nuteczki_password.value
            
            rm(self.COOKIE_FILE)
            
            self.loggedIn = False
            
            if '' == self.login.strip() or '' == self.password.strip():
                return False
            
            sts, data = self.getPage(self.getMainUrl())
            if not sts: return False
            self.setMainUrl(self.cm.meta['url'])
            
            actionUrl = self.cm.meta['url']
            post_data = {'login_name':self.login, 'login_password':self.password, 'login':'submit'}

            httpParams = dict(self.defaultParams)
            httpParams['header'] = dict(self.AJAX_HEADER)
            httpParams['header']['Referer'] = self.cm.meta['url']
            sts, data = self.cm.getPage(actionUrl, httpParams, post_data)
            if sts and 'action=logout' in data:
                printDBG('tryTologin OK')
                self.loggedIn = True
            else:
                msgTab = [_('Login failed.')]
                if sts: msgTab.append(self.cleanHtmlStr(self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'alert'), ('</div', '>'), False)[1])) 
                self.sessionEx.open(MessageBox, '\n'.join(msgTab), type = MessageBox.TYPE_ERROR, timeout = 10)
                printDBG('tryTologin failed')
        return self.loggedIn

    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('handleService start')
        
        self.tryTologin()
        
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name     = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode     = self.currItem.get("mode", '')
        
        printDBG( "handleService: || name[%s], category[%s] " % (name, category) )
        self.currList = []
        self.currItem = dict(self.currItem)
        self.currItem.pop('good_for_fav', None)
        
    #MAIN MENU
        if name == None:
            self.listMainMenu({'name':'category'})
        
        elif category == 'categories':
            self.listCategories(self.currItem, 'list_items')
        
        elif category == 'list_items':
            self.listItems(self.currItem)
        
        elif category == 'top10':
            self.top10Types(self.currItem, 'sub_items')
        
        elif category == 'filters':
            self.listFilters(self.currItem, 'list_items')

        elif category == 'sub_items':
            self.currList = self.currItem.get('sub_items', [])
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
        CHostBase.__init__(self, NuteczkiEU(), True, favouriteTypes=[]) 

