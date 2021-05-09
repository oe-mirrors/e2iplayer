## @file  ihost.py
#

###################################################
# E2 GUI COMMPONENTS
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.asynccall import MainSessionWrapper, iptv_execute
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common, CParsingHelper
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import CSearchHistoryHelper, GetCookieDir, printDBG, printExc, GetTmpDir, GetSubtitlesDir, \
                                                          MapUcharEncoding, GetPolishSubEncoding, GetUchardetPath, GetDefaultLang, \
                                                          rm, rmtree, mkdirs
from Plugins.Extensions.IPTVPlayer.tools.iptvsubtitles import IPTVSubtitlesHandler
from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.utils import clean_html

from Plugins.Extensions.IPTVPlayer.components.ihost import CDisplayListItem, RetHost

import re
import urllib
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

## class ISubProvider
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
        if None != validTypes and self.converItem(self.subProvider.currList[Index]).type not in validTypes:
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
        if(len(self.listOfprevList) > 0):
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
            if None != subProviderItem:
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
        self.TMP_DIR_NAME = '/.iptv_subtitles.dir/'
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
        return 1024 * 1024 * 5 # 5MB, max size of sub file to be download

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
        if type(v) == type(u''):
            return v.encode('utf-8')
        elif type(v) == type(''):
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

        if currUrl == None or not self.cm.isValidUrl(currUrl):
            try:
                mainUrl = self.getMainUrl()
            except Exception:
                mainUrl = 'http://fake'
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
            if currUrl == None or not self.cm.isValidUrl(currUrl):
                url = mainUrl + url
            else:
                url = urljoin(currUrl, url)
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
        if 2 == refresh: # refresh for more items
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
        if 2 == refresh: # refresh for more items
            currList = self.currList
            self.currList = self.beforeMoreItemList
            for item in currList:
                if 'more' == item['type'] or (item not in self.beforeMoreItemList and item not in self.afterMoreItemList):
                    self.currList.append(item)
            self.currList.extend(self.afterMoreItemList)
            self.beforeMoreItemList = []
            self.afterMoreItemList = []
        self.moreMode = False

    def imdbGetSeasons(self, imdbid, promSeason=None):
        printDBG('CBaseSubProviderClass.imdbGetSeasons imdbid[%s]' % imdbid)
        promotItem = None
        list = []
        # get all seasons
        sts, data = self.cm.getPage("http://www.imdb.com/title/tt%s/episodes" % imdbid)
        if not sts:
            return False, []
        data = self.cm.ph.getDataBeetwenMarkers(data, '<select id="bySeason"', '</select>', False)[1]
        seasons = re.compile('value="([0-9]+?)"').findall(data)
        for season in seasons:
            if None != promSeason and season == str(promSeason):
                promotItem = season
            else:
                list.append(season)

        if promotItem != None:
            list.insert(0, promotItem)

        return True, list

    def imdbGetEpisodesForSeason(self, imdbid, season, promEpisode=None):
        printDBG('CBaseSubProviderClass.imdbGetEpisodesForSeason imdbid[%s] season[%s]' % (imdbid, season))
        promotItem = None
        list = []

        # get episodes for season
        sts, data = self.cm.getPage("http://www.imdb.com/title/tt%s/episodes/_ajax?season=%s" % (imdbid, season))
        if not sts:
            return False, []

        data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="list detail eplist">', '<hr>', False)[1]
        data = data.split('<div class="clear">')
        if len(data):
            del data[-1]
        for item in data:
            episodeTitle = self.cm.ph.getSearchGroups(item, 'title="([^"]+?)"')[0]
            eimdbid = self.cm.ph.getSearchGroups(item, 'data-const="tt([0-9]+?)"')[0]
            episode = self.cm.ph.getSearchGroups(item, 'content="([0-9]+?)"')[0]
            params = {"episode_title": episodeTitle, "episode": episode, "eimdbid": eimdbid}

            if None != promEpisode and episode == str(promEpisode):
                promotItem = params
            else:
                list.append(params)

        if promotItem != None:
            list.insert(0, promotItem)
        return True, list

    def imdbGetMoviesByTitle(self, title):
        printDBG('CBaseSubProviderClass.imdbGetMoviesByTitle title[%s]' % (title))

        sts, data = self.cm.getPage("http://www.imdb.com/find?ref_=nv_sr_fn&q=%s&s=tt" % urllib.quote_plus(title))
        if not sts:
            return False, []
        list = []
        data = self.cm.ph.getDataBeetwenMarkers(data, '<table class="findList">', '</table>', False)[1]
        data = data.split('</tr>')
        if len(data):
            del data[-1]
        for item in data:
            item = item.split('<a ')
            item = '<a ' + item[2]
            if '(Video Game)' in item:
                continue
            imdbid = self.cm.ph.getSearchGroups(item, '/tt([0-9]+?)/')[0]
            baseTtitle = ' '.join(self.cm.ph.getAllItemsBeetwenMarkers(item, '<a ', '</a>'))
            #title = title.split('<br/>')[0]
            title = self.cleanHtmlStr(item)
            year = self.cm.ph.getSearchGroups(item, '\((20[0-9]{2})\)')[0]
            if '' == year:
                year = self.cm.ph.getSearchGroups(item, '\((20[0-9]{2})\)')[0]
            if title.endswith('-'):
                title = title[:-1].strip()
            list.append({'title': title, 'base_title': self.cleanHtmlStr(baseTtitle), 'year': year, 'imdbid': imdbid})
        return True, list

    def imdbGetOrginalByTitle(self, imdbid):
        printDBG('CBaseSubProviderClass.imdbGetOrginalByTitle imdbid[%s]' % (imdbid))

        if not imdbid.startswith('tt'):
            imdbid = 'tt' + imdbid
        sts, data = self.cm.getPage('http://www.imdb.com/title/' + imdbid)
        if not sts:
            return False, {}
        title = self.cm.ph.getSearchGroups(data, '''<meta property='og:title' content="([^\(^"]+?)["\(]''')[0].strip()
        return True, {'title': title}

    def getTypeFromThemoviedb(self, imdbid, title):
        if '(TV Series)' in title:
            return 'series'
        itemType = 'movie'
        try:
            # lazy import
            import base64
            try:
                import json
            except Exception:
                import simplejson as json
            from Plugins.Extensions.IPTVPlayer.tools.iptvtools import byteify

            url = "https://api.themoviedb.org/3/find/tt{0}?api_key={1}&external_source=imdb_id".format(imdbid, base64.b64decode('NjMxMWY4MmQ1MjAxNDI2NWQ3NjVkMzk4MDJhYWZhYTc='))
            sts, data = self.cm.getPage(url)
            if not sts:
                return itemType
            data = byteify(json.loads(data))
            if len(data["tv_results"]):
                itemType = 'series'
        except Exception:
            printExc()
        return itemType

    def downloadAndUnpack(self, url, params={}, post_data=None, unpackToSubDir=False):
        data, fileName = self.downloadFileData(url, params, post_data)
        if data == None:
            return None
        ext = fileName.rsplit('.', 1)[-1].lower()
        printDBG("fileName[%s] ext[%s]" % (fileName, ext))
        if ext not in ['zip', 'rar']:
            SetIPTVPlayerLastHostError(_('Unknown file extension "%s".') % ext)
            return None

        tmpFile = GetTmpDir(self.TMP_FILE_NAME)
        tmpArchFile = tmpFile + '.' + ext
        tmpDIR = ''
        if unpackToSubDir:
            dirName = fileName.rsplit('.', 1)[0].split('filename=', 1)[-1]
            if dirName != '':
                tmpDIR = GetSubtitlesDir(dirName)

        if tmpDIR == '':
            tmpDIR = GetTmpDir(self.TMP_DIR_NAME)

        printDBG(">>")
        printDBG(fileName)
        printDBG(tmpFile)
        printDBG(tmpArchFile)
        printDBG(tmpDIR)
        printDBG(">>")

        if not self.writeFile(tmpArchFile, data):
            return None

        if not self.unpackArchive(tmpArchFile, tmpDIR):
            rm(tmpArchFile)
            return None
        return tmpDIR

    def downloadFileData(self, url, params={}, post_data=None):
        printDBG('CBaseSubProviderClass.downloadFileData url[%s]' % url)
        urlParams = dict(params)
        urlParams['max_data_size'] = self.getMaxFileSize()

        sts, data = self.cm.getPage(url, urlParams, post_data)
        if sts:
            fileName = self.cm.meta.get('content-disposition', '')
            if fileName != '':
                tmpFileName = self.cm.ph.getSearchGroups(fileName.lower(), '''filename=['"]([^'^"]+?)['"]''')[0]
                if tmpFileName != '':
                    printDBG("downloadFileData: replace fileName[%s] with [%s]" % (fileName, tmpFileName))
                    fileName = tmpFileName
            else:
                fileName = urllib.unquote(self.cm.meta['url'].split('/')[-1])

            return data, fileName

        return None, ''

    def writeFile(self, filePath, data):
        printDBG('CBaseSubProviderClass.writeFile path[%s]' % filePath)
        try:
            with open(filePath, 'w') as f:
                f.write(data)
            return True
        except Exception:
            printExc()
            SetIPTVPlayerLastHostError(_('Failed to write file "%s".') % filePath)
        return False

    def unpackZipArchive(self, tmpFile, tmpDIR):
        errorCode = 0
        # check if archive is not evil
        cmd = "unzip -l '{0}' 2>&1 ".format(tmpFile)
        ret = self.iptv_execute(cmd)
        if not ret['sts'] or 0 != ret['code']:
            errorCode = ret['code']
            if errorCode == 0:
                errorCode = 9
        elif '..' in ret['data']:
            errorCode = 9

        # if archive is valid then upack it
        if errorCode == 0:
            cmd = "unzip -o '{0}' -d '{1}' 2>/dev/null".format(tmpFile, tmpDIR)
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
        printDBG('CBaseSubProviderClass.unpackArchive tmpFile[%s], tmpDIR[%s]' % (tmpFile, tmpDIR))
        rmtree(tmpDIR, ignore_errors=True)
        if not mkdirs(tmpDIR):
            SetIPTVPlayerLastHostError(_('Failed to create directory "%s".') % tmpDIR)
            return False
        if tmpFile.endswith('.zip'):
            return self.unpackZipArchive(tmpFile, tmpDIR)
        elif tmpFile.endswith('.rar'):
            cmd = "unrar e -o+ -y '{0}' '{1}' 2>/dev/null".format(tmpFile, tmpDIR)
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
        # list files
        for file in os_listdir(cItem['path']):
            numItems += 1
            filePath = os_path.join(cItem['path'], file)
            params = dict(cItem)
            if os_path.isfile(filePath):
                ext = file.rsplit('.', 1)[-1].lower()
                params.update({'file_path': filePath, 'title': os_path.splitext(file)[0]})
                if ext in subExt:
                    params['ext'] = ext
                    self.addSubtitle(params)
                elif ext in archExt:
                    self.addDir(params)
            elif dirCategory != None and os_path.isdir(filePath):
                params.update({'category': dirCategory, 'path': filePath, 'title': file})
                self.addDir(params)
            if numItems >= maxItems:
                break
        self.currList.sort(key=lambda k: k['title'])

    def converFileToUtf8(self, inFile, outFile, lang=''):
        printDBG('CBaseSubProviderClass.converFileToUtf8 inFile[%s] outFile[%s]' % (inFile, outFile))
        # detect encoding
        encoding = ''
        cmd = '%s "%s"' % (GetUchardetPath(), inFile)
        ret = self.iptv_execute(cmd)
        if ret['sts'] and 0 == ret['code']:
            encoding = MapUcharEncoding(ret['data'])
            if 0 != ret['code'] or 'unknown' in encoding:
                encoding = ''
            else:
                encoding = encoding.strip()

        if lang == '':
            lang = GetDefaultLang()

        if lang == 'pl' and encoding == 'iso-8859-2':
            encoding = GetPolishSubEncoding(tmpFile)
        elif '' == encoding:
            encoding = 'utf-8'

        # convert file to UTF-8
        try:
            with open(inFile) as f:
                data = f.read()
            try:
                data = data.decode(encoding).encode('UTF-8')
                if self.writeFile(outFile, data):
                    return True
            except Exception:
                printExc()
                SetIPTVPlayerLastHostError(_('Failed to convert the file "%s" to UTF-8.') % inFile)
        except Exception:
            printExc()
            SetIPTVPlayerLastHostError(_('Failed to open the file "%s".') % inFile)
        return False
