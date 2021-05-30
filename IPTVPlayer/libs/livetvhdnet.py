# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetCookieDir, byteify, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib
############################################

###################################################
# Config options for HOST
###################################################


def GetConfigList():
    optionList = []
    return optionList
###################################################


class LivetvhdNetApi(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self)
        self.MAIN_URL = 'https://livetvhd.net/'
        self.HEADER = {'User-Agent': 'Mozilla/5.0 (iPad; U; CPU OS 3_2 like Mac OS X; en-us) AppleWebKit/531.21.10 (KHTML, like Gecko) Version/4.0.4 Mobile/7B334b Safari/531.21.10', 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})

        self.COOKIE_FILE = GetCookieDir('livetvhdnet.cookie')

        self.http_params = {}
        self.http_params.update({'header': self.HEADER, 'save_cookie': True, 'load_cookie': True, 'cookiefile': self.COOKIE_FILE})

        self.cacheList = {}

        self.needProxy = None

    def isNeedProxy(self):
        if self.needProxy == None:
            sts, data = self.cm.getPage('https://static.livetvhd.net/thumbs/first.jpg')
            self.needProxy = not sts
        return self.needProxy

    def getFullIconUrl(self, url):
        url = self.getFullUrl(url)
        if url != '' and self.isNeedProxy():
            proxy = 'http://www.proxy-german.de/index.php?q={0}&hl=2e1'.format(urllib.quote(url, ''))
            params = {}
            params['User-Agent'] = self.HEADER['User-Agent'],
            params['Referer'] = proxy
            params['Cookie'] = 'flags=2e5;'
            url = strwithmeta(proxy, params)
        return url

    def getList(self, cItem):
        printDBG("LivetvhdNetApi.getChannelsList")
        channelsTab = []

        try:
            initList = cItem.get('init_list', True)
            if initList:
                rm(self.COOKIE_FILE)
                params = dict(cItem)
                params.update({'init_list': False, 'url': 'https://livetvhd.net/api/videos', 'title': _('--All--')})
                channelsTab.append(params)

                sts, data = self.cm.getPage('https://livetvhd.net/api/categories')
                if not sts:
                    return []
                data = json_loads(data)
                for item in data:
                    params = dict(cItem)
                    params.update({'init_list': False, 'url': 'https://livetvhd.net/api/videos/category/' + item['seo_name'], 'title': self.cleanHtmlStr(item['name'])})
                    channelsTab.append(params)
            else:
                sts, data = self.cm.getPage(cItem['url'])
                if not sts:
                    return []
                data = json_loads(data)
                if 'videos' in data:
                    data = data['videos']
                for item in data:
                    url = item['url']
                    icon = item['thumbnail']
                    title = self.cleanHtmlStr(item['title'])
                    desc = _('Views: ') + str(item.get('views', ''))
                    params = dict(cItem)
                    params.update({'type': 'video', 'title': title, 'url': url, 'desc': desc, 'icon': self.getFullIconUrl(icon)})
                    channelsTab.append(params)
        except Exception:
            printExc()
        return channelsTab

    def _getAttrVal(self, data, attr):
        return self.cm.ph.getSearchGroups(data, '''['"]?%s['"]?\s*:\s*['"]([^'^"]+?)['"]''' % attr)[0]

    def getVideoLink(self, cItem):
        printDBG("LivetvhdNetApi.getVideoLink")
        urlsTab = []
        if len(cItem['url']) < 3:
            return []

        sts, data = self.cm.getPage('https://livetvhd.net/api/videos', self.http_params)
        if not sts:
            return []
        token = self.cm.ph.getDataBeetwenReMarkers(data, re.compile('"token"\s*:\s*"'), re.compile('"'), False)[1]

        videoUrl = cItem['url'] + '?token=' + token

        videoUrl = strwithmeta(videoUrl, {'Referer': self.MAIN_URL, 'User-Agent': self.HEADER['User-Agent']})
        urlsTab = getDirectM3U8Playlist(videoUrl, checkContent=True)
        return urlsTab
