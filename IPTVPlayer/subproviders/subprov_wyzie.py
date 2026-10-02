# -*- coding: utf-8 -*-
# Wyzie Subs API (https://docs.wyzie.io/subs/usage/direct): search by IMDb id, a free key from
# https://store.wyzie.io/redeem is needed for every request
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.isubprovider import CSubProviderBase, CBaseSubProviderClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, GetDefaultLang
from Plugins.Extensions.IPTVPlayer.libs.subtitlesmatch import langCode, langName, langSortKey, sortByRelease

###################################################
# FOREIGN import
###################################################
import json
import urllib.parse
from Components.config import config

###################################################
# Config options for HOST
###################################################


def GetConfigList():
    optionList = []
    return optionList
###################################################


class WyzieProvider(CBaseSubProviderClass):

    def __init__(self, params={}):
        self.MAIN_URL = 'https://sub.wyzie.io/'
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'application/json, */*'}
        CBaseSubProviderClass.__init__(self, params)
        self.defaultParams = {'header': self.HTTP_HEADER}

    def getApiKey(self):
        return config.plugins.iptvplayer.wyzieapi.value.strip()

    def getMoviesTitles(self, cItem, nextCategory):
        printDBG('WyzieProvider.getMoviesTitles')
        if not self.getApiKey():
            SetIPTVPlayerLastHostError(_('Wyzie Subs needs an API key. You can get a free one at https://store.wyzie.io/redeem and enter it in the E2iPlayer configuration.'))
            return
        # imdbGetMoviesByTitle drops year / episode itself
        sts, tab = self.imdbGetMoviesByTitle(self.params['confirmed_title'])
        if not sts:
            return
        for item in tab:
            params = dict(cItem)
            params.update(item)  # item = {'title', 'base_title', 'year', 'imdbid'}
            params.update({'category': nextCategory})
            self.addDir(params)

    def getType(self, cItem):
        printDBG('WyzieProvider.getType')
        imdbid = cItem['imdbid']
        if self.getTypeFromThemoviedb(imdbid, cItem['title']) == 'series':
            promSeason = self.wantedInfo()[2]
            sts, tab = self.imdbGetSeasons(imdbid, promSeason)
            if not sts:
                return
            for item in tab:
                params = dict(cItem)
                params.update({'category': 'get_episodes', 'item_title': cItem['title'], 'season': item, 'title': _('Season %s') % item})
                self.addDir(params)
        else:
            self.getLanguages(cItem, 'get_subtitles')

    def getEpisodes(self, cItem, nextCategory):
        printDBG('WyzieProvider.getEpisodes')
        season = cItem['season']
        promEpisode = self.wantedInfo()[3]
        sts, tab = self.imdbGetEpisodesForSeason(cItem['imdbid'], season, promEpisode)
        if not sts:
            return
        for item in tab:
            if not item['episode'].isdigit():
                continue
            params = dict(cItem)
            params.update(item)  # item = "episode_title", "episode", "eimdbid"
            title = 's{0}e{1} {2}'.format(str(season).zfill(2), str(item['episode']).zfill(2), item['episode_title'])
            params.update({'category': nextCategory, 'title': title})
            self.addDir(params)

    def search(self, cItem):
        # the key has to be in the query string (the API ignores an Authorization / X-API-Key header),
        # so it is in the debug log with the url
        query = {'id': 'tt' + cItem['imdbid'], 'key': self.getApiKey()}
        if cItem.get('season') and cItem.get('episode'):
            query.update({'season': cItem['season'], 'episode': cItem['episode']})
        url = self.getFullUrl('/search?' + urllib.parse.urlencode(query))
        sts, data = self.cm.getPage(url, self.defaultParams)
        body = getattr(data, 'meta', {}).get('body_head') or data
        try:
            body = json.loads(body)
        except Exception:
            body = None
        if sts and isinstance(body, list):
            return body
        status = getattr(data, 'meta', {}).get('status_code') or self.cm.meta.get('status_code')
        message = body.get('message', '') if isinstance(body, dict) else ''
        printDBG('WyzieProvider.search status[%s] message[%s]' % (status, message))
        if status == 400 or 'no subtitles' in message.lower():
            return []
        if status in (401, 403):
            SetIPTVPlayerLastHostError(_('Wyzie Subs API key rejected: %s') % message)
        elif status == 429:
            SetIPTVPlayerLastHostError(_('Wyzie Subs: the daily request limit of the API key is reached.'))
        elif message:
            SetIPTVPlayerLastHostError('Wyzie Subs: %s' % message)
        return []

    def getLanguages(self, cItem, nextCategory):
        printDBG('WyzieProvider.getLanguages')
        formats = self.getSupportedFormats(all=True)
        rows = []
        for item in self.search(cItem):
            if not isinstance(item, dict) or not self.getStr(item.get('url')):
                continue
            ext = (self.getStr(item.get('format')) or 'srt').lower()
            if ext not in formats:
                continue
            code = langCode(self.getStr(item.get('language'))) or self.getStr(item.get('language')).lower() or '--'
            releases = item.get('releases')
            rows.append({'url': item['url'], 'lang': code, 'ext': ext, 'sub_id': str(item.get('id', '')),
                         'release': self.getStr(item.get('release')) or self.getStr(item.get('fileName')) or self.getStr(item.get('media')) or cItem.get('base_title', ''),
                         'releases': [x for x in releases if self.getStr(x)] if isinstance(releases, list) else [],
                         'hi': bool(item.get('isHearingImpaired')), 'ai': bool(item.get('ai')),
                         'source': self.getStr(item.get('source')), 'downloads': item.get('downloadCount') or 0})
        counts = {}
        for row in rows:
            counts[row['lang']] = counts.get(row['lang'], 0) + 1
        lang = GetDefaultLang()
        for code in sorted(counts, key=lambda c: langSortKey(c, lang)):
            params = dict(cItem)
            params.update({'category': nextCategory, 'title': '%s [%s] (%d)' % (_(langName(code)), code, counts[code]), 'rows': [r for r in rows if r['lang'] == code]})
            self.addDir(params)

    def getSubtitlesList(self, cItem):
        printDBG('WyzieProvider.getSubtitlesList')
        items = []
        for row in sorted(cItem.get('rows', []), key=lambda r: -int(r['downloads']) if str(r['downloads']).isdigit() else 0):
            title = '[%s] %s' % (row['lang'], row['release'])
            if row['ai']:
                title += ' (%s)' % _('machine translated')
            desc = [x for x in (row['ext'], row['source'], row['hi'] and _('Hearing impaired'), _('Downloads: %s') % row['downloads']) if x]
            params = dict(cItem)
            params.pop('rows', None)
            params.update({'title': title, 'release': row['release'], 'url': row['url'], 'lang': row['lang'], 'ext': row['ext'], 'sub_id': row['sub_id'],
                           'desc': '[/br]'.join([', '.join(desc)] + row['releases'])})
            items.append(params)
        for params in sortByRelease(items, self.releaseName(), key='release'):
            self.addSubtitle(params)

    def downloadSubtitleFile(self, cItem):
        printDBG('WyzieProvider.downloadSubtitleFile')
        sts, data = self.downloadBinary(cItem['url'], self.defaultParams)
        if not sts:
            SetIPTVPlayerLastHostError(_('Failed to download subtitle.'))
            return {}
        # an HTML / JSON error answer is refused there, MicroDVD ("{1}{100}...") is not
        return self.saveSubtitleData(data, cItem['release'], cItem['lang'], cItem['sub_id'], cItem.get('eimdbid') or cItem['imdbid'])

    def handleService(self, index, refresh=0):
        printDBG('handleService start')

        CBaseSubProviderClass.handleService(self, index, refresh)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
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
        CSubProviderBase.__init__(self, WyzieProvider(params))
