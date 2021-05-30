# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
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
    return 'http://filma24.io/'


class Filma24IO(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'Filma24IO', 'cookie': 'Filma24IO.cookie'})
        self.MAIN_URL = 'http://www.filma24.io/'
        self.DEFAULT_ICON_URL = 'http://www.filma24.io/wp-content/themes/cr_filma_greenv2/assets/img/logo2018.png'
        self.cacheLinks = {}

    def getPage(self, baseUrl, addParams={}, post_data=None):
        return self.cm.getPage(baseUrl, addParams, post_data)

    def listMain(self, cItem):
        printDBG("Filma24IO.listMain")
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        subItems = []
        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'sort'), ('</ul', '>'), False)[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<a', '</a>')
        for item in tmp:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)["']''', 1, True)[0])
            title = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'title': title, 'url': url, 'category': 'list_items'})
            subItems.append(params)

        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'main_menu'), ('</ul', '>'), False)[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li', '</li>')
        for item in tmp:
            if '_blank' in item:
                continue
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)["']''', 1, True)[0])
            title = self.cleanHtmlStr(item)
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)["']''', 1, True)[0])
            params = dict(cItem)
            if len(self.currList):
                params['category'] = 'list_items'
            else:
                params.update({'category': 'sub_items', 'sub_items': subItems})
            params.update({'title': title, 'url': url, 'icon': icon})
            self.addDir(params)

        subItems = []
        data = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'second-menu'), ('</ul', '>'), False)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)["']''', 1, True)[0])
            title = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'title': title, 'url': url, 'category': 'list_items'})
            subItems.append(params)

        if len(subItems):
            params = dict(cItem)
            params.update({'title': _('Categories'), 'category': 'sub_items', 'sub_items': subItems})
            self.addDir(params)

        MAIN_CAT_TAB = [{'category': 'search', 'title': _('Search'), 'search_item': True},
                        {'category': 'search_history', 'title': _('Search history'), }]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listSubItems(self, cItem):
        printDBG("Filma24IO.listSubItems")
        self.currList = cItem['sub_items']

    def listItems(self, cItem, nextCategory):
        printDBG("Filma24IO.listItems [%s]" % cItem)
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        page = cItem.get('page', 1)

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'pagination'), ('</div', '>'), False)[1]
        nextPage = self.cm.ph.getDataBeetwenNodes(nextPage, ('<a', '>', 'next'), ('</a', '>'))[1]
        nextPage = self.getFullUrl(self.cm.ph.getSearchGroups(nextPage, '''href=['"]([^"^']+?)["']''', 1, True)[0])

        if '/seriale/' in cItem['url']:
            baseTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'category-head'), ('</div', '>'))[1]) + ' : %s'
            data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'post-'), ('<div', '>', 'footer'))[1]
        else:
            baseTitle = '%s'
            data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'post-'), ('<div', '>', 'pagination'))[1]

        data = self.cm.ph.rgetAllItemsBeetwenNodes(data, ('</div', '>'), ('<div', '>', 'post-'))
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)["']''', 1, True)[0])
            if url == '':
                continue
            icon = self.cm.ph.getSearchGroups(item, '''image\:url\(([^\)]+?)\)''', 1, True)[0].strip()
            if icon[:1] in ['"', "'"]:
                icon = icon[1:-1]
            if icon == '':
                icon = self.cm.ph.getSearchGroups(item, '''\ssrc=['"]([^"^']+?\.(?:jpe?g|png)(?:\?[^'^"]*?)?)['"]''')[0]
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<h', '>'), ('</h', '>'), False)[1])

            desc = []
            t = self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'tags'), ('</div', '>'), False)[1]
            tmp = self.cm.ph.getAllItemsBeetwenNodes(item, ('<div', '>', '-poster'), ('</div', '>'), False)
            tmp.extend(self.cm.ph.getAllItemsBeetwenMarkers(t, '<li', '</li>'))
            for t in tmp:
                t = self.cleanHtmlStr(t)
                if t != '':
                    desc.append(t)

            params = dict(cItem)
            params.update({'good_for_fav': True, 'title': baseTitle % title, 'url': url, 'desc': ' | '.join(desc), 'icon': self.getFullIconUrl(icon)})
            if '/seriale/' not in url:
                params['category'] = nextCategory
            self.addDir(params)

        if nextPage != '':
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _('Next page'), 'page': page + 1, 'url': nextPage})
            self.addDir(params)

    def exploreItem(self, cItem):
        printDBG("Filma24IO.exploreItem")
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

        # trailer
        trailerUrl = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'trailer-player'), ('</div', '>'), False)[1]
        trailerUrl = self.getFullUrl(self.cm.ph.getSearchGroups(trailerUrl, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, ignoreCase=True)[0])
        if trailerUrl != '':
            trailerUrl = strwithmeta(trailerUrl, {'Referer': cItem['url']})
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': '%s - %s' % (cItem['title'], _('trailer')), 'url': trailerUrl, 'trailer': True, 'desc': desc, 'prev_url': cItem['url']})
            self.addVideo(params)

        self.cacheLinks[cUrl] = []
        tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<ul', '>', 'w-links'), ('</ul', '>'), False)
        for tmpItem in tmp:
            tmpItem = self.cm.ph.getAllItemsBeetwenMarkers(tmpItem, '<a', '</a>')
            for item in tmpItem:
                name = self.cleanHtmlStr(item)
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
                self.cacheLinks[cUrl].append({'name': name, 'url': url, 'need_resolve': 1})

        if len(self.cacheLinks[cUrl]):
            params = dict(cItem)
            params.update({'good_for_fav': False, 'url': cUrl, 'desc': desc, 'prev_url': cItem['url']})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        searchPattern = urllib.quote_plus(searchPattern)
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('/?s=') + urllib.quote_plus(searchPattern)
        cItem['category'] = 'list_items'
        self.listItems(cItem, 'explore_item')

    def getLinksForVideo(self, cItem):
        printDBG("Filma24IO.getLinksForVideo [%s]" % cItem)
        if 'trailer' in cItem:
            return self.up.getVideoLinkExt(cItem['url'])
        return self.cacheLinks.get(cItem['url'], [])

    def getVideoLinks(self, videoUrl):
        printDBG("Filma24IO.getVideoLinks [%s]" % videoUrl)
        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if videoUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name']

        if 0 == self.up.checkHostSupport(videoUrl):
            from Plugins.Extensions.IPTVPlayer.libs.unshortenit import unshorten
            uri, sts = unshorten(videoUrl)
            uri = str(uri)
            if self.cm.isValidUrl(uri):
                videoUrl = uri

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
        CHostBase.__init__(self, Filma24IO(), True, [])

    def withArticleContent(self, cItem):
        if 'prev_url' in cItem or cItem.get('category', '') == 'explore_item':
            return True
        else:
            return False
