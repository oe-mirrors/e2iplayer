# -*- coding: utf-8 -*-
# Last Modified: 10.10.2026
# 24.08.2026 - Added PHP iframe HLS link extraction, fixed crash on video open - Blindspot
# 10.10.2026 - host standard: the categories come from the site menu by their links (the old index list
#   skipped the wrong entries), paging is "/cikkek/<cat>.N/" with First/Jump/Next and the last page, no
#   extra request per film any more (the list carries genre/length/year), covers as full urls, "Latest added"
#   (home page), seasons ("... 1 ÉVAD") open as episode lists (hoster links or players in page order), every
#   player/hoster of a film is its own link through urlparser (vkvideo, ok.ru, videa, filemoon ...), search
#   through the site's own eStránky catalogue form (katalog.estranky.cz, the old katalogus.eoldal.hu is
#   gone), watched flag (season -> episode), favourites, sidecar, "Title (Year)" / "Show - SxxExx", INFO via
#   moviemeta merged with the site's fields; py2: no cgi import any more
# 10.10.2026 - review: series without "N. évad" in the title ("Dragon Ball") open as season 1 with an
#   episode per player instead of one film with dozens of links
###################################################
HOST_VERSION = "1.8"
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
###################################################
# FOREIGN import
###################################################
import re
###################################################


def GetConfigList():
    return []


def gettytul():
    return 'https://onlinefilmvilag2.eu/'


# search form of the site: the eStránky catalogue with the site's user id
SEARCH_URL = 'https://katalog.estranky.cz/'
SEARCH_UID = '1504382'
# menu entries that are no film lists (legal notice, film requests, audio track help, download help)
SKIP_MENU = ('jogi-nyilatkozat', 'kerjel-filmet', 'audio-track', 'letoltes-segedlet')
SEASON_RE = re.compile(r'^(.*?)[\s(\-]*(\d+)\s*\.?\s*(?:évad|Évad|evad)', re.I)  # é / É both: py2 matches bytes
QUALITY_RE = re.compile(r'\s*\((4K|2K|FHD|HD|SD|UHD|1080p|720p)\)\s*$', re.I)
EPISODE_RE = re.compile(r'(\d+)\s*\.?\s*rész')


class FilmVilag(GenericFolderWatchedScraperMixin, CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'filmvilag', 'cookie': 'filmvilag.cookie'})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/filmvilag135.png")
        self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper('filmvilag')
        self.wfInitFolderCache()

    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict) or cItem.get('search_item'):
                return ''
            url = str(cItem.get('url', '') or '').strip()
            if url == '':
                return ''
            if cItem.get('type') == 'video':
                return ('episode:%s' if cItem.get('category') == 'episode' else 'video:%s') % url
            if cItem.get('category') == 'fv_season':
                return 'season:%s' % url
        except Exception:
            printExc()
        return ''

    ###################################################
    # helpers
    ###################################################
    def _editorArea(self, data):
        return self.cm.ph.getDataBeetwenMarkers(data, '<div class="editor-area">', '<div class="article-cont-clear', False)[1]

    def _splitTitle(self, title):
        """(local title, original title, quality) of "Elrabolva/Taken/ (4K)" """
        quality = ''
        m = QUALITY_RE.search(title)
        if m:
            quality = m.group(1)
            title = title[:m.start()]
        parts = [p.strip() for p in title.split('/')]
        local = parts[0] or title.strip()
        original = parts[1] if len(parts) > 1 else ''
        return local, original, quality

    def _seasonOf(self, title):
        """(show, season) of "Terror 1 ÉVAD" / "12 Majom (1ÉVAD)", ('', '') for a film"""
        m = SEASON_RE.search(title)
        if not m:
            return '', ''
        show = m.group(1).strip(' -(/') or title
        return show, str(int(m.group(2)))

    def _addArticle(self, cItem, url, title, icon, siteDesc):
        title = self.cleanHtmlStr(title)
        if not url or not title:
            return
        year = (re.findall(r'\b((?:19|20)\d{2})\b', siteDesc) or [''])[-1]
        params = stripPagerKeys(dict(cItem), ('base_url',))
        params.update({'good_for_fav': True, 'url': url, 'icon': icon, 'desc': siteDesc, 's_year': year, 'raw_title': title})
        show, season = self._seasonOf(title)
        if not show and '/sorozat/' in url:
            # a series without "N. évad" in its title ("Dragon Ball (1986)"): one season, an episode per player
            show, season = re.sub(r'\s*\((?:19|20)\d{2}\)\s*$', '', title) or title, '1'
        if show:
            params.update({'category': 'fv_season', 'title': title, 's_title': show, 'season': season})
            if IsMediaNamingNormalized():
                params['title'] = '%s - %s' % (self._splitTitle(show)[0], formatSxxExx(season))
            self.addDir(params)
            return
        local, _original, quality = self._splitTitle(title)
        if IsMediaNamingNormalized():
            title = '%s (%s)' % (local, year) if year and ('(%s)' % year) not in local else local
        params.update({'category': 'movie', 'title': title, 'quality': quality})
        self.addVideo(params)

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self, cItem):
        printDBG('FilmVilag.listMainMenu')
        self.addDir(dict(cItem, category='list_filters', title=_('Latest added'), url=self.MAIN_URL, good_for_fav=True, single_page=True))
        sts, data = self.getPage(self.MAIN_URL)
        if sts:
            menu = self.cm.ph.getDataBeetwenMarkers(data, '<menu', '</menu>', False)[1]
            for href, title in re.findall(r'<a href="(/cikkek/[^"]+/)"[^>]*>([^<]+)</a>', menu):
                if any(s in href for s in SKIP_MENU):
                    continue
                self.addDir(dict(cItem, category='list_filters', title=self.cleanHtmlStr(title), url=self.getFullUrl(href), good_for_fav=True))
        self.listsTab(self.searchItems(), cItem)

    def listItems(self, cItem):
        printDBG('FilmVilag.listItems')
        base = cItem.get('base_url') or cItem['url']
        if not base.endswith('/'):
            base += '/'  # categories saved by the old version: ".../cikkek/akcio"
        try:
            page = max(1, int(cItem.get('page', 1) or 1))
        except (TypeError, ValueError):
            page = 1
        single = cItem.get('single_page') or base.rstrip('/') == self.MAIN_URL.rstrip('/')
        pageTpl = '' if single else base[:-1].replace('{', '{{').replace('}', '}}') + '.{page}/'
        sts, data = self.getPage(base if page == 1 or single else pageTpl.format(page=page))
        if not sts:
            return
        for article in data.split('<div class="article">')[1:]:
            article = article.split('<!-- /Article -->')[0]
            href = self.cm.ph.getSearchGroups(article, r'<h3>\s*<a href="([^"]+)"')[0]
            title = self.cm.ph.getSearchGroups(article, r'<span class="decoration" title="([^"]+)"')[0] or self.cm.ph.getSearchGroups(article, r'<h3>\s*<a[^>]*>([^<]+)</a>')[0]
            icon = self.cm.ph.getSearchGroups(article, r'<div class="preview">\s*<a[^>]*>\s*<img[^>]+src="([^"]+)"')[0]
            siteDesc = self.cleanHtmlStr(self._editorArea(article)).replace('(adsbygoogle = window.adsbygoogle || []).push({});', '').strip()
            self._addArticle(cItem, self.getFullUrl(href) if href else '', title, self.getFullIconUrl(icon) if icon else '', siteDesc)
        if single:
            return
        pages = [int(x) for x in re.findall(r'href="[^"]*\.(\d+)/"', self.cm.ph.getDataBeetwenMarkers(data, 'class="list-of-pages"', '</div>', False)[1])]
        lastPage = max(pages + [page])
        addPagingItems(self, dict(cItem, base_url=base, url=base), page, page < lastPage, lastPage, pageTpl)

    def _episodes(self, data):
        """[(episode number, [hoster urls], label)] of a season page"""
        area = self._editorArea(data)
        episodes = []
        # hoster links: "<a href=hoster>1.rész.Hun.Eng.Voice.720p...</a>"
        for href, label in re.findall(r'<a href="(https?://[^"]+)"[^>]*>(.*?)</a>', area, re.S):
            label = self.cleanHtmlStr(label)
            m = EPISODE_RE.search(label)
            if m and self.up.checkHostSupport(href) == 1:
                episodes.append((int(m.group(1)), [href], label))
        if episodes:
            return episodes
        # players only, one per episode in page order
        for idx, src in enumerate(re.findall(r'<iframe[^>]+src="([^"]+)"', area)):
            src = src.replace('&amp;', '&')
            episodes.append((idx + 1, ['https:' + src if src.startswith('//') else src], ''))
        return episodes

    def listEpisodes(self, cItem):
        printDBG('FilmVilag.listEpisodes')
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        show = cItem.get('s_title', '') or self._seasonOf(cItem.get('raw_title', cItem['title']))[0] or cItem['title']
        season = cItem.get('season', '') or '1'
        normalize = IsMediaNamingNormalized()
        local = self._splitTitle(show)[0]
        for num, links, label in self._episodes(data):
            if normalize:
                title = '%s - %s' % (local, formatSxxExx(season, num))
            else:
                title = '%s - %s' % (cItem.get('raw_title', cItem['title']), label or '%d. rész' % num)
            params = stripPagerKeys(dict(cItem))
            params.update({'good_for_fav': True, 'category': 'episode', 'title': title, 'url': '%s#e%d' % (cItem['url'], num), 'page_url': cItem['url'],
                           'ep_num': str(num), 'ep_links': links, 's_title': show, 'season': season})
            self.addVideo(params)
        if not self.currList:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("FilmVilag.listSearchResult [%s]" % searchPattern)
        sts, data = self.getPage(SEARCH_URL, dict(self.defaultParams), {'uid': SEARCH_UID, 'key': searchPattern})
        if not sts:
            return
        results = self.cm.ph.getDataBeetwenMarkers(data, 'id="userresult"', '</ul>', False)[1]
        seen = set()
        for href, title in re.findall(r'<li><a href="([^"]+)">([^<]+)</a>', results):
            href = href.replace('http://', 'https://')
            if href in seen or '/cikkek/' not in href or any(s in href for s in SKIP_MENU):
                continue
            seen.add(href)
            self._addArticle(cItem, href, title, '', '')

    ###################################################
    # links
    ###################################################
    def _pageLinks(self, data):
        area = self._editorArea(data)
        links = []
        for src in re.findall(r'<iframe[^>]+src="([^"]+)"', area) + re.findall(r'<a href="(https?://[^"]+)"', area):
            src = src.replace('&amp;', '&')
            src = 'https:' + src if src.startswith('//') else src
            if src not in links and self.up.checkHostSupport(src) == 1:
                links.append(src)
        return links

    def getLinksForVideo(self, cItem):
        printDBG("FilmVilag.getLinksForVideo [%s]" % cItem)
        url = cItem.get('url', '')
        if cItem.get('category') == 'episode':
            links = []
            sts, data = self.getPage(cItem.get('page_url') or url.split('#')[0])
            if sts:
                for num, epLinks, _label in self._episodes(data):
                    if str(num) == str(cItem.get('ep_num')):
                        links = epLinks
                        break
            links = links or cItem.get('ep_links') or []
        elif '/cikkek/' in url:
            sts, data = self.getPage(url)
            links = self._pageLinks(data) if sts else []
        else:
            # search rows saved by the old version carried the player url itself ("//ok.ru/...")
            links = ['https:' + url if url.startswith('//') else url]
        urlTab = []
        for link in links:
            urlTab.append({'name': self.up.getHostName(link).capitalize() or 'Link', 'url': strwithmeta(link, {'Referer': self.MAIN_URL}), 'need_resolve': 1})
        if not urlTab:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def getVideoLinks(self, videoUrl):
        printDBG("FilmVilag.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        urlTab = self.up.getVideoLinkExt(videoUrl)
        if not urlTab:
            SetIPTVPlayerLastHostError(_("Content not available"))
        return decorateResolvedLinkItems(urlTab, sidecarFromUrlMeta(videoUrl, IsSidecarEnabled()))

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("FilmVilag.getArticleContent [%s]" % cItem)
        isSeries = cItem.get('category') in ('fv_season', 'episode')
        pageUrl = cItem.get('page_url') or cItem.get('url', '').split('#')[0]
        rawTitle = cItem.get('raw_title', '') or cItem.get('title', '')
        info, story, icon = {}, '', cItem.get('icon', '')
        if pageUrl.startswith(self.MAIN_URL):
            sts, data = self.getPage(pageUrl)
            if sts:
                ogTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta property="og:title" content="([^"]+)"')[0])
                rawTitle = cItem.get('raw_title', '') or ogTitle or rawTitle
                icon = icon or self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
                facts = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta property="og:description" content="([^"]*)"')[0])
                area = self._editorArea(data)
                for para in re.findall(r'<p>(.*?)</p>', area, re.S):
                    text = self.cleanHtmlStr(para)
                    if len(text) > 80:
                        story = text
                        break
                credits = self.cleanHtmlStr(self.cm.ph.getSearchGroups(area, r'(Rendező:.*?)</h2>', 1, True)[0])
                director = self.cm.ph.getSearchGroups(credits, r'Rendező:\s*(.*?)\s*(?:Szereplők:|$)')[0]
                actors = self.cm.ph.getSearchGroups(credits, r'Szereplők:\s*(.*)$')[0]
                if director:
                    info['director'] = director
                if actors:
                    info['actors'] = actors
                if facts:
                    parts = [p.strip() for p in facts.split(',') if p.strip()]
                    if parts and not re.search(r'\d', parts[0]):
                        info['genre'] = parts[0]
                    for part in parts:
                        if 'perc' in part:
                            info['duration'] = part
        if isSeries:
            show = cItem.get('s_title', '') or self._seasonOf(rawTitle)[0] or rawTitle
            local, original, quality = self._splitTitle(show)
        else:
            local, original, quality = self._splitTitle(rawTitle)
        year = cItem.get('s_year', '')
        meta = {}
        try:
            for name in (original, local):
                if name:
                    meta = getMeta('tv' if isSeries else 'movie', re.sub(r'\s*\((?:19|20)\d{2}\)\s*$', '', name), year)
                    if meta:
                        break
        except Exception:
            printExc()
        merged = dict(meta.get('info', {}))
        merged.update(info)
        if year and 'year' not in merged:
            merged['year'] = year
        quality = quality or cItem.get('quality', '')
        if quality:
            merged['quality'] = quality
        if original:
            merged['original_title'] = original
        plot = meta.get('plot', '')
        text = story or plot or cItem.get('desc', '')
        if plot and story and plot != story:
            text = '%s[/br][/br]%s' % (story, plot)
        icon = icon or meta.get('poster', '')
        return [{'title': cItem.get('title', ''), 'text': text, 'images': [{'title': '', 'url': self.getFullIconUrl(icon)}] if icon else [], 'other_info': merged}]

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('FilmVilag.handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("handleService: >> name[%s], category[%s]" % (name, category))
        self.currList = []

        if name is None:
            self.listMainMenu({'name': 'category'})
        elif category == 'list_items':
            # "Kategóriák" saved by the old version - the categories are in the main menu now
            self.listMainMenu({'name': 'category'})
        elif category == 'list_filters':
            self.listItems(self.currItem)
        elif category == 'fv_season':
            self.listEpisodes(self.currItem)
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
        CHostBase.__init__(self, FilmVilag(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('filmvilag')

    def withArticleContent(self, cItem):
        return cItem.get('type') == 'video' or cItem.get('category') == 'fv_season'
