# -*- coding: utf-8 -*-
LAST_MODIFIED = "25.10.2026"
# 25.10.2026 - new webcam sources: worldcam.live, lookcam.com, San Diego Zoo, bieszczady.live,
#   nadmorski24.pl, lantech.com.pl (LiveSzczecin), korbielow.net, szczyrkowski.pl; 40mediagroup.com channels
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, RetHost, CUrlItem
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetHostsOrderList
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, getF4MLinksWithMeta
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
from Plugins.Extensions.IPTVPlayer.libs.filmonapi import FilmOnComApi, GetConfigList as FilmOn_GetConfigList
from Plugins.Extensions.IPTVPlayer.libs.webcamera import WebCameraApi
from Plugins.Extensions.IPTVPlayer.libs.weebtv import WeebTvApi, GetConfigList as WeebTv_GetConfigList
from Plugins.Extensions.IPTVPlayer.libs.meteopl import MeteoPLApi, GetConfigList as MeteoPL_GetConfigList
from Plugins.Extensions.IPTVPlayer.libs.skylinewebcamscom import WkylinewebcamsComApi, GetConfigList as WkylinewebcamsCom_GetConfigList
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.libs.djingcom import DjingComApi
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.pVer import isPY2
if not isPY2():
    basestring = str
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
###################################################
# FOREIGN import
###################################################
import re
from base64 import b64decode
from Components.config import config, ConfigSelection, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.configsecret import ConfigSecret
############################################


###################################################
# Config options for HOST
###################################################
# free key from https://api.windy.com/webcams - required, the listing API is authenticated
config.plugins.iptvplayer.windy_api_key = ConfigSecret(default="", fixed_size=False)
config.plugins.iptvplayer.fake_separator = ConfigSelection(default=" ", choices=[(" ", " ")])


def GetConfigList():
    optionList = []

    optionList.append(getConfigListEntry("------------------meteo.pl------------------", config.plugins.iptvplayer.fake_separator))
    try:
        optionList.extend(MeteoPL_GetConfigList())
    except Exception:
        printExc()

    optionList.append(getConfigListEntry("-------------------WeebTV-------------------", config.plugins.iptvplayer.fake_separator))
    try:
        optionList.extend(WeebTv_GetConfigList())
    except Exception:
        printExc()

    optionList.append(getConfigListEntry("-----------------FilmOn TV------------------", config.plugins.iptvplayer.fake_separator))
    try:
        optionList.extend(FilmOn_GetConfigList())
    except Exception:
        printExc()

    optionList.append(getConfigListEntry("-------------SkyLineWebCams.com-------------", config.plugins.iptvplayer.fake_separator))
    try:
        optionList.extend(WkylinewebcamsCom_GetConfigList())
    except Exception:
        printExc()

    optionList.append(getConfigListEntry("-----------------Windy Webcams------------------", config.plugins.iptvplayer.fake_separator))
    optionList.append(getConfigListEntry('https://api.windy.com/webcams ' + _("API Key"), config.plugins.iptvplayer.windy_api_key))

    return optionList

###################################################


def gettytul():
    return _('"Web" streams player')


class WebStreamHost(CBaseHostClass):
    # aggregator host - no single site of its own; kept as None so the generic
    # favourite-restore helpers in CBaseHostClass don't trip on a missing attr
    MAIN_URL = None
    MAIN_GROUPED_TAB = [{'alias_id': 'weeb.tv', 'name': 'weeb.tv', 'title': 'https://weeb.tv/', 'url': '', 'icon': 'https://static.weeb.tv/images/weebtv1.png'},
                        {'alias_id': 'meteo.pl', 'name': 'meteo.pl', 'title': 'https://meteo.pl/', 'url': 'https://meteo.pl/', 'icon': 'https://www.meteo.pl/img/napis_glowny_pl_2.png'},
                        {'alias_id': 'webcamera.pl', 'name': 'webcamera.pl', 'title': 'https://webcamera.pl/', 'url': 'https://www.webcamera.pl/', 'icon': 'https://www.webcamera.pl/images/logo_mobile.png'},
                        {'alias_id': 'skylinewebcams.com', 'name': 'skylinewebcams.com', 'title': 'https://skylinewebcams.com/', 'url': 'https://www.skylinewebcams.com/', 'icon': 'https://cdn.skylinewebcams.com/skylinewebcams.png'},
                        {'alias_id': 'filmon.com', 'name': 'filmon_groups', 'title': 'https://filmon.com/', 'url': 'https://www.filmon.com/', 'icon': 'https://static.filmon.com/theme/img/filmon_tv_logo_white.png'},
                        {'alias_id': 'djing.com', 'name': 'djing.com', 'title': 'https://djing.com/', 'url': 'https://djing.com/', 'icon': 'https://djing.com/img/logoog2048.png'},
                        {'alias_id': 'nhl24all.ir', 'name': 'nhl24all.ir', 'title': 'https://nhl24all.ir/', 'url': 'https://api.nhl24all.ir/api/v4/stateshot', 'icon': 'https://upload.wikimedia.org/wikipedia/en/thumb/3/3a/05_NHL_Shield.svg/250px-05_NHL_Shield.svg.png'},
                        {'alias_id': 'livemass.net', 'name': 'livemass.net', 'title': 'https://livemass.net/', 'url': 'https://livemass.net/locations/index.html', 'icon': 'https://livemass.net/images/live/iconclr@2x.png'},
                        {'alias_id': 'worldcam.live', 'name': 'worldcam_root', 'title': 'https://worldcam.live/', 'url': '', 'icon': 'https://worldcam.live/img/logo-wcam.png'},
                        {'alias_id': 'lookcam.com', 'name': 'lookcam_root', 'title': 'https://lookcam.com/', 'url': '', 'icon': 'https://lookcam.com/apple-icon.png'},
                        {'alias_id': 'nadmorski24.pl', 'name': 'nadmorski24_root', 'title': 'https://nadmorski24.pl/kamery', 'url': '', 'icon': 'https://nadmorski24.pl/public/img/n24_logo.png'},
                        {'alias_id': 'bieszczady.live', 'name': 'bieszczady_list', 'title': 'https://www.bieszczady.live/kamery', 'url': '', 'icon': 'https://static.bieszczady.live/images/logo/logo-tr-150px.png'},
                        {'alias_id': 'lantech.com.pl', 'name': 'lantech_list', 'title': 'https://lantech.com.pl/liveszczecin/', 'url': '', 'icon': 'https://lantech.com.pl/wp-content/uploads/2021/07/malelogo.png'},
                        {'alias_id': 'sandiegozoo.org', 'name': 'sdzoo_list', 'title': 'https://zoo.sandiegozoo.org/live-cameras', 'url': '', 'icon': 'https://zoo.sandiegozoo.org/sites/default/files/teaser_image/live_cameras_thumb.jpg'},
                        {'alias_id': 'korbielow.net', 'name': 'korbielow_list', 'title': 'https://korbielow.net/', 'url': '', 'icon': 'https://korbielownet.b-cdn.net/images/apple-touch-icon.png'},
                        {'alias_id': 'szczyrkowski.pl', 'name': 'szczyrk_list', 'title': 'https://www.szczyrkowski.pl/resort/kamery', 'url': '',
                         'icon': 'https://www.szczyrkowski.pl/typo3temp/assets/_processed_/f/3/csm_favicon-192x192_1c23e19e1c.png'},
                        {'alias_id': '40mediagroup.com', 'name': 'media40_list', 'title': 'https://www.40mediagroup.com/', 'url': '', 'icon': 'https://www.40mediagroup.com/images/logo/40media-logo-color.png'},
                        {'alias_id': 'windy.com', 'name': 'windy_root', 'title': 'https://www.windy.com/webcams/', 'url': '', 'icon': 'https://img.windy.com/albums/icons/logo-full.png?w=180'},
                        {'alias_id': 'iptv-org', 'name': 'iptvorg_root', 'title': 'https://github.com/iptv-org/iptv', 'url': '', 'icon': 'https://avatars.githubusercontent.com/u/64318809'},
                        {'alias_id': 'freecasthub', 'name': 'freecasthub_root', 'title': 'https://github.com/freecasthub/public-iptv', 'url': '', 'icon': 'https://avatars.githubusercontent.com/u/193939969'},
                        {'alias_id': 'internet-radio-hq', 'name': 'radiohq_list', 'title': 'https://github.com/Pulham/Internet-Radio-HQ-URL-playlists',
                         'url': 'https://raw.githubusercontent.com/Pulham/Internet-Radio-HQ-URL-playlists/main/Radio%20Stations.m3u', 'icon': 'https://avatars.githubusercontent.com/u/17600859'},
                       ]

    def __init__(self):
        CBaseHostClass.__init__(self)

        # temporary data
        self.currList = []
        self.currItem = {}

        self.filmOnApi = None
        self.webCameraApi = None
        self.meteoPLApi = None
        self.wkylinewebcamsComApi = None
        self.weebTvApi = None
        self.djingComApi = None

    # only the source rows of the main menu show the globe; the source APIs build their rows from dict(cItem),
    # so without this every category / video below would inherit it (also favourites stored that way)
    MAIN_MENU_IMAGE_TYPE = 'WWW'

    @classmethod
    def _dropMainMenuImageType(cls, item):
        if isinstance(item, dict) and item.get('image_type') == cls.MAIN_MENU_IMAGE_TYPE:
            item = dict(item)
            item.pop('image_type', None)
        return item

    def addItem(self, params):
        self.currList.append(params)
        return

    def listsMainMenu(self, tab, forceParams=None):
        if forceParams is None:
            forceParams = {}
        orderList = GetHostsOrderList('iptvplayerwebstreamorder')
        addedAlias = []

        # add in order from order file
        for alias in orderList:
            for item in tab:
                if item['alias_id'] == alias.strip():
                    params = dict(item)
                    params.update(forceParams)
                    self.addDir(params)
                    addedAlias.append(item['alias_id'])
                elif ('!' + item['alias_id']) == alias.strip():
                    addedAlias.append(item['alias_id'])

        # add other streams not listed at order file
        for item in tab:
            if item['alias_id'] not in addedAlias:
                params = dict(item)
                params.update(forceParams)
                self.addDir(params)

    def __getFilmOnIconUrl(self, item):
        icon = ''
        try:
            icon = item.get('big_logo', '')
            if '' == icon:
                icon = item.get('logo_148x148_uri', '')
            if '' == icon:
                icon = item.get('logo', '')
            if '' == icon:
                icon = item.get('logo_uri', '')
        except Exception:
            printExc()
        return ensure_str(icon)

    def __setFilmOn(self):
        if None is self.filmOnApi:
            self.filmOnApi = FilmOnComApi()

    def getFilmOnLink(self, channelID):
        self.__setFilmOn()
        return self.filmOnApi.getUrlForChannel(channelID)

    def getFilmOnGroups(self):
        self.__setFilmOn()
        tmpList = self.filmOnApi.getGroupList()
        for item in tmpList:
            try:
                params = {
                    'name': 'filmon_channels',
                    'title': ensure_str(item['title']),
                    'desc': ensure_str(item['description']),
                    'group_id': item['group_id'],
                    'icon': self.__getFilmOnIconUrl(item)
                }
                self.addDir(params)
            except Exception:
                printExc()

    def getFilmOnChannels(self):
        self.__setFilmOn()
        tmpList = self.filmOnApi.getChannelsListByGroupID(self.currItem['group_id'])
        for item in tmpList:
            try:
                params = {
                    'name': 'filmon_channel',
                    'title': ensure_str(item['title']),
                    'url': item['id'],
                    'desc': ensure_str(item['group']),
                    'seekable': item['seekable'],
                    'icon': self.__getFilmOnIconUrl(item)
                }
                self.addVideo(params)
            except Exception:
                printExc()

    def getWeebTvList(self, url):
        printDBG('getWeebTvList start')
        if None is self.weebTvApi:
            self.weebTvApi = WeebTvApi()
        if '' == config.plugins.iptvplayer.weebtv_login.value.strip():
            # anonymous /api/setPlayer answers -3 for every channel - say so before the user tries
            self.addMarker({'title': _('weeb.tv streams need a weeb.tv account - enter the login in the host configuration (Web streams, WeebTV)')})
        if '' == url:
            tmpList = self.weebTvApi.getCategoriesList()
            for item in tmpList:
                params = dict(item)
                params.update({'name': 'weeb.tv'})
                self.addDir(params)
        else:
            tmpList = self.weebTvApi.getChannelsList(url)
            for item in tmpList:
                item.update({'name': 'weeb.tv', 'good_for_fav': True})
                self.addVideo(item)

    def getWeebTvLink(self, url):
        printDBG("getWeebTvLink url[%s]" % url)
        if None is self.weebTvApi:
            self.weebTvApi = WeebTvApi()
        return self.weebTvApi.getVideoLink(url)

    def getWebCamera(self, cItem):
        printDBG("getWebCamera start cItem[%s]" % cItem)
        if None is self.webCameraApi:
            self.webCameraApi = WebCameraApi()
        tmpList = self.webCameraApi.getList(cItem)
        for item in tmpList:
            if 'video' == item['type']:
                self.addVideo(item)
            elif 'audio' == item['type']:
                self.addAudio(item)
            else:
                self.addDir(item)

    def getWebCameraLink(self, cItem):
        printDBG("getWebCameraLink start")
        if None is self.webCameraApi:
            self.webCameraApi = WebCameraApi()  # a favourite opened before the list
        return self.webCameraApi.getVideoLink(cItem)

    ########################################################
    def getDjingComList(self, cItem):
        printDBG("getDjingComList start")
        if None is self.djingComApi:
            self.djingComApi = DjingComApi()
        tmpList = self.djingComApi.getList(cItem)
        for item in tmpList:
            if 'video' == item['type']:
                self.addVideo(item)
            elif 'audio' == item['type']:
                self.addAudio(item)
            else:
                self.addDir(item)

    def getDjingComLink(self, cItem):
        printDBG("getDjingComLink start")
        if None is self.djingComApi:
            self.djingComApi = DjingComApi()
        urlsTab = self.djingComApi.getVideoLink(cItem)
        return urlsTab

    def getMeteoPLList(self, cItem):
        printDBG("getMeteoPLApiList start")
        if None is self.meteoPLApi:
            self.meteoPLApi = MeteoPLApi()
        tmpList = self.meteoPLApi.getList(cItem)
        for item in tmpList:
            self.addItem(item)

    def getMeteoPLLink(self, cItem):
        printDBG("getMeteoPLLink start")
        if None is self.meteoPLApi:
            self.meteoPLApi = MeteoPLApi()
        urlsTab = self.meteoPLApi.getVideoLink(cItem)
        return urlsTab

    def getWkylinewebcamsComList(self, cItem):
        printDBG("getWkylinewebcamsComList start")
        if None is self.wkylinewebcamsComApi:
            self.wkylinewebcamsComApi = WkylinewebcamsComApi()
        tmpList = self.wkylinewebcamsComApi.getChannelsList(cItem)
        for item in tmpList:
            if 'video' == item.get('type', ''):
                self.addVideo(item)
            else:
                self.addDir(item)

    def getWkylinewebcamsComLink(self, cItem):
        printDBG("getWkylinewebcamsComLink start")
        if None is self.wkylinewebcamsComApi:
            self.wkylinewebcamsComApi = WkylinewebcamsComApi()
        urlsTab = self.wkylinewebcamsComApi.getVideoLink(cItem)
        return urlsTab

    # nhl24all.ir (ex nhl66.ir) - api.nhl24all.ir/api/v4/stateshot lists media_events (v3 is 404 since
    # autumn 2026; anonymous callers only get the "free.vod.sportsnet" flavor);
    # api.nhl24all.ir/api/v2/generate_stream_info -> the HLS master url
    NHL24ALL_API = 'https://api.nhl24all.ir'

    def getNhl24AllList(self, url):
        printDBG("getNhl24AllList start")
        if '/api/v3/' in (url or ''):
            url = ''  # old favourite / order entry
        sts, data = self.cm.getPage(url or (self.NHL24ALL_API + '/api/v4/stateshot'), {'header': {'Referer': 'https://nhl24all.ir/', 'Origin': 'https://nhl24all.ir'}})
        if not sts:
            return
        try:
            data = json_loads(data)
            teams = {t.get('id'): t.get('abbreviation') or t.get('short_name') or '' for t in data.get('teams', []) if isinstance(t, dict)}
            games = {g.get('id'): g for g in data.get('games', []) if isinstance(g, dict)}
            flavorsByEvent = {}
            for fl in data.get('flavors', []):
                for meId in fl.get('media_event_ids', []):
                    flavorsByEvent.setdefault(meId, []).append(fl)
            mediaEvents = data.get('media_events', [])
        except Exception:
            printExc()
            return
        for me in mediaEvents:
            if not isinstance(me, dict):
                continue
            game = games.get(me.get('game_id'), {})
            matchup = ''
            if game:
                matchup = '%s @ %s' % (teams.get(game.get('away_team_id'), '?'), teams.get(game.get('home_team_id'), '?'))
            when = (game.get('start_datetime') or me.get('datetime') or '').replace('T', ' ').replace('Z', ' GMT')
            base = ' - '.join(x for x in (matchup, when, me.get('title', '')) if x)
            desc = me.get('description', '') or base
            # S = scheduled, F = final - anything else is running
            live = game.get('status', '') not in ('F', 'FINAL', 'S', '')
            for fl in flavorsByEvent.get(me.get('id'), []):
                # "premium.*" flavors need a paid-account token generate_stream_info
                # doesn't have for an anonymous caller (verified: always 401s) -
                # skip them instead of listing entries that can never play
                if str(fl.get('id', '')).startswith('premium.'):
                    continue
                title = base + (' [%s]' % fl.get('name', fl.get('id', '')))
                if live:
                    title = '[LIVE] ' + title
                params = {'name': 'nhl24all.ir', 'title': title, 'desc': desc, 'good_for_fav': False,
                          'url': 'nhl24all:%s:%s' % (me.get('id'), fl.get('id', '')),
                          'icon': self.currItem.get('icon', '')}
                self.addVideo(params)

    def getNhl24AllLink(self, cItem):
        printDBG("getNhl24AllLink [%s]" % cItem.get('url', ''))
        try:
            meId, flavorId = cItem['url'].split(':', 2)[1:]
            mediaEventId = int(meId) if str(meId).lstrip('-').isdigit() else meId
        except Exception:
            return []
        sts, data = self.cm.getPage(self.NHL24ALL_API + '/api/v2/generate_stream_info',
                                    {'header': {'Content-Type': 'application/json', 'Referer': 'https://nhl24all.ir/', 'Origin': 'https://nhl24all.ir'}, 'raw_post_data': True},
                                    json_dumps({'media_event_id': mediaEventId, 'flavor_id': flavorId}))
        if not sts:
            return []
        try:
            info = json_loads(data)
        except Exception:
            printExc()
            return []
        streamUrl = info.get('url') if isinstance(info, dict) else ''
        if not streamUrl:
            return []
        streamUrl = strwithmeta(streamUrl, {'Referer': 'https://nhl24all.ir/', 'Origin': 'https://nhl24all.ir', 'User-Agent': 'Mozilla/5.0'})
        return [{'name': 'nhl24all.ir', 'url': streamUrl}]

    # livemass.net - FSSP / Traditional Latin Mass live + recorded (Wowza HLS).
    # locations/index.html links to <loc>.html; each embeds the .m3u8 directly.
    def getLiveMassList(self, url):
        printDBG("getLiveMassList start")
        sts, data = self.cm.getPage(url or 'https://livemass.net/locations/index.html', {'header': {'Referer': 'https://livemass.net/'}})
        if not sts:
            return
        seen = set()
        for href, name in re.findall(r'<a[^>]+href="([a-z0-9-]+\.html)"[^>]*>([^<]{3,70})</a>', data, re.I):
            if href in ('index.html',) or href in seen:
                continue
            seen.add(href)
            self.addVideo({'name': 'livemass.net', 'title': self.cleanHtmlStr(name),
                           'url': 'https://livemass.net/locations/' + href, 'good_for_fav': True,
                           'icon': self.currItem.get('icon', ''), 'desc': self.cleanHtmlStr(name)})

    def getLiveMassLink(self, cItem):
        printDBG("getLiveMassLink [%s]" % cItem.get('url', ''))
        sts, data = self.cm.getPage(cItem['url'], {'header': {'Referer': 'https://livemass.net/'}})
        if not sts:
            return []
        urls = re.findall(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', data)
        if not urls:
            return []
        # a location page can also carry an ad/preview .m3u8 - prefer the
        # broadcaster's own streaming host; stable sort keeps document order
        # (first hit) within the same priority
        urls.sort(key=lambda u: 0 if re.search(r'livemass(?:stream)?\.net', u) else 1)
        return [{'name': 'livemass.net', 'url': strwithmeta(urls[0], {'Referer': 'https://livemass.net/', 'User-Agent': 'Mozilla/5.0'})}]

    #############################################################
    # Generic M3U/M3U8 playlist ingestion - shared by iptv-org, freecasthub's
    # public-iptv and Internet-Radio-HQ-URL-playlists. All three publish plain
    # M3U files pointing at the broadcasters'/stations' own public streams, so
    # there is no per-item resolving to do: the item 'url' is already the final
    # stream and is handled by the generic branch in getLinksForItem.
    @staticmethod
    def _parseM3U(data):
        items = []
        title, icon, group, headers = '', '', '', {}
        for line in data.replace('\r', '').split('\n'):
            line = line.strip()
            if not line:
                continue
            if line.startswith('#EXTINF:'):
                m = re.search(r'tvg-logo="([^"]*)"', line)
                icon = m.group(1) if m else ''
                m = re.search(r'group-title="([^"]*)"', line)
                group = m.group(1) if m else ''
                # title is what follows the last comma that is not inside a
                # quoted attribute value (group-title="A, B" must not split it)
                if ',' in line:
                    m = re.match(r'#EXTINF:[^,"]*(?:"[^"]*"[^,"]*)*,(.*)$', line)
                    title = (m.group(1) if m else line.rsplit(',', 1)[-1]).strip()
                else:
                    title = ''
                if title.startswith('- '):  # radio-HQ playlist uses "#EXTINF:0, - Name"
                    title = title[2:].strip()
            elif line.startswith('#EXTVLCOPT:'):
                opt = line[len('#EXTVLCOPT:'):].strip()
                key, _sep, val = opt.partition('=')
                key = key.strip().lower()
                if key == 'http-user-agent':
                    headers['User-Agent'] = val.strip()
                elif key == 'http-referrer':
                    headers['Referer'] = val.strip()
            elif line.startswith('#EXTHTTP:'):
                try:
                    for key, val in json_loads(line[len('#EXTHTTP:'):].strip()).items():
                        headers[key] = val
                except Exception:
                    printExc()
            elif line.startswith('#'):
                continue
            else:
                if title:
                    # headers stay a plain dict on the item (not folded into a
                    # strwithmeta url here) so they survive json_dumps when the
                    # channel is saved as a favourite; they are applied in
                    # WebStreamHost.getLinksForItem
                    items.append({'title': title, 'url': line, 'icon': icon, 'group': group, 'headers': dict(headers)})
                title, icon, group, headers = '', '', '', {}
        return items

    def _addM3UList(self, url, name, asAudio=False):
        sts, data = self.cm.getPage(url)
        if not sts:
            return
        for item in self._parseM3U(data):
            params = {'name': name, 'title': item['title'], 'url': item['url'], 'icon': item['icon'],
                      'desc': item['group'], 'good_for_fav': True}
            if item['headers']:
                params['http_headers'] = item['headers']
            if asAudio:
                self.addAudio(params)
            else:
                self.addVideo(params)

    # iptv-org (github.com/iptv-org/iptv) - community-curated collection of
    # free-to-air/officially public streams, only takes channels the
    # broadcasters themselves stream openly. Browsed via the project's own
    # categories.json/countries.json, each leading to a per-category/-country
    # .m3u file (iptv-org.github.io/iptv/categories|countries/<key>.m3u).
    IPTVORG_API = 'https://iptv-org.github.io/api'
    IPTVORG_M3U = 'https://iptv-org.github.io/iptv'

    def getIptvOrgRoot(self):
        printDBG("getIptvOrgRoot start")
        self.addDir({'name': 'iptvorg_taxonomy', 'title': _('Categories'), 'iptvorg_kind': 'categories'})
        self.addDir({'name': 'iptvorg_taxonomy', 'title': _('Countries'), 'iptvorg_kind': 'countries'})

    def getIptvOrgTaxonomy(self, cItem):
        printDBG("getIptvOrgTaxonomy start")
        kind = cItem.get('iptvorg_kind', 'categories')
        sts, data = self.cm.getPage('%s/%s.json' % (self.IPTVORG_API, kind))
        if not sts:
            return
        try:
            entries = json_loads(data)
        except Exception:
            printExc()
            return
        if not isinstance(entries, list):
            return
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if kind == 'countries':
                key, label = entry.get('code', ''), ('%s %s' % (entry.get('flag', ''), entry.get('name', ''))).strip()
            else:
                key, label = entry.get('id', ''), entry.get('name', '')
            if not key or not label:
                continue
            self.addDir({'name': 'iptvorg_list', 'title': label, 'iptvorg_kind': kind, 'iptvorg_key': key})

    def getIptvOrgList(self, cItem):
        printDBG("getIptvOrgList start")
        kind = cItem.get('iptvorg_kind', 'categories')
        key = cItem.get('iptvorg_key', '')
        folder = 'countries' if kind == 'countries' else 'categories'
        self._addM3UList('%s/%s/%s.m3u' % (self.IPTVORG_M3U, folder, key.lower()), 'iptvorg_video')

    # freecasthub/public-iptv (github.com/freecasthub/public-iptv) - a smaller,
    # explicitly "legal, no piracy" curated collection, split into a handful
    # of category playlists.
    FREECASTHUB_BASE = 'https://raw.githubusercontent.com/freecasthub/public-iptv/main'
    FREECASTHUB_CATS = (('news', 'News'), ('sports', 'Sport'), ('weather', 'Weather'), ('education', 'Education'), ('playlist', 'All'))

    def getFreecasthubRoot(self):
        printDBG("getFreecasthubRoot start")
        for key, label in self.FREECASTHUB_CATS:
            self.addDir({'name': 'freecasthub_list', 'title': _(label), 'freecasthub_key': key})

    def getFreecasthubList(self, cItem):
        printDBG("getFreecasthubList start")
        key = cItem.get('freecasthub_key', 'playlist')
        self._addM3UList('%s/%s.m3u' % (self.FREECASTHUB_BASE, key), 'freecasthub_video')

    # Internet-Radio-HQ-URL-playlists (github.com/Pulham/...) - a single curated
    # high-quality internet radio M3U, no submenu needed.
    def getRadioHqList(self, url):
        printDBG("getRadioHqList start")
        self._addM3UList(url or 'https://raw.githubusercontent.com/Pulham/Internet-Radio-HQ-URL-playlists/main/Radio%20Stations.m3u', 'radiohq_audio', asAudio=True)

    #############################################################
    # Windy Webcams (api.windy.com/webcams) - the listing API (categories/
    # countries/webcams) needs a free key from https://api.windy.com/webcams,
    # pasted into Settings -> "Web streams" -> Windy Webcams. The player embed
    # pages themselves are public (no key) and are scraped for the actual
    # .m3u8/.mp4 source, since the API only hands back an embed URL, not a
    # direct stream.
    WINDY_API = 'https://api.windy.com/webcams/api/v3'
    WINDY_PAGE_SIZE = 50

    def _windyGet(self, path):
        apiKey = config.plugins.iptvplayer.windy_api_key.value.strip()
        sts, data = self.cm.getPage(self.WINDY_API + path, {'header': {'x-windy-api-key': apiKey, 'Accept': 'application/json'}})
        if not sts:
            return {}
        try:
            data = json_loads(data)
        except Exception:
            printExc()
            return {}
        return data if isinstance(data, dict) else {}

    def getWindyRoot(self):
        printDBG("getWindyRoot start")
        if '' == config.plugins.iptvplayer.windy_api_key.value.strip():
            self.addMarker({'title': _('Missing API key - set it in Settings, Web streams, Windy Webcams')})
            return
        self.addDir({'name': 'windy_taxonomy', 'title': _('Categories'), 'windy_kind': 'categories'})
        self.addDir({'name': 'windy_taxonomy', 'title': _('Countries'), 'windy_kind': 'countries'})

    def getWindyTaxonomy(self, cItem):
        printDBG("getWindyTaxonomy start")
        kind = cItem.get('windy_kind', 'categories')
        data = self._windyGet('/%s?lang=en' % kind)
        if not data:
            return
        items = data.get(kind, [])
        if not isinstance(items, list):
            return
        for item in items:
            if not isinstance(item, dict):
                continue
            params = {'name': 'windy_list', 'title': item.get('name', str(item.get('id', item.get('code', '')))),
                      'windy_kind': kind, 'windy_id': str(item.get('id', item.get('code', ''))), 'windy_offset': 0}
            self.addDir(params)

    def getWindyList(self, cItem):
        printDBG("getWindyList start")
        kind = cItem.get('windy_kind', 'categories')
        wid = cItem.get('windy_id', '')
        offset = cItem.get('windy_offset', 0)
        data = self._windyGet('/webcams?%s=%s&limit=%d&offset=%d&include=images,location&lang=en' % (kind, wid, self.WINDY_PAGE_SIZE, offset))
        if not data:
            return
        for cam in data.get('webcams', []):
            if not isinstance(cam, dict):
                continue
            loc = cam.get('location', {}) or {}
            place = ', '.join(x for x in (loc.get('city', ''), loc.get('country', '')) if x)
            title = cam.get('title', '')
            params = {'name': 'windy_video', 'title': ('%s (%s)' % (title, place)) if place else title,
                      'icon': ((cam.get('images', {}) or {}).get('current', {}) or {}).get('preview', ''),
                      'desc': place, 'windy_id': str(cam.get('webcamId', '')), 'url': str(cam.get('webcamId', '')),
                      'good_for_fav': True}
            self.addVideo(params)
        if offset + self.WINDY_PAGE_SIZE < data.get('total', 0):
            params = dict(cItem)
            params.update({'title': _('Next page'), 'windy_offset': offset + self.WINDY_PAGE_SIZE})
            self.addDir(params)

    def getWindyLink(self, cItem):
        printDBG("getWindyLink [%s]" % cItem)
        camId = cItem.get('windy_id', '') or cItem.get('url', '')
        data = self._windyGet('/webcams/%s?include=player' % camId)
        if not data:
            return []
        player = data.get('player') or {}
        webcams = data.get('webcams') or []
        if not player and isinstance(webcams, list) and webcams and isinstance(webcams[0], dict):
            player = webcams[0].get('player', {}) or {}
        if not isinstance(player, dict):
            return []
        for key in ('live', 'day'):
            embedUrl = player.get(key, '')
            if not embedUrl:
                continue
            sts, html = self.cm.getPage(embedUrl, {'header': {'Referer': 'https://www.windy.com/'}})
            if not sts:
                continue
            m = re.search(r'''["'](https?://[^"'\s]+\.m3u8[^"'\s]*)["']''', html)
            if not m:
                m = re.search(r'''["'](https?://[^"'\s]+\.mp4[^"'\s]*)["']''', html)
            if m:
                return [{'name': 'windy.com', 'url': strwithmeta(m.group(1), {'Referer': 'https://www.windy.com/'})}]
        return []

    #############################################################
    # Webcam sites below: every row keeps the camera page (or the API id) as
    # 'url' and the stream is fetched fresh at play time (worldcam/lookcam
    # links carry a short-lived token), so a favourite plays without its list.
    def _camHeader(self, referer='', accept='*/*'):
        header = {'User-Agent': self.cm.getDefaultUserAgent(), 'Accept': accept}
        if referer:
            header['Referer'] = referer
        return header

    def _camGetPage(self, url, referer=''):
        return self.cm.getPage(url, {'header': self._camHeader(referer)})

    @staticmethod
    def _camAbsUrl(base, url):
        return (base + url) if url.startswith('/') else url

    @staticmethod
    def _camUnique(items):
        # order kept, a page lists the same camera / player more than once
        ret = []
        for item in items:
            if item not in ret:
                ret.append(item)
        return ret

    def _camHlsLinks(self, name, m3u8Url, referer=''):
        meta = {'User-Agent': self.cm.getDefaultUserAgent()}
        if referer:
            meta['Referer'] = referer
        retlist = []
        # checkContent: an offline camera answers with an empty playlist - no link then
        for item in getDirectM3U8Playlist(strwithmeta(m3u8Url, meta), checkExt=False, checkContent=True):
            retlist.append({'name': ('%s %s' % (name, item.get('name', ''))).strip(), 'url': item['url']})
        return retlist

    def _camMultiHlsLinks(self, name, streams, referer=''):
        # streams: (label, m3u8 url) of every player on one camera page; the label only when there are several
        retlist = []
        for label, m3u8Url in streams:
            retlist.extend(self._camHlsLinks(name if len(streams) == 1 else '%s [%s]' % (name, label), m3u8Url, referer))
        return retlist

    # worldcam.live - IP cameras (mostly Poland); /en/webcams lists all of them,
    # /en/webcams/<category> a part. The camera page has playerSettings.source =
    # base64 of the HLS url with a fresh token (without the token: 403).
    WORLDCAM_URL = 'https://worldcam.live'

    def getWorldcamRoot(self):
        printDBG("getWorldcamRoot start")
        sts, data = self._camGetPage(self.WORLDCAM_URL + '/en/webcams')
        if not sts:
            return
        self.addDir({'name': 'worldcam_list', 'title': _('All'), 'url': self.WORLDCAM_URL + '/en/webcams'})
        seen = set()
        for href, title in re.findall(r'href="(https://worldcam\.live/en/webcams/[a-z0-9-]+)"[^>]*>([^<]+)<', data):
            if href in seen:
                continue
            seen.add(href)
            self.addDir({'name': 'worldcam_list', 'title': self.cleanHtmlStr(title), 'url': href})

    def getWorldcamList(self, cItem):
        printDBG("getWorldcamList start")
        sts, data = self._camGetPage(cItem.get('url') or (self.WORLDCAM_URL + '/en/webcams'))
        if not sts:
            return
        seen = set()
        titles = {}
        # the list only names the town (several cameras can share it, they get a number); the
        # <a title> has town + country, the <p class="location"> text is cut ("Polan...")
        for href, linkTitle, block in re.findall(r'<a href="(/en/webcam/[^"]+)"[^>]*?title="([^"]*)"[^>]*>(.*?)</a>\s*<p class="location">', data, re.S):
            if href in seen:
                continue
            seen.add(href)
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'''alt=['"]([^'"]+)['"]''')[0])
            title = re.sub(r'^Webcam\s*-\s*', '', title) or href.rsplit('/', 1)[-1]
            titles[title] = titles.get(title, 0) + 1
            if titles[title] > 1:
                title = '%s (%d)' % (title, titles[title])
            icon = self.cm.ph.getSearchGroups(block, r'''data-src=['"]([^'"]+\.jpg)['"]''')[0]
            self.addVideo({'name': 'worldcam_video', 'title': title, 'url': self.WORLDCAM_URL + href,
                           'icon': self._camAbsUrl(self.WORLDCAM_URL, icon),
                           'desc': re.sub(r'^Webcam\s*-\s*', '', self.cleanHtmlStr(linkTitle))})

    def getWorldcamLink(self, cItem):
        printDBG("getWorldcamLink [%s]" % cItem.get('url', ''))
        sts, data = self._camGetPage(cItem['url'], self.WORLDCAM_URL + '/')
        if not sts:
            return []
        # no playerSettings = camera offline (archive only)
        m = re.search(r'"source"\s*:\s*"([^"]+)"', data)
        if not m:
            return []
        try:
            url = ensure_str(b64decode(m.group(1).replace('\\/', '/')))
        except Exception:
            printExc()
            return []
        if not url.startswith('http'):
            return []
        return self._camHlsLinks('worldcam.live', url, self.WORLDCAM_URL + '/')

    # lookcam.com - public API (lookcam.com/developers, no key for browse and
    # playback): /browse/streams lists the live cameras (18+ streams are left
    # out by default), /streams/<id>/playback gives the signed Streamway manifest.
    LOOKCAM_API = 'https://api.lookcam.com/v1'
    LOOKCAM_PAGE_SIZE = 50

    def _lookcamGet(self, path):
        header = self._camHeader('https://lookcam.com/', 'application/json')
        header['Origin'] = 'https://lookcam.com'
        sts, data = self.cm.getPage(self.LOOKCAM_API + path, {'header': header})
        if not sts:
            return None
        try:
            return json_loads(data)
        except Exception:
            printExc()
            return None

    def getLookcamRoot(self):
        printDBG("getLookcamRoot start")
        self.addDir({'name': 'lookcam_list', 'title': _('All'), 'lookcam_lang': '', 'page': 1})
        data = self._lookcamGet('/browse/languages')
        if not isinstance(data, list):
            return
        # the API names the languages in Polish only (no lang parameter)
        for lang in data:
            if not isinstance(lang, dict) or not lang.get('code'):
                continue
            self.addDir({'name': 'lookcam_list', 'title': '%s (%s)' % (ensure_str(lang.get('name') or lang['code']), lang.get('live_count', 0)),
                         'lookcam_lang': ensure_str(lang['code']), 'page': 1})

    def getLookcamList(self, cItem):
        printDBG("getLookcamList start")
        try:
            page = max(1, int(cItem.get('page', 1)))
        except (TypeError, ValueError):
            page = 1
        lang = cItem.get('lookcam_lang', '')
        # also the Jump template of the pager (the list itself is built from 'page')
        urlTpl = self.LOOKCAM_API + '/browse/streams?page={page}&per_page=%d&sort=viewers' % self.LOOKCAM_PAGE_SIZE
        if lang:
            urlTpl += '&language=' + lang
        data = self._lookcamGet(urlTpl.format(page=page)[len(self.LOOKCAM_API):])
        if not isinstance(data, dict):
            return
        for stream in data.get('items') or []:
            if not isinstance(stream, dict) or not stream.get('id') or stream.get('is_mature'):
                continue
            user = stream.get('user') or {}
            # every camera name starts with "LIVE: " - the list is live-only anyway
            title = re.sub(r'^LIVE:\s*', '', ensure_str(stream.get('name') or user.get('username_title') or stream['id']))
            tags = ', '.join(ensure_str(t) for t in (stream.get('tags') or []) if t)
            self.addVideo({'name': 'lookcam_video', 'title': title, 'url': ensure_str(stream['id']),
                           'lookcam_user': ensure_str(user.get('username') or ''),
                           'icon': ensure_str(stream.get('thumbnail_url') or ''), 'desc': tags})
        # total counts the 18+ streams too, so the last page can be a short one
        try:
            lastPage = (int(data.get('total') or 0) + self.LOOKCAM_PAGE_SIZE - 1) // self.LOOKCAM_PAGE_SIZE
        except (TypeError, ValueError):
            lastPage = 0
        addPagingItems(self, cItem, page, bool(data.get('has_more')), lastPage, urlTpl)

    def getLookcamLink(self, cItem):
        printDBG("getLookcamLink [%s]" % cItem.get('url', ''))
        data = self._lookcamGet('/streams/%s/playback' % cItem.get('url', ''))
        if not (isinstance(data, dict) and data.get('manifest_url')) and cItem.get('lookcam_user'):
            # the stream id can change when a camera restarts - a favourite asks its channel for the current one
            channel = self._lookcamGet('/channels/%s' % cItem['lookcam_user'])
            stream = channel.get('stream') if isinstance(channel, dict) else None
            if isinstance(stream, dict) and stream.get('id'):
                data = self._lookcamGet('/streams/%s/playback' % stream['id'])
        if not (isinstance(data, dict) and data.get('manifest_url')):
            return []
        # api.streamway.io/.../manifest redirects to the signed edge .m3u8
        return self._camHlsLinks('lookcam.com', ensure_str(data['manifest_url']), 'https://lookcam.com/')

    # nadmorski24.pl - Baltic coast cameras; one page with all cameras, the
    # category filter (<option class="jsCameraCategory">) is client side.
    # player.nadmorski24.pl/_camera?id=<n> has the HLS url in <source>.
    NADMORSKI24_URL = 'https://nadmorski24.pl'

    def getNadmorski24Root(self):
        printDBG("getNadmorski24Root start")
        sts, data = self._camGetPage(self.NADMORSKI24_URL + '/kamery')
        if not sts:
            return
        cats = re.findall(r'<option class="jsCameraCategory"[^>]*data-category="([^"]+)"[^>]*>([^<]+)</option>', data)
        if not cats:
            cats = [('category_all', _('All'))]
        for catId, title in cats:
            self.addDir({'name': 'nadmorski24_list', 'title': self.cleanHtmlStr(title), 'nadmorski24_cat': catId})

    def getNadmorski24List(self, cItem):
        printDBG("getNadmorski24List start")
        cat = cItem.get('nadmorski24_cat', 'category_all')
        sts, data = self._camGetPage(self.NADMORSKI24_URL + '/kamery')
        if not sts:
            return
        seen = set()
        for item in re.findall(r'(<a\s[^>]*class="jsCameraItem.*?</a>)', data, re.S):
            camId = self.cm.ph.getSearchGroups(item, r'''href=['"]/kamery/([0-9]+)-''')[0]
            if not camId or camId in seen:
                continue
            if cat != 'category_all' and self.cm.ph.getSearchGroups(item, r'''data-category=['"]([^'"]+)['"]''')[0] != cat:
                continue
            seen.add(camId)
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'''data-camera-name=['"]([^'"]+)['"]''')[0]) or camId
            icon = self.cm.ph.getSearchGroups(item, r'''<img[^>]+src=['"](/publicTmp/[^'"]+)['"]''')[0]
            self.addVideo({'name': 'nadmorski24_video', 'title': title,
                           'url': 'https://player.nadmorski24.pl/_camera?id=%s' % camId,
                           'icon': self._camAbsUrl(self.NADMORSKI24_URL, icon)})

    def getNadmorski24Link(self, cItem):
        printDBG("getNadmorski24Link [%s]" % cItem.get('url', ''))
        sts, data = self._camGetPage(cItem['url'], self.NADMORSKI24_URL + '/')
        if not sts:
            return []
        url = self.cm.ph.getSearchGroups(data, r'''<source[^>]+src=['"]([^'"]+\.m3u8[^'"]*)['"]''')[0]
        if not url:
            return []
        return self._camHlsLinks('nadmorski24.pl', url, 'https://player.nadmorski24.pl/')

    # bieszczady.live - Bieszczady mountains; the camera page embeds
    # player.bieszczady.live/kamera/<slug>, which has streamUrl = the HLS url.
    def getBieszczadyList(self, cItem):
        printDBG("getBieszczadyList start")
        sts, data = self._camGetPage('https://www.bieszczady.live/kamery')
        if not sts:
            return
        seen = set()
        for slug, icon, title, rest in re.findall(r'<a href="/kamery-bieszczady/([^"]+)"><img[^>]+?data-src="([^"]+)".*?<h6><a[^>]*>([^<]+)</a></h6>(.*?)</a>', data, re.S):
            if slug in seen:
                continue
            seen.add(slug)
            self.addVideo({'name': 'bieszczady_video', 'title': self.cleanHtmlStr(title), 'url': 'https://player.bieszczady.live/kamera/' + slug,
                           'icon': icon, 'desc': self.cleanHtmlStr(rest)})

    def getBieszczadyLink(self, cItem):
        printDBG("getBieszczadyLink [%s]" % cItem.get('url', ''))
        sts, data = self._camGetPage(cItem['url'], 'https://www.bieszczady.live/')
        if not sts:
            return []
        url = self.cm.ph.getSearchGroups(data, r'''streamUrl\s*=\s*['"]([^'"]+)['"]''')[0]
        if not url:
            url = self.cm.ph.getSearchGroups(data, r'''<source[^>]+src=['"]([^'"]+\.m3u8[^'"]*)['"]''')[0]
        if not url:
            return []
        return self._camHlsLinks('bieszczady.live', url, 'https://player.bieszczady.live/')

    # lantech.com.pl LiveSzczecin - Szczecin and the coast; a camera page embeds
    # one or more _lantech/kamery*.php?cam=<id> players with
    # serverip + cam -> https://<serverip>/hls/<cam>/index.m3u8.
    def getLantechList(self, cItem):
        printDBG("getLantechList start")
        sts, data = self._camGetPage('https://lantech.com.pl/liveszczecin/')
        if not sts:
            return
        seen = set()
        for href, icon, title in re.findall(r'<a href="(https://lantech\.com\.pl/[^"]+)" target="_self"><img[^>]+?src="([^"]+)"[^>]*></a><p[^>]*>(.*?)</p>', data, re.S):
            # the fibre TV offer is in the same grid but has no camera
            if href in seen or 'telewizja-swiatlowodowa' in href:
                continue
            seen.add(href)
            self.addVideo({'name': 'lantech_video', 'title': self.cleanHtmlStr(title), 'url': href, 'icon': icon})

    def getLantechLink(self, cItem):
        printDBG("getLantechLink [%s]" % cItem.get('url', ''))
        sts, data = self._camGetPage(cItem['url'])
        if not sts:
            return []
        streams = []
        for playerUrl in self._camUnique(re.findall(r'''src=['"](https?://lantech\.com\.pl/_lantech/kamery[^'"]*?\.php\?cam=[^'"&]+)''', data)):
            sts, html = self._camGetPage(playerUrl, cItem['url'])
            if not sts:
                continue
            server = self.cm.ph.getSearchGroups(html, r'''serverip\s*=\s*['"]([^'"]+)['"]''')[0]
            cam = self.cm.ph.getSearchGroups(html, r'''var\s+cam\s*=\s*['"]([^'"]+)['"]''')[0]
            if server and cam:
                streams.append((cam, 'https://%s/hls/%s/index.m3u8' % (server, cam)))
        return self._camMultiHlsLinks('lantech.com.pl', streams, 'https://lantech.com.pl/')

    # San Diego Zoo - the camera pages embed Camzone players
    # (<channel>.secureplayer.camzonecdn.com/...?channel=<channel>), the stream is
    # <channel>.hls.camzonecdn.com/CamzoneStreams/<channel>/Playlist.m3u8 (open, no token).
    SDZOO_URL = 'https://zoo.sandiegozoo.org'

    def getSdZooList(self, cItem):
        printDBG("getSdZooList start")
        sts, data = self._camGetPage(self.SDZOO_URL + '/live-cameras')
        if not sts:
            return
        seen = set()
        for href, icon, title in re.findall(r'<a href="(/cams/[^"]+)"[^>]*><img[^>]+?src="([^"]+)".*?<h3><a[^>]*>([^<]+)</a></h3>', data, re.S):
            if href in seen:
                continue
            seen.add(href)
            icon = icon.replace('&amp;', '&')
            self.addVideo({'name': 'sdzoo_video', 'title': self.cleanHtmlStr(title), 'url': self.SDZOO_URL + href,
                           'icon': self._camAbsUrl(self.SDZOO_URL, icon)})

    def getSdZooLink(self, cItem):
        printDBG("getSdZooLink [%s]" % cItem.get('url', ''))
        sts, data = self._camGetPage(cItem['url'])
        if not sts:
            return []
        # a page can still carry a retired channel next to the current one (giant panda) - its playlist is a 404
        channels = self._camUnique(re.findall(r'''camzonecdn\.com/[^'"]*?[?&](?:amp;)?channel=([a-zA-Z0-9_-]+)''', data))
        streams = [(channel, 'https://%s.hls.camzonecdn.com/CamzoneStreams/%s/Playlist.m3u8' % (channel, channel)) for channel in channels]
        return self._camMultiHlsLinks('sandiegozoo.org', streams)

    # 40mediagroup.com - Latin American Spanish channels (ENT, TotalMusic); every
    # /canales/<slug>/ page carries the open HLS master as data-src.
    MEDIA40_URL = 'https://www.40mediagroup.com'

    def getMedia40List(self, cItem):
        printDBG("getMedia40List start")
        sts, data = self._camGetPage(self.MEDIA40_URL + '/canales/')
        if not sts:
            return
        # not every channel has a tile (TotalMusic Dance / Concerts only a plain link): every
        # aria-label link counts, the logo follows the /images/channels/<slug>.png scheme
        seen = set()
        for slug, title in re.findall(r'<a href="/canales/([a-z0-9-]+)/"[^>]*?aria-label="([^"]+)"', data):
            if slug in seen:
                continue
            seen.add(slug)
            # some buttons are labelled "Ver <channel>" (watch ...)
            title = re.sub(r'^Ver\s+', '', self.cleanHtmlStr(title))
            self.addVideo({'name': 'media40_video', 'title': title, 'url': '%s/canales/%s/' % (self.MEDIA40_URL, slug),
                           'icon': '%s/images/channels/%s.png' % (self.MEDIA40_URL, slug)})

    def getMedia40Link(self, cItem):
        printDBG("getMedia40Link [%s]" % cItem.get('url', ''))
        sts, data = self._camGetPage(cItem['url'])
        if not sts:
            return []
        url = self.cm.ph.getSearchGroups(data, r'''data-src=['"](https?://[^'"]+\.m3u8[^'"]*)['"]''')[0]
        if not url:
            return []
        return self._camHlsLinks('40mediagroup.com', url, self.MEDIA40_URL + '/')

    # korbielow.net - Pilsko / Korbielów ski area; the camera pages (linked from
    # every one of them) embed Flussonic players <base>/embed.html, the stream
    # is <base>/index.m3u8.
    KORBIELOW_URL = 'https://korbielow.net'

    def getKorbielowList(self, cItem):
        printDBG("getKorbielowList start")
        sts, data = self._camGetPage(self.KORBIELOW_URL + '/kamery-solisko/')
        if not sts:
            return
        seen = set()
        for href, title in re.findall(r'<a href="(https://korbielow\.net/[^"]*kamer[^"]*)"[^>]*>([^<]+)</a>', data):
            if href in seen:
                continue
            seen.add(href)
            self.addVideo({'name': 'korbielow_video', 'title': self.cleanHtmlStr(title), 'url': href,
                           'icon': cItem.get('icon', '')})

    def getKorbielowLink(self, cItem):
        printDBG("getKorbielowLink [%s]" % cItem.get('url', ''))
        sts, data = self._camGetPage(cItem['url'])
        if not sts:
            return []
        bases = self._camUnique(re.findall(r'''<iframe[^>]+src=['"](https?://[^'"]+?)/embed\.html''', data))
        streams = [(str(idx + 1), base + '/index.m3u8') for idx, base in enumerate(bases)]
        return self._camMultiHlsLinks('korbielow.net', streams, self.KORBIELOW_URL + '/')

    # szczyrkowski.pl (Szczyrk Mountain Resort) - the camera pages embed
    # player.webcamera.pl, resolved by urlparser (parserWEBCAMERAPL).
    SZCZYRK_URL = 'https://www.szczyrkowski.pl'

    def getSzczyrkList(self, cItem):
        printDBG("getSzczyrkList start")
        sts, data = self._camGetPage(self.SZCZYRK_URL + '/resort/kamery')
        if not sts:
            return
        seen = set()
        for href, block, title in re.findall(r'<a href="(/resort/kamery/[^"]+)">(.*?)</a>\s*<figcaption[^>]*>(.*?)</figcaption>', data, re.S):
            if href in seen:
                continue
            seen.add(href)
            icon = self.cm.ph.getSearchGroups(block, r'''<img[^>]+src=['"]([^'"]+)['"]''')[0]
            self.addVideo({'name': 'szczyrk_video', 'title': self.cleanHtmlStr(title), 'url': self.SZCZYRK_URL + href,
                           'icon': self._camAbsUrl(self.SZCZYRK_URL, icon)})

    def getSzczyrkLink(self, cItem):
        printDBG("getSzczyrkLink [%s]" % cItem.get('url', ''))
        sts, data = self._camGetPage(cItem['url'])
        if not sts:
            return []
        url = self.cm.ph.getSearchGroups(data, r'''<iframe[^>]+src=['"]((?:https?:)?//player\.webcamera\.pl/[^'"]+)['"]''')[0]
        if not url:
            return []
        if url.startswith('//'):
            url = 'https:' + url
        return self.up.getVideoLinkExt(url)

    @staticmethod
    def _itemUrlWithHeaders(url, cItem):
        headers = cItem.get('http_headers') or {}
        return strwithmeta(url, dict(headers)) if headers else url

    def getLinksForItem(self, cItem):
        # single resolver for a video/audio entry, used both for normal
        # browsing (IPTVHost.getLinksForVideo) and for a restored favourite
        # (getLinksForFavourite) - so it must work from the plain item dict
        name = cItem.get('name', '')
        url = cItem.get('url', '')
        printDBG("WebStreamHost.getLinksForItem name[%s] url[%s]" % (name, url))

        urlList = None
        if 'weeb.tv' in name:
            url = self.getWeebTvLink(url)
        elif name == 'filmon_channel':
            urlList = self.getFilmOnLink(channelID=url)
        elif name == 'djing.com':
            urlList = self.getDjingComLink(cItem)
        elif name == 'meteo.pl':
            urlList = self.getMeteoPLLink(cItem)
        elif name == 'skylinewebcams.com':
            urlList = self.getWkylinewebcamsComLink(cItem)
        elif name == 'webcamera.pl':
            urlList = self.getWebCameraLink(cItem)
        elif name == 'nhl24all.ir':
            urlList = self.getNhl24AllLink(cItem)
        elif name == 'livemass.net':
            urlList = self.getLiveMassLink(cItem)
        elif name == 'windy_video':
            urlList = self.getWindyLink(cItem)
        elif name == 'worldcam_video':
            urlList = self.getWorldcamLink(cItem)
        elif name == 'lookcam_video':
            urlList = self.getLookcamLink(cItem)
        elif name == 'nadmorski24_video':
            urlList = self.getNadmorski24Link(cItem)
        elif name == 'bieszczady_video':
            urlList = self.getBieszczadyLink(cItem)
        elif name == 'lantech_video':
            urlList = self.getLantechLink(cItem)
        elif name == 'sdzoo_video':
            urlList = self.getSdZooLink(cItem)
        elif name == 'media40_video':
            urlList = self.getMedia40Link(cItem)
        elif name == 'korbielow_video':
            urlList = self.getKorbielowLink(cItem)
        elif name == 'szczyrk_video':
            urlList = self.getSzczyrkLink(cItem)

        if isinstance(urlList, list):
            return urlList

        if not (isinstance(url, basestring) and url):
            return []

        retlist = []
        url = urlparser.decorateUrl(self._itemUrlWithHeaders(url, cItem))
        iptv_proto = url.meta.get('iptv_proto', '')
        if 'm3u8' == iptv_proto:
            for item in getDirectM3U8Playlist(url, checkExt=False):
                retlist.append({'name': item['name'], 'url': item['url']})
        elif 'f4m' == iptv_proto:
            for item in getF4MLinksWithMeta(url, checkExt=False):
                retlist.append({'name': item['name'], 'url': item['url']})
        elif '://' in url:
            if 'balkanstream.com' in url and '' == strwithmeta(url).meta.get('User-Agent', ''):
                url.meta['User-Agent'] = 'Mozilla/5.0'
            retlist.append({'name': 'Link', 'url': url})
        return retlist

    def getLinksForVideo(self, cItem):
        # same entry point as the other CBaseHostClass hosts (used by the test harness)
        return self.getLinksForItem(cItem)

    def addVideo(self, params):
        # live channels / webcams / radio rows are favourites unless the source says otherwise
        params.setdefault('good_for_fav', True)
        CBaseHostClass.addVideo(self, params)

    def addAudio(self, params):
        params.setdefault('good_for_fav', True)
        CBaseHostClass.addAudio(self, params)

    def getLinksForFavourite(self, favData):
        try:
            cItem = json_loads(favData)
        except Exception:
            printExc()
            return []
        return self.getLinksForItem(cItem)

    def setInitListFromFavouriteItem(self, favData):
        try:
            self.currList.append(self._dropMainMenuImageType(json_loads(favData)))
        except Exception:
            printExc()
            return False
        return True

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", '')
        url = self.currItem.get("url", '')
        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s]" % (name))
        self.currList = []
        if name is not None:
            self.currItem = self._dropMainMenuImageType(self.currItem)
        if isJumpItem(self.currItem):
            # "Jump" row of a paged list (lookcam.com): asks for the page, the list keeps its own name
            self.currItem = jumpTarget(self, self.currItem)
            name = self.currItem.get('name', '')

        if name is None:
            self.listsMainMenu(self.MAIN_GROUPED_TAB, {'image_type': self.MAIN_MENU_IMAGE_TYPE})
        elif name == "djing.com":
            self.getDjingComList(self.currItem)
        elif name == 'meteo.pl':
            self.getMeteoPLList(self.currItem)
        elif name == 'skylinewebcams.com':
            self.getWkylinewebcamsComList(self.currItem)
        elif name == 'weeb.tv':
            self.getWeebTvList(url)
        elif name == "webcamera.pl":
            self.getWebCamera(self.currItem)
        elif name == "filmon_groups":
            self.getFilmOnGroups()
        elif name == "filmon_channels":
            self.getFilmOnChannels()
        elif name == 'nhl24all.ir':
            self.getNhl24AllList(url)
        elif name == 'livemass.net':
            self.getLiveMassList(url)
        elif name == 'windy_root':
            self.getWindyRoot()
        elif name == 'windy_taxonomy':
            self.getWindyTaxonomy(self.currItem)
        elif name == 'windy_list':
            self.getWindyList(self.currItem)
        elif name == 'worldcam_root':
            self.getWorldcamRoot()
        elif name == 'worldcam_list':
            self.getWorldcamList(self.currItem)
        elif name == 'lookcam_root':
            self.getLookcamRoot()
        elif name == 'lookcam_list':
            self.getLookcamList(self.currItem)
        elif name == 'nadmorski24_root':
            self.getNadmorski24Root()
        elif name == 'nadmorski24_list':
            self.getNadmorski24List(self.currItem)
        elif name == 'bieszczady_list':
            self.getBieszczadyList(self.currItem)
        elif name == 'lantech_list':
            self.getLantechList(self.currItem)
        elif name == 'sdzoo_list':
            self.getSdZooList(self.currItem)
        elif name == 'media40_list':
            self.getMedia40List(self.currItem)
        elif name == 'korbielow_list':
            self.getKorbielowList(self.currItem)
        elif name == 'szczyrk_list':
            self.getSzczyrkList(self.currItem)
        elif name == 'iptvorg_root':
            self.getIptvOrgRoot()
        elif name == 'iptvorg_taxonomy':
            self.getIptvOrgTaxonomy(self.currItem)
        elif name == 'iptvorg_list':
            self.getIptvOrgList(self.currItem)
        elif name == 'freecasthub_root':
            self.getFreecasthubRoot()
        elif name == 'freecasthub_list':
            self.getFreecasthubList(self.currItem)
        elif name == 'radiohq_list':
            self.getRadioHqList(url)

        if name is not None:
            self.currList = [self._dropMainMenuImageType(item) for item in self.currList]
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, WebStreamHost(), withSearchHistrory=False)

    def getLinksForVideo(self, Index=0, selItem=None):
        listLen = len(self.host.currList)
        if listLen <= Index or Index < 0:
            printDBG("ERROR getLinksForVideo - current list is to short len: %d, Index: %d" % (listLen, Index))
            return RetHost(RetHost.ERROR, value=[])

        if self.host.currList[Index]["type"] not in ['video', 'audio', 'picture']:
            printDBG("ERROR getLinksForVideo - current item has wrong type")
            return RetHost(RetHost.ERROR, value=[])

        retlist = []
        for item in self.host.getLinksForItem(self.host.currList[Index]):
            retlist.append(CUrlItem(item['name'], item['url'], item.get('need_resolve', 0)))
        return RetHost(RetHost.OK, value=retlist)
    # end getLinksForVideo

    def getResolvedURL(self, url):
        printDBG("getResolvedURL url[%s]" % url)
        return RetHost(RetHost.OK, value=[])
