# -*- coding: utf-8 -*-
# Last Modified: 10.10.2026
# 10.10.2026 - host standard: vod.tvp.pl catalogue with First page / Jump / Next page and the last page (it showed
#   only the first 100 titles), series -> seasons -> episodes (a series with one season lists its episodes),
#   watched flag (series -> season -> episode), downloaded marker, favourites (also the rows of the old version),
#   sidecar, INFO (moviemeta + the site's text), "Title (Year)" / "Show - SxxExx" naming; videos through the
#   current tokenizer (api.tvp.pl/tokenizer/token - the old tokenizer_v2.php answers 404, so TVP Sport and
#   "Rekonstrukcja cyfrowa" had no links), geo-blocked answers say so; TVP Sport categories without one request
#   per category, its lists page only where the site has more; no rate-limited Wikimedia logos, no own http patch
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import GetAlternativeProxyChoices, GetAlternativeProxyList, GetAlternativeProxyUrl, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.captcha_helper import CaptchaHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import CSelOneLink, printDBG, printExc, MergeDicts, readCFG, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import normalizeMediathekTitle, formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, getMPDLinksWithMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs import ph
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
###################################################
# FOREIGN import
###################################################
from Components.config import config, ConfigSelection, ConfigYesNo, ConfigText, getConfigListEntry, configfile
from Plugins.Extensions.IPTVPlayer.components.configsecret import ConfigLogin, ConfigSecret
from datetime import datetime, timedelta
import re
###################################################
config.plugins.iptvplayer.tvpvod_premium = ConfigYesNo(default=False)
config.plugins.iptvplayer.tvpvod_login = ConfigLogin(default=readCFG('tvpvod_login', ""), fixed_size=False)
config.plugins.iptvplayer.tvpvod_password = ConfigSecret(default=readCFG('tvpvod_password', ""), fixed_size=False)

config.plugins.iptvplayer.tvpvod_proxy = ConfigSelection(default="None", choices=GetAlternativeProxyChoices())
# legacy: the old yes/no switch used the "Polish proxy server" of the main settings, which is gone -
# both are only kept to move an existing setup over to one of the alternative proxies
config.plugins.iptvplayer.tvpVodProxyEnable = ConfigYesNo(default=False)
config.plugins.iptvplayer.proxyurl = ConfigText(default="http://user:pass@ip:port", fixed_size=False)  # NOSONAR
config.plugins.iptvplayer.tvpVodDefaultformat = ConfigSelection(default="9100000", choices=[("360000", "320x180"),
                                                                                               ("590000", "398x224"),
                                                                                               ("820000", "480x270"),
                                                                                               ("1250000", "640x360"),
                                                                                               ("1750000", "800x450"),
                                                                                               ("2850000", "960x540"),
                                                                                               ("3032000", "1024x576"),
                                                                                               ("5420000", "1280x720"),
                                                                                               ("6500000", "1600x900"),
                                                                                               ("9100000", "1920x1080")])
config.plugins.iptvplayer.tvpVodUseDF = ConfigYesNo(default=True)
config.plugins.iptvplayer.tvpVodPreferedformat = ConfigSelection(default="mp4", choices=[("mp4", "MP4"), ("m3u8", "HLS/m3u8"), ("mpd", "MPD")])

###################################################
# Config options for HOST
###################################################


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry("Strefa Widza", config.plugins.iptvplayer.tvpvod_premium))
    if config.plugins.iptvplayer.tvpvod_premium.value:
        optionList.append(getConfigListEntry("  %s:" % _("e-mail"), config.plugins.iptvplayer.tvpvod_login))
        optionList.append(getConfigListEntry("  %s:" % _("password"), config.plugins.iptvplayer.tvpvod_password))
    optionList.append(getConfigListEntry(_("Prefered format"), config.plugins.iptvplayer.tvpVodPreferedformat))
    optionList.append(getConfigListEntry(_("Default video quality:"), config.plugins.iptvplayer.tvpVodDefaultformat))
    optionList.append(getConfigListEntry(_("Use default video quality:"), config.plugins.iptvplayer.tvpVodUseDF))
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.tvpvod_proxy))
    return optionList


def _migrateLegacyProxy():
    # the old proxy address goes into a free (or already identical) alternative proxy slot; when all
    # slots hold other addresses it is dropped, the user has to pick one of them in the host settings
    cp = config.plugins.iptvplayer
    if not cp.tvpVodProxyEnable.value:
        return
    oldUrl = cp.proxyurl.value
    if oldUrl and oldUrl != cp.proxyurl.default:
        for slot, label, alt in GetAlternativeProxyList():
            if alt.value in (oldUrl, alt.default, ""):
                alt.value = oldUrl
                alt.save()
                cp.tvpvod_proxy.value = slot
                cp.tvpvod_proxy.save()
                printDBG("TvpVod: proxy setting moved to %s" % slot)
                break
        else:
            printDBG("TvpVod: all alternative proxy slots are in use, the old proxy setting was dropped")
    cp.tvpVodProxyEnable.value = False
    cp.tvpVodProxyEnable.save()
    cp.proxyurl.value = cp.proxyurl.default
    cp.proxyurl.save()
    configfile.save()


try:
    _migrateLegacyProxy()
except Exception:
    printExc()


def GetProxyUrl():
    return GetAlternativeProxyUrl(config.plugins.iptvplayer.tvpvod_proxy.value)
###################################################


def gettytul():
    return 'https://vod.tvp.pl/'


API_URL = 'https://vod.tvp.pl/api/'
API_PARAMS = 'lang=pl&platform=BROWSER'
TOKENIZER_URL = 'https://api.tvp.pl/tokenizer/token/%s'
CATALOG_PAGE_SIZE = 40
SPORT_PAGE_SIZE = 30
EPISODES_PAGE_SIZE = 100
PRODUCT_ID_RE = re.compile(r'/products/(\d+)/')
SXE_RE = re.compile(r',S(\d+)E(\d+),')


class TvpVod(GenericFolderWatchedScraperMixin, CBaseHostClass, CaptchaHelper):
    ALL_FORMATS = [{"video/mp4": "mp4"}, {"application/x-mpegurl": "m3u8"}, {"video/x-ms-wmv": "wmv"}]
    REAL_FORMATS = {'m3u8': 'ts', 'mp4': 'mp4', 'wmv': 'wmv'}
    LOGIN_URL = "https://user.tvp.pl/login.php?ref="
    ACCOUNT_URL = "https://user.tvp.pl/account.php"
    STREAMS_URL_TEMPLATE = 'http://www.api.v3.tvp.pl/shared/tvpstream/listing.php?parent_id=13010508&type=epg_item&direct=false&filter={%22release_date_dt%22:%22[iptv_date]%22,%22epg_play_mode%22:{%22$in%22:[0,1,3]}}&count=-1&dump=json'
    IMAGE_URL = 'http://s.v3.tvp.pl/images/%s/%s/%s/uid_%s_width_500_gs_0.%s'
    # stable identity of a row
    FAV_FIELDS = ('name', 'category', 'type', 'url', 'title', 'raw_title', 'icon', 'desc', 'f_asset', 'meta_type', 'meta_title', 'meta_year', 'date', 'live')

    VOD_CAT_TAB = [{'category': 'tvp_api', 'title': 'Seriale', 'id': '18'},
                   {'category': 'tvp_api', 'title': 'Filmy', 'id': '136'},
                   {'category': 'tvp_api', 'title': 'Programy', 'id': '88'},
                   {'category': 'tvp_api', 'title': 'Dokumenty', 'id': '163'},
                   {'category': 'tvp_api', 'title': 'Teatr', 'id': '202'},
                   {'category': 'tvp_api', 'title': 'News', 'id': '205'},
                   {'category': 'tvp_api', 'title': 'Dla dzieci', 'id': '24'},
                   {'category': 'tvp_sport', 'title': 'TVP Sport', 'url': 'https://sport.tvp.pl/wideo'},
                   {'category': 'streams', 'title': 'TVP na żywo', 'url': 'https://tvpstream.tvp.pl/'},
                   {'category': 'digi_menu', 'title': 'Rekonstrukcja cyfrowa TVP', 'url': 'https://cyfrowa.tvp.pl/'}]

    STREAMS_CAT_TAB = [{'category': 'tvp3_streams', 'title': 'TVP 3', 'url': 'https://tvpstream.tvp.pl/'},
                       {'category': 'week_epg', 'title': 'TVP SPORT', 'url': STREAMS_URL_TEMPLATE}]

    def __init__(self):
        printDBG("TvpVod.__init__")
        proxyUrl = GetProxyUrl()
        CBaseHostClass.__init__(self, {'history': 'TvpVod', 'cookie': 'tvpvod.cookie', 'proxyURL': proxyUrl, 'useProxy': proxyUrl != ''})
        self.MAIN_URL = 'https://vod.tvp.pl/'
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/tvpvod135.png")
        self.HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {'with_metadata': True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE, 'header': self.HTTP_HEADER}
        self.FormatBitrateMap = [("360000", "320x180"), ("590000", "398x224"), ("820000", "480x270"), ("1250000", "640x360"),
                                 ("1750000", "800x450"), ("2850000", "960x540"), ("5420000", "1280x720"), ("6500000", "1600x900"), ("9100000", "1920x1080")]
        self.loggedIn = None
        self.loginMessage = ''
        self.geoBlocked = False
        self.watchedHelper = IPTVWatchedHelper("tvpvod")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    def _getJson(self, url, params=None):
        sts, data = self.getPage(url, params)
        if not sts:
            return None
        try:
            return json_loads(data)
        except Exception:
            printExc()
        return None

    def _getFullUrl(self, url, baseUrl=None):
        if not url:
            return ''
        if url.startswith('//'):
            return 'https:' + url
        if url.startswith('http'):
            return url
        return self.cm.getFullUrl(url, baseUrl or self.MAIN_URL)

    def _apiImage(self, item):
        images = item.get('images') or {}
        for key in ('16x9', '4x3', '3x4', '1x1'):
            for img in images.get(key) or []:
                url = ensure_str(img.get('url') or '')
                if url:
                    return self._getFullUrl(url)
        return ''

    def getImageUrl(self, item):
        for key in ['logo_4x3', 'image_16x9', 'image_4x3', 'image_ns954', 'image_ns644', 'image']:
            if item.get(key):
                iconFile = ensure_str(item[key][0].get('file_name', '') or '')
                if iconFile:
                    tmp = iconFile.split('.')
                    return self.IMAGE_URL % (iconFile[0], iconFile[1], iconFile[2], tmp[0], tmp[1])
        return ''

    def getFormatFromBitrate(self, bitrate):
        for item in self.FormatBitrateMap:
            if int(bitrate) == int(item[0]):
                return item[1]
        return 'Bitrate[%s]' % bitrate

    def getBitrateFromFormat(self, format):
        for item in self.FormatBitrateMap:
            if format == item[1]:
                return int(item[0])
        return 0

    ###################################################
    # watched flag / favourites
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict) or cItem.get('live'):
                return ''
            url = cItem.get('url', '')
            if cItem.get('type') == 'video':
                m = PRODUCT_ID_RE.search(url)
                if m:
                    return 'video:product:%s' % m.group(1)
                m = re.search(r'tvp\.pl/(\d{6,})', url)
                if m:
                    return 'video:asset:%s' % m.group(1)
                return 'video:%s' % url if url else ''
            if cItem.get('category') == 'api_seasons' and cItem.get('f_serial'):
                return 'folder:serial:%s' % cItem['f_serial']
            if cItem.get('category') == 'api_episodes' and cItem.get('f_season'):
                return 'folder:season:%s' % cItem['f_season']
        except Exception:
            printExc()
        return ''

    def getFavouriteData(self, cItem):
        try:
            if cItem.get('type') == 'video':
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def getLinksForFavourite(self, fav_data):
        if self.loggedIn is None and config.plugins.iptvplayer.tvpvod_premium.value:
            self.loggedIn, msg = self.tryTologin()
        try:
            cItem = json_loads(fav_data)
        except Exception:
            # rows of very old versions: the asset id or the url
            if fav_data.isdigit():
                return self.getVideoLink(fav_data)
            cItem = {'url': fav_data}
        return self.getLinksForVideo(cItem)

    ###################################################
    # login (Strefa Widza, the user's own account)
    ###################################################
    def tryTologin(self):
        self.loginMessage = ''
        email = config.plugins.iptvplayer.tvpvod_login.value
        password = config.plugins.iptvplayer.tvpvod_password.value
        msg = 'Wystąpił problem z zalogowaniem użytkownika "%s"!' % email
        params = dict(self.defaultParams)
        sts, data = self.getPage(self.ACCOUNT_URL, params)
        if not sts or 'action=sign-out' not in data:
            params.update({'load_cookie': False})
            sts, data = self.getPage(self.LOGIN_URL, params)
            if sts:
                ref = self.cm.ph.getSearchGroups(data, 'name="ref".+?value="([^"]+?)"')[0]
                post_data = {'ref': ref, 'email': email, 'password': password, 'action': 'login'}
                sitekey = self.cm.ph.getSearchGroups(data, '''sitekey=['"]([^'^"]+?)['"]''')[0]
                if sitekey != '':
                    token, errorMsgTab = self.processCaptcha(sitekey, self.cm.meta['url'])
                    if token == '':
                        msg = _('Link protected with google recaptcha v2.') + '\n' + msg
                        sts = False
                    else:
                        post_data['g-recaptcha-response'] = token
                sts, data = self.getPage(self.LOGIN_URL + ref, self.defaultParams, post_data)
                sts, data = self.getPage(self.ACCOUNT_URL, self.defaultParams)
        if sts and 'action=sign-out' in data:
            tmp = self.cm.ph.getDataBeetwenNodes(data, ('<section', '>', 'abo__section'), ('</section', '>'), False)[1]
            if tmp == '':
                tmp = self.cm.ph.getDataBeetwenNodes(data, ('<section', '>', 'abo-inactive'), ('</section', '>'), False)[1]
            data = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(tmp, ('<p', '>'), ('</p', '>'), False)[1])
            self.loginMessage = '[/br]'.join(['Użytkownik "%s"' % email, 'Strefa Abo %s' % data])
            msg = self.loginMessage.replace('[/br]', '\n')
            authUrl = 'https://user.tvp.pl/oauth/auth_code.php?client_id=tvp-sso&redirect_uri=https%3A%2F%2Fvod.tvp.pl%2Fsubscriber%2Flogin%2Ftvp&scope=basic&response_type=code'
            params = dict(self.defaultParams)
            sts, data = self.getPage(authUrl, params, {'approve': '1'})
            params['max_data_size'] = 0
            params['no_redirection'] = True
            sts, data = self.getPage(authUrl, params, {'approve': '1'})
            url = self.cm.meta.get('location', '')
            url = API_URL + 'subscribers/sso/tvp/login?lang=pl&platform=BROWSER&code=' + self.cm.ph.getSearchGroups(url + '&', r'code=([^\?^&]+)[\?&]')[0]
            params = dict(self.defaultParams)
            params['raw_post_data'] = True
            params['header'] = MergeDicts(self.HTTP_HEADER, {'Content-Type': 'application/x-www-form-urlencoded', 'Referer': authUrl})
            sts, data = self.getPage(url, params, '{"auth":{"type":"SSO","value":"","app":"tvp"},"rememberMe":true}')
        else:
            sts = False
        return sts, msg

    ###################################################
    # vod.tvp.pl catalogue (api)
    ###################################################
    def listCatalogApi(self, cItem):
        printDBG("TvpVod.listCatalogApi")
        data = self._getJson(API_URL + 'items/categories?mainCategoryId=%s&%s' % (cItem['id'], API_PARAMS))
        if not isinstance(data, list):
            return
        base = API_URL + 'products/vods?mainCategoryId[]=%s' % cItem['id']
        self.addDir(MergeDicts(cItem, {'good_for_fav': True, 'category': 'api_list', 'title': _('All'), 'url': '%s&%s' % (base, API_PARAMS)}))
        for item in data:
            name = self.cleanHtmlStr(ensure_str(item.get('name', '')))
            if name:
                self.addDir(MergeDicts(cItem, {'good_for_fav': True, 'category': 'api_list', 'title': name, 'url': '%s&categoryId[]=%s&%s' % (base, item.get('id', ''), API_PARAMS)}))

    def _productRow(self, item, show=''):
        itemType = ensure_str(item.get('type', ''))
        pid = item.get('id', '')
        title = self.cleanHtmlStr(ensure_str(item.get('title', '') or ''))
        if not pid or not title:
            return None
        year = str(item.get('year', '') or '')
        lead = self.cleanHtmlStr(ensure_str(item.get('lead', '') or ''))
        info = []
        if year:
            info.append(year)
        try:
            if item.get('duration'):
                info.append('%d min' % (int(item['duration']) // 60))
        except (TypeError, ValueError):
            pass
        genres = ', '.join([ensure_str(x.get('name', '')) for x in item.get('genres') or [] if x.get('name')])
        if genres:
            info.append(genres)
        if item.get('payable'):
            info.append('Premium')
        row = {'good_for_fav': True, 'title': title, 'raw_title': title, 'icon': self._apiImage(item),
               'desc': '[/br]'.join([x for x in (' | '.join(info), lead) if x]), 'f_asset': ensure_str(item.get('externalUid', '') or '')}
        if itemType == 'SERIAL':
            row.update({'category': 'api_seasons', 'url': API_URL + 'products/vods/serials/%s/seasons?%s' % (pid, API_PARAMS), 'f_serial': str(pid),
                        'meta_type': 'tv', 'meta_title': title, 'meta_year': year})
            return row
        row['url'] = API_URL + 'products/%s/videos/playlist?platform=BROWSER&videoType=MOVIE' % pid
        if itemType == 'EPISODE':
            m = SXE_RE.search(ensure_str(item.get('webUrl', '') or ''))
            season, episode = (m.group(1), m.group(2)) if m else ((item.get('season') or {}).get('number', ''), item.get('number', ''))
            if show and season and episode and IsMediaNamingNormalized():
                row['title'] = '%s - %s' % (show, formatSxxExx(season, episode))
            row.update({'meta_type': 'tv', 'meta_title': show})
        else:
            row['title'] = normalizeMediathekTitle(title, year=year, isMovie=True) if year else title
            row.update({'meta_type': 'movie', 'meta_title': title, 'meta_year': year})
        return row

    def _addProducts(self, items, show=''):
        count = 0
        for item in items or []:
            row = self._productRow(item, show)
            if row is None:
                continue
            row['name'] = 'category'
            if row.get('category'):
                self.addDir(row)
            else:
                self.addVideo(row)
            count += 1
        return count

    def listApiProducts(self, cItem):
        printDBG("TvpVod.listApiProducts [%s]" % cItem.get('url', ''))
        try:
            page = max(1, int(cItem.get('page', 1) or 1))
        except (TypeError, ValueError):
            page = 1
        base = re.sub(r'&(?:firstResult|maxResults|iptvpage)=\d*', '', cItem['url'])
        data = self._getJson('%s&firstResult=%d&maxResults=%d' % (base, (page - 1) * CATALOG_PAGE_SIZE, CATALOG_PAGE_SIZE))
        if not isinstance(data, dict):
            return
        count = self._addProducts(data.get('items', []))
        try:
            total = int((data.get('meta') or {}).get('totalCount', 0) or 0)
        except (TypeError, ValueError):
            total = 0
        lastPage = (total + CATALOG_PAGE_SIZE - 1) // CATALOG_PAGE_SIZE
        params = MergeDicts(stripPagerKeys(dict(cItem)), {'url': base})
        addPagingItems(self, params, page, bool(count) and page < lastPage, lastPage, base.replace('{', '%7B').replace('}', '%7D') + '&iptvpage={page}')

    def listSeasons(self, cItem):
        printDBG("TvpVod.listSeasons [%s]" % cItem.get('url', ''))
        data = self._getJson(cItem['url'])
        if not isinstance(data, list):
            return
        serial = cItem.get('f_serial', '') or self.cm.ph.getSearchGroups(cItem['url'], r'/serials/(\d+)/')[0]
        show = cItem.get('meta_title', '') or cItem.get('raw_title', '') or cItem.get('title', '')
        seasons = []
        for item in data:
            if item.get('id'):
                url = API_URL + 'products/vods/serials/%s/seasons/%s/episodes?%s' % (serial, item['id'], API_PARAMS)
                title = self.cleanHtmlStr(ensure_str(item.get('title', '') or ''))
                if item.get('number') and title.lower() in ('', 'odcinki'):
                    title = _('Season %s') % item['number']
                seasons.append({'name': 'category', 'good_for_fav': True, 'category': 'api_episodes', 'title': title, 'url': url,
                                'f_season': str(item['id']), 'f_show': show, 'icon': cItem.get('icon', ''), 'desc': ensure_str(item.get('display', '') or ''),
                                'meta_type': 'tv', 'meta_title': show, 'meta_year': cItem.get('meta_year', '')})
        if len(seasons) == 1:
            self.listEpisodes(MergeDicts(cItem, seasons[0], {'title': cItem.get('title', '')}))
            return
        for item in seasons:
            self.addDir(item)

    def listEpisodes(self, cItem):
        printDBG("TvpVod.listEpisodes [%s]" % cItem.get('url', ''))
        try:
            page = max(1, int(cItem.get('page', 1) or 1))
        except (TypeError, ValueError):
            page = 1
        data = self._getJson(cItem['url'])
        if not isinstance(data, list):
            return
        lastPage = (len(data) + EPISODES_PAGE_SIZE - 1) // EPISODES_PAGE_SIZE
        self._addProducts(data[(page - 1) * EPISODES_PAGE_SIZE:page * EPISODES_PAGE_SIZE], cItem.get('f_show', ''))
        addPagingItems(self, stripPagerKeys(dict(cItem)), page, page < lastPage, lastPage)

    def listOldApiItem(self, cItem):
        # folders saved as favourites by the old version ("api_explore_item")
        url = cItem.get('url', '')
        if '/episodes' in url:
            self.listEpisodes(cItem)
        elif '/seasons' in url:
            self.listSeasons(cItem)
        elif '/search/' in url:
            data = self._getJson(url)
            self._addProducts((data or {}).get('items', []) if isinstance(data, dict) else data)
        else:
            self.listApiProducts(cItem)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("TvpVod.listSearchResult [%s] [%s]" % (searchPattern, searchType))
        kind = 'VOD' if searchType == 'movies' else 'SERIAL'
        data = self._getJson(API_URL + 'products/vods/search/%s?%s&keyword=%s' % (kind, API_PARAMS, urllib_quote(searchPattern)))
        if isinstance(data, dict):
            data = data.get('items', [])
        self._addProducts(data or [])
        if not self.currList:
            SetIPTVPlayerLastHostError(_("No matching entries found."))

    ###################################################
    # TVP Sport
    ###################################################
    def listTVPSportCategories(self, cItem):
        printDBG("TvpVod.listTVPSportCategories")
        sts, data = self.getPage(cItem['url'])
        dirId = '548369'
        if sts:
            dirId = self.cm.ph.getSearchGroups(data, r'''__directoryData\s*=\s*\{\s*"_id"\s*:\s*(\d+)''')[0] or dirId
        data = self._getJson('https://sport.tvp.pl/api/sport/www/directory/list?direct=true&sort=position,1&limit=30&id=%s' % dirId)
        for item in ((data or {}).get('data') or {}).get('items', []):
            name = self.cleanHtmlStr(ensure_str(item.get('title', '') or ''))
            if name and item.get('_id'):
                self.addDir(MergeDicts(cItem, {'good_for_fav': True, 'category': 'tvp_sport_list_items', 'title': name, 'f_dir_id': str(item['_id']),
                                               'url': 'https://sport.tvp.pl/api/sport/www/block/list?device=www&id=%s' % item['_id'], 'desc': ''}))

    def listTVPSportVideos(self, cItem):
        printDBG("TvpVod.listTVPSportVideos")
        try:
            page = max(1, int(cItem.get('page', 1) or 1))
        except (TypeError, ValueError):
            page = 1
        url = cItem['url']
        if '/block/list' in url:
            # the category's video block (one request when the category is opened, not for every category)
            data = self._getJson(url)
            try:
                url = 'https://sport.tvp.pl/api/sport/www/block/items?device=www&id=%s' % data['data']['items'][0]['_id']
            except Exception:
                printExc()
                return
        data = self._getJson(re.sub(r'&page=\d+', '', url) + '&page=%d' % page)
        count = 0
        for item in ((data or {}).get('data') or {}).get('items', []):
            videoUrl = self._getFullUrl(ensure_str(item.get('url', '') or ''), 'https://sport.tvp.pl')
            title = self.cleanHtmlStr(ensure_str(item.get('title', '') or ''))
            if not videoUrl.startswith('http') or not title or item.get('type', 'video') != 'video':
                continue
            date = ensure_str(item.get('release_date_tz', '') or '')[:10]
            info = ['%s.%s.%s' % (date[8:10], date[5:7], date[:4]) if len(date) == 10 else '']
            try:
                if item.get('duration'):
                    info.append('%d:%02d' % (int(item['duration']) // 60, int(item['duration']) % 60))
            except (TypeError, ValueError):
                pass
            icon = ensure_str(((item.get('image') or {}).get('url', '') or '')).replace('{width}', '480').replace('{height}', '270')
            desc = [' | '.join([x for x in info if x]), self.cleanHtmlStr(ensure_str(item.get('lead', '') or ''))]
            self.addVideo({'name': 'category', 'good_for_fav': True, 'title': normalizeMediathekTitle(title, date=date), 'raw_title': title, 'url': videoUrl,
                           'icon': self._getFullUrl(icon), 'desc': '[/br]'.join([x for x in desc if x]), 'date': date})
            count += 1
        params = MergeDicts(stripPagerKeys(dict(cItem)), {'url': url})
        addPagingItems(self, params, page, count >= SPORT_PAGE_SIZE)

    ###################################################
    # live
    ###################################################
    def listTVP3Streams(self, cItem):
        printDBG("TvpVod.listTVP3Streams")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        try:
            data = json_loads(self.cm.ph.getSearchGroups(data, r'window.__channels\s*=([^;]+?);')[0])
        except Exception:
            printExc()
            return
        for item in data:
            video_id = self.cm.ph.getSearchGroups(json_dumps(item.get('items', '')), r'''['"]video_id['"]\s*:\s*([^,]+?),''')[0].strip()
            if video_id == '':
                continue
            logo = json_dumps(item.get('image_logo', ''))
            icon = self.cm.ph.getSearchGroups(logo, r'''['"](http[^'"]+?\.(?:jpg|png))['"]''')[0].replace('\\/', '/')
            icon = icon.replace('{width}', '300').replace('{height}', '0')
            title = ensure_str(item.get('title', '')).replace('EPG - ', '')
            self.addVideo({'name': 'category', 'good_for_fav': True, 'live': True, 'title': title, 'url': TOKENIZER_URL % video_id, 'icon': icon, 'desc': '%s - %s' % (title, _('Live'))})

    def listWeekEPG(self, cItem):
        printDBG("TvpVod.listWeekEPG")
        d = datetime.today()
        for i in range(7):
            url = cItem['url'].replace('[iptv_date]', d.strftime('%Y-%m-%d'))
            self.addDir(MergeDicts(cItem, {'good_for_fav': False, 'category': 'epg_items', 'title': d.strftime('%d.%m.%Y'), 'url': url}))
            d += timedelta(days=1)

    def listEPGItems(self, cItem):
        printDBG("TvpVod.listEPGItems")
        data = self._getJson(cItem['url'])
        try:
            items = sorted(data['items'], key=lambda item: item.get('release_date_hour', ''))
        except Exception:
            printExc()
            return
        for item in items:
            if not item.get('is_live', False):
                continue
            desc = '%s - %s[/br]%s' % (ensure_str(item.get('release_date_hour', '')), ensure_str(item.get('broadcast_end_date_hour', '')), self.cleanHtmlStr(ensure_str(item.get('lead', '') or '')))
            self.addVideo({'name': 'category', 'good_for_fav': False, 'live': True, 'title': self.cleanHtmlStr(ensure_str(item.get('title', ''))),
                           'url': TOKENIZER_URL % item.get('video_id', ''), 'icon': self.getImageUrl(item), 'desc': desc})

    ###################################################
    # Rekonstrukcja cyfrowa TVP (cyfrowa.tvp.pl)
    ###################################################
    def listDigiMenu(self, cItem):
        printDBG("TvpVod.listDigiMenu")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        cUrl = self.cm.meta['url']
        tmp = ph.find(data, ('<nav', '>', 'navigation--menu'), '</nav>', flags=0)[1]
        for item in ph.findall(tmp, ('<li', '>'), '</li>', flags=0):
            parts = item.split('<ul', 1)
            if len(parts) > 1:
                item = parts[1]
            sTitle = ph.find(item, ('<a', '>'), '</a>')[1]
            sUrl = self.getFullUrl(ph.getattr(sTitle, 'href'), cUrl)
            sTitle = ph.clean_html(sTitle)
            if ',' in sUrl:
                self.addDir(MergeDicts(cItem, {'good_for_fav': True, 'category': 'digi_explore_site', 'title': sTitle, 'url': sUrl}))

    def exploreDigiSite(self, cItem):
        printDBG("TvpVod.exploreDigiSite")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        cUrl = self.cm.meta['url']

        if cItem.get('allow_sort', True):
            tmp = ph.find(data, ('<ul', '>', 'dropdown--sort'), '</ul>', flags=0)[1]
            for item in ph.findall(tmp, ('<a', '>'), '</a>'):
                title = ph.clean_html(item)
                url = self.getFullUrl(ph.getattr(item, 'href'), cUrl)
                if '{title},{id}' in url:
                    url = cUrl + self.cm.ph.getSearchGroups(item, r'''href=['"][^?]+?(\?[^'^"]+?)['"]''')[0]
                self.addDir(MergeDicts(cItem, {'good_for_fav': False, 'allow_sort': False, 'title': title, 'url': url}))
            if self.currList:
                return

        tmp = ph.find(data, ('<section', '>', 'episodes'), '</section>', flags=0)[1]
        nextPage = ph.find(tmp, ('<div', '>', 'common--title--container'), '</div>', flags=0)[1]
        nextPage = self.getFullUrl(ph.search(nextPage, ph.A_HREF_URI_RE)[1], cUrl)
        if nextPage != '':
            sts, data = self.getPage(nextPage)
            if not sts:
                return
            tmp = ph.find(data, ('<section', '>', 'episodes'), '</section>', flags=0)[1]
        tmp = ph.findall(tmp if tmp != '' else data, ('<div', '>', 'film--block'), '</div>', flags=0)
        for item in tmp:
            title = self.cm.ph.getSearchGroups(item, 'alt="([^"]+?)"')[0]
            url = self.getFullUrl(ph.search(item, ph.A_HREF_URI_RE)[1], cUrl)
            icon = self.getFullUrl(ph.search(item, ph.IMAGE_SRC_URI_RE)[1], cUrl)
            descData = ph.findall(item, ('<p', '>'), '</p>', flags=0)
            if not descData and not title:
                continue
            if not title:
                title = self.cleanHtmlStr(descData[0])
            desc = [ph.clean_html(x) for x in descData[1:] if ph.clean_html(x)]
            desc = ' | '.join(desc) + '[/br]' + ph.clean_html(item[-1])
            params = MergeDicts(cItem, {'good_for_fav': True, 'allow_sort': True, 'url': url, 'desc': desc, 'icon': icon})
            if '/video/' in url:
                if title.startswith('odc.') and cItem.get('prev_title'):
                    title = '%s: %s' % (cItem['prev_title'], title)
                params.update({'title': title, 'raw_title': title})
                params.pop('category', None)
                self.addVideo(params)
            else:
                params.update({'title': title, 'prev_title': title})
                self.addDir(params)

    ###################################################
    # links
    ###################################################
    def getObjectID(self, url):
        m = re.search(r'tvp\.pl/(\d{6,})(?:/|$)', url) or re.search(r',(\d{6,})(?:$|[/?])', url)
        if m and 'vod.tvp.pl' not in url:
            return m.group(1)
        sts, data = self.getPage(url)
        if not sts:
            return ''
        sess_player_url = self.cm.ph.getSearchGroups(data, '''(https?://[^'^"]+?/sess/player/video/[^'^"]+?)['"]''')[0]
        if sess_player_url != '':
            sts, tmp = self.getPage(sess_player_url)
            if sts:
                data = tmp
        for pattern in (r'''id=['"]tvplayer\-[0-9]+\-([0-9]+)''', 'object_id=([0-9]+?)[^0-9]', 'class="playerContainer"[^>]+?data-id="([0-9]+?)"',
                        r'data\-video\-id="([0-9]+?)"', "object_id:'([0-9]+?)'", r'data\-object\-id="([0-9]+?)"', r"videoID:\s*'([0-9]+?)'",
                        r'''['"]video_id['"]\s*:\s*['"]?([0-9]+)'''):
            asset_id = self.cm.ph.getSearchGroups(data, pattern)[0]
            if asset_id:
                return asset_id
        return ''

    def _sortVideoLinks(self, videoTab):
        if 1 < len(videoTab):
            max_bitrate = int(config.plugins.iptvplayer.tvpVodDefaultformat.value)

            def __getLinkQuality(itemLink):
                if 'width' in itemLink and 'height' in itemLink:
                    bitrate = self.getBitrateFromFormat('%sx%s' % (itemLink['width'], itemLink['height']))
                    if bitrate != 0:
                        return bitrate
                try:
                    return int(itemLink.get('bitrate', itemLink.get('bandwidth', 0)))
                except Exception:
                    return 0
            oneLink = CSelOneLink(videoTab, __getLinkQuality, max_bitrate)
            videoTab = oneLink.getOneLink() if config.plugins.iptvplayer.tvpVodUseDF.value else oneLink.getSortedLinks()
        return videoTab

    def _getTokenizerLinks(self, url):
        # api.tvp.pl/tokenizer/token/<asset id>: formats of the video / the live channel
        self.geoBlocked = False
        data = self._getJson(url)
        if not isinstance(data, dict):
            return []
        if data.get('isGeoBlocked') or data.get('geoBlocked'):
            # outside Poland the api answers with a "not available" clip
            self.geoBlocked = True
            SetIPTVPlayerLastHostError(_("Not available in your country (geo-blocking)."))
            return []
        if data.get('drm'):
            SetIPTVPlayerLastHostError(_("Video with DRM protection."))
            return []
        hlsTab, mp4Tab, dashTab = [], [], []
        formats = data.get('formats') or []
        if not formats and data.get('url'):
            formats = [{'mimeType': 'application/x-mpegurl', 'url': data['url']}]
        proxyUrl = GetProxyUrl()
        for item in formats:
            fUrl = ensure_str(item.get('url', '') or '')
            mime = ensure_str(item.get('mimeType', '') or '').lower()
            if not self.cm.isValidUrl(fUrl):
                continue
            if 'mpegurl' in mime or '.m3u8' in fUrl:
                hlsTab.extend(getDirectM3U8Playlist(fUrl, checkExt=False, variantCheck=False))
            elif 'dash' in mime or '.mpd' in fUrl:
                dashTab.extend(getMPDLinksWithMeta(fUrl, False, sortWithMaxBandwidth=999999999))
            elif 'mp4' in mime:
                meta = {'iptv_format': 'mp4'}
                if proxyUrl:
                    meta['http_proxy'] = proxyUrl
                bitrate = str(item.get('totalBitrate', '') or '0')
                mp4Tab.append({'name': '%s \t mp4' % self.getFormatFromBitrate(bitrate), 'bitrate': bitrate, 'url': self.up.decorateUrl(fUrl, meta)})
        prefered = config.plugins.iptvplayer.tvpVodPreferedformat.value
        order = {'m3u8': (hlsTab, mp4Tab, dashTab), 'mpd': (dashTab, hlsTab, mp4Tab)}.get(prefered, (mp4Tab, hlsTab, dashTab))
        for tab in order:
            if tab:
                return self._sortVideoLinks(tab)
        return []

    def getVideoLink(self, asset_id):
        printDBG("TvpVod.getVideoLink asset_id [%s]" % asset_id)
        if not asset_id:
            return []
        videoTab = self._getTokenizerLinks(TOKENIZER_URL % asset_id)
        if videoTab or self.geoBlocked:
            return videoTab
        # fallback: the api of the old android app
        formatMap = {'1': ("320x180", 360000), '2': ('398x224', 590000), '3': ('480x270', 820000), '4': ('640x360', 1250000), '5': ('800x450', 1750000), '6': ('960x540', 2850000), '7': ('1280x720', 5420000), '8': ("1600x900", 6500000), '9': ('1920x1080', 9100000)}
        params = dict(self.defaultParams)
        params['header'] = {'User-Agent': 'okhttp/3.8.1', 'Authorization': 'Basic YXBpOnZvZA==', 'Accept-Encoding': 'gzip'}
        data = self._getJson('https://apivod.tvp.pl/tv/video/%s/' % asset_id, params)
        try:
            for item in data.get('data', []):
                if 'formats' in item:
                    data = item
                    break
            hlsTab = []
            mp4Tab = []
            for item in data.get('formats', []):
                if not self.cm.isValidUrl(item.get('url', '')):
                    continue
                if item.get('mimeType', '').lower() == "application/x-mpegurl":
                    hlsTab = getDirectM3U8Playlist(item['url'])
                elif item.get('mimeType', '').lower() == "video/mp4":
                    fid = self.cm.ph.getSearchGroups(item['url'], r'''/video\-([1-9])\.mp4$''')[0]
                    fItem = formatMap.get(fid, ('0x0', 0))
                    mp4Tab.append({'name': '%s \t mp4' % fItem[0], 'url': item['url'], 'bitrate': fItem[1], 'id': fid})
            hlsTab = self._sortVideoLinks(hlsTab)
            mp4Tab = self._sortVideoLinks(mp4Tab)
            videoTab = hlsTab + mp4Tab if config.plugins.iptvplayer.tvpVodPreferedformat.value == 'm3u8' else mp4Tab + hlsTab
        except Exception:
            printExc("getVideoLink exception")
        return videoTab

    def _getPlaylistLinks(self, cItem, url):
        # vod.tvp.pl: products/<id>/videos/playlist (Poland only - outside it answers 403 GEOIP_FILTER_FAILED)
        httpParams = dict(self.defaultParams)
        httpParams['ignore_http_code_ranges'] = [(403, 403)]
        sts, data = self.getPage(url, httpParams)
        if not sts:
            return []
        if 'GEOIP_FILTER_FAILED' in data:
            SetIPTVPlayerLastHostError(_("Not available in your country (geo-blocking)."))
            return []
        if '"drm":' in data and '"drm":null' not in data.replace(' ', ''):
            SetIPTVPlayerLastHostError(_("Video with DRM protection."))
            return []
        prefered = config.plugins.iptvplayer.tvpVodPreferedformat.value
        videoTab = []
        if prefered == 'm3u8':
            hlsUrl = self.cm.ph.getSearchGroups(data, r'''['"](http[^'"]*?\.m3u8[^'"]*?)['"]''')[0].replace(r'\/', '/')
            if hlsUrl:
                videoTab = self._sortVideoLinks(getDirectM3U8Playlist(hlsUrl, checkExt=False, variantCheck=False))
        elif prefered == 'mpd':
            mpdLink = self.cm.ph.getSearchGroups(data, r'''['"](http[^'"]*?\.mpd[^'"]*?)['"]''')[0].replace(r'\/', '/')
            if mpdLink:
                videoTab = self._sortVideoLinks(getMPDLinksWithMeta(mpdLink, False, sortWithMaxBandwidth=999999999))
        if videoTab:
            return videoTab
        asset_id = self.cm.ph.getSearchGroups(data, '''['"]externalUid['"]\\s*:\\s*['"]([^'"]*?)['"]''')[0] or cItem.get('f_asset', '')
        return self.getVideoLink(asset_id)

    def getLinksForVideo(self, cItem):
        url = self._getFullUrl(cItem.get('url', ''))
        printDBG("TvpVod.getLinksForVideo [%s]" % url)
        if 'api.tvp.pl/tokenizer' in url:
            videoTab = self._getTokenizerLinks(url)
        elif '/api/' in url:
            videoTab = self._getPlaylistLinks(cItem, url)
        else:
            asset_id = str(cItem.get('object_id', '') or cItem.get('f_asset', '')) or self.getObjectID(url)
            videoTab = self.getVideoLink(asset_id)
        if not cItem.get('live'):
            videoTab = applySidecarToLinks(videoTab, buildSidecarFromItem(cItem, IsSidecarEnabled()))
        return videoTab

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("TvpVod.getArticleContent [%s]" % cItem.get('url', ''))
        title = cItem.get('raw_title', cItem.get('title', ''))
        text = cItem.get('desc', '')
        icon = cItem.get('icon', '')
        otherInfo = {}
        if cItem.get('date'):
            otherInfo['released'] = cItem['date']
        if cItem.get('meta_type') and cItem.get('meta_title'):
            meta = getMeta(cItem['meta_type'], cItem['meta_title'], cItem.get('meta_year', ''), maxYearDiff=1)
            if meta:
                if meta.get('plot'):
                    text = '%s[/br][/br]%s' % (meta['plot'], text) if text else meta['plot']
                icon = icon or meta.get('poster', '')
                otherInfo.update(meta.get('info', {}))
        return [{'title': title, 'text': text, 'images': [{'title': '', 'url': icon}] if icon else [], 'other_info': otherInfo}]

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('TvpVod.handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        self.informAboutGeoBlockingIfNeeded('PL')

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("TvpVod.handleService: name[%s], category[%s]" % (name, category))
        self.currList = []
        currItem = dict(self.currItem)

        if name is None:
            self.listsTab(self.VOD_CAT_TAB + self.searchItems(), {'name': 'category', 'desc': self.loginMessage})
        # LIVE
        elif category == 'streams':
            self.listsTab(self.STREAMS_CAT_TAB, currItem)
        elif category == 'tvp3_streams':
            self.listTVP3Streams(currItem)
        elif category == 'week_epg':
            self.listWeekEPG(currItem)
        elif category == 'epg_items':
            self.listEPGItems(currItem)
        # TVP SPORT
        elif category == 'tvp_sport':
            self.listTVPSportCategories(currItem)
        elif category == 'tvp_sport_list_items':
            self.listTVPSportVideos(currItem)
        # VOD
        elif category == 'tvp_api':
            self.listCatalogApi(currItem)
        elif category == 'api_list':
            self.listApiProducts(currItem)
        elif category == 'api_seasons':
            self.listSeasons(currItem)
        elif category == 'api_episodes':
            self.listEpisodes(currItem)
        elif category == 'api_explore_item':
            self.listOldApiItem(currItem)
        # Reconstruction
        elif category == 'digi_menu':
            self.listDigiMenu(currItem)
        elif category == 'digi_explore_site':
            self.exploreDigiSite(currItem)
        # SEARCH
        elif category in ("search", "list_search"):
            cItem = dict(currItem)
            cItem.update({'search_item': False, 'name': 'category'})
            self.listSearchResult(cItem, cItem.get('searchPattern', searchPattern), cItem.get('searchType', searchType))
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, TvpVod(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("tvpvod")

    def withArticleContent(self, cItem):
        return cItem.get('type', '') == 'video' or cItem.get('category', '') == 'api_seasons'

    def getSearchTypes(self):
        searchTypesOptions = []
        searchTypesOptions.append((_("Movies"), "movies"))
        searchTypesOptions.append((_("Series"), "series"))
        return searchTypesOptions
