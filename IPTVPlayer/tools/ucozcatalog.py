# -*- coding: utf-8 -*-
# Shared code of the uCoz sport replay catalogues (basketball-video.com, mlblive.net, fullraces.com and,
# partly, nfl-video.com): navigation groups, "?pageN" / ";p=N" pager, /search/ result table, game page
# body, hoster link pages with one <iframe>, INFO text.
#
#   class Host(UcozCatalogMixin, GenericFolderWatchedScraperMixin, CBaseHostClass)
#
# The host provides getPage(), _normTitle(), HEADER / defaultParams and may override:
#   UCOZ_DEAD_NAV      navigation paths to skip (404 on the site)
#   _mainLinks(links)  extra top level folders
#   _parseDate(text)   'YYYY-MM-DD' from a title
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
###################################################
# FOREIGN import
###################################################
import re
###################################################

MONTHS = {'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6, 'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12}
DATE_RE = r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b'
DATE_NUM_RE = r'\b(\d{2})\.(\d{2})\.(\d{4})\b'
YEAR_RE = r'\b((?:19|20)\d\d)\b'
# a short heading that only names the source ("Server #2", "Dailymotion", ...) - belongs to the heading above it
SOURCE_LABEL_RE = r'^(?:server\b|ok\b|ok\.ru|okru|dailymotion|filemoon|byse|vidara|luluvid|youtube|vk\b|backup|mirror|link\b|watch\b)'
FAV_FIELDS = ('name', 'category', 'type', 'url', 'title', 'icon', 'desc', 'raw_title', 'competition')


def parseDate(text):
    # "September 2, 2026" / "02.09.2026" -> "2026-09-02"
    m = re.search(DATE_RE, text or '', re.I)
    if m:
        return '%s-%02d-%02d' % (m.group(3), MONTHS[m.group(1).lower()[:3]], int(m.group(2)))
    m = re.search(DATE_NUM_RE, text or '')
    if m and 0 < int(m.group(2)) <= 12 and 0 < int(m.group(1)) <= 31:
        return '%s-%s-%s' % (m.group(3), m.group(2), m.group(1))
    return ''


def _fixUrl(url):
    url = url.replace('&amp;', '&')
    return 'https:' + url if url.startswith('//') else url


def numberDuplicateNames(urlTab):
    # e.g. two players under one "Server #2" heading -> "(1)", "(2)"
    names = [item['name'] for item in urlTab]
    counter = {}
    for item in urlTab:
        if names.count(item['name']) > 1:
            counter[item['name']] = counter.get(item['name'], 0) + 1
            item['name'] = '%s (%d)' % (item['name'], counter[item['name']])
    return urlTab


class UcozCatalogMixin(object):
    # mix in BEFORE GenericFolderWatchedScraperMixin / CBaseHostClass
    FAV_FIELDS = FAV_FIELDS
    UCOZ_DEAD_NAV = ()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ''
            if cItem.get('search_item') or cItem.get('name') == 'history':
                return ''
            if cItem.get('type') == 'video' or cItem.get('category') == 'video':
                url = self._stableUrl(cItem.get('url', ''))
                return 'video:%s' % url if url else ''
            if cItem.get('category') == 'list_items':
                # "Next page" rows carry the folder's url (wf_url), so page 2+ keys like page 1
                url = self._stableUrl(cItem.get('wf_url') or cItem.get('url', ''))
                return 'folder:%s' % url if url else ''
        except Exception:
            printExc()
        return ''

    def _stableUrl(self, url):
        # path only, so the domain may move
        url = str(url or '').strip()
        if not url or '/search/' in url:
            return ''
        url = re.sub(r'^https?://[^/]+', '', url)
        url = re.sub(r'\?page\d+$', '', url)
        return url or '/'

    def getFavouriteData(self, cItem):
        try:
            if cItem.get('type') == 'video':
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def _parseDate(self, text):
        return parseDate(text)

    ###################################################
    # listing
    ###################################################
    def _navLinks(self, html):
        links = []
        for url, attrs, title in re.findall(r'<a href="((?:https?://[^/"]+)?/[^"#]*)"([^>]*)>([^<]+)</a>', html):
            path = re.sub(r'^https?://[^/]+', '', url)
            if 'nofollow' in attrs or 'content-policy' in url or path in self.UCOZ_DEAD_NAV:
                continue
            links.append((self.getFullUrl(url), self.cleanHtmlStr(title)))
        return links

    def _mainLinks(self, links):
        return links

    def listMain(self, cItem):
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        self.setMainUrl(data.meta.get('url', self.getMainUrl()))
        nav = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'list_cat'), ('</nav', '>'), False)[1]
        params = dict(cItem)
        params.update({'good_for_fav': True, 'category': 'list_items', 'title': _('Latest'), 'url': self.getMainUrl()})
        self.addDir(params)
        # top level links, then the "beefup" groups (seasons / teams / ...) as sub folders
        top = re.sub(r'<li class="beefup2">.*?</ul>\s*</li>', '', nav, flags=re.S)
        for url, title in self._mainLinks(self._navLinks(top)):
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': 'list_items', 'title': title, 'url': url})
            self.addDir(params)
        for group in self.cm.ph.getAllItemsBeetwenMarkers(nav, '<li class="beefup2">', '</ul>'):
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(group, r'class="beefup-head"[^>]*>([^<]+)<')[0])
            subs = self._navLinks(group.split('</a>', 1)[-1])
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
            params.update({'good_for_fav': True, 'category': 'list_items', 'title': title, 'url': url})
            self.addDir(params)

    def _addGame(self, cItem, url, title, icon, desc, competition=''):
        if not url or not title:
            return
        params = stripPagerKeys(dict(cItem), ('subs', 'wf_url'))
        params.update({'good_for_fav': True, 'category': 'video', 'title': self._normTitle(title), 'raw_title': title,
                       'url': url, 'icon': icon, 'desc': desc, 'competition': competition})
        self.addVideo(params)

    def _addNextPage(self, cItem, nextPage, data):
        # uCoz pager: "?pageN" (lists) / ";p=N" (search) links, the highest number is the last page;
        # the page template comes from the pager's own "next" link
        nextPage = _fixUrl(nextPage)
        nextPage = self.getFullUrl(nextPage) if nextPage else ''
        try:
            page = max(1, int(cItem.get('page', 1) or 1))
        except (TypeError, ValueError):
            page = 1
        numbers = [int(n) for n in re.findall(r'class="swchItem[^"]*"[^>]*>\s*<span>(\d+)</span>', data)]
        lastPage = max(numbers + [page]) if numbers else 0
        tpl = ''
        m = re.match(r'^(.*?)(\d+)$', nextPage)
        if m and int(m.group(2)) == page + 1:
            tpl = m.group(1)
        elif page > 1:
            # last page (no "next" link): the page's own url ("?pageN" / ";p=N") gives the template, else
            # "First page" would keep this page's url and list it again
            m = re.match(r'^(.*?)(\d+)$', cItem.get('url', ''))
            if m and int(m.group(2)) == page:
                tpl = m.group(1)
        if tpl:
            tpl = tpl.replace('{', '%7B').replace('}', '%7D') + '{page}'
        params = dict(cItem, wf_url=cItem.get('wf_url') or cItem.get('url', ''))
        addPagingItems(self, params, page, bool(nextPage), lastPage, tpl, {'url': nextPage} if nextPage else None)

    def listItems(self, cItem):
        printDBG("%s.listItems [%s]" % (self.__class__.__name__, cItem['url']))
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        # the pager's own "next" link (from page 2 on the first swchItem points back to page 1)
        nextPage = self.cm.ph.getSearchGroups(data, r'swchItem-next"\s+href="([^"]+)"')[0]
        items = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="poster">', 'class="short_bottom"')
        for item in items:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<h3', '>'), ('</h3', '>'), False)[1])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0])
            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'short_descr'), ('</div', '>'), False)[1])
            competition = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'short_cat'), ('</div', '>'), False)[1])
            self._addGame(cItem, url, title, icon, desc, competition)
        self._addNextPage(cItem, nextPage if items else '', data)

    def listSearchResult(self, cItem, searchPattern, searchType):
        url = cItem.get('url', '')
        if not url:
            url = self.getFullUrl('/search/?q=%s' % urllib_quote_plus(searchPattern))
        params = dict(self.defaultParams)
        params['header'] = dict(self.HEADER, Referer=self.getMainUrl())
        sts, data = self.getPage(url, params)
        if not sts:
            return
        nextPage = self.cm.ph.getSearchGroups(data, r'swchItem-next"\s+href="([^"]+)"')[0]
        items = self.cm.ph.getAllItemsBeetwenMarkers(data, '<table border="0" cellpadding="0" cellspacing="0" width="100%" class="eBlock"', '</table>')
        for item in items:
            tmp = self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'eTitle'), ('</a', '>'))[1]
            link = self.cm.ph.getSearchGroups(tmp, r'href="([^"]+)"')[0]
            title = self.cleanHtmlStr(tmp)
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0])
            if not link or '/search/' in link:
                continue
            self._addGame(cItem, self.getFullUrl(link), title, icon, '')
        # ";md=" is a per-request token, the plain query pages fine
        self._addNextPage(cItem, nextPage.split(';md=')[0] if items else '', data)

    ###################################################
    # links
    ###################################################
    def _gameBody(self, data):
        body = self.cm.ph.getDataBeetwenMarkers(data, 'fullstory block_elem', 'full_info block_elem', False)[1]
        return re.sub(r'<(script|style)[^>]*>.*?</\1>', '', body, flags=re.S | re.I)

    def _isLabel(self, text):
        return 0 < len(text) < 90 and not text.lower().startswith('disclaimer') and not set(text) <= set('-_=* ')

    def _finishLinks(self, cItem, urlTab):
        if not urlTab:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        numberDuplicateNames(urlTab)
        synopsis = self.cleanHtmlStr(cItem.get('desc', ''))
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled(), synopsis))

    def getLinksForVideo(self, cItem):
        # player blocks ("gameplayer") and "Server #N" headings with buttons / <iframe>s (mlblive, fullraces)
        printDBG("%s.getLinksForVideo [%s]" % (self.__class__.__name__, cItem['url']))
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return []
        body = self._gameBody(data)
        urlTab = []
        seen = set()

        def addLink(url, name):
            url = self.getFullUrl(_fixUrl(url))
            if not self.cm.isValidUrl(url) or url in seen:
                return
            seen.add(url)
            # "Server #3" -> "Server #3 - bysesukior.com" (not for the site's own link pages)
            host = self.up.getHostName(url)
            if host and host not in self.getMainUrl() and not re.search(r'\b%s\b' % re.escape((host.split('.')[-2:-1] or [host])[0]), name, re.I):
                name = ' - '.join([x for x in (name, host) if x])
            urlTab.append({'name': name or host, 'url': strwithmeta(url, {'Referer': cItem['url']}), 'need_resolve': 1})

        # newer pages: a player block with one button per source ("OK.ru / Main", "Dailymotion 1 / Part 1", ...)
        for player in re.findall(r'<div class="gameplayer">(.*?)class="gp-foot"', body, re.S):
            heading = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(player, ('<h2', '>', 'gp-match'), ('</h2', '>'), False)[1])
            for url, inner in re.findall(r'<a[^>]+class="gp-src[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', player, re.S):
                source = self.cleanHtmlStr(self.cm.ph.getSearchGroups(inner, r'<b>(.*?)</b>')[0])
                note = self.cleanHtmlStr(self.cm.ph.getSearchGroups(inner, r'class="off">([^<]*)')[0])
                if note.lower() in ('main', 'playing'):
                    note = ''
                addLink(url, ' - '.join([x for x in (heading, source, note) if x]))
        body = re.sub(r'<div class="gameplayer">.*?class="gp-foot".*?</p>', '', body, flags=re.S)

        main = sub = ''
        # walk the page in order: a short paragraph names the following buttons / players; "Server #2" or
        # "Dailymotion" under a longer heading is added to it (no zero-width re.split - Python 2.7)
        for chunk in re.sub(r'(<p[\s>])', r'<!--split-->\1', body).split('<!--split-->'):
            para = self.cm.ph.getDataBeetwenNodes(chunk, ('<p', '>'), ('</p', '>'), False)[1]
            if para and '<br' not in para:
                heading = self.cleanHtmlStr(re.sub(r'<a[^>]+>.*?</a>', '', para, flags=re.S))
                if heading and set(heading) <= set('-_=* '):
                    main = sub = ''
                elif self._isLabel(heading):
                    if re.match(SOURCE_LABEL_RE, heading, re.I):
                        sub = heading
                    else:
                        main, sub = heading, ''
            anchors = re.findall(r'<a[^>]+class="su-button[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', chunk, re.S)
            frames = re.findall(r'<iframe[^>]+src="([^"]+)"', chunk, re.I)
            for url, text in anchors:
                text = self.cleanHtmlStr(text)
                if text.lower() == 'watch':
                    text = ''
                addLink(url, ' - '.join([x for x in (main, sub, text) if x]))
            for url in frames:
                addLink(url, ' - '.join([x for x in (main, sub) if x]))
        return self._finishLinks(cItem, urlTab)

    def _isDirect(self, url):
        return re.search(r'\.(?:mp4|m3u8)(?:\?|$)', url.split('#')[0], re.I) is not None

    def getVideoLinks(self, videoUrl):
        printDBG("%s.getVideoLinks [%s]" % (self.__class__.__name__, videoUrl))
        videoUrl = strwithmeta(videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        url = videoUrl
        if 1 != self.up.checkHostSupport(url) and not self._isDirect(url):
            # link page of the site network (nbaontv.com, mlblive.net/01-NNN, ...): one hoster <iframe>
            params = dict(self.defaultParams)
            params['header'] = dict(self.HEADER, Referer=videoUrl.meta.get('Referer', self.getMainUrl()))
            sts, data = self.getPage(url, params)
            if not sts:
                return []
            frame = _fixUrl(self.cm.ph.getSearchGroups(data, r'<iframe[^>]+src="([^"]+)"', ignoreCase=True)[0])
            if not self.cm.isValidUrl(frame):
                SetIPTVPlayerLastHostError(_("Content not available"))
                return []
            url = strwithmeta(frame, {'Referer': videoUrl})
        if self._isDirect(url):
            # a plain MP4 / HLS file (e.g. a condensed game on mlb.com)
            return decorateResolvedLinkItems([{'name': self.up.getHostName(url), 'url': strwithmeta(url, {'User-Agent': self.HEADER['User-Agent']})}], sidecar)
        if 0 > self.up.checkHostSupport(url):
            SetIPTVPlayerLastHostError(_("Hosting \"%s\" not supported.") % self.up.getHostName(url))
            return []
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(url), sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("%s.getArticleContent [%s]" % (self.__class__.__name__, cItem.get('url', '')))
        title = cItem.get('raw_title') or cItem.get('title', '')
        text = cItem.get('desc', '')
        icon = cItem.get('icon', '')
        other = {}
        if cItem.get('competition'):
            other['category'] = cItem['competition']
        sts, data = self.getPage(cItem['url'])
        if sts:
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<h1[^>]*>(.*?)</h1>')[0]) or title
            body = self._gameBody(data)
            body = re.sub(r'<a[^>]+class="(?:su-button|gp-src).*?</a>', '', body, flags=re.S)
            body = re.sub(r'<(?:div|p)[^>]+class="gp-(?:load|foot)".*?</(?:div|p)>', '', body, flags=re.S)
            lines = []
            for para in re.findall(r'<(?:p|div)[^>]*>((?:(?!<(?:p|div)[\s>]).)*?)</(?:p|div)>', body, re.S):
                para = self.cleanHtmlStr(re.sub(r'<br\s*/?>', '[/br]', para))
                para = re.sub(r'(?:^(?:\s*\[/br\])+)|(?:(?:\[/br\]\s*)+$)', '', para).strip()
                if not para or set(para) <= set('-[/br] ') or para.lower().startswith('disclaimer') or 'Server #' in para or re.match(SOURCE_LABEL_RE, para, re.I):
                    continue
                if para not in lines:
                    lines.append(para)
            if lines:
                text = '[/br]'.join(lines)
            icon = icon or self.getFullIconUrl(self.cm.ph.getSearchGroups(data, r'class="full_img"[^>]*>.*?<img[^>]+src="([^"]+)"')[0])
            category = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'class="e-category"[^>]*>(.*?)</span>')[0])
            if category:
                other['category'] = category
            views = self.cm.ph.getSearchGroups(data, r'class="ed-value">(\d+)<')[0]
            if views:
                other['views'] = views
        date = self._parseDate(title)
        if date:
            other['released'] = date
        return [{'title': self.cleanHtmlStr(title), 'text': text, 'images': [{'title': '', 'url': icon}] if icon else [], 'other_info': other}]

    ###################################################
    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("%s.handleService name[%s] category[%s]" % (self.__class__.__name__, name, category))
        self.currList = []
        if name is None:
            self.listMain({'name': 'category'})
        elif category == 'list_group':
            self.listGroup(self.currItem)
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
