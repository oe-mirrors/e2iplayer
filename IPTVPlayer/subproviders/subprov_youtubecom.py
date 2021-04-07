# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.isubprovider import CSubProviderBase, CBaseSubProviderClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetDefaultLang, \
                                                          RemoveDisallowedFilenameChars, GetSubtitlesDir, rm
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
        self.MAIN_URL = 'http://youtube.com/'
        self.USER_AGENT = 'Mozilla/5.0 (X11; Linux i686) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/37.0.2062.120 Chrome/37.0.2062.120 Safari/537.36'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'Referer': self.MAIN_URL, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Encoding': 'gzip, deflate'}

        params['cookie'] = 'youtubecom.cookie'
        CBaseSubProviderClass.__init__(self, params)
        
        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        if 'youtube_id' in self.params['url_params'] and '' != self.params['url_params']['youtube_id']:
            self.youtubeId = self.params['url_params']['youtube_id']
        else:
            self.youtubeId = '' 
            
    def getSubtitles(self, cItem):
        printDBG("YoutubeComProvider.getSubtitles")
        if '' == self.youtubeId:
            SetIPTVPlayerLastHostError(_('The YouTube video ID is invalid.'))
            return
        from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.extractor.youtube import YoutubeIE
        
        ytExtractor = YoutubeIE()
        # get normal langs
        tab = ytExtractor._get_subtitles(self.youtubeId)
        tab2 = ytExtractor._get_automatic_captions(self.youtubeId)
        for item in tab2:
            item['title'] = '[%s] %s' % (_('Auto-translate'), item['title'])  
            tab.append(item)
        defaultLang = GetDefaultLang()
        promotedItem = None
        for item in tab:
            params = dict(item)
            if None == promotedItem and defaultLang == params['lang']:
                promotedItem = params
            else:
                self.addSubtitle(params)
        if None != promotedItem:
            self.addSubtitle(promotedItem, False)
            
    def _getFileName(self, title, lang, subId, ytid):
        title = RemoveDisallowedFilenameChars(title).replace('_', '.')
        match = re.search(r'[^.]', title)
        if match:
            title = title[match.start():]

        fileName = "{0}_{1}_0_{2}_{3}".format(title, lang, subId, ytid)
        fileName = fileName + '.vtt'
        return fileName
            
    def downloadSubtitleFile(self, cItem):
        printDBG("YoutubeComProvider.downloadSubtitleFile")
        retData = {}
        title = cItem['title']
        lang = cItem['lang']
        subId = cItem.get('ytid', '0')
        fileName = self._getFileName(title, lang, subId, self.youtubeId)
        fileName = GetSubtitlesDir(fileName)
        
        urlParams = dict(self.defaultParams)
        urlParams['max_data_size'] = self.getMaxFileSize()
        sts, data = self.cm.getPage(cItem['url'], urlParams)
        if not sts:
            SetIPTVPlayerLastHostError(_('Failed to download subtitle.'))
            return retData
        
        try:
            with open(fileName, 'w') as f:
                f.write(data)
        except Exception:
            printExc()
            SetIPTVPlayerLastHostError(_('Failed to write file "%s".') % fileName)
            rm(fileName)
            return retData
        
        printDBG(">>")
        printDBG(fileName)
        printDBG("<<")
        retData = {'title': title, 'path': fileName, 'lang': lang, 'ytid': self.youtubeId, 'sub_id': subId}
        
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
            self.getSubtitles({'name': 'category', })
        
        CBaseSubProviderClass.endHandleService(self, index, refresh)

class IPTVSubProvider(CSubProviderBase):

    def __init__(self, params={}):
        CSubProviderBase.__init__(self, YoutubeComProvider(params))
    
