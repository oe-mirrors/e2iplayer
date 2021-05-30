# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.isubprovider import CSubProviderBase, CBaseSubProviderClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetDefaultLang, byteify, \
                                                          RemoveDisallowedFilenameChars, GetSubtitlesDir
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import hex_md5
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib
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


class OpenSubtitlesRest(CBaseSubProviderClass):

    def __init__(self, params={}):
        self.USER_AGENT = 'IPTVPlayer v1'
        #self.USER_AGENT    = 'Subliminal v0.3'
        self.MAIN_URL = 'https://rest.opensubtitles.org/'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'Referer': self.MAIN_URL, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Encoding': 'gzip, deflate'}

        params['cookie'] = 'opensubtitlesorg3.cookie'
        CBaseSubProviderClass.__init__(self, params)

        self.defaultParams = {'header': self.HTTP_HEADER, 'ignore_http_code_ranges': [], 'use_cookie': False, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.languages = [{"iso": "af", "id": "afr", "name": "Afrikaans"}, {"iso": "sq", "id": "alb", "name": "Albanian"}, {"iso": "ar", "id": "ara", "name": "Arabic"}, {"iso": "an", "id": "arg", "name": "Aragonese"}, {"iso": "hy", "id": "arm", "name": "Armenian"}, {"iso": "at", "id": "ast", "name": "Asturian"}, {"iso": "az", "id": "aze", "name": "Azerbaijani"}, {"iso": "eu", "id": "baq", "name": "Basque"}, {"iso": "be", "id": "bel", "name": "Belarusian"}, {"iso": "bn", "id": "ben", "name": "Bengali"}, {"iso": "bs", "id": "bos", "name": "Bosnian"}, {"iso": "br", "id": "bre", "name": "Breton"}, {"iso": "bg", "id": "bul", "name": "Bulgarian"}, {"iso": "my", "id": "bur", "name": "Burmese"}, {"iso": "ca", "id": "cat", "name": "Catalan"}, {"iso": "zh", "id": "chi", "name": "Chinese (simplified)"}, {"iso": "zt", "id": "zht", "name": "Chinese (traditional)"}, {"iso": "ze", "id": "zhe", "name": "Chinese bilingual"}, {"iso": "hr", "id": "hrv", "name": "Croatian"}, {"iso": "cs", "id": "cze", "name": "Czech"}, {"iso": "da", "id": "dan", "name": "Danish"}, {"iso": "nl", "id": "dut", "name": "Dutch"}, {"iso": "en", "id": "eng", "name": "English"}, {"iso": "eo", "id": "epo", "name": "Esperanto"}, {"iso": "et", "id": "est", "name": "Estonian"}, {"iso": "ex", "id": "ext", "name": "Extremaduran"}, {"iso": "fi", "id": "fin", "name": "Finnish"}, {"iso": "fr", "id": "fre", "name": "French"}, {"iso": "gl", "id": "glg", "name": "Galician"}, {"iso": "ka", "id": "geo", "name": "Georgian"}, {"iso": "de", "id": "ger", "name": "German"}, {"iso": "el", "id": "ell", "name": "Greek"}, {"iso": "he", "id": "heb", "name": "Hebrew"}, {"iso": "hi", "id": "hin", "name": "Hindi"}, {"iso": "hu", "id": "hun", "name": "Hungarian"}, {"iso": "is", "id": "ice", "name": "Icelandic"}, {"iso": "id", "id": "ind", "name": "Indonesian"}, {"iso": "it", "id": "ita", "name": "Italian"}, {"iso": "ja", "id": "jpn", "name": "Japanese"}, {"iso": "kn", "id": "kan", "name": "Kannada"}, {"iso": "kk", "id": "kaz", "name": "Kazakh"}, {"iso": "km", "id": "khm", "name": "Khmer"}, {"iso": "ko", "id": "kor", "name": "Korean"}, {"iso": "ku", "id": "kur", "name": "Kurdish"}, {"iso": "lv", "id": "lav", "name": "Latvian"}, {"iso": "lt", "id": "lit", "name": "Lithuanian"}, {"iso": "lb", "id": "ltz", "name": "Luxembourgish"}, {"iso": "mk", "id": "mac", "name": "Macedonian"}, {"iso": "ms", "id": "may", "name": "Malay"}, {"iso": "ml", "id": "mal", "name": "Malayalam"}, {"iso": "ma", "id": "mni", "name": "Manipuri"}, {"iso": "mn", "id": "mon", "name": "Mongolian"}, {"iso": "me", "id": "mne", "name": "Montenegrin"}, {"iso": "no", "id": "nor", "name": "Norwegian"}, {"iso": "oc", "id": "oci", "name": "Occitan"}, {"iso": "fa", "id": "per", "name": "Persian"}, {"iso": "pl", "id": "pol", "name": "Polish"}, {"iso": "pt", "id": "por", "name": "Portuguese"}, {"iso": "pb", "id": "pob", "name": "Portuguese (BR)"}, {"iso": "pm", "id": "pom", "name": "Portuguese (MZ)"}, {"iso": "ro", "id": "rum", "name": "Romanian"}, {"iso": "ru", "id": "rus", "name": "Russian"}, {"iso": "sr", "id": "scc", "name": "Serbian"}, {"iso": "si", "id": "sin", "name": "Sinhalese"}, {"iso": "sk", "id": "slo", "name": "Slovak"}, {"iso": "sl", "id": "slv", "name": "Slovenian"}, {"iso": "es", "id": "spa", "name": "Spanish"}, {"iso": "sw", "id": "swa", "name": "Swahili"}, {"iso": "sv", "id": "swe", "name": "Swedish"}, {"iso": "sy", "id": "syr", "name": "Syriac"}, {"iso": "tl", "id": "tgl", "name": "Tagalog"}, {"iso": "ta", "id": "tam", "name": "Tamil"}, {"iso": "te", "id": "tel", "name": "Telugu"}, {"iso": "th", "id": "tha", "name": "Thai"}, {"iso": "tr", "id": "tur", "name": "Turkish"}, {"iso": "uk", "id": "ukr", "name": "Ukrainian"}, {"iso": "ur", "id": "urd", "name": "Urdu"}, {"iso": "vi", "id": "vie", "name": "Vietnamese"}]

        self.dInfo = params['discover_info']

    def getMoviesTitles(self, cItem, nextCategory):
        printDBG("OpenSubtitlesRest.getMoviesTitles")
        sts, tab = self.imdbGetMoviesByTitle(self.params['confirmed_title'])
        if not sts:
            return
        printDBG(tab)
        for item in tab:
            params = dict(cItem)
            params.update(item) # item = {'title', 'imdbid'}
            params.update({'category': nextCategory})
            self.addDir(params)

        if 0 == len(self.currList):
            self.getLanguages(cItem, 'get_search')

    def getType(self, cItem):
        printDBG("OpenSubtitlesRest.getType")
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
        printDBG("OpenSubtitlesRest.getEpisodes")
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
        lang = GetDefaultLang()
        tmpList = []

        defaultLanguageItem = None
        engLanguageItem = None
        for item in self.languages:
            params = {'title': '{0} [{1}]'.format(_(item['name']), item['id']), 'search_lang': item['id']}
            if lang == item['iso']:
                defaultLanguageItem = params
            elif 'en' == item['iso']:
                engLanguageItem = params
            else:
                tmpList.append(params)

        if None != engLanguageItem:
            tmpList.insert(0, engLanguageItem)

        if None != defaultLanguageItem:
            tmpList.insert(0, defaultLanguageItem)

        #tmpList.insert(0, {'title':_('All'), 'search_lang':''})

        for item in tmpList:
            params = dict(cItem)
            params.update(item)
            params.update({'category': nextCategory})
            self.addDir(params)

    def _getSubtitleTitle(self, item):
        title = item.get('MovieReleaseName', '')
        if '' == title:
            title = item.get('SubFileName', '')
        if '' == title:
            title = item.get('MovieName', '')
        title = '[%s] %s' % (item['ISO639'], title.strip())

        cdMax = item.get('SubSumCD', '1')
        cd = item.get('SubActualCD', '1')
        if cdMax != '1':
            title += ' CD[{0}/{1}]'.format(cdMax, cd)

        #lastTime = item.get('SubLastTS', '')
        #if '' != lastTime: title += ' [{0}]'.format(lastTime)

        return RemoveDisallowedFilenameChars(title)

    def _getFileName(self, subItem):
        title = self._getSubtitleTitle(subItem).replace('_', '.').replace('.' + subItem['SubFormat'], '').replace(' ', '.')
        match = re.search(r'[^.]', title)
        if match:
            title = title[match.start():]

        fileName = "{0}_{1}_0_{2}_{3}".format(title, subItem['ISO639'], subItem['IDSubtitle'], subItem['IDMovieImdb'])
        try:
            fps = float(subItem['MovieFPS'])
            if fps > 0:
                fileName += '_fps{0}'.format(fps)
        except Exception:
            printExc()
        fileName += '.' + subItem['SubFormat']
        return fileName

    def getSearchList(self, cItem):
        printDBG("OpenSubtitlesRest.getSearchList")
        queryTab = []

        langid = cItem.get('search_lang', '')
        imdbid = cItem.get('imdbid', '')
        if imdbid != '':
            queryTab.append('imdbid-%s' % str(imdbid).zfill(7))
        else:
            if 'imdbid' in cItem:
                title = self.imdbGetOrginalByTitle(cItem['imdbid'])[1].get('title', cItem.get('base_title', ''))
            else:
                title = self.params['confirmed_title']
            queryTab.append('query-%s' % urllib.quote(title))

        if langid != '':
            queryTab.append('sublanguageid-%s' % langid)

        if 'season' in cItem and 'episode' in cItem:
            queryTab.append('episode-%s' % cItem['episode'])
            queryTab.append('season-%s' % cItem['season'])

        url = self.getFullUrl('/search/%s/' % ('/'.join(queryTab)))
        sts, data = self.cm.getPage(url, self.defaultParams)
        if not sts:
            return

        subFormats = self.getSupportedFormats(all=True)
        try:
            data = byteify(json.loads(data))
            for item in data:
                link = item.get('SubDownloadLink', '')
                if self.cm.isValidUrl(link) and item.get('SubFormat', '') in subFormats and link.endswith('.gz'):
                    title = self._getSubtitleTitle(item)
                    fileName = self._getFileName(item)
                    try:
                        fps = float(item['MovieFPS'])
                    except Exception:
                        fps = 0
                    params = dict(cItem)
                    params.update({'title': title, 'file_name': fileName, 'lang': item['ISO639'], 'fps': fps, 'encoding': item.get('SubEncoding', ''), 'imdbid': item['IDMovieImdb'], 'url': link})
                    self.addSubtitle(params)
        except Exception:
            printExc()

    def downloadSubtitleFile(self, cItem):
        printDBG("OpenSubtitlesRest.downloadSubtitleFile")
        retData = {}
        title = cItem['title']
        fileName = cItem['file_name']
        baseUrl = cItem['url']
        lang = cItem['lang']
        encoding = cItem['encoding']
        imdbid = cItem['imdbid']
        fps = cItem.get('fps', 0)

        urlParams = dict(self.defaultParams)
        urlParams['max_data_size'] = self.getMaxFileSize()

        login = config.plugins.iptvplayer.opensuborg_login.value
        password = config.plugins.iptvplayer.opensuborg_password.value
        loginUrl = 'http://api.opensubtitles.org/xml-rpc'
        loginData = '''<methodCall>
                         <methodName>LogIn</methodName>
                           <params>
                             <param>
                               <value><string>{0}</string></value>
                             </param>
                             <param>
                               <value><string>{1}</string></value>
                             </param>
                           <param>
                             <value><string>{2}</string></value>
                           </param>
                           <param>
                             <value><string>{3}</string></value>
                           </param>
                         </params>
                       </methodCall>'''

        if baseUrl.startswith('https://'):
            baseUrl = 'http://' + baseUrl.split('://', 1)[-1]

        url = baseUrl
        attempt = 0
        while attempt < 3:
            attempt += 1
            sts, data = self.cm.getPage(url, urlParams)
            if not sts:
                params = dict(self.defaultParams)
                params['raw_post_data'] = True
                post_data = loginData.format(login, hex_md5(password), 'en', self.USER_AGENT)
                sts2, data = self.cm.getPage(loginUrl, params, post_data)
                if sts2:
                    data = self.cm.ph.getDataBeetwenMarkers(data, '<name>token</name>', '</string>', False)[1].rsplit('>', 1)[-1].strip()
                    if data != '':
                        url = baseUrl.replace('/filead/', '/sid-%s/filead/' % data)
                        continue
                if login != '':
                    login = ''
                    password = ''
                    continue
            break

        if not sts:
            SetIPTVPlayerLastHostError(_('Failed to download subtitle.'))
            return retData

        try:
            buf = StringIO(data)
            f = gzip.GzipFile(fileobj=buf)
            data = f.read()
        except Exception:
            printExc()
            SetIPTVPlayerLastHostError(_('Failed to gzip.'))
            return retData

        if encoding != '':
            try:
                data = data.decode(encoding).encode('UTF-8')
            except Exception:
                encoding = ''
                printExc()

        filePath = GetSubtitlesDir(fileName)
        if self.writeFile(filePath, data):
            if encoding != '':
                retData = {'title': title, 'path': filePath, 'lang': lang, 'imdbid': imdbid, 'fps': fps}
            elif self.converFileToUtf8(filePath, filePath, lang):
                retData = {'title': title, 'path': filePath, 'lang': lang, 'imdbid': imdbid, 'fps': fps}

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
            self.getMoviesTitles({'name': 'category'}, 'get_type')
        elif category == 'get_type':
            # take actions depending on the type
            self.getType(self.currItem)
        elif category == 'get_episodes':
            self.getEpisodes(self.currItem, 'get_languages')
        elif category == 'get_languages':
            self.getLanguages(self.currItem, 'get_search')
        elif category == 'get_search':
            self.getSearchList(self.currItem)

        CBaseSubProviderClass.endHandleService(self, index, refresh)


class IPTVSubProvider(CSubProviderBase):

    def __init__(self, params={}):
        CSubProviderBase.__init__(self, OpenSubtitlesRest(params))
