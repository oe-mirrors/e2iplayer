# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# Based on techdealer-xbmc.googlecode.com/svn/trunk/plugin.audio.musicbox/
# Music charts (iTunes by country, Beatport Top 100, Billboard, the Last.fm user's tracks) played through YouTube
#   (the first YouTube search hit for "artist title", or the YouTube Data API with an own API key).
# 08.10.2026 - host standard: Beatport from the site's page data (pro.beatport.com is gone), Billboard parser for
#   the current chart pages (dead charts dropped, Global 200 added), Last.fm "My list" with the user's loved / top /
#   recent tracks with the API's pages (the playlist API was removed), track rows keyed on a stable song url (watched flag
#   album -> track, downloaded marker, favourites), "Artist - Title" naming, local pages for charts > 100,
#   INFO with the chart / album data, sidecar, current user agent, English labels
# 09.10.2026 - Billboard albums Last.fm does not know (new EPs, soundtracks): tracks from the matching iTunes album
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, GetIPTVNotify, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.components.configsecret import ConfigLogin, ConfigSecret
from Plugins.Extensions.IPTVPlayer.libs.youtubeparser import YouTubeParser
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str_deep
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus, urllib_unquote_plus
from Components.config import config, getConfigListEntry, ConfigYesNo
###################################################
# FOREIGN import
###################################################
import re
####################################################
# Config options for HOST
####################################################
config.plugins.iptvplayer.MusicBox_login = ConfigLogin(default="", fixed_size=False)
config.plugins.iptvplayer.api_key_youtube = ConfigSecret(default="", fixed_size=False)
config.plugins.iptvplayer.api_key_warning = ConfigYesNo(default=True)

audioscrobbler_api_key = "d49b72ffd881c2cb13b4595e67005ac4"
LOCAL_PAGE_SIZE = 100
YT_SEARCH = 'https://www.youtube.com/results?search_query='
LASTFM_API = 'https://ws.audioscrobbler.com/2.0/?format=json&api_key=' + audioscrobbler_api_key + '&method='
LASTFM_NO_IMAGE = '2a96cbd8b46e442fc41c2b86b821562f'  # Last.fm's grey star placeholder

ITUNES_COUNTRIES = [("Argentina", "ar"), ("Armenia", "am"), ("Australia", "au"), ("Austria", "at"), ("Azerbaijan", "az"), ("Bahamas", "bs"), ("Bahrain", "bh"),
                    ("Barbados", "bb"), ("Belarus", "by"), ("Belgium", "be"), ("Belize", "bz"), ("Bermuda", "bm"), ("Bolivia", "bo"), ("Botswana", "bw"),
                    ("Brazil", "br"), ("British Virgin Islands", "vg"), ("Brunei Darussalam", "bn"), ("Bulgaria", "bg"), ("Burkina Faso", "bf"),
                    ("Cambodia", "kh"), ("Canada", "ca"), ("Cape Verde", "cv"), ("Cayman Islands", "ky"), ("Chile", "cl"), ("Colombia", "co"),
                    ("Costa Rica", "cr"), ("Croatia", "hr"), ("Cyprus", "cy"), ("Czech Republic", "cz"), ("Denmark", "dk"), ("Dominica", "dm"),
                    ("Dominican Republic", "do"), ("Ecuador", "ec"), ("Egypt", "eg"), ("El Salvador", "sv"), ("Estonia", "ee"), ("Fiji", "fj"),
                    ("Finland", "fi"), ("France", "fr"), ("Gambia", "gm"), ("Germany", "de"), ("Ghana", "gh"), ("Greece", "gr"), ("Grenada", "gd"),
                    ("Guatemala", "gt"), ("Guinea-Bissau", "gw"), ("Honduras", "hn"), ("Hong Kong", "hk"), ("Hungary", "hu"), ("India", "in"),
                    ("Indonesia", "id"), ("Ireland", "ie"), ("Israel", "il"), ("Italy", "it"), ("Japan", "jp"), ("Jordan", "jo"), ("Kazakhstan", "kz"),
                    ("Kenya", "ke"), ("Kyrgyzstan", "kg"), ("Lao, People's Democratic Republic", "la"), ("Latvia", "lv"), ("Lebanon", "lb"),
                    ("Lithuania", "lt"), ("Luxembourg", "lu"), ("Macau", "mo"), ("Malaysia", "my"), ("Malta", "mt"), ("Mauritius", "mu"), ("Mexico", "mx"),
                    ("Micronesia, Federated States of", "fm"), ("Moldova", "md"), ("Mongolia", "mn"), ("Mozambique", "mz"), ("Namibia", "na"),
                    ("Nepal", "np"), ("Netherlands", "nl"), ("New Zealand", "nz"), ("Nicaragua", "ni"), ("Niger", "ne"), ("Nigeria", "ng"), ("Norway", "no"),
                    ("Oman", "om"), ("Panama", "pa"), ("Papua New Guinea", "pg"), ("Paraguay", "py"), ("Peru", "pe"), ("Philippines", "ph"),
                    ("Poland", "pl"), ("Portugal", "pt"), ("Qatar", "qa"), ("Romania", "ro"), ("Russia", "ru"), ("Saudi Arabia", "sa"), ("Singapore", "sg"),
                    ("Slovakia", "sk"), ("Slovenia", "si"), ("South Africa", "za"), ("Spain", "es"), ("Sri Lanka", "lk"), ("St. Kitts and Nevis", "kn"),
                    ("Swaziland", "sz"), ("Sweden", "se"), ("Switzerland", "ch"), ("Taiwan", "tw"), ("Tajikistan", "tj"), ("Thailand", "th"),
                    ("Trinidad and Tobago", "tt"), ("Turkey", "tr"), ("Turkmenistan", "tm"), ("Uganda", "ug"), ("Ukraine", "ua"),
                    ("United Arab Emirates", "ae"), ("United Kingdom", "gb"), ("United States", "us"), ("Uzbekistan", "uz"), ("Venezuela", "ve"),
                    ("Vietnam", "vn"), ("Zimbabwe", "zw")]

# (title, chart slug, album chart)
BILLBOARD_CHARTS = [("Billboard - The Hot 100", "hot-100", False), ("Billboard - 200", "billboard-200", True),
                    ("Billboard - Global 200", "billboard-global-200", False), ("Billboard - Hot Pop Songs", "pop-songs", False),
                    ("Billboard - Hot Country Songs", "country-songs", False), ("Billboard - Hot Country Albums", "country-albums", True), ("Billboard - Hot Rock Songs", "rock-songs", False),
                    ("Billboard - Hot Rock Albums", "rock-albums", True), ("Billboard - Hot R&B/Hip-Hop Songs", "r-b-hip-hop-songs", False),
                    ("Billboard - Hot R&B/Hip-Hop Albums", "r-b-hip-hop-albums", True), ("Billboard - Hot Dance/Electronic Songs", "dance-electronic-songs", False),
                    ("Billboard - Hot Dance/Electronic Albums", "dance-electronic-albums", True), ("Billboard - Hot Latin Songs", "latin-songs", False),
                    ("Billboard - Hot Latin Albums", "latin-albums", True)]

# category names of the menu folders before 08.10.2026 (favourites)
LEGACY_NAMES = {'Itunes_track_charts': 'itunes_songs', 'Itunes_album_charts': 'itunes_albums', 'Itunes_list_album_tracks': 'itunes_album',
                'List_album_tracks': 'lastfm_album'}


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry('https://youtube.com/ ' + _("API Key"), config.plugins.iptvplayer.api_key_youtube))
    optionList.append(getConfigListEntry(_("Show Youtube Api Key warnings"), config.plugins.iptvplayer.api_key_warning))
    optionList.append(getConfigListEntry(_("Last.fm user name:"), config.plugins.iptvplayer.MusicBox_login))
    return optionList


def gettytul():
    return 'Music-Box'


class MusicBox(GenericFolderWatchedScraperMixin, CBaseHostClass):

    TRACK_FIELDS = ('name', 'category', 'type', 'url', 'title', 'raw_title', 'icon', 'desc', 'artist', 'track', 'album', 'genre', 'released', 'duration')

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'musicbox', 'cookie': 'musicbox.cookie'})
        self.youtube_api_key = ""
        self.DEFAULT_ICON_URL = ''  # old default image host is gone
        self.HEADER = {'User-Agent': self.cm.getDefaultUserAgent(), 'Accept': 'text/html,application/json,*/*'}
        self.defaultParams = {'header': self.HEADER}
        self.watchedHelper = IPTVWatchedHelper('musicbox')
        self.wfInitFolderCache()

    ###################################################
    # watched flag / favourites
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ''
            if cItem.get('type') == 'video' and cItem.get('url', '').startswith(YT_SEARCH):
                return 'video:%s' % cItem['url']
            if cItem.get('type') == 'category' and cItem.get('category') in ('itunes_album', 'lastfm_album') and cItem.get('url'):
                return 'folder:%s' % cItem['url']
        except Exception:
            printExc()
        return ''

    def getFavouriteData(self, cItem):
        try:
            if cItem.get('type') == 'video':
                return json_dumps(dict((key, cItem[key]) for key in self.TRACK_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    def _getJson(self, url):
        sts, data = self.getPage(url)
        if not sts:
            return None
        try:
            return ensure_str_deep(json_loads(data))
        except Exception:
            printExc()
        return None

    def readYoutubeApiKey(self):
        if self.youtube_api_key != config.plugins.iptvplayer.api_key_youtube.value:
            apiKey = config.plugins.iptvplayer.api_key_youtube.value
            if len(apiKey) > 0 and len(apiKey) != 39:
                if config.plugins.iptvplayer.api_key_warning.value is True:
                    msg = _("Wrong Youtube Api Key length")
                    GetIPTVNotify().push(msg, 'error', 5)
            self.youtube_api_key = apiKey

        if not self.youtube_api_key:
            if config.plugins.iptvplayer.api_key_warning.value is True:
                config.plugins.iptvplayer.api_key_warning.value = False
                msg = _("Youtube searches are quicker, if you fill API key in setting menu")
                msg = msg + "\n" + ("Search for 'how to create your own Youtube api key'")
                GetIPTVNotify().push(msg, 'info', 5)

    ###################################################
    # rows
    ###################################################
    def _addTrack(self, artist, track, rank='', icon='', info=None, album='', genre='', released='', duration=''):
        artist = self.cleanHtmlStr(artist)
        track = self.cleanHtmlStr(track)
        if not track:
            return
        name = '%s - %s' % (artist, track) if artist else track
        rawTitle = '%s. %s' % (rank, name) if rank else name
        title = name if IsMediaNamingNormalized() else rawTitle
        desc = [x for x in (artist, album, genre, released, duration) if x]
        desc = ' | '.join(desc)
        if info:
            desc = (desc + '[/br]' if desc else '') + ' | '.join(info)
        # the YouTube search of the song is its stable identity (watched flag, downloaded marker, favourites)
        url = YT_SEARCH + urllib_quote_plus(('%s %s' % (artist, track)).strip())
        self.addVideo({'good_for_fav': True, 'title': title, 'raw_title': rawTitle, 'url': url, 'icon': icon, 'desc': desc, 'artist': artist,
                       'track': track, 'album': album, 'genre': genre, 'released': released, 'duration': duration})

    def _localPage(self, cItem, rows):
        # charts with more than LOCAL_PAGE_SIZE rows are shown in local pages
        try:
            page = max(1, int(cItem.get('page', 1) or 1))
        except (TypeError, ValueError):
            page = 1
        lastPage = (len(rows) + LOCAL_PAGE_SIZE - 1) // LOCAL_PAGE_SIZE
        if lastPage > 1:
            rows = rows[(page - 1) * LOCAL_PAGE_SIZE:page * LOCAL_PAGE_SIZE]
        return rows, page, lastPage

    def _addLocalPager(self, cItem, page, lastPage):
        if lastPage > 1:
            tpl = cItem.get('url', '').replace('{', '%7B').replace('}', '%7D') or 'musicbox'
            addPagingItems(self, dict(cItem, desc=''), page, page < lastPage, lastPage, tpl)

    @staticmethod
    def _duration(secs):
        try:
            secs = int(secs or 0)
        except (TypeError, ValueError):
            secs = 0
        return '%d:%02d' % (secs // 60, secs % 60) if secs > 0 else ''

    ###################################################
    # menus
    ###################################################
    def listsMainMenu(self):
        printDBG("MusicBox - lists main menu")
        self.addDir({'name': 'category', 'category': 'itunes', 'item': 'song', 'title': _("iTunes - Top songs by country")})
        self.addDir({'name': 'category', 'category': 'itunes', 'item': 'album', 'title': _("iTunes - Top albums by country")})
        self.addDir({'name': 'category', 'category': 'beatport', 'title': "Beatport - Top 100", 'url': 'https://www.beatport.com/top-100', 'good_for_fav': True})
        for title, slug, albums in BILLBOARD_CHARTS:
            self.addDir({'name': 'category', 'category': 'billboard_albums' if albums else 'billboard_charts', 'title': title,
                         'url': 'https://www.billboard.com/charts/%s/' % slug, 'good_for_fav': True})
        if config.plugins.iptvplayer.MusicBox_login.value.strip():
            self.addDir({'name': 'category', 'category': 'lastfm', 'title': "Last.fm - " + _("My list")})

    ###################################################
    # iTunes
    ###################################################
    def listItunesCountries(self, cItem):
        printDBG('MusicBox - Itunes countries menu')
        category = 'itunes_songs' if cItem.get('item') == 'song' else 'itunes_albums'
        for title, code in ITUNES_COUNTRIES:
            self.addDir({'name': 'category', 'category': category, 'good_for_fav': True, 'title': title, 'country': code,
                         'url': 'https://itunes.apple.com/%s/rss/%s/limit=100/explicit=true/json' % (code, 'topsongs' if category == 'itunes_songs' else 'topalbums'),
                         'icon': 'https://www.geonames.org/flags/x/%s.gif' % code, 'desc': title})

    def _itunesEntries(self, cItem, kind):
        country = cItem.get('country', '') or cItem.get('page', '')
        data = self._getJson('https://itunes.apple.com/%s/rss/%s/limit=100/explicit=true/json' % (country, kind))
        try:
            entries = data['feed']['entry']
            return entries if isinstance(entries, list) else [entries]
        except Exception:
            SetIPTVPlayerLastHostError(_('No matching entries found.'))
        return []

    @staticmethod
    def _label(item, *keys):
        try:
            for key in keys:
                item = item[key]
            return item if isinstance(item, str) else ''
        except Exception:
            return ''

    def listItunesSongs(self, cItem):
        printDBG('MusicBox - Itunes track charts')
        for idx, item in enumerate(self._itunesEntries(cItem, 'topsongs')):
            try:
                images = item.get('im:image') or []
                self._addTrack(self._label(item, 'im:artist', 'label'), self._label(item, 'im:name', 'label'), str(idx + 1),
                               images[-1]['label'] if images else '', album=self.cleanHtmlStr(self._label(item, 'im:collection', 'im:name', 'label')),
                               genre=self._label(item, 'category', 'attributes', 'label'), released=self._label(item, 'im:releaseDate', 'label')[:10])
            except Exception:
                printExc()

    def listItunesAlbums(self, cItem):
        printDBG('MusicBox - Itunes album charts')
        country = cItem.get('country', '') or cItem.get('page', '')
        for idx, item in enumerate(self._itunesEntries(cItem, 'topalbums')):
            try:
                artist = self.cleanHtmlStr(self._label(item, 'im:artist', 'label'))
                album = self.cleanHtmlStr(self._label(item, 'im:name', 'label'))
                albumId = self._label(item, 'id', 'attributes', 'im:id')
                if not albumId or not album:
                    continue
                images = item.get('im:image') or []
                genre = self._label(item, 'category', 'attributes', 'label')
                released = self._label(item, 'im:releaseDate', 'label')[:10]
                rawTitle = '%s. %s - %s' % (idx + 1, artist, album)
                self.addDir({'name': 'category', 'category': 'itunes_album', 'good_for_fav': True,
                             'title': '%s - %s' % (artist, album) if IsMediaNamingNormalized() else rawTitle,
                             'url': 'https://itunes.apple.com/lookup?id=%s&country=%s&entity=song&limit=200' % (albumId, country),
                             'artist': artist, 'album': album, 'genre': genre, 'released': released,
                             'icon': images[-1]['label'] if images else '', 'desc': ' | '.join([x for x in (artist, genre, released) if x])})
            except Exception:
                printExc()

    def listItunesAlbumTracks(self, cItem):
        printDBG('MusicBox - Itunes album tracks')
        url = cItem.get('url', '')
        if not url.startswith('https://itunes.apple.com/lookup'):
            url = 'https://itunes.apple.com/lookup?id=%s&country=%s&entity=song&limit=200' % (cItem.get('page', ''), cItem.get('country', ''))
        data = self._getJson(url)
        try:
            for item in data['results']:
                if item.get('wrapperType') != 'track':
                    continue
                self._addTrack(item.get('artistName', ''), item.get('trackName', ''), icon=item.get('artworkUrl100', '') or cItem.get('icon', ''),
                               album=self.cleanHtmlStr(item.get('collectionName', '')), genre=item.get('primaryGenreName', ''),
                               released=(item.get('releaseDate') or '')[:10], duration=self._duration((item.get('trackTimeMillis') or 0) // 1000))
        except Exception:
            printExc()

    ###################################################
    # Beatport
    ###################################################
    def listBeatport(self, cItem):
        printDBG('MusicBox - beatport top 100')
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        try:
            data = self.cm.ph.getSearchGroups(data, r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>')[0]
            data = ensure_str_deep(json_loads(data))
            results = []
            for query in data['props']['pageProps']['dehydratedState']['queries']:
                qData = query.get('state', {}).get('data', {})
                if isinstance(qData, dict) and isinstance(qData.get('results'), list):
                    results = qData['results']
                    break
            for idx, item in enumerate(results):
                artist = ', '.join([a.get('name', '') for a in item.get('artists') or [] if isinstance(a, dict)])
                track = item.get('name', '')
                if item.get('mix_name'):
                    track += ' (%s)' % item['mix_name']
                release = item.get('release') or {}
                icon = ((release.get('image') or {}).get('dynamic_uri') or '').replace('{w}x{h}', '250x250')
                info = []
                if item.get('bpm'):
                    info.append('%s BPM' % item['bpm'])
                if (item.get('key') or {}).get('name'):
                    info.append(item['key']['name'])
                if (release.get('label') or {}).get('name'):
                    info.append(release['label']['name'])
                self._addTrack(artist, track, str(idx + 1), icon, info, album=release.get('name', ''), genre=(item.get('genre') or {}).get('name', ''),
                               released=item.get('publish_date') or '', duration=item.get('length') or '')
        except Exception:
            printExc()

    ###################################################
    # Billboard
    ###################################################
    def _billboardRows(self, cItem):
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return [], ''
        week = self.cm.ph.getSearchGroups(data, r'(Week of [A-Z][a-z]+ \d+, \d{4})')[0]
        rows = []
        for part in data.split('o-chart-results-list-row-container')[1:]:
            part = part.split('charts-results-item-detail-inner', 1)[0]
            rank = self.cm.ph.getSearchGroups(part, r'<span class="c-label[^"]*"[^>]*>\s*(\d+)\s*</span>')[0]
            m = re.search(r'<h3 id="title-of-a-story"[^>]*>(.*?)</h3>\s*<span[^>]*>(.*?)</span>', part, re.S)
            if not m:
                continue
            icon = self.cm.ph.getSearchGroups(part, r'''<img[^>]+?(?:data-lazy-src|src)="(https://charts-static[^"]+)"''')[0]
            stats = []
            for label, fmt in (('LW', _('Last week: %s')), ('PEAK', _('Peak: %s')), ('WEEKS ON CHART', _('Weeks on chart: %s'))):
                value = self.cm.ph.getSearchGroups(part, r'(?s)>\s*%s\s*</span>.*?<span[^>]*>\s*([^<]+?)\s*</span>' % label)[0]
                if value:
                    stats.append(fmt % value)
            rows.append((rank, self.cleanHtmlStr(m.group(2)), self.cleanHtmlStr(m.group(1)), icon, stats))
        return rows, week

    def listBillboardCharts(self, cItem):
        printDBG("MusicBox - Billboard charts")
        rows, week = self._billboardRows(cItem)
        rows, page, lastPage = self._localPage(cItem, rows)
        for rank, artist, name, icon, stats in rows:
            self._addTrack(artist, name, rank, icon, stats + ([week] if week else []))
        self._addLocalPager(cItem, page, lastPage)

    def listBillboardAlbums(self, cItem):
        printDBG("MusicBox - Billboard charts album")
        rows, week = self._billboardRows(cItem)
        rows, page, lastPage = self._localPage(cItem, rows)
        for rank, artist, album, icon, stats in rows:
            name = '%s - %s' % (artist, album) if artist else album
            self.addDir({'name': 'category', 'category': 'lastfm_album', 'good_for_fav': True,
                         'title': name if IsMediaNamingNormalized() else '%s. %s' % (rank, name),
                         'url': 'https://www.last.fm/music/%s/%s' % (urllib_quote_plus(artist), urllib_quote_plus(album)),
                         'artist': artist, 'album': album, 'icon': icon, 'desc': ' | '.join(stats + ([week] if week else []))})
        self._addLocalPager(cItem, page, lastPage)

    ###################################################
    # Last.fm
    ###################################################
    def _lastfmAlbumInfo(self, cItem):
        if cItem.get('mbid'):
            url = LASTFM_API + 'album.getInfo&mbid=' + urllib_quote(cItem['mbid'])
        else:
            artist, album = cItem.get('artist', ''), cItem.get('album', '')
            if not artist and not album and cItem.get('url', '').startswith('https://www.last.fm/music/'):
                parts = cItem['url'].split('/music/', 1)[1].split('/')
                artist, album = urllib_unquote_plus(parts[0]), urllib_unquote_plus(parts[-1])
            url = LASTFM_API + 'album.getInfo&artist=' + urllib_quote(artist) + '&album=' + urllib_quote(album)
        data = self._getJson(url)
        return data.get('album') if isinstance(data, dict) and isinstance(data.get('album'), dict) else None

    def _lastfmImage(self, images):
        try:
            url = images[-1]['#text']
            return '' if LASTFM_NO_IMAGE in url else url
        except Exception:
            return ''

    @staticmethod
    def _albumKey(name):
        # "WILD (EP)" / "WILD - EP" / "KPop Demon Hunters (Soundtrack from the Netflix Film)" -> "wild" / "kpop demon hunters"
        name = re.sub(r'\s*[\(\[][^\)\]]*[\)\]]', '', name or '')
        name = re.sub(r'\s+-\s+(?:EP|Single)\s*$', '', name, flags=re.I)
        return re.sub(r'\s+', ' ', name).strip().lower()

    def _itunesAlbumLookup(self, artist, album):
        # Billboard albums Last.fm does not know (new EPs, soundtracks): the matching iTunes album's track lookup
        key = self._albumKey(album)
        if not key:
            return ''
        artistTerm = '' if artist.lower() in ('soundtrack', 'various artists') else artist
        data = self._getJson('https://itunes.apple.com/search?entity=album&limit=10&term=' + urllib_quote_plus(('%s %s' % (artistTerm, key)).strip()))
        for item in (data.get('results') or []) if isinstance(data, dict) else []:
            name = self._albumKey(item.get('collectionName', ''))
            if item.get('collectionId') and (name == key or name.startswith(key + ' ')):
                return 'https://itunes.apple.com/lookup?id=%s&entity=song&limit=200' % item['collectionId']
        return ''

    def listLastfmAlbumTracks(self, cItem):
        printDBG("MusicBox - list album tracks")
        album = self._lastfmAlbumInfo(cItem)
        tracks = ((album or {}).get('tracks') or {}).get('track') or []
        # Last.fm placeholder rows ("TBC - track 1", Olivia Rodrigo - Guts in the box log 09.10.2026)
        placeholder = isinstance(tracks, list) and any(
            isinstance(t, dict) and ((t.get('artist') or {}).get('name') == 'TBC' if isinstance(t.get('artist'), dict) else False) for t in tracks)
        if album is None or not isinstance(tracks, list) or len(tracks) < 2 or placeholder:
            lookup = self._itunesAlbumLookup(cItem.get('artist', '') or (album or {}).get('artist', ''), cItem.get('album', '') or (album or {}).get('name', ''))
            if lookup:
                self.listItunesAlbumTracks(dict(cItem, url=lookup))
                if self.currList:
                    return
        if album is None:
            SetIPTVPlayerLastHostError(_('No matching entries found.'))
            return
        try:
            icon = self._lastfmImage(album.get('image')) or cItem.get('icon', '')
            tracks = (album.get('tracks') or {}).get('track') or []
            if isinstance(tracks, dict):
                tracks = [tracks]
            for item in tracks:
                artist = item.get('artist', {}).get('name', '') if isinstance(item.get('artist'), dict) else album.get('artist', '')
                self._addTrack(artist, item.get('name', ''), icon=icon, album=album.get('name', ''), duration=self._duration(item.get('duration')))
        except Exception:
            printExc()
        if not self.currList:
            SetIPTVPlayerLastHostError(_('No matching entries found.'))

    def listLastfmMenu(self, cItem):
        printDBG("MusicBox - last.fm list")
        user = config.plugins.iptvplayer.MusicBox_login.value.strip()
        if not user:
            return
        for method, title in (('user.getLovedTracks', _('Loved tracks')), ('user.getTopTracks', _('Top tracks')), ('user.getRecentTracks', _('Recent'))):
            self.addDir({'name': 'category', 'category': 'lastfm_tracks', 'good_for_fav': True, 'title': '%s: %s' % (user, title),
                         'url': LASTFM_API + method + '&limit=100&user=' + urllib_quote(user), 'list_key': method[8:].lower()})

    def listLastfmTracks(self, cItem):
        printDBG("MusicBox - last.fm tracks")
        try:
            page = max(1, int(cItem.get('page', 1) or 1))
        except (TypeError, ValueError):
            page = 1
        data = self._getJson(cItem['url'] + '&page=%d' % page)
        try:
            data = data[cItem.get('list_key', 'lovedtracks')]
            try:
                lastPage = int((data.get('@attr') or {}).get('totalPages') or 0)
            except (TypeError, ValueError):
                lastPage = 0
            data = data['track']
        except Exception:
            SetIPTVPlayerLastHostError(_('No matching entries found.'))
            return
        if isinstance(data, dict):
            data = [data]
        for item in data:
            try:
                artist = item.get('artist') or {}
                artist = artist.get('name') or artist.get('#text') or ''
                album = (item.get('album') or {}).get('#text', '') if isinstance(item.get('album'), dict) else ''
                self._addTrack(artist, item.get('name', ''), icon=self._lastfmImage(item.get('image')), album=album,
                               released=(item.get('date') or {}).get('#text', '') if isinstance(item.get('date'), dict) else '')
            except Exception:
                printExc()
        if lastPage > 1:
            # the api url stays the folder's url, the page goes into 'page' (no "{page}" in the template)
            addPagingItems(self, dict(cItem, desc=''), page, page < lastPage, lastPage, cItem['url'].replace('{', '%7B').replace('}', '%7D'))

    ###################################################
    # links: the first YouTube video for "artist title"
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("MusicBox.getLinksForVideo [%s]" % cItem.get('url', ''))
        query = ('%s %s' % (cItem.get('artist', ''), cItem.get('track', ''))).strip()
        if not query and cItem.get('url', '').startswith(YT_SEARCH):
            query = urllib_unquote_plus(cItem['url'][len(YT_SEARCH):])
        if not query:
            # favourite of a version before 08.10.2026: the quoted search string in 'page'
            query = urllib_unquote_plus(cItem.get('page', '')).replace(' music video', '')
        if not query:
            return []
        ytUrl = ''
        self.readYoutubeApiKey()
        if len(self.youtube_api_key) == 39:
            # quicker solution
            sts, data = self.getPage("https://www.googleapis.com/youtube/v3/search?part=id&type=video&maxResults=1&q=" + urllib_quote_plus(query) + "&key=" + self.youtube_api_key)
            if sts:
                videoId = self.cm.ph.getSearchGroups(data, r'"videoId":\s*"([^"]+?)"')[0]
                if videoId:
                    ytUrl = "https://www.youtube.com/watch?v=" + videoId
        if not ytUrl:
            # without an API key or when that fails: the YouTube web search (slower)
            try:
                for item in YouTubeParser().getSearchResult(urllib_quote_plus(query), "video", 1, ""):
                    if item.get('type') == 'video' and 'watch?v=' in (item.get('url') or ''):
                        ytUrl = item['url']
                        break
            except Exception:
                printExc()
        if not ytUrl:
            SetIPTVPlayerLastHostError(_("No YouTube video found for this track."))
            return []
        return applySidecarToLinks([{'name': 'YouTube', 'url': ytUrl, 'need_resolve': 1}], buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def getVideoLinks(self, url):
        printDBG("MusicBox.getVideoLinks [%s]" % url)
        if not self.cm.isValidUrl(url):
            return []
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(url), sidecarFromUrlMeta(url, IsSidecarEnabled()))

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("MusicBox.getArticleContent [%s]" % cItem.get('url', ''))
        otherInfo = {}
        icon = cItem.get('icon', '')
        for key, src in (('creator', 'artist'), ('genre', 'genre'), ('released', 'released'), ('duration', 'duration')):
            if cItem.get(src):
                otherInfo[key] = cItem[src]
        title = cItem.get('track', '') or cItem.get('album', '') or cItem.get('title', '')
        text = cItem.get('desc', '')
        if cItem.get('type') == 'category':
            # album: Last.fm album info (summary, tags, listeners)
            album = self._lastfmAlbumInfo(cItem)
            if album:
                title = album.get('name', '') or title
                wiki = (album.get('wiki') or {}).get('summary', '')
                wiki = self.cleanHtmlStr(re.sub(r'<a href="https://www\.last\.fm[^"]*">Read more on Last\.fm</a>\.?', '', wiki))
                if wiki:
                    text = (text + '[/br]' if text else '') + wiki
                tags = (album.get('tags') or {}).get('tag') or []
                tags = [t.get('name', '') for t in (tags if isinstance(tags, list) else [tags]) if isinstance(t, dict)]
                if tags and 'genre' not in otherInfo:
                    otherInfo['genres'] = ', '.join([t for t in tags if t])
                if album.get('playcount'):
                    otherInfo['views'] = str(album['playcount'])
                icon = self._lastfmImage(album.get('image')) or icon
        return [{'title': title, 'text': text, 'images': [{'title': '', 'url': icon}] if icon else [], 'other_info': otherInfo}]

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        if name in LEGACY_NAMES and not category:
            category = LEGACY_NAMES[name]
        printDBG("handleService: |||||||||||||||||||||||||||||||||||| [%s] [%s]" % (name, category))
        self.currList = []

        if name is None:
            self.listsMainMenu()
        elif category == 'itunes':
            self.listItunesCountries(self.currItem)
        elif category == 'itunes_songs':
            self.listItunesSongs(self.currItem)
        elif category == 'itunes_albums':
            self.listItunesAlbums(self.currItem)
        elif category == 'itunes_album':
            self.listItunesAlbumTracks(self.currItem)
        elif category == 'beatport':
            self.listBeatport(self.currItem)
        elif category == 'billboard_charts':
            self.listBillboardCharts(self.currItem)
        elif category == 'billboard_albums':
            self.listBillboardAlbums(self.currItem)
        elif category == 'lastfm_album':
            self.listLastfmAlbumTracks(self.currItem)
        elif category == 'lastfm':
            self.listLastfmMenu(self.currItem)
        elif category == 'lastfm_tracks':
            self.listLastfmTracks(self.currItem)

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, MusicBox(), False)
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('musicbox')

    def withArticleContent(self, cItem):
        return cItem.get('type') == 'video' or cItem.get('category') in ('itunes_album', 'lastfm_album')
