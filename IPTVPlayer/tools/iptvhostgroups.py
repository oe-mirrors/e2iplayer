# -*- coding: utf-8 -*-
#

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetMigratedHostOrderFile, GetHostsList, IsHostEnabled, IsTorrentPlaybackEnabled, TORRENT_HOSTS, getHostsPath
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostsGroupItem
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.__init__ import GRIDSUPPORT
###################################################

###################################################
# FOREIGN import
###################################################
import io
from os import unlink
from os.path import isfile
###################################################

FOLDER_PREFIX = 'folder:'


def IsFolderKey(key):
    # own folders inside a group are list entries with the key "folder:<id>"
    try:
        return key.startswith(FOLDER_PREFIX)
    except Exception:
        return False


class IPTVHostsGroups:
    # Own folders inside a group (e.g. "Sport", "Religion" in the Arabic group) are saved in the group's
    # own file as "folders": [{"id", "title", "icon", "hosts"}]; the group's "hosts" list keeps a
    # "folder:<id>" entry at the folder's place. A host is in one place only: the group's own list or one
    # folder. getHostsList() stays the whole group (folder hosts at the folder's place) for the group
    # counter, "Add host to group" and the web interface; getGroupLayout() is what the group view shows.
    def __init__(self):
        printDBG("IPTVHostsGroups.__init__")
        self.lastError = ''
        self.GROUPS_FILE = GetMigratedHostOrderFile('iptvplayerhostsgroups.json')

        # groups
        self.PREDEFINED_GROUPS = ["userdefined", "worldwide", "moviesandseries", "cartoonsandanime", "music", "sport", "live", "iptv", "torrent", "documentary", "science", "adult",
                                  "polish", "english", "german", "french", "russian", "hungarian", "arabic", "greek", "latino", "italian", "swedish", "dutch", "turkish", "balkans", "others", "all"]
        self.PREDEFINED_GROUPS_TITLES = {"userdefined": _("User defined"),
                                         "worldwide": _("Worldwide"),
                                         "moviesandseries": _("Movies and series"),
                                         "cartoonsandanime": _("Cartoons and anime"),
                                         "music": _("Music"),
                                         "sport": _("Sport"),
                                         "live": _("Live"),
                                         "iptv": _("IPTV Portals"),
                                         "torrent": _("Torrent"),
                                         "documentary": _("Documentary"),
                                         "science": _("Science"),
                                         "adult": _("Adult"),
                                         "polish": _("Polish"),
                                         "english": _("English"),
                                         "german": _("German"),
                                         "french": _("French"),
                                         "russian": _("Russian"),
                                         "hungarian": _("Hungarian"),
                                         "arabic": _("Arabic"),
                                         "greek": _("Greek"),
                                         "latino": _("Latino"),
                                         "italian": _("Italian"),
                                         'swedish': _("Nordic"),
                                         "dutch": _("Dutch"),
                                         "turkish": _("Turkish"),
                                         "balkans": _("Balkans"),
                                         "others": _("Others"),
                                         "all": _("All")
                                        }
        if not GRIDSUPPORT:
            self.PREDEFINED_GROUPS.remove("all")
            del self.PREDEFINED_GROUPS_TITLES["all"]

        self.LOADED_GROUPS = []
        self.LOADED_GROUPS_TITLES = {}
        self.LOADED_DISABLED_GROUPS = []

        self.CACHE_GROUPS = None

        # hosts
        self.PREDEFINED_HOSTS = json_loads(self._loadFromFile(getHostsPath("hostgroups.txt")))
        self.LOADED_HOSTS = {}
        self.LOADED_DISABLED_HOSTS = {}
        self.LOADED_FOLDERS = {}
        self.CACHE_HOSTS = {}
        self.CACHE_LAYOUT = {}

        self.ADDED_HOSTS = {}

        self.hostListFromFolder = None
        self.hostListFromList = None

    @staticmethod
    def _hiddenGroups():
        return () if IsTorrentPlaybackEnabled() else ("torrent",)

    def _getGroupFile(self, groupName):
        printDBG("IPTVHostsGroups._getGroupFile")
        return GetMigratedHostOrderFile("iptvplayer%sgroup.json" % groupName)

    def getLastError(self):
        return self.lastError

    def addHostToGroup(self, groupName, hostName):
        printDBG("IPTVHostsGroups.addHostToGroup")
        hostsList = self.getHostsList(groupName)
        self.ADDED_HOSTS[groupName] = []
        if hostName in hostsList or hostName in self.ADDED_HOSTS[groupName]:
            self.lastError = _('This host has been added already to this group.')
            return False
        self.ADDED_HOSTS[groupName].append(hostName)
        return True

    def flushAddedHosts(self):
        printDBG("IPTVHostsGroups.flushAddedHosts")
        for groupName in self.ADDED_HOSTS:
            if 0 == len(self.ADDED_HOSTS[groupName]):
                continue
            # the group's own list (with its folder entries), not the whole group with the folder hosts
            newList = list(self.getGroupLayout(groupName))
            newList.extend(self.ADDED_HOSTS[groupName])
            self.setHostsList(groupName, newList)
        self.ADDED_HOSTS = {}

    def getGroupsWithoutHost(self, hostName):
        groupList = self.getGroupsList()
        retList = []
        for groupItem in groupList:
            hostsList = self.getHostsList(groupItem.name)
            if hostName not in hostsList and hostName not in self.ADDED_HOSTS.get(groupItem.name, []):
                retList.append(groupItem)
        return retList

    def getHostsList(self, groupName):
        printDBG("IPTVHostsGroups.getHostsList")
        if groupName in self.CACHE_HOSTS:
            return self.CACHE_HOSTS[groupName]

        if self.hostListFromFolder is None:
            self.hostListFromFolder = GetHostsList(fromList=False, fromHostFolder=True)
        if self.hostListFromList is None:
            self.hostListFromList = GetHostsList(fromList=True, fromHostFolder=False)

        groupFile = self._getGroupFile(groupName)
        self._loadHosts(groupFile, groupName, self.hostListFromFolder, self.hostListFromFolder)

        inFolders = self._folderHostsSet(groupName)
        layout = []
        for host in self.LOADED_HOSTS[groupName]:
            if IsFolderKey(host) or IsHostEnabled(host):
                layout.append(host)

        for host in self.PREDEFINED_HOSTS.get(groupName, []):
            if host not in layout and host not in inFolders and host not in self.LOADED_DISABLED_HOSTS[groupName] and host in self.hostListFromList and host in self.hostListFromFolder and IsHostEnabled(host):
                layout.append(host)

        self.CACHE_LAYOUT[groupName] = layout
        self.CACHE_HOSTS[groupName] = self._expandLayout(groupName, layout)
        return self.CACHE_HOSTS[groupName]

    def getGroupLayout(self, groupName):
        # what the group view shows: the group's own hosts and its "folder:<id>" entries, in their order
        self.getHostsList(groupName)
        return self.CACHE_LAYOUT[groupName]

    def _expandLayout(self, groupName, layout):
        # the whole group: a folder's hosts at the folder's place
        hosts = []
        for key in layout:
            if IsFolderKey(key):
                for host in self.getFolderHosts(groupName, key):
                    if host not in hosts:
                        hosts.append(host)
            elif key not in hosts:
                hosts.append(key)
        return hosts

    def _folderHostsSet(self, groupName):
        hosts = set()
        for folder in self.LOADED_FOLDERS.get(groupName, []):
            hosts.update(folder['hosts'])
        return hosts

    def getFolders(self, groupName):
        # [{'key', 'id', 'title', 'icon', 'hosts'}] in the order the group shows them
        self.getHostsList(groupName)
        retList = []
        for key in self.CACHE_LAYOUT[groupName]:
            folder = self.getFolder(groupName, key)
            if folder is not None:
                retList.append(folder)
        return retList

    def getFolder(self, groupName, key):
        # a copy of the folder with its list key, None for a host / a folder that is gone
        folder = self._folderById(groupName, key)
        if folder is None:
            return None
        ret = dict(folder)
        ret['key'] = key
        return ret

    def getFolderHosts(self, groupName, key):
        # the hosts the folder shows: switched on and (torrent hosts) only with torrent playback on
        folder = self.getFolder(groupName, key)
        if folder is None:
            return []
        return [host for host in folder['hosts'] if IsHostEnabled(host)]

    def _folderById(self, groupName, key):
        # the stored folder itself (changes go into the group file with _saveState())
        if not IsFolderKey(key):
            return None
        if groupName not in self.LOADED_FOLDERS:
            self.getHostsList(groupName)
        folderId = key[len(FOLDER_PREFIX):]
        for folder in self.LOADED_FOLDERS.get(groupName, []):
            if folder['id'] == folderId:
                return folder
        return None

    def createFolder(self, groupName, title, hosts=None):
        # new folder behind the group's last folder (first one: on top); hosts are moved into it
        printDBG("IPTVHostsGroups.createFolder groupName[%s]" % groupName)
        self.getHostsList(groupName)
        ids = []
        for folder in self.LOADED_FOLDERS[groupName]:
            try:
                ids.append(int(folder['id']))
            except Exception:
                pass
        folderId = str(max(ids) + 1 if ids else 1)
        key = FOLDER_PREFIX + folderId
        self.LOADED_FOLDERS[groupName].append({'id': folderId, 'title': title, 'icon': '', 'hosts': []})
        layout = list(self.CACHE_LAYOUT[groupName])
        pos = 0
        for idx, item in enumerate(layout):
            if IsFolderKey(item):
                pos = idx + 1
        layout.insert(pos, key)
        if hosts:
            layout = self._moveHosts(groupName, layout, hosts, key)
        if self._saveState(groupName, layout):
            return key
        return None

    def renameFolder(self, groupName, key, title):
        self.getHostsList(groupName)
        folder = self._folderById(groupName, key)
        if folder is None:
            return False
        folder['title'] = title
        return self._saveState(groupName, list(self.CACHE_LAYOUT[groupName]))

    def setFolderIcon(self, groupName, key, icon):
        self.getHostsList(groupName)
        folder = self._folderById(groupName, key)
        if folder is None:
            return False
        folder['icon'] = icon
        return self._saveState(groupName, list(self.CACHE_LAYOUT[groupName]))

    def deleteFolder(self, groupName, key):
        # the folder's hosts go back into the group's own list, at the folder's place
        printDBG("IPTVHostsGroups.deleteFolder groupName[%s] key[%s]" % (groupName, key))
        self.getHostsList(groupName)
        folder = self._folderById(groupName, key)
        if folder is None:
            return False
        layout = list(self.CACHE_LAYOUT[groupName])
        pos = layout.index(key) if key in layout else len(layout)
        if key in layout:
            layout.remove(key)
        for host in folder['hosts']:
            if host not in layout:
                layout.insert(pos, host)
                pos += 1
        self.LOADED_FOLDERS[groupName].remove(folder)
        return self._saveState(groupName, layout)

    def moveHostsToFolder(self, groupName, hosts, key=None):
        # key None: out of their folder, back into the group's own list (behind the last folder)
        printDBG("IPTVHostsGroups.moveHostsToFolder groupName[%s] key[%s] hosts[%s]" % (groupName, key, hosts))
        self.getHostsList(groupName)
        if key is not None and self._folderById(groupName, key) is None:
            return False
        layout = self._moveHosts(groupName, list(self.CACHE_LAYOUT[groupName]), hosts, key)
        return self._saveState(groupName, layout)

    def setFolderContents(self, groupName, key, hosts):
        # "Select hosts" list of a folder: exactly these hosts are in the folder afterwards (they leave
        # their old place), the ones that were in it and are not ticked any more go back to the group
        self.getHostsList(groupName)
        folder = self._folderById(groupName, key)
        if folder is None:
            return False
        removed = [host for host in folder['hosts'] if host not in hosts and IsHostEnabled(host)]
        layout = self._moveHosts(groupName, list(self.CACHE_LAYOUT[groupName]), [host for host in hosts if host not in folder['hosts']], key)
        if removed:
            layout = self._moveHosts(groupName, layout, removed, None)
        return self._saveState(groupName, layout)

    def _moveHosts(self, groupName, layout, hosts, key):
        for folder in self.LOADED_FOLDERS[groupName]:
            folder['hosts'] = [host for host in folder['hosts'] if host not in hosts]
        layout = [item for item in layout if item not in hosts]
        target = self._folderById(groupName, key)
        if target is not None:
            target['hosts'].extend([host for host in hosts if host not in target['hosts']])
        else:
            pos = 0
            for idx, item in enumerate(layout):
                if IsFolderKey(item):
                    pos = idx + 1
            for host in hosts:
                layout.insert(pos, host)
                pos += 1
        return layout

    def setFolderHostsList(self, groupName, key, hostsList):
        # order (and removed hosts) of the folder view; hosts the folder does not show right now
        # (switched off, torrent playback off) keep their place in it
        printDBG("IPTVHostsGroups.setFolderHostsList groupName[%s] key[%s] hostsList[%s]" % (groupName, key, hostsList))
        self.getHostsList(groupName)
        folder = self._folderById(groupName, key)
        if folder is None:
            return False
        shown = self.getFolderHosts(groupName, key)
        removed = [host for host in shown if host not in hostsList]
        newHosts = list(hostsList)
        for idx, host in enumerate(folder['hosts']):
            if host not in shown and host not in newHosts:
                newHosts.insert(min(idx, len(newHosts)), host)
        folder['hosts'] = newHosts
        disabledHosts = list(self.LOADED_DISABLED_HOSTS[groupName])
        for host in removed:
            if host in self.PREDEFINED_HOSTS.get(groupName, []) and host not in disabledHosts:
                disabledHosts.append(host)
        return self._saveState(groupName, list(self.CACHE_LAYOUT[groupName]), disabledHosts)

    def _saveState(self, groupName, layout, disabledHosts=None):
        if disabledHosts is None:
            disabledHosts = self.LOADED_DISABLED_HOSTS[groupName]
        self.LOADED_DISABLED_HOSTS[groupName] = disabledHosts
        self.LOADED_HOSTS[groupName] = list(layout)
        self.CACHE_LAYOUT[groupName] = [item for item in layout if IsFolderKey(item) or IsHostEnabled(item)]
        self.CACHE_HOSTS[groupName] = self._expandLayout(groupName, self.CACHE_LAYOUT[groupName])
        outObj = {"version": 0, "hosts": list(layout), "disabled_hosts": disabledHosts}
        if self.LOADED_FOLDERS.get(groupName):
            outObj['folders'] = self.LOADED_FOLDERS[groupName]
        return self._saveHosts(outObj, self._getGroupFile(groupName))

    def setHostsList(self, groupName, hostsList):
        printDBG("IPTVHostsGroups.setHostsList groupName[%s], hostsList[%s]" % (groupName, hostsList))
        # hostsList - must be updated with host which were not disabled in this group but they are not
        # available or they are disabled globally
        # hostsList is the group's own list as the group view shows it, "folder:<id>" entries included
        self.getHostsList(groupName)
        savedHosts = list(hostsList)

        # add 091026: torrent hosts hidden right now (torrent playback off) were not in the list the user edited - they
        # keep their saved place (e.g. in "User defined") instead of being dropped; the shown list stays without them
        if not IsTorrentPlaybackEnabled():
            for idx, host in enumerate(self.LOADED_HOSTS.get(groupName, [])):
                if host in TORRENT_HOSTS and host not in savedHosts:
                    savedHosts.insert(min(idx, len(savedHosts)), host)

        # a folder entry that went missing from the list (it cannot be removed there) keeps the folder on top
        for folder in reversed(self.LOADED_FOLDERS.get(groupName, [])):
            if FOLDER_PREFIX + folder['id'] not in savedHosts:
                savedHosts.insert(0, FOLDER_PREFIX + folder['id'])

        # check if some host from diabled one has been enabled
        inFolders = self._folderHostsSet(groupName)
        disabledHosts = []
        for host in self.LOADED_DISABLED_HOSTS[groupName]:
            if host not in hostsList and host not in inFolders:
                disabledHosts.append(host)

        # check if some host has been disabled
        for host in self.CACHE_LAYOUT[groupName]:
            if host not in hostsList and host in self.PREDEFINED_HOSTS.get(groupName, []) and host not in disabledHosts:
                disabledHosts.append(host)

        return self._saveState(groupName, savedHosts, disabledHosts)

    def resetHostList(self, groupName):
        printDBG("IPTVHostsGroups.resetHostList groupName[%s]" % (groupName))
        groupFile = self._getGroupFile(groupName)
        if isfile(groupFile):
            unlink(groupFile)

    def resetGroupList(self):
        # drop the whole groups file -> getGroupsList() rebuilds order and
        # visibility from hostgroups.txt defaults
        printDBG("IPTVHostsGroups.resetGroupList")
        if isfile(self.GROUPS_FILE):
            unlink(self.GROUPS_FILE)

    def resetHostsOrder(self):
        # drop the top-level hosts-order file (what "Sort by name" / manual
        # reordering of the main list and the "all" group persist)
        printDBG("IPTVHostsGroups.resetHostsOrder")
        orderFile = GetMigratedHostOrderFile('iptvplayerhostsorder')
        if isfile(orderFile):
            unlink(orderFile)

    def _saveHosts(self, outObj, groupFile):
        printDBG("IPTVHostsGroups._saveHosts")
        ret = True
        try:
            data = json_dumps(outObj)
            self._saveToFile(groupFile, data)
        except Exception:
            printExc()
            self.lastError = _("Error writing file \"%s\".\n") % groupFile
            ret = False
        return ret

    def _loadHosts(self, groupFile, groupName, hostListFromFolder, hostListFromList):
        printDBG("IPTVHostsGroups._loadHosts groupName[%s]" % groupName)
        predefinedHosts = self.PREDEFINED_HOSTS.get(groupName, [])
        hosts = []
        disabledHosts = []
        folders = []

        ret = True
        if isfile(groupFile):
            try:
                data = self._loadFromFile(groupFile)
                data = json_loads(data)
                for item in data.get('disabled_hosts', []):
                    # we need only information about predefined hosts which were disabled
                    if item in predefinedHosts and item in hostListFromList:
                        disabledHosts.append(str(item))

                for item in data.get('folders', []):
                    try:
                        folderId = str(item['id'])
                        if not folderId or folderId in [folder['id'] for folder in folders]:
                            continue
                        folderHosts = []
                        for host in item.get('hosts', []):
                            if host in hostListFromFolder and host not in folderHosts:
                                folderHosts.append(str(host))
                        folders.append({'id': folderId, 'title': str(item.get('title') or folderId), 'icon': str(item.get('icon') or ''), 'hosts': folderHosts})
                    except Exception:
                        printExc()
                folderKeys = [FOLDER_PREFIX + folder['id'] for folder in folders]
                inFolders = set()
                for folder in folders:
                    # a host is in one folder only
                    folder['hosts'] = [host for host in folder['hosts'] if host not in inFolders]
                    inFolders.update(folder['hosts'])

                for item in data.get('hosts', []):
                    if item in hosts:
                        continue
                    if item in folderKeys or (item in hostListFromFolder and item not in inFolders):
                        hosts.append(str(item))
                # a folder without its place in the list goes on top
                hosts = [key for key in folderKeys if key not in hosts] + hosts
            except Exception:
                printExc()

        self.LOADED_HOSTS[groupName] = hosts
        self.LOADED_DISABLED_HOSTS[groupName] = disabledHosts
        self.LOADED_FOLDERS[groupName] = folders

    def getGroupsList(self):
        printDBG("IPTVHostsGroups.getGroupsList")
        if self.CACHE_GROUPS is not None:
            return self.CACHE_GROUPS
        self._loadGroups()
        # "config" (both GRIDSUPPORT and Legacy) and "all" (Legacy only -
        # GRIDSUPPORT treats "all" as one of its own real PREDEFINED_GROUPS
        # instead) are reserved keys iptvplayerwidget.py's selectGroup()/
        # selectHostFromSingleList() append separately, unconditionally,
        # every single time a list is built - they must never ALSO come
        # from here, or they show up duplicated. The save logic in
        # selectGroupCallback()/selectHostCallback() guards against
        # persisting these two reserved keys as real group names when
        # they end up anywhere but the tail of the list (e.g. after "Sort
        # by name" in the BLUE menu - see those methods' own comments).
        # Filtering them out HERE as well self-heals any install whose
        # saved file already has this corruption, without needing to
        # hand-edit the JSON on the box.
        reservedKeys = {'config'} if GRIDSUPPORT else {'config', 'all'}
        loadedGroups = [g for g in self.LOADED_GROUPS if g not in reservedKeys]
        loadedDisabledGroups = [g for g in self.LOADED_DISABLED_GROUPS if g not in reservedKeys]
        groups = list(loadedGroups)

        for group in self.PREDEFINED_GROUPS:
            if group not in loadedGroups and group not in loadedDisabledGroups:
                groups.append(group)
        # the torrent group only while torrent playback (TorrServer) is switched on
        hidden = self._hiddenGroups()
        groups = [group for group in groups if group not in hidden]

        groupList = []
        for group in groups:
            title = self.PREDEFINED_GROUPS_TITLES.get(group, '')
            if title == '':
                title = self.LOADED_GROUPS_TITLES.get(group, '')
            if title == '':
                title = group.title()
            item = CHostsGroupItem(group, _(title))
            groupList.append(item)
        self.CACHE_GROUPS = groupList
        return groupList

    def getPredefinedGroupsList(self):
        printDBG("IPTVHostsGroups.getPredefinedGroupsList")
        groupList = []
        # fix 091026: a hidden group is not offered in the groups configuration either - it would show up as "off"
        # there although setGroupList() keeps it enabled
        hidden = self._hiddenGroups()
        for group in self.PREDEFINED_GROUPS:
            if group in hidden:
                continue
            title = self.PREDEFINED_GROUPS_TITLES[group]
            item = CHostsGroupItem(group, title)
            groupList.append(item)
        return groupList

    def setGroupList(self, groupList):
        printDBG("IPTVHostsGroups.setGroupList groupList[%s]" % groupList)
        # update disabled groups
        outObj = {"version": 0, "groups": [], "disabled_groups": []}

        # a group hidden right now was not in the list the user edited: it keeps its saved place / state
        hidden = self._hiddenGroups()
        groupList = list(groupList)
        # legacy grid (also "Force legacy grid" on a GRIDSUPPORT image): "all" is not a group there - it keeps
        # its saved place / state, else switching back to the native grid drops the saved order (_loadGroups())
        kept = list(hidden) if GRIDSUPPORT else list(hidden) + ['all']
        if kept:
            self._loadGroups()
        for group in kept:
            if group in self.LOADED_GROUPS and group not in groupList:
                groupList.insert(min(self.LOADED_GROUPS.index(group), len(groupList)), group)

        for group in self.PREDEFINED_GROUPS:
            if group not in groupList and (group not in hidden or group in self.LOADED_DISABLED_GROUPS):
                outObj['disabled_groups'].append(group)
        if not GRIDSUPPORT and 'all' in self.LOADED_DISABLED_GROUPS and 'all' not in groupList:
            outObj['disabled_groups'].append('all')

        for group in groupList:
            outObj['groups'].append({'name': group})
            if group in self.LOADED_GROUPS_TITLES:
                outObj['groups'][-1]['title'] = self.LOADED_GROUPS_TITLES[group]  # fix 091026: was ['groups']['title'] (TypeError)

        return self._saveGroups(outObj)

    def _saveGroups(self, outObj):
        printDBG("IPTVHostsGroups._saveGroups")
        ret = True
        try:
            data = json_dumps(outObj)
            self._saveToFile(self.GROUPS_FILE, data)
        except Exception:
            printExc()
            self.lastError = _("Error writing file \"%s\".\n") % self.GROUPS_FILE
            ret = False
        return ret

    def _loadGroups(self):
        printDBG("IPTVHostsGroups._loadGroups")
        self.LOADED_GROUPS = []
        self.LOADED_DISABLED_GROUPS = []
        self.LOADED_GROUPS_TITLES = {}

        groups = []
        titles = {}
        disabledGroups = []

        ret = True
        if isfile(self.GROUPS_FILE):
            try:
                data = self._loadFromFile(self.GROUPS_FILE)
                data = json_loads(data)
                for item in data.get('disabled_groups', []):
                    # we need only information about predefined groups which were disabled ("all" also on the
                    # legacy grid, where it is no group - kept for the native grid, see setGroupList())
                    if item in self.PREDEFINED_GROUPS or item == 'all':
                        disabledGroups.append(str(item))

                for item in data.get('groups', []):
                    name = str(item['name'])
                    groups.append(name)
                    if 'title' in item:
                        titles[name] = str(item['title'])
            except Exception:
                printExc()

        if GRIDSUPPORT and "all" not in groups and "all" not in disabledGroups:
            return

        self.LOADED_GROUPS = groups
        self.LOADED_DISABLED_GROUPS = disabledGroups
        self.LOADED_GROUPS_TITLES = titles

    def _saveToFile(self, filePath, data, encoding='utf-8'):
        printDBG("IPTVHostsGroups._saveToFile filePath[%s]" % filePath)
        with io.open(filePath, 'w', encoding=encoding, errors='replace', newline='') as fp:
            fp.write(data)

    def _loadFromFile(self, filePath, encoding='utf-8'):
        printDBG("IPTVHostsGroups._loadFromFile filePath[%s]" % filePath)
        with io.open(filePath, 'r', encoding=encoding, errors='replace', newline='') as fp:
            return fp.read()
