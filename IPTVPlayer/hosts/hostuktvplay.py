# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, CSelOneLink, byteify
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
###################################################

###################################################
# FOREIGN import
###################################################
import urlparse
import urllib
from datetime import timedelta
try:
    import json
except Exception:
    import simplejson as json
###################################################


def gettytul():
    return 'https://uktvplay.uktv.co.uk/'


class UKTVPlay(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'uktvplay.uktv.co.uk', 'cookie': 'uktvplay.uktv.co.uk.cookie'})
        self.DEFAULT_ICON_URL = 'https://uktv-static.s3.amazonaws.com/prod/uktvplay/img/logo.png?9b58be2039a7'
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.MAIN_URL = 'https://uktvplay.uktv.co.uk/'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Encoding': 'gzip, deflate', 'Referer': self.getMainUrl(), 'Origin': self.getMainUrl()}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding': 'gzip, deflate', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json, text/javascript, */*; q=0.01'})

        self.cacheLinks = {}
        self.cacheFilters = {}
        self.cacheFiltersKeys = []
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.tmpUrl = 'http://vschedules.uktv.co.uk/mobile/v2/%splatform=android&app_ver=4.3.2'

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

    def getChannelUrl(self, channel):
        return 'most_popular?channel=%s&carousel_limit=200&' % channel

    def listMainMenu(self, cItem):
        printDBG("UKTVPlay.listMainMenu")
        self.MAIN_CAT_TAB = [
                             {'category': 'list_items', 'title': 'DAVE', 'url': self.getChannelUrl('dave')},
                             {'category': 'list_items', 'title': 'REALLY', 'url': self.getChannelUrl('really')},
                             {'category': 'list_items', 'title': 'YESTERDAY', 'url': self.getChannelUrl('yesterday')},
                             {'category': 'list_items', 'title': 'DRAMA', 'url': self.getChannelUrl('drama')},
                             {'category': 'list_items', 'title': 'BOX SET', 'url': 'collections?collection_type=boxset&'},
                             {'category': 'list_items', 'title': 'COLLECTIONS', 'url': 'collections?collection_type=collection&'},
                             {'category': 'list_genres', 'title': 'GENRES', 'url': 'genres?'},
                             {'category': 'list_letters', 'title': 'A-Z', 'url': 'brand_list?channel=&'},

                             {'category': 'search', 'title': _('Search'), 'search_item': True},
                             {'category': 'search_history', 'title': _('Search history')},
                            ]
        self.listsTab(self.MAIN_CAT_TAB, cItem)

    def listGenres(self, cItem, nextCategory, data=None):
        printDBG("UKTVPlay.listGenres [%s]" % cItem)

        try:
            url = self.tmpUrl % cItem['url']

            if data == None:
                sts, data = self.getPage(url)
                if not sts:
                    return
                data = byteify(json.loads(data), '', True)

            for item in data:
                url = 'genre_items?genre_name=%s&' % item['name'].upper()
                title = self.cleanHtmlStr(item['title'])
                icon = self.getFullIconUrl(item['image'])
                params = {'good_for_fav': False, 'category': nextCategory, 'url': url, 'title': title, 'icon': icon}
                self.addDir(params)
        except Exception:
            printExc()

    def listLetters(self, cItem, nextCategory):
        printDBG("UKTVPlay.listLetters [%s]" % cItem)

        try:
            url = self.tmpUrl % cItem['url']

            sts, data = self.getPage(url)
            if not sts:
                return

            data = byteify(json.loads(data), '', True)
            for item in data:
                url = 'brand_list?channel=&letter=%s&' % item[0]
                title = self.cleanHtmlStr(item)
                params = {'good_for_fav': False, 'category': nextCategory, 'url': url, 'title': title}
                self.addDir(params)
        except Exception:
            printExc()

    def listItems(self, cItem, nextCategory, data=None):
        try:
            if data == None:
                url = self.tmpUrl % cItem['url']
                sts, data = self.getPage(url)
                if not sts:
                    return
                data = byteify(json.loads(data), '', True)

            for item in data:
                if item == '':
                    continue
                descTab = []

                icon = item.get('image', '')
                house = item.get('top_house_number', '')
                title = self.cleanHtmlStr(item.get('title', ''))

                if icon == '':
                    icon = item['brand_image']
                if house == '':
                    house = item['house_num']
                if title == '':
                    title = self.cleanHtmlStr(item['brand_name'])

                pg = []
                if '' != item.get('guidance_age', ''):
                    pg.append(item['guidance_age'])
                if '' != item.get('guidance_text', ''):
                    pg.append(item['guidance_text'])
                if len(pg):
                    descTab.append(' '.join(pg))

                if '' != item.get('channel', ''):
                    descTab.append(_('Channel: %s') % item['channel'].title())
                if '' != item.get('video_count', ''):
                    descTab.append(_('Videos count: %s') % item['video_count'])

                desc = '[/br]'.join(descTab)

                params = {'good_for_fav': True, 'category': nextCategory, 'title': title, 'icon': icon, 'desc': desc, 'f_house': house}
                self.addDir(params)
        except Exception:
            printExc()

    def listSeasons(self, cItem, nextCategory):
        printDBG("UKTVPlay.listSeasons [%s]" % cItem)
        try:
            url = self.tmpUrl % ('item_details?vod_ids=%s&' % cItem['f_house'])

            sts, data = self.getPage(url)
            if not sts:
                return

            data = byteify(json.loads(data), '', True)[0]
            brandId = data['brand_id']
            keys = list(data['available_series'].keys())
            keys.sort(reverse=True)

            for key in keys:
                seriesId = data['available_series'][key]
                params = dict(cItem)
                params.update({'good_for_fav': False, 'category': nextCategory, 'title': _('Season %s') % key, 'f_series_id': seriesId, 'f_brand_id': brandId})
                self.addDir(params)

            if len(self.currList) == 1:
                item = self.currList.pop()
                self.listEpisodes(item)
        except Exception:
            printExc()

    def listEpisodes(self, cItem):
        printDBG("UKTVPlay.listEpisodes [%s]" % cItem)
        try:
            url = self.tmpUrl % ('brand_episodes?brand_id=%s&series_id=%s&' % (cItem['f_brand_id'], cItem['f_series_id']))

            sts, data = self.getPage(url)
            if not sts:
                return

            data = byteify(json.loads(data), '', True)
            for item in data['episodes']:
                vidId = item['brightcove_video_id']
                icon = self.getFullIconUrl(item['episode_image'])
                sTitle = self.cleanHtmlStr(item['brand_name'])
                eTitle = self.cleanHtmlStr(item['episode_title'])
                sNum = item['series_txt']
                eNum = item['episode_txt']
                if 1 == len(data['episodes']) and sTitle == eTitle:
                    title = sTitle
                else:
                    title = '%s - s%se%s %s' % (sTitle, sNum.zfill(2), eNum.zfill(2), eTitle)
                url = self.getFullUrl(item['watch_online_link'])

                descTab = []
                pg = []
                if '' != item.get('guidance_age', ''):
                    pg.append(item['guidance_age'])
                if '' != item.get('guidance_text', ''):
                    pg.append(item['guidance_text'])
                if len(pg):
                    descTab.append(' '.join(pg))

                descTab.append(_('Duration: %s') % str(timedelta(seconds=int(item['content_duration']))))
                if '' != item.get('channel', ''):
                    descTab.append(_('Channel: %s') % item['channel'].title())

                descTab.append(item.get('teaser_text', ''))
                desc = '[/br]'.join(descTab)

                params = {'good_for_fav': True, 'title': title, 'f_video_id': vidId, 'url': url, 'icon': icon, 'desc': desc}
                self.addVideo(params)
        except Exception:
            printExc()

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("UKTVPlay.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        try:
            url = self.tmpUrl % ('search?q=%s&' % urllib.quote(searchPattern))

            sts, data = self.getPage(url)
            if not sts:
                return

            data = byteify(json.loads(data), '', True)
            self.listItems(cItem, 'list_seasons', data.get('brands', []))
            self.listItems(cItem, 'list_seasons', data.get('collections', []))
            self.listGenres(cItem, 'list_items', data.get('genres', []))
        except Exception:
            printExc()

    def getLinksForVideo(self, cItem):
        printDBG("UKTVPlay.getLinksForVideo [%s]" % cItem)

        retTab = []

        videoUrl = 'http://c.brightcove.com/services/mobile/streaming/index/master.m3u8?videoId=%s' % cItem['f_video_id']
        retTab = getDirectM3U8Playlist(videoUrl, checkContent=True)

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

        self.informAboutGeoBlockingIfNeeded('GB')

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listMainMenu({'name': 'category'})
        elif category == 'list_items':
            self.listItems(self.currItem, 'list_seasons')
        elif category == 'list_genres':
            self.listGenres(self.currItem, 'list_items')
        elif category == 'list_letters':
            self.listLetters(self.currItem, 'list_items')
        elif category == 'list_seasons':
            self.listSeasons(self.currItem, 'list_episodes')
        elif category == 'list_episodes':
            self.listEpisodes(self.currItem)
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
        CHostBase.__init__(self, UKTVPlay(), True, [])
