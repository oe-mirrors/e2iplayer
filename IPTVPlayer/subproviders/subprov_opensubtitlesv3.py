# -*- coding: utf-8 -*-
# OpenSubtitles through the Stremio "OpenSubtitles v3" addon: no key, no login, no download limit
# seen; it needs the IMDb id (movie: tt1375666, episode: tt0903747:2:5) and serves the files as UTF-8.
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.isubprovider import CSubProviderBase, CBaseSubProviderClass
from Plugins.Extensions.IPTVPlayer.subproviders.subprov_opensubtitlesorg import OpenSubtitlesBase
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetDefaultLang, RemoveDisallowedFilenameChars
from Plugins.Extensions.IPTVPlayer.libs.subtitlesmatch import langCode, langName, langSortKey, sortByRelease
###################################################

###################################################
# FOREIGN import
###################################################
import gzip
import json
###################################################

###################################################
# Config options for HOST
###################################################


def GetConfigList():
    optionList = []
    return optionList
###################################################


class OpenSubtitlesV3(OpenSubtitlesBase):

    def __init__(self, params={}):
        self.MAIN_URL = 'https://opensubtitles-v3.strem.io/'
        self.HTTP_HEADER = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36', 'Accept': 'application/json, */*'}

        CBaseSubProviderClass.__init__(self, params)

        self.defaultParams = {'header': self.HTTP_HEADER}

    def getEpisodes(self, cItem, nextCategory):
        # the addon needs the episode number
        OpenSubtitlesBase.getEpisodes(self, cItem, nextCategory, numberedOnly=True)

    def _getSubtitles(self, cItem):
        # all subtitles of the movie / episode (the addon has no language filter), None without an answer
        imdbid = 'tt' + str(cItem['imdbid']).replace('tt', '')
        if 'season' in cItem and 'episode' in cItem:
            url = self.getFullUrl('subtitles/series/%s:%s:%s.json' % (imdbid, cItem['season'], cItem['episode']))
        else:
            url = self.getFullUrl('subtitles/movie/%s.json' % imdbid)
        sts, data = self.cm.getPage(url, self.defaultParams)
        if not sts:
            return None
        try:
            return [item for item in json.loads(data).get('subtitles', []) if isinstance(item, dict) and self.cm.isValidUrl(item.get('url', ''))]
        except Exception:
            printExc()
        return None

    def getLanguages(self, cItem, nextCategory):
        printDBG("OpenSubtitlesV3.getLanguages")
        subtitles = self._getSubtitles(cItem)
        if subtitles is None:
            SetIPTVPlayerLastHostError(_('The OpenSubtitles v3 server did not answer. Please try again later.'))
            return
        if not subtitles:
            SetIPTVPlayerLastHostError(_('No subtitles found.'))
            return
        counts = {}
        for item in subtitles:
            counts[item.get('lang', '')] = counts.get(item.get('lang', ''), 0) + 1

        # the user's language first, then English, then by name
        defaultLang = GetDefaultLang()
        itemTitle = cItem.get('item_title', cItem['title'])
        for lang in sorted(counts, key=lambda x: langSortKey(x, defaultLang)):
            params = dict(cItem)
            params.update({'title': '%s [%s] (%d)' % (_(langName(langCode(lang) or lang)), lang, counts[lang]), 'search_lang': lang})
            params.update({'category': nextCategory, 'item_title': itemTitle})
            self.addDir(params)

    def getSubtitlesList(self, cItem):
        printDBG("OpenSubtitlesV3.getSubtitlesList")
        searchLang = cItem.get('search_lang', '')
        subFormats = self.getSupportedFormats(all=True)
        imdbid = str(cItem.get('eimdbid') or cItem['imdbid']).replace('tt', '')
        subList = []
        for item in self._getSubtitles(cItem) or []:
            if item.get('lang', '') != searchLang:
                continue
            fileName = item.get('subtitleFileName', '')
            ext = fileName.rsplit('.', 1)[-1].lower() if '.' in fileName else 'srt'
            if ext not in subFormats:
                continue
            release = item.get('movieReleaseName', '') or fileName.rsplit('.', 1)[0] or cItem.get('item_title', '')
            lang = langCode(searchLang) or searchLang
            try:
                fps = float(item.get('fpsMilli', 0)) / 1000.0
            except Exception:
                fps = 0
            title = RemoveDisallowedFilenameChars('[%s] %s' % (lang, release.strip()))
            subList.append({'title': title, 'release': release, 'lang': lang, 'fps': fps, 'ext': ext, 'sub_id': str(item.get('id', '')), 'imdbid': imdbid, 'url': item['url']})

        # the subtitles of the release the user plays first
        for item in sortByRelease(subList, self.releaseName(), 'release'):
            params = dict(cItem)
            params.update(item)
            self.addSubtitle(params)

    def downloadSubtitleFile(self, cItem):
        printDBG("OpenSubtitlesV3.downloadSubtitleFile")
        sts, data = self.downloadBinary(cItem['url'], {'header': self.HTTP_HEADER})
        if not sts or not data:
            SetIPTVPlayerLastHostError(_('Failed to download subtitle.'))
            return {}

        if data[:2] == b'\x1f\x8b':
            try:
                data = gzip.decompress(data)
            except Exception:
                printExc()
                SetIPTVPlayerLastHostError(_('Failed to gzip.'))
                return {}

        # the addon converts the files to UTF-8 ("subencoding-stremio-utf8" in the link): converFileToUtf8 keeps them
        return self.saveSubtitleData(data, cItem['title'], cItem['lang'], cItem['sub_id'], cItem['imdbid'], cItem.get('ext', ''), cItem.get('fps', 0))

    def handleService(self, index, refresh=0):
        printDBG('handleService start')

        CBaseSubProviderClass.handleService(self, index, refresh)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')

        printDBG("handleService: name[%s], category[%s] " % (name, category))
        self.currList = []

    # MAIN MENU
        if name is None:
            self.getMoviesTitles({'name': 'category'}, 'get_type')
        elif category == 'get_type':
            self.getType(self.currItem, 'get_subtitles')
        elif category == 'get_episodes':
            self.getEpisodes(self.currItem, 'get_languages')
        elif category == 'get_languages':
            self.getLanguages(self.currItem, 'get_subtitles')
        elif category == 'get_subtitles':
            self.getSubtitlesList(self.currItem)

        CBaseSubProviderClass.endHandleService(self, index, refresh)


class IPTVSubProvider(CSubProviderBase):

    def __init__(self, params={}):
        CSubProviderBase.__init__(self, OpenSubtitlesV3(params))
