# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, getMPDLinksWithMeta
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
###################################################

###################################################
# FOREIGN import
###################################################
import urlparse
import urllib
from datetime import datetime, date, timedelta
from Components.config import config, ConfigSelection, ConfigYesNo, getConfigListEntry
###################################################


###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.tvnowde_show_paid_items = ConfigYesNo(default=False)
config.plugins.iptvplayer.tvnowde_show_drm_items = ConfigYesNo(default=False)
config.plugins.iptvplayer.tvnowde_prefered_format = ConfigSelection(default="hls", choices=[
("hls", _("HLS/m3u8")),
("dash", _("DASH/mpd"))
])


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Show paid items (it may be illegal)"), config.plugins.iptvplayer.tvnowde_show_paid_items))
    optionList.append(getConfigListEntry(_("Show items with DRM"), config.plugins.iptvplayer.tvnowde_show_drm_items))
    optionList.append(getConfigListEntry(_("Preferred format:"), config.plugins.iptvplayer.tvnowde_prefered_format))
    return optionList

###################################################


def gettytul():
    return 'https://www.tvnow.de/'


class TVNowDE(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'movs4u.com', 'cookie': 'movs4u.com.cookie'})
        self.DEFAULT_ICON_URL = 'https://www.tvnow.de/styles/modules/header/tvnow.png'
        self.USER_AGENT = 'User-Agent=Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Encoding': 'gzip, deflate'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})
        self.MAIN_URL = 'https://api.tvnow.de/v3/'
        self.cacheLinks = {}
        self.cacheAllAZ = []
        self.cacheAZ = {'list': [], 'cache': {}}
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.MAIN_CAT_TAB = [{'category': 'az', 'title': _('A-Z')},
                             {'category': 'missed', 'title': _('Missed the program?')},
                             {'category': 'channels', 'title': _('Channels')},
                             {'category': 'list_cats', 'title': _('Categories')},
                            ]
        self.CHANNELS_TAB = [{'title': 'RTL', 'f_channel': 'rtl'},
                             {'title': 'Vox', 'f_channel': 'vox'},
                             {'title': 'RTL 2', 'f_channel': 'rtl2'},
                             {'title': 'Nitro', 'f_channel': 'nitro'},
                             {'title': 'N-TV', 'f_channel': 'ntv'},
                             {'title': 'RTLplus', 'f_channel': 'rtlplus'},
                             {'title': 'Super RTL', 'f_channel': 'superrtl'},
                            ]

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)

        def _getFullUrl(url):
            if self.cm.isValidUrl(url):
                return url
            else:
                return urlparse.urljoin(baseUrl, url)

        addParams['cloudflare_params'] = {'domain': self.up.getDomain(baseUrl), 'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT, 'full_url_handle': _getFullUrl}
        sts, data = self.cm.getPageCFProtection(baseUrl, addParams, post_data)
        return sts, data

    def getStr(self, item, key):
        value = item.get(key, None)
        if value == None:
            value = ''
        elif type('') == type(value):
            return value
        return str(value)

    def listChannelsCats(self, cItem, nextCategory):
        printDBG("TVNowDE.listChannelsCats")
        url = self.getFullUrl('/channels/?fields=*&filter=%7B%22Active%22:true%7D&maxPerPage=50&page=1')
        sts, data = self.getPage(url)
        if not sts:
            return
        try:
            data = json_loads(data)
            for item in data['items']:
                if not item.get('active', True):
                    continue
                #url = '/channels/{0}?fields=%5B%22*%22,%22movies%22,%5B%22id%22,%22title%22,%22episode%22,%22broadcastStartDate%22,%22blockadeText%22,%22free%22,%22replaceMovieInformation%22,%22seoUrl%22,%22pictures%22,%5B%22*%22%5D,%22packages%22,%5B%22*%22%5D,%22manifest%22,%5B%22*%22%5D,%22format%22,%5B%22id%22,+%22station%22,+%22title%22,%22seoUrl%22,%22defaultDvdImage%22%5D%5D%5D'.format(item['id'])
                url = '/channels/{0}?fields=%5B%22*%22,%22movies%22,%5B%22id%22,%22title%22,%22episode%22,%22broadcastStartDate%22,%22articleLong%22,%22duration%22,%22free%22,%22replaceMovieInformation%22,%22seoUrl%22,%22pictures%22,%5B%22*%22%5D,%22packages%22,%5B%22*%22%5D,%22manifest%22,%5B%22*%22%5D,%22format%22,%5B%22id%22,+%22station%22,+%22title%22,%22seoUrl%22,%22defaultDvdImage%22%5D%5D%5D'.format(item['id'])
                url = self.getFullUrl(url)
                title = self.getStr(item, 'title')
                icon = 'https://ais.tvnow.de/tvnow/cms/{0}/300x169/image2.jpg'.format(self.getStr(item, 'defaultImage'))
                params = dict(cItem)
                params.update({'category': nextCategory, 'sub_key': 'movies', 'title': title, 'url': url, 'icon': icon})
                self.addDir(params)
        except Exception:
            printExc()

    def addChannelFilter(self, cItem, nextCategory, withWatchBox=False):
        printDBG("TVNowDE.addChannelFilter")
        allChannels = []
        channelList = list(self.CHANNELS_TAB)

        if withWatchBox:
            channelList.append({'title': 'WatchBox', 'f_channel': 'watchbox'})
        else:
            for item in self.CHANNELS_TAB:
                allChannels.append(item['f_channel'])

        channelList.insert(0, {'title': _('--All--'), 'f_channels': allChannels})
        for item in channelList:
            if 'f_channel' in item:
                icon = 'https://www.tvnow.de/styles/modules/headerstations/%s_active.png' % item['f_channel']
                fChannels = [item['f_channel']]
            else:
                icon = cItem.get('icon', '')
                fChannels = item['f_channels']

            params = dict(cItem)
            params.update({'category': nextCategory, 'title': item['title'], 'icon': icon, 'f_channels': fChannels})
            self.addDir(params)

    def addMissedDay(self, cItem, nextCategory):
        printDBG("TVNowDE.addMissedDay")

        now = datetime.now()
        for d in range(8):
            t = (now - timedelta(days=d)).strftime('%Y-%m-%d')
            if d == 0:
                title = _('Today')
            elif d == 1:
                title = _('Yesterday')
            else:
                title = t
            url = '/movies?fields=*,format,paymentPaytypes,pictures,trailers,packages&filter=%7B%22BroadcastStartDate%22:%7B%22between%22:%7B%22start%22:%22{0}+00:00:00%22,%22end%22:%22{1}+23:59:59%22%7D%7D%7D&maxPerPage=200&order=BroadcastStartDate+asc'.format(t, t)
            url = self.getFullUrl(url)
            params = dict(cItem)
            params.update({'category': nextCategory, 'url': url, 'title': title, 'icon': cItem.get('icon', '')})
            self.addDir(params)

    def listCats(self, cItem, nextCategory):
        printDBG("TVNowDE.listCats")

        genres = ["Tägliche Serien", "Action", "Crime", "Ratgeber", "Comedy", "Show", "Docutainment", "Drama", "Tiere", "News", "Mags", "Romantik", "Horror", "Familie", "Kochen", "Auto", "Sport", "Reportage und Dokumentationen", "Sitcom", "Mystery", "Lifestyle", "Musik", "Spielfilm", "Anime"]
        #["Soap", "Action", "Crime", "Ratgeber", "Comedy", "Show", "Docutainment", "Drama", "Tiere", "News", "Mags", "Romantik", "Horror", "Familie", "Kochen", "Auto", "Sport", "Reportage und Dokumentationen", "Sitcom", "Mystery", "Lifestyle", "Musik", "Spielfilm", "Anime"]
        for item in genres:
            params = dict(cItem)
            params = {'good_for_fav': False, 'title': item, 'f_genre': item.lower()}
            params['category'] = nextCategory
            self.addDir(params)

    def fillAZCache(self, cItem):
        printDBG("TVNowDE.fillAZCache")
        if 0 == len(self.cacheAllAZ):
            page = cItem.get('page', 1)
            total = 0
            while True:
                url = self.getFullUrl('/formats?fields=id,title,station,title,titleGroup,seoUrl,icon,hasFreeEpisodes,hasPayEpisodes,categoryId,searchAliasName,genres&filter=%7B%22Id%22:%7B%22containsNotIn%22:%5B%221896%22%5D%7D,%22Disabled%22:0%7D&maxPerPage=500&page=1&page={0}'.format(page))

                sts, data = self.getPage(url)
                if not sts:
                    return
                try:
                    data = json_loads(data)
                    total += len(data['items'])
                    for item in data['items']:
                        self.cacheAllAZ.append(item)
                    if data['total'] > total:
                        page += 1
                        continue
                except Exception:
                    printExc()
                break

    def listAZ(self, cItem, nextCategory):
        printDBG("TVNowDE.listAZ")

        self.fillAZCache(cItem)
        self.cacheAZ = {'list': [], 'cache': {}}
        fChannels = cItem.get('f_channels', [])

        try:
            for item in self.cacheAllAZ:
                if not config.plugins.iptvplayer.tvnowde_show_paid_items.value and not item.get('hasFreeEpisodes', False):
                    continue
                station = self.getStr(item, 'station')
                if len(fChannels) and station not in fChannels:
                    continue
                letter = self.getStr(item, 'titleGroup')
                title = self.getStr(item, 'title')
                name = self.cleanHtmlStr(self.getStr(item, 'seoUrl'))
                desc = item.get('genres', [])
                if isinstance(desc, list):
                    desc = ' | '.join(desc)
                else:
                    desc = ''

                params = {'good_for_fav': True, 'orig_item': item, 'f_station': station, 'f_name': name, 'title': title, 'desc': desc}
                if not letter in self.cacheAZ['list']:
                    self.cacheAZ['list'].append(letter)
                    self.cacheAZ['cache'][letter] = []
                self.cacheAZ['cache'][letter].append(params)

                categoryId = self.getStr(item, 'categoryId')
                if categoryId not in ['serie', 'film', 'news']:
                    printDBG("Unknown categoryId [%s]" % categoryId)
                    printDBG(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
                    printDBG(item)
        except Exception:
            printExc()

        self.cacheAZ['list'].sort()
        if len(fChannels) and len(self.cacheAZ['list']) > 1:
            params = dict(cItem)
            params = {'name': 'category', 'category': nextCategory, 'f_letter': 'all', 'title': _('--All--')}
            self.addDir(params)

        for letter in self.cacheAZ['list']:
            params = dict(cItem)
            params = {'name': 'category', 'category': nextCategory, 'f_letter': letter, 'title': letter}
            self.addDir(params)

    def listItemsByLetter(self, cItem, nextCategory):
        printDBG("TVNowDE.listItemsByLetter")
        fLetter = cItem.get('f_letter', '')
        for letter in self.cacheAZ['list']:
            if fLetter == 'all' or fLetter == letter:
                tab = self.cacheAZ['cache'].get(letter, [])
                for item in tab:
                    params = dict(item)
                    params.update({'name': 'category', 'category': nextCategory})
                    self.addDir(params)

    def listCatsItems(self, cItem, nextCategory):
        printDBG("TVNowDE.listCatsItems")
        page = cItem.get('page', 1)
        genre = cItem.get('f_genre', '')

        url = self.getFullUrl('/formats/genre/{0}?fields=*&filter=%7B%22station%22:%22none%22%7D&maxPerPage=500&order=NameLong+asc&page={1}'.format(urllib.quote(genre), page))

        sts, data = self.getPage(url)
        if not sts:
            return
        try:
            data = json_loads(data)
            for item in data['items']:
                if not config.plugins.iptvplayer.tvnowde_show_paid_items.value and not item.get('hasFreeEpisodes', False):
                    continue
                icon = self.getStr(item, 'defaultDvdImage')
                if icon == '':
                    icon = self.getStr(item, 'defaultDvdImage')
                title = self.getStr(item, 'title')
                station = self.getStr(item, 'station')
                name = self.cleanHtmlStr(self.getStr(item, 'seoUrl'))
                desc = self.cleanHtmlStr(self.getStr(item, 'metaDescription'))

                params = {'name': 'category', 'good_for_fav': True, 'orig_item': item, 'category': nextCategory, 'f_station': station, 'f_name': name, 'title': title, 'icon': icon, 'desc': desc}
                self.addDir(params)

                categoryId = self.getStr(item, 'categoryId')
                if not categoryId in ['serie', 'film', 'news']:
                    printDBG("Unknown categoryId [%s]" % categoryId)
                    printDBG(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
                    printDBG(item)
        except Exception:
            printExc()

    def listNavigation(self, cItem):
        printDBG("TVNowDE.listNavigation")
        name = cItem.get('f_name', '')
        station = cItem.get('f_station', '')

        url = self.getFullUrl('/formats/seo?fields=*,.*,formatTabs.*,formatTabs.formatTabPages.*,formatTabs.formatTabPages.container.*,annualNavigation.*&name={0}.php&station={1}'.format(name, station))

        sts, data = self.getPage(url)
        if not sts:
            return
        try:
            data = json_loads(data)
            if data.get('tabSeason', False):
                for item in data['formatTabs']['items']:
                    if not item.get('visible', False):
                        continue
                    try:
                        title = self.getStr(item, 'headline')
                        containers = []
                        for tabItem in item['formatTabPages']['items']:
                            containers.append(tabItem['container']['id'])

                        if 0 == len(containers):
                            continue
                        params = {'name': 'category', 'category': 'list_tab_items', 'f_containers_items': containers, 'title': title, 'icon': cItem.get('icon', ''), 'desc': cItem.get('desc', '')}
                        self.addDir(params)
                    except Exception:
                        printExc()
            else:
                id = data['id']
                for item in data['annualNavigation']['items']:
                    year = int(self.getStr(item, 'year'))
                    months = item['months']
                    for m in range(1, 13, 1):
                        m1 = (m + 1)
                        if m1 > 12:
                            m1 = m1 % 12
                        days = (date(year + m / 12, m1, 1) - date(year, m, 1)).days

                        m = str(m)
                        if not m in months:
                            continue
                        title = '%s/%s' % (year, m.zfill(2))
                        url = self.getFullUrl('/movies?fields=*,format,paymentPaytypes,pictures,trailers,packages&filter=%7B%22BroadcastStartDate%22:%7B%22between%22:%7B%22start%22:%22{0}-{1}-{2}+00:00:00%22,%22end%22:+%22{3}-{4}-{5}+23:59:59%22%7D%7D,+%22FormatId%22+:+{6}%7D&maxPerPage=300&order=BroadcastStartDate+desc'.format(year, m.zfill(2), '01', year, m.zfill(2), str(days).zfill(2), id))
                        params = {'name': 'category', 'category': 'list_video_items', 'url': url, 'title': title, 'icon': cItem.get('icon', ''), 'desc': cItem.get('desc', '')}
                        self.addDir(params)
                self.currList.reverse()

        except Exception:
            printExc()

    def listTabItems(self, cItem):
        printDBG("TVNowDE.listTabItems")
        containers = cItem.get('f_containers_items', [])

        try:
            for item in containers:
                url = self.getFullUrl('/containers/{0}/movies?fields=*,format.*,paymentPaytypes.*,livestreamEvent.*,pictures,trailers,packages,annualNavigation&maxPerPage=500&order=OrderWeight+asc,+BroadcastStartDate+desc'.format(item))
                params = dict(cItem)
                cItem['url'] = url
                self.listVideoItems(cItem)
        except Exception:
            printExc()

    def listVideoItems(self, cItem):
        printDBG("TVNowDE.listVideoItems [%s]" % cItem)
        page = cItem.get('page', 1)
        url = cItem['url'] + '&page=%s' % page
        fChannels = cItem.get('f_channels', [])

        sts, data = self.getPage(url)
        if not sts:
            return
        try:
            data = json_loads(data)
            subKey = cItem.get('sub_key', '')
            if subKey != '':
                data = data[subKey]
            for item in data['items']:
                try:
                    if not config.plugins.iptvplayer.tvnowde_show_paid_items.value and not item.get('free', False):
                        continue

                    if not config.plugins.iptvplayer.tvnowde_show_drm_items.value and item.get('isDrm', False):
                        SetIPTVPlayerLastHostError(_("Items with DRM protection."))
                        continue

                    urlDashClear = item['manifest']['dashclear']
                    if not self.cm.isValidUrl(urlDashClear):
                        continue

                    station = self.getStr(item['format'], 'station')
                    if len(fChannels) and station not in fChannels:
                        continue

                    id = self.getStr(item, 'id')
                    icon = 'https://ais.tvnow.de/tvnow/movie/{0}/600x716/title.jpg'.format(id)
                    title = self.getStr(item, 'title')
                    desc = self.cleanHtmlStr(self.getStr(item, 'articleLong'))
                    seoUrlItem = self.getStr(item, 'seoUrl')
                    seoUrlFormat = self.getStr(item['format'], 'seoUrl')

                    descTab = []
                    for d in [('broadcastStartDate', '%s'), ('episode', _('episode: %s')), ('duration', _('duration: %s'))]:
                        t = self.getStr(item, d[0])
                        if t != '':
                            descTab.append(d[1] % t)
                    if len(descTab):
                        desc = ' | '.join(descTab) + '[/br]' + desc

                    url = '/%s/%s' % (seoUrlFormat, seoUrlItem)
                    params = {'good_for_fav': True, 'orig_item': item, 'dashclear': urlDashClear, 'f_seo_url_format': seoUrlFormat, 'f_seo_url_item': seoUrlItem, 'f_station': station, 'title': title, 'url': url, 'icon': icon, 'desc': desc}
                    self.addVideo(params)
                except Exception:
                    printExc()
        except Exception:
            printExc()

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("TVNowDE.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('/?s=' + urllib.quote_plus(searchPattern))
        self.listItems(cItem, 'explore_item')

    def getLinksForVideo(self, cItem):
        printDBG("TVNowDE.getLinksForVideo [%s]" % cItem)
        retTab = []

        cacheTab = self.cacheLinks.get(cItem['url'], [])
        if len(cacheTab):
            return cacheTab

        urlDashClear = '' #cItem.get('dashclear', '')
        if not self.cm.isValidUrl(urlDashClear):
            try:
                seoUrlItem = cItem['f_seo_url_format']
                seoUrlFormat = cItem['f_seo_url_item']
                station = cItem['f_station']
                url = self.getFullUrl('/movies/{0}/{1}?fields=*,format,files,manifest,breakpoints,paymentPaytypes,trailers,packages&station={2}'.format(seoUrlItem, seoUrlFormat, station))
                sts, data = self.getPage(url)
                if not sts:
                    return []
                try:
                    data = json_loads(data)
                except Exception:
                    data = 'error'

                if 'error' in data:
                    data = cItem['orig_item']

                urlDashClear = data['manifest']['dashclear']
                if data.get('isDrm', False):
                    SetIPTVPlayerLastHostError(_("Video with DRM protection."))
                if not self.cm.isValidUrl(urlDashClear):
                    return []
            except Exception:
                printExc()

        if self.cm.isValidUrl(urlDashClear):
            urlHlsClear = urlDashClear.replace('/vodnowusodash.', '/vodnowusohls.').split('?', 1)
            urlHlsClear[0] = urlHlsClear[0][:-3] + 'm3u8'
            urlHlsClear = '?'.join(urlHlsClear)
            hlsTab = getDirectM3U8Playlist(urlHlsClear, checkContent=True)
            dashTab = getMPDLinksWithMeta(urlDashClear, False)
            try:
                hlsTab = sorted(hlsTab, key=lambda item: -1 * int(item.get('bitrate', 0)))
                dashTab = sorted(dashTab, key=lambda item: -1 * int(item.get('bandwidth', 0)))
            except Exception:
                printExc()
            if config.plugins.iptvplayer.tvnowde_prefered_format.value == 'hls':
                retTab.extend(hlsTab)
                retTab.extend(dashTab)
            else:
                retTab.extend(dashTab)
                retTab.extend(hlsTab)
        if len(retTab):
            self.cacheLinks[cItem['url']] = retTab

        return retTab

    def getVideoLinks(self, videoUrl):
        printDBG("TVNowDE.getVideoLinks [%s]" % videoUrl)
        videoUrl = strwithmeta(videoUrl)
        urlTab = []
        orginUrl = str(videoUrl)

        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if videoUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name']
                        break

        if self.cm.isValidUrl(videoUrl):
            urlTab = self.up.getVideoLinkExt(videoUrl)

        return urlTab

    def getFavouriteData(self, cItem):
        printDBG('TVNowDE.getFavouriteData')
        params = dict(cItem)
        params.pop('dashclear', None)
        return json_dumps(params)

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: || name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})
        elif category == 'channels':
            self.listChannelsCats(self.currItem, 'list_video_items')
        elif category == 'missed':
            self.addChannelFilter(self.currItem, 'missed_day')
        elif category == 'missed_day':
            self.addMissedDay(self.currItem, 'list_video_items')
        elif category == 'list_missed':
            self.listMissedItems(self.currItem, 'list_missed')
        elif category == 'az':
            self.addChannelFilter(self.currItem, 'list_az', True)
        elif category == 'list_az':
            self.listAZ(self.currItem, 'list_items_by_letter')
        elif category == 'list_items_by_letter':
            self.listItemsByLetter(self.currItem, 'list_navigation')
        elif category == 'list_cats':
            self.listCats(self.currItem, 'list_cats_items')
        elif category == 'list_cats_items':
            self.listCatsItems(self.currItem, 'list_navigation')
        elif category == 'list_navigation':
            self.listNavigation(self.currItem)
        elif category == 'list_tab_items':
            self.listTabItems(self.currItem)
        elif category == 'list_video_items':
            self.listVideoItems(self.currItem)
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
        CHostBase.__init__(self, TVNowDE(), True, [])
