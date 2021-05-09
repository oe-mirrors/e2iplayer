# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify, rm, MergeDicts
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
###################################################

###################################################
# FOREIGN import
###################################################
import urllib
import base64
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
config.plugins.iptvplayer.vumedicom_login = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.vumedicom_password = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("login") + ":", config.plugins.iptvplayer.vumedicom_login))
    optionList.append(getConfigListEntry(_("password") + ":", config.plugins.iptvplayer.vumedicom_password))
    return optionList
###################################################


def gettytul():
    return 'https://vumedi.com/'


class VUMEDI(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'vumedi.com', 'cookie': 'vumedi.comcookie'})

        self.USER_AGENT = 'Mozilla/5.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'})

        self.MAIN_URL = 'https://www.vumedi.com/'
        self.DEFAULT_ICON_URL = 'https://pbs.twimg.com/media/DZTZrVhW4AAekGB.jpg'

        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.loggedIn = None
        self.login = ''
        self.password = ''

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def getFullUrl(self, url, baseUrl=None):
        if not self.cm.isValidUrl(url) and baseUrl != None:
            if url.startswith('/'):
                baseUrl = self.cm.getBaseUrl(baseUrl)
            else:
                baseUrl = baseUrl.rsplit('/', 1)[0] + '/'
        return CBaseHostClass.getFullUrl(self, url.replace('&#038;', '&').replace('&amp;', '&'), baseUrl)

    def listMainMenu(self, cItem):
        printDBG("VUMEDI.listMainMenu")

        MAIN_CAT_TAB = [{'category': 'list_spec', 'title': _('Specialities'), 'url': self.getMainUrl()},
                        {'category': 'list_sort', 'title': _('Browse videos'), 'url': self.getFullUrl('/video/browse/')},
                        {'category': 'search', 'title': _('Search'), 'search_item': True},
                        {'category': 'search_history', 'title': _('Search history')}]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listCategories(self, cItem, nextCategory1, nextCategory2):
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        cUrl = self.cm.meta['url']
        self.setMainUrl(cUrl)

        if 'news-feeds' in data:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'name': 'category', 'category': nextCategory1, 'url': cUrl, 'title': _('News Feed')})
            self.addDir(params)

        data = self.cm.ph.getDataBeetwenNodes(data, ('<nav', '>', 'secondary-nav'), ('</nav', '>'), False)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
        for sItem in data:
            sItem = sItem.split('</a>', 1)
            if len(sItem) < 2:
                continue
            sTitle = self.cleanHtmlStr(sItem[0])
            sUrl = self.getFullUrl(self.cm.ph.getSearchGroups(sItem[0], '''href=['"]([^"^']+?)['"]''')[0].split('#', 1)[0], cUrl)
            categories = []
            sItem = self.cm.ph.getAllItemsBeetwenMarkers(sItem[1], '<a', '</a>')
            for item in sItem:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0], cUrl)
                title = self.cleanHtmlStr(item)
                params = dict(cItem)
                params.update({'good_for_fav': True, 'name': 'category', 'category': nextCategory2, 'title': title, 'url': url})
                categories.append(params)

            if len(categories):
                if sUrl != '':
                    params = dict(cItem)
                    params.update({'good_for_fav': True, 'name': 'category', 'category': nextCategory2, 'title': _('--All--'), 'url': sUrl})
                    categories.insert(0, params)
                params = dict(cItem)
                params.update({'name': 'category', 'category': 'sub_items', 'title': sTitle, 'sub_items': categories})
                self.addDir(params)
            elif sUrl != '':
                params = dict(cItem)
                params.update({'good_for_fav': True, 'name': 'category', 'category': nextCategory2, 'title': sTitle, 'url': sUrl})
                self.addDir(params)

    def listTopics(self, cItem, nextCategory):
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        cUrl = self.cm.meta['url']
        self.setMainUrl(cUrl)

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<h2', '>', 'filters'), ('</div', '>'))
        for sItem in data:
            sItem = sItem.split('</h2>', 1)
            if len(sItem) < 2:
                continue
            sTitle = self.cleanHtmlStr(sItem[0])
            if sTitle.endswith(':'):
                sTitle = sTitle[:-1]
            categories = []
            sItem = self.cm.ph.getAllItemsBeetwenMarkers(sItem[1], '<a', '</a>')
            for item in sItem:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0], cUrl)
                title = self.cleanHtmlStr(item)
                params = dict(cItem)
                params.update({'good_for_fav': True, 'name': 'category', 'category': nextCategory, 'title': title, 'url': url})
                categories.append(params)

            if len(categories):
                params = dict(cItem)
                params.update({'name': 'category', 'category': 'sub_items', 'title': sTitle, 'sub_items': categories})
                self.addDir(params)

        params = dict(cItem)
        params.update({'good_for_fav': True, 'name': 'category', 'category': nextCategory, 'url': cUrl, 'title': _('--All--')})
        if len(self.currList):
            self.currList.insert(0, params)
        else:
            self.listSort(params, 'list_items')

    def listSpecialities(self, cItem, nextCategory):
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        cUrl = self.cm.meta['url']
        self.setMainUrl(cUrl)

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'navbarSpecDropdown'), ('</div', '>'), False)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0], cUrl)
            title = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'good_for_fav': True, 'name': 'category', 'category': nextCategory, 'title': title, 'url': url})
            self.addDir(params)

    def listSort(self, cItem, nextCategory):
        printDBG("VUMEDI.listItems [%s]" % cItem)

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        cUrl = self.cm.meta['url']
        self.setMainUrl(cUrl)

        data = self.cm.ph.getDataBeetwenNodes(data, ('<', '>', 'sort-dropdown"'), ('</div', '>'), False)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0], cUrl)
            if url == '':
                url = cUrl
            title = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'name': 'category', 'category': nextCategory, 'title': title, 'url': url})
            self.addDir(params)

    def listNewsFeed(self, cItem):
        printDBG("VUMEDI.listNewsFeed [%s]" % cItem)
        page = cItem.get('page', 0)
        url = self.getFullUrl('/beats/{0}/?is_long=true'.format(page))

        params = dict(self.defaultParams)
        params['header'] = MergeDicts(self.AJAX_HEADER, {'Referer': cItem['url']})

        sts, data = self.getPage(url, params)
        if not sts:
            return
        try:
            data = byteify(json.loads(data))
            nextPage = data.get('start', -1)
            data = data['beats']

            self.listVideoItems(cItem, data)

            if nextPage > page:
                params = dict(cItem)
                params.update({'good_for_fav': False, 'title': _("Next page"), 'page': nextPage})
                self.addDir(params)

        except Exception:
            printExc()

    def listVideoItems(self, cItem, data):

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'video-item'), ('</ul', '>'), False)
        for item in data:
            t = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<', '>', 'video-duration'), ('</', '>'), False)[1]).upper()
            if ':' not in t and 'VIDEO' not in t:
                continue
            tmp = self.cm.ph.getDataBeetwenNodes(item, ('<h', '>', '_title'), ('</h', '>'), False)[1]

            url = self.getFullUrl(self.cm.ph.getSearchGroups(tmp, '''\shref=['"]([^'^"]+?)['"]''')[0].strip())
            if url == '':
                continue

            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''\ssrc=['"]([^"^']+?\.(?:jpe?g|png)(?:\?[^'^"]*?)?)['"]''')[0])
            title = self.cleanHtmlStr(tmp)

            desc = [t]
            tmp = []
            for marker in ['_author', '_desc']:
                t = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<', '>', marker), ('</', '>'), False)[1])
                if t == '':
                    continue
                tmp.append(t)
            desc.append(' | '.join(tmp))

            tmp = []
            for t in self.cm.ph.getAllItemsBeetwenMarkers(item, '<li', '</li>'):
                t = self.cleanHtmlStr(t)
                if t == '':
                    continue
                tmp.append(t)
            desc.append(' | '.join(tmp))

            params = dict(cItem)
            params.update({'good_for_fav': True, 'title': title, 'url': url, 'icon': icon, 'desc': '[/br]'.join(desc)})
            self.addVideo(params)

    def listItems(self, cItem):
        printDBG("VUMEDI.listItems [%s]" % cItem)
        page = cItem.get('page', 1)

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        cUrl = self.cm.meta['url']
        self.setMainUrl(cUrl)

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'pagination'), ('</ul', '>'))[1]
        nextPage = self.cm.ph.getSearchGroups(nextPage, '''<a[^>]+?href=['"]([^'^"]+?)['"][^>]*?>%s</a>''' % (page + 1))[0]

        self.listVideoItems(cItem, data)

        if nextPage:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _("Next page"), 'page': page + 1, 'url': self.getFullUrl(nextPage, cUrl)})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("VUMEDI.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        self.tryTologin()

        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('/search/?q=') + urllib.quote(searchPattern)
        cItem['category'] = 'list_items'
        self.listItems(cItem)

    def getLinksForVideo(self, cItem):
        printDBG("VUMEDI.getLinksForVideo [%s]" % cItem)
        self.tryTologin()

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return []
        self.setMainUrl(self.cm.meta['url'])

        playerBase = 'http://player.ooyala.com/'
        # first check simple method
        baseUrl = playerBase + 'hls/player/all/%s.m3u8'
        videoId = self.cm.ph.getSearchGroups(data, '''data\-video=['"]([^'^"]+?)['"]''')[0]
        retTab = getDirectM3U8Playlist(baseUrl % videoId, checkExt=False, checkContent=True, sortWithMaxBitrate=999999999)
        if 0 == len(retTab):
            data = self.cm.ph.getDataBeetwenNodes(data, ('var ', '{', 'playerParam'), ('}', ';'))[1]
            partnerId = self.cm.ph.getSearchGroups(data, '''['"]?playerBrandingId['"]?\s*\:\s*['"]([^'^"]+?)['"]''')[0]
            pcode = self.cm.ph.getSearchGroups(data, '''['"]?pcode['"]?\s*\:\s*['"]([^'^"]+?)['"]''')[0]

            url = playerBase + 'player_api/v1/content_tree/embed_code/%s/%s?' % (pcode, videoId)
            sts, data = self.getPage(url)
            if not sts:
                return []
            try:
                printDBG(data)
                data = byteify(json.loads(data))['content_tree']
                key = data.keys()[0]
                data = data[key]

                embedCode = data['embed_code']
                pcode = data.get('asset_pcode', embedCode)

                url = playerBase + 'sas/player_api/v2/authorization/embed_code/%s/%s?device=html5&domain=%s' % (pcode, embedCode, self.cm.getBaseUrl(self.getMainUrl(), True))
                sts, data = self.getPage(url)
                if not sts:
                    return []
                printDBG(data)
                data = byteify(json.loads(data))['authorization_data'][key]['streams']
                for item in data:
                    url = ''
                    if item['url']['format'] == 'encoded':
                        url = base64.b64decode(item['url']['data'])
                    if not self.cm.isValidUrl(url):
                        continue

                    if item['delivery_type'] == 'mp4':
                        name = 'mp4 %s %sx%s %sfps' % (item['video_codec'], item['width'], item['height'], item['framerate'])
                        retTab.append({'name': name, 'url': url, 'need_resolve': 0})
                    elif item['delivery_type'] == 'hls':
                        retTab.extend(getDirectM3U8Playlist(url, checkExt=False, checkContent=True, sortWithMaxBitrate=999999999))
            except Exception:
                printExc()
        return retTab

    def tryTologin(self):
        printDBG('tryTologin start')
        if None == self.loggedIn or self.login != config.plugins.iptvplayer.vumedicom_login.value or\
            self.password != config.plugins.iptvplayer.vumedicom_password.value:

            self.login = config.plugins.iptvplayer.vumedicom_login.value
            self.password = config.plugins.iptvplayer.vumedicom_password.value

            rm(self.COOKIE_FILE)

            self.loggedIn = False

            if '' == self.login.strip() or '' == self.password.strip():
                self.sessionEx.open(MessageBox, _('The host %s requires registration. \nPlease fill your login and password in the host configuration. Available under blue button.' % self.getMainUrl()), type=MessageBox.TYPE_ERROR, timeout=10)
                return False

            sts, data = self.getPage(self.getFullUrl('/accounts/login/'))
            if not sts:
                return False
            cUrl = self.cm.meta['url']
            self.setMainUrl(cUrl)

            sts, data = self.cm.ph.getDataBeetwenNodes(data, ('<form', '>'), ('</form', '>'))
            if not sts:
                return False
            actionUrl = self.cm.getFullUrl(self.cm.ph.getSearchGroups(data, '''action=['"]([^'^"]+?)['"]''')[0], self.cm.getBaseUrl(cUrl))
            if actionUrl == '':
                actionUrl = cUrl

            post_data = {}
            inputData = self.cm.ph.getAllItemsBeetwenMarkers(data, '<input', '>')
            inputData.extend(self.cm.ph.getAllItemsBeetwenMarkers(data, '<button', '>'))
            for item in inputData:
                name = self.cm.ph.getSearchGroups(item, '''name=['"]([^'^"]+?)['"]''')[0]
                value = self.cm.ph.getSearchGroups(item, '''value=['"]([^'^"]+?)['"]''')[0].replace('&amp;', '&')
                post_data[name] = value

            post_data.update({'username': self.login, 'password': self.password})

            httpParams = dict(self.defaultParams)
            httpParams['header'] = dict(httpParams['header'])
            httpParams['header']['Referer'] = cUrl

            sts, data = self.cm.getPage(actionUrl, httpParams, post_data)
            if sts and '/logout' in data:
                printDBG('tryTologin OK')
                self.loggedIn = True

            if not self.loggedIn:
                errorMessage = [_('Login failed.')]
                if sts:
                    errorMessage.append(self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'alert-warning'), ('<', '>'), False)[1]))
                self.sessionEx.open(MessageBox, '\n'.join(errorMessage), type=MessageBox.TYPE_ERROR, timeout=10)
                printDBG('tryTologin failed')
        return self.loggedIn

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        self.tryTologin()

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: || name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listMainMenu({'name': 'category', 'type': 'category'})
        elif category == 'list_spec':
            self.listSpecialities(self.currItem, 'list_cats')
        elif category == 'news_feed':
            self.listNewsFeed(self.currItem)
        elif category == 'list_cats':
            self.listCategories(self.currItem, 'news_feed', 'list_topics')
        elif category == 'list_topics':
            self.listTopics(self.currItem, 'list_sort')
        elif category == 'list_sort':
            self.listSort(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem)
        elif category == 'sub_items':
            self.currList = self.currItem.get('sub_items', [])
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
        CHostBase.__init__(self, VUMEDI(), True, favouriteTypes=[])
