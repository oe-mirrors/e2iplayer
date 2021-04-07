# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, GetCookieDir
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
###################################################

###################################################
# FOREIGN import
###################################################
import re
###################################################

# code of TeledunetParser is based on https://github.com/hadynz/repository.arabic.xbmc-addons/blob/master/plugin.video.teledunet/resources/lib/teledunet/scraper.py#L11
class TeledunetParser:
    HEADER_REFERER = 'http://www.teledunet.com/'
    HEADER_HOST = 'www.teledunet.com'
    HEADER_USER_AGENT = 'Mozilla/5.0'
    TELEDUNET_TIMEPLAYER_URL = 'http://www.teledunet.com/tv_/?channel=%s&no_pub'

    def __init__(self):
        self.cm = common()
        self.COOKIE_FILE = GetCookieDir('teledunet.cookie')

    def __get_channel_time_player(self, channel_name):
        # Fetch the main Teledunet website to be given a Session ID
        params = {'cookiefile':self.COOKIE_FILE, 'use_cookie': True, 'load_cookie':False, 'save_cookie':True} 
        sts, data = self.cm.getPage(self.HEADER_REFERER, params)
        if False == sts:
            printDBG("__get_cookie_session getPage problem")
        
        url = self.TELEDUNET_TIMEPLAYER_URL % channel_name
        
        HTTP_HEADER = {'Host': self.HEADER_HOST,
                       'Referer': self.HEADER_REFERER,
                       'User-agent': self.HEADER_USER_AGENT}
                       
        params = {'header':HTTP_HEADER, 'cookiefile':self.COOKIE_FILE, 'use_cookie': True, 'load_cookie':True, 'save_cookie':False} 
        sts, data = self.cm.getPage(url, params)
        if False == sts:
            printDBG("__get_channel_time_player getPage problem")
 
        m = re.search('time_player=(.*);', data, re.M | re.I)
        time_player_str = eval(m.group(1))

        m = re.search('curent_media=\'(.*)\';', data, re.M | re.I)
        rtmp_url = m.group(1)
        play_path = rtmp_url[rtmp_url.rfind("/") + 1:]
        return rtmp_url, play_path, repr(time_player_str).rstrip('0').rstrip('.')
        
    def get_rtmp_params(self, url):
        try:
            channel_name = url.split(' ')[0].split('/')[-1]
            printDBG('get_rtmp_params channel_name[%s]' % channel_name)
            rtmp_url, play_path, time_player_id = self.__get_channel_time_player(channel_name)
            swf_url = ('http://www.teledunet.com/tv/player.swf?'
                    'bufferlength=5&'
                    'repeat=single&'
                    'autostart=true&'
                    'id0=%(time_player)s&'
                    'streamer=%(rtmp_url)s&'
                    'file=%(channel_name)s&'
                    'provider=rtmp'
                    ) % {'time_player': time_player_id, 'channel_name': play_path, 'rtmp_url': rtmp_url}
                        
            url = '%s playpath=%s app=teledunet swfUrl=%s pageUrl=http://www.teledunet.com/tv/?channel=%s&no_pub live=1' % (rtmp_url, play_path, swf_url, play_path)
            printDBG('get_rtmp_params url[%s]' % url)
            return url
        except Exception:
            printDBG('get_rtmp_params excetion')
            return ''
            

