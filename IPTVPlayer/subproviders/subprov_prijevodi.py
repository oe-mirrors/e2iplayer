# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.isubprovider import CSubProviderBase, CBaseSubProviderClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetDefaultLang, RemoveDisallowedFilenameChars, GetSubtitlesDir, rm
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib
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


class PrijevodiOnline(CBaseSubProviderClass):

    def __init__(self, params={}):
        self.MAIN_URL = 'https://www.prijevodi-online.org/'
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:39.0) Gecko/20100101 Firefox/39.0'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'Referer': self.MAIN_URL, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}

        params['cookie'] = 'prijevodionlineorg.cookie'
        CBaseSubProviderClass.__init__(self, params)

        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.languages = []

        self.dInfo = params['discover_info']
        self.searchTypes = [{'title': _('Series'), 'f_type': 'series', 'url': self.getFullUrl('serije')}, {'title': _('Movies'), 'f_type': 'movies', 'url': self.getFullUrl('filmovi')}]
        self.episodesCache = {}
        self.logedIn = None
        self.searchURL = ""

    def getPage(self, url, params={}, post_data=None):
        if params == {}:
            params = dict(self.defaultParams)
        sts, data = self.cm.getPage(url, params, post_data)
        return sts, data

    def initSubProvider(self):
        printDBG("PrijevodiOnline.initSubProvider")
        self.logedIn = False
        rm(self.COOKIE_FILE)
        # Login not supported at now

    def listSearchTypes(self, cItem, nextCategory):
        printDBG("PrijevodiOnline.listSearchTypes")
        cItem = dict(cItem)
        cItem['category'] = nextCategory
        self.listsTab(self.searchTypes, cItem)

    def listMenuABC(self, cItem, nextCategory):
        printDBG("PrijevodiOnline.listMenuABC")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        promItem = None
        data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="pages">', '</ul>')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
        for item in data:
            title = self.cleanHtmlStr(item)
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0])
            if not self.cm.isValidUrl(url):
                continue
            params = dict(cItem)
            params.update({'category': nextCategory, 'title': title, 'url': url})
            if promItem == None and self.params['confirmed_title'].title().startswith(title.upper()):
                promItem = params
            else:
                self.addDir(params)
        if promItem != None:
            self.addDir(promItem, False)

    def listSeries(self, cItem, nextCategory):
        printDBG("PrijevodiOnline.listSeries")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        promItems = []
        data = self.cm.ph.getDataBeetwenMarkers(data, '<table', '</table>')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<tr', '</tr>')
        for item in data:
            tmp = self.cm.ph.getDataBeetwenReMarkers(item, re.compile('<td[^>]+?class="naziv"[^>]*?>'), re.compile('</td>'))[1]
            title = self.cleanHtmlStr(tmp)
            if title == '':
                title = self.cm.ph.getSearchGroups(tmp, '''title=['"]([^'^"]+?)['"]''')[0]
            url = self.getFullUrl(self.cm.ph.getSearchGroups(tmp, 'href="([^"]+?)"')[0])
            if not self.cm.isValidUrl(url):
                continue
            descTab = []
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(item, '<td', '</td>')
            for t in tmp:
                if 'class="naziv"' in t:
                    continue
                t = self.cleanHtmlStr(t)
                if t != '':
                    descTab.append(t)

            params = dict(cItem)
            params.update({'category': nextCategory, 'title': title, 'url': url, 'desc': ' | '.join(descTab)})
            if self.params['confirmed_title'].lower().startswith(title.lower()):
                promItems.append(params)
            else:
                self.addDir(params)
        for item in promItems:
            self.addDir(item, False)

    def listSeasons(self, cItem, nextCategory):
        printDBG("PrijevodiOnline.listSeasons")

        self.episodesCache = {}
        promSeasonsItems = []
        promEpisodesItems = []

        printDBG(self.dInfo)

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        self.episodesCache['imdbid'] = self.cm.ph.getSearchGroups(data, '''/tt([0-9]+?)[^0-9]''')[0]
        self.episodesCache['key'] = self.cm.ph.getSearchGroups(data, '''key\s*=\s*['"]([^'^"]+?)['"]''')[0]

        data = self.cm.ph.getDataBeetwenMarkers(data, '<div id="epizode">', '<script', False)[1]
        data = data.split('<h3 ')
        if len(data):
            del data[0]
        for sItem in data:
            sItem = '<h3 ' + sItem
            tmp = self.cm.ph.getDataBeetwenMarkers(sItem, '<h3', '</h3>')[1]
            sNum = self.cm.ph.getSearchGroups(tmp, '''id=['"]sezona\-([0-9]+)['"]''')[0].strip()
            sTitle = self.cleanHtmlStr(tmp)

            sItem = self.cm.ph.getAllItemsBeetwenMarkers(sItem, '<div', '</ul>')
            self.episodesCache[sNum] = []
            promEpisodesItems = []
            for eItem in sItem:
                tmp = self.cm.ph.getAllItemsBeetwenMarkers(eItem, '<li', '</li>')
                if len(tmp) < 2:
                    continue
                url = self.getFullUrl(self.cm.ph.getSearchGroups(tmp[1], 'rel="([^"]+?/get/[^"]+?)"')[0])
                if not self.cm.isValidUrl(url):
                    continue

                eNum = self.cleanHtmlStr(tmp[0]).replace('.', '').strip()
                title = self.cleanHtmlStr(''.join(tmp[0:2]))

                descTab = []
                for t in tmp:
                    t = self.cleanHtmlStr(t)
                    if t != '':
                        descTab.append(t)

                params = {'s_num': sNum, 'e_num': eNum, 'title': title, 'url': url, 'desc': ' | '.join(descTab)}
                if eNum == str(self.dInfo.get('episode')):
                    promEpisodesItems.append(params)
                else:
                    self.episodesCache[sNum].append(params)

            for item in promEpisodesItems:
                self.episodesCache[sNum].insert(0, item)

            if len(self.episodesCache[sNum]):
                params = dict(cItem)
                params.update({'category': nextCategory, 'title': sTitle, 's_num': sNum})
                if sNum == str(self.dInfo.get('season')):
                    promSeasonsItems.append(params)
                else:
                    self.addDir(params)

        for item in promSeasonsItems:
            self.addDir(item, False)

    def listEpisodesItems(self, cItem, nextCategory):
        printDBG("PrijevodiOnline.listEpisodesItems")

        params = dict(cItem)
        params['category'] = nextCategory
        seasonKey = cItem.get('s_num', '')
        tab = self.episodesCache.get(seasonKey, [])
        self.listsTab(tab, params)

    def listDownloadItems(self, cItem, nextCategory):
        printDBG("PrijevodiOnline.listDownloadItems")

        imdbid = self.episodesCache['imdbid']
        key = self.episodesCache['key']

        sts, data = self.getPage(cItem['url'], post_data={'key': key})
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenMarkers(data, '<table', '</table>')[1]
        data = data.split('<td rowspan="2" class="extra">')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0])
            if not self.cm.isValidUrl(url):
                continue

            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenReMarkers(item, re.compile('<a[^>]+?href'), re.compile('</a>'))[1])
            subId = self.cm.ph.getSearchGroups(item, 'rel="([0-9]+?)"')[0]
            if subId == '':
                subId = '0'
            lang = 'hr'
            fps = 0
            format = 'srt'

            descTab = []
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(item, '<td', '</td>')
            for t in tmp:
                t = self.cleanHtmlStr(t)
                if t != '':
                    descTab.append(t)
            params = dict(cItem)
            params.update({'category': nextCategory, 'lang': lang, 'fps': fps, 'format': format, 'title': title, 'imdbid': imdbid, 'subid': subId, 'url': url, 'desc': ' | '.join(descTab)})
            self.addDir(params)

    def listMoviesItems(self, cItem, nextCategory):
        printDBG("PrijevodiOnline.listMoviesItems")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        printDBG("+++++++++++++++++++++++++++++++++++++++++++++++++")
        printDBG(data)
        printDBG("+++++++++++++++++++++++++++++++++++++++++++++++++")

        promItems = []
        if cItem['url'].endswith('izdvojeno'):
            data = self.cm.ph.getDataBeetwenMarkers(data, '<div id="filmovi-forum-index">', '<scrip', False)[1]
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
            for item in data:
                title = self.cm.ph.getSearchGroups(item, '''alt=['"]([^'^"]+?)['"]''')[0]
                if title == '':
                    title = self.cm.ph.getSearchGroups(item, '''title=['"]([^'^"]+?)['"]''')[0]
                desc = self.cleanHtmlStr(item)
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0])
                if url == '':
                    continue

                params = dict(cItem)
                params.update({'category': nextCategory, 'title': title, 'url': url, 'desc': desc})
                title = re.sub('\([0-9]{4}\)', '', title).strip()
                if self.params['confirmed_title'].lower().startswith(title.lower()):
                    promItems.append(params)
                else:
                    self.addDir(params)
        else:
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<tr id="film-', '</tr>')
            for item in data:
                tmp = self.cm.ph.getDataBeetwenReMarkers(item, re.compile('<td[^>]+?class="naziv"[^>]*?>'), re.compile('</td>'))[1]
                title = self.cleanHtmlStr(tmp)
                if title == '':
                    title = self.cm.ph.getSearchGroups(tmp, '''title=['"]([^'^"]+?)['"]''')[0]
                url = self.getFullUrl(self.cm.ph.getSearchGroups(tmp, 'href="([^"]+?)"')[0])
                if '' == url:
                    continue
                descTab = []
                tmp = self.cm.ph.getAllItemsBeetwenMarkers(item, '<td', '</td>')
                for t in tmp:
                    if 'class="naziv"' in t:
                        continue
                    t = self.cleanHtmlStr(t)
                    if t != '':
                        descTab.append(t)

                params = dict(cItem)
                params.update({'category': nextCategory, 'title': title, 'url': url, 'desc': ' | '.join(descTab)})
                title = re.sub('\([0-9]{4}\)', '', title).strip()
                if self.params['confirmed_title'].lower().startswith(title.lower()):
                    promItems.append(params)
                else:
                    self.addDir(params)

        for item in promItems:
            self.addDir(item, False)

    def listTopicDownloadItems(self, cItem, nextCategory):
        printDBG("PrijevodiOnline.listTopicDownloadItems")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        imdbid = '0'
        subId = '0'
        lang = 'hr'
        fps = 0
        format = 'srt'

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
        for item in data:
            url = self.cm.ph.getSearchGroups(item, 'href="(https?://[^"]+?\.(?:rar|zip))"')[0]
            if not self.cm.isValidUrl(url):
                continue
            title = urllib.unquote(url.split('/')[-1])
            url = url.replace(' ', '%20')

            desc = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'category': nextCategory, 'lang': lang, 'fps': fps, 'format': format, 'title': title, 'imdbid': imdbid, 'subid': subId, 'url': url, 'desc': desc})
            self.addDir(params)

    def getSubtitlesList(self, cItem, nextCategory):
        printDBG("PrijevodiOnline.getSubtitlesList")

        url = cItem['url']

        if not self.cm.isValidUrl(url):
            return

        urlParams = dict(self.defaultParams)
        tmpDIR = self.downloadAndUnpack(url, urlParams)
        if None == tmpDIR:
            return

        cItem = dict(cItem)
        cItem.update({'category': '', 'path': tmpDIR})
        self.listSupportedFilesFromPath(cItem, self.getSupportedFormats(all=True))

    def listSubsInPackedFile(self, cItem, nextCategory):
        printDBG("PrijevodiOnline.listSubsInPackedFile")
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
        lang = cItem.get('lang', '')
        subId = cItem.get('subid', '0')
        imdbid = cItem.get('imdbid', '0')
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
            self.initSubProvider()
            self.listSearchTypes(self.currItem, 'list_abc')
        elif category == 'list_abc':
            type = self.currItem.get('f_type')
            if type == 'movies':
                nextCategory = 'list_movies'
            else:
                nextCategory = 'list_series'
            self.listMenuABC(self.currItem, nextCategory)
        # SERIES
        elif category == 'list_series':
            self.listSeries(self.currItem, 'list_seasons')
        elif category == 'list_seasons':
            self.listSeasons(self.currItem, 'list_episodes')
        elif category == 'list_episodes':
            self.listEpisodesItems(self.currItem, 'list_download_items')
        elif category == 'list_download_items':
            self.listDownloadItems(self.currItem, 'list_subtitles')
        # MOVIES
        elif category == 'list_movies':
            self.listMoviesItems(self.currItem, 'list_topic_download_items')
        elif category == 'list_topic_download_items':
            self.listTopicDownloadItems(self.currItem, 'list_subtitles')

        elif category == 'list_subtitles':
            self.getSubtitlesList(self.currItem, 'list_sub_in_packed_file')
        elif category == 'list_sub_in_packed_file':
            self.listSubsInPackedFile(self.currItem, 'list_sub_in_packed_file')

        CBaseSubProviderClass.endHandleService(self, index, refresh)


class IPTVSubProvider(CSubProviderBase):

    def __init__(self, params={}):
        CSubProviderBase.__init__(self, PrijevodiOnline(params))
