# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, IsExecutable, printExc, byteify
from Plugins.Extensions.IPTVPlayer.tools.iptvfilehost import IPTVFileHost
from Plugins.Extensions.IPTVPlayer.libs.youtubeparser import YouTubeParser
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
###################################################

###################################################
# FOREIGN import
###################################################
try:    import json
except Exception: import simplejson as json
import  re, urllib
from Components.config import config, ConfigDirectory, getConfigListEntry
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.Sciezkaurllist = ConfigDirectory(default = "/hdd/")

def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Sort by:"), config.plugins.iptvplayer.ytSortBy))
    optionList.append(getConfigListEntry(_("Path to ytlist.txt, urllist.txt"), config.plugins.iptvplayer.Sciezkaurllist))
    optionList.append(getConfigListEntry(_("Video format:"), config.plugins.iptvplayer.ytformat))
    optionList.append(getConfigListEntry(_("Default video quality:"), config.plugins.iptvplayer.ytDefaultformat))
    optionList.append(getConfigListEntry(_("Use default video quality:"), config.plugins.iptvplayer.ytUseDF))
    optionList.append(getConfigListEntry(_("Age-gate bypass:"), config.plugins.iptvplayer.ytAgeGate))
    if config.plugins.iptvplayer.remember_last_position.value != 'false': 
        optionList.append(getConfigListEntry(_("Ignore remember last watched position:"), config.plugins.iptvplayer.remember_last_position_ignore))
    # temporary, the ffmpeg must be in right version to be able to merge file without transcoding
    # checking should be moved to setup
    if IsExecutable('ffmpeg'): 
        optionList.append(getConfigListEntry(_("Allow dash format:"), config.plugins.iptvplayer.ytShowDash))
        if config.plugins.iptvplayer.ytShowDash.value != 'false':
            optionList.append(getConfigListEntry(_("Allow VP9 codec:"), config.plugins.iptvplayer.ytVP9))
    return optionList
###################################################
###################################################

def gettytul():
    return 'https://youtube.com/'

class Youtube(CBaseHostClass):
    
    def __init__(self):
        printDBG("Youtube.__init__")
        CBaseHostClass.__init__(self, {'history':'ytlist', 'cookie':'youtube.cookie'})
        self.UTLIST_FILE      = 'ytlist.txt'
        self.DEFAULT_ICON_URL = 'http://www.mm229.com/images/youtube-button-psd-450203.png'
        self.MAIN_GROUPED_TAB = [{'category': 'from_file',             'title': _("User links"),     'desc': _("User links stored in the ytlist.txt file.")}, \
                                 {'category': 'search',                'title': _("Search"),         'desc': _("Search youtube materials "), 'search_item':True}, \
                                 {'category': 'search_history',        'title': _("Search history"), 'desc': _("History of searched phrases.")}]
        self.SEARCH_TYPES = [  (_("Video"),    "video"   ), 
                               (_("Channel"),  "channel" ),
                               (_("Playlist"), "playlist"),
                               (_("Movie"),    "movie"   ),
                               (_("Live"),     "live"    ) ]
                              #("Program",            "show"    ),
                              #("traylist",           "traylist"),
        self.ytp = YouTubeParser()
        self.currFileHost = None
        
    def _getCategory(self, url):
        printDBG("Youtube._getCategory")
        if '/playlist?list=' in url:
            category = 'playlist'
        elif url.split('?')[0].endswith('/playlists'):
            category = 'playlists'
        elif None != re.search('/watch\?v=[^\&]+?\&list=',  url):
            category = 'traylist'
        elif 'user/' in url or ('channel/' in url and not url.endswith('/live')):
            category = 'channel'
        else:
            category = 'video'
        return category
        
    def listsMainMenu(self):
        printDBG("Youtube.listsMainMenu")
        for item in self.MAIN_GROUPED_TAB:
            params = {'name': 'category'}
            params.update(item)
            self.addDir(params)
        
    def listCategory(self, cItem, searchMode=False):
        printDBG("Youtube.listCategory cItem[%s]" % cItem)
        
        sortList = True
        filespath = config.plugins.iptvplayer.Sciezkaurllist.value
        groupList = True
        if 'sub_file_category'  not in cItem:
            self.currFileHost = IPTVFileHost()
            self.currFileHost.addFile(filespath + self.UTLIST_FILE, encoding='utf-8')
            tmpList = self.currFileHost.getGroups(sortList)
            if 0 < len(tmpList):
                params = dict(cItem)
                params.update({'sub_file_category':'all', 'group': 'all', 'title':_("--All--")})
                self.addDir(params)
            for item in tmpList:
                if '' == item: title = _("--Other--")
                else:          title = item
                params = dict(cItem)
                params.update({'sub_file_category':'group', 'title':title, 'group':item})
                self.addDir(params)
        else:
            if 'all' == cItem['sub_file_category']:
                tmpList = self.currFileHost.getAllItems(sortList)
                for item in tmpList:
                    params = dict(cItem)
                    category = self._getCategory(item['url'])
                    params.update({'good_for_fav':True, 'title':item['full_title'], 'url':item['url'], 'desc': item['url'], 'category': category})
                    if 'video' == category:
                        self.addVideo(params)
                    else:
                        self.addDir(params)
            elif 'group' == cItem['sub_file_category']:
                tmpList = self.currFileHost.getItemsInGroup(cItem['group'], sortList)
                for item in tmpList:
                    if '' == item['title_in_group']:
                        title = item['full_title']
                    else:
                        title = item['title_in_group']
                    params = dict(cItem)
                    category = self._getCategory(item['url'])
                    params.update({'good_for_fav':True, 'title':title, 'url':item['url'], 'desc': item['url'], 'category': category})
                    if 'video' == category:
                        self.addVideo(params)
                    else:
                        self.addDir(params)
                        
    def listItems(self, cItem):
        printDBG('Youtube.listItems cItem[%s]' % (cItem))
        category = cItem.get("category", '')
        url      = cItem.get("url", '')
        page     = cItem.get("page", '1')
        
        if "playlists" == category:
            self.currList = self.ytp.getListPlaylistsItems(url, category, page, cItem)
        
        for idx in range(len(self.currList)):
            if self.currList[idx]['category'] in ["channel","playlist","movie","traylist"]:
                self.currList[idx]['good_for_fav'] = True
        
    def getVideos(self, cItem):
        printDBG('Youtube.getVideos cItem[%s]' % (cItem))
        
        category = cItem.get("category", '')
        url      = cItem.get("url", '')
        page     = cItem.get("page", '1')
                
        if "channel" == category:
            if -1 == url.find('browse_ajax'):
                if url.endswith('/videos'): 
                    url = url + '?flow=list&view=0&sort=dd'
                else:
                    url = url + '/videos?flow=list&view=0&sort=dd'
            self.currList = self.ytp.getVideosFromChannelList(url, category, page, cItem)
        elif "playlist" == category:
            self.currList = self.ytp.getVideosFromPlaylist(url, category, page, cItem)   
        elif "traylist" == category:
            self.currList = self.ytp.getVideosFromTraylist(url, category, page, cItem)
        else:
            printDBG('YTlist.getVideos Error unknown category[%s]' % category)
            
    def listSearchResult(self, cItem, pattern, searchType):
        page = self.currItem.get("page", '1')
        tmpList =  self.ytp.getSearchResult(urllib.quote_plus(pattern), searchType, page, 'search', config.plugins.iptvplayer.ytSortBy.value)
        for item in tmpList:
            item.update({'name':'category'})
            if 'video' == item['type']:
                self.addVideo(item)
            else:
                if item['category'] in ["channel","playlist","movie","traylist"]:
                    item['good_for_fav'] = True
                self.addDir(item)
                
    def getLinksForVideo(self, cItem):
        printDBG("Youtube.getLinksForVideo cItem[%s]" % cItem)
        urlTab = self.up.getVideoLinkExt(cItem['url'])
        if config.plugins.iptvplayer.ytUseDF.value and 0 < len(urlTab):
            return [urlTab[0]]
        return urlTab
        
    def getFavouriteData(self, cItem):
        printDBG('Youtube.getFavouriteData')
        return json.dumps(cItem)
        
    def getLinksForFavourite(self, fav_data):
        printDBG('Youtube.getLinksForFavourite')
        links = []
        try:
            cItem = byteify(json.loads(fav_data))
            links = self.getLinksForVideo(cItem)
        except Exception:
            printExc()
            return self.getLinksForVideo({'url':fav_data})
        return links

    def setInitListFromFavouriteItem(self, fav_data):
        printDBG('Youtube.setInitListFromFavouriteItem')
        try:
            params = byteify(json.loads(fav_data))
        except Exception: 
            params = {}
            printExc()
        self.addDir(params)
        return True

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('Youtube.handleService start')
        
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        
        name     = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG( "Youtube.handleService: ---------> name[%s], category[%s] " % (name, category) )
        self.currList = []
        
        if None == name:
            self.listsMainMenu()
        elif 'from_file' == category :
            self.listCategory(self.currItem)
        elif category in ["channel","playlist","movie","traylist"]:
            self.getVideos(self.currItem)
        elif category == 'playlists':
            self.listItems(self.currItem)
    #SEARCH
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item':False, 'name':'category'}) 
            self.listSearchResult(cItem, searchPattern, searchType)
    #HISTORIA SEARCH
        elif category == "search_history":
            self.listsHistory({'name':'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()
        
        CBaseHostClass.endHandleService(self, index, refresh)

    def getSuggestionsProvider(self, index):
        printDBG('Youtube.getSuggestionsProvider')
        from Plugins.Extensions.IPTVPlayer.suggestions.google import SuggestionsProvider
        return SuggestionsProvider(True)

class IPTVHost(CHostBase):
    
    def getSearchTypes(self):
        return self.host.SEARCH_TYPES
    
    def __init__(self):
        CHostBase.__init__(self, Youtube(), True, [CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO])

