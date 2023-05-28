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
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus
###################################################
# FOREIGN import
###################################################
from datetime import timedelta
import time
import re
import unicodedata
import base64
try:
    from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import urlsplit, urlunsplit
except Exception:
    printExc()
from os import listdir as os_listdir, path as os_path
try:
    import json
except Exception:
    import simplejson as json
try:
    try:
        from cStringIO import StringIO
    except Exception:
        from StringIO import StringIO
    import gzip
except Exception:
    pass
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


class PodnapisiNetProvider(CBaseSubProviderClass):

    def __init__(self, params={}):
        self.MAIN_URL = 'https://www.podnapisi.net/'
        self.USER_AGENT = 'Mozilla/5.0 (X11; Linux i686) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/37.0.2062.120 Chrome/37.0.2062.120 Safari/537.36'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'Referer': self.MAIN_URL, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Encoding': 'gzip, deflate'}

        params['cookie'] = 'podnapisinet.cookie'
        CBaseSubProviderClass.__init__(self, params)

        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.cacheFilters = {}

        self.dInfo = params['discover_info']

    def getPage(self, url, params={}, post_data=None):
        if params == {}:
            params = dict(self.defaultParams)

        sts, data = self.cm.getPage(url, params, post_data)
        if sts and params.get('use_cookie', True) and params.get('load_cookie', True) and params.get('save_cookie', True):
            session = self.cm.ph.getSearchGroups(data, '''var\s+phpbb3_session\s+=\s+['"]([^'^"]+?)['"]''')
            tmp = urlsplit(url)
            checkUrl = self.getFullUrl('/forum/app.php/track?path=') + tmp.path + urllib_quote('?' + tmp.query)
            checkSts, checkData = self.cm.getPage(checkUrl, params, post_data)
            if checkSts:
                checkSession = self.cm.ph.getSearchGroups(checkData, '''var\s+my_session\s+=\s+['"]([^'^"]+?)['"]''')
                printDBG('my_session [%s], phpbb3_session[%s]' % (checkSession, session))
                if checkSession != session:
                    sts, data = self.cm.getPage(url, params, post_data)
        return sts, data

    def fillCacheFilters(self):
        printDBG("PodnapisiNetProvider.fillFiltersCache")
        self.cacheFilters = {}

        baseUrl = '/subtitles/search/advanced'

        sts, data = self.getPage(self.getFullUrl(baseUrl))
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'advanced_search_panel'), ('</form', '>'))[1]
        for filter in [{'key': 'movie_type', 'marker': 'movie_type'},
                       {'key': 'episode_type', 'marker': 'episode_type'},
                       {'key': 'flags', 'marker': 'flags'},
                       {'key': 'fps', 'marker': 'fps'},
                       {'key': 'language', 'marker': 'language'}]:
            self.cacheFilters[filter['key']] = []
            tmp = self.cm.ph.getDataBeetwenMarkers(data, filter['marker'], '</select>', False)[1]
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<option', '</option>', withMarkers=True, caseSensitive=False)
            allItemAdded = False
            for item in tmp:
                value = self.cm.ph.getSearchGroups(item, '''value=["']?([^"^'^\s^>]+?)[\s"'>]''')[0].strip()
                self.cacheFilters[filter['key']].append({filter['key']: value, 'title': self.cleanHtmlStr(item)})
                if value == '':
                    allItemAdded = True
            if not allItemAdded:
                self.cacheFilters[filter['key']].insert(0, {filter['key']: '', 'title': _('Any')})

        # prepare default values for filters
        season = self.dInfo.get('season', None)
        episode = self.dInfo.get('episode', None)
        if season != None and episode != None:
            defaultType = 'tv-series'
        elif episode != None:
            defaultType = 'mini-series'
        else:
            defaultType = ''
        printDBG("season [%s] episode[%s]" % (episode, season))
        defaultLanguage = GetDefaultLang()

        # move default values to the begining of the list
        for defItem in [{'key': 'language', 'val': defaultLanguage}, {'key': 'movie_type', 'val': defaultType}]:
            newList = []
            promotedItem = None
            for item in self.cacheFilters[defItem['key']]:
                if None == promotedItem and defItem['val'] == item[defItem['key']]:
                    promotedItem = item
                else:
                    newList.append(item)
            if None != promotedItem:
                newList.insert(0, promotedItem)
                self.cacheFilters[defItem['key']] = newList

    def listFilters(self, cItem, filter, nextCategory):
        printDBG("PodnapisiNetProvider.listFilters")
        if {} == self.cacheFilters:
            self.fillCacheFilters()

        cItem = dict(cItem)
        cItem['category'] = nextCategory
        self.listsTab(self.cacheFilters.get(filter, []), cItem)

    def _getHeader(self, lang):
        header = dict(self.HTTP_HEADER)
        header['Cookie'] = 'LanguageFilter={0}; HearingImpaired=2; ForeignOnly=False;'.format(lang)
        return header

    def listSubItems(self, cItem, nextCategory):
        printDBG("PodnapisiNetProvider.listSubItems")

        keywords = urllib_quote_plus(self.params['confirmed_title'])
        year = cItem.get('year', '')
        language = cItem.get('language', '')
        season = None
        episode = None
        if 'tv-series' == cItem.get('movie_type'):
            season = self.dInfo.get('season', None)
            episode = self.dInfo.get('episode', None)
        elif 'mini-series' == cItem.get('movie_type'):
            episode = self.dInfo.get('episode', None)
        if season == None:
            season = ''
        if episode == None:
            episode = ''

        baseUrl = "/subtitles/search/advanced?keywords=%s&year=%s&seasons=%s&episodes=%s&language=%s" % (keywords, year, season, episode, language)
        for key in ['movie_type', 'episode_type', 'fps', 'flags']:
            if cItem.get(key, '') != '':
                baseUrl += '&' + key + '=' + cItem[key]

        url = self.getFullUrl(baseUrl)
        sts, data = self.cm.getPage(url)
        if not sts:
            return

        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<thead', '</thead>')[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<th', '</th>')
        rawDesc = []
        for item in tmp:
            name = self.cleanHtmlStr(item)
            key = self.cm.ph.getDataBeetwenMarkers(item, 'sort=', '&', False)[1]
            if name == '':
                name = key.replace('.', ' ').title()
            rawDesc.append({'key': key, 'name': name, 'val': ''})
        del tmp

        lang = ''
        data = self.cm.ph.getDataBeetwenMarkers(data, '<tbody', '</tbody>')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<tr', '</tr>')
        for item in data:
            item = self.cm.ph.getAllItemsBeetwenMarkers(item, '<td', '</td>')
            if len(item) < 1:
                continue
            title = self.cleanHtmlStr(item[0])
            url = self.cm.ph.getSearchGroups(item[0], '''href=["']?([^"^'^\s^>]+?)[\s"'>]''')[0].strip()
            descTab = []
            for idx in range(len(item)):
                if idx >= len(rawDesc):
                    break
                value = self.cleanHtmlStr(item[idx])
                rawDesc[idx]['val'] = value
                if idx == 0:
                    continue
                descTab.append('%s: %s' % (rawDesc[idx]['name'], value))
                if rawDesc[idx]['key'] == 'language':
                    lang = value
                if rawDesc[idx]['key'] == 'fps':
                    try:
                        fps = float(value.split('(')[0].strip())
                    except Exception:
                        printExc()
                        fps = 0

            params = dict(cItem)
            params.update({'category': nextCategory, 'title': title, 'url': self.getFullUrl(url), 'lang': lang, 'fps': fps, 'desc': ', '.join(descTab)})
            self.addDir(params)

    def getSubtitlesList(self, cItem, nextCategory):
        printDBG("PodnapisiNetProvider.getSubtitlesList")

        imdbid = ''
        subId = cItem['url'].split('/')[-2]
        fps = cItem.get('fps', 0)

        urlParams = dict(self.defaultParams)
        tmpDIR = self.downloadAndUnpack(cItem['url'], urlParams)
        if None == tmpDIR:
            return

        cItem = dict(cItem)
        cItem.update({'category': '', 'path': tmpDIR, 'fps': fps, 'imdbid': imdbid, 'sub_id': subId})
        self.listSupportedFilesFromPath(cItem, self.getSupportedFormats(all=True))

    def listSubsInPackedFile(self, cItem, nextCategory):
        printDBG("PodnapisiNetProvider.listSubsInPackedFile")
        tmpFile = cItem['file_path']
        tmpDIR = tmpFile[:-4]

        if not self.unpackArchive(tmpFile, tmpDIR):
            return

        cItem = dict(cItem)
        cItem.update({'category': nextCategory, 'path': tmpDIR})
        self.listSupportedFilesFromPath(cItem, self.getSupportedFormats(all=True))

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
        if name == None or category.startswith('list_filter_'):
            filter = category.replace('list_filter_', '')
            if filter == '':
                self.listFilters(self.currItem, 'movie_type', 'list_filter_language')
            elif filter == 'language':
                self.listFilters(self.currItem, filter, 'list_sub_items')
        elif category == 'list_sub_items':
            self.listSubItems(self.currItem, 'list_subtitles')
        elif category == 'list_subtitles':
            self.getSubtitlesList(self.currItem, 'list_sub_in_packed_file')
        elif category == 'list_sub_in_packed_file':
            self.listSubsInPackedFile(self.currItem, 'list_sub_in_packed_file')

        CBaseSubProviderClass.endHandleService(self, index, refresh)


class IPTVSubProvider(CSubProviderBase):

    def __init__(self, params={}):
        CSubProviderBase.__init__(self, PodnapisiNetProvider(params))
