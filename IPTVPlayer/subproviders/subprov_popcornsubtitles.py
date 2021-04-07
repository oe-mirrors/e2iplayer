# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.isubprovider import CSubProviderBase, CBaseSubProviderClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, RemoveDisallowedFilenameChars, \
                                                          GetSubtitlesDir, GetTmpDir, rm, MapUcharEncoding
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


class YoutubeComProvider(CBaseSubProviderClass): 
    
    def __init__(self, params={}):
        self.MAIN_URL = 'http://popcornsubtitles.com/'
        self.USER_AGENT = 'Mozilla/5.0 (X11; Linux i686) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/37.0.2062.120 Chrome/37.0.2062.120 Safari/537.36'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'Referer': self.MAIN_URL, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Encoding': 'gzip, deflate'}

        params['cookie'] = 'popcornsubtitlescom.cookie'
        CBaseSubProviderClass.__init__(self, params)
        
        self.defaultParams = {'header': self.HTTP_HEADER}
        if 'popcornsubtitles_url' in self.params['url_params'] and '' != self.params['url_params']['popcornsubtitles_url']:
            self.popcornsubtitlesUrl = self.params['url_params']['popcornsubtitles_url']
        else:
            self.popcornsubtitlesUrl = '' 
            
    def getSubtitles(self, cItem):
        printDBG("YoutubeComProvider.getSubtitles")
        if not self.cm.isValidUrl(self.popcornsubtitlesUrl):
            SetIPTVPlayerLastHostError(_('Wrong uri.'))
            return
        
        url = self.popcornsubtitlesUrl
        urlParams = dict(self.defaultParams)
        
        sts, tmp = self.cm.getPage(url, urlParams)
        if not sts:
            return
        
        imdbid = self.cm.ph.getSearchGroups(tmp, '/(tt[0-9]+?)[^0-9]')[0]
        tmp = self.cm.ph.getDataBeetwenMarkers(tmp, '<tbody>', '</tbody>')[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<tr', '</tr>', withMarkers=True)
        for item in tmp:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(item)
            lang = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<td', '</td>')[1])
            if self.cm.isValidUrl(url):
                params = dict(cItem)
                params.update({'title': lang, 'url': url, 'lang': lang, 'imdbid': imdbid, 'desc': title})
                self.addSubtitle(params)
            
    def _getFileName(self, title, lang, subId, imdbid):
        title = RemoveDisallowedFilenameChars(title).replace('_', '.')
        match = re.search(r'[^.]', title)
        if match:
            title = title[match.start():]

        fileName = "{0}_{1}_0_{2}_{3}".format(title, lang, subId, imdbid)
        fileName = fileName + '.srt'
        return fileName
            
    def downloadSubtitleFile(self, cItem):
        printDBG("downloadSubtitleFile")
        retData = {}
        title = cItem['title']
        lang = cItem['lang']
        subId = cItem.get('sub_id', '0')
        imdbid = cItem['imdbid']
        fileName = self._getFileName(title, lang, subId, imdbid)
        fileName = GetSubtitlesDir(fileName)
        
        tmpFile = GetTmpDir(self.TMP_FILE_NAME)
        
        urlParams = dict(self.defaultParams)
        sts, data = self.cm.getPage(cItem['url'], urlParams)
        if not sts:
            SetIPTVPlayerLastHostError(_('Failed to page with subtitle link.'))
            return retData
        
        url = self.cm.ph.getSearchGroups(data, '''<meta[^>]+?refresh[^>]+?(https?://[^"^']+?)['"]''')[0]
        urlParams['max_data_size'] = self.getMaxFileSize()
        sts, data = self.cm.getPage(url, urlParams)
        if not sts:
            SetIPTVPlayerLastHostError(_('Failed to download subtitle.'))
            return retData
        
        try:
            with open(tmpFile, 'w') as f:
                f.write(data)
        except Exception:
            printExc()
            SetIPTVPlayerLastHostError(_('Failed to write file "%s".') % tmpFile)
            return retData
        
        printDBG(">>")
        printDBG(tmpFile)
        printDBG(fileName)
        printDBG("<<")
        
        def __cleanFiles(all=False):
            if all:
                rm(fileName)
            rm(tmpFile)
        
        # detect encoding
        cmd = '%s "%s"' % (config.plugins.iptvplayer.uchardetpath.value, tmpFile)
        ret = self.iptv_execute(cmd)
        if ret['sts'] and 0 == ret['code']:
            encoding = MapUcharEncoding(ret['data'])
            if 0 != ret['code'] or 'unknown' in encoding:
                encoding = ''
            else:
                encoding = encoding.strip()
        else:
            encoding = ''
        
        # convert file to UTF-8
        try:
            with open(tmpFile) as f:
                data = f.read()
            try:
                data = data.decode(encoding).encode('UTF-8')
                try:
                    with open(fileName, 'w') as f:
                        f.write(data)
                    retData = {'title': title, 'path': fileName, 'lang': lang, 'imdbid': imdbid, 'sub_id': subId}
                except Exception:
                    printExc()
                    SetIPTVPlayerLastHostError(_('Failed to write the file "%s".') % fileName)
            except Exception:
                printExc()
                SetIPTVPlayerLastHostError(_('Failed to convert the file "%s" to UTF-8.') % tmpFile)
        except Exception: 
            printExc()
            SetIPTVPlayerLastHostError(_('Failed to open the file "%s".') % tmpFile)
        
        __cleanFiles()
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
            self.getSubtitles({'name': 'category', })
        
        CBaseSubProviderClass.endHandleService(self, index, refresh)


class IPTVSubProvider(CSubProviderBase):

    def __init__(self, params={}):
        CSubProviderBase.__init__(self, YoutubeComProvider(params))
    
