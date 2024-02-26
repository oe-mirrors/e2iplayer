# -*- coding: utf-8 -*-
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
    MAIN_GROUPED_TAB = [{'alias_id': 'weeb.tv', 'name': 'weeb.tv', 'title': 'http://weeb.tv/', 'url': '', 'icon': 'http://xmtvplayer.com/wp-content/uploads/2014/07/weebtv.png'},
                        {'alias_id': 'videostar.pl', 'name': 'videostar.pl', 'title': 'https://pilot.wp.pl/', 'url': '', 'icon': 'http://satkurier.pl/uploads/53612.jpg'},
                        {'alias_id': 'prognoza.pogody.tv', 'name': 'prognoza.pogody.tv', 'title': 'http://pogody.tv/', 'url': 'http://prognoza.pogody.tv', 'icon': 'http://pogody.pl/images/pogodytv.png'}, \
                        {'alias_id': 'meteo.pl', 'name': 'meteo.pl', 'title': 'http://meteo.pl/', 'url': 'http://meteo.pl/', 'icon': 'http://www.meteo.pl/img/napis_glowny_pl_2.png'}, \
                        {'alias_id': 'webcamera.pl', 'name': 'webcamera.pl', 'title': 'https://webcamera.pl/', 'url': 'https://www.webcamera.pl/', 'icon': 'http://static.webcamera.pl/webcamera/img/loader-min.png'}, \
                        {'alias_id': 'skylinewebcams.com', 'name': 'skylinewebcams.com', 'title': 'https://skylinewebcams.com/', 'url': 'https://www.skylinewebcams.com/', 'icon': 'https://cdn.skylinewebcams.com/skylinewebcams.png'}, \
                        {'alias_id': 'livespotting.tv', 'name': 'livespotting.tv', 'title': 'http://livespotting.tv/', 'url': 'http://livespotting.tv/', 'icon': 'https://livespotting.com/static/images/apple-touch-icon.png'},\
                        {'alias_id': 'filmon.com', 'name': 'filmon_groups', 'title': 'http://filmon.com/', 'url': 'http://www.filmon.com/', 'icon': 'http://static.filmon.com/theme/img/filmon_tv_logo_white.png'}, \
                        {'alias_id': 'ustvnow.com', 'name': 'ustvnow', 'title': 'https://ustvnow.com/', 'url': 'https://www.ustvnow.com/', 'icon': 'http://2.bp.blogspot.com/-SVJ4uZ2-zPc/UBAZGxREYRI/AAAAAAAAAKo/lpbo8OFLISU/s1600/ustvnow.png'}, \
                        {'alias_id': 'sport365.live', 'name': 'sport365.live', 'title': 'http://sport365.live/', 'url': 'http://www.sport365.live/', 'icon': 'http://s1.medianetworkinternational.com/images/icons/48x48px.png'}, \
                        {'alias_id': 'bilasport.com', 'name': 'bilasport.com', 'title': 'http://bilasport.com/', 'url': '', 'icon': 'https://projects.fivethirtyeight.com/2016-mlb-predictions/images/logos.png'}, \
                        {'alias_id': 'mlbstream.tv', 'name': 'mlbstream.tv', 'title': 'http://mlbstream.tv/ && http://nhlstream.tv/', 'url': '', 'icon': 'http://mlbstream.tv/wp-content/uploads/2018/03/mlb-network-291x300.png'}, \
                        {'alias_id': 'karwan.tv', 'name': 'karwan.tv', 'title': 'http://karwan.tv/', 'url': 'http://karwan.tv/', 'icon': 'http://karwan.tv//logo/karwan-tv/karwan-tv-1.png'}, \
                        {'alias_id': 'canlitvlive.io', 'name': 'canlitvlive.io', 'title': 'http://canlitvlive.io/', 'url': 'http://www.canlitvlive.io/', 'icon': 'http://www.canlitvlive.io/images/footer_simge.png'}, \
                        {'alias_id': 'wiziwig1.eu', 'name': 'wiziwig1.eu', 'title': 'http://wiziwig1.eu/', 'url': '', 'icon': 'http://i.imgur.com/yBX7fZA.jpg'},\
                        {'alias_id': 'djing.com', 'name': 'djing.com', 'title': 'https://djing.com/', 'url': 'https://djing.com/', 'icon': 'https://www.djing.com/newimages/content/c01.jpg'}, \
                        {'alias_id': 'nhl66.ir', 'name': 'nhl66.ir', 'title': 'https://nhl66.ir', 'url': 'https://api.nhl66.ir/api/sport/schedule', 'icon': 'https://nhl66.ir/cassets/logo.png'}, \
                        {'alias_id': 'strims.in', 'name': 'strims.in', 'title': 'http://strims.in/', 'url': 'http://strims.in/', 'icon': ''}, \
                       ]

    def __init__(self):
        CBaseHostClass.__init__(self)

        # temporary data
        self.currList = []
        self.currItem = {}

        #Login data
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
        if None == v:
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
        BASE_URL = 'http://hasbahcaiptv.com/'

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
            sts, data = self.getPage('http://hasbahcaiptv.com/page.php?seite=Passwort.html')
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
            title = self.cleanHtmlStr(item) #title.split('dir=')[-1]

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
        if None == self.filmOnApi:
            self.filmOnApi = FilmOnComApi()

    def getFilmOnLink(self, channelID):
        self.__setFilmOn()
        return self.filmOnApi.getUrlForChannel(channelID)

    def getFilmOnGroups(self):
        self.__setFilmOn()
        tmpList = self.filmOnApi.getGroupList()
        for item in tmpList:
            try:
                params = {'name': 'filmon_channels',
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
                params = {'name': 'filmon_channel',
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
                    cTitle = re.sub('\[[^\]]*?\]', '', title)
                    if len(cTitle):
                        title = cTitle
                    itemUrl = self.up.decorateParamsFromUrl(item)
                    if 'http://wownet.ro/' in itemUrl:
                        icon = 'http://wownet.ro/logo/' + icon
                    else:
                        icon = ''
                    if '' != catTitle:
                        desc = catTitle + ', '
                    else:
                        desc = ''
                    desc += (_("Protocol: ")) + itemUrl.meta.get('iptv_proto', '')

                    if 'headers=' in itemUrl:
                        headers = self.cm.ph.getSearchGroups(itemUrl, 'headers\=(\{[^\}]+?\})')[0]
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
        sts, data = self.cm.getPage("http://www.elevensports.pl/")
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
        if None == self.weebTvApi:
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
        if None == self.webCameraApi:
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
        if None == self.videoStarApi:
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
        if None == self.MLBStreamTVApi:
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
        if None == self.Wiziwig1Api:
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
        if None == self.ustvnowApi:
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
        if None == self.karwanTvApi:
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
        if None == self.bilaSportPwApi:
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
        if None == self.canlitvliveIoApi:
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
        if None == self.djingComApi:
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
        if None == self.meteoPLApi:
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
        if None == self.wkylinewebcamsComApi:
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
        if None == self.livespottingTvApi:
            self.livespottingTvApi = LivespottingTvApi()
        tmpList = self.livespottingTvApi.getChannelsList(cItem)
        for item in tmpList:
            self.addVideo(item)

    def getSport365LiveList(self, cItem):
        printDBG("getSport365LiveList start")
        if None == self.sport365LiveApi:
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
        url = self.cm.ph.getSearchGroups(data, 'src="([^"]+?\.mp4[^"]*?)"')[0]

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

    def getStrumykTvList(self, url):
        printDBG("StrumykTvList start")
        sts, data = self.cm.getPage(url)
        if not sts:
            return
        data = CParsingHelper.getDataBeetwenNodes(data, ('<table', '>', 'ramowka'), ('</table', '>'))[1]
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<td', '>'), ('</td', '>'))
        for item in data:
            linkVideo = self.cm.ph.getSearchGroups(item, '''\shref=['"]([^"^']+?)['"]''')[0]
            if len(linkVideo) and not linkVideo.startswith('http'):
                linkVideo = 'http://strims.in' + linkVideo
            if linkVideo.endswith('/') and 'class="f1' not in item:
                params = {'name': "strumyk_cat"}
            else:
                params = {'name': "strumyk_tv"}
            params['url'] = urlparser.decorateUrl(linkVideo, {'Referer': url})
#            params['icon'] = self.cm.ph.getSearchGroups(item, '''\ssrc=['"]([^"^']+?)['"]''')[0]
            params['title'] = self.cleanHtmlStr(item)
            self.addDir(params)

    def getStrumykTvDirCat(self, url):
        printDBG("getStrumykTvDirCat start")
        sts, data = self.cm.getPage(url)
        if not sts:
            return
        data = CParsingHelper.getDataBeetwenNodes(data, ('<table', '>', '-table'), ('</table', '>'))[1]
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<tr', '>'), ('</tr', '>'))
        for item in data:
            params = {'name': "strumyk_tv"}
            params['title'] = self.cleanHtmlStr(item)
            linkVideo = self.cm.ph.getSearchGroups(item, '''\shref=['"]([^"^']+?)['"]''')[0]
            if len(linkVideo):
                if not linkVideo.startswith('http'):
                    linkVideo = 'http://strims.in' + linkVideo
                params['url'] = urlparser.decorateUrl(linkVideo, {'Referer': url})
#                params['icon'] = self.cm.ph.getSearchGroups(item, '''\ssrc=['"]([^"^']+?)['"]''')[0]
                self.addDir(params)
            else:
                self.addMarker(params)

    def getStrumykTvDir(self, url):
        printDBG("StrumykTvDir start")
        sts, data = self.cm.getPage(url)
        if not sts:
            return []

        tmp = CParsingHelper.getDataBeetwenNodes(data, ('<iframe', '>', 'src'), ('<script', '>'))[1]
        if not tmp:
            tmp = CParsingHelper.getDataBeetwenNodes(data, ('<noscript', '>'), ('<script', '>'))[1]
        data = self.cm.ph.getAllItemsBeetwenNodes(tmp, ('<a', '>'), ('</a', '>'))
        if not data:
            linkVideo = self.cm.ph.getSearchGroups(tmp, '''src=['"]([^"^']+?)['"]''')[0]
            linkVideo = linkVideo.strip(' \n\t\r')
            if linkVideo.startswith('/live/'):
                sts, tmp = self.cm.getPage('http://strims.in' + linkVideo)
                if not sts:
                    return []
                linkVideo = self.cm.ph.getSearchGroups(tmp, '''src=['"]([^"^']+?)['"]''')[0]
                linkVideo = linkVideo.strip(' \n\t\r')
            if len(linkVideo):
                params = {'name': "strims.in"}
                params['url'] = urlparser.decorateUrl(linkVideo, {'Referer': url})
                params['title'] = self.up.getDomain(linkVideo)
                self.addVideo(params)

        for item in data:
            _url = self.cm.ph.getSearchGroups(item, '''\shref=['"]([^"^']+?)['"]''')[0]
            if '?' in url:
                url = url.split('?', 1)[0]
            if _url.startswith('?'):
                _url = url + _url
            if not _url.startswith('http'):
                _url = 'http://strims.in' + _url
            sts, data = self.cm.getPage(_url)
            if sts:
                tmp = CParsingHelper.getDataBeetwenNodes(data, ('<iframe', '>', 'allowfullscreen'), ('</iframe', '>'))[1]
                if len(tmp):
                    linkVideo = self.cm.ph.getSearchGroups(tmp, '''src=['"]([^"^']+?)['"]''')[0]
                    linkVideo = linkVideo.strip(' \n\t\r')
                else:
                    tmp = self.cm.ph.getSearchGroups(data, '''eval\(unescape\(['"]([^"^']+?)['"]''')[0]
                    tmp = urllib_unquote(tmp)
                    linkVideo = self.cm.ph.getSearchGroups(tmp, '''['"]*(http[^'^"]+?\.m3u8[^'^"]*?)['"]''')[0]
                if len(linkVideo) and linkVideo.startswith('//'):
                    linkVideo = 'http:' + linkVideo
                if len(linkVideo) and not linkVideo.startswith('http'):
                    linkVideo = 'http://strims.in' + linkVideo
                    sts, data = self.cm.getPage(linkVideo)
                    tmp = CParsingHelper.getDataBeetwenNodes(data, ('<iframe', '>', 'src'), ('</iframe', '>'))[1]
                    if len(tmp):
                        linkVideo = self.cm.ph.getSearchGroups(tmp, '''src=['"]([^"^']+?)['"]''')[0]
                        linkVideo = linkVideo.strip(' \n\t\r')
                    else:
                        tmp = self.cm.ph.getSearchGroups(data, '''eval\(unescape\(['"]([^"^']+?)['"]''')[0]
                        tmp = urllib_unquote(tmp)
                        linkVideo = self.cm.ph.getSearchGroups(tmp, '''['"]*(http[^'^"]+?\.m3u8[^'^"]*?)['"]''')[0]
                        if '' == linkVideo:
                            linkVideo = self.cm.ph.getSearchGroups(tmp, '''['"]*(http[^'^"]+?\.mpd[^'^"]*?)['"]''')[0].replace('\\', '')
                    if len(linkVideo) and linkVideo.startswith('//'):
                        linkVideo = 'http:' + linkVideo
                linkVideo = linkVideo.replace('https://href.li/', '')
                if '' == linkVideo:
                    continue
                params = {'name': "strims.in"}
                params['url'] = urlparser.decorateUrl(linkVideo, {'Referer': url})
                params['title'] = self.cleanHtmlStr(item) + ' - ' + self.up.getDomain(linkVideo)
                printDBG("StrumykTvDir params [%s]" % params)
                self.addVideo(params)

    def getStrumykTvLink(self, url):
        printDBG("StrumykTvLink url[%r]" % url)
        urlsTab = []

        if 'm3u8' in url and 'hlsplayer' not in url:
            urlsTab = getDirectM3U8Playlist(url, False)
        elif 'mpd' in url:
            urlsTab = getMPDLinksWithMeta(url, False)
        else:
            urlsTab.extend(self.up.getVideoLinkExt(url))
        return urlsTab

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        title = self.currItem.get("title", '')
        icon = self.currItem.get("icon", '')
        url = self.currItem.get("url", '')
        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s]" % (name))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listsMainMenu(self.MAIN_GROUPED_TAB)
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
        elif name == 'strims.in':
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
        elif name == "strims.in":
            urlList = self.host.getStrumykTvLink(url)

        if isinstance(urlList, list):
            for item in urlList:
                retlist.append(CUrlItem(item['name'], item['url'], item.get('need_resolve', 0)))
        elif isinstance(url, str):
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
