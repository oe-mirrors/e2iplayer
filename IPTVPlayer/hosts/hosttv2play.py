# -*- coding: utf-8 -*-
# Last Modified: 10.10.2026
# 17.04.2025 - Blindspot
# 10.10.2026 - host standard: shows -> seasons -> ribbons -> videos with watched flag (show -> season -> ribbon
#   -> video), favourites on every level (they reopen from the slug / ribbon id alone), sidecar, INFO from the
#   API (episode lead, length, category, channel, age limit; show description), "Show - SxxExx" / dated names,
#   First/Next paging (shows 50 per page, ribbons, search), no API request per card any more (the ribbon cards
#   carry the player id), cast/article ribbons and premium (subscription) titles left out, geo-blocked titles
#   tell the user, no crash on a failed or empty answer, English option text
# 10.10.2026 - review: "Next page" of the shows / search also when the answer held premium titles (a page
#   with one premium show had none), favourites of the old version (shows, seasons, ribbons, "Műsorok")
#   reopen, py2: API texts as utf-8 str, no crash on a non-numeric length
###################################################
HOST_VERSION = "1.3"
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx, normalizeMediathekTitle
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str_deep
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_unquote
###################################################
# FOREIGN import
###################################################
import re
import time
from Components.config import config, ConfigYesNo, getConfigListEntry
###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.tv2play_quality = ConfigYesNo(default=True)
###################################################


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Select best available quality"), config.plugins.iptvplayer.tv2play_quality))
    return optionList


def gettytul():
    return 'https://tv2play.hu/'


API_URL = 'https://tv2play.hu/api'
# recommendation engine of the site: shows (CONTENT_LISTING) and search (SEARCH_RESULT), 50 per answer
GRREC_URL = 'https://tv2-prod.d-saas.com/grrec-tv2-prod-war/JSServlet4?rn=&cid=&ts=%d&rd=0,%s,800,[*platform:web;*domain:tv2play;%s*country:HU;*userAge:18;*pagingOffset:%d],[displayType;channel;title;itemId;duration;isExtra;ageLimit;showId;genre;availableFrom;director;isExclusive;lead;url;contentType;seriesTitle;availableUntil;showSlug;videoType;series;availableEpisode;imageUrl;totalEpisode;category;playerId;currentSeasonNumber;currentEpisodeNumber;part;isPremium]'
GRREC_PER_PAGE = 50


class TV2Play(GenericFolderWatchedScraperMixin, CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'tv2play', 'cookie': 'tv2play.cookie'})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "https://raw.githubusercontent.com/oe-mirrors/e2iplayer/refs/heads/gh-pages/Thumbnails/tv2play.png"
        self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper('tv2play')
        self.wfInitFolderCache()

    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    def _getJson(self, url):
        sts, data = self.getPage(url)
        if not sts or not data:
            return {}
        try:
            data = ensure_str_deep(json_loads(data))  # py2: utf-8 str, not unicode (labels mixed with "évad")
        except Exception:
            printExc()
            return {}
        return data if isinstance(data, dict) else {}

    def _icon(self, url):
        url = url or ''
        if url and not url.startswith('http'):
            url = self.getFullIconUrl(url.lstrip('/'))
        return url

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict) or cItem.get('search_item'):
                return ''
            if cItem.get('type') == 'video':
                slug = cItem.get('slug', '')
                return 'video:%s' % slug if slug else ''
            category = cItem.get('category', '')
            if category == 'tv2_show' and cItem.get('slug'):
                return 'folder:show:%s' % cItem['slug']
            if category == 'tv2_season' and cItem.get('slug'):
                return 'folder:season:%s:%s' % (cItem['slug'], cItem.get('season', ''))
            if category == 'tv2_ribbon' and cItem.get('ribbon_id'):
                return 'folder:ribbon:%s' % cItem['ribbon_id']
        except Exception:
            printExc()
        return ''

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self, cItem):
        printDBG('TV2Play.listMainMenu')
        MAIN_CAT_TAB = [{'category': 'list_shows', 'title': _('Shows'), 'good_for_fav': True}] + self.searchItems()
        self.listsTab(MAIN_CAT_TAB, cItem)

    def _grrec(self, widget, extra, page):
        """(free items, whether the answer was a full page) - premium titles still count for the paging"""
        url = GRREC_URL % (int(time.time()), widget, extra, (page - 1) * GRREC_PER_PAGE)
        sts, data = self.getPage(url)
        if not sts or not data:
            return [], False
        m = re.search(r'var data = (.*)};', data, re.S)
        if not m:
            return [], False
        try:
            items = ensure_str_deep(json_loads('%s}' % m.group(1))['recommendationWrappers'][0]['recommendation']['items'])
        except Exception:
            printExc()
            return [], False
        if not isinstance(items, list):
            return [], False
        return [i for i in items if isinstance(i, dict) and str(i.get('isPremium', 'false')) != 'true'], len(items) >= GRREC_PER_PAGE

    def _addShow(self, cItem, slug, title, icon, desc):
        params = stripPagerKeys(dict(cItem), ('query',))
        params.update({'good_for_fav': True, 'category': 'tv2_show', 'title': title, 'slug': slug, 'show_title': title, 'icon': icon, 'desc': desc})
        self.addDir(params)

    @staticmethod
    def _toInt(value, default=0):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _page(self, cItem):
        return max(1, self._toInt(cItem.get('page'), 1))

    def listShows(self, cItem):
        printDBG('TV2Play.listShows')
        page = self._page(cItem)
        items, hasNext = self._grrec('TV2_W_CONTENT_LISTING', '*currentContent:SHOW;', page)
        for i in items:
            if i.get('contentType') == 'SHOW' and i.get('url'):
                self._addShow(cItem, i['url'], urllib_unquote(i.get('title', '')), i.get('imageUrl', ''), urllib_unquote(i.get('lead', '')))
        addPagingItems(self, cItem, page, hasNext)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("TV2Play.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem.update({'category': 'list_search', 'query': searchPattern, 'page': 1})
        self.listSearch(cItem)

    def listSearch(self, cItem):
        page = self._page(cItem)
        items, hasNext = self._grrec('TV2_W_SEARCH_RESULT', '*query:%s;' % urllib_quote(cItem.get('query', '')), page)
        for i in items:
            ctype = i.get('contentType', '')
            if not i.get('url'):
                continue
            if ctype == 'SHOW':
                self._addShow(cItem, i['url'], urllib_unquote(i.get('title', '')), i.get('imageUrl', ''), urllib_unquote(i.get('lead', '')))
            elif ctype == 'VIDEO':
                card = {'slug': i['url'], 'title': urllib_unquote(i.get('title', '')), 'imageUrl': i.get('imageUrl', ''), 'lead': urllib_unquote(i.get('lead', '')),
                        'showTitle': urllib_unquote(i.get('seriesTitle', '')), 'contentLength': i.get('duration'),
                        'seriesInfo': {'seasonNr': i.get('currentSeasonNumber'), 'episodeNr': i.get('currentEpisodeNumber')}}
                self._addCard(stripPagerKeys(dict(cItem), ('query',)), card)
        addPagingItems(self, cItem, page, hasNext)

    def _showData(self, slug):
        return self._getJson('%s/search/%s' % (API_URL, slug))

    def listShow(self, cItem):
        printDBG('TV2Play.listShow [%s]' % cItem.get('slug'))
        data = self._showData(cItem.get('slug', ''))
        pages = [p for p in data.get('pages') or [] if isinstance(p, dict)]
        seasons = [s for s in data.get('seasonNumbers') or [] if s is not None]
        showTitle = cItem.get('show_title', '') or cItem.get('title', '')
        if seasons:
            for season in seasons:
                tag = formatSxxExx(season) if IsMediaNamingNormalized() else '%s. évad' % season
                params = stripPagerKeys(dict(cItem))
                params.update({'good_for_fav': True, 'category': 'tv2_season', 'title': '%s - %s' % (showTitle, tag), 'season': str(season), 'show_title': showTitle})
                self.addDir(params)
            return
        self._listRibbons(cItem, pages[0] if pages else {})

    def listSeason(self, cItem):
        data = self._showData(cItem.get('slug', ''))
        for page in data.get('pages') or []:
            if isinstance(page, dict) and str(page.get('seasonNr')) == str(cItem.get('season')):
                self._listRibbons(cItem, page)
                return

    def _listRibbons(self, cItem, page):
        ribbonIds = []
        for tab in page.get('tabs') or []:
            if isinstance(tab, dict) and tab.get('tabType') == 'RIBBON':
                ribbonIds.extend(tab.get('ribbonIds') or [])
        ribbons = []
        for ribbonId in ribbonIds:
            data = self._getJson('%s/ribbons/%s' % (API_URL, ribbonId))
            # cast / article ribbons have no videos
            if data.get('type') == 'VIDEO' and data.get('cards'):
                ribbons.append(data)
        if len(ribbons) == 1:
            self._listCards(dict(cItem, category='tv2_ribbon', ribbon_id=str(ribbons[0].get('id', ''))), ribbons[0].get('cards'), 1)
            return
        for ribbon in ribbons:
            params = stripPagerKeys(dict(cItem))
            params.update({'good_for_fav': True, 'category': 'tv2_ribbon', 'title': '%s - %s' % (cItem.get('show_title', '') or cItem.get('title', ''), urllib_unquote(ribbon.get('title', ''))),
                           'ribbon_id': str(ribbon.get('id', ''))})
            self.addDir(params)

    def listRibbon(self, cItem):
        page = self._page(cItem)
        data = self._getJson('%s/ribbons/%s/%d' % (API_URL, cItem.get('ribbon_id', ''), page - 1))
        self._listCards(cItem, data.get('cards'), page)

    def _listCards(self, cItem, cards, page):
        for card in cards or []:
            if isinstance(card, dict) and card.get('contentLength') and not card.get('isPremium'):
                self._addCard(cItem, card)
        if cards:
            # the API answers the next page or 404 - asked once, there is no total
            nextData = self._getJson('%s/ribbons/%s/%d' % (API_URL, cItem.get('ribbon_id', ''), page))
            addPagingItems(self, cItem, page, bool(nextData.get('cards')))

    @staticmethod
    def _duration(seconds):
        return '%d:%02d:%02d' % (seconds // 3600, seconds // 60 % 60, seconds % 60)

    def _addCard(self, cItem, card):
        slug = card.get('slug', '')
        if not slug:
            return
        title = urllib_unquote(card.get('title', ''))
        info = card.get('seriesInfo') or {}
        showTitle = urllib_unquote(card.get('showTitle', '') or '') or cItem.get('show_title', '')
        date = (card.get('availableFrom') or '')[:10]
        if IsMediaNamingNormalized() and info.get('episodeNr') and showTitle:
            season = info.get('seasonNr') or cItem.get('season') or 1
            dispTitle = '%s - %s' % (showTitle, formatSxxExx(season, info['episodeNr']))
        else:
            dispTitle = normalizeMediathekTitle(title, date=date)
        descTab = []
        seconds = self._toInt(card.get('contentLength'))
        if seconds:
            descTab.append(self._duration(seconds))
        if date:
            descTab.append(date)
        desc = ' | '.join(descTab)
        if card.get('lead'):
            desc += '[/br]' + self.cleanHtmlStr(card['lead'])
        params = stripPagerKeys(dict(cItem), ('query',))
        params.update({'good_for_fav': True, 'category': 'video', 'title': dispTitle, 'raw_title': title, 'slug': slug, 'url': self.MAIN_URL + slug,
                       'player_id': card.get('playerId', '') if card.get('cardType') else '', 'icon': self._icon(card.get('imageUrl', '')), 'desc': desc,
                       'show_title': showTitle, 'date': date})
        self.addVideo(params)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("TV2Play.getLinksForVideo [%s]" % cItem)
        slug = cItem.get('slug', '')
        playerId = cItem.get('player_id', '')
        if not playerId and slug:
            playerId = self._showData(slug).get('playerId', '')
        if not playerId:
            SetIPTVPlayerLastHostError(_("Content not available"))
            return []
        data = self._getJson('%s/streaming-url?playerId=%s&stream=undefined' % (API_URL, playerId))
        if data.get('geoBlocked'):
            SetIPTVPlayerLastHostError(_("Not available in your country (geo-blocking)."))
            return []
        hls = ''
        if data.get('url'):
            stream = self._getJson(data['url'])
            hls = re.sub('^//', 'https://', ((stream.get('bitrates') or {}).get('hls') or ''))
        if not hls:
            SetIPTVPlayerLastHostError(_("Content not available"))
            return []
        urlTab = getDirectM3U8Playlist(hls, checkExt=False, checkContent=True, sortWithMaxBitrate=99999999)
        if not urlTab:
            urlTab = [{'name': 'HLS', 'url': hls}]
        elif config.plugins.iptvplayer.tv2play_quality.value:
            urlTab = urlTab[:1]
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("TV2Play.getArticleContent [%s]" % cItem)
        title = cItem.get('raw_title', '') or cItem.get('title', '')
        text = cItem.get('desc', '')
        icon = cItem.get('icon', '')
        other = {}
        data = self._showData(cItem.get('slug', ''))
        if cItem.get('type') == 'video':
            if data.get('title'):
                title = data['title']
                text = self.cleanHtmlStr(data.get('lead', '') or '') or text
                icon = data.get('imageUrl') or icon
                seconds = self._toInt(data.get('length'))
                if seconds:
                    other['duration'] = self._duration(seconds)
                if data.get('uploadedAt'):
                    other['released'] = data['uploadedAt'].rstrip('.')
                if data.get('channelName'):
                    other['station'] = data['channelName']
                if data.get('primaryCategory'):
                    other['category'] = data['primaryCategory']
                if data.get('ageRestriction'):
                    other['age_limit'] = str(data['ageRestriction'])
                for key, field in (('directors', 'directors'), ('actors', 'actors')):
                    names = [n.get('name', '') if isinstance(n, dict) else str(n) for n in data.get(key) or []]
                    if [n for n in names if n]:
                        other[field] = ', '.join([n for n in names if n])
        else:
            for page in data.get('pages') or []:
                if not isinstance(page, dict):
                    continue
                if cItem.get('season') and str(page.get('seasonNr')) != str(cItem.get('season')):
                    continue
                for tab in page.get('tabs') or []:
                    showData = tab.get('showData') if isinstance(tab, dict) else None
                    if isinstance(showData, dict):
                        text = self.cleanHtmlStr(showData.get('description', '') or '') or text
                        icon = showData.get('imageUrl') or icon
                        if showData.get('primaryCategory'):
                            other['category'] = showData['primaryCategory']
                if page.get('lead'):
                    text = '%s[/br][/br]%s' % (self.cleanHtmlStr(page['lead']), text) if text else self.cleanHtmlStr(page['lead'])
                if page.get('genre'):
                    other['genre'] = ', '.join(page['genre']) if isinstance(page['genre'], list) else page['genre']
                if page.get('ageRestriction'):
                    other['age_limit'] = str(page['ageRestriction'])
                icon = icon or page.get('backgroundImageUrl', '')
                break
            if data.get('seasonNumbers'):
                other['seasons'] = str(len(data['seasonNumbers']))
        return [{'title': title, 'text': text, 'images': [{'title': '', 'url': self._icon(icon)}] if icon else [], 'other_info': other}]

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('TV2Play.handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("handleService: >> name[%s], category[%s]" % (name, category))
        self.currList = []

        if name is None:
            self.listMainMenu({'name': 'category'})
        elif category == 'list_shows':
            self.listShows(self.currItem)
        elif category == 'list_filters':
            # "Műsorok" saved by the old version (any row could be saved then): its page was the item offset
            self.listShows(dict(self.currItem, category='list_shows', page=self._toInt(self.currItem.get('page')) // GRREC_PER_PAGE + 1))
        elif category == 'tv2_show':
            self.listShow(self.currItem)
        elif category in ('list_items', 'explore_items'):
            # a show / season saved by the old version: url .../api/search/<slug>, season 0 = no seasons
            cItem = dict(self.currItem, slug=self.currItem.get('url', '').replace(API_URL + '/search/', ''), season=str(self.currItem.get('season') or ''))
            if cItem['season']:
                self.listSeason(cItem)
            else:
                self.listShow(cItem)
        elif category == 'tv2_season':
            self.listSeason(self.currItem)
        elif category == 'tv2_ribbon':
            self.listRibbon(self.currItem)
        elif category == 'ribbons':
            # a ribbon saved by the old version: its "id" and a page counted from 0
            self.listRibbon(dict(self.currItem, category='tv2_ribbon', ribbon_id=str(self.currItem.get('id', '')), page=self._toInt(self.currItem.get('page')) + 1))
        elif category == 'list_search':
            self.listSearch(self.currItem)
        elif category in ('search', 'search_next_page'):
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
        CHostBase.__init__(self, TV2Play(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('tv2play')

    def withArticleContent(self, cItem):
        return bool(cItem.get('slug')) and (cItem.get('type') == 'video' or cItem.get('category') in ('tv2_show', 'tv2_season'))
