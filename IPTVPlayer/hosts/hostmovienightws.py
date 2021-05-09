# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify
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


def gettytul():
    return 'http://movienight.ws/'


class MoviesNight(CBaseHostClass):
    MAIN_URL = 'http://movienight.ws/'
    SRCH_URL = MAIN_URL + '?s='
    DEFAULT_ICON_URL = 'http://movienight.ws/wp-content/uploads/2017/07/movineight-logo-125-2.png'

    MAIN_CAT_TAB = [{'category': 'list_items', 'title': _('Latest movies'), 'url': MAIN_URL, 'icon': DEFAULT_ICON_URL},
                    {'category': 'movies_genres', 'title': _('Movies genres'), 'filter': 'genres', 'url': MAIN_URL, 'icon': DEFAULT_ICON_URL},
                    {'category': 'movies_genres', 'title': _('Movies by year'), 'filter': 'years', 'url': MAIN_URL, 'icon': DEFAULT_ICON_URL},
                    {'category': 'list_items', 'title': _('TV Series'), 'url': MAIN_URL + 'tvshows/', 'icon': DEFAULT_ICON_URL},
                    {'category': 'search', 'title': _('Search'), 'search_item': True},
                    {'category': 'search_history', 'title': _('Search history')}
                   ]

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'MoviesNight', 'cookie': 'MoviesNight.cookie'})
        self.movieFiltersCache = {'genres': [], 'years': []}
        self.episodesCache = {}

    def _getFullUrl(self, url, series=False):
        if not series:
            mainUrl = self.MAIN_URL
        else:
            mainUrl = self.S_MAIN_URL
        if url.startswith('/'):
            url = url[1:]
        if 0 < len(url) and not url.startswith('http'):
            url = mainUrl + url
        if not mainUrl.startswith('https://'):
            url = url.replace('https://', 'http://')
        return url

    def _fillFilters(self, url):
        printDBG("MoviesNight._fillFilters")
        cache = {'genres': [], 'years': []}
        sts, data = self.cm.getPage(url)
        if not sts:
            return {}

        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="scrolling years">', '</ul>', False)[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<a ', '</a>')
        for item in tmp:
            title = self.cleanHtmlStr(item)
            url = self._getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)["']''', 1, True)[0])
            if url.startswith('http'):
                cache['years'].append({'title': title, 'url': url})

        data = self.cm.ph.getDataBeetwenMarkers(data, 'Genre', '</ul>', False)[1]
        data = data.split('</li>')
        for item in data:
            title = self.cleanHtmlStr(item)
            url = self._getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)["']''', 1, True)[0])
            if url.startswith('http'):
                cache['genres'].append({'title': title, 'url': url})
        return cache

    def fillMovieFilters(self, url):
        printDBG("MoviesNight.fillMovieFilters")
        self.movieFiltersCache = self._fillFilters(url)
        return

    def listMoviesGenres(self, cItem, category):
        printDBG("MoviesNight.listMoviesGenres")
        filter = cItem.get('filter', '')
        if 0 == len(self.movieFiltersCache.get(filter, [])):
            self.fillMovieFilters(cItem['url'])

        cItem = dict(cItem)
        cItem['category'] = category
        #params = dict(cItem)
        #params.update({'title':_('All')})
        #self.addDir(params)
        self.listsTab(self.movieFiltersCache.get(filter, []), cItem)

    def listItems(self, cItem, category='list_seasons'):
        printDBG("MoviesNight.listMovies")
        url = cItem['url']
        if '?' in url:
            post = url.split('?')
            url = post[0]
            post = post[1]
        else:
            post = ''
        page = cItem.get('page', 1)
        if page > 1:
            url += '/page/%d/' % page
        if post != '':
            url += '?' + post

        sts, data = self.cm.getPage(url)
        if not sts:
            return

        nextPage = False
        if ('/page/%d/' % (page + 1)) in data:
            nextPage = True

        m1 = '<div class="movie">'
        data = self.cm.ph.getDataBeetwenMarkers(data, m1, '<div class="footer', False)[1]
        data = data.split(m1)
        if len(data):
            data[-1] = data[-1].split('<div id="paginador">')[0]

        for item in data:
            url = self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0]
            if url == '':
                continue
            icon = self.cm.ph.getSearchGroups(item, 'src="([^"]+?)"')[0]
            title = self.cm.ph.getDataBeetwenMarkers(item, '<h2>', '</h2>', False)[1]
            desc = self.cleanHtmlStr(item)

            params = dict(cItem)
            params.update({'title': self.cleanHtmlStr(title), 'url': self._getFullUrl(url), 'desc': desc, 'icon': self._getFullUrl(icon), 'good_for_fav': True})
            if '/tvshows/' in url:
                params['category'] = category
                self.addDir(params)
            else:
                self.addVideo(params)

        if nextPage:
            params = dict(cItem)
            params.update({'title': _('Next page'), 'page': page + 1})
            self.addDir(params)

    def listSeasons(self, cItem, category):
        printDBG("MoviesNight.listSeasons [%s]" % cItem)
        self.episodesCache = {}

        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenReMarkers(data, re.compile('''<div id=['"]cssmenu['"]>'''), re.compile('</div>'), False)[1]
        data = re.split('''<li class=['"]has-sub['"]>''', data)
        if len(data):
            del data[0]

        for item in data:
            if 'No episodes' in item:
                continue
            seasonTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<a ', '</a>')[1])
            printDBG(">>>>>>>>>>>>>>>>>>>>>>>>>>>> " + seasonTitle)

            episodesTab = []
            episodesData = self.cm.ph.getAllItemsBeetwenMarkers(item, '<li', '</li>')
            for eItem in episodesData:
                eTmp = re.split('''<span class=['"]datix['"]>''', eItem)
                title = self.cleanHtmlStr(eTmp[0])
                desc = self.cleanHtmlStr(eTmp[-1])
                url = self._getFullUrl(self.cm.ph.getSearchGroups(eItem, '''href=['"]([^"^']+?)["']''', 1, True)[0])
                if url.startswith('http'):
                    episodesTab.append({'title': '{0} - {1}: {2}'.format(cItem['title'], seasonTitle, title), 'url': url, 'desc': desc})

            if len(episodesTab):
                self.episodesCache[seasonTitle] = episodesTab
                params = dict(cItem)
                params.update({'category': category, 'title': seasonTitle, 'season_key': seasonTitle, 'good_for_fav': False})
                self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("MoviesNight.listEpisodes [%s]" % cItem)
        seasonKey = cItem.get('season_key', '')
        if '' == seasonKey:
            return
        cItem = dict(cItem)
        self.listsTab(self.episodesCache.get(seasonKey, []), cItem, 'video')

    def listSearchResult(self, cItem, searchPattern, searchType):
        searchPattern = urllib.quote_plus(searchPattern)
        cItem = dict(cItem)
        cItem['url'] = self.SRCH_URL + urllib.quote_plus(searchPattern)
        self.listItems(cItem)

    def getLinksForVideo(self, cItem):
        printDBG("MoviesNight.getLinksForVideo [%s]" % cItem)
        urlTab = []
        url = cItem['url']

        sts, data = self.cm.getPage(url)
        if not sts:
            return []

        data = re.compile('<iframe[^>]+?src="(https?://[^"]+?)"', re.I).findall(data)
        for videoUrl in data:
            urlTab.extend(self.up.getVideoLinkExt(videoUrl))

        return urlTab

    def getFavouriteData(self, cItem):
        printDBG('MoviesNight.getFavouriteData')
        params = {'type': cItem['type'], 'category': cItem.get('category', ''), 'title': cItem['title'], 'url': cItem['url'], 'desc': cItem.get('desc', ''), 'icon': cItem.get('icon', '')}
        return json.dumps(params)

    def getLinksForFavourite(self, fav_data):
        printDBG('MoviesNight.getLinksForFavourite')
        if fav_data.startswith('http://') or fav_data.startswith('https://'):
            return self.getLinksForVideo({'url': fav_data})
        links = []
        try:
            cItem = byteify(json.loads(fav_data))
            links = self.getLinksForVideo(cItem)
        except Exception:
            printExc()
        return links

    def setInitListFromFavouriteItem(self, fav_data):
        printDBG('MoviesNight.setInitListFromFavouriteItem')
        try:
            params = byteify(json.loads(fav_data))
        except Exception:
            params = {}
            printExc()
        self.addDir(params)
        return True

    def getArticleContent(self, cItem):
        printDBG("MoviesNight.getArticleContent [%s]" % cItem)
        retTab = []

        otherInfo = {}

        url = cItem.get('url', '')

        sts, data = self.cm.getPage(url)
        if not sts:
            return retTab

        m2 = '<div class="tsll">'
        if m2 not in data:
            m2 = ' id="player'

        data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="post">', m2)[1]
        title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<h1', '</h1>')[1])
        icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(data, '''<img[^>]+?src=['"]([^"^']+?\.jpe?g[^"^']*?)["']''')[0])
        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div id="dato-2"', '</p>')[1].split('</h2>')[-1])

        if '/episode/' in url:
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<p', '</p>')
            if len(data) > 1:
                title += ' - ' + self.cleanHtmlStr(data[0])
                desc = self.cleanHtmlStr(data[1])
        else:
            tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<span class="original">', '</span>')[1])
            if tmp != '':
                otherInfo['alternate_title'] = tmp

            tmp = self.cm.ph.getSearchGroups(data, '>\s*([12][0-9]{3})\s*<')[0]
            if tmp != '':
                otherInfo['year'] = tmp

            tmp = self.cm.ph.getSearchGroups(data, '>\s*([0-9]+\s*min)\s*<')[0]
            if tmp != '':
                otherInfo['duration'] = tmp

            tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div class="imdbdatos">', '</div>')[1])
            if tmp != '':
                otherInfo['rating'] = tmp

            tmp = []
            tmp2 = re.compile('<a[^>]+?rel="category[^>]+?>([^>]+?)<').findall(data)
            for t in tmp2:
                t = self.cleanHtmlStr(t)
                if t != '':
                    tmp.append(t)
            if len(tmp):
                otherInfo['genres'] = ', '.join(tmp)

        if title == '':
            title = cItem['title']
        if desc == '':
            desc = cItem.get('desc', '')
        if icon == '':
            icon = cItem.get('icon', self.DEFAULT_ICON_URL)

        return [{'title': self.cleanHtmlStr(title), 'text': self.cleanHtmlStr(desc), 'images': [{'title': '', 'url': self.getFullUrl(icon)}], 'other_info': otherInfo}]

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
    #MOVIES
        elif category == 'movies_genres':
            self.listMoviesGenres(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem)
    #TVSERIES
        elif category == 'list_seasons':
            self.listSeasons(self.currItem, 'list_episodes')
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
        CHostBase.__init__(self, MoviesNight(), True, [CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO])

    def withArticleContent(self, cItem):
        if (cItem['type'] == 'video') or cItem.get('category', '') in ['list_seasons', 'list_episodes']:
            return True
        return False
