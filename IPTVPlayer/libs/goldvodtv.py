# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, GetCookieDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass
###################################################

###################################################
# FOREIGN import
###################################################
from Components.config import config, ConfigText, getConfigListEntry
try:
    import json
except Exception:
    import simplejson as json

from os import path as os_path
############################################

###################################################
# E2 GUI COMMPONENTS 
###################################################
from Plugins.Extensions.IPTVPlayer.components.asynccall import MainSessionWrapper
from Screens.MessageBox import MessageBox
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.goldvodtv_login    = ConfigText(default = "", fixed_size = False)
config.plugins.iptvplayer.goldvodtv_password = ConfigText(default = "", fixed_size = False)

def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry('goldvod.tv ' + _("email") + ':', config.plugins.iptvplayer.goldvodtv_login))
    optionList.append(getConfigListEntry('goldvod.tv ' + _("password") + ':', config.plugins.iptvplayer.goldvodtv_password))
    return optionList
    
###################################################

class GoldVodTVApi:
    MAIN_URL   = 'http://goldvod.tv/'
    HTTP_HEADER  = { 'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux i686; rv:12.0) Gecko/20100101 Firefox/12.0', 'Referer': MAIN_URL }
    
    def __init__(self):
        self.COOKIE_FILE = GetCookieDir('goldvodtv.cookie')
        self.sessionEx = MainSessionWrapper()
        self.cm = common()
        self.up = urlparser()
        self.http_params = {}
        self.http_params.update({'save_cookie': True, 'load_cookie': True, 'cookiefile': self.COOKIE_FILE})
        self.cacheList = {}
        self.loggedIn = False
        
    def getFullUrl(self, url):
        if url.startswith('http'):
            return url
        elif url.startswith('/'):
            return self.MAIN_URL + url[1:]
        else:
            return self.MAIN_URL + url
        return url
        
    def cleanHtmlStr(self, str):
        return CBaseHostClass.cleanHtmlStr(str)
        
    def getChannelsList(self, cItem):
        printDBG("TelewizjadaNetApi.getChannelsList")
        
        login    = config.plugins.iptvplayer.goldvodtv_login.value
        password = config.plugins.iptvplayer.goldvodtv_password.value
        if login != '' and password != '':        
            if self.doLogin(login, password):
                self.loggedIn = True
                self.http_params.update({'save_cookie': True, 'load_cookie': True, 'cookiefile': self.COOKIE_FILE})
            else:
                self.sessionEx.open(MessageBox, 'Problem z zalogowanie użytkownika "%s. Sprawdź dane do logowania w konfiguracji hosta."' % login, type = MessageBox.TYPE_INFO, timeout = 10 )
                self.loggedIn = False
        
        channelsTab = []

        sts, data = self.cm.getPage(self.MAIN_URL + 'channels.html?show=on', self.http_params)
        if not sts:
            return []
        
        sts, data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="row">', "<div id='footer'>")
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a ', '</a>')
        for item in data:
            printDBG("item [%r]" % item)
            url  = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0]
            icon = self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''')[0]
            id   = self.cm.ph.getSearchGroups(url, '''[^0-9]([0-9]+?)[^0-9]''')[0]
            if '' != url:
                params = dict(cItem)
                params['url']   = self.getFullUrl(url)
                params['icon']  = self.getFullUrl(icon)
                params['title'] = self.cm.ph.getSearchGroups(item, '''title=['"]([^"^']+?)['"]''')[0]
                if '' == params['title']:
                    params['title'] = self.cm.ph.getSearchGroups(item, '''alt=['"]([^"^']+?)['"]''')[0]
                if '' == params['title']:
                    params['title'] = url.replace('.html', '').replace(',', ' ').title()
                params['desc']  = params['url']
                channelsTab.append(params)
            
        return channelsTab
        
    def getVideoLink(self, cItem):
        printDBG("GoldVodTVApi.getVideoLink")
        if self.loggedIn:
            url = strwithmeta(cItem['url'], {'params':{'load_cookie': True}})
        else:
            url = cItem['url']
        return self.up.getVideoLinkExt(url)
        
    def doLogin(self, login, password):
        logged = False
        loginUrl = self.MAIN_URL + 'login.html'
        
        params = dict(self.http_params)
        params['load_cookie'] = False
        sts, data = self.cm.getPage(loginUrl, params)
        if not sts:
            return False
        
        HTTP_HEADER= dict(GoldVodTVApi.HTTP_HEADER)
        HTTP_HEADER.update( {'Referer':loginUrl} )
        
        post_data = {'login': login, 'pass': password, 'remember': 1, 'logged': ''}
        params    = {'header': HTTP_HEADER, 'cookiefile': self.COOKIE_FILE, 'save_cookie': True, 'load_cookie': True}
        sts, data = self.cm.getPage( loginUrl, params, post_data)
        if sts:
            if os_path.isfile(self.COOKIE_FILE):
                if 'logout.html' in data:
                    printDBG('GoldVodTVApi.doLogin login as [%s]' % login)
                    logged = True
                else:
                    printDBG('GoldVodTVApi.doLogin login failed - wrong user or password?')
            else:
                printDBG('GoldVodTVApi.doLogin there is no cookie file after login')
        return logged
