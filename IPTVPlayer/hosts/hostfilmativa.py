# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem, RetHost, CUrlItem
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetLogoDir
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
###################################################

###################################################
# FOREIGN import
###################################################
import urllib
###################################################


def gettytul():
    return 'https://filmativa.xyz/'


class Filmativa(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'Filmativa', 'cookie': 'filmativa.cookie'})

        self.MAIN_URL = 'https://filmativa.xyz/'
        self.SRCH_URL = self.MAIN_URL + '?s='
        self.DEFAULT_ICON_URL = 'https://zoxh.com/screenshot/bupxbupx/pxlr/pxjk/pxos/filmativa.ws-desktop.jpg'

        self.S_MAIN_URL = 'http://epizode.ws/'
        self.S_SRCH_URL = self.S_MAIN_URL + '?s='
        self.S_DEFAULT_ICON_URL = "https://zoxh.com/screenshot/bupxbupx/pxlr/pxjk/pxos/filmativa.ws-desktop.jpg"

        self.MAIN_CAT_TAB = [{'category': 'movies', 'title': _('Movies'), 'url': self.MAIN_URL, 'icon': self.DEFAULT_ICON_URL},
                            {'category': 'series', 'title': _('TV series'), 'url': self.S_MAIN_URL, 'icon': self.S_DEFAULT_ICON_URL},
                            {'category': 'search', 'title': _('Search'), 'search_item': True},
                            {'category': 'search_history', 'title': _('Search history')}
                            ]

        self.MOVIES_TAB = [{'category': 'list_movies', 'title': _('New'), 'url': self.MAIN_URL, },
                            {'category': 'list_movies', 'title': _('Popular'), 'url': self.MAIN_URL + 'popularno/'},
                            ]

        self.SERIES_TAB = [{'category': 'list_series', 'title': _('New'), 'url': self.S_MAIN_URL, },
                      {'category': 'list_series', 'title': _('New episodes'), 'url': self.S_MAIN_URL + 'nove-epizode/'},
                      {'category': 'list_series', 'title': _('Popular'), 'url': self.S_MAIN_URL + 'popularno/'},
                 ]

        self.USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.103 Safari/537.36'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'text/html', 'Accept-Encoding': 'gzip'}
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.seriesCache = {}
        self.seasons = []

    def getPageCF(self, baseUrl, params={}, post_data=None):
        if params == {}:
            params = self.defaultParams
        params['cloudflare_params'] = {'domain': 'filmativa.xyz', 'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT}
        return self.cm.getPageCFProtection(baseUrl, params, post_data)

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def _getFullUrl(self, url, series=False):
        if not series:
            mainUrl = self.MAIN_URL
        else:
            mainUrl = self.S_MAIN_URL
        if 0 < len(url) and not url.startswith('http'):
            url = mainUrl + url
        if not mainUrl.startswith('https://'):
            url = url.replace('https://', 'http://')
        return url

    def listMoviesTab(self, cItem, category):
        printDBG("Filmativa.listMoviesTab")
        cItem = dict(cItem)
        cItem['category'] = category
        self.listsTab(self.MOVIES_TAB, cItem)

    def listSeriesTab(self, cItem, category):
        printDBG("Filmativa.listSeriesTab")
        cItem = dict(cItem)
        cItem['category'] = category
        self.listsTab(self.SERIES_TAB, cItem)

    def _listItems(self, cItem, category):
        printDBG("Filmativa._listItems")
        url = cItem['url']
        page = cItem.get('page', 1)
        if page > 1:
            url += 'page/%d/' % page

        sts, data = self.getPageCF(url)
        if not sts:
            return

        if ('/page/%d/' % (page + 1)) in data:
            nextPage = True
        else:
            nextPage = False

        try:
            marker = 'class="with_teaser">'
            data = data[data.find(marker) + len(marker):]
        except Exception:
            printExc()
            return
        data = data.split('</a>')
        if len(data):
            del data[-1]

        for item in data:
            if '"cover"' not in item:
                continue
            tmp = item.split('<span class="rating')
            url = self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0]
            icon = self.cm.ph.getSearchGroups(item, 'src="([^"]+?)"')[0]
            title = tmp[0]
            desc = ""
            if len(tmp) > 1:
                desc = self.cm.ph.getSearchGroups(tmp[1], 'title="([^"]+?)"')[0]
            params = dict(cItem)
            params.update({'title': self.cleanHtmlStr(title), 'url': self._getFullUrl(url), 'desc': self.cleanHtmlStr(desc), 'icon': self._getFullUrl(icon)})
            if category == 'video':
                self.addVideo(params)
            else:
                params['category'] = category
                self.addDir(params)

        if nextPage:
            params = dict(cItem)
            params.update({'title': _('Next page'), 'page': page + 1})
            self.addDir(params)

    def listMovies(self, cItem):
        printDBG("Filmativa.listMovies")
        self._listItems(cItem, 'video')

    def listSeries(self, cItem, category):
        printDBG("Filmativa.listSeries")
        self._listItems(cItem, category)

    def listSeasons(self, cItem, category):
        printDBG("Filmativa.listSeasons")
        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return

        tvShowTitle = cItem['title']
        self.seriesCache = {}
        self.seasons = []
        data = self.cm.ph.getDataBeetwenMarkers(data, ('<div', '>', 'seasons'), '<script>', False)[1]

        seasons = data.split('<dt>')

        for item in seasons:
            if item.find('</dt>') > 0:
                season = item[:item.find('</dt>')]
                sNum = season.upper().replace('SEZONA', '').strip()
                self.seasons.append({'title': season, 'season': season})

                if not self.seriesCache.get(season, []):
                    self.seriesCache[season] = []

                episodes = self.cm.ph.getAllItemsBeetwenMarkers(item, ('<dd', '>'), '</dd>')
                for tmp in episodes:
                    episodeTitle = self.cm.ph.getDataBeetwenMarkers(tmp, ('<div', '>', 'title'), '</div>', False)[1]
                    episodeTitle = self.cleanHtmlStr(episodeTitle)

                    postId = self.cm.ph.getSearchGroups(tmp, 'data-postid="([^"]+?)"')[0]
                    dataS = self.cm.ph.getSearchGroups(tmp, 'data-s="([^"]+?)"')[0]
                    dataE = self.cm.ph.getSearchGroups(tmp, 'data-e="([^"]+?)"')[0]

                    subtitleUrl = "https://cdn.opensubtitles.ml/sub/" + postId + "-" + dataS + "-" + dataE + ".vtt"

                    dataDood = self.cm.ph.getSearchGroups(tmp, 'data-doodstream="([^"]+?)"')[0]
                    dataMix = self.cm.ph.getSearchGroups(tmp, 'data-mix="([^"]+?)"')[0]
                    dataOnly = self.cm.ph.getSearchGroups(tmp, 'data-only="([^"]+?)"')[0]
                    dataVidoza = self.cm.ph.getSearchGroups(tmp, 'data-vidoza="([^"]+?)"')[0]

                    if dataDood:
                        url = "https://dood.watch/e/%s" % dataDood
                        self.seriesCache[season].append({'title': '{0}: s{1} - {2} [{3}]'.format(tvShowTitle, sNum, episodeTitle, "Doodstream"), 'url': url, 'direct': True})
                    elif dataMix:
                        url = "https://mixdrop.co/e/%s" % dataMix
                        self.seriesCache[season].append({'title': '{0}: s{1} - {2} [{3}]'.format(tvShowTitle, sNum, episodeTitle, "Mixdrop"), 'url': url, 'direct': True, 'subtitles': subtitleUrl})
                    elif dataOnly:
                        url = "https://onlystream.tv/e/%s" % dataOnly
                        self.seriesCache[season].append({'title': '{0}: s{1} - {2} [{3}]'.format(tvShowTitle, sNum, episodeTitle, "Onlystream"), 'url': url, 'direct': True})
                    elif dataVidoza:
                        url = "https://vidoza.net/embed-%s" % dataVidoza
                        self.seriesCache[season].append({'title': '{0}: s{1} - {2} [{3}]'.format(tvShowTitle, sNum, episodeTitle, "Vidoza"), 'url': url, 'direct': True})
                    else:
                        self.seriesCache[season].append({'title': '{0}: s{1} - {2} [{3}]'.format(tvShowTitle, sNum, episodeTitle, _("No valid links available.")), 'url': ''})

        cItem = dict(cItem)
        cItem['category'] = category
        self.listsTab(self.seasons, cItem)

    def listEpisodes(self, cItem):
        printDBG("Filmativa.listEpisodes")
        season = cItem.get('season', '')
        cItem = dict(cItem)
        self.listsTab(self.seriesCache.get(season, []), cItem, 'video')

    def listSearchResult(self, cItem, searchPattern, searchType):
        searchPattern = urllib.quote_plus(searchPattern)
        cItem = dict(cItem)
        if searchType == 'movies':
            cItem['url'] = self.SRCH_URL + searchPattern
            self.listMovies(cItem)
        else:
            cItem['url'] = self.S_SRCH_URL + searchPattern
            self.listSeries(cItem, 'list_seasons')

    def getLinksForVideo(self, cItem):
        printDBG("Filmativa.getLinksForVideo [%s]" % cItem)
        urlTab = []

        if not cItem.get('url', ''):
            return []

        if cItem.get('direct', False):
            if cItem.get('subtitles', ''):
                subtitlesTab = [{'title': 'Serbian', 'url': cItem.get('subtitles', ''), 'lang': 'srp', 'format': 'vtt'}]
                url = strwithmeta(cItem['url'], {'external_sub_tracks': subtitlesTab})
                urlTab.append({'name': 'link', 'url': url, 'need_resolve': 1})
            else:
                urlTab.append({'name': 'link', 'url': cItem['url'], 'need_resolve': 1})

        else:
            sts, data = self.cm.getPage(cItem['url'])
            if not sts:
                return urlTab

            if 'USKORO!' in data:
                SetIPTVPlayerLastHostError('USKORO!')
                return urlTab

            divIframe = self.cm.ph.getDataBeetwenMarkers(data, ('<div', '>', 'trailer'), '</div>', False)[1]
            url = self.cm.ph.getSearchGroups(divIframe, 'src="([^"]+?)"')[0]
            if 'videomega.tv/validatehash.php?' in url:
                sts, data = self.cm.getPage(url, {'header': {'Referer': cItem['url'], 'User-Agent': 'Mozilla/5.0'}})
                if sts:
                    data = self.cm.ph.getSearchGroups(data, 'ref="([^"]+?)"')[0]
                    linkUrl = 'http://videomega.tv/view.php?ref={0}&width=700&height=460&val=1'.format(data)
                    urlTab.append({'name': 'videomega.tv', 'url': linkUrl, 'need_resolve': 1})
            elif self.cm.isValidUrl(url):
                urlTab.append({'name': 'link', 'url': url, 'need_resolve': 1})

        return urlTab

    def getVideoLinks(self, baseUrl):
        printDBG("Filmativa.getVideoLinks [%s]" % baseUrl)
        urlTab = []
        urlTab = self.up.getVideoLinkExt(baseUrl)

        if isinstance(baseUrl, strwithmeta):
            if 'external_sub_tracks' in baseUrl.meta:
                subTracks = baseUrl.meta['external_sub_tracks']
                printDBG("subTracks %s " % str(subTracks))
                urlTab2 = []
                for u in urlTab:
                    printDBG(u)
                    url = strwithmeta(u['url'], {'Referer': baseUrl, 'external_sub_tracks': subTracks})
                    u.update({'url': url})
                    urlTab2.append(u)

                urlTab = urlTab2

        return urlTab

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
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})
    #MOVIES
        elif category == 'movies':
            self.listMoviesTab(self.currItem, 'list_movies')
        elif category == 'list_movies':
            self.listMovies(self.currItem)
    #SERIES
        elif category == 'series':
            self.listSeriesTab(self.currItem, 'list_series')
        elif category == 'list_series':
            self.listSeries(self.currItem, 'list_seasons')
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
        CHostBase.__init__(self, Filmativa(), True, [CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO])

    def getLogoPath(self):
        return RetHost(RetHost.OK, value=[GetLogoDir('filmotopialogo.png')])

    def getLinksForVideo(self, Index=0, selItem=None):
        retCode = RetHost.ERROR
        retlist = []
        if not self.isValidIndex(Index):
            return RetHost(retCode, value=retlist)

        urlList = self.host.getLinksForVideo(self.host.currList[Index])
        for item in urlList:
            retlist.append(CUrlItem(item["name"], item["url"], item['need_resolve']))

        return RetHost(RetHost.OK, value=retlist)
    # end getLinksForVideo

    def getResolvedURL(self, url):
        # resolve url to get direct url to video file
        retlist = []
        urlList = self.host.getVideoLinks(url)
        for item in urlList:
            need_resolve = 0
            retlist.append(CUrlItem(item["name"], item["url"], need_resolve))

        return RetHost(RetHost.OK, value=retlist)

    def converItem(self, cItem):
        hostList = []
        searchTypesOptions = [] # ustawione alfabetycznie
        searchTypesOptions.append((_("Movies"), "movies"))
        searchTypesOptions.append((_("Series"), "series"))

        hostLinks = []
        type = CDisplayListItem.TYPE_UNKNOWN
        possibleTypesOfSearch = None

        if 'category' == cItem['type']:
            if cItem.get('search_item', False):
                type = CDisplayListItem.TYPE_SEARCH
                possibleTypesOfSearch = searchTypesOptions
            else:
                type = CDisplayListItem.TYPE_CATEGORY
        elif cItem['type'] == 'video':
            type = CDisplayListItem.TYPE_VIDEO
        elif 'more' == cItem['type']:
            type = CDisplayListItem.TYPE_MORE
        elif 'audio' == cItem['type']:
            type = CDisplayListItem.TYPE_AUDIO

        if type in [CDisplayListItem.TYPE_AUDIO, CDisplayListItem.TYPE_VIDEO]:
            url = cItem.get('url', '')
            if '' != url:
                hostLinks.append(CUrlItem("Link", url, 1))

        title = cItem.get('title', '')
        description = cItem.get('desc', '')
        icon = cItem.get('icon', '')

        return CDisplayListItem(name=title,
                                    description=description,
                                    type=type,
                                    urlItems=hostLinks,
                                    urlSeparateRequest=1,
                                    iconimage=icon,
                                    possibleTypesOfSearch=possibleTypesOfSearch)
    # end converItem

    def getSearchItemInx(self):
        try:
            list = self.host.getCurrList()
            for i in range(len(list)):
                if list[i]['category'] == 'search':
                    return i
        except Exception:
            printDBG('getSearchItemInx EXCEPTION')
            return -1

    def setSearchPattern(self):
        try:
            list = self.host.getCurrList()
            if 'history' == list[self.currIndex]['name']:
                pattern = list[self.currIndex]['title']
                search_type = list[self.currIndex]['search_type']
                self.host.history.addHistoryItem(pattern, search_type)
                self.searchPattern = pattern
                self.searchType = search_type
        except Exception:
            printDBG('setSearchPattern EXCEPTION')
            self.searchPattern = ''
            self.searchType = ''
        return
