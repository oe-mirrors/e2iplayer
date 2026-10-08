# -*- coding: utf-8 -*-
# Last Modified: 07.10.2026
#   The site's JSON api (/api/v1/...) is behind a Cloudflare challenge now, the html pages are not and carry
#   the same data as "window.bootstrapData" (loaders: channelPage, searchPage, titlePage, seasonPage, watchPage):
#   - channels (/channel/<slug>?page=N) with First page / Jump / Next page, collections read from the homepage
#   - search (/search/<q>), only titles (no people)
#   - series -> seasons (all season pages) -> episodes (all episode pages of the season)
#   - links: the title's mirrors (movies) / the watch page's alternative videos (episodes); the premium
#     stream needs a login and is left out
#   - watched flag (stable title id keys, series -> season -> episode), downloaded flag on the title / episode
#     url, favourites, name normalisation ("Title (Year)", "Show - SxxExx"), sidecar, INFO via moviemeta
#     (IMDb id of the title page) + the site's own data
import re
from datetime import timedelta

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta, getMetaByImdbId
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper


def GetConfigList():
    return []


def gettytul():
    return 'https://moflix-stream.xyz/'


BOOTSTRAP_RE = re.compile(r'window\.bootstrapData\s*=\s*(\{.*?\});\s*</script>', re.DOTALL)
# homepage sections that are not collections (sliders, top lists, news) or already in the main menu
NO_COLLECTION = ('trending-movies', 'top-10-movies-serien', 'latest-news', 'releasing-soon', 'now-playing', 'trending-tv',
                 'top-kids-liste', 'movies', 'series', 'top-rated-movies')
MAX_SUB_PAGES = 20  # season / episode pages read for one list


class MoflixStream(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ('name', 'category', 'type', 'url', 'title', 'icon', 'desc', 'title_id', 'video_id', 's_title', 's_season',
                  's_episode', 'meta_type', 'meta_title', 'meta_year')

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'MoflixStream', 'cookie': 'MoflixStream.cookie'})
        self.HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = gettytul() + 'storage/branding_media/b0d168ea-8d1b-4b40-9292-65e9a600d3c6.png'
        self.MENU = [
            {'category': 'list_items', 'title': _('Recently added'), 'url': self._channelUrl('now-playing')},
            {'category': 'list_items', 'title': _('Movies'), 'url': self._channelUrl('movies')},
            {'category': 'list_items', 'title': _('Series'), 'url': self._channelUrl('series')},
            {'category': 'list_items', 'title': _('Trending'), 'url': self._channelUrl('trending-tv')},
            {'category': 'list_items', 'title': _('Top rated movies'), 'url': self._channelUrl('top-rated-movies')},
            {'category': 'list_items', 'title': _('Family'), 'url': self._channelUrl('top-kids-liste')},
            {'category': 'list_collections', 'title': _('Collections')}] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper('moflixstream')
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams['cloudflare_params'] = {'cookie_file': self.COOKIE_FILE, 'User-Agent': self.HEADER.get('User-Agent')}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def _channelUrl(self, slug):
        return self.MAIN_URL + 'channel/' + slug

    @staticmethod
    def _slug(name):
        return re.sub(r'[^a-z0-9]+', '-', (name or '').lower()).strip('-') or 'title'

    def _titleUrl(self, titleId, name):
        return '%stitles/%s/%s' % (self.MAIN_URL, titleId, self._slug(name))

    @staticmethod
    def _icon(url):
        # list covers: TMDb's w342 instead of the original size (several MB on the box)
        return (url or '').replace('/t/p/original/', '/t/p/w342/')

    @staticmethod
    def _year(item):
        year = str(item.get('year') or '')
        if not year.isdigit():
            year = str(item.get('release_date') or '')[:4]
        return year if year.isdigit() else ''

    def _loader(self, url):
        # the page's bootstrapData loader dict (channelPage / searchPage / titlePage / ...), {} on errors
        sts, data = self.getPage(url)
        if not sts:
            return {}
        raw = BOOTSTRAP_RE.search(data or '')
        if not raw:
            printDBG('MoflixStream._loader no bootstrapData [%s]' % url)
            return {}
        try:
            loaders = json_loads(raw.group(1)).get('loaders') or {}
            for value in loaders.values():
                if isinstance(value, dict):
                    return value
        except Exception:
            printExc()
        return {}

    def getFavouriteData(self, cItem):
        try:
            if cItem.get('category') in ('mf_video', 'mf_series', 'mf_season'):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ''
            category = cItem.get('category', '')
            titleId = str(cItem.get('title_id', '') or '')
            if not titleId:
                return ''
            if category == 'mf_series':
                return 'series:%s' % titleId
            if category == 'mf_season':
                return 'season:%s:%s' % (titleId, cItem.get('s_season', ''))
            if category == 'mf_video':
                if cItem.get('s_episode'):
                    return 'video:%s:s%se%s' % (titleId, cItem.get('s_season', ''), cItem.get('s_episode'))
                return 'video:%s' % titleId
        except Exception:
            printExc()
        return ''

    ###################################################
    # lists
    ###################################################
    def _addTitle(self, cItem, item, normalize):
        if item.get('model_type', 'title') != 'title' or not item.get('id'):
            return False
        name = self.cleanHtmlStr(item.get('name', ''))
        if not name:
            return False
        year = self._year(item)
        isSeries = bool(item.get('is_series'))
        params = stripPagerKeys(dict(cItem), ('base_url',))
        params.update({'name': 'category', 'good_for_fav': True, 'url': self._titleUrl(item['id'], name), 'title_id': str(item['id']),
                       'icon': self._icon(item.get('poster', '')), 'desc': self.cleanHtmlStr(item.get('description', '') or ''),
                       'meta_type': 'tv' if isSeries else 'movie', 'meta_title': name, 'meta_year': year})
        for key in ('video_id', 's_title', 's_season', 's_episode'):
            params.pop(key, None)
        if isSeries:
            params.update({'category': 'mf_series', 'title': name, 's_title': name})
            self.addDir(params)
        else:
            title = name
            if normalize and year and year not in name:
                title = '%s (%s)' % (name, year)
            params.update({'category': 'mf_video', 'title': title})
            self.addVideo(params)
        return True

    def listItems(self, cItem):
        page = max(1, int(cItem.get('page', 1) or 1))
        baseUrl = cItem.get('base_url') or cItem['url']
        url = baseUrl if page <= 1 else '%s?page=%d' % (baseUrl, page)
        printDBG('MoflixStream.listItems [%s]' % url)
        content = (self._loader(url).get('channel') or {}).get('content') or {}
        normalize = IsMediaNamingNormalized()
        added = 0
        for item in content.get('data') or []:
            if self._addTitle(cItem, item, normalize):
                added += 1
        listItem = dict(cItem)
        listItem.update({'category': 'list_items', 'base_url': baseUrl, 'url': baseUrl})
        addPagingItems(self, listItem, page, bool(added) and bool(content.get('next_page')), 0, baseUrl + '?page={page}')

    def listCollections(self, cItem):
        printDBG('MoflixStream.listCollections')
        content = (self._loader(self.MAIN_URL).get('channel') or {}).get('content') or {}
        for item in content.get('data') or []:
            if item.get('model_type') != 'channel' or not item.get('slug') or item['slug'] in NO_COLLECTION:
                continue
            if (item.get('config') or {}).get('contentModel') not in ('movie', 'series', 'title'):
                continue
            params = stripPagerKeys(dict(cItem), ('base_url',))
            params.update({'good_for_fav': True, 'category': 'list_items', 'title': self.cleanHtmlStr(item.get('name', '')), 'url': self._channelUrl(item['slug'])})
            self.addDir(params)

    def listSeasons(self, cItem):
        printDBG('MoflixStream.listSeasons [%s]' % cItem.get('url'))
        seasons = []
        page, lastPage = 1, 1
        while page <= min(lastPage, MAX_SUB_PAGES):
            loader = self._loader(cItem['url'] if page == 1 else '%s?page=%d' % (cItem['url'], page))
            block = loader.get('seasons') or {}
            for item in block.get('data') or []:
                num = item.get('number')
                if num is not None and num not in [s[0] for s in seasons]:
                    seasons.append((num, item))
            lastPage = int(block.get('last_page') or 1)
            page += 1
        seasons.sort(key=lambda s: s[0])
        show = cItem.get('s_title') or cItem.get('title', '')
        for num, item in seasons:
            params = stripPagerKeys(dict(cItem), ('base_url',))
            params.update({'good_for_fav': True, 'category': 'mf_season', 'title': '%s - %s' % (show, _('Season %s') % num), 'url': '%s/season/%s' % (cItem['url'], num),
                           'title_url': cItem['url'], 's_title': show, 's_season': num})
            if item.get('poster'):
                params['icon'] = self._icon(item['poster'])
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG('MoflixStream.listEpisodes [%s]' % cItem.get('url'))
        normalize = IsMediaNamingNormalized()
        show = cItem.get('s_title') or cItem.get('title', '')
        season = cItem.get('s_season', '')
        seen = set()
        page = 1
        while page <= MAX_SUB_PAGES:
            block = self._loader(cItem['url'] if page == 1 else '%s?page=%d' % (cItem['url'], page)).get('episodes') or {}
            for item in block.get('data') or []:
                episode = item.get('episode_number')
                videoId = (item.get('primary_video') or {}).get('id')
                if episode is None or not videoId or episode in seen:
                    continue
                seen.add(episode)
                epName = self.cleanHtmlStr(item.get('name', '') or '')
                if normalize:
                    title = '%s - %s' % (show, formatSxxExx(season, episode))
                else:
                    title = ' - '.join(x for x in (show, _('Season %s') % season, '%s %s' % (_('Episode'), episode), epName) if x)
                params = stripPagerKeys(dict(cItem), ('base_url',))
                params.update({'good_for_fav': True, 'category': 'mf_video', 'title': title, 'url': '%s/episode/%s' % (cItem['url'], episode),
                               'video_id': str(videoId), 's_title': show, 's_season': season, 's_episode': episode,
                               'desc': ' - '.join(x for x in (epName, self.cleanHtmlStr(item.get('description', '') or '')) if x) or cItem.get('desc', '')})
                if item.get('poster'):
                    params['icon'] = self._icon(item['poster'])
                self.addVideo(params)
            if not block.get('next_page'):
                break
            page += 1

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG('MoflixStream.listSearchResult [%s]' % searchPattern)
        searchPattern = (searchPattern or '').strip()
        if not searchPattern:
            return
        loader = self._loader('%ssearch/%s' % (self.MAIN_URL, urllib_quote(searchPattern, safe='')))
        normalize = IsMediaNamingNormalized()
        cItem = dict(cItem)
        cItem.update({'name': 'category'})
        for item in loader.get('results') or []:
            self._addTitle(cItem, item, normalize)

    ###################################################
    # links
    ###################################################
    def _mirrors(self, videos):
        urlTab = []
        for item in videos or []:
            src = (item.get('src') or '').strip()
            if src.startswith('//'):
                src = 'https:' + src
            if item.get('type') != 'embed' or not self.cm.isValidUrl(src) or '/premium-player/' in src:
                continue
            name = self.up.getHostName(src).capitalize()
            extra = ' '.join(x for x in (item.get('quality') or '', (item.get('language') or '').upper()) if x and x.upper() != 'DE')
            urlTab.append({'name': ('%s (%s)' % (name, extra)) if extra else name, 'url': strwithmeta(src, {'Referer': self.MAIN_URL}), 'need_resolve': 1})
        return urlTab

    def getLinksForVideo(self, cItem):
        printDBG('MoflixStream.getLinksForVideo [%s]' % cItem.get('url'))
        urlTab = []
        videoId = cItem.get('video_id', '')
        if not videoId:
            title = self._loader(cItem['url']).get('title') or {}
            urlTab = self._mirrors(title.get('videos'))
            videoId = (title.get('primary_video') or {}).get('id', '')
        if not urlTab and videoId:
            urlTab = self._mirrors(self._loader('%swatch/%s' % (self.MAIN_URL, videoId)).get('alternative_videos'))
        if not urlTab:
            SetIPTVPlayerLastHostError(_('No stream available'))
            return []
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def getVideoLinks(self, videoUrl):
        printDBG('MoflixStream.getVideoLinks [%s]' % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecarFromUrlMeta(videoUrl, IsSidecarEnabled()))
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG('MoflixStream.getArticleContent [%s]' % cItem.get('url'))
        isEpisode = bool(cItem.get('s_episode'))
        pageUrl = cItem.get('title_url') or cItem.get('url', '')
        if isEpisode:
            pageUrl = pageUrl.split('/season/')[0]
        loader = self._loader(pageUrl) if pageUrl else {}
        title = loader.get('title') or {}
        info = {}
        year = self._year(title) or cItem.get('meta_year', '')
        if year:
            info['year'] = year
        if title.get('rating'):
            info['rating'] = '%s/10' % title['rating']
        runtime = title.get('runtime')
        if str(runtime).isdigit() and int(runtime):
            info['duration'] = str(timedelta(minutes=int(runtime)))
        credits = loader.get('credits') or {}
        for key, field in (('actors', 'actors'), ('director', 'directing'), ('creators', 'creators'), ('writer', 'writing')):
            names = [p.get('name') for p in (credits.get(field) or [])[:6] if p.get('name')]
            if names:
                info[key] = ', '.join(names)
        meta = {}
        metaType = cItem.get('meta_type') or ('tv' if title.get('is_series') else 'movie')
        try:
            if title.get('imdb_id'):
                meta = getMetaByImdbId(metaType, title['imdb_id'])
            if not meta and cItem.get('meta_title'):
                meta = getMeta(metaType, cItem['meta_title'], year)
        except Exception:
            printExc()
        info.update(meta.get('info', {}))
        siteText = self.cleanHtmlStr(title.get('description', '') or '')
        if isEpisode:
            text = cItem.get('desc', '') or meta.get('plot', '') or siteText
        else:
            text = meta.get('plot', '') or siteText or cItem.get('desc', '')
        icon = meta.get('poster') or self._icon(title.get('poster', '')) or cItem.get('icon', '')
        return [{'title': cItem.get('title', ''), 'text': text, 'images': [{'title': '', 'url': icon}] if icon else [], 'other_info': info}]

    ###################################################
    # service
    ###################################################
    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get('name', '')
        category = self.currItem.get('category', '')
        printDBG('MoflixStream.handleService name[%s] category[%s]' % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {'name': 'category'})
        elif category == 'list_items':
            self.listItems(self.currItem)
        elif category == 'list_collections':
            self.listCollections(self.currItem)
        elif category == 'mf_series':
            self.listSeasons(self.currItem)
        elif category == 'mf_season':
            self.listEpisodes(self.currItem)
        elif category in ['search', 'search_next_page']:
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category'})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == 'search_history':
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc')
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, MoflixStream(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('moflixstream')

    def withArticleContent(self, cItem):
        return cItem.get('category', '') in ('mf_video', 'mf_series', 'mf_season')
