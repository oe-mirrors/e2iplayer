# -*- coding: utf-8 -*-
#

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.iptvlist import IPTVRadioButtonList
###################################################

###################################################
# FOREIGN import
###################################################
from Screens.Screen import Screen
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
            <screen name="IPTVChoiceBoxWidget" position="center,center" resolution="1280,720" title="%s" size="%d,%d" backgroundColor="#34111112" flags="wfNoBorder">
                <eLabel name="BG_Title" position="0,0" size="1000,50" backgroundColor="#100d0f16" zPosition="-1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/smallshadowline.png" position="0,50" size="e,2" zPosition="2" />
                <widget name="title" position="10,14" size="e-10,30" foregroundColor="#0066ccff" backgroundColor="black" borderWidth="1" borderColor="black" transparent="1" zPosition="1" font="Regular;24" valign="center" />
                <widget name="list"  position="5,60"  zPosition="2" size="e-10,e-50" scrollbarMode="showOnDemand" scrollbarSliderBorderWidth="1" scrollbarForegroundColor="#1b5a91" scrollbarBorderColor="#00b6b6b6" enableWrapAround="1" transparent="1" foregroundColor="white" backgroundColor="black" foregroundColorSelected="white" backgroundColorSelected="#1b5a91" borderWidth="1" borderColor="black"/>
            </screen>""" % (
            self.params.get('title', _("Select option")),
            width, height             # size of screen
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
        printDBG('IPTVChoiceBoxWidget.key_ok() getSelectedItem() = "%s"' % self.getSelectedItem())
        self.close(self.getSelectedItem())

    def key_cancel(self):
        printDBG('IPTVChoiceBoxWidget.key_cancel()')
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
