# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026
# Assabile (assabile.com) - Quran recitations, anasheed, adhan and Islamic lessons.
# Site languages are sub-domains (www = English, ar, fr, es, tr), all with the same markup.
#   person lists:  /quran, /quran/<country>, /anasheed, /lesson  (12 per page, /page:N)
#   reciter:       "var id_person" + riwaya drop-down (data-collection) -> /ajax/loadplayer-<person>-<collection> (JSON)
#   munshid:       /<person>/album -> album page tracks
#   lecturer:      /<person>/series (video, <source> mp4 per episode page), /<person>/series-audio (direct mp3)
#   tracks:        <a class="link-media" href="#<id>">: recitation -> /ajax/getrcita-link-<id>,
#                  nasheed (has data-title) -> /ajax/getsnng-link-<id>; both answer with the plain mp3 url
# 03.10.2026 - new host: reciters, surahs, anasheed, adhan, lessons, search, watched flag,
#   favourites, First page / Jump / Next page, sidecar, name normalisation "Person - Track"
import re
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetDefaultLang
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Components.config import config, ConfigSelection, getConfigListEntry

config.plugins.iptvplayer.assabile_lang = ConfigSelection(default='auto', choices=[
    ('auto', _('Auto')), ('www', 'English'), ('ar', 'العربية'), ('fr', 'Français'), ('es', 'Español'), ('tr', 'Türkçe')])


def GetConfigList():
    return [getConfigListEntry(_('Language:'), config.plugins.iptvplayer.assabile_lang)]


def gettytul():
    return 'https://www.assabile.com/'


class Assabile(GenericFolderWatchedScraperMixin, CBaseHostClass):

    # link endpoints answer on every language sub-domain; items keep the www
    # url so watched / downloaded marks survive a language switch
    LINK_BASE = 'https://www.assabile.com/ajax/'

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'Assabile', 'cookie': 'Assabile.cookie'})
        self.MAIN_URL = self.getSiteUrl()
        self.DEFAULT_ICON_URL = 'https://www.assabile.com/img/logo-assabile.png'
        self.HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper('assabile')
        self.wfInitFolderCache()

    @staticmethod
    def getSiteUrl():
        lang = config.plugins.iptvplayer.assabile_lang.value
        if lang == 'auto':
            lang = GetDefaultLang()
            if lang not in ('ar', 'fr', 'es', 'tr'):
                lang = 'www'
        return 'https://%s.assabile.com/' % lang

    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    def getAjax(self, url, referer=''):
        params = dict(self.defaultParams)
        params['header'] = dict(self.HEADER, Referer=referer or self.MAIN_URL)
        params['header']['X-Requested-With'] = 'XMLHttpRequest'
        return self.getPage(url, params)

    def fullUrl(self, url):
        if not url:
            return ''
        if url.startswith('//'):
            return 'https:' + url
        if url.startswith('/'):
            return self.MAIN_URL.rstrip('/') + url
        return url

    @staticmethod
    def pathOf(url):
        # language independent identity of a site page
        return re.sub(r'^https?://[^/]+', '', url or '').split('#')[0]

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ''
            if cItem.get('type', '') in ('video', 'audio'):
                # the path only: lesson pages live on the language sub-domain
                url = self.pathOf(cItem.get('url', ''))
                return 'video:%s' % url if url else ''
            if cItem.get('category', '') in ('list_person', 'list_collection', 'list_album', 'list_series',
                                             'list_audio_series', 'list_surah'):
                # page 2+ (/page:N) keys like page 1
                path = re.sub(r'/page:\d+/?$', '', self.wfNormalizeUrlKey(self.pathOf(cItem.get('url', ''))))
                if path:
                    return 'folder:%s:%s' % (path, cItem.get('collection', ''))
        except Exception:
            printExc()
        return ''

    ###################################################
    # lists
    ###################################################
    def addNextPage(self, cItem, data):
        # /<list>/page:N, the pager is a sliding window without the last page
        hasNext = bool(self.cm.ph.getSearchGroups(data, r'''<a[^>]+href=["']([^"']+)["'][^>]*rel=["']next["']''')[0])
        try:
            page = max(1, int(cItem.get('page', 1) or 1))
        except (TypeError, ValueError):
            page = 1
        base = re.sub(r'/page:\d+/?$', '', cItem.get('url', '')).rstrip('/')
        addPagingItems(self, cItem, page, hasNext, 0, base.replace('{', '').replace('}', '') + '/page:{page}' if base else '')

    def listFilters(self, cItem):
        # "All" + countries of the reciter list
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        for url, title in re.findall(r'''<a href="(/quran(?:/[a-z0-9-]+)?)" class="filtre"[^>]*>([^<]+)</a>''', data):
            if '/page:' in url:
                continue
            params = dict(cItem)
            params.update({'page': 1, 'category': 'list_persons', 'title': self.cleanHtmlStr(title), 'url': self.fullUrl(url)})
            self.addDir(params)

    def listPersons(self, cItem):
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, 'portfolio-image">', '</a>', False):
            url = self.cm.ph.getSearchGroups(item, r'''href=["']([^"']+\.htm)["']''')[0]
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'''title=["']([^"']+)["']''')[0])
            if not url or not title:
                continue
            icon = self.fullUrl(self.cm.ph.getSearchGroups(item, r'''src=["']([^"']+)["']''')[0])
            params = stripPagerKeys(dict(cItem))
            params.update({'page': 1, 'good_for_fav': True, 'category': 'list_person', 'title': title, 'url': self.fullUrl(url),
                           'icon': icon, 'person': title})
            self.addDir(params)
        self.addNextPage(cItem, data)

    def listPerson(self, cItem):
        # a reciter shows its mus'haf collections, a munshid its albums,
        # a lecturer its video / audio lesson series
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        personId = self.cm.ph.getSearchGroups(data, r'''id_person\s*=\s*['"](\d+)['"]''')[0]
        collections = re.findall(r'''<li[^>]+data-collection=["'](\d+)["'][^>]*>\s*<a[^>]*>([^<]+)</a>''', data)
        tabs = re.findall(r'''<li[^>]*><a href=["']([^"']+/(?:album|series|series-audio))["']>([^<]+)</a>''', data)
        if personId and collections:
            for collection, title in collections:
                params = dict(cItem)
                params.update({'category': 'list_collection', 'title': self.cleanHtmlStr(title), 'person_id': personId,
                               'collection': collection, 'desc': cItem.get('person', '')})
                self.addDir(params)
        catMap = {'album': 'list_albums', 'series': 'list_series_index', 'series-audio': 'list_audio_index'}
        for url, title in tabs:
            params = dict(cItem)
            params.update({'category': catMap[url.rsplit('/', 1)[-1]], 'title': self.cleanHtmlStr(title), 'url': self.fullUrl(url)})
            self.addDir(params)

    def listCollection(self, cItem):
        url = self.MAIN_URL + 'ajax/loadplayer-%s-%s' % (cItem['person_id'], cItem['collection'])
        sts, data = self.getAjax(url, cItem['url'])
        if not sts:
            return
        try:
            recitations = json_loads(data).get('Recitation', [])
        except Exception:
            printExc()
            return
        person = cItem.get('person', '')
        for rec in recitations:
            recId = (rec.get('href') or '').lstrip('#')
            if not recId.isdigit():
                continue
            num = rec.get('sura_id', '')
            name = '%03d. %s' % (int(num), rec.get('span_name', '')) if str(num).isdigit() else rec.get('span_name', '')
            title = self.trackTitle(person, name)
            desc = [rec.get('stats-riwaya', '') or rec.get('data-riwaya', ''), rec.get('stats-verset', ''), rec.get('duration', '')]
            self.addAudio({'good_for_fav': True, 'title': title, 'url': self.LINK_BASE + 'getrcita-link-' + recId,
                           'icon': cItem.get('icon', ''), 'desc': '\n'.join(x for x in [person] + desc if x)})

    def trackTitle(self, person, name):
        # with name normalisation on the person leads the title, so downloaded
        # files of different reciters / munshids do not share one name
        name = name.strip()
        if IsMediaNamingNormalized() and person and person.lower() not in name.lower():
            return '%s - %s' % (person, name)
        return name

    def parseTracks(self, data, cItem, person=''):
        # the <a class="link-media"> rows used by surah / top / album / adhan / audio lesson pages
        seen = set()
        for tag, inner in re.findall(r'''(<a[^>]+class=["']link-media[^"']*["'][^>]*>)(.*?)</a>''', data, re.S):
            href = self.cm.ph.getSearchGroups(tag, r'''href=["']([^"']+)["']''')[0]
            label = self.cleanHtmlStr(inner)

            def attr(name, tag=tag):
                # values are always double-quoted and may contain apostrophes (Al Mu'allim)
                return self.cleanHtmlStr(self.cm.ph.getSearchGroups(tag, r'''\s%s\s*=\s*"([^"]*)"''' % name)[0])
            duration = attr('data-duration')
            if href.startswith('#') and href[1:].isdigit():
                if 'data-title' in tag:
                    url = self.LINK_BASE + 'getsnng-link-' + href[1:]
                    title = self.trackTitle(attr('data-person') or person, attr('data-title') or label)
                    secs = attr('data-lenght')
                    if secs.isdigit():
                        duration = '%d:%02d' % (int(secs) // 60, int(secs) % 60)
                else:
                    url = self.LINK_BASE + 'getrcita-link-' + href[1:]
                    reciter = attr('data-person') or attr('title') or person
                    surah = attr('data-recitation') or cItem.get('surah', '')
                    title = self.trackTitle(reciter, surah) if surah else reciter
            elif href.startswith('http'):
                url = href
                title = self.trackTitle(person, label)
            else:
                continue
            # surah pages list some recitations twice
            if not title or url in seen:
                continue
            seen.add(url)
            desc = '\n'.join(x for x in (attr('data-riwaya'), duration) if x)
            self.addAudio({'good_for_fav': True, 'title': title, 'url': url, 'icon': cItem.get('icon', ''), 'desc': desc})

    def listTracks(self, cItem):
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.parseTracks(data, cItem, cItem.get('person', ''))
        self.addNextPage(cItem, data)

    def listSurahs(self, cItem):
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, 'h2_sourat">', '</h2>', False):
            url = self.cm.ph.getSearchGroups(item, r'''href=["']([^"']+)["']''')[0]
            title = self.cleanHtmlStr(item)
            count = self.cm.ph.getSearchGroups(item, r'''data-recitation=["'](\d+)["']''')[0]
            if not url or not title:
                continue
            params = dict(cItem)
            params.update({'page': 1, 'good_for_fav': True, 'category': 'list_surah', 'title': title, 'url': self.fullUrl(url),
                           'surah': title, 'desc': _('%s recitations') % count if count else ''})
            self.addDir(params)

    def listAlbums(self, cItem):
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="portfolio-item', '</p>', False):
            url = self.cm.ph.getSearchGroups(item, r'''href=["']([^"']+/album/[^"']+)["']''')[0]
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'''alt=["']([^"']+)["']''')[0])
            if not url:
                continue
            params = dict(cItem)
            params.update({'page': 1, 'good_for_fav': True, 'category': 'list_album', 'title': title or url.rsplit('/', 1)[-1],
                           'url': self.fullUrl(url), 'icon': self.fullUrl(self.cm.ph.getSearchGroups(item, r'''src=["']([^"']+)["']''')[0]) or cItem.get('icon', '')})
            self.addDir(params)

    def listSeriesIndex(self, cItem):
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="portfolio-item', '</p>', False):
            url = self.cm.ph.getSearchGroups(item, r'''href=["']([^"']+/series/[^"']+)["']''')[0]
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'''itemprop=["']name["'] content=["']([^"']+)["']''')[0])
            if not url or not title:
                continue
            params = stripPagerKeys(dict(cItem))
            params.update({'page': 1, 'good_for_fav': True, 'category': 'list_series', 'title': title, 'url': self.fullUrl(url), 'series': title,
                           'icon': self.fullUrl(self.cm.ph.getSearchGroups(item, r'''src=["']([^"']+)["']''')[0]) or cItem.get('icon', '')})
            self.addDir(params)
        self.addNextPage(cItem, data)

    def listSeries(self, cItem):
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        series = cItem.get('series', '')
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, 'entry clearfix', '</h2>', False):
            url = self.cm.ph.getSearchGroups(item, r'''href=["']([^"']+\.htm)["']''')[0]
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'''<h2>(.*?)$''')[0])
            if not url or not title:
                continue
            if IsMediaNamingNormalized() and series:
                title = '%s - %s' % (series, title)
            self.addVideo({'good_for_fav': True, 'title': title, 'url': self.fullUrl(url), 'icon': cItem.get('icon', ''),
                           'desc': cItem.get('person', '')})
        self.addNextPage(cItem, data)

    def listAudioIndex(self, cItem):
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        for row in self.cm.ph.getAllItemsBeetwenMarkers(data, '<tr>', '</tr>', False):
            url = self.cm.ph.getSearchGroups(row, r'''href=["']([^"']+/series-audio/[^"']+)["']''')[0]
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.S)
            if not url or not cells:
                continue
            params = stripPagerKeys(dict(cItem))
            params.update({'page': 1, 'good_for_fav': True, 'category': 'list_audio_series', 'title': self.cleanHtmlStr(cells[0]),
                           'url': self.fullUrl(url), 'desc': self.cleanHtmlStr(cells[1]) if len(cells) > 1 else ''})
            self.addDir(params)
        self.addNextPage(cItem, data)

    def listSearch(self, cItem, searchPattern, searchType):
        url = self.MAIN_URL + 'searches/search?search=' + urllib_quote_plus(searchPattern)
        sts, data = self.getPage(url)
        if not sts:
            return
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="search-h3"', '</h3>', False):
            url = self.cm.ph.getSearchGroups(item, r'''href=["']([^"']+\.htm)["']''')[0]
            title = self.cleanHtmlStr(item)
            if url and title:
                params = dict(cItem)
                params.update({'good_for_fav': True, 'name': 'category', 'category': 'list_person', 'title': title,
                               'url': self.fullUrl(url), 'person': title})
                self.addDir(params)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG('Assabile.getLinksForVideo [%s]' % cItem['url'])
        url = cItem['url']
        if '/ajax/get' in url:
            sts, data = self.getAjax(url.replace('https://www.assabile.com/', self.MAIN_URL))
            url = data.strip() if sts else ''
            if not url.startswith('http'):
                return []
        elif url.endswith('.htm'):
            sts, data = self.getPage(url)
            if not sts:
                return []
            url = self.cm.ph.getSearchGroups(data, r'''<source[^>]+src=["']([^"']+)["']''')[0] or \
                self.cm.ph.getSearchGroups(data, r'''file:\s*["']([^"']+)["']''')[0]
            if not url:
                return []
        url = strwithmeta(self.fullUrl(url), {'User-Agent': self.HEADER['User-Agent'], 'Referer': self.MAIN_URL})
        urlTab = [{'name': 'Assabile', 'url': url, 'need_resolve': 0}]
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def getArticleContent(self, cItem):
        return [{'title': cItem.get('title', ''), 'text': cItem.get('desc', ''),
                 'images': [{'title': '', 'url': cItem.get('icon') or self.DEFAULT_ICON_URL}], 'other_info': {}}]

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('Assabile.handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get('name', None)
        category = self.currItem.get('category', '')
        searchPattern = self.currItem.get('search_pattern', searchPattern)
        self.currList = []

        if name is None:
            tab = [{'category': 'list_filters', 'title': _('Reciters'), 'url': self.MAIN_URL + 'quran'},
                   {'category': 'list_surahs', 'title': _('Surahs'), 'url': self.MAIN_URL + 'quran/suwar'},
                   {'category': 'list_tracks', 'title': _('Most listened recitations'), 'url': self.MAIN_URL + 'quran/top'},
                   {'category': 'list_persons', 'title': _('Munshids'), 'url': self.MAIN_URL + 'anasheed'},
                   {'category': 'list_tracks', 'title': _('Most listened anasheed'), 'url': self.MAIN_URL + 'anasheed/top'},
                   {'category': 'list_tracks', 'title': _('Adhan'), 'url': self.MAIN_URL + 'adhan-call-prayer'},
                   {'category': 'list_persons', 'title': _('Lecturers'), 'url': self.MAIN_URL + 'lesson'}]
            self.listsTab(tab + self.searchItems(), {'name': 'category'})
        elif category == 'list_filters':
            self.listFilters(self.currItem)
        elif category == 'list_persons':
            self.listPersons(self.currItem)
        elif category == 'list_person':
            self.listPerson(self.currItem)
        elif category == 'list_collection':
            self.listCollection(self.currItem)
        elif category in ('list_tracks', 'list_surah', 'list_album', 'list_audio_series'):
            self.listTracks(self.currItem)
        elif category == 'list_surahs':
            self.listSurahs(self.currItem)
        elif category == 'list_albums':
            self.listAlbums(self.currItem)
        elif category == 'list_series_index':
            self.listSeriesIndex(self.currItem)
        elif category == 'list_series':
            self.listSeries(self.currItem)
        elif category == 'list_audio_index':
            self.listAudioIndex(self.currItem)
        elif category in ('search', 'search_next_page'):
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category'})
            self.listSearch(cItem, searchPattern, searchType)
        elif category == 'search_history':
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc')
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Assabile(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('assabile')

    def withArticleContent(self, cItem):
        return cItem.get('type', '') in ('audio', 'video') and len(cItem.get('desc', '')) > 20
