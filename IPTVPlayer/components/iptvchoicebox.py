# -*- coding: utf-8 -*-
#

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, IsValidFileName, GetFavouritesDir, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvfavourites import IPTVFavourites
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CFavItem, CDisplayListItem
from Plugins.Extensions.IPTVPlayer.components.iptvmultipleinputbox import IPTVMultipleInputBox
from Plugins.Extensions.IPTVPlayer.components.iptvlist import IPTVRadioButtonList
###################################################

###################################################
# FOREIGN import
###################################################
from enigma import getDesktop, gRGB
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Screens.ChoiceBox import ChoiceBox
from Components.Label import Label
from Components.ActionMap import ActionMap
###################################################


class IPTVChoiceBoxItem:
    TYPE_ON = "on"
    TYPE_OFF = "off"
    TYPE_NONE = None

    def __init__(self, name="",
                description="",
                privateData=None,
                type=TYPE_NONE):
        self.name = name
        self.description = description
        self.type = type
        self.privateData = privateData


class IPTVChoiceBoxWidget(Screen):

    def __prepareSkin(self):
        width = self.params.get('width', 300)
        height = self.params.get('height', 300)

        skin = """
            <screen name="IPTVChoiceBoxWidget" position="center,center" title="%s" size="%d,%d">
                <widget name="title" position="5,10"  zPosition="1" size="%d,30" font="Regular;20"            transparent="1"  backgroundColor="#00000000"/>
                <widget name="list"  position="5,50"  zPosition="2" size="%d,%d" scrollbarMode="showOnDemand" transparent="1"  backgroundColor="#00000000" enableWrapAround="1" />
            </screen>""" % (
                self.params.get('title', _("Select option")),
                width, height, # size
                width - 10, # title width
                width - 10, height - 50
                )
        return skin

    def __init__(self, session, params={'width': 300, 'height': 300, 'title': '', 'current_idx': 0, 'options': []}):
        self.params = params
        self.skin = self.__prepareSkin()
        Screen.__init__(self, session)
        self.skinName = "IPTVChoiceBoxWidget"

        self.onShown.append(self.onStart)
        self.onClose.append(self.__onClose)

        self["title"] = Label(self.params.get('title', _("Select option")))
        self["list"] = IPTVRadioButtonList()

        self["actions"] = ActionMap(["ColorActions", "SetupActions", "WizardActions", "ListboxActions"],
            {
                "cancel": self.key_cancel,
                "ok": self.key_ok,
            }, -2)

        self.prevIdx = 0
        self.reorderingMode = False

    def __onClose(self):
        try:
            self["list"].disconnectSelChanged(self.onSelectionChanged)
        except Exception:
            printExc()
        self.params = None

    def onStart(self):
        self.onShown.remove(self.onStart)

        self["list"].setList([(x,) for x in self.params['options']])
        try:
            self["list"].moveToIndex(self.params['current_idx'])
        except Exception:
            printExc()
        self["list"].connectSelChanged(self.onSelectionChanged)

    def key_ok(self):
        self.close(self.getSelectedItem())

    def key_cancel(self):
        self.close(None)

    def onSelectionChanged(self):
        callback = self.params.get('selection_changed', None)
        if callable(callback):
            callback(self.getSelectedItem())

    def getSelectedItem(self):
        sel = None
        try:
            sel = self["list"].l.getCurrentSelection()[0]
        except Exception:
            pass
        return sel
