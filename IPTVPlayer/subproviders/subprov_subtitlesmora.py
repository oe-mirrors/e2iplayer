# -*- coding: utf-8 -*-
# Arabic subtitles from the archive.org item "mora25r" (one .srt per movie, a few episodes);
# the file list comes from the archive.org metadata API and is kept for 24 hours
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.isubprovider import CSubProviderBase, CBaseSubProviderClass
from Plugins.Extensions.IPTVPlayer.libs.subtitlesmatch import normalizeTitle, romanVariations, yearMatch, episodeFits
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote

###################################################
# FOREIGN import
###################################################
import json
import re
import time

###################################################
# Config options for HOST
###################################################


def GetConfigList():
    optionList = []
    return optionList
###################################################


ITEM = 'mora25r'
SUB_EXTS = ('srt', 'ass', 'ssa', 'sub', 'vtt')
CACHE_TIMEOUT = 24 * 3600
# {'time': monotonic time, 'files': [(file name, normalised name + '.'), ...]} for the running session
FILE_LIST = {}


class SubtitlesMoraProvider(CBaseSubProviderClass):

    def __init__(self, params={}):
        CBaseSubProviderClass.__init__(self, params)

        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'Accept': '*/*', 'Accept-Encoding': 'gzip'}
        self.defaultParams = {'header': self.HTTP_HEADER}

    def getMainUrl(self):
        return 'https://archive.org/'

    def getFileList(self):
        if FILE_LIST and time.monotonic() - FILE_LIST['time'] < CACHE_TIMEOUT:
            return FILE_LIST['files']
        # /metadata/<item>/files is only 2% smaller than the whole metadata, so the full answer it is
        sts, data = self.cm.getPage(self.getFullUrl('/metadata/%s' % ITEM), self.defaultParams)
        files = []
        try:
            data = json.loads(data) if sts else {}
            for f in (data.get('files') if isinstance(data, dict) else None) or []:
                name = self.getStr(f.get('name')) if isinstance(f, dict) else ''
                if name.rsplit('.', 1)[-1].lower() in SUB_EXTS:
                    # normalised once here, not for all ~13000 names on every search
                    files.append((name, self.normalize(name.rsplit('.', 1)[0]) + '.'))
        except Exception:
            printExc()
            files = []
        if files:
            FILE_LIST.update({'time': time.monotonic(), 'files': files})
        # an outdated list is better than none
        return files or FILE_LIST.get('files', [])

    @staticmethod
    def normalize(text):
        # 'The Matrix: Reloaded' -> 'the.matrix.reloaded'
        return normalizeTitle(text).replace(' ', '.')

    def getSubtitlesList(self, cItem):
        printDBG("SubtitlesMoraProvider.getSubtitlesList")
        title, year, season, episode = self.wantedInfo()
        if not title:
            return
        prefixes = ['.'.join(words) + '.' for words in romanVariations(self.normalize(title).split('.'))]
        files = self.getFileList()
        if not files:
            SetIPTVPlayerLastHostError(_('Failed to get the file list from %s.') % self.getMainUrl())
            return
        hits = []
        for fileName, norm in files:
            prefix = next((p for p in prefixes if norm.startswith(p)), None)
            if prefix is None:
                continue
            rest = norm[len(prefix):]
            isEpisode = bool(re.match(r's\d+\.?e\d+\.', rest))
            if bool(season and episode) != isEpisode or not episodeFits(rest, season, episode):
                continue
            years = re.findall(r'(?:^|\.)((?:19|20)\d\d)(?=\.)', rest)
            if year and years and not any(yearMatch(y, year) for y in years):
                continue
            # the exact title (followed by its year / episode) first
            exact = isEpisode or bool(re.match(r'(19|20)\d\d\.', rest))
            hits.append((not exact, fileName))
        hits.sort(key=lambda x: x[0])
        for _exact, fileName in hits:
            params = dict(cItem)
            params.update({'title': fileName.rsplit('.', 1)[0], 'file_name': fileName, 'lang': 'ar', 'ext': fileName.rsplit('.', 1)[-1].lower(), 'imdbid': ''})
            self.addSubtitle(params)

    def downloadSubtitleFile(self, cItem):
        printDBG("SubtitlesMoraProvider.downloadSubtitleFile")
        url = self.getFullUrl('/download/%s/%s' % (ITEM, urllib_quote(cItem['file_name'])))
        sts, data = self.downloadBinary(url, {'header': self.HTTP_HEADER})
        if not sts:
            SetIPTVPlayerLastHostError(_('Failed to download subtitle.'))
            return {}
        # the files are mostly Windows-1256: the code page of 'ar' when they are not UTF-8 / UTF-16
        return self.saveSubtitleData(data, cItem['title'], cItem['lang'], ITEM, cItem['imdbid'])

    def handleService(self, index, refresh=0):
        printDBG('handleService start')

        CBaseSubProviderClass.handleService(self, index, refresh)

        name = self.currItem.get("name", '')

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s] " % name)
        self.currList = []

        if name is None:
            self.getSubtitlesList({'name': 'category'})

        CBaseSubProviderClass.endHandleService(self, index, refresh)


class IPTVSubProvider(CSubProviderBase):

    def __init__(self, params={}):
        CSubProviderBase.__init__(self, SubtitlesMoraProvider(params))
