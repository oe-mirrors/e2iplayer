# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, RetHost, ArticleContent
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify, MergeDicts
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.libs import ph
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib
import base64
try:
    import json
except Exception:
    import simplejson as json
from copy import deepcopy
###################################################


def gettytul():
    return 'https://hdfilme.cx/'


class HDFilmeTV(CBaseHostClass):
    USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.103 Safari/537.36'

    MAIN_URL = 'https://hdfilme.cx/'
    SEARCH_URL = MAIN_URL + 'movie-search'
    DEFAULT_ICON = "https://raw.githubusercontent.com/StoneOffStones/plugin.video.xstream/c88b2a6953febf6e46cf77f891d550a3c2ee5eea/resources/art/sites/hdfilme.png" #"http://hdfilme.tv/public/site/images/logo.png"

    MAIN_CAT_TAB = [{'icon': DEFAULT_ICON, 'category': 'list_filters', 'filter': 'genre', 'title': _('Movies'), 'url': MAIN_URL + 'filme1'},
                    {'icon': DEFAULT_ICON, 'category': 'list_filters', 'filter': 'genre', 'title': _('Series'), 'url': MAIN_URL + 'serien1'},
                    {'icon': DEFAULT_ICON, 'category': 'list_filters', 'filter': 'genre', 'title': _('Trailers'), 'url': MAIN_URL + 'trailer'},
                    {'icon': DEFAULT_ICON, 'category': 'search', 'title': _('Search'), 'search_item': True},
                    {'icon': DEFAULT_ICON, 'category': 'search_history', 'title': _('Search history')}]

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': '  HDFilmeTV.cc', 'cookie': 'hdfilmenet.cookie'})
        self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.filtersCache = {'genre': [], 'country': [], 'sort': []}
        self.seasonCache = {}
        self.cacheLinks = {}

    def c_int(self, n):
        if n.isdigit():
            return int(n)
        else:
            return 0

    def getFullUrl(self, url):
        return CBaseHostClass.getFullUrl(self, url)

    def getPage(self, baseUrl, params={}, post_data=None):
        if params == {}:
            params = self.defaultParams
        return self.cm.getPage(baseUrl, params, post_data)

    def getPageCF(self, baseUrl, params={}, post_data=None):
        if params == {}:
            params = self.defaultParams
        params['cloudflare_params'] = {'domain': 'hdfilme.cx', 'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT, 'full_url_handle': self.getFullUrl}
        return self.cm.getPageCFProtection(baseUrl, params, post_data)

    def getIconUrl(self, url):
        url = self.getFullUrl(url)
        if url == '':
            return ''
        cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE)
        return strwithmeta(url, {'Cookie': cookieHeader, 'User-Agent': self.USER_AGENT})

    def getMovieDatainJS(self, data):
        printDBG("HDFilmeTV.getMovieDatainJs")
        # example:
        #    var movieData = {
        #            id : 13810,
        #            name : "The Super",
        #            url : "https://hdfilme.cx/the-super-13810-stream"
        #    };

        movieData = {}
        code = self.cm.ph.getDataBeetwenMarkers(data, 'var movieData = {', '}', False)[1]
        printDBG("movie data code: -----------------")
        printDBG(code)
        printDBG("-----------------")
        movie_id = self.cm.ph.getSearchGroups(code, "id : ([0-9]+?),")[0]
        movie_name = self.cm.ph.getSearchGroups(code, '''name : ['"]([^'^"]+?)['"]''')[0]
        movie_url = self.cm.ph.getSearchGroups(code, '''url : ['"]([^'^"]+?)['"]''')[0]
        movieData = {'id': movie_id, 'name': movie_name, 'url': movie_url}
        printDBG(str(movieData))
        return movieData

    def getTrailerUrlinJS(self, data, movieData):
        printDBG("HDFilmeTV.getTrailerUrlinJs")

        #    function load_trailer() {
        #           $( "#play-area-wrapper" ).load( "/movie/load-trailer/" + movieData.id + "/0?trailer=bEplMVBHYVRHNDJoNjFWRWNXMFNiNm1zc0NvbllFNG1XU3JYM2xPbWVCcHVGMHNBU3FPRzJlTGdCWTBqcjZ5bg==", function() {
        #               $("html, body").animate({ scrollTop: $('#play-area-wrapper').offset().top }, 1000);
        #           console.log( "Load was performed." );
        #
        #           });
        #    }

        trailerUrl = ''
        code = self.cm.ph.getDataBeetwenMarkers(data, 'function load_trailer() {', '}', False)[1]
        printDBG("load_trailer code: -----------------")
        printDBG(code)
        printDBG("-----------------")
        trailerUrl = self.cm.ph.getSearchGroups(code, ".load\( \"(.*?)\",")[0]
        trailerUrl = self.getFullUrl(trailerUrl.replace("\" + movieData.id + \"", movieData['id']))
        return trailerUrl

    def fillFiltersCache(self, cItem):
        printDBG("HDFilmeTV.fillFiltersCache")
        self.filtersCache = {'genre': [], 'country': [], 'sort': []}

        params = MergeDicts(self.defaultParams, {'user-agent': self.USER_AGENT, 'referer': self.MAIN_URL, "accept-encoding": "gzip", "accept": "text/html"})
        printDBG("^^^^^^^^^^^^^^^^^^^^^^^")
        printDBG(str(params))

        sts, data = self.getPageCF(cItem['url'], params)
        if not sts:
            return

        for filter in [{'m': 'name="category"', 'key': 'genre'}, {'m': 'name="country"', 'key': 'country'}, {'m': 'name="sort"', 'key': 'sort'}]:
            filterData = []
            filterData = ph.findall(data, '<select class="orderby" ' + filter['m'] + '>', '</select>')
            #printDBG("^^^^^^^^^^^^^^^^^^")
            #printDBG(filterData[0])
            optionsData = []
            optionsData = ph.findall(filterData[0], ('<option', '>'), '</option>')
            #printDBG("^^^^^^^^^^^^^^^^^^")
            #printDBG(str(optionsData))
            optionsData.sort()
            #printDBG(str(optionsData))
            #printDBG("^^^^^^^^^^^^^^^^^^")
            #printDBG("^^^^^^^^^^^^^^^^^^")

            old_value = ""
            for item in optionsData:
                title = self.cleanHtmlStr(item)
                value = self.cm.ph.getSearchGroups(item, '''value=['"]([^'^"]+?)['"]''')[0]
                if value == '':
                    continue

                if value != old_value:
                    old_value = value
                    self.filtersCache[filter['key']].append({'title': title, filter['key']: value})

            if len(self.filtersCache[filter['key']]) and filter['key'] != 'sort':
                self.filtersCache[filter['key']].insert(0, {'title': _('--All--'), filter['key']: ''})

            # add sort_type to sort filter
        orderLen = len(self.filtersCache['sort'])
        for idx in range(orderLen):
            item = deepcopy(self.filtersCache['sort'][idx])
            # desc
            self.filtersCache['sort'][idx].update({'title': '\xe2\x86\x93 ' + self.filtersCache['sort'][idx]['title'], 'sort_type': 'desc'})
            # asc
            item.update({'title': '\xe2\x86\x91 ' + item['title'], 'sort_type': 'asc'})
            self.filtersCache['sort'].append(item)

    def listFilters(self, cItem, nextCategory, nextFilter):
        filter = cItem.get('filter', '')
        printDBG("HDFilmeTV.listFilters filter[%s] nextFilter[%s]" % (filter, nextFilter))
        tab = self.filtersCache.get(filter, [])
        if len(tab) == 0:
            self.fillFiltersCache(cItem)
        tab = self.filtersCache.get(filter, [])
        params = dict(cItem)
        params['category'] = nextCategory
        params['filter'] = nextFilter
        self.listsTab(tab, params)

    def listItems(self, cItem, nextCategory):
        printDBG("HDFilmeTV.listItems")

        itemsPerPage = 50
        page = cItem.get('page', 1)
        url = cItem['url']

        params = MergeDicts(self.defaultParams, {'header': {'User-Agent': self.USER_AGENT, "Accept-Encoding": "gzip", "Accept": "text/html", "content-length": "14", "content-type": "application/x-www-form-urlencoded; charset=UTF-8", "Origin": self.MAIN_URL, "Referer": url, "x-requested-with": "XMLHttpRequest"}})

        query = {}
        if 'search_pattern' in cItem:
            query = {'key': cItem['search_pattern'], 'page': page}
        else:
            query = {'page': page, 'category': cItem['genre'], 'country': cItem['country'], 'sort': cItem['sort'], 'sort_type': cItem['sort_type']}

        url += "?" + urllib.urlencode(query)
        sts, data = self.getPageCF(url, params, post_data={'load': 'full-page'})
        #printDBG(data)
        if not sts:
            return

        nextPage = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="pagination', '</ul>', False)[1]
        if 'data-page="{0}"'.format(page + 1) in nextPage:
            #printDBG("Next page found!")
            nextPage = True
        else:
            nextPage = False

        numOfItems = 0
        data = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="products row">', '</ul>')[1]
        data = ph.findall(data, '<li>', '</li>')
        #printDBG(str(data))

        for item in data:
            # icon
            icon = self.cm.ph.getSearchGroups(item, '''data-src=['"]([^'^"]+?)['"]''')[0]
            if icon == '':
                icon = cItem['icon']
            # url
            url = self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0]
            if url == '':
                continue
            #title
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<div class="title-product">', '</div>')[1])
            if title == '':
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h3 ', '</h3>')[1])
            #desc
            desc = self.cleanHtmlStr(item)

            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': self.getFullUrl(url), 'icon': self.getIconUrl(icon), 'desc': desc})
            #printDBG("----> movie item ------> " + str(params))
            self.addDir(params)
            numOfItems += 1

        if nextPage or numOfItems >= itemsPerPage:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _('Next page'), 'page': (page + 1)})
            self.addMore(params)

    def exploreItem(self, cItem):
        printDBG("HDFilmeTV.exploreItem")

        params = MergeDicts(self.defaultParams, {'user-agent': self.USER_AGENT, 'referer': self.MAIN_URL, "accept-encoding": "gzip", "accept": "text/html"})

        sts, data = self.getPageCF(cItem['url'], params)
        #printDBG(data)
        if not sts:
            return

        movieId = self.cm.ph.getSearchGroups(data, '''data-movie-id=['"]([^'^"]+?)['"]''')[0]
        printDBG("movieId ------->" + movieId)

        trailerUrl = ''
        linksPageUrl = ''

        links = re.findall('''<a[^>]*?class="btn btn-xemnow pull-right"[^>]*?href=['"]([^'^"]+?)['"][^>]*?>(.*?)</a>''', data, re.S)
        for l in links:
            if 'Trailer' in l[1]:
                trailerUrl = l[0]
            elif 'STREAM' in l[1]:
                linksPageUrl = l[0]

        # trailer section
        if trailerUrl:
            if trailerUrl == "javascript:":
                # find url in javascript code
                printDBG("HDFilmeTV.exploreItem. Find trailer url in javascript code")
                movieData = self.getMovieDatainJS(data)
                if 'id' in movieData:
                    trailerUrl = self.getTrailerUrlinJS(data, movieData)
                    printDBG("trailerUrl: \"%s\" " % trailerUrl)
                    params['referer'] = movieData['url']
                    sts, trailer_data = self.getPageCF(trailerUrl, params)
                    if not sts:
                        return
                    #printDBG(data)

                    # find url in iframe
                    #<iframe class="film-screen-content" width="100%" height="100%" frameborder="0" allowfullscreen="" allow="autoplay" src="https://www.youtube.com/embed/JH0WldpM8Hw?autohide=1&fs=1&modestbranding=1&iv_load_policy=3&rel=0&showinfo=0&version=2&hd=0&fs=0&enablejsapi=1&playerapiid=ytplayer&autoplay=1&loop=1"></iframe>

                    tmp = self.cm.ph.getDataBeetwenMarkers(trailer_data, '<iframe', '</iframe>')[1]
                    trailerUrl = self.cm.ph.getSearchGroups(tmp, '''src=['"]([^'^"]+?)['"]''')[0]
                    params = dict(cItem)
                    params.update({'good_for_fav': False, 'title': '%s [%s]' % (cItem['title'], _('Trailer')), 'urls': [{'name': 'trailer', 'url': strwithmeta(trailerUrl.replace('&amp;', '&'), {'trailer': 1}), 'need_resolve': 1}]})
                    self.addVideo(params)
            else:
                trailerUrl = self.getFullUrl(trailerUrl)
                params = dict(cItem)
                params.update({'good_for_fav': False, 'title': '%s [%s]' % (cItem['title'], _('Trailer')), 'urls': [{'name': 'trailer', 'url': strwithmeta(trailerUrl.replace('&amp;', '&'), {'trailer': 1}), 'need_resolve': 1}]})
                self.addVideo(params)

        # find links page url
        # example
        #<a title="The Ranch staffel 4 Stream" class="btn btn-xemnow pull-right" style="margin-left:5px" href="https://hdfilme.cx/the-ranch-staffel-4-13803-stream/folge-1">
        printDBG("HDFilmeTV.exploreItem. Find url of page with links - often url + '/deutsch' ")

        sts, linkspage_data = self.getPageCF(linksPageUrl, params)
        if not sts:
            return

        #printDBG(data)
        #printDBG(">>>>>>>>>>>>>>>>>>>>>>>>")

        episodesTab = []
        episodesLinks = {}

        data = []
        parts = self.cm.ph.getAllItemsBeetwenMarkers(linkspage_data, '<section class="box">', '</section>')
        for part in parts:
            data_part = self.cm.ph.getAllItemsBeetwenMarkers(part, '<i class="fa fa-chevron-right">', '</ul>') #'<ul class="list-inline list-film"'
            if data_part:
                data.extend(data_part)

        for server in data:
            serverName = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(server, '<i ', '</div>')[1])
            serverData = ph.findall(server, '<li>', '</li>')
            for link in serverData:
                #printDBG("----->" + link)
                episodeName = self.cleanHtmlStr(link)
                episodeUrl = self.getFullUrl(self.cm.ph.getSearchGroups(link, '''href=['"]([^'^"]+?)['"]''')[0])
                episodeId = self.cm.ph.getSearchGroups(link, '''data-episode-id=['"]([^'^"]+?)['"]''')[0]

                if not episodeUrl.startswith('http'):
                    continue
                if episodeName not in episodesTab:
                    episodesTab.append(episodeName)
                    episodesLinks[episodeName] = []

                params = {'name': serverName, 'url': strwithmeta(episodeUrl.replace('&amp;', '&'), {'episodeId': episodeId, 'movieId': movieId}), 'need_resolve': 1}
                #printDBG("------------->" + str(params))
                episodesLinks[episodeName].append(params)

        baseTitleReObj = re.compile('''staffel\s*[0-9]+?$''', flags=re.IGNORECASE)
        baseTitle = cItem['title']
        season = self.cm.ph.getSearchGroups(cItem['url'], '''staf[f]+?el-([0-9]+?)-''')[0]
        if season == '':
            season = self.cm.ph.getSearchGroups(baseTitle, '''staffel\s*([0-9]+?)$''', ignoreCase=True)[0]
            if season != '':
                baseTitle = baseTitleReObj.sub('', baseTitle, 1).strip()

        try:
            episodesTab.sort(key=lambda item: self.c_int(item))
        except Exception:
            printExc()
        for episode in episodesTab:
            title = baseTitle
            if season != '':
                title += ': ' + 's%se%s' % (season.zfill(2), episode.zfill(2))
            elif len(episodesTab) > 1:
                title += ': ' + 'e%s' % (episode.zfill(2))
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': title, 'urls': episodesLinks[episode]})
            self.addVideo(params)

    def getLinksForVideo(self, cItem):
        printDBG("HDFilmeTV.getLinksForVideo [%s]" % cItem)
        return cItem.get('urls', [])

    def getVideoLinks(self, videoUrl):
        printDBG("HDFilmeTV.getVideoLinks [%s]" % videoUrl)
        urlTab = []

        if isinstance(videoUrl, strwithmeta):
            if 'trailer' in videoUrl.meta:
                printDBG("--------> Trailer Url: %s" % videoUrl)
                return self.up.getVideoLinkExt(videoUrl)

            if 'episodeId' in videoUrl.meta:
                episode_id = videoUrl.meta['episodeId']
            if 'movieId' in videoUrl.meta:
                movie_id = videoUrl.meta['movieId']
            else:
                movie_id = ''

        params = MergeDicts(self.defaultParams, {'user-agent': self.USER_AGENT, 'referer': videoUrl, "accept-encoding": "gzip", "accept": "text/html"})

        sts, data = self.getPageCF(videoUrl, params)
        printDBG(data)
        if not sts:
            return []

        url = self.cm.ph.getDataBeetwenMarkers(data, '$( "#play-area-wrapper" ).load( "', '"', False)[1]

        if len(url) > 1:

            if movie_id == '':
                url = self.getFullUrl(url + episode_id + "?")
            else:
                url = self.getFullUrl(url + movie_id + '/' + episode_id + "?")
            printDBG("video link---->" + url)
            sts, tmp = self.getPage(url, params)
            #printDBG (tmp)
            #printDBG ("+++++++++++++++++")

            if sts:
                url = self.cm.ph.getDataBeetwenMarkers(tmp, 'window.urlVideo = "', '"', False)[1]
                url = strwithmeta(url, {'Accept': '*/*', 'Referer': self.getMainUrl(), 'Origin': self.getMainUrl()[:-1], 'User-Agent': self.USER_AGENT})
                url.meta['iptv_m3u8_seg_download_retry'] = 10
                urlTab.extend(getDirectM3U8Playlist(url, checkExt=False, checkContent=True, sortWithMaxBitrate=999999999))

                printDBG("------->" + url)

                '''
                url = strwithmeta(url, {'Accept':'*/*', 'Referer':self.getMainUrl(), 'Origin':self.getMainUrl()[:-1], 'User-Agent':self.defaultParams['header']['User-Agent']})
                printDBG(">> TYPE: " + type)
                if 'mp4' in type or 'flv' in type:
                    urlTab.append({'name':str(item['label']), 'url':url})
                elif 'hls' in type or 'm3u8' in type:
                    url.meta['iptv_m3u8_seg_download_retry'] = 10
                    urlTab.extend(getDirectM3U8Playlist(url, checkExt=False, checkContent=True, sortWithMaxBitrate=999999999))

                if len(urlTab):
                    return urlTab
                '''
        return urlTab

    def getFavouriteData(self, cItem):
        printDBG('HDFilmeTV.getFavouriteData')
        return json.dumps(cItem)

    def getLinksForFavourite(self, fav_data):
        printDBG('HDFilmeTV.getLinksForFavourite')
        links = []
        try:
            cItem = byteify(json.loads(fav_data))
            links = self.getLinksForVideo(cItem)
        except Exception:
            printExc()
        return links

    def setInitListFromFavouriteItem(self, fav_data):
        printDBG('HDFilmeTV.setInitListFromFavouriteItem')
        try:
            params = byteify(json.loads(fav_data))
        except Exception:
            params = {}
            printExc()
        self.addDir(params)
        return True

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("HDFilmeTV.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['search_pattern'] = urllib.quote(searchPattern)
        cItem['url'] = self.SEARCH_URL
        self.listItems(cItem, 'explore_item')

    def getArticleContent(self, cItem):
        printDBG("HDFilmeTV.getArticleContent [%s]" % cItem)
        retTab = []

        sts, data = self.getPage(cItem['url'], self.defaultParams)
        if not sts:
            return retTab

        data = self.cm.ph.getDataBeetwenMarkers(data, '<div id="main">', '<div class="row">')[1]

        icon = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''src=['"]([^'^"]+?)['"]''')[0])
        if icon == '':
            icon = cItem.get('icon', '')

        title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<b class="text-blue title-film">', '</b>', False)[1])
        if title == '':
            title = cItem['title']

        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div class="caption">', '</div>', False)[1])

        descData = self.cm.ph.getDataBeetwenMarkers(data, '<div class="movie-info pull-left">', '</div>', False)[1]
        descData = self.cm.ph.getAllItemsBeetwenMarkers(descData, '<p', '</p>', caseSensitive=False)
        descTabMap = {"Genre": "genre",
                      "IMDB": "rating",
                      "Bewertung": "rated",
                      "Veröffentlichungsjahr": "year",
                      "Regisseur": "director",
                      "Schauspieler": "actors",
                      "Staat": "country",
                      "Zeit": "duration",
                      }

        otherInfo = {}
        for item in descData:
            item = item.split('</span>')
            if len(item) < 2:
                continue
            key = self.cleanHtmlStr(item[0]).replace(':', '').strip()
            val = self.cleanHtmlStr(item[1])
            for dKey in descTabMap:
                if dKey in key:
                    if descTabMap[dKey] == 'rating':
                        val += ' IMDB'
                    otherInfo[descTabMap[dKey]] = val
                    break

        views = self.cm.ph.getSearchGroups(data, '''Aufrufe[^>]*?([0-9]+?)[^0-9]''')[0]
        if views != '':
            otherInfo['views'] = views

        return [{'title': self.cleanHtmlStr(title), 'text': desc, 'images': [{'title': '', 'url': self.getIconUrl(icon)}], 'other_info': otherInfo}]

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
        elif category == 'list_filters':
            if filter == 'genre':
                nextFilter = 'country'
                nextCategory = 'list_filters'
            elif filter == 'country':
                nextFilter = 'sort'
                nextCategory = 'list_filters'
            else:
                nextFilter = ''
                nextCategory = 'list_items'
            self.listFilters(self.currItem, nextCategory, nextFilter)
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
        # for now we must disable favourites due to problem with links extraction for types other than movie
        CHostBase.__init__(self, HDFilmeTV(), True, favouriteTypes=[])

    def getArticleContent(self, Index=0):
        retCode = RetHost.ERROR
        retlist = []
        if not self.isValidIndex(Index):
            return RetHost(retCode, value=retlist)
        cItem = self.host.currList[Index]

        if cItem['type'] != 'video' and cItem.get('category', '') != 'explore_item':
            return RetHost(retCode, value=retlist)
        hList = self.host.getArticleContent(cItem)
        for item in hList:
            title = item.get('title', '')
            text = item.get('text', '')
            images = item.get("images", [])
            othersInfo = item.get('other_info', '')
            retlist.append(ArticleContent(title=title, text=text, images=images, richDescParams=othersInfo))
        return RetHost(RetHost.OK, value=retlist)
