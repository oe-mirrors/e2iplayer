# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, GetIPTVNotify
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm, NextDay, PrevDay
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.components.captcha_helper import CaptchaHelper
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
###################################################
# FOREIGN import
###################################################
import time
from datetime import datetime, timedelta
import operator
from Components.config import config, ConfigText, getConfigListEntry
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.eurosportplayer_login = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.eurosportplayer_password = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("e-mail") + ":", config.plugins.iptvplayer.eurosportplayer_login))
    optionList.append(getConfigListEntry(_("password") + ":", config.plugins.iptvplayer.eurosportplayer_password))
    return optionList
###################################################


def gettytul():
    return 'https://www.eurosportplayer.com/'


class EuroSportPlayer(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'eurosportplayer.com', 'cookie': 'eurosportplayer.com.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/76.0.3809.132 Safari/537.36'
        self.MAIN_URL = 'https://www.eurosportplayer.com/'
        self.LOGIN_URL = 'https://auth.eurosportplayer.com/login?flow=login'

        self.API_URL = 'https://eu3-prod-direct.eurosportplayer.com/'
        self.USER_URL = self.API_URL + 'users/me'
        self.TOKEN_URL = self.API_URL + 'token?realm=eurosport&shortlived=true'
        self.CONFIG_URL = self.API_URL + "cms/configs/auth"
        self.MENUBAR_URL = self.API_URL + "cms/collections/web-menubar?include=default"
        self.SCHEDULE_URL = self.API_URL + "cms/routes/schedule?include=default"
        self.SCHEDULE_COLLECTION_URL = self.API_URL + 'cms/collections/{%id%}?include=default&{%filter%}'
        self.PLAYBACK_URL = self.API_URL + '/playback/v2/videoPlaybackInfo/{%video_id%}?usePreAuth=true'

        self.DEFAULT_ICON_URL = 'http://mirrors.kodi.tv/addons/leia/plugin.video.eurosportplayer/resources/icon.png'

        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'Referer': self.getMainUrl(), 'Origin': self.getMainUrl(), 'X-disco-client': 'WEB:UNKNOWN:esp-web:prod'}
        self.defaultParams = {'header': {'User-Agent': self.USER_AGENT}, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.recaptcha_sitekey = "6LfvErIUAAAAABlpqACnxRiUhqhX4p14sPxx_sKf"

        self.loggedIn = None
        self.login = ''
        self.password = ''

        # eurosport database
        self.espChannels = {}
        self.espRoutes = {}
        self.espCollections = {}
        self.espCollectionItems = {}
        self.espImages = {}
        self.espVideos = {}
        self.espTaxonomyNodes = {}
        self.espShows = {}

        self.OFFSET = datetime.now() - datetime.utcnow()
        seconds = self.OFFSET.seconds + self.OFFSET.days * 24 * 3600
        if ((seconds + 1) % 10) == 0:
            seconds += 1
        elif ((seconds - 1) % 10) == 0:
            seconds -= 1
        self.OFFSET = timedelta(seconds=seconds)

        self.ABBREVIATED_MONTH_NAME_TAB = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        self.ABBREVIATED_DAYS_NAME_TAB = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def getFullPath(self, url, category):
        if category == 'route':
            url = self.API_URL + 'cms/routes' + url
        elif category == 'video':
            url = 'https://www.eurosportplayer.com/videos/' + url
        return url

    def listMainMenu(self, cItem):
        printDBG("EuroSportPlayer.listMainMenu")

        try:
            CAT_TAB = [
                       {'category': 'on_air', 'title': _('On Air'), },
                       {'category': 'schedule', 'title': _('Schedule'), },
                       {'category': 'vod_sport_filters', 'title': _('All Sports'), } #,
                       #{'category':'search',             'title': _('Search'),          'search_item':True    },
                       #{'category':'search_history',     'title': _('Search history')}
                      ]

            self.listsTab(CAT_TAB, cItem)
        except Exception:
            printExc()

    def _str2date(self, txt):
        txt = self.cm.ph.getSearchGroups(txt, '([0-9]+\-[0-9]+\-[0-9]+T[0-9]+\:[0-9]+:[0-9]+)')[0]
        return datetime.strptime(txt, '%Y-%m-%dT%H:%M:%S')

    def _gmt2local(self, txt):
        utc_date = self._str2date(txt)
        utc_date = utc_date + self.OFFSET
        if utc_date.time().second == 59:
            utc_date = utc_date + timedelta(0, 1)
        return utc_date

    def _absTimeDelta(self, d1, d2, div=60):
        if d1 > d2:
            td = d1 - d2
        else:
            td = d2 - d1
        return (td.seconds + td.days * 24 * 3600) / div

    def addItemInDB(self, item):
        itemType = item['type']
        itemId = item['id']

        if itemType == 'channel':
            self.espChannels[itemId] = item
        elif itemType == 'route':
            self.espRoutes[itemId] = item
        elif itemType == 'collection':
            self.espCollections[itemId] = item
        elif itemType == 'collectionItem':
            self.espCollectionItems[itemId] = item
        elif itemType == 'image':
            self.espImages[itemId] = item
        elif itemType == 'show':
            self.espShows[itemId] = item
        elif itemType == 'video':
            self.espVideos[itemId] = item
        elif itemType == 'taxonomyNode':
            self.espTaxonomyNodes[itemId] = item
        else:
            printDBG("unhandled type %s" % itemType)

    def addVideoFromData(self, videoData, OnlyLive=False, label_format=None, future=False):
        # printDBG(json_dumps(videoData))
        #{"relationships": {
        #       "txSports": {"data": [{"type": "taxonomyNode", "id": "bec78875-c777-4b6b-aa5f-6f73093fef69"}]},
        #       "txCompetitions": {"data": [{"type": "taxonomyNode", "id": "3cc643aa-be3c-4bbc-b0bd-45537f4f9025"}]},
        #       "show": {"data": {"type": "show", "id": "5528"}},
        #       "contentPackages": {"data": [{"type": "package", "id": "Eurosport"}]},
        #       "primaryChannel": {"data": {"type": "channel", "id": "95"}},
        #       "txLegs": {"data": [{"type": "taxonomyNode", "id": "cdf73e0d-4662-4034-b238-87de281f89e5"}]},
        #       "routes": {"data": [{"type": "route", "id": "ba42a747696c2cc69574ee9414806703f3cc4271c97578ed68d795e81f526c3c"}]},
        #       "txMagazines": {"data": [{"type": "taxonomyNode", "id": "76f872af-e546-4a43-ac15-5a2512c36103"}]},
        #       "images": {"data": [{"type": "image", "id": "video_250797_80ec9f08-4b37-3033-994d-c492747cbdc7_default_it"}]},
        #       "txEvents": {"data": [{"type": "taxonomyNode", "id": "8aaff87f-4933-46e6-a9f3-872b336b2d8b"}]}
        #   },
        #   "attributes": {
        #       "availabilityWindows": [{"playableEnd": "2019-11-26T00:00:00Z", "playableStart": "2019-10-27T08:50:00Z", "package": "Eurosport"}],
        #       "isNew": false,
        #       "publishStart": "2019-10-20T00:00:00Z",
        #       "contentRatings": [],
        #       "alternateId": "world-cup-ambient-sound-250797",
        #       "clearkeyEnabled": true, "secondaryTitle": "Coppa del Mondo di Sci alpino",
        #       "drmEnabled": false,
        #       "contentDescriptors": [],
        #       "sourceSystemId": "eurosport-e14695126c0ch719",
        #       "scheduleStart": "2019-10-27T08:50:00Z",
        #       "description": "La Coppa del Mondo di sci alpino maschile 2019-20 prende il via in Austria, il primo appuntamento \u00e8 a S\u00f6lden.",
        #       "videoDuration": 6060000,
        #       "publishEnd": "2019-11-26T00:00:00Z",
        #       "earliestPlayableStart": "2019-10-27T08:50:00Z",
        #       "path": "eurosport/world-cup-ambient-sound-250797",
        #       "packages": ["Eurosport"],
        #       "videoType": "STANDALONE",
        #       "name": "S\u00f6lden, Gigante uomini (1a manche)",
        #       "rights": {"embeddable": false},
        #       "geoRestrictions": {"mode": "permit", "countries": ["world"]},
        #       "identifiers": {"epgId": "1041169", "originalMediaId": "64104745-4d53-40f8-aebd-ded76ebac868", "analyticsId": "e14695126c0ch719", "freewheel": "eurosport-e14695126c0ch719"},
        #       "scheduleEnd": "2019-10-27T10:50:00Z",
        #       "customAttributes": {"classificationId": "24851"},
        #       "sourceSystemName": "vdp",
        #       "playableTerritories": {"territories": ["de", "pt", "dk", "lt", "lu", "hr", "lv", "ua", "hu", "mc", "md", "me", "mf", "yt", "ie", "mk", "ee", "ad", "il", "im", "mq", "io", "mt", "is", "al", "it", "va", "am", "es", "vg", "at", "re", "nc", "ax", "az", "je", "ro", "nl", "ba", "no", "rs", "be", "fi", "ru", "bg", "fk", "fo", "fr", "wf", "fx", "se", "si", "by", "sk", "sm", "gb", "ge", "gf", "gg", "gi", "ko", "ch", "gl", "gp", "gr", "ta", "kz", "gy", "tf", "cy", "pf", "cz", "pl", "li", "pm", "tr"], "mode": "permit"},
        #       "isExpiring": false},
        #   "type": "video",
        #   "id": "250797"
        #}
        params = {}
        video_id = videoData['id']
        item_data = videoData['attributes']
        printDBG(json_dumps(item_data))

        if 'broadcastType' in item_data:
            #printDBG(" %s, %s , %s" % (item_data['name'], item_data['videoType'], item_data['broadcastType'] ))
            bt = item_data['broadcastType']
        else:
            #printDBG(" %s, %s , %s" % (item_data['name'], item_data['videoType'], '' ))
            bt = item_data['videoType']

        if (not OnlyLive) or (item_data['videoType'] == 'LIVE'):
            if 'scheduleStart' in item_data:
                start = item_data['scheduleStart']
            else:
                start = item_data['earliestPlayableStart']

            #printDBG("start: %s" % start)
            scheduleDate = self._gmt2local(start)
            #printDBG("local time: %s" % str(scheduleDate))

            if scheduleDate < datetime.now() or future:

                txtDate = scheduleDate.strftime("%d/%m/%Y")
                txtTime = scheduleDate.strftime("%H:%M")

                #"routes": {"data": [{"type": "route", "id": "ba42a747696c2cc69574ee9414806703f3cc4271c97578ed68d795e81f526c3c"}]},
                if 'routes' in videoData['relationships']:
                    route_id = videoData['relationships']['routes']['data'][0]['id']
                else:
                    route_id = ''

                if label_format:
                    if label_format == 'schedule':
                        if 'txSports' in videoData['relationships']:
                            sport_node_id = videoData['relationships']['txSports']['data'][0]['id']
                            sport = self.espTaxonomyNodes[sport_node_id]
                            #printDBG(json_dumps(sport))
                            txtSport = sport['attributes']['name']
                        else:
                            txtSport = ''

                        if 'primaryChannel' in videoData['relationships']:
                            channel_id = videoData['relationships']['primaryChannel']['data']['id']
                            channel = self.espChannels[channel_id]
                            #printDBG(json_dumps(channel))
                            txtChannel = channel['attributes']['name']
                        else:
                            txtChannel = ''

                        if bt == 'LIVE':
                            title = " %s %s - %s [%s]" % (txtTime, txtSport.upper(), item_data['name'], bt)
                        else:
                            title = " %s %s - %s - %s" % (txtTime, txtSport.upper(), item_data['name'], txtChannel)
                    # elif altri casi
                    else:
                        title = item_data['name'] + "  [%s] - (%s)" % (bt, txtDate)

                else:
                    title = item_data['name'] + "  [%s] - (%s)" % (bt, txtDate)

                desc = "video id: %s\n" % video_id
                if 'videoDuration' in item_data:
                    desc = desc + _("Duration") + ": %s" % str(timedelta(seconds=int(item_data['videoDuration'] / 1000))) + "\n"
                if 'secondaryTitle' in item_data:
                    desc = desc + item_data['secondaryTitle'] + "\n"

                desc = desc + item_data.get('description', '')

                icon_id = videoData['relationships']['images']['data'][0]['id']
                icon = self.espImages[icon_id]['attributes']['src']

                url = self.getFullPath(item_data['path'], 'video')

                params = {'title': title, 'desc': desc, 'url': url, 'icon': icon, 'video_id': video_id, 'schedule_date': scheduleDate, 'route_id': route_id}
                printDBG(str(params))

        return params

    def listSportFilters(self, cItem, nextCategory):
        printDBG("EuroSportPlayer.listSportFilters [%s]" % cItem)
        try:

            sts, data = self.getPage(self.MENUBAR_URL)
            if not sts:
                return

            data = json_loads(data)

            menuData = {}

            for item in data['included']:

                if item['type'] == 'collection':
                    if item['attributes']['alias'] == 'auto-taxonomy-container':
                        printDBG(item['attributes']['title'])
                        menuData = item['relationships']['items']
                        printDBG("-----------------------")
                        printDBG(json_dumps(menuData))
                        printDBG("-----------------------")
                else:
                    self.addItemInDB(item)

            for item in menuData['data']:
                #printDBG(json_dumps(self.espCollectionItems[item['id']]))
                node_id = self.espCollectionItems[item['id']]['relationships']['taxonomyNode']['data']['id']
                node = self.espTaxonomyNodes[node_id]

                #printDBG(json_dumps(node))
                iconData = self.espImages[node['relationships']['images']['data'][0]['id']]
                #printDBG(json_dumps(iconData))
                route_id = node['relationships']['routes']['data'][0]['id']
                routeData = self.espRoutes[route_id]
                #printDBG(json_dumps(routeData))
                title = node['attributes']['name']
                icon = iconData['attributes']['src']
                url = self.getFullPath(routeData['attributes']['url'], 'route')
                params = {'good_for_fav': False, 'category': nextCategory, 'title': title, 'icon': icon, 'url': url}
                printDBG(str(params))
                self.addDir(params)
                printDBG("-------------------------------------------")

        except Exception:
            printExc()

    def listVodItems(self, cItem):
        printDBG("EuroSportPlayer.listVodTypesFilters [%s]" % cItem)
        try:
            url = cItem['url'] + '?include=default'
            sts, data = self.getPage(url)
            if not sts:
                return

            #printDBG(data)
            data = json_loads(data)

            videoList = []
            videoParamsList = []
            for item in data['included']:
                self.addItemInDB(item)

                if item['type'] == 'video':
                    videoList.append(item['id'])

            for id in videoList:
                videoData = self.espVideos[id]
                params = self.addVideoFromData(videoData)
                if params:
                    videoParamsList.append(params)

            videoParamsList.sort(key=operator.itemgetter('schedule_date'), reverse=True)
            for v in videoParamsList:
                self.addVideo(v)

        except Exception:
            printExc()

    def listOnAir(self, cItem):
        printDBG("EuroSportPlayer.listOnAir [%s]" % cItem)
        try:

            url = "https://eu3-prod-direct.eurosportplayer.com/cms/routes/home?include=default"
            sts, data = self.getPage(url, {'header': {'User-Agent': self.USER_AGENT}, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE})
            if not sts:
                return

            data = json_loads(data)

            videoList = []
            videoParamsList = []
            for item in data['included']:
                self.addItemInDB(item)

                if item['type'] == 'video':
                    videoList.append(item['id'])

            for id in videoList:
                videoData = self.espVideos[id]
                params = self.addVideoFromData(videoData, OnlyLive=True, label_format='schedule', future=False)
                if params:
                    videoParamsList.append(params)

            videoParamsList.sort(key=operator.itemgetter('schedule_date'))
            for v in videoParamsList:
                self.addVideo(v)

        except Exception:
            printExc()

    def listDays(self, cItem, nextCategory):
        printDBG("EuroSportPlayer.listDays [%s]" % cItem)
        NOW = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)

        def _dataLabel(d):
            weekday = self.ABBREVIATED_DAYS_NAME_TAB[d.weekday()]
            text = ("%s %s %s" % (_(d.strftime('%A')), d.strftime('%d'), _(d.strftime('%B'))))
            return text.capitalize()

        try:
            sts, data = self.getPage(self.SCHEDULE_URL)
            if not sts:
                return

            data = json_loads(data)

            for item in data['included']:
                if item['type'] == 'collection':
                    if item['attributes']['name'] == 'schedule':
                        schedule_id = item['id']
                        for f in item['attributes']['component']['filters']:
                            for d in f['options']:
                                day_filter = d['parameter']
                                date = datetime.strptime(d['value'], "%Y-%m-%d")
                                title = _dataLabel(date)
                                if date == NOW:
                                    title = title + (" - [%s]" % _('Today')).upper()
                                params = dict(cItem)
                                params.update({'good_for_fav': False, 'category': nextCategory, 'title': title, 'filter': day_filter, 'schedule_id': schedule_id})
                                printDBG(str(params))
                                self.addDir(params)

        except Exception:
            printExc()

    def listSchedule(self, cItem):
        printDBG("EuroSportPlayer.listSchedule [%s]" % cItem)

        try:
            url = self.SCHEDULE_COLLECTION_URL.replace('{%id%}', cItem['schedule_id']).replace('{%filter%}', cItem['filter'])
            sts, data = self.getPage(url)
            if not sts:
                return

            data = json_loads(data)

            for item in data['included']:
                self.addItemInDB(item)

            for item in data['data']['relationships']['items']['data']:
                item_id = item['id']
                if item['type'] == 'collectionItem':
                    c = self.espCollectionItems[item_id]
                    #printDBG(json_dumps(c))
                    video_id = c['relationships']['video']['data']['id']
                    videoData = self.espVideos[video_id]
                    printDBG(json_dumps(videoData))
                    params = self.addVideoFromData(videoData, label_format='schedule', future=True)
                    if params:
                        self.addVideo(params)

        except Exception:
            printExc()

    def listSearchItems(self, cItem):
        printDBG("EuroSportPlayer.listSearchItems [%s]" % cItem)
        try:
            '''
            page = cItem.get('page', 1)
            variables = {"index":"eurosport_global","preferredLanguages":["pl","en"],"uiLang":"pl","mediaRights":["GeoMediaRight"],"page":page,"pageSize":20,"q":cItem['f_query'],"type":["Video","Airing","EventPage"],"include_images":True}
            url = self.serverApiData['server_path']['search'] + '/persisted/query/core/sitesearch?variables=' + urllib_quote(json_dumps(variables, separators=(',', ':')))

            sts, data = self.getJSPage(url)
            if not sts: return

            data = json_loads(data)['data']['sitesearch']
            NOW = datetime.now()
            for item in data['hits']:
                self._addItem(cItem, item['hit'], NOW)

            if page*20 < data['meta']['hits']:
                params = dict(cItem)
                params.pop('priv_item', None)
                params.update({'good_for_fav':False, 'title':_('Next page'), 'page':page+1})
                self.addDir(params)
            '''
        except Exception:
            printExc()

    def checkLogin(self):
        printDBG('EuroSportPlayer.checkLogin start')

        # try to open account informations
        sts, data = self.getPage(self.USER_URL)
        if sts:
            data = json_loads(data)
            if data['data']['attributes']['anonymous']:
                printDBG("------------------------EUROSPORT------------------------------------")
                printDBG("connected as anonymous: login needed")
                printDBG("---------------------------------------------------------------------")
                self.tryTologin()
            else:
                printDBG("------------------------EUROSPORT------------------------------------")
                printDBG("Ok, connected as username: %s " % data['data']['attributes']['username'])
                printDBG("Last Login %s" % data['data']['attributes']['lastLoginTime'])
                printDBG("---------------------------------------------------------------------")

                if config.plugins.iptvplayer.eurosportplayer_login.value != data['data']['attributes']['username']:
                    GetIPTVNotify().push(_("Username in settings is different from %s" % data['data']['attributes']['username']) + "\n" + _("Login needed"), 'error', 10)
                    self.tryTologin()
        else:
            self.tryTologin()

    def tryTologin(self):
        printDBG('EuroSportPlayer.tryTologin start')
        errorMsg = _('Error communicating with the server.')

        if None == self.loggedIn or self.login != config.plugins.iptvplayer.eurosportplayer_login.value or\
            self.password != config.plugins.iptvplayer.eurosportplayer_password.value:

            self.login = config.plugins.iptvplayer.eurosportplayer_login.value
            self.password = config.plugins.iptvplayer.eurosportplayer_password.value

            rm(self.COOKIE_FILE)

            self.loggedIn = False
            self.loginMessage = ''

            if '' == self.login.strip() or '' == self.password.strip():
                msg = _('The host %s requires subscription.\nPlease fill your login and password in the host configuration - available under blue button.') % self.getMainUrl()
                GetIPTVNotify().push(msg, 'info', 10)
                return False

            try:
                # get token
                tokenUrl = self.TOKEN_URL

                sts, data = self.getPage(tokenUrl)
                printDBG(data)

                # get config (also with catpcha site-key)
                sts, data = self.getPage(self.CONFIG_URL)
                printDBG(data)

                # solve captcha to login
                (token, errorMsgTab) = CaptchaHelper().processCaptcha(self.recaptcha_sitekey, self.LOGIN_URL)

                if not token:
                    printDBG(str(errorMsgTab))
                    return

                printDBG('Captcha token :%s' % token)

                # try to login
                header = {'User-Agent': self.USER_AGENT,
                          'Referer': self.LOGIN_URL,
                          'x-disco-client': 'WEB:x86_64:WEB_AUTH:1.1.0',
                          'x-disco-recaptcha-token': token,
                          'content-type': 'application/json'
                         }

                postData = {'credentials': {'username': self.login, 'password': self.password}}
                url = "https://eu3-prod-direct.eurosportplayer.com/login"

                httpParams = {'header': header, 'with_metadata': True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE, 'raw_post_data': True}

                sts, data = self.getPage(url, httpParams, post_data=json_dumps(postData))

                ''' good login
                {
                  "data" : {
                    "attributes" : {
                      "lastLoginTime" : "2019-11-01T21:45:15Z",
                      "realm" : "eurosport",
                      "token" : "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJVU0VSSUQ6ZXVyb3Nwb3J0OmI4OGQ0YTBhLWQwZDctNDdkZi1iMzI5LWJjNmM5ZDNiOTRjYyIsImp0aSI6InRva2VuLThkOWYxMDgwLWUwNGEtNDMyZi04NDY1LWUwYTgyNDljMjEwMyIsImFub255bW91cyI6ZmFsc2UsImlhdCI6MTU3MjY4NDk3MX0.DtSAY9kAVfwcJKhPXczRlPW3CACd6ZmZwZvJilIrlv8"
                    },
                    "id" : "token-8d9f1080-e04a-432f-8465-e0a8249c2103",
                    "type" : "token"
                  },
                  "meta" : {
                    "site" : {
                      "attributes" : {
                        "brand" : "eurosport",
                        "websiteHostName" : "it.eurosportplayer.com"
                      },
                      "id" : "IT",
                      "type" : "site"
                    }
                  }
                }
                '''

                ''' example: wrong password
                {
                  "errors" : [ {
                    "status" : "401",
                    "code" : "unauthorized",
                    "id" : "ATwRg09NZG",
                    "detail" : ""
                  } ]
                }
                '''

                if not sts and '401' in str(data):
                    msg = _('Login failed. Invalid email or password.')
                    GetIPTVNotify().push(msg, 'error', 10)
                    return False
                else:
                    data = json_loads(data)
                    printDBG(str(data))
                    self.loggedIn = True

            except Exception:
                printExc()

            printDBG('EuroSportPlayer.tryTologin end loggedIn[%s]' % self.loggedIn)
            return self.loggedIn

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("EuroSportPlayer.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))

        params = dict(cItem)
        params.update({'category': 'list_search_items', 'f_query': searchPattern})
        self.listSearchItems(params)

    def getLinksForVideo(self, cItem):
        printDBG("EuroSportPlayer.getLinksForVideo [%s]" % cItem)
        self.checkLogin()

        linksTab = []
        try:
            printDBG(str(cItem))
            video_id = cItem['video_id']
            # open video page
            video_page_url = cItem['url']
            sts, data = self.getPage(video_page_url, {'header': {'User-Agent': self.USER_AGENT, 'Referer': video_page_url}, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE})

            if not sts:
                return []

            # open route json page
            route_id = cItem.get('route_id', '')
            if route_id:
                route = self.espRoutes[route_id]
                printDBG(json_dumps(route))

                #{"attributes": {"url": "/videos/eurosport/world-championship-239400", "canonical": true}, "type": "route", "id": "292e72a63ebcccb480984a84f3497b7702623ab6fe6e7d7d29b1dce79ed3da35"}
                route_url = self.getFullPath(route['attributes']['url'], 'route') + "?include=default"

                sts, data = self.getPage(route_url)

                #if sts:
                    #printDBG('--------------------------------')
                    #printDBG(data)

            # open video playback json page
            playback_info_url = self.PLAYBACK_URL.replace('{%video_id%}', video_id)

            sts, data = self.getPage(playback_info_url, {'header': {'User-Agent': self.USER_AGENT, 'Referer': video_page_url}, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE})

            if not sts:
                return []

            printDBG('--------------------------------')
            printDBG(data)

            j = json_loads(data)

            s = j['data']['attributes']['streaming']

            if 'hls' in s:
                link_url = strwithmeta(s['hls']['url'], {'User-Agent': self.USER_AGENT, 'Referer': video_page_url})
                linksTab.append({'name': 'auto hls', 'url': link_url})
                linksTab.extend(getDirectM3U8Playlist(link_url, checkExt=False, variantCheck=True, checkContent=True, sortWithMaxBitrate=99999999))
            #if 'dash' in s:
            #    link_url = strwithmeta(s['dash']['url'], {'User-Agent': self.USER_AGENT, 'Referer' : video_page_url})
            #    linksTab.append({'name':'dash', 'url': link_url})
            #if 'mss' in s:
            #    link_url = strwithmeta(s['dash']['url'], {'User-Agent': self.USER_AGENT, 'Referer' : video_page_url})
            #    linksTab.append({'name':'mss', 'url': link_url})

        except Exception:
            printExc()

        return linksTab

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')
        self.checkLogin()

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: |||| name[%s], category[%s] " % (name, category))
        self.cacheLinks = {}
        self.currList = []

        #MAIN MENU
        if name == None:
            self.listMainMenu({'name': 'category'})

        # ON AIR
        elif category == 'on_air':
            self.listOnAir(self.currItem)

        # SCHEDULE
        elif category == 'schedule':
            self.listDays(self.currItem, 'list_schedule')
        elif category == 'list_schedule':
            self.listSchedule(self.currItem)

        # VOD
        elif category == 'vod_sport_filters':
            self.listSportFilters(self.currItem, 'list_vod_items')
        elif category == 'list_vod_items':
            self.listVodItems(self.currItem)

        #SEARCH
        elif category == 'list_search_items':
            self.listSearchItems(self.currItem)
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
        CHostBase.__init__(self, EuroSportPlayer(), True, [])
