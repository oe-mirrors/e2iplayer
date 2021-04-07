# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
###################################################

###################################################
# FOREIGN import
###################################################
from Components.config import config, ConfigSelection, ConfigYesNo, ConfigText, getConfigListEntry
from hashlib import md5
############################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.filmontvcom_streamprotocol = ConfigSelection(default="rtmp", choices=[("rtmp", "rtmp"), ("rtsp", "rtsp"), ("hls", "HLS - m3u8")]) 
config.plugins.iptvplayer.filmontvcom_premium = ConfigYesNo(default=False)
config.plugins.iptvplayer.filmontvcom_login = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.filmontvcom_password = ConfigText(default="", fixed_size=False)

def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry("FimOn.com " + _("Preferred streaming protocol") + ": ", config.plugins.iptvplayer.filmontvcom_streamprotocol))
    optionList.append(getConfigListEntry("FimOn.com " + _("Premium user") + ": ", config.plugins.iptvplayer.filmontvcom_premium))
    if config.plugins.iptvplayer.filmontvcom_premium.value:
        optionList.append(getConfigListEntry("  " + _("login") + ": ", config.plugins.iptvplayer.filmontvcom_login))
        optionList.append(getConfigListEntry("  " + _("password") + ": ", config.plugins.iptvplayer.filmontvcom_password))
    return optionList
###################################################

class FilmOnComApi:
    HTTP_USER_AGENT = 'User-Agent: AndroidNative/2.0.90 (Linux; U; Android 2.3.4; pl-pl; SAMSUNG GT-N7000; Build/GRJ22; com.filmontvcom.android) tablet; xlarge; 1024x600; FilmOn-MIDDLE-EAST'
    MAINURL = 'http://www.filmon.com/tv'
    
    BASE_INIT_PARAMS = "app_android_device_model=GT-N7000&app_android_test=false&app_version=2.0.90&app_android_device_tablet=true&app_android_device_manufacturer=SAMSUNG&app_secret=wis9Ohmu7i&app_id=android-native&app_android_api_version=10%20HTTP/1.1"
    STREAMING_PROTOCOLS = {'rtsp': "channelProvider=rtsp", 'rtmp': "channelProvider=rtmp", 'hls': "channelProvider=ipad&supported_streaming_protocol=livehttp"}

    def __init__(self):
        self.cm = common()
        self.cm.HOST = FilmOnComApi.HTTP_USER_AGENT

        self.middleware = 'http://la.api.filmon.com'
        self.session_key = None
        self.comscore = {}
        self.jsonData = {'channels': [], 'groups': []}
        self.streamprotocol = config.plugins.iptvplayer.filmontvcom_streamprotocol.value
        self.PREMIUM = config.plugins.iptvplayer.filmontvcom_premium.value
        self.LOGIN = config.plugins.iptvplayer.filmontvcom_login.value
        self.PASSWORD = config.plugins.iptvplayer.filmontvcom_password.value

    def initSession(self, force=False):
        printDBG('FilmOnComApi.initSession force[%r]' % force)
        if force or None == self.session_key:
            self.session_key = None
            data = FilmOnComApi.MAINURL + '/api/init?' + FilmOnComApi.BASE_INIT_PARAMS + '&' + FilmOnComApi.STREAMING_PROTOCOLS[self.streamprotocol]
            sts, data = self.cm.getPage(data)
            if sts:
                try:
                    data = json_loads(data)
                    self.session_key = data['session_key']
                    self.comscore = data['comscore']
                    self.middleware = data['middleware']
                except Exception:
                    printExc()
                self._login()
        return (None != self.session_key)
    
    def getUrlForChannel(self, channelID):
        printDBG('FilmOnComApi.getGroupList channelID[%r]' % channelID)
        url = self.middleware + "/api/channel/%s?session_key=%s&quality=low" % (str(channelID), str(self.session_key))
        def getUrlImpl(self, url):
            urlsList = []
            sts, data = self.cm.getPage(url)
            if sts:
                try:
                    data = json_loads(data)
                    seekable = data['seekable']
                    for stream in data['streams']:
                        name = stream.get('name', '')
                        if name == '':
                            name = stream['quality']
                        try:
                            if int(stream['watch-timeout']) < 1000:
                                name += ' ' + _('PAY')
                            else:
                                name += ' ' + _('FREE') 
                        except Exception:
                            pass
                        
                        url = stream['url']
                        if url.startswith('rtmp'):
                            flashplayer = 'http://www.filmon.com/tv/modules/FilmOnTV/files/flashapp/filmon/FilmonPlayer.swf?v=55'
                            pageUrl = 'http://www.filmon.com/tv/channel/export?channel_id=' + str(channelID)
                            url = url + '/' + stream['name'] + ' swfUrl=' + flashplayer + ' pageUrl=' + url
                        url = urlparser.decorateUrl(url)
                        url.meta.update({'iptv_urlwithlimit': False, 'iptv_livestream': not seekable})
                        urlsList.append({'name': name, 'url': url})
                except Exception:
                    printExc()
                
            return urlsList
            
        self.initSession()
        urlsList = getUrlImpl(self, url)
        if 0 == len(urlsList):
            self.initSession(force=True)
            urlsList = getUrlImpl(self, url)
        return urlsList
        
    def getGroupList(self, force=False):
        printDBG('FilmOnComApi.getGroupList force[%r]' % force)
        self._getJsonDataIfNeed('groups', force)
        return self.jsonData['groups']
        
    def getChannelsListByGroupID(self, group_id, force=False):
        printDBG('FilmOnComApi.getChannelsListByGroupID group_id[%r], force[%r]' % (group_id, force))
        self._getJsonDataIfNeed('channels', force)
        currChannelsList = [] 
        for channel_it in self.jsonData['channels']:
            if 'group_id' not in channel_it:
                continue
            if group_id == channel_it['group_id']:
                currChannelsList.append(channel_it)
        return currChannelsList
    
    def _getJsonItemlById(self, type, id):
        printDBG('FilmOnComApi._getChannelById type[%r], id[%r]' % (type, id))
        for item in self.jsonData[type]:
            if item['id'] == id:
                return item
        return None
        
    def _getJsonDataIfNeed(self, type, force=False):
        printDBG('FilmOnComApi._getJsonDataIfNeed type[%r], force[%r]' % (type, force))
        if 0 == len(self.jsonData[type]) or force:
            self.initSession(force=True)
            self._getJsonData(type)
        return 0 < len(self.jsonData[type])
        
    def _getJsonData(self, type):
        printDBG('FilmOnComApi._getJsonData type[%r]' % type)
        url = self.middleware + '/api/%s?session_key=%s' % (type, str(self.session_key))
        def getJsonDataImpl(self, url):
            sts, data = self.cm.getPage(url)
            if sts:
                try:
                    data = json_loads(data)
                    if not isinstance(data, list):
                        data = []
                except Exception:
                    printExc()
            else:
                data = []
            return data
        self.jsonData[type] = getJsonDataImpl(self, url)
        if 0 == len(self.jsonData[type]) and self.initSession(force=True):
            self.jsonData[type] = getJsonDataImpl(self, url)
        return 0 < len(self.jsonData[type])
        
    def _login(self):
        printDBG('FilmOnComApi.__login sessionKey[%s]' % str(self.session_key))
        if self.PREMIUM and None != self.session_key:
            postData = {}
            postData['login'] = self.LOGIN
            postData['password'] = md5(self.PASSWORD).hexdigest()
            postData['sessionkey'] = self.session_key
            loginURL = FilmOnComApi.MAINURL + "/api/login?session_key=" + self.session_key
            sts, data = self.cm.getPage(loginURL, {}, postData)
            if sts:
                printDBG('FilmOnComApi.__login user successfully logged in.')
                return True
            else:
                return False
        else:
            printDBG('FilmOnComApi.__login not premium')
            return True
