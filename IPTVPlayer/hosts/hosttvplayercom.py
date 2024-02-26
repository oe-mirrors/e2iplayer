# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify, rm, CSelOneLink
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
###################################################
# FOREIGN import
###################################################
import re
try:
    import json
except Exception:
    import simplejson as json
from Components.config import config, ConfigSelection, ConfigYesNo, ConfigText, getConfigListEntry
###################################################


###################################################
# E2 GUI COMMPONENTS
###################################################
from Screens.MessageBox import MessageBox
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.tvplayercom_login = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.tvplayercom_password = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.tvplayercom_password = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.tvplayercom_drmbypass = ConfigYesNo(default=False)
config.plugins.iptvplayer.tvplayercom_preferredbitrate = ConfigSelection(default="99999999", choices=[("99999999", _("highest")),
                                                                                               ("2564000", "2564k"),
                                                                                               ("1864000", "1864k"),
                                                                                               ("1064000", "1064k"),
                                                                                               ("564000", "564k"),
                                                                                               ("214000", "214k"),
                                                                                               ("0", _("lowest"))])
config.plugins.iptvplayer.tvplayercom_usepreferredbitrate = ConfigYesNo(default=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Preferred bitrate") + ":", config.plugins.iptvplayer.tvplayercom_preferredbitrate))
    optionList.append(getConfigListEntry(_("Use preferred bitrate") + ":", config.plugins.iptvplayer.tvplayercom_usepreferredbitrate))
    optionList.append(getConfigListEntry(_("email") + ":", config.plugins.iptvplayer.tvplayercom_login))
    optionList.append(getConfigListEntry(_("password") + ":", config.plugins.iptvplayer.tvplayercom_password))
    optionList.append(getConfigListEntry(_("Try to bypass DRM (it may be illegal)") + ":", config.plugins.iptvplayer.tvplayercom_drmbypass))
    return optionList
###################################################


def gettytul():
    return 'https://tvplayer.com/'


class TVPlayer(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'tvplayer.com', 'cookie': 'tvplayer.com.cookie'})
        self.DEFAULT_ICON_URL = 'http://ww1.prweb.com/prfiles/2012/03/21/9313945/TVPlayer%20Logo%20New%20USE%20THIS%20ONE.jpg'
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept-Encoding': 'gzip, deflate', 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})
        self.MAIN_URL = 'https://tvplayer.com/'
        self.cacheChannelsFlags = {}
        self.cacheChannelsGenres = []
        self.loggedIn = None
        self.login = ''
        self.password = ''

        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE, 'ignore_http_code_ranges': [(404, 500)]}

        self.MAIN_CAT_TAB = [{'category': 'list_channels_genres', 'title': _('Channels'), 'url': self.getFullUrl('/channels')},

                             #{'category':'search',           'title': _('Search'), 'search_item':True,},
                             #{'category':'search_history',   'title': _('Search history'),            }
                            ]

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def fillChannelsFreeFlags(self):
        printDBG("TVPlayer.fillFreeFlags")
        if self.cacheChannelsFlags != {}:
            return

        sts, data = self.getPage(self.getFullUrl('/watch'))
        if not sts:
            return []

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<ul class="list-unstyled', '</ul>')
        for item in data:
            item = self.cm.ph.getAllItemsBeetwenMarkers(item, '<li', '</li>')
            for it in item:
                url = self.cm.ph.getSearchGroups(it, '''href=['"]([^'^"]+?)['"]''')[0]
                icon = self.cm.ph.getSearchGroups(it, '''src=['"]([^'^"]+?)['"]''')[0]
                id = url.split('/watch/')
                if len(id) != 2:
                    continue
                title = self.cm.ph.getSearchGroups(it, '''data-name=['"]([^'^"]+?)['"]''')[0]
                type = self.cm.ph.getSearchGroups(it, '''class=['"]online\s*([^'^"]+?)['"]''')[0].lower()
                self.cacheChannelsFlags[id[1]] = {'title': self.cleanHtmlStr(title), 'url': self.getFullUrl(url), 'icon': self.getFullIconUrl(icon), 'f_type': type}

    def listChannelsGenres(self, cItem, nextCategory):
        printDBG("TVPlayer.listChannelsGenres")

        if 0 == len(self.cacheChannelsGenres):
            sts, data = self.getPage(cItem['url'])
            if not sts:
                return
            data = self.cm.ph.getDataBeetwenMarkers(data, '<ul id="nav"', '</ul>')[1]
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
            for item in data:
                genre = self.cm.ph.getSearchGroups(item, '''data-genre=['"]([^'^"]+?)['"]''')[0].lower()
                if genre == '':
                    continue
                params = {'title': self.cleanHtmlStr(item), 'f_genre': genre}
                self.cacheChannelsGenres.append(params)

        cItem = dict(cItem)
        cItem['category'] = nextCategory
        self.listsTab(self.cacheChannelsGenres, cItem)

    def listTypeFilter(self, cItem, nextCategory):
        printDBG("TVPlayer.listTypeFilter")
        tab = [{'title': _('All'), 'f_type': ''}, {'title': _('Free'), 'f_type': 'free'}, {'title': _('Paid'), 'f_type': 'paid'}]
        cItem = dict(cItem)
        cItem['category'] = nextCategory
        self.listsTab(tab, cItem)

    def listChannels(self, cItem):
        printDBG("TVPlayer.listChannels cItem[%s]" % cItem)

        self.fillChannelsFreeFlags()

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="list ', '</ul>')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
        for item in data:
            genres = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<p', '>', 'genre hidden'), ('</p', '>'), False)[1]).lower()
            if cItem.get('f_genre', '') not in genres:
                continue
            url = self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0]

            id = url.split('/watch/')[-1]
            if id in self.cacheChannelsFlags:
                flagType = self.cacheChannelsFlags[id]['f_type']
            else:
                flagType = ''

            if cItem.get('f_type', '') not in flagType:
                continue

            url = self.getFullUrl(url)
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''data-name=['"]([^'^"]+?)['"]''')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0])

            params = dict(cItem)
            params.update({'good_for_fav': True, 'title': title, 'url': url, 'icon': icon, 'desc': flagType.title()})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("TVPlayer.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('/?s=' + urllib_quote_plus(searchPattern))
        self.listItems(cItem, 'explore_item')

    def getLinksForVideo(self, cItem):
        printDBG("TVPlayer.getLinksForVideo [%s]" % cItem)
        self.tryTologin()

        def _SetIPTVPlayerLastHostError(msg):
            if not cItem.get('next_try', False):
                SetIPTVPlayerLastHostError(msg)

        retTab = []

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return []

        checkUrl = self.cm.ph.getSearchGroups(data, '''<[^>]+?id="check"[^>]+?src=['"]([^'^"]+?)['"]''')[0]

        playerData = self.cm.ph.getSearchGroups(data, '''<div([^"^']+?class=['"]video-js[^>]+?)>''')[0]
        printDBG(playerData)

        playerData = dict(re.findall('''\sdata\-(\w+?)\s*=\s*['"]([^'^"]+?)['"]''', playerData))
        printDBG(playerData)

        if 'resource' not in playerData or 'token' not in playerData:
            msg = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div class="centered-content">', '</h', False)[1])
            _SetIPTVPlayerLastHostError(msg)
            return []

        url = self.getFullUrl('/watch/context?resource={0}&gen={1}'.format(playerData.get('resource'), playerData.get('token')))
        sts, data = self.getPage(url)
        if not sts:
            return []
        printDBG("response: [%s]" % data)

        try:
            data = byteify(json.loads(data))
            url = 'https://api.tvplayer.com/api/v2/stream/live'
            ''' id: e.resource,
                service: 1,
                platform: e.platform.key,
                validate: e.validate
            '''
            post_data = {'id': data['resource'], 'service': 1, 'platform': data['platform']['key'], 'validate': data['validate']}
            if 'token' in data:
                post_data['token'] = data['token']

            sts, data = self.getPage(url, {}, post_data)
            if not sts:
                try:
                    _SetIPTVPlayerLastHostError(str(data))
                except Exception:
                    pass
                return []
            printDBG("response: [%s]" % data)

            data = byteify(json.loads(data))['tvplayer']['response']
            if 'error' in data:
                _SetIPTVPlayerLastHostError(data['error'])
                if not config.plugins.iptvplayer.tvplayercom_drmbypass.value or cItem.get('next_try', False):
                    return []
                self.getLinksForVideo({'next_try': True, 'url': self.defUrl})
                streamUrl = 'https://live.tvplayer.com/stream.m3u8?id=%s' % post_data['id']
            else:
                if None != data.get('drmToken'):
                    _SetIPTVPlayerLastHostError(_('DRM protected streams are not supported.'))
                    if not config.plugins.iptvplayer.tvplayercom_drmbypass.value or cItem.get('next_try', False):
                        return []
                    self.getLinksForVideo({'next_try': True, 'url': self.defUrl})
                    streamUrl = 'https://live.tvplayer.com/stream.m3u8?id=%s' % post_data['id']
                else:
                    streamUrl = data.get('stream', '')
                    if not self.cm.isValidUrl(streamUrl):
                        _SetIPTVPlayerLastHostError(_('No playable sources found.'))
                        return []

            retTab = getDirectM3U8Playlist(streamUrl, checkExt=True, variantCheck=True, cookieParams=self.defaultParams, checkContent=True)
            if len(retTab):
                cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE)
                for idx in range(len(retTab)):
                    retTab[idx]['url'] = strwithmeta(retTab[idx]['url'], {'iptv_proto': 'm3u8', 'Cookie': cookieHeader, 'User-Agent': self.defaultParams['header']['User-Agent']})

                def __getLinkQuality(itemLink):
                    try:
                        return int(itemLink['bitrate'])
                    except Exception:
                        printExc()
                        return 0

                retTab = CSelOneLink(retTab, __getLinkQuality, int(int(config.plugins.iptvplayer.tvplayercom_preferredbitrate.value) * 1.2)).getSortedLinks()
                if len(retTab) and config.plugins.iptvplayer.tvplayercom_usepreferredbitrate.value:
                    retTab = [retTab[0]]
                printDBG(retTab)
            elif self.cm.isValidUrl(checkUrl):
                sts, data = self.getPage(checkUrl)
                if not sts:
                    _SetIPTVPlayerLastHostError(_("Sorry. TVPlayer is currently only available in the United Kingdom"))
        except Exception:
            printExc()

        return retTab

    def getArticleContent(self, cItem):
        printDBG("TVPlayer.getArticleContent [%s]" % cItem)
        self.tryTologin()

        retTab = []

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return retTab

        title = cItem['title']
        desc = ''
        icon = cItem.get('icon', self.DEFAULT_ICON_URL)

        descTab = []
        tmp = self.cm.ph.getDataBeetwenReMarkers(data, re.compile('''<div[^>]+?class=['"]collapse['"][^>]*?>'''), re.compile('''<div[^>]+?id=['"]dark-button['"]'''), False)[1]
        tmp = tmp.split('<div class="row">')
        if len(tmp):
            del tmp[0]
        for item in tmp:
            item = self.cm.ph.getAllItemsBeetwenMarkers(item, '<p', '</p>')
            tmpTab = []
            for t in item:
                t = self.cleanHtmlStr(t)
                if t != '':
                    tmpTab.append(t)
            if len(tmpTab):
                descTab.append(tmpTab)

        tmp = self.cm.ph.getDataBeetwenMarkers(data, 'segment">', '<div class="collapse"', False)[1]
        tmp = re.split('''<[^>]+?segment[^>]*?>''', tmp)

        if len(descTab) == len(tmp) > 0:
            for idx in range(len(tmp)):
                items = self.cm.ph.getAllItemsBeetwenMarkers(tmp[idx], '<div', '</div>')
                tmpTab = []
                for t in items:
                    if 'hidden' in t and 'timer' not in t:
                        continue
                    tt = t.split('<br>')
                    for t in tt:
                        t = self.cleanHtmlStr(t)
                        if t != '':
                            tmpTab.append(t)
                if len(tmpTab):
                    title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(tmp[idx], '<h2', '</h2>')[1])
                    tmpTab.insert(1, title)
                tmpTab.extend(descTab[idx])
                descTab[idx] = tmpTab

        for tab in descTab:
            desc += '[/br]'.join(tab)
            desc += '[/br][/br]'

        return [{'title': self.cleanHtmlStr(title), 'text': self.cleanHtmlStr(desc), 'images': [{'title': '', 'url': self.DEFAULT_ICON_URL}], 'other_info': {}}]

    def tryTologin(self):
        printDBG('tryTologin start')
        self.defUrl = self.getFullUrl('/watch/russiatoday')
        if None == self.loggedIn or self.login != config.plugins.iptvplayer.tvplayercom_login.value or\
            self.password != config.plugins.iptvplayer.tvplayercom_password.value:

            self.login = config.plugins.iptvplayer.tvplayercom_login.value
            self.password = config.plugins.iptvplayer.tvplayercom_password.value

            rm(self.COOKIE_FILE)

            self.loggedIn = False

            if '' == self.login.strip() or '' == self.password.strip():
                return False

            url = self.getFullUrl('/account/login')

            sts, data = self.getPage(url)
            if not sts:
                return False

            sts, data = self.cm.ph.getDataBeetwenNodes(data, ('<form', '>', 'login'), ('</form', '>'))
            if not sts:
                return False
            actionUrl = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''action=['"]([^'^"]+?)['"]''')[0])
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<input', '>')
            post_data = {}
            for item in data:
                name = self.cm.ph.getSearchGroups(item, '''name=['"]([^'^"]+?)['"]''')[0]
                value = self.cm.ph.getSearchGroups(item, '''value=['"]([^'^"]+?)['"]''')[0]
                post_data[name] = value

            post_data.update({'email': self.login, 'password': self.password, 'remember_me': 1})

            httpParams = dict(self.defaultParams)
            httpParams['header'] = dict(httpParams['header'])
            httpParams['header']['Content-Type'] = 'application/x-www-form-urlencoded'
            httpParams['header']['Referer'] = url
            sts, data = self.cm.getPage(actionUrl, httpParams, post_data)
            if sts and '/account/channels' in data:
                printDBG('tryTologin OK')
                self.loggedIn = True
            else:
                self.sessionEx.open(MessageBox, _('Login failed.'), type=MessageBox.TYPE_ERROR, timeout=10)
                printDBG('tryTologin failed')
        return self.loggedIn

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        self.tryTologin()

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            #self.listsTab(self.MAIN_CAT_TAB, {'name':'category'})
            cItem = dict(self.MAIN_CAT_TAB[0])
            cItem['name'] = 'category'
            self.listChannelsGenres(cItem, 'list_type')
        elif category == 'list_channels_genres':
            self.listChannelsGenres(self.currItem, 'list_type')
        elif category == 'list_type':
            self.listTypeFilter(self.currItem, 'list_channels')
        elif category == 'list_channels':
            self.listChannels(self.currItem)
    #SEARCH
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
        CHostBase.__init__(self, TVPlayer(), True, [])

    def withArticleContent(self, cItem):
        if cItem['type'] == 'video':
            return True
        return False
