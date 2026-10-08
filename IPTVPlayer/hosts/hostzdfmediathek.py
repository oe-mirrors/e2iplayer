# -*- coding: utf-8 -*-
# Last Modified: 07.10.2026
# 07.10.2026 - INFO (document details, moviemeta for films and
# series), First/Jump/Next paging (A-Z, search), "Show - SxxExx" / "Title (Year)"
# from the season/episode numbers and production year, watched key per season
# cluster, default user agent, search term url-quoted.
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import normalizeMediathekTitle
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.p2p3.pVer import isPY2

###################################################
# FOREIGN import
###################################################
from Components.config import config, ConfigSelection, ConfigYesNo, getConfigListEntry
from datetime import datetime, timedelta
import re
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


class ZDFmediathek(GenericFolderWatchedScraperMixin, CBaseHostClass):
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
        self.HEADER = {'User-Agent': self.cm.getDefaultUserAgent(), 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}

        # NOTE: MAIN_CAT_TAB is a class attribute - build a fresh instance list,
        # otherwise "+=" mutates the shared class list on every re-instantiation
        # and the search block piles up (4x etc.)
        self.MAIN_CAT_TAB = list(ZDFmediathek.MAIN_CAT_TAB) + self.searchItems()

        self.watchedHelper = IPTVWatchedHelper('zdfmediathek')
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    # list_content carries inline 'content', no own url - dict(cItem) leaves the
    # enclosing cluster's url on it, which would collide with that cluster's key
    WF_SKIP_CATEGORIES = ('list_start', 'list_live', 'list_content', 'missed_date',
                          'list_brands_az', 'kinder', 'search', 'search_next_page', 'search_history')

    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict) or cItem.get('live'):
                return ''
            itemType = cItem.get('type', '')
            if itemType == 'video':
                vid = str(cItem.get('id', '') or '').strip()
                if vid:
                    return 'video:id:%s' % vid
                url = self.wfNormalizeUrlKey(cItem.get('url', ''))
                return 'video:%s' % url if url else ''
            if itemType in ('audio', 'more', 'marker'):
                return ''
            if cItem.get('search_item') or cItem.get('name') == 'history':
                return ''
            if cItem.get('category', '') == 'list_content' and cItem.get('content_key'):
                # a season cluster of a programme ("Staffel 25 - alle verfuegbaren Folgen")
                return cItem['content_key']
            if cItem.get('category', '') in self.WF_SKIP_CATEGORIES:
                return ''
            url = self.wfNormalizeUrlKey(cItem.get('url', ''))
            return 'folder:%s' % url if url else ''
        except Exception:
            printExc()
        return ''

    def getPage(self, url, params=None, post_data=None):
        params = dict(params or {})
        params['header'] = dict(self.HEADER)

        sts, data = self.cm.getPage(url, params, post_data)
        if sts and None is data:
            sts = False
        if sts and 'Duze obciazenie!' in data:
            SetIPTVPlayerLastHostError(self.cleanHtmlStr(data))
        return sts, data

    def getIconUrl(self, url):
        return self.getFullUrl(url)

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
                for key in ('content_key', 'meta_type', 'meta_title', 'meta_year', 'zdf_type'):
                    params.pop(key, None)
                params.update({'category': 'list_content', 'title': title, 'content': tab})
                if cItem.get('category') == 'list_cluster' and cItem.get('url') and item.get('name'):
                    params['content_key'] = 'folder:%s#%s' % (self.wfNormalizeUrlKey(cItem['url']), self.cleanHtmlStr(item['name']))
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
            nodePath = item.get('structureNodePath') or ''
            if item['type'] in ['brand', 'category', 'topic']:
                params = {'name': 'category', 'category': 'list_cluster', 'title': title, 'url': self.getFullUrl(item.get('url', '')), 'desc': ' | '.join(descTab), 'icon': self.getIconUrl(icon), 'id': item.get('id', ''), 'sharing_url': item.get('sharingUrl', ''), 'good_for_fav': True,
                          'zdf_type': item['type']}
                if not params['url']:
                    return
                if item['type'] == 'brand' and nodePath.startswith('/zdf/serien/'):
                    params.update({'meta_type': 'tv', 'meta_title': title})
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
                if item['type'] == 'livevideo':
                    params['live'] = True
                    if params['id']:
                        # all channels share the day's "live-tv" url: the channel's own document
                        # (favourite / download marker identity)
                        params['url'] = self.DOCUMENT_API_URL % params['id']
                else:
                    params['title'] = self._mediaTitle(item, title)
                    if '/filme/' in nodePath and not item.get('seasonNumber'):
                        params.update({'meta_type': 'movie', 'meta_title': self.cleanHtmlStr(item.get('brandTitle') or '') or self._stripPartNo(title),
                                       'meta_year': self._productionYear(item)})
                self.addVideo(params)
        except Exception:
            printExc()

    @staticmethod
    def _stripPartNo(title):
        # "Die Rebellin (1/3)" -> "Die Rebellin"
        return re.sub(r'\s*\(\d+/\d+\)\s*$', '', title) or title

    @staticmethod
    def _productionYear(item):
        year = str((((item.get('contentAttributes') or {}).get('productionYear') or {}).get('title')) or '').strip()
        return year[:4] if year[:4].isdigit() else ''

    @staticmethod
    def _isoDate(value):
        # "05.10.2026 20:15" -> "2026-10-05" (what normalizeMediathekTitle expects)
        m = re.match(r'(\d{2})\.(\d{2})\.(\d{4})', str(value or ''))
        return '%s-%s-%s' % (m.group(3), m.group(2), m.group(1)) if m else str(value or '')

    def _mediaTitle(self, item, title):
        # "Show - SxxExx - Episode" for numbered episodes, "Title (Year)" for films,
        # "Title (date)" otherwise - only with media naming normalisation on
        show = self.cleanHtmlStr(item.get('brandTitle') or item.get('headline') or '')
        try:
            season, episode = int(item.get('seasonNumber') or 0), int(item.get('episodeNumber') or 0)
        except (TypeError, ValueError):
            season, episode = 0, 0
        # documentary series number their "seasons" by year (2026): those get the date instead
        if season and episode and show and season < 1900:
            # "Tatort: Das Opfer" -> "Tatort - SxxExx - Das Opfer"
            rest = re.sub(r'^%s\s*[:|-]\s*' % re.escape(show), '', title, flags=re.I).strip()
            base = '%s - %s' % (show, rest) if rest and rest.lower() != show.lower() else show
            named = normalizeMediathekTitle(base, sxeHint='S%02dE%02d' % (season, episode))
            return named if named != base else title
        year = self._productionYear(item)
        if year and '/filme/' in (item.get('structureNodePath') or ''):
            return normalizeMediathekTitle(title, year=year, isMovie=True)
        attrDate = ((item.get('contentAttributes') or {}).get('editorialDate') or {}).get('title')
        date = item.get('editorialDate') or attrDate or item.get('airtimeBegin') or item.get('onlineDate') or ''
        return normalizeMediathekTitle(
            title, date=self._isoDate(date),
            sxeHint='%s %s' % (self.cleanHtmlStr(item.get('headline', '') or ''), title))

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
        if cItem.get('url'):
            url = cItem['url']  # a pager row
        else:
            letter = cItem.get('letter', 'A')
            query = '0' if letter == '0-9' else letter
            url = self.SEARCH_API_URL % (urllib_quote(query), 'brand')
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
            self._addPaging(cItem, data)
        except Exception:
            printExc()

    def _addPaging(self, cItem, data):
        # search answers: nextPage / nextPageUrl ("...&page=N") / totalResultsCount
        nextUrl = self.getFullUrl(data.get('nextPageUrl') or '') if data.get('nextPage') else ''
        tplSrc = nextUrl or cItem.get('url', '')
        if not re.search(r'[?&]page=\d+', tplSrc):
            tplSrc = ''
        tpl = re.sub(r'([?&]page=)\d+', r'\g<1>{page}', tplSrc) if tplSrc else ''
        m = re.search(r'[?&]page=(\d+)', cItem.get('url', '') or '')
        page = int(m.group(1)) if m else 1
        lastPage = 0
        try:
            perPage = len(data.get('results') or [])
            total = int(data.get('totalResultsCount') or 0)
            if nextUrl and perPage and total:
                lastPage = (total + perPage - 1) // perPage
        except (TypeError, ValueError):
            pass
        if tpl:
            addPagingItems(self, cItem, page, bool(nextUrl), lastPage, tpl)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("ZDFmediathek.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        if cItem.get('url'):
            url = cItem['url']  # a pager row
        else:
            url = self.SEARCH_API_URL % (urllib_quote(searchPattern), 'episode')

        sts, data = self.getPage(url)
        if not sts:
            return
        try:
            data = json_loads(data)
            for item in data.get('results') or []:
                self._addItem(cItem, item)
            self._addPaging(cItem, data)
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
            synopsis = self.cleanHtmlStr(data.get('beschreibung') or data.get('leadParagraph') or '')
            try:
                for item in data.get('captions') or []:
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
                    # keep the https URLs ZDF actually serves - the old
                    # 'http' + url[5:] downgrade was a workaround for ancient
                    # enigma2 images that could not do TLS to the Akamai CDN;
                    # modern images do, and the CDN answers both schemes.
                    for type in [{'pattern': 'm3u8', 'name': 'm3u8'}, {'pattern': 'mp4_', 'name': 'mp4'}]:
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
                                res = tmpItem.get('with', 0)
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
            if not isLive:
                urlTab = applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled(), synopsis))
            printDBG(tmpUrlTab)
        except Exception:
            printExc()

        return urlTab

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG('ZDFmediathek.getArticleContent [%s]' % cItem.get('url', ''))
        text, icon, info = cItem.get('desc', ''), cItem.get('icon', ''), {}
        url = cItem.get('url', '')
        if cItem.get('type') == 'video' and cItem.get('id') and '/mediathekV2/document/' not in url:
            url = self.DOCUMENT_API_URL % cItem['id']
        doc = {}
        if '/mediathekV2/document/' in url:
            sts, data = self.getPage(url)
            if sts:
                try:
                    data = json_loads(data)
                    doc = data.get('document') or {}
                    if not doc.get('beschreibung') and data.get('shortText'):
                        doc = dict(doc, beschreibung=(data['shortText'] or {}).get('text') or '')
                except Exception:
                    printExc()
        if doc:
            desc = self.cleanHtmlStr(doc.get('beschreibung') or doc.get('leadParagraph') or '')
            text = desc or text
            try:
                if int(doc.get('length') or 0) > 0:
                    info['duration'] = str(timedelta(seconds=int(doc['length'])))
            except (TypeError, ValueError):
                pass
            if doc.get('channel'):
                info['station'] = self.cleanHtmlStr(doc['channel'])
            fsk = str(doc.get('fsk') or '')
            m = re.search(r'(\d+)', fsk)
            if m and m.group(1) != '0':
                info['age_limit'] = '%s+' % m.group(1)
            airtime = self._isoDate(doc.get('airtime') or '')
            if re.match(r'\d{4}-\d{2}-\d{2}', airtime):
                info['broadcast'] = airtime
            avail = self._isoDate(doc.get('timetolive') or '')
            if re.match(r'\d{4}-\d{2}-\d{2}', avail):
                info['remaining'] = _('available until %s') % avail[:10]
        meta = {}
        if cItem.get('meta_type') and cItem.get('meta_title'):
            try:
                # the year must match: the title search also finds other films of the same name
                # (German TV film "Die Rebellin" 2008 -> "Rebelle" 2012)
                meta = getMeta(cItem['meta_type'], cItem['meta_title'], cItem.get('meta_year', ''), maxYearDiff=1)
            except Exception:
                printExc()
        if cItem.get('meta_year'):
            info.setdefault('year', cItem['meta_year'])
        # the site's German texts first, the service adds ratings, cast and the poster
        for key, value in (meta.get('info') or {}).items():
            info.setdefault(key, value)
        text = text or meta.get('plot', '')
        icon = meta.get('poster') or icon
        return [{'title': cItem.get('title', ''), 'text': text, 'images': [{'title': '', 'url': icon}] if icon else [], 'other_info': info}]

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('ZDFmediathek.handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
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


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, ZDFmediathek(), True)
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('zdfmediathek')

    def withArticleContent(self, cItem):
        return cItem.get('type') == 'video' or (cItem.get('category') == 'list_cluster' and cItem.get('zdf_type') == 'brand')
