# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetCookieDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass
###################################################

###################################################
# FOREIGN import
###################################################
from Components.config import config, ConfigText, getConfigListEntry
from hashlib import md5
try:
    import json
except Exception:
    import simplejson as json
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
config.plugins.iptvplayer.edemtv_login    = ConfigText(default = "", fixed_size = False)
config.plugins.iptvplayer.edemtv_password = ConfigText(default = "", fixed_size = False)

def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry( _("Email") + ": ", config.plugins.iptvplayer.edemtv_login))
    optionList.append(getConfigListEntry( _("Password") + ": ", config.plugins.iptvplayer.edemtv_password))
    return optionList
    
###################################################

class EdemTvApi:

    def __init__(self):
        self.MAIN_URL   = 'https://edem.tv/'
        self.HTTP_HEADER  = { 'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux i686; rv:12.0) Gecko/20100101 Firefox/12.0', 'Referer': self.MAIN_URL }
        self.COOKIE_FILE = GetCookieDir('edemtv.cookie')
        self.cm = common()
        self.up = urlparser()
        self.http_params = {}
        self.http_params.update({'header' : self.HTTP_HEADER, 'save_cookie': True, 'load_cookie': True, 'cookiefile': self.COOKIE_FILE})
        self.cacheChannels = {}
        self.sessionEx = MainSessionWrapper()
        
    def getFullUrl(self, url):
        if url.startswith('http'):
            return url
        elif url.startswith('/'):
            return self.MAIN_URL + url[1:]
        return self.MAIN_URL + url
        
    def cleanHtmlStr(self, str):
        return CBaseHostClass.cleanHtmlStr(str)
        
    def doLogin(self, login, password):
        logged = False
        HTTP_HEADER= dict(self.HTTP_HEADER)
        HTTP_HEADER.update( {'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8', 'X-Requested-With' : 'XMLHttpRequest'} )

        post_data = {'email' : login, 'password' : password}
        params    = {'header' : HTTP_HEADER, 'cookiefile' : self.COOKIE_FILE, 'save_cookie' : True}
        loginUrl  = self.getFullUrl('account/login')
        sts, data = self.cm.getPage( loginUrl, params, post_data)
        if sts and '/account/logout' in data:
            logged = True
        return logged
    
    def getChannelsList(self, cItem):
        printDBG("EdemTvApi.getChannelsList")
        channelsTab = []
        getList = cItem.get('get_list', True)
        if getList:
            login  = config.plugins.iptvplayer.edemtv_login.value
            passwd = config.plugins.iptvplayer.edemtv_password .value
            if '' != login.strip() and '' != passwd.strip():
                if not self.doLogin(login, passwd):
                    self.sessionEx.open(MessageBox, _('Login failed.'), type = MessageBox.TYPE_INFO, timeout = 10 )
                    return []
            else:
                self.sessionEx.open(MessageBox, _('This host requires registration. \nPlease fill your login and password in the host configuration. Available under blue button.'), type = MessageBox.TYPE_ERROR, timeout = 10 )
                return []
            
            self.cacheChannels = {}
            categoryUrl = self.getFullUrl('category')
            sts, data = self.cm.getPage(categoryUrl, self.http_params)
            if not sts:
                return []
            
            marker = "animated_hidden uk-width-1-1"
            channelsData = self.cm.ph.getDataBeetwenMarkers(data, marker, 'uk-visible-small', False)[1]
            channelsData = channelsData.split(marker)
            for catItem in channelsData:
                catId = self.cm.ph.getSearchGroups(catItem, ''' id=['"]([^'^"]+?)['"]''')[0]
                if catId == '':
                    continue
                channelsPerCat = self.cm.ph.getAllItemsBeetwenMarkers(catItem, '<a ', '</a>')
                for item in channelsPerCat:
                    url  = self.cm.ph.getSearchGroups(item, ''' href=['"]([^'^"]+?)['"]''')[0]
                    icon = self.cm.ph.getSearchGroups(item, ''' src=['"]([^'^"]+?)['"]''')[0]
                    alt = self.cm.ph.getSearchGroups(item, ''' alt=['"]([^'^"]+?)['"]''')[0]
                    
                    params = {'type':'video', 'url':self.getFullUrl(url), 'title':self.cleanHtmlStr(alt), 'icon':self.getFullUrl(icon), 'desc':self.cleanHtmlStr(item)}
                    if catId not in self.cacheChannels:
                        self.cacheChannels[catId] = [params]
                    else:
                        self.cacheChannels[catId].append(params)
            
            catsData = self.cm.ph.getDataBeetwenMarkers(data, 'uk-visible-small', '</ul>')[1]
            catsData = self.cm.ph.getAllItemsBeetwenMarkers(catsData, '<li ', '</li>')
            for item in catsData:
                catId = self.cm.ph.getSearchGroups(item, '''data-target=['"]([^'^"]+?)['"]''')[0]
                catTitle = self.cleanHtmlStr(item) + ' (%s)' % catId.title()
                if 0 == len(self.cacheChannels.get(catId, [])):
                    continue
                
                if 'adult' == catId:
                    adult = True
                else:
                    adult = False
                
                params = dict(cItem)
                params.update({'title':catTitle, 'cat_id':catId, 'get_list':False, 'pin_locked':adult})
                channelsTab.append(params)
        else:
            catId = cItem.get('cat_id', '')
            channels = self.cacheChannels.get(catId, [])
            for item in channels:
                params = dict(cItem)
                params.update(item)
                channelsTab.append(params)
        return channelsTab
    
    def getCookieItem(self, name):
        value = ''
        try:
            value = self.cm.getCookieItem(self.COOKIE_FILE, name)
        except Exception:
            printExc()
        return value
    
    def getVideoLink(self, cItem):
        printDBG("EdemTvApi.getVideoLink")
        
        playlistUrl = self.getFullUrl('playlist')
        tries = 0
        while tries < 7:
            tries += 1
            sts, data = self.cm.getPage(playlistUrl, self.http_params)
            if not sts:
                return []
            
            subdomain = self.cm.ph.getSearchGroups(data, '''<input[^>]*?name=['"]subdomain['"][^>]*?value=['"]([^'^"]+?)['"]''')[0]
            domainTab = self.cm.ph.getSearchGroups(data, '''<option[^>]*?value="([0-9]+?)"[^>]*?selected[^>]*?>([^<]+?)</option>''', 2)
            if subdomain == '' or '' == domainTab[0] or '' == domainTab[1]:
                HTTP_HEADER= dict(self.HTTP_HEADER)
                HTTP_HEADER.update( {'Referer':playlistUrl, 'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8', 'X-Requested-With' : 'XMLHttpRequest'} )
                
                login = config.plugins.iptvplayer.edemtv_login.value
                passwd = config.plugins.iptvplayer.edemtv_password.value
                subdomain = md5(login+passwd).hexdigest()
                post_data = {'server_id':tries, 'name':subdomain}
                params    = dict(self.http_params)
                params['header'] = HTTP_HEADER
                url = self.getFullUrl('ajax/user_server')
                sts, data = self.cm.getPage( url, params, post_data)
                printDBG(data)
                if 'success' in data:
                    post_data = {'server':tries, 'subdomain':subdomain, 'type':1}
                    sts, data = self.cm.getPage( playlistUrl, params, post_data)
                    printDBG(data)
            else:
                break
        
        
        sts, data = self.cm.getPage(cItem['url'], self.http_params)
        if not sts:
            return []
        
        #printDBG(data)
        
        data =  self.cm.ph.getDataBeetwenMarkers(data, 'playlist:', ']', False)[1]
        
        hlsUrl = self.cm.ph.getSearchGroups(data, '''['"](http[^'^"]+?)['"]''')[0]
        rmpUrl = self.cm.ph.getSearchGroups(data, '''['"](rtmp[^'^"]+?)['"]''')[0]

        urlsTab = []
        if hlsUrl.startswith('http://') and 'm3u8' in hlsUrl:
            hlsUrl = 'http://{0}.{1}/iptv/'.format(subdomain, domainTab[1]) + hlsUrl.split('/iptv/')[-1]
            hlsUrl = strwithmeta(hlsUrl, {'Cookie':'session=%s;' % self.getCookieItem('session'), 'Referer':cItem['url'], 'User-Agent':self.HTTP_HEADER['User-Agent']})
            urlsTab = getDirectM3U8Playlist(hlsUrl)
        #if rmpUrl.startswith('rtmp'):
        #    urlsTab.append({'name':'rtmp', 'url':rmpUrl + ' live=1'})
        return urlsTab
