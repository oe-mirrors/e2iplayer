# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import  printDBG, printExc, GetDefaultLang, rm, byteify
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.recaptcha_v2 import UnCaptchaReCaptcha
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs import ph
###################################################

###################################################
# E2 GUI COMMPONENTS 
###################################################
from Screens.MessageBox import MessageBox
###################################################
# FOREIGN import
###################################################
import base64
import re
import urlparse
import urllib
from Components.config import config, ConfigText, ConfigSelection, getConfigListEntry
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.ekinotv_login = ConfigText(default = "", fixed_size = False)
config.plugins.iptvplayer.ekinotv_password = ConfigText(default = "", fixed_size = False)

config.plugins.iptvplayer.ekinotv_sortby = ConfigSelection(default = "data-dodania", choices = [("alfabetycznie", "nazwy"), ("ocena", "oceny"),("odslony", "ilości odsłon"),("data-dodania", "daty dodania"),("data-premiery", "daty premiery"), ('data-aktualizacji', 'daty aktualizacji')])            
config.plugins.iptvplayer.ekinotv_sortorder = ConfigSelection(default = "desc", choices = [("desc", "malejąco"),("asc", "rosnąco")]) 

def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry("Ekino TV login:", config.plugins.iptvplayer.ekinotv_login))
    optionList.append(getConfigListEntry("Ekino TV hasło:", config.plugins.iptvplayer.ekinotv_password))
    optionList.append(getConfigListEntry("Sortuj według:", config.plugins.iptvplayer.ekinotv_sortby))
    optionList.append(getConfigListEntry("Kolejność wyświetlania:", config.plugins.iptvplayer.ekinotv_sortorder))
    return optionList
###################################################

def gettytul():
    return 'http://ekino-tv.pl/'

class EkinoTv(CBaseHostClass):
    
    def __init__(self):
        printDBG("EkinoTv.__init__")
        CBaseHostClass.__init__(self, {'history':'EkinoTv.tv', 'cookie':'ekinotv.cookie'})
        self.MAIN_URL = 'https://ekino-tv.pl/'
        self.DEFAULT_ICON_URL = 'https://img.cda.pl/obr/oryginalne/c53be9b25636d46fabbb0ec78abe75c8.png'
        self.FILMS_CAT_URL = self.getFullUrl('/movie/cat/')  
        
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT':'1', 'Accept': 'text/html', 'Accept-Encoding':'gzip, deflate', 'Referer':self.getMainUrl(), 'Origin':self.getMainUrl()}
        
        self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE, 'cookie_items':{'prch':'true'}}
        
        self.MAIN_CAT_TAB = [{'category':'list_cats',             'title': 'Filmy',           'url':self.FILMS_CAT_URL},
                             {'category':'series_abc',            'title': 'Seriale',         'url':self.getFullUrl('/serie/')},
                             {'category':'list_movies',           'title': 'Dla dzieci',      'url':self.FILMS_CAT_URL, 'cat':'2,3,5,6'},
                             {'category':'search',                'title': _('Search'), 'search_item':True},
                             {'category':'search_history',        'title': _('Search history')} ]
        
        self.SORT_MAP  = {'data-dodania':'add',
                          'data-aktualizacji':'update',
                          'data-premiery':'premiera',
                          'data-premiery':'premiera',
                          'odslony':'views',
                          'ocena':'rate',
                          'alfabetycznie':'alfa',}
        
        self.cacheMovieFilters = {'cats':[], 'vers':[], 'years':[]}
        self.loggedIn = None
        self.login    = ''
        self.password = ''
        self.loginMessage = ''
        
    def getPage(self, baseUrl, addParams = {}, post_data = None):
        if addParams == {}: addParams = dict(self.defaultParams)
        origBaseUrl = baseUrl
        baseUrl = self.cm.iriToUri(baseUrl)
        def _getFullUrl(url):
            if self.cm.isValidUrl(url): return url
            else: return urlparse.urljoin(baseUrl, url)
        addParams['cloudflare_params'] = {'domain':self.up.getDomain(baseUrl), 'cookie_file':self.COOKIE_FILE, 'User-Agent':self.USER_AGENT, 'full_url_handle':_getFullUrl}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)
    
    def getFullIconUrl(self, url):
        url = CBaseHostClass.getFullIconUrl(self, url.strip())
        if url == '': return ''
        cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE, ['cf_clearance'])
        return strwithmeta(url, {'Cookie':cookieHeader, 'User-Agent':self.USER_AGENT})
    
    def _checkNexPage(self, data, page):
        if -1 != data.find('strona[%s]' % page):
            return True
        else: return False
    
    ###################################################
    def _fillMovieFilters(self):
        self.cacheMovieFilters = { 'cats':[], 'vers':[], 'years':[]}
        sts, data = self.getPage(self.FILMS_CAT_URL)
        if not sts: return
        
        # fill cats
        dat = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="movieCategories">', '</ul>', False)[1]
        dat = re.compile('<a[^"]+?href="[^"]+?kategoria\[([0-9]+?)\][^>]*?>([^<]+?)<').findall(dat)
        for item in dat:
            self.cacheMovieFilters['cats'].append({'title': self.cleanHtmlStr(item[1]), 'cat': item[0]})
            
        # fill vers
        dat = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="quality"', '</ul>', False)[1]
        dat = re.compile('<li[^>]+?data-id="([^"]+?)"[^>]*?>(.+?)</li>').findall(dat)
        for item in dat:
            self.cacheMovieFilters['vers'].append({'title': self.cleanHtmlStr(item[1]), 'ver': item[0]})
            
        # fill years
        dat = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="filtyear">', '</ul>', False)[1]
        dat = re.compile('<li[^>]+?data-id="([^"]+?)"[^>]*?>(.+?)</li>').findall(dat)
        for item in dat:
            self.cacheMovieFilters['years'].append({'title': self.cleanHtmlStr(item[1]), 'year': item[0]})
    
    ###################################################
    def listMovieFilters(self, cItem, category):
        printDBG("EkinoTv.listMovieFilters")
        
        filter = cItem['category'].split('_')[-1]
        if 0 == len(self.cacheMovieFilters[filter]):
            self._fillMovieFilters()
        if len(self.cacheMovieFilters[filter]) > 0:
            filterTab = [{'title':'--Wszystkie--'}]
            filterTab.extend(self.cacheMovieFilters[filter])
            self.listsTab(filterTab, cItem, category)
        
    def listsTab(self, tab, cItem, category=None):
        printDBG("EkinoTv.listsTab")
        for item in tab:
            params = dict(cItem)
            if None != category:
                params['category'] = category
            params['desc'] = self.loginMessage
            params.update(item)
            self.addDir(params)
            
    def _addItems(self, cItem, dataTab, category='video'):
        for item in dataTab:
            item = item.split('</span>')
            title = self.cleanHtmlStr('<' + item[0])
            ids = self.cm.ph.getSearchGroups(item[0], 'id="([^"]+?)"')[0].split('-')
            if len(ids) > 2 and '' != ids[-1]:
                title += ' [%s]' % (ids[-1])
            url    = self.cm.ph.getSearchGroups(item[0], 'href="([^"]+?)"')[0]
            icon   = self.cm.ph.getSearchGroups(item[0], 'src="([^"]+?jpg)"')[0]
            if url == '': continue
            params = dict(cItem)
            params.update({'good_for_fav':True, 'title':self.cleanHtmlStr(title), 'url':self.getFullUrl(url), 'icon': self.getFullIconUrl(icon), 'desc': self.cleanHtmlStr(item[-1])})
            if category == 'video':
                self.addVideo(params)
            else:
                params['category'] = category
                self.addDir(params)
        
    def listMovies(self, cItem):
        printDBG("EkinoTv.listMovies")
        
        # prepare url
        sortby    = config.plugins.iptvplayer.ekinotv_sortby.value          
        sortorder = config.plugins.iptvplayer.ekinotv_sortorder.value
        page = cItem.get('page', 1)
        url  = cItem['url'] + 'strona[%s]+sort[%s]+method[%s]+' % (page, self.SORT_MAP[sortby], sortorder)
        
        for item in [('cat', 'kategoria'), ('ver', 'wersja'), ('year', 'rok')]:
            if item[0] in cItem:
                url += '%s[%s]+' % (item[1], cItem[item[0]])
        
        sts, data = self.getPage(url)
        if not sts: return
        
        # parse data
        nextPage = self._checkNexPage(data, page+1)
        sp = '<div class="movies-list-item"'
        data = self.cm.ph.getDataBeetwenMarkers(data, sp, '<div id="pager">', False)[1]
        data = data.split(sp)
        self._addItems(cItem, data)
        
        if nextPage:
            params = dict(cItem)
            params.update({'title':_('Next page'), 'page':page+1})
            self.addDir(params)
                
    def listsSeriesABC(self, cItem, category):
        printDBG('EkinoTv.listsSeriesABC start')
        sts, data = self.getPage(cItem['url'])
        if sts:
            data = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="serialsmenu">', '</ul>', False)[1]
            data = re.compile('<a[^"]+?href="([^"]+?)"[^>]*?><span class="name">([^<]+?)</span><span class="count">([^<]+?)<').findall(data)
            for item in data:
                params = dict(cItem)
                params.update({'category':category, 'title':'%s (%s)' % (item[1], item[2]), 'url':self.getFullUrl(item[0])})
                self.addDir(params)
                
    def listsSeries(self, cItem, category):
        printDBG('EkinoTv.listsSeries start')
        page = cItem.get('page', 1)
        url  = cItem['url'] + ',strona=%s' % page
        
        sts, data = self.getPage(url)
        if not sts: return
        
        nextPage = False
        if (',strona=%s"' % (page+1)) in data:
            nextPage = True
        
        sp = '<div class="movies-list-item"'
        data = self.cm.ph.getDataBeetwenMarkers(data, sp, '<div id="pager">', False)[1]
        data = data.split(sp)
        self._addItems(cItem, data, category)
        
        if nextPage:
            params = dict(cItem)
            params.update({'title':_('Next page'), 'page':page+1})
            self.addDir(params)
                
    def listEpisodes(self, cItem):
        printDBG('EkinoTv.listEpisodes start')
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        data = self.cm.ph.getDataBeetwenMarkers(data, '<div id="list-series"', '<br style="clear:both">', False)[1]
        data = data.split('</ul>')
        if len(data): del data[-1]
        for season in data:
            sTitle = self.cm.ph.getDataBeetwenMarkers(season, '<p>', '</p>', False)[1]
            eData = re.compile('<a[^>]+?href="([^"]+?)"[^>]*?>([^<]+?)<').findall(season)
            for eItem in eData:
                s = self.cm.ph.getSearchGroups(eItem[0], 'season\[([0-9]+?)\]')[0]
                e = self.cm.ph.getSearchGroups(eItem[0], 'episode\[([0-9]+?)\]')[0]
                title = '%s s%se%s %s' % (cItem['title'], s.zfill(2), e.zfill(2), eItem[1])
                params = dict(cItem)
                params.update({'title':title, 'url':self.getFullUrl(eItem[0])})
                self.addVideo(params)
    
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("EkinoTv.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        searchPattern = searchPattern.replace(' ', '+')
        
        url = 'https://ekino-tv.pl/s/search?q=' + urllib.quote_plus(searchPattern)
        sts, data = self.getPage(url)
        if not sts: return
        if not 'search' in self.cm.meta['url']:
            url = 'https://ekino-tv.pl/se/search?q=' + urllib.quote_plus(searchPattern)
            sts, data = self.getPage(url)
            if not sts: return
        
        if 'movies' == searchType:
            sp = '<div class="movies-list-item"'
            data = self.cm.ph.getDataBeetwenMarkers(data, sp, 'Znalezione seriale', False)[1]
            data = data.split(sp)
            self._addItems(cItem, data)
        else:
            sp = '<div class="movies-list-item"'
            data = self.cm.ph.getDataBeetwenMarkers(data, 'Znalezione seriale', '<br style="clear:both">', False)[1]
            data = data.split(sp)
            if len(data): del data[0]
            self._addItems(cItem, data, 'series_episodes')

    def getLinksForVideo(self, cItem):
        printDBG("EkinoTv.getLinksForVideo [%s]" % cItem)
        self.tryTologin()
        
        urlTab = []
        premiumTab = []
        ultraTab = []
        
        if self.loggedIn: self.cm.clearCookie(self.COOKIE_FILE, removeNames=['pplayer'])
        
        sts, data = self.getPage(cItem['url'])
        if not sts: return []
        
        baseVidUrl = self.cm.ph.getSearchGroups(data, '''src=['"]([^'^"]*?/watch/[^'^"]*?)['"]''')[0]
        if baseVidUrl == '': baseVidUrl = 'watch/f/'
        
        if 'dmcabitch.jpg' in data:
            message = self.cm.ph.getDataBeetwenMarkers(data, '<div class="playerContainer"', '<br style="clear:both">', True)[1]
            SetIPTVPlayerLastHostError(self.cleanHtmlStr(message))
            return []
        
        reTitleObj = re.compile('''title=['"]([^"^']+?)['"]''')
        
        def _findHostingLinks(data, linkTab, premium):
            if premium:
                jscode = [base64.b64decode('''dmFyIGRvY3VtZW50PXt9LHdpbmRvdz10aGlzLGVsZW1lbnQ9ZnVuY3Rpb24obil7dGhpcy5odG1sPWZ1bmN0aW9uKG4pe3ByaW50KG4pfSx0aGlzLmhpZGU9ZnVuY3Rpb24oKXt9fSwkPWZ1bmN0aW9uKG4pe3JldHVybiBuZXcgZWxlbWVudChuKX07''')]
                tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<script', '>'), ('</script', '>'), False)
                for item in tmp:
                    if 'function ShowPlayer(' in item:
                        jscode.append(item)
                        break
                jscode = '\n'.join(jscode)
        
            playersData = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="players"', '</ul>', False)[1]
            
            playersData = playersData.split('</li>')
            if len(playersData): del playersData[-1]
            players = []
            for item in playersData:
                item = self.cm.ph.getDataBeetwenMarkers(item, '<li>', '</a>', False)[1]
                title = self.cleanHtmlStr(item)
                id = self.cm.ph.getSearchGroups(item, 'href="#([^"]+?)"')[0]
                tmp = reTitleObj.findall(item)
                title += ' ' + ' '.join(tmp)
                players.append({'title':title, 'id':id})
            
            tmp = self.cm.ph.getDataBeetwenMarkers(data, '<div class="tab-content">', '<script>', False)[1]
            tmp = tmp.split('</div>')
            if len(tmp): del tmp[-1]
            for item in tmp:
                id  = self.cm.ph.getSearchGroups(item, 'id="([^"]+?)"')[0]
                playerParams = self.cm.ph.getSearchGroups(item, '''ShowPlayer[^"^']*?['"]([^"^']+?)['"]\s*\,\s*['"]([^"^']+?)['"]''', 2)
                url = ''
                if premium and '' not in playerParams:
                    ret = js_execute( jscode + ('\nShowPlayer("%s","%s");' % (playerParams[0], playerParams[1])))
                    if ret['sts'] and 0 == ret['code']:
                        printDBG(ret['data'])
                        url = self.getFullUrl(self.cm.ph.getSearchGroups(ret['data'], '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', ignoreCase=True)[0])
                else:
                    if '' not in playerParams: url = baseVidUrl + '/'.join(playerParams)
                    if url == '': url = self.cm.ph.getSearchGroups(item, 'src="([^"]+?)"')[0]
                    
                url = self.getFullUrl(url)
                if url == '' or url.split('?', 1)[0].split('.')[-1].lower() in ['jpg', 'jepg', 'gif', 'png']:
                    continue
                for p in players:
                    if p['id'] == id:
                        if premium: title = '[premium] %s' % p['title']
                        else: title = p['title']
                        linkTab.append({'name':title, 'url':strwithmeta(url, {'Referer':cItem['url']}), 'need_resolve':1})
                        break
        
        _findHostingLinks(data, urlTab, False)
        if self.loggedIn:
            setUltra = 'setUltra()' in data
            baseVidUrl = 'watch/p/'
            data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'select_premium'), ('</ul', '>'), False)[1]
            data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<li', '>'), ('</li', '>'))
            for item in data:
                playerParams = []
                playerParams.append(self.cm.ph.getSearchGroups(item, '''data\-vhost=['"]([^'^"]+?)['"]''')[0])
                playerParams.append(self.cm.ph.getSearchGroups(item, '''data\-file=['"]([^'^"]+?)['"]''')[0])
                if '' in playerParams: continue
                url = self.getFullUrl(baseVidUrl + '/'.join(playerParams))
                title = self.cleanHtmlStr(item)
                tmp   = reTitleObj.findall(item)
                title += ' ' + ' '.join(tmp)
                premiumTab.append({'name':'[premium] %s' % title, 'url':strwithmeta(url, {'Referer':cItem['url'], 'is_premium':True}), 'need_resolve':1})
            
            if setUltra:
                urlParams = dict(self.defaultParams)
                urlParams['cookie_items'] = {'pplayer':'1'}
                sts, data = self.getPage(cItem['url'], urlParams)
                if sts and 'setStandard()' in data:
                    _findHostingLinks(data, ultraTab, True)
                    
                    
        ultraTab.extend(premiumTab)
        ultraTab.extend(urlTab)
        return ultraTab
        
    def getVideoLinks(self, baseUrl):
        printDBG("EkinoTv.getVideoLinks [%s]" % baseUrl)
        urlTab = []
        meta = strwithmeta(baseUrl).meta
        urlParams = dict(self.defaultParams)
        urlParams['header'] = dict(urlParams['header'])
        urlParams['header']['Referer'] = meta.get('Referer', baseUrl)
        urlParams['handle_recaptcha'] = True
        urlParams['with_metadata'] = True
        
        url = baseUrl
        tries = 0
        while self.up.getDomain(self.getMainUrl()) in self.up.getDomain(url) and tries < 4:
            tries += 1
            
            sts, data = self.getPage(url, urlParams)
            if not sts: return []
            
            url = data.meta.get('url', url)
            
            if self.up.getDomain(self.getMainUrl()) not in self.up.getDomain(url):
                break
            
            if 'recaptcha' in data:
                SetIPTVPlayerLastHostError(_('Link protected with google recaptcha v2.')) 
                sitekey  = self.cm.ph.getSearchGroups(data, 'data-sitekey="([^"]+?)"')[0]
                if sitekey == '': sitekey = self.cm.ph.getSearchGroups(data, '''['"]?sitekey['"]?\s*:\s*['"]([^"^']+?)['"]''')[0]
                if sitekey != '':
                    recaptcha = UnCaptchaReCaptcha(lang=GetDefaultLang())
                    recaptcha.HTTP_HEADER['Referer'] = baseUrl
                    token = recaptcha.processCaptcha(sitekey)
                    if token != '':
                        vUrl = self.getFullUrl('/watch/verify.php')
                        urlParams['header']['Referer'] = baseUrl
                        sts, data = self.getPage(vUrl, urlParams, {'verify':token})
                    else:
                        SetIPTVPlayerLastHostError(_('Link protected with google recaptcha v2.')+'\n wejdź na https://ekino-tv.pl/ i odpal dowolny film przez przeglądarke na komputerze.')
                        return []
                        break
            
            sts, data = self.getPage(url, urlParams)
            if not sts: return urlTab
            
            if 'recaptcha' in data:
                SetIPTVPlayerLastHostError(_('Link protected with google recaptcha v2.')) 
                continue
            
            url = self.getFullUrl(self.cm.ph.getSearchGroups(data, '<iframe[^>]+?src="([^"]+?)"')[0])

            if 'window.atob' in url:
                player = self.cm.ph.getSearchGroups(data, '''player\s*=\s*['"]([^'^"]+?)['"]''')[0]
                url = base64.b64decode(player)

            if not self.cm.isValidUrl(url):
                url = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''var\s+url\s*=\s*['"]([^'^"]+?)['"]''')[0])
            
            if not self.cm.isValidUrl(url):
                url = data.meta.get('url', '')
                
            if meta.get('is_premium', False) and 'video-player' in data:
                vidUrl = self.cm.ph.getSearchGroups(data, '''var\s+[^=]+?\s*=\s*['"](https?://[^'^"]+?\.mp4(:?\?[^'^"]*?)?)['"]''', ignoreCase=True)[0]
                if self.cm.isValidUrl(vidUrl):
                    urlTab.append({'name':'direct', 'url':vidUrl})
                    return urlTab
            
            printDBG("|||"  + url)
            printDBG("#################################################################")
            printDBG(data)
            printDBG("#################################################################")
        
        if self.cm.isValidUrl(url): 
            urlTab = self.up.getVideoLinkExt(url)
        return urlTab
        
    def getLinksForFavourite(self, favData):
        try:
            cItem = json_loads(favData)
        except Exception:
            cItem = {'url':favData}
            printExc()
        return  self.getLinksForVideo(cItem)
    
    def tryTologin(self):
        printDBG('tryTologin start')
        
        if None == self.loggedIn or self.login != config.plugins.iptvplayer.ekinotv_login.value or\
            self.password != config.plugins.iptvplayer.ekinotv_password.value:
        
            self.login = config.plugins.iptvplayer.ekinotv_login.value
            self.password = config.plugins.iptvplayer.ekinotv_password.value
            
            #rm(self.COOKIE_FILE)
            self.cm.clearCookie(self.COOKIE_FILE, ['__cfduid', 'cf_clearance'])
            
            self.loggedIn = False
            
            if '' == self.login.strip() or '' == self.password.strip():
                return False
            
            sts, data = self.getPage(self.getMainUrl())
            if not sts: return False
            
            sts, data = self.cm.ph.getDataBeetwenNodes(data, ('<form', '>', 'login'), ('</form', '>'))
            if not sts: return False
            
            actionUrl = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''action=['"]([^'^"]+?)['"]''')[0])
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<input', '>')
            post_data = {}
            for item in data:
                name  = self.cm.ph.getSearchGroups(item, '''name=['"]([^'^"]+?)['"]''')[0]
                value = self.cm.ph.getSearchGroups(item, '''value=['"]([^'^"]+?)['"]''')[0]
                post_data[name] = value
            
            post_data.update({'login':self.login, 'password':self.password})
            
            httpParams = dict(self.defaultParams)
            httpParams['header'] = dict(httpParams['header'])
            httpParams['header']['Referer'] = self.getMainUrl()
            sts, data = self.cm.getPage(actionUrl, httpParams, post_data)
            if sts and 'user/logout' in data:
                self.loggedIn = True
                data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'menu'), ('</div', '>'))[1]
                data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<a', '>'), ('<br', '>', '/'))
                self.loginMessage =  []
                for t in data:
                    t = self.cleanHtmlStr(t)
                    if t != '': self.loginMessage.append(t)
                self.loginMessage = '[/br]'.join(self.loginMessage)
            else:
                if sts: message = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'alert'), ('</div', '>'))[1])
                else: message = ''
                self.sessionEx.open(MessageBox, _('Login failed.') + '\n' + message, type = MessageBox.TYPE_ERROR, timeout = 10)
                printDBG('tryTologin failed')
        return self.loggedIn
    
    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('EkinoTv.handleService start')
        
        self.tryTologin()
                
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        
        name     = self.currItem.get("name", None)
        category = self.currItem.get("category", '')
        printDBG( "EkinoTv.handleService: ---------> name[%s], category[%s] " % (name, category) )
        searchPattern = self.currItem.get("search_pattern", searchPattern)
        self.currList = []
        
        if None == name:
            self.listsTab(self.MAIN_CAT_TAB, {'name':'category'})
    #FILMS CATEGORIES
        elif 'list_cats' == category:
            self.listMovieFilters(self.currItem, 'list_vers')
        elif 'list_vers' == category:
            self.listMovieFilters(self.currItem, 'list_years')
        elif 'list_years' == category:
            self.listMovieFilters(self.currItem, 'list_movies')
        elif 'list_movies' == category:
            self.listMovies(self.currItem)
    #FILMS LETTERS
        elif 'series_abc' == category:
            self.listsSeriesABC(self.currItem, 'series_list')
    #LIST SERIALS
        elif 'series_list' == category:
            self.listsSeries(self.currItem, 'series_episodes')
        elif 'series_episodes' == category:
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
        CHostBase.__init__(self, EkinoTv(), True)
        
    def getSearchTypes(self):
        searchTypesOptions = []
        searchTypesOptions.append(("Filmy", "movies"))
        searchTypesOptions.append(("Seriale", "series"))
        return searchTypesOptions
