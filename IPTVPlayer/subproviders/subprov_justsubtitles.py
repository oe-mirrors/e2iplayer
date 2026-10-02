# -*- coding: utf-8 -*-
# justsubtitles.com: movies only, TMDb search + a Next.js server action; the files are subdl.com
# archives, fetched through the site's own /api/download proxy (dl.subdl.com wants an api key)
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.isubprovider import CSubProviderBase, CBaseSubProviderClass
from Plugins.Extensions.IPTVPlayer.libs.subtitlesmatch import matchTitle, sortByRelease
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetDefaultLang
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus, urllib_urlencode

###################################################
# FOREIGN import
###################################################
import json
import re

###################################################
# Config options for HOST
###################################################


def GetConfigList():
    optionList = []
    return optionList
###################################################


# the languages the site offers -> the name its server action expects
SITE_LANGS = {'en': 'English', 'ar': 'Arabic', 'de': 'German', 'it': 'Italian', 'id': 'Indonesian', 'ja': 'Japanese', 'ko': 'Korean'}
# page script -> "findSubsForLang" server action id (changes with every site deployment)
ACTION_IDS = {}


class JustSubtitlesProvider(CBaseSubProviderClass):

    def __init__(self, params={}):
        params['cookie'] = 'justsubtitles.cookie'
        CBaseSubProviderClass.__init__(self, params)

        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'Referer': self.getMainUrl(), 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Encoding': 'gzip'}
        self.defaultParams = {'header': self.HTTP_HEADER}
        self.dInfo = params['discover_info']

    def getMainUrl(self):
        return 'https://www.justsubtitles.com/'

    def getLanguages(self):
        # the server action answers for one language per request, so no language menu with all of them:
        # the user's language and English
        langs = [GetDefaultLang()]
        if 'en' not in langs:
            langs.append('en')
        return [lang for lang in langs if lang in SITE_LANGS]

    def getSearchList(self, cItem, nextCategory):
        printDBG("JustSubtitlesProvider.getSearchList")
        title, year, season = self.wantedInfo()[:3]
        if season is not None or self.dInfo.get('season'):
            SetIPTVPlayerLastHostError(_('This subtitle provider has subtitles for movies only.'))
            return
        if not title:
            return
        url = 'https://search.justsubtitles.com/api/search?q=' + urllib_quote_plus(title)
        sts, data = self.cm.getPage(url, {'header': dict(self.HTTP_HEADER, Accept='application/json')})
        if not sts:
            return
        try:
            data = json.loads(data)
            data = data.get('results') if isinstance(data, dict) else None
        except Exception:
            printExc()
            return
        results = []
        for movie in data if isinstance(data, list) else []:
            if not isinstance(movie, dict) or not movie.get('id') or not self.getStr(movie.get('title')):
                continue
            foundYear = self.getStr(movie.get('release_date'))[:4]
            results.append({'title': '%s (%s)' % (movie['title'], foundYear) if foundYear else movie['title'], 'tmdb_id': str(movie['id']), 'year': foundYear,
                            'names': [movie['title'], self.getStr(movie.get('original_title')) or movie['title']], 'desc': self.getStr(movie.get('overview'))})
        best = matchTitle(title, year, [(n, r['year'], r['tmdb_id']) for r in results for n in r['names']])
        results.sort(key=lambda r: r['tmdb_id'] != best)
        for item in results:
            params = dict(cItem)
            params.update({'category': nextCategory, 'title': item['title'], 'tmdb_id': item['tmdb_id'], 'year': item['year'],
                           'movie': item['names'][0], 'desc': item['desc']})
            self.addDir(params)

    def getActionId(self, tmdbId):
        # (action id, error message)
        sts, data = self.cm.getPage(self.getFullUrl('/movie/%s/x' % tmdbId), self.defaultParams)
        if not sts:
            return '', _('Failed to connect to server "%s".') % self.getMainUrl()
        chunk = self.cm.ph.getSearchGroups(data, r'''(/_next/static/chunks/app/movie/[^"']+?\.js)''')[0]
        if not chunk:
            return '', _('The page layout of %s has changed.') % self.getMainUrl()
        if chunk not in ACTION_IDS:
            sts, data = self.cm.getPage(self.getFullUrl(chunk), self.defaultParams)
            if not sts:
                return '', _('Failed to connect to server "%s".') % self.getMainUrl()
            actionId = self.cm.ph.getSearchGroups(data, r'''createServerReference\)\("([0-9a-f]+)"''')[0]
            if not actionId:
                return '', _('The page layout of %s has changed.') % self.getMainUrl()
            ACTION_IDS[chunk] = actionId
        return ACTION_IDS[chunk], ''

    def getSubtitlesList(self, cItem, nextCategory):
        printDBG("JustSubtitlesProvider.getSubtitlesList")
        actionId, error = self.getActionId(cItem['tmdb_id'])
        if not actionId:
            SetIPTVPlayerLastHostError(error)
            return
        urlParams = {'header': dict(self.HTTP_HEADER, **{'Accept': 'text/x-component', 'Content-Type': 'text/plain;charset=UTF-8', 'Next-Action': actionId,
                                                         'Origin': self.getMainUrl()[:-1], 'Referer': self.getFullUrl('/movie/%s/x' % cItem['tmdb_id'])}),
                     'raw_post_data': True}
        for lang in self.getLanguages():
            body = json.dumps([cItem['tmdb_id'], {'code': lang.upper(), 'language': SITE_LANGS[lang]}, cItem.get('year', '')])
            sts, data = self.cm.getPage(self.getMainUrl(), urlParams, body)
            if not sts:
                continue
            # RSC row 1 holds the result of the action
            m = re.search(r'(?m)^1:', data)
            try:
                data = json.JSONDecoder(strict=False).raw_decode(data, m.end())[0] if m else {}
            except Exception:
                printExc()
                continue
            if not isinstance(data, dict):
                continue
            movies = data.get('results')
            movie = movies[0] if isinstance(movies, list) and movies and isinstance(movies[0], dict) else {}
            imdbid = self.getStr(movie.get('imdb_id')).replace('tt', '')
            subtitles = data.get('subtitles')
            items = []
            for sub in subtitles if isinstance(subtitles, list) else []:
                if not isinstance(sub, dict) or not self.getStr(sub.get('url')):
                    continue
                name = self.getStr(sub.get('release_name')) or self.getStr(sub.get('name')) or cItem['movie']
                # old ".rar" entries answer 404/502, subdl serves every upload as ".zip" now
                url = re.sub(r'\.rar$', '.zip', sub['url'].split('?')[0])
                if url.startswith('/'):
                    url = 'https://dl.subdl.com' + url
                desc = [_('Author: %s') % sub['author']] if self.getStr(sub.get('author')) else []
                if sub.get('hi'):
                    desc.append(_('Hearing impaired'))
                params = dict(cItem)
                params.update({'category': nextCategory, 'title': '[%s] %s' % (lang, name), 'lang': lang, 'release': name, 'sub_url': url,
                               'sub_id': re.sub(r'\D', '', url.rsplit('/', 1)[-1].split('-')[-1]), 'imdbid': imdbid, 'desc': '[/br]'.join(desc)})
                items.append(params)
            for params in sortByRelease(items, self.releaseName(), 'release'):
                self.addDir(params)

    def getFilesList(self, cItem):
        printDBG("JustSubtitlesProvider.getFilesList")
        query = {'url': cItem['sub_url'], 'moviename': cItem['movie'], 'year': cItem.get('year', ''), 'backdrop': '', 'movieId': cItem['tmdb_id']}
        tmpDIR = self.downloadArchive(self.getFullUrl('/api/download?') + urllib_urlencode(query), {'header': self.HTTP_HEADER})
        if tmpDIR is None:
            return
        self.listArchiveFiles(dict(cItem, path=tmpDIR))

    def handleService(self, index, refresh=0):
        printDBG('handleService start')

        CBaseSubProviderClass.handleService(self, index, refresh)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

        if name is None:
            self.getSearchList({'name': 'category'}, 'get_subtitles')
        elif category == 'get_subtitles':
            self.getSubtitlesList(self.currItem, 'get_files')
        elif category == 'get_files':
            self.getFilesList(self.currItem)
        elif category == 'unpack_archive':
            self.unpackInnerArchive(self.currItem)

        CBaseSubProviderClass.endHandleService(self, index, refresh)


class IPTVSubProvider(CSubProviderBase):

    def __init__(self, params={}):
        CSubProviderBase.__init__(self, JustSubtitlesProvider(params))
