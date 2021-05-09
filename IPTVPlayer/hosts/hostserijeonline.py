# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, GetIPTVNotify
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify, rm
###################################################

###################################################
# FOREIGN import
###################################################
import urlparse
import re
import urllib
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
config.plugins.iptvplayer.serijeonline_login = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.serijeonline_password = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("login") + ":", config.plugins.iptvplayer.serijeonline_login))
    optionList.append(getConfigListEntry(_("password") + ":", config.plugins.iptvplayer.serijeonline_password))
    return optionList
###################################################


def gettytul():
    return 'http://www.serije.online/'


class SerijeOnline(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'serije.online', 'cookie': 'serije.online.cookie'})
        self.DEFAULT_ICON_URL = 'http://www.serije.online/uploads/custom-logo.jpg'
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.MAIN_URL = 'http://www.serije.online/'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate', 'Referer': self.getMainUrl(), 'Origin': self.getMainUrl()}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding': 'gzip, deflate', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json, text/javascript, */*; q=0.01'})

        self.MAIN_CAT_TAB = [{'category': 'list_items', 'title': _('Top Videos'), 'url': self.getFullUrl('/topvideos.html')},
                             {'category': 'list_items', 'title': _('Newest Videos'), 'url': self.getFullUrl('/newvideos.html')},
                             {'category': 'list_categories', 'title': _('Categories'), 'url': self.getFullUrl('/index.html')},
                             {'category': 'search', 'title': _('Search'), 'search_item': True},
                             {'category': 'search_history', 'title': _('Search history')},
                            ]

        self.cacheLinks = {}
        self.cacheSubCategories = {}
        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.loggedIn = None
        self.login = ''
        self.password = ''

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        origBaseUrl = baseUrl
        baseUrl = self.cm.iriToUri(baseUrl)

        def _getFullUrl(url):
            if self.cm.isValidUrl(url):
                return url
            else:
                return urlparse.urljoin(baseUrl, url)
        addParams['cloudflare_params'] = {'domain': self.up.getDomain(baseUrl), 'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT, 'full_url_handle': _getFullUrl}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def listMainMenu(self, cItem, nextCategory):
        printDBG("SerijeOnline.listMainMenu")
        self.listsTab(self.MAIN_CAT_TAB, cItem)

    def listCategories(self, cItem, nextCategory1, nextCategory2):
        printDBG("SerijeOnline.listCategories")

        self.cacheSubCategories = {}
        cacheIcons = {}

        sts, data = self.getPage(self.getFullUrl('/browse.html'))
        if sts:
            data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'pm-li-category'), ('</a', '>'))
            for item in data:
                catUrl = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
                catIcon = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0])
                cacheIcons[catUrl] = catIcon
        printDBG(cacheIcons)

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        reObjSubCats = re.compile('''<ul[^>]+?dropdown-menu[^>]+?>''')
        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'nav-collapse'), ('<a', '>', '/topvideos'))[1]
        data = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'dropdown-menu'), ('<a', '>', '/topvideos'), False)[1]
        data = re.compile('''<li[^>]+?dropdown\-submenu[^>]+?>|</ul>''').split(data)
        for catItem in data:
            catItem = reObjSubCats.split(catItem, 1)
            subCategories = []
            if len(catItem) == 2:
                # fill sub-categories
                tmp = self.cm.ph.getAllItemsBeetwenMarkers(catItem[1], '<a', '</a>')
                for item in tmp:
                    url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
                    title = self.cleanHtmlStr(item)
                    subCategories.append({'title': title, 'url': url, 'cat_url': url})
                catTitle = self.cleanHtmlStr(catItem[0])
                catUrl = self.getFullUrl(self.cm.ph.getSearchGroups(catItem[0], '''href=['"]([^'^"]+?)['"]''')[0])
                subCategories.insert(0, {'title': _('--All--'), 'url': catUrl})
                self.cacheSubCategories[catUrl] = subCategories
                params = dict(cItem)
                params.update({'good_for_fav': False, 'category': nextCategory1, 'title': catTitle, 'url': catUrl, 'cat_url': catUrl, 'icon': cacheIcons.get(catUrl, '')})
                self.addDir(params)
                continue

            tmp = self.cm.ph.getAllItemsBeetwenMarkers(catItem[0], '<a', '</a>')
            for item in tmp:
                catTitle = self.cleanHtmlStr(item)
                catUrl = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
                params = dict(cItem)
                params.update({'good_for_fav': False, 'category': nextCategory2, 'title': catTitle, 'url': catUrl, 'cat_url': catUrl, 'icon': cacheIcons.get(catUrl, '')})
                self.addDir(params)

    def listSubCategories(self, cItem, nextCategory):
        printDBG("SerijeOnline.listSubCategories")

        tab = self.cacheSubCategories.get(cItem['url'], [])
        params = dict(cItem)
        params.update({'good_for_fav': True, 'category': nextCategory})
        self.listsTab(tab, params)

    def listSort(self, cItem, nextCategory):
        printDBG("SerijeOnline.listSort [%s]" % cItem)

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'btn-group btn-group-sort'), ('</ul', '>'))[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            if not self.cm.isValidUrl(url):
                continue
            title = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'good_for_fav': False, 'category': nextCategory, 'url': url, 'title': title})
            self.addDir(params)

        if len(self.currList) < 2:
            self.currList = []
            params = dict(cItem)
            params['category'] = nextCategory
            self.listItems(params, 'explore_item')

    def listItems(self, cItem, nextCategory):
        printDBG("SerijeOnline.listItems [%s]" % cItem)
        page = cItem.get('page', 0)

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        nextPage = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<a[^>]+?href=['"]([^'^"]+?)['"][^>]*?>&raquo;</a>''')[0])
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'pm-li-video'), ('</li', '>'))
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h3', '</h3>')[1])

            desc = []
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(item, '<span', '</span>')
            for t in tmp:
                t = self.cleanHtmlStr(t)
                if t != '':
                    desc.append(t)
            desc = ' | '.join(desc) + '[/br]' + self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<p', '</p>')[1])
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'icon': icon, 'desc': desc})
            self.addDir(params)

        if self.cm.isValidUrl(nextPage):
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _("Next page"), 'url': nextPage, 'page': page + 1})
            self.addDir(params)

    def exploreItem(self, cItem, nextCategory):
        printDBG("SerijeOnline.exploreItem [%s]" % cItem)

        self.cm.clearCookie(self.COOKIE_FILE, ['PHPSESSID', '__cfduid', 'cf_clearance'])

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        desc = ''
        #desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<h2', '>', 'upper-blue'), ('</div', '>'))[1])
        if desc == '':
            desc = cItem.get('desc', '')

        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'pm-submit-data'), ('</div', '>'))[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<a', '</a>')
        if len(tmp) > 1:
            catUrl = self.getFullUrl(self.cm.ph.getSearchGroups(tmp[-1], '''href=['"]([^'^"]+?)['"]''')[0])
            catTitle = self.cleanHtmlStr(tmp[-1])
        else:
            catUrl = ''
            catTitle = ''

        printDBG("################# catUrl[%s] catTitle[%s]" % (catUrl, catTitle))

        num = 0
        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'Playerholder'), ('</div', '>'))[1]
        if tmp == '':
            printDBG("#################")
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'data:', '}', False)
            printDBG(data)
            for item in data:
                if 'getplayer' in item:
                    try:
                        query = byteify(json.loads(item + '}'), '', True)
                        query = urllib.urlencode(query)
                        url = self.getFullUrl("/ajax.php") + '?' + query
                        sts, data = self.getPage(url)
                        printDBG("---------------")
                        printDBG(data)
                        if sts:
                            if 'Playerholder' in data:
                                tmp = data
                            else:
                                msg = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'restricted-video'), ('</h2', '>'))[1])
                                if msg != '':
                                    GetIPTVNotify().push(msg, 'error', 10)
                    except Exception:
                        printExc()
                    break

        printDBG(tmp)

        data = re.compile('''<iframe[^>]+?src=['"]([^"^']+?)['"]''', re.IGNORECASE).findall(tmp)
        for url in data:
            url = self.getFullUrl(url)
            #if 1 != self.up.checkHostSupport(url): continue
            if not self.cm.isValidUrl(url):
                continue
            num += 1
            if len(data) > 1:
                title = '%s. %s' % (num, cItem['title'])
            else:
                title = cItem['title']
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': title, 'desc': desc, 'url': url})
            self.addVideo(params)

        if self.cm.isValidUrl(catUrl) and catUrl != cItem['url'] and catUrl != cItem.get('cat_url', ''):
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': nextCategory, 'title': catTitle, 'url': catUrl, 'cat_url': catUrl, 'desc': ''})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("SerijeOnline.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        if 0 == cItem.get('page', 0):
            cItem['url'] = self.getFullUrl('search.php?keywords=%s' % urllib.quote_plus(searchPattern))
        self.listItems(cItem, 'explore_item')

    def getLinksForVideo(self, cItem):
        printDBG("SerijeOnline.getLinksForVideo [%s]" % cItem)

        videoUrl = cItem['url'].replace('youtu.be/', 'youtube.com/watch?v=')
        return self.up.getVideoLinkExt(videoUrl)

    def tryTologin(self):
        printDBG('tryTologin start')

        if None == self.loggedIn or self.login != config.plugins.iptvplayer.serijeonline_login.value or\
            self.password != config.plugins.iptvplayer.serijeonline_password.value:

            self.login = config.plugins.iptvplayer.serijeonline_login.value
            self.password = config.plugins.iptvplayer.serijeonline_password.value

            rm(self.COOKIE_FILE)

            self.loggedIn = False

            if '' == self.login.strip() or '' == self.password.strip():
                return False

            sts, data = self.getPage(self.getFullUrl('/index.html'))
            if not sts:
                return False

            sts, data = self.cm.ph.getDataBeetwenNodes(data, ('<form', '>', 'login_form'), ('</form', '>'))
            if not sts:
                return False
            actionUrl = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''action=['"]([^'^"]+?)['"]''')[0])
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(data, '<input', '>')
            tmp.extend(self.cm.ph.getAllItemsBeetwenMarkers(data, '<button', '>'))
            post_data = {}
            for item in tmp:
                name = self.cm.ph.getSearchGroups(item, '''name=['"]([^'^"]+?)['"]''')[0]
                value = self.cm.ph.getSearchGroups(item, '''value=['"]([^'^"]+?)['"]''')[0]
                post_data[name] = value

            post_data.update({'username': self.login, 'pass': self.password})

            httpParams = dict(self.defaultParams)
            httpParams['header'] = dict(httpParams['header'])
            httpParams['header']['Referer'] = self.getFullUrl('/index.php')
            sts, data = self.cm.getPage(actionUrl, httpParams, post_data)
            if sts and 'do=logout' in data:
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
            self.listMainMenu({'name': 'category'}, 'list_genres')
        elif category == 'list_categories':
            self.listCategories(self.currItem, 'list_sub_categories', 'list_sort')
        elif category == 'list_sub_categories':
            self.listSubCategories(self.currItem, 'list_sort')
        elif category == 'list_sort':
            self.listSort(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem, 'explore_item')
        elif category == 'list_lists':
            self.listLists(self.currItem, 'list_items')
        elif category == 'explore_item':
            self.exploreItem(self.currItem, 'list_items')
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
        CHostBase.__init__(self, SerijeOnline(), True, [])
