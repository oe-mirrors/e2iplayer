# -*- coding: utf-8 -*-
# subs.ro: Romanian site (subtitles mostly in Romanian, some in English and other languages), the downloads are zip / rar archives
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.isubprovider import CSubProviderBase, CBaseSubProviderClass
from Plugins.Extensions.IPTVPlayer.libs.subtitlesmatch import matchTitle, normalizeTitle, langCode, langSortKey, episodeFits, sortByRelease
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import (
    printDBG,
    printExc,
    GetDefaultLang,
)

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


# the site's flag names (flag-<name>-big.png) that langCode does not know
SITE_LANGS = {'rom': 'ro', 'ung': 'hu'}


class SubsRoProvider(CBaseSubProviderClass):

    def __init__(self, params={}):
        params = dict(params)
        params['cookie'] = 'subsro.cookie'
        CBaseSubProviderClass.__init__(self, params)

        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'Referer': self.getMainUrl(), 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Encoding': 'gzip, deflate'}

        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

    def getMainUrl(self):
        return 'https://subs.ro/'

    def getMaxFileSize(self):
        return 1024 * 1024 * 10  # 10MB, max size of sub file to be download

    @staticmethod
    def langOrder(lang):
        # the user's language, Romanian (the site's own language), English, then by name
        notDefault, notEnglish, name = langSortKey(lang, GetDefaultLang())
        return (notDefault, lang != 'ro', notEnglish, name)

    @staticmethod
    def releaseFits(release, season, episode):
        # 'Breaking Bad - Sezonul 2' is a season pack, 'Sezoanele 1-2' several seasons in one archive
        m = re.search(r'(?i)\bsezoanele\s+(\d+)\s*-\s*(\d+)', release)
        if m and season and int(m.group(1)) <= int(season) <= int(m.group(2)):
            return True
        return episodeFits(re.sub(r'(?i)\bsezonul\s+', 'Season ', release), season, episode)

    def getSearchList(self, cItem, nextCategory):
        printDBG("SubsRoProvider.getSearchList")
        title, year, season, episode = self.wantedInfo()

        # the search form carries a token, without it the search answers "He's dead, Jim!"
        searchUrl = self.getFullUrl('/cautare')
        sts, data = self.cm.getPage(searchUrl, self.defaultParams)
        if not sts:
            SetIPTVPlayerLastHostError(_('subs.ro does not answer.'))
            return
        antispam = self.cm.ph.getSearchGroups(data, r'''<input[^>]+?name=['"]antispam['"][^>]+?value=['"]([^'"]+?)['"]''')[0]
        if antispam == '':
            antispam = self.cm.ph.getSearchGroups(data, r'''<input[^>]+?value=['"]([^'"]+?)['"][^>]+?name=['"]antispam['"]''')[0]

        urlParams = dict(self.defaultParams)
        urlParams['header'] = dict(self.HTTP_HEADER, **{'Referer': searchUrl, 'Accept': '*/*', 'X-Requested-With': 'XMLHttpRequest', 'HX-Request': 'true'})
        query = {'antispam': antispam, 'type': 'subtitrari', 'titlu-film': title, 'external_id': '', 'versiune-film': '', 'limba': ''}
        sts, data = self.cm.getPage(self.getFullUrl('/ajax/search'), urlParams, query)
        if not sts:
            SetIPTVPlayerLastHostError(_('subs.ro does not answer.'))
            return
        if 'data-subtitle-result' not in data and 'dead, Jim' in data:
            SetIPTVPlayerLastHostError(_('The site rejected the search request.'))
            return

        results = []
        for item in data.split('data-subtitle-result=')[1:]:
            url = self.cm.ph.getSearchGroups(item, r'''href=['"]([^'"]*?/subtitrare/descarca/[^'"]+?)['"]''')[0]
            if url == '':
                continue
            subId = url.rstrip('/').rsplit('/', 1)[-1]
            movie = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'''data-movie-name=['"]([^'"]+?)['"]''')[0])
            # 'Breaking Bad - Sezonul 2' -> 'Breaking Bad'
            name = re.sub(r'(?i)\s+-\s+sezo(?:nul|anele)\b.*$', '', movie)
            release = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'''title=['"]Subtitrare\s+([^'"]+?)['"]''')[0])
            if release.lower().startswith(name.lower()):
                release = release[len(name):].strip(' -')
            foundYear = self.cm.ph.getSearchGroups(item, r'''>\s*\((\d{4})\)\s*<''')[0]
            siteLang = self.cm.ph.getSearchGroups(item, r'''flag\-([a-z]+?)\-big\.png''')[0]
            lang = SITE_LANGS.get(siteLang) or langCode(siteLang) or siteLang
            imdbid = self.cm.ph.getSearchGroups(item, r'''imdb\.com/title/(tt[0-9]+)''')[0]

            descTab = [release]
            for label, marker in ((_('Translator: %s'), r'Traduc[^<]*?'), (_('Uploader: %s'), r'Uploader:')):
                m = re.search(marker + r'</span>(.*?)</span>', item, re.S)
                value = self.cleanHtmlStr(m.group(1)) if m else ''
                if value != '':
                    descTab.append(label % value)
            downloads = self.cm.ph.getSearchGroups(item, r'''download\.svg[^>]+?>\s*<span[^>]*?>([0-9.,]+)<''')[0]
            if downloads != '':
                descTab.append(_('Downloads: %s') % downloads)
            descTab.append(self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'leading-relaxed'), ('</div', '>'), False)[1]))

            # alternative titles: 'Moromete Family: On the Edge of Time (Morometii 2)'
            aliases = [name, name.split(' (', 1)[0]] + re.findall(r'\(([^)]+)\)', name)
            results.append({'name': name, 'movie': movie, 'aliases': aliases, 'year': foundYear, 'key': imdbid or '%s|%s' % (normalizeTitle(name), foundYear),
                            'sub_id': subId, 'url': self.getFullUrl(url), 'release': release, 'lang': lang, 'imdbid': imdbid,
                            'page': self.getFullUrl('/subtitrare/%s' % url.split('/descarca/', 1)[-1]),
                            'title': '[%s] %s%s%s' % (lang, name, ' (%s)' % foundYear if foundYear else '', ' ' + release if release else ''),
                            'desc': '[/br]'.join(x for x in descTab if x)})

        # the search is fuzzy ("Inception" brings "Soudain le vide" too): only the title that fits, when one fits
        # a tv show: the year of the episode is not the year of the show
        best = matchTitle(title, None if season else year, [(alias, r['year'], r['key']) for r in results for alias in r['aliases'] if alias])
        if best is not None:
            results = [r for r in results if r['key'] == best]
        if season and episode:
            # the season is often only in the movie name ('Breaking Bad - Sezonul 2'), not in the release text
            fits = [r for r in results if self.releaseFits(r['movie'] + ' ' + r['release'], season, episode)]
            if fits:
                results = fits

        if not results:
            SetIPTVPlayerLastHostError(_('No subtitles found.'))
            return
        byLang = {}
        for r in results:
            byLang.setdefault(r['lang'], []).append(r)
        for lang in sorted(byLang, key=self.langOrder):
            for r in sortByRelease(byLang[lang], self.releaseName(), 'release'):
                params = dict(cItem)
                params.update({'category': nextCategory, 'title': r['title'], 'url': r['url'], 'page': r['page'], 'lang': r['lang'],
                               'sub_id': r['sub_id'], 'imdbid': r['imdbid'], 'desc': r['desc']})
                self.addDir(params)

    def getSubtitlesList(self, cItem):
        printDBG("SubsRoProvider.getSubtitlesList")

        # the frame rate is only on the details page
        fps = 0
        sts, data = self.cm.getPage(cItem['page'], self.defaultParams)
        if sts:
            try:
                # <p ...>FPS</p> <p ...>23.976</p>
                tmp = self.cm.ph.getSearchGroups(data, r'''>\s*FPS\s*</p>\s*<p[^>]*>\s*([0-9]+(?:\.[0-9]+)?)\s*<''')[0]
                fps = float(tmp) if tmp else 0
            except Exception:
                printExc()

        urlParams = dict(self.defaultParams)
        urlParams['header'] = dict(self.HTTP_HEADER, Referer=cItem['page'])
        tmpDIR = self.downloadArchive(cItem['url'], urlParams)
        if None is tmpDIR:
            return

        cItem = dict(cItem)
        cItem.update({'path': tmpDIR, 'fps': fps})
        self.listArchiveFiles(cItem)

    def listArchiveFiles(self, cItem):
        printDBG("SubsRoProvider.listArchiveFiles")
        season, episode = self.wantedInfo()[2:]
        cItem = dict(cItem)
        cItem.update({'category': ''})
        self.listSupportedFilesFromPath(cItem, self.getSupportedFormats(all=True), dirCategory='list_dir')
        for item in self.currList:
            item['desc'] = cItem.get('path', '') + '/'
            if item.get('type') != 'subtitle' and item.get('file_path', '').lower().endswith(('.zip', '.rar')):
                item['category'] = 'unpack_archive'
        # a season pack: the files of this episode, when it has them
        if season and episode:
            fits = [item for item in self.currList if item.get('type') != 'subtitle' or episodeFits(item['title'], season, episode)]
            if any(item.get('type') == 'subtitle' for item in fits):
                self.currList = fits

    def handleService(self, index, refresh=0):
        printDBG('handleService start')

        CBaseSubProviderClass.handleService(self, index, refresh)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

        # MAIN MENU
        if name is None:
            self.getSearchList({'name': 'category'}, 'get_subtitles')
        elif category == 'list_dir':
            self.listArchiveFiles(self.currItem)
        elif category == 'unpack_archive':
            self.unpackInnerArchive(self.currItem)
        elif category == 'get_subtitles':
            self.getSubtitlesList(self.currItem)

        CBaseSubProviderClass.endHandleService(self, index, refresh)


class IPTVSubProvider(CSubProviderBase):

    def __init__(self, params={}):
        CSubProviderBase.__init__(self, SubsRoProvider(params))
