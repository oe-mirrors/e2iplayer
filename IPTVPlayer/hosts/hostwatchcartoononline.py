# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026
# 03.10.2026 - revived for the relaunched watchcartoononline.com
#   (new PHP site: /detail/<id> + /detail-dubbed/<id> series pages with the whole
#    episode list as inline "let playlist = [...]" JSON; /data-video/?v=<embed> gives
#    the own CDN tokens (SD/HD/FHD) -> <server>/getvid?evid=.. redirects to a media node;
#    A-Z lists, genre lists, /ajax/search.php JSON search; movies are premium-only)
#   + watched flag (episode key = series id + version + episode label, the same from the "Recently
#   added" cards and the series page) / sidecar / name normalisation / INFO (site + moviemeta) / favourites.
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
###################################################

###################################################
# FOREIGN import
###################################################
import re
###################################################


def GetConfigList():
    return []


def gettytul():
    return 'https://www.watchcartoononline.com/'


# "<show> [Season N] Episode M[ - ]<name>"
EPISODE_RE = re.compile(r'^(.*?)\s+(?:Season\s+(\d+)\s+)?Episode\s+(\d+(?:\.\d+)?)\b\s*(.*)$', re.I)
LANG_SUFFIX_RE = re.compile(r'\s*\(?\bEnglish\s+(?:Dubbed|Subbed|Sub|Dub)\b\)?\s*$', re.I)
CHUNK_SIZE = 100
PAGE_SIZE = 100  # series per page in the A-Z letter and genre lists


def _str(value):
    # json values as native str on py2 too (unicode -> utf-8; str() would fail on non-ASCII)
    value = ensure_str(value)
    return value if isinstance(value, str) else str(value)


class WatchCartoonOnline(GenericFolderWatchedScraperMixin, CBaseHostClass):
    # only what identifies a row and is needed to open it again; embed tokens, descriptions and
    # the watched parent key differ between the lists the same title comes from
    FAV_FIELDS = ('name', 'category', 'type', 'url', 'title', 's_id', 's_title', 'termid', 'ep_label', 'grp', 'chunk', 'version', 'icon', 'meta_type', 'meta_title', 'meta_year')

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'watchcartoononline.com', 'cookie': 'watchcartoononline.com.cookie'})
        self.HEADER = self.cm.getDefaultHeader()
        self.HEADER['Referer'] = gettytul()
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = gettytul() + 'assets/logo_.png'
        self.MENU = [{'category': 'home_section', 'title': _('Recently added'), 'section': 'recently-added'},
                     {'category': 'home_section', 'title': _('Latest anime episodes'), 'section': 'anime'},
                     {'category': 'home_section', 'title': _('Latest cartoon episodes'), 'section': 'cartoon'},
                     {'category': 'home_section', 'title': _('Popular series'), 'section': 'popular-series'},
                     {'category': 'list_abc', 'title': _('Anime A-Z'), 'url': self.getFullUrl('list/anime')},
                     {'category': 'list_abc', 'title': _('Cartoons A-Z'), 'url': self.getFullUrl('list/cartoon')},
                     {'category': 'list_genres', 'title': _('Anime genres'), 'url': self.getFullUrl('genre-list/anime/1')},
                     {'category': 'list_genres', 'title': _('Cartoon genres'), 'url': self.getFullUrl('genre-list/cartoon/1')}] + self.searchItems()
        self.indexCache = {}

        self.watchedHelper = IPTVWatchedHelper('watchcartoononline')
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ''
            category = cItem.get('category', '')
            if cItem.get('type', '') in ('video', 'audio'):
                return self._episodeWatchedKey(cItem)
            sid = str(cItem.get('s_id', '') or '').strip()
            if category == 'wco_series' and sid:
                return 'series:%s' % sid
            if category == 'wco_episodes' and sid:
                return 'list:%s|%s|%s|%s' % (sid, cItem.get('version', ''), cItem.get('grp', ''), cItem.get('chunk', ''))
            return ''
        except Exception:
            printExc()
        return ''

    def _episodeWatchedKey(self, cItem):
        # the "recently added" cards link /detail[-dubbed]/<series id>/<card id>, the series page lists the
        # same episode with its termid - both know the series id, the version and the episode label
        sid = str(cItem.get('s_id', '') or '').strip()
        label = cItem.get('ep_label', '')
        url = str(cItem.get('url', '') or '').strip()
        if sid and label:
            show, season, episode, dummy = self._parseLabel(label)
            ident = '%s|%s|%s' % (self._key(show), season, episode) if show else self._key(LANG_SUFFIX_RE.sub('', self._cleanLabel(label)))
            return 'episode:%s|%s|%s' % (sid, 'dub' if '/detail-dubbed/' in url else 'sub', ident)
        return 'video:%s' % url if url else ''

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams['cloudflare_params'] = {'cookie_file': self.COOKIE_FILE, 'User-Agent': self.HEADER.get('User-Agent')}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def getFavouriteData(self, cItem):
        try:
            if cItem.get('s_id') or cItem.get('termid'):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # helpers
    ###################################################
    def _seriesUrl(self, sid, dubbed=False):
        return '%s%s/%s' % (self.MAIN_URL, 'detail-dubbed' if dubbed else 'detail', sid)

    def _sidFromUrl(self, url):
        return self.cm.ph.getSearchGroups(url, r'/detail(?:-dubbed)?/(\d+)')[0]

    def _thumb(self, termid):
        return '%sthumb.php?termid=%s' % (self.MAIN_URL, termid) if termid else ''

    def _cleanLabel(self, label):
        label = label.replace("\\'", "'").replace('\\"', '"').replace('’', "'").replace('‘', "'")
        return self.cleanHtmlStr(label).strip()

    def _parseLabel(self, label):
        # -> (show, season, episode, episode name); show '' when the label has no "Episode N"
        label = self._cleanLabel(label)
        m = EPISODE_RE.match(label)
        if not m:
            return '', '', '', LANG_SUFFIX_RE.sub('', label).strip()
        show = m.group(1).strip().strip('"').strip()
        epName = LANG_SUFFIX_RE.sub('', m.group(4)).strip()
        epName = re.sub(r'^[\s:-]+', '', epName).strip()
        return show, m.group(2) or '1', m.group(3), epName

    def _formatEpisodeTitle(self, label):
        if not IsMediaNamingNormalized():
            return self._cleanLabel(label)
        show, season, episode, epName = self._parseLabel(label)
        if not show:
            return epName or self._cleanLabel(label)
        if '.' in episode:
            num, frac = episode.split('.', 1)
            tag = formatSxxExx(season, num) + '.' + frac
        else:
            tag = formatSxxExx(season, episode)
        if epName:
            return '%s - %s - %s' % (show, tag, epName)
        return '%s - %s' % (show, tag)

    @staticmethod
    def _key(text):
        return re.sub(r'[^a-z0-9]+', '', text.lower())

    def _parsePlaylist(self, data):
        # [[label, termid, embed, episode], ...] - the full episode list of this version of the series
        ret = []
        m = re.search(r'let\s+playlist\s*=\s*(\[.*?\])\s*;\s*\n', data, re.S)
        if m:
            try:
                for entry in json_loads(m.group(1)):
                    if isinstance(entry, list) and len(entry) >= 3 and _str(entry[1]).strip() and _str(entry[2]).strip():
                        ret.append({'label': _str(entry[0]), 'termid': _str(entry[1]).strip(), 'embed': _str(entry[2]).strip()})
            except Exception:
                printExc()
        if not ret:
            for label, termid, embed in re.findall(r"changeVideo\('((?:[^'\\]|\\.)*)'\s*,\s*'(\d+)'\s*,\s*'((?:[^'\\]|\\.)+)'", data):
                ret.append({'label': label, 'termid': termid, 'embed': embed.replace("\\'", "'")})
        seen = set()
        uniq = []
        for item in ret:
            if item['termid'] in seen:
                continue
            seen.add(item['termid'])
            uniq.append(item)
        return uniq

    def _infoField(self, data, label):
        # raw text of "<span class="text-orange">Label:</span> value" up to the next list entry
        # (?s): Studio and Genre spread their values over several lines
        raw = self.cm.ph.getSearchGroups(data, r'(?s)<span class="text-orange">\s*%s:?\s*</span>(.*?)(?:</li>|<li)' % re.escape(label), 1, True)[0]
        raw = re.sub(r'<[^>]+>', '  ', raw)
        return [self.cleanHtmlStr(x) for x in re.split(r'\s{2,}', raw) if self.cleanHtmlStr(x)]

    def _parseSeriesInfo(self, data):
        info = {}
        info['title'] = self._cleanLabel(self.cm.ph.getDataBeetwenNodes(data, ('<h1', '>'), ('</h1', '>'), False)[1])
        desc = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'class="desc"'), ('</p', '>'), False)[1]
        info['desc'] = self.cleanHtmlStr(desc.split('<p', 1)[-1].split('>', 1)[-1]) if '<p' in desc else ''
        for label, key in (('Type', 'type'), ('Studio', 'production'), ('Publish Date', 'released'), ('Status', 'status'),
                           ('Genre', 'genres'), ('Scores', 'rating'), ('Duration', 'duration')):
            val = ', '.join(self._infoField(data, label))
            if val:
                info[key] = val
        info['year'] = self.cm.ph.getSearchGroups(info.get('released', ''), r'((?:19|20)\d\d)')[0]
        versions = []
        for href, label in re.findall(r'<a href="(/detail(?:-dubbed)?/\d+)"\s+class="translator[^"]*">\s*([^<]*?)\s*<', data):
            if href not in [v[0] for v in versions]:
                versions.append((href, label.strip()))
        info['versions'] = versions
        return info

    ###################################################
    # lists
    ###################################################
    def listHomeSection(self, cItem):
        printDBG('WatchCartoonOnline.listHomeSection [%s]' % cItem.get('section'))
        sts, data = self.getPage(self.MAIN_URL)
        if not sts:
            return
        section = cItem.get('section', '')
        data = self.cm.ph.getDataBeetwenNodes(data, ('<h2', '>', 'id="title-%s"' % section), ('<h2', '>'), False)[1]
        if section == 'popular-series':
            for item in self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'popular-card'), ('<div', '>', 'badge-list')):
                url = self.cm.ph.getSearchGroups(item, r'''href=['"]([^'"]*?/detail/\d+)['"]''')[0]
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<a', '>', 'serie-title'), ('</a', '>'), False)[1])
                self._addSeries(cItem, self._sidFromUrl(url), title)
            return
        for item in self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'serie-card'), ('<div', '>', 'category')):
            url = self.cm.ph.getSearchGroups(item, r'''<a href=['"]([^'"]*?/detail(?:-dubbed)?/\d+(?:/\d+)?)['"][^>]*serie-title''')[0]
            label = self.cm.ph.getDataBeetwenNodes(item, ('<a', '>', 'serie-title'), ('</a', '>'), False)[1]
            sid = self._sidFromUrl(url)
            if not sid or not label:
                continue
            label = self._cleanLabel(label)
            show = self._parseLabel(label)[0]
            params = {'good_for_fav': True, 'name': 'category', 'category': 'wco_episode', 'title': self._formatEpisodeTitle(label), 'ep_label': label,
                      'url': self.getFullUrl(url), 's_id': sid, 's_title': show, 'icon': '', 'desc': label,
                      'meta_type': 'tv', 'meta_title': show}
            self.addVideo(params)

    def _addSeries(self, cItem, sid, title, desc='', year=''):
        if not sid or not title:
            return
        title = self._cleanLabel(title)
        params = {'good_for_fav': True, 'name': 'category', 'category': 'wco_series', 'title': title, 's_title': title, 's_id': sid,
                  'url': self._seriesUrl(sid), 'icon': '', 'desc': desc, 'meta_type': 'tv', 'meta_title': title, 'meta_year': year}
        self.addDir(params)

    def _getSeriesIndex(self, url):
        # all {id, title} of a /list/<type> or genre page (deduplicated, site order); the A-Z pages
        # are ~1.5 MB, so the last one stays in memory for the letter sub-lists
        if url in self.indexCache:
            return self.indexCache[url]
        ret = []
        sts, data = self.getPage(url)
        if not sts:
            return ret
        seen = set()
        for sid, title in re.findall(r'data-id="(\d+)"[^>]*class="ajax-tippy"[^>]*>([^<]+)<', data):
            title = self._cleanLabel(title)
            if sid in seen or not title:
                continue
            seen.add(sid)
            ret.append({'id': sid, 'title': title})
        if ret:
            self.indexCache = {url: ret}
        return ret

    @staticmethod
    def _letter(title):
        letter = title[:1].upper()
        if not ('A' <= letter <= 'Z'):
            letter = '#'
        return letter

    def listABC(self, cItem):
        printDBG('WatchCartoonOnline.listABC')
        letters = {}
        for item in self._getSeriesIndex(cItem['url']):
            letter = self._letter(item['title'])
            letters[letter] = letters.get(letter, 0) + 1
        for letter in sorted(letters.keys(), key=lambda x: (x != '#', x)):
            params = stripPagerKeys(dict(cItem))
            params.update({'good_for_fav': False, 'category': 'list_letter', 'title': '%s (%d)' % (letter, letters[letter]), 'letter': letter})
            self.addDir(params)

    def _listSeriesPaged(self, cItem, items):
        # the site has no paging (A-Z and genre pages hold the whole list), the cached index is paged here;
        # the folder url stays the same ("Jump" template without "{page}")
        page = max(1, int(cItem.get('page', 1) or 1))
        items = sorted(items, key=lambda x: x['title'].lower())
        start = (page - 1) * PAGE_SIZE
        for item in items[start:start + PAGE_SIZE]:
            self._addSeries(cItem, item['id'], item['title'])
        lastPage = (len(items) + PAGE_SIZE - 1) // PAGE_SIZE
        addPagingItems(self, cItem, page, page < lastPage, lastPage, cItem.get('url', '').replace('{', '%7B').replace('}', '%7D'))

    def listLetter(self, cItem):
        printDBG('WatchCartoonOnline.listLetter [%s]' % cItem.get('letter'))
        wanted = cItem.get('letter', '')
        self._listSeriesPaged(cItem, [item for item in self._getSeriesIndex(cItem['url']) if self._letter(item['title']) == wanted])

    def listGenres(self, cItem):
        printDBG('WatchCartoonOnline.listGenres')
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        for url, title in re.findall(r'<a href="(/genre-list/[a-z]+/\d+)"\s+class="genre-list-element[^"]*">\s*([^<]+?)\s*</a>', data):
            params = stripPagerKeys(dict(cItem))
            params.update({'good_for_fav': True, 'category': 'list_genre', 'title': self.cleanHtmlStr(title), 'url': self.getFullUrl(url)})
            self.addDir(params)

    def listGenre(self, cItem):
        printDBG('WatchCartoonOnline.listGenre [%s]' % cItem['url'])
        items = self._getSeriesIndex(cItem['url'])
        if len(items) > 300:
            # the big genres hold thousands of titles - split them A-Z like the full lists
            self.listABC(cItem)
            return
        self._listSeriesPaged(cItem, items)

    def listSeries(self, cItem):
        printDBG('WatchCartoonOnline.listSeries [%s]' % cItem['url'])
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        info = self._parseSeriesInfo(data)
        title = cItem.get('s_title') or info['title']
        sid = cItem.get('s_id') or self._sidFromUrl(cItem['url'])
        if cItem.get('category') == 'wco_series' and len(info['versions']) > 1:
            for href, label in info['versions']:
                dubbed = 'dubbed' in href
                vTitle = _('English dubbed') if dubbed else (_('English subbed') if label.upper() == 'SUB' else label)
                params = dict(cItem)
                params.update({'good_for_fav': True, 'category': 'wco_episodes', 'title': '%s - %s' % (title, vTitle), 's_title': title, 's_id': sid,
                               'url': self._seriesUrl(sid, dubbed), 'version': 'dub' if dubbed else 'sub', 'desc': info.get('desc', ''),
                               'meta_year': info.get('year', '')})
                self.addDir(params)
            return
        self._listEpisodes(cItem, data, info)

    def _listEpisodes(self, cItem, data, info):
        title = cItem.get('s_title') or info['title']
        sid = cItem.get('s_id') or self._sidFromUrl(cItem['url'])
        dubbed = '/detail-dubbed/' in cItem['url'] or (len(info['versions']) == 1 and 'dubbed' in info['versions'][0][0])
        playlist = self._parsePlaylist(data)
        if not playlist:
            if 'onlyforPremium' in data:
                SetIPTVPlayerLastHostError(_('This video is Premium-only content.'))
            return

        # group the episodes by "<show> / season" - one page can hold several shows (specials, spin-offs)
        groups = {}
        groupOrder = []
        mainKey = self._key(title)
        for idx, entry in enumerate(playlist):
            show, season, episode, epName = self._parseLabel(entry['label'])
            gkey = '%s|%s' % (self._key(show), season) if show else 'other|'
            entry.update({'show': show, 'season': season, 'episode': episode, 'idx': idx})
            if gkey not in groups:
                groups[gkey] = []
                groupOrder.append(gkey)
            groups[gkey].append(entry)
        # other shows in site order, every show's seasons in number order
        showFirst = {}
        for gkey in groupOrder:
            showFirst.setdefault(gkey.split('|', 1)[0], len(showFirst))

        def _sortGroup(gkey):
            showKey, season = gkey.split('|', 1)
            return (gkey == 'other|', showKey != mainKey, showFirst[showKey], int(season or 0))
        groupOrder.sort(key=_sortGroup)

        wanted = cItem.get('grp', '')
        desc = info.get('desc', '') or cItem.get('desc', '')
        if not wanted and len(groupOrder) > 1:
            showSeasons = {}
            for gkey in groupOrder:
                showSeasons.setdefault(gkey.split('|', 1)[0], []).append(gkey)
            for gkey in groupOrder:
                entries = groups[gkey]
                showKey, season = gkey.split('|', 1)
                if gkey == 'other|':
                    gTitle = _('Specials')
                else:
                    gTitle = entries[0]['show']
                    if len(showSeasons[showKey]) > 1 or season != '1':
                        gTitle = '%s - %s %s' % (gTitle, _('Season'), season)
                params = dict(cItem)
                params.update({'good_for_fav': True, 'category': 'wco_episodes', 'title': '%s (%d)' % (gTitle, len(entries)), 'grp': gkey,
                               's_title': title, 's_id': sid, 'desc': desc, 'meta_year': info.get('year', '')})
                params.pop('chunk', None)
                self.addDir(params)
            return
        if not wanted:
            wanted = groupOrder[0]
        entries = groups.get(wanted, [])

        def _epNum(entry):
            try:
                return float(entry['episode'])
            except Exception:
                return 100000.0 + entry['idx']
        entries.sort(key=lambda x: (_epNum(x), x['idx']))

        chunk = cItem.get('chunk', '')
        if len(entries) > CHUNK_SIZE and chunk == '':
            for start in range(0, len(entries), CHUNK_SIZE):
                part = entries[start:start + CHUNK_SIZE]
                params = dict(cItem)
                params.update({'good_for_fav': True, 'category': 'wco_episodes', 'grp': wanted, 'chunk': str(start // CHUNK_SIZE), 's_id': sid, 's_title': title,
                               'title': '%s %s - %s' % (_('Episodes'), part[0]['episode'] or (start + 1), part[-1]['episode'] or (start + len(part)))})
                self.addDir(params)
            return
        if chunk != '':
            try:
                start = int(chunk) * CHUNK_SIZE
            except Exception:
                start = 0
            entries = entries[start:start + CHUNK_SIZE]

        for entry in entries:
            label = self._cleanLabel(entry['label'])
            params = {'good_for_fav': True, 'name': 'category', 'category': 'wco_episode', 'title': self._formatEpisodeTitle(label), 'ep_label': label,
                      'url': '%s/%s' % (self._seriesUrl(sid, dubbed), entry['termid']), 'termid': entry['termid'], 'embed': entry['embed'],
                      's_id': sid, 's_title': title, 'icon': self._thumb(entry['termid']), 'desc': desc,
                      'meta_type': 'tv', 'meta_title': title, 'meta_year': info.get('year', '') or cItem.get('meta_year', '')}
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG('WatchCartoonOnline.listSearchResult [%s]' % searchPattern)
        params = dict(self.defaultParams)
        params['header'] = dict(self.HEADER)
        params['header'].update({'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json, text/javascript, */*; q=0.01'})
        sts, data = self.getPage(self.getFullUrl('ajax/search.php?q=%s' % urllib_quote_plus(searchPattern)), params)
        if not sts:
            return
        try:
            data = json_loads(data)
        except Exception:
            printExc()
            return
        if not isinstance(data, list):
            return
        for item in data:
            if not isinstance(item, dict) or str(item.get('source', '')) != 'serie':
                continue  # movies are premium-only on the site
            year = str(item.get('year', '') or '')
            desc = []
            if year:
                desc.append(year)
            if item.get('rating'):
                desc.append('%s/10' % item.get('rating'))
            desc = ' | '.join(desc)
            if item.get('short_description'):
                desc += '[/br]' + self.cleanHtmlStr(_str(item.get('short_description')))
            self._addSeries(cItem, _str(item.get('url', '')), _str(item.get('title', '')), desc, year)

    ###################################################
    # links
    ###################################################
    def _findEntry(self, cItem, playlist):
        termid = cItem.get('termid', '') or self.cm.ph.getSearchGroups(cItem.get('url', ''), r'/detail(?:-dubbed)?/\d+/(\d+)')[0]
        for entry in playlist:
            if entry['termid'] == termid:
                return entry
        label = cItem.get('ep_label', '')
        if not label:
            return None
        wantedKey = self._key(LANG_SUFFIX_RE.sub('', self._cleanLabel(label)))
        for entry in playlist:
            if self._key(LANG_SUFFIX_RE.sub('', self._cleanLabel(entry['label']))) == wantedKey:
                return entry
        show, season, episode, dummy = self._parseLabel(label)
        if show:
            for entry in playlist:
                eShow, eSeason, eEpisode, dummy = self._parseLabel(entry['label'])
                if self._key(eShow) == self._key(show) and eSeason == season and eEpisode == episode:
                    return entry
        return None

    def getLinksForVideo(self, cItem):
        printDBG('WatchCartoonOnline.getLinksForVideo [%s]' % cItem.get('url'))
        urlTab = []
        embed = cItem.get('embed', '')
        sidecarTxt = ''
        if not embed:
            # recently added cards and favourites: look the episode up in the series page
            sts, data = self.getPage(cItem['url'])
            if not sts:
                return []
            entry = self._findEntry(cItem, self._parsePlaylist(data))
            if entry is None:
                SetIPTVPlayerLastHostError(_('Content not available'))
                return []
            embed = entry['embed']
            sidecarTxt = self._parseSeriesInfo(data).get('desc', '')

        path, sep, rest = embed.replace('\\/', '/').partition('&')
        url = self.getFullUrl('data-video/?v=%s%s%s' % (urllib_quote(path, safe='/'), sep, rest))
        params = dict(self.defaultParams)
        params['header'] = dict(self.HEADER)
        params['header'].update({'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json, text/javascript, */*; q=0.01', 'Referer': cItem['url']})
        sts, data = self.getPage(url, params)
        if not sts:
            return []
        try:
            data = json_loads(data)
        except Exception:
            printExc()
            return []
        if not isinstance(data, dict):
            return []
        server = str(data.get('server', '') or '').rstrip('/')
        if not self.cm.isValidUrl(server):
            return []
        seen = set()
        for key, name in (('fhd', '1080p'), ('hd', '720p'), ('enc', 'SD')):
            evid = str(data.get(key, '') or '').strip()
            # the same token under two qualities gives one row
            if evid and evid not in seen:
                seen.add(evid)
                urlTab.append({'name': name, 'url': strwithmeta('%s/getvid?evid=%s' % (server, evid), {'Referer': self.MAIN_URL}), 'need_resolve': 1})
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled(), sidecarTxt))

    def getVideoLinks(self, videoUrl):
        printDBG('WatchCartoonOnline.getVideoLinks [%s]' % videoUrl)
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        # the balancer answers with a redirect to a media node; the TLS certificates of the media
        # nodes (and of the cizgifilmlerizle.com balancers) are expired, plain http works on all of them
        url = re.sub(r'^https://', 'http://', str(videoUrl))  # NOSONAR - expired certificates, see above
        params = dict(self.defaultParams)
        params['header'] = dict(self.HEADER)
        params['no_redirection'] = True
        self.cm.getPage(url, params)
        location = self.cm.meta.get('location', '') or ''
        if not location:
            printDBG('WatchCartoonOnline: no media node redirect')
            return []
        location = re.sub(r'^https://', 'http://', self.cm.getFullUrl(location, url))  # NOSONAR - expired certificates
        item = {'name': 'mp4', 'url': strwithmeta(location, {'User-Agent': self.HEADER['User-Agent'], 'Referer': self.MAIN_URL})}
        return decorateResolvedLinkItems([item], sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG('WatchCartoonOnline.getArticleContent [%s]' % cItem.get('url'))
        sid = cItem.get('s_id', '')
        info = {}
        if sid:
            sts, data = self.getPage(self._seriesUrl(sid))
            if sts:
                info = self._parseSeriesInfo(data)
        title = info.get('title') or cItem.get('s_title', '') or cItem.get('title', '')
        year = info.get('year', '') or cItem.get('meta_year', '')
        meta = {}
        try:
            meta = getMeta('tv', title, year) or {}
        except Exception:
            printExc()
        otherInfo = dict(meta.get('info', {}) or {})
        for key in ('type', 'production', 'released', 'status', 'genres', 'duration'):
            if info.get(key) and not otherInfo.get(key):
                otherInfo[key] = info[key]
        if info.get('rating'):
            otherInfo['rating'] = info['rating']
        text = info.get('desc', '') or meta.get('plot', '') or cItem.get('desc', '')
        isVideo = cItem.get('type') == 'video'
        if isVideo and cItem.get('ep_label'):
            text = '%s[/br][/br]%s' % (cItem['ep_label'], text)
        icon = meta.get('poster') or cItem.get('icon', '')
        return [{'title': cItem.get('title', '') if isVideo else title, 'text': text, 'images': [{'title': '', 'url': icon}] if icon else [], 'other_info': otherInfo}]

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get('name', '')
        category = self.currItem.get('category', '')
        printDBG('WatchCartoonOnline.handleService name[%s] category[%s]' % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {'name': 'category'})
        elif category == 'home_section':
            self.listHomeSection(self.currItem)
        elif category == 'list_abc':
            self.listABC(self.currItem)
        elif category == 'list_letter':
            self.listLetter(self.currItem)
        elif category == 'list_genres':
            self.listGenres(self.currItem)
        elif category == 'list_genre':
            self.listGenre(self.currItem)
        elif category in ('wco_series', 'wco_episodes'):
            self.listSeries(self.currItem)
        elif category in ['search', 'search_next_page']:
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category'})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == 'search_history':
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _('Type: '))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, WatchCartoonOnline(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('watchcartoononline')

    def withArticleContent(self, cItem):
        return bool(cItem.get('s_id'))
