# -*- coding: utf-8 -*-
# Last Modified: 10.10.2026
# Assabile (assabile.com) - Quran recitations, anasheed, adhan and Islamic lessons.
# Site languages are sub-domains (www = English, ar, fr, es, tr), same markup, localised slugs.
#   person lists:  /quran (?pays=<country> / ?riwaya=<riwaya>), /anasheed, /lessons (+ /<list>/<country>),
#                  <... class="person"> cards, pager ?page=N that always shows the last page
#   person page:   /<person> (also /<person>/anasheed, /<person>/lessons): <nav class="mushafs"> links,
#                  album / series cards (<a class="person" href="/<person>/anasheed|lessons/<x>">),
#                  "All anasheed" / "All series" links, videos -> /<person>/videos
#   surahs:        /quran/suwar -> /quran/suwar/<surah>/mp3 (all reciters), riwaya chips /quran/suwar/<surah>/<riwaya>
#   tracks:        <li data-track='{json}'> with the direct mp3 in "src"; ids: 123 recitation, s123 nasheed,
#                  a123 adhan, l123 audio lesson; /download/<recitation id> redirects to the zip next to the mp3
#   video lessons: <ol class="episodes"> -> episode page <video src="...mp4">
# 03.10.2026 - new host: reciters, surahs, anasheed, adhan, lessons, search, watched flag,
#   favourites, First page / Jump / Next page, sidecar, name normalisation "Person - Track"
# 10.10.2026 - site redesign: new list / person / surah / search parsers, mp3 from the data-track json,
#   reciter filters by country and riwaya, last page from the pager, video recitations
# 10.10.2026 - review: surah favourites follow the redirect to the new surah page, a message for links that are
#   gone (nasheed favourites from before the redesign) and for a search without hits
import re
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetDefaultLang
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
from Components.config import config, ConfigSelection, getConfigListEntry

config.plugins.iptvplayer.assabile_lang = ConfigSelection(default='auto', choices=[
    ('auto', _('Auto')), ('www', 'English'), ('ar', 'العربية'), ('fr', 'Français'), ('es', 'Español'), ('tr', 'Türkçe')])


def GetConfigList():
    return [getConfigListEntry(_('Language:'), config.plugins.iptvplayer.assabile_lang)]


def gettytul():
    return 'https://www.assabile.com/'


class Assabile(GenericFolderWatchedScraperMixin, CBaseHostClass):

    # recitations and anasheed keep their pre-redesign www identity, so watched /
    # downloaded marks survive the redesign and a language switch; the mp3 itself
    # travels in 'stream'
    LINK_BASE = 'https://www.assabile.com/ajax/'
    # /<person>, /<person>/anasheed, /<person>/lessons
    PERSON_RE = re.compile(r'^/[^/?#]+(?:/(?:anasheed|lessons))?/?$')

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

    @staticmethod
    def grab(data, pattern):
        match = re.search(pattern, data or '', re.S)
        return (match.group(1) or '') if match else ''

    def text(self, html):
        # the flag emojis (aria-hidden) do not render on the box
        return self.cleanHtmlStr(re.sub(r'<span aria-hidden="true">.*?</span>', '', html or '', flags=re.S))

    @staticmethod
    def duration(secs):
        try:
            secs = int(secs)
        except (TypeError, ValueError):
            return ''
        if secs <= 0:
            return ''
        if secs >= 3600:
            return '%d:%02d:%02d' % (secs // 3600, secs % 3600 // 60, secs % 60)
        return '%d:%02d' % (secs // 60, secs % 60)

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
                                             'list_audio_series', 'list_surah', 'list_videos'):
                # page 2+ (?page=N, old /page:N) keys like page 1
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
        # ?page=N, the pager shows the first and the last page around a sliding window
        pager = self.grab(data, r'<nav class="pager"[^>]*>(.*?)</nav>')
        if not pager:
            return
        try:
            page = max(1, int(cItem.get('page', 1) or 1))
        except (TypeError, ValueError):
            page = 1
        pages = [int(x) for x in re.findall(r'>\s*(\d+)\s*<', pager)]
        lastPage = max(pages) if pages else 0
        base = re.sub(r'([?&])page=\d+&?', r'\1', cItem.get('url', '')).rstrip('?&').replace('{', '').replace('}', '')
        tpl = base + ('&' if '?' in base else '?') + 'page={page}' if base else ''
        addPagingItems(self, cItem, page, lastPage > page, lastPage, tpl)

    def listFilters(self, cItem):
        # "All" + the country / riwaya drop-downs of the reciter list
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        params = dict(cItem)
        params.update({'page': 1, 'category': 'list_persons', 'title': _('All')})
        self.addDir(params)
        for name in ('pays', 'riwaya'):
            select = re.search(r'''<select[^>]+id=["']([^"']+)["'][^>]+name=["']%s["'].*?</select>''' % name, data, re.S)
            if not select:
                continue
            options = [(value, self.text(title)) for value, title in re.findall(r'''<option value=["']([^"']+)["'][^>]*>(.*?)</option>''', select.group(0), re.S)]
            if not options:
                continue
            # the site's own (localised) label: "Filter by country", "Filter by riwaya"
            label = self.text(self.grab(data, r'''<label[^>]+for=["']%s["'][^>]*>(.*?)</label>''' % re.escape(select.group(1))))
            params = dict(cItem)
            params.update({'category': 'list_filter_options', 'title': label or name, 'filter': name, 'options': options})
            self.addDir(params)

    def listFilterOptions(self, cItem):
        base = cItem['url'].split('?')[0]
        for value, title in cItem.get('options', []):
            params = dict(cItem)
            params.pop('options', None)
            params.update({'page': 1, 'category': 'list_persons', 'title': title,
                           'url': '%s?%s=%s' % (base, cItem.get('filter', ''), urllib_quote_plus(value))})
            self.addDir(params)

    def parsePersons(self, cItem, data):
        # <div class="person"> (reciter lists) and <a class="person"> (anasheed, lessons, search)
        seen = set()
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="person"', '</li>'):
            url = self.grab(item, r'''href=["'](/[^"'#?]+)["']''')
            if not url or not self.PERSON_RE.match(url) or url in seen:
                continue
            title = self.text(self.grab(item, r'<b>(.*?)</b>'))
            if not title:
                continue
            seen.add(url)
            params = stripPagerKeys(dict(cItem))
            params.update({'page': 1, 'good_for_fav': True, 'category': 'list_person', 'title': title, 'url': self.fullUrl(url),
                           'icon': self.fullUrl(self.grab(item, r'''<img[^>]+src=["']([^"']+)["']''')), 'person': title,
                           'desc': self.text(self.grab(item, r'<small>(.*?)</small>'))})
            self.addDir(params)

    def listPersons(self, cItem):
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        if re.match(r'^/(?:anasheed|lessons)/?$', self.pathOf(cItem['url'])):
            # munshids / preachers by country
            for url, title in re.findall(r'''<a class="chip" href=["'](/(?:anasheed|lessons)/[^"'/?]+)["'][^>]*>(.*?)</a>''', data, re.S):
                params = stripPagerKeys(dict(cItem))
                params.update({'page': 1, 'category': 'list_persons', 'title': self.text(title), 'url': self.fullUrl(url)})
                self.addDir(params)
        self.parsePersons(cItem, data)
        self.addNextPage(cItem, data)

    def listPerson(self, cItem):
        # a reciter shows its mushafs (+ anasheed, lessons, videos), a munshid its
        # albums and anasheed, a preacher its lesson series
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        # old favourites (/<name>-<id>/<name>.htm) are redirected to the new page
        path = self.pathOf(self.cm.meta.get('url', '') or cItem['url']).rstrip('/')
        slug = path.strip('/').split('/')[0]
        person = cItem.get('person', '') or self.text(self.grab(data, r'<h1[^>]*>(.*?)</h1>'))
        base = stripPagerKeys(dict(cItem))
        base.update({'page': 1, 'good_for_fav': True, 'person': person})
        for key in ('person_id', 'collection', 'series', 'album', 'surah'):
            base.pop(key, None)
        seen = set()

        nav = self.grab(data, r'<nav class="mushafs"[^>]*>(.*?)</nav>')
        for url, title, info in re.findall(r'''<a href=["']([^"']+)["'][^>]*>\s*<b>(.*?)</b>\s*(?:<small>(.*?)</small>)?''', nav, re.S):
            title, info = self.text(title), self.text(info)
            seen.add(url)
            params = dict(base)
            params.update({'category': 'list_collection', 'title': '%s (%s)' % (title, info) if info else title,
                           'url': self.fullUrl(url), 'desc': '\n'.join(x for x in (person, info) if x)})
            self.addDir(params)
        # "With translation: English, ...", "Recitations with several reciters: ..."
        for sub in re.findall(r'<p class="sub"[^>]*>(.*?)</p>', data, re.S):
            if '/moshaf/' not in sub:
                continue
            lead = self.text(sub.split('<a', 1)[0]).rstrip(': ')
            for url, title in re.findall(r'''<a class="more" href=["']([^"']+/moshaf/[^"']+)["'][^>]*>(.*?)</a>''', sub, re.S):
                if url in seen:
                    continue
                seen.add(url)
                title = self.text(title)
                params = dict(base)
                params.update({'category': 'list_collection', 'title': '%s: %s' % (lead, title) if lead else title,
                               'url': self.fullUrl(url), 'desc': person})
                self.addDir(params)

        # "All anasheed (68)" / "All series (18)" on a reciter page lead to the complete lists
        moreKinds = set()
        for url, kind, title in re.findall(r'''<a class="more" href=["'](/%s/(anasheed|lessons))["'][^>]*>(.*?)</a>''' % re.escape(slug), data, re.S):
            if url == path:
                continue
            moreKinds.add(kind)
            params = dict(base)
            params.update({'category': 'list_person', 'title': self.text(title), 'url': self.fullUrl(url)})
            self.addDir(params)
        for url, kind, inner in re.findall(r'''<a class="person" href=["'](/%s/(anasheed|lessons)/[^"'/?#]+)["'][^>]*>(.*?)</a>''' % re.escape(slug), data, re.S):
            title = self.text(self.grab(inner, r'<b>(.*?)</b>'))
            if kind in moreKinds or url in seen or not title:
                continue
            seen.add(url)
            info = self.text(self.grab(inner, r'<small>(.*?)</small>'))
            params = dict(base)
            params.update({'category': 'list_album' if kind == 'anasheed' else 'list_series', 'title': title, 'url': self.fullUrl(url),
                           'icon': self.fullUrl(self.grab(inner, r'''<img[^>]+src=["']([^"']+)["']''')) or cItem.get('icon', ''),
                           'desc': '\n'.join(x for x in (person, info) if x), 'album' if kind == 'anasheed' else 'series': title})
            self.addDir(params)

        if 'class="vgrid"' in data and slug and not path.endswith('/videos'):
            params = dict(base)
            params.update({'category': 'list_videos', 'title': _('Video recitations'), 'url': self.fullUrl('/%s/videos' % slug)})
            self.addDir(params)

        if not nav:
            # a single mushaf, a munshid's anasheed
            self.parseTracks(data, cItem, person)

    def trackTitle(self, person, name):
        # with name normalisation on the person leads the title, so downloaded
        # files of different reciters / munshids do not share one name
        name = name.strip()
        if IsMediaNamingNormalized() and person and person.lower() not in name.lower():
            return '%s - %s' % (person, name)
        return name

    def parseTracks(self, data, cItem, person=''):
        # <li data-track='{"id":..,"src":"..mp3","title":..,"subtitle":"Person, riwaya / album",..}'>
        numbered = cItem.get('category', '') == 'list_collection'
        tracks = []
        seen = set()
        for raw, num in re.findall(r'''data-track='([^']+)'[^>]*>\s*(?:<span class="n">(\d+)</span>)?''', data):
            try:
                track = json_loads(raw)
            except Exception:
                printExc()
                continue
            trackId = ensure_str('%s' % track.get('id', ''))
            src = ensure_str(track.get('src') or '')
            # surah / best-voices pages repeat some tracks
            if not trackId or not src or trackId in seen:
                continue
            seen.add(trackId)
            who, sep, extra = self.text(ensure_str(track.get('subtitle') or '')).partition(', ')
            if who == '0':
                # some adhans carry "0" instead of an empty muezzin
                who = ''
            name = self.text(ensure_str(track.get('title') or ''))
            if numbered and num:
                name = '%03d. %s' % (int(num), name)
            elif trackId[:1] == 'l' and extra and IsMediaNamingNormalized():
                # audio lesson: "Episode 01" alone says nothing, the series leads
                name = '%s - %s' % (extra, name)
            tracks.append((trackId, src, name, who or person, extra, track))
        # lists of several reciters (surah, best voices, adhan) always name the person
        mixed = len(set(t[3] for t in tracks)) > 1
        for trackId, src, name, who, extra, track in tracks:
            if trackId.isdigit():
                url = self.LINK_BASE + 'getrcita-link-' + trackId
            elif trackId[:1] == 's' and trackId[1:].isdigit():
                url = self.LINK_BASE + 'getsnng-link-' + trackId[1:]
            else:
                url = src
            if mixed and who and who.lower() not in name.lower():
                title = '%s - %s' % (who, name)
            else:
                title = self.trackTitle(who, name)
            desc = '\n'.join(x for x in (who, extra, self.duration(track.get('duration'))) if x)
            self.addAudio({'good_for_fav': True, 'title': title, 'url': url, 'stream': src, 'desc': desc,
                           'icon': self.fullUrl(ensure_str(track.get('cover') or '')) or cItem.get('icon', '')})
        return len(tracks)

    def parseVideos(self, data, cItem):
        # video lesson episodes and a person's video recitations
        person = cItem.get('person', '')
        series = cItem.get('series', '')
        items = []
        for item in self.cm.ph.getAllItemsBeetwenMarkers(self.grab(data, r'<ol class="episodes"[^>]*>(.*?)</ol>'), '<li', '</li>'):
            items.append((item, self.grab(item, r'<small>(.*?)</small>'), series))
        for item in self.cm.ph.getAllItemsBeetwenMarkers(self.grab(data, r'<ul class="vgrid"[^>]*>(.*?)</ul>'), '<li', '</li>'):
            items.append((item, self.grab(item, r'<time[^>]*>(.*?)</time>'), ''))
        for item, duration, prefix in items:
            url = self.grab(item, r'''<a[^>]+href=["']([^"']+)["']''')
            title = self.text(self.grab(item, r'<b>(.*?)</b>'))
            if not url or not title:
                continue
            if prefix and IsMediaNamingNormalized():
                title = '%s - %s' % (prefix, title)
            elif not prefix:
                title = self.trackTitle(person, title)
            self.addVideo({'good_for_fav': True, 'title': title, 'url': self.fullUrl(url),
                           'icon': self.fullUrl(self.grab(item, r'''<img[^>]+src=["']([^"']+)["']''')) or cItem.get('icon', ''),
                           'desc': '\n'.join(x for x in (person, self.text(duration)) if x)})

    def listTracks(self, cItem):
        url = cItem['url']
        if cItem.get('person_id') and cItem.get('collection'):
            # favourite of a pre-redesign collection: the old player url redirects to the mushaf
            url = self.MAIN_URL + 'ajax/loadplayer-%s-%s' % (cItem['person_id'], cItem['collection'])
        sts, data = self.getPage(url)
        if not sts:
            return
        if not self.parseTracks(data, cItem, cItem.get('person', '')):
            self.parseVideos(data, cItem)
        self.addNextPage(cItem, data)

    def parseSurahs(self, cItem, data):
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, '<a class="sura"', '</a>'):
            url = self.grab(item, r'''href=["']([^"']+)["']''')
            name = self.text(self.grab(item, r'<b>(.*?)</b>'))
            if not url or not name:
                continue
            num = self.text(self.grab(item, r'<span class="n">(.*?)</span>'))
            desc = '\n'.join(x for x in (self.text(self.grab(item, r'<small>(.*?)</small>')),
                                         self.text(self.grab(item, r'<span class="ar"[^>]*>(.*?)</span>'))) if x)
            params = stripPagerKeys(dict(cItem))
            params.update({'page': 1, 'good_for_fav': True, 'category': 'list_surah', 'title': '%s. %s' % (num, name) if num else name,
                           'url': self.fullUrl(url), 'surah': name, 'desc': desc})
            self.addDir(params)

    def listSurahs(self, cItem):
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.parseSurahs(cItem, data)

    def listSurah(self, cItem):
        # surah page: riwaya chips + the first reciters, /mp3 lists all of them
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        # the url after redirects (a favourite from before the redesign lands on the new surah page)
        path = self.pathOf(self.cm.meta.get('url', '') or cItem['url'])
        if re.match(r'^/quran/suwar/[^/]+/?$', path):
            for chipUrl, title in re.findall(r'''<a class="chip" href=["'](/quran/suwar/[^"'/]+/[^"'/?#]+)["'][^>]*>(.*?)</a>''', data, re.S):
                params = dict(cItem)
                params.update({'title': self.text(title), 'url': self.fullUrl(chipUrl), 'desc': cItem.get('surah', '')})
                self.addDir(params)
            sts, data = self.getPage(self.fullUrl(path.rstrip('/') + '/mp3'))
            if not sts:
                return
        self.parseTracks(data, cItem)

    def listSearch(self, cItem, searchPattern, searchType):
        url = self.MAIN_URL + 'search?q=' + urllib_quote_plus(searchPattern)
        sts, data = self.getPage(url)
        if not sts:
            return
        self.parsePersons(cItem, data)
        self.parseSurahs(cItem, data)
        if not self.currList:
            SetIPTVPlayerLastHostError(_('No results found for: %s') % searchPattern)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG('Assabile.getLinksForVideo [%s]' % cItem['url'])
        url = cItem['url']
        stream = cItem.get('stream', '')
        if not stream:
            if '/ajax/getrcita-link-' in url:
                # favourite from before the redesign: /download/<id> redirects to the zip next to the mp3
                params = dict(self.defaultParams)
                params['no_redirection'] = True
                self.getPage(self.MAIN_URL + 'download/' + url.rsplit('-', 1)[-1], params)
                location = self.cm.meta.get('location', '')
                if location.endswith('.zip') and '/zip/' in location:
                    stream = location.replace('/zip/', '/mp3/', 1)[:-4] + '.mp3'
            elif re.search(r'\.(?:mp3|mp4|m4a)(?:\?|$)', url):
                stream = url
            elif '/ajax/' not in url:
                # lesson episode / video recitation page
                sts, data = self.getPage(url)
                if sts:
                    stream = self.grab(data, r'''<video[^>]+src=["']([^"']+)["']''') or \
                        self.grab(data, r'''<source[^>]+src=["']([^"']+)["']''')
        if not stream:
            # e.g. a nasheed favourite from before the redesign: /ajax/getsnng-link-<id> is gone (410)
            SetIPTVPlayerLastHostError(_('Content not available'))
            return []
        stream = strwithmeta(self.fullUrl(stream), {'User-Agent': self.HEADER['User-Agent'], 'Referer': self.MAIN_URL})
        urlTab = [{'name': 'Assabile', 'url': stream, 'need_resolve': 0}]
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
                   {'category': 'list_tracks', 'title': _('Most listened recitations'), 'url': self.MAIN_URL + 'quran/best-voices'},
                   {'category': 'list_persons', 'title': _('Munshids'), 'url': self.MAIN_URL + 'anasheed'},
                   {'category': 'list_tracks', 'title': _('Most listened anasheed'), 'url': self.MAIN_URL + 'anasheed'},
                   {'category': 'list_tracks', 'title': _('Adhan'), 'url': self.MAIN_URL + 'adhan-call-prayer'},
                   {'category': 'list_persons', 'title': _('Lecturers'), 'url': self.MAIN_URL + 'lessons'}]
            self.listsTab(tab + self.searchItems(), {'name': 'category'})
        elif category == 'list_filters':
            self.listFilters(self.currItem)
        elif category == 'list_filter_options':
            self.listFilterOptions(self.currItem)
        elif category == 'list_persons':
            self.listPersons(self.currItem)
        elif category in ('list_person', 'list_albums', 'list_series_index', 'list_audio_index'):
            # list_albums / list_series_index / list_audio_index: favourites from before the redesign
            self.listPerson(self.currItem)
        elif category in ('list_collection', 'list_tracks', 'list_album', 'list_series', 'list_audio_series', 'list_videos'):
            self.listTracks(self.currItem)
        elif category == 'list_surahs':
            self.listSurahs(self.currItem)
        elif category == 'list_surah':
            self.listSurah(self.currItem)
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
