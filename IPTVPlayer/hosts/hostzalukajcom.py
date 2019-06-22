# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError, GetIPTVNotify
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify, rm, GetTmpDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
###################################################

###################################################
# FOREIGN import
###################################################
from Components.config import config, ConfigSelection, ConfigYesNo, ConfigText, getConfigListEntry
import re
try:    import simplejson as json
except Exception: import json
###################################################


###################################################
# E2 GUI COMMPONENTS 
###################################################
from Screens.MessageBox import MessageBox
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.zalukajtv_filmssort    = ConfigSelection(default = "ostatnio-dodane", choices = [("ostatnio-dodane", "ostatnio dodane"), ("ostatnio-ogladane", "ostatnio oglądane"), ("odslon", "odsłon"), ("ulubione", "ulubione"), ("oceny", "oceny"), ("mobilne", "mobilne")]) 
config.plugins.iptvplayer.zalukajtvPREMIUM       = ConfigYesNo(default = False)
config.plugins.iptvplayer.zalukajtv_login        = ConfigText(default = "", fixed_size = False)
config.plugins.iptvplayer.zalukajtv_password     = ConfigText(default = "", fixed_size = False)
config.plugins.iptvplayer.zalukajtv_proxy        = ConfigSelection(default = "None", choices = [("None",     _("None")),
                                                                                                ("proxy_1",  _("Alternative proxy server (1)")),
                                                                                                ("proxy_2",  _("Alternative proxy server (2)"))])
def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry("Sortuj filmy: ", config.plugins.iptvplayer.zalukajtv_filmssort))
    optionList.append(getConfigListEntry("Zaloguj:", config.plugins.iptvplayer.zalukajtvPREMIUM))
    if config.plugins.iptvplayer.zalukajtvPREMIUM.value:
        optionList.append(getConfigListEntry("  " + _("login") + ":", config.plugins.iptvplayer.zalukajtv_login))
        optionList.append(getConfigListEntry("  " + _("hasło") + ":", config.plugins.iptvplayer.zalukajtv_password))
    optionList.append(getConfigListEntry(_("Use proxy server:"),      config.plugins.iptvplayer.zalukajtv_proxy))
    return optionList
###################################################

def gettytul():
    return 'http://zalukaj.com/'

class ZalukajCOM(CBaseHostClass):
    USER_AGENT = 'Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.9.2.18) Gecko/20110621 Mandriva Linux/1.9.2.18-0.1mdv2010.2 (2010.2) Firefox/3.6.18'
    HEADER = {'User-Agent': USER_AGENT, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}
    AJAX_HEADER = dict(HEADER)
    AJAX_HEADER.update( {'X-Requested-With': 'XMLHttpRequest', 'Origin': 'https://zalukaj.com/', 'Referer': 'https://zalukaj.com/'} )
    
    DOMAIN     = 'zalukaj.com'
    MAIN_URL   = 'https://' + DOMAIN + '/'
    FILMS_URL  = MAIN_URL + '/gatunek,%d/%s,%s,strona-%d'
    SEARCH_URL = MAIN_URL + '/szukaj'
    LOGIN_URL  = MAIN_URL + '/account.php'
    DEFAULT_ICON_URL = 'http://www.userlogos.org/files/logos/8596_famecky/zalukaj.png'
    MAIN_CAT_TAB = [{'category':'films_sub_menu', 'title':"Filmy",   'url': ''},
                    {'category':'series_sub_menu','title':"Seriale", 'url': MAIN_URL},
                    {'category':'search',         'title':"Szukaj filmu", 'search_item':True},
                    {'category':'search_history', 'title':_('Search history')} ]
                    
    FILMS_SUB_MENU = [{ 'category':'films_category', 'title':'Kategorie',        'url':MAIN_URL },
                      { 'category':'films_list',     'title':'Ostatnio oglądane', 'url':MAIN_URL + '/ajax/load.videos?load=2&a=index&' },
                      { 'category':'films_list',     'title':'Ostatnio dodane',   'url':MAIN_URL + '/ajax/load.videos?load=1&a=index&'},
                      { 'category':'films_popular',  'title':'Najpopularniejsze', 'url':MAIN_URL + '/ajax/load.videos?load=0&a=index&' } ]
                    
    FILMS_POPULAR = [{ 'category':'films_list', 'title':'Wczoraj',        'url':MAIN_URL + '/ajax/load.videos?load=0&a=index&' },
                     { 'category':'films_list', 'title':'Ostatnie 7 dni', 'url':MAIN_URL + '/ajax/load.videos?load=0.2&a=index&' },
                     { 'category':'films_list', 'title':'W tym miesiącu', 'url':MAIN_URL + '/ajax/load.videos?load=0.3&a=index&'} ]
                     
    SERIES_SUB_MENU = [{ 'category':'series_list',   'title':'Lista',     'url':MAIN_URL },
                       { 'category':'series_updated','title':'Najpopularniejsze', 'url':MAIN_URL + '/ajax/load.videos?load=0&a=series&' } ]
                    
    LANGS_TAB = [{ 'title':'Wszystkie',     'lang':'wszystkie'      },
                 { 'title':'Z lektorem',    'lang':'tlumaczone'     },
                 { 'title':'Napisy pl',     'lang':'napisy-pl'      },
                 { 'title':'Nietłumaczone', 'lang':'nie-tlumaczone' } ]
     
    
    def __init__(self):
        printDBG("ZalukajCOM.__init__")
        CBaseHostClass.__init__(self, {'history':'ZalukajCOM', 'cookie':'zalukajtv.cookie'})
        self.loggedIn = None
        self.login    = ''
        self.password = ''
        self.msg = ''
        
    def _getPage(self, url, http_params_base={}, params=None, loggedIn=None):
        if None == loggedIn: loggedIn=self.loggedIn
        if '/ajax/' in url:
            HEADER = ZalukajCOM.AJAX_HEADER
        else:
            HEADER = ZalukajCOM.HEADER
        if loggedIn: http_params = {'header': HEADER, 'use_cookie': True, 'save_cookie': True, 'load_cookie': True, 'cookiefile': self.COOKIE_FILE}
        else: http_params = {'header': HEADER}
        http_params.update(http_params_base)
        return self.getPage(url, http_params, params)
        
    def getPage(self, url, addParams = {}, post_data = None):
        HTTP_HEADER= dict(self.HEADER)
        addParams = dict(addParams)
        addParams.update({'header':HTTP_HEADER})
            
        proxy = config.plugins.iptvplayer.zalukajtv_proxy.value
        if proxy != 'None':
            if proxy == 'proxy_1':
                proxy = config.plugins.iptvplayer.alternative_proxy1.value
            else:
                proxy = config.plugins.iptvplayer.alternative_proxy2.value
            addParams = dict(addParams)
            addParams.update({'http_proxy':proxy})
        
        sts, data = self.cm.getPage(url, addParams, post_data)
        try:
            if 'Duze obciazenie!' in data and loggedIn==False:
                message = self.cleanHtmlStr(re.compile('<script.+?</script>', re.DOTALL).sub("", data))
                GetIPTVNotify().push(message, 'info', 5)
                SetIPTVPlayerLastHostError(message)
            if '/sms' in self.cm.meta['url']:
                message = 'Duze obciazenie!'
                GetIPTVNotify().push(message, 'info', 5)
                SetIPTVPlayerLastHostError(message)
        except Exception:
            pass
        return sts, data
        
    def getFullIconUrl(self, url):
        url = self.getFullUrl(url)
        proxy = config.plugins.iptvplayer.zalukajtv_proxy.value
        if proxy != 'None':
            if proxy == 'proxy_1':
                proxy = config.plugins.iptvplayer.alternative_proxy1.value
            else:
                proxy = config.plugins.iptvplayer.alternative_proxy2.value
            url = strwithmeta(url, {'iptv_http_proxy':proxy})
        return url
            
    def _listLeftTable(self, cItem, category, m1, m2, sp):
        printDBG("ZalukajCOM.listLeftGrid")
        sts, data = self._getPage(cItem['url'])
        if not sts: return
        printDBG(data)
        data = self.cm.ph.getDataBeetwenMarkers(data, m1, m2, False)[1]
        data = data.split(sp)
        if len(data): del data[-1]
        for item in data:
            params = dict(cItem)
            url    = self.getFullUrl( self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"', 1)[0] )
            if self.DOMAIN not in url: continue
            params.update({'category':category, 'title':self.cleanHtmlStr( item ), 'url':url})
            self.addDir(params)
        
    def listFilmsCategories(self, cItem, category):
        printDBG("ZalukajCOM.listFilmsCategories")
        self._listLeftTable(cItem, category, '<table id="one" cellpadding="0" cellspacing="3">', '</table>', '</td>')
        
    def listSeries(self, cItem, category):
        printDBG("ZalukajCOM.listFilmsCategories")
        self._listLeftTable(cItem, category, '<table id="main_menu" cellpadding="0" cellspacing="3">', '</table>', '</td>')
        
    def listFilms(self, cItem):
        printDBG("ZalukajCOM.listFilms")
        url      = cItem['url']
        page = cItem.get('page', 1)
        nextPage = False
        extract  = False
        try:
            cat  = int(url.split('/')[-1])
            sort = config.plugins.iptvplayer.zalukajtv_filmssort.value
            url  = ZalukajCOM.FILMS_URL % (cat, sort, cItem['lang'], page)
            extract = True
        except Exception: pass
        post_data = None
        if '/ajax/load.videos' in url:
            a = self.cm.ph.getSearchGroups(url, 'a=([^"]+?)&', 1)[0]
            load = self.cm.ph.getSearchGroups(url, 'load=([^"]+?)&', 1)[0]
            post_data = {'a': a, 'load': load}
            url = url.split('?')[0]
        sts, data = self._getPage(self.getFullUrl(url), {}, post_data)
        if not sts: return
        printDBG("ZalukajCOM data %s" % data)

        sp = '<div class="tivief4">'
        if not sp in data: sp = '<div class="row">'

        if extract:
            if self.cm.ph.getSearchGroups(data, 'strona\-(%d)[^0-9]' % (page+1))[0] != '':
                nextPage = True
            m2 = '<div class="categories_page">' 
            if m2 not in data: m2 = '<div class="doln">'
            data = self.cm.ph.getDataBeetwenMarkers(data, sp, m2, True)[1]
        data = data.split(sp)
        #printDBG("ZalukajCOM data %s" % data)

        if len(data): del data[0]
        for item in data:
            #printDBG("ZalukajCOM item %s" % item)

            year = self.cleanHtmlStr( self.cm.ph.getDataBeetwenMarkers(item, '<p>', '</p>', False)[1] )
            if '' == year: year = self.cleanHtmlStr( self.cm.ph.getDataBeetwenMarkers(item, 'gen">', '<', False)[1] )
            desc = self.cleanHtmlStr( self.cm.ph.getDataBeetwenMarkers(item, '</h3>', '</div>', False)[1] )
            if '' == desc: desc = self.cleanHtmlStr( self.cm.ph.getDataBeetwenMarkers(item, 'desc">', '<', False)[1] )
            more = self.cleanHtmlStr( self.cm.ph.getDataBeetwenMarkers(item, '<p class="few_more">', '</p>', False)[1] )
            #if '' == more: more = self.cleanHtmlStr( self.cm.ph.getDataBeetwenMarkers(item, 'tooltip" title="', '"', False)[1] )
            desc = '%s | %s | %s |' % (year, more, desc)
            icon = self.getFullUrl( self.cm.ph.getDataBeetwenMarkers(item, 'background-image:url(', ')', False)[1] )
            if '' == icon: icon = self.getFullUrl( self.cm.ph.getSearchGroups(item, 'src="([^"]+?)"', 1)[0] )
            url  = self.getFullUrl( self.cm.ph.getSearchGroups(item, '<a href="([^"]+?)"', 1)[0] )
            title = self.cleanHtmlStr( self.cm.ph.getSearchGroups(item, 'title="([^"]+?)"', 1)[0] ) 
            title2 = self.cleanHtmlStr( self.cm.ph.getDataBeetwenMarkers(item, '<h3>', '</h3>', False)[1] ) 
            if len(title) < len(title2): title = title2
            if '/ajax/' in cItem['url']:
                title = self.cleanHtmlStr( self.cm.ph.getSearchGroups(item, 'html"\stitle="([^"]+?)"', 1)[0].replace('\n','') ) 
            if '/serial/' in url:
                params = dict(cItem)
                params.update({'category':'series_seasons', 'title':title +' (serial)', 'url':url, 'desc':desc, 'icon':icon})
                self.addDir(params)
            else:
                if '' != url: self.addVideo({'title':title, 'url':url, 'desc':desc, 'icon':icon})
        if nextPage: 
            params = dict(cItem)
            params.update({'title':_('Next page'), 'page':page+1})
            self.addDir(params)
            
    def listUpdatedSeries(self, cItem, category):
        printDBG("ZalukajCOM.listUpdatedSeries")
        url = cItem['url']
        post_data = None
        if '/ajax/load.videos' in url:
            a = self.cm.ph.getSearchGroups(url, 'a=([^"]+?)&', 1)[0]
            load = self.cm.ph.getSearchGroups(url, 'load=([^"]+?)&', 1)[0]
            post_data = {'a': a, 'load': load}
            url = url.split('?')[0]
        sts, data = self._getPage(url, {}, post_data)
        if not sts: return
        printDBG("ZalukajCOM.listUpdatedSeries data: %s" % data)
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="row">', '<div class="clearfix">', False, False)
        for item in data:
            gen  =  self.cm.ph.getSearchGroups(item, 'gen">([^>]+?)<', 1)[0]
            icon  = self.getFullUrl( self.cm.ph.getSearchGroups(item, 'src="([^"]+?)"', 1)[0] )
            url   = self.getFullUrl( self.cm.ph.getSearchGroups(item, '<a href="([^"]+?)"', 1)[0] )
            title = self.cm.ph.getSearchGroups(item, 'html"\stitle="([^"]+?)"', 1)[0].replace('\n','')
            desc  = self.cleanHtmlStr( self.cm.ph.getDataBeetwenMarkers(item, 'desc">', '</div>', False)[1] )
            if '' == url: continue
            self.addVideo({'title':title+'  '+gen, 'url':url, 'desc':gen+' | '+desc, 'icon':icon})
            
    def _listSeriesBase(self, cItem, category, m1, m2, sp):
        printDBG("ZalukajCOM._listSeriesBase")
        sts, data = self._getPage(cItem['url'])
        if not sts: return

        icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(data, '''<img[^>]+?src=['"]([^'^"]*?/promote_serial/[^'^"]+?)['"]''')[0])

        data = self.cm.ph.getDataBeetwenNodes(data, m1, m2, False)[1]
        data = data.split(sp)
        if len(data): del data[-1]
        for item in data:
            url   = self.getFullUrl( self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"', 1)[0] )
            title = self.cleanHtmlStr( item ) 
            if '' == url: continue
            params = dict(cItem)
            params.update({'category':category, 'title':title, 'url':url, 'icon':icon})
            if 'video' == category: self.addVideo(params)
            else: self.addDir(params)
                
    def listSeriesSeasons(self, cItem, category):
        printDBG("ZalukajCOM.listSeriesSeasons")
        self._listSeriesBase(cItem, category, ('<div', '>', '"sezony"'), ('<div', '>', 'class="doln2"'), '</div>')
        if 1 == len(self.currList):
            newItem = self.currList[0]
            self.currList = []
            self.listSeriesEpisodes(newItem)
        
    def listSeriesEpisodes(self, cItem):
        printDBG("ZalukajCOM.listSeriesEpisodes")
        self._listSeriesBase(cItem, 'video', ('<div', '>', '"odcinkicat"'), ('<div', '>', 'class="doln2"'), '</div>')
        
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("ZalukajCOM.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        self.tryTologin()
        szukaj = 'https://zalukaj.com/ajax/load.search?html=1&q=%s' % searchPattern
        params = {'name':'category', 'category':'films_list', 'url': szukaj, 'post_data':None}
        self.listFilms(params)
    
    def getLinksForVideo(self, cItem):
        printDBG("ZalukajCOM.getLinksForVideo url[%s]" % cItem['url'])
        self.tryTologin()
        
        if self.loggedIn: tries= [True, False]
        else: tries= [False]
        urlTab = []
        for loggedIn in tries:
            url = cItem['url']
            sts, data = self._getPage(url, loggedIn=loggedIn)
            if not sts: continue
            url = self.getFullUrl( self.cm.ph.getSearchGroups(data, '"([^"]+?player.php[^"]+?)"', 1)[0] )
            if '' == url:
                printDBG( 'No player.php in data')
                data = self.cm.ph.getDataBeetwenMarkers(data, 'Oglądaj Film Online', '<div class="doln">', False)[1]
                url = self.getFullUrl( self.cm.ph.getSearchGroups(data, 'href="([^"]+?)"[^>]*?target', 1)[0] )
                urlTab.extend(self.up.getVideoLinkExt(url))
                continue 
            sts, data = self._getPage(url, loggedIn=loggedIn)
            if not sts: continue
            url = self.getFullUrl(self.cm.ph.getSearchGroups(data, '<a href="([^"]+?)"', 1)[0])
            if '' == url:
                printDBG( 'No href in data[%s]' % '')
                continue
                
            sts, data = self._getPage(url, loggedIn=loggedIn)
            if not sts: continue

            # First check for premium link
            premium = False
            premiumLinks = self.cm.ph.getSearchGroups(data, '"bitrates"\t?\:\t?(\[[^]]+?\])', 1)[0]
            if premiumLinks != '':
                printDBG("New premium premiumLinks: [%s]" % premiumLinks)
                try:
                    premiumLinks = byteify( json.loads(premiumLinks) )
                    for pItem in premiumLinks:
                        urlTab.append({'name':'zalukaj.tv premium ' + pItem.get('label', ''), 'url':pItem['url']})
                        premium = True
                except Exception:
                    printExc()
            
            if not premium:
                url = self.cm.ph.getSearchGroups(data, "url:'([^']+?)'", 1)[0]
                printDBG("Old premium url: [%s]" % url)
                if url.startswith('http'):
                    urlTab.append({'name':'zalukaj.tv premium ', 'url':url})
                    premium = True
                    
            if not premium:
                printDBG( 'No premium link data[%s]' % data)
                tmp = self.cm.ph.getAllItemsBeetwenMarkers(data, '<source', '>', False, False)
                for item in tmp:
                    if 'video/mp4' in item or '.mp4' in item:
                        label = self.cm.ph.getSearchGroups(item, '''label=['"]([^"^']+?)['"]''')[0]
                        res = self.cm.ph.getSearchGroups(item, '''res=['"]([^"^']+?)['"]''')[0]
                        if label == '': label = res
                        url = self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''')[0]
                        if url.startswith('//'): url = 'http:' + url
                        if not self.cm.isValidUrl(url): continue
                        urlTab.append({'name':'zalukaj.tv premium ' + label, 'url':strwithmeta(url, {'Referer':cItem['url']})})
                        premium = True
            if not premium:
                url = self.getFullUrl( self.cm.ph.getSearchGroups(data, 'iframe src="([^"]+?)" width=', 1)[0] )
                if self.cm.isValidUrl(url):
                    urlTab.extend(self.up.getVideoLinkExt(url))
                # premium link should be checked at first, so if we have free link here break
                if len(urlTab):
                    break

        return urlTab
        
    def captcha(self):
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT':'1', 'Accept': 'application/json, text/javascript, */*; q=0.01', 'Accept-Encoding':'gzip, deflate', 'Referer':'https://zalukaj.com/', 'Origin':'https://zalukaj.com/'}
        self.defaultParams = {'header':self.HTTP_HEADER, 'with_metadata':True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        httpParams = dict(self.defaultParams)
        imgUrl = 'https://zalukaj.com/captcha-image'
        from copy import deepcopy
        from Plugins.Extensions.IPTVPlayer.components.iptvmultipleinputbox import IPTVMultipleInputBox
        from Plugins.Extensions.IPTVPlayer.components.asynccall import MainSessionWrapper
        self.sessionEx = MainSessionWrapper()  
        captchaTitle = ''
        captchaLabel = _('Captcha')
        captchaTitle = captchaLabel  
        sendLabel = _('Send')
        header = dict(self.HTTP_HEADER)
        header['Accept'] = 'image/png,image/*;q=0.8,*/*;q=0.5'
        params = dict(self.defaultParams)
        params.update( {'maintype': 'image', 'subtypes':['jpeg', 'png'], 'check_first_bytes':['\xFF\xD8','\xFF\xD9','\x89\x50\x4E\x47'], 'header':header} )
        filePath = GetTmpDir('.iptvplayer_captcha.jpg')
        rm(filePath)
        ret = self.cm.saveWebFile(filePath, imgUrl.replace('&amp;', '&'), params)
        if not ret.get('sts'):
            SetIPTVPlayerLastHostError(_('Fail to get "%s".') % imgUrl)
            return []
        params = deepcopy(IPTVMultipleInputBox.DEF_PARAMS)
        params['accep_label'] = sendLabel
        params['title'] = captchaLabel
        params['status_text'] = captchaTitle
        params['status_text_hight'] = 200
        params['with_accept_button'] = True
        params['list'] = []
        item = deepcopy(IPTVMultipleInputBox.DEF_INPUT_PARAMS)
        item['label_size'] = (660,110)
        item['input_size'] = (680,25)
        item['icon_path'] = filePath
        item['title'] = _('Answer')
        item['input']['text'] = ''
        params['list'].append(item)
        params['vk_params'] = {'invert_letters_case':True}
        ret = 0
        retArg = self.sessionEx.waitForFinishOpen(IPTVMultipleInputBox, params)
        printDBG(retArg)
        if retArg and len(retArg) and retArg[0]:
            return retArg[0][0].lower()
        else:
            return []

    def tryTologin(self):
        printDBG('tryTologin start')
        
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT':'1', 'Accept': 'application/json, text/javascript, */*; q=0.01', 'Accept-Encoding':'gzip, deflate', 'Referer':'https://zalukaj.com/', 'Origin':'https://zalukaj.com/'}
        self.defaultParams = {'header':self.HTTP_HEADER, 'with_metadata':True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        httpParams = dict(self.defaultParams)
        httpParams['header'] = dict(httpParams['header'])
        httpParams['header']['Referer'] = 'https://zalukaj.com/'
        
        if None == self.loggedIn or self.login != config.plugins.iptvplayer.zalukajtv_login.value or\
            self.password != config.plugins.iptvplayer.zalukajtv_password.value:
        
            self.login = config.plugins.iptvplayer.zalukajtv_login.value
            self.password = config.plugins.iptvplayer.zalukajtv_password.value
            
            rm(self.COOKIE_FILE)
            
            self.loggedIn = False
            self.msg = ''
            
            if '' == self.login.strip() or '' == self.password.strip():
                return False
            
            rm(self.COOKIE_FILE)

            sts, msg = False, 'Problem z zalogowaniem użytkownika \n"%s".' % self.login
            post_data = None
            sts, data  = self._getPage('https://zalukaj.com/', params=post_data, loggedIn=True)
            if self.cm.meta['url'] == 'https://zalukaj.com/limit': 
                httpParams['header']['Referer'] = 'https://zalukaj.com/limit'
                post_data = {'captcha': self.captcha()}
                sts, data = self.cm.getPage('https://zalukaj.com/limit', httpParams, post_data)
            if sts:
                #printDBG(data)
                hash = self.cm.ph.getSearchGroups(data, '''name="hash" value=['"]([^'^"]+?)['"]''')[0].strip()
                expires = self.cm.ph.getSearchGroups(data, '''"expires" value=['"]([^'^"]+?)['"]''')[0].strip()
                post_data = {'expires': expires, 'hash': hash, 'username': self.login,'password': self.password} 
                sts, data = self.cm.getPage('https://zalukaj.com/ajax/login', httpParams, post_data)
                printDBG(data)
                if '"error":[1' in data:
                    post_data['captcha'] = self.captcha()
                    sts, data = self.cm.getPage('https://zalukaj.com/ajax/login', httpParams, post_data)
                    printDBG(data)
                if '"succes' in data:
                    cookies = []
                    cj = self.cm.getCookie(self.COOKIE_FILE)
                    for cookie in cj:
                        if cookie.name == '__PHPSESSIDS':
                            cookies.append('%s=%s;' % (cookie.name, cookie.value))
                            printDBG(">> \t%s \t%s \t%s \t%s" % (cookie.domain, cookie.path, cookie.name, cookie.value) )

                sts, data = self._getPage(url=self.getFullUrl('/libs/ajax/login.php?login=1'), loggedIn=True)
                if sts:
                    printDBG(data)
                    sts,tmp = self.cm.ph.getDataBeetwenMarkers(data, '<p>Typ Konta:', '</p>', False)
                    if sts: 
                        tmp = tmp.replace('(kliknij by oglądać bez limitów)', '')
                        msg = 'Zostałeś poprawnie zalogowany.' + '\nTyp Konta: '+self.cleanHtmlStr(tmp)
                        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<p>Zebrane Punkty:', '</p>', False)[1].replace('&raquo; Wymień na VIP &laquo;', '')
                        if '' != tmp: msg += '\nZebrane Punkty: '+self.cleanHtmlStr(tmp)
                        self.loggedIn = True
            
            if not self.loggedIn: self.sessionEx.open(MessageBox, msg, type = MessageBox.TYPE_INFO, timeout = 10 )
            else: self.msg = msg.replace('\n', '[/br]')
        
        return self.loggedIn
    
    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('ZalukajCOM.handleService start')
        
        self.tryTologin()

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name     = self.currItem.get("name", None)
        category = self.currItem.get("category", '')
        printDBG( "ZalukajCOM.handleService: ---------> name[%s], category[%s] " % (name, category) )
        searchPattern = self.currItem.get("search_pattern", searchPattern)
        self.currList = [] 

        if None == name:
            self.listsTab(ZalukajCOM.MAIN_CAT_TAB, {'name':'category', 'desc':self.msg})
    #FILMS
        elif 'films_sub_menu' == category:
            self.listsTab(ZalukajCOM.FILMS_SUB_MENU, self.currItem)
        elif 'films_popular' == category:
            self.listsTab(ZalukajCOM.FILMS_POPULAR, self.currItem) 
        elif 'films_category' == category:
            self.listFilmsCategories(self.currItem, 'add_lang')
    #LANGS
        elif 'add_lang' == category:
            newItem = dict(self.currItem)
            newItem.update({'category':'films_list'})
            self.listsTab(ZalukajCOM.LANGS_TAB, newItem)
    #LIST FILMS 
        elif 'films_list' == category:
            self.listFilms(self.currItem)
    #SERIES
        elif 'series_sub_menu' == category:
            self.listsTab(ZalukajCOM.SERIES_SUB_MENU, self.currItem)
        elif 'series_list' == category:
            self.listSeries(self.currItem, 'series_seasons')
        elif 'series_updated' == category:
            self.listUpdatedSeries(self.currItem, 'series_episodes')
        elif 'series_seasons' == category:
            self.listSeriesSeasons(self.currItem, 'series_episodes')
        elif 'series_episodes' == category:
            self.listSeriesEpisodes(self.currItem)
    #WYSZUKAJ
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item':False, 'name':'category'}) 
            self.listSearchResult(cItem, searchPattern, searchType)
    #HISTORIA WYSZUKIWANIA
        elif category == "search_history":
            self.listsHistory({'name':'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, ZalukajCOM(), True)