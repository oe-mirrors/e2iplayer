# -*- coding: utf-8 -*-
# Last Modified: 03.10.2026 - revived for kabaret.tworzymyhistorie.pl (https, old PHP layout still in place):
#   "Lista NOS" chart, popular / all cabarets from /kabarety/, per-cabaret sketch list through
#   index/exec/load.php?tod=skecze_lista (needs the session cookie + the cabaret page as Referer;
#   First page / Jump / Next page, 99 per page),
#   interviews / other material as sub-folders, search via /szukaj/<slug> (cabarets, sketches,
#   interviews), YouTube embeds handed to urlparser (Facebook plugin embeds are skipped),
#   watched flag / downloaded flag (stable page urls) / name normalisation / sidecar / site INFO.
import re
import unicodedata

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems


def GetConfigList():
    return []


def gettytul():
    return 'https://kabaret.tworzymyhistorie.pl/'


class Kabarety(GenericFolderWatchedScraperMixin, CBaseHostClass):
    PER_PAGE = 99
    # what identifies a row and is needed to open it again - the same sketch comes with a different
    # title / description from the NOS chart, a cabaret list and the search
    FAV_FIELDS = ('name', 'category', 'type', 'url', 'k_cabaret', 'k_typ', 'icon')
    # material types of the cabaret sketch list (select "Rodzaj" on the site): 0 sketches, 2 interviews, 1 other

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'kabaret.tworzymyhistorie.pl', 'cookie': 'kabarettworzymyhistoriepl.cookie'})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = self.MAIN_URL + 'images/logo.png'
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.MENU = [{'category': 'k_nos', 'title': 'Lista NOS (%s)' % _('Most viewed'), 'url': self.getFullUrl('/nos')},
                     {'category': 'k_cabarets', 'title': _('Popular'), 'k_block': 'popular', 'url': self.getFullUrl('/kabarety/')},
                     {'category': 'k_cabarets', 'title': _('All'), 'k_block': 'all', 'url': self.getFullUrl('/kabarety/')}] + self.searchItems()

        # cabaret page url -> the site's cabaret id for load.php
        self.catCache = {}

        self.watchedHelper = IPTVWatchedHelper('kabarety')
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    def _absUrl(self, url):
        url = (url or '').replace('&amp;', '&').strip()
        if url.startswith('//'):
            url = 'https:' + url
        elif url and not self.cm.isValidUrl(url):
            url = self.getFullUrl(url if url.startswith('/') else '/' + url)
        return url.replace('http://kabaret.', 'https://kabaret.')

    def _cabaretUrl(self, url):
        # tags and search link "/kabarety/<slug>" without the slash - one key for the same cabaret
        url = self._absUrl(url).split('?')[0]
        return url if url.endswith('/') else url + '/'

    @staticmethod
    def _cleanTitle(title):
        title = re.sub(r'\s+', ' ', title or '').strip()
        title = re.sub(r'(?i)[\[(]\s*(?:hd|fullhd|full hd|720p|1080p|online)\s*[\])]', '', title)
        title = re.sub(r'(?i)\s+-?\s*(?:online|hd)$', '', title)
        return re.sub(r'\s+', ' ', title).strip(' -_')

    def _videoTitle(self, cabaret, title):
        # normalised: "Cabaret - Sketch" (no doubled cabaret name); raw: the site's label
        title = self.cleanHtmlStr(title)
        if not IsMediaNamingNormalized():
            return title
        title = self._cleanTitle(title)
        cabaret = self._cleanTitle(re.sub(r'\s*\[[^\]]*\]\s*$', '', cabaret or ''))
        if cabaret:
            low = title.lower()
            for prefix in (cabaret.lower(), re.sub(r'(?i)^kabaret\s+', '', cabaret).lower()):
                if prefix and low.startswith(prefix):
                    rest = title[len(prefix):].lstrip(' -:')
                    if rest:
                        title = rest
                    break
            title = '%s - %s' % (cabaret, title)
        return title

    # lead byte of a UTF-8 sequence read as Latin-1 and folded by the site's collation (0xC4 "Ä" -> "a")
    LATIN1_FOLD = ((0xC0, 0xC5, 'a'), (0xC7, 0xC7, 'c'), (0xC8, 0xCB, 'e'), (0xCC, 0xCF, 'i'), (0xD1, 0xD1, 'n'), (0xD2, 0xD6, 'o'), (0xD9, 0xDC, 'u'), (0xDD, 0xDD, 'y'))
    # Polish letters without a Unicode decomposition to ASCII
    TRANSLIT = {0x0142: 'l', 0x0141: 'l', 0x0111: 'd', 0x00DF: 'ss'}

    def _searchSlugs(self, pattern):
        # the site's /szukaj/<slug>: words joined with "_", "-" is a wildcard. Older titles are stored as
        # UTF-8 read as Latin-1 ("Ksiądz" -> "KsiÄ…dz", found with "ksia-dz"), newer ones properly
        # ("Śmiech" found with "smiech") - for a non-ASCII pattern both spellings are searched
        try:
            text = pattern.decode('utf-8')
        except Exception:
            text = pattern
        text = text.lower()
        plain, mojibake = [], []
        for ch in text:
            if ord(ch) < 128:
                if ch.isalnum():
                    plain.append(ch)
                    mojibake.append(ch)
                elif ch.isspace() or ch in '_-.,;:':
                    for out in (plain, mojibake):
                        if out and out[-1] != '_':
                            out.append('_')
                continue
            asc = self.TRANSLIT.get(ord(ch))
            if asc is None:
                try:
                    asc = ''.join(c for c in unicodedata.normalize('NFKD', ch) if ord(c) < 128 and c.isalnum())
                except Exception:
                    asc = ''
            plain.append(asc.lower())
            lead = bytearray(ch.encode('utf-8'))[0]
            fold = '-'
            for low, high, letter in self.LATIN1_FOLD:
                if low <= lead <= high:
                    fold = letter + '-'
                    break
            mojibake.append(fold)
        slugs = []
        for out in (plain, mojibake):
            slug = str(''.join(out).strip('_'))
            if slug and slug not in slugs:
                slugs.append(slug)
        return slugs

    def _parseVideoTiles(self, data):
        ret = []
        for item in data.split('video_inside_news_medium2 div_image_link')[1:]:
            url = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            if not url:
                continue
            title = self.cm.ph.getSearchGroups(item, r'<img[^>]+alt="([^"]*)"')[0]
            if not title:
                title = self.cm.ph.getSearchGroups(item, r'class="white">([^<]+)<')[0]
            title = self.cleanHtmlStr(title)
            if not title:
                continue
            icon = self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0]
            ret.append((self._absUrl(url), title, self._absUrl(icon) if icon else ''))
        return ret

    def _loadSketches(self, cItem, typ, limit, count):
        # the list is session based: it needs the PHP session cookie and a site page as Referer. The
        # cabaret page (it carries the cabaret id) is opened once; when the session has expired meanwhile
        # (no list marker in the answer, an empty list still has it) the page is opened again
        pageUrl = cItem['url']
        params = dict(self.defaultParams)
        params['header'] = dict(self.HEADER)
        params['header'].update({'Referer': pageUrl, 'X-Requested-With': 'XMLHttpRequest'})
        cat = self.catCache.get(pageUrl, '')
        for fromCache in (bool(cat), False):
            if not fromCache:
                sts, data = self.getPage(pageUrl)
                if not sts:
                    return None
                cat = self.cm.ph.getSearchGroups(data, r'<div class="load"[^>]+?name="([^"]*)"')[0]
                if not cat:
                    return None
                self.catCache[pageUrl] = cat
            url = self.getFullUrl('/index/exec/load.php?tod=skecze_lista&cat=%s&typ=%s&title=&sort=id&order=desc&limit=%d&count=%d' % (cat, typ, limit, count))
            sts, data = self.getPage(url, params)
            if sts and 'div_szukaj_video' in data:
                return data
            if not fromCache:
                break
        return None

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        # cabaret folder (its sketches, all pages) -> interviews / other material sub-folders -> videos
        try:
            if not isinstance(cItem, dict):
                return ''
            url = str(cItem.get('url', '') or '').strip()
            if not url:
                return ''
            if cItem.get('type', '') in ('video', 'audio'):
                return 'video:%s' % url
            category = cItem.get('category', '')
            typ = str(cItem.get('k_typ', '0') or '0')
            if category == 'k_cabaret' or (category == 'k_items' and typ == '0'):
                return 'cabaret:%s' % url
            if category == 'k_items':
                return 'cabaret:%s|%s' % (url, typ)
        except Exception:
            printExc()
        return ''

    ###################################################
    # lists
    ###################################################
    def listNos(self, cItem):
        printDBG('Kabarety.listNos')
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        week = self.cm.ph.getSearchGroups(data, r'Notowanie\s+(\d+)')[0]
        data = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="nos_lista', '</ul>', False)[1]
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>'):
            url = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            raw = self.cm.ph.getDataBeetwenMarkers(item, '<div class="nos_title">', '</div>', False)[1]
            if not url or not raw:
                continue
            cabaret = self.cleanHtmlStr(self.cm.ph.getSearchGroups(raw, r'<b>(.*?)</b>')[0])
            title = self.cleanHtmlStr(raw)
            if cabaret and IsMediaNamingNormalized():
                title = self._videoTitle(cabaret, re.sub(r'^.*?</b>\s*-?\s*', '', raw))
            pos = self.cm.ph.getSearchGroups(item, r'nos_pozycja_nr"><span>(\d+)<')[0]
            icon = self.cm.ph.getSearchGroups(item, r'<img src="([^"]+)" class="image_')[0]
            desc = ('Lista NOS%s: #%s' % ((' ' + week) if week else '', pos)) if pos else ''
            params = {'name': 'category', 'category': 'k_video', 'good_for_fav': True, 'title': title, 'url': self._absUrl(url),
                      'icon': self._absUrl(icon) if icon else '', 'desc': desc, 'k_cabaret': cabaret}
            self.addVideo(params)

    def listCabarets(self, cItem):
        printDBG('Kabarety.listCabarets [%s]' % cItem.get('k_block'))
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        if cItem.get('k_block') == 'popular':
            data = self.cm.ph.getDataBeetwenMarkers(data, 'NAJPOPULARNIEJSZE', 'WSZYSTKIE', False)[1]
        else:
            data = self.cm.ph.getDataBeetwenMarkers(data, 'WSZYSTKIE', 'width752', False)[1]
        for url, title in re.findall(r'<div class="kat_lista"[^>]*><a href="([^"]+)"[^>]*><p>(.*?)</p>', data):
            title = self.cleanHtmlStr(title)
            if not title:
                continue
            self.addDir({'name': 'category', 'category': 'k_cabaret', 'good_for_fav': True, 'title': title, 'k_cabaret': title,
                         'url': self._cabaretUrl(url), 'desc': ''})

    def listCabaret(self, cItem):
        # interviews / other material as sub-folders on top (when there are any), then the first page of the
        # sketches directly - the pager rows stay at the end of the list
        printDBG('Kabarety.listCabaret [%s]' % cItem['url'])
        cItem = dict(cItem)
        cItem.update({'k_typ': '0', 'page': 1})
        cabaret = cItem.get('k_cabaret') or cItem.get('title', '')
        for typ, label in (('2', _('Interviews')), ('1', _('Other'))):
            data = self._loadSketches(cItem, typ, 0, 1)
            if data and self._parseVideoTiles(data):
                self.addDir({'name': 'category', 'category': 'k_items', 'good_for_fav': True, 'title': '%s - %s' % (cabaret, label),
                             'k_cabaret': cabaret, 'k_typ': typ, 'url': cItem['url'], 'desc': ''})
        self.listItems(cItem)

    def listItems(self, cItem):
        page = max(1, int(cItem.get('page', 1) or 1))
        printDBG('Kabarety.listItems [%s] typ[%s] page[%d]' % (cItem['url'], cItem.get('k_typ'), page))
        typ = cItem.get('k_typ', '0')
        # one more than shown: tells whether a next page really exists
        data = self._loadSketches(cItem, typ, (page - 1) * self.PER_PAGE, self.PER_PAGE + 1)
        if data is None:
            return
        cabaret = cItem.get('k_cabaret', '')
        tiles = self._parseVideoTiles(data)
        for url, title, icon in tiles[:self.PER_PAGE]:
            self.addVideo({'name': 'category', 'category': 'k_video', 'good_for_fav': True, 'title': self._videoTitle(cabaret, title), 'url': url,
                           'icon': icon, 'desc': cabaret, 'k_cabaret': cabaret})
        listItem = dict(cItem)
        listItem.update({'category': 'k_items', 'desc': ''})
        # the list has no page count; one url for all pages, the page number becomes the load.php offset
        addPagingItems(self, listItem, page, len(tiles) > self.PER_PAGE, 0, cItem['url'])

    def listSearchResult(self, cItem, searchPattern, searchType):
        slugs = self._searchSlugs(searchPattern)
        printDBG('Kabarety.listSearchResult [%s] -> %s' % (searchPattern, slugs))
        cabarets, videos, seen = [], [], set()
        for slug in slugs:
            sts, data = self.getPage(self.getFullUrl('/szukaj/' + slug))
            if not sts:
                continue
            tmp = self.cm.ph.getDataBeetwenMarkers(data, 'div_szukaj_kabarety', 'div_count_kabarety_hidden', False)[1]
            for url, title in re.findall(r'<h1><a href="(/kabarety/[^"]+)"[^>]*>(.*?)</a>', tmp):
                url = self._cabaretUrl(url)
                if url not in seen:
                    seen.add(url)
                    cabarets.append((url, self.cleanHtmlStr(title)))
            # sketches, then interviews
            for start, end in (('div_szukaj_video', 'div_count_video_hidden'), ('div_szukaj_wywiady', 'div_count_wywiady_hidden')):
                tmp = self.cm.ph.getDataBeetwenMarkers(data, start, end, False)[1]
                for url, title, icon in self._parseVideoTiles(tmp):
                    if url not in seen:
                        seen.add(url)
                        videos.append((url, title, icon))
        for url, title in cabarets:
            name = re.sub(r'\s*\[[^\]]*\]\s*$', '', title)
            self.addDir({'name': 'category', 'category': 'k_cabaret', 'good_for_fav': True, 'title': name if IsMediaNamingNormalized() else title,
                         'k_cabaret': name, 'url': url, 'desc': ''})
        for url, title, icon in videos:
            self.addVideo({'name': 'category', 'category': 'k_video', 'good_for_fav': True, 'title': self._videoTitle('', title),
                           'url': url, 'icon': icon, 'desc': ''})

    ###################################################
    # links
    ###################################################
    def _getEmbeds(self, data):
        embeds = []
        tmp = self.cm.ph.getDataBeetwenMarkers(data, 'id="video_embed"', 'video_player_opis', False)[1] or data
        raw = re.findall(r'<iframe[^>]+src="([^"]+)"', tmp)
        raw += re.findall(r'class="fb-video"[^>]+data-href="([^"]+)"', tmp)
        for url in raw:
            url = self._absUrl(url)
            ytId = self.cm.ph.getSearchGroups(url, r'youtube(?:-nocookie)?\.com/embed/([A-Za-z0-9_-]{11})')[0]
            if ytId:
                url = 'https://www.youtube.com/watch?v=' + ytId
            if self.cm.isValidUrl(url) and url not in embeds:
                embeds.append(url)
        return embeds

    def getLinksForVideo(self, cItem):
        printDBG('Kabarety.getLinksForVideo [%s]' % cItem.get('url'))
        urlTab = []
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return []
        embeds = self._getEmbeds(data)
        if not embeds:
            # old player: the embed comes from load.php?tod=vidplay&name=<id>
            videoId = self.cm.ph.getSearchGroups(cItem['url'], r'\.pl/(?:[a-z_]+/)?([0-9]+)_')[0]
            if videoId:
                params = dict(self.defaultParams)
                params['header'] = dict(self.HEADER)
                params['header'].update({'Referer': cItem['url'], 'X-Requested-With': 'XMLHttpRequest'})
                sts, tmp = self.getPage(self.getFullUrl('/index/exec/load.php?tod=vidplay&name=' + videoId), params)
                if sts:
                    embeds = self._getEmbeds(tmp)
        unsupported = []
        for url in embeds:
            host = self.up.getHostName(url)
            if 'facebook.' in host or self.up.checkHostSupport(url) != 1:
                printDBG('Kabarety: hoster not supported [%s]' % url)
                unsupported.append(host)
                continue
            name = 'YouTube' if 'youtu' in host else host.capitalize()
            urlTab.append({'name': name, 'url': url, 'need_resolve': 1})
        if not urlTab and unsupported:
            SetIPTVPlayerLastHostError(_('Only unsupported hosters available: %s') % ', '.join(sorted(set(unsupported))))
        added = self.cm.ph.getSearchGroups(data, r'Dodano:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})')[0]
        ogTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta property="og:title" content="([^"]*)"')[0])
        sidecarTxt = '\n'.join(x for x in (ogTitle, ('%s: %s' % (_('Added'), added)) if added else '') if x)
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled(), sidecarTxt))

    def getVideoLinks(self, videoUrl):
        printDBG('Kabarety.getVideoLinks [%s]' % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO / favourites
    ###################################################
    def getArticleContent(self, cItem):
        printDBG('Kabarety.getArticleContent [%s]' % cItem.get('url'))
        title = cItem.get('title', '')
        icon = cItem.get('icon', '')
        text = ''
        other = {}
        sts, data = self.getPage(cItem['url'])
        if sts:
            if cItem.get('type') == 'video':
                ogTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta property="og:title" content="([^"]*)"')[0])
                if ogTitle:
                    title = ogTitle
                ogImage = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
                if ogImage:
                    icon = self._absUrl(ogImage)
                added = self.cm.ph.getSearchGroups(data, r'Dodano:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})')[0]
                if added:
                    other['released'] = added
                views = self.cm.ph.getSearchGroups(data, r'>(\d+)\s+wy\S*wietle')[0]
                if views:
                    other['views'] = views
                plus = self.cm.ph.getSearchGroups(data, r'id="vote_count_plus"[^>]*>(\d+)<')[0]
                minus = self.cm.ph.getSearchGroups(data, r'id="vote_count_minus"[^>]*>(\d+)<')[0]
                if plus or minus:
                    other['rating'] = '+%s / -%s' % (plus or '0', minus or '0')
                cabaret = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<a href="/kabarety/[^"]+" class="granat bold">(.*?)</a>')[0])
                if cabaret:
                    other['category'] = cabaret
                tags = [self.cleanHtmlStr(t) for t in re.findall(r'#<a href="/szukaj/[^"]+"[^>]*>(.*?)</a>', self.cm.ph.getDataBeetwenMarkers(data, 'Tagi:', 'clearFix', False)[1])]
                text = cItem.get('desc', '')
                if tags:
                    text = (text + '\n' if text else '') + ' '.join('#' + t for t in tags if t)
                embeds = self._getEmbeds(data)
                if embeds:
                    other['source'] = ', '.join(sorted(set(self.up.getHostName(u) for u in embeds)))
            else:
                block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="site_skecze">', 'Statystyki', False)[1]
                name = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'<h1[^>]*>(.*?)</h1>')[0])
                if name:
                    title = name
                lines = []
                for label, value in re.findall(r'<div class="inline width120 fontgrey">([^<]+)</div><div class="inline[^"]*">(.*?)</div>', block):
                    label = self.cleanHtmlStr(label).rstrip(':')
                    value = self.cleanHtmlStr(value)
                    if not value:
                        continue
                    if label.startswith('Rok'):
                        other['year'] = self.cm.ph.getSearchGroups(value, r'(\d{4})')[0] or value
                    elif label.startswith('Sk'):
                        other['cast'] = value
                    elif label.startswith('Strona'):
                        continue
                    else:
                        lines.append('%s: %s' % (label, value))
                popularity = self.cm.ph.getSearchGroups(data, r'<div class="inline margin0x5">(\d+%)</div>')[0]
                if popularity:
                    lines.append('%s: %s' % (_('Popularity'), popularity))
                text = '\n'.join(lines)
        images = [{'title': '', 'url': icon}] if icon else []
        return [{'title': self.cleanHtmlStr(title), 'text': text, 'images': images, 'other_info': other}]

    def getFavouriteData(self, cItem):
        try:
            return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get('name', '')
        category = self.currItem.get('category', '')
        printDBG('Kabarety.handleService name[%s] category[%s]' % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {'name': 'category'})
        elif category == 'k_nos':
            self.listNos(self.currItem)
        elif category == 'k_cabarets':
            self.listCabarets(self.currItem)
        elif category == 'k_cabaret':
            self.listCabaret(self.currItem)
        elif category == 'k_items':
            self.listItems(self.currItem)
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
        CHostBase.__init__(self, Kabarety(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('kabarety')

    def withArticleContent(self, cItem):
        return cItem.get('type') == 'video' or cItem.get('category') == 'k_cabaret'
