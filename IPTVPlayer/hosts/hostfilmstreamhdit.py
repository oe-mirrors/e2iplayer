# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
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
###################################################

def GetConfigList():
    optionList = []
    return optionList


def gettytul():
    return 'http://filmstreamhd.it/'


class FilmStreamHD(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'filmstreamhd.it', 'cookie': 'filmstreamhd.it.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.MAIN_URL = 'http://filmstreamhd.it/'
        self.DEFAULT_ICON_URL = self.getFullIconUrl('/wp-content/uploads/2018/09/logonuovoHD.png')
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate', 'Referer': self.getMainUrl(), 'Origin': self.getMainUrl()}
        self.defaultParams = {'header': self.HTTP_HEADER, 'with_metadata': True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.MAIN_CAT_TAB = [{'category': 'list_items', 'title': _('HOME'), 'url': self.getMainUrl()},
                             {'category': 'genres', 'title': _('FILM ARCHIVE'), 'url': self.getFullUrl('/film-archivio')},
                             {'category': 'search', 'title': _('Search'), 'search_item': True},
                             {'category': 'search_history', 'title': _('Search history'), }
                            ]

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

    def setMainUrl(self, url):
        if self.cm.isValidUrl(url):
            self.MAIN_URL = self.cm.getBaseUrl(url)

    def listCategories(self, cItem, nextCategory, m1, addAll=True):
        printDBG("FilmStreamHD.listCategories")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(data.meta['url'])

        if addAll:
            params = dict(cItem)
            params.update({'category': nextCategory, 'title': _('--All--'), 'url': data.meta['url']})
            self.addDir(params)

        data = self.cm.ph.getDataBeetwenMarkers(data, m1, '</ul>', False)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            title = self.cleanHtmlStr(item)
            if title == '':
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''title=['"]([^"^']+?)['"]''')[0])
            params = dict(cItem)
            params.update({'category': nextCategory, 'title': title, 'url': url})
            self.addDir(params)

    def listItems(self, cItem):
        printDBG("FilmStreamHD.listItems")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(data.meta['url'])

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<a', '>', 'loadnavi'), ('</a', '>'))[1]
        nextPage = self.getFullUrl(self.cm.ph.getSearchGroups(nextPage, '''href=['"]([^"^']+?)['"]''')[0])

        data = self.cm.ph.rgetAllItemsBeetwenNodes(data, ('<div', '>', 'preview'), ('<div', '>', 'clear'))
        for dataItem in data:
            dataItem = self.cm.ph.rgetAllItemsBeetwenNodes(dataItem, ('</div', '>'), ('<div', '>', 'preview'))
            for item in dataItem:
                icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''')[0])
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<span', '>', 'movie-title'), ('</span', '>'), False)[1])

                desc = []
                tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<span', '>', 'movie-release'), ('</span', '>'), False)[1])
                if tmp != '':
                    desc.append(tmp)
                tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<span', '>', 'icon-hd'), ('</span', '>'), False)[1])
                if tmp != '':
                    desc.append(tmp)
                tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'movie-info'), ('</div', '>'), False)[1])
                if tmp != '':
                    desc.append(tmp)
                desc = [' | '.join(desc)]

                tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'movie-cast'), ('</div', '>'), False)[1])
                if tmp != '':
                    desc.append(tmp)

                tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'movie-excerpt'), ('</div', '>'), False)[1])
                if tmp != '':
                    desc.append(tmp)

                params = dict(cItem)
                params.update({'good_for_fav': True, 'title': title, 'url': url, 'icon': icon, 'desc': '[/br]'.join(desc)})
                self.addVideo(params)

        if nextPage:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _('Next page'), 'url': nextPage, 'page': cItem.get('page', 1) + 1})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('/?s=') + urllib_quote_plus(searchPattern)
        cItem['category'] = 'list_items'
        self.listItems(cItem)

    def getLinksForVideo(self, cItem):
        printDBG("FilmStreamHD.getLinksForVideo [%s]" % cItem)
        urlTab = []

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        cUrl = data.meta['url']
        self.setMainUrl(cUrl)

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', '-player-'), ('</script', '>'), False)[1]
        data = self.cm.ph.getDataBeetwenMarkers(data, '"source"', ']')[1]
        data = re.compile('''['"]url['"]\s*?:\s*?['"]([^'^"]+?)['"]''').findall(data)
        for item in data:
            url = self.getFullUrl(item.replace('\\/', '/'))
            urlTab.append({'name': self.up.getHostName(url), 'url': strwithmeta(url, {'Referer': cUrl, 'User-Agent': self.USER_AGENT}), 'need_resolve': 0})

        return urlTab

    def getArticleContent(self, cItem):
        printDBG("FilmStreamHD.getArticleContent [%s]" % cItem)

        retTab = []

        otherInfo = {}

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return []
        cUrl = data.meta['url']
        self.setMainUrl(cUrl)

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'single-content'), ('<div', '>', 'single-content'))[1]
        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'excerpt'), ('</div', '>'))[1])
        icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(data, '''<img[^>]+?src=['"]([^"^']+?)['"]''')[0])
        title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<h1', '</h1>')[1])

        itemsList = []
        for m in ['imdb-rating', 'views-number']:
            tmp = self.cm.ph.getDataBeetwenNodes(data, ('<span', '>', m), ('</span', '>'), False)[1].split('<small>', 1)
            if len(tmp):
                key = self.cleanHtmlStr(tmp[1])
                val = self.cleanHtmlStr(tmp[0])
                itemsList.append((key + ':', val))

        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'release'), ('</div', '>'), False)[1].replace('(', ''))
        if tmp != '':
            itemsList.append((_('Release:'), tmp[:-1]))

        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'categories'), ('</div', '>'), False)[1].replace('</a>', ', ').replace(' , ', ', '))
        if tmp != '':
            itemsList.append((_('Categories:'), tmp[:-1]))

        for m in ['director', 'actor']:
            tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', m), ('</div', '>'), False)[1].split('</h4>', 1)
            if len(tmp):
                key = self.cleanHtmlStr(tmp[0])
                val = self.cleanHtmlStr(tmp[1])
                itemsList.append((key, val))

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
        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})
        elif category == 'genres':
            self.listCategories(self.currItem, 'release', '>Genere<', True)
        elif category == 'release':
            self.listCategories(self.currItem, 'sort', '>Anno<', True)
        elif category == 'sort':
            self.listCategories(self.currItem, 'list_items', '>Ordinare<', False)
    #ITEMS
        elif category == 'list_items':
            self.listItems(self.currItem)
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
        CHostBase.__init__(self, FilmStreamHD(), True)

    def withArticleContent(self, cItem):
        if 'video' == cItem.get('type', ''):
            return True
        else:
            return False
