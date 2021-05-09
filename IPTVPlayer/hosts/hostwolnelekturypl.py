# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify
###################################################

###################################################
# FOREIGN import
###################################################
import datetime
import re
import urllib
try:
    import json
except Exception:
    import simplejson as json
###################################################


def gettytul():
    return 'http://wolnelektury.pl/'


class WolnelekturyPL(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'wolnelektury.pl', 'cookie': 'WolnelekturyPL.cookie'})
        self.HTTP_HEADER = {'User-Agent': 'Mozilla/5.0', 'Accept': 'text/html'}
        self.MAIN_URL = 'http://wolnelektury.pl/'
        self.DEFAULT_ICON_URL = 'http://m.img.brothersoft.com/android/598/1352446551_icon.png'
        MAIN_CAT_TAB = [{'category': 'categories', 'key': 'author', 'title': 'Autorzy'},
                        {'category': 'categories', 'key': 'epoch', 'title': 'Epoki'},
                        {'category': 'categories', 'key': 'genre', 'title': 'Gatunki'},
                        {'category': 'categories', 'key': 'kind', 'title': 'Rodzaje'}]
        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.cacheFilters = {}

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        baseUrl = self.cm.iriToUri(baseUrl)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def listFilters(self, cItem, nextCategory):
        printDBG("WolnelekturyPL.listFilters")
        self.cacheFilters = {}

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        titlesMap = {}
        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'tabbed-filter'), ('</div', '>'))[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<a', '</a>')
        for item in tmp:
            id = self.cm.ph.getSearchGroups(item, '''\sdata\-id=['"]([^"^']+?)['"]''')[0]
            titlesMap[id] = self.cleanHtmlStr(item)

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div ', '>', 'tab-content'), ('</ul', '>'))
        for section in data:
            id = self.cm.ph.getSearchGroups(section, '''\sid=['"]([^"^']+?)['"]''')[0]
            sTitle = titlesMap.get(id, id)
            itemsTab = []
            section = self.cm.ph.getAllItemsBeetwenMarkers(section, '<a', '</a>')
            for item in section:
                title = self.cleanHtmlStr(item)
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^"^']+?)['"]''')[0])
                itemsTab.append({'title': title, 'url': url})
            if len(itemsTab):
                params = dict(cItem)
                params.update({'good_for_fav': False, 'category': nextCategory, 'title': sTitle, 'items_tab': itemsTab})
                self.addDir(params)

        MAIN_CAT_TAB = [{'category': 'search', 'title': _('Search'), 'search_item': True},
                        {'category': 'search_history', 'title': _('Search history')}, ]

        self.listsTab(MAIN_CAT_TAB, cItem)

    def listCategories(self, cItem, category):
        printDBG("WolnelekturyPL.listCategories")
        try:
            key = cItem['key']
            categories = set()
            for item in self.cache:
                tmp = item[key].split(',')
                for cat in tmp:
                    categories.add(cat.strip())
            categories = sorted(list(categories))
        except Exception:
            printExc()

        for item in categories:
            params = dict(cItem)
            params.update({'title': item, 'cat': item, 'category': category})
            self.addDir(params)

    def listItems(self, cItem, nextCategory1, nextCategory2, checkPlayable=False):
        printDBG("WolnelekturyPL.listItems")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        if '/szukaj/' in cItem['url']:
            data2 = self.cm.ph.getDataBeetwenNodes(data, ('<', '>', 'work-list'), ('<footer', '>'))[1]
        else:
            data2 = self.cm.ph.getDataBeetwenNodes(data, ('<ol', '>', 'work-list'), ('</ol', '>'))[1]
        data2 = re.compile('''<li[^>]+?Book-item[^>]+?>''', re.IGNORECASE).split(data2)
        if len(data2):
            del data2[0]
        for item in data2:
            if checkPlayable and 'jp-play' not in item:
                continue
            tmp = self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'title'), ('</div', '>'))[1]
            title = self.cleanHtmlStr(tmp)
            url = self.getFullUrl(self.cm.ph.getSearchGroups(tmp, '''\shref=['"]([^"^']+?)['"]''')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''\ssrc=['"]([^"^']+?)['"]''')[0])

            desc = []
            tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'book-box-head'), ('</div', '>'))[1]).replace(' , ', ', ')
            if tmp != '':
                desc.append(tmp)
            tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'tags'), ('</div', '>'))[1].replace('</span></span>', '[/br]'))
            if tmp != '':
                desc.append(' ' + tmp)

            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': nextCategory2, 'title': title, 'url': url, 'icon': icon, 'desc': '[/br]'.join(desc)})
            self.addDir(params)

        if nextCategory1 == '':
            return

        data = self.cm.ph.getDataBeetwenNodes(data, ('<h2', '</div>', 'plain-list'), ('<div', '>', 'clearboth'))[1].split('<h2>')
        if len(data):
            del data[0]
        for section in data:
            section = section.split('</h2>', 1)
            sTitle = self.cleanHtmlStr(section[0])
            section = self.cm.ph.getAllItemsBeetwenMarkers(section[1], '<p', '</p>')
            itemsTab = []
            author = ''
            for item in section:
                if 'header' in item:
                    author = self.cleanHtmlStr(item)
                    continue
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^"^']+?)['"]''')[0])
                if url == '':
                    continue
                if url.endswith('/'):
                    icon = url[:-1].split('/')
                else:
                    icon = icon.split('/')
                icon = self.getFullIconUrl('/media/book/cover_thumb/%s.jpg' % icon[-1])
                title = self.cleanHtmlStr(item)
                itemsTab.append({'title': title, 'url': url, 'icon': icon, 'desc': author})

            if len(itemsTab):
                params = dict(cItem)
                params.update({'good_for_fav': False, 'category': nextCategory1, 'title': sTitle, 'items_tab': itemsTab})
                self.addDir(params)

    def listSubItems(self, cItem, nextCategory):
        printDBG("WolnelekturyPL.listSubItems [%s]" % cItem)
        cItem = dict(cItem)
        itemsTab = cItem.pop('items_tab', [])
        cItem['category'] = nextCategory
        self.listsTab(itemsTab, cItem)

    def exploreItem(self, cItem):
        printDBG("WolnelekturyPL.exploreItem")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'jp-playlist'), ('</ul', '>'))[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
        objReDesc = re.compile('''<div[^>]+?extra\-info[^>]+?>''')
        for item in data:

            tmp = objReDesc.split(item)
            title = self.cleanHtmlStr(tmp[0])
            desc = self.cleanHtmlStr(tmp[1])
            urlTab = []
            mp3Url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\sdata\-mp3=['"]([^"^']+?)['"]''')[0])
            oggUrl = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\sdata\-ogg=['"]([^"^']+?)['"]''')[0])
            if mp3Url != '':
                urlTab.append({'name': 'mp3', 'url': mp3Url, 'need_resolve': 0})
            if oggUrl != '':
                urlTab.append({'name': 'ogg', 'url': mp3Url, 'need_resolve': 0})
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': title, 'urls': urlTab, 'desc': desc})
            self.addAudio(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("WolnelekturyPL.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('/szukaj/?q=%s' % urllib.quote_plus(searchPattern))
        self.listItems(cItem, '', 'explore_item', True)

    def getLinksForVideo(self, cItem):
        printDBG("WolnelekturyPL.getLinksForVideo [%s]" % cItem)
        return cItem.get('urls', [])

    def getArticleContent(self, cItem):
        printDBG("WolnelekturyPL.getArticleContent [%s]" % cItem)
        retTab = []

        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return []

        try:
            data = byteify(json.loads(data))
            url = data['txt']
            sts, desc = self.cm.getPage(url)
            if not sts:
                desc = ''
            otherInfo = {}
            return [{'title': self.cleanHtmlStr(data['title']), 'text': self.cleanHtmlStr(desc), 'images':[{'title': '', 'url': data['cover']}], 'other_info':otherInfo}]
        except Exception:
            printExc()

        return []

        icon = cItem.get('icon', '')
        otherInfo = {}
        try:
            data = byteify(json.loads(data))
            icon = self._viaProxy(self._getFullUrl(data['poster'], False))
            title = data['title']
            desc = data['overview']
            otherInfo['actors'] = data['actors']
            otherInfo['director'] = data['director']
            genres = []
            for item in data['genre']:
                genres.append(item['name'])
            otherInfo['genre'] = ', '.join(genres)
            otherInfo['rating'] = data['imdb_rating']
            otherInfo['year'] = data['year']
            otherInfo['duration'] = str(datetime.timedelta(seconds=data['runtime']))
        except Exception:
            printExc()

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
            self.listFilters({'name': 'category', 'url': self.getFullUrl('/katalog/audiobooki/')}, 'list_sub_items_1')
        elif category == 'list_sub_items_1':
            self.listSubItems(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem, 'list_sub_items_2', 'explore_item')
        elif category == 'list_sub_items_2':
            self.listSubItems(self.currItem, 'explore_item')
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
        CHostBase.__init__(self, WolnelekturyPL(), True, [])
