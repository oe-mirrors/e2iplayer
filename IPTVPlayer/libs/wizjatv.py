# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, GetCookieDir, rm
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass
###################################################

###################################################
# FOREIGN import
###################################################
from Components.config import config, ConfigText, getConfigListEntry
import urllib
try:
    import json
except Exception:
    import simplejson as json

from os import path as os_path
############################################

###################################################
# E2 GUI COMMPONENTS
###################################################
from Screens.MessageBox import MessageBox
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.wizjatv_login = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.wizjatv_password = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry('wizja.tv ' + _("login") + ':', config.plugins.iptvplayer.wizjatv_login))
    optionList.append(getConfigListEntry('wizja.tv ' + _("password") + ':', config.plugins.iptvplayer.wizjatv_password))
    return optionList

###################################################


class WizjaTvApi(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self)
        self.MAIN_URL = 'http://wizja.tv/'
        self.DEFAULT_ICON_URL = 'http://wizja.tv/logo.png'
        self.HTTP_HEADER = {'User-Agent': 'Mozilla/5.0', 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})

        self.COOKIE_FILE = GetCookieDir('wizjatv.cookie')

        self.http_params = {}
        self.http_params.update({'header': self.HTTP_HEADER, 'save_cookie': True, 'load_cookie': True, 'cookiefile': self.COOKIE_FILE})
        self.loggedIn = False

    def doLogin(self, login, password):
        logged = False
        premium = False
        loginUrl = self.getFullUrl('/users/index.php')

        rm(self.COOKIE_FILE)
        sts, data = self.cm.getPage(loginUrl, self.http_params)
        if not sts:
            return False, False

        HTTP_HEADER = dict(self.HTTP_HEADER)
        HTTP_HEADER.update({'Referer': loginUrl})
        params = dict(self.http_params)
        params['header'] = HTTP_HEADER

        post_data = {'user_name': login, 'user_password': password, 'login': 'Zaloguj'}
        sts, data = self.cm.getPage(loginUrl, params, post_data)
        printDBG("-------------------------------------")
        printDBG(data)
        printDBG("-------------------------------------")
        if sts:
            if os_path.isfile(self.COOKIE_FILE):
                if '?logout' in data:
                    printDBG('WizjaTvApi.doLogin login as [%s]' % login)
                    logged = True
                    if 'Premium aktywne do ' in data:
                        premium = True
                else:
                    printDBG('WizjaTvApi.doLogin login failed - wrong user or password?')
            else:
                printDBG('WizjaTvApi.doLogin there is no cookie file after login')
        return logged, premium

    def getList(self, cItem):
        printDBG("WizjaTvApi.getChannelsList")

        login = config.plugins.iptvplayer.wizjatv_login.value
        password = config.plugins.iptvplayer.wizjatv_password.value
        if login != '' and password != '':
            ret = self.doLogin(login, password)
            if ret[0]:
                self.loggedIn = True
                if not ret[1]:
                    self.sessionEx.open(MessageBox, ('Użytkownika "%s" zalogowany poprawnie. Brak premium!') % login, type=MessageBox.TYPE_INFO, timeout=10)
            else:
                self.sessionEx.open(MessageBox, ('Problem z zalogowanie użytkownika "%s". Sprawdź dane do logowania w konfiguracji hosta.') % login, type=MessageBox.TYPE_INFO, timeout=10)
                self.loggedIn = False
        else:
            self.sessionEx.open(MessageBox, 'Serwis ten wymaga zalogowania. Wprowadź swój login i hasło w konfiguracji hosta dostępnej po naciśnięciu niebieskiego klawisza.', type=MessageBox.TYPE_ERROR, timeout=10)
            return []

        channelsTab = []

        sts, data = self.cm.getPage(self.getMainUrl(), self.http_params)
        if not sts:
            return channelsTab

        data = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="dropdown-menu">', '</ul>')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
        for item in data:
            icon = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''')[0])
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            if not self.cm.isValidUrl(url):
                continue
            title = self.cleanHtmlStr(item)
            if title == '':
                title = icon.split('/')[-1][:-4].upper()

            params = {'name': 'wizja.tv', 'type': 'video', 'title': title, 'url': url, 'icon': icon}
            channelsTab.append(params)

        return channelsTab

    def getVideoLink(self, cItem):
        printDBG("WizjaTvApi.getVideoLink")
        urlsTab = []

        sts, data = self.cm.getPage(cItem['url'], self.http_params)
        if not sts:
            return urlsTab

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<iframe', '>', caseSensitive=False)
        printDBG(data)
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0])
            if not self.cm.isValidUrl(url):
                continue
            HTTP_HEADER = dict(self.HTTP_HEADER)
            HTTP_HEADER.update({'Referer': cItem['url']})
            params = dict(self.http_params)
            params['header'] = HTTP_HEADER

            tries = 0
            while tries < 2:
                tries += 1

                if 'porter' in url or 'player' in item:
                    sts, tmp = self.cm.getPage(url, params)
                    if not sts:
                        break
                    printDBG(tmp)
                    videoUrl = urllib.unquote(self.cm.ph.getSearchGroups(tmp, '''['"]?src['"]?\s*:\s*['"](rtmp[^'^"]+?)['"]''')[0])
                    killUrl = self.getFullUrl(self.cm.ph.getSearchGroups(tmp, '''<a[^>]+?href=["']([^'^"]*?killme\.php[^'^"]*?)''')[0])
                    if videoUrl != '':
                        urlTab = self.cm.ph.getSearchGroups(videoUrl, '''rtmp://([^/]+?)/([^/]+?)/([^/]+?)\?(.+?)&streamType''', 4)
                        rtmp = 'rtmp://' + urlTab[0] + '/' + urlTab[1] + '?' + urlTab[3] + \
                               ' playpath=' + urlTab[2] + '?' + urlTab[3] + \
                               ' app=' + urlTab[1] + '?' + urlTab[3] + \
                               ' swfVfy=1 flashVer=WIN\\2020,0,0,306 swfUrl=http://wizja.tv/player/StrobeMediaPlayback_v3.swf live=1 token=fake pageUrl=' + cItem['url']
                        urlsTab.append({'name': 'rtmp', 'url': rtmp})
                    elif self.cm.isValidUrl(killUrl):
                        sts, tmp = self.cm.getPage(killUrl, params)
                        continue
                    SetIPTVPlayerLastHostError(self.cleanHtmlStr(tmp))
                break
        return urlsTab
