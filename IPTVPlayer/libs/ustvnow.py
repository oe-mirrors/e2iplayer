# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetCookieDir, byteify, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
###################################################

###################################################
# FOREIGN import
###################################################
from Components.config import config, ConfigSelection, ConfigYesNo, ConfigText, getConfigListEntry
import urllib
from datetime import datetime, timedelta
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
config.plugins.iptvplayer.ustvnow_login = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.ustvnow_password = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.ustvnow_only_available = ConfigYesNo(default=True)
config.plugins.iptvplayer.ustvnow_epg = ConfigYesNo(default=True)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Email") + ": ", config.plugins.iptvplayer.ustvnow_login))
    optionList.append(getConfigListEntry(_("Password") + ": ", config.plugins.iptvplayer.ustvnow_password))
    optionList.append(getConfigListEntry(_("List only channels with subscription") + ": ", config.plugins.iptvplayer.ustvnow_only_available))
    optionList.append(getConfigListEntry(_("Get EPG") + ": ", config.plugins.iptvplayer.ustvnow_epg))

    return optionList

###################################################


class UstvnowApi:
    MAIN_URL = 'http://m.ustvnow.com/'
    LIVE_URL = MAIN_URL + 'iphone/1/live/playingnow?pgonly=true'
    HTTP_HEADER = {'User-Agent': 'Mozilla/5.0 (iPad; U; CPU OS 3_2 like Mac OS X; en-us) AppleWebKit/531.21.10 (KHTML, like Gecko) Version/4.0.4 Mobile/7B334b Safari/531.21.10', 'Referer': MAIN_URL}

    def __init__(self):
        self.cm = common()
        self.up = urlparser()
        self.sessionEx = MainSessionWrapper()
        self.cookiePath = GetCookieDir('ustvnow.cookie')
        self.token = ''
        self.passkey = ''

        HTTP_HEADER = dict(self.HTTP_HEADER)
        HTTP_HEADER.update({'Content-Type': 'application/x-www-form-urlencoded'})
        self.defParams = {'header': HTTP_HEADER, 'cookiefile': self.cookiePath, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True}

    def getFullUrl(self, url):
        if url.startswith('//'):
            return 'http:' + url
        if url.startswith('/'):
            url = url[1:]
        if 0 < len(url) and not url.startswith('http'):
            url = self.MAIN_URL + url
        if not self.MAIN_URL.startswith('https://'):
            url = url.replace('https://', 'http://')
        return url

    def cleanHtmlStr(self, str):
        return CBaseHostClass.cleanHtmlStr(str)

    def _getChannelsNames(self):
        printDBG("UstvnowApi._getChannelsNames")
        url = 'http://m.ustvnow.com/gtv/1/live/listchannels?%s' % urllib.urlencode({'token': self.token})
        sts, data = self.cm.getPage(url)
        if not sts:
            return []

        channelList = []
        try:
            data = json_loads(data)
            for item in data['results']['streamnames']:
                params = {}
                params['sname'] = item['sname']
                params['img'] = item['img']
                params['scode'] = item['scode']
                params['t'] = item['t']
                params['callsign'] = item['callsign']
                params['prgsvcid'] = item['prgsvcid']
                params['data_provider'] = item['data_provider']
                params['lang'] = item['lang']
                params['af'] = item['af']
                channelList.append(params)

            printDBG(channelList)

        except Exception:
            printExc()
        return channelList

    def getChannelsList(self, cItem):
        printDBG("UstvnowApi.getChannelsList")

        login = config.plugins.iptvplayer.ustvnow_login.value
        passwd = config.plugins.iptvplayer.ustvnow_password.value

        if '' != login.strip() and '' != passwd.strip():
            self.token = self.doLogin(login, passwd)
            self.passkey = self.getPasskey()
            if self.token == '' or self.passkey == '':
                self.sessionEx.open(MessageBox, _('An error occurred when try to sign in the user "%s.\nPlease check your login credentials and try again later..."') % login, type=MessageBox.TYPE_INFO, timeout=10)
                return []
        else:
            self.sessionEx.open(MessageBox, _('You need to enter email and password in configuration.'), type=MessageBox.TYPE_INFO, timeout=10)
            return []

        sts, data = self.cm.getPage(self.LIVE_URL, self.defParams)
        if not sts:
            return []

        channelsNames = self._getChannelsNames()
        channelsTab = []
        data = self.cm.ph.getDataBeetwenMarkers(data, '<div data-role="content" data-theme="c">', '</ul>', False)[1]
        data = data.split('</li>')
        prgsvcidMap = {}
        for item in data:
            url = self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0]
            ui = url.split('ui-page=')[-1]
            icon = self.cm.ph.getSearchGroups(item, 'src="([^"]+?)"')[0]
            desc = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.pop('url')
            params.update({'priv_url': self.getFullUrl(url), 'ui_page': ui, 'icon': icon, 'desc': desc})

            for nameItem in channelsNames:
                if nameItem['img'] in icon:
                    if config.plugins.iptvplayer.ustvnow_only_available.value and 0 == nameItem['t']:
                        break
                    params['title'] = nameItem['sname'] + ' [%s]' % nameItem['t']
                    params['prgsvcid'] = nameItem['prgsvcid']
                    params['scode'] = nameItem['scode']
                    prgsvcidMap[params['prgsvcid']] = len(channelsTab)
                    channelsTab.append(params)
                    break

        # calculate time difference from utcnow and the local system time reported by OS
        OFFSET = datetime.now() - datetime.utcnow()
        if config.plugins.iptvplayer.ustvnow_epg.value:
            sts, data = self.cm.getPage(self.MAIN_URL + 'gtv/1/live/channelguide', self.defParams)
            if sts:
                try:
                    data = json_loads(data)
                    for item in data['results']:
                        if item['prgsvcid'] in prgsvcidMap:
                            idx = prgsvcidMap[item['prgsvcid']]
                            utc_date = datetime.strptime(item.get('event_date', '') + ' ' + item.get('event_time', ''), '%Y-%m-%d %H:%M:%S')
                            utc_date = utc_date + OFFSET
                            if utc_date.time().second == 59:
                                utc_date = utc_date + timedelta(0, 1)
                            channelsTab[idx]['desc'] += '[/br][/br] [%s][/br]%s[/br]%s[/br]%s[/br]%s' % (utc_date.strftime('%Y-%m-%d %H:%M:%S'), item.get('title', ''), item.get('synopsis', ''), item.get('description', ''), item.get('episode_title', ''))
                except Exception:
                    printExc()

        return channelsTab

    def doLogin(self, login, password):
        printDBG("UstvnowApi.doLogin")
        rm(self.cookiePath)
        token = ''

        sts, data = self.cm.getPage(self.getFullUrl('iphone/1/live/settings'), self.defParams)
        if not sts:
            return token

        printDBG("===")
        printDBG(data)
        printDBG("===")

        url = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''action=['"]([^'^"]+?)['"]''')[0])
        if not self.cm.isValidUrl(url):
            return token

        post_data = {'username': login, 'password': password, 'device': 'iphone'}
        sts, data = self.cm.getPage(url, self.defParams, post_data)
        if sts:
            token = self.cm.getCookieItem(self.cookiePath, 'token')
        return token

    def getPasskey(self):

        url = 'http://m.ustvnow.com/gtv/1/live/viewdvrlist?%s' % urllib.urlencode({'token': self.token})
        sts, data = self.cm.getPage(url)
        if not sts:
            return ''

        try:
            data = json_loads(data)
            return data['globalparams']['passkey']
        except Exception:
            return ''

    def getVideoLink(self, cItem):
        printDBG("UstvnowApi.getVideoLink %s" % cItem)
        urlsTab = []
        cookieParams = {'cookiefile': self.cookiePath, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True}

        sts, data = self.cm.getPage('http://m-api.ustvnow.com/stream/1/live/view?scode=%s&token=%s&key=%s' % (cItem.get('scode', ''), self.token, self.passkey), self.defParams)
        if sts:
            try:
                data = json_loads(data)

                tmp = getDirectM3U8Playlist(strwithmeta(data['stream'], {'User-Agent': self.HTTP_HEADER['User-Agent']}), cookieParams=cookieParams, checkContent=True)
                cookieValue = self.cm.getCookieHeader(self.cookiePath)

                for item in tmp:
                    vidUrl = item['url']

                    item['url'] = urlparser.decorateUrl(vidUrl, {'User-Agent': self.HTTP_HEADER['User-Agent'], 'Cookie': cookieValue})
                    urlsTab.append(item)
                if len(urlsTab):
                    return urlsTab
            except Exception:
                printExc()

        sts, data = self.cm.getPage(self.LIVE_URL, self.defParams)
        if not sts:
            return []

        url = self.cm.ph.getSearchGroups(data, 'for="popup-%s"[^>]*?href="([^"]+?)"[^>]*?>' % cItem['ui_page'])[0]
        url = self.getFullUrl(url)

        sts, data = self.cm.getPage(url, self.defParams)
        if not sts:
            return []

        url = self.cm.ph.getSearchGroups(data, 'src="([^"]+?)"')[0]
        tmp = getDirectM3U8Playlist(strwithmeta(url, {'User-Agent': self.HTTP_HEADER['User-Agent']}), cookieParams=cookieParams, checkContent=True)
        cookieValue = self.cm.getCookieHeader(self.cookiePath)

        for item in tmp:
            vidUrl = item['url']

            item['url'] = urlparser.decorateUrl(vidUrl, {'User-Agent': self.HTTP_HEADER['User-Agent'], 'Cookie': cookieValue})
            urlsTab.append(item)

        return urlsTab
