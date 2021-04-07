# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetCookieDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass
###################################################

###################################################
# FOREIGN import
###################################################

import re
try:
    import json
except Exception:
    import simplejson as json
############################################

###################################################
# Config options for HOST
###################################################


def GetConfigList():
    optionList = []
    return optionList

###################################################


class LivemassNetApi(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self)
        self.MAIN_URL = 'http://www.livemass.net/'
        self.DEFAULT_ICON_URL = 'http://s3.amazonaws.com/livemass/warrington/images/warrington/iconclr.png'
        self.HTTP_HEADER = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.94 Safari/537.36', 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate'}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})

        self.COOKIE_FILE = GetCookieDir('livemass.net')

        self.defaultParams = {'header': self.HTTP_HEADER, 'with_metadata': True, 'save_cookie': True, 'load_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.linksCache = {}

    def getList(self, cItem):
        printDBG("LivemassNetApi.getChannelsList")
        mainItemsTab = []
        cats = cItem.get('iptv_cats', '')
        if cats == '':
            sts, data = self.cm.getPage(self.getMainUrl(), self.defaultParams)
            if not sts:
                return []

            if not sts:
                url = 'http://s3.amazonaws.com/livemass/index.html'
            else:
                printDBG(data)
                printDBG("----------------------")
                url = self.cm.ph.getSearchGroups(data, '''<i?frame[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0].replace('&amp;', '&')
                printDBG(url)
            if self.cm.isValidUrl(url):
                if 'index.html/' in url:
                    url = url.split('index.html/', 1)[0] + 'index.html'
                sts, data = self.cm.getPage(url, self.defaultParams)
                if not sts:
                    return []
                cUrl = data.meta['url']

                if 'refresh' in data:
                    url = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''url=([^'^"^>^\s]+?)['">\s]''', 1, True)[0], cUrl)
                    sts, data = self.cm.getPage(url, self.defaultParams)
                    if not sts:
                        return []

            cUrl = data.meta['url']
            data = re.compile('''<a[^>]+?href=['"]([^'^"]+?)['"][^>]*?>\s*?(EN|FR)\s*?<''', re.IGNORECASE).findall(data)
            for item in data:
                url = self.getFullUrl(item[0], cUrl)
                title = self.cleanHtmlStr(item[1])
                params = dict(cItem)
                params.update({'title': title, 'url': url, 'iptv_cats': 'list'})
                mainItemsTab.append(params)
        else:
            sts, data = self.cm.getPage(cItem['url'], self.defaultParams)
            if not sts:
                return []
            cUrl = data.meta['url']

            printDBG("_______________________")
            printDBG(data)
            linksTab = []
            groupsNames = []
            liveItem = None
            data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'shape_'), ('</div', '>'))
            for item in data:
                if 'href' not in item:
                    groupName = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<p', '</p>')[1])
                    if groupName != '':
                        groupsNames.append({'title': groupName})
                    printDBG('>>>> groupName[%s]' % groupName)
                else:
                    links = []
                    item = self.cm.ph.getAllItemsBeetwenNodes(item, ('<a', '>'), ('</a', '>'))
                    if 0 == len(item):
                        continue
                    for it in item:
                        title = self.cleanHtmlStr(it)
                        if title.upper() in ['FR', 'EN']:
                            break
                        url = self.getFullUrl(self.cm.ph.getSearchGroups(it, '''\shref=['"]([^'^"]+?)['"]''', 1, True)[0], cUrl)
                        if ('/live.' in url or '/live-fr.' in url) and liveItem == None:
                            liveItem = {'title': self.cleanHtmlStr(it), 'url': url}
                        elif self.cm.isValidUrl(url):
                            links.append({'title': title, 'url': url})
                    if 2 == len(links):
                        linksTab.append(links)

            if liveItem != None:
                params = dict(cItem)
                params.update(liveItem)
                params.update({'type': 'video'})
                mainItemsTab.append(params)

            if len(groupsNames) <= len(linksTab):
                for idx in range(len(groupsNames)):
                    params = dict(cItem)
                    params.update(groupsNames[idx])
                    params.update({'type': 'marker'})
                    mainItemsTab.append(params)
                    for item in linksTab[idx]:
                        params = dict(cItem)
                        params.update(item)
                        params.update({'type': 'video'})
                        mainItemsTab.append(params)

        return mainItemsTab

    def getVideoLink(self, cItem):
        printDBG("LivemassNetApi.getVideoLink")
        urlsTab = self.linksCache.get(cItem['url'], [])
        if len(urlsTab):
            return urlsTab

        sts, data = self.cm.getPage(cItem['url'], self.defaultParams)
        if not sts:
            return urlsTab

        data = self.cm.ph.getSearchGroups(data, '''['"]?sources['"]?\s*?:\s*?(\[[^\]]+?\])''', 1, True)[0]
        printDBG(data)
        data = data.split('},')
        for item in data:
            url = self.cm.ph.getSearchGroups(item, '''['"]?file['"]?\s*?:\s*['"](https?://[^'^"]+?)['"]''', 1, True)[0]
            if url == '':
                continue
            name = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''['"]?label['"]?\s*?:\s*['"]([^'^"]+?)['"]''', 1, True)[0])
            if '.m3u8' in url:
                urlsTab.extend(getDirectM3U8Playlist(url, checkContent=True))
            else:
                urlsTab.append({'name': name, 'url': url})

        for idx in range(len(urlsTab)):
            urlsTab[idx]['need_resolve'] = 0
            urlsTab[idx]['url'] = strwithmeta(urlsTab[idx]['url'], {'Referer': cItem['url']})

        try:
            urlsTab.sort(key=lambda item: int(item.get('bitrate', '0')), reverse=True)
        except Exception:
            printExc()

        if len(urlsTab):
            self.linksCache[cItem['url']] = urlsTab

        return urlsTab
