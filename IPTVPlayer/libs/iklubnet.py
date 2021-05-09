# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetCookieDir
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass
###################################################

###################################################
# FOREIGN import
###################################################
from Components.config import config, ConfigYesNo, getConfigListEntry
import re
import urllib
try:
    import json
except Exception:
    import simplejson as json
############################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.iklubnet_categorization = ConfigYesNo(default=True)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_('Categorization') + ": ", config.plugins.iptvplayer.iklubnet_categorization))
    return optionList

###################################################


class IKlubNetApi(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self)
        self.MAIN_URL = 'http://iklub.net/'
        self.HEADER = {'User-Agent': 'Mozilla/5.0', 'Accept': 'text/html'}
        self.COOKIE_FILE = GetCookieDir('iklubnet.cookie')

        self.http_params = {}
        self.http_params.update({'save_cookie': True, 'load_cookie': True, 'cookiefile': self.COOKIE_FILE})
        #self.cacheList = {}
        #self.cacheLinks = {'url':'', 'tab':[]}

    def getListOfChannels(self, cItem):
        printDBG("IKlubNetApi.getListOfChannels")
        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return []

        retList = []
        data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="entry-content">', '</div>')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
        for item in data:
            url = self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0]
            icon = self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0]
            title = self.cm.ph.getSearchGroups(item, '''alt=['"]([^'^"]+?)['"]''')[0].replace('Telewizja online - ', '')
            if url == '':
                continue
            params = dict(cItem)
            params.update({'type': 'video', 'url': self.getFullUrl(url), 'title': title, 'icon': self.getFullUrl(icon)})
            retList.append(params)
        return retList

    def getList(self, cItem):
        printDBG("IKlubNetApi.getChannelsList")
        channelsTab = []
        initList = cItem.get('init_list', True)
        if initList:
            if config.plugins.iptvplayer.iklubnet_categorization.value:
                retList = []
                sts, data = self.cm.getPage(self.getFullUrl(self.MAIN_URL))
                if not sts:
                    return []
                data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="menu">', '</ul>')[1]
                data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
                for item in data:
                    url = self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0]
                    title = self.cleanHtmlStr(item)
                    if url == '':
                        continue
                    #if 'vlc-channel' in url: continue
                    params = dict(cItem)
                    params.update({'init_list': False, 'url': self.getFullUrl(url), 'title': title})
                    retList.append(params)
                channelsTab = retList
            else:
                cItem = dict(cItem)
                cItem['url'] = self.getFullUrl('all/')
                channelsTab = self.getListOfChannels(cItem)
        else:
            if 'vlc-channel' in cItem['url']:
                sts, data = self.cm.getPage(self.getFullUrl('vlcchannel.html'))
                if not sts:
                    return []
                retList = []
                data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<option', '</option>', withMarkers=True, caseSensitive=False)
                for item in data:
                    uri = self.cm.ph.getSearchGroups(item, 'value="([^"]+?)"')[0]
                    if uri != '':
                        title = self.cleanHtmlStr(item)
                        params = dict(cItem)
                        params.update({'type': 'video', 'title': title, 'vlc': True, 'url': uri})
                        retList.append(params)
                return retList
            elif 'tvpregionalna' in cItem['url']:
                sts, data = self.cm.getPage('http://tvpstream.tvp.pl/')
                if not sts:
                    return []
                retList = []
                data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="button', '</div>', withMarkers=True, caseSensitive=False)
                for item in data:
                    id = self.cm.ph.getSearchGroups(item, 'data-video_id="([0-9]+?)"')[0]
                    if id != '':
                        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'titlte="([^"]+?)"')[0])
                        icon = self.cm.ph.getSearchGroups(item, 'src="(http[^"]+?)"')[0]
                        title = self.cm.ph.getSearchGroups(item, 'alt="([^"]+?)"')[0].replace('-', ' ').title()
                        params = dict(cItem)
                        params.update({'type': 'video', 'title': title, 'url': 'http://tvpstream.tvp.pl/sess/tvplayer.php?object_id=%s&autoplay=true' % id, 'icon': icon, 'desc': desc})
                        retList.append(params)
                return retList
            else:
                channelsTab = self.getListOfChannels(cItem)
        return channelsTab

    def getTvpStreamLink(self, data):
        printDBG(data)
        file = self.cm.ph.getSearchGroups(data, '''['"](https?[^'^"]+?\.m3u8[^'^"]*?)['"]''')[0]
        return getDirectM3U8Playlist(file)

    def getVideoLink(self, cItem):
        printDBG("IKlubNetApi.getVideoLink")
        urlsTab = []

        if cItem.get('vlc', False):
            uri = cItem['url']
            if uri.startswith('http') and uri.split('?')[-1].endswith('.m3u8'):
                urlsTab.extend(getDirectM3U8Playlist(uri))
            elif uri.startswith('rtmp'):
                urlsTab.append({'name': '[rtmp]', 'url': uri + ' live=1 '})
            elif uri.startswith('http'):
                urlsTab.append({'name': '[rtmp]', 'url': urlparser.decorateUrl(uri, {'iptv_livestream': True})})
            return urlsTab

        url = cItem['url']
        nextTitle = 'Podstawowy '
        for linkIdx in range(2):
            if '' == url:
                break
            title = nextTitle

            sts, data = self.cm.getPage(url)
            if not sts:
                return urlsTab

            if 'tvpstream.tvp.pl' in url:
                urlsTab.extend(self.getTvpStreamLink(data))
                if linkIdx > 0:
                    return urlsTab

            url = self.getFullUrl(self.cm.ph.getSearchGroups(data, '<a href="([^"]+?)"[^>]*?><img[^>]*?alt="Zapasowy Player"', 1, True)[0])
            if '' == url:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(data, '<a href="([^"]+?)"[^>]*?><img[^>]*?alt="[^"]*?vlc[^"]*?"', 1, True)[0])
            nextTitle = 'Zapasowy '

            printDBG(data)

            urlNext = self.cm.ph.getSearchGroups(data, '<iframe[^>]+?src="([^"]+?iklub[^"]+?)"', 1, True)[0]
            if '' == urlNext:
                urlNext = self.cm.ph.getSearchGroups(data, '<iframe[^>]+?src="([^"]+?)"', 1, True)[0]
            if self.cm.isValidUrl(urlNext):
                sts, data = self.cm.getPage(urlNext)
                if not sts:
                    continue

            data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'eval(', ');', False)
            try:
                ddata = ''
                for idx in range(len(data)):
                    tmp = data[idx].split('+')
                    for item in tmp:
                        item = item.strip()
                        if item.startswith("'") or item.startswith('"'):
                            ddata += self.cm.ph.getSearchGroups(item, '''['"]([^'^"]+?)['"]''')[0]
                        else:
                            tmp2 = re.compile('''unescape\(['"]([^"^']+?)['"]''').findall(item)
                            for item2 in tmp2:
                                ddata += urllib.unquote(item2)

                printDBG("++++++++++++++++++++++++++++++++++++++++++++++++++++")
                printDBG(ddata)
                printDBG("++++++++++++++++++++++++++++++++++++++++++++++++++++")

                funName = self.cm.ph.getSearchGroups(ddata, '''function\s*([^\(]+?)''')[0].strip()
                sp = self.cm.ph.getSearchGroups(ddata, '''split\(\s*['"]([^'^"]+?)['"]''')[0]
                modStr = self.cm.ph.getSearchGroups(ddata, '''\+\s*['"]([^'^"]+?)['"]''')[0]
                modInt = int(self.cm.ph.getSearchGroups(ddata, '''\+\s*(-?[0-9]+?)[^0-9]''')[0])

                ddata = self.cm.ph.getSearchGroups(ddata, '''document\.write[^'^"]+?['"]([^'^"]+?)['"]''')[0]
                data = ''
                tmp = ddata.split(sp)
                ddata = urllib.unquote(tmp[0])
                k = urllib.unquote(tmp[1] + modStr)
                for idx in range(len(ddata)):
                    data += chr((int(k[idx % len(k)]) ^ ord(ddata[idx])) + modInt)

                printDBG("++++++++++++++++++++++++++++++++++++++++++++++++++++")
                printDBG(data)
                printDBG("++++++++++++++++++++++++++++++++++++++++++++++++++++")

                if 'rtmp://' in data:
                    rtmpUrl = self.cm.ph.getDataBeetwenMarkers(data, '&source=', '&', False)[1]
                    if rtmpUrl == '':
                        rtmpUrl = self.cm.ph.getSearchGroups(data, r'''['"](rtmp[^"^']+?)['"]''')[0]
                    urlsTab.append({'name': title + ' [rtmp]', 'url': rtmpUrl + ' live=1 '})
                elif '.m3u8' in data:
                    file = self.cm.ph.getSearchGroups(data, r'''['"](http[^"^']+?\.m3u8[^"^']*?)['"]''')[0]
                    if file == '':
                        file = self.cm.ph.getDataBeetwenMarkers(data, 'src=', '&amp;', False)[1]
                    urlsTab.extend(getDirectM3U8Playlist(file))
                elif 'tvp.info' in data:
                    vidUrl = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''['"](http[^'^"]+?tvp.info[^'^"]+?)['"]''')[0])
                    sts, data = self.cm.getPage(vidUrl)
                    if not sts:
                        return []
                    urlsTab.extend(self.getTvpStreamLink(data))
                elif 'mrl=' in data:
                    file = self.cm.ph.getSearchGroups(data, '''mrl=['"](http[^'^"]+?)['"]''')[0]
                    urlsTab.append({'name': title + ' [mrl]', 'url': file})
                elif '<source ' in data:
                    file = self.cm.ph.getSearchGroups(data, '''<source[^>]+?src=['"](http[^'^"]+?)['"]''')[0]
                    urlsTab.append({'name': title + ' [src]', 'url': file})
                else:
                    urlsTab.extend(self.up.getAutoDetectedStreamLink(url, data))

                if 'content.jwplatform.com' in data:
                    vidUrl = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''['"]([^'^"]+?content.jwplatform.com[^'^"]+?)['"]''')[0])

                    sts, data = self.cm.getPage(vidUrl)
                    if not sts:
                        continue

                    if '/players/' not in vidUrl:
                        vidUrl = self.cm.ph.getSearchGroups(data, '''['"](https?[^'^"]+?/players/[^'^"]+?\.js)['"]''')[0]
                        HEADER = dict(self.HEADER)
                        HEADER['Referer'] = vidUrl
                        sts, data = self.cm.getPage(vidUrl, {'header': HEADER})
                        if not sts:
                            continue

                    data = self.cm.ph.getDataBeetwenMarkers(data, '"sources":', ']', False)[1]
                    file = self.cm.ph.getSearchGroups(data, r'''['"]?file['"]?\s*:\s*['"]([^"^']+)['"],''')[0]
                    printDBG(">>>>>>>>>>>>>>>>>>>>>>>> FILE[%s]" % file)
                    if file.startswith('http') and file.split('?')[-1].endswith('.m3u8'):
                        urlsTab.extend(getDirectM3U8Playlist(file))
                    elif file.startswith('rtmp'):
                        urlsTab.append({'name': title + ' [rtmp]', 'url': file + ' live=1 '})
            except Exception:
                printExc()
                continue

        return urlsTab
