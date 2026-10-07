# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026
# Spryciarze.pl - Polish how-to video guides (computers, cooking, DIY, hobby, sport, beauty, ...).
# 03.10.2026 - revival + rewrite for the current site: category tree from /kategorie
#   (www + the komputery/kulinaria/kobieta/sport sub-domains), "card" grids with "/page:N" pagination,
#   search /szukaj/<phrase>/film/page:N, player.spryciarze.pl/embed/<slug> = own MP4 ("mediaFiles")
#   or a YouTube embed + watched flag / downloaded flag / sidecar / favourites.
#   NOTE: the sub-domains serve an expired TLS certificate - works with the default
#   "https - validate SSL certificates: No".
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
###################################################
# FOREIGN import
###################################################
import re
###################################################


def GetConfigList():
    return []


def gettytul():
    return 'https://www.spryciarze.pl/'


CARD_RE = re.compile(r'<div class="card text-gray[^"]*">\s*<a href="([^"]+/zobacz/[^"]+)">\s*<img src="([^"]*)"[^>]*alt="([^"]*)"', re.DOTALL)
SLUG_RE = re.compile(r'/zobacz/([^/?#"]+)')


class Spryciarze(GenericFolderWatchedScraperMixin, CBaseHostClass):
    PLAYER_URL = 'https://player.spryciarze.pl/embed/%s'
    FAV_FIELDS = ('name', 'category', 'type', 'url', 'slug', 'title', 'icon', 'desc')

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'spryciarze', 'cookie': 'spryciarze.cookie'})
        self.MAIN_URL = 'https://www.spryciarze.pl/'
        self.DEFAULT_ICON_URL = 'https://www.spryciarze.pl/img/logotypes/logo-main.png'
        self.HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.catCache = []
        self.watchedHelper = IPTVWatchedHelper('spryciarze')
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ''
            if cItem.get('type', '') == 'video':
                slug = str(cItem.get('slug', '') or '').strip()
                return 'video:%s' % slug if slug else ''
            return ''
        except Exception:
            printExc()
        return ''

    ###################################################
    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    def _parseCatCards(self, data):
        # [{'title', 'url', 'subs': [(title, url), ...]}, ...] from the "card-header" boxes
        cats = []
        for block in data.split('<div class="card-header bg-light">')[1:]:
            header, _sep, body = block.partition('<div class="card-body">')
            url = self.cm.ph.getSearchGroups(header, r'<a href="([^"]+)"')[0]
            title = self.cleanHtmlStr(re.sub(r'<small>.*?</small>', '', header, flags=re.DOTALL))
            if not url or not title:
                continue
            body = body.split('</ul>', 1)[0]
            subs = []
            for surl, stitle in re.findall(r'<a class="[^"]*"\s+href="([^"]+)">(.*?)</a>', body, re.DOTALL):
                if surl.rstrip('/') == url.rstrip('/'):
                    continue
                count = self.cm.ph.getSearchGroups(stitle, r'<small>\((\d+)\)</small>')[0]
                stitle = self.cleanHtmlStr(re.sub(r'<small>.*?</small>', '', stitle, flags=re.DOTALL))
                if stitle:
                    subs.append((stitle, surl, count))
            cats.append({'title': title, 'url': url, 'subs': subs})
        return cats

    ###################################################
    # lists
    ###################################################
    def listMainCategories(self, cItem):
        if not self.catCache:
            sts, data = self.getPage(self.getFullUrl('/kategorie'))
            if not sts:
                return
            data = self.cm.ph.getDataBeetwenMarkers(data, 'py-5 bg-light-v2', '<footer', False)[1]
            self.catCache = self._parseCatCards(data)
        for cat in self.catCache:
            params = dict(cItem)
            params.update({'category': 'list_subcats', 'title': cat['title'], 'url': cat['url'], 'good_for_fav': True})
            self.addDir(params)

    def listSubCategories(self, cItem):
        cat = None
        for item in self.catCache:
            if item['url'] == cItem['url']:
                cat = item
        if cat is None:
            self.listMainCategories({})
            self.currList = []
            for item in self.catCache:
                if item['url'] == cItem['url']:
                    cat = item
        # the sub-domains (komputery, kulinaria, ...) list their videos under /film/wszystkie-filmy,
        # their /kategorie page only holds the category boxes
        allUrl = cItem['url']
        if allUrl.rstrip('/').endswith('/kategorie'):
            allUrl = allUrl.rstrip('/')[:-len('/kategorie')] + '/film/wszystkie-filmy'
        params = dict(cItem)
        params.update({'category': 'list_items', 'title': _('All'), 'url': allUrl})
        self.addDir(params)
        for title, url, count in (cat or {}).get('subs', []):
            params = dict(cItem)
            params.update({'category': 'list_items', 'title': title, 'url': url, 'good_for_fav': True,
                           'desc': ('%s: %s' % (_('Videos'), count)) if count else ''})
            self.addDir(params)

    def listItems(self, cItem):
        url = cItem['url']
        sts, data = self.getPage(url)
        if not sts:
            return
        # sub-categories of this category (side box whose header links to the same page) - first page only
        if '/page:' not in url and not cItem.get('search_pattern'):
            for cat in self._parseCatCards(data):
                if cat['url'].rstrip('/') != url.rstrip('/'):
                    continue
                for title, surl, count in cat['subs']:
                    params = stripPagerKeys(dict(cItem))
                    params.update({'category': 'list_items', 'title': title, 'url': surl, 'good_for_fav': True,
                                   'desc': ('%s: %s' % (_('Videos'), count)) if count else ''})
                    self.addDir(params)
        hasNext = bool(self.cm.ph.getSearchGroups(data, r'<a class="page-link" href="([^"]+)" rel="next"')[0])
        # "Strona 2 z 2738"
        page, lastPage = self.cm.ph.getSearchGroups(data, r'<span class="page-link">\s*\w+\s+(\d+)\s+\w+\s+(\d+)\s*</span>', 2)
        page = int(page) if page.isdigit() else int(self.cm.ph.getSearchGroups(url, r'/page:(\d+)')[0] or 1)
        lastPage = int(lastPage) if lastPage.isdigit() else 0
        seen = set()
        for vurl, icon, title in CARD_RE.findall(data):
            slug = SLUG_RE.search(vurl)
            title = self.cleanHtmlStr(title)
            if not slug or not title or slug.group(1) in seen:
                continue
            seen.add(slug.group(1))
            params = {'name': 'category', 'good_for_fav': True, 'title': title, 'url': vurl, 'slug': slug.group(1),
                      'icon': icon, 'desc': ''}
            self.addVideo(params)
        if seen:
            tpl = re.sub(r'/page:\d+/?$', '', url.rstrip('/')) + '/page:{page}'
            addPagingItems(self, cItem, page, hasNext, lastPage, tpl)

    def listSearchResult(self, cItem, searchPattern, searchType):
        params = dict(cItem)
        params.update({'url': self.getFullUrl('/szukaj/%s/film/page:1' % urllib_quote_plus(searchPattern)), 'search_pattern': searchPattern})
        self.listItems(params)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG('Spryciarze.getLinksForVideo [%s]' % cItem.get('slug', ''))
        slug = cItem.get('slug', '')
        if not slug:
            return []
        playerUrl = self.PLAYER_URL % slug
        params = dict(self.defaultParams)
        params['header'] = dict(self.HEADER)
        params['header']['Referer'] = cItem.get('url', self.MAIN_URL)
        sts, data = self.getPage(playerUrl, params)
        if not sts:
            return []
        urlTab = []
        ytId = self.cm.ph.getSearchGroups(data, r'youtube(?:-nocookie)?\.com/embed/([A-Za-z0-9_-]{11})')[0]
        if ytId:
            urlTab.append({'name': 'YouTube', 'url': 'https://www.youtube.com/watch?v=%s' % ytId, 'need_resolve': 1})
        files = self.cm.ph.getSearchGroups(data, r'"mediaFiles"\s*:\s*(\[.*?\])', 1, True)[0]
        if files:
            try:
                for item in json_loads(files):
                    src = item.get('src', '')
                    if not src:
                        continue
                    kind = (item.get('type', '') or '').split('/')[-1].upper() or 'MP4'
                    if kind == 'WEBM':
                        continue   # same video, the MP4 plays everywhere
                    urlTab.append({'name': kind, 'url': strwithmeta(src, {'Referer': 'https://player.spryciarze.pl/', 'User-Agent': self.HEADER['User-Agent']}), 'need_resolve': 0})
            except Exception:
                printExc()
        if not urlTab:
            SetIPTVPlayerLastHostError(_('No stream available'))
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled(), ''))

    def getVideoLinks(self, videoUrl):
        printDBG('Spryciarze.getVideoLinks [%s]' % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO: the VideoObject (ld+json) of the video page
    ###################################################
    def getArticleContent(self, cItem):
        printDBG('Spryciarze.getArticleContent [%s]' % cItem.get('url', ''))
        title, text, icon, other = cItem.get('title', ''), '', cItem.get('icon', ''), {}
        sts, data = self.getPage(cItem.get('url', '')) if cItem.get('url') else (False, '')
        if sts:
            block = self.cm.ph.getDataBeetwenMarkers(data, '"@type": "VideoObject"', '</script>', False)[1]

            def field(key):
                return self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)"%s"\s*:\s*"(.*?)",\s*\n' % key)[0].replace('&amp;', '&'))
            title = field('name') or title
            text = field('description')
            icon = field('thumbnailUrl') or icon
            uploaded = field('uploadDate')[:10]
            if uploaded:
                other['released'] = uploaded
            author = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'"author"\s*:\s*\{[^}]*"name"\s*:\s*"([^"]+)"')[0])
            if author:
                other['creator'] = author
        return [{'title': title, 'text': text, 'images': [{'title': '', 'url': icon}] if icon else [], 'other_info': other}]

    ###################################################
    # favourites
    ###################################################
    def getFavouriteData(self, cItem):
        try:
            if cItem.get('slug'):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('Spryciarze.handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get('name', None)
        category = self.currItem.get('category', '')
        printDBG('Spryciarze.handleService: name[%s] category[%s]' % (name, category))
        self.currList = []

        if name is None:
            tab = [{'category': 'list_items', 'title': _('Latest'), 'url': self.getFullUrl('/film/wszystkie-filmy')},
                   {'category': 'list_cats', 'title': _('Categories')}] + self.searchItems()
            self.listsTab(tab, {'name': 'category'})
        elif category == 'list_cats':
            self.listMainCategories(self.currItem)
        elif category == 'list_subcats':
            self.listSubCategories(self.currItem)
        elif category == 'list_items':
            self.listItems(self.currItem)
        elif category in ('search', 'search_next_page'):
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category', 'category': 'list_items'})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == 'search_history':
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _('Type: '))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Spryciarze(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('spryciarze')

    def withArticleContent(self, cItem):
        return cItem.get('type') == 'video' and bool(cItem.get('url'))
