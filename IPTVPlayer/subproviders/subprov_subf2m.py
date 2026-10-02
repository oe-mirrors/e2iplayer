# -*- coding: utf-8 -*-
# subf2m.co (Subscene mirror). The site search answers with HTTP 500, so the title pages are opened
# by their Subscene name: /subtitles/the-matrix, /subtitles/breaking-bad-second-season
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.isubprovider import CSubProviderBase, CBaseSubProviderClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, GetDefaultLang
from Plugins.Extensions.IPTVPlayer.libs.subtitlesmatch import SEASONS, normalizeTitle, romanVariations, yearMatch, langCode, langName, langSortKey, \
    episodeFilters, sortByRelease

###################################################
# FOREIGN import
###################################################
import re

###################################################
# Config options for HOST
###################################################


def GetConfigList():
    optionList = []
    return optionList
###################################################


class Subf2mProvider(CBaseSubProviderClass):

    def __init__(self, params={}):
        self.MAIN_URL = 'https://subf2m.co/'
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'Referer': self.MAIN_URL, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}
        params['cookie'] = 'subf2m.cookie'
        CBaseSubProviderClass.__init__(self, params)
        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

    def slugCandidates(self, name, year, season):
        # 'Rocky II' -> rocky-ii, rocky-2 (+ -<year> or -<ordinal>-season)
        slugs = ['-'.join(words) for words in romanVariations(normalizeTitle(name).split())]
        if season:
            ordinal = SEASONS[season].lower() if season < len(SEASONS) else str(season)
            return ['%s-%s-season' % (s, ordinal) for s in slugs] + slugs  # season page, else the complete series
        return slugs + ['%s-%s' % (s, year) for s in slugs if year]

    def getTitlePage(self, name, year, season):
        for slug in self.slugCandidates(name, year, season):
            url = self.getFullUrl('/subtitles/' + slug)
            sts, data = self.cm.getPage(url, self.defaultParams)
            if not sts or not re.search(r'''class=['"]download''', data):
                continue
            found = self.cm.ph.getSearchGroups(data, r'Year:\s*</strong>\s*([0-9]{4})')[0]
            if found and not yearMatch(found, year):
                printDBG('Subf2mProvider %s is from %s, not %s' % (slug, found, year))
                continue
            header = self.cm.ph.getDataBeetwenNodes(data, ('<h2', '>'), ('</h2', '>'), False)[1]
            title = self.cleanHtmlStr(header.split('<a', 1)[0]) or name
            imdbid = self.cm.ph.getSearchGroups(header, r'/title/tt([0-9]+)')[0]
            return url, title, imdbid, data
        return None, '', '', ''

    def getSubtitlesRows(self, data, season, episode):
        if season:
            thisEpisode, anyEpisode, thisSeason = episodeFilters(season, episode)
        episodes, packs = [], []
        for item in re.split(r'''<li class=['"]item''', data)[1:]:
            url = self.cm.ph.getSearchGroups(item, r'''<a[^>]+?class=['"]download[^>]+?href=['"]([^'^"]+?)['"]''')[0]
            lang = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<span', '>', 'language'), ('</span', '>'), False)[1])
            if not url or not lang:
                continue
            releases = [self.cleanHtmlStr(x) for x in self.cm.ph.getAllItemsBeetwenMarkers(self.cm.ph.getDataBeetwenNodes(item, ('<ul', '>', 'scrolllist'), ('</ul', '>'), False)[1], '<li', '</li>')]
            releases = [x for x in releases if x]
            if not releases and season:
                continue
            row = {'url': self.getFullUrl(url), 'lang': langCode(lang) or lang.lower(), 'releases': releases, 'release': releases[0] if releases else '',
                   'rate': self.cm.ph.getSearchGroups(item, r'''class=['"]rate ([^'^"]+?)['"]''')[0].strip(),
                   'author': self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, 'By ', '</b>', False)[1]),
                   'comment': self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<p>', '</p>', False)[1])}
            if not season:
                episodes.append(row)
                continue
            matching = [rel for rel in releases if thisEpisode.search(rel)]
            if matching:
                row['release'] = matching[0]
                episodes.append(row)
            elif not any(anyEpisode.search(rel) for rel in releases) and any(thisSeason.search(rel) for rel in releases):
                row['pack'] = True  # the whole season in one archive
                packs.append(row)
        return episodes + packs

    def getLanguages(self, cItem, nextCategory):
        printDBG('Subf2mProvider.getLanguages')
        title, year, season, episode = self.wantedInfo()
        if not title:
            return
        # season pages carry the year of the season, not of the show
        url, pageTitle, imdbid, data = self.getTitlePage(title, None if season else year, season or 0)
        if not url:
            return
        rows = self.getSubtitlesRows(data, season, episode)
        counts = {}
        for row in rows:
            counts[row['lang']] = counts.get(row['lang'], 0) + 1
        lang = GetDefaultLang()
        for code in sorted(counts, key=lambda c: langSortKey(c, lang)):
            params = dict(cItem)
            params.update({'category': nextCategory, 'title': '%s [%s] (%d)' % (_(langName(code)), code, counts[code]), 'desc': pageTitle, 'base_title': pageTitle, 'imdbid': imdbid,
                           'rows': [r for r in rows if r['lang'] == code]})
            self.addDir(params)

    def getSubtitlesList(self, cItem, nextCategory):
        printDBG('Subf2mProvider.getSubtitlesList')
        items = []
        for row in cItem.get('rows', []):
            title = row['release'] or '%s (%s)' % (cItem['base_title'], row['url'].rsplit('/', 1)[-1])
            if row.get('pack'):
                title += ' [%s]' % _('season pack')
            desc = [x for x in (row['rate'], row['author'] and _('By %s') % row['author'], row['comment']) if x]
            params = dict(cItem)
            params.pop('rows', None)
            params.update({'category': nextCategory, 'title': '[%s] %s' % (row['lang'], title), 'release': row['release'], 'url': row['url'], 'lang': row['lang'],
                           'sub_id': row['url'].rsplit('/', 1)[-1], 'pack': row.get('pack', False),
                           'desc': '[/br]'.join([', '.join(desc)] + row['releases'])})
            items.append(params)
        items = sortByRelease(items, self.releaseName(), key='release')
        items.sort(key=lambda it: it['pack'])
        for params in items:
            self.addDir(params)

    def getSubtitleFiles(self, cItem):
        printDBG('Subf2mProvider.getSubtitleFiles')
        urlParams = dict(self.defaultParams)
        urlParams['header'] = dict(self.HTTP_HEADER, Referer=cItem['url'])
        tmpDIR = self.downloadArchive(cItem['url'] + '/download', urlParams)
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
            self.getLanguages({'name': 'category'}, 'get_subtitles')
        elif category == 'get_subtitles':
            self.getSubtitlesList(self.currItem, 'get_files')
        elif category == 'get_files':
            self.getSubtitleFiles(self.currItem)
        elif category == 'unpack_archive':
            self.unpackInnerArchive(self.currItem)

        CBaseSubProviderClass.endHandleService(self, index, refresh)


class IPTVSubProvider(CSubProviderBase):

    def __init__(self, params={}):
        CSubProviderBase.__init__(self, Subf2mProvider(params))
