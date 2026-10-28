# -*- coding: utf-8 -*-
LAST_MODIFIED = "28.10.2026"
# 28.10.2026 - new host
#   volleybox.net (men, women.volleybox.net, beach.volleybox.net): the videos of the news feed and of a team /
#   player / tournament season ("<page>/movies", newest / best rated / most viewed), search of teams, players and
#   tournaments (ajax/get_tags_ajax); the videos are YouTube / Vimeo embeds, resolved by urlparser
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
###################################################
# FOREIGN import
###################################################
import re
###################################################


def GetConfigList():
    return []


def gettytul():
    return 'https://volleybox.net/'


# section -> (title, base url, gender of the search)
SECTIONS = (('men', 'Men', 'https://volleybox.net/', 'M'),
            ('women', 'Women', 'https://women.volleybox.net/', 'F'))
BEACH = ('beach', 'Beach', 'https://beach.volleybox.net/')
# data-movie-host: 1 = YouTube, 2 = Vimeo (the others are posts / links / Facebook without a usable player)
PLAYERS = {'1': 'https://www.youtube.com/watch?v=%s', '2': 'https://vimeo.com/%s'}
MOVIES_PAGE_SIZE = 30
# sort order of a /movies list -> label (msgids that exist already)
ORDERS = (('add_date', 'Latest'), ('rating', 'Top rated'), ('views', 'Most viewed'))
# search hit type -> label
KINDS = {'T': 'Team', 'P': 'Player', 'O': 'Tournament', 'S': 'Tournament'}
ITEM_RE = re.compile(r'data-movie-key="([^"]*)"\s+data-movie-host="([^"]*)"\s+data-item-type="movie_page"\s+data-movie-id="(\d+)"\s+data-url="([^"]+)"')


class Volleybox(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ('name', 'category', 'type', 'url', 'title', 'raw_title', 'icon', 'desc', 'author', 'movie_id', 'movie_key', 'movie_host', 'list_url', 'order')

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'volleybox', 'cookie': 'volleybox.cookie'})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = 'https://volleybox.net/media/img/logo/men/196-2026.png'
        self.HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper('volleybox')
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if isinstance(cItem, dict) and cItem.get('type') == 'video' and cItem.get('movie_id'):
                return 'video:%s' % cItem['movie_id']
        except Exception:
            printExc()
        return ''

    ###################################################
    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    def getFavouriteData(self, cItem):
        try:
            if cItem.get('type') == 'video' or cItem.get('category') in ('list_movies', 'list_entity'):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # listing
    ###################################################
    def listMain(self, cItem):
        # the latest videos of each section's news feed; sorted lists only exist per team / player / tournament (search)
        for _key, title, base in [s[:3] for s in SECTIONS] + [BEACH]:
            self.addDir(dict(cItem, category='list_news', title=title, base=base))
        self.listsTab(self.searchItems(), cItem)

    def _addItems(self, data):
        for block in data.split('<li class="')[1:]:
            m = ITEM_RE.search(block[:600])
            if not m:
                continue
            key, host, movieId, url = m.groups()
            if host not in PLAYERS or not key:
                continue
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'class="title">([^<]+)<')[0])
            if not title:
                continue
            date = self.cm.ph.getSearchGroups(block, r'<time[^>]+datetime="(\d{4}-\d\d-\d\d)')[0]
            author = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'class=" tooltip_item bold"[^>]*>([^<]+)<')[0])
            icon = 'https://i.ytimg.com/vi/%s/hqdefault.jpg' % key if host == '1' else ''
            desc = ' | '.join(x for x in (date, author) if x)
            self.addVideo({'name': 'category', 'type': 'video', 'title': title, 'url': url, 'icon': icon, 'desc': desc, 'author': author,
                           'movie_id': movieId, 'movie_key': key, 'movie_host': host, 'good_for_fav': True})

    def listNews(self, cItem):
        page = int(cItem.get('page', 1) or 1)
        tpl = cItem['base'].rstrip('/') + '/news/{page}'
        sts, data = self.getPage(tpl.format(page=page))
        if not sts:
            return
        self._addItems(data)
        pages = [int(n) for n in re.findall(r'href="[^"]*/news/(\d+)"', data)]
        addPagingItems(self, cItem, page, (page + 1) in pages, max(pages + [page]), tpl)

    def listMovies(self, cItem):
        # the video tab of a team / player / tournament season
        page = int(cItem.get('page', 1) or 1)
        order = cItem.get('order', 'add_date')
        tpl = '%s/movies?page={page}&orderValue=%s&orderDirection=desc' % (cItem['list_url'], order)
        # page 1 only without "page=" (with it a sorted list comes back empty), its pager is missing then
        url = tpl.format(page=page) if page > 1 else '%s/movies?orderValue=%s&orderDirection=desc' % (cItem['list_url'], order)
        sts, data = self.getPage(url)
        if not sts:
            return
        self._addItems(data)
        pages = [int(n) for n in re.findall(r'movies\?page=(\d+)', data)]
        hasNext = (page + 1) in pages if pages else len(re.findall(r'data-item-type="', data)) >= MOVIES_PAGE_SIZE
        addPagingItems(self, cItem, page, hasNext, max(pages + [page]) if pages else 0, tpl)

    def listEntity(self, cItem):
        # a search hit: its videos in the three orders
        for order, title in ORDERS:
            self.addDir(dict(cItem, category='list_movies', title='%s - %s' % (cItem['raw_title'], _(title)), order=order, good_for_fav=True))

    def listSearchResult(self, cItem, searchPattern, searchType):
        seen = set()
        for _key, section, base, gender in SECTIONS:
            post = {'query': searchPattern, 'searchedItems': 'players,teams,tournaments', 'ground': '"I"', 'gender': gender, 'mainSearchRequest': 'true'}
            params = dict(self.defaultParams)
            params['header'] = dict(self.HEADER, **{'X-Requested-With': 'XMLHttpRequest', 'Referer': base})
            sts, data = self.getPage(base + 'ajax/get_tags_ajax', params, post)
            if not sts:
                continue
            try:
                hits = json_loads(data)
            except Exception:
                printExc()
                continue
            for hit in hits if isinstance(hits, list) else []:
                link = (hit.get('link') or '').rstrip('/')
                title = self.cleanHtmlStr(hit.get('search') or '')
                if not self.cm.isValidUrl(link) or not title or link in seen:
                    continue
                seen.add(link)
                kind = KINDS.get(hit.get('type', ''), '')
                if kind == 'Tournament':
                    kind = _(kind)
                icon = self.getFullUrl(hit.get('image') or '', base) if hit.get('image') else ''
                desc = ' | '.join(x for x in (kind, section, self.cleanHtmlStr(hit.get('desc') or '')) if x)
                self.addDir(dict(cItem, category='list_entity', title='%s (%s)' % (title, section), raw_title=title, list_url=link, icon=icon, desc=desc,
                                 good_for_fav=True))

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("Volleybox.getLinksForVideo [%s]" % cItem.get('url', ''))
        key, host = cItem.get('movie_key', ''), cItem.get('movie_host', '')
        if host not in PLAYERS or not key:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        url = PLAYERS[host] % urllib_quote_plus(key)
        urlTab = [{'name': 'YouTube' if host == '1' else 'Vimeo', 'url': url, 'need_resolve': 1}]
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled(), cItem.get('desc', '')))

    def getVideoLinks(self, videoUrl):
        printDBG("Volleybox.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecarFromUrlMeta(videoUrl, IsSidecarEnabled()))

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("Volleybox.getArticleContent [%s]" % cItem.get('url', ''))
        title = cItem.get('title', '')
        icon = cItem.get('icon', '')
        text = cItem.get('desc', '')
        # the user who added the video (the site's description is often only a hashtag)
        other = {'source': cItem['author']} if cItem.get('author') else {}
        sts, data = self.getPage(cItem['url'])
        if sts:
            text = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta property="og:description" content="([^"]*)"')[0]) or text
            icon = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0] or icon
            released = self.cm.ph.getSearchGroups(data, r'<time[^>]+datetime="(\d{4}-\d\d-\d\d)')[0]
            if released:
                other['released'] = released
        return [{'title': title, 'text': text, 'images': [{'title': '', 'url': icon}] if icon else [], 'other_info': other}]

    ###################################################
    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("Volleybox.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMain({'name': 'category'})
        elif category == 'list_news':
            self.listNews(self.currItem)
        elif category == 'list_movies':
            self.listMovies(self.currItem)
        elif category == 'list_entity':
            self.listEntity(self.currItem)
        elif category in ('search', 'search_next_page'):
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category'})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == 'search_history':
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Volleybox(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('volleybox')

    def withArticleContent(self, cItem):
        return cItem.get('type') == 'video'
