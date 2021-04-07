# -*- coding: utf-8 -*-
#
#  Konfigurator dla iptv 2013
#  autorzy: j00zek, samsamsam
#

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetHostsList, IsHostEnabled, SaveHostsOrderList, SortHostsList, GetHostsAliases
from Plugins.Extensions.IPTVPlayer.components.configbase import ConfigBaseWidget
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
###################################################

###################################################
# FOREIGN import
###################################################
from enigma import gRGB
from Screens.MessageBox import MessageBox
from Screens.ChoiceBox import ChoiceBox
from Components.config import config, getConfigListEntry, NumericalTextInput
from Tools.BoundFunction import boundFunction
###################################################

class ConfigHostMenu(ConfigBaseWidget):
   
    def __init__(self, session, hostName):
        printDBG("ConfigHostMenu.__init__ ")
        self.list = []
        self.hostName = hostName
        ConfigBaseWidget.__init__(self, session)
        self.setup_title = _("Configuration [%s] service") % self.hostName
        self.host = __import__('Plugins.Extensions.IPTVPlayer.hosts.host' + hostName, globals(), locals(), ['GetConfigList'], -1)

    def __del__(self):
        printDBG("ConfigHostMenu.__del__ ")

    def __onClose(self):
        printDBG("ConfigHostMenu.__onClose ")
        ConfigBaseWidget.__onClose(self)

    def layoutFinished(self):
        ConfigBaseWidget.layoutFinished(self)
        self.setTitle("E2iPlayer " + (_("[%s] - configuration") % self.hostName))

    def runSetup(self):
        self.list = self.host.GetConfigList()
        ConfigBaseWidget.runSetup(self)

    def changeSubOptions(self):
        try:
            if not isinstance(self["config"].getCurrent()[1], NumericalTextInput):
                self.runSetup()
        except Exception:
            pass
        
class ConfigHostsMenu(ConfigBaseWidget):
   
    def __init__(self, session, listOfHostsNames):
        printDBG("ConfigHostsMenu.__init__ ")
        self.list = []
        self.privacePoliceWorningList = []
        self.hostsConfigsAvailableList = []
        self.listOfHostsNames = []
        self.orgListOfHostsNames = SortHostsList(listOfHostsNames)
        ConfigBaseWidget.__init__(self, session)
        self.setup_title = _("Services configuration")
        self.__preparHostsConfigs(self.orgListOfHostsNames)
        
        self.reorderingEnabled = False
        self.reorderingMode = False

    def __del__(self):
        printDBG("ConfigHostsMenu.__del__ ")

    def __onClose(self):
        printDBG("ConfigHostsMenu.__onClose ")
        ConfigBaseWidget.__onClose(self)

    def layoutFinished(self):
        ConfigBaseWidget.layoutFinished(self)
        self.setTitle(_("%s services configuration") % ('E2iPlayer'))

    def runSetup(self):
        ConfigBaseWidget.runSetup(self)

    #def changeSubOptions(self):
    #    self.runSetup()
        
    def isChanged(self):
        if self.orgListOfHostsNames != self.listOfHostsNames:
            return True
        return ConfigBaseWidget.isChanged(self)
        
    def saveOrCancel(self, operation="save"):
        if "save" == operation:
            if self.orgListOfHostsNames != self.listOfHostsNames:
                SaveHostsOrderList(self.listOfHostsNames)
        ConfigBaseWidget.saveOrCancel(self, operation)
        
    def isOkActive(self):
        curIndex = self["config"].getCurrentIndex()
        if curIndex < len(self.hostsConfigsAvailableList):
            return self.hostsConfigsAvailableList[curIndex]
        return False
        
    def setOKLabel(self):
        if self.reorderingEnabled:
            self["key_ok"].setText(_("OK"))
        else:
            ConfigBaseWidget.setOKLabel(self)

    def keyOK(self):
        if self["config"].instance is None:
            return
        if self.reorderingEnabled:
            if not self.reorderingMode:
                self["config"].instance.setForegroundColorSelected(gRGB(0xFF0505))
                self.reorderingMode = True
            else:
                self["config"].instance.setForegroundColorSelected(gRGB(0xFFFFFF))
                self.reorderingMode = False
            self.runSetup()
            return
  
        curIndex = self["config"].getCurrentIndex()
        currItem = self["config"].list[curIndex][1]
        if curIndex < len(self.listOfHostsNames):
            hostName = self.listOfHostsNames[curIndex]
            if self.hostsConfigsAvailableList[curIndex] and IsHostEnabled(hostName):
                addConf = False
                try:
                    self.host = __import__('Plugins.Extensions.IPTVPlayer.hosts.host' + hostName, globals(), locals(), ['GetConfigList'], -1)
                    if(len(self.host.GetConfigList()) < 1):
                        printDBG('ConfigMenu host "%s" does not have additional configs' % hostName)
                    else:
                        self.session.open(ConfigHostMenu, hostName=hostName)
                        addConf = True
                except Exception:
                    printExc('ConfigMenu host "%s" does not have method GetConfigList' % hostName)
                if not addConf:
                    self.hostsConfigsAvailableList[curIndex] = False
                    self.onSelectionChanged()
                    self.session.open(MessageBox, _("Service [%s] has no additional settings.") % hostName, type=MessageBox.TYPE_INFO, timeout=5)
        else:
            ConfigBaseWidget.keyOK(self)
    
    def keyMenu(self):     
        options = []
        if not self.reorderingEnabled:
            options.append((_("Enable reordering mode"), "REORDERING_ENABLED"))
        else:
            options.append((_("Disable reordering mode"), "REORDERING_DISABLED"))
        self.session.openWithCallback(self._changeMode, ChoiceBox, title=_("Select option"), list=options)
    
    def _changeMode(self, ret):
        if ret:
            if ret[1] == "REORDERING_ENABLED": 
                self.reorderingEnabled = True
            elif ret[1] == "REORDERING_DISABLED":
                self.reorderingEnabled = False
            if not self.reorderingEnabled:
                self.reorderingMode = False
                self["config"].instance.setForegroundColorSelected(gRGB(0xFFFFFF))
                self.runSetup()
            self.setOKLabel()
        
    def _moveItem(self, curIndex):
        assert(len(self.list) == len(self.hostsConfigsAvailableList) == len(self.listOfHostsNames))
        newIndex = self["config"].getCurrentIndex()
        if 0 <= curIndex and len(self.list) > curIndex and 0 <= newIndex and len(self.list) > newIndex:
            printDBG(">>>>>>>>>>>>>>>>>>> _moveItem")
            self.list.insert(newIndex, self.list.pop(curIndex))
            self.hostsConfigsAvailableList.insert(newIndex, self.hostsConfigsAvailableList.pop(curIndex))
            self.listOfHostsNames.insert(newIndex, self.listOfHostsNames.pop(curIndex))
            self.runSetup()
            
    def keyUp(self):
        if self.reorderingMode:
            printDBG(">>>>>>>>>>>>>>>>>>> keyUp")
            curIndex = self["config"].getCurrentIndex()
            ConfigBaseWidget.keyUp(self)
            self._moveItem(curIndex)
        else:
            ConfigBaseWidget.keyUp(self)
        
    def keyDown(self):
        if self.reorderingMode:
            printDBG(">>>>>>>>>>>>>>>>>>> keyDown")
            curIndex = self["config"].getCurrentIndex()
            ConfigBaseWidget.keyDown(self)
            self._moveItem(curIndex)
        else:
            ConfigBaseWidget.keyDown(self)
            
    def keyPageUp(self):
        if not self.reorderingEnabled:
            ConfigBaseWidget.keyPageUp(self)
    
    def keyPageDown(self):
        if not self.reorderingEnabled:
            ConfigBaseWidget.keyPageDown(self)
    
    def keyLeft(self):
        if not self.reorderingEnabled:
            ConfigBaseWidget.keyLeft(self)
        
    def keyRight(self):
        if not self.reorderingEnabled:
            ConfigBaseWidget.keyRight(self)
            
    def changedEntry(self):
        if self["config"].getCurrent()[1] in self.privacePoliceWorningList and self["config"].getCurrent()[1].value:
            message = _('Using this host in your country can be illegal.\nDo you want to continue at your own risk?')
            self.session.openWithCallback(boundFunction(self.privatePoliceWorningCallback, self["config"].getCurrent()[1]), MessageBox, text=message, type=MessageBox.TYPE_YESNO)
            
    def privatePoliceWorningCallback(self, configEntry=None, arg=None):
        if not arg:
            if configEntry != None:
                configEntry.value = False
        
    def __preparHostsConfigs(self, listOfHostsNames):
        '''
        prepar config entries for hosts Enabling/Disabling
        '''
        self.list = []
        self.hostsConfigsAvailableList = []
        self.listOfHostsNames = []
        sortedList = list(listOfHostsNames)
        hostsAliases = GetHostsAliases()
        for hostName in sortedList:
            try:    
                optionEntry = None
                exec('optionEntry = config.plugins.iptvplayer.host' + hostName)
                self.list.append(getConfigListEntry("%s" % hostsAliases.get('host' + hostName, hostName), optionEntry))
                if hostName in ['ipla']:
                    self.privacePoliceWorningList.append(optionEntry)
                self.hostsConfigsAvailableList.append(True)
                self.listOfHostsNames.append(hostName)
            except Exception:
                printExc()
