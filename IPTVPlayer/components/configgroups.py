# -*- coding: utf-8 -*-
#
#  Konfigurator dla iptv 2013
#  autorzy: j00zek, samsamsam
#

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetHostTitle
from Plugins.Extensions.IPTVPlayer.components.configbase import ConfigBaseWidget
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.tools.iptvhostgroups import IPTVHostsGroups, IsFolderKey
###################################################

###################################################
# FOREIGN import
###################################################
from Components.config import getConfigListEntry, ConfigYesNo
###################################################


class ConfigGroupsMenu(ConfigBaseWidget):
    # BLUE is a bulk "Enable all groups"/"Disable all groups" toggle,
    # same HAS_BLUE_KEY opt-in ConfigHostsMenu (confighost.py) uses for
    # its own reordering-mode toggle. Saves clicking every single
    # ConfigYesNo entry by hand when the user wants either extreme (all on
    # to reset, all off to start from a clean slate).
    HAS_BLUE_KEY = True

    def __init__(self, session):
        printDBG("ConfigGroupsMenu.__init__ -------------------------------")
        self.list = []
        self.inList = []
        self.groupObj = IPTVHostsGroups()

        ConfigBaseWidget.__init__(self, session)
        self.setup_title = _("E2iPlayer enable/disabled groups")
        self.__preparLists()
        self._updateBlueLabel()

    def __del__(self):
        printDBG("ConfigGroupsMenu.__del__ -------------------------------")

    def __onClose(self):
        printDBG("ConfigGroupsMenu.__onClose -----------------------------")
        ConfigBaseWidget.__onClose(self)

    def layoutFinished(self):
        ConfigBaseWidget.layoutFinished(self)
        self.setTitle(self.setup_title)

    def runSetup(self):
        ConfigBaseWidget.runSetup(self)

    def _allGroupsEnabled(self):
        return all(entry[1].value for entry in self.list)

    def _updateBlueLabel(self):
        self["key_blue"].setText(_("Disable all groups") if self._allGroupsEnabled() else _("Enable all groups"))

    def keyBlue(self):
        # toggles every entry to the opposite of the current overall state
        # (all currently enabled -> disable all, otherwise -> enable all -
        # same "target is the complement of fully-on" convention a plain
        # on/off switch would use, so a half-enabled list always goes to
        # "all enabled" first on press, matching what the label about to
        # be shown promises)
        target = not self._allGroupsEnabled()
        for entry in self.list:
            entry[1].value = target
        self.runSetup()
        self._updateBlueLabel()

    def changedEntry(self):
        # keep the BLUE label in sync when the user toggles an individual
        # entry by hand too, not just via keyBlue() itself
        ConfigBaseWidget.changedEntry(self)
        self._updateBlueLabel()

    def saveOrCancel(self, operation="save"):
        if "save" == operation:
            groupList = []
            currentList = self.groupObj.getGroupsList()
            for item in currentList:
                # find idx
                validIdx = False
                idx = -1
                for idx in range(len(self.inList)):
                    if self.inList[idx].name == item.name:
                        validIdx = True
                        break

                if not validIdx or self.list[idx][1].value:
                    groupList.append(item.name)

            for idx in range(len(self.list)):
                if self.list[idx][1].value and self.inList[idx].name not in groupList:
                    groupList.append(self.inList[idx].name)

            self.groupObj.setGroupList(groupList)

    def __preparLists(self):
        currentList = self.groupObj.getGroupsList()
        predefinedList = self.groupObj.getPredefinedGroupsList()
        self.list = []
        self.inList = []
        for item in predefinedList:
            enabled = False
            for it in currentList:
                if item.name == it.name:
                    enabled = True
                    break
            optionEntry = ConfigYesNo(default=enabled)
            self.list.append(getConfigListEntry(item.title, optionEntry))
            self.inList.append(item)


class ConfigGroupFolderMenu(ConfigBaseWidget):
    # "Select hosts for this folder...": every host of the group with an on/off switch, OK ticks / unticks
    # the row, BLUE ticks / unticks all. GREEN saves: the ticked hosts are in the folder afterwards (taken
    # out of the group's own list or another folder), the unticked ones of the folder go back to the group.
    HAS_BLUE_KEY = True

    def __init__(self, session, groupObj, groupName, folderKey, title=''):
        printDBG("ConfigGroupFolderMenu.__init__ -------------------------------")
        self.groupObj = groupObj
        self.groupName = groupName
        self.folderKey = folderKey
        self.hosts = []
        ConfigBaseWidget.__init__(self, session)
        self.setup_title = title
        self.__prepareLists()
        self._updateBlueLabel()

    def layoutFinished(self):
        ConfigBaseWidget.layoutFinished(self)
        self.setTitle(self.setup_title)

    def _allSelected(self):
        return bool(self.list) and all(entry[1].value for entry in self.list)

    def _updateBlueLabel(self):
        self["key_blue"].setText(_("Unselect all") if self._allSelected() else _("Select all"))

    def keyBlue(self):
        target = not self._allSelected()
        for entry in self.list:
            entry[1].value = target
        self.runSetup()
        self._updateBlueLabel()

    def isOkActive(self):
        return self["config"].getCurrent() is not None

    def keyOK(self):
        current = self["config"].getCurrent()
        if current is None:
            return
        current[1].value = not current[1].value
        self["config"].invalidateCurrent()
        self.changedEntry()

    def changedEntry(self):
        ConfigBaseWidget.changedEntry(self)
        self._updateBlueLabel()

    def keyDefaults(self):
        # YELLOW: back to the folder's hosts as they were when the list was opened
        self.resetToDefaults(lambda: self.list)
        self._updateBlueLabel()

    def saveOrCancel(self, operation="save"):
        if "save" == operation:
            hosts = [self.hosts[idx] for idx in range(len(self.list)) if self.list[idx][1].value]
            try:
                self.groupObj.setFolderContents(self.groupName, self.folderKey, hosts)
            except Exception:
                printExc()

    def __prepareLists(self):
        # the folder's hosts first, then the group's own list, then the hosts of the other folders
        self.list = []
        self.hosts = []
        inFolder = self.groupObj.getFolderHosts(self.groupName, self.folderKey)
        rows = [(host, '') for host in inFolder]
        others = []
        for key in self.groupObj.getGroupLayout(self.groupName):
            if not IsFolderKey(key):
                rows.append((key, ''))
            elif key != self.folderKey:
                folder = self.groupObj.getFolder(self.groupName, key)
                if folder is not None:
                    others.extend([(host, folder['title']) for host in self.groupObj.getFolderHosts(self.groupName, key)])
        for host, folderTitle in rows + others:
            if host in self.hosts:
                continue
            title = GetHostTitle(host) or host
            if folderTitle:
                title = '%s  [%s]' % (title, folderTitle)
            optionEntry = ConfigYesNo(default=host in inFolder)
            self.list.append(getConfigListEntry(title, optionEntry))
            self.hosts.append(host)
