# -*- coding: utf-8 -*-
#
#  Trailer of a film / series row: MENU -> "Trailer" in a list and the blue key of the INFO page.
#  Looked for in this order: a trailer the host itself has on the row (a YouTube link or a direct video url), TMDb
#  (own API key of the details settings), a YouTube search "<title> <year> Trailer <language>". The list of hits (or
#  with "Play the first trailer at once" the first one) plays in the player chosen in the settings; afterwards the
#  list is shown again.
#
from Plugins.Extensions.IPTVPlayer.components.asynccall import AsyncMethod
from Plugins.Extensions.IPTVPlayer.components.iptvchoicebox import IPTVChoiceBoxItem, openChoiceBox
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs import moviemeta
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, eConnectCallback, StripColorCodes

from Components.config import config
from Screens.MessageBox import MessageBox
from enigma import eTimer

import re
import threading
import time

MAX_HITS = 20
YOUTUBE_WATCH = 'https://www.youtube.com/watch?v=%s'
YOUTUBE_THUMB = 'https://i.ytimg.com/vi/%s/hqdefault.jpg'
# what YouTube trailers of a language are called, appended to the search (default: "Trailer")
SEARCH_SUFFIX = {
    'de': 'Trailer Deutsch',
    'cs': 'trailer cz',
    'es': 'tráiler español',
    'fr': 'bande annonce vf',
    'hu': 'előzetes',
    'it': 'trailer italiano',
    'nl': 'trailer nederlands',
    'pl': 'zwiastun',
    'pt': 'trailer dublado',
    'ru': 'трейлер',
    'tr': 'fragman',
    'uk': 'трейлер українською',
}
# keys of a host row that carry a trailer: a YouTube url or id, or a direct video url (MovieBox: trailer_url)
HOST_TRAILER_KEYS = ('youtube_trailer', 'trailer_url', 'trailer')
_YT_ID_RE = re.compile(r'(?:[?&]v=|youtu\.be/|/embed/|/shorts/)([A-Za-z0-9_-]{11})')


def youtubeId(value):
    value = str(value or '').strip()
    if re.match(r'^[A-Za-z0-9_-]{11}$', value):
        return value
    match = _YT_ID_RE.search(value)
    return match.group(1) if match else ''


def trailerLanguage():
    # '' = original (no language wish), a fixed language, or the language of the details (TMDb / IMDb, Auto = E2iPlayer's)
    value = config.plugins.iptvplayer.trailer_language.value
    if value == 'original':
        return ''
    if value != 'auto':
        return value
    try:
        return moviemeta._getLanguage()
    except Exception:
        printExc()
        return ''


def searchSuffix(lang):
    # the words after the title: the user's own, else the usual ones of the language ("Trailer Deutsch")
    own = str(config.plugins.iptvplayer.trailer_search_suffix.value or '').strip()
    return own or SEARCH_SUFFIX.get(lang, 'Trailer')


def cleanTitle(title):
    # (title, year) of a list row: colour codes, [tags], (2019), S01E02 / "Staffel 2", quality marks out
    title = StripColorCodes(str(title or ''))
    year = ''
    match = re.search(r'[\(\[]((?:19|20)\d{2})[\)\]]', title)
    if match:
        year = match.group(1)
    title = re.sub(r'\s*[\(\[][^\)\]]*[\)\]]\s*', ' ', title)
    title = re.sub(r'\b[sS]\d{1,2}\s*[eE]\d{1,3}\b.*$', ' ', title)
    title = re.sub(r'\b(Staffel|Season|Folge|Episode|Teil)\s*\d+\b.*$', ' ', title, flags=re.I)
    title = re.sub(r'\b(4K|UHD|HD|FullHD|1080p|720p|HDR|DV)\b', ' ', title, flags=re.I)
    title = re.sub(r'\s+', ' ', title).strip(' -:|,.')
    return title, year


def rowQuery(name, rawItem=None):
    # (title, year, mediaType) of a list row: the host's meta fields where it sets them (libs/moviemeta), else the row name
    rawItem = rawItem if isinstance(rawItem, dict) else {}
    title, year = cleanTitle(rawItem.get('meta_title') or name)
    year = str(rawItem.get('meta_year') or year or '')[:4]
    return title, year if year.isdigit() else '', rawItem.get('meta_type', '')


def _hit(videoId, title, desc='', source=''):
    return {'video_id': videoId, 'url': YOUTUBE_WATCH % videoId, 'title': title, 'desc': desc, 'icon': YOUTUBE_THUMB % videoId, 'source': source}


def hostTrailers(rawItem, title):
    hits = []
    if isinstance(rawItem, dict):
        for key in HOST_TRAILER_KEYS:
            value = str(rawItem.get(key) or '').strip()
            videoId = youtubeId(value)
            if videoId:
                hits.append(_hit(videoId, '%s - %s' % (title, _('Trailer')), source='host'))
            elif value.startswith(('http://', 'https://')):
                # a direct video url of the site: played as it is (no YouTube resolver, no thumbnail)
                hits.append({'video_id': value, 'url': value, 'title': '%s - %s' % (title, _('Trailer')), 'desc': '',
                             'icon': '', 'source': 'host', 'direct': True})
    return hits


def tmdbTrailers(title, year, mediaType, lang):
    # the YouTube trailers / teasers TMDb lists for the title; only with the TMDb API key of the details settings
    cp = config.plugins.iptvplayer
    key = cp.meta_tmdb_apikey.value.strip()
    if not cp.meta_tmdb.value or not key:
        return []
    tmdb = moviemeta._TMDb(key, lang or 'en')
    for mt in ([mediaType] if mediaType in ('movie', 'tv') else ['movie', 'tv']):
        movie = mt == 'movie'
        params = {'query': title}
        if year:
            params['year' if movie else 'first_air_date_year'] = year
        data = tmdb._call('search/movie' if movie else 'search/tv', params)
        if data is None:
            return []
        hit = moviemeta._pickResult(data.get('results') or [], title, year, ('title', 'original_title') if movie else ('name', 'original_name'), 'release_date' if movie else 'first_air_date')
        if not hit:
            continue
        # the wanted language, English and videos without a language; original: all of them
        videoParams = {'include_video_language': '%s,en,null' % lang} if lang else {'language': 'en', 'include_video_language': 'en,null'}
        videos = tmdb._call('%s/%s/videos' % (mt, hit['id']), videoParams)
        results = [v for v in ((videos or {}).get('results') or []) if v.get('site') == 'YouTube' and v.get('type') in ('Trailer', 'Teaser') and youtubeId(v.get('key'))]

        def order(v):
            return (0 if (lang and v.get('iso_639_1') == lang) else 1, 0 if v.get('type') == 'Trailer' else 1, 0 if v.get('official') else 1)
        results.sort(key=order)
        printDBG('IPTVTrailer.tmdbTrailers %s[%s] videos[%d]' % (mt, hit['id'], len(results)))
        return [_hit(v['key'], v.get('name') or title, '%s | %s' % (v.get('type', ''), (v.get('iso_639_1') or '').upper()), 'tmdb') for v in results]
    return []


def youtubeTrailers(title, year, lang):
    from Plugins.Extensions.IPTVPlayer.libs.youtubeparser import YouTubeParser
    query = ' '.join([p for p in (title, year, searchSuffix(lang)) if p])
    for attempt in range(2):
        # YouTube sometimes answers with a page without results ("more" only): ask once more
        items = YouTubeParser().getSearchResult(urllib_quote_plus(query), 'video', 1, 'search', 'A') or []
        if [i for i in items if i.get('type') == 'video']:
            break
        printDBG('IPTVTrailer.youtubeTrailers query[%s] no videos (attempt %d)' % (query, attempt + 1))
        time.sleep(1)
    hits = []
    for item in items or []:
        videoId = youtubeId(item.get('video_id') or item.get('url'))
        if item.get('type') != 'video' or not videoId or item.get('image_type') == 'SHORT':
            continue
        desc = re.sub(r'\s*(?:\[/br\]|\n)+\s*', ' | ', str(item.get('desc', '') or '')).strip(' |')
        hits.append(_hit(videoId, StripColorCodes(str(item.get('title', ''))), desc, 'youtube'))
    # titles with more words of the search addition first ("bande annonce vf" for French: YouTube also answers with
    # trailers in the language of the box's region), then the ones with "trailer"; YouTube's order within the groups
    words = [w for w in searchSuffix(lang).lower().split() if len(w) > 2]

    def rank(hit):
        title = hit['title'].lower()
        return (-sum(1 for w in words if w in title), 0 if 'trailer' in title else 1)
    hits.sort(key=rank)
    printDBG('IPTVTrailer.youtubeTrailers query[%s] videos[%d] words%s' % (query, len(hits), words))
    return hits


def findTrailers(title, year, mediaType, rawItem, firstOnly=False):
    # firstOnly ("Play the first trailer at once"): the later sources are not asked once one has a hit
    lang = trailerLanguage()
    hits, known = [], set()
    for source in (lambda: hostTrailers(rawItem, title), lambda: tmdbTrailers(title, year, mediaType, lang), lambda: youtubeTrailers(title, year, lang)):
        try:
            for hit in source():
                if hit['video_id'] not in known:
                    known.add(hit['video_id'])
                    hits.append(hit)
        except Exception:
            printExc()
        if len(hits) >= MAX_HITS or (firstOnly and hits):
            break
    return hits[:MAX_HITS]


def resolveTrailer(hit):
    # the urls to play, best first: the links of the YouTube resolver with the trailer's description (MENU ->
    # "Description" / chapters in the player), or a direct url of the host as it is
    if hit.get('direct'):
        return [hit['url']]
    from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
    from Plugins.Extensions.IPTVPlayer.libs import urlmetahelper
    url = hit['url']
    sidecar = options = None
    try:
        from Plugins.Extensions.IPTVPlayer.libs.youtubeparser import YouTubeParser
        watch = YouTubeParser()._getWatchPageData(hit['video_id']) or {}
        text = str(watch.get('fullDescription') or hit.get('desc') or '')
        sidecar = urlmetahelper.buildSidecar(True, text, hit.get('icon', ''))
        options = urlmetahelper.buildYoutubeOptions(False, False, str(watch.get('channelName') or ''))
        url = urlmetahelper.decorateYoutubeUrl(url, sidecar=sidecar, youtubeOptions=options)
    except Exception:
        printExc()
    links = urlparser().getVideoLinkExt(url) or []
    if links and sidecar is not None:
        try:
            links = urlmetahelper.decorateYoutubeLinkItems(links, sidecar=sidecar, youtubeOptions=options)
        except Exception:
            printExc()
    printDBG('IPTVTrailer.resolveTrailer [%s] links[%d]' % (hit['video_id'], len(links)))
    return [link['url'] for link in links if link.get('url')]


class IPTVTrailer(object):
    # one search at a time for the list widget (owner): owner.setStatusTex(), owner.isInWorkThread(),
    # owner._getMoviePlayerPickerHeight(), owner.playTrailer(urls, title, iconUrl)

    def __init__(self, owner):
        self.owner = owner
        self.session = owner.session
        self.lock = threading.Lock()
        self.job = None  # (kind, AsyncCall)
        self.result = None
        self.title = ''
        self.hit = None
        self.startList = None
        self.timer = eTimer()
        self.timer_conn = eConnectCallback(self.timer.timeout, self._poll)

    def isBusy(self):
        return self.job is not None

    def stop(self):
        self.timer.stop()
        if self.job is not None:
            try:
                self.job[1].kill()
            except Exception:
                printExc()
        self.job = None

    def close(self):
        self.stop()
        self.timer_conn = None
        self.owner = None

    def start(self, name, rawItem=None):
        if self.isBusy():
            return
        title, year, mediaType = rowQuery(name, rawItem)
        if not title:
            return
        self.title = title
        printDBG('IPTVTrailer.start title[%s] year[%s] type[%s]' % (title, year, mediaType))
        self._run('search', findTrailers, title, year, mediaType, rawItem, bool(config.plugins.iptvplayer.trailer_autoplay.value),
                  status=_("Looking for trailers..."))

    def _setStatus(self, text):
        # the list's status line, unless a list request of its own runs and shows its text there
        if not self.owner.isInWorkThread():
            self.owner.setStatusTex(text)

    def _run(self, kind, fnc, *args, **kwargs):
        self.result = None
        # the list the search started from: a folder opened meanwhile replaces it (a new list object)
        self.startList = self.owner.currList
        self._setStatus(kwargs.get('status', ''))
        self.job = (kind, AsyncMethod(fnc, self._done)(*args))
        self.timer.start(100)

    def _done(self, result):
        # worker thread: only hand the result over
        with self.lock:
            self.result = (result,)

    def _poll(self):
        with self.lock:
            result = self.result
        if result is None:
            if self.job is not None and self.job[1].getExceptStack():
                result = (None,)  # the worker died with an exception (already in the log)
            else:
                return
        self.timer.stop()
        kind = self.job[0] if self.job else ''
        self.job = None
        if self.owner is None:
            return
        try:
            self._setStatus('')
            if (self.session.current_dialog is not self.owner or self.owner.currList is not self.startList
                    or self.owner.isInWorkThread()):
                # the user went on meanwhile (another screen on top, a folder opened or loading, a video started):
                # no list / player over that
                printDBG('IPTVTrailer._poll %s result dropped, the list is not the one of the search' % kind)
            elif kind == 'search':
                self._searchDone(result[0] or [])
            elif kind == 'resolve':
                self._resolveDone(result[0])
        except Exception:
            printExc()

    def _searchDone(self, hits):
        if not hits:
            self.session.open(MessageBox, _("No trailer found for \"%s\".") % self.title, type=MessageBox.TYPE_INFO, timeout=10)
            return
        if config.plugins.iptvplayer.trailer_autoplay.value:
            self._play(hits[0])
            return
        options = []
        for hit in hits:
            label = hit['title']
            if hit['source'] == 'tmdb':
                label = '%s  [TMDb]' % label
            options.append(IPTVChoiceBoxItem(label, hit.get('desc', ''), hit))
        openChoiceBox(self.session, {'width': 1000, 'height': self.owner._getMoviePlayerPickerHeight(min(len(options), 10)), 'current_idx': 0,
                                     'title': _("Trailer") + ': ' + self.title, 'options': options, 'chrome': True, 'footerMargin': 136}, self._picked)

    def _picked(self, ret=None):
        if isinstance(ret, IPTVChoiceBoxItem) and isinstance(ret.privateData, dict) and self.owner is not None:
            self._play(ret.privateData)

    def _play(self, hit):
        self.hit = hit
        self._run('resolve', resolveTrailer, hit, status=_("Loading..."))

    def _resolveDone(self, urls):
        if not urls:
            self.session.open(MessageBox, _("No valid links available."), type=MessageBox.TYPE_INFO, timeout=10)
            return
        self.owner.playTrailer(urls, self.hit['title'], self.hit.get('icon', ''))
