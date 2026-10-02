# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.isubprovider import CSubProviderBase, CBaseSubProviderClass
from Plugins.Extensions.IPTVPlayer.libs.subtitlesmatch import langCode, sortByRelease
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_urlencode

from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetDefaultLang
###################################################
# FOREIGN import
###################################################
import calendar
import json
import re
import time
from Components.config import config
# ###################################################
# Config options for HOST
###################################################


def GetConfigList():
    optionList = []
    return optionList
###################################################

# titlovi.com's website search sits behind a Cloudflare challenge. The official Kodi add-on
# service.subtitles.titlovi (v2.0.1, github.com/xbmc/repo-scripts branch matrix, main.py) uses this
# API instead: it needs a (free) titlovi.com account - gettoken -> Token + UserId, then search.
API_BASE_URL = 'https://kodi.titlovi.com/api/subtitles/'
DOWNLOAD_URL = 'https://titlovi.com/download/?type=%s&mediaid=%s'
# what the add-on sends with the download (the download itself is not challenged and needs no token)
DOWNLOAD_HEADER = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.6312.106 Safari/537.36',
                   'Referer': 'www.titlovi.com'}

# API language name ("Lang" of a result, "lang" search parameter) -> ISO 639-1 code
API_LANGS = [('Hrvatski', 'hr'), ('Srpski', 'sr'), ('Cirilica', 'sr'), ('Bosanski', 'bs'), ('Slovenski', 'sl'), ('Makedonski', 'mk'), ('English', 'en')]
API_LANG_CODES = dict(API_LANGS)

# token of the session: {'key': (login, password), 'token', 'userid', 'expires': epoch seconds}
_TOKEN = {}


def _parseExpiration(value):
    # '2026-10-09T17:23:48.123' -> epoch seconds (the API time is taken as UTC), 0 when unknown
    match = re.match(r'(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)', str(value or ''))
    if not match:
        return 0
    try:
        return calendar.timegm(time.strptime(match.group(1), '%Y-%m-%dT%H:%M:%S'))
    except Exception:
        printExc()
        return 0


class TitlovicomProvider(CBaseSubProviderClass):

    # the language whose code page converFileToUtf8 uses for the file being downloaded ('' = its own)
    codePageLang = ''

    def __init__(self, params={}):
        CBaseSubProviderClass.__init__(self, params)
        self.MAIN_URL = 'https://titlovi.com/'
        self.API_HEADER = {'User-Agent': self.cm.getDefaultHeader()['User-Agent']}
        self.dInfo = params['discover_info']

    # ---------------------------------------------------------------- API

    def _apiRequest(self, url, post_data=None):
        # -> (HTTP status code, text); 0 when there was no answer
        params = {'header': dict(self.API_HEADER), 'ignore_http_code_ranges': [(300, 599)]}
        if post_data is not None:
            params['raw_post_data'] = True
        sts, data = self.cm.getPage(url, params, post_data)
        code = self.cm.meta.get('status_code', 0)
        if not sts and not code:
            return 0, ''
        return int(code or 0), data or ''

    def _credentials(self):
        return config.plugins.iptvplayer.titlovi_login.value.strip(), config.plugins.iptvplayer.titlovi_password.value

    def _login(self, force=False):
        # -> True with _TOKEN filled; False after SetIPTVPlayerLastHostError
        login, password = self._credentials()
        if login == '' or password == '':
            SetIPTVPlayerLastHostError(_('Titlovi.com needs a free titlovi.com account. Enter login and password in the E2iPlayer settings.'))
            return False
        # like the add-on: a cached token is renewed a day before it expires
        if not force and _TOKEN.get('key') == (login, password) and _TOKEN.get('expires', 0) - 86400 > time.time():
            return True
        _TOKEN.clear()

        # add-on: requests.post(API_BASE_URL + "gettoken", params={username, password, returnStatusCode, json}) - all in the query, empty body
        url = API_BASE_URL + 'gettoken?' + urllib_urlencode([('username', login), ('password', password), ('returnStatusCode', 'True'), ('json', 'True')])
        code, data = self._apiRequest(url, '')
        if code in (401, 404):
            SetIPTVPlayerLastHostError(_('Titlovi.com login failed for user "%s". Please check your login and password.') % login)
            return False
        if code == 403:
            SetIPTVPlayerLastHostError(_('Titlovi.com: API access is disabled for the account "%s". See titlovi.com/donacije.') % login)
            return False
        if code != 200:
            SetIPTVPlayerLastHostError(_('Titlovi.com login failed (HTTP %s).') % (code or _('no answer')))
            return False
        try:
            data = json.loads(data)
            token, userid = data['Token'], data['UserId']
        except Exception:
            printExc()
            SetIPTVPlayerLastHostError(_('Titlovi.com: invalid server response.'))
            return False
        if not token:
            SetIPTVPlayerLastHostError(_('Titlovi.com login failed for user "%s". Please check your login and password.') % login)
            return False
        expires = _parseExpiration(data.get('ExpirationDate')) or time.time() + 86400 * 2
        _TOKEN.update({'key': (login, password), 'token': token, 'userid': userid, 'expires': expires})
        printDBG('TitlovicomProvider._login ok user[%s] userid[%s] expires[%s]' % (data.get('UserName'), userid, data.get('ExpirationDate')))
        return True

    def _apiSearch(self, query):
        # query: list of (name, value) pairs -> list of result dicts, or None after SetIPTVPlayerLastHostError
        if not self._login():
            return None
        for attempt in (0, 1):
            # add-on: requests.get(API_BASE_URL + "search", params={..., token, userid, json}); lists -> repeated parameters
            url = API_BASE_URL + 'search?' + urllib_urlencode(list(query) + [('token', _TOKEN['token']), ('userid', _TOKEN['userid']), ('json', 'True')])
            code, data = self._apiRequest(url)
            if code == 401 and attempt == 0:
                # token expired or revoked: log in again once
                if not self._login(force=True):
                    return None
                continue
            if code == 403:
                SetIPTVPlayerLastHostError(_('Titlovi.com: API access is disabled for the account "%s". See titlovi.com/donacije.') % self._credentials()[0])
                return None
            if code != 200:
                SetIPTVPlayerLastHostError(_('Titlovi.com search failed (HTTP %s).') % (code or _('no answer')))
                return None
            try:
                results = json.loads(data).get('SubtitleResults') or []
            except Exception:
                printExc()
                SetIPTVPlayerLastHostError(_('Titlovi.com: invalid server response.'))
                return None
            return [x for x in results if isinstance(x, dict) and x.get('Id')]

    def _langOrder(self):
        # the API language names, the user's language first
        lang = langCode(GetDefaultLang())
        return [n for n, c in API_LANGS if c == lang] + [n for n, c in API_LANGS if c != lang]

    # ---------------------------------------------------------------- lists

    def getMoviesTitles(self, cItem, nextCategory):
        printDBG("TitlovicomProvider.getMoviesTitles")
        # no account -> say so at once instead of an IMDb list that leads nowhere
        if not self._login():
            return
        sts, tab = self.imdbGetMoviesByTitle(self.params['confirmed_title'])
        if not sts:
            return
        printDBG(tab)
        for item in tab:
            params = dict(cItem)
            params.update(item)  # item = {'title', 'base_title', 'year', 'imdbid'}
            params.update({'category': nextCategory})
            self.addDir(params)

    def getType(self, cItem):
        printDBG("TitlovicomProvider.getType")
        imdbid = cItem['imdbid']
        title = cItem['title']
        type = self.getTypeFromThemoviedb(imdbid, title)
        if type == 'series':
            promSeason = self.dInfo.get('season')
            sts, tab = self.imdbGetSeasons(imdbid, promSeason)
            if not sts:
                return
            for item in tab:
                params = dict(cItem)
                params.update({'category': 'get_episodes', 'item_title': cItem['title'], 'season': item, 'title': _('Season %s') % item})
                self.addDir(params)
        elif type == 'movie':
            self.getSearchList(cItem, 'get_subtitles')

    def getEpisodes(self, cItem, nextCategory):
        printDBG("TitlovicomProvider.getEpisodes")
        imdbid = cItem['imdbid']
        season = cItem['season']

        promEpisode = self.dInfo.get('episode')
        sts, tab = self.imdbGetEpisodesForSeason(imdbid, season, promEpisode)
        if not sts:
            return
        for item in tab:
            params = dict(cItem)
            params.update(item)  # item = "episode_title", "episode", "eimdbid"
            title = 's{0}e{1} {2}'.format(str(season).zfill(2), str(item['episode']).zfill(2), item['episode_title'])
            params.update({'category': nextCategory, 'title': title})
            self.addDir(params)

    def getSearchList(self, cItem, nextCategory):
        printDBG("TitlovicomProvider.getSearchList")
        langNames = self._langOrder()
        isSeries = 'season' in cItem
        query = [('returnStatusCode', 'True'), ('ignoreLangAndEpisode', 'False'), ('lang', '|'.join(langNames))]
        if isSeries:
            # like the add-on: season 0 / episodes -1 and 0 are the season packs and specials
            query.extend([('season', '0'), ('season', str(cItem['season']))])
            episode = str(cItem.get('episode', ''))
            if episode.isdigit():
                query.extend([('episode', '-1'), ('episode', '0'), ('episode', episode)])

        results = self._apiSearch([('imdbid', 'tt%s' % cItem['imdbid'])] + query)
        if results is None:
            return
        if not results:
            # the subtitle may not be linked to IMDb: the add-on's title search
            title = self.imdbGetOrginalByTitle(cItem['imdbid'])[1].get('title') or cItem.get('base_title', '')
            if title:
                types = [('type', '2')] if isSeries else [('type', '1'), ('type', '3')]
                results = self._apiSearch([('query', title)] + types + query)
                if results is None:
                    return

        items = []
        for item in results:
            langName = item.get('Lang', '')
            lang = API_LANG_CODES.get(langName) or langCode(langName) or ''
            release = self.getStr(item.get('Release'))
            label = self.getStr(item.get('Title'))
            if item.get('Year'):
                label += ' (%s)' % item['Year']
            try:
                if int(item.get('Type', 0)) == 2 and int(item.get('Season', -1)) >= 0:
                    label += ' S%02dE%02d' % (int(item['Season']), max(int(item.get('Episode') or 0), 0))
            except Exception:
                pass
            descTab = [x for x in (langName, release, _('Downloads: %s') % item.get('DownloadCount', 0) if item.get('DownloadCount') is not None else '',
                                   _('Rating: %s') % item.get('Rating') if item.get('Rating') else '', self.getStr(item.get('Date'))[:10]) if x]
            params = dict(cItem)
            params.update({'category': nextCategory, 'title': '[%s] %s %s' % (lang or langName, label, release), 'lang': lang, 'lang_name': langName,
                           'release': release, 'sub_id': str(item['Id']), 'url': DOWNLOAD_URL % (item.get('Type', 1), item['Id']), 'desc': '[/br]'.join(descTab)})
            items.append(params)

        # by language (the user's first), the best release fit first within each language
        wanted = self.releaseName()
        for name in langNames + sorted(set(x['lang_name'] for x in items) - set(langNames)):
            for params in sortByRelease([x for x in items if x['lang_name'] == name], wanted, 'release'):
                self.addDir(params)

    def getSubtitlesList(self, cItem):
        printDBG("TitlovicomProvider.getSubtitlesList")
        tmpDIR = self.downloadArchive(cItem['url'], {'header': dict(DOWNLOAD_HEADER)})
        if None is tmpDIR:
            return

        cItem = dict(cItem)
        cItem.update({'category': '', 'path': tmpDIR})
        self.listSupportedFilesFromPath(cItem, self.getSupportedFormats(all=True))

    def downloadSubtitleFile(self, cItem):
        # Serbian Cyrillic ("Cirilica") files without UTF-8 are cp1251 (the code page of 'mk'), not cp1250 like Latin 'sr'
        self.codePageLang = 'mk' if cItem.get('lang_name') == 'Cirilica' else ''
        try:
            return CBaseSubProviderClass.downloadSubtitleFile(self, cItem)
        finally:
            self.codePageLang = ''

    def converFileToUtf8(self, inFile, outFile, lang=''):
        return CBaseSubProviderClass.converFileToUtf8(self, inFile, outFile, self.codePageLang or lang)

    def handleService(self, index, refresh=0):
        printDBG('handleService start')

        CBaseSubProviderClass.handleService(self, index, refresh)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

    # MAIN MENU
        if name is None:
            self.getMoviesTitles({'name': 'category'}, 'get_type')
        elif category == 'get_type':
            # take actions depending on the type
            self.getType(self.currItem)
        elif category == 'get_episodes':
            self.getEpisodes(self.currItem, 'get_search')
        elif category == 'get_search':
            self.getSearchList(self.currItem, 'get_subtitles')
        elif category == 'get_subtitles':
            self.getSubtitlesList(self.currItem)

        CBaseSubProviderClass.endHandleService(self, index, refresh)


class IPTVSubProvider(CSubProviderBase):

    def __init__(self, params={}):
        CSubProviderBase.__init__(self, TitlovicomProvider(params))
