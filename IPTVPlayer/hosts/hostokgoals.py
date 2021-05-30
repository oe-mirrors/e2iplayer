# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
###################################################

###################################################
# FOREIGN import
###################################################
import urllib
try:
    import json
except Exception:
    import simplejson as json
from Components.config import config
###################################################


def gettytul():
    return 'http://okgoals.com/'


class OkGoals(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'OkGoals.tv', 'cookie': 'filisertv.cookie'})

        self.HEADER = {'User-Agent': 'Mozilla/5.0', 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.MAIN_URL = 'http://www.okgoals.com/'
        self.DEFAULT_ICON_URL = self.getFullUrl('/okgoals_logo.jpg')

        self.MAIN_CAT_TAB = [{'category': 'list_items', 'title': _('Main'), 'url': self.getFullUrl('index.php')},
                             {'category': 'list_categories', 'title': _('Categories'), 'url': self.getMainUrl()},
                             {'category': 'search', 'title': _('Search'), 'search_item': True, },
                             {'category': 'search_history', 'title': _('Search history'), },
                            ]

    def getFullUrl(self, url):
        if url.startswith('//'):
            url = 'http:' + url
        url = CBaseHostClass.getFullUrl(self, url)
        return url

    def getBiggerImage(self, icon):
        ICON_PATH = [
                    {'orig': 'images/it.png', 'new': 'https://www.bandiere-mondo.it/data/flags/h80/it.png'},
                    {'orig': 'images/pt.png', 'new': 'https://www.bandiere-mondo.it/data/flags/h80/pt.png'},
                    {'orig': 'images/fr.png', 'new': 'https://www.bandiere-mondo.it/data/flags/h80/fr.png'},
                    {'orig': 'images/de.png', 'new': 'https://www.bandiere-mondo.it/data/flags/h80/de.png'},
                    {'orig': 'images/cl.png', 'new': 'https://www.calcioweb.eu/wp-content/uploads/2014/04/Logo-Champions-League-bianco.jpg'},
                    {'orig': 'images/uef.png', 'new': 'https://img.uefa.com/imgml/uefaorg/new/logo.png'},
                     ]

        for i in ICON_PATH:
            if i['orig'] in icon:
                icon = i['new']
                break

        return self.getFullIconUrl(icon)

    def listCategories(self, cItem, nextCategory):
        printDBG("OkGoals.listCategories")

        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenMarkers(data, '<ul id="mediamenu">', '</ul>')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>', withMarkers=True)
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            if not self.cm.isValidUrl(url):
                continue
            icon = self.getBiggerImage(self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(item)
            title = _(title.capitalize())
            params = {'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'icon': icon}
            self.addDir(params)

    def listItems(self, cItem, nextCategory):
        printDBG("OkGoals.listItems")

        page = cItem.get('page', 1)

        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return

        nextPage = self.cm.ph.getDataBeetwenMarkers(data, '<div class="wpnavi">', '<div class="clear">')[1]
        nextPage = self.cm.ph.getSearchGroups(nextPage, '''<a[^>]+?href=["']([^'^"]+?)["'][^>]*?>\s*{0}\s*</a>'''.format(page + 1))[0]

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div id="matchlistng">', '</a>', withMarkers=False)
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            icon = self.getBiggerImage(self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0])
            desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''alt=['"]([^'^"]+?)['"]''')[0].replace('icon', ''))
            title = self.cleanHtmlStr(item)

            params = {'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'icon': icon, 'desc': desc}
            self.addDir(params)

        if nextPage != '':
            params = dict(cItem)
            params.update({'title': _('Next page'), 'page': page + 1, 'url': self.getFullUrl(nextPage)})
            self.addDir(params)

    def exploreItem(self, cItem):
        printDBG("OkGoals.exploreItem")

        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return

        tmp = self.cm.ph.getDataBeetwenMarkers(data, ('<div', '>', 'matchcontainer'), '</div>', False)[1]
        tmp = tmp.split('</script>')
        for item in tmp:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''['"]([^'^"]*?//config\.playwire\.com[^'^"]+?\.json)['"]''')[0])

            if not url:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''loadSource\(['"]([^'^"]+?)['"]''')[0])

            if not url:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, "src\s?=\s?['\"]([^'^\"]+?)['\"]")[0])

            if self.cm.isValidUrl(url):
                title = cItem['title']
                params = {'good_for_fav': True, 'title': title, 'url': url}
                self.addVideo(params)

    def getLinksForVideo(self, cItem):
        printDBG("OkGoals.getLinksForVideo [%s]" % cItem)
        urlTab = []
        videoUrl = cItem['url']

        if 'm3u8' in videoUrl:
            params = getDirectM3U8Playlist(videoUrl)
            if params:
                printDBG(str(params))
                urlTab.extend(params)
                return urlTab

        if 'playwire.com' in videoUrl:
            sts, data = self.cm.getPage(videoUrl)
            if not sts:
                return []
            try:
                data = byteify(json.loads(data))
                if 'content' in data:
                    url = data['content']['media']['f4m']
                else:
                    url = data['src']
                sts, data = self.cm.getPage(url)
                baseUrl = self.cm.ph.getDataBeetwenMarkers(data, '<baseURL>', '</baseURL>', False)[1].strip()
                data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<media ', '>')
                for item in data:
                    url = self.cm.ph.getSearchGroups(item, '''url=['"]([^'^"]+?)['"]''')[0]
                    height = self.cm.ph.getSearchGroups(item, '''height=['"]([^'^"]+?)['"]''')[0]
                    bitrate = self.cm.ph.getSearchGroups(item, '''bitrate=['"]([^'^"]+?)['"]''')[0]
                    name = '[%s] bitrate:%s height: %s' % (url.split('.')[-1], bitrate, height)
                    if not url.startswith('http'):
                        url = baseUrl + '/' + url
                    if url.startswith('http'):
                        if 'm3u8' in url:
                            hlsTab = getDirectM3U8Playlist(url)
                            for idx in range(len(hlsTab)):
                                hlsTab[idx]['name'] = '[hls] bitrate:%s height: %s' % (hlsTab[idx]['bitrate'], hlsTab[idx]['height'])
                            urlTab.extend(hlsTab)
                        else:
                            urlTab.append({'name': name, 'url': url})
            except Exception:
                printExc()
        elif videoUrl.startswith('http'):
            urlTab.extend(self.up.getVideoLinkExt(videoUrl))
        return urlTab

    def getVideoLinks(self, videoUrl):
        printDBG("OkGoals.getVideoLinks [%s]" % videoUrl)
        urlTab = []
        return urlTab

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("KissCartoonMe.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        url = self.getFullUrl('search.php?dosearch=yes&search_in_archives=yes&title=') + urllib.quote_plus(searchPattern)
        sts, data = self.cm.getPage(url)
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenMarkers(data, 'Founded matches', '<div class="clear">')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>', withMarkers=True)
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(item)

            params = {'good_for_fav': True, 'category': 'explore_item', 'title': title, 'url': url}
            self.addDir(params)

    def getFavouriteData(self, cItem):
        printDBG('OkGoals.getFavouriteData')
        return json.dumps(cItem)

    def getLinksForFavourite(self, fav_data):
        printDBG('OkGoals.getLinksForFavourite')
        links = []
        try:
            cItem = byteify(json.loads(fav_data))
            links = self.getLinksForVideo(cItem)
        except Exception:
            printExc()
        return links

    def setInitListFromFavouriteItem(self, fav_data):
        printDBG('OkGoals.setInitListFromFavouriteItem')
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

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})
        elif category == 'list_categories':
            self.listCategories(self.currItem, 'list_items')
        elif 'list_items' == category:
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
        CHostBase.__init__(self, OkGoals(), True, [])
