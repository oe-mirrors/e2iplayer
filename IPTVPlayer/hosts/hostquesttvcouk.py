# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify, CSelOneLink
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
###################################################

###################################################
# FOREIGN import
###################################################
import urlparse
import urllib
try:
    import json
except Exception:
    import simplejson as json
###################################################


def gettytul():
    return 'http://questtv.co.uk/'


class QuesttvCoUK(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'questtv.co.uk', 'cookie': 'questtv.co.uk.cookie'})
        self.DEFAULT_ICON_URL = 'http://www.questtv.co.uk/wp-content/themes/dni_wp_theme_quest_uk/img/quest_logo.png'
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.MAIN_URL = 'http://www.questtv.co.uk/'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate', 'Referer': self.getMainUrl(), 'Origin': self.getMainUrl()}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding': 'gzip, deflate', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json, text/javascript, */*; q=0.01'})

        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        origBaseUrl = baseUrl
        baseUrl = self.cm.iriToUri(baseUrl)

        def _getFullUrl(url):
            if self.cm.isValidUrl(url):
                return url
            else:
                return urlparse.urljoin(baseUrl, url)
        addParams['cloudflare_params'] = {'domain': self.up.getDomain(baseUrl), 'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT, 'full_url_handle': _getFullUrl}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def listOnDemand(self, cItem):
        printDBG("QuesttvCoUK.listOnDemand")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenMarkers(data, 'jQuery.get(', ')')[1]
        url = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''['"]([^'^"]+?)['"]''')[0])

        params = dict(self.defaultParams)
        params['header'] = dict(self.AJAX_HEADER)
        params['header']['Referer'] = cItem['url']

        sts, data = self.getPage(url, params)
        if not sts:
            return

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'dni-video-playlist-thumb-box'), ('</a', '>'))
        for item in data:
            videoId = self.cm.ph.getSearchGroups(item, '''href=['"]#([0-9]+?)['"]''')[0]
            if videoId == '':
                continue
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''alt=['"]([^'^"]+?)['"]''')[0])
            if title == '':
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<h3', '>', 'descHidden'), ('</h3', '>'))[1])
            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<p', '>', 'descHidden'), ('</p', '>'))[1])
            icon = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0])
            params = {'type': 'video', 'title': title, 'f_video_id': videoId, 'desc': desc, 'icon': icon}
            self.addVideo(params)

    def getLinksForVideo(self, cItem):
        printDBG("QuesttvCoUK.getLinksForVideo [%s]" % cItem)
        urlTab = []
        mp4Tab = []
        hlsTab = []

        if 'f_video_id' in cItem:
            videoId = cItem['f_video_id']
        else:
            sts, data = self.getPage(cItem['url'])
            if not sts:
                return

            videoId = self.cm.ph.getSearchGroups(data, '''data\-videoid=['"]([^'^"]+?)['"]''')[0]
            if videoId == '':
                return ''

            getParams = {}
            data = self.cm.ph.getDataBeetwenMarkers(data, '<object', '</object>')[1]
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<param', '>')
            for item in data:
                name = self.cm.ph.getSearchGroups(item, '''name=['"]([^'^"]+?)['"]''')[0]
                if name not in ['playerID', '@videoPlayer', 'playerKey']:
                    continue
                value = self.cm.ph.getSearchGroups(item, '''value=['"]([^'^"]+?)['"]''')[0]
                getParams[name] = value

            url = 'http://c.brightcove.com/services/viewer/htmlFederated?' + urllib.urlencode(getParams)
            sts, data = self.getPage(url)
            if sts:
                data = self.cm.ph.getDataBeetwenMarkers(data, '"renditions":', ']', False)[1]
                try:
                    printDBG(data)
                    data = byteify(json.loads(data + ']'), '', True)
                    for item in data:
                        if item['videoCodec'] != 'H264':
                            continue
                        url = item['defaultURL']
                        if not self.cm.isValidUrl(url):
                            continue
                        name = '[mp4] bitrate: %s, %sx%s' % (item['encodingRate'], item['frameWidth'], item['frameHeight'])
                        mp4Tab.append({'name': name, 'url': url, 'bitrate': item['encodingRate']})

                        def __getLinkQuality(itemLink):
                            try:
                                return int(itemLink['bitrate'])
                            except Exception:
                                return 0
                        mp4Tab = CSelOneLink(mp4Tab, __getLinkQuality, 999999999).getSortedLinks()
                except Exception:
                    printExc()

        hlsUrl = 'http://c.brightcove.com/services/mobile/streaming/index/master.m3u8?videoId=' + videoId
        hlsTab = getDirectM3U8Playlist(hlsUrl, checkContent=True, sortWithMaxBitrate=999999999)
        for idx in range(len(hlsTab)):
            hlsTab[idx]['name'] = '[hls] ' + hlsTab[idx]['name'].replace('None', '').strip()

        urlTab.extend(mp4Tab)
        urlTab.extend(hlsTab)
        return urlTab

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listOnDemand({'name': 'category', 'url': self.getFullUrl('/video')})
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, QuesttvCoUK(), True, [])
