# -*- coding: utf-8 -*-
# Last Modified: 10.10.2026
# 10.10.2026 - links are no longer renamed to "*name*" after use - that broke the link list's own used mark (tick + colour);
#   lists repaired for auvio.rtbf.be (the old www.rtbf.be/auvio pages are gone): every menu now reads the site's own
#   bff-service api (pages -> widgets -> programmes / videos / lives / radios, seasons of a programme, the whole
#   programme mosaic, search), First page / Jump / Next page where the api pages; "En Direct" no longer fails on the
#   dead planninglist api (401); playback through the site's player backend (Red Bee: anonymous, or the own Auvio
#   account of the host configuration - Gigya login), HLS / DASH without DRM only (DRM and geo-blocked videos say
#   so); old favourites (www.rtbf.be/auvio/...?id=) reopen; watched flag (programme -> season -> video), favourites,
#   "Show - SxxExx" when names are normalised, INFO from the site's data, English menu labels; loads on py2 again
#   (no module-level datetime.timezone)
# 10.10.2026 - review: a video outside its geo zone says "geo-blocking" (Red Bee answers NOT_ENTITLED there, not a
#   missing account); no "!geo-blocked!" mark when the own country is unknown; tabs named by year give no SxxExx
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, getMPDLinksWithMeta
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus
###################################################
# FOREIGN import
###################################################
import re
import uuid
from Components.config import config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.configsecret import ConfigLogin, ConfigSecret
###################################################


###################################################
# E2 GUI COMMPONENTS
###################################################
from Screens.MessageBox import MessageBox
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.rtbfbe_login = ConfigLogin(default="", fixed_size=False)
config.plugins.iptvplayer.rtbfbe_password = ConfigSecret(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("e-mail") + ":", config.plugins.iptvplayer.rtbfbe_login))
    optionList.append(getConfigListEntry(_("password") + ":", config.plugins.iptvplayer.rtbfbe_password))
    return optionList
###################################################


def gettytul():
    return 'https://auvio.rtbf.be/'


BFF_URL = 'https://bff-service.rtbf.be/auvio/v1.23/'
LOGIN_URL = 'https://login.rtbf.be/'
REDBEE_URL = 'https://exposure.api.redbee.live/v2/customer/RTBF/businessunit/Auvio/'
# widgets without anything to list here (ads, the site user's own lists, single trailers)
SKIP_WIDGETS = ('BANNER', 'ONGOING_PLAY_HISTORY', 'FAVORITE_PROGRAM_LIST', 'PROMOBOX', 'MEDIA_TRAILER', 'FAVORITE_MEDIA_LIST')
# old www.rtbf.be/auvio links (favourites of the old version): kind of page -> new path prefix
OLD_URL_RES = ((re.compile(r'/auvio/emissions/detail[^?]*\?.*\bid=(\d+)'), 'emission'),
               (re.compile(r'/auvio/detail[^?]*\?.*\blid=(\d+)'), 'live'),
               (re.compile(r'/auvio/detail[^?]*\?.*\bid=(\d+)'), 'media'),
               (re.compile(r'/auvio/chaine[^?]*\?.*\bid=(\d+)'), 'chaine'),
               (re.compile(r'/auvio/categorie/[^?]*\?.*\bid=(\d+)'), 'categorie'))
# "01 - À bout de souffle", "Épisode 3" (no character class with "É": py2 matches utf-8 bytes)
EPISODE_NUM_RE = re.compile(r'^\s*(?:(?:Episode|Épisode|épisode|Ep\.?)\s*)?0*(\d{1,3})\s*(?:[-.:/]|$)', re.I)


class RTBFBE(GenericFolderWatchedScraperMixin, CBaseHostClass):
    CHECK_GEO_LOCK = True
    FAV_FIELDS = ('name', 'category', 'type', 'url', 'title', 'icon', 'desc', 'r_kind', 'media_id', 'asset_id', 'program_id',
                  's_title', 's_season', 's_episode')

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'rtbf.be', 'cookie': 'rtbf.be.cookie'})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = 'file://' + GetIconDir('PlayerSelector/rtbfbe135.png')
        self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.HTTP_HEADER.update({'Referer': self.MAIN_URL, 'Origin': self.MAIN_URL.rstrip('/')})
        self.defaultParams = {'header': self.HTTP_HEADER, 'with_metadata': True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.login = ''
        self.password = ''
        self.loggedIn = None
        self.loginMessage = ''
        self.loginToken = ''
        self.apiKey = ''
        self.userGeoLoc = ''
        self.deviceId = str(uuid.uuid4())
        self.bearer = {}
        self.cacheLinks = {}
        self.watchedHelper = IPTVWatchedHelper('rtbfbe')
        self.wfInitFolderCache()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        baseUrl = self.cm.iriToUri(baseUrl)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def _getJson(self, url, addParams=None, post_data=None):
        params = dict(self.defaultParams) if addParams is None else addParams
        # the api answers its errors (401/403/404) as json too
        params['ignore_http_code_ranges'] = [(400, 499)]
        sts, data = self.getPage(url, params, post_data)
        if not sts:
            return None
        try:
            return json_loads(data)
        except Exception:
            printExc()
        return None

    def getFavouriteData(self, cItem):
        try:
            if cItem.get('type') in ('video', 'audio') or cItem.get('program_id'):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # watched flag: programme -> season -> video (lives / radios have none)
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ''
            if cItem.get('r_kind') == 'media' and cItem.get('media_id'):
                return 'media:%s' % cItem['media_id']
            if cItem.get('category') == 'list_widget' and cItem.get('program_id') and cItem.get('s_season'):
                return 'season:%s#%s' % (cItem['program_id'], cItem['s_season'])
            if cItem.get('category') == 'sections' and cItem.get('program_id'):
                return 'program:%s' % cItem['program_id']
        except Exception:
            printExc()
        return ''

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self, cItem):
        printDBG("RTBFBE.listMainMenu")
        CAT_TAB = [{'category': 'sections', 'title': _('Main'), 'url': BFF_URL + 'pages/home'},
                   {'category': 'sections', 'title': _('Live'), 'url': BFF_URL + 'pages/direct'},
                   {'category': 'home_widget', 'title': _('Channels'), 'widget_type': 'CHANNEL_LIST'},
                   {'category': 'list_widget', 'title': _('Programmes'), 'url': BFF_URL + 'mosaic/program?includeFastTv=true'},
                   {'category': 'home_widget', 'title': _('Categories'), 'widget_type': 'CATEGORY_LIST'}] + self.searchItems()
        params = dict(cItem)
        params['desc'] = self.loginMessage
        self.listsTab(CAT_TAB, params)

    def _pageUrl(self, path):
        return BFF_URL + 'pages/' + path.lstrip('/')

    def _icon(self, item):
        for key in ('illustration', 'background'):
            images = item.get(key) or {}
            if isinstance(images, dict):
                for size in ('m', 's', 'l', 'xs'):
                    if images.get(size):
                        return images[size]
        logo = item.get('logo') or {}
        if isinstance(logo, dict):
            logo = logo.get('dark') or logo.get('light') or {}
            if isinstance(logo, dict):
                return logo.get('png', '')
        return ''

    @staticmethod
    def _time(value):
        # "2026-10-10T13:00:00+02:00" -> "10.10. 13:00" (Belgian time, as the site shows it)
        m = re.match(r'\d{4}-(\d\d)-(\d\d)T(\d\d:\d\d)', value or '')
        return '%s.%s. %s' % (m.group(2), m.group(1), m.group(3)) if m else ''

    def _addContent(self, cItem, item):
        kind = item.get('resourceType', '')
        title = self.cleanHtmlStr(item.get('title') or item.get('label') or '')
        path = item.get('path', '') or ''
        icon = self._icon(item)
        if kind in ('PROGRAM', 'CATEGORY', 'CHANNEL') and path and title:
            params = {'name': 'category', 'good_for_fav': True, 'category': 'sections', 'title': title, 'url': self._pageUrl(path), 'icon': icon, 'desc': ''}
            if kind == 'PROGRAM':
                params.update({'program_id': str(item.get('id', '')), 's_title': title.strip()})
            self.addDir(params)
        elif kind in ('MEDIA', 'MEDIA_PREMIUM') and path and title:
            subtitle = self.cleanHtmlStr(item.get('subtitle') or '')
            label = ('%s - %s' % (title, subtitle)) if subtitle and subtitle.lower() not in title.lower() else title
            duration = ('%d min' % (int(item['duration']) // 60)) if item.get('duration') else ''
            desc = [' | '.join(v for v in (item.get('channelLabel', ''), item.get('categoryLabel', ''), item.get('releaseDate', ''), duration) if v)]
            if kind == 'MEDIA_PREMIUM':
                desc.insert(0, _('Premium'))
            desc.append(self.cleanHtmlStr(item.get('description') or ''))
            params = {'name': 'category', 'good_for_fav': True, 'title': label, 'url': self.MAIN_URL + path.lstrip('/'), 'icon': icon,
                      'desc': '[/br]'.join(d for d in desc if d), 'r_kind': 'media', 'media_id': str(item.get('id', '')), 'asset_id': item.get('assetId', ''),
                      'program_id': str(item.get('programId') or cItem.get('program_id', '') or '')}
            season = cItem.get('s_season')
            episode = EPISODE_NUM_RE.search(subtitle)
            # some programmes name their tabs by year ("Année 2025") - no SxxExx from those
            if season and str(season).isdigit() and int(season) < 100 and episode and cItem.get('s_title'):
                params.update({'s_title': cItem['s_title'], 's_season': season, 's_episode': episode.group(1)})
                if IsMediaNamingNormalized():
                    params['title'] = '%s - %s' % (cItem['s_title'], formatSxxExx(season, episode.group(1)))
            if item.get('type') == 'AUDIO':
                self.addAudio(params)
            else:
                self.addVideo(params)
        elif kind == 'LIVE' and title:
            subtitle = self.cleanHtmlStr(item.get('subtitle') or '')
            label = ('%s - %s' % (title, subtitle)) if subtitle else title
            when = '%s - %s' % (self._time(item.get('scheduledFrom')), self._time(item.get('scheduledTo'))[-5:])
            desc = ' | '.join(v for v in (when.strip(' -'), item.get('channelLabel', '')) if v)
            params = {'name': 'category', 'good_for_fav': False, 'title': label, 'url': self.MAIN_URL + path.lstrip('/'), 'icon': icon, 'desc': desc,
                      'r_kind': 'live', 'media_id': str(item.get('id', '')), 'asset_id': item.get('assetId', '')}
            if item.get('type') == 'AUDIO':
                self.addAudio(params)
            else:
                self.addVideo(params)
        elif kind == 'RADIO_LIVE':
            channel = item.get('channel') or {}
            asset = channel.get('streamAssetId') or ''
            if not asset:
                return
            name = self.cleanHtmlStr(channel.get('label', ''))
            desc = ' | '.join(v for v in ('%s - %s' % (self._time(item.get('scheduledFrom')), self._time(item.get('scheduledTo'))[-5:]), title) if v.strip(' -'))
            self.addAudio({'name': 'category', 'good_for_fav': True, 'title': name or title, 'url': self.MAIN_URL + (channel.get('path', '') or '').lstrip('/'),
                           'icon': self._icon(channel), 'desc': desc, 'r_kind': 'radio', 'asset_id': asset})

    def listSections(self, cItem):
        # a page of the site (home, direct, category, channel, programme): its widgets; a page with one widget is
        # listed directly (programme -> its seasons)
        printDBG("RTBFBE.listSections [%s]" % cItem.get('url', ''))
        data = self._getJson(self._fromOldUrl(cItem.get('url', '')))
        page = (data or {}).get('data') or {}
        if not isinstance(page, dict):
            return
        content = page.get('content') or {}
        if content.get('pageType') == 'PROGRAM':
            cItem = dict(cItem, program_id=str(content.get('id', '')), s_title=self.cleanHtmlStr(content.get('title', '')) or cItem.get('s_title', ''))
            if not cItem.get('desc'):
                cItem['desc'] = self.cleanHtmlStr(content.get('description', ''))
        widgets = [w for w in (page.get('widgets') or []) if w.get('type') not in SKIP_WIDGETS and '{' not in (w.get('contentPath') or '{')]
        if len(widgets) == 1:
            self.listWidget(dict(cItem, category='list_widget', url=widgets[0]['contentPath'], page=1))
            return
        for widget in widgets:
            title = self.cleanHtmlStr(widget.get('title', '')) or self.cleanHtmlStr(widget.get('subtitle', ''))
            if not title:
                continue
            params = {'name': 'category', 'good_for_fav': True, 'category': 'list_widget', 'title': title, 'url': widget['contentPath'],
                      'icon': cItem.get('icon', ''), 'desc': self.cleanHtmlStr(widget.get('subtitle', ''))}
            for key in ('program_id', 's_title'):
                if cItem.get(key):
                    params[key] = cItem[key]
            self.addDir(params)
        if not self.currList:
            self.addMarker({'title': _('No items found'), 'desc': ''})

    @staticmethod
    def _withPage(url, page):
        url = re.sub(r'([?&])_page=\d+&?', r'\1', url).rstrip('?&')
        return '%s%s_page=%s' % (url, '&' if '?' in url else '?', page)

    def listWidget(self, cItem):
        page = cItem.get('page', 1)
        url = cItem.get('url', '')
        printDBG("RTBFBE.listWidget [%s] page[%s]" % (url, page))
        data = self._getJson(self._withPage(url, page) if page > 1 else url)
        if not data or not isinstance(data.get('data'), (dict, list)):
            return
        # a widget: {"type", "content": [...]}; the programme mosaic: the list itself
        widget = data['data'] if isinstance(data['data'], dict) else {'content': data['data']}
        content = widget.get('content') or []
        if isinstance(content, dict):
            content = content.get('items') or []
        if widget.get('type') == 'TAB_LIST':
            # the seasons of a programme
            tabs = [t for t in content if t.get('contentPath')]
            if len(tabs) == 1:
                self.listWidget(dict(cItem, url=tabs[0]['contentPath'], page=1, s_season=tabs[0].get('season') or cItem.get('s_season', '')))
                return
            for tab in tabs:
                params = dict(cItem)
                params.update({'good_for_fav': True, 'title': self.cleanHtmlStr(tab.get('title', '')), 'url': tab['contentPath'], 'page': 1,
                               'desc': self.cleanHtmlStr(tab.get('subtitle', '')), 's_season': tab.get('season') or ''})
                self.addDir(params)
            return
        for item in content:
            self._addContent(cItem, item)
        if not self.currList:
            self.addMarker({'title': _('No items found'), 'desc': ''})
            return
        meta = ((data.get('meta') or {}).get('page') or {})
        lastPage = meta.get('last') or 0
        hasNext = bool((data.get('links') or {}).get('next')) and bool(content)
        addPagingItems(self, dict(cItem), page, hasNext, lastPage, self._withPage(url, '{page}'))

    def listHomeWidget(self, cItem):
        # channels / categories: the list widget of that type on the home page
        data = self._getJson(BFF_URL + 'pages/home')
        for widget in (((data or {}).get('data') or {}).get('widgets') or []):
            if widget.get('type') == cItem.get('widget_type') and widget.get('contentPath'):
                self.listWidget(dict(cItem, category='list_widget', url=widget['contentPath'], page=1))
                return

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("RTBFBE.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        data = self._getJson(BFF_URL + 'search?query=' + urllib_quote_plus(searchPattern))
        for section in ((data or {}).get('data') or []):
            content = section.get('content') or []
            if section.get('type') not in ('PROGRAM_LIST', 'MEDIA_LIST', 'MEDIA_PREMIUM_LIST'):
                continue
            if section.get('type') != 'PROGRAM_LIST' and searchType in ('video', 'audio'):
                content = [c for c in content if (c.get('type') or '').lower() == searchType]
            for item in content:
                self._addContent(cItem, item)
        if not self.currList:
            self.addMarker({'title': _('No items found'), 'desc': ''})

    def _fromOldUrl(self, url):
        # favourites of the old version: www.rtbf.be/auvio/...?id=N -> the api page of that programme / channel / category
        if 'www.rtbf.be/auvio' not in url:
            return url
        for regex, kind in OLD_URL_RES:
            m = regex.search(url)
            if m and kind in ('emission', 'chaine', 'categorie'):
                return self._pageUrl('%s/x-%s' % (kind, m.group(1)))
        return url

    ###################################################
    # links
    ###################################################
    def getUserGeoLoc(self):
        if not self.userGeoLoc:
            data = self._getJson('https://www.rtbf.be/api/geoloc')
            try:
                self.userGeoLoc = (data or {}).get('country', '') or ''
            except Exception:
                printExc()
        return self.userGeoLoc

    def _embed(self, cItem):
        # (asset id, embed data) of a video / live row; old favourites only carry the old page url
        url = cItem.get('url', '')
        kind, mid = cItem.get('r_kind', ''), cItem.get('media_id', '')
        if not mid:
            for regex, oldKind in OLD_URL_RES:
                m = regex.search(url)
                if m and oldKind in ('media', 'live'):
                    kind, mid = oldKind, m.group(1)
                    break
        if not mid:
            m = re.search(r'/(media|live)/[^/?#]*?-?(\d+)(?:[/?#]|$)', url)
            if m:
                kind, mid = m.group(1), m.group(2)
        if kind not in ('media', 'live') or not mid:
            return cItem.get('asset_id', ''), {}
        data = self._getJson(BFF_URL + 'embed/%s/%s?userAgent=%s' % (kind, mid, urllib_quote(self.HTTP_HEADER.get('User-Agent', ''))))
        embed = ((data or {}).get('data') or {}) if isinstance(data, dict) else {}
        return embed.get('assetId') or cItem.get('asset_id', ''), embed

    def _bearer(self):
        # Red Bee session: with the own account (Gigya JWT) when logged in, anonymous otherwise
        key = 'user' if self.loggedIn else 'anonymous'
        if self.bearer.get(key):
            return self.bearer[key]
        request = {'deviceId': self.deviceId, 'device': {'deviceId': self.deviceId, 'name': 'Chrome', 'type': 'WEB'}}
        endpoint = 'auth/anonymous'
        if self.loggedIn:
            jwt = self._getJWT()
            if jwt:
                request['jwt'] = jwt
                endpoint = 'auth/gigyaLogin'
        params = dict(self.defaultParams)
        params.update({'raw_post_data': True, 'use_cookie': False})
        params['header'] = dict(self.HTTP_HEADER, **{'Content-Type': 'application/json;charset=utf-8', 'Accept': 'application/json'})
        data = self._getJson(REDBEE_URL + endpoint, params, json_dumps(request))
        token = (data or {}).get('sessionToken', '')
        if token:
            self.bearer[key] = token
        return token

    def getLinksForVideo(self, cItem):
        printDBG("RTBFBE.getLinksForVideo [%s]" % cItem)
        self.tryTologin()
        cacheKey = cItem.get('url', '')
        if self.cacheLinks.get(cacheKey):
            return self.cacheLinks[cacheKey]

        assetId, embed = self._embed(cItem)
        if not assetId:
            SetIPTVPlayerLastHostError(_('No stream available'))
            return []
        token = self._bearer()
        if not token:
            SetIPTVPlayerLastHostError(_('No stream available'))
            return []
        params = dict(self.defaultParams)
        params['use_cookie'] = False
        params['header'] = dict(self.HTTP_HEADER, **{'Authorization': 'Bearer ' + token, 'Accept': 'application/json, text/plain, */*'})
        data = self._getJson(REDBEE_URL + 'entitlement/%s/play' % assetId, params) or {}
        formats = data.get('formats') or []
        geo = ((embed.get('geoloc') or {}).get('key') or '').lower()
        userGeo = self.getUserGeoLoc().lower() if geo else ''
        # an unknown own country (geoloc api down) is no reason to mark the video
        geoBlocked = bool(userGeo) and geo not in ('open', 'world', 'monde', 'all') and geo != userGeo
        if not formats:
            message = data.get('message', '')
            printDBG("RTBFBE: entitlement [%s] %s" % (assetId, data))
            # Red Bee answers NOT_ENTITLED outside Belgium too - the video's own geo zone tells which it is
            if 'GEO' in message or (geoBlocked and message == 'NOT_ENTITLED'):
                SetIPTVPlayerLastHostError(_('Not available in your country (geo-blocking).'))
            elif message in ('NOT_ENTITLED', 'LOGIN_REQUIRED', 'NOT_AUTHENTICATED') and not self.loggedIn:
                SetIPTVPlayerLastHostError(_('%s needs a free account. Enter login and password in the host configuration.') % 'Auvio')
            else:
                SetIPTVPlayerLastHostError(_('No valid entitlement found for asset.') + (' (%s)' % message if message else ''))
            return []

        namePrefix = '!geo-blocked! ' if geoBlocked else ''
        retTab = []
        drm = False
        for item in formats:
            url = item.get('mediaLocator', '')
            proto = {'HLS': 'm3u8', 'DASH': 'mpd'}.get(item.get('format', ''), '')
            if not self.cm.isValidUrl(url) or not proto:
                continue
            if item.get('drm'):
                drm = True
                continue
            meta = {'Referer': self.MAIN_URL, 'Origin': self.MAIN_URL.rstrip('/'), 'User-Agent': self.HTTP_HEADER.get('User-Agent'), 'iptv_proto': proto}
            retTab.append({'name': '%s[%s]' % (namePrefix, 'HLS/m3u8' if proto == 'm3u8' else 'DASH/mpd'), 'url': strwithmeta(url, meta), 'need_resolve': 1})
        if not retTab:
            SetIPTVPlayerLastHostError(_('Video with DRM protection.') if drm else _('No stream available'))
            return []
        # HLS first: the box's players handle it better than DASH
        retTab.sort(key=lambda link: 0 if 'm3u8' in link['name'] else 1)
        retTab = applySidecarToLinks(retTab, buildSidecarFromItem(cItem, IsSidecarEnabled(), self.cleanHtmlStr(embed.get('description', ''))))
        self.cacheLinks[cacheKey] = retTab
        return retTab

    def getVideoLinks(self, videoUrl):
        printDBG("RTBFBE.getVideoLinks [%s]" % videoUrl)
        videoUrl = strwithmeta(videoUrl)
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        meta = dict(videoUrl.meta)
        proto = meta.get('iptv_proto', 'm3u8')
        if proto == 'mpd':
            retTab = getMPDLinksWithMeta(videoUrl, checkExt=False, sortWithMaxBandwidth=999999999)
        else:
            retTab = getDirectM3U8Playlist(videoUrl, checkExt=False, checkContent=True, sortWithMaxBitrate=999999999)
        for item in retTab:
            item['url'] = strwithmeta(item['url'], dict(meta, **getattr(item['url'], 'meta', {})))
        return decorateResolvedLinkItems(retTab, sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("RTBFBE.getArticleContent [%s]" % cItem.get('url', ''))
        title, text, icon, info = cItem.get('title', ''), cItem.get('desc', ''), cItem.get('icon', ''), {}
        if cItem.get('type') in ('video', 'audio') and cItem.get('r_kind') in ('media', 'live'):
            embed = self._embed(cItem)[1]
            if embed:
                text = self.cleanHtmlStr(embed.get('description', '')) or text
                icon = self._icon(embed) or icon
                if embed.get('duration'):
                    info['duration'] = '%d min' % (int(embed['duration']) // 60)
                for key, value in (('station', (embed.get('channel') or {}).get('label')), ('genre', (embed.get('category') or {}).get('label')),
                                   ('released', embed.get('releaseDate')), ('age_limit', embed.get('minimumAge'))):
                    if value:
                        info[key] = str(value)
                cast = [c.get('name', '') for c in (embed.get('casting') or []) if c.get('name')]
                if cast:
                    info['cast'] = ', '.join(cast[:8])
        elif cItem.get('program_id'):
            data = self._getJson(self._pageUrl('emission/x-%s' % cItem['program_id']))
            content = (((data or {}).get('data') or {}).get('content') or {})
            text = self.cleanHtmlStr(content.get('description', '')) or text
            for key, field in (('seasons', 'seasonCount'), ('episodes', 'videoCount')):
                if content.get(field):
                    info[key] = str(content[field])
            if (content.get('category') or {}).get('label'):
                info['genre'] = content['category']['label']
        return [{'title': title, 'text': text, 'images': [{'title': '', 'url': icon}] if icon else [], 'other_info': info}]

    ###################################################
    # login (own Auvio account of the host configuration)
    ###################################################
    def _getApiKey(self):
        # the site's public Gigya key, read from its own app script
        if not self.apiKey:
            sts, data = self.getPage(self.MAIN_URL)
            script = self.cm.ph.getSearchGroups(data, r'''src=['"]([^'"]*/_next/static/chunks/pages/_app-[^'"]+\.js)['"]''')[0] if sts else ''
            if script:
                sts, data = self.getPage(self.getFullUrl(script))
                if sts:
                    self.apiKey = self.cm.ph.getSearchGroups(data, r'''GIGYA:\{dataCenter:"[^"]*",apiKey:"([^"]+)"''')[0]
        return self.apiKey

    def _getJWT(self):
        if not self.loginToken:
            return ''
        data = self._getJson(LOGIN_URL + 'accounts.getJWT?login_token=%s&APIKey=%s&format=json' % (urllib_quote(self.loginToken), urllib_quote(self._getApiKey())))
        return (data or {}).get('id_token', '')

    def tryTologin(self):
        printDBG('RTBFBE.tryTologin start')
        if self.login == config.plugins.iptvplayer.rtbfbe_login.value and \
           self.password == config.plugins.iptvplayer.rtbfbe_password.value:
            return self.loggedIn

        self.login = config.plugins.iptvplayer.rtbfbe_login.value
        self.password = config.plugins.iptvplayer.rtbfbe_password.value

        rm(self.COOKIE_FILE)
        self.loggedIn = False
        self.loginToken = ''
        self.bearer = {}
        self.cacheLinks = {}
        self.loginMessage = ''

        if '' == self.login.strip() or '' == self.password.strip():
            return False

        message = _('Unknown server response.')
        apiKey = self._getApiKey()
        if apiKey:
            post_data = {'loginID': self.login, 'password': self.password, 'APIKey': apiKey, 'targetEnv': 'jssdk',
                         'sessionExpiration': '-2', 'include': 'profile,data', 'format': 'json'}
            data = self._getJson(LOGIN_URL + 'accounts.login', None, post_data) or {}
            if data.get('statusCode') == 200:
                self.loginToken = (data.get('sessionInfo') or {}).get('login_token', '')
            elif data.get('errorMessage'):
                message = self.cleanHtmlStr(data['errorMessage'])
        if self.loginToken:
            self.loggedIn = True
        else:
            self.sessionEx.open(MessageBox, _('Login failed.') + '\n' + message, type=MessageBox.TYPE_ERROR, timeout=10)
        return self.loggedIn

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        self.tryTologin()

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)

        if RTBFBE.CHECK_GEO_LOCK:
            RTBFBE.CHECK_GEO_LOCK = False
            self.informAboutGeoBlockingIfNeeded('BE')

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')

        printDBG("handleService: |||| name[%s], category[%s] " % (name, category))
        self.cacheLinks = {}
        self.currList = []

    # MAIN MENU
        if name is None:
            self.listMainMenu({'name': 'category'})
    # PAGES (main, live, channel, category, programme) - "live_categories" / "channels" / "categories": old favourites
        elif category in ('sections', 'live_categories', 'channels', 'categories', 'list_playlist_items'):
            self.listSections(self.currItem)
        elif category == 'list_widget':
            self.listWidget(self.currItem)
        elif category == 'home_widget':
            self.listHomeWidget(self.currItem)
    # SEARCH
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category'})
            self.listSearchResult(cItem, searchPattern, searchType)
    # HISTORIA SEARCH
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc')
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, RTBFBE(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('rtbfbe')

    def withArticleContent(self, cItem):
        return (cItem.get('type') in ('video', 'audio') and cItem.get('r_kind') in ('media', 'live')) or bool(cItem.get('program_id'))

    def getSearchTypes(self):
        searchTypesOptions = []
        searchTypesOptions.append((_("Video"), "video"))
        searchTypesOptions.append((_("Audio"), "audio"))
        return searchTypesOptions
