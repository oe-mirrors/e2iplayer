# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem, RetHost, CUrlItem
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, GetLogoDir
from Plugins.Extensions.IPTVPlayer.tools.iptvfilehost import IPTVFileHost
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, getF4MLinksWithMeta, getMPDLinksWithMeta
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
from Plugins.Extensions.IPTVPlayer.libs import ph
###################################################

###################################################
# FOREIGN import
###################################################
from Components.config import config, ConfigYesNo, ConfigDirectory, getConfigListEntry
from os.path import normpath
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.Sciezkaurllist = ConfigDirectory(default="/hdd/")
config.plugins.iptvplayer.grupujurllist = ConfigYesNo(default=True)
config.plugins.iptvplayer.sortuj = ConfigYesNo(default=True)

def GetConfigList():
    optionList = [] 
    optionList.append(getConfigListEntry(_('Text files ytlist and urllist are in:'), config.plugins.iptvplayer.Sciezkaurllist))
    optionList.append(getConfigListEntry(_('Sort the list:'), config.plugins.iptvplayer.sortuj))
    optionList.append(getConfigListEntry(_('Group links into categories: '), config.plugins.iptvplayer.grupujurllist))
    return optionList
###################################################

def gettytul():
    return _('Urllists player')

class Urllist(CBaseHostClass):
    URLLIST_FILE = 'urllist.txt'
    URRLIST_STREAMS = 'urllist.stream'
    URRLIST_USER = 'urllist.user'

    def __init__(self):
        printDBG("Urllist.__init__")
        path = config.plugins.iptvplayer.Sciezkaurllist.value + '/'
        
        self.MAIN_GROUPED_TAB = [{'category': 'all', 'title': _("All in one"), 'desc': _("Links from all files without categories"), 'icon':'https://mikeharwood.files.wordpress.com/2011/01/all-in-one-logo-on-blue.jpg'}]
        self.MAIN_GROUPED_TAB.extend([{'category': Urllist.URLLIST_FILE, 'title': _("Videos"), 'desc': _("Links from the file %s") % normpath(path + 'urllist.txt'), 'icon':'https://st2.depositphotos.com/3000465/12281/v/950/depositphotos_122812390-stock-illustration-video-play-sign-with-letter.jpg'},
                                       {'category': Urllist.URRLIST_STREAMS, 'title': _("Live streams"), 'desc': _("Links from the file %s") % normpath(path + 'urllist.stream'), 'icon':'http://asiamh.ru.images.1c-bitrix-cdn.ru/images/media_logo.jpg?136879146733721'},
                                       {'category': Urllist.URRLIST_USER, 'title': _("User files"), 'desc': _("Links from the file %s") % normpath(path + 'urllist.user'), 'icon':'http://kinovesti.ru/uploads/posts/2014-12/1419918660_1404722920_02.jpg'}])
        CBaseHostClass.__init__(self)
        self.currFileHost = None

    def _getHostingName(self, url):
        if 0 != self.up.checkHostSupport(url):
            return self.up.getHostName(url)
        elif self._uriIsValid(url):
            return (_('direct link'))
        else:
            return (_('unknown'))

    def _uriIsValid(self, url):
        return '://' in url

    def listCategory(self, cItem, searchMode=False):
        printDBG("Urllist.listCategory cItem[%s]" % cItem)
        
        sortList = config.plugins.iptvplayer.sortuj.value
        filespath = config.plugins.iptvplayer.Sciezkaurllist.value
        groupList = config.plugins.iptvplayer.grupujurllist.value
        if cItem['category'] in ['all', Urllist.URLLIST_FILE, Urllist.URRLIST_STREAMS, Urllist.URRLIST_USER]:
            self.currFileHost = IPTVFileHost()
            
            if cItem['category'] in ['all', Urllist.URLLIST_FILE]: 
                self.currFileHost.addFile(filespath + Urllist.URLLIST_FILE, encoding='utf-8')
            if cItem['category'] in ['all', Urllist.URRLIST_STREAMS]: 
                self.currFileHost.addFile(filespath + Urllist.URRLIST_STREAMS, encoding='utf-8')
            if cItem['category'] in ['all', Urllist.URRLIST_USER]:
                self.currFileHost.addFile(filespath + Urllist.URRLIST_USER, encoding='utf-8')
            
            if 'all' != cItem['category'] and groupList:
                tmpList = self.currFileHost.getGroups(sortList)
                for item in tmpList:
                    if '' == item:
                        title = (_("Other"))
                    else:
                        title = item
                    params = {'name': 'category', 'category':'group', 'title':title, 'group':item}
                    self.addDir(params)
            else:
                tmpList = self.currFileHost.getAllItems(sortList)
                for item in tmpList:
                    desc = (_("Hosting: %s, %s")) % (self._getHostingName(item['url']), item['url'])
                    if item['desc'] != '':
                        desc = item['desc']
                    params = {'title':item['full_title'], 'url':item['url'], 'desc':desc, 'icon':item['icon']}
                    self.addVideo(params)
        elif 'group' in cItem:
            tmpList = self.currFileHost.getItemsInGroup(cItem['group'], sortList)
            for item in tmpList:
                if '' == item['title_in_group']:
                    title = item['full_title']
                else:
                    title = item['title_in_group']
                desc = (_("Hosting: %s, %s")) % (self._getHostingName(item['url']), item['url'])
                if item.get('desc', '') != '':
                    desc = item['desc']
                params = {'title':title, 'url':item['url'], 'desc': desc, 'icon':item.get('icon', '')}
                self.addVideo(params)
                
    def getLinksForVideo(self, cItem):
        printDBG("Urllist.getLinksForVideo url[%s]" % cItem['url'])
        videoUrls = []
        uri = urlparser.decorateParamsFromUrl(cItem['url'])
        protocol = uri.meta.get('iptv_proto', '')
        
        printDBG("PROTOCOL [%s] " % protocol)
        
        urlSupport = self.up.checkHostSupport(uri)
        if 1 == urlSupport:
            retTab = self.up.getVideoLinkExt(uri)
            videoUrls.extend(retTab)
        elif 0 == urlSupport and self._uriIsValid(uri):
            if protocol == 'm3u8':
                retTab = getDirectM3U8Playlist(uri, checkExt=False, checkContent=True)
                videoUrls.extend(retTab)
            elif protocol == 'f4m':
                retTab = getF4MLinksWithMeta(uri)
                videoUrls.extend(retTab)
            elif protocol == 'mpd':
                retTab = getMPDLinksWithMeta(uri, False)
                videoUrls.extend(retTab)
            else:
                videoUrls.append({'name':'direct link', 'url':uri})
        return videoUrls
    
    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('Urllist.handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", None)
        category = self.currItem.get("category", '')
        printDBG("Urllist.handleService: ---------> name[%s], category[%s] " % (name, category))
        self.currList = []
        
        if None == name:
            self.listsTab(self.MAIN_GROUPED_TAB, self.currItem)
        else:
            self.listCategory(self.currItem)
        
        CBaseHostClass.endHandleService(self, index, refresh)

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Urllist(), True)
        
    def _isPicture(self, url):
        def _checkExtension(url): 
            return url.endswith(".jpeg") or url.endswith(".jpg") or url.endswith(".png")
        if _checkExtension(url):
            return True
        if _checkExtension(url.split('|')[0]):
            return True
        if _checkExtension(url.split('?')[0]):
            return True
        return False

    def getLogoPath(self):
        return RetHost(RetHost.OK, value=[GetLogoDir('urllistlogo.png')])

    def getLinksForVideo(self, Index=0, selItem=None):
        listLen = len(self.host.currList)
        if listLen < Index and listLen > 0:
            printDBG("ERROR getLinksForVideo - current list is to short len: %d, Index: %d" % (listLen, Index))
            return RetHost(RetHost.ERROR, value=[])
        
        if self.host.currList[Index]["type"] != 'video':
            printDBG("ERROR getLinksForVideo - current item has wrong type")
            return RetHost(RetHost.ERROR, value=[])

        retlist = []
        uri = self.host.currList[Index].get('url', '')
        if not self._isPicture(uri):
            urlList = self.host.getLinksForVideo(self.host.currList[Index])
            for item in urlList:
                retlist.append(CUrlItem(item["name"], item["url"], 0))
        else:
            retlist.append(CUrlItem('picture link', urlparser.decorateParamsFromUrl(uri, True), 0))

        return RetHost(RetHost.OK, value=retlist)
    # end getLinksForVideo

    def convertList(self, cList):
        hostList = []
        searchTypesOptions = [] # ustawione alfabetycznie
        #searchTypesOptions.append(("Filmy", "filmy"))
        #searchTypesOptions.append(("Seriale", "seriale"))
    
        for cItem in cList:
            hostLinks = []
            type = CDisplayListItem.TYPE_UNKNOWN
            possibleTypesOfSearch = None

            if cItem['type'] == 'category':
                if cItem['title'] == 'Wyszukaj':
                    type = CDisplayListItem.TYPE_SEARCH
                    possibleTypesOfSearch = searchTypesOptions
                else:
                    type = CDisplayListItem.TYPE_CATEGORY
            elif cItem['type'] == 'video':
                type = CDisplayListItem.TYPE_VIDEO
                url = cItem.get('url', '')
                if self._isPicture(url):
                    type = CDisplayListItem.TYPE_PICTURE
                else:
                    type = CDisplayListItem.TYPE_VIDEO
                if '' != url:
                    hostLinks.append(CUrlItem("Link", url, 1))
                
            title = cItem.get('title', '')
            description = ph.clean_html(cItem.get('desc', ''))
            icon = cItem.get('icon', '')
            
            hostItem = CDisplayListItem(name=title,
                                        description=description,
                                        type=type,
                                        urlItems=hostLinks,
                                        urlSeparateRequest=1,
                                        iconimage=icon,
                                        possibleTypesOfSearch=possibleTypesOfSearch)
            hostList.append(hostItem)

        return hostList
    # end convertList

    def getSearchItemInx(self):
        # Find 'Wyszukaj' item
        try:
            list = self.host.getCurrList()
            for i in range(len(list)):
                if list[i]['category'] == 'Wyszukaj':
                    return i
        except Exception:
            printDBG('getSearchItemInx EXCEPTION')
            return -1

    def setSearchPattern(self):
        try:
            list = self.host.getCurrList()
            if 'history' == list[self.currIndex]['name']:
                pattern = list[self.currIndex]['title']
                search_type = list[self.currIndex]['search_type']
                self.host.history.addHistoryItem(pattern, search_type)
                self.searchPattern = pattern
                self.searchType = search_type
        except Exception:
            printDBG('setSearchPattern EXCEPTION')
            self.searchPattern = ''
            self.searchType = ''
        return
