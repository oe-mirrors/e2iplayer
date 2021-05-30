# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, GetIPTVNotify
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib
###################################################


def gettytul():
    return 'https://official-film-illimite.ws/'


class OfficialFilmIllimite(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'OfficialFilmIllimite', 'cookie': 'OfficialFilmIllimite.cookie'})
        self.MAIN_URL = 'https://official-film-illimite.ws/'
        self.DEFAULT_ICON_URL = self.getFullIconUrl('/wp-content/uploads/2016/10/official-film-illimite.png')
        self.cacheLinks = {}

    def getFullUrl(self, url, baseUrl=None):
        return CBaseHostClass.getFullUrl(self, url.replace('&#038;', '&'), baseUrl)

    def getPage(self, baseUrl, addParams={}, post_data=None):
        return self.cm.getPage(baseUrl, addParams, post_data)

    def listMain(self, cItem):
        printDBG("OfficialFilmIllimite.listMain")
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'rmenus'), ('</div', '>'), False)[1]
        tmp = re.compile('(<li[^>]*?>|</li>|<ul[^>]*?>|</ul>)').split(tmp)
        if len(tmp) > 1:
            try:
                cTree = self.listToDir(tmp[1:-1], 0)[0]
                params = dict(cItem)
                params['c_tree'] = cTree['list'][0]
                params['category'] = 'cat_items'
                self.listCatItems(params, 'list_items')
            except Exception:
                printExc()

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'filter-widget'), ('<script', '>'), False)[1]
        printDBG(data)
        baseTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'header'), ('</div', '>'), False)[1]) + ': %s'
        tabsTitles = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'filter-tab-'), ('</div', '>'), False)
        tabsData = data.split('</i>')
        if len(tabsData):
            del tabsData[0]
        if len(tabsTitles) == len(tabsData):
            for idx in range(len(tabsData)):
                data = self.cm.ph.getAllItemsBeetwenMarkers(tabsData[idx], '<a', '</a>')
                subItems = []
                for item in data:
                    url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)["']''', 1, True)[0])
                    title = self.cleanHtmlStr(item)
                    params = dict(cItem)
                    params.update({'title': title, 'url': url, 'category': 'list_items'})
                    subItems.append(params)
                if len(subItems):
                    params = dict(cItem)
                    params.update({'title': baseTitle % self.cleanHtmlStr(tabsTitles[idx]), 'category': 'sub_items', 'sub_items': subItems})
                    self.addDir(params)
        else:
            GetIPTVNotify().push("Parsing error. Number of tab titles mismatched number of tabs!", 'error', 10)

        MAIN_CAT_TAB = [{'category': 'search', 'title': _('Search'), 'search_item': True},
                        {'category': 'search_history', 'title': _('Search history'), }]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listCatItems(self, cItem, nextCategory):
        printDBG("OfficialFilmIllimite.listCatItems")
        printDBG(cItem['c_tree'])
        try:
            cTree = cItem['c_tree']
            url = self.getFullUrl(self.cm.ph.getSearchGroups(cTree['dat'], '''href=['"]([^'^"]+?)['"]''')[0])
            if url != '':
                params = dict(cItem)
                params.update({'good_for_fav': False, 'category': nextCategory, 'title': _('--All--'), 'url': url})
                self.addDir(params)

            for item in cTree['list']:
                title = self.cleanHtmlStr(item['dat'])
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item['dat'], '''href=['"]([^'^"]+?)['"]''')[0])
                if 'list' not in item:
                    if url != '' and title != '':
                        params = dict(cItem)
                        params.update({'good_for_fav': False, 'category': nextCategory, 'title': title, 'url': url})
                        self.addDir(params)
                elif len(item['list']) == 1 and title != '':
                    item['list'][0]['dat'] = item['dat']
                    params = dict(cItem)
                    params.update({'good_for_fav': False, 'c_tree': item['list'][0], 'title': title, 'url': url})
                    self.addDir(params)
        except Exception:
            printExc()

    def listSubItems(self, cItem):
        printDBG("OfficialFilmIllimite.listSubItems")
        self.currList = cItem['sub_items']

    def listItems(self, cItem, nextCategory):
        printDBG("OfficialFilmIllimite.listItems [%s]" % cItem)
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        page = cItem.get('page', 1)

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'pag_b'), ('</div', '>'), False)[1]
        nextPage = self.getFullUrl(self.cm.ph.getSearchGroups(nextPage, '''href=['"]([^"^']+?)["']''', 1, True)[0])

        if 'paginador' in data:
            data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'mt-'), ('<div', '>', 'paginador'))[1]
        else:
            data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'mt-'), ('<style', '>'))[1]

        data = self.cm.ph.rgetAllItemsBeetwenNodes(data, ('</div', '>'), ('<div', '>', 'mt-'))
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)["']''', 1, True)[0])
            if url == '':
                continue
            icon = self.cm.ph.getSearchGroups(item, '''\ssrc=['"]([^"^']+?\.(?:jpe?g|png)(?:\?[^'^"]*?)?)['"]''')[0]
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<h', '>'), ('</h', '>'), False)[1])
            desc = ''
            descTab = []
            item = self.cm.ph.getAllItemsBeetwenNodes(item, ('<span', '>'), ('</span', '>'))
            for t in item:
                d = self.cleanHtmlStr(t)
                if d == '':
                    continue
                elif '"ttx' in t:
                    desc = d
                elif '"tt' in t or 'imdb' in t:
                    continue
                else:
                    descTab.append(d)
            desc = ' | '.join(descTab[1:2] + descTab[2:3] + descTab[0:1] + descTab[3:]) + '[/br]' + desc
            params = dict(cItem)
            params.update({'good_for_fav': True, 'title': title, 'category': nextCategory, 'url': url, 'desc': desc, 'icon': self.getFullIconUrl(icon)})
            self.addDir(params)

        if nextPage != '':
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _('Next page'), 'page': page + 1, 'url': nextPage})
            self.addDir(params)

    def exploreItem(self, cItem):
        printDBG("OfficialFilmIllimite.exploreItem")
        self.cacheLinks = {}

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        cUrl = self.cm.meta['url']
        self.setMainUrl(cUrl)

        desc = []
        try:
            descObj = self.getArticleContent(cItem, data)[0]
            for item in descObj['other_info']['custom_items_list']:
                desc.append(item[1])
            desc = ' | '.join(desc) + '[/br]' + descObj['text']
        except Exception:
            printExc()

        self.cacheLinks[cUrl] = []
        playerData = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'player'), ('</ul', '>'), False)[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(playerData, '<li', '</li>')
        for item in tmp:
            link = self.cm.ph.getSearchGroups(item, '''href=['"]#([^"^']+?)['"]''')[0]
            if link == '':
                continue
            name = self.cleanHtmlStr(item)
            link = self.cm.ph.getDataBeetwenNodes(playerData, ('<div', '>', link), ('</div', '>'), False)[1]
            url = self.getFullUrl(self.cm.ph.getSearchGroups(link, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0])
            if url != '':
                self.cacheLinks[cUrl].append({'name': name, 'url': strwithmeta(url, {'Referer': cUrl}), 'need_resolve': 1})

        if len(self.cacheLinks[cUrl]):
            params = dict(cItem)
            params.update({'good_for_fav': False, 'url': cUrl, 'desc': desc, 'prev_url': cItem['url']})
            self.addVideo(params)
        else:
            playerData = self.cm.ph.rgetAllItemsBeetwenNodes(data, ('</iframe', '>'), ('<div', '>', 'id'), caseSensitive=False)
            for item in playerData:
                frameId = self.cm.ph.getSearchGroups(item, '''<div[^>]+?id=['"]([^"^']+?)['"]''', 1, True)[0]
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0])
                if url == '':
                    continue
                name = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<a', '>', '#' + frameId), ('</a', '>'), False)[1])
                self.cacheLinks[url] = [{'name': name, 'url': strwithmeta(url, {'Referer': cUrl}), 'need_resolve': 1}]
                params = dict(cItem)
                params.update({'good_for_fav': False, 'url': url, 'title': cItem['title'] + ': ' + name, 'desc': desc, 'prev_url': cItem['url']})
                self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        searchPattern = urllib.quote_plus(searchPattern)
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('/?s=') + urllib.quote_plus(searchPattern)
        cItem['category'] = 'list_items'
        self.listItems(cItem, 'explore_item')

    def getLinksForVideo(self, cItem):
        printDBG("OfficialFilmIllimite.getLinksForVideo [%s]" % cItem)
        if 'trailer' in cItem:
            return self.up.getVideoLinkExt(cItem['url'])
        return self.cacheLinks.get(cItem['url'], [])

    def getVideoLinks(self, videoUrl):
        printDBG("OfficialFilmIllimite.getVideoLinks [%s]" % videoUrl)
        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if videoUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name']

        if 0 == self.up.checkHostSupport(videoUrl):
            sts, data = self.getPage(videoUrl, {'max_data_size': 0, 'header': MergeDicts(self.cm.getDefaultHeader(), {'Referer': videoUrl.meta['Referer']})})
            try:
                videoUrl = strwithmeta(self.cm.meta['url'], videoUrl.meta)
            except Exception:
                printExc()

        return self.up.getVideoLinkExt(videoUrl)

    def getArticleContent(self, cItem, data=None):
        printDBG("Altadefinizione.getArticleContent [%s]" % cItem)
        retTab = []

        url = cItem.get('prev_url', cItem['url'])
        if data == None:
            sts, data = self.getPage(url)
            if not sts:
                data = ''

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'movie-info'), ('<div', '>', 'watch-links'), False)[1]
        icon = ''
        if '/seria/' in url:
            title = ''
        else:
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'title'), ('</div', '>'), False)[1])
        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'synopsis'), ('</div', '>'), False)[1])

        itemsList = []
        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'info-right'), ('</div', '>'), False)[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<span', '</span>')
        for idx in range(1, len(tmp), 2):
            key = self.cleanHtmlStr(tmp[idx - 1])
            val = self.cleanHtmlStr(tmp[idx])
            if key == '' or val == '':
                continue
            itemsList.append((key, val))

        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<span', '>', 'movie-len'), ('</span', '>'), False)[1])
        if tmp != '':
            itemsList.append((_('Duration:'), tmp))

        data = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'genre'), ('</ul', '>'), False)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
        tmp = []
        for t in data:
            t = self.cleanHtmlStr(t)
            if t != '':
                tmp.append(t)
        if len(tmp):
            itemsList.append((_('Genres:'), ', '.join(tmp)))

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
        printDBG("handleService: ||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listMain({'name': 'category', 'type': 'category'})
        elif category == 'cat_items':
            self.listCatItems(self.currItem, 'list_items')
        elif category == 'sub_items':
            self.listSubItems(self.currItem)
        elif category == 'list_items':
            self.listItems(self.currItem, 'explore_item')
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
        CHostBase.__init__(self, OfficialFilmIllimite(), True, [])

    def withArticleContent(self, cItem):
        if 'prev_url' in cItem or cItem.get('category', '') == 'explore_item':
            return True
        else:
            return False
