# -*- coding: utf-8 -*-
#
#  Konfigurator dla iptv 2013
#  autorzy: j00zek, samsamsam
#


###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.components.iptvdirbrowser import IPTVDirectorySelectorWidget, IPTVFileSelectorWidget
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.e2ivkselector import GetVirtualKeyboard
###################################################

###################################################
# FOREIGN import
###################################################
import re
from enigma import getDesktop
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen

from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.config import ConfigDirectory, ConfigText, ConfigPassword, ConfigBoolean, ConfigSelection, configfile
from Components.ConfigList import ConfigListScreen
from Components.Sources.StaticText import StaticText
from Tools.BoundFunction import boundFunction
###################################################
COLORS_DEFINITONS = [("#000000", _("black")), ("#C0C0C0", _("silver")), ("#808080", _("gray")), ("#FFFFFF", _("white")), ("#800000", _("maroon")), ("#FF0000", _("red")), ("#800080", _("purple")), ("#FF00FF", _("fuchsia")),
                     ("#008000", _("green")), ("#00FF00", _("lime")), ("#808000", _("olive")), ("#FFFF00", _("yellow")), ("#000080", _("navy")), ("#0000FF", _("blue")), ("#008080", _("teal")), ("#00FFFF", _("aqua"))]


class ConfigIPTVFileSelection(ConfigDirectory):
    def __init__(self, ignoreCase=True, fileMatch=None, default="", visible_width=60):
        self.fileMatch = fileMatch
        self.ignoreCase = ignoreCase
        ConfigDirectory.__init__(self, default, visible_width)


class ConfigBaseWidget(Screen, ConfigListScreen):
    skin = """
        <screen position="center,center" size="1020,660" resolution="1280,720" title="" backgroundColor="#34111112" flags="wfNoBorder">
            <widget source="Title" render="Label" position="240,10" size="780,40" foregroundColor="white" backgroundColor="black" borderWidth="1" borderColor="black" transparent="1" zPosition="1" font="Regular;24" valign="center" />
            <widget name="config" position="10,64" size="1000,546" itemHeight="32" font="Regular;20" scrollbarMode="showOnDemand" scrollbarSliderBorderWidth="1" scrollbarForegroundColor="#1b5a91" scrollbarBorderColor="#00b6b6b6" enableWrapAround="1" transparent="1" foregroundColor="white" backgroundColor="black" foregroundColorSelected="white" backgroundColorSelected="#1b5a91" borderWidth="1" borderColor="black" shadowColor="black" shadowOffset="-2,-2" />
            <ePixmap position="22,627" size="40,26" zPosition="10" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/ok.png" transparent="1" alphatest="blend" />
            <ePixmap position="80,627" size="40,26" zPosition="10" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/exit.png" transparent="1" alphatest="blend" />
            <ePixmap position="138,627" size="40,26" zPosition="10" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/menu.png" transparent="1" alphatest="blend" />
            <widget name="footnote" position="150,12" size="100,30" foregroundColor="white" backgroundColor="black" borderWidth="1" borderColor="black" transparent="1" zPosition="1" font="Regular;24" valign="center" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/iptvlogo.png" position="12,10" size="100,40" alphatest="blend" transparent="1" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/red.png" position="240,630" size="20,20" alphatest="blend" transparent="1" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/green.png" position="470,630" size="20,20" alphatest="blend" transparent="1" />
            <widget source="key_red" render="Label" position="274,626" size="200,28" zPosition="1" font="Regular;20" backgroundColor="black" foregroundColor="white" halign="left" transparent="1" valign="center" noWrap="1" />
            <widget source="key_green" render="Label" position="504,626" size="200,28" zPosition="1" font="Regular;20" backgroundColor="black" foregroundColor="white" halign="left" transparent="1" valign="center" noWrap="1" />
            <eLabel name="BG_Title" position="0,0" size="1020,60" backgroundColor="#100d0f16" zPosition="-1" />
            <eLabel name="BG_Buttons" position="0,612" size="1020,48" backgroundColor="#100d0f16" zPosition="-1" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/smallshadowline.png" position="0,60" size="1020,2" zPosition="2" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/smallshadowline.png" position="0,610" size="1020,2" zPosition="2" />
        </screen>"""

    fullHD = getDesktop(0).size().width() == 1920
    if fullHD:
        skin = skin.replace("/HD/", "/FHD/")

    def __init__(self, session):
        printDBG("ConfigBaseWidget.__init__ -------------------------------")

        Screen.__init__(self, session)

        self.skinName = ["ConfigBaseWidgetScreen", "ConfigBaseWidget"]

        self.onChangedEntry = []
        self.list = []
        ConfigListScreen.__init__(self, self.list, session=session, on_change=self.changedEntry)
        self.setup_title = (_("E2iPlayer - settings"))

        self["key_green"] = StaticText(_("Save"))
        self["footnote"] = Label(_(" "))
        self["key_red"] = StaticText(_("Cancel"))

        self["actions"] = ActionMap(["SetupActions", "ColorActions", "WizardActions", "ListboxActions", "IPTVPlayerListActions"],
            {
                "cancel": self.keyExit,
                "green": self.keySave,
                "ok": self.keyOK,
                "red": self.keyCancel,
                "menu": self.keyMenu,

                "up": self.keyUp,
                "down": self.keyDown,
                "moveUp": self.keyUp,
                "moveDown": self.keyDown,
                "moveTop": self.keyHome,
                "moveEnd": self.keyEnd,
                "home": self.keyHome,
                "end": self.keyEnd,
                "pageUp": self.keyPageUp,
                "pageDown": self.keyPageDown
            }, -2)

        self.onLayoutFinish.append(self.layoutFinished)
        self.onClose.append(self.__onClose)
        self.isOkEnabled = False

    def __del__(self):
        printDBG("ConfigBaseWidget.__del__ -------------------------------")

    def __onClose(self):
        printDBG("ConfigBaseWidget.__onClose -----------------------------")
        self.onClose.remove(self.__onClose)
        self.onLayoutFinish.remove(self.layoutFinished)
        if self.onSelectionChanged in self["config"].onSelectionChanged:
            self["config"].onSelectionChanged.remove(self.onSelectionChanged)

    def layoutFinished(self):
        self.setTitle(_("E2iPlayer - settings"))
        if self.onSelectionChanged not in self["config"].onSelectionChanged:
            self["config"].onSelectionChanged.append(self.onSelectionChanged)
        self.runSetup()

    def onSelectionChanged(self):
        self.isOkEnabled = self.isOkActive()
        self.isSelectable = self.isSelectableActive()
        self.setOKLabel()

    def setOKLabel(self):
        if self.isSelectable:
            labelText = "<  %s  >"
        else:
            labelText = "   %s   "
        if self.isOkEnabled:
            labelText = labelText % "OK"
        else:
            labelText = labelText % "  "
        self["footnote"].setText(_(labelText))

    def isOkActive(self):
        if self["config"].getCurrent() is not None:
            currItem = self["config"].getCurrent()[1]
            if isinstance(currItem, ConfigText) or isinstance(currItem, ConfigPassword):
                try:
                    # I really do not like this "help screen" NumericalTextInputHelpDialog which cover others options
                    # it is much easier to type text with VK after OK press, but maybe option need to be added to allow user to have this "help"
                    currItem.help_window.hide()
                except Exception:
                    pass
                return True
        return False

    def isSelectableActive(self):
        if self["config"].getCurrent() is not None:
            currItem = self["config"].getCurrent()[1]
            if currItem and isinstance(currItem, ConfigSelection) or isinstance(currItem, ConfigBoolean):
                return True
        return False

    def runSetup(self):
        self["config"].list = self.list
        self["config"].setList(self.list)

    def isChanged(self):
        bChanged = False
        for item in self["config"].list:
            if len(item) > 1 and item[1].isChanged():
                bChanged = True
                break
        printDBG("ConfigMenu.isChanged bChanged[%r]" % bChanged)
        return bChanged

    def getMessageAfterSave(self):
        return ''

    def getMessageBeforeClose(self):
        return ''

    def askForSave(self, callbackYesFun, callBackNoFun):
        self.session.openWithCallback(boundFunction(self.saveOrCancelChanges, callbackYesFun, callBackNoFun), MessageBox, text=_('Save changes?'), type=MessageBox.TYPE_YESNO)
        return

    def saveOrCancelChanges(self, callbackFun=None, failCallBackFun=None, answer=None):
        if answer:
            self.save()
            if callbackFun:
                callbackFun()
        else:
            self.cancel()
            if failCallBackFun:
                failCallBackFun()

    def keySave(self):
        self.saveAndClose()

    def saveOrCancel(self, operation="save"):
        for item in self["config"].list:
            if len(item) > 1:
                if "save" == operation:
                    item[1].save()
                else:
                    item[1].cancel()
        if "save" == operation:
            configfile.save()

    def save(self):
        self.saveOrCancel("save")

    def cancel(self):
        self.saveOrCancel("cancel")
        self.runSetup()

    def saveAndClose(self):
        self.save()
        self.performCloseWithMessage(True)

    def performCloseWithMessage(self, afterSave=True):
        if afterSave:
            message = self.getMessageAfterSave()
        else:
            message = self.getMessageBeforeClose()
        if message == '':
            self.close()
        else:
            self.session.openWithCallback(self.closeAfterMessage, MessageBox, text=message, type=MessageBox.TYPE_INFO)

    def closeAfterMessage(self, arg=None):
        self.close()

    def cancelAndClose(self):
        self.cancel()
        self.performCloseWithMessage()

    def keyOK(self):
        if not self.isOkEnabled:
            return

        curIndex = self["config"].getCurrentIndex()
        currItem = self["config"].list[curIndex][1]

        if isinstance(currItem, ConfigIPTVFileSelection):
            def SetFilePathCallBack(curIndex, newPath):
                if None is not newPath:
                    self["config"].list[curIndex][1].value = newPath
            try:
                if None is not currItem.fileMatch:
                    if currItem.ignoreCase:
                        fileMatch = re.compile(currItem.fileMatch, re.IGNORECASE)
                    else:
                        fileMatch = re.compile(currItem.fileMatch)
                else:
                    fileMatch = None
            except Exception:
                printExc()
                return
            self.session.openWithCallback(boundFunction(SetFilePathCallBack, curIndex), IPTVFileSelectorWidget, currItem.value, _('Select the file'), fileMatch)
            return

        elif isinstance(currItem, ConfigDirectory):
            def SetDirPathCallBack(curIndex, newPath):
                if None is not newPath:
                    self["config"].list[curIndex][1].value = newPath
            self.session.openWithCallback(boundFunction(SetDirPathCallBack, curIndex), IPTVDirectorySelectorWidget, currDir=currItem.value, title=_('Select the directory'))
            return
        elif isinstance(currItem, ConfigText):
            def VirtualKeyBoardCallBack(curIndex, newTxt):
                if isinstance(newTxt, str):
                    self["config"].list[curIndex][1].value = newTxt
            try:
                # we need hide NumericalTextInputHelpDialog before
                self["config"].list[curIndex][1].help_window.hide()
            except Exception:
                printExc()
            self.session.openWithCallback(boundFunction(VirtualKeyBoardCallBack, curIndex), GetVirtualKeyboard(), title=(_("Enter a value")), text=currItem.value)
            return

        ConfigListScreen.keyOK(self)

    def keyExit(self):
        if self.isChanged():
            self.askForSave(self.saveAndClose, self.cancelAndClose)
        else:
            self.performCloseWithMessage()

    def keyCancel(self):
        self.cancelAndClose()

    def keyMenu(self):
        ConfigListScreen.keyMenu(self)

    def keyUp(self):
        if self["config"].instance is not None:
            self["config"].instance.moveSelection(self["config"].instance.moveUp)

    def keyDown(self):
        if self["config"].instance is not None:
            self["config"].instance.moveSelection(self["config"].instance.moveDown)

    def keyPageUp(self):
        if self["config"].instance is not None:
            self["config"].instance.moveSelection(self["config"].instance.pageUp)

    def keyPageDown(self):
        if self["config"].instance is not None:
            self["config"].instance.moveSelection(self["config"].instance.pageDown)

    def keyHome(self):
        pass

    def keyEnd(self):
        pass

    def keyLeft(self):
        ConfigListScreen.keyLeft(self)

    def keyRight(self):
        ConfigListScreen.keyRight(self)

    def getSubOptionsList(self):
        tab = []
        return tab

    def changeSubOptions(self):
        if self["config"].getCurrent()[1] in self.getSubOptionsList():
            self.runSetup()

    def changedEntry(self):
        self.changeSubOptions()
        for x in self.onChangedEntry:
            x()
