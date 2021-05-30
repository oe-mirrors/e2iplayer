# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CDisplayListItem, RetHost
from Plugins.Extensions.IPTVPlayer.components.isubprovider import CSubProviderBase, CBaseSubProviderClass

from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetDefaultLang, GetCookieDir, byteify, \
                                                          RemoveDisallowedFilenameChars, GetSubtitlesDir, GetTmpDir, rm, \
                                                          MapUcharEncoding, GetPolishSubEncoding, rmtree, mkdirs
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
###################################################

###################################################
# FOREIGN import
###################################################
from datetime import timedelta
import time
import re
import urllib
import unicodedata
import base64
from os import listdir as os_listdir, path as os_path
from Components.config import config, ConfigSelection, ConfigYesNo, ConfigText, getConfigListEntry
###################################################


###################################################
# E2 GUI COMMPONENTS
###################################################
from Plugins.Extensions.IPTVPlayer.components.asynccall import MainSessionWrapper
from Screens.MessageBox import MessageBox
###################################################

###################################################
# Config options for HOST
###################################################


def GetConfigList():
    optionList = []
    return optionList
###################################################


class SubsRoProvider(CBaseSubProviderClass):

    def __init__(self, params={}):
        params['cookie'] = 'subsro.cookie'
        CBaseSubProviderClass.__init__(self, params)

        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/64.0.3282.168 Safari/537.36'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'Referer': self.getMainUrl(), 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Encoding': 'gzip, deflate'}

        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.dInfo = params['discover_info']

    def getMainUrl(self):
        return 'http://subs.ro/'

    def getMaxFileSize(self):
        return 1024 * 1024 * 10 # 10MB, max size of sub file to be download

    def getFormQuery(self, data, marker, searchText):
        query = {}
        data = self.cm.ph.getDataBeetwenNodes(data, ('<form', '>', marker), ('</form', '>'), withNodes=True, caseSensitive=False)[1]
        actionUrl = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''action=['"]([^'^"]+?)['"]''')[0])
        data = re.compile('''(<input[^>]+?>)''', re.I).findall(data)
        for item in data:
            name = self.cm.ph.getSearchGroups(item, '''name=['"]([^'^"]+?)['"]''', ignoreCase=True)[0]
            value = self.cm.ph.getSearchGroups(item, '''value=['"]([^'^"]+?)['"]''', ignoreCase=True)[0]
            if '' != name:
                query[name] = value
        key = 'titlu-film'
        if key in query:
            query[key] = searchText
        else:
            query['search-text'] = searchText
        return actionUrl, query

    def getSearchList(self, cItem, nextCategory):
        printDBG("SubsRoProvider.getSearchList")

        urlParams = dict(self.defaultParams)
        urlParams['header'] = dict(urlParams['header'])

        url = self.getFullUrl('/subtitrari')
        sts, data = self.cm.getPage(url, urlParams)
        if not sts:
            return

        actionUrl, query = self.getFormQuery(data, '', self.params['confirmed_title'])
        if '?' in actionUrl:
            actionUrl += '&'
        else:
            actionUrl += '?'
        actionUrl += urllib.urlencode(query)

        sts, data = self.cm.getPage(actionUrl, urlParams)
        if not sts:
            return

        urlParams['header'].update({'Referer': actionUrl, 'Accept': '*/*', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'X-Requested-With': 'XMLHttpRequest'})
        actionUrl, query = self.getFormQuery(data, 'search-subtitrari', self.params['confirmed_title'])
        sts, data = self.cm.getPage(actionUrl, urlParams, query)
        if not sts:
            return

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
        for item in data:
            url = self.cm.ph.getDataBeetwenNodes(item, ('<a', '>', 'details'), ('</a', '>'))[1]
            url = self.getFullUrl(self.cm.ph.getSearchGroups(url, '''href=['"]([^"^']+?)['"]''')[0])
            if url == '':
                continue

            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<h', '>', 'title'), ('</h', '>'), False)[1])
            lang = self.cm.ph.getSearchGroups(item, 'flag\-([a-z]+?)\-big\.png')[0]

            descTab = []
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(item, '<p', '</p>')
            for t in tmp:
                t = self.cleanHtmlStr(t).replace(' , ', ', ').replace(' : ', ': ')
                if t != '':
                    descTab.append(t)

            descTab.append(self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'sub-comment'), ('</div', '>'), False)[1]))

            params = dict(cItem)
            params.update({'category': nextCategory, 'url': self.getFullUrl(url), 'title': self.cleanHtmlStr(title), 'lang': lang, 'desc': '[/br]'.join(descTab)})
            params['title'] = ('[%s] ' % lang) + params['title']
            self.addDir(params)

    def getSubtitlesList(self, cItem):
        printDBG("SubsRoProvider.getSubtitlesList")

        sts, data = self.cm.getPage(cItem['url'], self.defaultParams)
        if not sts:
            return
        imdbid = self.cm.ph.getSearchGroups(data, '/title/(tt[0-9]+?)[^0-9]')[0]
        url = self.getFullUrl(self.cm.ph.getSearchGroups(data, 'href="([^"]*?/descarca/[^"]+?)"')[0])
        subId = url.rsplit('/', 1)[-1]

        try:
            fps = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, 'FPS', '</p>', False)[1])
            fps = float(self.cm.ph.getSearchGroups(fps, '''([0-9\.]+)''')[0])
        except Exception:
            fps = 0
            printExc()

        urlParams = dict(self.defaultParams)
        tmpDIR = self.downloadAndUnpack(url, urlParams, unpackToSubDir=True)
        if None == tmpDIR:
            return

        cItem = dict(cItem)
        cItem.update({'path': tmpDIR, 'fps': fps, 'imdbid': imdbid, 'sub_id': subId})
        self.listDir(cItem)

    def listDir(self, cItem):
        printDBG("SubsRoProvider.listDir")
        cItem = dict(cItem)
        cItem.update({'category': ''})
        self.listSupportedFilesFromPath(cItem, self.getSupportedFormats(all=True), dirCategory='list_dir')
        for item in self.currList:
            item['desc'] = cItem.get('path', '') + '/'

    def _getFileName(self, title, lang, subId, imdbid, fps, ext):
        title = RemoveDisallowedFilenameChars(title).replace('_', '.')
        match = re.search(r'[^.]', title)
        if match:
            title = title[match.start():]

        fileName = "{0}_{1}_0_{2}_{3}".format(title, lang, subId, imdbid)
        if fps > 0:
            fileName += '_fps{0}'.format(fps)
        fileName = fileName + '.' + ext
        return fileName

    def downloadSubtitleFile(self, cItem):
        printDBG("SubsceneComProvider.downloadSubtitleFile")
        retData = {}
        title = cItem['title']
        lang = cItem['lang']
        subId = cItem['sub_id']
        imdbid = cItem['imdbid']
        inFilePath = cItem['file_path']
        ext = cItem.get('ext', 'srt')
        fps = cItem.get('fps', 0)

        outFileName = self._getFileName(title, lang, subId, imdbid, fps, ext)
        outFileName = GetSubtitlesDir(outFileName)

        printDBG(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
        printDBG(inFilePath)
        printDBG(outFileName)
        printDBG(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")

        if self.converFileToUtf8(inFilePath, outFileName, lang):
            retData = {'title': title, 'path': outFileName, 'lang': lang, 'imdbid': imdbid, 'sub_id': subId, 'fps': fps}

        return retData

    def handleService(self, index, refresh=0):
        printDBG('handleService start')

        CBaseSubProviderClass.handleService(self, index, refresh)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.getSearchList({'name': 'category'}, 'get_subtitles')
        if category == 'list_dir':
            self.listDir(self.currItem)
        elif category == 'get_subtitles':
            self.getSubtitlesList(self.currItem)

        CBaseSubProviderClass.endHandleService(self, index, refresh)


class IPTVSubProvider(CSubProviderBase):

    def __init__(self, params={}):
        CSubProviderBase.__init__(self, SubsRoProvider(params))
