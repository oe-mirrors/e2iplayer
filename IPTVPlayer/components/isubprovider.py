# @file  ihost.py
#

###################################################
# E2 GUI COMMPONENTS
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.asynccall import MainSessionWrapper, iptv_execute
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common, CParsingHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import GetCookieDir, printDBG, printExc, GetTmpDir, GetSubtitlesDir, \
                                                          MapUcharEncoding, GetPolishSubEncoding, GetDefaultLang, \
                                                          rm, rmtree, mkdirs, RemoveDisallowedFilenameChars
from Plugins.Extensions.IPTVPlayer.tools.iptvsubtitles import IPTVSubtitlesHandler
from Plugins.Extensions.IPTVPlayer.libs.subtitlesmatch import parseTitle, langCode, langIso2, langName, episodeFilters

from Plugins.Extensions.IPTVPlayer.components.ihost import CDisplayListItem, RetHost
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_binary
from Plugins.Extensions.IPTVPlayer.iptvdm.downloaderhelpers import shellQuote, shellSingleQuote

import json
import re
import urllib.parse
from os import listdir as os_listdir, path as os_path


class CSubItem:
    def __init__(self, path="",
                 name="",
                 lang="",
                 imdbid="",
                 subId=""):
        self.path = path
        self.name = name
        self.lang = lang
        self.imdbid = imdbid
        self.subId = subId

# class ISubProvider
# interface base class with method used to
# communicate display layer with host
#


class ISubProvider:

    # return firs available list of item category or video or link
    def getInitList(self):
        return RetHost(RetHost.NOT_IMPLEMENTED, value=[])

    # return List of item from current List
    # for given Index
    # 1 == refresh - force to read data from
    #                server if possible
    # server instead of cache
    def getListForItem(self, Index=0, refresh=0):
        return RetHost(RetHost.NOT_IMPLEMENTED, value=[])

    # return prev requested List of item
    # for given Index
    # 1 == refresh - force to read data from
    #                server if possible
    def getPrevList(self, refresh=0):
        return RetHost(RetHost.NOT_IMPLEMENTED, value=[])

    # return current List
    # for given Index
    # 1 == refresh - force to read data from
    #                server if possible
    def getCurrentList(self, refresh=0):
        return RetHost(RetHost.NOT_IMPLEMENTED, value=[])

    # return current List
    # for given Index
    def getMoreForItem(self, Index=0):
        return RetHost(RetHost.NOT_IMPLEMENTED, value=[])

    # return list of CSubItem objects
    # for given Index,
    def downloadSubtitleFile(self, Index=0,):
        return RetHost(RetHost.NOT_IMPLEMENTED, value=[])


'''
CSubProviderBase implements some typical methods
          from ISubProvider interface
'''


class CSubProviderBase(ISubProvider):
    def __init__(self, subProvider):
        self.subProvider = subProvider

        self.currIndex = -1
        self.listOfprevList = []
        self.listOfprevItems = []

    def isValidIndex(self, Index, validTypes=None):
        listLen = len(self.subProvider.currList)
        if listLen <= Index or Index < 0:
            printDBG("ERROR getLinksForVideo - current list is to short len: %d, Index: %d" % (listLen, Index))
            return False
        if validTypes is not None and self.converItem(self.subProvider.currList[Index]).type not in validTypes:
            printDBG("ERROR getLinksForVideo - current item has wrong type")
            return False
        return True
    # end getFavouriteItem

    # return firs available list of item category or video or link
    def getInitList(self):
        self.currIndex = -1
        self.listOfprevList = []
        self.listOfprevItems = []

        self.subProvider.handleService(self.currIndex)
        convList = self.convertList(self.subProvider.getCurrList())

        return RetHost(RetHost.OK, value=convList)

    def getListForItem(self, Index=0, refresh=0, selItem=None):
        self.listOfprevList.append(self.subProvider.getCurrList())
        self.listOfprevItems.append(self.subProvider.getCurrItem())

        self.currIndex = Index

        self.subProvider.handleService(Index, refresh)
        convList = self.convertList(self.subProvider.getCurrList())

        return RetHost(RetHost.OK, value=convList)

    def getPrevList(self, refresh=0):
        if (len(self.listOfprevList) > 0):
            subProviderList = self.listOfprevList.pop()
            subProviderCurrItem = self.listOfprevItems.pop()
            self.subProvider.setCurrList(subProviderList)
            self.subProvider.setCurrItem(subProviderCurrItem)

            convList = self.convertList(subProviderList)
            return RetHost(RetHost.OK, value=convList)
        else:
            return RetHost(RetHost.ERROR, value=[])

    def getCurrentList(self, refresh=0):
        if refresh == 1:
            self.subProvider.handleService(self.currIndex, refresh)
        convList = self.convertList(self.subProvider.getCurrList())
        return RetHost(RetHost.OK, value=convList)

    def getMoreForItem(self, Index=0):
        self.subProvider.handleService(Index, 2)
        convList = self.convertList(self.subProvider.getCurrList())
        return RetHost(RetHost.OK, value=convList)

    def downloadSubtitleFile(self, Index=0):
        if self.isValidIndex(Index, [CDisplayListItem.TYPE_SUBTITLE]):
            retData = self.subProvider.downloadSubtitleFile(self.subProvider.currList[Index])
            if 'path' in retData and 'title' in retData:
                return RetHost(RetHost.OK, value=[CSubItem(retData['path'], retData['title'], retData.get('lang', ''), retData.get('imdbid', ''), retData.get('sub_id', ''))])
        return RetHost(RetHost.ERROR, value=[])

    def convertList(self, cList):
        subProviderList = []
        for cItem in cList:
            subProviderItem = self.converItem(cItem)
            if subProviderItem is not None:
                subProviderList.append(subProviderItem)
        return subProviderList
    # end convertList

    def converItem(self, cItem):
        type = CDisplayListItem.TYPE_UNKNOWN

        if 'category' == cItem['type']:
            type = CDisplayListItem.TYPE_CATEGORY
        elif cItem['type'] == 'subtitle':
            type = CDisplayListItem.TYPE_SUBTITLE
        elif 'more' == cItem['type']:
            type = CDisplayListItem.TYPE_MORE

        title = cItem.get('title', '')
        description = cItem.get('desc', '')

        return CDisplayListItem(name=title,
                                description=description,
                                type=type)
    # end converItem


class CBaseSubProviderClass:

    def __init__(self, params={}):
        self.TMP_FILE_NAME = '.iptv_subtitles.file'
        self.TMP_DIR_NAME = '.iptv_subtitles.dir/'
        self.sessionEx = MainSessionWrapper(mainThreadIdx=1)

        proxyURL = params.get('proxyURL', '')
        useProxy = params.get('useProxy', False)
        self.cm = common(proxyURL, useProxy)

        self.currList = []
        self.currItem = {}
        if '' != params.get('cookie', ''):
            self.COOKIE_FILE = GetCookieDir(params['cookie'])
        self.moreMode = False
        self.params = params

    def getSupportedFormats(self, all=False):
        if all:
            ret = list(IPTVSubtitlesHandler.getSupportedFormats())
        else:
            ret = list(IPTVSubtitlesHandler.SUPPORTED_FORMATS)
        return ret

    def getMaxFileSize(self):
        return 1024 * 1024 * 5  # 5MB, max size of sub file to be download

    def getMaxItemsInDir(self):
        return 500

    def listsTab(self, tab, cItem):
        for item in tab:
            params = dict(cItem)
            params.update(item)
            params['name'] = 'category'
            self.addDir(params)

    def iptv_execute(self, cmd):
        printDBG("iptv_execute cmd_exec [%s]" % cmd)
        ret = iptv_execute(1)(cmd)
        printDBG("iptv_execute cmd_ret sts[%s] code[%s] data[%s]" % (ret.get('sts', ''), ret.get('code', ''), ret.get('data', '')))
        return ret

    @staticmethod
    def cleanHtmlStr(str):
        return CParsingHelper.cleanHtmlStr(str)

    @staticmethod
    def getStr(v, default=''):
        if isinstance(v, str):
            return v
        return default

    def getCurrList(self):
        return self.currList

    def setCurrList(self, list):
        self.currList = list

    def getCurrItem(self):
        return self.currItem

    def setCurrItem(self, item):
        self.currItem = item

    def addDir(self, params, atTheEnd=True):
        params['type'] = 'category'
        if atTheEnd:
            self.currList.append(params)
        else:
            self.currList.insert(0, params)
        return

    def addMore(self, params, atTheEnd=True):
        params['type'] = 'more'
        if atTheEnd:
            self.currList.append(params)
        else:
            self.currList.insert(0, params)
        return

    def addSubtitle(self, params, atTheEnd=True):
        params['type'] = 'subtitle'
        if atTheEnd:
            self.currList.append(params)
        else:
            self.currList.insert(0, params)
        return

    def getMainUrl(self):
        return self.MAIN_URL

    def getFullUrl(self, url, currUrl=None):
        if url.startswith('./'):
            url = url[1:]

        if currUrl is None or not self.cm.isValidUrl(currUrl):
            try:
                mainUrl = self.getMainUrl()
            except Exception:
                mainUrl = 'http://fake'  # NOSONAR
        else:
            mainUrl = self.cm.getBaseUrl(currUrl)

        if url.startswith('//'):
            proto = mainUrl.split('://', 1)[0]
            url = proto + ':' + url
        elif url.startswith('://'):
            proto = mainUrl.split('://', 1)[0]
            url = proto + url
        elif url.startswith('/'):
            url = mainUrl + url[1:]
        elif 0 < len(url) and '://' not in url:
            if currUrl is None or not self.cm.isValidUrl(currUrl):
                url = mainUrl + url
            else:
                url = urllib.parse.urljoin(currUrl, url)
        return url

    def handleService(self, index, refresh=0):

        self.moreMode = False
        if 0 == refresh:
            if len(self.currList) <= index:
                return
            if -1 == index:
                self.currItem = {"name": None}
            else:
                self.currItem = self.currList[index]
        if 2 == refresh:  # refresh for more items
            printDBG("CBaseSubProviderClass endHandleService index[%s]" % index)
            # remove item more and store items before and after item more
            self.beforeMoreItemList = self.currList[0:index]
            self.afterMoreItemList = self.currList[index + 1:]
            self.moreMode = True
            if -1 == index:
                self.currItem = {"name": None}
            else:
                self.currItem = self.currList[index]

    def endHandleService(self, index, refresh):
        if 2 == refresh:  # refresh for more items
            currList = self.currList
            self.currList = self.beforeMoreItemList
            for item in currList:
                if 'more' == item['type'] or (item not in self.beforeMoreItemList and item not in self.afterMoreItemList):
                    self.currList.append(item)
            self.currList.extend(self.afterMoreItemList)
            self.beforeMoreItemList = []
            self.afterMoreItemList = []
        self.moreMode = False

    # The imdb.com HTML pages answer non-browsers with an empty AWS WAF challenge (HTTP 202),
    # so these helpers use IMDb's own GraphQL API like the oe-alliance IMDb plugin: no key, it
    # only needs the website referer. Without a language header the titles come in English,
    # which suits the subtitle search. IMDb ids are passed without the "tt" prefix.
    IMDB_GRAPHQL_URL = 'https://caching.graphql.imdb.com/'

    def imdbGraphQL(self, query):
        # the "data" part of the answer, or None
        params = {'header': {'User-Agent': self.cm.getDefaultHeader()['User-Agent'], 'Content-Type': 'application/json', 'Referer': 'https://www.imdb.com/'},
                  'raw_post_data': True}
        sts, data = self.cm.getPage(self.IMDB_GRAPHQL_URL, params, json.dumps({'query': query}))
        if not sts:
            return None
        try:
            data = json.loads(data).get('data')
        except Exception:
            printExc()
            return None
        return data if isinstance(data, dict) else None

    def imdbTitle(self, imdbid, fields):
        if not re.match(r'^(tt)?[0-9]+$', str(imdbid)):
            return None
        data = self.imdbGraphQL('query { title(id: "tt%s") { %s } }' % (str(imdbid).replace('tt', ''), fields))
        return (data or {}).get('title')

    def imdbGetSeasons(self, imdbid, promSeason=None):
        printDBG('CBaseSubProviderClass.imdbGetSeasons imdbid[%s]' % imdbid)
        title = self.imdbTitle(imdbid, 'episodes { seasons { number } }')
        if title is None:
            return False, []
        seasons = [str(s['number']) for s in (title.get('episodes') or {}).get('seasons') or [] if s.get('number') is not None]
        if promSeason is not None and str(promSeason) in seasons:
            seasons.remove(str(promSeason))
            seasons.insert(0, str(promSeason))
        return True, seasons

    def imdbGetEpisodesForSeason(self, imdbid, season, promEpisode=None):
        printDBG('CBaseSubProviderClass.imdbGetEpisodesForSeason imdbid[%s] season[%s]' % (imdbid, season))
        fields = 'episodes { episodes(first: 250, filter: {includeSeasons: [%s]}) { edges { node { id titleText { text } series { episodeNumber { episodeNumber } } } } } }' % json.dumps(str(season))
        title = self.imdbTitle(imdbid, fields)
        if title is None:
            return False, []
        episodes = []
        for edge in ((title.get('episodes') or {}).get('episodes') or {}).get('edges') or []:
            node = edge.get('node') or {}
            episode = str((((node.get('series') or {}).get('episodeNumber') or {}).get('episodeNumber')) or '')
            episodes.append({"episode_title": (node.get('titleText') or {}).get('text') or '', "episode": episode, "eimdbid": (node.get('id') or '').replace('tt', '')})
        # in episode order, unnumbered ones (e.g. an unaired pilot) last, the wanted episode first
        episodes.sort(key=lambda e: int(e['episode']) if e['episode'].isdigit() else 9999)
        for params in episodes:
            if promEpisode is not None and params['episode'] == str(promEpisode):
                episodes.remove(params)
                episodes.insert(0, params)
                break
        return True, episodes

    def imdbGetMoviesByTitle(self, title):
        printDBG('CBaseSubProviderClass.imdbGetMoviesByTitle title[%s]' % (title))
        # the confirmed title is often "Show S02E05" - IMDb finds nothing with the episode in it
        searchTitle = parseTitle(title)[0]
        if searchTitle:
            title = searchTitle
        query = '''query { mainSearch(first: 25, options: {searchTerm: %s, type: TITLE, titleSearchOptions: {type: [MOVIE, TV]}}) {
 edges { node { entity { ... on Title { id titleText { text } titleType { text } releaseYear { year } } } } } } }''' % json.dumps(title)
        data = self.imdbGraphQL(query)
        if data is None:
            return False, []
        iteamList = []
        for edge in (data.get('mainSearch') or {}).get('edges') or []:
            entity = (edge.get('node') or {}).get('entity') or {}
            if not entity.get('id'):
                continue
            baseTitle = (entity.get('titleText') or {}).get('text') or ''
            year = str((entity.get('releaseYear') or {}).get('year') or '')
            itemType = (entity.get('titleType') or {}).get('text') or ''
            # "(TV Series)" lets getTypeFromThemoviedb() skip its request
            sTitle = ' '.join(x for x in (baseTitle, year, '(%s)' % itemType if itemType else '') if x)
            iteamList.append({'title': sTitle, 'base_title': baseTitle, 'year': year, 'imdbid': entity['id'].replace('tt', '')})
        return True, iteamList

    def imdbGetOrginalByTitle(self, imdbid):
        printDBG('CBaseSubProviderClass.imdbGetOrginalByTitle imdbid[%s]' % (imdbid))
        # the English title, as the og:title of the website was
        title = self.imdbTitle(imdbid, 'titleText { text }')
        if title is None:
            return False, {}
        return True, {'title': (title.get('titleText') or {}).get('text') or ''}

    def getTypeFromThemoviedb(self, imdbid, title):
        # 'series' or 'movie'; the name stays for the subtitle providers, the answer now comes from IMDb
        if '(TV Series)' in title or '(TV Mini Series)' in title:
            return 'series'
        info = self.imdbTitle(imdbid, 'titleType { canHaveEpisodes }')
        if info and (info.get('titleType') or {}).get('canHaveEpisodes'):
            return 'series'
        return 'movie'

    def wantedInfo(self):
        """(title, year, season, episode) the user searches for: from the confirmed title ("Show S02E05",
        "Movie (2010)"), season / episode from discover_info when the title has none. Year is a string,
        season / episode are ints or None."""
        title, year, season, episode = parseTitle(self.params.get('confirmed_title') or self.params.get('movie_title') or '')
        dInfo = self.params.get('discover_info') or {}
        if season is None and dInfo.get('season') and dInfo.get('episode'):
            season, episode = dInfo['season'], dInfo['episode']
        return title, year, season, episode

    def releaseName(self):
        """the stream / file name as it came (release tags for sortByRelease), the confirmed title if unknown"""
        return self.params.get('release_title') or self.params.get('movie_title') or ''

    @staticmethod
    def imdbNumber(imdbid):
        """'tt0133093' -> '0133093'; other ids (a YouTube id) stay as they are"""
        return re.sub(r'^tt(?=\d)', '', str(imdbid or ''))

    @staticmethod
    def subtitleFileName(title, lang, subId, imdbid, ext, fps=0):
        """file name of a downloaded subtitle: the player reads lang / ids / fps back from it"""
        title = RemoveDisallowedFilenameChars(title).replace('_', '.')
        match = re.search(r'[^.]', title)
        if match:
            title = title[match.start():]
        fileName = '{0}_{1}_0_{2}_{3}'.format(title, lang, subId, CBaseSubProviderClass.imdbNumber(imdbid))
        if fps and float(fps) > 0:
            fileName += '_fps{0}'.format(fps)
        return fileName + '.' + ext

    @staticmethod
    def _archiveType(data):
        if data[:2] == b'PK':
            return 'zip'
        if data[:4] == b'Rar!':
            return 'rar'
        return ''

    @staticmethod
    def subtitleType(data):
        """file extension for a plain subtitle body (srt, vtt, ass, sub, txt, mpl), '' for anything else
        (an HTML / JSON error page, a picture). The same format detection the player uses."""
        head = data[:8192]
        if head[:2] in (b'\xff\xfe', b'\xfe\xff'):
            text = head.decode('utf-16', 'ignore')
        else:
            text = head.decode('utf-8', 'ignore').lstrip('\ufeff')
        if text.lstrip()[:1] == '<':
            return ''
        fmt = IPTVSubtitlesHandler._detectFormat(text, '')
        if fmt == 'srt':
            return 'vtt' if text.lstrip().startswith('WEBVTT') else 'srt'
        return {'ass': 'ass', 'microdvd': 'sub', 'subviewer': 'sub', 'tmplayer': 'txt', 'mpl': 'mpl'}.get(fmt, '')

    def downloadArchive(self, url, params={}, post_data=None):
        # zip / rar / a plain subtitle file -> directory with the subtitle files, or None
        data, fileName = self.downloadFileData(url, params, post_data)
        if not data:
            SetIPTVPlayerLastHostError(_('Failed to download subtitle.'))
            return None
        tmpDIR = GetTmpDir(self.TMP_DIR_NAME)
        ext = self._archiveType(data)
        if ext:
            tmpArchFile = GetTmpDir(self.TMP_FILE_NAME) + '.' + ext
            if not self.writeFile(tmpArchFile, data):
                return None
            ret = self.unpackArchive(tmpArchFile, tmpDIR)
            rm(tmpArchFile)
            return tmpDIR if ret else None
        ext = self.subtitleType(data)
        if not ext:
            SetIPTVPlayerLastHostError(_('The server did not send a subtitle file.'))
            return None
        rmtree(tmpDIR, ignore_errors=True)
        if not mkdirs(tmpDIR):
            return None
        fileName = RemoveDisallowedFilenameChars(urllib.parse.unquote(fileName)).rsplit('.', 1)[0] or 'subtitle'
        return tmpDIR if self.writeFile(os_path.join(tmpDIR, fileName + '.' + ext), data) else None

    def saveSubtitleData(self, data, title, lang, subId, imdbid, ext='', fps=0, encoding=''):
        """a downloaded plain subtitle (bytes) -> UTF-8 file in the subtitles folder, the result dict for
        downloadSubtitleFile or {}. encoding: what the site says the file is in, tried first."""
        detected = self.subtitleType(data) if data else ''
        if not detected:
            SetIPTVPlayerLastHostError(_('The server did not send a subtitle file.'))
            return {}
        ext = ext or detected
        outFile = GetSubtitlesDir(self.subtitleFileName(title, lang, subId, imdbid, ext, fps))
        sts = False
        if encoding:
            try:
                sts = self.writeFile(outFile, data.decode(encoding).encode('UTF-8'))
            except Exception:
                printDBG('saveSubtitleData: not %s' % encoding)
        if not sts:
            tmpFile = GetTmpDir(self.TMP_FILE_NAME)
            sts = self.writeFile(tmpFile, data) and self.converFileToUtf8(tmpFile, outFile, lang)
            rm(tmpFile)
        if not sts:
            return {}
        return {'title': title, 'path': outFile, 'lang': lang, 'imdbid': self.imdbNumber(imdbid), 'sub_id': subId, 'fps': fps}

    def downloadSubtitleFile(self, cItem):
        """default for a subtitle item that is a file of an unpacked archive (cItem['file_path'])"""
        printDBG('CBaseSubProviderClass.downloadSubtitleFile')
        title, lang = cItem['title'], cItem.get('lang', '')
        subId, imdbid, fps = cItem.get('sub_id', ''), self.imdbNumber(cItem.get('imdbid', '')), cItem.get('fps', 0)
        outFile = GetSubtitlesDir(self.subtitleFileName(title, lang, subId, imdbid, cItem.get('ext', 'srt'), fps))
        if self.converFileToUtf8(cItem['file_path'], outFile, lang):
            return {'title': title, 'path': outFile, 'lang': lang, 'imdbid': imdbid, 'sub_id': subId, 'fps': fps}
        return {}

    def downloadBinary(self, url, params={}, post_data=None):
        """(sts, bytes) of a download - archives, gz files, captcha pictures. cm.getPage would decode the
        body to text, so it goes through saveWebFile into a temporary file (redirects are followed, the
        cookie, proxy and certificate settings apply). self.cm.meta has the final url, status and headers."""
        printDBG('isubprovider.py CBaseSubProviderClass.downloadBinary url[%s]' % url)
        urlParams = dict(params)
        # getURLRequestData refuses max_data_size without return_data - the size is checked below
        for key in ('max_data_size', 'allow_redirects', 'return_data'):
            urlParams.pop(key, None)
        maxSize = self.getMaxFileSize()
        tmpFile = GetTmpDir(self.TMP_FILE_NAME + '.download')
        data = None
        try:
            self.cm.meta = {}
            ret = self.cm.saveWebFile(tmpFile, url, urlParams, post_data)
            # saveWebFile also stores the body of an HTTP error page (meant for pictures)
            status = self.cm.meta.get('status_code') or 200
            if ret.get('sts') and status < 400 and 0 < ret.get('fsize', 0) <= maxSize:
                with open(tmpFile, 'rb') as f:
                    data = f.read()
            else:
                printDBG('downloadBinary failed status[%s] size[%s] reason[%s]' % (status, ret.get('fsize'), ret.get('reason', '')))
        except Exception:
            printExc()
        rm(tmpFile)
        return data is not None, data

    def downloadFileData(self, url, params={}, post_data=None):
        printDBG('isubprovider.py CBaseSubProviderClass.downloadFileData url[%s]' % url)
        sts, data = self.downloadBinary(url, params, post_data)
        if sts:
            # attachment; filename="x.zip" / filename=x.zip / filename*=UTF-8''x%20y.zip - without a name the
            # file name of the (final) URL
            disposition = self.cm.meta.get('content-disposition', '')
            match = re.search(r'''filename\*=(?:[\w-]+'[\w-]*')?"?([^";]+)''', disposition, re.I) or \
                re.search(r'''filename="([^"]+)"''', disposition, re.I) or re.search(r'''filename=([^;]+)''', disposition, re.I)
            fileName = urllib.parse.unquote(match.group(1)).strip().strip("'") if match else ''
            if fileName != '':
                printDBG("downloadFileData: content-disposition[%s] -> fileName[%s]" % (disposition, fileName))
                fileName = RemoveDisallowedFilenameChars(fileName)
            else:
                sUrl = self.cm.meta.get('url', url)
                fileName = urllib.parse.urlparse(sUrl).path.rsplit('/', 1)[-1]

            return data, fileName

        return None, ''

    def writeFile(self, filePath, data):
        printDBG("isubprovider.py CBaseSubProviderClass.writeFile path='%s'" % filePath)
        try:
            with open(filePath, 'wb') as f:
                f.write(ensure_binary(data))  # p3 needs bytes, for p2 no oncoding
            return True
        except Exception:
            printExc()
            SetIPTVPlayerLastHostError(_('Failed to write file "%s".') % filePath)
        return False

    def unpackZipArchive(self, tmpFile, tmpDIR):
        errorCode = 0
        # check if archive is not evil
        cmd = "unzip -l {0} 2>&1 ".format(shellSingleQuote(tmpFile))
        ret = self.iptv_execute(cmd)
        if not ret['sts'] or 0 != ret['code']:
            errorCode = ret['code']
            if errorCode == 0:
                errorCode = 9
        elif '..' in ret['data']:
            errorCode = 9

        # if archive is valid then upack it
        if errorCode == 0:
            cmd = "unzip -o {0} -d {1} 2>/dev/null".format(shellSingleQuote(tmpFile), shellSingleQuote(tmpDIR))
            ret = self.iptv_execute(cmd)
            if not ret['sts'] or 0 != ret['code']:
                errorCode = ret['code']
                if errorCode == 0:
                    errorCode = 9

        if errorCode != 0:
            message = _('Unzip error code[%s].') % errorCode
            if str(errorCode) == str(127):
                message += '\n' + _('It seems that unzip utility is not installed.')
            elif str(errorCode) == str(9):
                message += '\n' + _('Wrong format of zip archive.')
            SetIPTVPlayerLastHostError(message)
            return False

        return True

    def unpackArchive(self, tmpFile, tmpDIR):
        printDBG("isubprovider.py CBaseSubProviderClass.unpackArchive tmpFile='%s', tmpDIR='%s'" % (tmpFile, tmpDIR))
        rmtree(tmpDIR, ignore_errors=True)
        if not mkdirs(tmpDIR):
            SetIPTVPlayerLastHostError(_('Failed to create directory "%s".') % tmpDIR)
            return False
        if tmpFile.endswith('.zip'):
            return self.unpackZipArchive(tmpFile, tmpDIR)
        elif tmpFile.endswith('.rar'):
            cmd = "unrar e -o+ -y {0} {1} 2>/dev/null".format(shellSingleQuote(tmpFile), shellSingleQuote(tmpDIR))
            printDBG("cmd[%s]" % cmd)
            ret = self.iptv_execute(cmd)
            if not ret['sts'] or 0 != ret['code']:
                message = _('Unrar error code[%s].') % ret['code']
                if str(ret['code']) == str(127):
                    message += '\n' + _('It seems that unrar utility is not installed.')
                elif str(ret['code']) == str(9):
                    message += '\n' + _('Wrong format of rar archive.')
                SetIPTVPlayerLastHostError(message)
                return False
            return True
        return False

    def listSupportedFilesFromPath(self, cItem, subExt=['srt'], archExt=['rar', 'zip'], dirCategory=None):
        printDBG('CBaseSubProviderClass.listSupportedFilesFromPath')
        maxItems = self.getMaxItemsInDir()
        numItems = 0
        # without a dirCategory of the provider the files of sub folders are listed too (season packs often
        # keep them in a folder), named "folder/file"
        pending = [('', cItem['path'])]
        while pending and numItems < maxItems:
            prefix, path = pending.pop(0)
            for file in sorted(os_listdir(path)):
                numItems += 1
                filePath = os_path.join(path, file)
                params = dict(cItem)
                if os_path.isfile(filePath):
                    ext = file.rsplit('.', 1)[-1].lower()
                    params.update({'file_path': filePath, 'title': prefix + os_path.splitext(file)[0]})
                    if ext in subExt:
                        params['ext'] = ext
                        self.addSubtitle(params)
                    elif ext in archExt:
                        self.addDir(params)
                elif os_path.isdir(filePath):
                    if dirCategory is not None:
                        params.update({'category': dirCategory, 'path': filePath, 'title': file})
                        self.addDir(params)
                    else:
                        pending.append((prefix + file + '/', filePath))
                if numItems >= maxItems:
                    break
        # real subtitle files before .txt / .sub (chapter lists, NFOs and the like often come along in archives)
        self.currList.sort(key=lambda k: (k.get('type') == 'subtitle' and k.get('ext') in ('txt', 'sub'), k['title']))

    def listArchiveFiles(self, cItem):
        """the subtitle files of an unpacked archive (cItem['path'], sub folders included). An archive in the
        archive (season packs: one per release) becomes an 'unpack_archive' item - the provider's handleService
        sends that category to unpackInnerArchive(). The wanted episode comes first."""
        self.listSupportedFilesFromPath(dict(cItem, category=''), self.getSupportedFormats(all=True))
        for item in self.currList:
            if item['type'] == 'category':
                item['category'] = 'unpack_archive'
        # multi-language archives: "Movie_ger.srt" before "Movie_eng.srt" when German was chosen
        lang = langCode(cItem.get('lang', ''))
        if lang:
            names = set((lang, langIso2(lang), langName(lang).lower()))
            self.currList.sort(key=lambda it: not names.intersection(re.findall(r'[a-z]+', it['title'].lower())))
        season, episode = self.wantedInfo()[2:]
        if season and episode:
            thisEpisode = episodeFilters(season, episode)[0]
            self.currList.sort(key=lambda it: not thisEpisode.search(it['title']))

    def unpackInnerArchive(self, cItem):
        printDBG('CBaseSubProviderClass.unpackInnerArchive')
        tmpDIR = cItem['file_path'] + '.dir'
        if self.unpackArchive(cItem['file_path'], tmpDIR):
            self.listArchiveFiles(dict(cItem, path=tmpDIR))

    # the usual 8-bit code page of subtitles in a language, when the file is not UTF-8 and uchardet is missing
    LANG_CODEPAGES = {'pl': 'cp1250', 'cs': 'cp1250', 'sk': 'cp1250', 'hu': 'cp1250', 'hr': 'cp1250', 'sl': 'cp1250',
                      'ro': 'cp1250', 'bs': 'cp1250', 'sr': 'cp1250', 'sq': 'cp1250', 'ru': 'cp1251', 'uk': 'cp1251',
                      'bg': 'cp1251', 'mk': 'cp1251', 'el': 'cp1253', 'tr': 'cp1254', 'he': 'cp1255', 'ar': 'cp1256',
                      'fa': 'cp1256', 'ur': 'cp1256', 'lt': 'cp1257', 'lv': 'cp1257', 'et': 'cp1257', 'vi': 'cp1258',
                      'th': 'cp874', 'ja': 'cp932', 'ko': 'cp949', 'zh': 'gbk'}

    def converFileToUtf8(self, inFile, outFile, lang=''):
        printDBG('CBaseSubProviderClass.converFileToUtf8 inFile[%s] outFile[%s]' % (inFile, outFile))
        try:
            with open(inFile, 'rb') as f:
                data = f.read()
        except Exception:
            printExc()
            SetIPTVPlayerLastHostError(_('Failed to open the file "%s".') % inFile)
            return False

        # 'pol' / 'Polish' / 'pt-BR' from the sites -> 'pl' / 'pt-br' for the code page table
        lang = langCode(lang or GetDefaultLang()) or lang

        for bom, bomEncoding in ((b'\xef\xbb\xbf', 'utf-8-sig'), (b'\xff\xfe', 'utf-16'), (b'\xfe\xff', 'utf-16')):
            if data.startswith(bom):
                return self.writeFile(outFile, data.decode(bomEncoding, 'replace').encode('UTF-8'))
        try:
            data.decode('utf-8')
            return self.writeFile(outFile, data)
        except UnicodeDecodeError:
            pass

        # detect encoding
        encoding = ''
        if os_path.isfile('/usr/bin/uchardet'):
            ret = self.iptv_execute('/usr/bin/uchardet "%s"' % shellQuote(inFile))
            if ret['sts'] and 0 == ret['code']:
                encoding = MapUcharEncoding(ret['data']).strip().lower()
                if 'unknown' in encoding or 'ascii' in encoding or 'utf-8' in encoding:
                    encoding = ''
        if lang == 'pl' and encoding in ('', 'iso-8859-2'):
            # the file that is converted - not the provider's temp download
            encoding = GetPolishSubEncoding(inFile)

        if encoding != '':
            try:
                return self.writeFile(outFile, data.decode(encoding).encode('UTF-8'))
            except Exception:
                printExc()
        # no uchardet on the box or a wrong guess: the usual code page of the language
        encoding = self.LANG_CODEPAGES.get(lang.split('-')[0], 'cp1252')
        printDBG('CBaseSubProviderClass.converFileToUtf8 fallback encoding[%s]' % encoding)
        try:
            return self.writeFile(outFile, data.decode(encoding, 'replace').encode('UTF-8'))
        except Exception:
            printExc()
            SetIPTVPlayerLastHostError(_('Failed to convert the file "%s" to UTF-8.') % inFile)
        return False
