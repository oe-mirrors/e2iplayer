# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_unquote_plus
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import iterDictItems
from Plugins.Extensions.IPTVPlayer.p2p3.pVer import isPY2
###################################################
# FOREIGN import
###################################################
from Components.config import config, ConfigSelection, ConfigYesNo, ConfigText, getConfigListEntry
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
config.plugins.iptvplayer.weebtv_premium = ConfigYesNo(default=True)
config.plugins.iptvplayer.weebtv_login = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.weebtv_password = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.weebtv_videoquality = ConfigSelection(default="1", choices=[("0", _("Low")), ("1", _("Standard")), ("2", _("High (or HD)"))])


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Premium user"), config.plugins.iptvplayer.weebtv_premium))
    if config.plugins.iptvplayer.weebtv_premium.value:
        optionList.append(getConfigListEntry(_("Username:"), config.plugins.iptvplayer.weebtv_login))
        optionList.append(getConfigListEntry(_("Password:"), config.plugins.iptvplayer.weebtv_password))
    optionList.append(getConfigListEntry(_("Preferred video quality:"), config.plugins.iptvplayer.weebtv_videoquality))
    return optionList
###################################################


class WeebTvApi:
    HOST = 'XBMC'
    HEADER = {'User-Agent': HOST, 'ContentType': 'application/x-www-form-urlencoded'}
    DEFPARAMS = {'header': HEADER}
    MAINURL = 'http://weeb.tv'
    checkUrl = MAINURL + '/api/checkPluginVersionXBMC'
    PLAYERURL = MAINURL + '/api/setPlayer'
    JSONURL = MAINURL + '/api/getChannelList'
    VERSION = 140

    MAIN_TAB = [{'category': 'main', 'url': JSONURL + '&option=online-alphabetical', 'title': _('Sorted channels A-Z [live]')},
                 {'category': 'main', 'url': JSONURL + '&option=online-now-viewed', 'title': _('Sorted most viewed channels now [live]')},
                 {'category': 'main', 'url': JSONURL + '&option=online-most-viewed', 'title': _('Sorted most viewed channels general [live]')},
                 {'category': 'main', 'url': JSONURL + '&option=offline-ranking', 'title': _('Offline channels')},
                 {'category': 'main', 'url': JSONURL + '&option=all-ranking', 'title': _('Show all channels')}]

    def __init__(self):
        self.cm = common()

    def _jsonToSortedTab(self, data):
        strTab = []
        outTab = []
        for v, k in iterDictItems(data):
            strTab.append(int(v))
            strTab.append(k)
            outTab.append(strTab)
            strTab = []
        outTab.sort(key=lambda x: x[0])
        return outTab

    def _getJsonFromAPI(self, url):
        ret = {'0': 'Null'}
        try:
            if config.plugins.iptvplayer.weebtv_premium.value:
                username = config.plugins.iptvplayer.weebtv_login.value
                password = config.plugins.iptvplayer.weebtv_password.value
            else:
                username = ''
                password = ''
            postdata = {'username': username, 'userpassword': password}
            sts, data = self.cm.getPage(url, WeebTvApi.DEFPARAMS, postdata)
            if sts:
                ret = json_loads(data)
        except Exception:
            printExc()
        return ret

    def _getStr(self, v, default=''):
        if isPY2() and type(v) == type(u''):
            return v.encode('utf-8')
        elif type(v) == type(''):
            return v
        return default

    def getCategoriesList(self):
        printDBG("WeebTvApi.getCategoriesList")
        retTab = []
        for item in WeebTvApi.MAIN_TAB:
            params = dict(item)
            params['name'] = 'category'
            retTab.append(params)
        return retTab

    def getChannelsList(self, url):
        printDBG("WeebTvApi.getChannelsList url[%s]" % url)
        channelsList = []
        channelsArray = self._jsonToSortedTab(self._getJsonFromAPI(url))
        if len(channelsArray) > 0:
            try:
                if channelsArray[0][1] != 'Error' and channelsArray[0][1] != 'Null':
                    for i in range(len(channelsArray)):
                        try:
                            k = channelsArray[i][1]
                            name = self._getStr(k['channel_name']).replace("\"", '')
                            title = self._getStr(k['channel_title']).replace("\"", '')
                            desc = self._getStr(k['channel_description']).replace("\"", '')
                            tags = self._getStr(k['channel_tags']).replace("\"", '')
                            image = self._getStr(k['channel_logo_url'])
                            online = int(k['channel_online'])
                            rank = k['rank']
                            bitrate = k['multibitrate']
                            user = self._getStr(k['user_name']).replace("\"", '')
                            if 0 == len(title):
                                title = name
                            if 0 == online:
                                online = 'offline'
                                channel = ''
                            elif 2 == online:
                                online = 'online'
                                channel = name
                            title = '%s - %s %s' % (title, user, online)
                            params = {'url': channel, 'title': title, 'desc': desc, 'icon': image, 'rank': rank, 'bitrate': bitrate, 'user': user}
                            channelsList.append(params)
                        except Exception:
                            printExc()
            except Exception:
                printExc()
        return channelsList

    def getVideoLink(self, url):
        printDBG("WeebTvApi.getVideoLink")
        rtmp = ''
        channel = url
        premium = 0
        if 0 == len(channel):
            return ''
        try:
            if config.plugins.iptvplayer.weebtv_premium.value:
                username = config.plugins.iptvplayer.weebtv_login.value
                password = config.plugins.iptvplayer.weebtv_password.value
                postdata = {'username': username, 'userpassword': password}
            else:
                postdata = {'username': '', 'userpassword': ''}
            postdata['channel'] = channel
            postdata['platform'] = WeebTvApi.HOST

            sts, data = self.cm.getPage(WeebTvApi.PLAYERURL, WeebTvApi.DEFPARAMS, postdata)
            if sts:
                printDBG("||||||||||||||||||||||||||||| " + data)
                parser = UrlParser()
                params = parser.getParams(data)
                status = parser.getParam(params, '0')
                premium = parser.getIntParam(params, '5')
                imgLink = parser.getParam(params, '8')
                rtmpLink = parser.getParam(params, '10')
                playPath = parser.getParam(params, '11')
                bitrate = parser.getIntParam(params, '20')
                token = parser.getParam(params, '73')
                title = parser.getParam(params, '6')

                if title == '':
                    title = parser.getParam(params, '7')

                video_quality = config.plugins.iptvplayer.weebtv_videoquality.value
                if video_quality == '2' and bitrate == 1:
                    playPath = playPath + 'HI'
                elif video_quality == '0' and bitrate == 2:
                    playPath = playPath + 'LOW'

                rtmp = str(rtmpLink) + '/' + str(playPath) + ' live=1 token=fake pageUrl=token swfUrl=' + str(token)
                printDBG("||||||||||||||||||||||||||||| " + rtmp)
        except Exception:
            printExc()

        if rtmp.startswith('rtmp'):
            if 0 == premium:
                MainSessionWrapper().waitForFinishOpen(MessageBox, _("You do not have a premium account. Starting a sponsored broadcast."), type=MessageBox.TYPE_INFO, timeout=5)
            return rtmp
        else:
            return ''


class UrlParser:
    def __init__(self):
        pass

    def getParam(self, params, name):
        try:
            result = params[name]
            result = urllib_unquote_plus(result)
            return result
        except Exception:
            return None

    def getIntParam(self, params, name):
        try:
            param = self.getParam(params, name)
            return int(param)
        except Exception:
            return None

    def getBoolParam(self, params, name):
        try:
            param = self.getParam(params, name)
            return 'True' == param
        except Exception:
            return None

    def getParams(self, paramstring=''):
        param = []
        if len(paramstring) >= 2:
            params = paramstring
            cleanedparams = params.replace('?', '')
            if (params[len(params) - 1] == '/'):
                params = params[0:len(params) - 2]
            pairsofparams = cleanedparams.split('&')
            param = {}
            for i in range(len(pairsofparams)):
                splitparams = {}
                splitparams = pairsofparams[i].split('=')
                if (len(splitparams)) == 2:
                    param[splitparams[0]] = splitparams[1]
        return param
