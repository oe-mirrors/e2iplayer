# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CDisplayListItem, RetHost
from Plugins.Extensions.IPTVPlayer.components.isubprovider import CSubProviderBase, CBaseSubProviderClass

from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetDefaultLang, GetCookieDir, byteify, \
                                                          RemoveDisallowedFilenameChars, GetSubtitlesDir, GetTmpDir, rm, \
                                                          MapUcharEncoding, GetPolishSubEncoding, IsSubtitlesParserExtensionCanBeUsed, \
                                                          ReadTextFile
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


class NapiProjektProvider(CBaseSubProviderClass):

    def __init__(self, params={}):
        self.MAIN_URL = 'http://www.napiprojekt.pl/'
        self.USER_AGENT = 'DMnapi 13.1.30'
        self.HTTP_HEADER = {'User-Agent': 'Mozilla/5.0', 'Referer': self.MAIN_URL, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Encoding': 'gzip, deflate'}
        self.AJAX_HEADER = {'User-Agent': 'Mozilla/5.0', 'Referer': self.MAIN_URL, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Encoding': 'gzip, deflate', 'X-Requested-With': 'XMLHttpRequest'}

        params['cookie'] = 'napiprojektpl.cookie'
        CBaseSubProviderClass.__init__(self, params)

        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.defaultAjaxParams = {'header': self.AJAX_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.dInfo = params['discover_info']

        self.kaindTab = [{'title': 'Film & Serial', 'kind': 0},
                         {'title': 'Serial', 'kind': 1},
                         {'title': 'Film', 'kind': 2}]

    def sortSubtitlesByDurationMatch(self):
        # we need duration to sort
        movieDurationSec = self.params.get('duration_sec', 0)
        if movieDurationSec <= 0:
            return

        # get only subtitles items from current list
        hasDuration = False
        subList = []
        for item in self.currList:
            if 'subtitle' == item.get('type', ''):
                subList.append(item)
                if 'duration_sec' in item:
                    hasDuration = True

        # if there is no subtitle with duration available
        # we will skip sort
        if not hasDuration:
            return
        subList.sort(key=lambda item: abs(item.get('duration_sec', 0) - movieDurationSec))

        for idx in range(len(self.currList)):
            if 'subtitle' == self.currList[idx].get('type', ''):
                self.currList[idx] = subList.pop(0)

    def listKinds(self, cItem, nextCategoryMovie):
        printDBG("NapiProjektProvider.listKinds")
        for item in self.kaindTab:
            params = dict(cItem)
            params.update(item)
            params['category'] = nextCategoryMovie
            self.addDir(params)

    def getMoviesList(self, cItem, nextCategoryMovie):
        printDBG("NapiProjektProvider.getMoviesList")
        title = urllib.quote_plus(self.params['confirmed_title'])
        url = self.getFullUrl('/ajax/search_catalog.php')

        post_data = {'queryString': title, 'queryKind': cItem.get('kind', 0), 'queryYear': '', 'associate': ''}
        sts, data = self.cm.getPage(url, self.defaultAjaxParams, post_data)
        if not sts:
            return

        data = data.split('<div class="greyBoxCatcher">')
        if len(data):
            del data[0]

        for item in data:
            imdbid = self.cm.ph.getSearchGroups(item, 'imdb\.com/title/(tt[0-9]+?)[^0-9]')[0]

            item = item.split('<div class="movieBottom">')[0]
            subId = self.cm.ph.getSearchGroups(item, 'id="([0-9]+?)"')[0]
            title = self.cm.ph.getDataBeetwenMarkers(item, '<h3', '</h3>')[1]
            url = self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0]
            if '' == url:
                continue

            desc = self.cm.ph.getDataBeetwenMarkers(item, '<p', '</p>')[1]
            params = dict(cItem)
            params.update({'category': nextCategoryMovie, 'title': self.cleanHtmlStr(title), 'url': self.getFullUrl(url), 'sub_id': subId, 'imdbid': imdbid, 'desc': self.cleanHtmlStr(desc)})
            self.addDir(params)

    def exploreSubtitlesItem(self, cItem):
        printDBG("NapiProjektProvider.exploreSubtitlesItem")

        url = cItem['url']
        sts, data = self.cm.getPage(url, self.defaultParams)
        if not sts:
            return

        sts, data = self.cm.ph.getDataBeetwenMarkers(data, '-&gt;', '>napisy<')
        if not sts:
            return
        url = self.getFullUrl(self.cm.ph.getSearchGroups(data, 'href="([^"]+?)"')[0])
        if '' == url:
            return
        sts, data = self.cm.getPage(url, self.defaultParams)
        if not sts:
            return

        # if series get seasons
        tmp = self.cm.ph.getDataBeetwenMarkers(data, 'sezonySubtitlesList', '</script>', False)[1]
        movieId = self.cm.ph.getSearchGroups(tmp, "'movieID':([0-9]+?)[^0-9]")[0]
        urlPattern = self.cm.ph.getDataBeetwenMarkers(tmp, 'window.location.href=', ';', False)[1].replace("'", "").replace('"', '').strip()
        urlPattern = urlPattern.split('tytul=')
        if 2 == len(urlPattern):
            urlPattern = urlPattern[0] + 'tytul=' + urllib.quote(urlPattern[1])
        else:
            urlPattern = ''

        if '' != movieId and '' != urlPattern:
            tab = []
            promItem = None
            promSeason = str(self.dInfo.get('season'))
            tmp = self.cm.ph.getDataBeetwenMarkers(data, '<select id="sezonySubtitlesList" name="sezon">', '</select>', False)[1]
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<option>', '</option>', False)
            for item in tmp:
                try:
                    season = int(item.strip())
                except Exception:
                    continue
                params = {'category': 'get_episodes', 'title': str(season), 'season': str(season), 'movie_id': movieId, 'url_pattern': urlPattern}
                if None == promItem and promSeason == str(season):
                    promItem = params
                else:
                    tab.append(params)
            if None != promItem:
                tab.insert(0, promItem)
            if len(tab):
                for item in tab:
                    params = dict(cItem)
                    params.update(item)
                    self.addDir(params)
                return

        # if not series then
        cItem = dict(cItem)
        cItem.update({'category': 'list_subtitles', 'url': url})
        self.listSubtitles(cItem)

    def listSubtitles(self, cItem):
        printDBG("NapiProjektProvider.listSubtitles")

        page = cItem.get('page', 1)
        sts, data = self.cm.getPage(cItem['url'], self.defaultParams)
        if not sts:
            return

        nextPage = self.cm.ph.getSearchGroups(data, '"(napisy%s,[^"]+?)"' % (page + 1))[0]
        data = self.cm.ph.getDataBeetwenMarkers(data, '<tbody>', '</tbody>')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<tr', '</tr>')
        for item in data:
            desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'title="([^"]+?)"')[0])
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(item, '<td', '</td>')
            if len(tmp) != 7:
                continue
            subId = self.cm.ph.getSearchGroups(tmp[0], 'href="napiprojekt\:([0-9a-f]+?)"')[0]
            if '' == subId:
                continue
            title = self.cleanHtmlStr(tmp[0])

            try:
                fps = float(tmp[2].strip())
            except Exception:
                fps = 0

            duration = self.cleanHtmlStr(tmp[3])
            durationSecTab = self.cm.ph.getSearchGroups('|%s|' % duration, '[^0-9]([0-9]{2}):([0-9]{2}):([0-9]{2})[^0-9]', 3)
            if '' not in durationSecTab:
                durationSec = int(durationSecTab[0]) * 3600 + int(durationSecTab[1]) * 60 + int(durationSecTab[2])
            else:
                durationSec = 0

            params = dict(cItem)
            params.update({'title': _('Season') + ' ' + title + ' ' + duration, 'duration_sec': durationSec, 'fps': fps, 'sub_id': subId, 'lang': 'pl', 'desc': desc, 'size': tmp[1].strip(), 'translator': item[4].strip(), 'added': item[5], 'downloaded': item[6]})
            self.addSubtitle(params)
        self.sortSubtitlesByDurationMatch()

        if '' != nextPage:
            params = dict(cItem)
            params.update({'title': _('Next page'), 'url': self.getFullUrl(nextPage), 'page': page + 1})
            self.addDir(params)

    def getEpisodes(self, cItem, nextCategory):
        printDBG("NapiProjektProvider.getEpisodes")

        url = self.getFullUrl('/ajax/search_episodes.php')

        post_data = {'sezon': cItem['season'], 'movieID': cItem['movie_id']}
        sts, data = self.cm.getPage(url, self.defaultAjaxParams, post_data)
        if not sts:
            return

        urlPattern = cItem['url_pattern']
        tab = []
        promItem = None
        promEpisode = str(self.dInfo.get('episode'))
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<option>', '</option>', False)
        for item in data:
            try:
                episode = int(item.strip())
            except Exception:
                continue
            params = {'category': nextCategory, 'title': _('Episode') + ' ' + str(episode), 'episode': str(episode), 'url': self.getFullUrl(urlPattern.replace('+sezon+', str(cItem['season'])).replace('+odcinek+', str(episode)))}
            if None == promItem and promEpisode == str(episode):
                promItem = params
            else:
                tab.append(params)
        if None != promItem:
            tab.insert(0, promItem)
        if len(tab):
            for item in tab:
                params = dict(cItem)
                params.update(item)
                self.addDir(params)

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
        printDBG("NapiProjektProvider.downloadSubtitleFile")
        retData = {}
        title = cItem['title']
        lang = cItem.get('lang', 'pl')
        subId = cItem['sub_id']
        imdbid = cItem['imdbid']
        fps = cItem.get('fps', 0)

        post_data = {"mode": "32770",
                     "client": "pynapi",
                     "client_ver": "0.1",
                     "VideoFileInfoID": subId}

        url = self.getFullUrl('api/api-napiprojekt3.php')
        sts, data = self.cm.getPage(url, self.defaultParams, post_data)
        if not sts:
            return retData

        fps = self.cm.ph.getDataBeetwenMarkers(data, '<fps>', '</fps>', False)[1]
        try:
            fps = float(fps.strip())
        except Exception:
            fps = 0

        post_data = {"downloaded_subtitles_id": subId,
                     "mode": "1",
                     "client": "pynapi",
                     "client_ver": "0.1",
                     "downloaded_subtitles_lang": lang.upper(),
                     "downloaded_subtitles_txt": "1"}

        url = self.getFullUrl('api/api-napiprojekt3.php')
        sts, data = self.cm.getPage(url, self.defaultParams, post_data)
        if not sts:
            return retData

        data = self.cm.ph.getDataBeetwenMarkers(data, '<content><![CDATA[', ']]></content>', False)[1]
        try:
            data = base64.b64decode(data)
            if IsSubtitlesParserExtensionCanBeUsed():
                from Plugins.Extensions.IPTVPlayer.libs.iptvsubparser import _subparser as subparser
                subsObj = subparser.parse(data, 0, False, False)
                typeExtMap = {'microdvd': 'sub', 'subrip': 'srt', 'subviewer': 'sub', 'ssa1': 'ssa', 'ssa2-4': 'ssa',
                              'ass': 'ssa', 'vplayer': 'txt', 'sami': 'smi', 'mpl2': 'mpl', 'aqt': 'aqt', 'pjs': 'pjs',
                              'mpsub': 'sub', 'jacosub': 'jss', 'psb': 'psb', 'realtext': 'rt',
                              'dks': 'dks', 'subviewer1': 'sub', 'text/vtt': 'vtt', 'sbv': 'sbv'}
                ext = typeExtMap.get(subsObj['type'], '')
                if ext == '':
                    SetIPTVPlayerLastHostError(_('Unknown subtitle parser for format "%s".') % subsObj['type'])
                    return retData
                tmpFile = GetTmpDir(self.TMP_FILE_NAME)
                if not self.writeFile(tmpFile, data):
                    return retData
                fileName = self._getFileName(title, lang, subId, imdbid, fps, ext)
                fileName = GetSubtitlesDir(fileName)
                if not self.converFileToUtf8(tmpFile, fileName):
                    rm(tmpFile)
                    return retData
                retData = {'title': title, 'path': fileName, 'lang': lang, 'imdbid': imdbid, 'sub_id': subId}
        except Exception:
            printExc()
            return retData

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
            self.listKinds({'name': 'category'}, 'get_movies_list')
        elif category == 'get_movies_list':
            self.getMoviesList(self.currItem, 'explore_sub_item')
        elif category == 'explore_sub_item':
            self.exploreSubtitlesItem(self.currItem)
        elif category == 'get_episodes':
            self.getEpisodes(self.currItem, 'list_subtitles')
        elif category == 'list_subtitles':
            self.listSubtitles(self.currItem)

        CBaseSubProviderClass.endHandleService(self, index, refresh)


class IPTVSubProvider(CSubProviderBase):

    def __init__(self, params={}):
        CSubProviderBase.__init__(self, NapiProjektProvider(params))
