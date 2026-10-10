# -*- coding: utf-8 -*-
# Last Modified: 10.10.2026
# tvgry / GRYOnline.pl video (gry-online.pl/video/): tvgry shows, podcasts and game trailers, played from Dailymotion
# 10.10.2026 - rewrite for gry-online.pl/video/ (tvgry.pl redirects there since the site move): newest videos,
#   tvgry, podcasts and trailers with First/Jump/Next paging and the last page, search through the site's video
#   quick search, Dailymotion player id from the video page (age check answered with the site's agegate cookie -
#   the birth date option is gone), INFO from the page's video data (description, date, duration, author),
#   watched flag / downloaded marker on the video page url, favourites, sidecar, current user agent
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
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
    return 'https://www.gry-online.pl/video/'


class TvGryPL(GenericFolderWatchedScraperMixin, CBaseHostClass):

    # stable identity of a video row
    VIDEO_FIELDS = ('name', 'category', 'type', 'url', 'title', 'icon')

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'TvGryPL.tv', 'cookie': 'grypl.cookie'})
        self.HEADER = {'User-Agent': self.cm.getDefaultUserAgent(), 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}
        # the video pages show the player only after the age check ("agegate" cookie of the site)
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE,
                              'cookie_items': {'agegate': '1'}}
        self.DEFAULT_ICON_URL = 'https://www.gry-online.pl/apple-touch-icon-120x120.png'
        self.MAIN_URL = 'https://www.gry-online.pl/'
        self.watchedHelper = IPTVWatchedHelper('tvgrypl')
        self.wfInitFolderCache()

    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    ###################################################
    # watched flag / favourites
    ###################################################
    def _isVideo(self, cItem):
        return cItem.get('type') == 'video' and '/video/' in cItem.get('url', '')

    def _getWatchedKeyForItem(self, cItem):
        try:
            if isinstance(cItem, dict) and self._isVideo(cItem):
                return 'video:%s' % re.sub(r'^https?://[^/]+', '', cItem['url'])
        except Exception:
            printExc()
        return ''

    def getFavouriteData(self, cItem):
        try:
            if self._isVideo(cItem):
                return json_dumps(dict((key, cItem[key]) for key in self.VIDEO_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self, cItem):
        printDBG("TvGryPL.listMainMenu")
        MAIN_CAT_TAB = [{'category': 'list_items', 'title': _('Latest'), 'url': self.getFullUrl('/video/najnowsze/'), 'good_for_fav': True},
                        {'category': 'list_items', 'title': 'tvgry', 'url': self.getFullUrl('/video/tvgry/'), 'good_for_fav': True},
                        {'category': 'list_items', 'title': 'Podcasty', 'url': self.getFullUrl('/video/podcasty/'), 'good_for_fav': True},
                        {'category': 'list_items', 'title': 'Trailery', 'url': self.getFullUrl('/video/trailery/'), 'good_for_fav': True}] + self.searchItems()
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listItems(self, cItem):
        printDBG("TvGryPL.listItems [%s]" % cItem.get('url', ''))
        try:
            page = max(1, int(cItem.get('page', 1)))
        except (TypeError, ValueError):
            page = 1
        baseUrl = cItem.get('url', '')
        if 'gry-online.pl/video/' not in baseUrl:
            # folders of the old tvgry.pl host - the old pages redirect to the video start page
            baseUrl = self.getFullUrl('/video/najnowsze/')
        baseUrl = re.sub(r'[?&]PAGE=\d+', '', baseUrl)
        sts, data = self.getPage(baseUrl + ('?PAGE=%d' % page if page > 1 else ''))
        if not sts:
            return
        for item in data.split('<div class="lh-c')[1:]:
            link = self.cm.ph.getDataBeetwenNodes(item, ('<a', '>', 'lh-link'), ('</a', '>'))[1]
            url = self.cm.ph.getSearchGroups(link, r'''href=['"]([^'^"]+?)['"]''')[0]
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<h3', '>'), ('</h3', '>'), False)[1]) or self.cleanHtmlStr(link)
            if not url or not title or '/video/' not in url:
                continue
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, r'''<img[^>]+?src=['"]([^'^"]+?)['"]''')[0])
            lead = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<p', '>', 'lead'), ('</p', '>'), False)[1])
            bot = self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'lh-bot'), ('</div', '>'), False)[1]
            bot = ' | '.join([self.cleanHtmlStr(x) for x in self.cm.ph.getAllItemsBeetwenMarkers(bot, '<p', '</p>') if self.cleanHtmlStr(x)])
            desc = '[/br]'.join([x for x in (bot, lead) if x])
            params = stripPagerKeys(dict(cItem))
            params.update({'name': 'category', 'good_for_fav': True, 'category': 'video', 'title': title, 'url': self.getFullUrl(url), 'icon': icon, 'desc': desc})
            self.addVideo(params)
        # "1 2 3 4 5 <div class="dots">...</div> 267" - the last page follows the inner div
        pager = data.split('next-prev-enc-pages">', 1)[1].split('next-prev-arr', 1)[0] if 'next-prev-enc-pages">' in data else ''
        pages = [int(x) for x in re.findall(r'PAGE=(\d+)', pager)]
        lastPage = max(pages + [page])
        if self.currList and lastPage > 1:
            addPagingItems(self, dict(cItem, url=baseUrl), page, page < lastPage, lastPage, baseUrl + '?PAGE={page}')

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("TvGryPL.listSearchResult [%s]" % searchPattern)
        sts, data = self.getPage(self.getFullUrl('/ajax/xml/video.asp?search=%s' % urllib_quote(searchPattern.strip())))
        if sts:
            for item in self.cm.ph.getAllItemsBeetwenMarkers(data, '<row', '>'):
                url = self.cm.ph.getSearchGroups(item, r'''url=['"]([^'^"]+?)['"]''')[0]
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'''name=['"]([^'^"]+?)['"]''')[0])
                if url and title and '/video/' in url:
                    self.addVideo({'name': 'category', 'good_for_fav': True, 'category': 'video', 'title': title, 'url': self.getFullUrl(url)})
        if not self.currList:
            SetIPTVPlayerLastHostError(_('No matching entries found.'))

    ###################################################
    # links / INFO
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("TvGryPL.getLinksForVideo [%s]" % cItem.get('url', ''))
        if 'gry-online.pl/video/' not in cItem.get('url', ''):
            # favourites of the old tvgry.pl host: their ids do not exist on gry-online.pl
            SetIPTVPlayerLastHostError(_('No stream available'))
            return []
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return []
        linksTab = []
        videoId = self.cm.ph.getSearchGroups(data, r'''loadContent\(\{\s*video:\s*['"]([a-zA-Z0-9]+)['"]''')[0] or self.cm.ph.getSearchGroups(data, r'''dm-player-(x[a-zA-Z0-9]+)''')[0]
        if videoId:
            linksTab.append({'name': 'Dailymotion', 'url': 'https://www.dailymotion.com/video/%s' % videoId, 'need_resolve': 1})
        else:
            for url in re.findall(r'''<iframe[^>]+?src=['"]([^"^']+?)['"]''', self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'player-c'), ('</script', '>'))[1]):
                url = self.getFullUrl(url)
                if self.up.checkHostSupport(url) == 1:
                    linksTab.append({'name': self.up.getHostName(url), 'url': url, 'need_resolve': 1})
        if not linksTab:
            SetIPTVPlayerLastHostError(_('No stream available'))
        return applySidecarToLinks(linksTab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def getVideoLinks(self, videoUrl):
        printDBG("TvGryPL.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecarFromUrlMeta(videoUrl, IsSidecarEnabled()))

    def getArticleContent(self, cItem):
        printDBG("TvGryPL.getArticleContent [%s]" % cItem.get('url', ''))
        title = cItem.get('title', '')
        text = cItem.get('desc', '')
        icon = cItem.get('icon', '')
        otherInfo = {}
        sts, data = self.getPage(cItem.get('url', '')) if 'gry-online.pl/video/' in cItem.get('url', '') else (False, '')
        if sts:
            video = {}
            for tmp in re.findall(r'''(?s)<script[^>]+?application/ld\+json[^>]*>(.*?)</script>''', data):
                if '"VideoObject"' in tmp:
                    try:
                        video = ensure_str_deep(json_loads(tmp))
                    except Exception:
                        printExc()
                    break
            title = self.cleanHtmlStr(video.get('name', '')) or title
            icon = video.get('thumbnailUrl', '') or icon
            lead = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'''<meta[^>]+?og:description[^>]+?content=['"]([^'^"]+?)['"]''')[0])
            text = self.cleanHtmlStr(video.get('description', '')) or lead or text
            duration = re.match(r'^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$', str(video.get('duration', '')))
            if duration and any(duration.groups()):
                hours, minutes, seconds = [int(x or 0) for x in duration.groups()]
                otherInfo['duration'] = ('%d:%02d:%02d' % (hours, minutes, seconds)) if hours else ('%d:%02d' % (minutes, seconds))
            if video.get('uploadDate'):
                otherInfo['released'] = str(video['uploadDate'])[:10]
            if (video.get('author') or {}).get('name'):
                otherInfo['creator'] = self.cleanHtmlStr(video['author']['name'])
            if video.get('interactionCount'):
                otherInfo['views'] = str(video['interactionCount'])
        return [{'title': title, 'text': text or title, 'images': [{'title': '', 'url': icon or self.DEFAULT_ICON_URL}], 'other_info': otherInfo}]

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('TvGryPL.handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", None)
        category = self.currItem.get("category", '')
        printDBG("handleService: name[%s], category[%s] " % (name, category))
        self.currList = []

        if name is None:
            self.listMainMenu({'name': 'category'})
        # 'list_tabs': folders of the old tvgry.pl host
        elif category in ('list_items', 'list_tabs'):
            self.listItems(self.currItem)
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
        CHostBase.__init__(self, TvGryPL(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('tvgrypl')

    def withArticleContent(self, cItem):
        return cItem.get('type') == 'video'
