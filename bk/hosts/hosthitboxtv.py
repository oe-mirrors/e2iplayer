# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem, RetHost, CUrlItem
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetLogoDir, byteify
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
###################################################

###################################################
# FOREIGN import
###################################################
from Components.config import config, ConfigSelection
import urllib
try:
    import simplejson as json
except Exception:
    import json
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.hitbox_iconssize = ConfigSelection(default="medium", choices=[("large", _("large")), ("medium", _("medium")), ("small", _("small"))])


def GetConfigList():
    optionList = []
    return optionList
###################################################


def gettytul():
    return 'http://hitbox.tv/'


class Hitbox(CBaseHostClass):
    NUM_OF_ITEMS = 20
    STATIC_URL = 'http://edge.sf.hitbox.tv/'
    MAIN_URL = 'http://api.hitbox.tv/'
    MAIN_URLS = 'https://api.hitbox.tv/'

    MAIN_CAT_TAB = [{'category': 'games_list', 'title': _('Games played Now'), 'url': MAIN_URL + 'api/games?fast=true&limit={0}&media=true&offset={1}&size=list&liveonly=true'},
                    {'category': 'media', 'title': _('Live'), 'url': MAIN_URL + 'api/media/live/list?filter=popular&game=0&hiddenOnly=false&showHidden=true&fast=true&limit={0}&media=true&offset={1}&size=list&liveonly=true'},
                    {'category': 'media', 'title': _('Videos'), 'url': MAIN_URL + 'api/media/video/list?filter=weekly&follower_id=&game=0&fast=true&limit={0}&media=true&offset={1}&size=list'},
                    {'category': 'search', 'title': _('Search'), 'search_item': True},
                    {'category': 'search_history', 'title': _('Search history')}]

    GAME_CAT_TAB = [{'category': 'media', 'title': _('Live Channels'), 'url': 'live'},
                    {'category': 'media', 'title': _('Videos'), 'url': 'video'}]

    def __init__(self):
        printDBG("Hitbox.__init__")
        CBaseHostClass.__init__(self, {'history': 'Hitbox.tv'})

    def _getFullUrl(self, url, baseUrl=None):
        if None == baseUrl:
            baseUrl = Hitbox.MAIN_URL
        if 0 < len(url) and not url.startswith('http'):
            url = baseUrl + url
        return url

    def _getStr(self, v, default=''):
        if isinstance(v, str):
            return v
        elif isinstance(v, list):
            return '%r' % v
        else:
            return default

    def _getCategoryBaseParams(self, item):
        params = {}
        params['title'] = self._getStr(item.get("category_name"))
        if '' == params['title']:
            params['title'] = self._getStr(item.get("category_name_short"))
        params['icon'] = self._getFullUrl(self._getStr(item.get("category_logo_small")), Hitbox.STATIC_URL)
        if '' == params['icon']:
            params['icon'] = self._getFullUrl(self._getStr(item.get("category_logo_large")), Hitbox.STATIC_URL)
        params['desc'] = ''
        for tmp in [('category_viewers', _('viewers: ')), ('category_media_count', _('media count: ')), ('category_updated', _('updated: '))]:
            desc = self._getStr(item.get(tmp[0]))
            if '' != desc:
                params['desc'] += ('%s %s, ' % (tmp[1], desc))
        if '' != params['desc']:
            params['desc'] = params['desc'][:-2]
        return params

    def _getLiveStreamsBaseParams(self, item):
        params = {}
        params['title'] = '%s (%s)' % (self._getStr(item.get("media_display_name")), self._getStr(item.get("media_status")))
        params['icon'] = self._getFullUrl(self._getStr(item.get("media_thumbnail")), Hitbox.STATIC_URL)
        if '' == params['icon']:
            params['icon'] = self._getFullUrl(self._getStr(item.get("media_thumbnail_large")), Hitbox.STATIC_URL)
        if '' == params['icon']:
            params['icon'] = self._getFullUrl(self._getStr(item.get("user_logo_small")), Hitbox.STATIC_URL)
        if '' == params['icon']:
            params['icon'] = self._getFullUrl(self._getStr(item.get("user_logo")), Hitbox.STATIC_URL)
        if '' == params['icon']:
            params['icon'] = self._getFullUrl(self._getStr(item.get('channel', {}).get("user_logo_small")), Hitbox.STATIC_URL)
        if '' == params['icon']:
            params['icon'] = self._getFullUrl(self._getStr(item.get('channel', {}).get("user_logo")), Hitbox.STATIC_URL)
        params['desc'] = ''
        for tmp in [('media_views', _('views: ')), ('media_countries', _('countries: ')), ('media_live_since', _('live since: '))]:
            desc = self._getStr(item.get(tmp[0]))
            if '' != desc:
                params['desc'] += ('%s %s, ' % (tmp[1], desc))
        if '' != params['desc']:
            params['desc'] = params['desc'][:-2]
        return params

    def listGames(self, cItem, category):
        printDBG("Hitbox.listGames")
        page = cItem.get('page', 0)
        sts, data = self.cm.getPage(cItem['url'].format(Hitbox.NUM_OF_ITEMS, page * Hitbox.NUM_OF_ITEMS))
        if not sts:
            return
        try:
            data = byteify(json.loads(data))["categories"]
            for item in data:
                params = dict(cItem)
                params['url'] = item['category_id']
                params['category'] = category
                params.update(self._getCategoryBaseParams(item))
                #params['seo_key'] = item['category_seo_key']
                self.addDir(params)
            # check next page
            sts, data = self.cm.getPage(cItem['url'].format(1, (page + 1) * Hitbox.NUM_OF_ITEMS))
            if not sts:
                return
            if len(json.loads(data)["categories"]):
                params = dict(cItem)
                params.update({'title': _('Next page'), 'page': page + 1})
                self.addDir(params)
        except Exception:
            printExc()

    def listGamesTab(self, cItem, category=''):
        printDBG("Hitbox.listGamesTab")
        for item in Hitbox.GAME_CAT_TAB:
            params = dict(cItem)
            params['title'] = item['title']
            params['category'] = item['category']
            params['url'] = Hitbox.MAIN_URL + 'api/media/' + item['url'] + '/list?fast=true&filter=&media=true&size=list&game=' + cItem['url'] + '&limit={0}&offset={1}'
            self.addDir(params)

    def listMedia(self, cItem):
        printDBG("Hitbox.listMedia")
        page = cItem.get('page', 0)
        sts, data = self.cm.getPage(cItem['url'].format(Hitbox.NUM_OF_ITEMS, page * Hitbox.NUM_OF_ITEMS))
        if not sts:
            return
        try:
            data = byteify(json.loads(data))
            if 'live' == data['media_type']:
                key = 'livestream'
            elif 'video' == data['media_type']:
                key = 'video'
            else:
                printExc("Uknown type [%s]" % data['media_type'])
                return

            data = data[key]
            for item in data:
                params = dict(cItem)
                params.update(self._getLiveStreamsBaseParams(item))
                if key == 'video':
                    params['media_id'] = item['media_id']
                else:
                    params['channel_link'] = item['channel']['channel_link']
                self.addVideo(params)
            # check next page
            sts, data = self.cm.getPage(cItem['url'].format(1, (page + 1) * Hitbox.NUM_OF_ITEMS))
            if not sts:
                return
            if len(json.loads(data)[key]):
                params = dict(cItem)
                params.update({'title': _('Next page'), 'page': page + 1})
                self.addDir(params)
        except Exception:
            printExc()

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Hitbox.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        searchPattern = urllib.quote_plus(searchPattern)
        item = dict(cItem)
        item['category'] = 'media'
        item['url'] = Hitbox.MAIN_URLS + 'api/media/' + searchType + '/list?filter=popular&media=true&search=' + searchPattern + '&limit={0}&media=true&start={1}&size=list'
        if 'live' == searchType:
            item['url'] += '&liveonly=true'
        self.listMedia(item)

    def getLinksForVideo(self, cItem):
        printDBG("Hitbox.getLinksForVideo [%s]" % cItem)
        urls = []
        if 'channel_link' in cItem:
            live = True
            urls.append({'name': 'hls', 'type': 'hls', 'url': Hitbox.MAIN_URL + 'player/hls/%s.m3u8' % cItem['channel_link'].split('/')[-1]})
        elif 'media_id' in cItem:
            live = False
            sts, data = self.cm.getPage(Hitbox.MAIN_URL + 'api/player/config/video/%s?redis=true&embed=false&qos=false&redis=true&showHidden=true' % cItem['media_id'])
            if sts:
                try:
                    data = byteify(json.loads(data))
                    baseUrl = data['clip']['baseUrl']
                    if None == baseUrl:
                        baseUrl = ''
                    for item in data['clip']['bitrates']:
                        url = item['url']
                        if url.split('?')[0].endswith('m3u8'):
                            type = 'hls'
                        else:
                            type = 'vod'

                        if not url.startswith('http'):
                            if 'vod' == type:
                                url = baseUrl + '/' + url
                            else:
                                url = Hitbox.MAIN_URL + '/' + url

                        if url.startswith('http'):
                            urls.append({'name': item.get('label', 'vod'), 'type': type, 'url': url})
                            if 'vod' == type:
                                break
                except Exception:
                    printExc()

        urlTab = []
        for urlItem in urls:
            if 'hls' == urlItem['type']:
                url = urlItem['url']
                data = getDirectM3U8Playlist(url, checkExt=False)
                if 1 == len(data):
                    urlItem['url'] = urlparser.decorateUrl(urlItem['url'], {'iptv_proto': 'm3u8', 'iptv_livestream': live})
                    urlTab.append(urlItem)
                else:
                    for item in data:
                        item['url'] = urlparser.decorateUrl(item['url'], {'iptv_proto': 'm3u8', 'iptv_livestream': live})
                        urlTab.append(item)
            else:
                urlTab.append(urlItem)
        return urlTab

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('Hitbox.handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", None)
        category = self.currItem.get("category", '')
        printDBG("Hitbox.handleService: ---------> name[%s], category[%s] " % (name, category))
        searchPattern = self.currItem.get("search_pattern", searchPattern)
        self.currList = []

        if None == name:
            self.listsTab(Hitbox.MAIN_CAT_TAB, {'name': 'category'})
    #GAMES
        elif 'games_list' == category:
            self.listGames(self.currItem, 'games_tab')
        elif 'games_tab' == category:
            self.listGamesTab(self.currItem)
    #MEDIA
        elif 'media' == category:
            self.listMedia(self.currItem)
    #WYSZUKAJ
        elif category in ["search"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category'})
            self.listSearchResult(cItem, searchPattern, searchType)
    #HISTORIA WYSZUKIWANIA
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Hitbox(), True)

    def getLogoPath(self):
        return RetHost(RetHost.OK, value=[GetLogoDir('hitboxtvlogo.png')])

    def getLinksForVideo(self, Index=0, selItem=None):
        retCode = RetHost.ERROR
        retlist = []
        if not self.isValidIndex(Index):
            return RetHost(retCode, value=retlist)

        urlList = self.host.getLinksForVideo(self.host.currList[Index])
        for item in urlList:
            need_resolve = 0
            name = self.host._getStr(item["name"])
            url = item["url"]
            retlist.append(CUrlItem(name, url, need_resolve))

        return RetHost(RetHost.OK, value=retlist)
    # end getLinksForVideo

    def convertList(self, cList):
        hostList = []
        searchTypesOptions = [] # ustawione alfabetycznie
        searchTypesOptions.append((_("Live now"), "live"))
        searchTypesOptions.append((_("Recordings"), "video"))

        for cItem in cList:
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

            title = self.host._getStr(cItem.get('title', ''))
            description = self.host._getStr(cItem.get('desc', '')).strip()
            icon = self.host._getStr(cItem.get('icon', ''))

            hostItem = CDisplayListItem(name=title,
                                        description=description,
                                        type=type,
                                        urlItems=hostLinks,
                                        urlSeparateRequest=1,
                                        iconimage=icon,
                                        possibleTypesOfSearch=possibleTypesOfSearch)
            hostList.append(hostItem)

        return hostList
    # end convertList

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
