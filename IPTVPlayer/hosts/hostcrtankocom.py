# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib
try:
    import json
except Exception:
    import simplejson as json
###################################################


def gettytul():
    return 'http://www.crtanko.com/'


class CrtankoCom(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': '  CrtankoCom.tv', 'cookie': 'crtankocom.cookie'})

        self.MAIN_URL = 'http://www.crtanko.com/'
        self.SEARCH_URL = self.MAIN_URL
        self.DEFAULT_ICON_URL = "http://www.crtanko.com/wp-content/uploads/2015/04/logo5.png"

        self.MAIN_CAT_TAB = [{'category': 'search', 'title': _('Search'), 'search_item': True, },
                             {'category': 'search_history', 'title': _('Search history'), }]

        self.BY_LETTER_TAB = [{'title': _('All')},
                              {'title': '#', 'letter': 'numeric'}, {'title': '', 'letter': 'A'},
                              {'title': '', 'letter': 'B'}, {'title': '', 'letter': 'C'},
                              {'title': '', 'letter': 'Č'}, {'title': '', 'letter': 'D'},
                              {'title': '', 'letter': 'E'}, {'title': '', 'letter': 'F'},
                              {'title': '', 'letter': 'G'}, {'title': '', 'letter': 'H'},
                              {'title': '', 'letter': 'I'}, {'title': '', 'letter': 'J'},
                              {'title': '', 'letter': 'K'}, {'title': '', 'letter': 'L'},
                              {'title': '', 'letter': 'LJ'}, {'title': '', 'letter': 'M'},
                              {'title': '', 'letter': 'N'}, {'title': '', 'letter': 'O'},
                              {'title': '', 'letter': 'P'}, {'title': '', 'letter': 'R'},
                              {'title': '', 'letter': 'S'}, {'title': '', 'letter': 'Š'},
                              {'title': '', 'letter': 'T'}, {'title': '', 'letter': 'U'},
                              {'title': '', 'letter': 'V'}, {'title': '', 'letter': 'W'},
                              {'title': '', 'letter': 'Y'}, {'title': '', 'letter': 'Z'},
                              {'title': '', 'letter': 'Ž'}]

        self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.cacheSubCategory = []
        self.cacheLinks = {}

    def _getFullUrl(self, url):
        if url.startswith('//'):
            url = 'http:' + url
        else:
            if 0 < len(url) and not url.startswith('http'):
                url = self.MAIN_URL + url
            if not self.MAIN_URL.startswith('https://'):
                url = url.replace('https://', 'http://')

        url = self.cleanHtmlStr(url)
        url = self.replacewhitespace(url)

        return url

    def replacewhitespace(self, data):
        data = data.replace(' ', '%20')
        return CBaseHostClass.cleanHtmlStr(data)

    def listMainMenu(self, cItem, nextCategory1, nextCategory2):
        printDBG("CrtankoCom.listMainMenu")
        sts, data = self.cm.getPage(self.getMainUrl())
        if sts:
            data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'menu-meni-container'), ('</ul', '>'))[1]
            data = re.compile('(<li[^>]*?>|</li>|<ul[^>]*?>|</ul>)').split(data)
            if len(data) > 1:
                try:
                    cTree = self.listToDir(data[1:-1], 0)[0]
                    params = dict(cItem)
                    params['c_tree'] = cTree['list'][0]
                    params['category'] = 'list_categories'
                    self.listCategories(params, nextCategory1, nextCategory2)
                except Exception:
                    printExc()
        self.listsTab(self.MAIN_CAT_TAB, cItem)

    def listCategories(self, cItem, nextCategory1, nextCategory2):
        printDBG("CrtankoCom.listCategories")
        try:
            cTree = cItem['c_tree']
            for item in cTree['list']:
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item['dat'], '<a', '</a>')[1])
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item['dat'], '''href=['"]([^'^"]+?)['"]''')[0])
                if url.endswith('/dugometrazni/') or url.endswith('/kratkometrazni/') or \
                   url.endswith('/prijevod/') or url.endswith('/prijevod/'):
                        params = dict(cItem)
                        params.update({'good_for_fav': False, 'category': nextCategory2, 'title': title, 'url': url})
                        self.addDir(params)
                elif 'list' not in item:
                    if self.cm.isValidUrl(url) and title != '':
                        params = dict(cItem)
                        params.update({'good_for_fav': False, 'category': nextCategory1, 'title': title, 'url': url})
                        self.addDir(params)
                elif len(item['list']) == 1 and title != '':
                    params = dict(cItem)
                    params.update({'good_for_fav': False, 'c_tree': item['list'][0], 'title': title, 'url': url})
                    self.addDir(params)
        except Exception:
            printExc()

    def listLetters(self, cItem, nextCategory):
        printDBG("CrtankoCom.listCategories")
        tab = []
        for item in self.BY_LETTER_TAB:
            params = dict(cItem)
            params.update(item)
            params['category'] = nextCategory
            if item['title'] == '':
                params['title'] = item['letter']
            self.addDir(params)

    def listItems(self, cItem, nextCategory='explore_item'):
        printDBG("CrtankoCom.listItems")
        page = cItem.get('page', 1)
        search = cItem.get('search', '')
        letter = cItem.get('letter', '')
        url = cItem['url']

        if page > 1:
            url += 'page/%s/' % page
        if letter != '':
            url += '?ap=%s' % letter
        elif search != '':
            url += '?s=%s' % search

        sts, data = self.cm.getPage(url)
        if not sts:
            return

        nextPage = self.cm.ph.getDataBeetwenMarkers(data, 'rel="next"', '>', False)[1]
        if '/page/{0}/'.format(page + 1) in nextPage:
            nextPage = True
        else:
            nextPage = False

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<article', '>'), ('</article', '>'))
        for item in data:
            title = self.cm.ph.getSearchGroups(item, '''title=['"]([^"^']+?)['"]''')[0]
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''data-src=['"]([^"^']+?)['"]''')[0])
            url = self._getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            if self.cm.isValidUrl(url):
                params = dict(cItem)
                params.update({'good_for_fav': True, 'category': nextCategory, 'title': self.cleanHtmlStr(title), 'url': url, 'icon': icon, 'desc': self.cleanHtmlStr(item.split('</noscript>')[-1])})
                self.addDir(params)

        if nextPage:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _('Next page'), 'page': page + 1})
            self.addDir(params)

    def exploreItem(self, cItem, category):
        printDBG("CrtankoCom.exploreItem")
        page = cItem.get('page', 1)
        url = cItem['url']

        if page > 1:
            url += '%s/' % page

        sts, data = self.cm.getPage(url)
        if not sts:
            return

        nextPage = self.cm.ph.getDataBeetwenMarkers(data, 'Pages:', '</section>', False)[1]
        if '>{0}<'.format(page + 1) in nextPage:
            nextPage = True
        else:
            nextPage = False

        tmp1 = self.cm.ph.getDataBeetwenMarkers(data, '<section', '</section', False)[1]
        tmp1 = self.cm.ph.getAllItemsBeetwenMarkers(tmp1, '<p', '</div>')
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'class="youtube"'), ('</div', '>'))
        searchMore = True
        for tmp in [tmp1, data]:
            for item in tmp:
                linkData = self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'class="youtube"'), ('</div', '>'), False)[1]
                if linkData == '':
                    continue
                titles = self.cm.ph.getAllItemsBeetwenMarkers(item, '<p', '</p>')
                if len(titles) and titles[-1] != '':
                    title = self.cleanHtmlStr(titles[-1])
                else:
                    title = self.cleanHtmlStr(item)
                t1 = cItem['title'].strip().upper()
                t2 = title.strip().upper()
                if t1 != t2 and t2 != '' and not t1 in t2:
                    title = '{0} - {1}'.format(cItem['title'], title)
                if title == '':
                    title = cItem['title']
                params = dict(cItem)
                params.update({'good_for_fav': False, 'title': title, 'url_data': linkData})
                self.addVideo(params)
                searchMore = False
            if not searchMore:
                break

        if nextPage:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _('Next page'), 'page': page + 1})
            self.addDir(params)

    def getLinksForVideo(self, cItem):
        printDBG("CrtankoCom.getLinksForVideo [%s]" % cItem)
        urlTab = []

        if 'url_data' in cItem:
            data = cItem['url_data']
        else:
            sts, data = self.cm.getPage(cItem['url'])
            if not sts:
                return []

        vidUrl = self.cm.ph.getSearchGroups(data, '<iframe[^>]+?src="([^"]+?)"', 1, True)[0]
        if vidUrl == '':
            vidUrl = self.cm.ph.getSearchGroups(data, '<script[^>]+?src="([^"]+?)"', 1, True)[0]
        if vidUrl == '':
            vidUrl = self.cm.ph.getDataBeetwenMarkers(data, 'data-rocketsrc="', '"', False, True)[1]

        if vidUrl.startswith('//'):
            vidUrl = 'http:' + vidUrl

        vidUrl = self._getFullUrl(vidUrl)
        validatehash = ''
        for hashName in ['up2stream.com', 'videomega.tv']:
            if hashName + '/validatehash.php?' in vidUrl:
                validatehash = hashName
        if validatehash != '':
            sts, dat = self.cm.getPage(vidUrl, {'header': {'Referer': cItem['url'], 'User-Agent': 'Mozilla/5.0 (X11; Linux i686) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/37.0.2062.120 Chrome/37.0.2062.120 Safari/537.36'}})
            if not sts:
                return urlTab
            dat = self.cm.ph.getSearchGroups(dat, 'ref="([^"]+?)"')[0]
            if '' == dat:
                return urlTab
            vidUrl = 'http://{0}/view.php?ref={1}&width=700&height=460&val=1'.format(validatehash, dat)

        if '' != vidUrl:
            title = self.up.getHostName(vidUrl)
            urlTab.append({'name': title, 'url': vidUrl, 'need_resolve': 1})

        return urlTab

    def getVideoLinks(self, videoUrl):
        printDBG("CrtankoCom.getVideoLinks [%s]" % videoUrl)

        urlTab = []
        if videoUrl.startswith('http'):
            urlTab = self.up.getVideoLinkExt(videoUrl)
        return urlTab

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("CrtankoCom.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.SEARCH_URL
        cItem['search'] = urllib.quote(searchPattern)
        self.listItems(cItem)

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| [%s] " % self.currItem)
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listMainMenu({'name': 'category', 'url': self.MAIN_URL}, 'list_items', 'list_letters')
        elif category == 'list_categories':
            self.listCategories(self.currItem, 'list_items', 'list_letters')
        elif category == 'list_letters':
            self.listLetters(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem)
    #EXPLORE ITEM
        elif category == 'explore_item':
            self.exploreItem(self.currItem, 'list_videos')
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
        CHostBase.__init__(self, CrtankoCom(), True, favouriteTypes=[])
