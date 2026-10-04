# -*- coding: utf-8 -*-
# ArabSciences (arabsciences.com) - Arabic documentaries (dubbed / subtitled), mostly 2011-2021.
# WordPress: categories, posts and search come from the REST API (/wp-json/wp/v2/). A post embeds
# its video as YouTube / Dailymotion / ok.ru / Google Drive iframes (resolved by urlparser) or as
# arabsciences.com/embed/<youtube id>/; VideoPress embeds are private now and skipped. Posts
# without a playable embed (plain articles) are left out of the lists.
# Last Modified: 03.10.2026 - new host: latest, categories, search, watched flag, favourites,
#   First page / Jump / Next page (page count from X-WP-TotalPages), sidecar
import re
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus


def GetConfigList():
    return []


def gettytul():
    return 'https://arabsciences.com/'


class ArabSciences(GenericFolderWatchedScraperMixin, CBaseHostClass):

    API = 'https://arabsciences.com/wp-json/wp/v2/'
    PER_PAGE = 30
    POST_FIELDS = 'id,date,link,title,excerpt,content,jetpack_featured_media_url,categories'
    # article-only categories (articles & magazines, health, site news) - no videos
    ARTICLE_CATS = (1689, 2010, 656)

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'ArabSciences', 'cookie': 'ArabSciences.cookie'})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = 'https://i0.wp.com/arabsciences.com/wp-content/uploads/2016/01/logo_arabsciences512.png'
        self.HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.HEADER['Accept'] = 'application/json'
        self._categories = {}
        self.watchedHelper = IPTVWatchedHelper('arabsciences')
        self.wfInitFolderCache()

    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ''
            if cItem.get('type', '') == 'video':
                return 'video:%s' % cItem['post_id'] if cItem.get('post_id') else ''
            if cItem.get('category', '') in ('list_posts', 'list_categories') and cItem.get('cat_id'):
                return 'folder:%s' % cItem['cat_id']
        except Exception:
            printExc()
        return ''

    def getJson(self, endpoint, withTotal=False):
        # withTotal: (json, X-WP-TotalPages) - the REST API sends the page count as a header
        sts, data = self.cm.getPage(self.API + endpoint, {'header': self.HEADER, 'with_metadata': withTotal, 'collect_all_headers': withTotal})
        result, total = [], 0
        if sts:
            try:
                total = int((getattr(data, 'meta', None) or {}).get('x-wp-totalpages', 0) or 0)
            except (TypeError, ValueError):
                total = 0
            try:
                result = json_loads(data)
            except Exception:
                printExc()
        return (result, total) if withTotal else result

    def getCategories(self, parent):
        # one level at a time - the site is slow and has ~450 categories
        if parent not in self._categories:
            cats = self.getJson('categories?parent=%s&per_page=100&hide_empty=true&_fields=id,name,count' % parent)
            self._categories[parent] = cats if isinstance(cats, list) else []
        return self._categories[parent]

    def listCategories(self, cItem):
        parent = cItem.get('cat_id', 0)
        cats = [c for c in self.getCategories(parent) if c.get('id') not in self.ARTICLE_CATS]
        if parent:
            if not cats:
                # a leaf: its posts right away ("Next page" then continues as list_posts)
                return self.listPosts(dict(cItem, category='list_posts', page=1))
            # a channel / series group: all its posts first, then its sub-categories
            params = dict(cItem)
            params.update({'category': 'list_posts', 'title': _('All'), 'page': 1})
            self.addDir(params)
        for cat in sorted(cats, key=lambda c: -(c.get('count') or 0)):
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': 'list_categories', 'title': self.cleanHtmlStr(cat.get('name', '')),
                           'cat_id': cat['id'], 'url': '%s?cat=%s' % (self.MAIN_URL, cat['id']), 'desc': _('%s posts') % cat.get('count', 0)})
            self.addDir(params)

    def getEmbeds(self, content):
        # playable embeds of a post, in page order, without its links to other posts
        out = []
        for url in re.findall(r'''<(?:iframe|source|video)[^>]+?(?:data-lazy-src|data-src|src)=["']([^"']+)["']''', content):
            url = url.replace('&#038;', '&').replace('&amp;', '&')
            if url.startswith('//'):
                url = 'https:' + url
            m = re.search(r'(?:arabsciences\.com|youtube(?:-nocookie)?\.com)/embed/([A-Za-z0-9_-]{11})', url)
            if m:
                url = 'https://www.youtube.com/watch?v=' + m.group(1)
            elif 'arabsciences.com' in url or 'videopress.com' in url or not url.startswith('http'):
                continue
            if url not in out:
                out.append(url)
        return out

    def addPosts(self, cItem, posts):
        added = 0
        for post in posts:
            embeds = self.getEmbeds((post.get('content') or {}).get('rendered', ''))
            if not embeds:
                continue
            title = self.cleanHtmlStr((post.get('title') or {}).get('rendered', ''))
            date = (post.get('date') or '')[:10]
            excerpt = self.cleanHtmlStr((post.get('excerpt') or {}).get('rendered', '')).replace('[&hellip;]', '').strip()
            self.addVideo({'good_for_fav': True, 'title': title, 'url': post.get('link', ''), 'post_id': post.get('id'),
                           'embeds': embeds, 'icon': post.get('jetpack_featured_media_url', ''),
                           'desc': '\n'.join(x for x in (date, excerpt) if x)})
            added += 1
        return added

    def listPosts(self, cItem, query=''):
        # the newest posts are mostly plain articles: read on (up to 5 API pages)
        # until the list has some videos
        page = startPage = max(1, int(cItem.get('page', 1) or 1))
        added = lastPage = 0
        posts = []
        for _i in range(5):
            endpoint = 'posts?per_page=%d&page=%d&_fields=%s' % (self.PER_PAGE, page, self.POST_FIELDS)
            if cItem.get('cat_id'):
                endpoint += '&categories=%s' % cItem['cat_id']
            else:
                endpoint += '&categories_exclude=%s' % ','.join(str(c) for c in self.ARTICLE_CATS)
            if query:
                endpoint += '&search=' + urllib_quote_plus(query)
            posts, lastPage = self.getJson(endpoint, True)
            if not isinstance(posts, list):
                return
            added += self.addPosts(cItem, posts)
            if added >= 10 or len(posts) < self.PER_PAGE:
                break
            page += 1
        # API paging; the folder url is constant and only serves "Jump" as the page template
        params = dict(cItem)
        if query:
            params.update({'category': 'search_next_page', 'search_pattern': query})
        hasNext = len(posts) >= self.PER_PAGE and (not lastPage or page < lastPage)
        addPagingItems(self, params, startPage, hasNext, lastPage, '' if query else cItem.get('url', ''), {'page': page + 1})

    def getLinksForVideo(self, cItem):
        printDBG('ArabSciences.getLinksForVideo [%s]' % cItem.get('url', ''))
        embeds = cItem.get('embeds')
        if not embeds:
            # favourite / older item without the embeds: read the post again
            post = self.getJson('posts/%s?_fields=content' % cItem.get('post_id')) if cItem.get('post_id') else {}
            embeds = self.getEmbeds(((post or {}).get('content') or {}).get('rendered', '')) if isinstance(post, dict) else []
        urlTab = []
        for url in embeds:
            name = self.up.getHostName(url, True) or 'link'
            urlTab.append({'name': name, 'url': url, 'need_resolve': 1})
        if not urlTab:
            SetIPTVPlayerLastHostError(_('No stream available'))
            return []
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def getVideoLinks(self, videoUrl):
        printDBG('ArabSciences.getVideoLinks [%s]' % videoUrl)
        try:
            if self.up.checkHostSupport(videoUrl) == 1:
                return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecarFromUrlMeta(videoUrl, IsSidecarEnabled()))
        except Exception:
            printExc()
        return []

    def getArticleContent(self, cItem):
        return [{'title': cItem.get('title', ''), 'text': cItem.get('desc', ''),
                 'images': [{'title': '', 'url': cItem.get('icon') or self.DEFAULT_ICON_URL}], 'other_info': {}}]

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('ArabSciences.handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get('name', None)
        category = self.currItem.get('category', '')
        searchPattern = self.currItem.get('search_pattern', searchPattern)
        self.currList = []

        if name is None:
            tab = [{'category': 'list_posts', 'title': _('Latest'), 'page': 1, 'url': self.MAIN_URL},
                   {'category': 'list_categories', 'title': _('Categories'), 'cat_id': 0}]
            self.listsTab(tab + self.searchItems(), {'name': 'category'})
        elif category == 'list_categories':
            self.listCategories(self.currItem)
        elif category == 'list_posts':
            self.listPosts(self.currItem)
        elif category in ('search', 'search_next_page'):
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category'})
            self.listPosts(cItem, searchPattern)
        elif category == 'search_history':
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc')
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, ArabSciences(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('arabsciences')

    def withArticleContent(self, cItem):
        return cItem.get('type', '') == 'video'
