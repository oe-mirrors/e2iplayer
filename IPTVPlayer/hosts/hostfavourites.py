# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import IHost, CHostBase, CBaseHostClass, CDisplayListItem, RetHost, CUrlItem, CFavItem
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import  printDBG, printExc, GetLogoDir, GetFavouritesDir, mkdirs, rm, touch
from Plugins.Extensions.IPTVPlayer.tools.iptvfavourites import IPTVFavourites
from Plugins.Extensions.IPTVPlayer.components.iptvchoicebox import IPTVChoiceBoxItem
from Plugins.Extensions.IPTVPlayer.libs.crypto.hash.md5Hash import MD5
###################################################

###################################################
# FOREIGN import
###################################################
from Tools.Directories import fileExists
try:
    import simplejson as json
except Exception:
    import json
from binascii import hexlify
from Components.config import config, ConfigYesNo, getConfigListEntry
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.favourites_use_watched_flag = ConfigYesNo(default = True)

def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Allow watched flag to be set"), config.plugins.iptvplayer.favourites_use_watched_flag))
    if config.plugins.iptvplayer.favourites_use_watched_flag.value:
        optionList.append(getConfigListEntry(_("The color of the viewed item"), config.plugins.iptvplayer.watched_item_color))
    return optionList
###################################################

def gettytul():
    return _('Favourites')

class Favourites(CBaseHostClass):
     
    def __init__(self):
        printDBG("Favourites.__init__")
        CBaseHostClass.__init__(self)
        self.helper = IPTVFavourites(GetFavouritesDir())
        self.host = None
        self.hostName = ''
        self.guestMode = False # main or guest
        self.DEFAULT_ICON_URL = 'http://sarah-bauer.weebly.com/uploads/4/2/2/3/42234635/1922500_orig.png'
        
    def _setHost(self, hostName):
        if hostName == self.hostName:
            return True
        try:
            _temp = __import__('Plugins.Extensions.IPTVPlayer.hosts.host' + hostName, globals(), locals(), ['IPTVHost'], -1)
            host = _temp.IPTVHost()
            if isinstance(host, IHost):
                self.hostName = hostName
                self.host = host
                return True
        except Exception:
            printExc()
        return False
        
    def getHostNameFromItem(self, index):
        hostName = self.currList[index]['host']
        return hostName
        
    def isQuestMode(self):
        return self.guestMode
        
    def clearQuestMode(self):
        self.guestMode = False
                
    def listGroups(self, category):
        printDBG("Favourites.listGroups")
        sts = self.helper.load()
        if not sts:
            return
        data = self.helper.getGroups()
        self.listsTab(data, {'category':category})
        
    def listFavourites(self, cItem):
        printDBG("Favourites.listFavourites")
        sts, data = self.helper.getGroupItems(cItem['group_id'])
        if not sts:
            return
        
        typesMap = {CDisplayListItem.TYPE_VIDEO: self.addVideo, 
                    CDisplayListItem.TYPE_AUDIO: self.addAudio, 
                    CDisplayListItem.TYPE_PICTURE: self.addPicture, 
                    CDisplayListItem.TYPE_ARTICLE: self.addArticle,
                    CDisplayListItem.TYPE_CATEGORY: self.addDir}
        
        for idx in range(len(data)):
            item = data[idx]
            addFun = typesMap.get(item.type, None)
            params = {'name':'item', 'title':item.name, 'host':item.hostName, 'icon':item.iconimage, 'desc':item.description, 'group_id':cItem['group_id'], 'item_idx':idx}
            if None != addFun:
                addFun(params)
        
    def getLinksForVideo(self, cItem):
        printDBG("Favourites.getLinksForVideo idx[%r]" % cItem)
        ret = RetHost(RetHost.ERROR, value = [])
        sts, data = self.helper.getGroupItems(cItem['group_id'])
        if not sts:
            return ret
        item = data[cItem['item_idx']]
        
        printDBG(">>>>>>>>>>>>>>>>>>>>>>>>>>>> [%s]" % item.resolver)
        
        if CFavItem.RESOLVER_URLLPARSER == item.resolver:
            self.host = None
            self.hostName = None
            retlist = []
            urlList = self.up.getVideoLinkExt(item.data)
            for item in urlList:
                name = self.host.cleanHtmlStr( item["name"] )
                url  = item["url"]
                retlist.append(CUrlItem(name, url, 0))
            ret = RetHost(RetHost.OK, value = retlist)
        elif CFavItem.RESOLVER_DIRECT_LINK == item.resolver:
            self.host = None
            self.hostName = None
            retlist = []
            retlist.append(CUrlItem('direct link', item.data, 0))
            ret = RetHost(RetHost.OK, value = retlist)
        else:
            if self._setHost(item.resolver):
                ret = self.host.getLinksForFavourite(item)
        return ret
        
    def getResolvedURL(self, url):
        try:
            return self.host.getResolvedURL(url)
        except Exception:
            return RetHost(RetHost.ERROR, value = [])

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('Favourites.handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name     = self.currItem.get("name", None)
        category = self.currItem.get("category", '')
        self.currList = [] 

        self.guestMode = False
        if None == name:
            self.host = None
            self.hostName = None
            self.listGroups('list_favourites')
        elif 'list_favourites' == category:
            self.listFavourites(self.currItem)
        elif 'host' in self.currItem:
            sts, data = self.helper.getGroupItems(self.currItem['group_id'])
            if sts:
                item = data[self.currItem['item_idx']]
                if self._setHost(self.currItem['host']):
                    ret = self.host.setInitFavouriteItem(item)
                    if RetHost.OK == ret.status:
                        self.guestMode = True
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)
        
    def prepareGuestHostItem(self, index):
        ret = False
        try:
            cItem = self.currList[index]
            sts, data = self.helper.getGroupItems(cItem['group_id'])
            if sts:
                item = data[cItem['item_idx']]
                if self._setHost(cItem['host']):
                    ret = self.host.setInitFavouriteItem(item)
                    if RetHost.OK == ret.status: 
                        ret = True
        except Exception:
            printExc()
        return ret
        
    def getCurrentGuestHost(self):
        return self.host
        
    def getCurrentGuestHostName(self):
        return self.hostName

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Favourites(), False, [])
        self.cachedRet = None
        self.useWatchedFlag = config.plugins.iptvplayer.favourites_use_watched_flag.value
        self.refreshAfterWatchedFlagChange = False
        
    def getItemHashData(self, index, displayItem):
        if self.host.isQuestMode(): 
            hostName = str(self.host.getCurrentGuestHostName())
        else:
            hostName = str(self.host.getHostNameFromItem(index))
        
        ret = None
        if hostName not in [None, '']:
            # prepare item hash
            hashAlg = MD5()
            hashData = ('%s_%s' % (str(displayItem.name), str(displayItem.type)))
            hashData = hexlify(hashAlg(hashData))
            return (hostName, hashData)
        return ret
    
    def isItemWatched(self, index, displayItem):
        ret = self.getItemHashData(index, displayItem)
        if ret != None:
            return fileExists( GetFavouritesDir('IPTVWatched/%s/.%s.iptvhash' % ret) )
        else:
            return False
            
    def fixWatchedFlag(self, ret):
        if self.useWatchedFlag:
            # check watched flag from hash
            for idx in range(len(ret.value)):
                if ret.value[idx].type in [CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO] and not ret.value[idx].isWatched:
                    if self.isItemWatched(idx, ret.value[idx]):
                        ret.value[idx].isWatched = True
                        ret.value[idx].name = ret.value[idx].name
            self.cachedRet = ret
        return ret
        
    def _createViewedFile(self, hashData):
        if hashData != None and mkdirs( GetFavouritesDir('IPTVWatched') + ('/%s/' % hashData[0]) ):
            flagFilePath = GetFavouritesDir('IPTVWatched/%s/.%s.iptvhash' % hashData)
            if touch(flagFilePath):
                return True
        return False
        
    def markItemAsViewed(self, Index = 0):
        retCode = RetHost.ERROR
        retlist = []
        if self.useWatchedFlag:
            ret = self.cachedRet
            if ret.value[Index].isWatched != True and ret.value[Index].type in [CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO]:
                hashData = self.getItemHashData(Index, ret.value[Index])
                if self._createViewedFile(hashData):
                    self.cachedRet.value[Index].isWatched = True
                    retCode = RetHost.OK
                    retlist = ['refresh']
                    self.refreshAfterWatchedFlagChange = True
        return RetHost(retCode, value = retlist)
    
    def getCustomActions(self, Index = 0):
        retCode = RetHost.ERROR
        retlist = []
        if self.useWatchedFlag:
            ret = self.cachedRet
            if ret.value[Index].type in [CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO]:
                tmp = self.getItemHashData(Index, ret.value[Index])
                if tmp != '':
                    if self.cachedRet.value[Index].isWatched:
                        params = IPTVChoiceBoxItem(_('Unset watched'), "", {'action':'unset_watched_flag', 'item_index':Index, 'hash_data':tmp})
                    else:
                        params = IPTVChoiceBoxItem(_('Set watched'), "", {'action':'set_watched_flag', 'item_index':Index, 'hash_data':tmp})
                    retlist.append(params)
                retCode = RetHost.OK
        return RetHost(retCode, value = retlist)
        
    def performCustomAction(self, privateData):
        retCode = RetHost.ERROR
        retlist = []
        if self.useWatchedFlag:
            hashData = privateData['hash_data']
            Index = privateData['item_index']
            if privateData['action'] == 'unset_watched_flag':
                flagFilePath = GetFavouritesDir('IPTVWatched/%s/.%s.iptvhash' % hashData)
                if rm(flagFilePath):
                    self.cachedRet.value[Index].isWatched = False
                    retCode = RetHost.OK
            elif privateData['action'] == 'set_watched_flag':
                if self._createViewedFile(hashData):
                    self.cachedRet.value[Index].isWatched = True
                    retCode = RetHost.OK
            
            if retCode == RetHost.OK:
                self.refreshAfterWatchedFlagChange = True
                retlist = ['refresh']
        
        return RetHost(retCode, value=retlist)
        
    def getLogoPath(self):
        return RetHost(RetHost.OK, value = [GetLogoDir('favouriteslogo.png')])

    def getLinksForVideo(self, Index = 0, selItem = None):
        if self.host.isQuestMode(): 
            return self.host.getCurrentGuestHost().getLinksForVideo(Index)
        else:
            listLen = len(self.host.currList)
            if listLen < Index and listLen > 0:
                printDBG( "ERROR getLinksForVideo - current list is to short len: %d, Index: %d" % (listLen, Index) )
                return RetHost(RetHost.ERROR, value = [])
            
            if self.host.currList[Index]["type"] not in ['audio', 'video', 'picture']:
                printDBG( "ERROR getLinksForVideo - current item has wrong type" )
                return RetHost(RetHost.ERROR, value = [])
            return self.host.getLinksForVideo(self.host.currList[Index])
    # end getLinksForVideo
        
    def getResolvedURL(self, url):
        if self.host.isQuestMode(): 
            return self.host.getCurrentGuestHost().getResolvedURL(url)
        else:
            return self.host.getResolvedURL(url)
    
    def getListForItem(self, Index = 0, refresh = 0, selItem = None):
        guestIndex = Index
        ret = RetHost(RetHost.ERROR, value = [])
        if not self.host.isQuestMode(): 
            ret = CHostBase.getListForItem(self, Index, refresh)
            guestIndex = 0
        if self.host.isQuestMode(): 
            ret = self.host.getCurrentGuestHost().getListForItem(guestIndex, refresh)
            for idx in range(len(ret.value)):
                ret.value[idx].isGoodForFavourites = False
        
        self.fixWatchedFlag(ret)
        return ret

    def getPrevList(self, refresh = 0):
        ret = RetHost(RetHost.ERROR, value = [])
        if not self.host.isQuestMode() or len(self.host.getCurrentGuestHost().listOfprevList) <= 1:
            if self.host.isQuestMode():
                self.host.clearQuestMode()
            ret = CHostBase.getPrevList(self, refresh)
        else:
            ret = self.host.getCurrentGuestHost().getPrevList(refresh)
            for idx in range(len(ret.value)):
                ret.value[idx].isGoodForFavourites = False
        self.fixWatchedFlag(ret)
        return ret

    def getCurrentList(self, refresh = 0):
        if refresh == 1 and self.refreshAfterWatchedFlagChange and self.cachedRet != None:
            ret = self.cachedRet
        else: 
            ret = RetHost(RetHost.ERROR, value = [])
            if not self.host.isQuestMode(): 
                ret = CHostBase.getCurrentList(self, refresh)
            if self.host.isQuestMode(): 
                ret = self.host.getCurrentGuestHost().getCurrentList(refresh)
                for idx in range(len(ret.value)):
                    ret.value[idx].isGoodForFavourites = False
            self.fixWatchedFlag(ret)
        self.refreshAfterWatchedFlagChange = False
        return ret
        
    def getMoreForItem(self, Index = 0):
        ret = RetHost(RetHost.ERROR, value = [])
        if not self.host.isQuestMode(): 
            ret = CHostBase.getMoreForItem(self, Index)
        if self.host.isQuestMode(): 
            ret = self.host.getCurrentGuestHost().getMoreForItem(Index)
            for idx in range(len(ret.value)):
                ret.value[idx].isGoodForFavourites = False
        self.fixWatchedFlag(ret)
        return ret
    
    def getArticleContent(self, Index = 0):
        retCode = RetHost.ERROR
        retlist = []
        guestIndex = Index
        callQuestHost = True
        if not self.host.isQuestMode():
            callQuestHost = self.host.prepareGuestHostItem(Index)
            guestIndex = 0
        if callQuestHost: 
            return self.host.getCurrentGuestHost().getArticleContent(guestIndex)
        return RetHost(retCode, value = retlist)
        
        
