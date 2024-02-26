# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify, PrevDay
from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.utils import clean_html
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
###################################################
# FOREIGN import
###################################################
try:
    import json
except Exception:
    import simplejson as json
from datetime import datetime
from Components.config import config, ConfigYesNo, getConfigListEntry
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.tv3player_use_web_proxy = ConfigYesNo(default=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use web-proxy for VODs (it may be illegal):"), config.plugins.iptvplayer.tv3player_use_web_proxy))
    return optionList
###################################################


def gettytul():
    return 'https://srgssr.ch/'


class PlayRTSIW(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'PlayRTSIW.tv', 'cookie': 'rte.ie.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})

        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.ITEMS_TYPE_MAP = {'tv': 'videos', 'radio': 'audios'}
        self.PLAYER_MAP = ['rtr', 'srf', 'rsi', 'swi', 'rts']
        self.URL_MAP = {'rtr': 'https://www.rtr.ch/',
                        'srf': 'https://www.srf.ch/',
                        'rsi': 'https://www.rsi.ch/',
                        'swi': 'https://play.swissinfo.ch/',
                        'rts': 'http://www.rts.ch/'}

        self.PORTALS_MAP = {}
        for item in self.PLAYER_MAP:
            self.URL_MAP['%s_icon' % item] = self.URL_MAP[item] + 'play/static/img/srg/%s/play%s_logo.png' % (item, item)
            self.PORTALS_MAP[item] = {'title': item.upper(), 'url': self.URL_MAP[item] + 'play/tv', 'icon': self.URL_MAP['%s_icon' % item]}
        self.SEARCH_ICON_URL = 'https://www.srgssr.ch/fileadmin/dam/images/quicklinks/srgssr-auf-einen-blick.png'
        self.DEFAULT_ICON_URL = 'https://upload.wikimedia.org/wikipedia/commons/thumb/d/d4/SRG_SSR_2011_logo.svg/2000px-SRG_SSR_2011_logo.svg.png'
        self.MAIN_URL = None
        self.cacheLinks = {}
        self.cacheShowsMap = []
        self.cacheShowsAZ = []

    def setMainUrl(self, url):
        if self.cm.isValidUrl(url):
            self.MAIN_URL = self.cm.getBaseUrl(url)

    def getFullIconUrl(self, url):
        url = self.getFullUrl(url)
        lurl = url.lower()
        if url != '' and '/scale/' not in url and \
           not lurl.endswith('.png') and \
           not lurl.endswith('.jpg') and \
           not lurl.endswith('.jpeg'):
            url += '/scale/width/344'
        return url

    def listMainMenu(self, cItem, nextCategory1, nextCategory2):
        printDBG("PlayRTSIW.listMainMenu")
        for portal in ['rtr', 'rsi', 'srf', 'rts', 'swi']:
            params = dict(cItem)
            params.update(self.PORTALS_MAP[portal])
            params.update({'portal': portal, 'desc': params['url']})
            if portal == 'swi':
                params.update({'f_type': 'tv', 'category': nextCategory2})
            else:
                params.update({'category': nextCategory1})
            self.addDir(params)

        MAIN_CAT_TAB = [{'category': 'search', 'title': _('Search'), 'search_item': True, 'icon': self.SEARCH_ICON_URL},
                        {'category': 'search_history', 'title': _('Search history'), 'icon': self.SEARCH_ICON_URL}]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listType(self, cItem):
        printDBG("PlayRTSIW.listType")
        self.setMainUrl(cItem['url'])
        self.DEFAULT_ICON_URL = cItem['icon']

        for item in [('tv', _('TV')), ('radio', _('Radio'))]:
            params = dict(cItem)
            params.update({'f_type': item[0], 'title': item[1], 'desc': self.getFullUrl('/play/' + item[0])})
            if item[0] == 'tv':
                params.update({'category': 'portal'})
            else:
                params.update({'category': 'radio_channels'})
            self.addDir(params)

    def listRadioChannels(self, cItem, nextCategory):
        printDBG("PlayRTSIW.listPortalMain")

        url = self.getFullUrl('/play/radio/page/channel/navigation')
        sts, data = self.cm.getPage(url)
        if not sts:
            return

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(item)
            if title == '':
                title = self.cm.ph.getSearchGroups(item, '''channelNavigationLogo__([^'^"]+?)['"]''')[0].upper()
            params = dict(cItem)
            params.update({'title': title, 'url': url})
            if 'station=' in url:
                channelId = self.cm.ph.getSearchGroups(item, '''station=([^'^"]+?)['"]''')[0]
                params.update({'category': nextCategory, 'f_channel_id': channelId})
                self.addDir(params)
            else:
                params.update({'good_for_fav': True, 'desc': url})
                self.addAudio(params)

    def listPortalMain(self, cItem):
        printDBG("PlayRTSIW.listPortalMain")
        self.cacheShowsMap = []
        self.cacheShowsAZ = []

        self.setMainUrl(cItem['url'])
        self.DEFAULT_ICON_URL = cItem['icon']

        portal = cItem['portal']
        type = cItem['f_type']

        if type == 'tv':
            params = dict(cItem)
            params.update({'category': 'list_live', 'title': _('Live'), 'url': self.getFullUrl('/play/v2/tv/live/overview'), 'desc': self.getFullUrl('/play/tv/live')})
            self.addDir(params)

        if type == 'tv':
            url = '/play/tv/videos/latest?numberOfVideos=100&moduleContext=homepage'
        else:
            url = '/play/radio/latest/audios?numberOfAudios=100&moduleContext=homepage&channelId=' + cItem['f_channel_id']
        params = dict(cItem)
        params.update({'category': 'list_teaser_items', 'title': _('Latest'), 'url': self.getFullUrl(url)})
        self.addDir(params)

        if type == 'tv':
            url = '/play/tv/videos/trending?numberOfVideos=23&onlyEpisodes=true&includeEditorialPicks=true'
        else:
            url = '/play/radio/mostclicked/audios?numberOfAudios=23&moduleContext=homepage&channelId=' + cItem['f_channel_id']
        params = dict(cItem)
        params.update({'category': 'list_teaser_items', 'title': _('Most popular'), 'url': self.getFullUrl(url)})
        self.addDir(params)

        if portal != 'swi':
            params = dict(cItem)
            params.update({'category': 'list_days', 'title': _('List by day'), 'icon': 'http://icons.iconarchive.com/icons/paomedia/small-n-flat/1024/calendar-icon.png'})
            self.addDir(params)

        # chek if categories are available
        url = self.getFullUrl('/play/v2/%s/topicList?numberOfMostClicked=1&numberOfLatest=1&moduleContext=topicpaget' % type)
        sts, data = self.cm.getPage(url)
        if not sts:
            return
        try:
            if len(json.loads(data)):
                params = dict(cItem)
                params.update({'category': 'list_cats', 'title': _('Categories')})
                self.addDir(params)
        except Exception:
            printExc()

        # check AZ
        if portal != 'swi':
            if type == 'tv':
                url = self.getFullUrl('/play/v2/tv/shows/atoz/index')
            else:
                url = self.getFullUrl('/play/v2/radio/channel/%s/shows/atoz/index' % cItem['f_channel_id'])
            sts, data = self.cm.getPage(url)
            if not sts:
                return
            try:
                self.cacheShowsAZ = byteify(json.loads(data))
            except Exception:
                printExc()
            if len(self.cacheShowsAZ):
                params = dict(cItem)
                params.update({'category': 'list_az', 'title': _('AZ')})
                self.addDir(params)

    def listSubItems(self, cItem):
        printDBG("PlayRTSIW.listSubItems")
        self.currList = cItem['sub_items']

    def listCats(self, cItem, nextCategory1, nextCategory2):
        printDBG("PlayRTSIW.listCats")
        type = cItem['f_type']
        url = self.getFullUrl('/play/v2/%s/topicList?numberOfMostClicked=100&numberOfLatest=100&moduleContext=topicpaget' % type)

        sts, data = self.cm.getPage(url)
        if not sts:
            return
        try:
            data = byteify(json.loads(data))
            for item in data:
                sTitle = self.cleanHtmlStr(item['title'])
                sUrl = self.getFullUrl(item['url'])

                latestSubItems = []
                mostSubItems = []

                for it in item.get('subTopics', []):
                    title = self.cleanHtmlStr(it['title'])
                    url = self.getFullUrl(it['url'])

                    if 'latestModuleUrl' in it:
                        params = dict(cItem)
                        params.update({'category': nextCategory2, 'url': self.getFullUrl(it['latestModuleUrl']), 'title': title})
                        latestSubItems.append(params)

                    if 'mostClickedModuleUrl' in it:
                        params = dict(cItem)
                        params.update({'category': nextCategory2, 'url': self.getFullUrl(it['mostClickedModuleUrl']), 'title': title})
                        mostSubItems.append(params)

                subItems = []

                if len(latestSubItems):
                    if 'latestModuleUrl' in item:
                        params = dict(cItem)
                        params.update({'category': nextCategory2, 'url': self.getFullUrl(item['latestModuleUrl']), 'title': _('--All--')})
                        latestSubItems.insert(0, params)
                    params = dict(cItem)
                    params.update({'category': nextCategory1, 'title': _('Most recent'), 'sub_items': latestSubItems})
                    subItems.append(params)
                else:
                    if 'latestModuleUrl' in item:
                        params = dict(cItem)
                        params.update({'category': nextCategory2, 'url': self.getFullUrl(item['latestModuleUrl']), 'title': _('Most recent')})
                        subItems.append(params)

                if len(mostSubItems):
                    if 'mostClickedModuleUrl' in item:
                        params = dict(cItem)
                        params.update({'category': nextCategory2, 'url': self.getFullUrl(item['mostClickedModuleUrl']), 'title': _('--All--')})
                        mostSubItems.insert(0, params)
                    params = dict(cItem)
                    params.update({'category': nextCategory1, 'title': _('Most recent'), 'sub_items': mostSubItems})
                    subItems.append(params)
                else:
                    if 'mostClickedModuleUrl' in item:
                        params = dict(cItem)
                        params.update({'category': nextCategory2, 'url': self.getFullUrl(item['mostClickedModuleUrl']), 'title': _('Most recent')})
                        subItems.append(params)

                params = dict(cItem)
                if len(subItems) > 1:
                    params.update({'category': nextCategory1, 'url': sUrl, 'title': sTitle, 'sub_items': subItems})
                    self.addDir(params)
                elif len(subItems) == 1 and 'sub_items' not in subItems[0]:
                    params.update({'category': nextCategory2, 'url': subItems[0]['url'], 'title': sTitle})
                    self.addDir(params)
        except Exception:
            printExc()

    def listDays(self, cItem, nextCategory):
        printDBG("PlayRTSIW.listDays [%s]" % cItem)
        type = cItem['f_type']
        channelId = cItem.get('f_channel_id', '')
        if 'f_date' not in cItem:
            dt = datetime.now()
        else:
            dt = datetime.strptime(cItem['f_date'], '%d-%m-%Y').date()
        baseUrl = self.getFullUrl('/play/v2/{0}/programDay/%s/{1}'.format(type, channelId))
        for item in range(31):
            title = dt.strftime('%d-%m-%Y')
            url = baseUrl % title
            params = dict(cItem)
            params.update({'good_for_fav': False, 'category': nextCategory, 'title': title, 'url': url})
            self.addDir(params)
            dt = PrevDay(dt)

        params = dict(cItem)
        params.update({'good_for_fav': False, 'title': _('Older'), 'f_date': dt.strftime('%d-%m-%Y')})
        self.addDir(params)

    def _listItems(self, cItem, data):
        printDBG("PlayRTSIW._listItems")
        type = cItem['f_type']
        try:
            for item in data:
                title = item['title']
                url = item['absoluteDetailUrl']
                icon = self.getFullIconUrl(item['imageUrl'])
                desc = [item['duration'], item['date']]
                if item['isGeoblocked']:
                    desc.append(_('geoblocked'))
                descTab = []
                descTab.append(item['showTitle'])
                descTab.append(', '.join(desc))
                descTab.append(item.get('description', ''))

                params = dict(cItem)
                params.update({'good_for_fav': True, 'title': title, 'url': url, 'item_id': item['id'], 'popup_url': self.getFullUrl(item['popupUrl']), 'detail_url': self.getFullUrl(item['detailUrl']), 'icon': icon, 'desc': '[/br]'.join(descTab)})
                if 'downloadHdUrl' in item:
                    params['download_hd_url'] = item['downloadHdUrl']
                if 'downloadSdUrl' in item:
                    params['download_sd_url'] = item['downloadSdUrl']
                if type == 'tv':
                    self.addVideo(params)
                else:
                    self.addAudio(params)
        except Exception:
            printExc()

    def _listShows(self, cItem, data):
        printDBG("PlayRTSIW._listShows")
        type = cItem['f_type']
        for item in data:
            title = self.cleanHtmlStr(item['title'])
            icon = self.getFullIconUrl(item['imageUrl'])
            url = item['absoluteOverviewUrl']
            desc = []
            if 'episodeCount' in item and item['episodeCount']['isDefined']:
                desc.append(_('%s episodes') % item['episodeCount']['formatted'])
            desc.append(self.cleanHtmlStr(item.get('description', '')))
            sUrl = self.getFullUrl('/play/%s/show/%s/latestEpisodes' % (type, item['id']))

            params = dict(cItem)
            params.update({'good_for_fav': True, 'title': title, 'url': url, 'f_show_url': sUrl, 'icon': icon, 'desc': '[/br]'.join(desc)})
            self.addDir(params)

    def listTeaserItems(self, cItem):
        printDBG("PlayRTSIW.listTeaserItems")
        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return

        tmp = self.cm.ph.getAllItemsBeetwenMarkers(data, 'data-teaser="', '"', False)
        for data in tmp:
            data = clean_html(data)
            try:
                data = byteify(json.loads(data))
                self._listItems(cItem, data)
            except Exception:
                printExc()

    def listAZ(self, cItem, nextCategory):
        printDBG("PlayRTSIW.listAZ cItem[%s]" % (cItem))

        try:
            allLetters = []
            for item in self.cacheShowsAZ:
                if not item['hasShows']:
                    continue
                params = dict(cItem)
                params.update({'good_for_fav': False, 'title': item['id'], 'category': nextCategory, 'f_letters': [item['id']]})
                self.addDir(params)
                allLetters.append(item['id'])
        except Exception:
            printExc()

        if len(allLetters):
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _('All'), 'category': nextCategory, 'f_letters': allLetters})
            self.currList.insert(0, params)

    def listAZItems(self, cItem, nextCategory):
        printDBG("PlayRTSIW.listAZItems cItem[%s]" % (cItem))
        type = cItem['f_type']
        if self.cacheShowsMap == []:
            if type == 'tv':
                url = self.getFullUrl('/play/v2/%s/shows' % type)
            else:
                url = self.getFullUrl('/play/radio/shows/alphabetical-sections?channelId=' + cItem['f_channel_id'])
            sts, data = self.cm.getPage(url)
            if not sts:
                return

            data = clean_html(self.cm.ph.getDataBeetwenMarkers(data, 'data-alphabetical-sections="', '"', False)[1])
            try:
                self.cacheShowsMap = byteify(json.loads(data))
            except Exception:
                printExc()

        letters = cItem.get('f_letters', '')
        try:
            for section in self.cacheShowsMap:
                if section['id'] not in letters:
                    continue
                params = dict(cItem)
                params['category'] = nextCategory
                self._listShows(params, section['showTeaserList'])
        except Exception:
            printExc()

    def listEpisodes(self, cItem):
        printDBG("PlayRTSIW.listEpisodes cItem[%s]" % (cItem))

        sts, data = self.cm.getPage(cItem['f_show_url'])
        if not sts:
            return
        try:
            data = byteify(json.loads(data))
            self._listItems(cItem, data['episodes'])

            nextPage = self.getFullUrl(data['nextPageUrl'])
            if nextPage != '':
                params = dict(cItem)
                params.update({'good_for_fav': False, 'title': _('Next page'), 'f_show_url': nextPage})
                self.addDir(params)
        except Exception:
            printExc()

    def listLiveChannels(self, cItem):
        printDBG("PlayRTSIW.listLiveChannels")

        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return
        try:
            data = byteify(json.loads(data))
            for item in data['teaser']:
                title = item['channelName']
                url = self.getFullUrl(item['urlToLivePage'])
                urlToPlayer = self.getFullUrl(item['urlToPlayer'])
                icon = self.getFullIconUrl(item['logo'])
                descTab = []

                params = dict(cItem)
                params.update({'good_for_fav': True, 'title': title, 'url': url, 'item_id': item['id'], 'popup_url': url, 'url_to_player': urlToPlayer, 'icon': icon, 'desc': '[/br]'.join(descTab)})
                self.addVideo(params)
        except Exception:
            printExc()

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("PlayRTSIW.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))

        self.setMainUrl(self.URL_MAP[searchType.lower()])
        self.DEFAULT_ICON_URL = self.SEARCH_ICON_URL
        pattern = urllib_quote(searchPattern)

        baseUrl = 'search?searchQuery={0}&numberOf'.format(pattern)
        for type in ['tv', 'radio']:
            baseItem = {'name': 'category', 'type': 'category', 'f_type': type}
            subItems = []

            countDesc = []
            # SHOWS
            cUrl = self.getFullUrl('/play/v2/' + type + '/shows/' + baseUrl) + 'Shows='
            sts, data = self.cm.getPage(cUrl + '1')
            if not sts:
                return
            try:
                data = json.loads(data)
                if data['numberOfAvailableShows'] > 0:
                    params = dict(baseItem)
                    params.update({'category': 'search_shows', 'title': _('SHOWS'), 'url': cUrl + '100', 'desc': _('Search for "%s", %s, %s %s') % (searchPattern, _(type), data['numberOfAvailableShows'], _('shows'))})
                    subItems.append(params)
                countDesc.append(_('%s shows') % data['numberOfAvailableShows'])
            except Exception:
                printExc()
                continue

            # VIDEOS/AUDIOS
            cUrl = self.getFullUrl('/play/v2/' + type + '/' + self.ITEMS_TYPE_MAP[type] + '/' + baseUrl) + self.ITEMS_TYPE_MAP[type].title() + '='
            sts, data = self.cm.getPage(cUrl + '1')
            if not sts:
                return
            try:
                data = json.loads(data)
                countKey = 'numberOfAvailable' + self.ITEMS_TYPE_MAP[type].title()
                if data[countKey] > 0:
                    params = dict(baseItem)
                    params.update({'category': 'search_items', 'title': _(self.ITEMS_TYPE_MAP[type].upper()), 'url': cUrl + '100', 'desc': _('Search for "%s", %s, %s %s') % (searchPattern, _(type), data[countKey], _(self.ITEMS_TYPE_MAP[type]))})
                    subItems.append(params)
                countDesc.append(_('%s ' + self.ITEMS_TYPE_MAP[type]) % (data[countKey]))
            except Exception:
                printExc()
                continue

            if len(subItems):
                params = dict(baseItem)
                params.update({'category': 'sub_items', 'title': _(type.upper()), 'desc': ', '.join(countDesc), 'sub_items': subItems})
                self.addDir(params)

    def listSearchItems(self, cItem):
        printDBG("PlayRTSIW.listSearchItems cItem[%s]" % (cItem))
        type = self.ITEMS_TYPE_MAP[cItem.get('f_type', 'tv')]
        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return
        try:
            data = byteify(json.loads(data))
            self._listItems(cItem, data[type])

            nextPage = self.getFullUrl(data['nextPageUrl'])
            if nextPage != '':
                params = dict(cItem)
                params.update({'good_for_fav': False, 'title': _('Next page'), 'url': nextPage})
                self.addDir(params)
        except Exception:
            printExc()

    def listSearchShows(self, cItem, nextCategory):
        printDBG("PlayRTSIW.listSearchShows cItem[%s]" % (cItem))
        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return
        try:
            data = byteify(json.loads(data))
            params = dict(cItem)
            params['category'] = nextCategory
            self._listShows(params, data['shows'])
        except Exception:
            printExc()

    def getLinksForVideo(self, cItem):
        printDBG("PlayRTSIW.getLinksForVideo [%s]" % cItem)
        linksTab = []

        if 'popup_url' not in cItem:
            sts, data = self.cm.getPage(cItem['url'])
            if not sts:
                return []
            url = self.cm.ph.getSearchGroups(data, '''ATR\.stream\s*?=\s*?\{[^\}]*?['"](https?://[^'^"]+?)['"]''')[0]
            if url != '':
                linksTab.append({'name': 'stream', 'url': url, 'need_resolve': 0})
            return linksTab

        if 'download_sd_url' in cItem:
            linksTab.append({'url': cItem['download_sd_url'], 'name': _('Download %s') % 'SD', 'need_resolve': 0})
        if 'download_hd_url' in cItem:
            linksTab.append({'url': cItem['download_hd_url'], 'name': _('Download %s') % 'HD', 'need_resolve': 0})

        if '/tv/' in cItem['popup_url']:
            if 'url_to_player' in cItem:
                url = cItem['url_to_player']
            else:
                url = cItem['popup_url'].replace('/tv/popupvideoplayer?', '/v2/tv/popupvideoplayer/content?')
            mediaType = 'VIDEO'
            progressType = 'mp4'
        else:
            url = cItem['popup_url'].replace('/radio/popupaudioplayer?', '/v2/radio/popupaudioplayer/content?')
            mediaType = 'AUDIO'
            progressType = 'mp3'

        if '/tp.' not in url:
            sts, data = self.cm.getPage(url)
            if not sts:
                return []
            url = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0]).replace('&amp;', '&')

        baseUrl = self.cm.getBaseUrl(url)
        urn = self.cleanHtmlStr(self.cm.ph.getSearchGroups(url + '&', '''urn=([^&]+?)&''')[0])
        url = baseUrl.replace('/tp.', '/il.') + 'integrationlayer/2.0/mediaComposition/byUrn/{0}.json?onlyChapters=true&vector=portalplay'.format(urn)
        tokenUrl = baseUrl + 'akahd/token?acl='
        sts, data = self.cm.getPage(url)
        try:
            data = byteify(json.loads(data))
            for item in data['chapterList']:
                printDBG("> mediaType[%s] [%s]" % (item['mediaType'], mediaType))
                if item['mediaType'] == mediaType:
                    data = item['resourceList']
                    break
            printDBG(">")
            printDBG(data)
            printDBG("<")
            for item in data:
                mimeType = item['mimeType'].split('/', 1)[-1].lower()
                if mimeType == 'x-mpegurl':
                    mimeType = 'HLS'
                elif mimeType == progressType:
                    mimeType = mimeType.upper()
                elif 'rtmp' in item['protocol'].lower():
                    mimeType = mimeType.upper()
                elif mimeType == 'mpeg':
                    mimeType = mimeType.upper()
                else:
                    continue
                n = item['url'].split('/')
                url = strwithmeta(item['url'], {'priv_token_url': tokenUrl + '%2F{0}%2F{1}%2F*'.format(n[3], n[4]), 'priv_type': mimeType.lower()})
                name = '[%s/%s] %s' % (mimeType, url.split('://', 1)[0].upper(), item['quality'])
                params = {'name': name, 'url': url, 'need_resolve': 1}
                if item['quality'].upper() == 'HD':
                    linksTab.append(params)
                else:
                    linksTab.insert(0, params)
        except Exception:
            printExc()

        return linksTab[::-1]

    def getVideoLinks(self, videoUrl):
        printDBG("PlayRTSIW.getVideoLinks [%s]" % videoUrl)
        meta = strwithmeta(videoUrl).meta
        tokenUrl = meta['priv_token_url']
        type = meta['priv_type']

        sts, data = self.cm.getPage(tokenUrl)
        try:
            data = byteify(json.loads(data))['token']['authparams']
            if '?' not in videoUrl:
                videoUrl += '?' + data
            else:
                videoUrl += '&' + data
        except Exception:
            printExc()

        urlTab = []
        if type == 'hls':
            urlTab = getDirectM3U8Playlist(videoUrl, checkContent=True, sortWithMaxBitrate=999999999)
        else:
            urlTab.append({'name': 'direct', 'url': videoUrl})
        return urlTab

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
            self.listMainMenu({'name': 'category'}, 'type', 'portal')
        elif category == 'type':
            self.listType(self.currItem)
        elif category == 'radio_channels':
            self.listRadioChannels(self.currItem, 'portal')
        elif category == 'portal':
            self.listPortalMain(self.currItem)
        elif category == 'list_cats':
            self.listCats(self.currItem, 'sub_items', 'list_teaser_items')
        elif category == 'sub_items':
            self.listSubItems(self.currItem)
        elif category == 'list_teaser_items':
            self.listTeaserItems(self.currItem)
        elif category == 'list_days':
            self.listDays(self.currItem, 'list_teaser_items')
        elif category == 'list_az':
            self.listAZ(self.currItem, 'list_az_items')
        elif category == 'list_az_items':
            self.listAZItems(self.currItem, 'list_episodes')
        elif category == 'list_episodes':
            self.listEpisodes(self.currItem)
        elif category == 'search_items':
            self.listSearchItems(self.currItem)
        elif category == 'search_shows':
            self.listSearchShows(self.currItem, 'list_episodes')
        elif category == 'list_live':
            self.listLiveChannels(self.currItem)
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
        CHostBase.__init__(self, PlayRTSIW(), True, [])

    def getSearchTypes(self):
        searchTypesOptions = []
        for item in self.host.PLAYER_MAP:
            searchTypesOptions.append((item.upper(), item.upper()))
        return searchTypesOptions
