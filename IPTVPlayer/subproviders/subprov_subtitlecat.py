# -*- coding: utf-8 -*-
# subtitlecat.com: every subtitle has its original language plus the machine translations that were
# already made on the site (new translations are made in the browser, so only existing ones are offered)
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.isubprovider import CSubProviderBase, CBaseSubProviderClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, GetDefaultLang
from Plugins.Extensions.IPTVPlayer.libs.subtitlesmatch import langCode, langName, langSortKey, episodeFits, sortByRelease

###################################################
# FOREIGN import
###################################################
import re
import urllib.parse

###################################################
# Config options for HOST
###################################################


def GetConfigList():
    optionList = []
    return optionList
###################################################


class SubtitlecatProvider(CBaseSubProviderClass):
    # site codes that differ from ISO 639-1; the other region codes (zh-tw, es-419, pt-br) stay as they
    # are, the site has them next to zh / es / pt
    SITE_CODES = {'iw': 'he', 'zh-cn': 'zh', 'sr-me': 'sr', 'jw': 'jv'}
    # the key of an original whose language the search list did not name
    UNKNOWN_LANG = '--'

    def __init__(self, params={}):
        self.MAIN_URL = 'https://www.subtitlecat.com/'
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'Referer': self.MAIN_URL, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}
        params['cookie'] = 'subtitlecat.cookie'
        CBaseSubProviderClass.__init__(self, params)
        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

    def siteLang(self, code):
        code = code.lower()
        return self.SITE_CODES.get(code, langCode(code) or code)

    def search(self, query):
        url = self.getFullUrl('index.php?search=' + urllib.parse.quote_plus(query))
        sts, data = self.cm.getPage(url, self.defaultParams)
        if not sts:
            return []
        rows = []
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, '<tr>', '</tr>'):
            td = self.cm.ph.getDataBeetwenMarkers(item, '<td>', '</td>', False)[1]
            href = self.cm.ph.getSearchGroups(td, '''href=['"](subs/[^'^"]+?)['"]''')[0]
            if not href:
                continue
            name = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(td, '<a', '</a>')[1])
            orig = self.cm.ph.getSearchGroups(td, r'\(translated from ([^)]+)\)')[0].strip()
            desc = [_('Original language: %s') % orig] if orig else []
            for metric in self.cm.ph.getAllItemsBeetwenNodes(item, ('<span', '>', 'metric-value'), ('</td', '>'), False):
                metric = self.cleanHtmlStr(metric)
                if metric:
                    desc.append(metric)
            rows.append({'name': name, 'url': self.getFullUrl(href), 'orig': orig, 'orig_lang': langCode(orig) or '', 'desc': ', '.join(desc)})
        printDBG('SubtitlecatProvider.search "%s" -> %d' % (query, len(rows)))
        return rows

    def getSearchList(self, cItem, nextCategory):
        printDBG('SubtitlecatProvider.getSearchList')
        title, year, season, episode = self.wantedInfo()
        if not title:
            return
        if season and episode:
            rows = [r for r in self.search('%s S%02dE%02d' % (title, int(season), int(episode))) if episodeFits(r['name'], season, episode)]
        else:
            rows = (year and self.search('%s %s' % (title, year))) or self.search(title)
        items = []
        for row in rows:
            params = dict(cItem)
            params.update({'category': nextCategory, 'url': row['url'], 'base_title': row['name'], 'orig_lang': row['orig_lang'], 'desc': row['desc'],
                           'title': ('[%s] ' % row['orig_lang'] if row['orig_lang'] else '') + row['name']})
            items.append(params)
        # the user's language as original first, then English originals, the rest in release order
        lang = GetDefaultLang()
        items = sortByRelease(items, self.releaseName(), key='base_title')
        items.sort(key=lambda it: langSortKey(it['orig_lang'], lang)[:2])
        for params in items:
            self.addDir(params)

    def getSubtitlesList(self, cItem):
        printDBG('SubtitlecatProvider.getSubtitlesList')
        sts, data = self.cm.getPage(cItem['url'], self.defaultParams)
        if not sts:
            return
        links = {}
        for code, href in re.findall(r'''<a[^>]+?id=['"]download_([^'^"]+?)['"][^>]+?href=['"]([^'^"]+?\.srt)['"]''', data):
            # two site codes for one language (sr / sr-me): the first link
            links.setdefault(self.siteLang(code), self.getFullUrl(urllib.parse.quote(href, safe='/%')))
        origLang = cItem.get('orig_lang') or self.UNKNOWN_LANG
        orig = re.search(r"translate_from_server_folder\('[\w-]+', '([^']+)', '([^']+)'\)", data)
        if orig:
            links[origLang] = self.getFullUrl(urllib.parse.quote(orig.group(2) + orig.group(1), safe='/%'))

        subId = self.cm.ph.getSearchGroups(cItem['url'], r'/subs/([0-9]+)/')[0]
        items = []
        for code, url in links.items():
            title = '[%s] %s' % (code, cItem['base_title'])
            if code != origLang:
                title += ' (%s)' % _('machine translated')
            params = dict(cItem)
            params.update({'title': title, 'url': url, 'lang': code, 'sub_id': subId, 'imdbid': '', 'desc': cItem.get('desc', '')})
            items.append(params)
        # the user's language, English, the original, the rest by name
        lang = GetDefaultLang()
        items.sort(key=lambda it: (langSortKey(it['lang'], lang)[:2], it['lang'] != origLang, langName(it['lang'])))
        for params in items:
            self.addSubtitle(params)

    def downloadSubtitleFile(self, cItem):
        printDBG('SubtitlecatProvider.downloadSubtitleFile')
        urlParams = dict(self.defaultParams)
        urlParams['header'] = dict(self.HTTP_HEADER, Referer=self.cm.getBaseUrl(cItem['url']))
        sts, data = self.downloadBinary(cItem['url'], urlParams)
        if not sts:
            SetIPTVPlayerLastHostError(_('Failed to download subtitle.'))
            return {}
        # some files are (translated) HTML error pages - saveSubtitleData refuses them
        return self.saveSubtitleData(data, cItem['base_title'], cItem['lang'], cItem['sub_id'], cItem['imdbid'])

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
            self.getSubtitlesList(self.currItem)

        CBaseSubProviderClass.endHandleService(self, index, refresh)


class IPTVSubProvider(CSubProviderBase):

    def __init__(self, params={}):
        CSubProviderBase.__init__(self, SubtitlecatProvider(params))
