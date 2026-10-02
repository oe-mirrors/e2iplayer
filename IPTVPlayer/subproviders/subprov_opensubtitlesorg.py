# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.isubprovider import CSubProviderBase, CBaseSubProviderClass

from Plugins.Extensions.IPTVPlayer.tools.iptvtools import (
    printDBG,
    printExc,
    GetDefaultLang,
    RemoveDisallowedFilenameChars,
    rm,
)

from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import hex_md5
from Plugins.Extensions.IPTVPlayer.libs.subtitlesmatch import sortByRelease

###################################################
# FOREIGN import
###################################################
import gzip
import re
from xml.sax.saxutils import escape as xml_escape, unescape as xml_unescape
from Components.config import config
###################################################

###################################################
# Config options for HOST
###################################################


def GetConfigList():
    optionList = []
    return optionList
###################################################


class OpenSubtitlesBase(CBaseSubProviderClass):
    """What the OpenSubtitles providers (opensubtitlesorg, opensubtitlesorg3, opensubtitlesv3) share: the IMDb steps
    title -> type -> season -> episode, and for the two opensubtitles.org ones the result items and the download
    of the .gz files. Subclasses implement getLanguages(cItem, nextCategory)."""

    def getMoviesTitles(self, cItem, nextCategory):
        printDBG("%s.getMoviesTitles" % self.__class__.__name__)
        # imdbGetMoviesByTitle drops "S02E05" / the year of the confirmed title itself
        for item in self.imdbGetMoviesByTitle(self.params['confirmed_title'])[1]:
            params = dict(cItem)
            params.update(item)  # item = {'title', 'base_title', 'year', 'imdbid'}
            params.update({'category': nextCategory})
            self.addDir(params)

    def getType(self, cItem, nextCategory):
        # a series -> its seasons (the wanted one first), a movie -> the languages, then nextCategory
        printDBG("%s.getType" % self.__class__.__name__)
        imdbid = cItem['imdbid']
        if self.getTypeFromThemoviedb(imdbid, cItem['title']) == 'series':
            for item in self.imdbGetSeasons(imdbid, self.wantedInfo()[2])[1]:
                params = dict(cItem)
                params.update({'category': 'get_episodes', 'item_title': cItem['title'], 'season': item, 'title': _('Season %s') % item})
                self.addDir(params)
        else:
            self.getLanguages(cItem, nextCategory)

    def getEpisodes(self, cItem, nextCategory, numberedOnly=False):
        printDBG("%s.getEpisodes" % self.__class__.__name__)
        season = cItem['season']
        for item in self.imdbGetEpisodesForSeason(cItem['imdbid'], season, self.wantedInfo()[3])[1]:
            if numberedOnly and not item['episode'].isdigit():
                continue
            params = dict(cItem)
            params.update(item)  # item = "episode_title", "episode", "eimdbid"
            title = 's{0}e{1} {2}'.format(str(season).zfill(2), str(item['episode']).zfill(2), item['episode_title'])
            params.update({'category': nextCategory, 'title': title})
            self.addDir(params)

    @staticmethod
    def subtitleTitle(item, withLang=False, withTime=False):
        # the list title of an opensubtitles.org result
        title = (item.get('MovieReleaseName') or item.get('SubFileName') or item.get('MovieName') or '').strip()
        ext = '.' + item.get('SubFormat', '')
        if len(ext) > 1 and title.lower().endswith(ext.lower()):
            title = title[:-len(ext)]
        if withLang:
            title = '[%s] %s' % (item.get('ISO639', ''), title)
        cdMax = item.get('SubSumCD', '1')
        if cdMax != '1':
            title += ' CD[{0}/{1}]'.format(item.get('SubActualCD', '1'), cdMax)
        if withTime and item.get('SubLastTS'):
            title += ' [{0}]'.format(item['SubLastTS'])
        return RemoveDisallowedFilenameChars(title)

    def subtitleItem(self, item, subFormats, withLang=False, withTime=False):
        # an opensubtitles.org result (XML-RPC or REST, same fields) -> list item, None when it is no usable file
        link = item.get('SubDownloadLink', '')
        if not (self.cm.isValidUrl(link) and link.endswith('.gz') and item.get('SubFormat', '') in subFormats):
            return None
        try:
            fps = float(item.get('MovieFPS') or 0)
        except (TypeError, ValueError):
            fps = 0
        return {'title': self.subtitleTitle(item, withLang, withTime), 'lang': item.get('ISO639', ''), 'sub_id': item.get('IDSubtitle', ''),
                'imdbid': item.get('IDMovieImdb', ''), 'fps': fps, 'encoding': item.get('SubEncoding', ''), 'url': link}

    def fetchSubtitleData(self, url):
        # the subtitle file as bytes: the .gz from dl.opensubtitles.org unpacked, or None with self.lastDownloadError
        self.lastDownloadError = ''
        sts, data = self.downloadBinary(url, {'header': self.HTTP_HEADER})
        if not sts or not data:
            return None
        if data[:2] == b'\x1f\x8b':
            try:
                data = gzip.decompress(data)
            except Exception:
                printExc()
                self.lastDownloadError = _('Failed to gzip.')
                return None
        elif data.lstrip()[:15].lower().startswith((b'<!doctype', b'<html')):
            # a web page instead of the file, e.g. when the download limit is reached
            printDBG("%s.fetchSubtitleData not a subtitle file:\n%s" % (self.__class__.__name__, data[:500]))
            self.lastDownloadError = _('The server did not return a subtitle file (download limit reached?).')
            return None
        if len(data) < 1024 and b'osdb.link/vip' in data.lower():
            # the "Become OpenSubtitles.org VIP member" note instead of the subtitle
            printDBG("%s.fetchSubtitleData VIP note instead of the subtitle" % self.__class__.__name__)
            self.lastDownloadError = _('OpenSubtitles.org sent a "become VIP member" note instead of the subtitle (download limit reached?).')
            return None
        return data

    def saveFetchedSubtitle(self, data, cItem):
        # the downloaded file -> UTF-8 in the subtitles folder; the encoding the site reports is tried first
        # (UTF-8 / ASCII are left to converFileToUtf8, which also drops a BOM)
        encoding = (cItem.get('encoding') or '').strip().lower()
        if encoding in ('utf-8', 'utf8', 'ascii', 'us-ascii'):
            encoding = ''
        return self.saveSubtitleData(data, cItem['title'], cItem['lang'], cItem.get('sub_id', ''), cItem.get('imdbid', ''), fps=cItem.get('fps', 0), encoding=encoding)


class OpenSubOrgProvider(OpenSubtitlesBase):
    LANGUAGE_CACHE = []

    def __init__(self, params={}):
        self.USER_AGENT = 'IPTVPlayer v1'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Encoding': 'gzip, deflate'}
        self.MAIN_URL = 'http://api.opensubtitles.org/xml-rpc'  # NOSONAR - xml-rpc endpoint, kept on http (matches subprov_opensubtitlesorg3)

        params['cookie'] = 'opensubtitlesorg.cookie'
        CBaseSubProviderClass.__init__(self, params)
        self.cm.HEADER = self.HTTP_HEADER

        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.lastApiError = {'code': 0, 'message': ''}
        self.loginToken = ''
        self.lastDownloadError = ''

    def _resp2Json(self, data):
        retJson = []

        stage = 'none'
        tagsStack = []
        tagName = ''
        startTag = False
        endTag = False
        codingTag = False

        value = None
        name = None
        obj = {}

        for idx in range(len(data)):
            it = data[idx]
            if it == '<':
                if stage in ['text', 'none']:
                    stage = 'tag'
                    tagName = ''
                    startTag = False
                    endTag = False
                    codingTag = False
                else:
                    raise Exception("Not expected < stage[%s] idx[%d]\n========================%s\n" % (stage, idx, data[idx:]))
            elif 'tag' == stage:
                if True not in [startTag, endTag, codingTag]:
                    if '/' == it:
                        endTag = True
                    elif '?' == it:
                        codingTag = True
                    else:
                        startTag = True
                        tagName = it
                else:
                    if '>' == it:
                        if startTag:
                            if 0 == len(tagName):
                                raise Exception("Empty tag name detected")
                            tagsStack.append(tagName)
                            text = ''
                            if '/' != tagName[-1]:
                                stage = 'text'
                                continue
                            else:
                                endTag = True
                        if endTag:
                            if tagName != tagsStack[-1]:
                                raise Exception("End not existing start tag [%s][%s]" % (tagName, tagsStack[-1]))
                            del tagsStack[-1]
                            if tagName == 'name':
                                name = self._unescape(text)
                            elif tagName == 'value':
                                value = self._unescape(text)
                            elif 'double' == tagName:
                                text = float(text)
                            elif 'member' == tagName:
                                if name is not None:
                                    obj[name] = value
                                    name = None
                                    value = None
                            elif 'struct' == tagName:
                                retJson.append(obj)
                                obj = {}
                        stage = 'none'
                    else:
                        tagName += it

            elif 'text' == stage:
                text += it

        if 0 != len(tagsStack):
            raise Exception("Some tags have not been ended")
        return retJson

    @staticmethod
    def _unescape(text):
        if isinstance(text, str):
            return xml_unescape(text, {'&quot;': '"', '&apos;': "'"})
        return text

    def _rpcMethodCall(self, method, paramsList=[]):
        requestData = "<methodCall><methodName>{0}</methodName><params>".format(method)
        for item in paramsList:
            requestData += "<param>"
            requestData += "<value>"
            if item.startswith('<'):
                requestData += item
            else:
                requestData += "<string>{0}</string>".format(xml_escape(item))
            requestData += "</value>"
            requestData += "</param>"
        requestData += "</params></methodCall>"

        printDBG("OpenSubOrgProvider._rpcMethodCall requestData[%s]" % requestData)
        httpParams = dict(self.defaultParams)
        httpParams['raw_post_data'] = True
        sts, data = self.cm.getPage(self.MAIN_URL, httpParams, requestData)
        if sts:
            try:
                data = self._resp2Json(data)
            except Exception:
                sts = False
                printExc()
        return sts, data

    def _checkStatus(self, data, idx=None):
        try:
            if None is idx:
                for idx in range(len(data)):
                    if 'status' in data[idx]:
                        item = data[idx]
                        break
            else:
                item = data[idx]
            code = int(item['status'].split(' ')[0])
            if code >= 200 and code < 300:
                return True
            self.lastApiError = {'code': code, 'message': item['status']}

        except Exception:
            printExc()
            self.lastApiError = {'code': -999, 'message': _('_checkStatus except error')}
        return False

    def _serializeValue(self, item):
        param = '<value>'
        if isinstance(item, float):
            param += '<double>{0}</double>'.format(item)
        elif isinstance(item, str):
            param += '<string>{0}</string>'.format(xml_escape(item))
        param += '</value>'
        return param

    def _getArraryParam(self, array=[]):
        param = '<array><data><value><struct>'
        for item in array:
            param += '<member>'
            param += '<name>{0}</name>'.format(item['name'])
            param += self._serializeValue(item['value'])
            param += '</member>'
        param += '</struct></value></data></array>'
        return param

    def _doLogin(self, login, password):
        lang = GetDefaultLang()
        params = [login, hex_md5(password), lang, self.USER_AGENT]
        sts, data = self._rpcMethodCall("LogIn", params)
        if sts and (None is data or 0 == len(data)):
            sts = False
        printDBG(">>>>>>>>>>>>>>>>>>>>>>>>>>>>> data[%s]" % data)
        if not sts:
            SetIPTVPlayerLastHostError(_('Login failed!'))
        elif ('' != login and self._checkStatus(data, 0)) or '' == login:
            if 'token' in data[0]:
                self.loginToken = data[0]['token']
            else:
                SetIPTVPlayerLastHostError(_('Get token failed!') + '\n' + _('Error message: \"%s\".\nError code: \"%s\".') % (self.lastApiError['message'], self.lastApiError['code']))
        else:
            SetIPTVPlayerLastHostError(_('Login failed!') + '\n' + _('Error message: \"%s\".\nError code: \"%s\".') % (self.lastApiError['message'], self.lastApiError['code']))

    def _getLanguages(self):
        lang = GetDefaultLang()
        subParams = [{'name': 'sublanguageid', 'value': lang}]
        params = [self.loginToken, self._getArraryParam(subParams)]

        sts, data = self._rpcMethodCall("GetSubLanguages", params)
        printDBG(">>>>>>>>>>>>>>>>>>>>>>>>>>>>> data[%s]" % data)
        if sts:
            try:
                list = []
                defaultLanguageItem = None
                engLanguageItem = None
                for item in data:
                    if 'LanguageName' in item and 'SubLanguageID' in item and 'ISO639' in item:
                        params = {'title': '{0} [{1}]'.format(item['LanguageName'], item['SubLanguageID']), 'lang': item['SubLanguageID']}
                        if lang == item['ISO639']:
                            defaultLanguageItem = params
                        elif 'en' == item['ISO639']:
                            engLanguageItem = params
                        else:
                            list.append(params)
                for params in (engLanguageItem, defaultLanguageItem):
                    if None is not params:
                        list.insert(0, params)
                return list
            except Exception:
                printExc()
        SetIPTVPlayerLastHostError(_('Get languages failed!'))
        return []

    def _searchSubtitle(self, cItem):
        # the episode has its own IMDb id, a movie the one of the title
        subParams = [{'name': 'sublanguageid', 'value': cItem['lang']}, {'name': 'imdbid', 'value': cItem.get('eimdbid') or cItem['imdbid']}]
        params = [self.loginToken, self._getArraryParam(subParams)]

        sts, data = self._rpcMethodCall("SearchSubtitles", params)
        printDBG(">>>>>>>>>>>>>>>>>>>>>>>>>>>>> data[%s]" % data)
        if not sts:
            return []
        subFormats = self.getSupportedFormats()
        subList = []
        for item in data:
            # one odd result must not cost the others
            try:
                params = self.subtitleItem(item, subFormats, withTime=True)
            except Exception:
                printExc()
                continue
            if params is not None:
                subList.append(params)
        return subList

    def getLanguages(self, cItem, nextCategory):
        printDBG("OpenSubOrgProvider.getLanguages")
        if 0 == len(OpenSubOrgProvider.LANGUAGE_CACHE):
            OpenSubOrgProvider.LANGUAGE_CACHE = self._getLanguages()

        itemTitle = cItem.get('item_title', cItem['title'])
        for item in OpenSubOrgProvider.LANGUAGE_CACHE:
            params = dict(cItem)
            params.update(item)
            params.update({'category': nextCategory, 'item_title': itemTitle})
            self.addDir(params)

    def getSubtitles(self, cItem):
        printDBG("OpenSubOrgProvider.getSubtitles")
        for item in sortByRelease(self._searchSubtitle(cItem), self.releaseName()):
            params = dict(cItem)
            params.update(item)
            # the search language (SubLanguageID, e.g. "ger") becomes the ISO 639-1 code of the file
            params.update({'lang': item['lang'] or cItem['lang'], 'imdbid': item['imdbid'] or cItem.get('eimdbid') or cItem['imdbid']})
            self.addSubtitle(params)

    def downloadSubtitleFile(self, cItem):
        printDBG("OpenSubOrgProvider.downloadSubtitleFile")
        url = cItem['url']
        # The link carries the session token (sid-...) of the search. With the token of an anonymous
        # login it only gives a "Become VIP member" note instead of the subtitle, the link without it
        # gives the file (anonymous download, limited per IP). A user login is tried with its token first.
        urls = [url]
        if '/sid-' in url:
            stripped = re.sub(r'/sid-[^/]+', '', url)
            urls = [url, stripped] if config.plugins.iptvplayer.opensuborg_login.value else [stripped]
        data = None
        for url in urls:
            data = self.fetchSubtitleData(url)
            if data is not None:
                break
        if data is None:
            SetIPTVPlayerLastHostError(self.lastDownloadError or _('Failed to download subtitle.'))
            return {}
        return self.saveFetchedSubtitle(data, cItem)

    def handleService(self, index, refresh=0):
        printDBG('handleService start')

        CBaseSubProviderClass.handleService(self, index, refresh)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')

        printDBG("handleService: name[%s], category[%s] " % (name, category))
        self.currList = []

    # MAIN MENU
        if name is None:
            rm(self.COOKIE_FILE)
            login = config.plugins.iptvplayer.opensuborg_login.value
            password = config.plugins.iptvplayer.opensuborg_password.value
            self._doLogin(login, password)
            if self.loginToken != '':
                self.getMoviesTitles({'name': 'category'}, 'get_type')
        elif category == 'get_type':
            # take actions depending on the type
            self.getType(self.currItem, 'get_subtitles')
        elif category == 'get_episodes':
            self.getEpisodes(self.currItem, 'get_languages')
        elif category == 'get_languages':
            self.getLanguages(self.currItem, 'get_subtitles')
        elif category == 'get_subtitles':
            self.getSubtitles(self.currItem)

        CBaseSubProviderClass.endHandleService(self, index, refresh)


class IPTVSubProvider(CSubProviderBase):

    def __init__(self, params={}):
        CSubProviderBase.__init__(self, OpenSubOrgProvider(params))
