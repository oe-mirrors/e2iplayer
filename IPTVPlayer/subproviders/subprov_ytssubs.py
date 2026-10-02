# -*- coding: utf-8 -*-
# yifysubtitles.ch (YTS subtitles), movies only
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.isubprovider import CSubProviderBase, CBaseSubProviderClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetDefaultLang
from Plugins.Extensions.IPTVPlayer.libs.subtitlesmatch import matchTitle, langCode, langName, langSortKey, sortByRelease

###################################################
# FOREIGN import
###################################################
import json
import re
import urllib.parse

###################################################
# Config options for HOST
###################################################


def GetConfigList():
    optionList = []
    return optionList
###################################################


class YtsSubsProvider(CBaseSubProviderClass):

    def __init__(self, params={}):
        self.MAIN_URL = 'https://yifysubtitles.ch/'
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'Referer': self.MAIN_URL, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}
        params['cookie'] = 'ytssubs.cookie'
        CBaseSubProviderClass.__init__(self, params)
        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.dInfo = params['discover_info']

    def getMoviesList(self, cItem, nextCategory):
        printDBG('YtsSubsProvider.getMoviesList')
        title, year, season = self.wantedInfo()[:3]
        if season is not None or self.dInfo.get('season'):
            SetIPTVPlayerLastHostError(_('This subtitle provider has subtitles for movies only.'))
            return
        if not title:
            return
        urlParams = dict(self.defaultParams)
        urlParams['header'] = dict(self.HTTP_HEADER, **{'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json, text/javascript, */*; q=0.01'})
        sts, data = self.cm.getPage(self.getFullUrl('/ajax/search/?mov=' + urllib.parse.quote_plus(title)), urlParams)
        if not sts:
            return
        try:
            data = json.loads(data)
        except Exception:
            printExc()
            return
        results = []
        for item in data if isinstance(data, list) else []:
            if not isinstance(item, dict):
                continue
            imdbid = self.getStr(item.get('imdb'))
            movie = self.getStr(item.get('movie')).strip()
            if not imdbid or not movie:
                continue
            m = re.match(r'(.*?)\s+(\d{4})$', movie)  # "Inception 2010"
            results.append((m.group(1), m.group(2), imdbid) if m else (movie, '', imdbid))
        best = matchTitle(title, year, results)
        results.sort(key=lambda r: r[2] != best)
        for name, movieYear, imdbid in results:
            params = dict(cItem)
            params.update({'category': nextCategory, 'title': ('%s (%s)' % (name, movieYear)) if movieYear else name, 'base_title': name, 'imdbid': imdbid,
                           'url': self.getFullUrl('/movie-imdb/' + imdbid)})
            self.addDir(params)

    def getSubtitlesRows(self, cItem):
        sts, data = self.cm.getPage(cItem['url'], self.defaultParams)
        if not sts:
            return []
        rows = []
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, '<tr data-id', '</tr>'):
            url = self.cm.ph.getSearchGroups(item, '''href=['"](/subtitles/[^'^"]+?)['"]''')[0]
            lang = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<span', '>', 'sub-lang'), ('</span', '>'), False)[1])
            if not url or not lang:
                continue
            link = self.cm.ph.getDataBeetwenNodes(item, ('<a', '>', url), ('</a', '>'), False)[1]
            link = re.sub(r'<span[^>]*?>.*?</span>', '', link, flags=re.S)
            releases = [x for x in (self.cleanHtmlStr(x) for x in re.split(r'<br\s*/?>', link)) if x]
            rating = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<td', '>', 'rating-cell'), ('</td', '>'), False)[1])
            try:
                rating = int(rating)
            except Exception:
                rating = 0
            rows.append({'url': self.getFullUrl(url), 'lang': langCode(lang) or lang.lower(), 'lang_name': lang, 'releases': releases, 'rating': rating,
                         'hi': 'hearing impaired' in item, 'sub_id': self.cm.ph.getSearchGroups(item, '''data-id=['"]([0-9]+?)['"]''')[0]})
        return rows

    def getLanguages(self, cItem, nextCategory):
        printDBG('YtsSubsProvider.getLanguages')
        rows = self.getSubtitlesRows(cItem)
        counts = {}
        for row in rows:
            counts[row['lang']] = counts.get(row['lang'], 0) + 1
        lang = GetDefaultLang()
        for code in sorted(counts, key=lambda c: langSortKey(c, lang)):
            params = dict(cItem)
            params.update({'category': nextCategory, 'title': '%s [%s] (%d)' % (_(langName(code)), code, counts[code]), 'rows': [r for r in rows if r['lang'] == code]})
            self.addDir(params)

    def getSubtitlesList(self, cItem, nextCategory):
        printDBG('YtsSubsProvider.getSubtitlesList')
        items = []
        for row in sorted(cItem.get('rows', []), key=lambda r: -r['rating']):
            title = row['releases'][0] if row['releases'] else cItem['base_title']
            desc = [_('Rating: %s') % row['rating']]
            if row['hi']:
                desc.append(_('Hearing impaired'))
            params = dict(cItem)
            params.pop('rows', None)
            params.update({'category': nextCategory, 'title': '[%s] %s' % (row['lang'], title), 'release': ' '.join(row['releases']), 'url': row['url'], 'lang': row['lang'],
                           'sub_id': row['sub_id'], 'desc': '[/br]'.join([', '.join(desc)] + row['releases'])})
            items.append(params)
        for params in sortByRelease(items, self.releaseName(), key='release'):
            self.addDir(params)

    def getSubtitleFiles(self, cItem):
        printDBG('YtsSubsProvider.getSubtitleFiles')
        sts, data = self.cm.getPage(cItem['url'], self.defaultParams)
        if not sts:
            return
        url = self.cm.ph.getSearchGroups(data, r'''<a[^>]+?download-subtitle[^>]+?href=['"]([^'^"]+?)['"]''')[0]
        if not url:
            url = cItem['url'].replace('/subtitles/', '/subtitle/') + '.zip'
        urlParams = dict(self.defaultParams)
        urlParams['header'] = dict(self.HTTP_HEADER, Referer=cItem['url'])
        tmpDIR = self.downloadArchive(self.getFullUrl(url), urlParams)
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
            self.getMoviesList({'name': 'category'}, 'get_languages')
        elif category == 'get_languages':
            self.getLanguages(self.currItem, 'get_subtitles')
        elif category == 'get_subtitles':
            self.getSubtitlesList(self.currItem, 'get_files')
        elif category == 'get_files':
            self.getSubtitleFiles(self.currItem)
        elif category == 'unpack_archive':
            self.unpackInnerArchive(self.currItem)

        CBaseSubProviderClass.endHandleService(self, index, refresh)


class IPTVSubProvider(CSubProviderBase):

    def __init__(self, params={}):
        CSubProviderBase.__init__(self, YtsSubsProvider(params))
