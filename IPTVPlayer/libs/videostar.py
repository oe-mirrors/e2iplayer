# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetCookieDir, byteify, rm, CSelOneLink
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, getMPDLinksWithMeta
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.recaptcha_v2helper import CaptchaHelper
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
###################################################

###################################################
# FOREIGN import
###################################################
from Components.config import config, ConfigSelection, ConfigYesNo, ConfigText, getConfigListEntry
import random
############################################

###################################################
# E2 GUI COMMPONENTS 
###################################################
from Screens.MessageBox import MessageBox
###################################################

###################################################
# Config options for HOST
###################################################

config.plugins.iptvplayer.videostar_streamprotocol = ConfigSelection(default="2", choices=[("1", "rtmp"), ("2", "HLS - m3u8"), ("3", "DASHS - mpd"), ("4", "DASH - mpd")]) 
config.plugins.iptvplayer.videostar_defquality = ConfigSelection(default="9999999999", choices=[("0", _("the worst")), ("400000", _("low")), ("950000", _("average")), ("1600000", _("high")), ("9999999999", _("the best"))])
config.plugins.iptvplayer.videostar_use_defquality = ConfigYesNo(default=True)
config.plugins.iptvplayer.videostar_show_all_channels = ConfigYesNo(default=False)
config.plugins.iptvplayer.videostar_login = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.videostar_password = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_('Show all channels') + ": ", config.plugins.iptvplayer.videostar_show_all_channels))
    optionList.append(getConfigListEntry(_('Preferred streaming protocol') + ": ", config.plugins.iptvplayer.videostar_streamprotocol))
    optionList.append(getConfigListEntry(_('Preferred quality') + ": ", config.plugins.iptvplayer.videostar_defquality))
    optionList.append(getConfigListEntry(_('Use preferred quality') + ": ", config.plugins.iptvplayer.videostar_use_defquality))
    optionList.append(getConfigListEntry(_("Login") + ": ", config.plugins.iptvplayer.videostar_login))
    optionList.append(getConfigListEntry(_("Password") + ": ", config.plugins.iptvplayer.videostar_password))
    return optionList
###################################################
    
###################################################


class VideoStarApi(CBaseHostClass, CaptchaHelper):

    def __init__(self):
        CBaseHostClass.__init__(self)
        self.MAIN_URL = 'https://pilot.wp.pl/'
        self.API_BASE_URL = 'https://api-pilot.wp.pl/'
        self.STATIC_BASE_URL = 'https://static-pilot.wp.pl/'
    
        self.DEFAULT_ICON_URL = 'http://satkurier.pl/uploads/53612.jpg'
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.94 Safari/537.36'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate'}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})
        
        self.COOKIE_FILE = GetCookieDir('pilot.wp.pl.cookie')
        
        self.defaultParams = {}
        self.defaultParams.update({'header': self.HTTP_HEADER, 'ignore_http_code_ranges': [(422, 422), (404, 404), (500, 500)], 'save_cookie': True, 'load_cookie': True, 'cookiefile': self.COOKIE_FILE})
        self.loggedIn = False
        self.accountInfo = ''
        
        self.urlType = ''
        
        self.cacheChannelList = []
    
    def getFullUrl(self, url, urlType=''):
        self.urlType = urlType
        return CBaseHostClass.getFullUrl(self, url)
        
    def getMainUrl(self):
        if self.urlType == 'api':
            return self.API_BASE_URL
        elif self.urlType == 'static':
            return self.STATIC_BASE_URL
        return self.MAIN_URL
        
    def doLogin(self, login, password):
        printDBG("VideoStarApi.doLogin")
        
        logged = False

        httpParams = dict(self.defaultParams)
        actionUrl = self.getFullUrl('v1/user', 'api')
        sts, data = self.cm.getPage(actionUrl, httpParams)
        printDBG(">>> user >>>")
        printDBG(data)
        printDBG("<<<")
        if sts:
            try:
                data = json_loads(data, '', True)
                if '' != data['data']['token']:
                    self.userToken = data['data']['token']
                    return True, ''
            except Exception:
                printExc()

        loginUrl = self.getFullUrl('/login')
        errMessage = _("Get page \"%s\" error.")
        
        sts, data = self.cm.getPage(loginUrl, self.defaultParams)
        if not sts:
            return False, (errMessage % loginUrl)

#        sts, data = self.cm.ph.getDataBeetwenNodes(data, ('<form', '>', 'login'), ('</form', '>'))
#        if not sts: return False, ""

        link = self.cm.ph.getSearchGroups(data, '''<link as="script" rel="preload" href=['"](\/gatsby\-statics\/app\-[^'^"]+?)['"]''')[0]
        sts, data = self.cm.getPage(self.getFullUrl(link), self.defaultParams)
        if not sts:
            return False, (errMessage % loginUrl)

        if login != 'guest':
            sitekey = self.cm.ph.getSearchGroups(data, '''GRECAPTCHA_SITEKEY.*?['"]([^'^"]+?)['"]''')[0]
            if sitekey != '':
                token, errorMsgTab = self.processCaptcha(sitekey, loginUrl)
                if token == '':
                    return False, errorMsgTab
            else:
                return False, errorMsgTab
            post_data = '{"login":"%s","password":"%s","g-recaptcha-response":"%s","permanent":"1","device":"web"}' % (login, password, token)
        else:
            post_data = '{"login":"%s","password":"%s","permanent":"1","device":"web"}' % (login, password)

        actionUrl = self.getFullUrl('v1/user_auth/login', 'api')

        httpParams['header'] = dict(httpParams['header'])
        httpParams['header']['Referer'] = loginUrl
        httpParams['raw_post_data'] = True
        sts, data = self.cm.getPage(actionUrl, httpParams, post_data)
        printDBG(">>> user_auth/login >>>")
        printDBG(data)
        printDBG("<<<")
        if sts:
            errMessage = ''
            try:
                data = json_loads(data, '', True)
                if '' == data['data']['token']:
                    errMessage = 'Błędne dane do logowania.'
                else:
                    self.userToken = data['data']['token']
                    return True, ''
            except Exception:
                printExc()
                errMessage = 'Niezrozumiała odpowiedź serwera.'
            if errMessage != '': 
                return False, errMessage
        else:
            return False, (errMessage % actionUrl)

        return False, _("Unknown error.")
    
    def getList(self, cItem):
        printDBG("VideoStarApi.getList")
        
#        rm(self.COOKIE_FILE)
        
        self.informAboutGeoBlockingIfNeeded('PL')
        
        login = config.plugins.iptvplayer.videostar_login.value
        password = config.plugins.iptvplayer.videostar_password.value
        if login != '' and password != '':
            self.accountInfo = ''
            ret, msg = self.doLogin(login, password)
            if ret:
                self.loggedIn = True
                self.accountInfo = msg
            else:
                self.sessionEx.open(MessageBox, '%s\nProblem z zalogowanie użytkownika "%s". Sprawdź dane do logowania w konfiguracji hosta.' % (msg, login), type=MessageBox.TYPE_INFO, timeout=10)
                self.loggedIn = False
        else:
            self.doLogin('guest', 'guest')
        
        self.cacheChannelList = []
        channelsTab = []
        
        if self.loggedIn:
            url = self.getFullUrl('v1/channels/list?device=web', 'api')
        else:
            url = self.getFullUrl('/static/guest/channels/list/web.json', 'static')
        
        sts, data = self.cm.getPage(url, self.defaultParams)
        if not sts:
            return channelsTab

        try:
            idx = 0
            if 'channels' in data:
                jsonChannels = 'channels'
            else:
                jsonChannels = 'data'
            data = json_loads(data, '', True)
            for item in data[jsonChannels]:
                guestTimeout = item.get('guest_timeout', '')
                if not config.plugins.iptvplayer.videostar_show_all_channels.value and (item['access_status'] == 'unsubscribed' or (not self.loggedIn and guestTimeout == '0')):
                    continue
                title = self.cleanHtmlStr(item['name'])
                icon = self.getFullUrl(item.get('thumbnail', '')) 
                url = self.getFullUrl(item['slug'])
                
                desc = []
                if item.get('hd', False):
                    desc.append('HD')
                else:
                    desc.append('SD')
                if self.loggedIn:
                    desc.append(item['access_status'])
                elif guestTimeout != '':
                    desc.append(_('Guest timeout: %s') % guestTimeout)
                if item.get('geoblocked', False):
                    desc.append('geoblocked')
                
                params = {'name': cItem['name'], 'type': 'video', 'title': title, 'url': url, 'icon': icon, 'priv_idx': idx, 'desc': ' | '.join(desc)}
                channelsTab.append(params)
                self.cacheChannelList.append(item)
                idx += 1
        except Exception:
            printExc()
        
        return channelsTab
        
    def getVideoLink(self, cItem):
        printDBG("VideoStarApi.getVideoLink")
        urlsTab = []
        
        idx = cItem.get('priv_idx', -1)
        if idx < 0 or idx >= len(self.cacheChannelList):
            return urlsTab
            
        vidItem = self.cacheChannelList[idx]
        formatId = config.plugins.iptvplayer.videostar_streamprotocol.value
        tries = 0
        while True:
            tries += 1
            try:
                if self.loggedIn:
                    url = 'v1/channel/%s?format_id=%s&device_type=web' % (vidItem['id'], formatId)
                else:
                    url = 'v1/guest/channel/%s?format_id=%s&device_type=web' % (vidItem['id'], formatId)
                url = self.getFullUrl(url, 'api')
                sts, data = self.cm.getPage(url, self.defaultParams)
                printDBG(data)
                if not sts and not self.loggedIn and tries == 1:
                    rm(self.COOKIE_FILE)
                    self.doLogin('guest', 'guest')
                    sts, data = self.cm.getPage(self.getFullUrl('/static/guest/channels/list/web.json', 'static'), self.defaultParams)
                    if sts:
                        continue
                
                if not sts:
                    break
                data = json_loads(data)
                if data['data'] != None:
                    for item in data['data']['stream_channel']['streams']:
                        if formatId == '2':
                            if 'hls' in item['type']:
                                hslUrl = item['url'][0] # add here random
                                urlsTab.extend(getDirectM3U8Playlist(hslUrl, checkExt=False, cookieParams=self.defaultParams, checkContent=True))
                        elif formatId in ['3', '4']:
                            if 'dash' in item['type']:
                                dashUrl = item['url'][0] # add here random
                                urlsTab.extend(getMPDLinksWithMeta(dashUrl, checkExt=False, cookieParams=self.defaultParams))
                elif data['_meta'] != None:
                    info = data['_meta']['error']['info']
                    message = []
                    message.append('Oglądasz już kanał %s na urządeniu %s o adresie: %s.' % (info['channel_name'], info['device'], info['user_ip']))
                    message.append('W WP Pilocie nie możesz oglądać większej liczby kanałów jednocześnie.')
                    message.append('Czy chcesz kontynować tutaj?')
                    arg1 = self.sessionEx.waitForFinishOpen(MessageBox, '\n'.join(message), type=MessageBox.TYPE_YESNO)
                    if arg1:
                        url = self.getFullUrl('v1/channels/close', 'api')
                        paramsUrl = dict(self.defaultParams)
                        paramsUrl['header'] = dict(paramsUrl['header'])
                        paramsUrl['header']['Referer'] = self.getFullUrl('tv')
                        paramsUrl['header']['Origin'] = self.MAIN_URL[:-1]
                        paramsUrl['header']['content-type'] = 'application/json;charset=UTF-8'
                        paramsUrl['raw_post_data'] = True
                        sts, data = self.cm.getPage(url, paramsUrl, '{"channelId":"%s","t":"%s"}' % (info['channel_id'], self.userToken))
                        printDBG("==================== token1[%s] token2[%s]" % (self.userToken, info['stream_token']))
                        printDBG(data)
                        printDBG("====================")
                        continue

            except Exception:
                printExc()
            break
        
        if len(urlsTab):
            cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE)
            for idx in range(len(urlsTab)):
                urlsTab[idx]['url'] = strwithmeta(urlsTab[idx]['url'], {'Cookie': cookieHeader, 'User-Agent': self.USER_AGENT})
        
        if len(urlsTab):
            maxBitrate = int(config.plugins.iptvplayer.videostar_defquality.value) * 1.3

            def __getLinkQuality(itemLink):
                try:
                    if 'bitrate' in itemLink:
                        return int(itemLink['bitrate'])
                    elif 'bandwidth' in itemLink:
                        return int(itemLink['bandwidth'])
                except Exception:
                    printExc()
                return 0
            
            oneLink = CSelOneLink(urlsTab, __getLinkQuality, maxBitrate)
            urlsTab = oneLink.getSortedLinks()
            if config.plugins.iptvplayer.videostar_use_defquality.value:
                urlsTab = [urlsTab[0]]
        
        return urlsTab
