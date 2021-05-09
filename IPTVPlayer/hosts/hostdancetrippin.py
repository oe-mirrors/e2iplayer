# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib
###################################################


def gettytul():
    return 'http://dancetrippin.tv/'


class DancetrippinTV(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'DancetrippinTV.tv', 'cookie': 'kinomantv.cookie'})
        self.defaultParams = {'with_metadata': True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.HEADER = {'User-Agent': 'Mozilla/5.0', 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})

        self.MAIN_URL = "http://www.dancetelevision.net/"
        self.DEFAULT_ICON_URL = 'https://frenezy.files.wordpress.com/2010/10/dancetrippin.jpg'

        self.MAIN_CAT_TAB = [{'category': 'fill_items', 'title': _('LATEST CONTENT'), 'url': self.getMainUrl()},
                             {'category': 'channels', 'title': _('CHANNELS '), 'url': self.getMainUrl()},
                             {'category': 'artists', 'title': _('ARTISTS'), 'url': self.getMainUrl()},
                             {'category': 'fill_items', 'title': _('PARTIES'), 'url': self.getFullUrl('/parties')},
                             {'category': 'fill_items', 'title': _('VENUES'), 'url': self.getFullUrl('/venues')},
                             {'category': 'search', 'title': _('Search'), 'search_item': True},
                             {'category': 'search_history', 'title': _('Search history')}]

        self.ARTISTS_CAT_TAB = [{'category': 'fill_items', 'title': _('Most featured'), 'url': self.getFullUrl('/artists')},
                                {'category': 'fill_items', 'title': _('Alphabetical '), 'url': self.getFullUrl('/artists/sort/alphabetical')}]

        self.cacheItems = []
        self.cacheFilters = []

    def setMainUrl(self, url):
        if self.cm.isValidUrl(url):
            self.MAIN_URL = self.cm.getBaseUrl(url)

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def listsChannels(self, cItem, nextCategory):
        printDBG("DancetrippinTV.listsChannels")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(data.meta['url'])

        data = self.cm.ph.getDataBeetwenNodes(data, ('<', '>', 'browsenetwork'), ('</ul', '>'), False)[1]
        data = data.split('</li>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0])
            if url == '':
                continue
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''\ssrc=['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<a', '>'), ('</a', '>'), False)[1])
            params = dict(cItem)
            params.update({'good_for_fav': False, 'category': nextCategory, 'url': url, 'title': title, 'icon': icon})
            self.addDir(params)

    def listChannel(self, cItem):
        printDBG("DancetrippinTV.listChannel")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(data.meta['url'])

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'navigation'), ('</div', '>'), False)[1]
        for item in ['menu-videos', 'menu-24', 'menu-djmixes']:
            tmp = self.cm.ph.getDataBeetwenNodes(data, ('<a', '>', item), ('</a', '>'))[1]
            url = self.getFullUrl(self.cm.ph.getSearchGroups(tmp, '''\shref=['"]([^'^"]+?)['"]''')[0])
            if url == '':
                continue
            if item == 'menu-24':
                if url.endswith('/channels'):
                    nextCategory = 'playlists24'
                else:
                    nextCategory = 'playlist'
            else:
                nextCategory = 'fill_items'

            title = self.cleanHtmlStr(tmp)
            params = dict(cItem)
            params.update({'good_for_fav': False, 'category': nextCategory, 'url': url, 'title': title})
            self.addDir(params)

    def listPlaylists24(self, cItem, nextCategory):
        printDBG("DancetrippinTV.listPlaylists24")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(data.meta['url'])

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'grid-content'), ('<footer', '>'), False)[1]
        data = self.cm.ph.rgetAllItemsBeetwenNodes(data, ('</div', '>'), ('<div', '>', '"single'))
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0])
            if url == '':
                continue
            icon = self.getFullIconUrl(self.cm.ph.getDataBeetwenMarkers(item, 'url(', ')', False)[1].strip())
            item = item.split('</h3>', 1)
            title = self.cleanHtmlStr(self.cleanHtmlStr(item[0]))
            desc = self.cleanHtmlStr(item[-1])
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': nextCategory, 'url': url, 'title': title, 'icon': icon, 'desc': desc})
            self.addDir(params)

    def listPlaylist(self, cItem):
        printDBG("DancetrippinTV.listPlaylist")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(data.meta['url'])

        pevId = cItem.get('last_id', '')
        lastId = ''
        data = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'playlist'), ('</ul', '>'), False)[1]
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<li', '>', 'single'), ('</li', '>'))
        for item in data:
            lastId = self.cm.ph.getSearchGroups(item, '''\sdata\-id=['"]([^'^"]+?)['"]''')[0]
            if pevId != '' and pevId == lastId:
                self.currList = []
                continue

            streamUrl = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\sdata\-loc=['"]([^'^"]+?)['"]''')[0])
            if streamUrl == '':
                continue
            streamType = self.cm.ph.getSearchGroups(item, '''\sdata\-type=['"]([^'^"]+?)['"]''')[0].lower()
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''\sdata\-poster=['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(self.cm.ph.rgetDataBeetwenMarkers2(item, '</div>', '<div')[1])

            params = dict(cItem)
            params.update({'good_for_fav': False, 'url': streamUrl, 'stream_type': streamType, 'title': title, 'icon': icon})
            self.addVideo(params)

        if len(self.currList) or pevId != '':
            cItem = dict(cItem)
            cItem.update({'title': _('More'), 'last_id': lastId})
            self.addMore(cItem)

    def fillItems(self, cItem, nextCategory1, nextCategory2):
        printDBG("DancetrippinTV.fillItems")

        self.cacheItems = []
        self.cacheFilters = []

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(data.meta['url'])

        hasVideos = False
        hasAudios = False
        hasFilters = False
        reTitleObj = re.compile('''<div[^>]+?genre[^>]+?>''')
        m1 = '"content"'
        m2 = '"content-grid"'
        if m1 not in data:
            m1 = m2

        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'genrelist'), ('<div', '>', 'content'), False)[1]
        tmp = self.cm.ph.getAllItemsBeetwenNodes(tmp, ('<a', '>'), ('</a', '>'), False)
        for item in tmp:
            item = self.cleanHtmlStr(item)
            if item == '':
                continue
            self.cacheFilters.append(item)

        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', m1), ('<div', '>', 'show-more'), False)[1]
        if tmp == '':
            tmp = data
        data = self.cm.ph.rgetAllItemsBeetwenNodes(tmp, ('</div', '>'), ('<div', '>', '"single'))
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0])
            if url == '':
                continue
            icon = self.cm.ph.getDataBeetwenMarkers(item, 'url(', ')', False)[1].strip()
            if len(icon) > 2 and icon[0] in ['"', "'"] and icon[-1] in ['"', "'"]:
                icon = self.getFullIconUrl(icon[1:-1])
            else:
                icon = self.getFullIconUrl(icon)

            filters = []
            tmp = self.cm.ph.getAllItemsBeetwenNodes(item, ('<a', '>', 'filter'), ('</a', '>'), False)
            for t in tmp:
                t = self.cleanHtmlStr(t)
                if t == '':
                    continue
                filters.append(t)

            if len(filters):
                hasFilters = True

            #title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''\stitle=['"]([^'^"]+?)['"]''')[0])
            #if title == '':
            item = reTitleObj.split(item)
            title = self.cleanHtmlStr(self.cleanHtmlStr(item[0]))

            if '/play/' in url:
                type = 'audio'
                hasAudios = True
            elif '/video' in url:
                type = 'video'
                hasVideos = True
            elif '/artists/' in url or '/parties/' in url or '/venues/' in url:
                type = cItem['type']
            else:
                printDBG('>>> unknown url tyle for url[%s]' % url)
                continue

            params = dict(cItem)
            params.update({'good_for_fav': True, 'type': type, 'url': url, 'title': title, 'icon': icon, 'filters': filters, 'desc': ' | '.join(filters)})
            self.cacheItems.append(params)

        if hasVideos and hasAudios:
            if not hasFilters or 0 == len(self.cacheFilters):
                self.listTypes(cItem, nextCategory2)
            else:
                self.listTypes(cItem, nextCategory1)
        elif hasFilters and len(self.cacheFilters):
            self.listFilters(cItem, nextCategory2)
        else:
            self.currList = self.cacheItems

    def listTypes(self, cItem, nextCategory):
        printDBG("DancetrippinTV.listTypes")
        tab = [{'title': _('All')}, {'title': _('Video'), 'f_type': 'video'}, {'title': _('Audio'), 'f_type': 'audio'}]
        cItem = dict(cItem)
        cItem.update({'category': nextCategory})
        self.listsTab(tab, cItem)

    def listFilters(self, cItem, nextCategory):
        printDBG("DancetrippinTV.listFilters")
        for item in self.cacheFilters:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'category': nextCategory, 'title': item})
            if ' all' not in item.lower():
                params['f_filter'] = item
            self.addDir(params)

    def listsItems(self, cItem):
        printDBG("DancetrippinTV.listsItems")
        fType = cItem.get('f_type', None)
        fFilter = cItem.get('f_filter', None)

        for item in self.cacheItems:
            if fType != None and item['type'] != fType:
                continue
            if fFilter != None and fFilter not in item['filters']:
                continue
            self.currList.append(item)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("DancetrippinTV.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('/search.cfm?q=') + urllib.quote_plus(searchPattern)
        self.fillItems(cItem, 'list_filters', 'list_items')

    def getLinksForVideo(self, cItem):
        printDBG("DancetrippinTV.getLinksForVideo [%s]" % cItem)
        urlTab = []

        if 'stream_type' in cItem:
            if 'video/mp4' == cItem['stream_type']:
                urlTab.append({'name': 'direct', 'url': cItem['url'], 'need_resolve': 0})
            elif 'application/x-mpegurl' == cItem['stream_type']:
                urlTab.extend(getDirectM3U8Playlist(cItem['url'], checkExt=False, checkContent=True, sortWithMaxBitrate=999999999))
            return urlTab

        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return urlTab

        tmp = self.cm.ph.getDataBeetwenMarkers(data, 'videoplayer', '</div>')[1]
        url = self.getFullUrl(self.cm.ph.getSearchGroups(tmp, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0]).replace('&amp;', '&')
        if 1 == self.up.checkHostSupport(url):
            return self.up.getVideoLinkExt(url)

        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<video', '</video>', False)[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<source', '>')
        if len(tmp):
            for item in tmp:
                type = self.cm.ph.getSearchGroups(item, '''type=['"]([^'^"]+?)['"]''')[0].lower()
                name = self.cm.ph.getSearchGroups(item, '''label=['"]([^'^"]+?)['"]''')[0]
                url = self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0]

                if 'video/mp4' == type:
                    urlTab.append({'name': name, 'url': self.getFullUrl(url), 'need_resolve': 0})
                elif 'application/x-mpegurl' == type:
                    urlTab.extend(getDirectM3U8Playlist(url, checkExt=False, checkContent=True, sortWithMaxBitrate=999999999))
        else:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0])
            sts, data = self.cm.getPage(url)
            if not sts:
                return urlTab
            hlsUrls = re.compile('''['"]((?:https?:)?//[^'^"]+?\.m3u8(?:\?[^'^"]+?)?)['"]''', re.IGNORECASE).findall(data)
            for url in hlsUrls:
                urlTab.extend(getDirectM3U8Playlist(self.getFullUrl(url), checkExt=False, checkContent=True, sortWithMaxBitrate=999999999))

        return urlTab

    def getVideoLinks(self, videoUrl):
        printDBG("DancetrippinTV.getVideoLinks [%s]" % videoUrl)
        urlTab = []

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
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})
        elif category == 'artists':
            self.listsTab(self.ARTISTS_CAT_TAB, self.currItem)
        elif category == 'channels':
            self.listsChannels(self.currItem, 'channel_menu')
        elif category == 'channel_menu':
            self.listChannel(self.currItem)
        elif category == 'fill_items':
            self.fillItems(self.currItem, 'list_filters', 'list_items')
        elif category == 'fill_items':
            self.listFilters(self.currItem, 'list_items')
        elif category == 'playlists24':
            self.listPlaylists24(self.currItem, 'playlist')
        elif category == 'playlist':
            self.listPlaylist(self.currItem)
        elif category == 'list_items':
            self.listsItems(self.currItem)
    #SEARCH
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category'})
            self.listSearchResult(cItem, searchPattern, searchType)
    #HISTORIA SEARCH
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, DancetrippinTV(), True, [])
