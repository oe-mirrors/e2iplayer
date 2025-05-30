# -*- coding: utf-8 -*-
####################
#  2025 Team Jogi  #
####################
import json
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta


def GetConfigList():
    return []


def gettytul():
    return 'https://movie2k.ch/'


class Movie2K(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'Movie2K', 'cookie': 'Movie2K.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:138.0) Gecko/20100101 Firefox/138.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'text/html', 'Referer': gettytul()}
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.DEFAULT_ICON_URL = 'https://movie2k.ch/images/movie2k/logo3.png'
        self.MAIN_URL = None

    def menu(self):
        self.MAIN_URL = 'https://movie2k.ch/data/'
        self.API_URL = 'https://movie2k.ch/data/browse/?lang=2&type=%s&order_by=%s&page=1&limit=20'
        self.MENU = [
            {'category': 'movies', 'title': _("Movies")},
            {'category': 'series', 'title': _("Series")},
            {'category': 'list_genres', 'title': 'Genres'},
            {'category': 'search', 'title': _('Search'), 'search_item': True, },
            {'category': 'search_history', 'title': _('Search history'), }]
        self.MOVIES_MENU = [
            {'category': 'list_items', 'title': 'Filme Trending', 'url': self.API_URL % ('movies', 'trending')},
            {'category': 'list_items', 'title': 'Filme Updates', 'url': self.API_URL % ('movies', 'updates')},
            {'category': 'list_items', 'title': 'Filme Neu', 'url': self.API_URL % ('movies', 'Neu')},
            {'category': 'list_items', 'title': 'Filme Views', 'url': self.API_URL % ('movies', 'Views')},
            {'category': 'list_items', 'title': 'Filme Rating', 'url': self.API_URL % ('movies', 'Rating')}]
        self.SERIES_MENU = [
            {'category': 'list_items', 'title': 'Serien Trending', 'url': self.API_URL % ('tvseries', 'trending')},
            {'category': 'list_items', 'title': 'Serien Updates', 'url': self.API_URL % ('tvseries', 'updates')},
            {'category': 'list_items', 'title': 'Serien Neu', 'url': self.API_URL % ('tvseries', 'Neu')},
            {'category': 'list_items', 'title': 'Serien Views', 'url': self.API_URL % ('tvseries', 'Views')},
            {'category': 'list_items', 'title': 'Serien Rating', 'url': self.API_URL % ('tvseries', 'Rating')}]

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        addParams['cloudflare_params'] = {'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def getFullIconUrl(self, url):
        url = self.getFullUrl(url)
        if url == '':
            return ''
        cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE)
        return strwithmeta(url, {'Cookie': cookieHeader, 'User-Agent': self.USER_AGENT})

    def listItems(self, cItem, nextCategory):
        printDBG("Movie2K.listItems |%s|" % cItem)
        url = cItem['url']
        nextPage = ''
        sts, data = self.getPage(url)
        if not sts or 'movies' not in data:
            return
        data = json.loads(data)
        if data.get('message', '') == 'no results found':
            return
        curPage = data.get('pager', {}).get('currentPage', 0)
        totalPages = data.get('pager', {}).get('totalPages', 0)
        if curPage or totalPages:
            nextPage = url.replace('page={}'.format(curPage), 'page={}'.format(curPage + 1))
        for js in data.get('movies', []):
            if not js.get('title') or not js.get('_id'):
                continue
            title = js.get('title')
            url = '%swatch/?_id=%s' % (self.MAIN_URL, js.get('_id'))
            icon = 'https://image.tmdb.org/t/p/w300%s' % js.get('poster_path') if js.get('poster_path') else ''
            desc = 'Jahr: %s' % js.get('year') if js.get('year') else ''
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': nextCategory, 'title': self.cleanHtmlStr(title), 'url': url, 'icon': icon, 'desc': desc})
            if 'affel' in title:
                params.update({'category': 'list_episodes'})
                self.addDir(params)
            else:
                self.addVideo(params)
        if curPage < totalPages:
            params.update({'good_for_fav': False, 'category': 'list_items', 'title': _("Next page"), 'url': nextPage})
            self.addDir(params)

    def listGenres(self, cItem):
        printDBG("Movie2K.Genres")
        for title in ["Action", "Adventure", "Animation", "Comedy", "Crime", "Documentary", "Drama", "Family", "Fantasy", "History", "Horror", "Music", "Mystery", "Romance", "Reality-TV", "Sci-Fi", "Sport", "Thriller", "War", "Western"]:
            url = '%sbrowse/?lang=2&genre=%s&&order_by=Neu&page=1&limit=20' % (self.MAIN_URL, title)
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': 'list_items', 'title': title, 'url': url})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("Movie2K.listEpisodes")
        icon = cItem['icon']
        url = cItem['url']
        sts, data = self.getPage(url)
        if not sts:
            return
        data = json.loads(data)
        episodes = {int(stream['e']) for stream in data['streams'] if 'e' in stream}
        for episode in episodes:
            title = '%s - Episode %s' % (cItem.get('title'), episode)
            params = dict(cItem)
            params.update({'good_for_fav': True, 'title': title, 'url': url, 'icon': icon, 'desc': '', 'episode': episode})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Movie2K.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = '%sbrowse/?lang=2&keyword=%s&year=&networks=&rating=&votes=&genre=&country=&cast=&directors=&type=&order_by=&page=1&limit=20' % (self.MAIN_URL, urllib_quote(searchPattern))
        self.listItems(cItem, 'video')

    def getLinksForVideo(self, cItem):
        printDBG("Movie2K.getLinksForVideo [%s]" % cItem)
        urlsTab = []
        url = cItem['url']
        sts, data = self.getPage(url, self.defaultParams)
        if not sts:
            return []
        data = json.loads(data)
        for js in data.get('streams', []):
            if js.get('stream'):
                url = js.get('stream')
                if cItem.get('episode'):
                    if (cItem.get('episode') and cItem.get('episode') != js.get('e')) or js.get('deleted'):
                        continue
                if 'wolfstream' in url or 'voeunbl' in url or 'bigwarp' in url or 'bgwp' in url or 'wq.d-nl' in url or 'streamcloud' in url or 'strcloud' in url or 'tapecontent' in url or 'xcine.io' in url or 'streamkiste.tv' in url or 'tapeblocker' in url or 'hdfilme.me' in url:
                    continue
                if 'veev.to' in url or 'voeunbl' in url:
                    continue
                if url.startswith('//'):
                    url = 'https:' + url
                ref = js.get('url') if js.get('url') else gettytul()
                add = js.get('added') if js.get('added') else '1900-01-01'
                urlsTab.append({'name': "%s (%s)" % (self.up.getHostName(url).capitalize(), add[:10]), 'add': add, 'url': strwithmeta(url, {'Referer': ref}), 'need_resolve': 1})
        if urlsTab:
            urlsTab.sort(key=lambda x: x['add'], reverse=True)
        return urlsTab

    def getVideoLinks(self, videoUrl):
        printDBG("Movie2K.getVideoLinks [%s]" % videoUrl)
        urlTab = []
        if self.cm.isValidUrl(videoUrl):
            return self.up.getVideoLinkExt(videoUrl)
        return urlTab

    def getArticleContent(self, cItem):
        printDBG("Movie2K.getArticleContent [%s]" % cItem)
        sts, data = self.getPage(cItem['url'])
        otherInfo = {}
        if not sts:
            return []
        data = json.loads(data)
        desc = data.get('storyline', '')
        actors = ', '.join(data.get('cast', []))
        if actors:
            otherInfo['actors'] = actors
        duration = data.get('runtime', '')
        if duration:
            otherInfo['duration'] = "%s Min" % duration
        director = ', '.join(data.get('directors', []))
        if director:
            otherInfo['director'] = director
        title = cItem['title']
        icon = cItem.get('icon', self.DEFAULT_ICON_URL)
        return [{'title': self.cleanHtmlStr(title), 'text': self.cleanHtmlStr(desc), 'images': [{'title': '', 'url': self.getFullUrl(icon)}], 'other_info': otherInfo}]

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if self.MAIN_URL is None:
            self.menu()
        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []
        if name is None:
            self.getPage(self.MAIN_URL)
            self.listsTab(self.MENU, {'name': 'category'})
        elif 'movies' == category:
            self.listsTab(self.MOVIES_MENU, self.currItem)
        elif 'series' == category:
            self.listsTab(self.SERIES_MENU, self.currItem)
        elif 'list_items' == category:
            self.listItems(self.currItem, 'video')
        elif 'list_episodes' == category:
            self.listEpisodes(self.currItem)
        elif 'list_genres' == category:
            self.listGenres(self.currItem)
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category'})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Movie2K(), True, [])

    def withArticleContent(self, cItem):
        return cItem.get('category', '') == 'video'
