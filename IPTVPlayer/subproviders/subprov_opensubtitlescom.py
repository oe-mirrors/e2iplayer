# -*- coding: utf-8 -*-
# OpenSubtitles.com REST API v1 (https://opensubtitles.stoplight.io/docs/opensubtitles-api): every request
# needs the key of an own API consumer (free, https://www.opensubtitles.com/consumers), entered in the
# E2iPlayer settings (Subtitles). Searching is free; downloads are counted: without a login a few per IP
# and day, an opensubtitles.com account (login / password in the settings) raises the daily quota.
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.isubprovider import CSubProviderBase, CBaseSubProviderClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetDefaultLang
from Plugins.Extensions.IPTVPlayer.libs.subtitlesmatch import LANGUAGES, langCode, langSortKey, sortByEpisode, sortByRelease

###################################################
# FOREIGN import
###################################################
import json
import time
import urllib.parse
from Components.config import config

###################################################
# Config options for HOST
###################################################


def GetConfigList():
    # API key, login and password are in the E2iPlayer settings (Subtitles)
    return []
###################################################


API_HOST = 'api.opensubtitles.com'
MAX_PAGES = 3
# our language codes that the API spells differently, and back
API_LANG = {'pt': 'pt-pt', 'zh': 'zh-cn'}
FROM_API_LANG = {'pt-pt': 'pt', 'zh-cn': 'zh', 'zh-tw': 'zh'}
# login token of the account: {'key': (login, password), 'token': ..., 'host': ..., 'expires': ...}; a token is
# valid for 24 hours, the API limits logins (1 per second, too many get HTTP 429)
_TOKEN = {}


def getConfigValue(name):
    try:
        return getattr(config.plugins.iptvplayer, name).value.strip()
    except Exception:
        printExc()
        return ''


def apiLang(code):
    """our language code -> the one of the API ('pt' -> 'pt-pt', 'pt-br' stays)"""
    return API_LANG.get(code, code)


def ourLang(code):
    """language code of the API -> ours ('pt-pt' -> 'pt', 'zh-tw' -> 'zh')"""
    code = (code or '').lower()
    return FROM_API_LANG.get(code) or langCode(code) or code


def imdbParam(imdbid):
    """'tt0133093' / '0133093' -> '133093' (the API wants the number), '' when it is none"""
    imdbid = str(imdbid or '').replace('tt', '')
    return str(int(imdbid)) if imdbid.isdigit() else ''


class OpenSubtitlesComProvider(CBaseSubProviderClass):

    def __init__(self, params={}):
        from Plugins.Extensions.IPTVPlayer.version import IPTV_VERSION
        self.MAIN_URL = 'https://www.opensubtitles.com/'
        # the API wants the name and version of the application here, a browser UA is refused
        self.USER_AGENT = 'E2iPlayer v%s' % IPTV_VERSION
        CBaseSubProviderClass.__init__(self, params)
        self.lastError = ''

    def apiHeader(self, token=''):
        header = {'User-Agent': self.USER_AGENT, 'Api-Key': getConfigValue('opensubcom_apikey'),
                  'Accept': 'application/json', 'Content-Type': 'application/json'}
        if token:
            header['Authorization'] = 'Bearer %s' % token
        return header

    def apiRequest(self, path, query=None, post=None, token='', host=API_HOST):
        """-> (HTTP status, answer dict); (0, {}) without an answer. The search parameters go in sorted and
        lower case - the API redirects other forms."""
        url = 'https://%s/api/v1/%s' % (host, path)
        if query:
            url += '?' + urllib.parse.urlencode(sorted((k, str(v).lower()) for k, v in query.items() if v not in ('', None)))
        params = {'header': self.apiHeader(token), 'ignore_http_code_ranges': [(300, 599)]}
        if post is not None:
            params['raw_post_data'] = True
            post = json.dumps(post)
        self.cm.meta = {}
        sts, data = self.cm.getPage(url, params, post)
        code = int(self.cm.meta.get('status_code') or (200 if sts else 0))
        try:
            data = json.loads(data) if data else {}
        except Exception:
            printDBG('OpenSubtitlesComProvider.apiRequest no JSON answer HTTP %s' % code)
            data = {}
        if not isinstance(data, dict):
            data = {'data': data}
        if code != 200:
            printDBG('OpenSubtitlesComProvider.apiRequest %s HTTP %s message[%s]' % (path, code, self.apiMessage(data)))
        return code, data

    @staticmethod
    def apiMessage(data):
        message = data.get('message') or data.get('error') or ''
        if not message and isinstance(data.get('errors'), list):
            message = ' '.join(str(x) for x in data['errors'])
        return str(message).strip()

    def apiError(self, code, data):
        # the message for a failed request
        message = self.apiMessage(data)
        if code == 0:
            return _('The OpenSubtitles.com server did not answer. Please try again later.')
        if code in (401, 403):
            return _('OpenSubtitles.com rejected the request (HTTP %s). Please check the API key in the E2iPlayer settings.') % code + ('\n' + message if message else '')
        if code == 429:
            return 'OpenSubtitles.com: ' + _('Too many requests. Please try again later.')
        return 'OpenSubtitles.com: %s' % (message or ('HTTP %s' % code))

    def checkApiKey(self):
        if getConfigValue('opensubcom_apikey'):
            return True
        SetIPTVPlayerLastHostError(_('OpenSubtitles.com needs an API key. Create a free API consumer at https://www.opensubtitles.com/consumers and enter its key in the E2iPlayer settings (Subtitles).'))
        return False

    # ---------------------------------------------------------------- login

    def getLogin(self, force=False):
        """-> (token, host) of the account; ('', API_HOST) without login data. None when the login failed
        (lastError says why)."""
        login, password = getConfigValue('opensubcom_login'), getConfigValue('opensubcom_password')
        if not login or not password:
            return '', API_HOST
        if not force and _TOKEN.get('key') == (login, password) and _TOKEN.get('expires', 0) > time.time():
            return _TOKEN['token'], _TOKEN['host']
        _TOKEN.clear()
        code, data = self.apiRequest('login', post={'username': login, 'password': password})
        token = data.get('token') if code == 200 else ''
        if not token:
            if code in (400, 401):
                self.lastError = _('OpenSubtitles.com login failed for user "%s". Please check your login and password.') % login
            else:
                self.lastError = self.apiError(code, data)
            return None
        # VIP accounts get their own server ("vip-api.opensubtitles.com")
        host = urllib.parse.urlparse('//' + str(data.get('base_url') or API_HOST).split('://')[-1]).hostname or API_HOST
        _TOKEN.update({'key': (login, password), 'token': token, 'host': host, 'expires': time.time() + 23 * 3600})
        user = data.get('user') or {}
        printDBG('OpenSubtitlesComProvider.getLogin ok host[%s] allowed_downloads[%s] vip[%s]' % (host, user.get('allowed_downloads'), user.get('vip')))
        return token, host

    # ---------------------------------------------------------------- titles

    def getMoviesTitles(self, cItem, nextCategory):
        printDBG('OpenSubtitlesComProvider.getMoviesTitles')
        if not self.checkApiKey():
            return
        # imdbGetMoviesByTitle drops "S02E05" / the year of the confirmed title itself
        for item in self.imdbGetMoviesByTitle(self.params['confirmed_title'])[1]:
            params = dict(cItem)
            params.update(item)  # item = {'title', 'base_title', 'year', 'imdbid'}
            params.update({'category': nextCategory})
            self.addDir(params)
        if not self.currList:
            # nothing (or no answer) from IMDb: the title search of the API
            self.getLanguages(dict(cItem, imdbid=''), 'get_subtitles')

    def getType(self, cItem):
        printDBG('OpenSubtitlesComProvider.getType')
        imdbid = cItem['imdbid']
        if self.getTypeFromThemoviedb(imdbid, cItem['title']) == 'series':
            for item in self.imdbGetSeasons(imdbid, self.wantedInfo()[2])[1]:
                params = dict(cItem)
                params.update({'category': 'get_episodes', 'item_title': cItem['title'], 'season': item, 'title': _('Season %s') % item})
                self.addDir(params)
            if self.currList:
                return
        self.getLanguages(cItem, 'get_subtitles')

    def getEpisodes(self, cItem, nextCategory):
        printDBG('OpenSubtitlesComProvider.getEpisodes')
        season = cItem['season']
        for item in self.imdbGetEpisodesForSeason(cItem['imdbid'], season, self.wantedInfo()[3])[1]:
            if not item['episode'].isdigit():
                continue
            params = dict(cItem)
            params.update(item)  # item = "episode_title", "episode", "eimdbid"
            title = 's{0}e{1} {2}'.format(str(season).zfill(2), str(item['episode']).zfill(2), item['episode_title'])
            params.update({'category': nextCategory, 'title': title})
            self.addDir(params)

    def getLanguages(self, cItem, nextCategory):
        # the user's language first, then English, then by name; Chinese traditional as its own entry ("Chinese [zh-tw]")
        printDBG('OpenSubtitlesComProvider.getLanguages')
        langs = [(code, name) for name, code, _iso2 in LANGUAGES] + [('zh-tw', 'Chinese')]
        defaultLang = GetDefaultLang()
        itemTitle = cItem.get('item_title', cItem.get('title', ''))
        for code, name in sorted(langs, key=lambda x: (langSortKey(x[0], defaultLang), x[0])):
            params = dict(cItem)
            params.update({'title': '%s [%s]' % (_(name), apiLang(code)), 'search_lang': apiLang(code), 'category': nextCategory, 'item_title': itemTitle})
            self.addDir(params)

    # ---------------------------------------------------------------- subtitles

    def searchQuery(self, cItem):
        """the search parameters of the item: IMDb id (an episode: the series id with season and episode)
        or the title"""
        query = {'languages': cItem.get('search_lang', '')}
        imdbid = imdbParam(cItem.get('imdbid'))
        season, episode = cItem.get('season'), cItem.get('episode')
        if imdbid and season and episode:
            query.update({'parent_imdb_id': imdbid, 'season_number': season, 'episode_number': episode})
        elif imdbid:
            query['imdb_id'] = imdbid
        else:
            title, year, season, episode = self.wantedInfo()
            query['query'] = title or self.params.get('confirmed_title', '')
            if season and episode:
                query.update({'season_number': season, 'episode_number': episode})
            elif year:
                query['year'] = year
        return query

    def getSubtitlesList(self, cItem):
        printDBG('OpenSubtitlesComProvider.getSubtitlesList')
        query = self.searchQuery(cItem)
        results = []
        for page in range(1, MAX_PAGES + 1):
            if page > 1:
                query['page'] = page
            code, data = self.apiRequest('subtitles', query)
            if code != 200:
                if not results:
                    SetIPTVPlayerLastHostError(self.apiError(code, data))
                    return
                break
            results.extend(x for x in data.get('data') or [] if isinstance(x, dict))
            try:
                if page >= int(data.get('total_pages') or 1):
                    break
            except (TypeError, ValueError):
                break

        subFormats = self.getSupportedFormats(all=True)
        items = []
        for result in results:
            try:
                items.extend(self.subtitleItems(cItem, result.get('attributes') or {}, subFormats))
            except Exception:
                printExc()
        if not items:
            SetIPTVPlayerLastHostError(_('No subtitles found.'))
            return
        # the most downloaded first, then the release of the video and (title search) the wanted episode
        items.sort(key=lambda x: -x['downloads'])
        items = sortByRelease(items, self.releaseName(), 'release')
        if not imdbParam(cItem.get('imdbid')):
            season, episode = self.wantedInfo()[2:]
            items = sortByEpisode(items, season, episode, 'release')
        for params in items:
            self.addSubtitle(params)

    def subtitleItems(self, cItem, attrs, subFormats):
        # one item per file (a subtitle for a CD1/CD2 release has two)
        lang = ourLang(attrs.get('language'))
        feature = attrs.get('feature_details') or {}
        release = self.getStr(attrs.get('release')).strip() or self.getStr(feature.get('title')) or cItem.get('base_title', '')
        try:
            downloads = int(attrs.get('download_count') or 0)
        except (TypeError, ValueError):
            downloads = 0
        try:
            fps = float(attrs.get('fps') or 0)
        except (TypeError, ValueError):
            fps = 0
        flags = []
        if attrs.get('hearing_impaired'):
            flags.append(_('Hearing impaired'))
        if attrs.get('machine_translated') or attrs.get('ai_translated'):
            flags.append(_('machine translated'))
        if attrs.get('foreign_parts_only'):
            flags.append(_('Foreign parts only'))
        uploader = self.getStr((attrs.get('uploader') or {}).get('name'))
        files = [f for f in attrs.get('files') or [] if isinstance(f, dict) and f.get('file_id')]
        imdbid = imdbParam(cItem.get('eimdbid') or feature.get('imdb_id') or cItem.get('imdbid'))
        items = []
        for idx, f in enumerate(files):
            fileName = self.getStr(f.get('file_name'))
            # the file name often has no extension ("Movie.2010.1080p.BluRay"): the download finds the format
            ext = fileName.rsplit('.', 1)[-1].lower() if '.' in fileName else ''
            ext = ext if ext in subFormats else ''
            title = '[%s] %s' % (lang, release)
            if len(files) > 1:
                title += ' (CD%s)' % (f.get('cd_number') or idx + 1)
            if flags:
                title += ' (%s)' % ', '.join(flags)
            desc = [x for x in (fileName, ', '.join(flags), _('Downloads: %s') % downloads, fps and 'FPS: %s' % fps,
                                uploader and _('Author: %s') % uploader) if x]
            params = dict(cItem)
            params.update({'title': title, 'release': release, 'lang': lang, 'file_id': f['file_id'], 'sub_id': str(f['file_id']),
                           'ext': ext, 'fps': fps, 'imdbid': imdbid, 'downloads': downloads, 'desc': '[/br]'.join(desc)})
            items.append(params)
        return items

    def downloadSubtitleFile(self, cItem):
        printDBG('OpenSubtitlesComProvider.downloadSubtitleFile file_id[%s]' % cItem.get('file_id'))
        if not self.checkApiKey():
            return {}
        login = self.getLogin()
        if login is None:
            SetIPTVPlayerLastHostError(self.lastError)
            return {}
        token, host = login
        try:
            post = {'file_id': int(cItem['file_id'])}
        except (KeyError, TypeError, ValueError):
            SetIPTVPlayerLastHostError(_('Failed to download subtitle.'))
            return {}
        code, data = self.apiRequest('download', post=post, token=token, host=host)
        if code == 401 and token:
            # the token expired early: one new login
            login = self.getLogin(force=True)
            if login is None:
                SetIPTVPlayerLastHostError(self.lastError)
                return {}
            token, host = login
            code, data = self.apiRequest('download', post=post, token=token, host=host)
        link = self.getStr(data.get('link')) if code == 200 else ''
        if not link:
            if code == 406:
                # the daily download quota is used up - the API says when it is renewed
                message = self.apiMessage(data) or _('The daily download limit is reached.')
                if not token:
                    message += '\n' + _('An opensubtitles.com account (login and password in the E2iPlayer settings) raises the limit.')
                SetIPTVPlayerLastHostError('OpenSubtitles.com: %s' % message)
            else:
                SetIPTVPlayerLastHostError(self.apiError(code, data))
            return {}
        printDBG('OpenSubtitlesComProvider.downloadSubtitleFile requests[%s] remaining[%s] reset[%s]' % (data.get('requests'), data.get('remaining'), data.get('reset_time_utc')))
        # the temporary link of the file server, no API headers needed
        sts, body = self.downloadBinary(link, {'header': {'User-Agent': self.USER_AGENT}})
        if not sts or not body:
            SetIPTVPlayerLastHostError(_('Failed to download subtitle.'))
            return {}
        return self.saveSubtitleData(body, cItem.get('release') or cItem['title'], cItem['lang'], cItem['sub_id'], cItem.get('imdbid', ''),
                                     cItem.get('ext', ''), cItem.get('fps', 0))

    def handleService(self, index, refresh=0):
        printDBG('OpenSubtitlesComProvider.handleService start')

        CBaseSubProviderClass.handleService(self, index, refresh)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')

        printDBG("handleService: name[%s], category[%s] " % (name, category))
        self.currList = []

        if name is None:
            self.getMoviesTitles({'name': 'category'}, 'get_type')
        elif category == 'get_type':
            self.getType(self.currItem)
        elif category == 'get_episodes':
            self.getEpisodes(self.currItem, 'get_languages')
        elif category == 'get_languages':
            self.getLanguages(self.currItem, 'get_subtitles')
        elif category == 'get_subtitles':
            self.getSubtitlesList(self.currItem)

        CBaseSubProviderClass.endHandleService(self, index, refresh)


class IPTVSubProvider(CSubProviderBase):

    def __init__(self, params={}):
        CSubProviderBase.__init__(self, OpenSubtitlesComProvider(params))
