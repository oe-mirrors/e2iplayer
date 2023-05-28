# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.isubprovider import CSubProviderBase, CBaseSubProviderClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetDefaultLang, RemoveDisallowedFilenameChars, GetSubtitlesDir, rm
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus, urllib_urlencode
from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import urljoin
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_binary
###################################################
# FOREIGN import
###################################################
import re
try:
    import json
except Exception:
    import simplejson as json
from hashlib import md5
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


class OpenSubtitles(CBaseSubProviderClass):

    def __init__(self, params={}):
        self.MAIN_URL = 'https://www.opensubtitles.org/'
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3359.139 Safari/537.36'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'Referer': self.MAIN_URL, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Encoding': 'gzip, deflate'}

        params['cookie'] = 'opensubtitlesorg2.cookie'
        CBaseSubProviderClass.__init__(self, params)

        self.defaultParams = {'header': self.HTTP_HEADER, 'with_metadata': True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.languages = []

        self.dInfo = params['discover_info']
        self.searchTypes = [{'title': _('Search Movies and TV Series')}, {'title': _('Search only in Movies'), 'search_only_movies': 'on'}, {'title': _('Search only in TV Series'), 'search_only_tv_series': 'on'}]
        self.episodesCache = {}
        self.logedIn = None
        self.searchURL = ""

        self.wasInformedAboutReCaptcha = False

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)

        def _getFullUrl(url):
            if self.cm.isValidUrl(url):
                return url
            else:
                return urljoin(baseUrl, url)

        addParams['cloudflare_params'] = {'domain': self.cm.getBaseUrl(baseUrl, domainOnly=True), 'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT, 'full_url_handle': _getFullUrl}
        sts, data = self.cm.getPageCFProtection(baseUrl, addParams, post_data)
        try:
            if not self.wasInformedAboutReCaptcha and self.cm.meta['status_code'] == 429:
                self.sessionEx.open(MessageBox, _('%s has been protected with google recaptcha v2. You can try to use API version.') % ('https://www.opensubtitles.org/'), type=MessageBox.TYPE_INFO, timeout=10)
                self.wasInformedAboutReCaptcha = True
        except Exception:
            printExc()
        return sts, data

    def initSubProvider(self, cItem):
        printDBG("OpenSubtitles.initSubProvider")
        self.logedIn = False

        login = config.plugins.iptvplayer.opensuborg_login.value
        passwd = config.plugins.iptvplayer.opensuborg_password.value
        currentHash = md5(ensure_binary('\n\n--\n\n'.join((login, passwd)))).hexdigest()
        cokieFile = self.COOKIE_FILE + '.hash'
        try:
            with open(cokieFile, 'r') as f:
                prevHash = f.read()
        except Exception:
            prevHash = ''
            printExc()

        try:
            with open(cokieFile, 'w') as f:
                f.write(currentHash)
        except Exception:
            prevHash = ''
            printExc()

        # select site language
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return

        logoutUrl = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<a[^>]+?href=['"]([^"^']+?logout)['"]''')[0])

        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'lang-selector'), ('</ul', '>'))[1]
        printDBG(">>>\n%s\n<<" % tmp)
        lang = GetDefaultLang()
        url = self.getFullUrl(self.cm.ph.getSearchGroups(tmp, 'href="([^"]+?setlang\-%s[^"]*?)"' % lang)[0])
        printDBG(">> LANG URL: " + url)
        if self.cm.isValidUrl(url):
            sts, data = self.getPage(url)
            if not sts:
                return

        printDBG(self.cm.ph.getAllItemsBeetwenMarkers(data, '<form', '>'))
        self.searchURL = self.cm.ph.getSearchGroups(data, '<form[^>]+?"searchform"[^>]+?action="([^"]+?)"')[0]
        printDBG(">> SEARCH URL: " + self.searchURL)

        # fill language cache
        self.languages = []
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<select name="SubLanguageID"', '</select>')[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<option', '</option>')
        for item in tmp:
            title = self.cleanHtmlStr(item)
            subLanguageID = self.cm.ph.getSearchGroups(item, '''value=['"]([^"^']+?)['"]''')[0]
            self.languages.append({'title': title, 'sub_language_id': subLanguageID})

        # login user
        if login != '' and passwd != '':
            if currentHash != prevHash:
                errMsg = _('Failed to connect to server "%s".') % self.getMainUrl()

                if logoutUrl != '':
                    sts, data = self.getPage(logoutUrl)
                    if not sts:
                        self.sessionEx.open(MessageBox, errMsg, type=MessageBox.TYPE_INFO, timeout=5)
                        return

                url = self.getFullUrl(self.cm.ph.getSearchGroups(data, '<form[^>]+?name="loginform"[^>]+?action="([^"]+?)"')[0])
                sts, data = self.getPage(url)
                if not sts:
                    self.sessionEx.open(MessageBox, errMsg, type=MessageBox.TYPE_INFO, timeout=5)
                    return

                data = self.cm.ph.getDataBeetwenMarkers(data, '<form', '</form>')[1]
                loginUrl = self.getFullUrl(self.cm.ph.getSearchGroups(data, 'action="([^"]+?)"')[0])
                data = re.compile('<input[^>]+?name="([^"]+?)"[^>]+?value="([^"]+?)"').findall(data)
                post_data = {}
                for item in data:
                    post_data[item[0]] = item[1]
                post_data.update({'user': login, 'password': passwd, 'remember': 'on'})

                sts, data = self.getPage(loginUrl, post_data=post_data)
                if not sts:
                    self.sessionEx.open(MessageBox, errMsg, type=MessageBox.TYPE_INFO, timeout=5)
                elif 'logout' not in data:
                    self.sessionEx.open(MessageBox, _('Failed to log in user "%s". Please check your login and password.') % login, type=MessageBox.TYPE_INFO, timeout=5)
                    self.logedIn = False
                else:
                    if self.searchURL == '':
                        self.searchURL = self.cm.ph.getSearchGroups(data, '<form[^>]+?"searchform"[^>]+?action="([^"]+?)"')[0]
                        printDBG(">> SEARCH URL: " + self.searchURL)
                    self.logedIn = True
        elif logoutUrl != '':
            sts, data = self.getPage(logoutUrl)
            if not sts:
                self.sessionEx.open(MessageBox, errMsg, type=MessageBox.TYPE_INFO, timeout=5)
                return

    def listLanguages(self, cItem, nextCategory):
        printDBG("OpenSubtitles.listLanguages")
        cItem = dict(cItem)
        cItem['category'] = nextCategory
        self.listsTab(self.languages, cItem)

    def listSearchTypes(self, cItem, nextCategory):
        printDBG("OpenSubtitles.listLanguages")
        cItem = dict(cItem)
        cItem['category'] = nextCategory
        self.listsTab(self.searchTypes, cItem)

    def searchSubtitles(self, cItem, nextCategory):
        printDBG("OpenSubtitles.searchSubtitles")
        url = cItem.get('url', '')
        if url == '':
            query = {'id': 8, 'action': 'search', 'SubSumCD': '', 'Genre': '', 'MovieByteSize': '', 'MovieLanguage': '', 'MovieImdbRatingSign': '1', 'MovieImdbRating': '', 'MovieCountry': '', 'MovieYearSign': '1', 'MovieYear': '', 'MovieFPS': '', 'SubFormat': '', 'SubAddDate': '', 'Uploader': '', 'IDUser': '', 'Translator': '', 'IMDBID': '', 'MovieHash': '', 'IDMovie': ''}
            keywords = urllib_quote_plus(self.params['confirmed_title'])
            subLanguageID = cItem.get('sub_language_id', '')
            searchOnlyTVSeries = cItem.get('search_only_tv_series', '')
            searchOnlyMovies = cItem.get('search_only_movies', '')

            if 'on' == searchOnlyTVSeries:
                season = self.dInfo.get('season', None)
                episode = self.dInfo.get('episode', None)
            else:
                season = None
                episode = None

            if season == None:
                season = ''
            if episode == None:
                episode = ''

            query['MovieName'] = keywords
            query['SubLanguageID'] = subLanguageID
            if 'on' == searchOnlyTVSeries:
                query['SearchOnlyTVSeries'] = searchOnlyTVSeries
            if 'on' == searchOnlyMovies:
                query['SearchOnlyMovies'] = searchOnlyMovies
            query['Season'] = season
            query['Episode'] = episode

            if self.searchURL != '':
                searchURL = self.searchURL
            else:
                searchURL = '/search2'
            url = self.getFullUrl(searchURL) + '?' + urllib_urlencode(query)
        else:
            url = cItem['url']

        sts, data = self.getPage(url)
        if not sts:
            return

        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<table id="search_results"', '</tbody>')[1]
        m1 = '<tr id="name'
        m2 = '<tr onclick'
        m3 = '<span id="season'

        cItem = dict(cItem)
        cItem['url'] = url

        if m1 in tmp:
            self.listSearchItems(cItem, cItem['category'], data)
        elif m2 in tmp:
            self.listDownloadItems(cItem, nextCategory, data)
        elif m3 in tmp:
            self.listSeasonsItems(cItem, 'list_episodes', data)
        else:
            self.getSubtitlesList(cItem, 'list_sub_in_packed_file')

    def listSearchItems(self, cItem, nextCategory, data=None):
        printDBG("OpenSubtitles.listSearchItems")
        if data == None:
            sts, data = self.getPage(cItem['url'])
            if not sts:
                return
        page = cItem.get('page', 1)
        nextPage = self.getFullUrl(self.cm.ph.getSearchGroups(data, '<link[^>]+?rel="next"[^>]+?href="([^"]+?)"')[0])

        data = self.cm.ph.getDataBeetwenMarkers(data, '<tr id="name', '</tbody>')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<tr id="name', '</tr>')
        for item in data:
            url = self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0]
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<td', '</a>')[1])
            imdbid = self.cm.ph.getSearchGroups(item, '''/tt([0-9]+?)[^0-9]''')[0]

            descTab = []
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(item, '<td', '</td>')
            for t in tmp:
                t = t.split('<a rel="nofollow"')[0]
                t = self.cleanHtmlStr(t)
                if t != '':
                    descTab.append(t)
            params = dict(cItem)
            params.update({'category': nextCategory, 'title': title, 'imdbid': imdbid, 'url': self.getFullUrl(url), 'desc': ' | '.join(descTab)})
            self.addDir(params)

        if self.cm.isValidUrl(nextPage):
            params = dict(cItem)
            params.update({'title': _('Next page'), 'page': page + 1})
            self.addDir(params)

    def listDownloadItems(self, cItem, nextCategory, data=None):
        printDBG("OpenSubtitles.listDownloadItems")
        if data == None:
            sts, data = self.getPage(cItem['url'])
            if not sts:
                return
        page = cItem.get('page', 1)
        nextPage = self.getFullUrl(self.cm.ph.getSearchGroups(data, '<link[^>]+?rel="next"[^>]+?href="([^"]+?)"')[0])

        data = self.cm.ph.getDataBeetwenMarkers(data, '<tr onclick', '</tbody>')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<tr onclick', '</tr>')
        for item in data:
            url = self.cm.ph.getSearchGroups(item, 'href="([^"]+?/sub/[^"]+?)"')[0]
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<td', '</td>')[1].split('<a rel="nofollow"')[0])
            imdbid = self.cm.ph.getSearchGroups(item, '''/tt([0-9]+?)[^0-9]''')[0]
            lang = self.cm.ph.getSearchGroups(item, '''class="flag\s*([^"]+?)"''')[0]

            descTab = []
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(item, '<td', '</td>')
            if len(tmp) > 3:
                fps = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(tmp[3], '<span', '</span>')[1])
            else:
                fps = '0'
            if len(tmp) > 4:
                format = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(tmp[4], '<span', '</span>')[1])
            else:
                format = '0'

            for t in tmp:
                t = t.split('<a rel="nofollow"')[0]
                t = self.cleanHtmlStr(t)
                if t != '':
                    descTab.append(t)
            params = dict(cItem)
            params.update({'category': nextCategory, 'lang': lang, 'fps': fps, 'format': format, 'title': '[%s | %s] %s' % (lang, format, title), 'imdbid': imdbid, 'url': self.getFullUrl(url), 'desc': ' | '.join(descTab)})
            self.addDir(params)

        if self.cm.isValidUrl(nextPage):
            params = dict(cItem)
            params.update({'title': _('Next page'), 'page': page + 1})
            self.addDir(params)

    def listSeasonsItems(self, cItem, nextCategory, data=None):
        printDBG("OpenSubtitles.listSeasonsItems")
        self.episodesCache = {}

        if data == None:
            sts, data = self.getPage(cItem['url'])
            if not sts:
                return

        data = self.cm.ph.getDataBeetwenMarkers(data, '<table id="search_results"', '</tbody>')[1]
        data = data.split('<span id="season')
        if len(data):
            del data[0]
        for seasonItem in data:
            seasonTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(seasonItem, '<b', '</b>')[1])
            episodesTab = []
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(seasonItem, '<tr itemprop="episode"', '</tr>')
            for item in tmp:
                td = self.cm.ph.getAllItemsBeetwenMarkers(item, '<td', '</td>')
                title = self.cleanHtmlStr(td[0])
                desc = self.cleanHtmlStr(item)
                url = self.cm.ph.getSearchGroups(td[0], 'href="([^"]+?)"')[0]
                if url == '':
                    continue
                imdbid = self.cm.ph.getSearchGroups(item, '''/tt([0-9]+?)[^0-9]''')[0]
                params = {'title': title, 'imdbid': imdbid, 'url': self.getFullUrl(url), 'desc': desc}

                numOfSubs = self.cleanHtmlStr(td[1])
                if numOfSubs == '1':
                    params['category'] = 'list_subtitles'
                episodesTab.append(params)

            if len(episodesTab):
                self.episodesCache[seasonTitle] = episodesTab
                params = dict(cItem)
                params.update({'category': nextCategory, 'title': seasonTitle, 'season_key': seasonTitle})
                self.addDir(params)

    def listEpisodesItems(self, cItem, nextCategory):
        printDBG("OpenSubtitles.listSeasonsItems")

        params = dict(cItem)
        params['category'] = nextCategory
        seasonKey = cItem.get('season_key', '')
        tab = self.episodesCache.get(seasonKey, [])
        self.listsTab(tab, params)

    def getSubtitlesList(self, cItem, nextCategory):
        printDBG("OpenSubtitles.getSubtitlesList [%s]" % cItem)

        url = cItem['url']
        downloadUrl = ''
        data = ''

        def _getDownloadUrl(url):
            urlParams = dict(self.defaultParams)
            urlParams['max_data_size'] = 0

            sts = self.getPage(url, urlParams)[0]
            if not sts:
                return ''
            fileName = self.cm.meta.get('content-disposition', '')
            fileName = self.cm.ph.getSearchGroups(fileName.lower(), '''filename=['"]([^'^"]+?)['"]''')[0]
            if fileName.endswith('.zip') or fileName.endswith('.rar'):
                return url

            return ''

        downloadUrl = _getDownloadUrl(url)
        if downloadUrl == '':
            sts, data = self.getPage(url)
            if not sts:
                return
            url = self.getFullUrl(self.cm.ph.getSearchGroups(data, 'href="([^"]*?/subtitleserve/sub/[^"]+?)"')[0])
            if url == '':
                url = self.getFullUrl(self.cm.ph.getSearchGroups(data, 'href="([^"]*?/download/sub/[^"]+?)"')[0])
            if not self.cm.isValidUrl(url):
                return

        imdbid = cItem.get('imdbid', '')
        subId = url.split('/')[-2]
        fps = cItem.get('fps', 0)

        if not self.logedIn and downloadUrl == '' and url != cItem['url']:
            downloadUrl = _getDownloadUrl(url)
            if downloadUrl == '':
                sts, data = self.getPage(url)
                if not sts:
                    return
                downloadUrl = self.cm.ph.getSearchGroups(data, '''URL=(https?://[^"^'^\s]+?)["'\s]''')[0]

        if not self.cm.isValidUrl(downloadUrl):
            return

        urlParams = dict(self.defaultParams)
        tmpDIR = self.downloadAndUnpack(downloadUrl, urlParams)
        if None == tmpDIR:
            return

        cItem = dict(cItem)
        cItem.update({'category': '', 'path': tmpDIR, 'fps': fps, 'imdbid': imdbid, 'sub_id': subId})
        self.listSupportedFilesFromPath(cItem, self.getSupportedFormats(all=True))

    def listSubsInPackedFile(self, cItem, nextCategory):
        printDBG("OpenSubtitles.listSubsInPackedFile")
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
        subId = cItem['sub_id']
        imdbid = cItem['imdbid']
        inFilePath = cItem['file_path']
        ext = cItem.get('ext', 'srt')
        fps = cItem.get('fps', 0)

        outFileName = self._getFileName(title, lang, subId, imdbid, fps, ext)
        outFileName = GetSubtitlesDir(outFileName)

        printDBG(">>")
        printDBG(inFilePath)
        printDBG(outFileName)
        printDBG("<<")

        if self.converFileToUtf8(inFilePath, outFileName, lang):
            retData = {'title': title, 'path': outFileName, 'lang': lang, 'imdbid': imdbid, 'sub_id': subId, 'fps': fps}

        return retData

    def handleService(self, index, refresh=0):
        printDBG('handleService start')

        CBaseSubProviderClass.handleService(self, index, refresh)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')

        printDBG("handleService: name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.initSubProvider(self.currItem)
            if len(self.languages):
                self.listSearchTypes(self.currItem, 'list_languages')
        elif category == 'list_languages':
            self.listLanguages(self.currItem, 'search_subtitles')
        elif category == 'search_subtitles':
            self.searchSubtitles(self.currItem, 'list_subtitles')
        elif category == 'list_episodes':
            self.listEpisodesItems(self.currItem, 'list_download_items')
        elif category == 'list_download_items':
            self.listDownloadItems(self.currItem, 'list_subtitles')
        elif category == 'list_subtitles':
            self.getSubtitlesList(self.currItem, 'list_sub_in_packed_file')
        elif category == 'list_sub_in_packed_file':
            self.listSubsInPackedFile(self.currItem, 'list_sub_in_packed_file')

        CBaseSubProviderClass.endHandleService(self, index, refresh)


class IPTVSubProvider(CSubProviderBase):

    def __init__(self, params={}):
        CSubProviderBase.__init__(self, OpenSubtitles(params))
