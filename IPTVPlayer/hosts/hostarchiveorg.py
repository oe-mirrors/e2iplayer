# -*- coding: utf-8 -*-
LAST_MODIFIED = "19.11.2026"
# 19.11.2026 - new host for archive.org: public domain films, classic TV, music, live concerts, audiobooks and podcasts
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getItemMeta, metaArticle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
try:
    from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
except ImportError:
    # E2iPlayer without tools/iptvpaging.py (older python3 or the zadmario fork): only "Next page"
    addPagingItems = isJumpItem = jumpTarget = None
###################################################
# FOREIGN import
###################################################
import re
###################################################


def GetConfigList():
    return []


def gettytul():
    return 'https://archive.org/'


class ArchiveOrg(GenericFolderWatchedScraperMixin, CBaseHostClass):
    FAV_FIELDS = ('name', 'type', 'category', 'url', 'id', 'title', 'icon', 'desc', 'collection', 'mtype', 'sort', 's_title', 'creator',
                  'duration', 'meta_type', 'meta_title', 'meta_year')
    ROWS = 30
    # advancedsearch.php refuses results beyond the first 10000 ("DEEP_PAGING")
    MAX_RESULTS = 10000
    # local paging of long track / episode lists
    LOCAL_ROWS = 100
    # (archive.org's own collection title, collection, video|audio)
    COLLECTIONS = (
        ('Feature Films', 'feature_films', 'video'),
        ('Animation & Cartoons', 'animationandcartoons', 'video'),
        ('Classic TV', 'classic_tv', 'video'),
        ('Prelinger Archives', 'prelinger', 'video'),
        ('Community Video', 'opensource_movies', 'video'),
        ('Music, Arts & Culture', 'audio_music', 'audio'),
        ('Live Music Archive', 'etree', 'audio'),
        ('LibriVox Free Audiobook Collection', 'librivoxaudio', 'audio'),
        ('Podcasts', 'podcasts', 'audio'),
    )
    # an item of these collections holds a whole series -> folder with one row per video
    SERIES_COLLECTIONS = ('classic_tv',)
    # films moviemeta can look up (INFO); other video collections only when the item is in one of these too
    FILM_COLLECTIONS = ('feature_films', 'silent_films', 'film_noir', 'moviesandfilms', 'sci-fi_horror', 'comedy_films', 'classic_cartoons')
    VIDEO_EXT = ('mp4', 'm4v', 'mkv', 'webm', 'avi', 'ogv', 'mpg', 'mpeg', 'mov', 'flv', 'wmv')
    AUDIO_EXT = ('mp3', 'ogg', 'm4a', 'flac', 'wav')

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'archiveorg', 'cookie': 'archiveorg.cookie'})
        self.MAIN_URL = gettytul()
        self.HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.defaultParams = {'header': self.HEADER}
        self.SORTS = ((_('Most popular'), 'downloads desc'), (_('Recently added'), 'publicdate desc'), (_('A-Z'), 'titleSorter asc'))
        self.MENU = [{'category': 'list_sorts', 'title': title, 'collection': coll, 'mtype': mtype, 'good_for_fav': True}
                     for title, coll, mtype in self.COLLECTIONS] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper('archiveorg')
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def _getJson(self, url):
        sts, data = self.getPage(url)
        if not sts:
            return None
        try:
            return json_loads(data)
        except Exception:
            printExc()
        return None

    def _getMetadata(self, ident):
        data = self._getJson(self.getFullUrl('metadata/' + urllib_quote(ident))) if ident else None
        return data if isinstance(data, dict) else {}

    def _asText(self, value):
        if isinstance(value, (int, float)):
            value = str(value)
        elif isinstance(value, list):
            value = ', '.join([ensure_str(v if not isinstance(v, (int, float)) else str(v)) for v in value if v])
        return self.cleanHtmlStr(ensure_str(value or ''))

    def _identOf(self, cItem):
        ident = cItem.get('id', '')
        if not ident:
            ident = self.cm.ph.getSearchGroups(cItem.get('url', ''), r'archive\.org/(?:details|download)/([^/?#]+)')[0]
        return ident

    def _fileUrl(self, ident, name):
        return self.getFullUrl('download/%s/%s' % (urllib_quote(ident), urllib_quote(name)))

    @staticmethod
    def _duration(value):
        # "1535.49" (seconds) or "05:23" -> "25:35" / "1:02:03"
        value = ensure_str(value or '').strip()
        try:
            secs = int(float(value))
        except Exception:
            return value
        if secs <= 0:
            return ''
        if secs >= 3600:
            return '%d:%02d:%02d' % (secs // 3600, secs % 3600 // 60, secs % 60)
        return '%d:%02d' % (secs // 60, secs % 60)

    @staticmethod
    def _filmTitle(title):
        # "Nosferatu, eine Symphonie des Grauens (A Symphony of Horror)" -> "Nosferatu, eine Symphonie des Grauens"
        return re.sub(r'\s*[\(\[].*$', '', title).strip() or title

    ###################################################
    # watched flag and favourites
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ''
            url = str(cItem.get('url', '') or '').strip()
            if url == '':
                return ''
            if cItem.get('type', '') in ('video', 'audio'):
                return 'video:%s' % url
            if cItem.get('category', '') in ('list_videos', 'list_tracks'):
                return 'folder:%s' % url
        except Exception:
            printExc()
        return ''

    def getFavouriteData(self, cItem):
        return self.getFavouriteFieldsData(cItem)

    ###################################################
    # paging
    ###################################################
    def addPaging(self, cItem, page, hasNext, lastPage):
        if addPagingItems is not None:
            addPagingItems(self, cItem, page, hasNext, lastPage)
        elif hasNext:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _('Next page'), 'page': page + 1})
            self.addDir(params)

    def _localPage(self, cItem, rows):
        # the rows of the current page of a long local list (+ pager rows after them)
        page = int(cItem.get('page', 1) or 1)
        lastPage = max(1, (len(rows) + self.LOCAL_ROWS - 1) // self.LOCAL_ROWS)
        return rows[(page - 1) * self.LOCAL_ROWS:page * self.LOCAL_ROWS], page, lastPage

    ###################################################
    # lists
    ###################################################
    def listSorts(self, cItem):
        for title, sort in self.SORTS:
            self.addDir({'name': 'category', 'category': 'list_items', 'title': title, 'collection': cItem.get('collection', ''),
                         'mtype': cItem.get('mtype', ''), 'sort': sort, 'icon': cItem.get('icon', ''), 'good_for_fav': True})

    def listItems(self, cItem):
        printDBG('ArchiveOrg.listItems [%s]' % cItem)
        page = int(cItem.get('page', 1) or 1)
        pattern = cItem.get('search_pattern', '')
        collection = cItem.get('collection', '')
        if pattern:
            # the search query is Lucene syntax: slashes, brackets and an unclosed quote make the API answer an error
            pattern = re.sub(r'[\\/()\[\]{}]', ' ', pattern)
            if pattern.count('"') % 2:
                pattern = pattern.replace('"', ' ')
            query, sort = '(%s) AND mediatype:(movies OR audio OR etree)' % (pattern.strip() or '*'), 'downloads desc'
        else:
            query = 'collection:%s AND mediatype:%s' % (collection, 'movies' if cItem.get('mtype') == 'video' else '(audio OR etree)')
            sort = cItem.get('sort', 'downloads desc')
        url = self.getFullUrl('advancedsearch.php?q=%s&fl%%5B%%5D=identifier&fl%%5B%%5D=title&fl%%5B%%5D=description&fl%%5B%%5D=year'
                              '&fl%%5B%%5D=mediatype&fl%%5B%%5D=creator&sort%%5B%%5D=%s&rows=%d&page=%d&output=json'
                              % (urllib_quote_plus(query), urllib_quote_plus(sort), self.ROWS, page))
        data = self._getJson(url)
        response = data.get('response', {}) if isinstance(data, dict) else {}
        if not response:
            SetIPTVPlayerLastHostError(_('Loading failed.'))
            return
        normalize = IsMediaNamingNormalized()
        for doc in response.get('docs', []):
            ident = ensure_str(doc.get('identifier', ''))
            if not ident:
                continue
            title = self._asText(doc.get('title', '')) or ident
            # a year in the title ("Aces Go Places III (1984)") wins over the item's year (often the upload year)
            year = self.cm.ph.getSearchGroups(title, r'\(((?:18|19|20)\d\d)\)')[0] or self._asText(doc.get('year', ''))[:4]
            params = {'name': 'category', 'good_for_fav': True, 'id': ident, 'url': self.getFullUrl('details/' + ident),
                      'icon': self.getFullUrl('services/img/' + ident), 'desc': self._asText(doc.get('description', ''))[:600],
                      's_title': title, 'creator': self._asText(doc.get('creator', ''))}
            if doc.get('mediatype') != 'movies':
                params.update({'category': 'list_tracks', 'title': title, 'mtype': 'audio'})
                self.addDir(params)
            elif collection in self.SERIES_COLLECTIONS:
                params.update({'category': 'list_videos', 'title': title, 'mtype': 'video'})
                self.addDir(params)
            else:
                if collection in self.FILM_COLLECTIONS:
                    params.update({'meta_type': 'movie', 'meta_title': self._filmTitle(title), 'meta_year': year})
                if normalize and year and year not in title:
                    title = '%s (%s)' % (title, year)
                params.update({'category': 'video', 'title': title, 'mtype': 'video'})
                self.addVideo(params)
        lastPage = min((int(response.get('numFound', 0) or 0) + self.ROWS - 1) // self.ROWS, self.MAX_RESULTS // self.ROWS)
        self.addPaging(cItem, page, page < lastPage, lastPage)

    def listVideos(self, cItem):
        # the videos of an item holding a series: one row per original video (its derivatives are its formats)
        printDBG('ArchiveOrg.listVideos [%s]' % cItem.get('id'))
        ident = self._identOf(cItem)
        files = self._getMetadata(ident).get('files', [])
        groups = {}
        for f in files:
            name = ensure_str(f.get('name', ''))
            low = name.lower()
            if low.rsplit('.', 1)[-1] not in self.VIDEO_EXT or f.get('private') or '_sample' in low or 'trailer' in low:
                continue
            root = f.get('original', '') if f.get('source') == 'derivative' else ''
            root = ensure_str((root[0] if isinstance(root, list) and root else root) or name)
            group = groups.setdefault(root.rsplit('.', 1)[0], {'root': root, 'title': '', 'length': ''})
            group['title'] = group['title'] or self._asText(f.get('title', ''))
            group['length'] = group['length'] or self._duration(f.get('length', ''))
        if not groups:
            SetIPTVPlayerLastHostError(_('Content not available'))
            return
        normalize = IsMediaNamingNormalized()
        show = cItem.get('s_title', '') or cItem.get('title', '')
        rows = [groups[k] for k in sorted(groups, key=lambda k: k.lower())]
        rows, page, lastPage = self._localPage(cItem, rows)
        for group in rows:
            title = group['title'] or group['root'].rsplit('.', 1)[0].split('/')[-1].replace('_', ' ')
            if normalize and show and not title.lower().startswith(show.lower()):
                title = '%s - %s' % (show, title)
            desc = ' | '.join([x for x in (group['length'], cItem.get('desc', '')) if x])
            self.addVideo({'name': 'category', 'category': 'episode', 'good_for_fav': True, 'id': ident, 'title': title, 's_title': show,
                           'url': self.getFullUrl('details/%s/%s' % (urllib_quote(ident), urllib_quote(group['root']))),
                           'icon': cItem.get('icon', ''), 'desc': desc, 'duration': group['length']})
        self.addPaging(cItem, page, page < lastPage, lastPage)

    def listTracks(self, cItem):
        # tracks of an album / audiobook / concert / podcast item
        printDBG('ArchiveOrg.listTracks [%s]' % cItem.get('id'))
        ident = self._identOf(cItem)
        meta = self._getMetadata(ident)
        files = []
        for f in meta.get('files', []):
            name = ensure_str(f.get('name', ''))
            low = name.lower()
            if low.rsplit('.', 1)[-1] in self.AUDIO_EXT and not f.get('private') and '_sample' not in low:
                files.append(f)
        # the MP3 derivatives when there are any, without the 64 kbit copies of a concert
        mp3 = [f for f in files if ensure_str(f.get('name', '')).lower().endswith('.mp3')]
        if mp3:
            files = [f for f in mp3 if '_64kb' not in ensure_str(f.get('name', '')).lower()] or mp3
        if not files:
            SetIPTVPlayerLastHostError(_('Content not available'))
            return

        def trackKey(f):
            num = re.match(r'\d+', ensure_str(f.get('track', '') or ''))
            return (int(num.group(0)) if num else 9999, ensure_str(f.get('name', '')).lower())

        files.sort(key=trackKey)
        normalize = IsMediaNamingNormalized()
        album = cItem.get('s_title', '') or cItem.get('title', '')
        creator = cItem.get('creator', '') or self._asText(meta.get('metadata', {}).get('creator', ''))
        rows, page, lastPage = self._localPage(cItem, files)
        for f in rows:
            name = ensure_str(f.get('name', ''))
            trackTitle = self._asText(f.get('title', '')) or name.rsplit('.', 1)[0].split('/')[-1].replace('_', ' ')
            title = '%s - %s' % (album, trackTitle) if (normalize and album and not trackTitle.startswith(album)) else trackTitle
            duration = self._duration(f.get('length', ''))
            desc = ' | '.join([x for x in (duration, self._asText(f.get('artist', '')) or creator, album) if x])
            self.addAudio({'name': 'category', 'category': 'track', 'good_for_fav': True, 'id': ident, 'title': title, 's_title': album,
                           'url': self._fileUrl(ident, name), 'icon': cItem.get('icon', ''), 'desc': desc, 'duration': duration, 'creator': creator})
        self.addPaging(cItem, page, page < lastPage, lastPage)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG('ArchiveOrg.listSearchResult [%s]' % searchPattern)
        self.listItems({'name': 'category', 'category': 'list_items', 'search_pattern': searchPattern, 'page': 1})

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG('ArchiveOrg.getLinksForVideo [%s]' % cItem.get('url'))
        url = cItem.get('url', '')
        if '/download/' in url:
            links = [{'name': url.rsplit('.', 1)[-1].upper(), 'url': url, 'need_resolve': 0}]
        else:
            # the item's video files, best first: urlparser parserARCHIVEORG (also used by other hosts)
            links = [{'name': item['name'], 'url': item['url'], 'need_resolve': 0} for item in self.up.getVideoLinkExt(url)]
        if not links:
            SetIPTVPlayerLastHostError(_('Content not available'))
            return []
        return applySidecarToLinks(links, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    ###################################################
    # INFO key
    ###################################################
    def getArticleContent(self, cItem):
        printDBG('ArchiveOrg.getArticleContent [%s]' % cItem.get('url'))
        icon = cItem.get('icon', '')
        if cItem.get('category') in ('track', 'episode'):
            info = {}
            if cItem.get('duration'):
                info['duration'] = cItem['duration']
            if cItem.get('creator'):
                info['creator'] = cItem['creator']
            return metaArticle(cItem, {}, poster=icon, info=info)
        meta = self._getMetadata(self._identOf(cItem)).get('metadata', {})
        story = self._asText(meta.get('description', ''))
        year = self._asText(meta.get('year', '') or meta.get('date', ''))[:4]
        info = {}
        for key, value in (('year', year), ('creator', self._asText(meta.get('creator', ''))), ('duration', self._duration(meta.get('runtime', ''))),
                           ('language', self._asText(meta.get('language', '')))):
            if value:
                info[key] = value
        filmMeta = {}
        collections = meta.get('collection', [])
        collections = collections if isinstance(collections, list) else [collections]
        if cItem.get('meta_type') == 'movie' or (cItem.get('mtype') == 'video' and [c for c in collections if c in self.FILM_COLLECTIONS]):
            title = cItem.get('meta_title', '') or self._filmTitle(self._asText(meta.get('title', '')) or cItem.get('s_title', ''))
            filmMeta = getItemMeta(dict(cItem, meta_type='movie', meta_title=title, meta_year=cItem.get('meta_year', '') or year))
        return metaArticle(cItem, filmMeta, story=story, poster=icon, info=info, desc=cItem.get('desc', '') or cItem.get('title', ''))

    ###################################################
    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('ArchiveOrg.handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem is not None and isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get('name', '')
        category = self.currItem.get('category', '')
        printDBG('handleService: name[%s], category[%s]' % (name, category))
        self.currList = []

        if name is None:
            self.listsTab(self.MENU, {'name': 'category'})
        elif category == 'list_sorts':
            self.listSorts(self.currItem)
        elif category == 'list_items':
            self.listItems(self.currItem)
        elif category == 'list_videos':
            self.listVideos(self.currItem)
        elif category == 'list_tracks':
            self.listTracks(self.currItem)
        elif category in ('search', 'search_next_page'):
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
        CHostBase.__init__(self, ArchiveOrg(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('archiveorg')

    def withArticleContent(self, cItem):
        return cItem.get('category', '') in ('video', 'episode', 'track', 'list_videos', 'list_tracks')
