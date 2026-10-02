# -*- coding: utf-8 -*-
# indexsubtitle.cc: movies and tv shows, many languages, the downloads are zip archives
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.isubprovider import CSubProviderBase, CBaseSubProviderClass
from Plugins.Extensions.IPTVPlayer.libs.subtitlesmatch import matchTitle, langCode, langName, langSortKey, episodeFits, sortByRelease
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetDefaultLang

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


class IndexSubtitleProvider(CBaseSubProviderClass):

    def __init__(self, params={}):
        params['cookie'] = 'indexsubtitle.cookie'
        CBaseSubProviderClass.__init__(self, params)

        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'Referer': self.getMainUrl(), 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Encoding': 'gzip'}
        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

    def getMainUrl(self):
        return 'https://indexsubtitle.cc/'

    def getPage(self, url, params={}, post_data=None):
        if params == {}:
            params = self.defaultParams
        sts, data = self.cm.getPage(url, params, post_data)
        if not sts and self.cm.meta.get('status_code') == 429:
            # about 5 requests per 10 seconds
            SetIPTVPlayerLastHostError(_('The server limits the number of requests. Please try again in a few seconds.'))
        return sts, data

    def getSearchList(self, cItem, nextCategory):
        printDBG("IndexSubtitleProvider.getSearchList")
        title, year, season = self.wantedInfo()[:3]
        if not title:
            return
        urlParams = dict(self.defaultParams)
        urlParams['header'] = dict(self.HTTP_HEADER, **{'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json, text/javascript, */*; q=0.01'})
        sts, data = self.getPage(self.getFullUrl('/search'), urlParams, {'query': title})
        if not sts:
            return
        try:
            data = json.loads(data) if data.strip() else []  # an empty answer = nothing found
        except Exception:
            printExc()
            return
        results = []
        for item in data if isinstance(data, list) else []:
            if not isinstance(item, dict) or not self.getStr(item.get('url')):
                continue
            fullName = name = self.getStr(item.get('title')).strip()
            foundYear = None
            m = re.match(r'(.*?)\s*\((\d{4})\)\s*$', name)
            if m:
                name, foundYear = m.group(1), m.group(2)
            results.append({'title': fullName, 'name': name, 'year': foundYear, 'url': self.getFullUrl(item['url'])})
        # a tv show: the year of the episode is not the year of the show
        best = matchTitle(title, None if season else year, [(r['name'], r['year'], r['url']) for r in results])
        results.sort(key=lambda r: r['url'] != best)
        for item in results:
            params = dict(cItem)
            params.update({'category': nextCategory, 'title': item['title'], 'url': item['url']})
            self.addDir(params)

    def getLanguages(self, cItem, nextCategory):
        printDBG("IndexSubtitleProvider.getLanguages")
        # the title page lists the subtitles of all languages
        season, episode = self.wantedInfo()[2:]
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        ttl = self.cm.ph.getSearchGroups(data, r'''ttl\s*=\s*(\d+)''')[0]
        m = re.search(r'data:\s*(\[\{"title".*?\}\])\s*,\s*columns', data, re.S)
        if not m or not ttl:
            return
        try:
            data = json.loads(m.group(1))
        except Exception:
            printExc()
            return
        rows = []
        for item in data if isinstance(data, list) else []:
            if not isinstance(item, dict):
                continue
            siteLang = self.getStr(item.get('language'))
            lang = langCode(siteLang.replace('_', ' '))
            name = self.getStr(item.get('title')).strip()
            url = self.getStr(item.get('url'))
            if not lang or not url or not episodeFits(name, season, episode):
                continue
            desc = self.cleanHtmlStr(self.getStr(item.get('comment')))
            author = item.get('author')
            author = self.getStr(author.get('name')) if isinstance(author, dict) else ''
            rows.append({'lang': lang, 'name': name, 'url': url, 'site_lang': siteLang,
                         'desc': '[/br]'.join(x for x in (desc, _('Author: %s') % author if author else '') if x)})
        counts = {}
        for row in rows:
            counts[row['lang']] = counts.get(row['lang'], 0) + 1
        lang = GetDefaultLang()
        for code in sorted(counts, key=lambda c: langSortKey(c, lang)):
            params = dict(cItem)
            params.update({'category': nextCategory, 'title': '%s [%s] (%d)' % (_(langName(code)), code, counts[code]), 'ttl': ttl, 'page': cItem['url'],
                           'rows': [r for r in rows if r['lang'] == code]})
            self.addDir(params)

    def getSubtitlesList(self, cItem, nextCategory):
        printDBG("IndexSubtitleProvider.getSubtitlesList")
        items = []
        for row in cItem.get('rows', []):
            params = dict(cItem)
            params.pop('rows', None)
            params.update({'category': nextCategory, 'title': '[%s] %s' % (row['lang'], row['name']), 'lang': row['lang'], 'sub_url': row['url'],
                           'site_lang': row['site_lang'], 'sub_id': row['url'].split('/')[-1], 'release': row['name'], 'desc': row['desc']})
            items.append(params)
        for params in sortByRelease(items, self.releaseName(), 'release'):
            self.addDir(params)

    def getFilesList(self, cItem):
        printDBG("IndexSubtitleProvider.getFilesList")
        url, subId = cItem['sub_url'], cItem['sub_id']  # url = <slug>/<language>/<id>
        urlParams = dict(self.defaultParams)
        urlParams['header'] = dict(self.HTTP_HEADER, **{'X-Requested-With': 'XMLHttpRequest', 'Referer': cItem['page']})
        sts, data = self.getPage(self.getFullUrl('/subtitlesInfo'), urlParams, {'id': subId, 'lang': cItem['site_lang'], 'url': url})
        if not sts:
            return
        try:
            data = json.loads(data)
            token = self.getStr(data.get('token')) if isinstance(data, dict) else ''
        except Exception:
            printExc()
            token = ''
        if not token:
            SetIPTVPlayerLastHostError(_('Failed to get the download link.'))
            return
        # as the site's javascript: url.replace(/[^\w ]/, '').replace(/\//g, '_')
        zipName = re.sub(r'[^\w ]', '', url, count=1).replace('/', '_')
        link = self.getFullUrl('/d/%s/%s/%s/%s.zip' % (subId, cItem['ttl'], token, zipName))
        tmpDIR = self.downloadArchive(link, {'header': dict(self.HTTP_HEADER, Referer=cItem['page'])})
        if tmpDIR is None:
            return
        self.listArchiveFiles(dict(cItem, path=tmpDIR, imdbid=''))

    def listArchiveFiles(self, cItem):
        CBaseSubProviderClass.listArchiveFiles(self, cItem)
        # the site's own text file in every archive
        self.currList = [item for item in self.currList if item['title'].lower() != 'indexsubtitle']

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
        CSubProviderBase.__init__(self, IndexSubtitleProvider(params))
