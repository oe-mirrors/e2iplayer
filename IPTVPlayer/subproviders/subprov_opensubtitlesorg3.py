# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.isubprovider import CSubProviderBase, CBaseSubProviderClass
from Plugins.Extensions.IPTVPlayer.subproviders.subprov_opensubtitlesorg import OpenSubtitlesBase
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetDefaultLang
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import hex_md5
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.libs.subtitlesmatch import sortByRelease

###################################################
# FOREIGN import
###################################################
import json
from xml.sax.saxutils import escape as xml_escape
from Components.config import config
###################################################

###################################################
# Config options for HOST
###################################################


def GetConfigList():
    optionList = []
    return optionList
###################################################


class OpenSubtitlesRest(OpenSubtitlesBase):

    def __init__(self, params={}):
        self.USER_AGENT = 'IPTVPlayer v1'
        self.MAIN_URL = 'https://rest.opensubtitles.org/'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'Referer': self.MAIN_URL, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Encoding': 'gzip, deflate'}

        CBaseSubProviderClass.__init__(self, params)

        self.defaultParams = {'header': self.HTTP_HEADER}
        self.languages = [{"iso": "af", "id": "afr", "name": "Afrikaans"}, {"iso": "sq", "id": "alb", "name": "Albanian"}, {"iso": "ar", "id": "ara", "name": "Arabic"}, {"iso": "an", "id": "arg", "name": "Aragonese"}, {"iso": "hy", "id": "arm", "name": "Armenian"}, {"iso": "at", "id": "ast", "name": "Asturian"}, {"iso": "az", "id": "aze", "name": "Azerbaijani"}, {"iso": "eu", "id": "baq", "name": "Basque"}, {"iso": "be", "id": "bel", "name": "Belarusian"}, {"iso": "bn", "id": "ben", "name": "Bengali"}, {"iso": "bs", "id": "bos", "name": "Bosnian"}, {"iso": "br", "id": "bre", "name": "Breton"}, {"iso": "bg", "id": "bul", "name": "Bulgarian"}, {"iso": "my", "id": "bur", "name": "Burmese"}, {"iso": "ca", "id": "cat", "name": "Catalan"}, {"iso": "zh", "id": "chi", "name": "Chinese (simplified)"}, {"iso": "zt", "id": "zht", "name": "Chinese (traditional)"}, {"iso": "ze", "id": "zhe", "name": "Chinese bilingual"}, {"iso": "hr", "id": "hrv", "name": "Croatian"}, {"iso": "cs", "id": "cze", "name": "Czech"}, {"iso": "da", "id": "dan", "name": "Danish"}, {"iso": "nl", "id": "dut", "name": "Dutch"}, {"iso": "en", "id": "eng", "name": "English"}, {"iso": "eo", "id": "epo", "name": "Esperanto"}, {"iso": "et", "id": "est", "name": "Estonian"}, {"iso": "ex", "id": "ext", "name": "Extremaduran"}, {"iso": "fi", "id": "fin", "name": "Finnish"}, {"iso": "fr", "id": "fre", "name": "French"}, {"iso": "gl", "id": "glg", "name": "Galician"}, {"iso": "ka", "id": "geo", "name": "Georgian"}, {"iso": "de", "id": "ger", "name": "German"}, {"iso": "el", "id": "ell", "name": "Greek"}, {"iso": "he", "id": "heb", "name": "Hebrew"}, {"iso": "hi", "id": "hin", "name": "Hindi"}, {"iso": "hu", "id": "hun", "name": "Hungarian"}, {"iso": "is", "id": "ice", "name": "Icelandic"}, {"iso": "id", "id": "ind", "name": "Indonesian"}, {"iso": "it", "id": "ita", "name": "Italian"}, {"iso": "ja", "id": "jpn", "name": "Japanese"}, {"iso": "kn", "id": "kan", "name": "Kannada"}, {"iso": "kk", "id": "kaz", "name": "Kazakh"}, {"iso": "km", "id": "khm", "name": "Khmer"}, {"iso": "ko", "id": "kor", "name": "Korean"}, {"iso": "ku", "id": "kur", "name": "Kurdish"}, {"iso": "lv", "id": "lav", "name": "Latvian"}, {"iso": "lt", "id": "lit", "name": "Lithuanian"}, {"iso": "lb", "id": "ltz", "name": "Luxembourgish"}, {"iso": "mk", "id": "mac", "name": "Macedonian"}, {"iso": "ms", "id": "may", "name": "Malay"}, {"iso": "ml", "id": "mal", "name": "Malayalam"}, {"iso": "ma", "id": "mni", "name": "Manipuri"}, {"iso": "mn", "id": "mon", "name": "Mongolian"}, {"iso": "me", "id": "mne", "name": "Montenegrin"}, {"iso": "no", "id": "nor", "name": "Norwegian"}, {"iso": "oc", "id": "oci", "name": "Occitan"}, {"iso": "fa", "id": "per", "name": "Persian"}, {"iso": "pl", "id": "pol", "name": "Polish"}, {"iso": "pt", "id": "por", "name": "Portuguese"}, {"iso": "pb", "id": "pob", "name": "Portuguese (BR)"}, {"iso": "pm", "id": "pom", "name": "Portuguese (MZ)"}, {"iso": "ro", "id": "rum", "name": "Romanian"}, {"iso": "ru", "id": "rus", "name": "Russian"}, {"iso": "sr", "id": "scc", "name": "Serbian"}, {"iso": "si", "id": "sin", "name": "Sinhalese"}, {"iso": "sk", "id": "slo", "name": "Slovak"}, {"iso": "sl", "id": "slv", "name": "Slovenian"}, {"iso": "es", "id": "spa", "name": "Spanish"}, {"iso": "sw", "id": "swa", "name": "Swahili"}, {"iso": "sv", "id": "swe", "name": "Swedish"}, {"iso": "sy", "id": "syr", "name": "Syriac"}, {"iso": "tl", "id": "tgl", "name": "Tagalog"}, {"iso": "ta", "id": "tam", "name": "Tamil"}, {"iso": "te", "id": "tel", "name": "Telugu"}, {"iso": "th", "id": "tha", "name": "Thai"}, {"iso": "tr", "id": "tur", "name": "Turkish"}, {"iso": "uk", "id": "ukr", "name": "Ukrainian"}, {"iso": "ur", "id": "urd", "name": "Urdu"}, {"iso": "vi", "id": "vie", "name": "Vietnamese"}]

        self.lastDownloadError = ''

    def getMoviesTitles(self, cItem, nextCategory):
        OpenSubtitlesBase.getMoviesTitles(self, cItem, nextCategory)
        if 0 == len(self.currList):
            # nothing (or no answer) from IMDb: the title query of the REST API
            self.getLanguages(cItem, 'get_search')

    def getLanguages(self, cItem, nextCategory):
        printDBG("OpenSubtitlesRest.getLanguages")
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

        if None is not engLanguageItem:
            tmpList.insert(0, engLanguageItem)

        if None is not defaultLanguageItem:
            tmpList.insert(0, defaultLanguageItem)

        for item in tmpList:
            params = dict(cItem)
            params.update(item)
            params.update({'category': nextCategory})
            self.addDir(params)

    def getSearchList(self, cItem):
        printDBG("OpenSubtitlesRest.getSearchList")
        queryTab = []

        langid = cItem.get('search_lang', '')
        imdbid = cItem.get('imdbid', '')
        if imdbid != '':
            queryTab.append('imdbid-%s' % str(imdbid).zfill(7))
        else:
            # no IMDb hit: the title without "S02E05" / the year, season and episode as parameters
            title, _year, season, episode = self.wantedInfo()
            title = title or self.params['confirmed_title']
            queryTab.append('query-%s' % urllib_quote(title.lower()))
            if 'season' not in cItem and season and episode:
                cItem = dict(cItem, season=season, episode=episode)

        if langid != '':
            queryTab.append('sublanguageid-%s' % langid)

        if 'season' in cItem and 'episode' in cItem:
            queryTab.append('episode-%s' % cItem['episode'])
            queryTab.append('season-%s' % cItem['season'])

        # the REST API only answers the canonical form: parameters in alphabetical order, no slash at
        # the end (else it redirects, for another order to the broken host "https://_/")
        url = self.getFullUrl('/search/%s' % ('/'.join(sorted(queryTab))))
        sts, data = self.cm.getPage(url, self.defaultParams)
        if not sts:
            return
        try:
            data = json.loads(data)
        except Exception:
            printExc()
            return

        subFormats = self.getSupportedFormats(all=True)
        subList = []
        for item in data if isinstance(data, list) else []:
            # one odd result must not cost the others
            try:
                params = self.subtitleItem(item, subFormats, withLang=True)
            except Exception:
                printExc()
                continue
            if params is not None:
                subList.append(dict(cItem, **params))
        # the subtitles of the release the user plays first
        for params in sortByRelease(subList, self.releaseName()):
            self.addSubtitle(params)

    def downloadSubtitleFile(self, cItem):
        printDBG("OpenSubtitlesRest.downloadSubtitleFile")
        baseUrl = cItem['url']

        # The link of the REST search has no session token and gives the file (anonymous download,
        # limited per IP). When that fails, the token of a user login (sid-...) is put into the link;
        # the token of an anonymous login only gives a "Become VIP member" note, so it is not tried.
        if baseUrl.startswith('https://'):
            baseUrl = 'http://' + baseUrl.split('://', 1)[-1]  # NOSONAR - opensubtitles is used over http on purpose (box TLS)

        data = self.fetchSubtitleData(baseUrl)
        if data is None and '/filead/' in baseUrl and '/sid-' not in baseUrl:
            error = self.lastDownloadError
            token = self._getLoginToken(config.plugins.iptvplayer.opensuborg_login.value, config.plugins.iptvplayer.opensuborg_password.value)
            if token != '':
                data = self.fetchSubtitleData(baseUrl.replace('/filead/', '/sid-%s/filead/' % token))
            if data is None and error:
                self.lastDownloadError = error

        if data is None:
            SetIPTVPlayerLastHostError(self.lastDownloadError or _('Failed to download subtitle.'))
            return {}
        return self.saveFetchedSubtitle(data, cItem)

    def _getLoginToken(self, login, password):
        # XML-RPC LogIn of the opensubtitles.org account, '' without an account or when it fails
        if login == '':
            return ''
        loginUrl = 'http://api.opensubtitles.org/xml-rpc'  # NOSONAR - opensubtitles xml-rpc is used over http on purpose (box TLS)
        loginData = '<methodCall><methodName>LogIn</methodName><params>'
        for value in (login, hex_md5(password), 'en', self.USER_AGENT):
            loginData += '<param><value><string>{0}</string></value></param>'.format(xml_escape(value))
        loginData += '</params></methodCall>'
        params = {'header': self.HTTP_HEADER, 'raw_post_data': True}
        sts, data = self.cm.getPage(loginUrl, params, loginData)
        if not sts:
            return ''
        status = self.cm.ph.getDataBeetwenMarkers(data, '<name>status</name>', '</string>', False)[1].rsplit('>', 1)[-1].strip()
        printDBG("OpenSubtitlesRest._getLoginToken status[%s]" % status)
        if not status.startswith('2'):
            self.lastDownloadError = _('Login failed!') + ' ' + status
            return ''
        return self.cm.ph.getDataBeetwenMarkers(data, '<name>token</name>', '</string>', False)[1].rsplit('>', 1)[-1].strip()

    def handleService(self, index, refresh=0):
        printDBG('handleService start')

        CBaseSubProviderClass.handleService(self, index, refresh)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')

        printDBG("handleService: name[%s], category[%s] " % (name, category))
        self.currList = []

    # MAIN MENU
        if name is None:
            self.getMoviesTitles({'name': 'category'}, 'get_type')
        elif category == 'get_type':
            # take actions depending on the type
            self.getType(self.currItem, 'get_search')
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
