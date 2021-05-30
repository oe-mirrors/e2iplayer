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


def GetLanguageTab():
    tab = [["Albanian", "sq", "alb"],
            ["Arabic", "ar", "ara"],
            ["Belarusian", "hy", "arm"],
            ["Bosnian", "bs", "bos"],
            ["BosnianLatin", "bs", "bos"],
            ["Bulgarian", "bg", "bul"],
            ["Brazilian", "pb", "pob"],
            ["Catalan", "ca", "cat"],
            ["Chinese", "zh", "chi"],
            ["Croatian", "hr", "hrv"],
            ["Czech", "cs", "cze"],
            ["Danish", "da", "dan"],
            ["Dutch", "nl", "dut"],
            ["English", "en", "eng"],
            ["Espanol", "es", "spa"],
            ["Estonian", "et", "est"],
            ["Persian", "fa", "per"],
            ["Farsi", "fa", "per"],
            ["Finnish", "fi", "fin"],
            ["French", "fr", "fre"],
            ["German", "de", "ger"],
            ["Greek", "el", "ell"],
            ["Hebrew", "he", "heb"],
            ["Hindi", "hi", "hin"],
            ["Hungarian", "hu", "hun"],
            ["Icelandic", "is", "ice"],
            ["Indonesian", "id", "ind"],
            ["Italian", "it", "ita"],
            ["Japanese", "ja", "jpn"],
            ["Korean", "ko", "kor"],
            ["Latvian", "lv", "lav"],
            ["Lithuanian", "lt", "lit"],
            ["Macedonian", "mk", "mac"],
            ["Malay", "ms", "may"],
            ["Norwegian", "no", "nor"],
            ["Polish", "pl", "pol"],
            ["Portuguese", "pt", "por"],
            ["Romanian", "ro", "rum"],
            ["Russian", "ru", "rus"],
            ["Serbian", "sr", "scc"],
            ["Slovak", "sk", "slo"],
            ["Slovenian", "sl", "slv"],
            ["Spanish", "es", "spa"],
            ["Swedish", "sv", "swe"],
            ["Thai", "th", "tha"],
            ["Turkish", "tr", "tur"],
            ["Ukrainian", "uk", "ukr"],
            ["Vietnamese", "vi", "vie"]
          ]
    return tab


class SubsceneComProvider(CBaseSubProviderClass):
    LANGUAGE_CACHE = []

    def __init__(self, params={}):
        self.MAIN_URL = 'https://subscene.com/'
        self.USER_AGENT = 'Mozilla/5.0 (X11; Linux i686) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/37.0.2062.120 Chrome/37.0.2062.120 Safari/537.36'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'Referer': self.MAIN_URL, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Encoding': 'gzip, deflate'}

        params['cookie'] = 'subscenecom.cookie'
        CBaseSubProviderClass.__init__(self, params)

        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.SEARCH_TYPE_TAB = [{'title': _('By media title'), 'category': 'search_by_title'}]
                                #,
                                #{'title':_('By release name'), 'category':'search_by_release'}]
        self.cache = {}

    def _getHeader(self, lang):
        header = dict(self.HTTP_HEADER)
        header['Cookie'] = 'LanguageFilter={0}; HearingImpaired=2; ForeignOnly=False;'.format(lang)
        return header

    def _getLanguages(self):
        defLang = GetDefaultLang()

        def _isDefaultLanguage(langName):
            tab = GetLanguageTab()
            for item in tab:
                if item[1] != defLang:
                    continue
                if item[0] in langName:
                    return True

        url = self.getFullUrl('/filter/edit')
        sts, data = self.cm.getPage(url, self.defaultParams)
        if not sts:
            return []

        list = []
        defaultLanguages = []
        data = self.cm.ph.getDataBeetwenMarkers(data, '<label class="h5">', '<button type="submit">', False)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<label>', '</label>')
        for item in data:
            langId = self.cm.ph.getSearchGroups(item, 'value="([0-9]+?)"')[0]
            if '' == langId:
                continue
            title = self.cleanHtmlStr(item)
            if _isDefaultLanguage(title):
                defaultLanguages.append({'title': _(title), 'lang_id': langId})
            else:
                list.append({'title': _(title), 'lang_id': langId})
        defaultLanguages.extend(list)
        return defaultLanguages

    def getLanguages(self, cItem, nextCategory):
        printDBG("SubsceneComProvider.getEpisodes")
        if 0 == len(SubsceneComProvider.LANGUAGE_CACHE):
            SubsceneComProvider.LANGUAGE_CACHE = self._getLanguages()

        for item in SubsceneComProvider.LANGUAGE_CACHE:
            params = dict(cItem)
            params.update(item)
            params.update({'category': nextCategory})
            self.addDir(params)

    def listSearchType(self, cItem):
        printDBG("SubsceneComProvider.listSearchType")
        self.listsTab(self.SEARCH_TYPE_TAB, cItem)

    def searchByTitle(self, cItem, nextCategory):
        printDBG("SubsceneComProvider.searchByTitle")
        self.cache = {}

        url = self.getFullUrl('/subtitles/searchbytitle')

        #urllib.quote_plus()

        header = self._getHeader(cItem['lang_id'])
        sts, data = self.cm.getPage(url, {'header': header}, {'query': self.params['confirmed_title'], 'l': ''})
        if not sts:
            return

        if 'alternativeSearch' in data:
            data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="search-result">', '<div class="alternativeSearch">', False)[1]
        else:
            data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="search-result">', '<footer>', False)[1]

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<h2', '</ul>')
        for groupItem in data:
            groupTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(groupItem, '<h2', '</h2>', True)[1])
            if '' == groupTitle:
                continue
            items = self.cm.ph.getAllItemsBeetwenMarkers(groupItem, '<li', '</li>')
            tab = []
            for item in items:
                tmp = self.cm.ph.getSearchGroups(item, '<a[^>]+?href="([^"]+?)"[^>]*?>([^<]+?)</a>', 2)
                if tmp[0] == '' or tmp[1] == '':
                    continue
                tab.append({'group_id': groupTitle, 'title': self.cleanHtmlStr(tmp[1]), 'url': self.getFullUrl(tmp[0])})
            if len(tab):
                self.cache[groupTitle] = tab
                params = dict(cItem)
                params.update({'title': groupTitle, 'group_id': groupTitle, 'category': nextCategory})
                self.addDir(params)

    def listGroup(self, cItem, nextCategory):
        printDBG("SubsceneComProvider.listGroup")
        cItem = dict(cItem)
        cItem.update({'category': nextCategory})
        self.listsTab(self.cache[cItem['group_id']], cItem)

    def searchByReleaseName(self, cItem, nextCategory):
        printDBG("SubsceneComProvider.searchByReleaseName")
        url = self.getFullUrl('/subtitles/release?q={0}&r=true'.format(urllib.quote_plus(self.params['confirmed_title'])))
        cItem = dict(cItem)
        cItem.update({'url': url})
        self.listSubItems(cItem, nextCategory)

    def listSubItems(self, cItem, nextCategory):
        printDBG("SubsceneComProvider.listSubItems")

        def _getLangCode(lang):
            tab = GetLanguageTab()
            for item in tab:
                if item[0] == lang:
                    return item[1]
            return ''

        header = self._getHeader(cItem['lang_id'])

        sts, data = self.cm.getPage(cItem['url'], {'header': header})
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenMarkers(data, '<table>', '</table>', False)[1]

        headData = self.cm.ph.getDataBeetwenMarkers(data, '<thead>', '</thead>', False)[1]
        headData = self.cm.ph.getAllItemsBeetwenMarkers(headData, '<td ', '</td>')
        heads = []
        for item in headData:
            heads.append(self.cleanHtmlStr(item))
        del headData

        data = self.cm.ph.getDataBeetwenMarkers(data, '<tbody>', '</tbody>', False)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<td class="a1">', '</tr>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0])
            if url == '':
                continue

            bodyData = self.cm.ph.getAllItemsBeetwenMarkers(item, '<td ', '</td>')

            #title
            if 'positive-icon' in bodyData[0]:
                t1 = '[+]'
            elif 'neutral-icon' in bodyData[0]:
                t1 = '[/]'
            else:
                t1 = '[-]'
            title = t1 + ' ' + self.cleanHtmlStr(bodyData[0])

            #lang
            lang = _getLangCode(self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(bodyData[0], '<span class="l', '</span>')[1]))

            # desc
            descTab = []
            if len(bodyData) == len(heads):
                for idx in range(len(heads)):
                    val = self.cleanHtmlStr(bodyData[idx])
                    if val.strip() == '':
                        if 'class="a41"' in bodyData[idx]:
                            val = _('Yes')
                        elif 'class="a40"' in bodyData[idx]:
                            val = _('No')
                    descTab.append('{0}: {1}'.format(heads[idx], val))
                desc = '[/br]'.join(descTab[1:])
            else:
                desc = cItem['desc']

            params = dict(cItem)
            params.update({'category': nextCategory, 'title': title, 'url': url, 'lang': lang, 'desc': desc})
            self.addDir(params)

    def getSubtitlesList(self, cItem, nextCategory):
        printDBG("SubsceneComProvider.getSubtitlesList")

        sts, data = self.cm.getPage(cItem['url'], {'with_metadata': True})
        if not sts:
            return
        cUrl = data.meta['url']

        imdbid = self.cm.ph.getSearchGroups(data, '/title/(tt[0-9]+?)[^0-9]')[0]
        subId = self.cm.ph.getSearchGroups(data, 'SubtitleId[^0-9]*?([0-9]+?)[^0-9]')[0]
        url = self.getFullUrl(self.cm.ph.getSearchGroups(data, 'href="([^"]*?/subtitle/download[^"]+?)"')[0], cUrl)
        if url == '':
            url = self.cm.ph.getDataBeetwenNodes(data, ('<a', '>', 'downloadButton'), ('</a', '>'))[1]
            url = self.getFullUrl(self.cm.ph.getSearchGroups(url, 'href="([^"]+?)"')[0], cUrl)

        urlParams = dict(self.defaultParams)
        tmpDIR = self.downloadAndUnpack(url, urlParams)
        if None == tmpDIR:
            return

        cItem = dict(cItem)
        cItem.update({'category': nextCategory, 'path': tmpDIR, 'imdbid': imdbid, 'sub_id': subId})
        self.listSupportedFilesFromPath(cItem)

    def listSubsInPackedFile(self, cItem, nextCategory):
        printDBG("SubsceneComProvider.listSubsInPackedFile")
        tmpFile = cItem['file_path']
        tmpDIR = tmpFile[:-4]

        if not self.unpackArchive(tmpFile, tmpDIR):
            return

        cItem = dict(cItem)
        cItem.update({'category': nextCategory, 'path': tmpDIR})
        self.listSupportedFilesFromPath(cItem)

    def _getFileName(self, title, lang, subId, imdbid):
        title = RemoveDisallowedFilenameChars(title).replace('_', '.')
        match = re.search(r'[^.]', title)
        if match:
            title = title[match.start():]

        fileName = "{0}_{1}_0_{2}_{3}".format(title, lang, subId, imdbid)
        fileName = fileName + '.srt'
        return fileName

    def downloadSubtitleFile(self, cItem):
        printDBG("SubsceneComProvider.downloadSubtitleFile")
        retData = {}
        title = cItem['title']
        lang = cItem['lang']
        subId = cItem['sub_id']
        imdbid = cItem['imdbid']
        inFilePath = cItem['file_path']

        outFileName = self._getFileName(title, lang, subId, imdbid)
        outFileName = GetSubtitlesDir(outFileName)

        printDBG(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
        printDBG(inFilePath)
        printDBG(outFileName)
        printDBG(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")

        if self.converFileToUtf8(inFilePath, outFileName, lang):
            retData = {'title': title, 'path': outFileName, 'lang': lang, 'imdbid': imdbid, 'sub_id': subId}

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
            self.getLanguages({'name': 'category'}, 'list_search_types')
        elif category == 'list_search_types':
            self.listSearchType(self.currItem)
        elif category == 'search_by_title':
            self.searchByTitle(self.currItem, 'list_group')
        elif category == 'list_group':
            self.listGroup(self.currItem, 'list_sub_items')
        elif category == 'list_sub_items':
            self.listSubItems(self.currItem, 'list_subtitles')
        elif category == 'search_by_release':
            self.searchByReleaseName(self.currItem, 'list_subtitles')
        elif category == 'list_subtitles':
            self.getSubtitlesList(self.currItem, 'list_sub_in_packed_file')
        elif category == 'list_sub_in_packed_file':
            self.listSubsInPackedFile(self.currItem, 'list_sub_in_packed_file')

        CBaseSubProviderClass.endHandleService(self, index, refresh)


class IPTVSubProvider(CSubProviderBase):

    def __init__(self, params={}):
        CSubProviderBase.__init__(self, SubsceneComProvider(params))
