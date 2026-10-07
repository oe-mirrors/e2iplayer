# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026
# TVN24 (tvn24.pl) - Polish news portal: the free video clips embedded in the news articles
# Sections (Najnowsze, Polska, Swiat, Biznes, regions ...) are paged with /<section>/s-N, search = the site's search
# box (/_i/y/f/search-results/<words>) plus the tag page /tagi/<slug> when one exists; an article page carries
# the clip as "playlistUrl" (/_e/p/playlist/cue/...) -> JSON with movie.video.sources (HLS with a separate audio
# rendition, sometimes MP4). TVN24+ (live channels, programmes, podcasts) is subscription + DRM only and is not listed.
# 03.10.2026 - rewrite for the new site: sections, regions, search, watched flag, sidecar, INFO
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
###################################################
# FOREIGN import
###################################################
import re
import unicodedata
###################################################


def GetConfigList():
    return []


def gettytul():
    return 'https://tvn24.pl/'


class TVN24(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ('name', 'category', 'type', 'url', 'title', 'icon', 'desc')
    SECTIONS = [('najnowsze', _('Latest')), ('polska', _('Poland')), ('swiat', _('World')), ('biznes', _('Business')),
                ('kultura-i-styl', _('Culture and lifestyle')), ('tvnmeteo', 'TVN Meteo'), ('tvnwarszawa', 'TVN Warszawa')]
    REGIONS = [('bialystok', 'Białystok'), ('katowice', 'Katowice'), ('krakow', 'Kraków'), ('lodz', 'Łódź'),
               ('lubuskie', 'Lubuskie'), ('opole', 'Opole'), ('poznan', 'Poznań'), ('rzeszow', 'Rzeszów'),
               ('szczecin', 'Szczecin'), ('trojmiasto', 'Trójmiasto'), ('wroclaw', 'Wrocław')]

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'tvn24', 'cookie': 'tvn24.cookie'})
        self.MAIN_URL = 'https://tvn24.pl/'
        self.DEFAULT_ICON_URL = 'https://tvn24.pl/najnowsze/cdn-zdjecie-9930616-logo-tvn24-ph8320467/alternates/LANDSCAPE_320'
        self.HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.defaultParams = {'header': self.HEADER, 'with_metadata': True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper('tvn24')
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict) or cItem.get('type') != 'video':
                return ''
            aid = self.cm.ph.getSearchGroups(cItem.get('url', ''), r'-((?:st|ra|ar)\d+)$')[0]
            return 'video:%s' % aid if aid else ''
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
            if cItem.get('type') == 'video':
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    @staticmethod
    def _jpeg(url, size=None):
        # the teasers use WebP renditions; the same picture exists as JPEG (LANDSCAPE_320 / LANDSCAPE_1280)
        url = (url or '').replace('&amp;', '&')
        url = re.sub(r'/alternates/WEBP_LANDSCAPE_(\d+)', r'/alternates/LANDSCAPE_\1', url)
        if size:
            url = re.sub(r'/alternates/LANDSCAPE_\d+', '/alternates/LANDSCAPE_%s' % size, url)
        elif '/alternates/LANDSCAPE_' in url:
            url = re.sub(r'/alternates/LANDSCAPE_\d+', '/alternates/LANDSCAPE_320', url)
        return url

    ###################################################
    # listing
    ###################################################
    def listMain(self, cItem):
        for path, title in self.SECTIONS:
            params = dict(cItem)
            params.update({'category': 'list_items', 'title': title, 'url': self.getFullUrl('/' + path), 'good_for_fav': True})
            self.addDir(params)
        params = dict(cItem)
        params.update({'category': 'list_regions', 'title': _('Regions')})
        self.addDir(params)
        self.listsTab(self.searchItems(), cItem)

    def listRegions(self, cItem):
        for path, title in self.REGIONS:
            params = dict(cItem)
            params.update({'category': 'list_items', 'title': title, 'url': self.getFullUrl('/' + path), 'good_for_fav': True})
            self.addDir(params)

    def _addTeasers(self, cItem, data, seen):
        count = 0
        for chunk in data.split('part="SectionTeaser')[1:]:
            if 'data-paywall="1"' in chunk[:600]:
                continue
            url = self.cm.ph.getSearchGroups(chunk, r'''<a href="(https://tvn24\.pl/[^"]+-(?:st|ra|ar)\d+)"''')[0]
            if not url or '/plus/' in url or url in seen:
                continue
            seen.add(url)
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(chunk, r'''<a href="[^"]+" title="([^"]+)"''')[0])
            if not title:
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(chunk, '<span>', '</span>', False)[1])
            if not title:
                continue
            icon = self._jpeg(self.cm.ph.getSearchGroups(chunk, r'''<img src="([^"]+)"''')[0])
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(chunk, r'''Label--link TextBox" href="[^"]+">([^<]+)<''')[0])
            params = {'name': 'category', 'type': 'video', 'title': title, 'url': url, 'icon': icon,
                      'desc': label, 'good_for_fav': True}
            self.addVideo(params)
            count += 1
        return count

    def _listTeaserPage(self, cItem, baseUrl, page, seen):
        # a section, region or tag page; "/s-N" is page N - the link to the next one is on the page itself
        tpl = baseUrl.rstrip('/') + '/s-{page}'
        sts, data = self.getPage(baseUrl if page == 1 else tpl.format(page=page))
        if not sts:
            return
        main = data.find('<main')
        if main > -1:
            data = data[main:]
        count = self._addTeasers(cItem, data, seen)
        path = self.cm.ph.getSearchGroups(baseUrl, r'https://tvn24\.pl(/[^?#]+)')[0].rstrip('/')
        # the pager links the next pages and the last one
        pages = [int(n) for n in re.findall(r'%s/s-(\d+)"' % re.escape(path), data)] if path else []
        lastPage = max(pages + [page])
        if count:
            addPagingItems(self, dict(cItem, base_url=baseUrl), page, (page + 1) in pages, lastPage, tpl)

    def listItems(self, cItem):
        self._listTeaserPage(cItem, cItem.get('base_url') or cItem['url'], int(cItem.get('page', 1) or 1), set())

    @staticmethod
    def _tagSlug(pattern):
        # "Donald Tusk" -> "donald-tusk" (the tag pages use ASCII slugs)
        try:
            txt = pattern.decode('utf-8') if isinstance(pattern, bytes) else pattern
            txt = unicodedata.normalize('NFKD', txt.lower().replace(u'ł', 'l'))
            txt = ''.join(c for c in txt if not unicodedata.combining(c))
            return re.sub(r'[^a-z0-9]+', '-', ensure_str(txt)).strip('-')
        except Exception:
            printExc()
        return ''

    def listSearchResult(self, cItem, searchPattern, searchType):
        page = int(cItem.get('page', 1) or 1)
        seen = set()
        if page == 1:
            # the site's own search box: a handful of best matches
            sts, data = self.getPage(self.getFullUrl('/_i/y/f/search-results/%s' % urllib_quote(searchPattern)))
            if sts:
                try:
                    self._addTeasers(cItem, json_loads(data).get('html') or '', seen)
                except Exception:
                    printExc()
        # the tag page of the same words (when it exists) carries the full, paged list
        slug = self._tagSlug(searchPattern)
        if slug:
            self._listTeaserPage(cItem, self.getFullUrl('/tagi/%s' % slug), page, seen)

    ###################################################
    # links
    ###################################################
    def _getPlaylist(self, articleUrl):
        sts, data = self.getPage(articleUrl)
        if not sts:
            return None, ''
        playlists = re.findall(r'"playlistUrl":"([^"]+)"', data)
        # the article's main video first ("mainMultimedium"), then the other embedded clips
        playlists.sort(key=lambda u: 0 if 'mainMultimedium' in u else 1)
        for pl in playlists:
            try:
                pl = json_loads('"%s"' % pl)
            except Exception:
                pl = pl.replace('\\u0026', '&')
            sts, raw = self.getPage(self.getFullUrl(pl))
            if not sts:
                continue
            try:
                js = json_loads(raw)
            except Exception:
                printExc()
                continue
            if isinstance(js, dict) and isinstance(js.get('movie'), dict):
                return js, data
        return None, data

    def getLinksForVideo(self, cItem):
        printDBG("TVN24.getLinksForVideo [%s]" % cItem.get('url', ''))
        js, data = self._getPlaylist(cItem['url'])
        if js is None:
            if data:
                SetIPTVPlayerLastHostError(_("This article has no free video."))
            return []
        video = js['movie'].get('video') or {}
        if video.get('is_protected') or (video.get('protections') and not (video.get('sources') or {}).get('mp4', {}).get('url')):
            SetIPTVPlayerLastHostError(_("Video with DRM protection."))
            return []
        sources = video.get('sources') or {}
        urlTab = []
        hls = (sources.get('hls') or {}).get('url') or ''
        mp4 = (sources.get('mp4') or {}).get('url') or ''
        live = bool(video.get('is_live'))
        if hls:
            hlsUrl = strwithmeta(hls, {'User-Agent': self.HEADER['User-Agent'], 'Referer': self.getMainUrl(), 'iptv_livestream': live})
            for item in getDirectM3U8Playlist(hlsUrl, checkExt=False, checkContent=True, sortWithMaxBitrate=999999999):
                item['need_resolve'] = 0
                urlTab.append(item)
        if mp4:
            urlTab.append({'name': 'MP4', 'url': strwithmeta(mp4, {'User-Agent': self.HEADER['User-Agent'], 'Referer': self.getMainUrl()}), 'need_resolve': 0})
        if not urlTab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        if live:
            return urlTab
        info = js['movie'].get('info') or {}
        synopsis = self.cleanHtmlStr(info.get('description') or cItem.get('desc', ''))
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled(), synopsis))

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("TVN24.getArticleContent [%s]" % cItem.get('url', ''))
        title = self.cleanHtmlStr(cItem.get('title', ''))
        icon = self._jpeg(cItem.get('icon', ''), 1280)
        text = ''
        other = {}
        sts, data = self.getPage(cItem['url'])
        if sts:
            text = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'''<meta[^>]+name="description"[^>]+content="([^"]*)"''')[0])
            if not text:
                text = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'''<meta[^>]+content="([^"]*)"[^>]+property="og:description"''')[0])
            date = self.cm.ph.getSearchGroups(data, r'"datePublished":"(\d{4}-\d{2}-\d{2})')[0]
            if date:
                other['released'] = date
        if cItem.get('desc'):
            other['genre'] = cItem['desc']
        return [{'title': title, 'text': text or cItem.get('desc', ''), 'images': [{'title': '', 'url': icon}] if icon else [], 'other_info': other}]

    ###################################################
    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("TVN24.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMain({'name': 'category'})
        elif category == 'list_regions':
            self.listRegions(self.currItem)
        elif category == 'list_items':
            self.listItems(self.currItem)
        elif category in ('search', 'search_next_page'):
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category', 'category': 'search_next_page'})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == 'search_history':
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, TVN24(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('tvn24')

    def withArticleContent(self, cItem):
        return cItem.get('type') == 'video'
