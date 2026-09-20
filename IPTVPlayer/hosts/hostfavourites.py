# -*- coding: utf-8 -*-
# Last Modified: 20.09.2026 - YouTube channels in a group: sort by newest upload + merged "newest videos" list,
# folder watched/started marking, markers under the host's own watched folder name, origin host line
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import IHost, CHostBase, CBaseHostClass, CDisplayListItem, RetHost, CUrlItem, CFavItem
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetLogoDir, GetFavouritesDir, GetWatchedDir, mkdirs, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvfavourites import IPTVFavourites
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.components.iptvchoicebox import IPTVChoiceBoxItem
from Plugins.Extensions.IPTVPlayer.libs.crypto.hash.md5Hash import MD5
from Plugins.Extensions.IPTVPlayer.libs import ytchannelfeed
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
import re
import time
from Components.config import config, ConfigInteger, getConfigListEntry
###################################################


# how many of the newest videos of every channel go into "Newest videos" of a favourites group (the feed has 15 per channel)
config.plugins.iptvplayer.favourites_yt_newest_per_channel = ConfigInteger(3, (1, 15))


def GetConfigList():
    # "Allow watched flag to be set" / "The color of the viewed item" live in the global
    # E2iPlayer settings (components/iptvconfigmenu.py), only the YouTube list is set here
    optionList = []
    optionList.append(getConfigListEntry(_("Newest videos of a YouTube channel in a group") + ":", config.plugins.iptvplayer.favourites_yt_newest_per_channel))
    return optionList
###################################################


def gettytul():
    return _("Favorites")


class Favourites(CBaseHostClass):
    YT_NEWEST_MAX = 100

    def __init__(self):
        printDBG("Favourites.__init__")
        CBaseHostClass.__init__(self)
        self.helper = IPTVFavourites(GetFavouritesDir())
        self.host = None
        self.hostName = ''
        self.guestMode = False  # main or guest
        self.DEFAULT_ICON_URL = "https://raw.githubusercontent.com/oe-mirrors/e2iplayer/refs/heads/gh-pages/icons/favourites.png"
        self._guestParentWatchedHelper = IPTVWatchedHelper('favourites')
        self.ytSortedGroups = set()  # group ids shown sorted by the newest YouTube upload (this visit only)
        self.hostTitles = {}  # host module name -> title to show, see _getHostTitle()

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

        rows = []
        for idx in range(len(data)):
            item = data[idx]
            addFun = typesMap.get(item.type, None)
            favUrl, favItem = self._parseFavItem(item)
            params = {'name': 'item', 'title': item.name, 'host': item.hostName, 'icon': item.iconimage, 'desc': item.description, 'group_id': cItem['group_id'], 'item_idx': idx, 'fav_url': favUrl, 'fav_item': favItem}
            if None is not addFun:
                rows.append((params, addFun))

        ytChannels = [params for params, addFun in rows if self._isYtChannelParams(params)]
        if len(ytChannels) > 1:
            self.addDir({'name': 'category', 'category': 'yt_newest', 'group_id': cItem['group_id'], 'title': _("Newest videos (all YouTube channels)"), 'desc': _("The latest uploads of all YouTube channels in this group, newest first."), 'icon': self.DEFAULT_ICON_URL})
        if ytChannels and self.isYtSorted(cItem['group_id']):
            try:
                self._annotateYtChannels(rows)
            except Exception:
                printExc()
        for params, addFun in rows:
            params['desc'] = self._addHostLine(params['host'], params['desc'])
            addFun(params)

    def _addHostLine(self, hostName, desc):
        # the host a favourite comes from, first line of its description
        title = self._getHostTitle(hostName)
        if title == '':
            return desc
        return _("Host") + ": " + title + ("\n" + desc if desc else '')

    def _getHostTitle(self, hostName):
        if hostName not in self.hostTitles:
            title = ''
            try:
                module = __import__('Plugins.Extensions.IPTVPlayer.hosts.host' + hostName, globals(), locals(), ['gettytul'], 0)
                title = re.sub(r'^https?://(www\.)?', '', str(module.gettytul()).strip()).rstrip('/')
            except Exception:
                printExc()
            self.hostTitles[hostName] = title or str(hostName)
        return self.hostTitles[hostName]

    def _parseFavItem(self, item):
        # -> (favUrl, favItem) of a stored favourite; favItem is the host's own item dict (or None)
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
        return favUrl, favItem

    @staticmethod
    def _isYtChannel(hostName, favItem):
        return hostName == 'youtube' and isinstance(favItem, dict) and favItem.get('category', '') == 'channel' and bool(favItem.get('url', ''))

    def _isYtChannelParams(self, params):
        return self._isYtChannel(params.get('host', ''), params.get('fav_item'))

    def hasYtChannels(self):
        # the group list currently shown holds YouTube channels (cheap, no I/O - asked on every MENU check)
        if self.guestMode:
            return False
        return any('item_idx' in params and self._isYtChannelParams(params) for params in self.currList)

    def isYtSorted(self, groupId):
        return groupId in self.ytSortedGroups

    def setYtSorted(self, groupId, enabled):
        if enabled:
            self.ytSortedGroups.add(groupId)
        else:
            self.ytSortedGroups.discard(groupId)

    def getCurrentGroupId(self):
        for params in self.currList:
            if 'item_idx' in params and 'group_id' in params:
                return params['group_id']
        return ''

    def getGroupItemIdx(self, index):
        # position of the favourite in its group's file for the row at list position index;
        # -1 for anything that is not a plain stored favourite (guest lists, the virtual
        # "newest videos" row and its videos) - the list can be sorted, so the row position
        # is not the storage position
        if self.guestMode or not (0 <= index < len(self.currList)):
            return -1
        params = self.currList[index]
        if params.get('yt_video') or 'group_id' not in params:
            return -1
        return params.get('item_idx', -1)

    def onGroupItemDeleted(self, index, storageIdx):
        # keep the raw list in step with a favourite removed from the group (see getGroupItemIdx)
        try:
            del self.currList[index]
            for params in self.currList:
                if params.get('item_idx', -1) > storageIdx:
                    params['item_idx'] -= 1
        except Exception:
            printExc()

    def _annotateYtChannels(self, rows):
        # rows: [(params, addFun)] of one group; adds the latest upload of every YouTube channel
        # to its description and moves the channels with the newest upload to the top
        channels = [params for params, addFun in rows if self._isYtChannelParams(params)]
        feeds = ytchannelfeed.getFeeds([params['fav_item']['url'] for params in channels])
        now = time.time()
        for params in channels:
            latest = ytchannelfeed.latestUpload(feeds.get(params['fav_item']['url']))
            if latest:
                params['yt_latest'] = latest['published']
                line = _("Latest video") + ": " + ytchannelfeed.describeDate(latest['published'], now) + "\n" + latest['title']
            else:
                line = _("Latest video") + ": ?"
            params['desc'] = line + ("\n" + params['desc'] if params.get('desc') else '')
        # stable: rows without a known upload keep their order behind the dated ones
        rows.sort(key=lambda row: -row[0].get('yt_latest', 0))

    @staticmethod
    def _getNewestPerChannel():
        try:
            return max(1, int(config.plugins.iptvplayer.favourites_yt_newest_per_channel.value))
        except Exception:
            printExc()
        return 3

    def listYtNewest(self, cItem):
        printDBG("Favourites.listYtNewest")
        sts, data = self.helper.getGroupItems(cItem['group_id'])
        if not sts:
            return
        urls = []
        for item in data:
            favItem = self._parseFavItem(item)[1]
            if self._isYtChannel(item.hostName, favItem):
                urls.append(favItem['url'])
        ytchannelfeed.clearFailed()  # opening the list (or OK on its "could not be read" row) tries those channels again
        feeds = ytchannelfeed.getFeeds(urls)
        # a channel whose feed is missing in the result counts too (not finished in time)
        failed = len([url for url in set(urls) if feeds.get(url) is None])
        now = time.time()
        newest = self._getNewestEntries(feeds)
        for entry in newest:
            self._addNewestVideo(entry, now)
        if failed or not newest:
            self._addNewestNotice(cItem['group_id'], failed)

    def _getNewestEntries(self, feeds):
        # the newest videos of all channels, newest first; a busy channel must not push the others out
        perChannel = self._getNewestPerChannel()
        videos = {}
        for info in feeds.values():
            for entry in (info or {}).get('entries', [])[:perChannel]:
                videos[entry['video_id']] = entry
        return sorted(videos.values(), key=lambda entry: -entry['published'])[:self.YT_NEWEST_MAX]

    def _addNewestVideo(self, entry, now):
        video = {'type': 'video', 'category': 'video', 'title': entry['title'], 'url': 'https://www.youtube.com/watch?v=' + entry['video_id'],
                 'icon': entry['icon'], 'video_id': entry['video_id'], 'channel': entry['channel']}
        desc = entry['channel'] + "\n" + ytchannelfeed.describeDate(entry['published'], now)
        extra = []
        if entry['short']:
            extra.append('Short')
        if entry['views']:
            extra.append(entry['views'] + ' ' + _("views"))
        if extra:
            desc += "\n" + ' | '.join(extra)
        # the age first: the list is sorted by it, not by channel
        title = '[' + ytchannelfeed.formatAge(entry['published'], now) + '] ' + entry['channel'] + ': ' + entry['title']
        self.addVideo({'name': 'item', 'title': title, 'host': 'youtube', 'icon': entry['icon'], 'desc': desc,
                       'yt_video': True, 'yt_item': video, 'fav_item': video, 'fav_url': video['url']})

    def _addNewestNotice(self, groupId, failed):
        # a row that says so, not a silently shorter list; pressing OK on it asks the feeds again
        if failed:
            title = _("(%d YouTube channel(s) could not be read)") % failed
            desc = _("The feed of these channels could not be read - press OK to try again.")
        else:
            title = _("(no videos found)")
            desc = _("The YouTube channels of this group have no videos.")
        self.addDir({'name': 'category', 'category': 'yt_newest', 'group_id': groupId, 'title': title, 'desc': desc})

    def getLinksForVideo(self, cItem):
        printDBG("Favourites.getLinksForVideo idx[%r]" % cItem)
        ret = RetHost(RetHost.ERROR, value=[])
        if cItem.get('yt_video'):
            # video of the merged "newest videos" list - not a stored favourite, resolved by the YouTube host
            if self._setHost('youtube'):
                urlList = self.host.host.getLinksForVideo(dict(cItem['yt_item']))
                ret = RetHost(RetHost.OK, value=[CUrlItem(self.cleanHtmlStr(urlItem['name']), urlItem['url'], urlItem.get('need_resolve', 0)) for urlItem in urlList])
            return ret
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
            for urlItem in urlList:
                name = self.cleanHtmlStr(urlItem["name"])
                url = urlItem["url"]
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
        if 1 == refresh and category in ('list_favourites', 'yt_newest'):
            ytchannelfeed.clearCache()  # a refresh should look for new uploads again
        if None is name:
            self.host = None
            self.hostName = None
            self.listGroups('list_favourites')
        elif 'list_favourites' == category:
            self.listFavourites(self.currItem)
        elif 'yt_newest' == category:
            self.listYtNewest(self.currItem)
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

    def _getWatchedDirName(self, hostName):
        # markers live under the name the host's own IPTVWatchedHelper uses - that is not always the
        # module name (hostfilmpalast -> "filmpalastto", hostplayrtsiw -> "srgssr"); using the
        # module name here made the favourites and the host mark into two different folders
        try:
            if self.host.isQuestMode():
                rawHost = self._getRawGuestHost(self.host.getCurrentGuestHost())
            else:
                rawHost = self._getRawHostForName(hostName)
            name = str(getattr(getattr(rawHost, 'watchedHelper', None), 'hostName', '') or '')
            if name != '':
                return name
        except Exception:
            printExc()
        return hostName

    def _getItemHashParts(self, index, displayItem):
        # -> (module name of the host, md5 of the item's stable id) or None
        if self.host.isQuestMode():
            hostName = str(self.host.getCurrentGuestHostName())
        else:
            hostName = str(self.host.getHostNameFromItem(index))
        if hostName in [None, '']:
            return None
        hashSrc = self._getStableItemHashSource(index)
        if hashSrc == '':
            hashSrc = '%s_%s' % (str(displayItem.name), str(displayItem.type))
        hashAlg = MD5()
        hashData = hexlify(hashAlg(hashSrc))
        if not isPY2():
            hashData = hashData.decode()
        return (hostName, hashData)

    def getItemHashData(self, index, displayItem):
        parts = self._getItemHashParts(index, displayItem)
        if parts is None:
            return None
        return (self._getWatchedDirName(parts[0]), parts[1])

    def _readItemMarker(self, index, displayItem):
        # marker content of the item (None = none), also picking up - and moving to the host's own
        # folder - a marker an older build wrote under the module name of the host
        parts = self._getItemHashParts(index, displayItem)
        if parts is None:
            return None
        hashData = (self._getWatchedDirName(parts[0]), parts[1])
        content = self._readMarkerContent(hashData)
        if parts[0] == hashData[0]:
            return content
        oldData = parts
        oldContent = self._readMarkerContent(oldData)
        if oldContent is None:
            return content
        if content is None or (content == IPTVWatchedHelper.STARTED_MARKER and oldContent != IPTVWatchedHelper.STARTED_MARKER):
            content = oldContent
            self._createViewedFile(hashData, oldContent)
        rm(GetWatchedDir('%s/.%s.iptvhash' % oldData))
        return content

    def _readMarkerContent(self, hashData):
        # None = no file at all, '' or any other text = watched, STARTED_MARKER = started
        if hashData is None:
            return None
        flagFilePath = GetWatchedDir('%s/.%s.iptvhash' % hashData)
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
        content = self._readItemMarker(index, displayItem)
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
        return self._readItemMarker(index, displayItem) == IPTVWatchedHelper.STARTED_MARKER

    def fixWatchedFlag(self, ret):
        if self.useWatchedFlag:
            # check watched flag from hash
            for idx in range(len(ret.value)):
                if ret.value[idx].type in [CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO] and not ret.value[idx].isWatched:
                    if self.isItemWatched(idx, ret.value[idx]):
                        ret.value[idx].isWatched = True
                        ret.value[idx].isStarted = False
                    elif self.isItemStarted(idx, ret.value[idx]):
                        ret.value[idx].isStarted = True
                elif ret.value[idx].type == CDisplayListItem.TYPE_CATEGORY:
                    self._fixFolderWatchedFlag(idx, ret.value[idx])
            self.cachedRet = ret
        return ret

    def _fixFolderWatchedFlag(self, idx, displayItem):
        # A favourite that is a folder of the host (a movie with its streams, a season, a series)
        # shows the state the host keeps for that folder - the same green/yellow marking the host's
        # own list has. Only for the rows of a group: inside a guest host the host flags its own rows.
        if self.host.isQuestMode() or self._getStableItemHashSource(idx) == '':
            return
        content = self._readItemMarker(idx, displayItem)
        displayItem.isWatched = content is not None and content != IPTVWatchedHelper.STARTED_MARKER
        displayItem.isStarted = content == IPTVWatchedHelper.STARTED_MARKER

    def _createViewedFile(self, hashData, content=''):
        if hashData is not None and mkdirs(GetWatchedDir('%s/' % hashData[0])):
            flagFilePath = GetWatchedDir('%s/.%s.iptvhash' % hashData)
            try:
                # write (not touch): must overwrite a possible "started" marker
                f = open(flagFilePath, 'w')
                try:
                    f.write(content)
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
            if ret is not None and hasattr(ret, 'value') and 0 <= Index < len(ret.value) \
               and ret.value[Index].isWatched is not True and ret.value[Index].type in [CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO]:
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
                if ret is not None and hasattr(ret, 'value') and 0 <= Index < len(ret.value) \
                   and ret.value[Index].type in [CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO]:
                    tmp = self.getItemHashData(Index, ret.value[Index])
                    if tmp != '':
                        isWatched = bool(self.cachedRet.value[Index].isWatched)
                        isStarted = bool(getattr(self.cachedRet.value[Index], 'isStarted', False))
                        if not isWatched:
                            retlist.append(IPTVChoiceBoxItem(_('Set watched'), "", {'action': 'set_watched_flag', 'item_index': Index, 'hash_data': tmp}))
                        if isWatched or isStarted:
                            retlist.append(IPTVChoiceBoxItem(_('Unset watched'), "", {'action': 'unset_watched_flag', 'item_index': Index, 'hash_data': tmp}))
                    retCode = RetHost.OK
        retlist.extend(self._getYtGroupActions())
        if retlist:
            retCode = RetHost.OK
        return RetHost(retCode, value=retlist)

    def _getYtGroupActions(self):
        # sort switch for a favourites group that holds YouTube channels (not tied to the watched flag)
        favourites = self.host
        if not favourites.hasYtChannels():
            return []
        groupId = favourites.getCurrentGroupId()
        if favourites.isYtSorted(groupId):
            return [IPTVChoiceBoxItem(_("YouTube channels: original order"), "", {'action': 'yt_sort_reset', 'group_id': groupId})]
        return [IPTVChoiceBoxItem(_("YouTube channels: sort by newest upload"), "", {'action': 'yt_sort_newest', 'group_id': groupId})]

    def performCustomAction(self, privateData):
        retCode = RetHost.ERROR
        retlist = []
        if isinstance(privateData, dict) and privateData.get('action', '') in ('yt_sort_newest', 'yt_sort_reset'):
            self.host.setYtSorted(privateData.get('group_id', ''), privateData['action'] == 'yt_sort_newest')
            self.refreshAfterWatchedFlagChange = False  # re-list the group instead of reusing the cached rows
            return RetHost(RetHost.OK, value=['refresh'])
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
                    flagFilePath = GetWatchedDir('%s/.%s.iptvhash' % hashData)
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
