# -*- coding: utf-8 -*-
LAST_MODIFIED = "18.10.2026"
# HGTV (de.hgtv.com) - Mediathek of the German free-TV channel HGTV (Warner Bros. Discovery).
# 18.10.2026 - new host: the site is a single-page app on the WBD "Aurora" CMS API
#   (public.aurora.enhanced.live/site/: page/<slug>, search/page), streams from the Discovery "Sonic"
#   playback API (anonymous token, realm "de"): plain HLS without DRM, the video renditions carry no
#   sound - the AUDIO group is merged in (merge://). Home page rows, new episodes, all shows A-Z,
#   seasons / episodes / clips, films (TELE 5), search with paging, moviemeta INFO, watched flag,
#   downloaded flag, name normalisation, sidecar, favourites.
#   hostdmax / hosttlc / hosthgtv / hosttele5 are the same code - only the CHANNEL block below differs (keep them in sync).
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir, b64Encode
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
###################################################
# FOREIGN import
###################################################
import re
from datetime import date
###################################################


def GetConfigList():
    return []


###################################################
# CHANNEL
###################################################
CHANNEL_NAME = 'HGTV'
CHANNEL_KEY = 'hgtv'                # history / cookie / watched file / icons
CHANNEL_ENV = 'hgtvde'              # CMS environment
CHANNEL_NEW_EPISODES = False        # the home page has the "Neue Folgen" playlist
CHANNEL_SHOWS = 'sendungen'         # slug of the all-shows page (parent of every show page)
CHANNEL_PAGES = ()                  # more main-menu pages: (title msgid, page slug)


def gettytul():
    return 'https://de.hgtv.com/'


CHANNEL_URL = gettytul()
###################################################


class WBDMediathek(GenericFolderWatchedScraperMixin, CBaseHostClass):
    SITE_API = 'https://public.aurora.enhanced.live/site/'
    SITE_QUERY = 'include=default&filter[environment]=%s&v=2' % CHANNEL_ENV
    SONIC_API = 'https://public.aurora.enhanced.live/'
    SONIC_REALM = 'de'
    # the site's image service (sharp on CloudFront): the S3 originals answer 403, this one scales + gives JPEG
    IMG_SERVICE = 'https://d2v9mhsiek5lbq.cloudfront.net/'
    IMG_WIDTH = 500
    SEARCH_PAGE_SIZE = 100  # the API's maximum; the shows of a search fit on the first page
    FAV_FIELDS = ('name', 'category', 'type', 'url', 'title', 'icon', 'desc', 'slug', 'parent_slug', 'video_id',
                  's_title', 'season', 'episode', 'duration', 'age_limit', 'released', 'meta_type', 'meta_title')
    # genre taxonomy of the film pages (TELE 5); everything else is a series / show
    FILM_TAXONOMIES = ('filme', 'film', 'spielfilm', 'spielfilme')

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': CHANNEL_KEY, 'cookie': CHANNEL_KEY + '.cookie'})
        self.MAIN_URL = CHANNEL_URL
        self.DEFAULT_ICON_URL = 'file://' + GetIconDir('PlayerSelector/%s135.png' % CHANNEL_KEY)
        self.HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.HEADER.update({'Accept': 'application/json, text/plain, */*', 'Referer': self.MAIN_URL, 'Origin': self.MAIN_URL[:-1]})
        self.defaultParams = {'header': self.HEADER}
        self.sonicToken = ''
        self.watchedHelper = IPTVWatchedHelper(CHANNEL_KEY)
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ''
            if cItem.get('type', '') == 'video':
                vid = str(cItem.get('video_id', '') or '').strip()
                return 'video:%s' % vid if vid else ''
            category = cItem.get('category', '')
            if category == 'list_show' and cItem.get('slug'):
                return 'show:%s' % cItem['slug']
            if category == 'list_season' and cItem.get('slug'):
                return 'season:%s:%s' % (cItem['slug'], cItem.get('season', ''))
            return ''
        except Exception:
            printExc()
        return ''

    ###################################################
    # helpers
    ###################################################
    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    def _json(self, url, addParams=None, post_data=None):
        sts, data = self.getPage(url, addParams, post_data)
        if not sts or not data:
            return None
        try:
            return json_loads(data)
        except Exception:
            printExc()
        return None

    def _pageApi(self, slug, parentSlug=''):
        url = '%spage/%s/?%s' % (self.SITE_API, slug, self.SITE_QUERY)
        if parentSlug:
            url += '&parent_slug=' + parentSlug
        return url

    def _page(self, slug, parentSlug=''):
        data = self._json(self._pageApi(slug, parentSlug))
        if not isinstance(data, dict) or data.get('slug') == 'http404':
            return {}
        return data

    def _img(self, url):
        # S3 (loma-media-de) and images.aurora.enhanced.live (aurora-content-images) -> scaled JPEG
        try:
            url = url or ''
            bucket, key = '', ''
            if '/loma-media-de/' in url:
                bucket, key = 'loma-media-de', url.split('/loma-media-de/', 1)[1]
            elif '://images.aurora.enhanced.live/' in url:
                bucket, key = 'aurora-content-images', url.split('://images.aurora.enhanced.live/', 1)[1]
            if not bucket or not key:
                return url
            req = {'bucket': bucket, 'key': key.split('?', 1)[0],
                   'edits': {'resize': {'width': self.IMG_WIDTH, 'fit': 'cover'}, 'toFormat': 'jpeg', 'jpeg': {'quality': 70}}}
            return self.IMG_SERVICE + b64Encode(json_dumps(req, separators=(',', ':')))
        except Exception:
            printExc()
        return url

    def _mediaUrl(self, media):
        if isinstance(media, dict):
            return media.get('url') or media.get('src') or ''
        return ''

    @staticmethod
    def _duration(ms):
        try:
            secs = int(ms or 0) // 1000
        except Exception:
            return ''
        if secs <= 0:
            return ''
        if secs >= 3600:
            return '%d:%02d:%02d' % (secs // 3600, (secs % 3600) // 60, secs % 60)
        return '%d:%02d' % (secs // 60, secs % 60)

    @staticmethod
    def _date(value):
        # "2026-10-13T20:05:00+00:00" -> "13.10.2026"
        try:
            value = (value or '')[:10]
            if len(value) == 10 and value[4] == '-' and value[7] == '-':
                return '%s.%s.%s' % (value[8:10], value[5:7], value[:4])
        except Exception:
            pass
        return ''

    def _isFilm(self, data, header):
        # TELE 5 films are show pages with one video and the genre "filme" (on the show page only)
        for tax in list(header.get('taxonomies') or []) + list(data.get('taxonomies') or []):
            if isinstance(tax, dict) and (tax.get('slug') or '').lower() in self.FILM_TAXONOMIES:
                return True
        return False

    @staticmethod
    def _notOnline(tunein, today=None):
        # the site's own note in the show list says there is nothing to watch: "DERZEIT NICHT IM PROGRAMM",
        # "ALLE FOLGEN AUF TLC.DE" or an "Online 25.10. - 24.11." window that has not begun / is over
        text = (tunein or '').lower()
        if 'nicht im programm' in text or 'folgen auf ' in text:
            return True
        match = re.search(r'online:?\s*(\d{1,2})\.(\d{1,2})\.?\s*-\s*(\d{1,2})\.(\d{1,2})', text)
        if not match:
            return False
        today = today or date.today()

        def nearest(day, month):
            # the note has no year: the date nearest to today
            try:
                cands = [date(today.year + off, int(month), int(day)) for off in (-1, 0, 1)]
            except ValueError:
                return None
            return min(cands, key=lambda d: abs((d - today).days))

        start = nearest(match.group(1), match.group(2))
        end = nearest(match.group(3), match.group(4))
        if start is None or end is None:
            return False
        return start > today or end < today

    @staticmethod
    def _isGerman(label):
        label = (label or '').lower()
        return not label or label.startswith('german') or label.startswith('deu') or label.startswith('deutsch')

    @staticmethod
    def _toInt(value):
        try:
            return int(value or 0)
        except Exception:
            return 0

    ###################################################
    # items
    ###################################################
    def _addShow(self, cItem, item):
        # a "showpage" of the all-shows list / search, or a collectionItemBlock pointing to one
        try:
            if not isinstance(item, dict):
                return False
            pageType = item.get('pageType') or item.get('type') or ''
            if pageType not in ('showpage', 'collectionItemBlock'):
                return False
            if item.get('type') == 'collectionItemBlock' and (item.get('pageType') != 'showpage' or item.get('urlType') == 'external'):
                return False
            slug = item.get('slug') or item.get('url') or ''
            title = self.cleanHtmlStr(item.get('pageTitleOverride') or item.get('title') or '')
            if not slug or not title or '://' in slug:
                return False
            parentSlug = item.get('parentSlug') or item.get('parentUrl') or ''
            if not parentSlug and isinstance(item.get('parentPage'), dict):
                parentSlug = item['parentPage'].get('slug') or ''
            icon = self._mediaUrl(item.get('image'))
            for media in (item.get('metaMedia') or []):
                if not icon and isinstance(media, dict):
                    icon = self._mediaUrl(media.get('media'))
            # metaDescription is double-encoded UTF-8 (mojibake) - never use it
            desc = self.cleanHtmlStr(item.get('articleContent') or item.get('description') or '')
            tunein = self.cleanHtmlStr(item.get('tuneinInfo') or '')
            if not tunein and isinstance(item.get('attributes'), dict):
                tunein = self.cleanHtmlStr(item['attributes'].get('tuneinInfo') or '')
            attrs = item.get('attributes') if isinstance(item.get('attributes'), dict) else {}
            showId = item['showId'] if 'showId' in item else attrs.get('showId')
            if self._notOnline(tunein) or (showId is not None and not str(showId).strip().isdigit()):
                # an empty folder: the site lists it for the TV programme only, or no video show is linked
                # (empty showId; TELE 5 even has "Online: 9.4. - 23.4." in that field)
                return False
            if tunein:
                desc = '%s[/br]%s' % (tunein, desc) if desc else tunein
            # meta_type "tv" until the show page tells a film (listShow / getArticleContent)
            params = {'name': 'category', 'category': 'list_show', 'good_for_fav': True, 'title': title, 's_title': title,
                      'slug': slug, 'parent_slug': parentSlug or CHANNEL_SHOWS, 'icon': self._img(icon), 'desc': desc,
                      'url': self.MAIN_URL + '%s/%s' % (parentSlug or CHANNEL_SHOWS, slug), 'meta_type': 'tv', 'meta_title': title}
            self.addDir(params)
            return True
        except Exception:
            printExc()
        return False

    def _addVideo(self, cItem, item, withShow=True):
        try:
            if not isinstance(item, dict) or item.get('type') != 'video' or not item.get('id'):
                return False
            title = self.cleanHtmlStr(item.get('title') or '')
            show = item.get('show') or {}
            sTitle = self.cleanHtmlStr(show.get('title') or cItem.get('s_title') or '')
            videoType = (item.get('videoType') or '').upper()
            season = self._toInt(item.get('seasonNumber'))
            episode = self._toInt(item.get('episodeNumber'))
            isFilm = bool(cItem.get('is_film'))
            label = title
            if withShow and sTitle and sTitle.lower() not in title.lower():
                label = '%s - %s' % (sTitle, title)
            elif not withShow and videoType == 'EPISODE' and episode and not isFilm:
                label = '%s %d: %s' % (_('Episode'), episode, title) if title else '%s %d' % (_('Episode'), episode)
            params = {'name': 'category', 'type': 'video', 'good_for_fav': True, 'video_id': str(item['id']),
                      'icon': self._img(self._mediaUrl(item.get('poster'))) or cItem.get('icon', ''),
                      # the downloaded marker is keyed on the url: the same in every list (new episodes,
                      # home rows, the show's seasons) - the show slug is not known everywhere
                      'url': '%svideo/%s' % (self.MAIN_URL, item['id'])}
            if sTitle:
                params.update({'s_title': sTitle, 'meta_type': 'tv', 'meta_title': sTitle})
            if isFilm:
                # a film has one video; its name is the film page's (German) title
                filmTitle = self.cleanHtmlStr(cItem.get('s_title') or '') or sTitle or title
                params.update({'meta_type': 'movie', 'meta_title': filmTitle})
                params['title'] = filmTitle if IsMediaNamingNormalized() else label
            elif videoType == 'EPISODE' and season and episode:
                params.update({'season': str(season), 'episode': str(episode)})
                # built here, not by normalizeMediathekTitle: show titles contain " - " themselves
                # ("110 Hannover - Im Visier der Polizei")
                if sTitle and IsMediaNamingNormalized():
                    params['title'] = '%s - %s' % (sTitle, formatSxxExx(season, episode)) + (' - %s' % title if title else '')
                else:
                    params['title'] = label
            else:
                params['title'] = label
            duration = self._duration(item.get('videoDuration'))
            released = self._date(item.get('publishStart'))
            rating = (item.get('contentRating') or {}).get('code')
            ageLimit = '%s+' % rating if str(rating).isdigit() else ''  # like the ZDF host: "12+" (also "0+")
            head = []
            if videoType == 'EPISODE' and season and episode and not isFilm:
                head.append('%s %d, %s %d' % (_('Season'), season, _('Episode'), episode))
            for part in (duration, released, ageLimit):
                if part:
                    head.append(part)
            descText = self.cleanHtmlStr(item.get('description') or '')
            params['desc'] = '[/br]'.join([x for x in (' | '.join(head), descText) if x])
            params.update({'duration': duration, 'released': released, 'age_limit': ageLimit})
            self.addVideo(params)
            return True
        except Exception:
            printExc()
        return False

    ###################################################
    # lists
    ###################################################
    def listHome(self, cItem):
        # the home page or a CHANNEL_PAGES page: its rows (playlist, show collections, carousel, clips)
        data = self._page(cItem.get('page_slug') or 'homepage')
        clips = []
        for idx, block in enumerate(data.get('blocks') or []):
            try:
                btype = block.get('type', '')
                title = self.cleanHtmlStr(block.get('title') or '')
                items = block.get('items')
                if btype == 'sonicVideoBlock':
                    if isinstance(block.get('item'), dict):
                        clips.append(block['item'])
                    continue
                if not title or not isinstance(items, list) or not items:
                    continue
                if btype == 'sonicPlaylistBlock':
                    kind = 'videos'
                elif btype in ('collectionBlock', 'heroBlock') and any(isinstance(it, dict) and it.get('pageType') == 'showpage' and it.get('urlType') != 'external' for it in items):
                    kind = 'shows'
                else:
                    continue
                if btype == 'heroBlock':
                    title = _('Highlights')  # the CMS name of the carousel ("New Hero")
                params = dict(cItem)
                params.update({'category': 'list_home_block', 'title': title, 'block_idx': idx, 'block_kind': kind,
                               'block_uid': block.get('uid', ''), 'good_for_fav': False})
                self.addDir(params)
            except Exception:
                printExc()
        if clips:
            params = dict(cItem)
            params.update({'category': 'list_home_block', 'title': _('Clips'), 'block_kind': 'clips', 'good_for_fav': False})
            self.addDir(params)
        if cItem.get('page_slug') and len(self.currList) == 1:
            # a page with one row only ("Unsere Filme:") - open it right away
            row = self.currList.pop()
            self.listHomeBlock(row)

    def listHomeBlock(self, cItem):
        data = self._page(cItem.get('page_slug') or 'homepage')
        blocks = data.get('blocks') or []
        kind = cItem.get('block_kind', '')
        if kind == 'clips':
            for block in blocks:
                if block.get('type') == 'sonicVideoBlock':
                    self._addVideo(cItem, block.get('item'))
            return
        block = None
        for idx, it in enumerate(blocks):
            # the uid survives a reordering of the home page, the index is the fallback
            if cItem.get('block_uid') and it.get('uid') == cItem['block_uid']:
                block = it
                break
            if not cItem.get('block_uid') and idx == cItem.get('block_idx', -1):
                block = it
                break
        if not block:
            return
        for item in (block.get('items') or []):
            if kind == 'videos':
                self._addVideo(cItem, item)
            else:
                if isinstance(item, dict) and item.get('type') == 'heroElementBlock':
                    item = self._heroToShow(item)
                self._addShow(cItem, item)

    @staticmethod
    def _heroToShow(item):
        # the teaser carousel: the show is in link.url ("sendungen/<slug>")
        link = item.get('link') or {}
        path = (link.get('url') or '').strip('/') if link.get('type') == 'internal' else ''
        if not path or '://' in path:
            return {}
        parent, slug = path.rsplit('/', 1) if '/' in path else ('', path)
        return {'type': 'collectionItemBlock', 'pageType': item.get('pageType') or 'showpage', 'url': slug, 'parentUrl': parent,
                'title': item.get('title') or link.get('title') or '', 'image': item.get('image'),
                'articleContent': item.get('description') or ''}

    def listNewEpisodes(self, cItem):
        data = self._page('homepage')
        for block in (data.get('blocks') or []):
            if block.get('type') == 'sonicPlaylistBlock':
                for item in (block.get('items') or []):
                    self._addVideo(cItem, item)
                return

    def listShows(self, cItem):
        data = self._page(CHANNEL_SHOWS)
        shows = []
        for block in (data.get('blocks') or []):
            if block.get('type') == 'categoryCollectionBlock':
                shows.extend([it for it in (block.get('items') or []) if isinstance(it, dict)])
        shows.sort(key=lambda it: (it.get('title') or '').lower())
        for item in shows:
            self._addShow(cItem, item)

    def _showData(self, cItem):
        data = self._page(cItem.get('slug', ''), cItem.get('parent_slug', ''))
        episodes, clips, header = [], [], {}
        for block in (data.get('blocks') or []):
            btype = block.get('type', '')
            if btype == 'showHeaderBlock':
                header = block.get('show') or {}
            elif btype == 'sonicShowBlock':
                for item in (block.get('items') or []):
                    if not isinstance(item, dict):
                        continue
                    if (item.get('videoType') or '').upper() == 'EPISODE':
                        episodes.append(item)
                    else:
                        clips.append(item)
            elif btype == 'sonicVideoBlock' and isinstance(block.get('item'), dict):
                clips.append(block['item'])
        seen = set(e.get('id') for e in episodes)
        uniq, standalone = [], []
        for item in clips:
            if item.get('id') not in seen:
                seen.add(item.get('id'))
                (standalone if (item.get('videoType') or '').upper() == 'STANDALONE' else uniq).append(item)
        if episodes:
            # specials of a series (DMAX "Expedition X") go with the clips
            uniq = standalone + uniq
        elif standalone:
            # a film (TELE 5) is the one STANDALONE video of its page; several of them (TLC "Ghost
            # Adventures") are the show's videos
            episodes = standalone
        if self._isFilm(data, header) or (len(standalone) == 1 and episodes == standalone):
            cItem['is_film'] = True
        return data, header, episodes, uniq

    def listShow(self, cItem):
        cItem = dict(cItem)
        data, header, episodes, clips = self._showData(cItem)
        if not data:
            return
        seasons = {}
        for item in episodes:
            seasons.setdefault(self._toInt(item.get('seasonNumber')), []).append(item)
        icon = self._img(self._mediaUrl(header.get('image'))) or cItem.get('icon', '')
        sTitle = cItem.get('s_title') or cItem.get('title', '')
        if (len(seasons) == 1 and not clips) or (cItem.get('is_film') and episodes):
            # one season, or a film: its video right here (the trailers of a film stay in "Clips")
            self._listEpisodes(cItem, episodes)
            seasons = {}
        if not seasons and not clips and self.currList:
            return
        for num in sorted(seasons.keys()):
            params = dict(cItem)
            params.update({'category': 'list_season', 'title': ('%s %d' % (_('Season'), num)) if num else _('Episodes'),
                           'season': str(num), 's_title': sTitle, 'icon': icon, 'good_for_fav': True,
                           'desc': '%d %s' % (len(seasons[num]), _('Episodes'))})
            self.addDir(params)
        if clips:
            params = dict(cItem)
            params.update({'category': 'list_show_clips', 'title': _('Clips'), 's_title': sTitle, 'icon': icon,
                           'good_for_fav': False, 'desc': ''})
            self.addDir(params)
        if not seasons and not clips:
            # nothing online yet / any more (TELE 5 films): add the site's window "Online 25.10. - 24.11."
            tunein = self.cleanHtmlStr((data.get('attributes') or {}).get('tuneinInfo') or '')
            SetIPTVPlayerLastHostError('%s\n%s' % (_('No stream available'), tunein) if tunein else _('No stream available'))

    def _listEpisodes(self, cItem, items):
        items = sorted(items, key=lambda it: (self._toInt(it.get('seasonNumber')), self._toInt(it.get('episodeNumber'))))
        for item in items:
            self._addVideo(cItem, item, withShow=False)

    def listSeason(self, cItem):
        cItem = dict(cItem)
        _data, _header, episodes, _clips = self._showData(cItem)
        num = self._toInt(cItem.get('season'))
        self._listEpisodes(cItem, [it for it in episodes if self._toInt(it.get('seasonNumber')) == num])

    def listShowClips(self, cItem):
        cItem = dict(cItem)
        _data, _header, _episodes, clips = self._showData(cItem)
        for item in clips:
            self._addVideo(cItem, item, withShow=False)

    def listSearchResult(self, cItem, searchPattern, searchType):
        page = max(1, self._toInt(cItem.get('page', 1)))
        url = '%ssearch/page/?%s&q=%s&page[number]=%d&page[size]=%d' % (self.SITE_API, self.SITE_QUERY, urllib_quote_plus(searchPattern),
                                                                       page, self.SEARCH_PAGE_SIZE)
        data = self._json(url)
        if not isinstance(data, dict):
            return
        items = data.get('data') or []
        for item in items:
            self._addShow(cItem, item)
        # the search also finds the site's articles (DIY tips ...), always after the shows: a page that
        # has one is the last one with shows - no "Next page" into pages of articles only
        onlyShows = all(isinstance(it, dict) and it.get('type') == 'showpage' for it in items)
        meta = data.get('meta') or {}
        hasNext = bool(meta.get('nextPage')) and bool(items) and onlyShows
        addPagingItems(self, cItem, page, hasNext, self._toInt(meta.get('totalPages')) if hasNext else 0,
                       '%ssearch/?q=%s&page={page}' % (self.MAIN_URL, urllib_quote_plus(searchPattern)))

    ###################################################
    # links
    ###################################################
    def _getSonicToken(self, refresh=False):
        if self.sonicToken and not refresh:
            return self.sonicToken
        data = self._json('%stoken?realm=%s' % (self.SONIC_API, self.SONIC_REALM))
        try:
            self.sonicToken = data['data']['attributes']['token']
        except Exception:
            printExc()
            self.sonicToken = ''
        return self.sonicToken

    def _playbackInfo(self, videoId):
        for attempt in (0, 1):
            token = self._getSonicToken(refresh=bool(attempt))
            if not token:
                return {}
            header = dict(self.HEADER)
            header.update({'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
            # 4xx answers carry the reason (geo block, expired token) as JSON
            params = {'header': header, 'raw_post_data': True, 'ignore_http_code_ranges': [(400, 499)]}
            data = self._json(self.SONIC_API + 'playback/v3/videoPlaybackInfo', params, json_dumps({'videoId': str(videoId)}))
            if not isinstance(data, dict):
                return {}
            errors = data.get('errors') or []
            if errors and not attempt and str(errors[0].get('status', '')) == '401':
                continue
            return data
        return {}

    def getLinksForVideo(self, cItem):
        printDBG('WBDMediathek.getLinksForVideo [%s]' % cItem.get('video_id', ''))
        videoId = cItem.get('video_id', '')
        if not videoId:
            return []
        data = self._playbackInfo(videoId)
        errors = data.get('errors') or []
        if errors:
            err = errors[0] if isinstance(errors[0], dict) else {}
            printDBG('WBDMediathek.getLinksForVideo error %s' % err)
            if 'geoblocked' in (err.get('code') or ''):
                SetIPTVPlayerLastHostError(_('Not available in your country (geo-blocking).'))
            else:
                SetIPTVPlayerLastHostError(err.get('detail') or _('No stream available'))
            return []
        streams = ((data.get('data') or {}).get('attributes') or {}).get('streaming') or []
        hls = [s for s in streams if isinstance(s, dict) and s.get('type') == 'hls' and s.get('url')]
        if not hls:
            SetIPTVPlayerLastHostError(_('No stream available'))
            return []
        protection = hls[0].get('protection') or {}
        if protection.get('drmEnabled'):
            SetIPTVPlayerLastHostError(_('Video with DRM protection.'))
            return []
        master = hls[0]['url']
        meta = {'User-Agent': self.HEADER['User-Agent'], 'Referer': self.MAIN_URL, 'Origin': self.MAIN_URL[:-1], 'iptv_proto': 'm3u8'}
        urlTab = []
        # the variant TS segments are video only - the sound is the separate AUDIO group -> merge://
        # (one link per audio rendition: TLC / HGTV have German + English, both flagged DEFAULT)
        links = getDirectM3U8Playlist(strwithmeta(master, meta), checkExt=False, checkContent=True, mergeAltAudio=True)
        langs = set()
        for link in links:
            link['need_resolve'] = 0
            name = link.get('name', '')
            link['audio_lang'] = name[1:name.index(']')] if name.startswith('[') and ']' in name else ''
            langs.add(link['audio_lang'])
        for link in links:
            if link.get('height'):
                link['name'] = '%sp (%s kbps)' % (link['height'], int(link.get('bitrate', 0) or 0) // 1000)
                if len(langs) > 1 and link['audio_lang']:
                    link['name'] = '[%s] %s' % (link['audio_lang'], link['name'])
        links.sort(key=lambda it: (0 if self._isGerman(it['audio_lang']) else 1, -self._toInt(it.get('height')),
                                   -self._toInt(it.get('bitrate'))))
        urlTab.extend(links)
        # the master itself: the player picks video + audio (gstplayer cannot play merge://)
        urlTab.append({'name': 'HLS auto (master)', 'url': strwithmeta(master, meta), 'need_resolve': 0})
        # the helper takes the text from the item's desc itself (passing it again doubled it)
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    ###################################################
    # info / favourites
    ###################################################
    def getArticleContent(self, cItem):
        printDBG('WBDMediathek.getArticleContent [%s]' % cItem.get('slug', ''))
        otherInfo = {'station': CHANNEL_NAME}
        text = ''
        icon = cItem.get('icon', '')
        if cItem.get('type') == 'video':
            for key in ('duration', 'released', 'age_limit'):
                if cItem.get(key):
                    otherInfo[key] = cItem[key]
            desc = cItem.get('desc', '')
            # the first line of the list description is the season/duration/date head
            text = self.cleanHtmlStr(desc.split('[/br]', 1)[1] if '[/br]' in desc else desc)
        elif cItem.get('slug'):
            cItem = dict(cItem)
            data, header, episodes, _clips = self._showData(cItem)
            text = self.cleanHtmlStr(header.get('description') or data.get('articleContent') or '') or self.cleanHtmlStr(cItem.get('desc', ''))
            icon = self._img(self._mediaUrl(header.get('poster') or header.get('image'))) or icon
            if cItem.get('is_film'):
                cItem.update({'meta_type': 'movie', 'meta_title': cItem.get('s_title') or cItem.get('title', '')})
            else:
                seasons = set(self._toInt(it.get('seasonNumber')) for it in episodes)
                if seasons:
                    otherInfo['seasons'] = str(len(seasons))
                if episodes:
                    otherInfo['episodes'] = str(len(episodes))
            genres = [t.get('title') for t in (header.get('taxonomies') or [])
                      if isinstance(t, dict) and t.get('category') == 'genre' and t.get('title') and (t.get('slug') or '').lower() not in self.FILM_TAXONOMIES]
            if genres:
                otherInfo['genres'] = ', '.join(genres)
        meta = {}
        if cItem.get('meta_type') and cItem.get('meta_title'):
            try:
                meta = getMeta(cItem['meta_type'], cItem['meta_title'])
            except Exception:
                printExc()
        # the site's German texts first, the service adds ratings, cast and the poster
        for key, value in (meta.get('info') or {}).items():
            otherInfo.setdefault(key, value)
        text = text or meta.get('plot', '')
        icon = icon or meta.get('poster', '')
        return [{'title': cItem.get('title', ''), 'text': text,
                 'images': [{'title': '', 'url': icon}] if icon else [], 'other_info': otherInfo}]

    def getFavouriteData(self, cItem):
        try:
            if cItem.get('video_id') or cItem.get('slug'):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('WBDMediathek.handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get('name', None)
        category = self.currItem.get('category', '')
        searchPattern = self.currItem.get('search_pattern', searchPattern)
        printDBG('WBDMediathek.handleService: name[%s] category[%s]' % (name, category))
        self.currList = []

        if name is None:
            tab = [{'category': 'list_home', 'title': _('Home page')}]
            if CHANNEL_NEW_EPISODES:
                tab.append({'category': 'list_new', 'title': _('New episodes')})
            for title, slug in CHANNEL_PAGES:
                tab.append({'category': 'list_home', 'title': _(title), 'page_slug': slug})
            tab += [{'category': 'list_shows', 'title': _('All shows')}] + self.searchItems()
            self.listsTab(tab, {'name': 'category'})
        elif category == 'list_home':
            self.listHome(self.currItem)
        elif category == 'list_home_block':
            self.listHomeBlock(self.currItem)
        elif category == 'list_new':
            self.listNewEpisodes(self.currItem)
        elif category == 'list_shows':
            self.listShows(self.currItem)
        elif category == 'list_show':
            self.listShow(self.currItem)
        elif category == 'list_season':
            self.listSeason(self.currItem)
        elif category == 'list_show_clips':
            self.listShowClips(self.currItem)
        elif category in ('search', 'search_next_page'):
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category', 'category': 'search_next_page', 'search_pattern': searchPattern})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == 'search_history':
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _('Type: '))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, WBDMediathek(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper(CHANNEL_KEY)

    def withArticleContent(self, cItem):
        return bool(cItem.get('video_id') or cItem.get('slug'))
