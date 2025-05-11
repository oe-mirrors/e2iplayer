# -*- coding: utf-8 -*-
import json
from datetime import timedelta
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import urlparse
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta


def GetConfigList():
    return []


def gettytul():
    return 'https://moflix-stream.xyz/'


class MoflixStream(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'MoflixStream', 'cookie': 'MoflixStream.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'text/html'}
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.DEFAULT_ICON_URL = 'https://moflix-stream.xyz/storage/branding_media/18ffe280-a89b-4c07-99db-78556219aad2.png'
        self.MAIN_URL = None

    def menu(self):
        self.MAIN_URL = 'https://moflix-stream.xyz/'
        self.API_URL = 'https://moflix-stream.xyz/api/v1/channel/%s?channelType=channel&restriction=&paginate=simple&page='
        self.MENU = [
            {'category': 'list_items', 'title': 'Kürzlich hinzugefügt', 'link': self.API_URL % 'now-playing'},
            {'category': 'list_items', 'title': 'Filme', 'link': self.API_URL % 'movies'},
            {'category': 'list_items', 'title': 'Serien', 'link': self.API_URL % 'series'},
            {'category': 'list_items', 'title': 'Top bewertete Filme', 'link': self.API_URL % 'top-rated-movies'},
            {'category': 'list_items', 'title': 'Frisch hinzugefügte Serien', 'link': self.API_URL % 'trending-tv'},
            {'category': 'list_items', 'title': 'Kinder & Familien', 'link': self.API_URL % 'top-kids-liste'},
            {'category': 'Collection', 'title': "Collectionen"},
            {'category': 'search', 'title': _('Search'), 'search_item': True, },
            {'category': 'search_history', 'title': _('Search history'), }]
        self.COLLECTION = [
            {'category': 'list_items', 'title': 'American Pie Complete Collection', 'link': self.API_URL % 'the-american-pie-collection'},
            {'category': 'list_items', 'title': 'A Nightmare on Elm Street Collection', 'link': self.API_URL % 'a-nightmare-on-elm-street-collection'},
            {'category': 'list_items', 'title': 'Bud Spencer & Terence Hill Collection', 'link': self.API_URL % 'bud-spencer-terence-hill-collection'},
            {'category': 'list_items', 'title': 'DC Superhelden Collection', 'link': self.API_URL % 'the-dc-universum-collection'},
            {'category': 'list_items', 'title': 'Die Saga der Maschinen Collection', 'link': self.API_URL % 'transformers-die-saga-der-maschinen'},
            {'category': 'list_items', 'title': 'Fast & Furious Movie Collection', 'link': self.API_URL % 'fast-furious-movie-collection'},
            {'category': 'list_items', 'title': 'Halloween Movie Collection', 'link': self.API_URL % 'halloween-movie-collection'},
            {'category': 'list_items', 'title': 'Harry Potter Collection', 'link': self.API_URL % 'harry-potter-collection'},
            {'category': 'list_items', 'title': 'Herr der Ringe Collection', 'link': self.API_URL % 'der-herr-der-ringe-collection'},
            {'category': 'list_items', 'title': 'James Bond Collection', 'link': self.API_URL % 'the-james-bond-collection'},
            {'category': 'list_items', 'title': 'Jason Bourne Collection', 'link': self.API_URL % 'the-jason-bourne-collection'},
            {'category': 'list_items', 'title': 'Jurassic Park Collection', 'link': self.API_URL % 'the-jurassic-park-collection'},
            {'category': 'list_items', 'title': 'Marvel Cinematic Universe Collection', 'link': self.API_URL % 'the-marvel-cinematic-universe-collection'},
            {'category': 'list_items', 'title': 'Mission: Impossible Collection', 'link': self.API_URL % 'the-mission-impossible-collection'},
            {'category': 'list_items', 'title': 'Olsenbande Collection', 'link': self.API_URL % 'die-olsenbande-collection'},
            {'category': 'list_items', 'title': 'Planet der Affen Collection', 'link': self.API_URL % 'the-planet-der-affen-collection'},
            {'category': 'list_items', 'title': 'Rocky - The Knockout Collection', 'link': self.API_URL % 'rocky-the-knockout-collection'},
            {'category': 'list_items', 'title': 'Star Trek Kinofilm Collection', 'link': self.API_URL % 'the-star-trek-movies-collection'},
            {'category': 'list_items', 'title': 'Star Wars Collection', 'link': self.API_URL % 'the-star-wars-collection'},
            {'category': 'list_items', 'title': 'Scream Collection', 'link': self.API_URL % 'dein-albtraum-beginnt-hier-die-scream-collection'},
            {'category': 'list_items', 'title': 'Stirb Langsam Collection', 'link': self.API_URL % 'stirb-langsam-collection'},
            {'category': 'list_items', 'title': 'X-Men Collection', 'link': self.API_URL % 'x-men-collection'}]

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
        printDBG("MoflixStream.listItems |%s|" % cItem)
        url = cItem['link']
        nextPage = ''
        sts, data = self.getPage(url)
        if not sts:
            return
        data = json.loads(data)
        if 'channel' in data:
            data = data['channel'].get('content', [])
            nextPage = data.get('next_page', '')
            data = data.get('data', [])
        elif 'results' in data:
            data = data.get('results', [])
        for item in data:
            title = item['name']
            icon = item.get('poster', '')
            desc = item.get('description', '')
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': nextCategory, 'title': self.cleanHtmlStr(title), 'link': item.get('id', ''), 'icon': icon, 'desc': self.cleanHtmlStr(desc) if desc else ''})
            if item.get('is_series'):
                params.update({'category': 'list_seasons'})
                self.addDir(params)
            else:
                self.addVideo(params)
        if nextPage:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _("Next page"), 'link': url + str(nextPage)})
            self.addDir(params)

    def listSeasons(self, cItem):
        printDBG("MoflixStream.listSeasons")
        icon = cItem['icon']
        sts, data = self.getPage('%sapi/v1/titles/%s?loader=titlePage' % (self.MAIN_URL, cItem['link']))
        if not sts:
            return
        data = json.loads(data)
        for item in data.get('seasons', {}).get('data', []):
            sn = item.get('number')
            url = item.get('title_id')
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': 'list_episodes', 'title': '%s - Staffel%s' % (cItem['title'], sn), 'link': url, 'icon': icon, 'desc': cItem.get('desc', ''), 'season': sn})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("MoflixStream.listEpisodes")
        icon = cItem['icon']
        sts, data = self.getPage('%sapi/v1/titles/%s/seasons/%s?loader=seasonPage' % (self.MAIN_URL, cItem['link'], cItem['season']))
        if not sts:
            return
        data = json.loads(data)
        for item in data.get('episodes', {}).get('data', []):
            url = item.get('primary_video', {}).get('id') if item.get('primary_video') else ''
            if not url:
                continue
            title = '%s - Episode %s - %s' % (cItem.get('title'), item.get('episode_number'), item.get('name'))
            params = dict(cItem)
            params.update({'good_for_fav': True, 'title': title, 'link': url, 'icon': icon, 'desc': item.get('description', '')})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("MoflixStream.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['link'] = '%sapi/v1/search/%s?loader=searchPage' % (self.MAIN_URL, urllib_quote(searchPattern))
        self.listItems(cItem, 'video')

    def getLinksForVideo(self, cItem):
        printDBG("MoflixStream.getLinksForVideo [%s]" % cItem)
        linksTab = []
        url = cItem['link']
        if 'Episode' not in cItem['title']:
            sts, data = self.getPage('%sapi/v1/titles/%s?loader=titlePage' % (self.MAIN_URL, url))
            if not sts:
                return []
            data = json.loads(data)
            url = data.get('title', {}).get('primary_video', {}).get('id', '')
        sts, data = self.getPage('%sapi/v1/watch/%s' % (self.MAIN_URL, url), self.defaultParams)
        if not sts:
            return []
        data = json.loads(data)
        for item in data.get('alternative_videos', []):
            if item['src']:
                url = item['src']
                title = urlparse(url).netloc.split('/')[0]
                linksTab.append({'name': title.capitalize(), 'url': strwithmeta(url, {'Referer': self.MAIN_URL}), 'need_resolve': 1})
        if linksTab:
            cItem['url'] = linksTab
        return linksTab

    def getVideoLinks(self, videoUrl):
        printDBG("MoflixStream.getVideoLinks [%s]" % videoUrl)
        urlTab = []
        if self.cm.isValidUrl(videoUrl):
            return self.up.getVideoLinkExt(videoUrl)
        return urlTab

    def getArticleContent(self, cItem):
        printDBG("MoflixStream.getArticleContent [%s]" % cItem)
        sts, data = self.getPage('%sapi/v1/titles/%s?loader=titlePage' % (self.MAIN_URL, cItem['link']))
        otherInfo = {}
        if not sts:
            return []
        data = json.loads(data)
        desc = data.get('title', {}).get('description', '')
        cr = data.get('credits', {})
        actors = [actor.get('name') for actor in cr.get('actors', []) if actor.get('name')]
        if actors:
            otherInfo['actors'] = ', '.join(actors)
        director = [actor.get('name') for actor in cr.get('directing', []) if actor.get('name')]
        if director:
            otherInfo['director'] = ', '.join(director)
        creators = [actor.get('name') for actor in cr.get('writing', []) if actor.get('name')]
        if creators:
            otherInfo['creators'] = ', '.join(creators)
        duration = str(timedelta(seconds=int(data.get('title', {}).get('runtime')))) if str(data.get('title', {}).get('runtime')).isdigit() else ""
        if duration:
            otherInfo['duration'] = duration
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
        elif 'list_items' == category:
            self.listItems(self.currItem, 'video')
        elif 'list_seasons' == category:
            self.listSeasons(self.currItem)
        elif 'list_episodes' == category:
            self.listEpisodes(self.currItem)
        elif 'Collection' == category:
            self.listsTab(self.COLLECTION, self.currItem)
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
        CHostBase.__init__(self, MoflixStream(), True, [])

    def withArticleContent(self, cItem):
        return cItem.get('category', '') == 'video'
