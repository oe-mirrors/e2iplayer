# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem, RetHost, CUrlItem
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
###################################################

###################################################
# FOREIGN import
###################################################
import urllib
from hashlib import md5
try:
    import json
except Exception:
    import simplejson as json
from Components.config import config, ConfigText, getConfigListEntry
###################################################


###################################################
# E2 GUI COMMPONENTS
###################################################
from Screens.MessageBox import MessageBox
###################################################

###################################################
# Config options for HOST
###################################################

config.plugins.iptvplayer.kreskowkazone_login = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.kreskowkazone_password = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry("Login:", config.plugins.iptvplayer.kreskowkazone_login))
    optionList.append(getConfigListEntry("Hasło:", config.plugins.iptvplayer.kreskowkazone_password))
    return optionList
###################################################


def gettytul():
    return 'http://kreskowkazone.pl/'


class KreskowkaZonePL(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'KreskowkaZonePL.tv', 'cookie': 'kreskowkazoneonline.cookie'})
        self.HEADER = {'User-Agent': 'Mozilla/5.0', 'Accept': 'text/html'}
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})

        self.MAIN_URL = 'http://www.kreskowkazone.pl/'
        self.DEFAULT_ICON_URL = self.MAIN_URL + 'images/sprites.png'

        self.MAIN_TAB = [{'category': 'main', 'title': 'Główna', 'url': self.MAIN_URL, 'icon': self.DEFAULT_ICON_URL},
                         {'category': 'cartoons', 'title': 'Kreskówki', 'url': self.MAIN_URL, 'icon': self.DEFAULT_ICON_URL},
                         {'category': 'list_items', 'title': 'Seriale', 'url': self.MAIN_URL + 'seriale', 'icon': self.DEFAULT_ICON_URL},
                         {'category': 'rank', 'title': 'Ranking', 'url': self.MAIN_URL + 'ranking_anime', 'icon': self.DEFAULT_ICON_URL},
                         {'category': 'search', 'title': _('Search'), 'search_item': True, 'icon': self.DEFAULT_ICON_URL},
                         {'category': 'search_history', 'title': _('Search history'), 'icon': self.DEFAULT_ICON_URL}]

        self.CARTOONS_CAT_TAB = [{'category': 'list_abc', 'title': 'Lista kreskówek', 'url': self.MAIN_URL + 'lista_kreskowek-0'},
                                 {'category': 'list_abc', 'title': 'Lista filmów', 'url': self.MAIN_URL + 'lista_filmow-0'},
                                 {'category': 'list_items', 'title': 'Wychodzące kreskówki', 'url': self.MAIN_URL + 'wychodzace'},
                                 {'category': 'list_items', 'title': 'Wychodzące seriale', 'url': self.MAIN_URL + 'wychodzace-seriale'},
                                 {'category': 'list_items', 'title': 'Nadchodzące', 'url': self.MAIN_URL + 'nadchodzace'}]

        self.MAIN_CAT_TAB = [{'category': 'list_items', 'title': 'Najnowsze seriale', 'url': self.MAIN_URL},
                             {'category': 'list_items', 'm1': 'Najnowsze serie', 'title': 'Lista filmów', 'url': self.MAIN_URL}]

        self.login = ''
        self.password = ''
        self.cacheLinks = {}
        self.rankCache = {}

    def getFullUrl(self, url):
        if url.startswith('../'):
            url = url[3:]
        return CBaseHostClass.getFullUrl(self, url)

    def listRankCategories(self, cItem, nextCategory):
        printDBG("KreskowkaZonePL.listRank")

        sts, data = self.cm.getPage(cItem['url'], self.defaultParams)
        if not sts:
            return

        self.rankCache = {}
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="naglowek naglowek-click">', '</table>', withMarkers=True)
        for rankData in data:
            rankTile = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(rankData, '<h2>', '</h2>')[1])
            rankItems = []
            items = self.cm.ph.getAllItemsBeetwenMarkers(rankData, '<tr class="wiersz">', '</tr>', withMarkers=True)
            for item in items:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
                title = self.cleanHtmlStr(item)
                rankItems.append({'title': title, 'url': url})

            if len(rankItems):
                self.rankCache[rankTile] = rankItems
                params = dict(cItem)
                params.update({'good_for_fav': False, 'category': nextCategory, 'title': rankTile})
                self.addDir(params)

    def listRankItems(self, cItem, nextCategory):
        printDBG("KreskowkaZonePL.listRankItems")
        params = dict(cItem)
        params.update({'good_for_fav': True, 'category': nextCategory})
        self.listsTab(self.rankCache.get(cItem['title'], []), params)

    def listABC(self, cItem, nextCategory):
        printDBG("KreskowkaZonePL.listABC")

        sts, data = self.cm.getPage(cItem['url'], self.defaultParams)
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="litery-conteiner">', '</ul>')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li ', '</li>', withMarkers=True)
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'good_for_fav': False, 'category': nextCategory, 'title': title, 'url': url})
            self.addDir(params)

    def listItems(self, cItem, nextCategory):
        printDBG("KreskowkaZonePL.listItems")

        m1 = cItem.get('m1', '<div class="box">')
        cItem = dict(cItem)
        cItem.pop('m1', None)

        sts, data = self.cm.getPage(cItem['url'], self.defaultParams)
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenMarkers(data, m1, '</ul>')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="box">', '</li>', withMarkers=True)
        for item in data:
            tmp = self.cm.ph.getDataBeetwenMarkers(item, '<div class="box-title">', '</div>')[1]
            url = self.getFullUrl(self.cm.ph.getSearchGroups(tmp, '''href=['"]([^'^"]+?)['"]''')[0])
            if not self.cm.isValidUrl(url):
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            icon = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(tmp)
            if title == '':
                title = self.cm.ph.getSearchGroups(item, '''title=['"]([^'^"]+?)['"]''')[0]
            if title == '':
                title = self.cm.ph.getSearchGroups(item, '''alt=['"]([^'^"]+?)['"]''')[0]

            newUrl = self.cm.ph.getSearchGroups(url, '''(.+?)_[0-9]+$''')[0]
            if newUrl != '':
                url = newUrl

            desc = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'icon': icon, 'desc': desc})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("KreskowkaZonePL.listThreads")

        sts, data = self.cm.getPage(cItem['url'], self.defaultParams)
        if not sts:
            return

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<tr class="wiersz">', '</tr>', withMarkers=True)
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(item, '<td ', '</td>', withMarkers=True)
            title = self.cleanHtmlStr(' '.join(tmp[:-1]))
            params = dict(cItem)
            params.update({'good_for_fav': True, 'title': cItem['title'] + ': ' + title, 'url': url})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("KreskowkaZonePL.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))

        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('szukaj?szukana=') + urllib.quote_plus(searchPattern)
        self.listItems(cItem, 'list_episodes')

    def getLinksForVideo(self, cItem):
        printDBG("KreskowkaZonePL.getLinksForVideo [%s]" % cItem)
        urlTab = []

        if cItem['url'] in self.cacheLinks:
            return self.cacheLinks[cItem['url']]

        sts, data = self.cm.getPage(cItem['url'], self.defaultParams)
        if not sts:
            return []

        varName = self.cm.ph.getSearchGroups(data, '''var\s*__gaq\s*=\s*['"]([^'^"]+?)['"]''')[0]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<tr class="wiersz">', '</tr>', withMarkers=True)
        for item in data:
            url = self.cm.ph.getSearchGroups(item, '''%s=['"]([^'^"]+?)['"]''' % varName)[0]
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(item, '<td ', '</td>', withMarkers=True)
            title = self.cleanHtmlStr(' '.join(tmp))
            url = strwithmeta(url, {'origin_url': cItem['url']})
            urlTab.append({'name': title, 'url': url, 'need_resolve': 1})

        self.cacheLinks[cItem['url']] = urlTab
        return urlTab

    def getVideoLinks(self, videoUrl):
        printDBG("KreskowkaZonePL.getVideoLinks [%s]" % videoUrl)
        urlTab = []

        originUrl = strwithmeta(videoUrl).meta.get('origin_url', '')
        # mark requested link as used one
        if originUrl in self.cacheLinks:
            for idx in range(len(self.cacheLinks[originUrl])):
                if videoUrl in self.cacheLinks[originUrl][idx]['url']:
                    if not self.cacheLinks[originUrl][idx]['name'].startswith('*'):
                        self.cacheLinks[originUrl][idx]['name'] = '*' + self.cacheLinks[originUrl][idx]['name']
                    break

        if not self.cm.isValidUrl(videoUrl):
            for retry in [True, False]:
                url = self.getFullUrl('odcinki_ajax')
                params = dict(self.defaultParams)
                params['header'] = dict(self.AJAX_HEADER)
                params['header']['Referer'] = originUrl
                sts, data = self.cm.getPage(url, params, {'o': str(videoUrl)})
                if not sts:
                    return []
                printDBG('+++++++++++++++++++++++++++++++++++++++++++++++')
                printDBG(data)
                printDBG('+++++++++++++++++++++++++++++++++++++++++++++++')
                tmp = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0])
                if tmp == '':
                    tmp = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<embed[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0])
                if tmp == '':
                    tmp = self.cm.ph.getSearchGroups(data, '''<a[^>]+?href="([^>\s]+?)"[>\s]''')[0]
                if tmp == '':
                    tmp = self.cleanHtmlStr(data)
                if not self.cm.isValidUrl(tmp) and 1 <> self.up.checkHostSupport(tmp) and retry:
                    sts, tmp = self.cm.getPage(self.getFullUrl('images/statystyki.gif'), self.defaultParams)
                else:
                    videoUrl = tmp
                    break
        videoUrl = videoUrl.replace('&amp;', '&')
        if self.cm.isValidUrl(videoUrl):
            return self.up.getVideoLinkExt(videoUrl)

        return urlTab

    def getFavouriteData(self, cItem):
        printDBG('KreskowkaZonePL.getFavouriteData')
        return json.dumps(cItem)

    def getLinksForFavourite(self, fav_data):
        printDBG('KreskowkaZonePL.getLinksForFavourite')
        links = []
        try:
            cItem = byteify(json.loads(fav_data))
            links = self.getLinksForVideo(cItem)
        except Exception:
            printExc()
        return links

    def setInitListFromFavouriteItem(self, fav_data):
        printDBG('KreskowkaZonePL.setInitListFromFavouriteItem')
        try:
            params = byteify(json.loads(fav_data))
        except Exception:
            params = {}
            printExc()
        self.addDir(params)
        return True

    def tryTologin(self, login, password):
        printDBG('tryTologin start')
        connFailed = _('Connection to server failed!')

        rm(self.COOKIE_FILE)
        sts, data = self.cm.getPage(self.MAIN_URL, self.defaultParams)
        if not sts:
            return False, connFailed

        md5Password = md5(password).hexdigest()
        post_data = {"vb_login_username": login, "vb_login_password_hint": "Hasło", "vb_login_password": "", "do": "login", "s": "", "securitytoken": "guest", "cookieuser": "1", "vb_login_md5password": md5Password, "vb_login_md5password_utf8": md5Password}
        params = dict(self.defaultParams)
        params.update({'header': self.AJAX_HEADER}) #, 'raw_post_data':True

        # login
        sts, data = self.cm.getPage(self.getFullUrl('login.php?s=&do=login'), params, post_data)
        if not sts:
            return False, connFailed

        # check if logged
        sts, data = self.cm.getPage(self.MAIN_URL, self.defaultParams)
        if not sts:
            return False, connFailed

        if 'do=logout' in data:
            return True, 'OK'
        else:
            return False, 'NOT OK'

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        if self.login != config.plugins.iptvplayer.kreskowkazone_login.value and \
           self.password != config.plugins.iptvplayer.kreskowkazone_password.value and \
           '' != config.plugins.iptvplayer.kreskowkazone_login.value.strip() and \
           '' != config.plugins.iptvplayer.kreskowkazone_password.value.strip():
            loggedIn, msg = self.tryTologin(config.plugins.iptvplayer.kreskowkazone_login.value, config.plugins.iptvplayer.kreskowkazone_password.value)
            if not loggedIn:
                self.sessionEx.open(MessageBox, 'Problem z zalogowaniem użytkownika "%s".' % config.plugins.iptvplayer.kreskowkazone_login.value, type=MessageBox.TYPE_INFO, timeout=10)
            else:
                self.login = config.plugins.iptvplayer.kreskowkazone_login.value
                self.password = config.plugins.iptvplayer.kreskowkazone_password.value
                #self.sessionEx.open(MessageBox, 'Zostałeś poprawnie \nzalogowany.\n' + msg, type = MessageBox.TYPE_INFO, timeout = 10 )

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            if self.login == '' or self.password == '':
                rm(self.COOKIE_FILE)
            self.listsTab(self.MAIN_TAB, {'name': 'category'})
        elif 'main' == category:
            self.listsTab(self.MAIN_CAT_TAB, self.currItem)
        elif 'cartoons' == category:
            self.listsTab(self.CARTOONS_CAT_TAB, self.currItem)
        elif 'rank' == category:
            self.listRankCategories(self.currItem, 'list_rank_items')
        elif 'list_rank_items' == category:
            self.listRankItems(self.currItem, 'list_episodes')
        elif 'list_abc' == category:
            self.listABC(self.currItem, 'list_items')
        elif 'list_items' == category:
            self.listItems(self.currItem, 'list_episodes')
        elif category == 'list_episodes':
            self.listEpisodes(self.currItem)
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
        CHostBase.__init__(self, KreskowkaZonePL(), True, []) #[CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO]

    def getLinksForVideo(self, Index=0, selItem=None):
        retCode = RetHost.ERROR
        retlist = []
        if not self.isValidIndex(Index):
            return RetHost(retCode, value=retlist)

        urlList = self.host.getLinksForVideo(self.host.currList[Index])
        for item in urlList:
            retlist.append(CUrlItem(item["name"], item["url"], item.get('need_resolve', False)))

        return RetHost(RetHost.OK, value=retlist)
    # end getLinksForVideo

    def getResolvedURL(self, url):
        # resolve url to get direct url to video file
        retlist = []
        urlList = self.host.getVideoLinks(url)
        for item in urlList:
            need_resolve = 0
            retlist.append(CUrlItem(item["name"], item["url"], need_resolve))

        return RetHost(RetHost.OK, value=retlist)

    def converItem(self, cItem):
        hostList = []
        searchTypesOptions = [] # ustawione alfabetycznie
        #searchTypesOptions.append((_("Movies"),   "movie"))
        #searchTypesOptions.append((_("TV Shows"), "series"))

        hostLinks = []
        type = CDisplayListItem.TYPE_UNKNOWN
        possibleTypesOfSearch = None

        if 'category' == cItem['type']:
            if cItem.get('search_item', False):
                type = CDisplayListItem.TYPE_SEARCH
                possibleTypesOfSearch = searchTypesOptions
            else:
                type = CDisplayListItem.TYPE_CATEGORY
        elif cItem['type'] == 'video':
            type = CDisplayListItem.TYPE_VIDEO
        elif 'more' == cItem['type']:
            type = CDisplayListItem.TYPE_MORE
        elif 'audio' == cItem['type']:
            type = CDisplayListItem.TYPE_AUDIO

        if type in [CDisplayListItem.TYPE_AUDIO, CDisplayListItem.TYPE_VIDEO]:
            url = cItem.get('url', '')
            if '' != url:
                hostLinks.append(CUrlItem("Link", url, 1))

        title = cItem.get('title', '')
        description = cItem.get('desc', '')
        icon = cItem.get('icon', '')
        if icon == '':
            icon = self.host.DEFAULT_ICON_URL
        isGoodForFavourites = cItem.get('good_for_fav', False)

        return CDisplayListItem(name=title,
                                    description=description,
                                    type=type,
                                    urlItems=hostLinks,
                                    urlSeparateRequest=1,
                                    iconimage=icon,
                                    possibleTypesOfSearch=possibleTypesOfSearch,
                                    isGoodForFavourites=isGoodForFavourites)
    # end converItem
