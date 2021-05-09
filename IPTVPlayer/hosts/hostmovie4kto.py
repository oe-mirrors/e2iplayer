# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem, ArticleContent, RetHost
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
###################################################

###################################################
# FOREIGN import
###################################################
from Components.config import config, ConfigSelection, ConfigText, getConfigListEntry
import re
import urllib
try:
    import json
except Exception:
    import simplejson as json
###################################################


###################################################
# E2 GUI COMMPONENTS
###################################################
from Components.config import config, ConfigSelection, ConfigText, getConfigListEntry
from Components.Language import language
###################################################


###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.movie4kto_language = ConfigSelection(default="", choices=[("", _("Auto")), ("en", _("English")), ("de", _("German")), ("fr", _("French")), ("es", _("Spanish")), ("it", _("Italian")), ("jp", _("Japanese")), ("tr", _("Turkish")), ("ru", _("Russian"))])
config.plugins.iptvplayer.movie4kto_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Language:"), config.plugins.iptvplayer.movie4kto_language))
    optionList.append(getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.movie4kto_alt_domain))
    return optionList
###################################################


def gettytul():
    return 'http://movie4k.org/'


class Movie4kTO(CBaseHostClass):

    def __init__(self):
        printDBG("Movie4kTO.__init__")
        CBaseHostClass.__init__(self, {'history': 'Movie4kTO', 'cookie': 'Movie4kTO.cookie'})
        self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.DEFAULT_ICON_URL = 'https://superrepo.org/static/images/icons/original/xplugin.video.movie4k.png.pagespeed.ic.l0TuslqM0i.jpg'

        self.USER_AGENT = 'Mozilla/5.0 (X11; Ubuntu; Linux i686; rv:21.0) Gecko/20100101 Firefox/21.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})

        self.MAIN_URL = 'http://movie4k.org/'
        self.SRCH_URL = self.getFullUrl('movies.php?list=search&search=')
        self.MOVIE_GENRES_URL = self.getFullUrl('movies-genre-%s-{0}.html')
        self.TV_SHOWS_GENRES_URL = self.getFullUrl('tvshows-genre-%s-{0}.html')

        self.MOVIES_ABC_URL = self.getFullUrl('movies-all-%s-{0}.html')
        self.TV_SHOWS_ABC_URL = self.getFullUrl('tvshows-all-%s.html')
        self.MAIN_CAT_TAB = [{'category': 'cat_movies', 'title': _('Movies'), },
                             {'category': 'cat_tv_shows', 'title': _('TV shows'), },
                             {'category': 'search', 'title': _('Search'), 'search_item': True},
                             {'category': 'search_history', 'title': _('Search history')}]

        self.MOVIES_CAT_TAB = [{'category': 'cat_movies_list1', 'title': _('Cinema movies'), 'url': self.getFullUrl('index.php')},
                               {'category': 'cat_movies_list2', 'title': _('Latest updates'), 'url': self.getFullUrl('movies-updates.html')},
                               {'category': 'cat_movies_abc', 'title': _('All movies'), 'url': self.getFullUrl('movies-all.html')},
                               {'category': 'cat_movies_genres', 'title': _('Genres'), 'url': self.getFullUrl('genres-movies.html')}]

        self.TV_SHOWS_CAT_TAB = [{'category': 'cat_tv_shows_list1', 'title': _('Featured'), 'url': self.getFullUrl('featuredtvshows.html')},
                                 {'category': 'cat_tv_shows_list2', 'title': _('Latest updates'), 'url': self.getFullUrl('tvshows-updates.html')},
                                 {'category': 'cat_tv_shows_abc', 'title': _('All TV shows'), 'url': self.getFullUrl('tvshows-all.html')},
                                 {'category': 'cat_tv_shows_genres', 'title': _('Genres'), 'url': self.getFullUrl('genres-tvshows.html')}]

    def getMainUrl(self):
        domain = config.plugins.iptvplayer.movie4kto_alt_domain.value.strip()
        if self.cm.isValidUrl(domain):
            if domain[-1] != '/':
                domain += '/'
            return domain
        return self.MAIN_URL

    def getPage(self, baseUrl, params={}, post_data=None):
        if params == {}:
            params = dict(self.defaultParams)
        lang = config.plugins.iptvplayer.movie4kto_language.value
        if '' == lang:
            try:
                lang = language.getActiveLanguage().split('_')[0]
            except Exception:
                lang = 'en'
        params['cookie_items'] = {'lang': lang}
        params['cloudflare_params'] = {'domain': self.up.getDomain(self.getMainUrl()), 'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT, 'full_url_handle': self.getFullUrl}
        return self.cm.getPageCFProtection(baseUrl, params, post_data)

    def getFullIconUrl(self, url):
        url = self.getFullUrl(url)
        if url == '':
            return ''
        cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE)
        if url.startswith('https://'):
            url = 'http' + url[5:]
        return strwithmeta(url, {'Cookie': cookieHeader, 'User-Agent': self.USER_AGENT})

    def listsTab(self, tab, cItem):
        printDBG("Movie4kTO.listsMainMenu")
        for item in tab:
            params = dict(cItem)
            params.update(item)
            params['name'] = 'category'
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("Movie4kTO.listEpisodes")
        url = self.getFullUrl(cItem['url'])
        sts, data = self.getPage(url)
        if not sts:
            return
        testMark = '<FORM name="seasonform">'
        m1 = ''
        m2 = ''
        found = False
        for test in [{'m1': ']="', 'm2': '";'}, {'m1': 'id="tablemoviesindex"', 'm2': '</TABLE>'}, {}, None]:
            if testMark not in data:
                if None == test:
                    continue
                m1 = test.get('m1', m1)
                m2 = test.get('m2', m2)
                sts, tmpData = self.cm.ph.getDataBeetwenMarkers(data, m1, m2, False)
                tmpData = tmpData.replace('\\"', '"')
                url = self.cm.ph.getSearchGroups(tmpData, 'href="([^"]+?)"')[0]
                if '' == url:
                    continue
                sts, data = self.getPage(self.getFullUrl(url))
                if not sts:
                    data = ''
            else:
                found = True
                break

        if not found:
            return
        sts, data = self.cm.ph.getDataBeetwenMarkers(data, testMark, '</table>', False)
        if not sts:
            return

        data = data.split('</FORM>')
        if len(data):
            del data[-1]
        if 0 == len(data):
            return
        seasons = re.compile('<OPTION[^>]+?>([^<]+?)</OPTION>').findall(data[0])
        episodesReObj = re.compile('<OPTION[^>]+?value="([^"]+?)"[^>]*?>([^<]+?)</OPTION>')
        del data[0]
        if len(seasons) != len(data):
            printDBG("Movie4kTO.listEpisodes >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> WRONG THIG HAPPENS seasons[%d] data[%d]", len(seasons), len(data))
        for idx in range(len(data)):
            if idx < len(seasons):
                season = seasons[idx]
            else:
                season = ''
            episodes = episodesReObj.findall(data[idx])
            for episod in episodes:
                url = episod[0]
                title = episod[1]
                if '' != url and '' != title:
                    params = dict(cItem)
                    params.update({'title': '%s, %s, %s' % (cItem['title'], season, title), 'url': self.getFullUrl(url)})
                    self.addVideo(params)

    def listsTVShow1(self, cItem, category):
        printDBG("Movie4kTO.listsTVShow1")
        return self.listsItems1(cItem, category, m1='<div id="maincontenttvshow">', sp='</table>')

    def listsMovies1(self, cItem):
        printDBG("Movie4kTO.listsMovies1")
        return self.listsItems1(cItem, None)

    def listsItems1(self, cItem, category, m1='<div id="maincontent2">', m2='</body>', sp='<div id="maincontent2">'):
        printDBG("Movie4kTO.listsMovies1")
        page = cItem.get('page', 1)
        url = self.getFullUrl(cItem['url'])
        if page > 1:
            if '?' in url:
                url += '?'
            else:
                url += '&'
            url += 'page=%s' % page

        sts, data = self.getPage(url)
        if not sts:
            return

        sts, nextPage = self.cm.ph.getDataBeetwenMarkers(data, 'class="pagination"', '</div>', False)
        if sts:
            if ('>{0}<'.format(page + 1)) in nextPage:
                nextPage = True
        if nextPage != True:
            nextPage = False

        sts, data = self.cm.ph.getDataBeetwenMarkers(data, m1, m2, False)
        if not sts:
            self.listsMovies2(cItem)
            return
        data = data.split(sp)

        for item in data:
            if None == category:
                sts, item = self.cm.ph.getDataBeetwenMarkers(item, '<div id="xline">', '<div id="xline">', False)
                if not sts:
                    continue

            url = self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0]
            icon = self.cm.ph.getSearchGroups(item, 'src="([^"]+?)"')[0]

            title = self.cm.ph.getSearchGroups(item, 'title="([^"]+?)"')[0]
            if '' == title:
                self.cm.ph.getSearchGroups(item, 'alt="([^"]+?)"')[0]
            lang = self.cm.ph.getSearchGroups(item, 'src="/img/([^"]+?)_small.png"')[0].replace('us', '').replace('_', '').replace('flag', '')
            #if '' == lang: lang = 'eng'
            if '' != lang:
                title += ' ({0})'.format(lang)

            desc = self.cm.ph.getDataBeetwenMarkers(item, 'class="info">', '</div>', False)[1]

            if '' != url and '' != title:
                params = dict(cItem)
                params.update({'category': category, 'title': self.cleanHtmlStr(title.replace('kostenlos', '')), 'url': self.getFullUrl(url), 'desc': self.cleanHtmlStr(desc), 'icon': self.getFullUrl(icon)})
                if None == category:
                    self.addVideo(params)
                else:
                    self.addDir(params)
        if nextPage:
            params = dict(cItem)
            params.update({'title': _('Next page'), 'page': page + 1})

    def listsTVShow2(self, cItem, category):
        printDBG("Movie4kTO.listsTVShow2")
        return self.listsItems2(cItem, category)#, m1='<div id="maincontenttvshow">', sp='</table>')

    def listsMovies2(self, cItem):
        printDBG("Movie4kTO.listsMovies2")
        return self.listsItems2(cItem, None)

    def listsItems2(self, cItem, category):
        printDBG("Movie4kTO.listsItems2")
        page = cItem.get('page', 1)
        baseUrl = self.getFullUrl(cItem['url'])
        if '{0}' in baseUrl:
            url = baseUrl.format(page)
        else:
            url = baseUrl

        sts, data = self.getPage(url)
        if not sts:
            return

        nextPage = False
        if '{0}' in baseUrl:
            tmp = baseUrl.format(page + 1).split('/')[-1]
            if tmp in data:
                nextPage = True

        # covers
        covers = {}
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '#coverPreview', '</script>', caseSensitive=False)[1]
        tmp = tmp.split('function()')
        for item in tmp:
            iconId = self.cm.ph.getSearchGroups(item, '''"#coverPreview([0-9]+?)"''')[0]
            if iconId == '':
                continue
            covers[iconId] = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''')[0])

        year = ''
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<TR', '</TR>', caseSensitive=False)
        for item in data:
            if "tdmovies" not in item:
                continue
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<a', '</a>', caseSensitive=False)[1])

            descTab = []
            # year
            tmp = self.cm.ph.getSearchGroups(item, '[>\s]([0-9]{4})[<\s]')[0]
            if tmp != '':
                year = tmp
            if year != '':
                descTab.append(year)
            # rating
            tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<STRONG>', '</TD>', caseSensitive=False)[1])
            if tmp != '':
                descTab.append(tmp)
            # lang
            tmp = self.cm.ph.getSearchGroups(item, 'src="/img/([^"]+?)_small.png"')[0].replace('us', '').replace('_', '').replace('flag', '')
            if tmp != '':
                descTab.append(tmp)

            iconId = self.cm.ph.getSearchGroups(item, '''"coverPreview([0-9]+?)"''')[0]

            params = dict(cItem)
            params.update({'category': category, 'title': title, 'url': url, 'desc': ' | '.join(descTab), 'icon': covers.get(iconId, '')})
            if None == category:
                self.addVideo(params)
            else:
                if category == 'search':
                    if '-serie-' in url:
                        params['category'] = 'episodes'
                        self.addDir(params)
                    else:
                        self.addVideo(params)
                else:
                    self.addDir(params)

        if nextPage:
            params = dict(cItem)
            params.update({'title': _("Next page"), 'page': page + 1})
            self.addDir(params)

    def listsTVShowABC(self, cItem, category):
        printDBG("Movie4kTO.listsTVShowABC")
        self.listsABC(cItem, category, self.TV_SHOWS_ABC_URL)

    def listsMoviesABC(self, cItem, category):
        printDBG("Movie4kTO.listsMoviesABC")
        self.listsABC(cItem, category, self.MOVIES_ABC_URL)

    def listsABC(self, cItem, category, ABC_URL):
        printDBG("Movie4kTO.listsABC")
        TAB = ['#1', 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z']
        for item in TAB:
            url = ABC_URL % item[-1]
            params = dict(cItem)
            params.update({'title': item[0], 'url': self.getFullUrl(url), 'category': category})
            self.addDir(params)

    def listsTVShowGenres(self, cItem, category):
        printDBG("Movie4kTO.listsTVShowGenres")
        self.listGenres(cItem, category, 'tvshows-genre-', self.TV_SHOWS_GENRES_URL)

    def listsMoviesGenres(self, cItem, category):
        printDBG("Movie4kTO.listsMoviesGenres")
        self.listGenres(cItem, category, 'movies-genre-', self.MOVIE_GENRES_URL)

    def listGenres(self, cItem, category, genreMarker, GENRES_URL):
        printDBG("Movie4kTO.listGenres")
        url = self.getFullUrl(cItem['url'])

        sts, data = self.getPage(url)
        if not sts:
            return
        sts, data = self.cm.ph.getDataBeetwenMarkers(data, '<TABLE id="tablemovies" cellpadding=5 cellspacing=5>', '</TABLE>', False)
        if not sts:
            return

        data = data.split('</TR>')
        if len(data):
            del data[-1]
        for item in data:

            genreID = self.cm.ph.getSearchGroups(item, genreMarker + '([0-9]+?)-')[0]
            title = self.cleanHtmlStr(item).replace('Random', '')

            if '' != genreID and '' != title:
                url = GENRES_URL % genreID
                params = dict(cItem)
                params.update({'title': title, 'url': self.getFullUrl(url), 'category': category})
                self.addDir(params)

    def listCategories(self, cItem, category):
        printDBG("Movie4kTO.listCategories")
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        sts, data = self.cm.ph.getDataBeetwenMarkers(data, 'aria-labelledby="menu_select">', '</ul>', False)
        if not sts:
            return
        data = data.split('</li>')
        if len(data):
            del data[-1]

        for item in data:
            url = self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0]
            url = url[0:url.rfind('/')]
            title = self.cleanHtmlStr(item)

            if '' != url and '' != title:
                params = dict(cItem)
                params.update({'title': title, 'url': self.getFullUrl(url), 'category': category})
                self.addDir(params)

    def listVideosFromCategory(self, cItem):
        printDBG("Movie4kTO.listVideosFromCategory")
        page = cItem.get('page', 1)
        url = cItem['url'] + "/{0},{1}.html".format(page, config.plugins.iptvplayer.Movie4kTO_sort.value)

        sts, data = self.getPage(url)
        if not sts:
            return

        if '"Następna"' in data:
            nextPage = True
        else:
            nextPage = False

        sts, data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="col-md-2" style="margin-bottom: 35px;">', '<script>', False)
        if not sts:
            return

        data = data.split('<div class="col-md-2" style="margin-bottom: 35px;">')
        if len(data):
            del data[0]

        for item in data:
            icon = self.cm.ph.getSearchGroups(item, 'src="([^"]+?)"')[0]
            url = self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0]
            title = self.cm.ph.getSearchGroups(item, 'title="([^"]+?)"')[0]
            if '' == title:
                title = self.cm.ph.getSearchGroups(item, 'alt="([^"]+?)"')[0]
            desc = ''
            if '' != url and '' != title:
                params = dict(cItem)
                params.update({'title': self.cleanHtmlStr(title.replace('kostenlos', '')), 'url': self.getFullUrl(url), 'desc': desc, 'icon': self.getFullUrl(icon)})
                self.addVideo(params)

        if nextPage:
            params = dict(cItem)
            params.update({'title': _('Next page'), 'page': page + 1})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Movie4kTO.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))

        cItem = dict(cItem)
        page = cItem.get('page', 1)
        if page == 1:
            cItem['url'] = self.SRCH_URL + urllib.quote(searchPattern)
            cItem['category'] = 'search'

        self.listsItems2(cItem, None)

    def getArticleContent(self, cItem):
        printDBG("Movie4kTO.getArticleContent [%s]" % cItem)
        retTab = []

        if 'url' not in cItem:
            return retTab

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return retTab

        title = self.cm.ph.getSearchGroups(data, 'title" content="([^"]+?)"')[0]
        icon = self.cm.ph.getSearchGroups(data, 'image" content="([^"]+?)"')[0]
        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div class="moviedescription">', '</div>', False)[1])

        return [{'title': title, 'text': desc, 'images': []}]

    def getLinksForVideo(self, cItem):
        printDBG("Movie4kTO.getLinksForVideo [%s]" % cItem)
        urlTab = []

        sts, pageData = self.getPage(cItem['url'])
        if not sts:
            return urlTab

        for idx in range(0, 2):
            if 0 != idx:
                sts, data = self.cm.ph.getDataBeetwenMarkers(pageData, 'links = new Array();', '</table>', False)
                data = data.replace('\\"', "'")
                data = re.compile(']="([^"]+?)";').findall(data) #, re.DOTALL
            else:
                #printDBG(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
                sts, data = self.cm.ph.getDataBeetwenMarkers(pageData, '<tr id="tablemoviesindex2"', '</table>', False)
                data = data.split('<tr id="tablemoviesindex2"')
                for idx in range(len(data)):
                    for marker in ['"<SCRIPT"', 'links = new Array();']:
                        tmpIdx = data[idx].find(marker)
                        if tmpIdx > 0:
                            data[idx] = data[idx][:tmpIdx]
                    data[idx] = data[idx].strip()
                    if not data[idx].startswith('<'):
                        data[idx] = '<' + data[idx]
                #printDBG(data)

            for item in data:
                url = self.cm.ph.getSearchGroups(item, '''href=["']([^"']+?)['"]''')[0]
                title = self.cleanHtmlStr(item)
                title += ' ' + self.cm.ph.getSearchGroups(item, '/img/smileys/([0-9]+?)\.gif')[0]

                if '' != url and '' != title:
                    urlTab.append({'name': title, 'need_resolve': 1, 'url': self.getFullUrl(url)})

        if 0 == len(urlTab):
            urlTab.append({'name': 'main url', 'need_resolve': 1, 'url': cItem['url']})

        for idx in range(len(urlTab)):
            urlTab[idx]['name'] = urlTab[idx]['name'].split('Quality:')[0]

        doSort = True
        for item in urlTab:
            if '' == self.cm.ph.getSearchGroups(item['name'], '''([0-9]{2}/[0-9]{2}/[0-9]{4})''')[0]:
                doSort = False
                break
        if doSort:
            urlTab.sort(key=lambda item: item['name'], reverse=True)
        return urlTab

    def getVideoLinks(self, url):
        printDBG("Movie4kTO.getVideoLinks [%s]" % url)
        urlTab = []

        sts, data = self.getPage(url)
        if not sts:
            return urlTab

        videoUrl = self.cm.ph.getSearchGroups(data, '<a target="_blank" href="([^"]+?)"')[0]
        if '' == videoUrl:
            videoUrl = self.cm.ph.getDataBeetwenMarkers(data, '-Download-', 'id="underplayer"', False)[1]
            videoUrl = self.cm.ph.getSearchGroups(videoUrl, '<iframe[^>]+?src="(http[^"]+?)"[^>]*?>')[0]

        videoUrl = self.getFullUrl(videoUrl)
        urlTab = self.up.getVideoLinkExt(videoUrl)
        return urlTab

    def getFavouriteData(self, cItem):
        return cItem['url']

    def getLinksForFavourite(self, fav_data):
        return self.getLinksForVideo({'url': fav_data})

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('Movie4kTO.handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", None)
        category = self.currItem.get("category", '')
        printDBG("Movie4kTO.handleService: ---------> name[%s], category[%s] " % (name, category))
        searchPattern = self.currItem.get("search_pattern", searchPattern)
        self.currList = []

    #MAIN MENU
        if None == name:
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})
    #TV SHOW
        elif 'cat_tv_shows' == category:
            self.listsTab(self.TV_SHOWS_CAT_TAB, self.currItem)
        elif 'cat_tv_shows_list1' == category:
            self.listsTVShow1(self.currItem, 'episodes')
        elif 'cat_tv_shows_list2' == category:
            self.listsTVShow2(self.currItem, 'episodes')
        elif 'cat_tv_shows_genres' == category:
            self.listsTVShowGenres(self.currItem, 'cat_tv_shows_list2')
        elif 'cat_tv_shows_abc' == category:
            self.listsTVShowABC(self.currItem, 'cat_tv_shows_list2')
        elif 'episodes' == category:
            self.listEpisodes(self.currItem)
    #MOVIES
        elif 'cat_movies' == category:
            self.listsTab(self.MOVIES_CAT_TAB, self.currItem)
        elif 'cat_movies_list1' == category:
            self.listsMovies1(self.currItem)
        elif 'cat_movies_list2' == category:
            self.listsMovies2(self.currItem)
        elif 'cat_movies_genres' == category:
            self.listsMoviesGenres(self.currItem, 'cat_movies_list2')
        elif 'cat_movies_abc' == category:
            self.listsMoviesABC(self.currItem, 'cat_movies_list2')
    #CATEGORIES
        elif 'categories' == category:
            self.listCategories(self.currItem, 'list_videos')
    #LIST_VIDEOS
        elif 'list_videos' == category:
            self.listVideosFromCategory(self.currItem)
    #WYSZUKAJ
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category'})
            self.listSearchResult(cItem, searchPattern, searchType)
    #HISTORIA WYSZUKIWANIA
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Movie4kTO(), True, [CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO])

    def getArticleContent(self, Index=0):
        retCode = RetHost.ERROR
        retlist = []
        if not self.isValidIndex(Index):
            return RetHost(retCode, value=retlist)

        hList = self.host.getArticleContent(self.host.currList[Index])
        for item in hList:
            title = item.get('title', '')
            text = item.get('text', '')
            images = item.get("images", [])
            retlist.append(ArticleContent(title=title, text=text, images=images))
        return RetHost(RetHost.OK, value=retlist)
    # end getArticleContent
