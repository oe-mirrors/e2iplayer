# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.isubprovider import CSubProviderBase, CBaseSubProviderClass
from Plugins.Extensions.IPTVPlayer.libs.pCommon import DecodeGzipped

from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetDefaultLang, \
                                                          RemoveDisallowedFilenameChars, GetSubtitlesDir, rm
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import hex_md5
###################################################

###################################################
# FOREIGN import
###################################################
import re
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

class OpenSubOrgProvider(CBaseSubProviderClass): 
    LANGUAGE_CACHE = []
    
    def __init__(self, params={}):
        self.USER_AGENT   = 'IPTVPlayer v1'
        self.HTTP_HEADER   = {'User-Agent':self.USER_AGENT, 'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Encoding':'gzip, deflate'}
        self.MAIN_URL      = 'http://api.opensubtitles.org/xml-rpc'
        
        params['cookie'] = 'opensubtitlesorg.cookie'
        CBaseSubProviderClass.__init__(self, params)
        self.cm.HEADER = self.HTTP_HEADER
        
        self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.lastApiError = {'code':0, 'message':''}
        self.loginToken   = ''
        
        self.dInfo = params['discover_info']
        
    def _resp2Json(self, data):
        retJson = []
        
        stage = 'none'
        tagsStack = []
        tagName   = ''
        startTag  = False
        endTag    = False
        codingTag = False
        
        value = None
        name  = None
        obj = {}
        
        for idx in range(len(data)):
            it = data[idx]
            if it == '<':
                if stage in ['text', 'none']: 
                    stage = 'tag'
                    tagName   = ''
                    startTag  = False
                    endTag    = False
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
                            if  '/' != tagName[-1]:
                                stage = 'text'
                                continue
                            else:
                                endTag = True
                        if endTag:
                            if tagName != tagsStack[-1]: 
                                raise Exception("End not existing start tag [%s][%s]" % (tagName, tagsStack[-1]))
                            del tagsStack[-1]
                            if tagName == 'name':
                                name  = text
                            elif tagName == 'value':
                                value  = text
                            elif 'double' == tagName:
                                text = float(text)
                            elif 'member' == tagName:
                                if name != None:
                                    obj[name] = value
                                    name  = None
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
        
    def _rpcMethodCall(self, method, paramsList=[]):
        requestData = "<methodCall><methodName>{0}</methodName><params>".format(method)
        for item in paramsList:
            requestData += "<param>"
            requestData += "<value>"
            if item.startswith('<'):
                requestData += item
            else:
                requestData += "<string>{0}</string>".format(item)
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
            if None == idx:
                for idx in range(len(data)):
                    if 'status' in data[idx]:
                        item = data[idx]
                        break
            else:
                item = data[idx]
            code = int(item['status'].split(' ')[0])
            if code >= 200 and code < 300:
                return True
            self.lastApiError = {'code':code, 'message':item['status']}
            
        except Exception:
            printExc()
            self.lastApiError = {'code':-999, 'message':_('_checkStatus except error')}
        return False
        
    def _serializeValue(self, item):
        param = '<value>'
        if isinstance(item, float):
            param += '<double>{0}</double>'.format(item)
        elif isinstance(item, str):
            param += '<string>{0}</string>'.format(item)
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
        if sts and (None == data or 0 == len(data)):
            sts = False 
        printDBG(">>>>>>>>>>>>>>>>>>>>>>>>>>>>> data[%s]" % data)
        if not sts:
            SetIPTVPlayerLastHostError(_('Login failed!'))
        elif ('' != login and self._checkStatus(data, 0)) or '' == login: 
            if 'token' in data[0]:
                self.loginToken = data[0]['token']
            else:
                SetIPTVPlayerLastHostError(_('Get token failed!') + '\n' + _('Error message: \"%s\".\nError code: \"%s\".') % (self.lastApiError['code'], self.lastApiError['message']) )
        else:
            SetIPTVPlayerLastHostError(_('Login failed!') + '\n' + _('Error message: \"%s\".\nError code: \"%s\".') % (self.lastApiError['code'], self.lastApiError['message']) )
        
    def _getLanguages(self):        
        lang = GetDefaultLang()
        subParams = [{'name':'sublanguageid', 'value':lang}]
        params = [self.loginToken, self._getArraryParam(subParams)]
        
        sts, data = self._rpcMethodCall("GetSubLanguages", params)
        printDBG(">>>>>>>>>>>>>>>>>>>>>>>>>>>>> data[%s]" % data)
        if sts:
            try:
                list = []
                defaultLanguageItem = None
                for item in data:
                    if 'LanguageName' in item and 'SubLanguageID' in item and 'ISO639' in item :
                        params = {'title':'{0} [{1}]'.format(item['LanguageName'], item['SubLanguageID']), 'lang':item['SubLanguageID']}
                        if lang !=  item['ISO639']:
                            list.append(params)
                        else:
                            defaultLanguageItem = params
                if None != defaultLanguageItem:
                    list.insert(0, defaultLanguageItem)
                return list
            except Exception:
                printExc()
        SetIPTVPlayerLastHostError(_('Get languages failed!'))
        return []
        
    def _getSubtitleTitle(self, item):
        title = item.get('MovieReleaseName', '')
        if '' == title:
            title = item.get('SubFileName', '')
        if '' == title:
            title = item.get('MovieName', '')
        
        cdMax = item.get('SubSumCD', '1')
        cd    = item.get('SubActualCD', '1')
        if cdMax != '1':
            title += ' CD[{0}/{1}]'.format(cdMax, cd)
        
        lastTime = item.get('SubLastTS', '')
        if '' != lastTime:
            title += ' [{0}]'.format(lastTime)
        
        return RemoveDisallowedFilenameChars(title)
        
    def _getFileName(self, subItem):
        title = self._getSubtitleTitle(subItem).replace('_', '.').replace('.'+subItem['SubFormat'], '').replace(' ', '.')
        match = re.search(r'[^.]', title)
        if match:
            title = title[match.start():]

        fileName = "{0}_{1}_0_{2}_{3}".format(title, subItem['ISO639'], subItem['IDSubtitle'], subItem['IDMovieImdb'])
        fileName = fileName + '.' + subItem['SubFormat']
        return fileName
        
    def _searchSubtitle(self, cItem):
        imdbid = cItem.get('eimdbid', cItem['imdbid'])
        sublanguageid = cItem['lang'] 
        
        subParams = [{'name':'sublanguageid', 'value':sublanguageid}, {'name':'imdbid', 'value':imdbid}]
        params = [self.loginToken, self._getArraryParam(subParams)]
        
        sts, data = self._rpcMethodCall("SearchSubtitles", params)
        printDBG(">>>>>>>>>>>>>>>>>>>>>>>>>>>>> data[%s]" % data)
        subFormats = self.getSupportedFormats()
        if sts:
            try:
                list = []
                for item in data:
                    link = item.get('SubDownloadLink', '')
                    if 'SubEncoding' in item and item.get('SubFormat', '') in subFormats and link.startswith('http') and link.endswith('.gz'):
                        title = self._getSubtitleTitle(item)
                        fileName = self._getFileName(item)
                        list.append({'title':title, 'file_name':fileName, 'encoding':item['SubEncoding'], 'url':link})
                return list
            except Exception:
                printExc()
        return []
        
    def getMoviesTitles(self, cItem, nextCategory):
        printDBG("OpenSubOrgProvider.getMoviesTitles")
        sts, tab = self.imdbGetMoviesByTitle(self.params['confirmed_title'])
        if not sts:
            return
        printDBG(tab)
        for item in tab:
            params = dict(cItem)
            params.update(item) # item = {'title', 'imdbid'}
            params.update({'category':nextCategory})
            self.addDir(params)
                
    def getType(self, cItem):
        printDBG("OpenSubOrgProvider.getType")
        imdbid = cItem['imdbid']
        title  = cItem['title']
        type = self.getTypeFromThemoviedb(imdbid, title)
        if type == 'series':
            promSeason = self.dInfo.get('season')
            sts, tab = self.imdbGetSeasons(imdbid, promSeason)
            if not sts:
                return
            for item in tab:
                params = dict(cItem)
                params.update({'category':'get_episodes', 'item_title':cItem['title'], 'season':item, 'title':_('Season %s') % item})
                self.addDir(params)
        elif type == 'movie':
            self.getLanguages(cItem, 'get_subtitles')
            
    def getEpisodes(self, cItem, nextCategory):
        printDBG("OpenSubOrgProvider.getEpisodes")
        imdbid    = cItem['imdbid']
        itemTitle = cItem['item_title']
        season    = cItem['season']
        
        promEpisode = self.dInfo.get('episode')
        sts, tab = self.imdbGetEpisodesForSeason(imdbid, season, promEpisode)
        if not sts:
            return
        for item in tab:
            params = dict(cItem)
            params.update(item) # item = "episode_title", "episode", "eimdbid"
            title = 's{0}e{1} {2}'.format(str(season).zfill(2), str(item['episode']).zfill(2), item['episode_title'])
            params.update({'category':nextCategory, 'title':title})
            self.addDir(params)
        
    def getLanguages(self, cItem, nextCategory):
        printDBG("OpenSubOrgProvider.getEpisodes")
        if 0 == len(OpenSubOrgProvider.LANGUAGE_CACHE):
            OpenSubOrgProvider.LANGUAGE_CACHE = self._getLanguages()

        itemTitle = cItem.get('item_title', cItem['title'])
        for item in OpenSubOrgProvider.LANGUAGE_CACHE:
            params = dict(cItem)
            params.update(item)
            params.update({'category':nextCategory, 'item_title':itemTitle})
            self.addDir(params)
            
    def getSubtitles(self, cItem):
        printDBG("OpenSubOrgProvider.getSubtitles")
        list = self._searchSubtitle(cItem)
        for item in list:
            params = dict(cItem)
            params.update(item)
            self.addSubtitle(params)
            
    def downloadSubtitleFile(self, cItem):
        printDBG("OpenSubOrgProvider.downloadSubtitleFile")
        retData = {}
        title    = cItem['title']
        fileName = cItem['file_name']
        url      = cItem['url']
        lang     = cItem['lang']
        encoding = cItem['encoding']
        imdbid   = cItem['imdbid']
        
        urlParams = dict(self.defaultParams)
        urlParams['max_data_size'] = self.getMaxFileSize()
        
        sts, data = self.cm.getPage(url, urlParams)
        if not sts:
            SetIPTVPlayerLastHostError(_('Failed to download subtitle.'))
            return retData
        
        try:
            data = DecodeGzipped(data)
        except Exception:
            printExc()
            SetIPTVPlayerLastHostError(_('Failed to gzip.'))
            return retData
        
        try:
            data = data.decode(encoding).encode('UTF-8')
        except Exception:
            printExc()
            SetIPTVPlayerLastHostError(_('Failed to decode to UTF-8.'))
            return retData
        
        fileName = GetSubtitlesDir(fileName)
        printDBG(">>")
        printDBG(fileName)
        printDBG("<<")
        try:
            with open(fileName, 'w') as f:
                f.write(data)
            retData = {'title':title, 'path':fileName, 'lang':lang, 'imdbid':imdbid}
        except Exception: 
            SetIPTVPlayerLastHostError(_('Failed to write file "%s".') % fileName)
            printExc()
        return retData
    
    def handleService(self, index, refresh=0):
        printDBG('handleService start')
        
        CBaseSubProviderClass.handleService(self, index, refresh)

        name     = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        
        printDBG( "handleService: name[%s], category[%s] " % (name, category) )
        self.currList = []
        
    #MAIN MENU
        if name == None:
            rm(self.COOKIE_FILE)
            login = config.plugins.iptvplayer.opensuborg_login.value
            password = config.plugins.iptvplayer.opensuborg_password.value
            self._doLogin(login, password)
            if self.loginToken != '':
                self.getMoviesTitles({'name':'category'}, 'get_type')
        elif category == 'get_type':
            # take actions depending on the type
            self.getType(self.currItem)
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
    
