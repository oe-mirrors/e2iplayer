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
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import hex_md5
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


class TitlovicomProvider(CBaseSubProviderClass):

    def __init__(self, params={}):
        params['cookie'] = 'titlovicom.cookie'
        CBaseSubProviderClass.__init__(self, params)

        self.LANGUAGE_CACHE = ['hr', 'ba', 'mk', 'si', 'rs']
        self.BASE_URL_CACHE = {'hr': 'titlovi', 'ba': 'prijevodi', 'mk': 'prevodi', 'si': 'podnapisi', 'rs': 'prevodi'}
        self.pageLang = 'hr'
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/64.0.3282.168 Safari/537.36'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'Referer': self.getMainUrl(), 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Encoding': 'gzip, deflate'}

        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.dInfo = params['discover_info']

    def getBaseGet(self):
        return self.BASE_URL_CACHE.get(self.pageLang, '') + '/'

    def getMainUrl(self):
        lang = GetDefaultLang()
        if lang in self.LANGUAGE_CACHE:
            self.pageLang = lang
        if self.pageLang == 'hr':
            return 'https://titlovi.com/'
        return 'https://%s.titlovi.com/' % self.pageLang

    def getMoviesTitles(self, cItem, nextCategory):
        printDBG("TitlovicomProvider.getMoviesTitles")
        sts, tab = self.imdbGetMoviesByTitle(self.params['confirmed_title'])
        if not sts:
            return
        printDBG(tab)
        for item in tab:
            params = dict(cItem)
            params.update(item) # item = {'title', 'imdbid'}
            params.update({'category': nextCategory})
            self.addDir(params)

    def getType(self, cItem):
        printDBG("TitlovicomProvider.getType")
        imdbid = cItem['imdbid']
        title = cItem['title']
        type = self.getTypeFromThemoviedb(imdbid, title)
        if type == 'series':
            promSeason = self.dInfo.get('season')
            sts, tab = self.imdbGetSeasons(imdbid, promSeason)
            if not sts:
                return
            for item in tab:
                params = dict(cItem)
                params.update({'category': 'get_episodes', 'item_title': cItem['title'], 'season': item, 'title': _('Season %s') % item})
                self.addDir(params)
        elif type == 'movie':
            self.getLanguages(cItem, 'get_search')

    def getEpisodes(self, cItem, nextCategory):
        printDBG("TitlovicomProvider.getEpisodes")
        imdbid = cItem['imdbid']
        itemTitle = cItem['item_title']
        season = cItem['season']

        promEpisode = self.dInfo.get('episode')
        sts, tab = self.imdbGetEpisodesForSeason(imdbid, season, promEpisode)
        if not sts:
            return
        for item in tab:
            params = dict(cItem)
            params.update(item) # item = "episode_title", "episode", "eimdbid"
            title = 's{0}e{1} {2}'.format(str(season).zfill(2), str(item['episode']).zfill(2), item['episode_title'])
            params.update({'category': nextCategory, 'title': title})
            self.addDir(params)

    def getLanguages(self, cItem, nextCategory):
        printDBG("OpenSubOrgProvider.getEpisodes")

        url = self.getFullUrl(self.getBaseGet())
        sts, data = self.cm.getPage(url)
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenMarkers(data, 'name="jezikSelectedValues"', '</select>', False)[1]
        data = re.compile('<option[^>]+?value="([^"]+?)"[^>]*>([^<]+?)</option>').findall(data)

        if len(data):
            params = dict(cItem)
            params.update({'title': _('All'), 'search_lang': ''})
            params.update({'category': nextCategory})
            self.addDir(params)

        for item in data:
            params = dict(cItem)
            params.update({'title': item[1], 'search_lang': item[0]})
            params.update({'category': nextCategory})
            self.addDir(params)

    def getSearchList(self, cItem, nextCategory):
        printDBG("TitlovicomProvider.getSearchList")

        page = cItem.get('page', 1)

        post_data = None
        if page == 1:
            url = self.getFullUrl(self.getBaseGet())
            sts, data = self.cm.getPage(url, self.defaultParams)
            if not sts:
                return
            searchName = ''
            post_data = {}

            data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="advanced_search hidden">', '</form>', False)[1]
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<input', '/>')
            for item in data:
                name = self.cm.ph.getSearchGroups(item, 'name="([^"]+?)"')[0]
                value = self.cm.ph.getSearchGroups(item, 'value="([^"]+?)"')[0]
                if 'Token' in name:
                    post_data[name] = value
                if searchName == '' and 'type="text"' in item:
                    searchName = name

            year = cItem.get('year', '')
            if '' == year:
                year = -1

            if 'season' in cItem and 'episode' in cItem:
                post_data['t'] = '2' # type
                post_data['g'] = -1  # year
                post_data['s'] = cItem['season']
                post_data['e'] = cItem['episode']
            else:
                post_data['t'] = '0'  # type
                post_data['g'] = year # year

            title = self.imdbGetOrginalByTitle(cItem['imdbid'])[1].get('title', cItem['base_title'])
            post_data[searchName] = title
            post_data['sort'] = 4
            post_data['korisnik'] = ''

            if cItem.get('search_lang', '') != '':
                post_data['jezikSelectedValues'] = cItem['search_lang']
        else:
            url = cItem.get('next_page_url', '')

        sts, data = self.cm.getPage(url, self.defaultParams, post_data)
        if not sts:
            return

        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="titlovi">', '</section>', False)[1].split('<div class="paging">')
        if 2 == len(tmp):
            nextPage = self.cm.ph.getSearchGroups(tmp[1], '<a[^>]+?href="([^"]+?)"[^>]*?>%s<' % (page + 1))[0]
        else:
            nextPage = ''

        data = tmp[0]
        del tmp

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<h3', '</div></li>')
        for item in data:
            descTab = []
            url = self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0]
            if url == '':
                continue
            title = item.split('<h5>')[0] #self.cm.ph.getDataBeetwenMarkers(item, '<h4', '</h4>')[1]
            lang = self.cm.ph.getSearchGroups(item, 'flags/([a-z]{2})')[0]

            # lang name
            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<span class="lang', '</span>')[1])
            if desc != '':
                descTab.append(desc)

            # release
            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<span class="release">', '</span>')[1])
            if desc != '':
                descTab.append(desc)

            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '</ul>', '</li>')[1])
            if desc != '':
                descTab.append(desc)

            params = dict(cItem)
            params.update({'category': nextCategory, 'url': self.getFullUrl(url), 'title': self.cleanHtmlStr(title), 'lang': lang, 'desc': self.cleanHtmlStr(item)}) #'[/br]'.join(descTab)
            params['title'] = ('[%s] ' % lang) + params['title']
            self.addDir(params)

        if nextPage != '':
            params = dict(cItem)
            params.update({'title': _('Next page'), 'page': page + 1, 'next_page_url': self.getFullUrl(nextPage)})
            self.addDir(params)

    def getSubtitlesList(self, cItem):
        printDBG("TitlovicomProvider.getSubtitlesList")

        sts, data = self.cm.getPage(cItem['url'], self.defaultParams)
        if not sts:
            return

        imdbid = self.cm.ph.getSearchGroups(data, '/title/(tt[0-9]+?)[^0-9]')[0]
        subId = self.cm.ph.getSearchGroups(data, 'mediaid=([0-9]+?)[^0-9]')[0]
        url = self.getFullUrl(self.cm.ph.getSearchGroups(data, 'href="([^"]*?/download[^"]+?mediaid=[^"]+?)"')[0])

        try:
            fps = float(self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, 'class="fps">', 'FPS', False)[1].upper()))
        except Exception:
            fps = 0
            printExc()

        urlParams = dict(self.defaultParams)
        tmpDIR = self.downloadAndUnpack(url, urlParams)
        if None == tmpDIR:
            return

        cItem = dict(cItem)
        cItem.update({'category': '', 'path': tmpDIR, 'fps': fps, 'imdbid': imdbid, 'sub_id': subId})
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
            self.getMoviesTitles({'name': 'category'}, 'get_type')
        elif category == 'get_type':
            # take actions depending on the type
            self.getType(self.currItem)
        elif category == 'get_episodes':
            self.getEpisodes(self.currItem, 'get_languages')
        elif category == 'get_languages':
            self.getLanguages(self.currItem, 'get_search')
        elif category == 'get_search':
            self.getSearchList(self.currItem, 'get_subtitles')
        elif category == 'get_subtitles':
            self.getSubtitlesList(self.currItem)

        CBaseSubProviderClass.endHandleService(self, index, refresh)


class IPTVSubProvider(CSubProviderBase):

    def __init__(self, params={}):
        CSubProviderBase.__init__(self, TitlovicomProvider(params))
