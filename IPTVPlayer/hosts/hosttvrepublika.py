# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
###################################################

###################################################
# FOREIGN import
###################################################
import re
try:
    import json
except Exception:
    import simplejson as json
###################################################


def gettytul():
    return 'http://telewizjarepublika.pl/'


class TVRepublkaPL(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'telewizjarepublika.pl', 'cookie': 'telewizjarepublika.pl.cookie'})

        self.DEFAULT_ICON_URL = 'https://www.wykop.pl/cdn/c3397993/link_Slctpx7wLRquolqkd37R5bhtYaVcBy5P,w300h223.jpg'
        self.HEADER = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0', 'DNT': '1', 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})
        self.MAIN_URL = 'http://telewizjarepublika.pl/'
        self.defaultParams = {'with_metadata': True, 'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

    def getPage(self, url, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)

        return self.cm.getPage(url, addParams, post_data)

    def listMainMenu(self, cItem):
        params = dict(cItem)
        params = {'good_for_fav': True, 'title': 'Telewizja Republika - na żywo', 'url': 'http://live.telewizjarepublika.pl/live.php', 'icon': self.getFullIconUrl('/imgcache/750x400/c/uploads/news/republika.png')}
        self.addVideo(params)

        MAIN_CAT_TAB = [{'category': 'list_items', 'title': 'Poland Daily', 'url': self.getFullUrl('/poland-daily')},
                        {'category': 'list_items', 'title': 'Wideo', 'url': self.getFullUrl('/wideo')},
                        {'category': 'magazines', 'title': 'Magazyny', 'url': self.getFullUrl('/wideo')}, ]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listItems(self, cItem):
        printDBG("TVRepublkaPL.listItems")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'video-item'), ('<div', '>', 'footer'))[1]
        data = self.cm.ph.rgetAllItemsBeetwenNodes(data, ('</div', '>'), ('<div', '>', 'video-item'))
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^"^']+?)['"]''')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'video-title'), ('</div', '>'))[1])
            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'video-date'), ('</div', '>'))[1])
            if not self.cm.isValidUrl(url):
                continue
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''\ssrc=['"]([^"^']+?)['"]''')[0])
            params = dict(cItem)
            params = {'good_for_fav': True, 'title': title, 'url': url, 'icon': icon, 'desc': desc}
            self.addVideo(params)

    def listMagazines(self, cItem, nextCategory):
        printDBG("TVRepublkaPL.listMagazines")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'magazyny'), ('<div', '>', 'video'))[1]
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'magazyn-item'), ('</div', '>'))
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^"^']+?)['"]''')[0])
            if url == '':
                continue
            title = url.split('/')[-2].replace('-', ' ').decode('utf-8').title().encode('utf-8')
            if not self.cm.isValidUrl(url):
                continue
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''\ssrc=['"]([^"^']+?)['"]''')[0])
            params = dict(cItem)
            params = {'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'icon': icon}
            self.addDir(params)

    def getLinksForVideo(self, cItem):
        printDBG("TVRepublkaPL.getLinksForVideo [%s]" % cItem)
        urlTab = []

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'video-play'), ('<script', '>'), False)[1]
        tmp = self.cm.ph.getDataBeetwenMarkers(tmp, '<video', '</video>', False)[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<source', '>')
        if len(tmp):
            for item in tmp:
                type = self.cm.ph.getSearchGroups(item, '''type=['"]([^'^"]+?)['"]''')[0].lower()
                name = self.cm.ph.getSearchGroups(item, '''label=['"]([^'^"]+?)['"]''')[0]
                url = self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0]
                if name == '':
                    name = '%s. %s' % (str(len(urlTab) + 1), type)

                if 'video/mp4' == type:
                    urlTab.append({'name': name, 'url': self.getFullUrl(url), 'need_resolve': 0})
                elif 'application/x-mpegurl' == type:
                    urlTab.extend(getDirectM3U8Playlist(url, checkExt=False, checkContent=True, sortWithMaxBitrate=999999999))
        if 0 == len(urlTab):
            tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'video-id'), ('</div', '>'))
            for item in tmp:
                videoId = self.cm.ph.getSearchGroups(item, '''\sdata\-video\-id=['"]([^'^"]+?)['"]''')[0]
                dataType = self.cm.ph.getSearchGroups(item, '''\sdata\-type=['"]([^'^"]+?)['"]''')[0].lower()
                if dataType in 'youtube':
                    urlTab.append({'name': dataType, 'url': 'https://www.youtube.com/watch?v=' + videoId, 'need_resolve': 1})
                else:
                    printDBG("Unknown url type [%s] id[%s]" % (dataType, videoId))
        if 0 == len(urlTab):
            tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<iframe', '>', 'player'), ('</div', '>'))
            for item in tmp:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0])
                name = '%s. %s' % (str(len(urlTab) + 1), self.up.getHostName(url))
                urlTab.append({'name': name, 'url': url, 'need_resolve': 1})

        return urlTab

    def getVideoLinks(self, videoUrl):
        printDBG("TVRepublkaPL.getVideoLinks [%s]" % videoUrl)
        urlTab = []
        if 1 == self.up.checkHostSupport(videoUrl):
            urlTab = self.up.getVideoLinkExt(videoUrl)
        else:
            sts, data = self.getPage(videoUrl)
            if sts:
                hlsUrls = set(re.compile('''(https?://[^'^"]+?\.m3u8(?:\?[^'^"]+?)?)['"]''', re.IGNORECASE).findall(data))
                for url in hlsUrls:
                    urlTab.extend(getDirectM3U8Playlist(url, checkExt=False, checkContent=True, sortWithMaxBitrate=999999999))
        return urlTab

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: >> name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listMainMenu({'name': 'category'})
        elif category == 'magazines':
            self.listMagazines(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem)
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, TVRepublkaPL(), True, [])
