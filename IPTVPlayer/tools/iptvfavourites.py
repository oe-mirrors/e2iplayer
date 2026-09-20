# -*- coding: utf-8 -*-
#

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.components.ihost import CFavItem
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
###################################################

###################################################
# FOREIGN import
###################################################
import codecs
from os import listdir as os_listdir, path as os_path, remove as os_remove, stat as os_stat
###################################################


class IPTVFavourites:
    FILE_NAME_MACRO = 'iptv_%s.fav'
    GROUPS_FILE_NAME = FILE_NAME_MACRO % 'groups'
    # fields of a host's item dict that differ between two listings of the same item, or between the
    # folder of a movie and the movie inside it (the host copies the folder's dict, only "type" is
    # then video instead of category) - the film in a favourite folder counts as the favourite too
    VOLATILE_ITEM_FIELDS = ('isWatched', 'isStarted', 'desc', 'icon', 'time', 'type', 'good_for_fav')

    def __init__(self, favDir):
        self.lastError = ''
        self.favDir = favDir
        self.groups = []
        self.loadedGroups = {}
        self.delGroups = {}

    def getLastError(self):
        return self.lastError

    def load(self, groupsOnly=False):
        ret = self._loadGroups()
        if not ret:
            lastError = self.lastError
        else:
            lastError = ''
        if ret and not groupsOnly:
            for idx in range(len(self.groups)):
                tmpRet = self._loadItems(idx)
                if tmpRet:
                    self.loadedGroups[self.groups[idx]['group_id']] = True
                else:
                    ret = False
                    lastError += self.lastError
        if not ret:
            self.lastError = lastError
        return ret

    def save(self, groupsOnly=False):
        ret = self._saveGroups()
        if not ret:
            lastError = self.lastError
        else:
            lastError = ''
        if not groupsOnly:
            for idx in range(len(self.groups)):
                if self.loadedGroups.get(self.groups[idx]['group_id'], False):
                    tmpRet = self._saveItems(idx)
                    if not tmpRet:
                        ret = False
                        lastError += self.lastError
            for key in self.delGroups:
                if self.delGroups[key]:
                    tmpRet = self._delItems(key)
                    if not tmpRet:
                        ret = False
                        lastError += self.lastError
        if not ret:
            self.lastError = lastError
        return ret

    def getGroup(self, group_id):
        idx = self._getGroupIdx(group_id)
        if -1 != idx:
            return self.groups[idx]
        else:
            return None

    def getGroups(self):
        return self.groups

    def addGroup(self, group):
        idx = self._getGroupIdx(group['group_id'])
        if -1 == idx:
            if 'items' not in group:
                group['items'] = []
            self.groups.append(group)
            self.loadedGroups[group['group_id']] = True
            self.delGroups.pop(group['group_id'], None)
            return True
        else:
            self.lastError = _("Group \"%s\" already exists.") % group['group_id']
            return False

    def modifyGroup(self, group):
        idx = self._getGroupIdx(group['group_id'])
        if -1 != idx:
            group['items'] = self.groups[idx].get('items', [])
            self.groups[idx] = group
            return True
        else:
            return False

    def delGroup(self, group_id):
        idx = self._getGroupIdx(group_id)
        if -1 != idx:
            self.loadedGroups.pop(group_id, None)
            self.delGroups[group_id] = True
            del self.groups[idx]
            return True
        else:
            return False

    def moveGroup(self, curIndex, newIndex):
        if 0 <= curIndex and len(self.groups) > curIndex and 0 <= newIndex and len(self.groups) > newIndex:
            self.groups.insert(newIndex, self.groups.pop(curIndex))
            return True
        else:
            self.lastError = _("Wrong indexes.")
            return False

    def saveGroupItems(self, group_id):
        idx = self._getGroupIdx(group_id)
        if -1 != idx:
            return self._saveItems(idx)
        else:
            return False

    def getGroupItems(self, group_id):
        idx = self._getGroupIdx(group_id)
        if -1 != idx:
            return True, self.groups[idx].get('items', [])
        return False, []

    def loadGroupItems(self, group_id, force=False):
        sts = False
        idx = self._getGroupIdx(group_id)
        if -1 != idx:
            if self.loadedGroups.get(group_id, False) and not force:
                return True
            sts = self._loadItems(idx)
            if sts:
                self.loadedGroups[group_id] = True
        return sts

    def addGroupItem(self, item, group_id):
        idx = self._getGroupIdx(group_id)
        if -1 != idx:
            items = self.groups[idx].get('items', [])
            exists = False
            for tmp in items:
                if tmp.getAsDict() == item.getAsDict():
                    exists = True
                    break
            if not exists:
                items.append(item)
                self.groups[idx]['items'] = items
                return True
            else:
                self.lastError = _("The same item already exists in this group.")
        return False

    @classmethod
    def _getItemIdentity(cls, hostName, resolver, data):
        # what makes two favourites "the same item": host, resolver and the host's own item dict
        # without the fields above (a plain string, e.g. a direct link, is compared as it is)
        try:
            itemData = json_loads(data)
        except Exception:
            itemData = None
        if isinstance(itemData, dict):
            itemData = {key: value for key, value in itemData.items() if key not in cls.VOLATILE_ITEM_FIELDS}
        else:
            itemData = data
        return (hostName, resolver, itemData)

    @classmethod
    def getItemIdentityKey(cls, hostName, resolver, data):
        # _getItemIdentity() as a string, for set lookups
        return json_dumps(cls._getItemIdentity(hostName, resolver, data), sort_keys=True)

    def findItems(self, hostName, resolver, data):
        # -> [(group_id, group title, item index)] of the stored favourites equal to the given item
        target = self._getItemIdentity(hostName, resolver, data)
        found = []
        for group in self.groups:
            for idx, item in enumerate(group.get('items', [])):
                if self._getItemIdentity(item.hostName, item.resolver, item.data) == target:
                    found.append((group['group_id'], group.get('title', ''), idx))
        return found

    def delGroupItem(self, itemIdx, group_id):
        idx = self._getGroupIdx(group_id)
        if -1 != idx:
            try:
                del self.groups[idx]['items'][itemIdx]
            except Exception:
                printExc()
                self.lastError = _("Item idx[%d] not found in group[%s].") % (itemIdx, group_id)
                return False
            return True
        else:
            return False

    def moveGroupItem(self, curIndex, newIndex, group_id):
        idx = self._getGroupIdx(group_id)
        if -1 != idx:
            if 0 <= curIndex and len(self.groups[idx]['items']) > curIndex and 0 <= newIndex and len(self.groups[idx]['items']) > newIndex:
                self.groups[idx]['items'].insert(newIndex, self.groups[idx]['items'].pop(curIndex))
                return True
            else:
                self.lastError = _("Wrong indexes.")
                return False
        else:
            return False

    def _getGroupIdx(self, group_id):
        for idx in range(len(self.groups)):
            if group_id == self.groups[idx]['group_id']:
                return idx
        self.lastError = _("Group with id[%s] not found.") % group_id
        return -1

    def _loadItems(self, groupIdx):
        ret = True
        filePath = os_path.join(self.favDir, IPTVFavourites.FILE_NAME_MACRO % self.groups[groupIdx]['group_id'])
        if os_path.isfile(filePath):
            try:
                data = self._loadFromFile(filePath)
                printDBG(data)
                data = json_loads(data)
                favItems = []
                for item in data:
                    favItems.append(CFavItem().setFromDict(item))
                self.groups[groupIdx]['items'] = favItems
            except Exception:
                printExc()
                self.lastError = _("Error reading file \"%s\".\n") % filePath
                ret = False
        else:
            self.groups[groupIdx]['items'] = []
        return ret

    def _loadGroups(self):
        ret = True
        filePath = os_path.join(self.favDir, IPTVFavourites.GROUPS_FILE_NAME)
        if os_path.isfile(filePath):
            try:
                data = self._loadFromFile(filePath)
                printDBG(data)
                data = json_loads(data)
                self.groups = data
            except Exception:
                printExc()
                self.lastError = _("Error reading file \"%s\".\n") % filePath
                ret = False
        else:
            self.groups = []
        return ret

    def _delItems(self, groupId):
        ret = True
        filePath = os_path.join(self.favDir, IPTVFavourites.FILE_NAME_MACRO % groupId)
        if os_path.isfile(filePath):
            try:
                os_remove(filePath)
            except Exception:
                printExc()
                self.lastError = _("Error deleting file \"%s\".\n") % filePath
                ret = False
        return ret

    def _saveItems(self, groupIdx):
        ret = True
        group = self.groups[groupIdx]
        printDBG("%s" % group)
        filePath = os_path.join(self.favDir, IPTVFavourites.FILE_NAME_MACRO % group['group_id'])
        try:
            items = []
            for favItem in group['items']:
                items.append(favItem.getAsDict())
            data = json_dumps(items)
            self._saveToFile(filePath, data)
        except Exception:
            printExc()
            self.lastError = _("Error writing file \"%s\".\n") % filePath
            ret = False
        return ret

    def _saveGroups(self):
        ret = True
        try:
            from copy import deepcopy
            groups = deepcopy(self.groups)
            for item in groups:
                item.pop("items", None)
            filePath = os_path.join(self.favDir, IPTVFavourites.GROUPS_FILE_NAME)
            data = json_dumps(groups)
            self._saveToFile(filePath, data)
        except Exception:
            self.lastError = _("Error writing file \"%s\".\n") % filePath
            ret = False
        return ret

    def _saveToFile(self, filePath, data, encoding='utf-8'):
        with codecs.open(filePath, 'w', encoding, 'replace') as fp:
            fp.write(data)

    def _loadFromFile(self, filePath, encoding='utf-8'):
        with codecs.open(filePath, 'r', encoding, 'replace') as fp:
            return fp.read()


_indexCache = {'signature': None, 'keys': frozenset()}


def getFavouritesIdentityKeys(favDir):
    # identity keys (IPTVFavourites.getItemIdentityKey) of everything stored in the favourites; read again
    # only when one of the favourites files changed, so it is cheap to ask for every list that is shown
    if not os_path.isdir(favDir):
        return frozenset()  # no favourites stored yet
    try:
        signature = []
        for fileName in sorted(os_listdir(favDir)):
            if fileName.startswith('iptv_') and fileName.endswith('.fav'):
                fileStat = os_stat(os_path.join(favDir, fileName))
                signature.append((fileName, fileStat.st_mtime, fileStat.st_size))
        if signature != _indexCache['signature']:
            helper = IPTVFavourites(favDir)
            keys = set()
            if helper.load():
                for group in helper.getGroups():
                    for item in group.get('items', []):
                        keys.add(IPTVFavourites.getItemIdentityKey(item.hostName, item.resolver, item.data))
            _indexCache['signature'] = signature
            _indexCache['keys'] = frozenset(keys)
    except Exception:
        printExc()
        _indexCache['signature'] = None
        return frozenset()
    return _indexCache['keys']
