# -*- coding: utf-8 -*-
# moviesubtitles.org: movies only, 13 languages, the downloads are zip archives
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.isubprovider import CSubProviderBase, CBaseSubProviderClass
from Plugins.Extensions.IPTVPlayer.libs.subtitlesmatch import matchTitle, normalizeTitle, langName, langSortKey, sortByRelease
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, GetDefaultLang

###################################################
# FOREIGN import
###################################################
import html
import re

###################################################
# Config options for HOST
###################################################


def GetConfigList():
    optionList = []
    return optionList
###################################################


# flag name used by the site -> ISO 639-1 (ar br de en es fr gr hu it pl ru tr ua)
SITE_FLAGS = {'gr': 'el', 'br': 'pt-br', 'ua': 'uk'}


class MovieSubtitlesProvider(CBaseSubProviderClass):

    def __init__(self, params={}):
        params['cookie'] = 'moviesubtitles.cookie'
        CBaseSubProviderClass.__init__(self, params)

        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'Referer': self.getMainUrl(), 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Encoding': 'gzip'}
        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.dInfo = params['discover_info']

    def getMainUrl(self):
        return 'https://www.moviesubtitles.org/'

    def getSearchList(self, cItem, nextCategory):
        printDBG("MovieSubtitlesProvider.getSearchList")
        title, year, season = self.wantedInfo()[:3]
        if season is not None or self.dInfo.get('season'):
            SetIPTVPlayerLastHostError(_('This subtitle provider has subtitles for movies only.'))
            return
        if not title:
            return
        # the site answers search.php with HTTP 500 but a valid result page
        data = self.cm.getPage(self.getFullUrl('/search.php'), self.defaultParams, {'q': title})[1]
        if not data:
            return
        results = []
        for url, name, found_year in re.findall(r'<a\s+href="(/movie-\d+\.html)">([^<]+?)\s*\((\d{4})\)</a>', data):
            name = html.unescape(name)
            # "Fate of the Furious, The (Fast and Furious 8)": main or alternative title
            names = [n for n in re.match(r'(.*?)(?:\s*\(([^)]*)\))?$', name).groups() if n]
            results.append({'title': '%s (%s)' % (name, found_year), 'url': self.getFullUrl(url), 'names': names, 'year': found_year})
        best = matchTitle(title, year, [(n, r['year'], r['url']) for r in results for n in r['names']])
        results.sort(key=lambda r: (r['url'] != best, not any(normalizeTitle(n) == normalizeTitle(title) for n in r['names'])))
        for item in results:
            params = dict(cItem)
            params.update({'category': nextCategory, 'title': item['title'], 'url': item['url']})
            self.addDir(params)

    def getLanguages(self, cItem, nextCategory):
        printDBG("MovieSubtitlesProvider.getLanguages")
        # the movie page lists the subtitles of all languages
        sts, data = self.cm.getPage(cItem['url'], self.defaultParams)
        if not sts:
            return
        rows = []
        for item in data.split('<div class="subtitle">')[1:]:
            flag = self.cm.ph.getSearchGroups(item, r'''flags/[^"]+?"[^>]+?alt="([a-z]+)"''')[0]
            lang = SITE_FLAGS.get(flag, flag)
            url = self.cm.ph.getSearchGroups(item, r'''href="(/subtitle-\d+\.html)"''')[0]
            if not lang or not url:
                continue
            name = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<b>', '</b>', False)[1])
            name = re.sub(r'\s+\S+ subtitles\b|\s*\(\)', '', name)  # drop "english subtitles"
            parts = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'''title="parts">([^<]*)<''')[0])
            if parts not in ('', '1'):
                name += ' ' + _('[%s CD]') % parts
            downloads = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'''title="downloaded">([^<]*)<''')[0])
            rows.append({'lang': lang, 'name': name, 'sub_id': re.sub(r'\D', '', url), 'url': self.getFullUrl(url.replace('/subtitle-', '/download-')),
                         'desc': _('Downloads: %s') % downloads if downloads else ''})
        counts = {}
        for row in rows:
            counts[row['lang']] = counts.get(row['lang'], 0) + 1
        lang = GetDefaultLang()
        for code in sorted(counts, key=lambda c: langSortKey(c, lang)):
            params = dict(cItem)
            params.update({'category': nextCategory, 'title': '%s [%s] (%d)' % (_(langName(code)), code, counts[code]), 'rows': [r for r in rows if r['lang'] == code]})
            self.addDir(params)

    def getSubtitlesList(self, cItem, nextCategory):
        printDBG("MovieSubtitlesProvider.getSubtitlesList")
        items = []
        for row in cItem.get('rows', []):
            params = dict(cItem)
            params.pop('rows', None)
            params.update({'category': nextCategory, 'title': '[%s] %s' % (row['lang'], row['name']), 'lang': row['lang'], 'sub_id': row['sub_id'],
                           'url': row['url'], 'release': row['name'], 'desc': row['desc']})
            items.append(params)
        for params in sortByRelease(items, self.releaseName(), 'release'):
            self.addDir(params)

    def getFilesList(self, cItem):
        printDBG("MovieSubtitlesProvider.getFilesList")
        # download-<id>.html redirects to the zip file
        tmpDIR = self.downloadArchive(cItem['url'], {'header': self.HTTP_HEADER})
        if tmpDIR is None:
            return
        self.listArchiveFiles(dict(cItem, path=tmpDIR, imdbid=''))

    def handleService(self, index, refresh=0):
        printDBG('handleService start')

        CBaseSubProviderClass.handleService(self, index, refresh)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

        if name is None:
            self.getSearchList({'name': 'category'}, 'get_languages')
        elif category == 'get_languages':
            self.getLanguages(self.currItem, 'get_subtitles')
        elif category == 'get_subtitles':
            self.getSubtitlesList(self.currItem, 'get_files')
        elif category == 'get_files':
            self.getFilesList(self.currItem)
        elif category == 'unpack_archive':
            self.unpackInnerArchive(self.currItem)

        CBaseSubProviderClass.endHandleService(self, index, refresh)


class IPTVSubProvider(CSubProviderBase):

    def __init__(self, params={}):
        CSubProviderBase.__init__(self, MovieSubtitlesProvider(params))
