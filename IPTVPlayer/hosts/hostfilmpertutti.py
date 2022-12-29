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
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
###################################################
# FOREIGN import
###################################################
import re
###################################################


def gettytul():
    return 'https://filmpertutti.club/'


class FilmPertutti(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'FilmPertutti', 'cookie': 'FilmPertutti.cookie'})
        self.MAIN_URL = 'https://www.filmpertutti.club/'
        self.DEFAULT_ICON_URL = 'https://thumbnails.webinfcdn.net/thumbnails/280x202/f/filmpertutti.click.png'
        self.cacheLinks = {}

    def getPage(self, baseUrl, addParams={}, post_data=None):
        return self.cm.getPage(baseUrl, addParams, post_data)

    def listMain(self, cItem):
        printDBG("FilmPertutti.listMain")
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        MAIN_CAT_TAB = [{'category': 'list_cats', 'title': 'Film', 'url': self.getFullUrl('/category/film/')},
                        {'category': 'list_cats', 'title': 'Serie TV', 'url': self.getFullUrl('/category/serie-tv/')},
                        {'category': 'list_items', 'title': 'Prime visioni', 'url': self.getFullUrl('/prime-visioni/')},
                        {'category': 'list_items', 'title': 'Aggiornamenti Serie TV', 'url': self.getFullUrl('/aggiornamenti-serie-tv/')},
                        {'category': 'search', 'title': _('Search'), 'search_item': True},
                        {'category': 'search_history', 'title': _('Search history'), }]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listCategories(self, cItem, nextCategory):
        printDBG("FilmPertutti.listCategories")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        params = dict(cItem)
        params.update({'good_for_fav': False, 'title': _('--All--'), 'category': nextCategory})
        self.addDir(params)

        data = self.cm.ph.getDataBeetwenNodes(data, ('<select', '>', '"cats"'), ('</select', '>'), False)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<option', '</option>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''<option[^>]+?src=['"]([^'^"]+?)['"]''')[0])
            if url == '':
                continue
            title = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': title, 'category': nextCategory, 'url': url})
            self.addDir(params)

    def listSubItems(self, cItem):
        printDBG("FilmPertutti.listSubItems")
        self.currList = cItem['sub_items']

    def listItems(self, cItem, nextCategory):
        printDBG("FilmPertutti.listItems [%s]" % cItem)
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        page = cItem.get('page', 1)

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'navigation'), ('</div', '>'), False)[1]
        nextPage = self.getFullUrl(self.cm.ph.getSearchGroups(nextPage, '''<a[^>]+?href=['"]([^"^']+?)["'][^>]*?>\s*%s\s*<''' % (page + 1), 1, True)[0])

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<ul', '>', 'posts'), ('</ul', '>'))
        for datItem in data:
            printDBG(datItem)
            printDBG('<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<')
            datItem = datItem.split('<li')
            for item in datItem:
                printDBG(item)
                printDBG('+++++++++++++++++++++++++++++++++++++')
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)["']''', 1, True)[0])
                if url == '':
                    continue
                icon = self.cm.ph.getSearchGroups(item, '''\ssrc=['"]([^"^']+?\.(?:jpe?g|png)(?:\?[^'^"]*?)?)['"]''')[0]
                if icon == '':
                    icon = self.cm.ph.getSearchGroups(item, '''thumbnail=['"]([^"^']+?\.(?:jpe?g|png)(?:\?[^'^"]*?)?)['"]''')[0]
                descTab = []
                item = self.cm.ph.getAllItemsBeetwenNodes(item, ('<div', '>'), ('</div', '>'))
                for t in item:
                    t = self.cleanHtmlStr(t)
                    if t != '':
                        descTab.append(t)

                title = descTab.pop(0) if len(descTab) else ''

                params = dict(cItem)
                params.update({'good_for_fav': True, 'title': title, 'category': nextCategory, 'url': url, 'desc': ' | '.join(descTab), 'icon': self.getFullIconUrl(icon)})
                self.addDir(params)

        if nextPage != '':
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _('Next page'), 'page': page + 1, 'url': nextPage})
            self.addDir(params)

    def exploreItem(self, cItem):
        printDBG("FilmPertutti.exploreItem")
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

        tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'embed-title'), ('</iframe', '>'), False, caseSensitive=False)
        for item in tmp:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0])
            if url == '':
                continue
            title = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': '%s - %s' % (cItem['title'], title), 'url': url, 'main_link': True, 'desc': desc, 'prev_url': cItem['url']})
            self.addVideo(params)

        self.cacheLinks = {}
        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '"pad"'), ('<div', '>', 'disqus_thread'), False)[1]
        data = data.split('</p>')

        episodes = []
        links = {}

        linksCategory = ''
        episodeName = ''
        reObj = re.compile('<br[^>]*?>')

        idx1 = -1
        idx2 = -1
        for item in data:
            idx1 = item.find('<strong')
            if idx1 > -1:
                idx2 = item.find('<br', idx1 + 7)
                if idx2 < 0:
                    idx2 = item.find('</strong', idx1 + 7)

            if -1 not in [idx1, idx2]:
                linksCategory = self.cleanHtmlStr(item[idx1:idx2])
                printDBG("linksCategory %s" % linksCategory)

            if 'Download:' in linksCategory:
                continue
            item = reObj.split(item)
            for tmp in item:
                episodeName = self.cleanHtmlStr(tmp[:tmp.find('<a')]).split(';', 1)[0]
                if '×' not in episodeName:
                    episodeName = ''
                else:
                    try:
                        episodeName = ensure_str(episodeName)
                    except Exception:
                        pass

                if linksCategory == '' and episodeName == '':
                    continue
                typeName = linksCategory.split(' – ', 1)[-1] if episodeName != '' else linksCategory

                tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<a', '</a>')
                for it in tmp:
                    name = self.cleanHtmlStr(it)
                    url = self.getFullUrl(self.cm.ph.getSearchGroups(it, '''href=['"]([^"^']+?)['"]''')[0])
                    if url == '' or '.addtoany.' in url:
                        continue
                    printDBG('>> | %s | %s | %s | > %s' % (typeName, episodeName, name, url))
                    if episodeName not in episodes:
                        episodes.append(episodeName)
                        links[episodeName] = []
                    links[episodeName].append({'name': '%s %s' % (typeName, name), 'url': strwithmeta(url, {'Referer': cUrl}), 'need_resolve': 1})

        printDBG('+++++++++++++++++++++++++++++++++++++++')
        printDBG(episodes)
        for episode in episodes:
            cacheKey = cUrl + '#' + episode
            self.cacheLinks[cacheKey] = links[episode]

            if episode == '':
                title = cItem['title'] + _(' - others links')
            else:
                title = cItem['title'] + ' ' + episode

            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': title, 'url': cUrl, 'cache_key': cacheKey, 'desc': desc, 'prev_url': cItem['url']})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        searchPattern = urllib_quote_plus(searchPattern)
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('/?s=') + urllib_quote_plus(searchPattern)
        cItem['category'] = 'list_items'
        self.listItems(cItem, 'explore_item')

    def getLinksForVideo(self, cItem):
        printDBG("FilmPertutti.getLinksForVideo [%s]" % cItem)
        if cItem.get('main_link', False):
            return self.up.getVideoLinkExt(cItem['url'])
        return self.cacheLinks.get(cItem['cache_key'], [])

    def getVideoLinks(self, videoUrl):
        printDBG("FilmPertutti.getVideoLinks [%s]" % videoUrl)
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
            try:
                videoUrl = strwithmeta(uri, videoUrl.meta)
            except Exception:
                printExc()

        return self.up.getVideoLinkExt(videoUrl)

    def getArticleContent(self, cItem, data=None):
        printDBG("Altadefinizione.getArticleContent [%s]" % cItem)
        retTab = []

        descTab = []
        itemsList = []

        url = cItem.get('prev_url', cItem['url'])
        if data == None:
            sts, data = self.getPage(url)
            if not sts:
                data = ''

        data = self.cm.ph.getDataBeetwenNodes(data, ('<section', '>', 'content'), ('</section', '>'), False)[1]
        icon = ''
        title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<h1', '</h1>')[1])

        item = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'rating'), ('<div', '>', 'stars'), False)[1])
        itemsList.append((_('Rating'), item))

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'subtitle'), ('<div', '>', 'clear'))[1]
        data = self.cm.ph.rgetAllItemsBeetwenNodes(data, ('</div', '>'), ('<div', '>', 'subtitle'))
        for item in data:
            item = item.split('</div>', 1)
            if len(item) != 2:
                continue
            key = self.cleanHtmlStr(item[0])
            val = self.cleanHtmlStr(item[1]).replace(' , ', ', ')
            if key == '' or val == '':
                continue
            if key.lower() in ['approfondimento', 'trama']:
                descTab.append(key + '[/br]' + val)
            else:
                itemsList.append((key, val))

        if title == '':
            title = cItem['title']
        if icon == '':
            icon = cItem.get('icon', self.DEFAULT_ICON_URL)

        return [{'title': self.cleanHtmlStr(title), 'text': '[/br][/br]'.join(descTab), 'images': [{'title': '', 'url': self.getFullUrl(icon)}], 'other_info': {'custom_items_list': itemsList}}]

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
        elif category == 'list_cats':
            self.listCategories(self.currItem, 'list_items')
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
        CHostBase.__init__(self, FilmPertutti(), True, [])

    def withArticleContent(self, cItem):
        if 'prev_url' in cItem or cItem.get('category', '') == 'explore_item':
            return True
        else:
            return False
