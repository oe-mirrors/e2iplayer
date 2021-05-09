# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
###################################################

###################################################
# FOREIGN import
###################################################
import urllib
try:
    import json
except Exception:
    import simplejson as json
###################################################


def gettytul():
    return 'http://movizland.com/'


class MovizlandCom(CBaseHostClass):
    HEADER = {'User-Agent': 'Mozilla/5.0', 'Accept': 'text/html'}
    AJAX_HEADER = dict(HEADER)
    AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})

    MAIN_URL = 'http://m.movizland.com/'
    SEARCH_URL = MAIN_URL + '?s='
    DEFAULT_ICON_URL = "http://vb.movizland.com/movizland/images/logo.png"

    MAIN_CAT_TAB = [{'category': 'categories', 'title': _('Categories'), 'url': MAIN_URL, },
                    {'category': 'search', 'title': _('Search'), 'search_item': True, },
                    {'category': 'search_history', 'title': _('Search history'), }]

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': '  MovizlandCom.tv', 'cookie': 'movizlandcom.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (X11; Linux i686) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/37.0.2062.120 Chrome/37.0.2062.120 Safari/537.36'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'text/html'}
        self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
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

    def _getIconUrl(self, url):
        url = self._getFullUrl(url)
        if url == '':
            return ''
        cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE)
        return strwithmeta(url, {'Cookie': cookieHeader, 'User-Agent': self.USER_AGENT})

    def getPage(self, baseUrl, params={}, post_data=None):
        params['cloudflare_params'] = {'domain': 'm.movizland.com', 'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT, 'full_url_handle': self._getFullUrl}
        return self.cm.getPageCFProtection(baseUrl, params, post_data)

    def cleanHtmlStr(self, data):
        data = data.replace('&nbsp;', ' ')
        data = data.replace('&nbsp', ' ')
        return CBaseHostClass.cleanHtmlStr(data)

    def replacewhitespace(self, data):
        data = data.replace(' ', '%20')
        return CBaseHostClass.cleanHtmlStr(data)

    def listsTab(self, tab, cItem, type='dir'):
        printDBG("MovizlandCom.listsTab")
        for item in tab:
            params = dict(cItem)
            params.update(item)
            params['name'] = 'category'
            if type == 'dir':
                self.addDir(params)
            else:
                self.addVideo(params)

    def listCategories(self, cItem, nextCategory):
        printDBG("MovizlandCom.listCategories")

        sts, data = self.getPage(cItem['url'], self.defaultParams)
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenMarkers(data, '<ul id="tabs-ui">', '</ul>', False)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li>', '</li>')

        for item in data:
            url = self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''', 1)[0]
            url = self._getFullUrl(url)
            if not url.startswith('http'):
                continue
            title = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'category': nextCategory, 'title': title, 'url': url})
            self.addDir(params)

    def listItems(self, cItem, nextCategory='explore_item'):
        printDBG("MovizlandCom.listItems")
        page = cItem.get('page', 1)
        post_data = cItem.get('post_data', None)
        url = cItem['url']

        if page > 1:
            if url.endswith('/'):
                url += 'page/%d/' % page
            elif '?' not in url:
                url += '?page=%d' % page
            else:
                url += '&page=%d' % page

        sts, data = self.getPage(url, self.defaultParams, post_data)
        if not sts:
            return

        nextPage = self.cm.ph.getDataBeetwenMarkers(data, '<div class="paging">', '</ul>', False)[1]
        if '>{0}<'.format(page + 1) in nextPage:
            nextPage = True
        else:
            nextPage = False

        data = self.cm.ph.getDataBeetwenMarkers(data, '<main ', '</main>')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li class="grid-item ">', '</li>')

        for item in data:
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(item, '<a ', '</a>')
            item = ''
            for t in tmp:
                if '<img' in t:
                    item = t
                    break
            if item == '' and len(tmp):
                item = tmp[-1]
            url = self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''', 1)[0]
            if url == '':
                continue
            title = self.cleanHtmlStr(item)
            icon = self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''', 1)[0]

            url = self._getFullUrl(url)
            url = self._getFullUrl(url)

            params = dict(cItem)
            params.update({'category': nextCategory, 'title': title, 'url': self._getFullUrl(url), 'icon': self._getFullUrl(icon)})

            if '/movies/ in url':
                self.addVideo(params)
            else:
                self.addDir(params)

        if nextPage:
            params = dict(cItem)
            params.update({'title': _('Next page'), 'page': page + 1})
            self.addDir(params)

    def exploreItem(self, cItem):
        printDBG("MovizlandCom.exploreItem")
        # not implemented
        # it seems that there are no series on this service
        return

    def getLinksForVideo(self, cItem):
        printDBG("MovizlandCom.getLinksForVideo [%s]" % cItem)
        urlTab = []

        sts, data = self.getPage(cItem['url'], self.defaultParams)
        if not sts:
            return []

        data = self.cm.ph.getDataBeetwenMarkers(data, 'class="iframeWide"', '<div class="footer">')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
        for item in data:
            url = self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''', 1)[0]
            url = self._getFullUrl(url)
            if not self.cm.isValidUrl(url):
                continue
            title = self.cleanHtmlStr(item)
            printDBG(">>>>>>>>>>>>>> " + title)
            if 'class="ViewMovieNow"' not in item:
                continue

            if '?view=1' in url or '?high' in url or '?download' in url or 'embedM-' in url:
                urlTab.append({'name': title, 'url': url, 'need_resolve': 0})
            elif 'movizland.com' in url:
                continue
            elif 'moshahda.net' in url and ('embedM-' in url or '?download' in url):
                continue
            elif self.up.checkHostSupport(url) == 1:
                title = self.up.getHostName(url)
                urlTab.append({'name': title, 'url': url, 'need_resolve': 1})
        return urlTab

    def getVideoLinks(self, videoUrl):
        printDBG("MovizlandCom.getVideoLinks [%s]" % videoUrl)
        urlTab = []
        if videoUrl.startswith('http'):
            urlTab = self.up.getVideoLinkExt(videoUrl)
        return urlTab

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("MovizlandCom.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.SEARCH_URL + urllib.quote_plus(searchPattern)
        self.listItems(cItem)

    def getFavouriteData(self, cItem):
        printDBG("MovizlandCom.getFavouriteData")
        return str(cItem['url'])

    def getLinksForFavourite(self, fav_data):
        printDBG("MovizlandCom.getLinksForFavourite")
        return self.getLinksForVideo({'url': fav_data})

    def getArticleContent(self, cItem):
        printDBG("MovizlandCom.getArticleContent [%s]" % cItem)

        retTab = []

        otherInfo = {}

        url = cItem['url'].replace('://m.', '://')
        sts, data = self.getPage(url)
        if not sts:
            return []
        cUrl = data.meta['url']

        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'contentMovie'), ('</div', '>'))[1])
        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'poster-movie'), ('</div', '>'))[1]
        icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(tmp, '''<img[^>]+?src=['"]([^"^']+?)['"]''')[0])
        title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<em', '>', 'befores'), ('</em', '>'))[1])

        itemsList = []

        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<span', '>', 'ratings'), ('</span', '>'), False)[1])
        if tmp != '':
            itemsList.append((_('Rating:'), tmp))

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<btns', '</btns>')
        for item in data:
            item = item.split('</span>', 1)
            if len(item) < 2:
                continue
            key = self.cleanHtmlStr(item[0])
            if key == '':
                cotninue
            val = []
            item = self.cm.ph.getAllItemsBeetwenMarkers(item[1], '<a', '</a>')
            for it in item:
                it = self.cleanHtmlStr(it)
                if it:
                    val.append(it)

            if len(val):
                itemsList.append((key, ', '.join(val)))

        if title == '':
            title = cItem['title']
        if icon == '':
            icon = cItem.get('icon', self.DEFAULT_ICON_URL)
        if desc == '':
            desc = cItem.get('desc', '')

        return [{'title': self.cleanHtmlStr(title), 'text': self.cleanHtmlStr(desc), 'images': [{'title': '', 'url': self.getFullUrl(icon)}], 'other_info': {'custom_items_list': itemsList}}]

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})
        elif category == 'categories':
                self.listCategories(self.currItem, 'list_items')
        elif category == 'list_items':
                self.listItems(self.currItem)
    #EXPLORE ITEM
        elif category == 'explore_item':
            self.exploreItem(self.currItem)
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
        # for now we must disable favourites due to problem with links extraction for types other than movie
        CHostBase.__init__(self, MovizlandCom(), True, favouriteTypes=[CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO])

    def withArticleContent(self, cItem):
        if cItem['type'] != 'video':
            return False
        return True
