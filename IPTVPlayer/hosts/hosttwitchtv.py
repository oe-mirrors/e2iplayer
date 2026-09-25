# -*- coding: utf-8 -*-
# Last Modified: 23.09.2026
#
# Revived against Twitch's current web GraphQL API (gql.twitch.tv), used
# anonymously with the public web Client-ID:
#   - the old kraken REST API (search) and api.twitch.tv/api/.../access_token
#     are gone, and the persisted query hashes the old host used change all
#     the time - plain GraphQL queries are used instead;
#   - playback: stream/video/clip PlaybackAccessToken -> usher.ttvnw.net
#     m3u8 (live/VOD), clip mp4 + sig/token;
#   - any request with an "after" cursor fails Twitch's client integrity
#     check without a browser, so every list is fetched as one first page
#     (up to 100, live streams max 30) and paged locally.
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetDefaultLang
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_urlencode
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
###################################################

###################################################
# FOREIGN import
###################################################
from datetime import timedelta
###################################################

CLIENT_ID = 'kimne78kx3ncx6brgo4mv6wki5h1ko'
GQL_URL = 'https://gql.twitch.tv/gql'
PER_PAGE = 30
MAX_ITEMS = 100
MAX_STREAMS = 30

PLAYBACK_PARAMS = '{platform: "web", playerBackend: "mediaplayer", playerType: "site"}'

# Twitch "Language" enum values, shown in their own language
LANGUAGES = [('DE', 'Deutsch'), ('EN', 'English'), ('ES', u'Español'), ('FR', u'Français'), ('IT', 'Italiano'),
             ('PL', 'Polski'), ('PT', u'Português'), ('RU', u'Русский'), ('TR', u'Türkçe'), ('NL', 'Nederlands'),
             ('SV', 'Svenska'), ('NO', 'Norsk'), ('DA', 'Dansk'), ('FI', 'Suomi'), ('CS', u'Čeština'),
             ('HU', 'Magyar'), ('RO', u'Română'), ('SK', u'Slovenčina'), ('EL', u'Ελληνικά'), ('BG', u'Български'),
             ('UK', u'Українська'), ('AR', u'العربية'), ('JA', u'日本語'), ('KO', u'한국어'), ('ZH', u'中文'),
             ('ZH_HK', u'中文(粵語)'), ('TH', u'ภาษาไทย'), ('VI', u'Tiếng Việt'), ('ASL', 'American Sign Language'),
             ('OTHER', 'Other')]
LANG_CODES = frozenset(code for code, _title in LANGUAGES)

STREAM_FIELDS = 'id title type viewersCount previewImageURL(width: 440, height: 248) broadcaster { login displayName } game { name displayName }'
VIDEO_FIELDS = 'id title lengthSeconds viewCount publishedAt broadcastType previewThumbnailURL(width: 440, height: 248) owner { displayName } game { displayName }'
CLIP_FIELDS = 'slug title durationSeconds viewCount createdAt language thumbnailURL(width: 480, height: 272) curator { displayName } broadcaster { displayName } game { displayName }'


def GetConfigList():
    return []


def gettytul():
    return 'https://twitch.tv/'


def jstr(item, key, default=''):
    if not item:
        return default
    v = item.get(key, default)
    if v is None:
        return default
    return ensure_str(v)


class Twitch(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'Twitch', 'cookie': 'Twitch.cookie'})
        self.MAIN_URL = 'https://www.twitch.tv/'
        self.DEFAULT_ICON_URL = 'https://s.jtvnw.net/jtv_user_pictures/hosted_images/GlitchIcon_WhiteonPurple.png'
        self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.HTTP_HEADER.update({'Client-ID': CLIENT_ID, 'Accept': '*/*', 'Content-Type': 'text/plain;charset=UTF-8'})
        self.defaultParams = {'header': self.HTTP_HEADER, 'raw_post_data': True}

        # the box language first, then the rest
        lang = GetDefaultLang().upper()
        self.langItems = [{'title': _('All')}]
        others = []
        for code, title in LANGUAGES:
            item = {'title': title, 'lang': code}
            if code == lang:
                self.langItems.append(item)
            else:
                others.append(item)
        self.langItems.extend(others)

        self.VIDEOS_TYPES_TAB = [{'title': _('All')},
                                 {'title': _('Archive'), 'videos_type': 'ARCHIVE'},
                                 {'title': _('Highlights'), 'videos_type': 'HIGHLIGHT'},
                                 {'title': _('Uploads'), 'videos_type': 'UPLOAD'},
                                 {'title': _('Past premieres'), 'videos_type': 'PAST_PREMIERE'}]

        self.VIDEOS_SORT_TAB = [{'title': _('Popular'), 'sort': 'VIEWS'},
                                {'title': _('Recent'), 'sort': 'TIME'}]

        self.CLIPS_FILTERS_TAB = [{'title': _('Last day'), 'clips_period': 'LAST_DAY'},
                                  {'title': _('Last week'), 'clips_period': 'LAST_WEEK'},
                                  {'title': _('Last month'), 'clips_period': 'LAST_MONTH'},
                                  {'title': _('All time'), 'clips_period': 'ALL_TIME'}]

        self.GAME_CAT_TAB = [{'category': 'game_lang', 'next_category': 'game_channels', 'title': _('Channels')},
                             {'category': 'game_videos_types', 'title': _('Videos')},
                             {'category': 'game_lang', 'next_category': 'game_clips_filters', 'title': _('Clips')}]

    # ---------------------------------------------------------------- api
    def gql(self, query, variables=None):
        body = json_dumps({'query': query, 'variables': variables or {}})
        sts, data = self.cm.getPage(GQL_URL, dict(self.defaultParams), body)
        if not sts:
            return None
        try:
            data = json_loads(data)
        except Exception:
            printExc()
            return None
        if data.get('errors'):
            printDBG('Twitch.gql errors: %s' % data['errors'])
        return data.get('data') or None

    @staticmethod
    def _langOption(cItem):
        lang = cItem.get('lang', '')
        if lang in LANG_CODES:
            return ', broadcasterLanguages: [%s]' % lang
        return ''

    @staticmethod
    def _edges(node):
        try:
            return [e['node'] for e in node['edges'] if e.get('node')]
        except Exception:
            return []

    def _addPaged(self, cItem, items, addFunc):
        page = cItem.get('page', 0)
        for item in items[page * PER_PAGE:(page + 1) * PER_PAGE]:
            addFunc(cItem, item)
        if len(items) > (page + 1) * PER_PAGE:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _('Next page'), 'page': page + 1})
            self.addDir(params)

    # ---------------------------------------------------------------- item builders
    def _addStream(self, cItem, item):
        broadcaster = item.get('broadcaster') or {}
        if not broadcaster.get('login'):
            return
        descTab = [jstr(item, 'title'), _('%s viewers') % item.get('viewersCount', 0)]
        if item.get('game'):
            descTab.append(_('Game: %s') % jstr(item['game'], 'displayName'))
        params = {'good_for_fav': True, 'name': 'category', 'type': 'category', 'category': 'list_channel',
                  'title': jstr(broadcaster, 'displayName') or jstr(broadcaster, 'login'), 'user_login': jstr(broadcaster, 'login'),
                  'icon': jstr(item, 'previewImageURL'), 'desc': '[/br]'.join(descTab)}
        self.addDir(params)

    def _addGame(self, cItem, item):
        desc = _('%s viewers') % item.get('viewersCount', 0) if item.get('viewersCount') is not None else ''
        params = {'good_for_fav': True, 'name': 'category', 'category': 'browse_game',
                  'title': jstr(item, 'displayName') or jstr(item, 'name'), 'game_name': jstr(item, 'name'),
                  'icon': jstr(item, 'boxArtURL'), 'desc': desc}
        self.addDir(params)

    def _addVideo(self, cItem, item):
        descTab = [str(timedelta(seconds=int(item.get('lengthSeconds') or 0))), _('%s views') % item.get('viewCount', 0), jstr(item, 'publishedAt')[:10]]
        descTab = [' | '.join(descTab)]
        if item.get('owner'):
            descTab.append(_('Channel: %s') % jstr(item['owner'], 'displayName'))
        if item.get('game'):
            descTab.append(_('Game: %s') % jstr(item['game'], 'displayName'))
        params = {'good_for_fav': True, 'title': jstr(item, 'title'), 'video_type': 'video', 'video_id': jstr(item, 'id'),
                  'icon': jstr(item, 'previewThumbnailURL'), 'desc': '[/br]'.join(descTab)}
        self.addVideo(params)

    def _addClip(self, cItem, item):
        descTab = [str(timedelta(seconds=int(item.get('durationSeconds') or 0))), _('%s views') % item.get('viewCount', 0), jstr(item, 'language')]
        descTab = [' | '.join(descTab)]
        if item.get('broadcaster'):
            descTab.append(_('Channel: %s') % jstr(item['broadcaster'], 'displayName'))
        if item.get('curator'):
            descTab.append(_('Clipped by: %s') % jstr(item['curator'], 'displayName'))
        if item.get('game'):
            descTab.append(_('Game: %s') % jstr(item['game'], 'displayName'))
        params = {'good_for_fav': True, 'title': '[%s] %s' % (jstr(item, 'createdAt')[:10], jstr(item, 'title')),
                  'video_type': 'clip', 'clip_slug': jstr(item, 'slug'), 'icon': jstr(item, 'thumbnailURL'), 'desc': '[/br]'.join(descTab)}
        self.addVideo(params)

    def _addChannelUser(self, cItem, item):
        stream = item.get('stream')
        descTab = []
        if stream:
            descTab.append('%s | %s' % (_('Live'), _('%s viewers') % stream.get('viewersCount', 0)))
            descTab.append(jstr(stream, 'title'))
            if stream.get('game'):
                descTab.append(_('Game: %s') % jstr(stream['game'], 'displayName'))
        if item.get('followers'):
            descTab.append(_('%s followers') % item['followers'].get('totalCount', 0))
        params = {'good_for_fav': True, 'name': 'category', 'type': 'category', 'category': 'list_channel',
                  'title': jstr(item, 'displayName') or jstr(item, 'login'), 'user_login': jstr(item, 'login'),
                  'icon': jstr(item, 'profileImageURL'), 'desc': '[/br]'.join(descTab)}
        self.addDir(params)

    # ---------------------------------------------------------------- listings
    def listMain(self, cItem):
        printDBG("Twitch.listMain")
        MAIN_CAT_TAB = [{'category': 'dir_games', 'title': _('Games')},
                        {'category': 'streams_lang', 'title': _('Live channels')}] + self.searchItems()
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listStreams(self, cItem):
        printDBG("Twitch.listStreams [%s]" % cItem)
        data = self.gql('{ streams(first: %d, options: {sort: VIEWER_COUNT%s}) { edges { node { %s } } } }' % (MAX_STREAMS, self._langOption(cItem), STREAM_FIELDS))
        if data:
            self._addPaged(cItem, self._edges(data.get('streams')), self._addStream)

    def listDirGames(self, cItem):
        printDBG("Twitch.listDirGames [%s]" % cItem)
        data = self.gql('{ games(first: %d) { edges { node { name displayName viewersCount boxArtURL(width: 285, height: 380) } } } }' % MAX_ITEMS)
        if data:
            self._addPaged(cItem, self._edges(data.get('games')), self._addGame)

    def listGameChannels(self, cItem):
        printDBG("Twitch.listGameChannels [%s]" % cItem)
        data = self.gql('query($n: String!) { game(name: $n) { streams(first: %d, options: {sort: VIEWER_COUNT%s}) { edges { node { %s } } } } }' % (MAX_ITEMS, self._langOption(cItem), STREAM_FIELDS), {'n': cItem['game_name']})
        if data and data.get('game'):
            self._addPaged(cItem, self._edges(data['game'].get('streams')), self._addStream)

    def listChannel(self, cItem):
        login = cItem['user_login']
        printDBG("Twitch.listChannel %s" % login)
        data = self.gql('query($l: String!) { user(login: $l) { displayName profileImageURL(width: 300) '
                        'stream { title viewersCount previewImageURL(width: 440, height: 248) game { displayName } } '
                        'videos { totalCount } } }', {'l': login})
        user = (data or {}).get('user')
        if not user:
            return
        icon = jstr(user, 'profileImageURL')
        stream = user.get('stream')
        if stream:
            descTab = [_('%s viewers') % stream.get('viewersCount', 0)]
            if stream.get('game'):
                descTab.append(_('Game: %s') % jstr(stream['game'], 'displayName'))
            self.addVideo({'good_for_fav': True, 'title': '[%s] %s' % (_('Live'), jstr(stream, 'title')), 'video_type': 'live',
                           'user_login': login, 'icon': jstr(stream, 'previewImageURL') or icon, 'desc': '[/br]'.join(descTab)})
        videosCount = (user.get('videos') or {}).get('totalCount') or 0
        if videosCount:
            self.addDir(dict(cItem, good_for_fav=False, category='videos_types', title=_('Videos %s') % videosCount, icon=icon, desc=''))
        self.addDir(dict(cItem, good_for_fav=False, category='clips_filters', title=_('Clips'), icon=icon, desc=''))

    def listVideos(self, cItem):
        printDBG("Twitch.listVideos [%s]" % cItem)
        vtype = ', type: %s' % cItem['videos_type'] if cItem.get('videos_type') else ''
        data = self.gql('query($l: String!) { user(login: $l) { videos(first: %d, sort: %s%s) { edges { node { %s } } } } }' % (MAX_ITEMS, cItem['sort'], vtype, VIDEO_FIELDS), {'l': cItem['user_login']})
        if data and data.get('user'):
            self._addPaged(cItem, self._edges(data['user'].get('videos')), self._addVideo)

    def listGameVideos(self, cItem):
        printDBG("Twitch.listGameVideos [%s]" % cItem)
        vtype = ', types: [%s]' % cItem['videos_type'] if cItem.get('videos_type') else ''
        data = self.gql('query($n: String!) { game(name: $n) { videos(first: %d, sort: %s%s) { edges { node { %s } } } } }' % (MAX_ITEMS, cItem['sort'], vtype, VIDEO_FIELDS), {'n': cItem['game_name']})
        if data and data.get('game'):
            self._addPaged(cItem, self._edges(data['game'].get('videos')), self._addVideo)

    def listClips(self, cItem):
        printDBG("Twitch.listClips [%s]" % cItem)
        data = self.gql('query($l: String!) { user(login: $l) { clips(first: %d, criteria: {period: %s}) { edges { node { %s } } } } }' % (MAX_ITEMS, cItem['clips_period'], CLIP_FIELDS), {'l': cItem['user_login']})
        if data and data.get('user'):
            self._addPaged(cItem, self._edges(data['user'].get('clips')), self._addClip)

    def listGameClips(self, cItem):
        printDBG("Twitch.listGameClips [%s]" % cItem)
        lang = ', languages: [%s]' % cItem['lang'] if cItem.get('lang') in LANG_CODES else ''
        data = self.gql('query($n: String!) { game(name: $n) { clips(first: %d, criteria: {period: %s%s}) { edges { node { %s } } } } }' % (MAX_ITEMS, cItem['clips_period'], lang, CLIP_FIELDS), {'n': cItem['game_name']})
        if data and data.get('game'):
            self._addPaged(cItem, self._edges(data['game'].get('clips')), self._addClip)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Twitch.listSearchResult [%s] [%s]" % (searchPattern, searchType))
        data = self.gql('query($q: String!) { searchFor(userQuery: $q, platform: "web") { '
                        'channels { edges { item { ... on User { login displayName profileImageURL(width: 150) followers { totalCount } '
                        'stream { viewersCount title game { displayName } } } } } } '
                        'games { edges { item { ... on Game { name displayName viewersCount boxArtURL(width: 285, height: 380) } } } } } }', {'q': searchPattern})
        result = (data or {}).get('searchFor') or {}
        if searchType == 'games':
            for edge in (result.get('games') or {}).get('edges', []):
                if edge.get('item', {}).get('name'):
                    self._addGame(cItem, edge['item'])
            return
        for edge in (result.get('channels') or {}).get('edges', []):
            item = edge.get('item') or {}
            if not item.get('login'):
                continue
            if searchType == 'streams' and not item.get('stream'):
                continue
            self._addChannelUser(cItem, item)

    # ---------------------------------------------------------------- playback
    def _getToken(self, field, arg, argType, value):
        data = self.gql('query($v: %s) { %s(%s: $v, params: %s) { value signature } }' % (argType, field, arg, PLAYBACK_PARAMS), {'v': value})
        token = (data or {}).get(field)
        if token and token.get('value') and token.get('signature'):
            return token
        return None

    def getLinksForVideo(self, cItem):
        printDBG("Twitch.getLinksForVideo [%s]" % cItem)
        urlTab = []
        videoType = cItem.get('video_type', '')

        if videoType == 'clip':
            data = self.gql('query($s: ID!) { clip(slug: $s) { playbackAccessToken(params: %s) { value signature } videoQualities { quality frameRate sourceURL } } }' % PLAYBACK_PARAMS, {'s': cItem['clip_slug']})
            clip = (data or {}).get('clip') or {}
            token = clip.get('playbackAccessToken') or {}
            if token.get('value'):
                query = urllib_urlencode({'sig': token['signature'], 'token': token['value']})
                for item in clip.get('videoQualities') or []:
                    if item.get('sourceURL'):
                        name = '%sp' % item.get('quality')
                        if item.get('frameRate'):
                            name += ', %dfps' % int(item['frameRate'])
                        urlTab.append({'name': name, 'url': item['sourceURL'] + '?' + query, 'need_resolve': 0})
            return urlTab

        if videoType == 'live':
            token = self._getToken('streamPlaybackAccessToken', 'channelName', 'String!', cItem['user_login'])
            url = 'https://usher.ttvnw.net/api/channel/hls/%s.m3u8' % cItem['user_login'].lower()
            liveStream = True
        else:
            token = self._getToken('videoPlaybackAccessToken', 'id', 'ID!', cItem['video_id'])
            url = 'https://usher.ttvnw.net/vod/%s.m3u8' % cItem['video_id']
            liveStream = False
        if not token:
            return urlTab

        url += '?' + urllib_urlencode({'sig': token['signature'], 'token': token['value'], 'allow_source': 'true', 'allow_audio_only': 'true', 'fast_bread': 'true', 'player': 'twitchweb'})
        try:
            for item in getDirectM3U8Playlist(url, checkExt=False, sortWithMaxBitrate=99999999):
                item['url'] = urlparser.decorateUrl(item['url'], {'iptv_proto': 'm3u8', 'iptv_livestream': liveStream})
                urlTab.append(item)
        except Exception:
            printExc()
        return urlTab

    # ---------------------------------------------------------------- service
    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("handleService: ||| name[%s], category[%s] " % (name, category))
        self.currList = []

        if name is None:
            self.listMain({'name': 'category', 'type': 'category'})
        elif category == 'streams_lang':
            self.listsTab(self.langItems, dict(self.currItem, category='list_streams'))
        elif category == 'list_streams':
            self.listStreams(self.currItem)
        elif category == 'dir_games':
            self.listDirGames(self.currItem)
        elif category == 'browse_game':
            self.listsTab(self.GAME_CAT_TAB, self.currItem)
        elif category == 'game_lang':
            self.listsTab(self.langItems, dict(self.currItem, category=self.currItem['next_category']))
        elif category == 'game_channels':
            self.listGameChannels(self.currItem)
        elif category == 'game_videos_types':
            self.listsTab(self.VIDEOS_TYPES_TAB, dict(self.currItem, category='game_videos_sort'))
        elif category == 'game_videos_sort':
            self.listsTab(self.VIDEOS_SORT_TAB, dict(self.currItem, category='game_list_videos'))
        elif category == 'game_list_videos':
            self.listGameVideos(self.currItem)
        elif category == 'game_clips_filters':
            self.listsTab(self.CLIPS_FILTERS_TAB, dict(self.currItem, category='game_list_clips'))
        elif category == 'game_list_clips':
            self.listGameClips(self.currItem)
        elif category == 'list_channel':
            self.listChannel(self.currItem)
        elif category == 'videos_types':
            self.listsTab(self.VIDEOS_TYPES_TAB, dict(self.currItem, category='videos_sort'))
        elif category == 'videos_sort':
            self.listsTab(self.VIDEOS_SORT_TAB, dict(self.currItem, category='list_videos'))
        elif category == 'list_videos':
            self.listVideos(self.currItem)
        elif category == 'clips_filters':
            self.listsTab(self.CLIPS_FILTERS_TAB, dict(self.currItem, category='list_clips'))
        elif category == 'list_clips':
            self.listClips(self.currItem)
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category'})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc')
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Twitch(), True, [CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_CATEGORY])

    def getSearchTypes(self):
        return [(_("Channels"), "channels"), (_("Live streams"), "streams"), (_("Games"), "games")]
