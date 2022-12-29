# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
###################################################
# FOREIGN import
###################################################
try:
    import json
except Exception:
    import simplejson as json
###################################################


def gettytul():
    return 'http://kreskoweczki.pl/'


class KreskoweczkiPL(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': '  KreskoweczkiPL.tv', 'cookie': 'kreskoweczkipl.cookie'})
        self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.abcCache = {}

        self.HEADER = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:68.0) Gecko/20100101 Firefox/68.0', 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})

        self.MAIN_URL = 'https://www.kreskoweczki.pl/'
        self.DEFAULT_ICON = "http://svn.sd-xbmc.org/filedetails.php?repname=sd-xbmc&path=%2Ftrunk%2Fxbmc-addons%2Fsrc%2Fxbmc-addons%2Fkreskoweczki.png&rev=936&peg=936"

        self.MAIN_CAT_TAB = [{'icon': self.DEFAULT_ICON, 'category': 'list_abc', 'title': 'Alfabetycznie', 'url': self.MAIN_URL},
                             {'icon': self.DEFAULT_ICON, 'category': 'list_items', 'title': 'Ostatnio dodane', 'url': self.MAIN_URL + 'ostatnio-dodane/wszystkie'},
                             {'icon': self.DEFAULT_ICON, 'category': 'list_items', 'title': 'Anime', 'url': self.MAIN_URL + 'typ/anime/'},
                             {'icon': self.DEFAULT_ICON, 'category': 'list_items', 'title': 'Bajki', 'url': self.MAIN_URL + 'typ/toon/'},
                             {'icon': self.DEFAULT_ICON, 'category': 'list_items', 'title': 'Seriale', 'url': self.MAIN_URL + 'typ/serial/'},
                             {'icon': self.DEFAULT_ICON, 'category': 'list_items', 'title': 'Pozostałe', 'url': self.MAIN_URL + 'typ/pozostale/'},
                             {'icon': self.DEFAULT_ICON, 'category': 'search', 'title': _('Search'), 'search_item': True},
                             {'icon': self.DEFAULT_ICON, 'category': 'search_history', 'title': _('Search history')}]
        self.needProxy = None

    def getPage(self, url, params={}, post_data=None):
        if 'header' not in params:
            HTTP_HEADER = dict(self.HEADER)
            params.update({'header': HTTP_HEADER})

        sts, data = self.cm.getPage(url, params, post_data)
        if sts and None == data:
            sts = False
        if sts and 'Duze obciazenie!' in data:
            SetIPTVPlayerLastHostError(self.cleanHtmlStr(data))
        return sts, data

    def getFullIconUrl(self, url):
        return self.getFullUrl(url)

    def getFullUrl(self, url):
        return CBaseHostClass.getFullUrl(self, url)

    def listABC(self, cItem, category):
        printDBG("KreskoweczkiPL.listABC")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="category-list one-quarter">', '</ul>')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
        for item in data:
            title = self.cleanHtmlStr(item)
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            params = dict(cItem)
            params.update({'category': category, 'title': title, 'url': url})
            self.addDir(params)

    def listTitles(self, cItem, nextCategory):
        printDBG("KreskoweczkiPL.listTitles")
        subCat = cItem.get('sub_cat', '')
        tab = self.abcCache.get(subCat, [])
        params = dict(cItem)
        params['category'] = nextCategory
        self.listsTab(tab, params)

    def listItems(self, cItem):
        printDBG("KreskoweczkiPL.listItems")

        url = cItem['url']
        page = cItem.get('page', 1)

        post_data = cItem.get('post_data', None)
        sts, data = self.getPage(url, {}, post_data)
        if not sts:
            return

        if '/odcinki' not in url:
            url = self.cm.ph.getDataBeetwenNodes(data, ('<a', '</a>', 'Lista Odcinków'), ('</div', '>'))[1]
            url = self.getFullUrl(self.cm.ph.getSearchGroups(url, '''href=['"]([^'^"]+?)['"]''')[0])
            if url != '':
                sts, data = self.getPage(url)
                if not sts:
                    return

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'pagination'), ('</div', '>'))[1]
        nextPage = self.getFullUrl(self.cm.ph.getSearchGroups(nextPage, '''href=['"]([^'^"]+?)['"][^>]*?>%s<''' % (page + 1))[0])

        videoMarker = '''/([0-9]+?)/'''

        video = True
        m1 = '<a class="item" '
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, m1, '</li>')
        for item in data:
            video = True
            if '' == self.cm.ph.getSearchGroups(item, videoMarker)[0]:
                video = False
            # icon
            icon = self.cm.ph.getSearchGroups(item, '''url\(\s*?['"]([^'^"]+?)['"]''')[0]
            if icon == '':
                icon = self.cm.ph.getSearchGroups(item, '''data-bg-url=['"]([^'^"]+?\.jpe?g(:?\?[^'^"]*?)?)['"]''')[0]
            if icon == '':
                icon = cItem.get('icon', '')
            # url
            url = self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0]
            if url == '':
                continue
            #title
            desc = []
            title1 = []
            title2 = []
            item = self.cm.ph.getAllItemsBeetwenMarkers(item, '<div', '</div>')
            for t in item:
                if 'category-nam' in t:
                    t = self.cleanHtmlStr(t).replace('Seria:', '').replace('Tytuł:', '')
                    if t != '':
                        title1.append(t)
                elif '"header"' in t or '"number"' in t:
                    t = self.cleanHtmlStr(t.split('</b>', 1)[-1])
                    if t != '':
                        title2.append(t)
                else:
                    t = self.cleanHtmlStr(t.replace('</span>', '[/br]'))
                    if t != '':
                        desc.append(t)

            title = ' '.join(title1)
            if len(title2):
                desc.insert(0, '  '.join(title2))
            #title = self.cm.ph.getDataBeetwenMarkers(item, '<div class="category-name"', '</div>')[1]
            #if title == '': title = self.cm.ph.getSearchGroups(item, '''title=['"]([^'^"]+?)['"]''')[0]
            #if title == '': title = self.cm.ph.getDataBeetwenMarkers(item, '<a ', '</a>')[1]
            #title = self.cm.ph.getDataBeetwenMarkers(item, '<span class="pm-category-name', '</span>')[1] + ' ' + title

            params = dict(cItem)
            params.pop('post_data', None)
            params.update({'good_for_fav': True, 'page': 1, 'title': self.cleanHtmlStr(title), 'url': self.getFullUrl(url), 'icon': self.getFullUrl(icon), 'desc': '[/br]'.join(desc).replace('[/br][/br]', '[/br]')})

            if video:
                #params.update({'desc':self.cleanHtmlStr(item)})
                self.addVideo(params)
            else:
                #params.update({'desc':self.cleanHtmlStr(item.replace('</b>', '[/br]'))})
                self.addDir(params)

        if nextPage != '':
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _('Next page'), 'url': nextPage, 'page': page + 1})
            self.addDir(params)

    def getLinksForVideo(self, cItem):
        printDBG("KreskoweczkiPL.getLinksForVideo [%s]" % cItem)
        urlTab = []

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return []

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>', caseSensitive=False)
        for item in data:
            url = self.cm.ph.getSearchGroups(item, '''action="([^"]+?)"''')[0]
            vid = self.cm.ph.getSearchGroups(item, '''value="([0-9]+?)"''')[0]
            if url != '' and vid != '':
                url = strwithmeta(self.getFullUrl(url), {'Referer': cItem['url'], 'vid': vid})
                urlTab.append({'name': self.cleanHtmlStr(item), 'url': url, 'need_resolve': 1})

        return urlTab

    def getVideoLinks(self, videoUrl):
        printDBG("KreskoweczkiPL.getVideoLinks [%s]" % videoUrl)

        videoUrl = strwithmeta(videoUrl)
        vid = videoUrl.meta.get('vid', '')
        ref = videoUrl.meta.get('Referer', '')
        if '' == vid:
            return []

        HEADER = dict(self.HEADER)
        HEADER['Referer'] = ref
        post_data = {'source_id': vid}
        sts, data = self.getPage(videoUrl, {'header': HEADER}, post_data)
        if not sts:
            return []

        urlTab = []
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(data, '<iframe', '</iframe>', caseSensitive=False)
        for item in tmp:
            videoUrl = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'src="([^"]+?)"', ignoreCase=True)[0])
            if videoUrl == '':
                videoUrl = self.getFullUrl(self.cm.ph.getSearchGroups(item, "src='([^']+?)'", ignoreCase=True)[0])
            if 1 != self.up.checkHostSupport(videoUrl):
                continue
            urlTab.extend(self.up.getVideoLinkExt(videoUrl))

        if 0 == len(urlTab):
            tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'playerholder'), ('</div', '>'), caseSensitive=False)
            printDBG(tmp)
            for item in tmp:
                videoUrl = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"', ignoreCase=True)[0])
                if videoUrl == '':
                    videoUrl = self.getFullUrl(self.cm.ph.getSearchGroups(item, "href='([^']+?)'", ignoreCase=True)[0])
                if 1 != self.up.checkHostSupport(videoUrl):
                    continue
                urlTab.extend(self.up.getVideoLinkExt(videoUrl))

        return urlTab

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("KreskoweczkiPL.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['category'] = 'list_items'
        cItem['url'] = self.getFullUrl('/szukaj?query=' + urllib_quote_plus(searchPattern))
        self.listItems(cItem)

    def getFavouriteData(self, cItem):
        printDBG('KreskoweczkiPL.getFavouriteData')
        return json.dumps(cItem)

    def getLinksForFavourite(self, fav_data):
        printDBG('KreskoweczkiPL.getLinksForFavourite')
        links = []
        try:
            cItem = byteify(json.loads(fav_data))
            links = self.getLinksForVideo(cItem)
        except Exception:
            return self.getLinksForVideo({'url': fav_data})
        return links

    def setInitListFromFavouriteItem(self, fav_data):
        printDBG('KreskoweczkiPL.setInitListFromFavouriteItem')
        try:
            params = byteify(json.loads(fav_data))
        except Exception:
            params = {}
            printExc()
        self.addDir(params)
        return True

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')
        filter = self.currItem.get("filter", '')

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})
        elif category == 'list_abc':
            self.listABC(self.currItem, 'list_items')
        elif category == 'list_titles':
            self.listTitles(self.currItem, 'list_items')
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
        # for now we must disable favourites due to problem with links extraction for types other than movie
        CHostBase.__init__(self, KreskoweczkiPL(), True, favouriteTypes=[CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO])
