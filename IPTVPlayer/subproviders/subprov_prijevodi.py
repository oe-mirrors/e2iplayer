# -*- coding: utf-8 -*-
# prijevodi-online.org: Croatian / Serbian / Bosnian / ... subtitles for series and films. The site is a
# single page app on a JSON API (/api/v1/...). Search, lists and series downloads work anonymously; film
# downloads need an account (the anonymous user lacks "movies.translations.download"). The login is a
# session cookie from POST /api/v1/auth/login {username, password, rememberMe[, captchaToken]}.
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.isubprovider import CSubProviderBase, CBaseSubProviderClass
from Plugins.Extensions.IPTVPlayer.libs.subtitlesmatch import matchTitle, langCode, sortByRelease, episodeFits
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetDefaultLang, rm
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_urlencode
###################################################
# FOREIGN import
###################################################
import json
import re
import time
from os import path as os_path
from Components.config import config

###################################################
# Config options for HOST (prijevodi_login / prijevodi_password are defined in iptvconfig.py)
###################################################


def GetConfigList():
    optionList = []
    return optionList
###################################################


# one login per session (its cookies are in the cookie file): {'key': (login, password), 'logged_in': True, 'expires': time, 'error': message}
SESSION = {}
SESSION_TTL = 30 * 60
# a failed login is not repeated at once (the site allows 5 login attempts per few seconds)
FAILED_LOGIN_TTL = 60

# the languages of the site after the user's one
SITE_LANGS = ['hr', 'bs', 'sr', 'sl', 'mk', 'en']


class PrijevodiOnline(CBaseSubProviderClass):

    def __init__(self, params={}):
        params['cookie'] = 'prijevodionlineorg.cookie'
        CBaseSubProviderClass.__init__(self, params)

        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'Referer': self.getMainUrl(), 'Accept': 'application/json, text/plain, */*'}
        self.defaultParams = {'header': self.HTTP_HEADER}
        self.API_URL = self.getMainUrl() + 'api/v1/'

    def getMainUrl(self):
        return 'https://www.prijevodi-online.org/'

    def getMaxFileSize(self):
        return 1024 * 1024 * 10

    def getLanguages(self):
        lang = GetDefaultLang()
        return [lang] + [x for x in SITE_LANGS if x != lang]

    def getWanted(self):
        title, year, season, episode = self.wantedInfo()
        # "<localized title> (<title>)" -> the first one
        return title.split('(')[0].strip() or title, year, season, episode

    def getApi(self, path, query=None):
        # the decoded JSON answer, or None
        url = self.API_URL + path
        if query:
            url += '?' + urllib_urlencode(query)
        sts, data = self.cm.getPage(url, self.defaultParams)
        if not sts:
            return None
        try:
            data = json.loads(data)
        except Exception:
            printExc()
            return None
        return data if isinstance(data, dict) else None

    @staticmethod
    def getItems(data, key):
        items = ((data or {}).get(key) or {}).get('items')
        return [x for x in items if isinstance(x, dict)] if isinstance(items, list) else []

    def listSearch(self, cItem, nextSeries, nextMovie):
        printDBG("PrijevodiOnline.listSearch")
        title, year, season, episode = self.getWanted()
        types = ['series', 'movies'] if season and episode else ['movies', 'series']
        items = []
        for type in types:
            for item in self.getItems(self.getApi('search/results', {'q': title, 'type': type, 'perPage': '50'}), 'results'):
                if not item.get('id') or item.get('translationCount') == 0:
                    continue
                name = item.get('title') or ''
                if type == 'series':
                    years = '-'.join(str(x) for x in (item.get('premiereYear'), item.get('finaleYear')) if x)
                    desc = [_('Series'), _('Seasons: %s') % item.get('seasonCount', '?'), _('Episodes: %s') % item.get('episodeCount', '?')]
                    params = {'category': nextSeries, 'series_id': item['id'], 'series_slug': item.get('slug') or '', 'item_year': item.get('premiereYear')}
                else:
                    years = str(item.get('year') or '')
                    desc = [_('Movie'), ', '.join(item.get('genres') or [])]
                    params = {'category': nextMovie, 'movie_id': item['id'], 'item_year': item.get('year')}
                if item.get('originalTitle'):
                    desc.insert(0, item['originalTitle'])
                desc.append(_('Subtitles: %s') % item.get('translationCount', '?'))
                params.update({'title': '%s (%s)' % (name, years) if years else name, 'item_title': name, 'original_title': item.get('originalTitle') or '',
                               'desc': '[/br]'.join(x for x in desc if x)})
                items.append(params)
        # the best match first
        results = []
        for params in items:
            for name in (params['item_title'], params['original_title']):
                if name:
                    results.append((name, params['item_year'], params))
        best = matchTitle(title, year, results)
        if best is not None:
            items.remove(best)
            items.insert(0, best)
        for params in items:
            item = dict(cItem)
            item.update(params)
            self.addDir(item)

    def listSeasons(self, cItem, nextCategory):
        printDBG("PrijevodiOnline.listSeasons")
        season = self.getWanted()[2]
        imdbid = ''
        # series/<id> is for the staff, by-slug is public
        sts, data = self.cm.getPage(self.API_URL + 'series/by-slug/%s' % cItem['series_slug'], self.defaultParams) if cItem.get('series_slug') else (False, '')
        if sts:
            # the IMDb link is in the description document
            imdbid = self.cm.ph.getSearchGroups(data, r'''imdb\.com/title/tt([0-9]+)''')[0]
        items = sorted(self.getItems(self.getApi('series/%s/seasons' % cItem['series_id']), 'seasons'), key=lambda x: x.get('sortOrder') or 0)
        for item in items:
            num = item.get('seasonNumber')
            params = dict(cItem)
            title = item.get('title') or _('Season %s') % num
            params.update({'category': nextCategory, 'title': title, 'season_id': item.get('id'), 's_num': num, 'imdbid': imdbid, 'desc': '%s[/br]%s' % (cItem['item_title'], title)})
            self.addDir(params, not (season and num == season))

    def listEpisodes(self, cItem, nextCategory):
        printDBG("PrijevodiOnline.listEpisodes")
        episode = self.getWanted()[3]
        items = [x for x in self.getItems(self.getApi('series/%s/episodes' % cItem['series_id']), 'episodes') if x.get('seasonId') == cItem['season_id']]
        items.sort(key=lambda x: x.get('episodeNumber') or 0)
        for item in items:
            sNum, eNum = item.get('seasonNumber') or 0, item.get('episodeNumber') or 0
            title = 'S%02dE%02d' % (sNum, eNum)
            if item.get('title'):
                title += ' - ' + item['title']
            desc = [title, (item.get('airdate') or '')[:10]]
            if item.get('status') and item['status'] != 'translated':
                desc.append(item['status'])
            params = dict(cItem)
            params.update({'category': nextCategory, 'title': title, 'episode_id': item.get('id'), 'e_num': eNum, 'desc': '[/br]'.join(x for x in desc if x)})
            self.addDir(params, not (episode and eNum == episode))

    def listTranslations(self, cItem, nextCategory):
        printDBG("PrijevodiOnline.listTranslations")
        if cItem.get('episode_id'):
            kind = 'series'
            data = self.getItems(self.getApi('translations/series', {'episodeId': cItem['episode_id'], 'perPage': '100'}), 'translations')
            season, episode = cItem.get('s_num'), cItem.get('e_num')
        else:
            kind = 'movies'
            data = self.getItems(self.getApi('translations/movies', {'movieId': cItem['movie_id'], 'perPage': '100'}), 'movieTranslations')
            season = episode = None
        langs = self.getLanguages()
        items = []
        for item in data:
            if not item.get('id') or item.get('isPublished') is False or item.get('isRevoked'):
                continue
            lang = langCode(item.get('languageCode') or '') or langCode(item.get('languageName') or '') or 'hr'
            name = item.get('name') or item.get('title') or item.get('fileName') or str(item['id'])
            name = re.sub(r'(?i)\.(zip|rar|srt)$', '', name.strip())
            release = ' '.join(x for x in (name, item.get('description'), item.get('versionTitle'), item.get('fileName')) if x)
            desc = []
            for x in (item.get('description'), item.get('versionTitle'), item.get('fileName')):
                if x and x not in desc:
                    desc.append(x)
            flags = [item.get('releaseFormatName') or '']
            if item.get('fps'):
                flags.append('%s fps' % item['fps'])
            if (item.get('cdCount') or 1) > 1:
                flags.append('%s CD' % item['cdCount'])
            if item.get('hearingImpaired'):
                flags.append(_('hearing impaired'))
            if item.get('machineTranslated'):
                flags.append(_('machine translated'))
            desc.append(', '.join(x for x in flags if x))
            if item.get('username'):
                desc.append(_('Uploader: %s') % item['username'])
            downloads = item.get('downloadCount') or 0
            desc.append(_('Downloads: %s') % downloads)
            fps = item.get('fps') or 0  # 23.976 stays a float
            params = dict(cItem)
            params.update({'category': nextCategory, 'title': '[%s] %s' % (lang, name), 'sub_title': name, 'lang': lang, 'sub_id': str(item['id']),
                           'kind': kind, 'release': release, 'downloads': downloads, 'fps': fps if isinstance(fps, (int, float)) else 0,
                           'fits': episodeFits(release, season, episode), 'imdbid': cItem.get('imdbid', ''), 'desc': '[/br]'.join(x for x in desc if x)})
            items.append(params)
        if not items:
            SetIPTVPlayerLastHostError(_('No subtitles found.'))
            return
        items.sort(key=lambda x: (langs.index(x['lang']) if x['lang'] in langs else len(langs), not x['fits'], -x['downloads']))
        for lang in [x for x in langs if x in set(i['lang'] for i in items)] + sorted(set(i['lang'] for i in items) - set(langs)):
            for params in sortByRelease([x for x in items if x['lang'] == lang], self.releaseName(), 'release'):
                self.addDir(params)

    def getCredentials(self):
        return config.plugins.iptvplayer.prijevodi_login.value.strip(), config.plugins.iptvplayer.prijevodi_password.value

    def hasSession(self):
        # a still valid login with the configured account (its cookies are in the cookie file)
        return SESSION.get('key') == self.getCredentials() and SESSION.get('logged_in', False) and SESSION.get('expires', 0) > time.time()

    def doLogin(self, force=False):
        # True when logged in, False when the login failed (the message is set)
        login, password = self.getCredentials()
        key = (login, password)
        if not force:
            if self.hasSession():
                return True
            if SESSION.get('key') == key and SESSION.get('error') and SESSION.get('expires', 0) > time.time():
                SetIPTVPlayerLastHostError(SESSION['error'])
                return False
        SESSION.clear()
        rm(self.COOKIE_FILE)
        header = dict(self.HTTP_HEADER, **{'Content-Type': 'application/json', 'Origin': self.getMainUrl().rstrip('/')})
        params = {'header': header, 'raw_post_data': True, 'use_cookie': True, 'load_cookie': False, 'save_cookie': True,
                  'cookiefile': self.COOKIE_FILE, 'ignore_http_code_ranges': [(400, 499)]}
        sts, data = self.cm.getPage(self.API_URL + 'auth/login', params, json.dumps({'username': login, 'password': password, 'rememberMe': False}))
        try:
            data = json.loads(data) if data else {}
        except Exception:
            data = {}
        if not isinstance(data, dict):
            data = {}
        if sts and data.get('auth') and os_path.isfile(self.COOKIE_FILE) and self.cm.getCookieItems(self.COOKIE_FILE):
            printDBG("PrijevodiOnline.doLogin logged in as [%s]" % (data['auth'].get('name') if isinstance(data['auth'], dict) else login))
            SESSION.update({'key': key, 'logged_in': True, 'expires': time.time() + SESSION_TTL})
            return True
        error = data.get('error') if isinstance(data.get('error'), dict) else {}
        printDBG("PrijevodiOnline.doLogin failed sts[%s] error[%s]" % (sts, error))
        if error.get('code') == 'Auth/CaptchaFailed':
            # the website shows a Cloudflare Turnstile captcha at its login form
            message = _('Login to prijevodi-online.org failed: the site asks for a captcha, which E2iPlayer cannot solve. Series subtitles download without an account.')
        elif error.get('message'):
            message = _('Login to prijevodi-online.org failed: %s') % error['message']
        else:
            message = _('Failed to log in user "%s". Please check your login and password.') % login
        SESSION.update({'key': key, 'error': message, 'expires': time.time() + FAILED_LOGIN_TTL})
        SetIPTVPlayerLastHostError(message)
        return False

    def downloadTranslation(self, url, loggedIn):
        # (directory with the files or None, HTTP status of the download - downloadBinary resets cm.meta)
        params = {'header': dict(self.HTTP_HEADER, Accept='*/*')}
        if loggedIn:
            # the session cookies from the cookie file of doLogin, anonymous without
            params.update({'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE})
        tmpDIR = self.downloadArchive(url, params)
        return tmpDIR, self.cm.meta.get('status_code')

    def getSubtitlesList(self, cItem):
        printDBG("PrijevodiOnline.getSubtitlesList")
        url = self.API_URL + 'translations/%s/%s/download' % (cItem['kind'], cItem['sub_id'])
        login, password = self.getCredentials()
        loggedIn = self.hasSession()
        loggedInNow = False
        if not loggedIn and cItem['kind'] == 'movies' and login and password:
            # the anonymous user may not download film subtitles
            if not self.doLogin():
                return
            loggedIn = loggedInNow = True
        tmpDIR, status = self.downloadTranslation(url, loggedIn)
        if tmpDIR is None and status == 401:
            if not login or not password:
                SetIPTVPlayerLastHostError(_('Downloading from prijevodi-online.org needs a free account. Enter login and password in the E2iPlayer settings.'))
                return
            if not loggedInNow:
                # the session has expired
                if not self.doLogin(force=True):
                    return
                tmpDIR, status = self.downloadTranslation(url, True)
            if tmpDIR is None and status == 401:
                SetIPTVPlayerLastHostError(_('prijevodi-online.org refused the download for this account.'))
        if tmpDIR is None:
            if status in (402, 403):
                SetIPTVPlayerLastHostError(_('prijevodi-online.org refused the download for this account.'))
            elif status == 429:
                SetIPTVPlayerLastHostError(_('Too many requests. Please try again later.'))
            return
        cItem = dict(cItem)
        cItem.update({'category': '', 'path': tmpDIR})
        self.listSupportedFilesFromPath(cItem, self.getSupportedFormats(all=True))

    def handleService(self, index, refresh=0):
        printDBG('handleService start')

        CBaseSubProviderClass.handleService(self, index, refresh)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

        if name is None:
            self.listSearch({'name': 'category'}, 'list_seasons', 'list_translations')
        elif category == 'list_seasons':
            self.listSeasons(self.currItem, 'list_episodes')
        elif category == 'list_episodes':
            self.listEpisodes(self.currItem, 'list_translations')
        elif category == 'list_translations':
            self.listTranslations(self.currItem, 'list_subtitles')
        elif category == 'list_subtitles':
            self.getSubtitlesList(self.currItem)

        CBaseSubProviderClass.endHandleService(self, index, refresh)


class IPTVSubProvider(CSubProviderBase):

    def __init__(self, params={}):
        CSubProviderBase.__init__(self, PrijevodiOnline(params))
