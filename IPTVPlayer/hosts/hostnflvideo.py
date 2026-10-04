# -*- coding: utf-8 -*-
# NFL Video (nfl-video.com) - NFL / College Football full game replays, condensed games, Super Bowls
# Site: uCoz catalogue (seasons / teams from the side navigation, "?pageN" paging, /search/ needs the ucz_h cookie)
# Game page: "Server #N XX" buttons -> link pages (nhlgamestoday.com, nbaontv.com, ...) with one hoster <iframe>
#   (ok.ru, odysee, vidara, ...), older games embed the hoster <iframe> directly. Resolved lazily in getVideoLinks.
#   Link pages, favourites and handleService: tools/ucozcatalog.py (listing / paging / links of this site differ)
# Last Modified: 03.10.2026 - rewrite: watched flag, name normalisation, sidecar, search, INFO, paging (First / Jump / Next)
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.tools.ucozcatalog import UcozCatalogMixin
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
###################################################
# FOREIGN import
###################################################
import re
###################################################


def GetConfigList():
    return []


def gettytul():
    return 'https://nfl-video.com/'


class NFLVideo(UcozCatalogMixin, GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ('name', 'category', 'type', 'url', 'title', 'icon', 'desc', 'raw_title')

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'nflvideo', 'cookie': 'nflvideo.cookie'})
        self.MAIN_URL = 'https://nfl-video.com/'
        self.DEFAULT_ICON_URL = ''  # the site has no logo image (text logotype only)
        self.HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.defaultParams = {'header': self.HEADER, 'with_metadata': True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper('nflvideo')
        self.wfInitFolderCache()

    ###################################################
    # watched flag (keys: UcozCatalogMixin._getWatchedKeyForItem)
    ###################################################
    def _stableUrl(self, url):
        # path only, without the uCoz "?pageN" / "/archive/<cat>/<id>-N" paging, so page 2 keys like page 1
        # and the domain may move
        url = str(url or '').strip()
        if not url or '/search/' in url:
            return ''
        url = re.sub(r'^https?://[^/]+', '', url)
        url = re.sub(r'\?page\d+$', '', url)
        url = re.sub(r'^(/archive/[^?]+/\d+)-\d+$', r'\1', url)
        return url

    ###################################################
    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    ###################################################
    # naming (dates: UcozCatalogMixin._parseDate)
    ###################################################
    def _normTitle(self, title):
        # "Steelers vs. Browns - Full Game Replay - NFL Week 04 - October 1, 2026" -> "Steelers vs. Browns - NFL Week 04 (2026-10-01)"
        if not IsMediaNamingNormalized():
            return title
        try:
            date = self._parseDate(title)
            parts = [p.strip() for p in title.split(' - ') if p.strip()]
            keep = []
            for p in parts:
                if re.match(r'^Full Game(?: Replay)?(?:\s*(?:&|and)\s*Highlights)?$', p, re.I):
                    continue
                if date and self._parseDate(p) and len(re.sub(r'[\d,\s]', '', p)) <= 10:
                    continue
                keep.append(p)
            out = ' - '.join(keep) or title
            if date and date[:4] not in out.split('(')[-1]:
                out = '%s (%s)' % (out, date)
            return out
        except Exception:
            printExc()
        return title

    ###################################################
    # listing
    ###################################################
    def listMain(self, cItem):
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        self.setMainUrl(data.meta.get('url', self.getMainUrl()))
        nav = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'list_cat'), ('</nav', '>'), False)[1]
        params = dict(cItem)
        params.update({'category': 'list_items', 'title': _('Latest'), 'url': self.getMainUrl(), 'good_for_fav': True})
        self.addDir(params)
        # top level links, then the "beefup" groups (Full Games / by Teams / ...) as sub folders
        top = re.sub(r'<li class="beefup2">.*?</ul>\s*</li>', '', nav, flags=re.S)
        for url, title in re.findall(r'<a href="(/[^"]+)"[^>]*>([^<]+)</a>', top):
            params = dict(cItem)
            params.update({'category': 'list_items', 'title': self.cleanHtmlStr(title), 'url': self.getFullUrl(url), 'good_for_fav': True})
            self.addDir(params)
        for group in self.cm.ph.getAllItemsBeetwenMarkers(nav, '<li class="beefup2">', '</ul>'):
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(group, r'class="beefup-head"[^>]*>([^<]+)<')[0])
            subs = re.findall(r'<a href="(/[^"]+)"[^>]*>([^<]+)</a>', group)
            if not title or not subs:
                continue
            params = dict(cItem)
            params.update({'category': 'list_group', 'title': title, 'subs': subs})
            self.addDir(params)
        self.listsTab(self.searchItems(), cItem)

    def listGroup(self, cItem):
        for url, title in cItem.get('subs', []):
            params = dict(cItem)
            params.pop('subs', None)
            params.update({'category': 'list_items', 'title': self.cleanHtmlStr(title), 'url': self.getFullUrl(url), 'good_for_fav': True})
            self.addDir(params)

    def _addGame(self, cItem, url, title, icon, desc):
        if not url or not title:
            return
        params = stripPagerKeys(dict(cItem), ('subs', 'page_tpl'))
        params.update({'good_for_fav': True, 'category': 'video', 'title': self._normTitle(title), 'raw_title': title,
                       'url': url, 'icon': icon, 'desc': desc})
        self.addVideo(params)

    def listItems(self, cItem):
        printDBG("NFLVideo.listItems [%s]" % cItem['url'])
        sts, data = self.getPage(cItem['url'])
        if not sts:
            # the site's own menu links to pages that are gone (e.g. /2025 answers 404)
            SetIPTVPlayerLastHostError(_("Content not available"))
            return
        items = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="poster">', 'class="short_bottom"')
        for item in items:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<h3', '>'), ('</h3', '>'), False)[1])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0])
            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'short_descr'), ('</div', '>'), False)[1])
            self._addGame(cItem, url, title, icon, desc)
        if not items and 'fullstory block_elem' in data:
            # a navigation entry that is a single show page (e.g. Hard Knocks)
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<h1[^>]*>(.*?)</h1>')[0]) or cItem['title']
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(data, r'class="full_img"[^>]*>\s*<img[^>]+src="([^"]+)"')[0])
            self._addGame(cItem, cItem['url'], title, icon, '')
        self._addPaging(cItem, data, bool(items))

    def listSearchResult(self, cItem, searchPattern, searchType):
        url = cItem.get('url', '')
        if not url:
            url = self.getFullUrl('/search/?q=%s' % urllib_quote_plus(searchPattern))
        params = dict(self.defaultParams)
        params['header'] = dict(self.HEADER, Referer=self.getMainUrl())
        sts, data = self.getPage(url, params)
        if not sts:
            return
        items = self.cm.ph.getAllItemsBeetwenMarkers(data, '<table border="0" cellpadding="0" cellspacing="0" width="100%" class="eBlock"', '</table>')
        for item in items:
            tmp = self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'eTitle'), ('</a', '>'))[1]
            link = self.cm.ph.getSearchGroups(tmp, r'href="([^"]+)"')[0]
            title = self.cleanHtmlStr(tmp)
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0])
            if not link or '/search/' in link:
                continue
            self._addGame(cItem, self.getFullUrl(link), title, icon, '')
        self._addPaging(cItem, data, bool(items))

    def _addPaging(self, cItem, data, hasItems):
        # uCoz paginator: "/?page2", "/archive/<cat>/<id>-2", "/search/?q=x&t=0&p=2;md=" - the numbered links
        # give the last page, the "next" link the url template
        pageRe = r'(\?page|-|[?&]p=)(\d+)(?:;md=)?$'
        page = int(cItem.get('page', 1) or 1)
        tpl = cItem.get('page_tpl', '')
        lastPage = 0
        hasNext = False
        for href in re.findall(r'class="swchItem[^"]*"\s+href="([^"]+)"', data):
            href = href.replace('&amp;', '&')
            m = re.search(pageRe, href)
            if not m:
                continue
            lastPage = max(lastPage, int(m.group(2)))
            if int(m.group(2)) == page + 1:
                hasNext = True
                if href.startswith('//'):
                    href = 'https:' + href
                tpl = self.getFullUrl(re.sub(pageRe, r'\1{page}', href))
        if lastPage and lastPage < page:
            lastPage = page
        addPagingItems(self, dict(cItem, page_tpl=tpl), page, hasItems and hasNext and bool(tpl), lastPage, tpl)

    ###################################################
    # links
    ###################################################
    def _gameBody(self, data):
        body = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'video-content'), ('<div', '>', 'entry-meta-bottom'), False)[1]
        if not body:
            body = self.cm.ph.getDataBeetwenMarkers(data, 'fullstory block_elem', 'full_info block_elem', False)[1]
        return body

    def getLinksForVideo(self, cItem):
        printDBG("NFLVideo.getLinksForVideo [%s]" % cItem['url'])
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return []
        body = self._gameBody(data)
        urlTab = []
        seen = set()
        label = ''
        # walk the page in order: a paragraph text without buttons ("Server #2 DM", "Condensed Game") names the
        # following buttons; a paragraph with a heading and buttons carries both
        # (no zero-width re.split - Python 2.7 does not split on empty matches)
        for chunk in re.sub(r'(<p[\s>])', r'<!--split-->\1', body).split('<!--split-->'):
            anchors = re.findall(r'<a[^>]+class="su-button[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', chunk, re.S)
            frames = re.findall(r'<iframe[^>]+src="([^"]+)"', chunk, re.I)
            heading = self.cleanHtmlStr(re.sub(r'<a[^>]+>.*?</a>', '', chunk, flags=re.S))
            isLabel = (anchors or frames) and len(heading) < 40
            isLabel = isLabel or (len(heading) < 30 and re.search(r'Server|Condensed|Highlights', heading))
            if heading and isLabel:
                label = heading
            for url, text in anchors:
                url = self.getFullUrl(url.replace('&amp;', '&'))
                if not self.cm.isValidUrl(url) or url in seen:
                    continue
                seen.add(url)
                text = self.cleanHtmlStr(text)
                name = '%s - %s' % (label, text) if label and text else (label or text or self.up.getHostName(url))
                urlTab.append({'name': name, 'url': strwithmeta(url, {'Referer': cItem['url']}), 'need_resolve': 1})
            for url in frames:
                url = url.replace('&amp;', '&')
                if url.startswith('//'):
                    url = 'https:' + url
                if not self.cm.isValidUrl(url) or url in seen:
                    continue
                seen.add(url)
                host = self.up.getHostName(url)
                name = '%s - %s' % (label, host) if label else host
                urlTab.append({'name': name, 'url': strwithmeta(url, {'Referer': cItem['url']}), 'need_resolve': 1})
        # unnamed groups (full game / condensed ...) repeat the same button labels - numbered there
        return self._finishLinks(cItem, urlTab)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("NFLVideo.getArticleContent [%s]" % cItem.get('url', ''))
        title = cItem.get('raw_title') or cItem.get('title', '')
        text = cItem.get('desc', '')
        icon = cItem.get('icon', '')
        other = {}
        sts, data = self.getPage(cItem['url'])
        if sts:
            body = self._gameBody(data)
            body = re.sub(r'<p[^>]*>\s*<span[^>]*>\s*<span[^>]*>Server.*?</p>', '', body, flags=re.S)
            body = re.sub(r'<a[^>]+class="su-button.*?</a>', '', body, flags=re.S)
            lines = []
            for para in re.findall(r'<p[^>]*>(.*?)</p>', body, re.S):
                para = self.cleanHtmlStr(para.replace('<br />', '[/br]').replace('<br>', '[/br]'))
                if not para or set(para) <= set('-[/br] ') or para.startswith('Disclaimer') or 'Server #' in para:
                    continue
                lines.append(para)
            if lines:
                text = '[/br]'.join(lines)
            icon = icon or self.getFullIconUrl(self.cm.ph.getSearchGroups(data, r'class="full_img"[^>]*>\s*<img[^>]+src="([^"]+)"')[0])
        date = self._parseDate(title)
        if date:
            other['released'] = date
        return [{'title': self.cleanHtmlStr(title), 'text': text, 'images': [{'title': '', 'url': icon}] if icon else [], 'other_info': other}]


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, NFLVideo(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('nflvideo')

    def withArticleContent(self, cItem):
        return cItem.get('type') == 'video'
