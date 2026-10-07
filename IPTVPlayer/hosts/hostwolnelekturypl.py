# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026
# Wolne Lektury (wolnelektury.pl) - free Polish e-library of the Fundacja Nowoczesna Polska; this host
# plays its audiobooks (classic Polish and world literature read by actors).
# 03.10.2026 - revival + rewrite on the public JSON API: /api/audiobooks/ (all books with
#   audio, grouped locally by author / epoch / genre / kind, local search), /api/books/<slug>/ ("media":
#   MP3 + OGG per chapter, "children" for multi-part works) + watched flag (chapters and books) /
#   downloaded flag / sidecar / INFO from the book data / favourites.
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
###################################################


def GetConfigList():
    return []


def gettytul():
    return 'https://wolnelektury.pl/'


class WolnelekturyPL(GenericFolderWatchedScraperMixin, CBaseHostClass):
    API = 'https://wolnelektury.pl/api/'
    PAGE_SIZE = 50
    GROUPS_PAGE_SIZE = 100
    FAV_FIELDS = ('name', 'category', 'type', 'url', 'slug', 'title', 'icon', 'desc', 'book_title', 'ogg')

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'wolnelektury.pl', 'cookie': 'wolnelekturypl.cookie'})
        self.MAIN_URL = 'https://wolnelektury.pl/'
        self.DEFAULT_ICON_URL = 'https://static.wolnelektury.pl/img/favicon.42a6f6ccda01.png'
        self.HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.HEADER.update({'Accept': 'application/json'})
        self.defaultParams = {'header': self.HEADER}
        self.abCache = []
        self.watchedHelper = IPTVWatchedHelper('wolnelekturypl')
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ''
            if cItem.get('type', '') in ('audio', 'video'):
                url = self.wfNormalizeUrlKey(cItem.get('url', ''))
                return 'track:%s' % url if url else ''
            if cItem.get('category') == 'list_book' and cItem.get('slug'):
                return 'book:%s' % cItem['slug']
            return ''
        except Exception:
            printExc()
        return ''

    ###################################################
    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    def _json(self, url):
        sts, data = self.getPage(url)
        if not sts or not data:
            return None
        try:
            return json_loads(data)
        except Exception:
            printExc()
        return None

    def _audiobooks(self):
        if not self.abCache:
            data = self._json(self.API + 'audiobooks/')
            if isinstance(data, list):
                self.abCache = [item for item in data if isinstance(item, dict) and item.get('slug')]
        return self.abCache

    @staticmethod
    def _sortKey(text):
        return ensure_str(text or '').lower()

    def _addBook(self, cItem, item):
        title = self.cleanHtmlStr(item.get('title') or '')
        if not title or not item.get('slug'):
            return
        author = self.cleanHtmlStr(item.get('author') or '')
        desc = []
        if author:
            desc.append(author)
        tags = [self.cleanHtmlStr(item.get(key) or '') for key in ('kind', 'genre', 'epoch')]
        tags = ' | '.join([x for x in tags if x])
        if tags:
            desc.append(tags)
        icon = item.get('simple_thumb') or item.get('cover_thumb') or item.get('cover') or ''
        if icon and not icon.startswith('http'):
            icon = self.MAIN_URL + 'media/' + icon.lstrip('/')
        params = {'name': 'category', 'category': 'list_book', 'good_for_fav': True, 'slug': item['slug'],
                  'title': '%s - %s' % (author, title) if author and cItem.get('group_key') != 'author' else title,
                  'book_title': title, 'url': item.get('url') or '%skatalog/lektura/%s/' % (self.MAIN_URL, item['slug']),
                  'icon': icon, 'desc': '[/br]'.join(desc)}
        self.addDir(params)

    ###################################################
    # lists
    ###################################################
    def listAll(self, cItem):
        books = sorted(self._audiobooks(), key=lambda x: self._sortKey(x.get('title')))
        self._listPaged(cItem, books)

    def _listPaged(self, cItem, books):
        # local paging of the cached list (the url template only enables "Jump", the rows are cut by 'page')
        page = max(1, int(cItem.get('page', 1) or 1))
        for item in books[(page - 1) * self.PAGE_SIZE:page * self.PAGE_SIZE]:
            self._addBook(cItem, item)
        lastPage = (len(books) + self.PAGE_SIZE - 1) // self.PAGE_SIZE
        addPagingItems(self, cItem, page, page < lastPage, lastPage, self.MAIN_URL + '#page={page}')

    def listGroups(self, cItem):
        key = cItem['group_key']
        counts = {}
        for item in self._audiobooks():
            for value in (item.get(key) or '').split(','):
                value = value.strip()
                if value:
                    counts[value] = counts.get(value, 0) + 1
        values = sorted(counts.keys(), key=self._sortKey)
        # a few hundred authors: local paging like the book lists
        page = max(1, int(cItem.get('page', 1) or 1))
        for value in values[(page - 1) * self.GROUPS_PAGE_SIZE:page * self.GROUPS_PAGE_SIZE]:
            params = dict(cItem)
            params.update({'category': 'list_group', 'title': '%s (%d)' % (self.cleanHtmlStr(value), counts[value]),
                           'group_value': value, 'page': 1, 'good_for_fav': True})
            self.addDir(params)
        lastPage = (len(values) + self.GROUPS_PAGE_SIZE - 1) // self.GROUPS_PAGE_SIZE
        if lastPage > 1:
            addPagingItems(self, cItem, page, page < lastPage, lastPage, self.MAIN_URL + '#page={page}')

    def listGroup(self, cItem):
        key, value = cItem['group_key'], cItem['group_value']
        books = [item for item in self._audiobooks() if value in [v.strip() for v in (item.get(key) or '').split(',')]]
        books.sort(key=lambda x: self._sortKey(x.get('title')))
        self._listPaged(cItem, books)

    def listBook(self, cItem):
        data = self._json(self.API + 'books/%s/' % cItem['slug'])
        if not isinstance(data, dict):
            return
        bookTitle = cItem.get('book_title') or self.cleanHtmlStr(data.get('title') or '')
        icon = data.get('simple_thumb') or data.get('cover_thumb') or cItem.get('icon', '')
        tracks = {}
        order = []
        for media in (data.get('media') or []):
            mtype = (media.get('type') or '').lower()
            if mtype not in ('mp3', 'ogg') or not media.get('url'):
                continue
            name = self.cleanHtmlStr(media.get('name') or '')
            if name not in tracks:
                tracks[name] = {}
                order.append(name)
            tracks[name][mtype] = media
        for name in order:
            entry = tracks[name]
            main = entry.get('mp3') or entry.get('ogg')
            descTab = []
            if main.get('artist'):
                descTab.append('%s: %s' % (_('Read by'), self.cleanHtmlStr(main['artist'])))
            if main.get('director'):
                descTab.append('%s %s' % (_('Director:'), self.cleanHtmlStr(main['director'])))
            params = {'name': 'category', 'good_for_fav': True, 'slug': cItem['slug'], 'book_title': bookTitle,
                      'title': name or bookTitle, 'url': main['url'], 'icon': icon, 'desc': '[/br]'.join(descTab)}
            if entry.get('mp3') and entry.get('ogg'):
                params['ogg'] = entry['ogg']['url']
            self.addAudio(params)
        # multi-part works: the audio sits on the parts
        for child in (data.get('children') or []):
            if not isinstance(child, dict):
                continue
            slug = child.get('slug') or (child.get('href') or '').rstrip('/').rsplit('/', 1)[-1]
            title = self.cleanHtmlStr(child.get('title') or '')
            if not slug or not title:
                continue
            params = {'name': 'category', 'category': 'list_book', 'good_for_fav': True, 'slug': slug,
                      'title': title, 'book_title': title, 'url': child.get('url') or '', 'icon': icon,
                      'desc': cItem.get('desc', '')}
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        pattern = self._sortKey(searchPattern).strip()
        if not pattern:
            return
        books = [item for item in self._audiobooks()
                 if pattern in self._sortKey(item.get('title')) or pattern in self._sortKey(item.get('author'))]
        books.sort(key=lambda x: self._sortKey(x.get('title')))
        self._listPaged(cItem, books)

    ###################################################
    # links / info / favourites
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG('WolnelekturyPL.getLinksForVideo [%s]' % cItem.get('url', ''))
        url = cItem.get('url', '')
        if not self.cm.isValidUrl(url):
            return []
        urlTab = [{'name': 'MP3' if '.mp3' in url.lower() else 'OGG', 'url': url, 'need_resolve': 0}]
        if cItem.get('ogg'):
            urlTab.append({'name': 'OGG', 'url': cItem['ogg'], 'need_resolve': 0})
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled(), self.cleanHtmlStr(cItem.get('desc', ''))))

    def getArticleContent(self, cItem):
        printDBG('WolnelekturyPL.getArticleContent [%s]' % cItem.get('slug', ''))
        data = self._json(self.API + 'books/%s/' % cItem['slug']) if cItem.get('slug') else None
        if not isinstance(data, dict):
            data = {}
        otherInfo = {}

        def names(key):
            return ', '.join([self.cleanHtmlStr(x.get('name') or '') for x in (data.get(key) or []) if isinstance(x, dict) and x.get('name')])
        for key, field in (('authors', 'writers'), ('translators', 'translation'), ('epochs', 'category'), ('genres', 'genres'), ('kinds', 'type')):
            val = names(key)
            if val:
                otherInfo[field] = val
        if data.get('audio_length'):
            otherInfo['duration'] = str(data['audio_length'])
        text = self.cleanHtmlStr(((data.get('fragment_data') or {}).get('html')) or '') or self.cleanHtmlStr(cItem.get('desc', ''))
        icon = data.get('cover') or data.get('simple_cover') or cItem.get('icon', '')
        title = self.cleanHtmlStr(data.get('title') or '') or cItem.get('book_title') or cItem.get('title', '')
        return [{'title': title, 'text': text, 'images': [{'title': '', 'url': icon}] if icon else [], 'other_info': otherInfo}]

    def getFavouriteData(self, cItem):
        try:
            if cItem.get('slug'):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('WolnelekturyPL.handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get('name', None)
        category = self.currItem.get('category', '')
        searchPattern = self.currItem.get('search_pattern', searchPattern)
        printDBG('WolnelekturyPL.handleService: name[%s] category[%s]' % (name, category))
        self.currList = []

        if name is None:
            tab = [{'category': 'list_all', 'title': _('All audiobooks'), 'page': 1},
                   {'category': 'list_groups', 'title': _('Authors'), 'group_key': 'author'},
                   {'category': 'list_groups', 'title': _('Epochs'), 'group_key': 'epoch'},
                   {'category': 'list_groups', 'title': _('Genres'), 'group_key': 'genre'},
                   {'category': 'list_groups', 'title': _('Kinds'), 'group_key': 'kind'}]
            self.listsTab(tab + self.searchItems(), {'name': 'category'})
        elif category == 'list_all':
            self.listAll(self.currItem)
        elif category == 'list_groups':
            self.listGroups(self.currItem)
        elif category == 'list_group':
            self.listGroup(self.currItem)
        elif category == 'list_book':
            self.listBook(self.currItem)
        elif category in ('search', 'search_next_page'):
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category', 'category': 'search_next_page', 'search_pattern': searchPattern})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == 'search_history':
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _('Type: '))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, WolnelekturyPL(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('wolnelekturypl')

    def withArticleContent(self, cItem):
        return bool(cItem.get('slug'))
