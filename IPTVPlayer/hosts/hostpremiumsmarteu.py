# -*- coding: utf-8 -*-
# Last Modified: 10.10.2026
# PREMIUMSMART (premiumsmart.eu): Polish films and series (lektor / dubbing / napisy) from the site's JSON API,
#   played from Byse, Vidara, Streamtape, Abyss, FlyFile ... through urlparser
# 10.10.2026 - host standard: the API answers only with the session cookie of the site (401 without it - the host
#   was empty), films keyed on the title (not on its changing video id), series -> seasons -> episodes from the
#   API (more than 8 seasons, an episode list of more than 30, a series with one season opens its episodes),
#   watched flag (series -> season -> episode), favourites reopen without state (also the old rows), downloaded
#   marker, "Title (Year)" / "Show - SxxExx" names, INFO via moviemeta (IMDb id) merged with the site's data,
#   all sources of a title with language / quality, trailer last, sidecar, First/Jump/Next paging, English labels
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta, getMetaByImdbId
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str_deep
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
###################################################
# FOREIGN import
###################################################
import re
###################################################


def GetConfigList():
    return []


def gettytul():
    return 'https://premiumsmart.eu/'


class Premiumsmarteu(GenericFolderWatchedScraperMixin, CBaseHostClass):

    PER_PAGE = 50

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'premiumsmart.eu', 'cookie': 'premiumsmart.eu.cookie'})
        self.HEADER = self.cm.getDefaultHeader()
        self.MAIN_URL = gettytul()
        self.API_URL = self.MAIN_URL + 'api/v1/'
        self.API_HEADER = dict(self.HEADER)
        self.API_HEADER.update({'Accept': 'application/json, text/plain, */*', 'Referer': self.MAIN_URL})
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.DEFAULT_ICON_URL = self.MAIN_URL + 'storage/branding_media/9a5b1890-53ce-4052-9a83-862d97a6b285.png'
        self.watchedHelper = IPTVWatchedHelper('premiumsmarteu')
        self.wfInitFolderCache()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def _api(self, path):
        # the API answers 401 without the session cookie the start page sets
        url = path if path.startswith('http') else self.API_URL + path
        params = dict(self.defaultParams)
        params['header'] = self.API_HEADER
        for attempt in (0, 1):
            sts, data = self.getPage(url, params)
            if sts and data.lstrip().startswith('{'):
                try:
                    return ensure_str_deep(json_loads(data))
                except Exception:
                    printExc()
                    return {}
            if attempt == 0:
                self.getPage(self.MAIN_URL)
        return {}

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ''
            url = re.sub(r'^https?://[^/]+/api/v1/', '', str(cItem.get('url', '') or '').strip())
            prefix = {'list_seasons': 'series', 'list_episodes': 'season'}.get(cItem.get('category', ''), '')
            if cItem.get('type', '') == 'video':
                prefix = 'video'
            return '%s:%s' % (prefix, url) if (prefix and url.startswith(('titles/', 'watch/'))) else ''
        except Exception:
            printExc()
        return ''

    ###################################################
    # helpers
    ###################################################
    @staticmethod
    def _year(item):
        year = str(item.get('year', '') or '')
        if not year:
            year = str(item.get('release_date', '') or '')[:4]
        return year if re.match(r'^(?:19|20)\d\d$', year) else ''

    def _icon(self, url):
        return self.getFullIconUrl(url or '').replace('/original/', '/w500/')

    @staticmethod
    def _titleId(url):
        return re.search(r'/titles/(\d+)', url).group(1) if re.search(r'/titles/(\d+)', url) else ''

    def _addTitle(self, cItem, item):
        try:
            title = self.cleanHtmlStr(item.get('name', ''))
            if not title or not item.get('id'):
                return
            year = self._year(item)
            desc = []
            if year:
                desc.append(year)
            if item.get('rating'):
                desc.append('IMDb %s' % item['rating'])
            if (item.get('primary_video') or {}).get('language_type'):
                desc.append(item['primary_video']['language_type'])
            desc = ' | '.join(desc)
            if item.get('description'):
                desc += ('[/br]' if desc else '') + self.cleanHtmlStr(item['description'])
            params = stripPagerKeys(dict(cItem), ('f_order',))
            params.update({'name': 'category', 'good_for_fav': True, 'title': title, 'url': self.API_URL + 'titles/%s' % item['id'], 'icon': self._icon(item.get('poster')),
                           'desc': desc, 's_title': title, 's_year': year, 'imdb_id': item.get('imdb_id') or ''})
            if item.get('is_series'):
                params.update({'category': 'list_seasons', 'meta_type': 'tv'})
                self.addDir(params)
            else:
                if year and IsMediaNamingNormalized():
                    params['title'] = '%s (%s)' % (title, year)
                params.update({'category': 'video', 'meta_type': 'movie'})
                self.addVideo(params)
        except Exception:
            printExc()

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self, cItem):
        printDBG("Premiumsmarteu.listMainMenu")
        MENU = [{'category': 'list_sort', 'title': _('Movies'), 'url': self.API_URL + 'channel/filmy', 'good_for_fav': True},
                {'category': 'list_sort', 'title': _('Series'), 'url': self.API_URL + 'channel/seriale', 'good_for_fav': True}] + self.searchItems()
        self.listsTab(MENU, cItem)

    def listSort(self, cItem):
        printDBG("Premiumsmarteu.listSort")
        url = cItem['url'].split('?', 1)[0]
        SORT_TAB = [(_('Latest added'), 'created_at:desc'), (_('Most popular'), 'popularity:desc'), ('Release date', 'release_date:desc'),
                    (_('Top rated'), 'rating:desc')]
        if 'filmy' in url:
            SORT_TAB += [('Revenue', 'revenue:desc'), ('Budget', 'budget:desc')]
        for title, order in SORT_TAB:
            self.addDir({'name': 'category', 'category': 'list_items', 'title': title, 'url': '%s?perPage=%d&order=%s' % (url, self.PER_PAGE, order), 'good_for_fav': True})

    def listItems(self, cItem):
        printDBG("Premiumsmarteu.listItems [%s]" % cItem.get('url', ''))
        try:
            page = max(1, int(cItem.get('page', 1)))
        except (TypeError, ValueError):
            page = 1
        url = re.sub(r'[?&]page=\d+', '', cItem['url'])
        if 'perPage=' not in url:
            # rows of the old version: "...?perPage=50&order=..." or the bare channel url
            url += ('&' if '?' in url else '?') + 'perPage=%d' % self.PER_PAGE
        data = self._api(url + ('&page=%d' % page if page > 1 else ''))
        content = (data.get('channel') or {}).get('content') or {}
        for item in content.get('data') or []:
            self._addTitle(cItem, item)
        if self.currList:
            addPagingItems(self, dict(cItem, url=url), page, bool(content.get('next_page')), 0, url.replace('{', '{{').replace('}', '}}') + '&page={page}')

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Premiumsmarteu.listSearchResult [%s]" % searchPattern)
        data = self._api('search/%s?limit=50' % urllib_quote(searchPattern.strip()))
        for item in data.get('results') or []:
            if item.get('model_type', 'title') == 'title':
                self._addTitle({'name': 'category'}, item)
        if not self.currList:
            SetIPTVPlayerLastHostError(_('No matching entries found.'))

    def _pages(self, path, perPage):
        # all pages of a paginated API list
        items = []
        page = 1
        while page and page <= 10:
            data = self._api('%s?perPage=%d%s' % (path, perPage, '&page=%d' % page if page > 1 else ''))
            pagination = data.get('pagination') or {}
            items.extend(pagination.get('data') or [])
            page = pagination.get('next_page') or 0
        return items

    def listSeasons(self, cItem):
        printDBG("Premiumsmarteu.listSeasons [%s]" % cItem.get('url', ''))
        titleId = self._titleId(cItem['url'])
        if not titleId:
            return
        seasons = sorted([s for s in self._pages('titles/%s/seasons' % titleId, 30) if s.get('number') is not None and s.get('available_episodes_count', 1)],
                         key=lambda s: int(s['number']))
        if not seasons:
            SetIPTVPlayerLastHostError(_('No streams are available for this title yet.'))
            return
        url = self.API_URL + 'titles/%s' % titleId
        sTitle = cItem.get('s_title', '') or cItem.get('title', '')
        if len(seasons) == 1:
            self.listEpisodes(dict(cItem, category='list_episodes', season=str(seasons[0]['number']), url='%s#s%s' % (url, seasons[0]['number']), s_title=sTitle))
            return
        normalize = IsMediaNamingNormalized()
        for season in seasons:
            number = str(season['number'])
            seasonTag = formatSxxExx(number) if normalize else '%s %s' % (_('Season'), number)
            params = stripPagerKeys(dict(cItem))
            params.update({'good_for_fav': True, 'category': 'list_episodes', 'title': '%s - %s' % (sTitle, seasonTag), 'season': number, 's_title': sTitle,
                           'url': '%s#s%s' % (url, number), 'icon': self._icon(season.get('poster')) or cItem.get('icon', '')})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("Premiumsmarteu.listEpisodes [%s]" % cItem.get('url', ''))
        titleId = self._titleId(cItem['url'])
        season = str(cItem.get('season', '') or self.cm.ph.getSearchGroups(cItem['url'], r'#s(\d+)')[0])
        if not titleId or not season:
            return
        sTitle = cItem.get('s_title', '') or cItem.get('title', '')
        normalize = IsMediaNamingNormalized()
        for item in self._pages('titles/%s/seasons/%s/episodes' % (titleId, season), 100):
            try:
                episode = str(item.get('episode_number', '') or '')
                if not episode or item.get('has_sources') is False:
                    continue
                epName = self.cleanHtmlStr(item.get('name', ''))
                if normalize:
                    title = '%s - %s' % (sTitle, formatSxxExx(season, episode))
                else:
                    title = '%s - %s %s - %s %s' % (sTitle, _('Season'), season, _('Episode'), episode) + (': %s' % epName if epName else '')
                desc = [x for x in (epName, str(item.get('release_date', '') or '')[:10], self.cleanHtmlStr(item.get('description', ''))) if x]
                params = stripPagerKeys(dict(cItem))
                params.update({'good_for_fav': True, 'category': 'video', 'title': title, 's_title': sTitle, 'season': season, 'episode': episode, 'meta_type': 'tv',
                               'url': self.API_URL + 'titles/%s/seasons/%s/episodes/%s' % (titleId, season, episode),
                               'icon': self._icon(item.get('poster')) or cItem.get('icon', ''), 'desc': '[/br]'.join(desc)})
                self.addVideo(params)
            except Exception:
                printExc()

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("Premiumsmarteu.getLinksForVideo [%s]" % cItem.get('url', ''))
        path = cItem['url'].replace(self.API_URL, '')
        data = self._api(path)
        if '/watch/' in cItem['url']:
            # rows of the old version: the video id of the title
            videos = data.get('alternative_videos') or ([data['video']] if data.get('video') else [])
        else:
            videos = (data.get('episode') or data.get('title') or {}).get('videos') or []
        full, trailers = [], []
        for item in sorted(videos, key=lambda v: (v.get('order') or 99)):
            url = (item.get('src') or '').strip()
            if url.startswith('//'):
                url = 'https:' + url
            if not self.cm.isValidUrl(url):
                continue
            category = item.get('category', '') or 'full'
            if category == 'full':
                name = ' - '.join([x for x in (item.get('language_type', ''), ('%s %s' % (item.get('name', '') or self.up.getHostName(url), item.get('quality') or '')).strip()) if x])
                full.append({'name': name, 'url': strwithmeta(url, {'Referer': self.MAIN_URL}), 'need_resolve': 1})
            elif category == 'trailer' and not trailers:
                trailers.append({'name': '%s - %s' % (_('Trailer'), self.up.getHostName(url)), 'url': url.replace('/embed/', '/watch?v='), 'need_resolve': 1})
        linksTab = full + trailers
        if not full:
            SetIPTVPlayerLastHostError(_('No streams are available for this title yet.'))
        return applySidecarToLinks(linksTab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def getVideoLinks(self, videoUrl):
        printDBG("Premiumsmarteu.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecarFromUrlMeta(videoUrl, IsSidecarEnabled()))

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("Premiumsmarteu.getArticleContent [%s]" % cItem.get('url', ''))
        url = cItem.get('url', '')
        if '/watch/' in url:
            titleId = str(((self._api(url.replace(self.API_URL, '')) or {}).get('title') or {}).get('id', '') or '')
        else:
            titleId = self._titleId(url)
        data = self._api('titles/%s' % titleId) if titleId else {}
        title = data.get('title') or {}
        mediaType = 'tv' if (title.get('is_series') or cItem.get('meta_type') == 'tv' or cItem.get('category') in ('list_seasons', 'list_episodes')) else 'movie'
        info = {}
        genres = ', '.join([g.get('display_name', '') or g.get('name', '') for g in title.get('genres') or [] if isinstance(g, dict)])
        if genres:
            info['genres'] = genres
        countries = ', '.join([c.get('display_name', '') for c in title.get('production_countries') or [] if isinstance(c, dict) and c.get('display_name')])
        if countries:
            info['country'] = countries
        if title.get('original_title') and title.get('original_title') != title.get('name'):
            info['original_title'] = title['original_title']
        if title.get('runtime'):
            info['duration'] = '%s min' % title['runtime']
        if title.get('rating'):
            info['rating'] = str(title['rating'])
        if title.get('certification'):
            info['age_limit'] = str(title['certification']).upper()
        if title.get('release_date'):
            info['released'] = str(title['release_date'])[:10]
        credits = data.get('credits') or {}
        for key, src in (('directors', 'directing'), ('creators', 'creators'), ('actors', 'actors')):
            names = ', '.join([p.get('name', '') for p in (credits.get(src) or [])[:5] if isinstance(p, dict) and p.get('name')])
            if names:
                info[key] = names
        year = self._year(title) or cItem.get('s_year', '')
        meta = {}
        try:
            imdbId = title.get('imdb_id') or cItem.get('imdb_id', '')
            meta = getMetaByImdbId(mediaType, imdbId) if imdbId else {}
            if not meta:
                meta = getMeta(mediaType, title.get('original_title') or cItem.get('s_title', '') or cItem.get('title', ''), year)
        except Exception:
            printExc()
        metaInfo = dict(meta.get('info', {}))
        metaInfo.update(info)
        if year and 'year' not in metaInfo:
            metaInfo['year'] = year
        plot = self.cleanHtmlStr(title.get('description', ''))
        if cItem.get('episode'):
            text = cItem.get('desc', '') or plot
        else:
            text = plot or cItem.get('desc', '')
        if meta.get('plot') and meta['plot'] not in text and not cItem.get('episode'):
            text = '%s[/br][/br]%s' % (text, meta['plot']) if text else meta['plot']
        icon = cItem.get('icon', '') or self._icon(title.get('poster')) or meta.get('poster', '') or self.DEFAULT_ICON_URL
        return [{'title': cItem.get('title', '') or title.get('name', ''), 'text': text, 'images': [{'title': '', 'url': icon}], 'other_info': metaInfo}]

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("handleService: name[%s], category[%s] " % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu({'name': 'category'})
        elif category == 'list_sort':
            self.listSort(self.currItem)
        elif category == 'list_items':
            self.listItems(self.currItem)
        elif category == 'list_seasons':
            self.listSeasons(self.currItem)
        elif category == 'list_episodes':
            self.listEpisodes(self.currItem)
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category'})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc')
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Premiumsmarteu(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('premiumsmarteu')

    def withArticleContent(self, cItem):
        return cItem.get('type') == 'video' or cItem.get('category', '') in ('list_seasons', 'list_episodes')
