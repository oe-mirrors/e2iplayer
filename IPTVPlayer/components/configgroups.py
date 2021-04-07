# -*- coding: utf-8 -*-
#
#  Konfigurator dla iptv 2013
#  autorzy: j00zek, samsamsam
#

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.components.configbase import ConfigBaseWidget
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.tools.iptvhostgroups import IPTVHostsGroups
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostsGroupItem
###################################################

###################################################
# FOREIGN import
###################################################
from enigma import gRGB
from Screens.MessageBox import MessageBox
from Screens.ChoiceBox import ChoiceBox
from Components.config import config, getConfigListEntry, NumericalTextInput, ConfigYesNo
from Tools.BoundFunction import boundFunction
###################################################
        

class ConfigGroupsMenu(ConfigBaseWidget):
   
    def __init__(self, session):
        printDBG("ConfigGroupsMenu.__init__ -------------------------------")
        self.list = []
        self.inList = []
        self.groupObj = IPTVHostsGroups()
        
        ConfigBaseWidget.__init__(self, session)
        self.setup_title = _("E2iPlayer enable/disabled groups")
        self.__preparLists()

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
        
