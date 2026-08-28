# -*- coding: utf-8 -*-
# Last Modified: 14.06.2025
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_unquote
from Plugins.Extensions.IPTVPlayer.p2p3.pVer import isPY2

###################################################
# FOREIGN import
###################################################
from Components.config import config, ConfigSelection, ConfigYesNo, getConfigListEntry
from datetime import datetime, timedelta
import time
if not isPY2():
    from functools import cmp_to_key
###################################################


###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.zdfmediathek_iconssize = ConfigSelection(default="medium", choices=[("large", _("large")), ("medium", _("medium")), ("small", _("small"))])
config.plugins.iptvplayer.zdfmediathek_prefformat = ConfigSelection(default="mp4,m3u8", choices=[
("mp4,m3u8", "mp4,m3u8"), ("m3u8,mp4", "m3u8,mp4")])
config.plugins.iptvplayer.zdfmediathek_prefquality = ConfigSelection(default="4", choices=[("0", _("low")), ("1", _("medium")), ("2", _("high")), ("3", _("very high")), ("4", _("hd"))])
config.plugins.iptvplayer.zdfmediathek_prefmoreimportant = ConfigSelection(default="quality", choices=[("quality", _("quality")), ("format", _("format"))])
config.plugins.iptvplayer.zdfmediathek_onelinkmode = ConfigYesNo(default=True)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Icons size"), config.plugins.iptvplayer.zdfmediathek_iconssize))
    optionList.append(getConfigListEntry(_("Prefered format"), config.plugins.iptvplayer.zdfmediathek_prefformat))
    optionList.append(getConfigListEntry(_("Prefered quality"), config.plugins.iptvplayer.zdfmediathek_prefquality))
    optionList.append(getConfigListEntry(_("More important"), config.plugins.iptvplayer.zdfmediathek_prefmoreimportant))
    optionList.append(getConfigListEntry(_("One link mode"), config.plugins.iptvplayer.zdfmediathek_onelinkmode))
    return optionList
###################################################


def gettytul():
    return 'ZDFmediathek'


class ZDFmediathek(CBaseHostClass):
    HOST = 'Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.9.2.18) Gecko/20110621 Mandriva Linux/1.9.2.18-0.1mdv2010.2 (2010.2) Firefox/3.6.18'
    HEADER = {'User-Agent': HOST, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}
    AJAX_HEADER = dict(HEADER)
    AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Connection': 'keep-alive', 'Pragma': 'no-cache', 'Cache-Control': 'no-cache'})

    MAIN_URL = 'https://www.zdf.de/'
    MAIN_API_URL = 'https://zdf-prod-futura.zdf.de/'
    ZDF_API_URL = 'https://api.zdf.de/'
    DOCUMENT_API_URL = MAIN_API_URL + 'mediathekV2/document/%s'
    BROADSCAST_MISSED_API_URL = MAIN_API_URL + 'mediathekV2/broadcast-missed/%s'
    TYPEAHEAD_API_URL = MAIN_API_URL + 'mediathekV2/search/typeahead?q=%s&context=%s'
    SEARCH_API_URL = MAIN_API_URL + 'mediathekV2/search?q=%s&contentTypes=%s'
    START_PAGE_API_URL = MAIN_API_URL + 'mediathekV2/start-page'
    IMPRINT_PAGE_API_URL = MAIN_API_URL + 'mediathekV2/page/imprint'
    CONTACT_PAGE_API_URL = MAIN_API_URL + 'mediathekV2/page/contact'
    PRIVACY_PAGE_API_URL = MAIN_API_URL + 'mediathekV2/page/privacy'
    CATEGORIES_PAGE_API_URL = MAIN_API_URL + 'mediathekV2/categories'
    MYZDF_API_URL = MAIN_API_URL + 'mediathekV2/user/my-zdf'
    CLIP_GROUP_API_URL = MAIN_API_URL + 'mediathek/champions-league/match/%s/clip-group/%s'
    LOGIN_URL = ZDF_API_URL + 'identity/login'
    LOGIN_FACEBOOK_URL = ZDF_API_URL + 'identity/thirdparty/facebook/login'
    LOGIN_GOOGLE_URL = ZDF_API_URL + 'identity/thirdparty/google/login'
    REGISTER_URL = MAIN_URL + 'mein-zdf#start'
    SUBSCRIPTIONS_API_URL = MAIN_API_URL + 'mediathekV2/user/subscriptions'
    PUSH_SUBSCRIBE_URL = 'http://push.live.cellular.de/api/device/'
    BOOKMARKS_API_URL = MAIN_API_URL + 'mediathekV2/user/bookmarks'
    AUTH_TOKEN_API_URL = MAIN_API_URL + 'mediathekV2/token'
    AKAMAI_TOKEN_API_URL = 'https://tg2cl15.zdf.de/generate'

    MAIN_CAT_TAB = [{'category': 'list_start', 'title': _('Home page'), 'url': START_PAGE_API_URL},
                    {'category': 'list_live', 'title': _('Live')},
                    {'category': 'missed_date', 'title': _('Missed the show?')},
                    {'category': 'list_brands_az', 'title': _('Program A-Z')},
                    {'category': 'list_cluster', 'title': _('Categories'), 'url': CATEGORIES_PAGE_API_URL},
                    # {'category':'themen',         'title':_('Topics'), 'url': NEWS_API_URL},
                    {'category': 'kinder', 'title': _('Children')}]

    QUALITY_MAP = {'hd': 4, 'veryhigh': 3, 'high': 2, 'med': 1, 'low': 0}

    def __init__(self):
        printDBG("ZDFmediathek.__init__")
        CBaseHostClass.__init__(self, {'history': 'ZDFmediathek.tv', 'cookie': 'zdfde.cookie'})
        self.DEFAULT_ICON_URL = 'https://brandguide.zdf.de/pictures/447/2f865620700065672dbce9582f77ad83569beb7f/ZDF_DE_Logo_02.png'


        # NOTE: MAIN_CAT_TAB is a class attribute - build a fresh instance list,
        # otherwise "+=" mutates the shared class list on every re-instantiation
        # and the search block piles up (4x etc.)
        self.MAIN_CAT_TAB = list(ZDFmediathek.MAIN_CAT_TAB) + self.searchItems()

    def getPage(self, url, params={}, post_data=None):
        HTTP_HEADER = dict(self.HEADER)
        params.update({'header': HTTP_HEADER})

        if 'zdf-cdn.live.cellular.de' in url and False:
            proxy = 'http://www.proxy-german.de/index.php?q={0}&hl=2e1'.format(urllib_quote(url, ''))
            params['header']['Referer'] = proxy
            # params['header']['Cookie'] = 'flags=2e5;'
            url = proxy
        sts, data = self.cm.getPage(url, params, post_data)
        if sts and None is data:
            sts = False
        if sts and 'Duze obciazenie!' in data:
            SetIPTVPlayerLastHostError(self.cleanHtmlStr(data))
        return sts, data

    def getIconUrl(self, url):
        url = self.getFullUrl(url)
        if 'zdf-cdn.live.cellular.de' in url and False:
            proxy = 'http://www.proxy-german.de/index.php?q={0}&hl=2e1'.format(urllib_quote(url, ''))
            params = {}
            params['User-Agent'] = self.HEADER['User-Agent'],
            params['Referer'] = proxy
            params['Cookie'] = 'flags=2e5;'
            url = strwithmeta(proxy, params)
        elif url.startswith('https://'):
            url = 'http' + url[5:]

        return url

    def getFullUrl(self, url):
        if 'proxy-german.de' in url:
            url = urllib_unquote(self.cm.ph.getSearchGroups(url + '&', r'''\?q=(http[^&]+?)&''')[0])
        return CBaseHostClass.getFullUrl(self, url)

    def _getNum(self, v, default=0):
        try:
            return int(v)
        except Exception:
            try:
                return float(v)
            except Exception:
                return default

    def _getList(self, data, key, default=[]):
        try:
            if isinstance(data[key], list):
                return data[key]
        except Exception:
            printExc()
        return default

    def _getIcon(self, iconsItem):
        iconssize = config.plugins.iptvplayer.zdfmediathek_iconssize.value
        iconsTab = []
        for item in list(iconsItem.keys()):
            item = iconsItem[item]
            if "/assets/" in item["url"]:
                iconsTab.append({'size': item["width"], 'url': item["url"]})
        idx = len(iconsTab)
        if idx:
            iconsTab.sort(key=lambda k: k['size'])
            if 'large' == iconssize:
                idx -= 1
            elif 'medium' == iconssize:
                idx /= 2
            elif 'small' == iconssize:
                idx = 0
            return iconsTab[int(idx)]['url']
        return ''

    def listStart(self, cItem):
        printDBG('listStart')
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        try:
            data = json_loads(data)
            for item in data['stage']:
                self._addItem(cItem, item)
            self._listCluster(cItem, data['cluster'])
        except Exception:
            printExc()

    def listSendungverpasst(self, cItem):
        printDBG('listSendungverpasst')
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        try:
            data = json_loads(data)['broadcastCluster']
            self._listCluster(cItem, data)
        except Exception:
            printExc()

    def listCluster(self, cItem):
        printDBG('listCluster')
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        try:
            data = json_loads(data)['cluster']
            self._listCluster(cItem, data)
        except Exception:
            printExc()

    def _listCluster(self, cItem, data):
        for item in data:

            if 'teaser' in item['type']:
                tab = self._getList(item, 'teaser')
                if 0 == len(tab):
                    continue
                if 1 == len(tab) and cItem.get('simplify', True):
                    self._addItem(cItem, tab[0])
                    continue
                title = self.cleanHtmlStr(item['type'])
                if 'name' in item:
                    title = self.cleanHtmlStr(item['name'])
                elif 'teaserLivevideo' == item['type']:
                    title = _('Live')
                params = dict(cItem)
                params.update({'category': 'list_content', 'title': title, 'content': tab})
                self.addDir(params)

    def listContent(self, cItem):
        printDBG('listCluster')
        contentTab = cItem.get('content', [])
        for item in contentTab:
            self._addItem(cItem, item)

    def _addItem(self, cItem, item):
        printDBG('_addItem')
        try:
            if not isinstance(item, dict) or not item.get('titel'):
                return
            icon = self._getIcon(item.get("teaserBild", {}))
            if icon == '':
                icon = cItem.get('icon', '')
            title = self.cleanHtmlStr(item["titel"])
            descTab = [self.cleanHtmlStr(item.get(k, '')) for k in ('headline', 'channel', 'beschreibung')]
            descTab = [x for x in descTab if x]
            if item['type'] in ['brand', 'category', 'topic']:
                params = {'name': 'category', 'category': 'list_cluster', 'title': title, 'url': self.getFullUrl(item.get('url', '')), 'desc': ' | '.join(descTab), 'icon': self.getIconUrl(icon), 'id': item.get('id', ''), 'sharing_url': item.get('sharingUrl', ''), 'good_for_fav': True}
                if not params['url']:
                    return
                self.addDir(params)
            elif item['type'] in ["video", "livevideo"]:
                if 'length' in item and item.get('length'):
                    try:
                        descTab.insert(1, str(timedelta(seconds=int(item["length"]))))
                    except Exception:
                        pass
                params = {'title': title, 'url': self.getFullUrl(item.get('url', '')), 'desc': ' | '.join(descTab), 'icon': self.getIconUrl(icon), 'id': item.get('id', ''), 'sharing_url': item.get('sharingUrl', ''), 'good_for_fav': True}
                if not params['url'] and not params['id']:
                    return
                self.addVideo(params)
        except Exception:
            printExc()

    def listMissedDate(self, cItem):
        printDBG("listMissedDate")
        # convert to timestamp
        now = int(time.time())
        for item in range(7):
            date = datetime.fromtimestamp(now - item * 24 * 3600).strftime('%Y-%m-%d')
            params = dict(cItem)
            params.update({'category': 'list_missed', 'title': date, 'url': self.BROADSCAST_MISSED_API_URL % date})
            self.addDir(params)

    def listLive(self, cItem):
        printDBG('listLive')
        sts, data = self.getPage(self.START_PAGE_API_URL)
        if not sts:
            return
        cItem = dict(cItem)
        cItem.setdefault('icon', self.DEFAULT_ICON_URL)
        try:
            data = json_loads(data)
            for cluster in data.get('cluster', []):
                if cluster.get('type') == 'teaserLivevideo':
                    for item in self._getList(cluster, 'teaser'):
                        self._addItem(cItem, item)
        except Exception:
            printExc()

    def listBrandsAZ(self, cItem):
        printDBG('listBrandsAZ')
        for letter in list('ABCDEFGHIJKLMNOPQRSTUVWXYZ') + ['0-9']:
            params = dict(cItem)
            params.pop('page', None)
            params.pop('url', None)
            params.update({'category': 'list_brands', 'title': letter, 'letter': letter, 'icon': self.DEFAULT_ICON_URL})
            self.addDir(params)

    def listBrands(self, cItem):
        printDBG('listBrands')
        page = cItem.get('page', 0)
        if page == 0:
            letter = cItem.get('letter', 'A')
            query = '0' if letter == '0-9' else letter
            url = self.SEARCH_API_URL % (urllib_quote(query), 'brand')
        else:
            url = cItem['url']
        kids = bool(cItem.get('f_kids'))
        sts, data = self.getPage(url)
        if not sts:
            return
        try:
            data = json_loads(data)
            for item in data.get('results', []):
                if item.get('type') not in ('brand', 'topic'):
                    continue
                if kids and item.get('channel') != 'KI.KA' and '/kinder/' not in (item.get('sharingUrl') or ''):
                    continue
                self._addItem(cItem, item)
            if data.get('nextPage'):
                params = dict(cItem)
                params.update({'title': _('Next page'), 'url': self.getFullUrl(data['nextPageUrl']), 'page': page + 1})
                self.addDir(params)
        except Exception:
            printExc()

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("ZDFmediathek.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        page = cItem.get('page', 0)
        if page == 0:
            url = self.SEARCH_API_URL % (searchPattern, 'episode')
        else:
            url = cItem['url']

        sts, data = self.getPage(url)
        if not sts:
            return
        try:
            data = json_loads(data)
            for item in data['results']:
                self._addItem(cItem, item)
            if data['nextPage']:
                params = dict(cItem)
                params.update({'title': _('Next page'), 'url': self.getFullUrl(data['nextPageUrl']), 'page': page + 1})
                self.addDir(params)
        except Exception:
            printExc()

    def getLinksForVideo(self, cItem):
        printDBG("ZDFmediathek.getLinksForVideo [%s]" % cItem)

        if 'id' not in cItem and 'url' in cItem:
            sts, data = self.getPage(cItem['url'])
            if not sts:
                return []
            id = self.cm.ph.getSearchGroups(data, r'''['"]?docId['"]?\s*:\s*['"]([^'^"]+?)['"]''')[0]
        else:
            id = cItem['id']

        sts, data = self.getPage(self.DOCUMENT_API_URL % id)
        if not sts:
            return []

        preferedQuality = int(config.plugins.iptvplayer.zdfmediathek_prefquality.value)
        preferedFormat = config.plugins.iptvplayer.zdfmediathek_prefformat.value
        tmp = preferedFormat.split(',')
        formatMap = {}
        for i in range(len(tmp)):
            formatMap[tmp[i]] = i

        try:
            subTracks = []
            urlTab = []
            tmpUrlTab = []
            data = json_loads(data)['document']
            try:
                for item in data['captions']:
                    if 'vtt' in item['format'] and self.cm.isValidUrl(item['uri']):
                        subTracks.append({'title': item['language'], 'url': item['uri'], 'lang': item['language'], 'format': 'vtt'})
            except Exception:
                printExc()

            live = data['type']
            isLive = 'live' in str(live).lower()
            try:
                data = data['formitaeten']
                for item in data:
                    quality = item['quality']
                    url = item['url']
                    if url.startswith('https://'):
                        url = 'http' + url[5:]
                    for type in [{'pattern': 'http_m3u8_http', 'name': 'm3u8'}, {'pattern': 'mp4_http', 'name': 'mp4'}]:
                        if type['pattern'] not in item['type']:
                            continue
                        if type['name'] == 'mp4':
                            if item['hd']:
                                quality = 'hd'
                            qualityVal = ZDFmediathek.QUALITY_MAP.get(quality, 10)
                            qualityPref = abs(qualityVal - preferedQuality)
                            formatPref = formatMap.get(type['name'], 10)
                            tmpUrlTab.append({'url': url, 'quality_name': quality, 'quality': qualityVal, 'quality_pref': qualityPref, 'format_name': type['name'], 'format_pref': formatPref})
                        elif type['name'] == 'm3u8' and isLive:
                            # live master playlists have separate audio rendition groups -
                            # hand the master straight to the player, don't pre-resolve
                            # (otherwise a video-only variant is picked -> picture but no sound)
                            tmpUrlTab.append({'url': url, 'quality_name': 'auto', 'quality': 10, 'quality_pref': 0,
                                              'format_name': 'm3u8', 'format_pref': formatMap.get('m3u8', 10)})
                        elif type['name'] == 'm3u8':
                            tmpList = getDirectM3U8Playlist(strwithmeta(url, {'iptv_proto': 'm3u8'}), checkExt=False)
                            for tmpItem in tmpList:
                                res = tmpItem['with']
                                if res == 0:
                                    continue
                                if res > 300:
                                    quality = 'low'
                                if res > 600:
                                    quality = 'med'
                                if res > 800:
                                    quality = 'high'
                                if res > 1000:
                                    quality = 'veryhigh'
                                if res > 1200:
                                    quality = 'hd'
                                qualityVal = ZDFmediathek.QUALITY_MAP.get(quality, 10)
                                qualityPref = abs(qualityVal - preferedQuality)
                                formatPref = formatMap.get(type['name'], 10)
                                tmpUrlTab.append({'url': tmpItem['url'], 'quality_name': quality, 'quality': qualityVal, 'quality_pref': qualityPref, 'format_name': type['name'], 'format_pref': formatPref})
            except Exception:
                printExc()

            def _cmpLinks(it1, it2):
                prefmoreimportantly = config.plugins.iptvplayer.zdfmediathek_prefmoreimportant.value
                if 'quality' == prefmoreimportantly:
                    if it1['quality_pref'] < it2['quality_pref']:
                        return -1
                    elif it1['quality_pref'] > it2['quality_pref']:
                        return 1
                    else:
                        if it1['quality'] < it2['quality']:
                            return -1
                        elif it1['quality'] > it2['quality']:
                            return 1
                        else:
                            if it1['format_pref'] < it2['format_pref']:
                                return -1
                            elif it1['format_pref'] > it2['format_pref']:
                                return 1
                            else:
                                return 0
                else:
                    if it1['format_pref'] < it2['format_pref']:
                        return -1
                    elif it1['format_pref'] > it2['format_pref']:
                        return 1
                    else:
                        if it1['quality_pref'] < it2['quality_pref']:
                            return -1
                        elif it1['quality_pref'] > it2['quality_pref']:
                            return 1
                        else:
                            if it1['quality'] < it2['quality']:
                                return -1
                            elif it1['quality'] > it2['quality']:
                                return 1
                            else:
                                return 0
            if isPY2():
                tmpUrlTab.sort(_cmpLinks)
            else:
                tmpUrlTab.sort(key=cmp_to_key(_cmpLinks))
            onelinkmode = config.plugins.iptvplayer.zdfmediathek_onelinkmode.value
            for item in tmpUrlTab:
                url = item['url']
                name = item['quality_name'] + ' ' + item['format_name']
                if '' != url:
                    decorateParams = {'iptv_livestream': isLive, 'external_sub_tracks': subTracks}
                    if item['format_name'] == 'm3u8':
                        decorateParams['iptv_proto'] = 'm3u8'
                    urlTab.append({'need_resolve': 0, 'name': name, 'url': self.up.decorateUrl(url, decorateParams)})
                    if onelinkmode:
                        break
            printDBG(tmpUrlTab)
        except Exception:
            printExc()

        return urlTab

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('ZDFmediathek.handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", None)
        category = self.currItem.get("category", '')
        printDBG("ZDFmediathek.handleService: ---------> name[%s], category[%s] " % (name, category))
        searchPattern = self.currItem.get("search_pattern", searchPattern)
        self.currList = []

        if None is name:
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})
        elif 'kinder' == category:
            self.listBrandsAZ(dict(self.currItem, f_kids=True))
        elif 'list_start' == category:
            self.listStart(self.currItem)
        elif 'list_live' == category:
            self.listLive(self.currItem)
        elif 'missed_date' == category:
            self.listMissedDate(self.currItem)
        elif 'list_missed' == category:
            self.listSendungverpasst(self.currItem)
        elif 'list_cluster' == category:
            self.listCluster(self.currItem)
        elif 'list_brands_az' == category:
            self.listBrandsAZ(self.currItem)
        elif 'list_brands' == category:
            self.listBrands(self.currItem)
        elif 'list_content' == category:
            self.listContent(self.currItem)
    # WYSZUKAJ
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category', 'category': 'search_next_page'})
            self.listSearchResult(cItem, searchPattern, searchType)
    # HISTORIA WYSZUKIWANIA
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc')
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, ZDFmediathek(), True)
