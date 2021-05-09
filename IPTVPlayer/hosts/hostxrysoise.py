# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify
from Plugins.Extensions.IPTVPlayer.libs.pCommon import CParsingHelper
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
from Components.config import config, ConfigSelection
###################################################


###################################################
# E2 GUI COMMPONENTS
###################################################
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.movieshdco_sortby = ConfigSelection(default="date", choices=[("date", _("Lastest")), ("views", _("Most viewed")), ("duree", _("Longest")), ("rate", _("Top rated")), ("random", _("Random"))])


def GetConfigList():
    optionList = []
    return optionList
###################################################


def gettytul():
    return 'https://xrysoi.tv/'


class XrysoiSE(CBaseHostClass):
    HEADER = {'User-Agent': 'Mozilla/5.0', 'Accept': 'text/html'}
    AJAX_HEADER = dict(HEADER)
    AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})

    MAIN_URL = 'https://xrysoi.tv/'
    SEARCH_SUFFIX = '?s='

    MAIN_CAT_TAB = [{'category': 'movies', 'mode': 'movies', 'title': 'Ταινιες', 'url': '', 'icon': ''},
                    {'category': 'list_items', 'mode': 'series', 'title': 'Ξένες σειρές', 'url': MAIN_URL + 'category/ξένες-σειρές/', 'icon': ''},
                    #{'category':'list_items',     'mode':'collection', 'title': 'Συλλογες',     'url':MAIN_URL + 'category/collection/',      'icon':''},
                    {'category': 'search', 'title': _('Search'), 'search_item': True},
                    {'category': 'search_history', 'title': _('Search history')}]

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'XrysoiSE.tv', 'cookie': 'XrysoiSEtv.cookie'})
        self.DEFAULT_ICON_URL = self.MAIN_URL + 'wp-content/uploads/2015/03/logo-GM.png'
        self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.cacheFilters = {}
        self.cacheLinks = {}

    def _getFullUrl(self, url):
        if 0 < len(url) and not url.startswith('http'):
            url = self.MAIN_URL + url
        if not self.MAIN_URL.startswith('https://'):
            url = url.replace('https://', 'http://')
        return url

    def cleanHtmlStr(self, data):
        data = data.replace('&nbsp;', ' ')
        data = data.replace('&nbsp', ' ')
        return CBaseHostClass.cleanHtmlStr(data)

    def listsTab(self, tab, cItem, type='dir'):
        printDBG("XrysoiSE.listsTab")
        for item in tab:
            params = dict(cItem)
            params.update(item)
            params['name'] = 'category'
            if type == 'dir':
                self.addDir(params)
            else:
                self.addVideo(params)

    def fillCategories(self):
        printDBG("XrysoiSE.fillCategories")
        self.cacheFilters = {}
        sts, data = self.cm.getPage(self.MAIN_URL)
        if not sts:
            return

        moviesTab = [{'title': '2019', 'url': self._getFullUrl('category/tainiesonline/2019/')},
                     {'title': '2018', 'url': self._getFullUrl('category/tainiesonline/2018/')},
                     {'title': '2017', 'url': self._getFullUrl('category/tainiesonline/2017/')},
                     {'title': '2016', 'url': self._getFullUrl('category/2016/')},
                     {'title': '2013-2015', 'url': self._getFullUrl('category/new-good/')},
                     {'title': 'Ελληνικές Ταινίες', 'url': self._getFullUrl('category/ελλ-ταινίες/')}]
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '>Ταινιες<', '</ul>', False)[1]
        tmp = re.compile('<a[^>]*?href="([^"]+?)"[^>]*?>([^<]+?)<').findall(tmp)
        for item in tmp:
            if item[0].endswith('collection/'):
                continue # at now we are not able to handle colletion
            if item[0].endswith('προσεχώς/'):
                continue # soon, so there is only trailer link available
            moviesTab.append({'title': self.cleanHtmlStr(item[1]), 'url': self._getFullUrl(item[0])})

        moviesTab.append({'title': 'Κινούμενα Σχέδια (με μετάφραση)', 'url': self._getFullUrl('category/κιν-σχέδια/')})
        moviesTab.append({'title': 'Κινούμενα Σχέδια (με υπότιτλους)', 'url': self._getFullUrl('category/κιν-σχέδια-subs/')})
        moviesTab.append({'title': 'Anime Movies', 'url': self._getFullUrl('category/animemovies/')})
        self.cacheFilters['movies'] = moviesTab

    def listMoviesCategory(self, cItem, nextCategory):
        printDBG("XrysoiSE.listMoviesCategory")
        if {} == self.cacheFilters:
            self.fillCategories()

        cItem = dict(cItem)
        cItem['category'] = nextCategory
        self.listsTab(self.cacheFilters.get('movies', []), cItem)

    def listItems(self, cItem, nextCategory='explore_item'):
        printDBG("XrysoiSE.listItems")
        page = cItem.get('page', 1)

        url = cItem['url']
        if page > 1:
            url += '/page/' + str(page)

        if 'url_suffix' in cItem:
            url += cItem['url_suffix']

        sts, data = self.cm.getPage(url) #, {'header':self.AJAX_HEADER}
        if not sts:
            return

        nextPage = self.cm.ph.getDataBeetwenReMarkers(data, re.compile('''class=['"]pages['"]'''), re.compile('</div>'), False)[1]
        if 'rel="next"' in nextPage:
            nextPage = True
        else:
            nextPage = False

        data = self.cm.ph.getDataBeetwenMarkers(data, '<h1 class=', 'class="filmborder">', False)[1]
        data = data.split('class="moviefilm">')
        for item in data:
            url = self._getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0])
            icon = self._getFullUrl(self.cm.ph.getSearchGroups(item, 'src="([^"]+?)"')[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'alt="([^"]+?)"')[0])
            #if 'search' == cItem.get('mode'):
            #    if '-collection' in url: continue
            if url.startswith('http'):
                params = dict(cItem)
                params.update({'category': nextCategory, 'good_for_fav': True, 'title': title, 'url': url, 'icon': icon})
                self.addDir(params)
        if nextPage:
            params = dict(cItem)
            params.update({'title': _("Next page"), 'page': page + 1})
            self.addDir(params)

    def exploreItem(self, cItem):
        printDBG("XrysoiSE.exploreItem")
        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return

        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, '<meta[^>]*?property="og:description"[^>]*?content="([^"]+?)"')[0])
        title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, '<meta[^>]*?property="og:title"[^>]*?content="([^"]+?)"')[0])
        if '' == title:
            title = cItem['title']

        # trailer link extraction
        trailerMarker = '/trailer'
        sts, trailer = self.cm.ph.getDataBeetwenMarkers(data, trailerMarker, '</iframe>', False, False)
        if sts:
            trailer = self.cm.ph.getSearchGroups(trailer, '<iframe[^>]+?src="([^"]+?)"', 1, ignoreCase=True)[0]
            if trailer.startswith('//'):
                trailer = 'http:' + trailer
            if trailer.startswith('http'):
                params = dict(cItem)
                params['title'] = 'TRAILER'
                params['mode'] = 'trailer'
                params['links'] = [{'name': 'TRAILER', 'url': trailer, 'need_resolve': 1}]
                params['desc'] = desc
                self.addVideo(params)

        # check
        ms1 = '<b>ΠΕΡΙΛΗΨΗ</b>'
        if ms1 in data:
            m1 = ms1
        elif trailerMarker in data:
            m1 = trailerMarker
        else:
            m1 = '<!-- END TAG -->'
        sts, linksData = self.cm.ph.getDataBeetwenMarkers(data, m1, '<center>', False, False)
        if not sts:
            return

        mode = cItem.get('mode', 'unknown')
        # find all links for this season
        eLinks = {}
        episodes = []
        if '-collection' in cItem['url']:
            mode = 'collect_item'
            spTab = [re.compile('<b>'), re.compile('<div[\s]+class="separator"[\s]+style="text-align\:[\s]+center;">'), re.compile('<div[\s]+style="text-align\:[\s]+center;">')]
            for sp in spTab:
                if None != sp.search(linksData):
                    break

            collectionItems = sp.split(linksData)
            if len(collectionItems) > 0:
                del collectionItems[0]
            linksData = ''
            for item in collectionItems:
                itemTitle = item.find('<')
                if itemTitle < 0:
                    continue
                itemTitle = self.cleanHtmlStr(item[:itemTitle])
                linksData = re.compile('<a[^>]*?href="([^"]+?)"[^>]*?>').findall(item)
                links = []
                for itemUrl in linksData:
                    if 1 != self.up.checkHostSupport(itemUrl):
                        continue
                    links.append({'name': self.up.getHostName(itemUrl), 'url': itemUrl, 'need_resolve': 1})
                if len(links):
                    params = dict(cItem)
                    params.update({'title': itemTitle, 'mode': mode, 'links': links, 'desc': desc})
                    self.addVideo(params)
        elif '>Season' in linksData or '>Σεζόν' in linksData:
            if '>Season' in linksData:
                seasonMarker = '>Season'
            else:
                seasonMarker = '>Σεζόν'
            mode = 'episode'
            seasons = linksData.split(seasonMarker)
            if len(seasons) > 0:
                del seasons[0]
            for item in seasons:
                seasonID = item.find('<')
                if seasonID < 0:
                    continue
                seasonID = item[:seasonID + 1]
                seasonID = self.cm.ph.getSearchGroups(seasonID, '([0-9]+?)[^0-9]')[0]
                if '' == seasonID:
                    continue
                episodesData = re.compile('<a[^>]*?href="([^"]+?)"[^>]*?>([^<]+?)</a>').findall(item)
                for eItem in episodesData:
                    eUrl = eItem[0]
                    eID = eItem[1].strip()
                    if eUrl.startswith('//'):
                        eUrl += 'http'
                    if 1 != self.up.checkHostSupport(eUrl):
                        continue

                    linksID = '-s{0}e{1}'.format(seasonID, eID)
                    if linksID not in eLinks:
                        eLinks[linksID] = []
                        episodes.append({'linksID': linksID, 'episode': eID, 'season': seasonID})
                    eLinks[linksID].append({'name': self.up.getHostName(eUrl), 'url': eUrl, 'need_resolve': 1})
            for item in episodes:
                linksID = item['linksID']
                if len(eLinks[linksID]):
                    params = dict(cItem)
                    params.update({'title': title + linksID, 'mode': mode, 'episode': item['episode'], 'season': item['season'], 'links': eLinks[linksID], 'desc': desc})
                    self.addVideo(params)
        else:
            links = self.getLinksForMovie(linksData)
            if len(links):
                params = dict(cItem)
                params['mode'] = 'movie'
                params['links'] = links
                params['desc'] = desc
                self.addVideo(params)

    def getLinksForMovie(self, data):
        urlTab = []
        linksData = re.compile('<a[^>]*?href="([^"]+?)"[^>]*?>([^<]*?)<').findall(data)
        for item in linksData:
            url = item[0]
            title = item[1]
            # only supported hosts will be displayed
            if 1 != self.up.checkHostSupport(url):
                continue

            name = self.up.getHostName(url)
            if url.startswith('//'):
                url += 'http'
            if url.startswith('http'):
                urlTab.append({'name': title + ': ' + name, 'url': url, 'need_resolve': 1})
        return urlTab

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("XrysoiSE.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.MAIN_URL
        cItem['url_suffix'] = self.SEARCH_SUFFIX + urllib.quote_plus(searchPattern)
        cItem['mode'] = 'search'
        self.listItems(cItem)

    def getLinksForVideo(self, cItem):
        printDBG("XrysoiSE.getLinksForVideo [%s]" % cItem)
        # Use Season and Episode information when exist for cache index
        idx = cItem['mode'] + cItem['url'] + cItem.get('season', '') + cItem.get('episode', '')
        urlTab = self.cacheLinks.get(idx, [])
        if len(urlTab):
            return urlTab
        self.cacheLinks = {}

        urlTab = cItem.get('links', [])

        self.cacheLinks[idx] = urlTab
        return urlTab

    def getVideoLinks(self, videoUrl):
        printDBG("XrysoiSE.getVideoLinks [%s]" % videoUrl)
        urlTab = []

        if videoUrl.startswith('http'):
            urlTab = self.up.getVideoLinkExt(videoUrl)
        return urlTab

    def getArticleContent(self, cItem):
        printDBG("XrysoiSE.getArticleContent [%s]" % cItem)
        retTab = []

        if 'movie' == cItem.get('mode') or 'explore_item' == cItem.get('category'):
            sts, data = self.cm.getPage(cItem['url'])
            if not sts:
                return retTab

            sts, data = CParsingHelper.getDataBeetwenMarkers(data, '<meta property', '<script')
            if not sts:
                return retTab

            icon = self.cm.ph.getSearchGroups(data, '<meta[^>]*?property="og:image"[^>]*?content="(http[^"]+?)"')[0]
            title = self.cm.ph.getSearchGroups(data, '<meta[^>]*?property="og:title"[^>]*?content="([^"]+?)"')[0]
            desc = self.cm.ph.getSearchGroups(data, '<meta[^>]*?property="og:description"[^>]*?content="([^"]+?)"')[0]
            return [{'title': self.cleanHtmlStr(title), 'text': self.cleanHtmlStr(desc), 'images': [{'title': '', 'url': self._getFullUrl(icon)}], 'other_info': {}}]
        else:
             return retTab

    def getFavouriteData(self, cItem):
        printDBG('XrysoiSE.getFavouriteData')
        params = {'type': cItem['type'], 'category': cItem.get('category', ''), 'title': cItem['title'], 'url': cItem['url'], 'desc': cItem.get('desc', ''), 'icon': cItem['icon']}
        return json.dumps(params)

    def setInitListFromFavouriteItem(self, fav_data):
        printDBG('XrysoiSE.setInitListFromFavouriteItem')
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
        self.currItem = dict(self.currItem)
        self.currItem.pop('good_for_fav', None)

    #MAIN MENU
        if name == None:
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})
        elif category == 'movies':
            self.listMoviesCategory(self.currItem, 'list_items')
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
        CHostBase.__init__(self, XrysoiSE(), True, favouriteTypes=[])
