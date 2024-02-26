# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify, CSelOneLink
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
###################################################
# FOREIGN import
###################################################
import time
import random
try:
    import json
except Exception:
    import simplejson as json
from Components.config import config, ConfigSelection, ConfigYesNo, getConfigListEntry
###################################################


###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.onetvodDefaultformat = ConfigSelection(default="9999", choices=[("0", "bitrate: najgorszy"), ("200", "bitrate: 200p"), ("450", "bitrate: 450p"), ("900", "bitrate: 900"), ("1800", "bitrate: 1800"), ("9999", "bitrate: najlepszy")])
config.plugins.iptvplayer.onetvodUseDF = ConfigYesNo(default=True)
config.plugins.iptvplayer.proxyOnet = ConfigYesNo(default=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry("Domyślny format video:", config.plugins.iptvplayer.onetvodDefaultformat))
    optionList.append(getConfigListEntry("Używaj domyślnego format video:", config.plugins.iptvplayer.onetvodUseDF))
    optionList.append(getConfigListEntry("Korzystaj z proxy?", config.plugins.iptvplayer.proxyOnet))
    return optionList
###################################################


def gettytul():
    return 'https://vod.pl/'


class VODPL(CBaseHostClass):

    def __init__(self):
        proxyUrl = config.plugins.iptvplayer.proxyurl.value
        useProxy = config.plugins.iptvplayer.proxyOnet.value

        CBaseHostClass.__init__(self, {'proxyURL': proxyUrl, 'useProxy': useProxy, 'history': 'vod.pl', 'cookie': 'vod.pl.cookie'})
        self.DEFAULT_ICON_URL = 'https://ocdn.eu/static/ucs/ZTc7MDA_/3981e069a1f7f560017885aaad40ea1a/assets/img/logo.png'
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})
        self.MAIN_URL = 'https://vod.pl/'
        self.cacheFilters = {}
        self.cacheFiltersKeys = []
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.MAIN_CAT_TAB = [{'category': 'list_filters', 'title': _('Movies'), 'url': self.getFullUrl('filmy'), 'f_element': 'SiteFilmy', },
                             {'category': 'list_items', 'title': _('Series'), 'url': self.getFullUrl('seriale'), 'f_element': 'SiteSeriale', },
                             {'category': 'list_filters', 'title': 'Programy onetu', 'url': self.getFullUrl('programy-onetu'), 'f_element': 'SiteProgramyOnetu', },
                             {'category': 'list_filters', 'title': 'Dokumentalne', 'url': self.getFullUrl('filmy-dokumentalne'), 'f_element': 'SiteDokumenty', },


                             {'category': 'search', 'title': _('Search'), 'search_item': True, },
                             {'category': 'search_history', 'title': _('Search history'), }
                            ]

    def getFullIconUrl(self, url):
        url = url.replace('&amp;', '&')
        return CBaseHostClass.getFullIconUrl(self, url)

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)

        sts, data = self.cm.getPage(baseUrl, addParams, post_data)
        return sts, data

    def fillCacheFilters(self, cItem):
        printDBG("VODPL.listCategories")
        self.cacheFilters = {}
        self.cacheFiltersKeys = []

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        def addFilter(data, marker, baseKey, allTitle='', titleBase=''):
            key = 'f_' + baseKey
            self.cacheFilters[key] = []
            for item in data:
                value = self.cm.ph.getSearchGroups(item, marker + '''="([^"]+?)"''')[0]
                if value == '':
                    continue
                title = self.cleanHtmlStr(item)
                self.cacheFilters[key].append({'title': title.title(), key: value})

            if len(self.cacheFilters[key]):
                if allTitle != '':
                    self.cacheFilters[key].insert(0, {'title': allTitle})
                self.cacheFiltersKeys.append(key)

        # genres
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<select name="genres"', '</select>')[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<option ', '</option>')
        if len(tmp):
            addFilter(tmp, 'value', 'genres')

        # country
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<select name="country"', '</select>')[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<option ', '</option>')
        if len(tmp):
            addFilter(tmp, 'value', 'country')

        # sort
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<select name="sort"', '</select>')[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<option ', '</option>')
        if len(tmp):
            addFilter(tmp, 'value', 'sort')

        printDBG(self.cacheFilters)

    def listFilters(self, cItem, nextCategory):
        printDBG("VODPL.listFilters")
        cItem = dict(cItem)

        f_idx = cItem.get('f_idx', 0)
        if f_idx == 0:
            self.fillCacheFilters(cItem)

        if 0 == len(self.cacheFiltersKeys):
            return

        filter = self.cacheFiltersKeys[f_idx]
        f_idx += 1
        cItem['f_idx'] = f_idx
        if f_idx == len(self.cacheFiltersKeys):
            cItem['category'] = nextCategory
        self.listsTab(self.cacheFilters.get(filter, []), cItem)

    def listItems(self, cItem, nextCategory):
        printDBG("VODPL.listItems")

        if 'url' in cItem:
            sts, data = self.getPage(cItem['url'])
            if not sts:
                return
            mainDesc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<p class="hyphenate"', '</p>')[1])
        else:
            mainDesc = ''

        page = cItem.get('page', 0)
        elementId = cItem.get('f_element', '')
        filters = {}
        filters['payment'] = cItem.get('f_payment', 'free')
        if 'f_country' in cItem:
            val = cItem.get('f_country', '0')
            key = 'country'
            if val == 'npl':
                key = '~country'
                val = 'polska'
            elif val == 'pl':
                val = 'polska'
            filters[key] = val
        if 'f_channel' in cItem:
            filters['channel'] = cItem['f_channel']

        reqParams = {elementId: {'elementId': elementId, 'site': page}}
        if 'f_genres' in cItem:
            reqParams[elementId]['genres'] = urllib_quote(cItem.get('f_genres', ''))
        if 'f_query' in cItem:
            reqParams[elementId]['query'] = urllib_quote(cItem.get('f_query', ''))
        if 'f_sort' in cItem:
            reqParams[elementId]['sort'] = {cItem['f_sort']: 'desc'}
        if 'f_series' in cItem:
            reqParams[elementId]['series'] = cItem['f_series']
        if 'f_season' in cItem:
            reqParams[elementId]['season'] = cItem['f_season']
        if 'f_limit' in cItem:
            reqParams[elementId]['limit'] = cItem['f_limit']

        reqParams[elementId]['filters'] = filters

        baseUrl = '/_a/list.html?deviceConfig=%s&lists=' % urllib_quote('{"ckmdevice":"mobile","ckmformat":["mp4"],"geo":"pl"}')
        url = self.getFullUrl(baseUrl + urllib_quote(json.dumps(reqParams).decode('utf-8')))

        sts, data = self.getPage(url)
        if not sts:
            return

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            if not self.cm.isValidUrl(url):
                continue

            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''data-original=['"]([^"^']+?)['"]''')[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''alt=['"]([^"^']+?)['"]''')[0])
            episodeTitle = ''

            # desc start
            descTab = []
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(item, '<span class="v_', '</span>')
            for t in tmp:
                tt = self.cleanHtmlStr(t)
                if tt == '':
                    continue
                if 'v_itemTitle' in t:
                    title = tt
                    continue
                if tt.startswith('odc.') or tt.startswith('sez.'):
                    episodeTitle = tt
                descTab.append(tt)
            ######
            if episodeTitle != '':
                title += ', ' + episodeTitle

            params = dict(cItem)
            params = {'good_for_fav': True, 'title': title, 'url': url, 'desc': ' | '.join(descTab) + '[/br]' + mainDesc, 'icon': icon, 'episode_title': episodeTitle}
            params['category'] = nextCategory
            self.addDir(params)

        if len(self.currList) > 0:
            reqParams[elementId]['site'] = page + 1
            url = self.getFullUrl(baseUrl + urllib_quote(json.dumps(reqParams).decode('utf-8')))
            sts, data = self.getPage(url)
            if not sts:
                return
            if 'v_itemTitle' in data:
                params = dict(cItem)
                params.update({'title': _("Next page"), 'page': page + 1})
                self.addDir(params)

    def exploreItem(self, cItem, nextCategory):
        printDBG("VODPL.exploreItem")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<p class="hyphenate"', '</p>')[1])
        tmpDesc = cItem.get('desc', '') + '[/br]' + desc
        if 'serialDetail' in data:
            seriesId = self.cm.ph.getSearchGroups(data, '''\s*['"]?series['"]?\s*:\s*['"]([^'^"]+?)['"]''')[0]
            data = self.cm.ph.getDataBeetwenMarkers(data, 'v_seasonListContainer', '</ul>')[1]
            seasonTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<p', '</p>')[1])
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
            if len(data) and seasonTitle != '':
                for item in data:
                    sNum = self.cm.ph.getSearchGroups(item, '''data\-id=['"]([0-9]+?)['"]''')[0]
                    if sNum == '':
                        continue
                    title = self.cleanHtmlStr(item)
                    params = dict(cItem)
                    params.update({'good_for_fav': False, 'category': nextCategory, 'title': '%s %s' % (seasonTitle, title), 'f_series': seriesId, 'f_season': sNum, 'f_element': 'v_seasonEpisodes', 'desc': tmpDesc})
                    self.addDir(params)
            else:
                cItem = dict(cItem)
                cItem.update({'category': nextCategory, 'f_series': seriesId, 'f_element': 'v_seasonEpisodes', 'desc': tmpDesc})
                self.listItems(cItem, 'explore_item')
        else:
            tmp = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="v_videoAttributes"', '</ul>')[1]
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li', '</li>')
            tmpDesc = []
            for t in tmp:
                t = self.cleanHtmlStr(t)
                if t != '':
                    tmpDesc.append(t)
            tmpDesc = ' | '.join(tmpDesc)
            desc = tmpDesc + '[/br]' + desc

            episodeTitle = cItem.get('episode_title', '')
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div class="v_videoTitle">', '</div>')[1].split('</span>')[0])
            if episodeTitle != '':
                title += ', ' + episodeTitle

            params = dict(cItem)
            params.update({'title': title, 'desc': desc})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("VODPL.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)

        if searchType == 'wszystkie':
            searchType = "0"

        cItem.update({'f_element': 'SearchResults', 'f_limit': 48, 'f_sort': 'score', 'f_channel': searchType, 'f_query': searchPattern})
        self.listItems(cItem, 'explore_item')

    def _getVideoTab(self, ckmId):
        printDBG("VODPL.getVideoTab_ETV ckmId[%r]" % ckmId)
        tm = str(int(time.time() * 1000))
        jQ = str(random.randrange(562674473039806, 962674473039806))
        authKey = 'FDF9406DE81BE0B573142F380CFA6043'
        contentUrl = 'http://qi.ckm.onetapi.pl/?callback=jQuery183040' + jQ + '_' + tm + '&body%5Bid%5D=' + authKey + '&body%5Bjsonrpc%5D=2.0&body%5Bmethod%5D=get_asset_detail&body%5Bparams%5D%5BID_Publikacji%5D=' + ckmId + '&body%5Bparams%5D%5BService%5D=ekstraklasa.onet.pl&content-type=application%2Fjsonp&x-onet-app=player.front.onetapi.pl&_=' + tm
        sts, data = self.cm.getPage(contentUrl)
        valTab = []
        if sts:
            try:
                result = byteify(json.loads(data[data.find("(") + 1:-2]))
                strTab = []
                valTab = []
                for items in result['result']['0']['formats']['wideo']:
                    for i in range(len(result['result']['0']['formats']['wideo'][items])):
                        strTab.append(items)
                        strTab.append(result['result']['0']['formats']['wideo'][items][i]['url'])
                        if result['result']['0']['formats']['wideo'][items][i]['video_bitrate']:
                            strTab.append(int(float(result['result']['0']['formats']['wideo'][items][i]['video_bitrate'])))
                        else:
                            strTab.append(0)
                        valTab.append(strTab)
                        strTab = []
            except Exception:
                printExc()
        return valTab

    def getLinksForVideo(self, cItem):
        printDBG("VODPL.getLinksForVideo [%s]" % cItem)
        url = cItem['url']
        videoUrls = []
        tmpTab = []
        tries = 0
        while tries < 2:
            tries += 1
            sts, data = self.cm.getPage(url)
            if not sts:
                return videoUrls
            ckmId = self.cm.ph.getSearchGroups(data, 'data-params-mvp="([^"]+?)"')[0]
            if '' == ckmId:
                ckmId = self.cm.ph.getSearchGroups(data, 'id="mvp:([^"]+?)"')[0]
            if '' != ckmId:
                tmpTab = self._getVideoTab(ckmId)
                break
            data = self.cm.ph.getDataBeetwenMarkers(data, 'pulsembed_embed', '</div>')[1]
            url = self.cm.ph.getSearchGroups(data, 'href="([^"]+?)"')[0]

        tab = []
        for item in tmpTab:
            if item[0] == 'mp4':
                tab.append(item)

        def __getLinkQuality(itemLink):
            try:
                return int(itemLink[2])
            except Exception:
                return 0

        maxRes = int(config.plugins.iptvplayer.onetvodDefaultformat.value) * 1.1
        tab = CSelOneLink(tab, __getLinkQuality, maxRes).getSortedLinks()
        if config.plugins.iptvplayer.onetvodUseDF.value and len(tab) > 0:
            tab = [tab[0]]

        for item in tab:
            name = "type: %s \t bitrate: %s" % (item[0], item[2])
            url = item[1]
            videoUrls.append({'name': name, 'url': url, 'need_resolve': 0})

        return videoUrls

    def getFavouriteData(self, cItem):
        printDBG('VODPL.getFavouriteData')
        return json.dumps(cItem)

    def getLinksForFavourite(self, fav_data):
        printDBG('VODPL.getLinksForFavourite')
        if self.MAIN_URL == None:
            self.selectDomain()
        links = []
        try:
            cItem = byteify(json.loads(fav_data))
            links = self.getLinksForVideo(cItem)
        except Exception:
            printExc()
        return links

    def setInitListFromFavouriteItem(self, fav_data):
        printDBG('VODPL.setInitListFromFavouriteItem')
        if self.MAIN_URL == None:
            self.selectDomain()
        try:
            params = byteify(json.loads(fav_data))
        except Exception:
            params = {}
            printExc()
        self.addDir(params)
        return True

    def getArticleContent(self, cItem):
        printDBG("VODPL.getArticleContent [%s]" % cItem)
        retTab = []

        otherInfo = {}

        url = cItem.get('url', '')

        sts, data = self.getPage(url)
        if not sts:
            return retTab

        data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="row" id="content-tab">', '<div id="zone')[1]

        title = '' #self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div class="f_t_b">', '</div>')[1])
        icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(data, '''<img[^>]+?src=['"]([^"^']+?\.jpe?g[^"^']*?)["']''')[0])
        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<p>', '</p>', False)[1])

        for item in [('Rendező(k):', 'directors'),
                     ('Színészek:', 'actors'),
                     ('Kategoria:', 'genre')]:
            tmpTab = []
            tmp = self.cm.ph.getDataBeetwenMarkers(data, item[0], '</li>', False)[1].split('<br>')
            for t in tmp:
                t = self.cleanHtmlStr(t).replace(' , ', ', ')
                if t != '':
                    tmpTab.append(t)
            if len(tmpTab):
                otherInfo[item[1]] = ', '.join(tmpTab)

        for item in [('Játékidő:', 'duration'),
                     ('IMDB Pont:', 'imdb_rating'),
                     ('Nézettség:', 'views')]:
            tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, item[0], '</li>', False)[1])
            if tmp != '':
                otherInfo[item[1]] = tmp

        if title == '':
            title = cItem['title']
        if desc == '':
            desc = cItem.get('desc', '')
        if icon == '':
            icon = cItem.get('icon', self.DEFAULT_ICON_URL)

        return [{'title': self.cleanHtmlStr(title), 'text': self.cleanHtmlStr(desc), 'images': [{'title': '', 'url': self.getFullUrl(icon)}], 'other_info': otherInfo}]

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
        elif category == 'list_filters':
            self.listFilters(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem, 'explore_item')
        elif category == 'explore_item':
            self.exploreItem(self.currItem, 'list_items')
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
        CHostBase.__init__(self, VODPL(), True, [])

    def getSearchTypes(self):
        searchTypesOptions = []
        searchTypesOptions.append(("Wszystkie", "wszystkie"))
        searchTypesOptions.append(("Filmy", "filmy"))
        searchTypesOptions.append(("Seriale", "seriale"))
        searchTypesOptions.append(("Dokumentalne", "dokumenty"))
        searchTypesOptions.append(("Programy TV", "programy"))
        return searchTypesOptions

    #def withArticleContent(self, cItem):
    #    if (cItem['type'] != 'video' and cItem['category'] != 'explore_item'):
    #        return False
    #    return True
