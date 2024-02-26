# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, GetIPTVNotify
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem, ArticleContent, RetHost, CUrlItem
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import CSelOneLink, printDBG, printExc, MergeDicts
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs import ph
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist

###################################################

###################################################
# FOREIGN import
###################################################
import re
import time
import datetime
import random
from Components.config import config, ConfigText, ConfigSelection, ConfigYesNo, getConfigListEntry

###################################################

###################################################
# Config options for HOST
###################################################

#config.plugins.iptvplayer.ekstraklasa_usedf = ConfigYesNo(default = False)
#config.plugins.iptvplayer.ekstraklasa_proxy = ConfigYesNo(default = False)

config.plugins.iptvplayer.ekstraklasa_defaultres = ConfigSelection(default="0", choices=[("0", _("Ask")), ("800", "800 kbps"), ("1000", "1000 kbps"), ("1800", "1800 kbps"), ("3600", "3600 kbps"), ("6000", "6000 kbps"), ("99999", "Max")])
config.plugins.iptvplayer.ekstraklasa_login = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.ekstraklasa_password = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Max bitrate:"), config.plugins.iptvplayer.ekstraklasa_defaultres))
    optionList.append(getConfigListEntry(_("Username"), config.plugins.iptvplayer.ekstraklasa_login))
    optionList.append(getConfigListEntry(_("Password"), config.plugins.iptvplayer.ekstraklasa_password))

    #optionList.append( getConfigListEntry( "Używaj domyślnego format video:", config.plugins.iptvplayer.ekstraklasa_usedf ) )
    #optionList.append( getConfigListEntry( "Ekstraklasa korzystaj z proxy?", config.plugins.iptvplayer.ekstraklasa_proxy) )
    return optionList
###################################################


def gettytul():
    return 'https://ekstraklasa.tv/'


class Ekstraklasa(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'ekstraklasa.tv', 'cookie': 'ektraklasa.cookie'})

        self.MAIN_URL = 'https://ekstraklasa.tv/'
        self.ORG_URL = 'https://ekstraklasa.org/'
        self.CHANNELS_JSON_URL = 'https://core.oz.com/channels?slug=ekstraklasa&org=ekstraklasa.tv'
        self.AUTH_URL = "https://core.oz.com/oauth2/token"
        #self.CHANNELS_JSON_URL = 'https://core.oz.com/channels'

        self.DEFAULT_ICON_URL = "https://d3pwgdagcpl4mv.cloudfront.net/oz/image/upload/f_auto,fl_progressive,w_300/v1565967880/gbtbw0hwdthy72jknsct.png"

        #self.HEADER = {'User-Agent':self.USER_AGENT, 'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Encoding':'gzip, deflate'}
        #self.AJAX_HEADER = dict(self.HEADER)
        #self.AJAX_HEADER.update( {'X-Requested-With': 'XMLHttpRequest'} )
        #self.cm.HEADER = self.HEADER # default header
        #self.defaultParams = {'header':self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.MAIN_CAT_TAB = [
                            {'category': 'matches', 'title': _('Matches'), 'url': self.MAIN_URL + 'ekstraklasa/schedule'},
                            {'category': 'categories', 'title': _('Videos'), 'url': self.MAIN_URL + 'ekstraklasa/browse'},
                            #{'category':'search',           'title': _('Search'), 'search_item':True,   },
                            #{'category':'search_history',   'title': _('Search history'),               }
                            ]

        self.loggedIn = None
        self.token = ""
        self.login = ''
        self.password = ''

        self.timeoffset = datetime.datetime.now() - datetime.datetime.utcnow() + datetime.timedelta(milliseconds=500)

    def TryToLogin(self):
        printDBG("Ekstraklasa.TryToLogin")

        if None == self.loggedIn or self.login != config.plugins.iptvplayer.ekstraklasa_login.value or\
            self.password != config.plugins.iptvplayer.ekstraklasa_password.value:

            self.login = config.plugins.iptvplayer.ekstraklasa_login.value
            self.password = config.plugins.iptvplayer.ekstraklasa_password.value

            self.loggedIn = False
            self.loginMessage = ''

            if '' == self.login.strip() or '' == self.password.strip():
                msg = _('The host %s requires subscription.\nPlease fill your login and password in the host configuration - available under blue button.') % self.getMainUrl()
                GetIPTVNotify().push(msg, 'info', 10)
                return False

            clsecret = 'PHb7Aw7KZXGMYvgfEz'
            clid = "ClubWebClient"
            #UA = 'Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:68.0) Gecko/20100101 Firefox/68.0'

            postData = {
                "client_id": clid,
                "client_secret": clsecret,
                "grant_type": "password",
                "username": self.login.strip(),
                "password": self.password.strip(),
            }

            sts, data = self.cm.getPage(self.AUTH_URL, post_data=postData)

            if sts:
                printDBG("------------- auth --------------")
                printDBG(data)
                printDBG("------------------------------")

            try:
                response = json_loads(data)
                self.token = response["access_token"]
                self.loggedIn = True
                printDBG('EuroSportPlayer.tryTologin end loggedIn[%s]' % self.loggedIn)
                return True

            except:
                msg = _('Login failed. Invalid email or password.')
                GetIPTVNotify().push(msg, 'error', 10)
                return False

    def getVideoInfo(self, video_json):
        printDBG("Ekstraklasa.getVideoInfo")

        descStr = []

        if 'streamUrl' in video_json['_links']:
            url = video_json['_links']['streamUrl']
        else:
            url = ''

        title = video_json.get('title', '')

        if "scheduledAirDate" in video_json:
            date_time_str = video_json["scheduledAirDate"]
            date_time_obj = datetime.datetime.strptime(date_time_str, '%Y-%m-%dT%H:%M:%S.%fZ') + self.timeoffset #"2020-06-09T15:55:00.000Z"
            date_time_text = date_time_obj.strftime("%d/%m/%Y, %H:%M")
            title = title + " (" + date_time_text + ")"

            scheduleDate = date_time_text
        else:
            scheduleDate = ""

        icon = video_json.get('posterUrl', '')

        duration = video_json.get("duration", 0)
        if duration > 0:
            descStr.append(_("Duration") + ": " + str(datetime.timedelta(seconds=int(duration))))

        vtype = video_json.get("sourceType", "")

        if vtype:
            descStr.append(_("Source type") + ": " + vtype)

        free = video_json.get("isFree", False)
        if free:
            descStr.append(_("Free"))
        else:
            descStr.append(_("Not Free"))

        playFrom = video_json.get("playableFrom", '') #"2020-06-07T17:55:00.000Z"
        if playFrom:
            date_time_str = playFrom
            date_time_obj = datetime.datetime.strptime(date_time_str, '%Y-%m-%dT%H:%M:%S.%fZ') + self.timeoffset #"2020-06-09T15:55:00.000Z"
            date_time_text = date_time_obj.strftime("%d/%m/%Y, %H:%M")

            descStr.append(_("Playable from ") + date_time_text)

        desc = '|'.join(descStr)

        if url:
            params = {'url': url, 'title': title, 'icon': icon, 'desc': desc}
        else:
            params = {'url': '', 'title': title, 'icon': icon, 'desc': desc, 'schedule_date': scheduleDate}

        return params

    def getCollectionInfo(self, coll_json):
        printDBG("Ekstraklasa.getCollectionInfo")

        descStr = []

        icon = coll_json.get('posterUrl', '')
        title = coll_json.get('name', '')
        count = coll_json.get('videoCount', 0)
        if count > 0:
            title = '%s [%s]' % (title, count)

        url = coll_json['_links']['videosCollectionsV2']

        desc = '|'.join(descStr)

        params = {'title': title, 'url': url, 'icon': icon, 'category': 'cat', 'desc': desc}

        return params

    def listMainMenu(self, cItem):
        printDBG("Ekstraklasa.listMainMenu")
        self.listsTab(self.MAIN_CAT_TAB, cItem)

    def listMatches(self, cItem):
        printDBG("Ekstraklasa.listMatches")

        sts, data = self.cm.getPage(self.CHANNELS_JSON_URL)

        if sts:

            response = json_loads(data)
            nextUrl = response['data'][0]['_links']['scheduleV2']

            printDBG("schedule collection url ------> '%s'" % nextUrl)
            sts, data = self.cm.getPage(nextUrl)

            if sts:

                try:
                    response = json_loads(data)

                    for item in response['data']['data']:
                        tmp = item.get('_meta', {})
                        playing = tmp.get('isNowPlaying', False)

                        v_json = item.get('video', '')

                        if v_json:
                            params2 = self.getVideoInfo(v_json)

                            if playing:
                                params2['title'] = '\c00????00 ' + params2['title'] + ' [Live]'
                                params2['url'] = item['_links']['streamUrl']
                                params2['desc'] = params2['desc'] + "|" + _("Now playing")

                            params = dict(cItem)
                            params.update(params2)
                            printDBG(str(params))
                            self.addVideo(params)

                except Exception:
                    printExc()

    def listCategories(self, cItem):
        printDBG("Ekstraklasa.listCategories")

        sts, data = self.cm.getPage(self.CHANNELS_JSON_URL)

        if sts:

            response = json_loads(data)
            nextUrl = response['data'][0]['_links']['videosCollectionsV2']

            printDBG("video collection url ------> '%s'" % nextUrl)
            sts, data = self.cm.getPage(nextUrl)

            if sts:

                try:

                    response = json_loads(data)

                    for item in response['data']:

                        c_json = item.get('collection', '')

                        if c_json:
                            params2 = self.getCollectionInfo(c_json)
                            params = dict(cItem)
                            params.update(params2)
                            printDBG(str(params))
                            self.addDir(params)

                except Exception:
                    printExc()

    def exploreCategory(self, cItem):
        printDBG("Ekstraklasa.exploreCategory '%s'" % cItem)

        url = cItem.get('url', '')
        page = cItem.get('page', 0)

        if not url:
            return

        if page > 0:
            url = "%s&page=%d" % (url, page)

        sts, data = self.cm.getPage(url)

        if sts:

            try:
                response = json_loads(data)

                for item in response['data']:

                    c_json = item.get('collection', '')
                    if c_json:
                        params2 = self.getCollectionInfo(c_json)
                        params = dict(cItem)
                        params.update(params2)
                        printDBG(str(params))
                        self.addDir(params)

                    v_json = item.get('video', '')
                    if v_json:
                        params2 = self.getVideoInfo(v_json)

                        params = dict(cItem)
                        params.update(params2)
                        printDBG(str(params))
                        self.addVideo(params)

                if len(response['data']) >= 25:
                    page = page + 1
                    params = dict(cItem)
                    params.update({'title': _("Next page"), 'page': page})
                    printDBG(str(params))
                    self.addMore(params)

            except Exception:
                printExc()

    def getLinksForVideo(self, cItem):
        printDBG("Ekstraklasa.getLinksForVideo '%s'" % cItem)

        url = cItem.get('url', '')
        if not url:
            scheduleDate = cItem.get('schedule_date', '')
            if scheduleDate:
                msg = _("Stream starts from %s") % scheduleDate
                GetIPTVNotify().push(msg, 'info', 10)
            return []

        if not self.loggedIn:
            # need to login to view videos
            self.TryToLogin()

        if not self.loggedIn:
            return []

        headers = {
            'User-Agent': "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36",
            'Accept': 'application/json',
            'Accept-Language': 'pl,en-US;q=0.7,en;q=0.3',
            'Referer': 'https://www.ekstraklasa.tv/',
            'Content-Type': 'application/json',
            'Authorization': 'Bearer %s' % self.token,
            'Origin': 'https://www.ekstraklasa.tv',
            'DNT': '1',
        }

        linksTab = []

        sts, data = self.cm.getPage(url, {'header': headers})

        if sts:
            printDBG("*********************")
            printDBG(data)
            printDBG("*********************")

            response = json_loads(data)
            url = response['data']['url']

            playlist = getDirectM3U8Playlist(url, checkExt=False, variantCheck=True, checkContent=True, sortWithMaxBitrate=99999999)
            if (config.plugins.iptvplayer.ekstraklasa_defaultres.value == None) or (config.plugins.iptvplayer.ekstraklasa_defaultres.value == '') or (config.plugins.iptvplayer.ekstraklasa_defaultres.value == "0"):
                linksTab.extend(playlist)
            else:
                def_res = int(config.plugins.iptvplayer.ekstraklasa_defaultres.value)
                printDBG(json_dumps(playlist))
                for track in playlist:
                    if int(track.get("bitrate", "0")) < (def_res * 1000):
                        linksTab.append(track)
                        break

        else:
            msg = _("You are not allowed to play this video")
            GetIPTVNotify().push(msg, 'info', 10)

        return linksTab

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
            self.listMainMenu(self.currItem)
        elif category == 'matches':
            self.listMatches(self.currItem)
        elif category == 'categories':
            self.listCategories(self.currItem)
        elif category == 'cat':
            self.exploreCategory(self.currItem)

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Ekstraklasa(), False)
