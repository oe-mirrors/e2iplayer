# -*- coding: utf-8 -*-
# Last Modified: 22.06.2025
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import IHost, CHostBase, CBaseHostClass, CDisplayListItem, RetHost, CUrlItem, CFavItem
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetLogoDir, GetFavouritesDir, mkdirs, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvfavourites import IPTVFavourites
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.components.iptvchoicebox import IPTVChoiceBoxItem
from Plugins.Extensions.IPTVPlayer.libs.crypto.hash.md5Hash import MD5
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.pVer import isPY2
###################################################
# FOREIGN import
###################################################
from Tools.Directories import fileExists
try:
    import simplejson as json
except Exception:
    import json
from binascii import hexlify
from Components.config import config
###################################################


def GetConfigList():
    # "Allow watched flag to be set" / "The color of the viewed item" now live in the
    # global E2iPlayer settings (components/iptvconfigmenu.py), not per-host
    return []
###################################################


def gettytul():
    return _("Favorites")


class Favourites(CBaseHostClass):

    def __init__(self):
        printDBG("Favourites.__init__")
        CBaseHostClass.__init__(self)
        self.helper = IPTVFavourites(GetFavouritesDir())
        self.host = None
        self.hostName = ''
        self.guestMode = False  # main or guest
        self.DEFAULT_ICON_URL = "https://raw.githubusercontent.com/oe-mirrors/e2iplayer/refs/heads/gh-pages/icons/favourites.png"
        self._guestParentWatchedHelper = IPTVWatchedHelper('favourites')

    def _setHost(self, hostName):
        if hostName == self.hostName:
            return True
        try:
            _temp = __import__('Plugins.Extensions.IPTVPlayer.hosts.host' + hostName, globals(), locals(), ['IPTVHost'], 0)  # absolute import for P3 compatybility
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
        self.listsTab(data, {'category': category})

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
            favUrl = ''
            favItem = None
            try:
                if item.resolver in (CFavItem.RESOLVER_DIRECT_LINK, CFavItem.RESOLVER_URLLPARSER):
                    favUrl = str(item.data or '')
                else:
                    favItemData = json.loads(item.data)
                    if isinstance(favItemData, dict):
                        favItem = favItemData
                        favUrl = str(favItemData.get('url', '') or '')
            except Exception:
                favUrl = ''
            params = {'name': 'item', 'title': item.name, 'host': item.hostName, 'icon': item.iconimage, 'desc': item.description, 'group_id': cItem['group_id'], 'item_idx': idx, 'fav_url': favUrl, 'fav_item': favItem}
            if None is not addFun:
                addFun(params)

    def getLinksForVideo(self, cItem):
        printDBG("Favourites.getLinksForVideo idx[%r]" % cItem)
        ret = RetHost(RetHost.ERROR, value=[])
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
                name = self.host.cleanHtmlStr(item["name"])
                url = item["url"]
                retlist.append(CUrlItem(name, url, 0))
            ret = RetHost(RetHost.OK, value=retlist)
        elif CFavItem.RESOLVER_DIRECT_LINK == item.resolver:
            self.host = None
            self.hostName = None
            retlist = []
            retlist.append(CUrlItem('direct link', item.data, 0))
            ret = RetHost(RetHost.OK, value=retlist)
        else:
            if self._setHost(item.resolver):
                ret = self.host.getLinksForFavourite(item)
        return ret

    def getResolvedURL(self, url):
        try:
            return self.host.getResolvedURL(url)
        except Exception:
            return RetHost(RetHost.ERROR, value=[])

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('Favourites.handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", None)
        category = self.currItem.get("category", '')
        self.currList = []

        self.guestMode = False
        if None is name:
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
        self._rawHostCache = {}

    def _getRawGuestHost(self, guestHost):
        # guestHost is the per-site IPTVHost wrapper; currItem/currList/_getWatchedKeyForItem
        # only exist on the raw host it wraps (guestHost.host), not on the wrapper itself
        return getattr(guestHost, 'host', None)

    def _getRawHostForName(self, hostName):
        # standalone lookup of a raw per-site host by name, independent of guest-mode
        # navigation state (Favourites.host/hostName) - used so favourites hashing can
        # call the host's own _getWatchedKeyForItem() (e.g. YouTube prefers a videoid
        # key over the url) instead of guessing a generic "url:%s" key that may not
        # match what the host itself actually uses
        hostName = str(hostName or '').strip()
        if hostName == '':
            return None
        if hostName in self._rawHostCache:
            return self._rawHostCache[hostName]
        rawHost = None
        try:
            module = __import__('Plugins.Extensions.IPTVPlayer.hosts.host' + hostName, globals(), locals(), ['IPTVHost'], 0)
            wrapper = module.IPTVHost()
            rawHost = getattr(wrapper, 'host', None)
        except Exception:
            printExc()
        self._rawHostCache[hostName] = rawHost
        return rawHost

    def _getGuestParentState(self, guestHost):
        try:
            rawGuestHost = self._getRawGuestHost(guestHost)
            if rawGuestHost is None:
                return None, []
            currItem = getattr(rawGuestHost, 'currItem', {})
            if not isinstance(currItem, dict) or not currItem:
                return None, []
            category = str(currItem.get('category', '') or '').strip()
            seriesUrl = str(currItem.get('series_url', '') or '').strip()
            seasonNum = str(currItem.get('season_num', '') or '').strip()
            if category in ['list_episodes', 'list_seasons']:
                return currItem, list(getattr(rawGuestHost, 'currList', []) or [])
            if seriesUrl != '' and seasonNum != '':
                childItems = []
                for childItem in getattr(rawGuestHost, 'currList', []) or []:
                    if isinstance(childItem, dict) and childItem.get('type', '') in ['video', 'audio']:
                        childItems.append(childItem)
                return {'category': 'list_episodes', 'url': currItem.get('url', ''), 'series_url': seriesUrl, 'season_num': seasonNum}, childItems
            if seriesUrl != '':
                childItems = []
                for childItem in getattr(rawGuestHost, 'currList', []) or []:
                    if isinstance(childItem, dict) and childItem.get('category', '') == 'list_episodes':
                        childItems.append(childItem)
                return {'category': 'list_seasons', 'url': seriesUrl}, childItems
        except Exception:
            printExc()
        return None, []

    def _syncGuestParentFavoriteState(self, ret):
        try:
            if not self.host.isQuestMode():
                return ret
            guestHost = self.host.getCurrentGuestHost()
            if guestHost is None:
                return ret
            rawGuestHost = self._getRawGuestHost(guestHost)
            keyProvider = getattr(rawGuestHost, '_getWatchedKeyForItem', None)
            if not callable(keyProvider):
                return ret
            parentItem, childItems = self._getGuestParentState(guestHost)
            if parentItem is None or len(childItems) == 0:
                return ret
            guestHost.watchedHelper.updateParentWatchedState(parentItem, childItems, keyProvider)
            parentKey = keyProvider(parentItem)
            if parentKey == '':
                return ret
            if self.cachedRet is not None and hasattr(self.cachedRet, 'value'):
                # the list shown just before navigating into the current one (where parentItem
                # itself, e.g. the season/series row, is displayed) mirrors self.cachedRet
                # positionally - use it to find the matching row by key, not by title, so that
                # two rows sharing the same display title don't get each other's state
                prevList = list(guestHost.listOfprevList[-1]) if getattr(guestHost, 'listOfprevList', None) else []
                matchIdx = -1
                for idx in range(min(len(prevList), len(self.cachedRet.value))):
                    rawItem = prevList[idx]
                    if isinstance(rawItem, dict):
                        try:
                            if keyProvider(rawItem) == parentKey:
                                matchIdx = idx
                                break
                        except Exception:
                            printExc()
                if matchIdx >= 0:
                    # updateParentWatchedState() above already wrote the marker file via
                    # guestHost.watchedHelper (same path/hash scheme as this host's own
                    # getItemHashData) - just reflect that into the cached display item,
                    # no need to (and don't) recompute/rewrite the file from here again
                    displayItem = self.cachedRet.value[matchIdx]
                    watchState = guestHost.watchedHelper.getWatchedState(parentKey)
                    displayItem.isWatched = (watchState == 'watched')
                    displayItem.isStarted = (watchState == 'started')
            return ret
        except Exception:
            printExc()
            return ret

    def _getStableItemHashSource(self, index):
        # prefer a stable url-based identity over the display title, so items with
        # identical titles (e.g. same-named episodes in different shows) don't collide
        try:
            if self.host.isQuestMode():
                guestHost = self.host.getCurrentGuestHost()
                rawGuestHost = self._getRawGuestHost(guestHost)
                keyProvider = getattr(rawGuestHost, '_getWatchedKeyForItem', None)
                guestList = getattr(rawGuestHost, 'currList', None) or []
                if callable(keyProvider) and 0 <= index < len(guestList):
                    return keyProvider(guestList[index]) or ''
            else:
                item = self.host.currList[index]
                favItem = item.get('fav_item')
                hostName = str(item.get('host', '') or '')
                if isinstance(favItem, dict) and hostName != '':
                    rawHost = self._getRawHostForName(hostName)
                    keyProvider = getattr(rawHost, '_getWatchedKeyForItem', None)
                    if callable(keyProvider):
                        key = keyProvider(favItem)
                        if key:
                            return key
                favUrl = str(item.get('fav_url', '') or '')
                if favUrl != '':
                    return 'url:%s' % favUrl
        except Exception:
            printExc()
        return ''

    def _getLegacyItemHashData(self, index, displayItem):
        # pre-stable-id hash scheme (title+type), kept only to read state written before this fix
        if self.host.isQuestMode():
            hostName = str(self.host.getCurrentGuestHostName())
        else:
            hostName = str(self.host.getHostNameFromItem(index))
        if hostName in [None, '']:
            return None
        hashAlg = MD5()
        hashData = hexlify(hashAlg('%s_%s' % (str(displayItem.name), str(displayItem.type))))
        if not isPY2():
            hashData = hashData.decode()
        return (hostName, hashData)

    def getItemHashData(self, index, displayItem):
        if self.host.isQuestMode():
            hostName = str(self.host.getCurrentGuestHostName())
        else:
            hostName = str(self.host.getHostNameFromItem(index))

        ret = None
        if hostName not in [None, '']:
            hashSrc = self._getStableItemHashSource(index)
            if hashSrc == '':
                hashSrc = '%s_%s' % (str(displayItem.name), str(displayItem.type))
            hashAlg = MD5()
            hashData = hexlify(hashAlg(hashSrc))
            if not isPY2():
                hashData = hashData.decode()
            return (hostName, hashData)
        return ret

    def _readMarkerContent(self, hashData):
        # None = no file at all, '' or any other text = watched, STARTED_MARKER = started
        if hashData is None:
            return None
        flagFilePath = GetFavouritesDir('IPTVWatched/%s/.%s.iptvhash' % hashData)
        if not fileExists(flagFilePath):
            return None
        try:
            f = open(flagFilePath, 'r')
            try:
                return f.read().strip()
            finally:
                f.close()
        except Exception:
            printExc()
        return ''

    def isItemWatched(self, index, displayItem):
        ret = self.getItemHashData(index, displayItem)
        content = self._readMarkerContent(ret)
        if content is not None:
            return content != IPTVWatchedHelper.STARTED_MARKER
        # backward compatibility: favourites marked watched before the stable-id hash existed
        legacyRet = self._getLegacyItemHashData(index, displayItem)
        legacyContent = self._readMarkerContent(legacyRet)
        if legacyRet is not None and legacyRet != ret and legacyContent is not None and legacyContent != IPTVWatchedHelper.STARTED_MARKER:
            self._createViewedFile(ret)
            return True
        return False

    def isItemStarted(self, index, displayItem):
        ret = self.getItemHashData(index, displayItem)
        return self._readMarkerContent(ret) == IPTVWatchedHelper.STARTED_MARKER

    def fixWatchedFlag(self, ret):
        if self.useWatchedFlag:
            # check watched flag from hash
            for idx in range(len(ret.value)):
                if ret.value[idx].type in [CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO] and not ret.value[idx].isWatched:
                    if self.isItemWatched(idx, ret.value[idx]):
                        ret.value[idx].isWatched = True
                        ret.value[idx].isStarted = False
                        ret.value[idx].name = ret.value[idx].name
                    elif self.isItemStarted(idx, ret.value[idx]):
                        ret.value[idx].isStarted = True
            self.cachedRet = ret
        return ret

    def _createViewedFile(self, hashData):
        if hashData is not None and mkdirs(GetFavouritesDir('IPTVWatched') + ('/%s/' % hashData[0])):
            flagFilePath = GetFavouritesDir('IPTVWatched/%s/.%s.iptvhash' % hashData)
            try:
                # write (not touch): must overwrite a possible "started" marker
                f = open(flagFilePath, 'w')
                try:
                    f.write('')
                finally:
                    f.close()
                return True
            except Exception:
                printExc()
        return False

    def markItemAsStarted(self, Index=0):
        # called from iptvplayerwidget.py's playVideo() right before a player is
        # actually opened for the item at Index - not on download, and not if
        # resolving/opening failed before getting here. Mirrors the guest/non-guest
        # host resolution used for reading state (_getStableItemHashSource) but on
        # the write side, so the real host's own watched key/helper is used instead
        # of a favourites-only mechanism.
        try:
            if not self.useWatchedFlag:
                return
            if self.host.isQuestMode():
                guestHost = self.host.getCurrentGuestHost()
                if guestHost is None:
                    return
                rawGuestHost = self._getRawGuestHost(guestHost)
                keyProvider = getattr(rawGuestHost, '_getWatchedKeyForItem', None)
                guestList = getattr(rawGuestHost, 'currList', None) or []
                if not callable(keyProvider) or not (0 <= Index < len(guestList)):
                    return
                item = guestList[Index]
                if guestHost.watchedHelper.markHostItemAsStarted(rawGuestHost, item, keyProvider):
                    propagate = getattr(rawGuestHost, '_propagateEpisodeWatchedState', None)
                    if callable(propagate):
                        propagate(item)
            else:
                if not (0 <= Index < len(self.host.currList)):
                    return
                item = self.host.currList[Index]
                favItem = item.get('fav_item')
                hostName = str(item.get('host', '') or '')
                if not isinstance(favItem, dict) or hostName == '':
                    return
                rawHost = self._getRawHostForName(hostName)
                keyProvider = getattr(rawHost, '_getWatchedKeyForItem', None)
                watchedHelper = getattr(rawHost, 'watchedHelper', None)
                if not callable(keyProvider) or watchedHelper is None:
                    return
                if watchedHelper.markHostItemAsStarted(rawHost, favItem, keyProvider):
                    propagate = getattr(rawHost, '_propagateEpisodeWatchedState', None)
                    if callable(propagate):
                        propagate(favItem)
            if self.cachedRet is not None and hasattr(self.cachedRet, 'value') and 0 <= Index < len(self.cachedRet.value):
                if not self.cachedRet.value[Index].isWatched:
                    self.cachedRet.value[Index].isStarted = True
                self.refreshAfterWatchedFlagChange = True
        except Exception:
            printExc()

    def markItemAsViewed(self, Index=0):
        retCode = RetHost.ERROR
        retlist = []
        if self.useWatchedFlag:
            ret = self.cachedRet
            if ret.value[Index].isWatched is not True and ret.value[Index].type in [CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO]:
                hashData = self.getItemHashData(Index, ret.value[Index])
                if self._createViewedFile(hashData):
                    self.cachedRet.value[Index].isWatched = True
                    self.cachedRet.value[Index].isStarted = False
                    retCode = RetHost.OK
                    retlist = ['refresh']
                    self.refreshAfterWatchedFlagChange = True
        return RetHost(retCode, value=retlist)

    def getCustomActions(self, Index=0):
        retCode = RetHost.ERROR
        retlist = []
        if self.useWatchedFlag:
            if self.host.isQuestMode():
                guestHost = self.host.getCurrentGuestHost()
                if guestHost is not None:
                    rawGuestHost = self._getRawGuestHost(guestHost)
                    guestList = getattr(rawGuestHost, 'currList', None) or []
                    # use the highlighted row, not the item the current list was opened
                    # from - otherwise MENU on any season row would always act on the
                    # whole series instead of just that season
                    rowItem = guestList[Index] if 0 <= Index < len(guestList) else None
                    category = str(rowItem.get('category', '') or '').strip() if isinstance(rowItem, dict) else ''
                    if category in ['list_episodes', 'list_seasons']:
                        keyProvider = getattr(rawGuestHost, '_getWatchedKeyForItem', None)
                        if callable(keyProvider):
                            watchedKey = keyProvider(rowItem)
                            if watchedKey != '':
                                state = guestHost.watchedHelper.getWatchedState(watchedKey)
                                isWatched = (state == 'watched')
                                isStarted = (state == 'started')
                                # a "started" item isn't fully watched yet, so offer both
                                # promoting it to watched and clearing it entirely
                                if not isWatched:
                                    retlist.append(IPTVChoiceBoxItem(_('Set watched'), "", {'action': 'set_watched_flag', 'guest_parent_category': category, 'guest_item_index': Index, 'guest_item': rowItem, 'watched_key': watchedKey}))
                                if isWatched or isStarted:
                                    retlist.append(IPTVChoiceBoxItem(_('Unset watched'), "", {'action': 'unset_watched_flag', 'guest_parent_category': category, 'guest_item_index': Index, 'guest_item': rowItem, 'watched_key': watchedKey}))
                                if retlist:
                                    retCode = RetHost.OK
            if retCode != RetHost.OK:
                ret = self.cachedRet
                if ret.value[Index].type in [CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO]:
                    tmp = self.getItemHashData(Index, ret.value[Index])
                    if tmp != '':
                        isWatched = bool(self.cachedRet.value[Index].isWatched)
                        isStarted = bool(getattr(self.cachedRet.value[Index], 'isStarted', False))
                        if not isWatched:
                            retlist.append(IPTVChoiceBoxItem(_('Set watched'), "", {'action': 'set_watched_flag', 'item_index': Index, 'hash_data': tmp}))
                        if isWatched or isStarted:
                            retlist.append(IPTVChoiceBoxItem(_('Unset watched'), "", {'action': 'unset_watched_flag', 'item_index': Index, 'hash_data': tmp}))
                    retCode = RetHost.OK
        return RetHost(retCode, value=retlist)

    def performCustomAction(self, privateData):
        retCode = RetHost.ERROR
        retlist = []
        if self.useWatchedFlag:
            if privateData.get('guest_parent_category') in ['list_episodes', 'list_seasons']:
                guestHost = self.host.getCurrentGuestHost()
                if guestHost is not None:
                    rawGuestHost = self._getRawGuestHost(guestHost)
                    category = privateData.get('guest_parent_category', '')
                    action = privateData.get('action', '')
                    currItem = privateData.get('guest_item')
                    if not isinstance(currItem, dict) or not currItem:
                        currList = getattr(rawGuestHost, 'currList', []) or []
                        guestIndex = int(privateData.get('guest_item_index', 0) or 0)
                        if 0 <= guestIndex < len(currList):
                            currItem = currList[guestIndex]
                    if category == 'list_episodes':
                        setter = getattr(guestHost, '_setWatchedStateForSeasonItem', None)
                        if callable(setter):
                            changed = setter(currItem, action)
                            if changed:
                                retCode = RetHost.OK
                    elif category == 'list_seasons':
                        setter = getattr(guestHost, '_setWatchedStateForSeriesItem', None)
                        if callable(setter):
                            changed = setter(currItem, action)
                            if changed:
                                retCode = RetHost.OK
                    if retCode == RetHost.OK:
                        try:
                            self._syncGuestParentFavoriteState(self.host.getCurrentGuestHost().getCurrentList())
                        except Exception:
                            printExc()
                        retlist = ['refresh']
                        self.refreshAfterWatchedFlagChange = True
            else:
                hashData = privateData['hash_data']
                Index = privateData['item_index']
                if privateData['action'] == 'unset_watched_flag':
                    flagFilePath = GetFavouritesDir('IPTVWatched/%s/.%s.iptvhash' % hashData)
                    if rm(flagFilePath):
                        self.cachedRet.value[Index].isWatched = False
                        self.cachedRet.value[Index].isStarted = False
                        retCode = RetHost.OK
                elif privateData['action'] == 'set_watched_flag':
                    if self._createViewedFile(hashData):
                        self.cachedRet.value[Index].isWatched = True
                        self.cachedRet.value[Index].isStarted = False
                        retCode = RetHost.OK

                if retCode == RetHost.OK:
                    self.refreshAfterWatchedFlagChange = True
                    retlist = ['refresh']

        return RetHost(retCode, value=retlist)

    def getLogoPath(self):
        return RetHost(RetHost.OK, value=[GetLogoDir('favouriteslogo.png')])

    def getLinksForVideo(self, Index=0, selItem=None):
        if self.host.isQuestMode():
            return self.host.getCurrentGuestHost().getLinksForVideo(Index)
        else:
            listLen = len(self.host.currList)
            if listLen < Index and listLen > 0:
                printDBG("ERROR getLinksForVideo - current list is to short len: %d, Index: %d" % (listLen, Index))
                return RetHost(RetHost.ERROR, value=[])

            if self.host.currList[Index]["type"] not in ['audio', 'video', 'picture']:
                printDBG("ERROR getLinksForVideo - current item has wrong type")
                return RetHost(RetHost.ERROR, value=[])
            return self.host.getLinksForVideo(self.host.currList[Index])
    # end getLinksForVideo

    def getResolvedURL(self, url):
        if self.host.isQuestMode():
            return self.host.getCurrentGuestHost().getResolvedURL(url)
        else:
            return self.host.getResolvedURL(url)

    def getListForItem(self, Index=0, refresh=0, selItem=None):
        guestIndex = Index
        ret = RetHost(RetHost.ERROR, value=[])
        if not self.host.isQuestMode():
            ret = CHostBase.getListForItem(self, Index, refresh)
            guestIndex = 0
        if self.host.isQuestMode():
            ret = self.host.getCurrentGuestHost().getListForItem(guestIndex, refresh)
            for idx in range(len(ret.value)):
                ret.value[idx].isGoodForFavourites = False

        self._syncGuestParentFavoriteState(ret)
        self.fixWatchedFlag(ret)
        return ret

    def getPrevList(self, refresh=0):
        ret = RetHost(RetHost.ERROR, value=[])
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

    def getCurrentList(self, refresh=0):
        if refresh == 1 and self.refreshAfterWatchedFlagChange and self.cachedRet is not None:
            ret = self.cachedRet
        else:
            ret = RetHost(RetHost.ERROR, value=[])
            if not self.host.isQuestMode():
                ret = CHostBase.getCurrentList(self, refresh)
            if self.host.isQuestMode():
                ret = self.host.getCurrentGuestHost().getCurrentList(refresh)
                for idx in range(len(ret.value)):
                    ret.value[idx].isGoodForFavourites = False
            self._syncGuestParentFavoriteState(ret)
            self.fixWatchedFlag(ret)
        self.refreshAfterWatchedFlagChange = False
        return ret

    def getMoreForItem(self, Index=0):
        ret = RetHost(RetHost.ERROR, value=[])
        if not self.host.isQuestMode():
            ret = CHostBase.getMoreForItem(self, Index)
        if self.host.isQuestMode():
            ret = self.host.getCurrentGuestHost().getMoreForItem(Index)
            for idx in range(len(ret.value)):
                ret.value[idx].isGoodForFavourites = False
        self._syncGuestParentFavoriteState(ret)
        self.fixWatchedFlag(ret)
        return ret

    def getArticleContent(self, Index=0):
        retCode = RetHost.ERROR
        retlist = []
        guestIndex = Index
        callQuestHost = True
        if not self.host.isQuestMode():
            callQuestHost = self.host.prepareGuestHostItem(Index)
            guestIndex = 0
        if callQuestHost:
            return self.host.getCurrentGuestHost().getArticleContent(guestIndex)
        return RetHost(retCode, value=retlist)
