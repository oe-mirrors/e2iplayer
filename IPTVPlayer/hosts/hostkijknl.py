# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, PrevDay, CSelOneLink, byteify
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib
import datetime
try:
    import json
except Exception:
    import simplejson as json
###################################################


def gettytul():
    return 'http://kijk.nl/'


class KijkNL(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'kijk.nl.uk', 'cookie': 'kijk.nl.cookie'})
        self.DEFAULT_ICON_URL = 'http://is2.mzstatic.com/image/thumb/Purple128/v4/81/1d/19/811d19eb-3de6-1456-ab00-f68204e7dae4/source/1200x630bb.jpg'
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.MAIN_URL = 'http://www.kijk.nl/'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Encoding': 'gzip, deflate'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding': 'gzip, deflate', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json, text/javascript, */*; q=0.01'})

        self.cacheLinks = {}
        self.cacheFilters = {}
        self.cacheFiltersKeys = []
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.tmpUrl = 'http://api.kijk.nl/'
        self.policyKeyCache = ''

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def listMainMenu(self, cItem):
        printDBG("KijkNL.listMainMenu")
        self.MAIN_CAT_TAB = [
                             {'category': 'list_home', 'title': 'Home', 'url': ''},
                             {'category': 'list_missed', 'title': 'Gemist', 'url': ''},
                             {'category': 'list_popular', 'title': 'Populair', 'url': self.tmpUrl + 'v2/templates/page/popular'},
                             {'category': 'list_letters', 'title': 'A-Z', 'url': ''},
                             {'category': 'list_themas', 'title': "THEMA'S", 'url': self.getMainUrl()},
                             {'category': 'search', 'title': _('Search'), 'search_item': True},
                             {'category': 'search_history', 'title': _('Search history')},
                            ]
        self.HOME_CAT_TAB = [
                                {'category': 'list_items', 'title': _("Episodes"), 'url': self.tmpUrl + 'v1/default/sections/home_Episodes-popular'},
                                {'category': 'list_items', 'title': _("Clips"), 'url': self.tmpUrl + 'v1/default/sections/home_Clips-popular'},
                                {'category': 'list_items', 'title': _("Missed"), 'url': self.tmpUrl + 'v1/default/sections/home_HomeMissed'},
                                {'category': 'list_items', 'title': _("Series"), 'url': self.tmpUrl + 'v1/default/sections/home_Series-popularPrograms'},
                               ]
        self.POPULAR_CAT_TAB = [
                                {'category': 'list_items', 'title': "Populaire afleveringen", 'url': self.tmpUrl + 'v2/default/sections/popular_PopularVODs'},
                                {'category': 'list_items', 'title': "Populaire programma's", 'url': self.tmpUrl + 'v2/default/sections/popular_PopularFormats'},
                                {'category': 'list_items', 'title': "Populaire clips", 'url': self.tmpUrl + 'v2/default/sections/popular_PopularClips'},
                               ]
        self.listsTab(self.MAIN_CAT_TAB, cItem)

    def listHome(self, cItem):
        printDBG("KijkNL.listHome")
        params = dict(cItem)
        params['good_for_fav'] = True
        self.listsTab(self.HOME_CAT_TAB, cItem)

    def listMissed(self, cItem, nextCategory):
        printDBG("KijkNL.listMissed")
        dt = cItem.get('f_date', None)
        ITEMS_PER_PAGE = 15
        if dt == None:
            dt = datetime.date.today()
        else:
            try:
                dt = datetime.datetime.strptime(dt, '%Y-%m-%d').date()
            except Exception:
                printExc()
                return
        dtIt = dt
        for m in range(ITEMS_PER_PAGE):
            url = self.tmpUrl + 'v1/default/sections/missed-all-' + dtIt.strftime("%Y%m%d")
            params = {'good_for_fav': False, 'category': nextCategory, 'title': dtIt.strftime("%d-%m-%Y"), 'url': url}
            self.addDir(params)
            dtIt = PrevDay(dtIt)

        params = dict(cItem)
        params.update({'good_for_fav': False, 'title': _('Next page'), 'f_date': dtIt.strftime('%Y-%m-%d')})
        self.addDir(params)

    def listPopular(self, cItem):
        printDBG("KijkNL.listPopular")
        params = dict(cItem)
        params['good_for_fav'] = True
        self.listsTab(self.POPULAR_CAT_TAB, cItem)

    def listLetters(self, cItem, nextCategory):
        printDBG("KijkNL.listLetters [%s]" % cItem)
        catList = [{'title': '0 T/M 9', 'url': '0123456789'},
                  {'title': 'ABCD', },
                  {'title': 'EFGH', },
                  {'title': 'IJKL', },
                  {'title': 'MNOP', },
                  {'title': 'QRST', },
                  {'title': 'UVW', },
                  {'title': 'XYZ', }]

        for item in catList:
            url = item.get('url', '')
            if url == '':
                url = item['title'].lower()
            url = self.tmpUrl + 'v1/default/sections/programs-abc-' + url
            params = {'good_for_fav': True, 'category': nextCategory, 'title': item['title'], 'url': url}
            self.addDir(params)

    def listThemas(self, cItem, nextCategory):
        printDBG("KijkNL.listThemas [%s]" % cItem)

        urlparams = dict(self.defaultParams)
        urlparams['header'] = dict(urlparams['header'])
        urlparams['cookie_items'] = {'OPTOUTMULTI': '0:0%7Cc5:0%7Cc1:0%7Cc4:0%7Cc3:0%7Cc2:0'} #{'OPTOUTMULTI':'0:0|c5:0|c1:0|c4:0|c3:0|c2:0'}
        urlparams['header']['Referer'] = 'http://consent.kijk.nl/?url=' + urllib.quote('http://www.kijk.nl/')

        sts, data = self.getPage(cItem['url'], urlparams)
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenMarkers(data, '>Thema', '</ul>')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>', withMarkers=True)
        for item in data:
            url = self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0].split('/')[-1]
            if url == '':
                continue
            url = self.tmpUrl + 'v2/templates/page/theme/' + url
            title = self.cleanHtmlStr(item)
            params = {'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url}
            self.addDir(params)

    def listComponents(self, cItem, nextCategory):
        printDBG("KijkNL.listComponents [%s]" % cItem)

        def _doHasItems(url):
            try:
                sts, data = self.getPage(url + '?limit=1&offset=0')
                return json.loads(data)['totalItemsAvailable'] > 0
            except Exception:
                printExc()
            return False

        type = cItem.get('f_type', '')
        try:
            sts, data = self.getPage(cItem['url'])
            if not sts:
                return
            data = byteify(json.loads(data), '', True)
            for item in data['components']:
                if item['type'] == 'video_list':
                    id = item['id']
                    item = item['data']
                    url = item['url']
                    if not self.cm.isValidUrl(url):
                        continue
                    if type == 'series' and item['more']['parameters']['type'] != 'episodes' and not _doHasItems(url):
                        continue
                    title = self.cleanHtmlStr(item['title'])
                    params = {'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'f_id': id}
                    self.addDir(params)
        except Exception:
            printExc()

    def listItems(self, cItem, nextCategory):
        ITEMS = 12
        page = cItem.get('page', 0)
        try:
            url = cItem['url']
            if '?' in url:
                url += '&'
            else:
                url += '?'

            url += 'limit=%s&offset=%s' % (ITEMS, ITEMS * page)

            sts, data = self.getPage(url)
            if not sts:
                return

            data = byteify(json.loads(data))

            if isinstance(data, list):
                items = data
            else:
                items = data['items']

            for item in items:
                if item['type'] in ['clip', 'episode', 'series']: #and item['available']
                    icon = item['images'].get('nonretina_image', '')
                    if icon == '':
                        icon = item['images'].get('retina_image', '')
                    title = self.cleanHtmlStr(item['title'])
                    id = item['id']
                    url = item['_links']['self']
                    descTab = []
                    if 'duration' in item:
                        descTab.append(item['duration'])
                    sTtile = self.cleanHtmlStr(item.get('seriesTitle', ''))
                    if sTtile != '':
                        if item['type'] == 'episode':
                            title = '%s - %s' % (sTtile, title)
                        else:
                            descTab.append(sTtile)

                    descTab.append(item.get('dateStringNoTime', item.get('dateString', '')))
                    if 'channel' in item:
                        descTab.append(item['channel'])
                    if 'genres' in item:
                        descTab.append(', '.join(item['genres']))
                    if 'nicam' in item:
                        descTab.append(', '.join(item['nicam']))

                    desc = self.cleanHtmlStr(' | '.join(descTab)) + '[/br]' + self.cleanHtmlStr(item.get('synopsis', ''))
                    params = {'good_for_fav': True, 'title': title, 'url': url, 'icon': icon, 'desc': desc, 'f_type': item['type'], 'f_id': id}
                    if item['type'] in ['clip', 'episode']:
                        self.addVideo(params)
                    else:
                        params['category'] = nextCategory
                        params['url'] = self.tmpUrl + 'v2/templates/page/format/' + id
                        self.addDir(params)
                else:
                    printDBG('+++++++++++++++++NOT PLAYABLE ITEM++++++++++++++++++')
                    printDBG(item)
                    printDBG('++++++++++++++++++++++++++++++++++++++++++++++++++++')
            if data.get('hasMoreItems', False):
                params = dict(cItem)
                params.update({'good_for_fav': False, 'title': _('Next page'), 'page': page + 1})
                self.addDir(params)
        except Exception:
            printExc()

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("KijkNL.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.tmpUrl + ('v1/default/searchresultsgrouped?search=%s' % urllib.quote(searchPattern))
        self.listItems(cItem, 'list_components')

    def getLinksForVideo(self, cItem):
        printDBG("KijkNL.getLinksForVideo [%s]" % cItem)

        retTab = []
        videoUrl = ''
        embedVideoUrl = ''
        try:
            url = self.tmpUrl + 'v1/default/entitlement/' + cItem['f_id']

            sts, data = self.getPage(url)
            if not sts:
                return

            data = byteify(json.loads(data), '', True)
            if data['playerInfo']['hasDRM']:
                SetIPTVPlayerLastHostError(_('DRM protection detected.'))
            embedVideoUrl = self.getFullUrl(data['playerInfo'].get('embed_video_url', ''))
            url = data['playerInfo']['embed_api_url']
            if self.cm.isValidUrl(url):
                sts, data = self.getPage(url)
                if not sts:
                    return
                data = byteify(json.loads(data), '', True)
                videoUrl = data['playlist']
                retTab = getDirectM3U8Playlist(videoUrl, checkContent=True)
            else:
                SetIPTVPlayerLastHostError(_('No valid entitlement found for asset.'))
        except Exception:
            SetIPTVPlayerLastHostError(_('Entitlement parsing error.'))
            printExc()

        printDBG(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> embedVideoUrl[%s]" % embedVideoUrl)
        if self.cm.isValidUrl(embedVideoUrl) and 0 == len(retTab):
            sts, data = self.getPage(embedVideoUrl)
            try:
                vidData = self.cm.ph.getDataBeetwenMarkers(data, '<video', '>')[1]
                account = self.cm.ph.getSearchGroups(vidData, '''data\-account=['"]([^'^"]+?)['"]''')[0]
                video = self.cm.ph.getSearchGroups(vidData, '''data\-video\-id=['"]([^'^"]+?)['"]''')[0]

                if self.policyKeyCache == '':
                    data = re.compile('''<script[^>]+?src=['"]([^'^"]+?)['"]''').findall(data)
                    for item in data:
                        url = self.getFullUrl(item)
                        if not self.cm.isValidUrl(url):
                            continue
                        sts, script = self.getPage(url)
                        if sts:
                            self.policyKeyCache = self.cm.ph.getSearchGroups(script, '''policyKey\s*:\s*['"]([^'^"]+?)['"]''')[0]
                        if self.policyKeyCache != '':
                            break

                urlParams = dict(self.defaultParams)
                urlParams['header'] = dict(urlParams['header'])
                urlParams['header']['Accept'] = "application/json;pk=" + self.policyKeyCache
                url = 'https://edge.api.brightcove.com/playback/v1/accounts/%s/videos/%s' % (account, video)
                sts, data = self.getPage(url, urlParams)
                if not sts:
                    return
                data = byteify(json.loads(data), '', True)
                for item in data['sources']:
                    videoUrl = item.get('src', '')
                    if not self.cm.isValidUrl(videoUrl):
                        continue
                    retTab = getDirectM3U8Playlist(videoUrl, checkContent=True)
                    if len(retTab):
                        break
            except Exception:
                SetIPTVPlayerLastHostError(_('Player data parsing error.'))
                printExc()

        def __getLinkQuality(itemLink):
            try:
                return int(itemLink['bitrate'])
            except Exception:
                return 0

        retTab = CSelOneLink(retTab, __getLinkQuality, 99999999).getSortedLinks()

        return retTab

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        self.informAboutGeoBlockingIfNeeded('NL')

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

        cItem = self.currItem

    #MAIN MENU
        if name == None:
            self.listMainMenu({'name': 'category'})
        elif category == 'list_home':
            self.listHome(cItem)
        elif category == 'list_missed':
            self.listMissed(cItem, 'list_items')
        elif category == 'list_themas':
            self.listThemas(cItem, 'list_components')
        elif category == 'list_popular':
            self.listPopular(cItem)
        elif category == 'list_components':
            self.listComponents(cItem, 'list_items')
            if 1 == len(self.currList):
                cItem = self.currList.pop()
                category = cItem['category']
        if category == 'list_items':
            self.listItems(cItem, 'list_components')
        elif category == 'list_letters':
            self.listLetters(cItem, 'list_items')
    #SEARCH
        elif category in ["search", "search_next_page"]:
            cItem = dict(cItem)
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
        CHostBase.__init__(self, KijkNL(), True, [])
