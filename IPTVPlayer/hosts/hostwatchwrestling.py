# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
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


###################################################
# Config options for HOST
###################################################

def GetConfigList():
    optionList = []
    return optionList
###################################################


def gettytul():
    return 'http://watchwrestlingup.live/'


class Watchwrestling(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'Watchwrestling', 'cookie': 'Watchwrestling.cookie'})
        self.serversCache = []

        self.MAIN_URL = 'http://watchwrestlingup.live/'
        self.SRCH_URL = self.getFullUrl('index.php?s=')
        self.DEFAULT_ICON_URL = 'http://watchwrestlingup.live/wp-content/uploads/2015/05/WatchWrestlingUp.in_1.png'

        self.SORT_TAB = [{'sort': 'date', 'title': _('Order by date')},
                         {'sort': 'views', 'title': _('Order by views')},
                         {'sort': 'likes', 'title': _('Order by likes')},
                         {'sort': 'comments', 'title': _('Order by comments')}
                        ]

    def listMain(self):
        printDBG("Watchwrestling.listMain")
        sts, data = self.cm.getPage(self.MAIN_URL)
        if not sts:
            return

        menu = self.cm.ph.getDataBeetwenMarkers(data, '<!-- end #header-->', '<!-- end #main-nav -->', False)[1]
        items = re.findall("(<li.*</a>(</li>|\n<ul(.|\n)*?</ul>))", menu)

        for i in items:
            if 'Report Issues' in i[0]:
                continue
            if '<ul' in i[0]:
                # contains a sub menu
                si = re.findall("(<li.*</a>)", i[0])
                subItems = []
                title_menu = self.cleanHtmlStr(si[0])

                for j in range(1, len(si)):
                    url = re.findall("href=\"(.*?)\"", si[j])
                    if url:
                        title = self.cleanHtmlStr(si[j])
                        params = {'title': title, 'url': url[0], 'category': 'list_filters'}
                        printDBG(str(params))
                        subItems.append(params)

                params = {'title': title_menu, 'category': 'list_subitems', 'sub_items': subItems}
                printDBG(str(params))
                self.addDir(params)

            else:
                # single item
                url = re.findall("href=\"(.*?)\"", i[0])
                if url:
                    title = self.cleanHtmlStr(i[0])
                    params = {'title': title, 'url': url[0], 'category': 'list_filters'}
                    printDBG(str(params))
                    self.addDir(params)

    def listSubItems(self, cItem):
        printDBG("Watchwrestling.listMain")

        for i in cItem['sub_items']:
            printDBG(str(i))
            self.addDir(i)

    def listFilters(self, cItem, category):
        printDBG("Watchwrestling.listFilters")
        cItem = dict(cItem)
        cItem['category'] = category
        self.listsTab(self.SORT_TAB, cItem)

    def listMovies(self, cItem, nextCategory):
        printDBG("Watchwrestling.listMovies")
        url = cItem['url']
        page = cItem.get('page', 1)
        if page > 1:
            url += 'page/%d/' % page
        if '?' in url:
            url += '&'
        else:
            url += '?'
        url += 'orderby=%s' % cItem['sort']

        sts, data = self.cm.getPage(url)
        if not sts:
            return

        if ('/page/%d/' % (page + 1)) in data:
            nextPage = True
        else:
            nextPage = False

        if '<div class="loop-nav pag-nav">' in data:
            m2 = '<div class="loop-nav pag-nav">'
        else:
            m2 = '<div id="sidebar"'
        data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="nag cf">', m2, False)[1]

        data = data.split('<div id="post-')
        if len(data):
            del data[0]

        for item in data:
            tmp = item.split('<p class="stats">')
            url = self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0]
            icon = self.cm.ph.getSearchGroups(item, 'src="([^"]+?)"')[0]
            title = self.cm.ph.getSearchGroups(item, 'title="([^"]+?)"')[0]
            desc = tmp[-1].split('<p class="entry-summary">')[0]
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': nextCategory, 'title': self.cleanHtmlStr(title), 'url': self.getFullUrl(url), 'desc': self.cleanHtmlStr(desc), 'icon': self.getFullUrl(icon)})
            printDBG(str(params))
            self.addDir(params)

        if nextPage:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _('Next page'), 'page': page + 1})
            self.addDir(params)

    def listServers(self, cItem, nextCategory):
        printDBG("Watchwrestling.listServers [%s]" % cItem)
        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return

        matchObj = re.compile('href="([^"]+?)"[^>]*?>([^>]+?)</a>')
        if 'iframe' in data:
            frame_url = re.findall("<iframe src=['\"](.*?)['\"]", data)
            if frame_url:
                sts, data = self.cm.getPage(frame_url[0])
                if not sts:
                    return
                data = self.cm.ph.getDataBeetwenMarkers(data, '<!-- Type below this </br> -->', '<!-- Type above this -->', False)[1]

                data = data.split('<span')
                for item in data:
                    item2 = '<span' + item
                    sts, serverName = self.cm.ph.getDataBeetwenMarkers(item2, '<span', '</span>', True)
                    if sts:
                        serverName = self.cleanHtmlStr(serverName)
                    else:
                        serverName = ''
                    parts = matchObj.findall(item)
                    partsTab = []
                    for part in parts:
                        title = serverName + ' ' + part[1]
                        params = dict(cItem)
                        params.update({'good_for_fav': False, 'title': title, 'url': part[0], 'Referer': cItem['url']})
                        printDBG(params)
                        self.addVideo(params)

        else:
            data = self.cm.ph.getDataBeetwenMarkers(data, ('<div', '>', 'entry-content'), '<div id="extras">', False)[1]
            data = data.split('</p>')

            for item in data:
                sts, serverName = self.cm.ph.getDataBeetwenMarkers(item, '<span', '</span>', True)
                if sts:
                    serverName = self.cleanHtmlStr(serverName)
                else:
                    serverName = ''
                parts = matchObj.findall(item)
                partsTab = []
                for part in parts:
                    title = serverName + ' ' + part[1]
                    params = dict(cItem)
                    params.update({'good_for_fav': False, 'title': title, 'url': part[0], 'Referer': cItem['url']})
                    printDBG(params)
                    self.addVideo(params)

    def listParts(self, cItem):
        printDBG("Watchwrestling.listServers [%s]" % cItem)
        partIdx = cItem['part_idx']
        self.listsTab(self.serversCache[partIdx], cItem, 'video')

    def listLiveStreams(self, cItem):
        printDBG("Watchwrestling.listLiveStreams [%s]" % cItem)
        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return
        sp = '<div style="text-align: center;">'
        data = self.cm.ph.getDataBeetwenMarkers(data, sp, '</div>', False)[1]
        data = re.compile('href="([^"]+?)"[^>]*?>([^>]+?)</a>').findall(data)
        for item in data:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': item[1], 'url': item[0], 'Referer': cItem['url'], 'live': True})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        searchPattern = urllib.quote_plus(searchPattern)
        cItem = dict(cItem)
        cItem['url'] = self.SRCH_URL + searchPattern
        cItem['sort'] = searchType
        self.listMovies(cItem, 'list_server')

    def _clearData(self, data):
        data = re.sub("<!--[\s\S]*?-->", "", data)
        data = re.sub("/\*[\s\S]*?\*/", "", data)
        return data

    def getLinksForVideo(self, cItem):
        printDBG("Watchwrestling.getLinksForVideo [%s]" % cItem)
        urlTab = []
        url = cItem['url']
        Referer = cItem.get('Referer', '')
        if 1 != self.up.checkHostSupport(url):
            tries = 0
            while tries < 3:
                sts, data = self.cm.getPage(url, {'header': {'Referer': Referer, 'User-Agent': 'Mozilla/5.0'}})
                if not sts:
                    return urlTab
                data = data.replace('// -->', '')
                data = self._clearData(data)
                #printDBG(data)
                if 'eval(unescape' in data:
                    data = urllib.unquote(self.cm.ph.getSearchGroups(data, '''eval\(unescape\(['"]([^"^']+?)['"]''')[0])
                url = self.cm.ph.getSearchGroups(data, '''<iframe[^>]*?src=['"]([^"^']+?)['"]''', 1, True)[0]
                if 'protect.cgi' in url:
                    Referer = cItem['url']
                else:
                    break
                tries += 1
        url = strwithmeta(url)
        url.meta['Referer'] = Referer
        url.meta['live'] = cItem.get('live', False)

        urlTab.append({'name': cItem['title'], 'url': url, 'need_resolve': 1})
        return urlTab

    def getVideoLinks(self, baseUrl):
        printDBG("Watchwrestling.getVideoLinks [%s]" % baseUrl)
        urlTab = []

        url = strwithmeta(baseUrl)
        if url.meta.get('live'):
            urlTab = self.up.getAutoDetectedStreamLink(url)
        else:
            urlTab = self.up.getVideoLinkExt(url)
        return urlTab

    def getFavouriteData(self, cItem):
        printDBG('Watchwrestling.getFavouriteData')
        return json.dumps(cItem)

    def getLinksForFavourite(self, fav_data):
        printDBG('Watchwrestling.getLinksForFavourite')
        links = []
        try:
            cItem = byteify(json.loads(fav_data))
            links = self.getLinksForVideo(cItem)
        except Exception:
            printExc()
        return links

    def setInitListFromFavouriteItem(self, fav_data):
        printDBG('Watchwrestling.setInitListFromFavouriteItem')
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
        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

        #MAIN MENU
        if name == None:
            self.listMain()
        elif category == 'list_subitems':
            self.listSubItems(self.currItem)
        elif category == 'list_filters':
            self.listFilters(self.currItem, 'list_movies')
        #MOVIES
        elif category == 'list_movies':
            self.listMovies(self.currItem, 'list_server')
        elif category == 'list_server':
            self.listServers(self.currItem, 'list_parts')
        elif category == 'list_parts':
            self.listParts(self.currItem)
        #LIVE
        elif category == 'live':
            self.listLiveStreams(self.currItem)
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
        CHostBase.__init__(self, Watchwrestling(), True, [])

    def getSearchTypes(self):
        searchTypesOptions = []
        searchTypesOptions.append((_("DATE"), "date"))
        searchTypesOptions.append((_("VIEWS"), "views"))
        searchTypesOptions.append((_("LIKES"), "likes"))
        searchTypesOptions.append((_("COMMENTS"), "comments"))
        return searchTypesOptions
