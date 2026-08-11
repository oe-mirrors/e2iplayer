# -*- coding: utf-8 -*-
# added: 06.08.2026 - central watched helper for normal items, host lists and favourites, file based watched flag handling via hashed keys, item/list/host state updates, favourite hash synchronization, season/series parent propagation for episode items, grouped debug call handling, central config based write protection, custom menu action handling (mark/unmark watched via MENU key), incl. generic group/parent recompute helpers (recomputeGroupWatched/recomputeAllGroupsWatched) for season/series propagation on unmark - Kamikaze24
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetFavouritesDir, mkdirs, rm
from Plugins.Extensions.IPTVPlayer.libs.crypto.hash.md5Hash import MD5
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import RetHost, CDisplayListItem
from Plugins.Extensions.IPTVPlayer.components.iptvchoicebox import IPTVChoiceBoxItem
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.pVer import isPY2
###################################################

###################################################
# FOREIGN import
###################################################
from Tools.Directories import fileExists
from binascii import hexlify
import os
from Components.config import config
# favourites_use_watched_flag / watched_item_color are defined centrally in
# components/iptvconfigmenu.py (global E2iPlayer settings)


class IPTVWatchedHelper(object):

    # marker file content that means "started but not fully watched yet";
    # any other content (incl. empty, the historic touch()-created files) means "watched"
    STARTED_MARKER = 'started'

    def __init__(self, hostName=''):
        self.hostName = str(hostName or '')
        self._favouritesBaseDir = None
        self._watchedBaseDir = None
        self._ensuredDirs = {}
        self._debugCalls = {}
        self._debugEnabled = True
        self._lastRet = None
        self._lastCurrList = None
        self._lastKeyProvider = None

    ###################################################
    # debug helpers
    ###################################################
    def _dbgCall(self, name):
        try:
            if not self._debugEnabled:
                return
            self._debugCalls[name] = self._debugCalls.get(name, 0) + 1
        except Exception:
            printExc()

    def dumpDebugCalls(self, prefix='IPTVWatchedHelper'):
        try:
            if not self._debugEnabled or self._debugCalls == {}:
                return
            keys = sorted(self._debugCalls.keys())
            parts = []
            for key in keys:
                parts.append('%s.%s x%d' % (prefix, key, self._debugCalls[key]))
            printDBG(' | '.join(parts))
            self._debugCalls = {}
        except Exception:
            printExc()

    def setDebugEnabled(self, enabled):
        try:
            self._debugEnabled = bool(enabled)
        except Exception:
            printExc()

    ###################################################
    # normalization helpers
    ###################################################
    def _normalizeKey(self, watchedKey):
        try:
            watchedKey = str(watchedKey or '').strip()
            return watchedKey
        except Exception:
            printExc()
        return ''

    def _normalizeHostName(self, hostName=None):
        try:
            if hostName in [None, '']:
                hostName = self.hostName
            hostName = str(hostName or '').strip()
            return hostName
        except Exception:
            printExc()
        return ''

    def _hashString(self, value):
        try:
            hashAlg = MD5()
            hashData = hexlify(hashAlg(str(value or '')))
            if not isPY2():
                hashData = hashData.decode()
            return hashData
        except Exception:
            printExc()
        return ''

    def _setItemWatchedFlag(self, item, value):
        try:
            if isinstance(item, dict):
                item['isWatched'] = value
            else:
                item.isWatched = value
        except Exception:
            printExc()

    def _setItemStartedFlag(self, item, value):
        try:
            if isinstance(item, dict):
                item['isStarted'] = value
            else:
                item.isStarted = value
        except Exception:
            printExc()

    def _writeMarkerFile(self, path, content):
        try:
            f = open(path, 'w')
            try:
                f.write(content)
            finally:
                f.close()
            return True
        except Exception:
            printExc()
        return False

    def _readMarkerFile(self, path):
        try:
            f = open(path, 'r')
            try:
                return f.read().strip()
            finally:
                f.close()
        except Exception:
            pass
        return ''

    ###################################################
    # path helpers
    ###################################################
    def _getFavouritesBaseDir(self):
        try:
            if self._favouritesBaseDir is None:
                self._favouritesBaseDir = GetFavouritesDir('').rstrip('/')
            return self._favouritesBaseDir
        except Exception:
            printExc()
        return ''

    def _getWatchedBaseDir(self):
        try:
            if self._watchedBaseDir is None:
                baseDir = self._getFavouritesBaseDir()
                if baseDir == '':
                    return ''
                self._watchedBaseDir = os.path.join(baseDir, 'IPTVWatched')
            return self._watchedBaseDir
        except Exception:
            printExc()
        return ''

    ###################################################
    # config helpers
    ###################################################
    def isMarkingAllowed(self):
        try:
            return bool(config.plugins.iptvplayer.favourites_use_watched_flag.value)
        except Exception:
            printExc()
        return False

    ###################################################
    # watched file helpers
    ###################################################
    def getWatchedFilePath(self, watchedKey):
        self._dbgCall('getWatchedFilePath')
        try:
            watchedKey = self._normalizeKey(watchedKey)
            hostName = self._normalizeHostName()
            if watchedKey == '' or hostName == '':
                return ''
            hashData = self._hashString(watchedKey)
            if hashData == '':
                return ''
            baseDir = self._getWatchedBaseDir()
            if baseDir == '':
                return ''
            return os.path.join(baseDir, hostName, '.%s.iptvhash' % hashData)
        except Exception:
            printExc()
        return ''

    def _ensureWatchedDir(self, hostName=None):
        try:
            hostName = self._normalizeHostName(hostName)
            if hostName == '':
                return False
            dirPath = os.path.join(self._getWatchedBaseDir(), hostName)
            if dirPath == '':
                return False
            if self._ensuredDirs.get(dirPath, False):
                return True
            sts = mkdirs(dirPath)
            if sts:
                self._ensuredDirs[dirPath] = True
            return sts
        except Exception:
            printExc()
        return False

    ###################################################
    # watched state helpers
    ###################################################
    def getWatchedState(self, watchedKey):
        # returns 'watched', 'started' or 'none' - single source of truth for
        # both isWatched()/isStarted() and for reading the marker file content
        self._dbgCall('getWatchedState')
        try:
            flagFilePath = self.getWatchedFilePath(watchedKey)
            if flagFilePath != '' and fileExists(flagFilePath):
                content = self._readMarkerFile(flagFilePath)
                return 'started' if content == self.STARTED_MARKER else 'watched'
        except Exception:
            printExc()
        return 'none'

    def isWatched(self, watchedKey):
        self._dbgCall('isWatched')
        return self.getWatchedState(watchedKey) == 'watched'

    def isStarted(self, watchedKey):
        self._dbgCall('isStarted')
        return self.getWatchedState(watchedKey) == 'started'

    def markItemWatched(self, item, watchedKey):
        self._dbgCall('markItemWatched')
        try:
            if not self.isMarkingAllowed():
                return False
            watchedKey = self._normalizeKey(watchedKey)
            if watchedKey == '':
                return False
            if not self._ensureWatchedDir():
                return False
            flagFilePath = self.getWatchedFilePath(watchedKey)
            if flagFilePath == '':
                return False
            # write (not touch): must overwrite a possible "started" marker
            if self._writeMarkerFile(flagFilePath, ''):
                self._setItemWatchedFlag(item, True)
                self._setItemStartedFlag(item, False)
                return True
        except Exception:
            printExc()
        return False

    def _writeStartedMarker(self, item, watchedKey):
        # unconditional write, no anti-downgrade guard - used by parent (season/series)
        # recompute, where "started" must reflect the current children truthfully even
        # if the parent was previously fully watched (e.g. one episode got unwatched
        # again after the whole season was marked watched)
        try:
            if not self.isMarkingAllowed():
                return False
            watchedKey = self._normalizeKey(watchedKey)
            if watchedKey == '':
                return False
            if not self._ensureWatchedDir():
                return False
            flagFilePath = self.getWatchedFilePath(watchedKey)
            if flagFilePath == '':
                return False
            if self._writeMarkerFile(flagFilePath, self.STARTED_MARKER):
                self._setItemStartedFlag(item, True)
                self._setItemWatchedFlag(item, False)
                return True
        except Exception:
            printExc()
        return False

    def markItemStarted(self, item, watchedKey):
        # used when playback of a single item starts - deliberately keeps an
        # already fully-watched item watched instead of downgrading it just
        # because it's being played again
        self._dbgCall('markItemStarted')
        try:
            if not self.isMarkingAllowed():
                return False
            watchedKey = self._normalizeKey(watchedKey)
            if watchedKey == '':
                return False
            if self.isWatched(watchedKey):
                self._setItemWatchedFlag(item, True)
                self._setItemStartedFlag(item, False)
                return False
        except Exception:
            printExc()
            return False
        return self._writeStartedMarker(item, watchedKey)

    def unmarkItemWatched(self, item, watchedKey):
        self._dbgCall('unmarkItemWatched')
        try:
            watchedKey = self._normalizeKey(watchedKey)
            if watchedKey == '':
                return False
            flagFilePath = self.getWatchedFilePath(watchedKey)
            if flagFilePath == '':
                return False
            if rm(flagFilePath):
                self._setItemWatchedFlag(item, False)
                self._setItemStartedFlag(item, False)
                return True
        except Exception:
            printExc()
        return False

    ###################################################
    # item update helpers
    ###################################################
    def updateItemFlag(self, item, watchedKey):
        self._dbgCall('updateItemFlag')
        try:
            state = self.getWatchedState(watchedKey)
            item['isWatched'] = (state == 'watched')
            item['isStarted'] = (state == 'started')
        except Exception:
            printExc()
            try:
                item['isWatched'] = False
                item['isStarted'] = False
            except Exception:
                printExc()
        return item

    def updateListFlags(self, itemList, keyProvider):
        self._dbgCall('updateListFlags')
        try:
            for item in itemList:
                try:
                    watchedKey = keyProvider(item)
                except Exception:
                    watchedKey = ''
                    printExc()
                if watchedKey == '':
                    try:
                        item['isWatched'] = False
                        item['isStarted'] = False
                    except Exception:
                        printExc()
                else:
                    self.updateItemFlag(item, watchedKey)
        except Exception:
            printExc()
        return itemList

    def updateHostItemFlag(self, host, cItem, keyProvider):
        self._dbgCall('updateHostItemFlag')
        try:
            watchedKey = keyProvider(cItem)
            if watchedKey == '':
                cItem['isWatched'] = False
                cItem['isStarted'] = False
            else:
                self.updateItemFlag(cItem, watchedKey)
        except Exception:
            printExc()
        return cItem

    def updateHostListFlags(self, host, itemList, keyProvider):
        self._dbgCall('updateHostListFlags')
        try:
            self.updateListFlags(itemList, keyProvider)
        except Exception:
            printExc()
        self.dumpDebugCalls()
        return itemList

    def updateParentWatchedState(self, parentItem, childItems, keyProvider):
        self._dbgCall('updateParentWatchedState')
        try:
            if not isinstance(parentItem, dict):
                return False
            parentKey = keyProvider(parentItem)
            if parentKey == '':
                return False
            childKeys = []
            for childItem in childItems or []:
                try:
                    childKey = keyProvider(childItem)
                except Exception:
                    printExc()
                    childKey = ''
                if childKey != '':
                    childKeys.append(childKey)
            if len(childKeys) == 0:
                return False
            childStates = [self.getWatchedState(childKey) for childKey in childKeys]
            allWatched = all(state == 'watched' for state in childStates)
            anyProgress = any(state != 'none' for state in childStates)
            if allWatched:
                self.markItemWatched(parentItem, parentKey)
            elif anyProgress:
                self._writeStartedMarker(parentItem, parentKey)
            else:
                self.unmarkItemWatched(parentItem, parentKey)
            return True
        except Exception:
            printExc()
        return False

    def markHostItemAsStarted(self, host, cItem, keyProvider):
        self._dbgCall('markHostItemAsStarted')
        try:
            if not self.isMarkingAllowed():
                return False
            watchedKey = keyProvider(cItem)
            if watchedKey != '':
                self.markItemStarted(cItem, watchedKey)
            return True
        except Exception:
            printExc()
        return False

    def markHostItemAsWatched(self, host, cItem, keyProvider):
        self._dbgCall('markHostItemAsWatched')
        try:
            if not self.isMarkingAllowed():
                return False
            watchedKey = keyProvider(cItem)
            if watchedKey != '':
                self.markItemWatched(cItem, watchedKey)
            return True
        except Exception:
            printExc()
        return False

    def unmarkHostItemAsWatched(self, host, cItem, keyProvider):
        self._dbgCall('unmarkHostItemAsWatched')
        try:
            watchedKey = keyProvider(cItem)
            if watchedKey != '':
                self.unmarkItemWatched(cItem, watchedKey)
            if isinstance(cItem, dict):
                seriesUrl = str(cItem.get('series_url', '') or '').strip()
                seasonNum = str(cItem.get('season_num', '') or '').strip()
                if seriesUrl != '' and seasonNum != '':
                    seasonItem = {'category': 'list_episodes', 'url': cItem.get('url', ''), 'series_url': seriesUrl, 'season_num': seasonNum}
                    seasonKey = keyProvider(seasonItem)
                    if seasonKey != '':
                        self.unmarkItemWatched(seasonItem, seasonKey)
                if seriesUrl != '':
                    seriesItem = {'category': 'list_seasons', 'url': seriesUrl}
                    seriesKey = keyProvider(seriesItem)
                    if seriesKey != '':
                        self.unmarkItemWatched(seriesItem, seriesKey)
            return True
        except Exception:
            printExc()
        return False

    ###################################################
    # ret/favourite sync helpers
    #
    # Host list items are keyed by their own stable url-based key
    # (keyProvider/_getWatchedKeyForItem), so fixHostRet() only needs that key -
    # there used to be a second, separate lookup here keyed by display title+type,
    # but its result was always immediately overwritten by the key-based one below,
    # so it never actually affected what was shown and has been removed instead of
    # also switching it to a stable key.
    ###################################################
    def fixHostRet(self, ret, currList, keyProvider):
        self._dbgCall('fixHostRet')
        try:
            if ret is None or not hasattr(ret, 'value') or ret.value is None:
                self.dumpDebugCalls()
                return ret
            for idx in range(len(ret.value)):
                if currList is not None and idx < len(currList):
                    try:
                        watchedKey = keyProvider(currList[idx])
                        if watchedKey != '':
                            state = self.getWatchedState(watchedKey)
                            ret.value[idx].isWatched = (state == 'watched')
                            ret.value[idx].isStarted = (state == 'started')
                    except Exception:
                        printExc()
        except Exception:
            printExc()
        self._lastRet = ret
        self._lastCurrList = currList
        self._lastKeyProvider = keyProvider
        self.dumpDebugCalls()
        return ret

    ###################################################
    # menu custom action helpers (watched toggle via MENU key)
    ###################################################
    def getCustomActionsForRet(self, ret, currList, keyProvider, Index=0):
        self._dbgCall('getCustomActionsForRet')
        retCode = RetHost.ERROR
        retlist = []
        try:
            if self.isMarkingAllowed():
                if ret is not None and hasattr(ret, 'value') and ret.value is not None and 0 <= Index < len(ret.value):
                    displayItem = ret.value[Index]
                    watchedKey = ''
                    itemDict = None
                    if keyProvider is not None and currList is not None and Index < len(currList):
                        try:
                            itemDict = currList[Index]
                            watchedKey = keyProvider(itemDict)
                        except Exception:
                            watchedKey = ''
                            printExc()
                    isGroupItem = isinstance(itemDict, dict) and itemDict.get('category', '') in ['list_episodes', 'list_seasons']
                    if displayItem.type in [CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO] or isGroupItem:
                        if watchedKey != '':
                            isWatched = bool(getattr(displayItem, 'isWatched', False))
                            isStarted = bool(getattr(displayItem, 'isStarted', False))
                            # a "started" item isn't fully watched yet, so it should offer
                            # both promoting it to watched and clearing it back to nothing -
                            # not just the one toggle a plain watched/unwatched item gets
                            if not isWatched:
                                retlist.append(IPTVChoiceBoxItem(_('Set watched'), "", {'action': 'set_watched_flag', 'item_index': Index, 'watched_key': watchedKey}))
                            if isWatched or isStarted:
                                retlist.append(IPTVChoiceBoxItem(_('Unset watched'), "", {'action': 'unset_watched_flag', 'item_index': Index, 'watched_key': watchedKey}))
                            if retlist:
                                retCode = RetHost.OK
                                self._lastRet = ret
                                self._lastCurrList = currList
                                self._lastKeyProvider = keyProvider
        except Exception:
            printExc()
        self.dumpDebugCalls()
        return RetHost(retCode, value=retlist)

    def performCustomAction(self, privateData):
        self._dbgCall('performCustomAction')
        retCode = RetHost.ERROR
        retlist = []
        try:
            if self.isMarkingAllowed():
                ret = self._lastRet
                watchedKey = privateData.get('watched_key', '')
                Index = privateData.get('item_index', -1)
                action = privateData.get('action', '')
                if ret is not None and hasattr(ret, 'value') and watchedKey != '' and 0 <= Index < len(ret.value):
                    displayItem = ret.value[Index]

                    if action == 'unset_watched_flag':
                        if self.unmarkItemWatched(displayItem, watchedKey):
                            retCode = RetHost.OK

                    elif action == 'set_watched_flag':
                        if self.markItemWatched(displayItem, watchedKey):
                            retCode = RetHost.OK

                    if retCode == RetHost.OK:
                        retlist = ['refresh']
        except Exception:
            printExc()
        self.dumpDebugCalls()
        return RetHost(retCode, value=retlist)

    ###################################################
    # group/parent recompute helpers (e.g. season <- episodes)
    ###################################################
    def recomputeGroupWatched(self, childItems, keyProvider, parentItem):
        self._dbgCall('recomputeGroupWatched')
        try:
            childKeys = []
            for child in childItems or []:
                try:
                    childKey = keyProvider(child)
                except Exception:
                    childKey = ''
                    printExc()
                if childKey != '':
                    childKeys.append(childKey)
            parentKey = keyProvider(parentItem)
            if parentKey == '':
                return False
            if len(childKeys) == 0:
                return self.unmarkItemWatched(parentItem, parentKey)
            childStates = [self.getWatchedState(childKey) for childKey in childKeys]
            allWatched = all(state == 'watched' for state in childStates)
            anyProgress = any(state != 'none' for state in childStates)
            if allWatched:
                return self.markItemWatched(parentItem, parentKey)
            elif anyProgress:
                return self._writeStartedMarker(parentItem, parentKey)
            else:
                return self.unmarkItemWatched(parentItem, parentKey)
        except Exception:
            printExc()
        return False

    def recomputeAllGroupsWatched(self, groupsDict, keyProvider, parentItemBuilder):
        self._dbgCall('recomputeAllGroupsWatched')
        try:
            if not groupsDict:
                return
            for groupId in list(groupsDict.keys()):
                try:
                    parentItem = parentItemBuilder(groupId)
                except Exception:
                    parentItem = None
                    printExc()
                if parentItem is not None:
                    self.recomputeGroupWatched(groupsDict.get(groupId, []), keyProvider, parentItem)
        except Exception:
            printExc()
        self.dumpDebugCalls()
