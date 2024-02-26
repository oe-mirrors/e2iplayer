# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem, RetHost, CUrlItem
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetLogoDir, GetCookieDir, byteify, CSelOneLink, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus, urllib_urlencode
###################################################
# FOREIGN import
###################################################
import datetime
import time
import re
try:
    import json
except Exception:
    import simplejson as json
from Components.config import config, ConfigSelection, ConfigYesNo, ConfigText, getConfigListEntry
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.laola1tv_defquality = ConfigSelection(default="1000000", choices=[("0", _("The worst")), ("500000", _("Low")), ("1000000", _("Mid")), ("1500000", _("High")), ("9000000", _("The best"))])
config.plugins.iptvplayer.laola1tv_onelink = ConfigYesNo(default=False)
config.plugins.iptvplayer.laola1tv_portal = ConfigSelection(default="int", choices=[("at", "AT"), ("de", "DE"), ("int", "INT")])
config.plugins.iptvplayer.laola1tv_language = ConfigSelection(default="en", choices=[("en", _("English")), ("de", _("Deutsch"))])
config.plugins.iptvplayer.laola1tv_myip1 = ConfigText(default="146.0.32.8", fixed_size=False)
config.plugins.iptvplayer.laola1tv_myip2 = ConfigText(default="85.128.142.29", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Video default quality:"), config.plugins.iptvplayer.laola1tv_defquality))
    optionList.append(getConfigListEntry(_("Use default quality:"), config.plugins.iptvplayer.laola1tv_onelink))
    optionList.append(getConfigListEntry(_("Portal:"), config.plugins.iptvplayer.laola1tv_portal))
    optionList.append(getConfigListEntry(_("Language:"), config.plugins.iptvplayer.laola1tv_language))
    optionList.append(getConfigListEntry(_("Alternative geolocation IP 1:"), config.plugins.iptvplayer.laola1tv_myip1))
    optionList.append(getConfigListEntry(_("Alternative geolocation IP 2:"), config.plugins.iptvplayer.laola1tv_myip2))
    return optionList
###################################################


def gettytul():
    return 'http://laola1.tv/'


class Laola1TV(CBaseHostClass):
    HTTP_HEADER = {'User-Agent': 'Mozilla/5.0 (iPad; U; CPU OS 3_2 like Mac OS X; en-us) AppleWebKit/531.21.10 (KHTML, like Gecko) Version/4.0.4 Mobile/7B334b Safari/531.21.10'}
    MAIN_URL = 'http://laola1.tv/'

    #'http://www.laola1.tv/img/laola1_logo.png'
    MAIN_CAT_TAB = [{'category': 'search', 'title': _('Search'), 'search_item': True},
                    {'category': 'search_history', 'title': _('Search history')}]

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'Laola1TV', 'cookie': 'Laola1TV.cookie'})
        self.mainCache = {}

    def _getFullUrl(self, url, baseUrl=None):
        if baseUrl == None:
            baseUrl = self.MAIN_URL
        if url.startswith('//'):
            url = 'http:' + url
        elif 0 < len(url) and not url.startswith('http'):
            if url.startswith('/'):
                url = url[1:]
            url = baseUrl + url

        if baseUrl.startswith('https://'):
            url = url.replace('https://', 'http://')
        return url

    def getPage(self, url, params={}, post_data=None):
        return self.cm.getPage(url, params, post_data)

    def getMainUrl(self):
        return (self.MAIN_URL + '{language}-{portal}/').format(language=config.plugins.iptvplayer.laola1tv_language.value, portal=config.plugins.iptvplayer.laola1tv_portal.value)

    def listsTab(self, tab, cItem, type=''):
        printDBG("Laola1TV.listsTab")
        for item in tab:
            params = dict(cItem)
            params.update(item)
            params['name'] = 'category'
            if type == '':
                type = item['category']
            if type == 'video':
                self.addVideo(params)
            else:
                self.addDir(params)

    def listFromCache(self, cItem, key=None):
        if 'cache_key' in cItem:
            key = cItem['cache_key']
        printDBG('Laola1TV.listFromCache key[%s]' % key)

        tab = self.mainCache.get(key, [])
        for item in tab:
            params = dict(cItem)
            params.update(item)
            self.addDir(params)

    def listMainMenu(self, cItem):
        printDBG('Laola1TV.listMainMenu')
        sts, data = self.getPage(self.getMainUrl() + 'home/')
        if not sts:
            return

        # live
        liveUrl = self.cm.ph.getSearchGroups(data, '<a href="([^"]+?)" class="live">')[0]
        liveTitle = self.cm.ph.getDataBeetwenMarkers(data, 'class="live">', '</a>', False)[1]
        params = dict(cItem)
        params.update({'category': 'calendar', 'title': self.cleanHtmlStr(liveTitle), 'url': self._getFullUrl(liveUrl)})
        self.addDir(params)

        data = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="level1">', '</div>', False)[1]
        data = data.split('<li class="active">')
        if len(data):
            del data[0]

        def _getLastItems(data, baseItem):
            retTab = []
            data = data.split('</a>')
            if len(data):
                del data[-1]
            for item in data:
                params = dict(baseItem)
                url = self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0]
                title = self.cleanHtmlStr(item)
                params.update({'url': self._getFullUrl(url), 'title': title})
                retTab.append(params)
            return retTab

        self.mainCache = {}
        self.mainCache['level_1'] = []
        for itemL1 in data:
            dataL2 = itemL1.split('<ul class="level2">')
            if 1 == len(dataL2):
                subItems = _getLastItems(itemL1, {'category': 'explore_page', 'level': '1'})
                self.mainCache['level_1'].extend(subItems)
            elif 1 < len(dataL2):
                titleL2 = self.cleanHtmlStr(dataL2[0])
                cacheKey2 = 'level_2_%s' % titleL2
                self.mainCache[cacheKey2] = []

                del dataL2[0]
                for itemL2 in dataL2:
                    if '<ul class="level3">' in itemL2:
                        dataL3 = itemL2.split('<span class="level2point">') #'<ul class="level3">')
                    else:
                        dataL3 = [itemL2]
                    if 1 == len(dataL3):
                        subItems = _getLastItems(itemL2, {'category': 'explore_page', 'level': '2'})
                        self.mainCache[cacheKey2].extend(subItems)
                        self.mainCache['level_1'].append({'title': titleL2, 'category': 'list_cache_cat', 'cache_key': cacheKey2, 'level': '2'})
                    elif 1 < len(dataL3):
                        for itemL3 in dataL3:
                            tmp = itemL3.split('<ul class="level3">')
                            if 2 != len(tmp):
                                continue
                            titleL3 = self.cleanHtmlStr(tmp[0])
                            cacheKey3 = 'level_3_%s_%s' % (titleL2, titleL3)
                            subItems = _getLastItems(tmp[1], {'category': 'explore_page', 'level': '3'})
                            self.mainCache[cacheKey2].append({'title': titleL3, 'category': 'list_cache_cat', 'cache_key': cacheKey3, 'level': '3'})
                            self.mainCache[cacheKey3] = subItems
                        self.mainCache['level_1'].append({'title': titleL2, 'category': 'list_cache_cat', 'cache_key': cacheKey2, 'level': '2'})

        self.listFromCache(cItem, 'level_1')

    def explorePage(self, cItem):
        printDBG("Laola1TV.explorePage")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        m1 = '<div class="teaser-title'
        data = self.cm.ph.getDataBeetwenMarkers(data, m1, '</section>', False)[1]
        data = data.split(m1)

        for item in data:
            tmp = item.split('<div class="teaser-list"')
            if 2 != len(tmp):
                continue
            url = self.cm.ph.getSearchGroups(tmp[0], 'href="([^"]+?)"')[0]
            icon = self.cm.ph.getSearchGroups(tmp[0], 'src="([^"]+?)"')[0]
            title = self.cm.ph.getDataBeetwenMarkers(tmp[0], '<h2>', '</h2>', False)[1]
            desc = self.cm.ph.getDataBeetwenMarkers(tmp[0], '<p>', '</p>', False)[1]
            if url != '':
                params = dict(cItem)
                params.update({'category': 'videos_list', 'url': self._getFullUrl(url), 'title': self.cleanHtmlStr(title), 'icon': self._getFullUrl(icon), 'desc': self.cleanHtmlStr(desc)})
                self.addDir(params)

    def listCalendary(self, cItem):
        printDBG("Laola1TV.listCalendary")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenReMarkers(data, re.compile('<ul class="list list-day day-[^"]+?" style="display:none;">'), re.compile('<ul class="list list-day day-[^"]+?" style="display:none;">'))[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li class="item list-sport', '</li>')
        for item in data:
            tmp = item.split('<div class="badge">')
            title = self.cleanHtmlStr(tmp[0])
            icon = self._getFullUrl(self.cm.ph.getSearchGroups(tmp[0], 'src="([^"]+?)"')[0])
            url = self._getFullUrl(self.cm.ph.getSearchGroups(tmp[0], 'href="([^"]+?)"')[0])
            desc = self.cleanHtmlStr(tmp[1])
            params = dict(cItem)
            params.update({'title': title, 'url': url, 'desc': desc, 'icon': icon})
            self.addVideo(params)

    def listVideos(self, cItem):
        printDBG("Laola1TV.listVideos")
        page = cItem.get('page', 1)
        url = cItem['url']
        if url.startswith('/'):
            url = url[1:]
        if page > 1:
            url += '/%s' % page

        sts, data = self.getPage(url)
        if not sts:
            return

        nextPage = self.cm.ph.getDataBeetwenMarkers(data, 'class="paging"', '<p>', False)[1]
        if ('/%s"' % (page + 1)) in nextPage:
            nextPage = True
        else:
            nextPage = False

        data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="teaser-list">', '</section>', False)[1]
        data = data.split('</a>')
        if len(data):
            del data[-1]
        for item in data:
            if '"ico-play"' not in item:
                continue
            url = self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0]
            icon = self.cm.ph.getSearchGroups(item, 'src="([^"]+?)"')[0]
            title = self.cm.ph.getDataBeetwenMarkers(item, '<p>', '</p>', False)[1]
            desc = item.split('</p>')[-1]
            if url != '':
                params = {'category': 'videos_list', 'url': self._getFullUrl(url), 'title': self.cleanHtmlStr(title), 'icon': self._getFullUrl(icon), 'desc': self.cleanHtmlStr(desc)}
                self.addVideo(params)

        if nextPage:
            params = dict(cItem)
            params.update({'title': _("Next page"), 'page': page + 1})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Laola1TV.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))

        # this looks strange but live attrib is returned for not live stream
        # for me this is server bug
        searchLive = '1'
        if searchType == 'live':
            searchLive = ''

        page = cItem.get('page', 1)
        url = 'http://search-api.laola1.at/?callback=ret&q=%s&p=%d&i=laola1tv-2015-int&include=[]&_=%s' % (urllib_quote_plus(searchPattern), page, str(time.time()))
        sts, data = self.getPage(url)
        if not sts:
            return
        try:
            data = data.strip()[4:-2]
            data = byteify(json.loads(data))['result']

            pagesize = int(self.cm.ph.getSearchGroups(data, 'pagesize="([0-9]+?)"')[0])
            total = int(self.cm.ph.getSearchGroups(data, 'total="([0-9]+?)"')[0])
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<result id=', '</result>')

            def _getText(data, name):
                return self.cm.ph.getDataBeetwenMarkers(data, '<%s>' % name, '</%s>' % name, False)[1]

            for item in data:
                def _getText(name):
                    return self.cm.ph.getDataBeetwenMarkers(item, '<%s>' % name, '</%s>' % name, False)[1]
                live = _getText('live')
                if searchLive != live:
                    continue
                title = self.cleanHtmlStr(_getText('title'))
                icon = self._getFullUrl(_getText('pic'))
                url = self._getFullUrl(_getText('url'))
                text = self.cleanHtmlStr(_getText('text'))
                rubric = self.cleanHtmlStr(_getText('rubric'))
                datetime = self.cleanHtmlStr(_getText('datetime'))

                desc = ' \n'.join([datetime, rubric, text])
                params = dict(cItem)
                params.update({'title': title, 'url': url, 'desc': desc, 'icon': icon})
                self.addVideo(params)

            if (page * pagesize) < total:
                params = dict(cItem)
                params.update({'title': _("Next page"), 'page': page + 1})
                self.addDir(params)
        except Exception:
            printExc()

    def getLinksForVideo(self, cItem):
        printDBG("Laola1TV.getLinksForVideo [%s]" % cItem)
        urlTab = []

        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return []
        baseUrl = self.cm.meta['url']

        data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="videoplayer"', '</script>')[1]
        printDBG(data)
        getParams = {}
        getParams['videoid'] = self.cm.ph.getSearchGroups(data, '\svideoid\s*:\s*"([0-9]*?)"')[0]
        getParams['partnerid'] = self.cm.ph.getSearchGroups(data, '\spartnerid\s*:\s*"([0-9]*?)"')[0]
        getParams['language'] = self.cm.ph.getSearchGroups(data, '\slanguage\s*:\s*"([a-z]*?)"')[0]
        getParams['portal'] = self.cm.ph.getSearchGroups(data, '\portalid\s*:\s*"([a-z]*?)"')[0]
        getParams['format'] = 'iphone'
        vidUrl = self.cm.ph.getSearchGroups(data, '\configUrl\s*:\s*"([^"]*?)"')[0]
        if vidUrl.startswith('//'):
            vidUrl = 'http:' + vidUrl
        vidUrl += '?' + urllib_urlencode(getParams)
        vidUrl = self._getFullUrl(vidUrl, baseUrl)

        sts, data = self.getPage(vidUrl)
        if not sts:
            return []

        try:
            data = byteify(json.loads(data))
            url = data['video']['streamAccess']
            req_abo = []
            for item in data['video']['abo']['required']:
                req_abo.append(str(item))
        except Exception:
            return []
            printExc()

        ######################################################
        streamaccessTab = []
        post_data = {}
        for idx in range(len(req_abo)):
            post_data[idx] = req_abo[idx]
        sts, data = self.getPage(url, {}, post_data)
        try:
            data = byteify(json.loads(data))
            for item in data['data']['stream-access']:
                streamaccessTab.append(item)
        except Exception:
            printExc()

        comment = ''
        for streamaccess in streamaccessTab:
            for myip in ['', config.plugins.iptvplayer.laola1tv_myip1.value, config.plugins.iptvplayer.laola1tv_myip2.value]:
                if '' != myip:
                    header = {'X-Forwarded-For': myip}
                else:
                    header = {}
                sts, data = self.getPage(streamaccess, {'header': header})
                if not sts:
                    return urlTab
                data = self.cm.ph.getDataBeetwenMarkers(data, '<data>', '</data>', False)[1]
                printDBG(data)
                comment = self.cm.ph.getSearchGroups(data, 'comment="([^"]+?)"')[0]
                auth = self.cm.ph.getSearchGroups(data, 'auth="([^"]+?)"')[0]
                if auth in ['restricted', 'blocked']:
                    continue
                url = self.cm.ph.getSearchGroups(data, 'url="([^"]+?)"')[0]
                url = url + '?hdnea=' + auth

                if myip != '':
                    url = strwithmeta(url, {'X-Forwarded-For': myip})

                COOKIE_FILE = GetCookieDir('m3u8_laola1.tv')
                rm(COOKIE_FILE)
                cookieParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIE_FILE}
                tmp = getDirectM3U8Playlist(url, checkExt=False, cookieParams=cookieParams, checkContent=True)
                if len(tmp):
                    urlMeta = {'iptv_proto': 'm3u8', 'Origin': self.up.getDomain(baseUrl, False), 'Cookie': self.cm.getCookieHeader(COOKIE_FILE), 'User-Agent': self.cm.HOST, 'Referer': baseUrl}
                for idx in range(len(tmp)):
                    tmp[idx]['need_resolve'] = 0
                    tmp[idx]['url'] = strwithmeta(tmp[idx]['url'], urlMeta)
                    urlTab.append(tmp[idx])
                break
            if 0 < len(urlTab):
                break

        if 0 < len(urlTab):
            max_bitrate = int(config.plugins.iptvplayer.laola1tv_defquality.value)

            def __getLinkQuality(itemLink):
                try:
                    value = itemLink['bitrate']
                    return int(value)
                except Exception:
                    printExc()
                    return 0
            urlTab = CSelOneLink(urlTab, __getLinkQuality, max_bitrate).getSortedLinks()
            if config.plugins.iptvplayer.laola1tv_onelink.value:
                urlTab = [urlTab[0]]
        else:
            SetIPTVPlayerLastHostError(comment)

        return urlTab

    def getVideoLinks(self, baseUrl):
        printDBG("Movie4kTO.getVideoLinks [%s]" % baseUrl)
        urlTab = []
        if '' != baseUrl:
            videoUrl = baseUrl
            urlTab = self.up.getVideoLinkExt(videoUrl)
        return urlTab

    def getFavouriteData(self, cItem):
        return cItem['url']

    def getLinksForFavourite(self, fav_data):
        return self.getLinksForVideo({'url': fav_data})

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listMainMenu({'name': 'category'})
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'}, 'dir')
        elif category == 'list_cache_cat':
            self.listFromCache(self.currItem)
        elif category == 'explore_page':
            self.explorePage(self.currItem)
        elif category == 'videos_list':
            self.listVideos(self.currItem)
        elif category == 'calendar':
            self.listCalendary(self.currItem)
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
        CHostBase.__init__(self, Laola1TV(), True, [CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO])

    def getLogoPath(self):
        return RetHost(RetHost.OK, value=[GetLogoDir('laola1tvlogo.png')])

    def getLinksForVideo(self, Index=0, selItem=None):
        retCode = RetHost.ERROR
        retlist = []
        if not self.isValidIndex(Index):
            return RetHost(retCode, value=retlist)

        urlList = self.host.getLinksForVideo(self.host.currList[Index])
        for item in urlList:
            retlist.append(CUrlItem(item["name"], item["url"], item["need_resolve"]))

        return RetHost(RetHost.OK, value=retlist)
    # end getLinksForVideo

    def getResolvedURL(self, url):
        # resolve url to get direct url to video file
        retlist = []
        urlList = self.host.getVideoLinks(url)
        for item in urlList:
            need_resolve = 0
            retlist.append(CUrlItem(item["name"], item["url"], need_resolve))

        return RetHost(RetHost.OK, value=retlist)

    def converItem(self, cItem):
        hostList = []
        searchTypesOptions = [] # ustawione alfabetycznie
        searchTypesOptions.append((_("Live-streams"), "live"))
        searchTypesOptions.append((_("Videos"), "videos"))

        hostLinks = []
        type = CDisplayListItem.TYPE_UNKNOWN
        possibleTypesOfSearch = None

        if 'category' == cItem['type']:
            if cItem.get('search_item', False):
                type = CDisplayListItem.TYPE_SEARCH
                possibleTypesOfSearch = searchTypesOptions
            else:
                type = CDisplayListItem.TYPE_CATEGORY
        elif cItem['type'] == 'video':
            type = CDisplayListItem.TYPE_VIDEO
        elif 'more' == cItem['type']:
            type = CDisplayListItem.TYPE_MORE
        elif 'audio' == cItem['type']:
            type = CDisplayListItem.TYPE_AUDIO

        if type in [CDisplayListItem.TYPE_AUDIO, CDisplayListItem.TYPE_VIDEO]:
            url = cItem.get('url', '')
            if '' != url:
                hostLinks.append(CUrlItem("Link", url, 1))

        title = cItem.get('title', '')
        description = cItem.get('desc', '')
        icon = cItem.get('icon', '')

        return CDisplayListItem(name=title,
                                    description=description,
                                    type=type,
                                    urlItems=hostLinks,
                                    urlSeparateRequest=1,
                                    iconimage=icon,
                                    possibleTypesOfSearch=possibleTypesOfSearch)
    # end converItem

    def getSearchItemInx(self):
        try:
            list = self.host.getCurrList()
            for i in range(len(list)):
                if list[i]['category'] == 'search':
                    return i
        except Exception:
            printDBG('getSearchItemInx EXCEPTION')
            return -1

    def setSearchPattern(self):
        try:
            list = self.host.getCurrList()
            if 'history' == list[self.currIndex]['name']:
                pattern = list[self.currIndex]['title']
                search_type = list[self.currIndex]['search_type']
                self.host.history.addHistoryItem(pattern, search_type)
                self.searchPattern = pattern
                self.searchType = search_type
        except Exception:
            printDBG('setSearchPattern EXCEPTION')
            self.searchPattern = ''
            self.searchType = ''
        return
