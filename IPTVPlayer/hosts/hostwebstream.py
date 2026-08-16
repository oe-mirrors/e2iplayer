# -*- coding: utf-8 -*-
# Last Modified: 15.08.2025
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, RetHost, CUrlItem
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetLogoDir, GetCookieDir, GetHostsOrderList
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.pCommon import CParsingHelper
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, getF4MLinksWithMeta, getMPDLinksWithMeta
from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.utils import clean_html
from Plugins.Extensions.IPTVPlayer.libs.teledunet import TeledunetParser
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
from Plugins.Extensions.IPTVPlayer.libs.filmonapi import FilmOnComApi, GetConfigList as FilmOn_GetConfigList
from Plugins.Extensions.IPTVPlayer.libs.videostar import VideoStarApi, GetConfigList as VideoStar_GetConfigList
from Plugins.Extensions.IPTVPlayer.libs.webcamera import WebCameraApi
from Plugins.Extensions.IPTVPlayer.libs.bilasportpw import BilaSportPwApi, GetConfigList as BilaSportPw_GetConfigList
from Plugins.Extensions.IPTVPlayer.libs.canlitvliveio import CanlitvliveIoApi
from Plugins.Extensions.IPTVPlayer.libs.weebtv import WeebTvApi, GetConfigList as WeebTv_GetConfigList
from Plugins.Extensions.IPTVPlayer.libs.ustvnow import UstvnowApi, GetConfigList as Ustvnow_GetConfigList
from Plugins.Extensions.IPTVPlayer.libs.meteopl import MeteoPLApi, GetConfigList as MeteoPL_GetConfigList
from Plugins.Extensions.IPTVPlayer.libs.skylinewebcamscom import WkylinewebcamsComApi, GetConfigList as WkylinewebcamsCom_GetConfigList
from Plugins.Extensions.IPTVPlayer.libs.livespottingtv import LivespottingTvApi
from Plugins.Extensions.IPTVPlayer.libs.sport365live import Sport365LiveApi
from Plugins.Extensions.IPTVPlayer.libs.karwantv import KarwanTvApi
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.djingcom import DjingComApi
from Plugins.Extensions.IPTVPlayer.libs.mlbstreamtv import MLBStreamTVApi, GetConfigList as MLBStreamTV_GetConfigList
from Plugins.Extensions.IPTVPlayer.libs.wiziwig1 import Wiziwig1Api
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.pVer import isPY2
if not isPY2():
    basestring = str
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus, urllib_unquote
from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import urlsplit, urlunsplit
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
###################################################
# FOREIGN import
###################################################
import re
from Components.config import config, ConfigSelection, ConfigYesNo, getConfigListEntry
############################################

###################################################
# E2 GUI COMMPONENTS
###################################################
from Plugins.Extensions.IPTVPlayer.components.asynccall import MainSessionWrapper
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.SortowanieWebstream = ConfigYesNo(default=False)
config.plugins.iptvplayer.weatherbymatzgprohibitbuffering = ConfigYesNo(default=True)
config.plugins.iptvplayer.weather_useproxy = ConfigYesNo(default=False)
config.plugins.iptvplayer.fake_separator = ConfigSelection(default=" ", choices=[(" ", " ")])


def GetConfigList():
    optionList = []

    optionList.append(getConfigListEntry("----------------pilot.wp.pl-----------------", config.plugins.iptvplayer.fake_separator))
    try:
        optionList.extend(VideoStar_GetConfigList())
    except Exception:
        printExc()

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

    optionList.append(getConfigListEntry(_("----------Other----------"), config.plugins.iptvplayer.fake_separator))
    optionList.append(getConfigListEntry(_("Turn off buffering for http://prognoza.pogody.tv/"), config.plugins.iptvplayer.weatherbymatzgprohibitbuffering))
    optionList.append(getConfigListEntry(_("Use Polish proxy for http://prognoza.pogody.tv/"), config.plugins.iptvplayer.weather_useproxy))

    optionList.append(getConfigListEntry("----------------bilasport.pw-------------------", config.plugins.iptvplayer.fake_separator))
    try:
        optionList.extend(BilaSportPw_GetConfigList())
    except Exception:
        printExc()

    optionList.append(getConfigListEntry("-----------------mlbstream.tv------------------", config.plugins.iptvplayer.fake_separator))
    try:
        optionList.extend(MLBStreamTV_GetConfigList())
    except Exception:
        printExc()

    return optionList

###################################################


def gettytul():
    return _('"Web" streams player')


class HasBahCa(CBaseHostClass):
    HTTP_HEADER = {'User-Agent': 'Mozilla/5.0 (Windows; U; Windows NT 5.1; en-GB; rv:1.9.0.3 Gecko/2008092417 Firefox/3.0.3'}
    MAIN_GROUPED_TAB = [{'alias_id': 'weeb.tv', 'name': 'weeb.tv', 'title': 'https://weeb.tv/', 'url': '', 'icon': 'https://static.weeb.tv/images/weebtv1.png'},
                        {'alias_id': 'videostar.pl', 'name': 'videostar.pl', 'title': 'https://pilot.wp.pl/', 'url': '', 'icon': 'https://satkurier.pl/uploads/53612.jpg'},
                        {'alias_id': 'prognoza.pogody.tv', 'name': 'prognoza.pogody.tv', 'title': 'http://pogody.tv/', 'url': 'http://prognoza.pogody.tv', 'icon': 'http://pogody.pl/images/pogodytv.png'},
                        {'alias_id': 'meteo.pl', 'name': 'meteo.pl', 'title': 'https://meteo.pl/', 'url': 'https://meteo.pl/', 'icon': 'https://www.meteo.pl/img/napis_glowny_pl_2.png'},
                        {'alias_id': 'webcamera.pl', 'name': 'webcamera.pl', 'title': 'https://webcamera.pl/', 'url': 'https://www.webcamera.pl/', 'icon': 'https://static.webcamera.pl/webcamera/img/loader-min.png'},
                        {'alias_id': 'skylinewebcams.com', 'name': 'skylinewebcams.com', 'title': 'https://skylinewebcams.com/', 'url': 'https://www.skylinewebcams.com/', 'icon': 'https://cdn.skylinewebcams.com/skylinewebcams.png'},
                        {'alias_id': 'livespotting.tv', 'name': 'livespotting.tv', 'title': 'https://livespotting.tv/', 'url': 'https://livespotting.tv/', 'icon': 'https://livespotting.com/static/images/apple-touch-icon.png'},
                        {'alias_id': 'filmon.com', 'name': 'filmon_groups', 'title': 'https://filmon.com/', 'url': 'https://www.filmon.com/', 'icon': 'https://static.filmon.com/theme/img/filmon_tv_logo_white.png'},
                        {'alias_id': 'ustvnow.com', 'name': 'ustvnow', 'title': 'https://ustvnow.com/', 'url': 'https://www.ustvnow.com/', 'icon': 'https://2.bp.blogspot.com/-SVJ4uZ2-zPc/UBAZGxREYRI/AAAAAAAAAKo/lpbo8OFLISU/s1600/ustvnow.png'},
                        {'alias_id': 'sport365.live', 'name': 'sport365.live', 'title': 'https://sport365.live/', 'url': 'https://www.sport365.live/', 'icon': 'https://www.sport365.live/assets/48x48px.png'},
                        {'alias_id': 'bilasport.com', 'name': 'bilasport.com', 'title': 'http://bilasport.com/', 'url': '', 'icon': 'https://projects.fivethirtyeight.com/2016-mlb-predictions/images/logos.png'},
                        {'alias_id': 'mlbstream.tv', 'name': 'mlbstream.tv', 'title': 'http://mlbstream.tv/ && http://nhlstream.tv/', 'url': '', 'icon': 'http://mlbstream.tv/wp-content/uploads/2018/03/mlb-network-291x300.png'},
                        {'alias_id': 'karwan.tv', 'name': 'karwan.tv', 'title': 'https://karwan.tv/', 'url': 'https://karwan.tv/', 'icon': 'https://karwan.tv//logo/karwan-tv/karwan-tv-1.png'},
                        {'alias_id': 'canlitvlive.io', 'name': 'canlitvlive.io', 'title': 'http://canlitvlive.io/', 'url': 'http://www.canlitvlive.io/', 'icon': 'http://www.canlitvlive.io/images/footer_simge.png'},
                        {'alias_id': 'wiziwig1.eu', 'name': 'wiziwig1.eu', 'title': 'https://wiziwig1.eu/', 'url': 'https://wiziwig1.eu/', 'icon': 'https://i.imgur.com/yBX7fZA.jpg'},
                        {'alias_id': 'djing.com', 'name': 'djing.com', 'title': 'https://djing.com/', 'url': 'https://djing.com/', 'icon': 'https://www.djing.com/newimages/content/c01.jpg'},
                        {'alias_id': 'nhl66.ir', 'name': 'nhl66.ir', 'title': 'https://nhl66.ir', 'url': 'https://api.nhl66.ir/api/sport/schedule', 'icon': 'https://nhl66.ir/cassets/logo.png'},
                        {'alias_id': 'strumyk.net', 'name': 'strumyk.net', 'title': 'https://strumyk.net/', 'url': 'https://strumyk.net/', 'icon': 'https://strumyk.net/assets/logo.png'},
                       ]

    def __init__(self):
        CBaseHostClass.__init__(self)

        # temporary data
        self.currList = []
        self.currItem = {}

        # Login data
        self.sort = config.plugins.iptvplayer.SortowanieWebstream.value
        self.sessionEx = MainSessionWrapper()

        self.filmOnApi = None
        self.videoStarApi = None
        self.webCameraApi = None
        self.ustvnowApi = None
        self.meteoPLApi = None
        self.sport365LiveApi = None
        self.wkylinewebcamsComApi = None
        self.livespottingTvApi = None
        self.karwanTvApi = None
        self.bilaSportPwApi = None
        self.canlitvliveIoApi = None
        self.weebTvApi = None
        self.djingComApi = None
        self.MLBStreamTVApi = None
        self.Wiziwig1Api = None

        self.hasbahcaiptv = {}
        self.webcameraSubCats = {}
        self.webCameraParams = {}

    def getPage(self, url, params={}, post_data=None):
        HTTP_HEADER = {'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux i686; rv:21.0) Gecko/20100101 Firefox/21.0'}
        params.update({'header': HTTP_HEADER})

        if False and 'hasbahcaiptv.com' in url:
            printDBG(url)
            proxy = 'http://www.proxy-german.de/index.php?q={0}&hl=2e5'.format(urllib_quote_plus(url))
            params['header']['Referer'] = proxy
            url = proxy
        return self.cm.getPage(url, params, post_data)

    def _getJItemStr(self, item, key, default=''):
        v = item.get(key, None)
        if None is v:
            return default
        return ensure_str(clean_html(u'%s' % v))

    def addItem(self, params):
        self.currList.append(params)
        return

    def listsMainMenu(self, tab, forceParams={}):
        # sort tab if needed
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

    def listHasBahCa(self, item):
        url = item.get('url', '')
        if 'proxy-german.de' in url:
            url = urllib_unquote(url.split('?q=')[-1])

        printDBG("listHasBahCa url[%s]" % url)
        BASE_URL = 'https://hasbahcaiptv.com/'

        if '?' in url and '/' == url[-1]:
            url = url[:-1]

        def _url_path_join(*parts):
            """Normalize url parts and join them with a slash."""
            schemes, netlocs, paths, queries, fragments = list(zip(*(urlsplit(part) for part in parts)))
            scheme, netloc, query, fragment = _first_of_each(schemes, netlocs, queries, fragments)
            path = '/'.join(x.strip('/') for x in paths if x)
            return urlunsplit((scheme, netloc, path, query, fragment))

        def _first_of_each(*sequences):
            return (next((x for x in sequence if x), '') for sequence in sequences)

        login = self.hasbahcaiptv.get('login', '')
        password = self.hasbahcaiptv.get('password', '')

        if login == '' and password == '':
            sts, data = self.getPage('https://hasbahcaiptv.com/page.php?seite=Passwort.html')
            if sts:
                login = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, 'Downloads Login', '</h3>', False)[1])
                password = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, 'Downloads Pass', '</h3>', False)[1])
                self.hasbahcaiptv['login'] = login.replace('&nbsp;', '').replace('\xc2\xa0', '').strip()
                self.hasbahcaiptv['password'] = password.replace('&nbsp;', '').replace('\xc2\xa0', '').strip()

        sts, data = self.getPage(url, {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': GetCookieDir('hasbahcaiptv')}, {'username': self.hasbahcaiptv.get('login', 'downloader'), 'password': self.hasbahcaiptv.get('password', 'hasbahcaiptv.com')})
        if not sts:
            return

        data = CParsingHelper.getDataBeetwenMarkers(data, '<table class="autoindex_table">', '</table>', False)[1]
        data = data.split('</tr>')
        for item in data:
            printDBG(item)
            if 'text.png' in item:
                name = 'm3u'
            elif 'dir.png' in item:
                name = 'HasBahCa'
            else:
                continue
            desc = self.cleanHtmlStr(item)
            new_url = self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0]
            title = new_url
            printDBG("listHasBahCa new_url[%s]" % new_url)
            if title[-1] != '/':
                title = title.split('/')[-1]
            title = self.cleanHtmlStr(item)  # title.split('dir=')[-1]

            if new_url.startswith('.'):
                if 'm3u' == name:
                    new_url = BASE_URL + new_url[2:]
                else:
                    new_url = _url_path_join(url[:url.rfind('/') + 1], new_url[1:])
            if not new_url.startswith('http'):
                new_url = BASE_URL + new_url
            new_url = new_url.replace("&amp;", "&")

            new_url = strwithmeta(new_url, {'cookiefile': 'hasbahcaiptv'})
            params = {'name': name, 'title': title.strip(), 'url': new_url, 'desc': desc}
            self.addDir(params)

    def getDirectVideoHasBahCa(self, name, url):
        printDBG("getDirectVideoHasBahCa name[%s], url[%s]" % (name, url))
        videoTabs = []
        url = strwithmeta(url)
        if 'cookiefile' in url.meta:
            sts, data = self.cm.getPage(url, {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': GetCookieDir(url.meta['cookiefile'])})
        else:
            sts, data = self.cm.getPage(url)
        if sts:
            data = data.strip()
            if data.startswith('http'):
                videoTabs.append({'name': name, 'url': data})
        return videoTabs

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

    def m3uList(self, listURL):
        printDBG('m3uList entry')
        params = {'header': self.HTTP_HEADER}

        listURL = strwithmeta(listURL)
        meta = listURL.meta
        if 'proxy-german.de' in listURL:
            listURL = urllib_unquote(listURL.split('?q=')[-1])

        listURL = strwithmeta(listURL, meta)
        if 'cookiefile' in listURL.meta:
            params.update({'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': GetCookieDir(listURL.meta['cookiefile'])})

        sts, data = self.getPage(listURL, params)
        if not sts:
            printDBG("getHTMLlist ERROR geting [%s]" % listURL)
            return
        data = data.replace("\r", "\n").replace('\n\n', '\n').split('\n')
        printDBG("[\n%s\n]" % data)
        title = ''
        nr = ''
        catTitle = ''
        icon = ''
        for item in data:
            if item.startswith('#EXTINF:'):
                try:
                    nr = self.cm.ph.getDataBeetwenMarkers(item, 'tvg-id="', '"', False)[1]
                    catTitle = self.cm.ph.getDataBeetwenMarkers(item, 'group-title="', '"', False)[1]
                    icon = self.cm.ph.getDataBeetwenMarkers(item, 'tvg-logo="', '"', False)[1]
                    title = item.split(',')[1]
                except Exception:
                    title = item
            else:
                if 0 < len(title):
                    if 'Lista_matzgPL' in listURL and title.startswith('TVP '):
                        continue
                    item = item.replace('rtmp://$OPT:rtmp-raw=', '')
                    cTitle = re.sub(r'\[[^\]]*?\]', '', title)
                    if len(cTitle):
                        title = cTitle
                    itemUrl = self.up.decorateParamsFromUrl(item)
                    if 'https://wownet.ro/' in itemUrl:
                        icon = 'https://wownet.ro/logo/' + icon
                    else:
                        icon = ''
                    if '' != catTitle:
                        desc = catTitle + ', '
                    else:
                        desc = ''
                    desc += _("Protocol:") + " " + itemUrl.meta.get('iptv_proto', '')

                    if 'headers=' in itemUrl:
                        headers = self.cm.ph.getSearchGroups(itemUrl, r'headers\=(\{[^\}]+?\})')[0]
                        try:
                            headers = json_loads(headers)
                            itemUrl = itemUrl.split('headers=')[0].strip()
                            itemUrl = urlparser.decorateUrl(itemUrl, headers)
                        except Exception:
                            printExc()
                    params = {'title': title, 'url': itemUrl, 'icon': icon, 'desc': desc}
                    if listURL.endswith('radio.m3u'):
                        if icon == '':
                            params['icon'] = 'http://www.darmowe-na-telefon.pl/uploads/tapeta_240x320_muzyka_23.jpg'
                        self.addAudio(params)
                    else:
                        self.addVideo(params)
                    title = ''

    def getOthersList(self, cItem):
        sts, data = self.cm.getPage("https://www.elevensports.pl/")
        if not sts:
            return
        channels = {0: "ELEVEN", 1: "ELEVEN SPORTS"}
        data = re.compile('''stream=(http[^"']+?)["']''').findall(data)
        for idx in range(len(data)):
            params = dict(cItem)
            params.update({'title': channels.get(idx, 'Unknown'), 'provider': 'elevensports', 'url': data[idx].replace('~', '=')})
            self.addVideo(params)

    def getOthersLinks(self, cItem):
        printDBG("getOthersLinks cItem[%s]" % cItem)
        hlsTab = []
        url = cItem.get('url', '')
        if url != '':
            if cItem['urlkey'] == '' and cItem['replacekey'] == '':
                hlsTab = getDirectM3U8Playlist(url, False)
            else:
                hlsTab = getDirectM3U8Playlist(url, checkContent=True, sortWithMaxBitrate=9000000)
                for idx in range(len(hlsTab)):
                    hlsTab[idx]['url'] = strwithmeta(hlsTab[idx]['url'], {'iptv_m3u8_key_uri_replace_old': cItem['replacekey'], 'iptv_m3u8_key_uri_replace_new': cItem['urlkey']})

        return hlsTab

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
                item.update({'name': 'weeb.tv'})
                self.addVideo(item)

    def getWeebTvLink(self, url):
        printDBG("getWeebTvLink url[%s]" % url)
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
    def getVideostarList(self, cItem):
        printDBG("getVideostarList start")
        if None is self.videoStarApi:
            self.videoStarApi = VideoStarApi()
        tmpList = self.videoStarApi.getList(cItem)
        for item in tmpList:
            if 'video' == item['type']:
                self.addVideo(item)
            elif 'audio' == item['type']:
                self.addAudio(item)
            else:
                self.addDir(item)

    def getVideostarLink(self, cItem):
        printDBG("getVideostarLink start")
        urlsTab = self.videoStarApi.getVideoLink(cItem)
        return urlsTab
    #############################################################

    #############################################################
    def getMLBStreamTVList(self, cItem):
        printDBG("getMLBStreamTVList start")
        if None is self.MLBStreamTVApi:
            self.MLBStreamTVApi = MLBStreamTVApi()
        tmpList = self.MLBStreamTVApi.getList(cItem)
        for item in tmpList:
            if 'video' == item['type']:
                self.addVideo(item)
            elif 'audio' == item['type']:
                self.addAudio(item)
            else:
                self.addDir(item)

    def getMLBStreamTVLink(self, cItem):
        printDBG("getMLBStreamTVLink start")
        urlsTab = self.MLBStreamTVApi.getVideoLink(cItem)
        return urlsTab

    def getMLBStreamResolvedLink(self, url):
        printDBG("getMLBStreamResolvedLink start")
        return self.MLBStreamTVApi.getResolvedVideoLink(url)
    #############################################################

    #############################################################
    def getWiziwig1List(self, cItem):
        printDBG("getWiziwig1List start")
        if None is self.Wiziwig1Api:
            self.Wiziwig1Api = Wiziwig1Api()
        tmpList = self.Wiziwig1Api.getList(cItem)
        for item in tmpList:
            if 'video' == item['type']:
                self.addVideo(item)
            elif 'audio' == item['type']:
                self.addAudio(item)
            else:
                self.addDir(item)

    def getWiziwig1Link(self, cItem):
        printDBG("getWiziwig1Link start")
        urlsTab = self.Wiziwig1Api.getVideoLink(cItem)
        return urlsTab
    #############################################################

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

    def getKarwanTvList(self, cItem):
        printDBG("getKarwanTvList start")
        if None is self.karwanTvApi:
            self.karwanTvApi = KarwanTvApi()
        tmpList = self.karwanTvApi.getList(cItem)
        for item in tmpList:
            if 'video' == item['type']:
                self.addVideo(item)
            elif 'audio' == item['type']:
                self.addAudio(item)
            else:
                self.addDir(item)

    def getKarwanTvLink(self, cItem):
        printDBG("getKarwanTvLink start")
        urlsTab = self.karwanTvApi.getVideoLink(cItem)
        return urlsTab

    ########################################################
    def getBilaSportPwList(self, cItem):
        printDBG("getBilaSportPwList start")
        if None is self.bilaSportPwApi:
            self.bilaSportPwApi = BilaSportPwApi()
        tmpList = self.bilaSportPwApi.getList(cItem)
        for item in tmpList:
            if 'video' == item['type']:
                self.addVideo(item)
            elif 'audio' == item['type']:
                self.addAudio(item)
            elif 'marker' == item['type']:
                self.addMarker(item)
            else:
                self.addDir(item)

    def getBilaSportPwLink(self, cItem):
        printDBG("getBilaSportPwLink start")
        urlsTab = self.bilaSportPwApi.getVideoLink(cItem)
        return urlsTab

    def getBilaSportPwResolvedLink(self, url):
        printDBG("getBilaSportPwResolvedLink start")
        return self.bilaSportPwApi.getResolvedVideoLink(url)

    ########################################################
    def getCanlitvliveIoList(self, cItem):
        printDBG("getCanlitvliveIoList start")
        if None is self.canlitvliveIoApi:
            self.canlitvliveIoApi = CanlitvliveIoApi()
        tmpList = self.canlitvliveIoApi.getList(cItem)
        for item in tmpList:
            if 'video' == item['type']:
                self.addVideo(item)
            elif 'audio' == item['type']:
                self.addAudio(item)
            else:
                self.addDir(item)

    def getCanlitvliveIoLink(self, cItem):
        printDBG("getCanlitvliveIoLink start")
        urlsTab = self.canlitvliveIoApi.getVideoLink(cItem)
        return urlsTab

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

    def getLivespottingTvList(self, cItem):
        printDBG("getLivespottingTvList start")
        if None is self.livespottingTvApi:
            self.livespottingTvApi = LivespottingTvApi()
        tmpList = self.livespottingTvApi.getChannelsList(cItem)
        for item in tmpList:
            self.addVideo(item)

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

    def prognozaPogodyList(self, url):
        printDBG("prognozaPogodyList start")
        if config.plugins.iptvplayer.weather_useproxy.value:
            params = {'http_proxy': config.plugins.iptvplayer.proxyurl.value}
        else:
            params = {}
        sts, data = self.cm.getPage(url, params)
        if not sts:
            return
        data = CParsingHelper.getDataBeetwenMarkers(data, '<div id="items">', '</div>', False)[1]
        data = data.split('</a>')
        if len(data):
            del data[-1]
        for item in data:
            params = {'name': "prognoza.pogody.tv"}
            params['url'] = self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0]
            params['icon'] = self.cm.ph.getSearchGroups(item, 'src="([^"]+?)"')[0]
            params['title'] = self.cleanHtmlStr(item)
            if len(params['icon']) and not params['icon'].startswith('http'):
                params['icon'] = 'http://prognoza.pogody.tv/' + params['icon']
            if len(params['url']) and not params['url'].startswith('http'):
                params['url'] = 'http://prognoza.pogody.tv/' + params['url']
            self.addVideo(params)

    def prognozaPogodyLink(self, url):
        printDBG("prognozaPogodyLink url[%r]" % url)
        if config.plugins.iptvplayer.weather_useproxy.value:
            params = {'http_proxy': config.plugins.iptvplayer.proxyurl.value}
        else:
            params = {}
        sts, data = self.cm.getPage(url, params)
        if not sts:
            return []
        url = self.cm.ph.getSearchGroups(data, r'src="([^"]+?\.mp4[^"]*?)"')[0]

        urlMeta = {}
        if config.plugins.iptvplayer.weatherbymatzgprohibitbuffering.value:
            urlMeta['iptv_buffering'] = 'forbidden'
        if config.plugins.iptvplayer.weather_useproxy.value:
            urlMeta['http_proxy'] = config.plugins.iptvplayer.proxyurl.value

        url = self.up.decorateUrl(url, urlMeta)
        return [{'name': 'prognoza.pogody.tv', 'url': url}]

    def getNhl66List(self, url):
        printDBG("nhl66List start")
        sts, data = self.cm.getPage(url)
        if not sts:
            return
        try:
            data = json_loads(data)
            for item in data['games']:
                for sitem in item['streams']:
                    url = sitem['url']
                    if url == '':
                        continue
                    if sitem['is_live']:
                        title = '[LIVE]  '
                    else:
                        title = ''
                    name = sitem['name']
                    dtime = item['start_datetime'].replace('T', ' - ').replace('Z', ' GMT')
                    title = title + item['away_abr'] + ' vs. ' + item['home_abr'] + ' - ' + dtime + ' - ' + name
                    desc = dtime + '[/br]' + item['away_name'] + ' vs. ' + item['home_name'] + '[/br]' + name
                    params = {'good_for_fav': True, 'name': "others", 'url': url, 'title': title, 'desc': desc, 'replacekey': 'https://mf.svc.nhl.com/', 'urlkey': 'https://api.nhl66.ir/api/get_key_url/'}
                    self.addVideo(params)
        except Exception:
            printExc()

    # lululla modd -> https://adstrim.live/api/matches/upcoming https://adstrim.live/api/match/54
    # lululla modd -> https://github.com/vb6rocod/hddlinks_android/blob/a46e87eb723b7def115be2f58cb1cb6ffe88afbc/tv/direct_link.php#L394
    def getStrumykTvList(self, url):  # sort LIVE match
        printDBG("StrumykTvList start - Using API")
        api_url = "https://adstrim.live/api/matches/upcoming"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Referer': 'https://strumyk.net/',
        }
        sts, data = self.cm.getPage(api_url, {'header': headers})
        if not sts:
            printDBG("Failed to get data from API")
            return

        try:
            matches = json_loads(data)
            printDBG("Found %d matches from API" % len(matches))

            # Sort matches: live first
            matches.sort(key=lambda x: x.get('status') != 'live')

            for match in matches:
                title = match.get('match_name', 'No Title')
                match_id = match.get('id', '')
                streams_data = match.get('stream_urls', '[]')
                status = match.get('status', '')

                try:
                    streams = json_loads(streams_data)
                    has_streams = len(streams) > 0
                except:
                    has_streams = False
                    printDBG("Failed to parse streams data")

                if not has_streams:
                    continue

                desc_parts = []
                if match.get('start_timestamp'):
                    from datetime import datetime
                    dt = datetime.fromtimestamp(match['start_timestamp'])
                    time_str = dt.strftime('%Y-%m-%d %H:%M')
                    desc_parts.append(time_str)

                if match.get('sport'):
                    desc_parts.append(match['sport'])

                if match.get('tournament'):
                    desc_parts.append(match['tournament'])

                if status:
                    desc_parts.append("Status: " + status.upper())

                desc_parts.append("Streams: " + str(len(streams)))

                desc = ' | '.join(desc_parts)

                icon = match.get('img_url', '')
                if icon and not icon.startswith('http'):
                    icon = 'https://adstrim.live/static/' + icon

                params = {
                    'name': "strumyk_tv",
                    'title': title,
                    'url': str(match_id),
                    'desc': desc,
                    'icon': icon
                }

                if status == 'live':
                    params['title'] = '[LIVE] ' + params['title']
                    viewer_count = match.get('viewer_count')
                    if viewer_count is not None:
                        params['desc'] += " | Viewers: " + str(viewer_count)

                self.addDir(params)

        except Exception as e:
            printDBG("Error parsing API data: %s" % str(e))
            printExc()

    def getStrumykTvDir(self, url):  # sort LIVE
        printDBG("StrumykTvDir start - Getting streams for match ID: %s" % url)

        api_url = "https://adstrim.live/api/match/" + url
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Referer': 'https://strumyk.net/',
        }

        sts, data = self.cm.getPage(api_url, {'header': headers})
        if not sts:
            printDBG("Failed to get match details from API")
            return

        try:
            match_data = json_loads(data)
            streams_data = match_data.get('stream_urls', '[]')
            streams = json_loads(streams_data)

            live_streams = []
            other_streams = []

            for stream in streams:
                stream_url = stream.get('url', '')
                if not stream_url:
                    continue

                # Determine if live
                if match_data.get('status') == 'live':
                    live_streams.append(stream)
                else:
                    other_streams.append(stream)

            # Combine lists: live first
            sorted_streams = live_streams + other_streams

            for stream in sorted_streams:
                stream_url = stream.get('url', '')
                stream_name = stream.get('name', 'Stream')
                stream_lang = stream.get('lang', '')
                stream_quality = stream.get('quality', '')

                name_parts = []
                if match_data.get('status') == 'live':
                    name_parts.append('[LIVE]')
                name_parts.append(stream_name)
                if stream_lang:
                    name_parts.append("[" + stream_lang + "]")
                if stream_quality:
                    name_parts.append("(" + stream_quality + ")")
                title = ' '.join(name_parts)

                desc_parts = []
                if match_data.get('match_name'):
                    desc_parts.append(match_data.get('match_name'))
                if match_data.get('sport'):
                    desc_parts.append(match_data.get('sport'))
                if match_data.get('tournament'):
                    desc_parts.append(match_data.get('tournament'))
                if match_data.get('status'):
                    desc_parts.append("Status: " + match_data.get('status').upper())
                desc = ' | '.join(desc_parts)

                url_meta = {'Referer': 'https://strumyk.net/'}
                if 'vidembed' in stream_url or 'veplay' in stream_url:
                    url_meta['need_resolve'] = '1'
                    url_meta['vidembed_url'] = stream_url

                decorated_url = strwithmeta(stream_url, url_meta)
                params = {
                    'name': "strumyk.net",
                    'title': title,
                    'url': decorated_url,
                    'desc': desc,
                    'need_resolve': url_meta.get('need_resolve', '0')
                }
                self.addVideo(params)

        except Exception as e:
            printDBG("Error parsing stream data: %s" % str(e))
            printExc()

    def resolveVidembed(self, url):
        printDBG("Resolving vidembed URL using working method: %s" % url)

        # Estrai l'ID dello stream dall'URL
        stream_id = url.split('/stream/')[-1].split('?')[0].split('#')[0]
        printDBG("Stream ID: %s" % stream_id)

        # URL dell'API funzionante (aggiornato)
        api_url = "https://www.vidembed.re/api/source/" + stream_id

        # Dati POST necessari
        post_data = '{"r":"https://daddylive.dad/","d":"www.vidembed.re"}'

        # Headers completi per bypassare le protezioni
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Length': str(len(post_data)),
            'Origin': 'https://www.vidembed.re',
            'Referer': 'https://www.vidembed.re/stream/' + stream_id,
            'Connection': 'keep-alive',
            'Pragma': 'no-cache',
            'Cache-Control': 'no-cache',
        }

        # Prima visita la pagina principale per ottenere i cookie necessari
        main_url = "https://www.vidembed.re/"
        self.cm.getPage(main_url, {
            'header': headers,
            'use_cookie': True,
            'load_cookie': True,
            'save_cookie': True,
            'cookiefile': GetCookieDir('vidembed.cookie')
        })

        # Aspetta un momento per permettere ai cookie di essere impostati
        import time
        time.sleep(2)

        # Fai la richiesta POST all'API
        sts, data = self.cm.getPage(api_url, {
            'header': headers,
            'post_data': post_data,
            'use_cookie': True,
            'load_cookie': True,
            'save_cookie': True,
            'cookiefile': GetCookieDir('vidembed.cookie'),
            'timeout': 30
        })

        if not sts:
            printDBG("API request failed, trying alternative approach")
            return self.tryAlternativeVidembedResolution(stream_id)

        printDBG("API response: %s" % data)

        try:
            # Parsa la risposta JSON
            response = json_loads(data)

            if not response.get('success', False):
                printDBG("API returned unsuccessful response")
                return []

            # Decodifica il campo player (base64)
            import base64
            player_data_encoded = response['player']
            player_data_decoded = base64.b64decode(player_data_encoded).decode('utf-8')
            printDBG("Decoded player data: %s" % player_data_decoded)

            # Parsa i dati decodificati
            player_info = json_loads(player_data_decoded)
            source_file = player_info.get('source_file', '')

            if not source_file:
                printDBG("No source_file found in player data")
                return []

            printDBG("Found source file: %s" % source_file)

            # Prepara gli header per il video
            meta = {
                'Referer': 'https://www.vidembed.re/',
                'Origin': 'https://www.vidembed.re',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

            return [{'name': 'strumyk.net', 'url': strwithmeta(source_file, meta)}]

        except Exception as e:
            printDBG("Error processing response: %s" % str(e))
            return []

    def tryAlternativeVidembedResolution(self, stream_id):
        """Metodo alternativo per risolvere gli URL Vidembed"""
        printDBG("Trying alternative resolution for stream ID: %s" % stream_id)

        # Prova con diversi pattern di URL noti
        url_patterns = [
            "https://vidembed.io/stream/{}/index.m3u8",
            "https://vidembed.cc/stream/{}/playlist.m3u8",
            "https://vidembed.net/{}",
            "https://vidembed.pro/{}/master.m3u8",
        ]

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.vidembed.re/',
        }

        for pattern in url_patterns:
            test_url = pattern.format(stream_id)
            printDBG("Testing URL pattern: %s" % test_url)

            try:
                # Prova una richiesta HEAD per verificare se l'URL esiste
                sts, _ = self.cm.getPage(test_url, {
                    'header': headers,
                    'method': 'HEAD',
                    'timeout': 10
                })

                if sts:
                    printDBG("Alternative URL works: %s" % test_url)
                    return [{'name': 'strumyk.net', 'url': strwithmeta(test_url, {'Referer': 'https://www.vidembed.re/'})}]
            except:
                continue

        printDBG("All alternative methods failed")
        return []

    def extractUrlFromResolver(self, data):
        """Estrai l'URL video dalla risposta del resolver"""
        try:
            # Prova a parsare come JSON
            response = json_loads(data)
            return response.get('url', response.get('stream_url', ''))
        except:
            pass

        # Cerca URL direttamente nel testo
        patterns = [
            r'(https?://[^\s"\']+\.m3u8[^\s"\']*)',
            r'(https?://[^\s"\']+\.mp4[^\s"\']*)',
            r'stream_url["\']?:\s*["\']([^"\']+)["\']',
            r'url["\']?:\s*["\']([^"\']+)["\']',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, data)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                if match.startswith('http'):
                    return match
        return None

    def fallbackToDirectStream(self, url):
        """Approccio di fallback: prova a costruire URL diretti basati su pattern noti"""
        printDBG("Trying fallback direct stream approach")

        # Estrai l'ID dall'URL
        stream_id = url.split('/stream/')[-1].split('?')[0].split('#')[0]

        # Prova vari pattern di URL basati su servizi di streaming noti
        direct_url_patterns = [
            "https://vidembed.re/stream/{}/index.m3u8",
            "https://vidembed.re/{}/playlist.m3u8",
            "https://vidembed.re/hls/{}/index.m3u8",
            "https://vidembed.re/{}/master.m3u8",
        ]

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.vidembed.re/',
        }

        for pattern in direct_url_patterns:
            test_url = pattern.format(stream_id)
            printDBG("Testing direct URL: %s" % test_url)

            # Prova una richiesta HEAD per verificare se l'URL esiste
            try:
                sts, _ = self.cm.getPage(test_url, {'header': headers, 'method': 'HEAD', 'timeout': 10})
                if sts:
                    printDBG("Direct URL works: %s" % test_url)
                    return [{'name': 'strumyk.net', 'url': strwithmeta(test_url, {'Referer': 'https://www.vidembed.re/'})}]
            except:
                continue

        printDBG("All resolution attempts failed")
        return []

    def getStrumykTvLink(self, url):
        printDBG("StrumykTvLink url[%s]" % url)

        if hasattr(url, 'meta') and url.meta.get('need_resolve') == '1':
            return self.resolveVidembed(url.meta.get('vidembed_url', str(url)))

        return [{'name': 'strumyk.net', 'url': url}]

    def getStrumykTvListOld(self, url):
        printDBG("StrumykTvList start - nuova versione")
        printDBG("URL: %s" % url)

        # Try to find the API endpoint that the website uses
        # Common patterns for sports streaming sites
        api_endpoints = [
            "/api/matches",
            "/api/games",
            "/api/events",
            "/api/live",
            "/matches.json",
            "/games.json",
            "/events.json",
            "/data/matches",
            "/data/games",
        ]

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        }

        # Try each API endpoint
        for endpoint in api_endpoints:
            api_url = self.cm.getFullUrl(endpoint, url)
            printDBG("Trying API endpoint: %s" % api_url)

            sts, api_data = self.cm.getPage(api_url, {'header': headers})
            if sts and len(api_data) > 100:
                printDBG("API data length: %d" % len(api_data))

                # Try to parse as JSON
                try:
                    json_data = json_loads(api_data)
                    printDBG("Successfully parsed JSON from API endpoint")
                    self.parseStrumykJson(json_data, url)
                    return
                except:
                    printDBG("Failed to parse API data as JSON")

        # If API endpoints don't work, try to find the data in the HTML using different patterns
        sts, data = self.cm.getPage(url, {'header': headers})
        if not sts:
            printDBG("Failed to get page content")
            return

        printDBG("Page content length: %d" % len(data))

        # Look for JavaScript variables that might contain the data
        js_patterns = [
            r'var\s+matches\s*=\s*(\[.*?\]);',
            r'const\s+matches\s*=\s*(\[.*?\]);',
            r'let\s+matches\s*=\s*(\[.*?\]);',
            r'window\.matches\s*=\s*(\[.*?\]);',
            r'data:\s*(\[.*?\]),',
            r'matches:\s*(\[.*?\]),',
        ]

        for pattern in js_patterns:
            matches = re.findall(pattern, data, re.DOTALL)
            for match in matches:
                try:
                    json_data = json_loads(match)
                    printDBG("Found matches data in JavaScript variable")
                    self.parseStrumykJson(json_data, url)
                    return
                except:
                    printDBG("Failed to parse JavaScript variable as JSON")

        # If all else fails, try to use a hardcoded list of matches or categories
        printDBG("Using fallback hardcoded categories")

        # Create some basic categories based on common sports
        categories = [
            {"name": "Football", "url": "/schedule?sport=football"},
            {"name": "Tennis", "url": "/schedule?sport=tennis"},
            {"name": "Volleyball", "url": "/schedule?sport=volleyball"},
            {"name": "Basketball", "url": "/schedule?sport=basketball"},
            {"name": "Hockey", "url": "/schedule?sport=hockey"},
        ]

        for category in categories:
            full_url = self.cm.getFullUrl(category["url"], url)
            params = {
                'name': "strumyk_cat",
                'title': category["name"],
                'url': full_url,
                'desc': "",
                'icon': ""
            }
            self.addDir(params)

    # lululla modd

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", '')
        title = self.currItem.get("title", '')
        icon = self.currItem.get("icon", '')
        url = self.currItem.get("url", '')
        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s]" % (name))
        self.currList = []

    # MAIN MENU
        if name is None:
            self.listsMainMenu(self.MAIN_GROUPED_TAB, {'image_type': "WWW"})
        elif name == "HasBahCa":
            self.listHasBahCa(self.currItem)
        elif name == "m3u":
            self.m3uList(url)
        elif name == "prognoza.pogody.tv":
            self.prognozaPogodyList(url)
        elif name == "sport365.live":
            self.getSport365LiveList(self.currItem)
        elif name == "videostar.pl":
            self.getVideostarList(self.currItem)
        elif name == "bilasport.com":
            self.getBilaSportPwList(self.currItem)
        elif name == "canlitvlive.io":
            self.getCanlitvliveIoList(self.currItem)
        elif name == "djing.com":
            self.getDjingComList(self.currItem)
        elif name == 'ustvnow':
            self.getUstvnowList(self.currItem)
        elif name == 'karwan.tv':
            self.getKarwanTvList(self.currItem)
        elif name == 'meteo.pl':
            self.getMeteoPLList(self.currItem)
        elif name == 'skylinewebcams.com':
            self.getWkylinewebcamsComList(self.currItem)
        elif name == 'livespotting.tv':
            self.getLivespottingTvList(self.currItem)
        elif name == 'weeb.tv':
            self.getWeebTvList(url)
        elif name == "webcamera.pl":
            self.getWebCamera(self.currItem)
        elif name == "filmon_groups":
            self.getFilmOnGroups()
        elif name == "filmon_channels":
            self.getFilmOnChannels()
        elif name == 'others':
            self.getOthersList(self.currItem)
        elif name == 'mlbstream.tv':
            self.getMLBStreamTVList(self.currItem)
        elif name == 'wiziwig1.eu':
            self.getWiziwig1List(self.currItem)
        elif name == 'nhl66.ir':
            self.getNhl66List(url)
        elif name == 'strumyk.net':
            self.getStrumykTvList(url)
        elif name == 'strumyk_tv':
            self.getStrumykTvDir(url)
        elif name == 'strumyk_cat':
            self.getStrumykTvDirCat(url)

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, HasBahCa(), withSearchHistrory=False)

    def getLogoPath(self):
        return RetHost(RetHost.OK, value=[GetLogoDir('webstreamslogo.png')])

    def getLinksForVideo(self, Index=0, selItem=None):
        listLen = len(self.host.currList)
        if listLen <= Index or Index < 0:
            printDBG("ERROR getLinksForVideo - current list is to short len: %d, Index: %d" % (listLen, Index))
            return RetHost(RetHost.ERROR, value=[])

        if self.host.currList[Index]["type"] not in ['video', 'audio', 'picture']:
            printDBG("ERROR getLinksForVideo - current item has wrong type")
            return RetHost(RetHost.ERROR, value=[])

        retlist = []
        cItem = self.host.currList[Index]
        url = self.host.currList[Index].get("url", '')
        name = self.host.currList[Index].get("name", '')

        printDBG(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> [%s] [%s]" % (name, url))
        urlList = None

        if -1 != url.find('teledunet'):
            new_url = TeledunetParser().get_rtmp_params(url)
            if 0 < len(url):
                retlist.append(CUrlItem("Własny link", new_url))
        elif name == "sport365.live":
            urlList = self.host.getSport365LiveLink(cItem)
        elif name == 'others':
            urlList = self.host.getOthersLinks(cItem)
        elif 'weeb.tv' in name:
            url = self.host.getWeebTvLink(url)
        elif name == "filmon_channel":
            urlList = self.host.getFilmOnLink(channelID=url)
        elif name == "videostar.pl":
            urlList = self.host.getVideostarLink(cItem)
        elif name == 'bilasport.com':
            urlList = self.host.getBilaSportPwLink(cItem)
        elif name == 'canlitvlive.io':
            urlList = self.host.getCanlitvliveIoLink(cItem)
        elif name == 'djing.com':
            urlList = self.host.getDjingComLink(cItem)
        elif name == 'ustvnow':
            urlList = self.host.getUstvnowLink(cItem)
        elif name == 'karwan.tv':
            urlList = self.host.getKarwanTvLink(cItem)
        elif name == 'meteo.pl':
            urlList = self.host.getMeteoPLLink(cItem)
        elif name == 'skylinewebcams.com':
            urlList = self.host.getWkylinewebcamsComLink(cItem)
        elif name == "webcamera.pl":
            urlList = self.host.getWebCameraLink(cItem)
        elif name == "prognoza.pogody.tv":
            urlList = self.host.prognozaPogodyLink(url)
        elif name == "mlbstream.tv":
            urlList = self.host.getMLBStreamTVLink(cItem)
        elif name == "wiziwig1.eu":
            urlList = self.host.getWiziwig1Link(cItem)

        # mod lululla
        elif name == "strumyk.net":
            # Se l'URL ha bisogno di essere risolto
            if hasattr(url, 'meta') and url.meta.get('need_resolve') == '1':
                urlList = self.host.resolveVidembed(str(url))
            else:
                urlList = self.host.getStrumykTvLink(url)

        if isinstance(urlList, list):
            for item in urlList:
                retlist.append(CUrlItem(item['name'], item['url'], item.get('need_resolve', 0)))
        elif isinstance(url, basestring):
            if url.endswith('.m3u'):
                tmpList = self.host.getDirectVideoHasBahCa(name, url)
                for item in tmpList:
                    retlist.append(CUrlItem(item['name'], item['url']))
            else:
                url = urlparser.decorateUrl(url)
                iptv_proto = url.meta.get('iptv_proto', '')
                if 'm3u8' == iptv_proto:
                    if '84.114.88.26' == url.meta.get('X-Forwarded-For', ''):
                        url.meta['iptv_m3u8_custom_base_link'] = '' + url
                        url.meta['iptv_proxy_gateway'] = 'http://webproxy.at/surf/printer.php?u={0}&b=192&f=norefer'
                        url.meta['Referer'] = url.meta['iptv_proxy_gateway'].format(urllib_quote_plus(url))
                        meta = url.meta
                        tmpList = getDirectM3U8Playlist(url, checkExt=False)
                        if 1 == len(tmpList):
                            url = urlparser.decorateUrl(tmpList[0]['url'], meta)

                    tmpList = getDirectM3U8Playlist(url, checkExt=False)
                    for item in tmpList:
                        retlist.append(CUrlItem(item['name'], item['url']))
                elif 'f4m' == iptv_proto:
                    tmpList = getF4MLinksWithMeta(url, checkExt=False)
                    for item in tmpList:
                        retlist.append(CUrlItem(item['name'], item['url']))
                else:
                    if '://' in url:
                        ua = strwithmeta(url).meta.get('User-Agent', '')
                        if 'balkanstream.com' in url:
                            if '' == ua:
                                url.meta['User-Agent'] = 'Mozilla/5.0'

                        retlist.append(CUrlItem("Link", url))

        return RetHost(RetHost.OK, value=retlist)
    # end getLinksForVideo

    def getResolvedURL(self, url):
        retlist = []
        url = strwithmeta(url)
        name = url.meta.get('name', '')

        printDBG("getResolvedURL url[%s], meta[%s]" % (url, url.meta))

        urlList = []

        if name == 'bilasport.com':
            urlList = self.host.getBilaSportPwResolvedLink(url)
        elif name == 'mlbstream.tv':
            urlList = self.host.getMLBStreamResolvedLink(url)

        if isinstance(urlList, list):
            for item in urlList:
                need_resolve = 0
                retlist.append(CUrlItem(item["name"], item["url"], need_resolve))

        return RetHost(RetHost.OK, value=retlist)
