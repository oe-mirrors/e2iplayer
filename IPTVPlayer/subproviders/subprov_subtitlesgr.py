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
try:
    from urlparse import urlsplit, urlunsplit
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


class SubtitlesGrProvider(CBaseSubProviderClass):

    def __init__(self, params={}):
        self.MAIN_URL = 'http://gr.greek-subtitles.com/'
        self.USER_AGENT = 'Mozilla/5.0 (X11; Linux i686) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/37.0.2062.120 Chrome/37.0.2062.120 Safari/537.36'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'Referer': self.MAIN_URL, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Encoding': 'gzip, deflate'}

        params['cookie'] = 'subtitlesgr.cookie'
        CBaseSubProviderClass.__init__(self, params)

        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.cacheFilters = {}

        self.dInfo = params['discover_info']

    def getPage(self, url, params={}, post_data=None):
        if params == {}:
            params = dict(self.defaultParams)
        return self.cm.getPage(url, params, post_data)

    def listSubItems(self, cItem, nextCategory):
        printDBG("SubtitlesGrProvider.listSubItems")
        page = cItem.get('page', 0)
        keywords = urllib.quote_plus(self.params['confirmed_title'])
        baseUrl = "http://gr.greek-subtitles.com/search.php?page=%s&name=%s" % (page, keywords)

        url = self.getFullUrl(baseUrl)
        sts, data = self.cm.getPage(url)
        if not sts:
            return

        if ('page=%s&' % (page + 1)) in data:
            nextPage = True
        else:
            nextPage = False

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<tr on', '</tr>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=["']([^'^"]+?)['"]''')[0])
            lang = self.cm.ph.getSearchGroups(item, '''flags/([^\.]+?)\.gif''')[0]
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<a', '</a>')[1])
            desc = self.cleanHtmlStr(item.replace('</td>', ' | ').replace('</a>', ' | '))
            params = dict(cItem)
            params.update({'name': 'category', 'category': nextCategory, 'title': title, 'url': url, 'lang': lang, 'fps': 0, 'desc': desc})
            self.addDir(params)

        if nextPage:
            params = dict(cItem)
            params.update({'title': _('Next page'), 'page': page + 1})
            self.addDir(params)

    def getSubtitlesList(self, cItem):
        printDBG("SubtitlesGrProvider.getSubtitlesList")

        url = cItem['url']
        sts, data = self.getPage(url)
        if not sts:
            return

        imdbid = self.cm.ph.getSearchGroups(data, '''/tt([0-9]+?)[^0-9]''')[0]
        subId = self.cm.ph.getSearchGroups(url + '/', '''/([0-9]+?)/''')[0]
        fps = cItem.get('fps', 0)

        url = self.cm.ph.getSearchGroups(data, '''href="(https?://[^"]+?getp\.php[^"]+?)"''')[0]
        if not self.cm.isValidUrl(url):
            return

        urlParams = dict(self.defaultParams)
        tmpDIR = self.downloadAndUnpack(url, urlParams)
        if None == tmpDIR:
            return

        cItem = dict(cItem)
        cItem.update({'category': '', 'path': tmpDIR + '/subs', 'fps': fps, 'imdbid': imdbid, 'sub_id': subId})
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
        if name == None:
            self.listSubItems(self.currItem, 'list_subtitles')
        elif category == 'list_subtitles':
            self.getSubtitlesList(self.currItem)

        CBaseSubProviderClass.endHandleService(self, index, refresh)


class IPTVSubProvider(CSubProviderBase):

    def __init__(self, params={}):
        CSubProviderBase.__init__(self, SubtitlesGrProvider(params))
