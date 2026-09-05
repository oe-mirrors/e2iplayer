# -*- coding: utf-8 -*-
# Last Modified: 05.09.2026
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, RetHost, CUrlItem
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetHostsOrderList
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, getF4MLinksWithMeta
from Plugins.Extensions.IPTVPlayer.libs.teledunet import TeledunetParser
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
from Plugins.Extensions.IPTVPlayer.libs.filmonapi import FilmOnComApi, GetConfigList as FilmOn_GetConfigList
from Plugins.Extensions.IPTVPlayer.libs.webcamera import WebCameraApi
from Plugins.Extensions.IPTVPlayer.libs.weebtv import WeebTvApi, GetConfigList as WeebTv_GetConfigList
from Plugins.Extensions.IPTVPlayer.libs.ustvnow import UstvnowApi, GetConfigList as Ustvnow_GetConfigList
from Plugins.Extensions.IPTVPlayer.libs.meteopl import MeteoPLApi, GetConfigList as MeteoPL_GetConfigList
from Plugins.Extensions.IPTVPlayer.libs.skylinewebcamscom import WkylinewebcamsComApi, GetConfigList as WkylinewebcamsCom_GetConfigList
from Plugins.Extensions.IPTVPlayer.libs.sport365live import Sport365LiveApi
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
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
from Components.config import config, ConfigSelection, ConfigText, getConfigListEntry
############################################


###################################################
# Config options for HOST
###################################################
# free key from https://api.windy.com/webcams - required, the listing API is authenticated
config.plugins.iptvplayer.windy_api_key = ConfigText(default="", fixed_size=False)
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

    optionList.append(getConfigListEntry("----------------ustvnow.com-----------------", config.plugins.iptvplayer.fake_separator))
    try:
        optionList.extend(Ustvnow_GetConfigList())
    except Exception:
        printExc()

    optionList.append(getConfigListEntry("-------------SkyLineWebCams.com-------------", config.plugins.iptvplayer.fake_separator))
    try:
        optionList.extend(WkylinewebcamsCom_GetConfigList())
    except Exception:
        printExc()

    optionList.append(getConfigListEntry("-----------------Windy Webcams------------------", config.plugins.iptvplayer.fake_separator))
    optionList.append(getConfigListEntry(_("%s API KEY") % 'https://api.windy.com/webcams', config.plugins.iptvplayer.windy_api_key))

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
                        {'alias_id': 'webcamera.pl', 'name': 'webcamera.pl', 'title': 'https://webcamera.pl/', 'url': 'https://www.webcamera.pl/', 'icon': 'https://static.webcamera.pl/webcamera/img/loader-min.png'},
                        {'alias_id': 'skylinewebcams.com', 'name': 'skylinewebcams.com', 'title': 'https://skylinewebcams.com/', 'url': 'https://www.skylinewebcams.com/', 'icon': 'https://cdn.skylinewebcams.com/skylinewebcams.png'},
                        {'alias_id': 'filmon.com', 'name': 'filmon_groups', 'title': 'https://filmon.com/', 'url': 'https://www.filmon.com/', 'icon': 'https://static.filmon.com/theme/img/filmon_tv_logo_white.png'},
                        {'alias_id': 'ustvnow.com', 'name': 'ustvnow', 'title': 'https://ustvnow.com/', 'url': 'https://www.ustvnow.com/', 'icon': 'https://2.bp.blogspot.com/-SVJ4uZ2-zPc/UBAZGxREYRI/AAAAAAAAAKo/lpbo8OFLISU/s1600/ustvnow.png'},
                        {'alias_id': 'sport365.live', 'name': 'sport365.live', 'title': 'https://sport365.live/', 'url': 'https://www.sport365.live/', 'icon': 'https://www.sport365.live/assets/48x48px.png'},
                        {'alias_id': 'djing.com', 'name': 'djing.com', 'title': 'https://djing.com/', 'url': 'https://djing.com/', 'icon': 'https://www.djing.com/newimages/content/c01.jpg'},
                        {'alias_id': 'nhl24all.ir', 'name': 'nhl24all.ir', 'title': 'https://nhl24all.ir/', 'url': 'https://api.nhl24all.ir/api/v3/stateshot', 'icon': 'https://nhl24all.ir/favicon.ico'},
                        {'alias_id': 'livemass.net', 'name': 'livemass.net', 'title': 'https://livemass.net/', 'url': 'https://livemass.net/locations/index.html', 'icon': 'https://livemass.net/images/logo.png'},
                        {'alias_id': 'windy.com', 'name': 'windy_root', 'title': 'https://www.windy.com/webcams/', 'url': '', 'icon': 'https://www.windy.com/favicon.ico'},
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
        self.ustvnowApi = None
        self.meteoPLApi = None
        self.sport365LiveApi = None
        self.wkylinewebcamsComApi = None
        self.weebTvApi = None
        self.djingComApi = None

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
        return self.webCameraApi.getVideoLink(cItem)

    #############################################################
    def getUstvnowList(self, cItem):
        printDBG("getUstvnowList start")
        if None is self.ustvnowApi:
            self.ustvnowApi = UstvnowApi()
        tmpList = self.ustvnowApi.getChannelsList(cItem)
        for item in tmpList:
            self.addVideo(item)

    def getUstvnowLink(self, cItem):
        printDBG("getUstvnowLink start")
        urlsTab = self.ustvnowApi.getVideoLink(cItem)
        return urlsTab
    #############################################################

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
        urlsTab = self.wkylinewebcamsComApi.getVideoLink(cItem)
        return urlsTab

    def getSport365LiveList(self, cItem):
        printDBG("getSport365LiveList start")
        if None is self.sport365LiveApi:
            self.sport365LiveApi = Sport365LiveApi()
        tmpList = self.sport365LiveApi.getChannelsList(cItem)
        for item in tmpList:
            self.currList.append(item)

    def getSport365LiveLink(self, cItem):
        printDBG("getSport365LiveLink start")
        urlsTab = self.sport365LiveApi.getVideoLink(cItem)
        return urlsTab

    # nhl24all.ir (ex nhl66.ir) - api.nhl24all.ir/api/v3/stateshot lists media_events;
    # api.nhl24all.ir/api/v2/generate_stream_info -> the HLS master url
    NHL24ALL_API = 'https://api.nhl24all.ir'

    def getNhl24AllList(self, url):
        printDBG("getNhl24AllList start")
        sts, data = self.cm.getPage(url or (self.NHL24ALL_API + '/api/v3/stateshot'), {'header': {'Referer': 'https://nhl24all.ir/', 'Origin': 'https://nhl24all.ir'}})
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
            live = game.get('status', '') not in ('F', 'FINAL', '')
            for fl in flavorsByEvent.get(me.get('id'), []):
                # "premium.*" flavors need a paid-account token generate_stream_info
                # doesn't have for an anonymous caller (verified: always 401s) -
                # skip them instead of listing entries that can never play
                if str(fl.get('id', '')).startswith('premium.'):
                    continue
                title = base + (' [%s]' % fl.get('name', fl.get('id', '')))
                if live:
                    title = '[LIVE] ' + title
                params = {'name': 'nhl24all.ir', 'title': title, 'desc': desc,
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

        if 'teledunet' in url:
            newUrl = TeledunetParser().get_rtmp_params(url)
            return [{'name': 'Własny link', 'url': newUrl}] if newUrl else []

        urlList = None
        if name == 'sport365.live':
            urlList = self.getSport365LiveLink(cItem)
        elif 'weeb.tv' in name:
            url = self.getWeebTvLink(url)
        elif name == 'filmon_channel':
            urlList = self.getFilmOnLink(channelID=url)
        elif name == 'djing.com':
            urlList = self.getDjingComLink(cItem)
        elif name == 'ustvnow':
            urlList = self.getUstvnowLink(cItem)
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

    def getLinksForFavourite(self, favData):
        try:
            cItem = json_loads(favData)
        except Exception:
            printExc()
            return []
        return self.getLinksForItem(cItem)

    def setInitListFromFavouriteItem(self, favData):
        try:
            self.currList.append(json_loads(favData))
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

        if name is None:
            self.listsMainMenu(self.MAIN_GROUPED_TAB, {'image_type': "WWW"})
        elif name == "sport365.live":
            self.getSport365LiveList(self.currItem)
        elif name == "djing.com":
            self.getDjingComList(self.currItem)
        elif name == 'ustvnow':
            self.getUstvnowList(self.currItem)
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
