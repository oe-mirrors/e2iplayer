# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib
###################################################


def gettytul():
    return 'http://ls-streaming.com/'


class LibreStream(CBaseHostClass):
    MAIN_URL = 'http://ls-streaming.com/'
    SEARCH_URL = MAIN_URL + 'index.php?q='
    DEFAULT_ICON_URL = 'http://thumbnail.easycounter.com/thumbnails/300x180/l/libre-stream.org.png'

    MAIN_CAT_TAB = [
                    {'category': 'cats', 'cache_key': 'movie_cats', 'title': _('Movie'), 'url': MAIN_URL + 'films/', 'icon': DEFAULT_ICON_URL},
                    {'category': 'cats', 'cache_key': 'year_cats', 'title': _('Year'), 'url': MAIN_URL + 'films/', 'icon': DEFAULT_ICON_URL},
                    {'category': 'cats', 'cache_key': 'series_cats', 'title': _('Series TV'), 'url': MAIN_URL, 'icon': DEFAULT_ICON_URL},
                    {'category': 'cats', 'cache_key': 'qualities', 'title': _('Quality'), 'url': MAIN_URL + 'films/', 'icon': DEFAULT_ICON_URL},
                    {'category': 'cats', 'cache_key': 'platforms', 'title': _('Platform'), 'url': MAIN_URL + 'films/', 'icon': DEFAULT_ICON_URL},
                    {'category': 'search', 'title': _('Search'), 'icon': DEFAULT_ICON_URL, 'search_item': True},
                    {'category': 'search_history', 'title': _('Search history'), 'icon': DEFAULT_ICON_URL}
                   ]

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'LibreStream', 'cookie': 'LibreStream.cookie'})
        self.catCache = {'movies': [], 'series': []}
        self.USER_AGENT = "Mozilla/5.0 (Linux; U; Android 4.1.1; en-us; androVM for VirtualBox ('Tablet' version with phone caps) Build/JRO03S) AppleWebKit/534.30 (KHTML, like Gecko) Version/4.0 Safari/534.30"
        self.HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'text/html'}
        self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.sortCache = []
        self.catCache = {'year_cats': [], 'movie_cats': [], 'series_cats': [], 'qualities': [], 'platforms': []}

    def _getFullUrl(self, url):
        mainUrl = self.MAIN_URL
        if 0 < len(url) and not url.startswith('http'):
            if url.startswith('/'):
                url = url[1:]
            url = mainUrl + url
        if not mainUrl.startswith('https://'):
            url = url.replace('https://', 'http://')
        return url

    def listsTab(self, tab, cItem, type='dir'):
        printDBG("LibreStream.listsTab")
        for item in tab:
            params = dict(cItem)
            params.update(item)
            params['name'] = 'category'
            if type == 'dir':
                self.addDir(params)
            else:
                self.addVideo(params)

    def _fillCache(self):
        printDBG("LibreStream._fillCache")
        sts, data = self.cm.getPage(self.MAIN_URL)
        self.sortCache = []
        self.catCache = {'year_cats': [], 'movie_cats': [], 'series_cats': [], 'qualities': [], 'platforms': []}
        if not sts:
            return

        # fill sort cache
        tmpData = self.cm.ph.getDataBeetwenMarkers(data, '<form name="news_set_sort"', '<input ', False)[1]
        tmpData = re.compile("dle_change_sort\('([^']+?)','([^']+?)'\)[^>]*?>([^<]+?)<").findall(tmpData)
        for item in tmpData:
            post_data = {'dlenewssortby': item[0], 'dledirection': item[1], 'set_new_sort': 'dle_sort_cat', 'set_direction_sort': 'dle_direction_cat'}
            params = {'title': item[2], 'post_data': post_data}
            self.sortCache.append(params)

        # fill movie year
        tmpData = self.cm.ph.getDataBeetwenMarkers(data, '<form name="choix_annee" method="get">', '</select>', False)[1]
        tmpData = re.compile('<option value="(http[^"]+?)">([^<]+?)</option>').findall(tmpData)
        for item in tmpData:
            params = {'title': item[1], 'url': item[0]}
            self.catCache['year_cats'].append(params)

        # fill movie cats
        tmpData = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="genre_style half">', '</ul>', False)[1]
        tmpData = re.compile('<a href="(/films/[^"]+?)">([^<]+?)</a>').findall(tmpData)
        for item in tmpData:
            params = {'title': item[1], 'url': self._getFullUrl(item[0])}
            self.catCache['movie_cats'].append(params)
        if len(self.catCache['movie_cats']):
            self.catCache['movie_cats'].insert(0, {'title': _('--All--'), 'url': self._getFullUrl('/films/')})

        # fill series cats
        tmpData = self.cm.ph.getDataBeetwenMarkers(data, '<a href="/series/">', '</ul>', True)[1]
        tmpData = re.compile('<a href="([^"]+?)">([^<]+?)</a>').findall(tmpData)
        for item in tmpData:
            params = {'title': item[1], 'url': self._getFullUrl(item[0])}
            self.catCache['series_cats'].append(params)

        # fill qualities
        tmpData = self.cm.ph.getDataBeetwenMarkers(data, 'Qualite', '</ul>', True)[1]
        tmpData = re.compile('<a href="([^"]+?)">([^<]+?)</a>').findall(tmpData)
        for item in tmpData:
            params = {'title': item[1], 'url': self._getFullUrl(item[0])}
            self.catCache['qualities'].append(params)

        # fill platforms
        tmpData = self.cm.ph.getDataBeetwenMarkers(data, 'Plateforme', '</ul>', True)[1]
        tmpData = re.compile('<a href="([^"]+?)">([^<]+?)</a>').findall(tmpData)
        for item in tmpData:
            params = {'title': item[1], 'url': self._getFullUrl(item[0])}
            self.catCache['platforms'].append(params)

    def listMainMenu(self):
        printDBG("LibreStream.listMainMenu")
        self._fillCache()
        printDBG('++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++')
        printDBG(self.sortCache)
        printDBG('++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++')
        printDBG(self.catCache)
        printDBG('++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++')
        self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})

    def listCategories(self, cItem, category):
        printDBG("LibreStream.listCategories")
        catsKey = cItem['cache_key']
        tmpTab = self.catCache[catsKey]
        if 0 == len(tmpTab):
            self._fillCache()
            tmpTab = self.catCache[catsKey]
        cItem = dict(cItem)
        cItem['category'] = category
        self.listsTab(tmpTab, cItem)

    def listEpisodes(self, cItem):
        printDBG("LibreStream.listEpisodes")
        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return

        episodes = self._getLinksFromContent(data, 'id')
        title = cItem['title']
        id = self.cm.ph.getSearchGroups(cItem['url'], '-saison-([0-9]+?)\.')[0]

        for item in episodes:
            params = dict(cItem)
            params.update({'title': 's{0}e{1} {2}'.format(id, item['id'], item['episode_title']), 'url': item['url']})
            self.addVideo(params)

    def listItems(self, cItem, category):
        printDBG("LibreStream.listItems")
        url = cItem['url']
        page = cItem.get('page', 1)

        post_data = cItem.get('post_data', None)
        sts, data = self.cm.getPage(url, {}, post_data)
        if not sts:
            return

        m1 = '<div class="libre-movie libre-movie-block">'
        data = self.cm.ph.getDataBeetwenMarkers(data, m1, '<footer>', False)[1]
        data = data.split(m1)

        nextPageUrl = ''
        if len(data):
            navMarker = '<div class="navigation">'
            tmp = data[-1].split(navMarker)
            data[-1] = tmp[0]
            nextPageUrl = self.cm.ph.getSearchGroups(tmp[-1], '<a[^<]+?href="([^"]+?)"[^<]*?>%s</a>' % (page + 1))[0]

        for item in data:
            url = self.cm.ph.getSearchGroups(item, "location.href='([^']+?)'")[0]
            title = self.cm.ph.getSearchGroups(item, 'alt="([^"]+?)"')[0]
            if title == '':
                title = self.cm.ph.getSearchGroups(item, 'title="([^"]+?)"')[0]
            if title == '':
                title = self.cm.ph.getSearchGroups(item, '<h2[^>]*?>([^<]+?)</h2>')[0]
            title = self.cleanHtmlStr(title)
            if title == '':
                continue
            icon = self.cm.ph.getSearchGroups(item, '<img[^>]+?data-src="([^"]+?)"')[0]
            desc = self.cleanHtmlStr(item.split('<div class="mcontent">')[-1]).replace(' ---------------', ': ')
            params = dict(cItem)
            params.update({'title': title, 'icon': self._getFullUrl(icon), 'desc': desc, 'url': self._getFullUrl(url)})
            if '-saison-' not in url and ' Saison ' not in title:
                self.addVideo(params)
            else:
                params['category'] = category
                self.addDir(params)

        if nextPageUrl != '':
            params = dict(cItem)
            params.update({'title': _('Next page'), 'page': cItem.get('page', 1) + 1, 'url': self._getFullUrl(nextPageUrl)})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        searchPattern = searchPattern
        searchPattern = urllib.quote_plus(searchPattern)
        cItem = dict(cItem)
        cItem['url'] = self.SEARCH_URL + searchPattern + '&search_start=%s' % cItem.get('page', 1)
        #cItem['category'] = 'list_items'
        #cItem['search_item'] = False
        self.listItems(cItem, 'list_episodes')

    def _getLinksFromContent(self, data, title_key='title', baseItem={}):
        printDBG("LibreStream._getLinksFromContent")
        linksTab = []

        etitleMap = {}
        linksMap = {}
        linksData = self.cm.ph.getDataBeetwenMarkers(data, 'panel-container', '<style>', False)[1]
        linksData = linksData.split('tab-buttons-panel')
        for item in linksData:
            id = self.cm.ph.getSearchGroups(item, 'id="([^"]+?)"')[0]
            playerUrl = self.cm.ph.getSearchGroups(item, '''<iframe[^>]+?src=["'](http[^"^']+?)["']''', 1, True)[0]
            if playerUrl.startswith('http') and id != '':
                linksMap[id] = playerUrl
                episodeTitle = self.cm.ph.getDataBeetwenMarkers(item, '<h3 class="episodetitle">', '</h3>', False)[1]
                etitleMap[id] = self.cleanHtmlStr(episodeTitle)

        servers = self.cm.ph.getDataBeetwenMarkers(data, "<ul class='etabs'", '</ul>')[1]
        servers = servers.split('</li>')
        if len(servers):
            del servers[-1]
        for item in servers:
            title = self.cleanHtmlStr(item)
            id = self.cm.ph.getSearchGroups(item, 'href="#([^"]+?)"')[0]
            if id in linksMap:
                params = dict(baseItem)
                params.update({title_key: title, 'episode_title': etitleMap.get(id, ''), 'url': linksMap[id]})
                linksTab.append(params)
        return linksTab

    def getLinksForVideo(self, cItem):
        printDBG("LibreStream.getLinksForVideo [%s]" % cItem)
        urlTab = []
        if 'libre-stream.com' in cItem['url'] or self.up.getDomain(self.getMainUrl(), True) in cItem['url']:
            sts, data = self.cm.getPage(cItem['url'])
            if not sts:
                return []
            urlTab = self._getLinksFromContent(data, 'name', {'need_resolve': 1})
        else:
            urlTab.append({'name': 'Main url', 'url': cItem['url'], 'need_resolve': 1})
        return urlTab

    def getVideoLinks(self, videoUrl):
        printDBG("LibreStream.getVideoLinks [%s]" % videoUrl)
        urlTab = []

        if 0 == self.up.checkHostSupport(videoUrl):
            sts, data = self.cm.getPage(videoUrl, {'max_data_size': 0})
            if not sts:
                return []
            videoUrl = self.cm.meta['url']
        return self.up.getVideoLinkExt(videoUrl)

    def getFavouriteData(self, cItem):
        return cItem['url']

    def getLinksForFavourite(self, fav_data):
        return self.getLinksForVideo({'url': fav_data})

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listMainMenu()
        elif category == 'cats':
            self.listCategories(self.currItem, 'show_sort')
        elif category == 'show_sort':
            cItem = dict(self.currItem)
            cItem['category'] = 'list_items'
            self.listsTab(self.sortCache, cItem)
        elif category == 'list_items':
            self.listItems(self.currItem, 'list_episodes')
        elif category == 'list_episodes':
            self.listEpisodes(self.currItem)
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
        CHostBase.__init__(self, LibreStream(), True, [CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO])
