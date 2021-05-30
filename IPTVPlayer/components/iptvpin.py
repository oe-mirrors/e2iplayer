# -*- coding: utf-8 -*-
#
#  IPTV pin window
#
#  $Id$
#
#
from Screens.Screen import Screen
from Components.ActionMap import ActionMap, NumberActionMap, HelpableActionMap
from cover import Cover3
from Components.Label import Label
from Tools.LoadPixmap import LoadPixmap
from Tools.Directories import resolveFilename, SCOPE_PLUGINS

from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, GetIconDir
from cover import Cover3


#########################################################
#                    GLOBALS
#########################################################

class IPTVPinWidget(Screen):
    PIN_LEN = 4
    skin = """
        <screen name="IPTVPinWidget" position="center,center" title="E2iPlayer" size="300,260">
         <widget name="titel" position="5,5" zPosition="1" size="290,40" font="Regular;24" transparent="1" halign="center" valign="center" backgroundColor="black"/>
         <widget name="cover_0" zPosition="4" position="5,80" size="60,60" transparent="1" alphatest="on" />
         <widget name="cover_1" zPosition="4" position="75,80" size="60,60" transparent="1" alphatest="on" />
         <widget name="cover_2" zPosition="4" position="145,80" size="60,60" transparent="1" alphatest="on" />
         <widget name="cover_3" zPosition="4" position="215,80" size="60,60" transparent="1" alphatest="on" />
         <ePixmap position="100,150" zPosition="4" size="100,100" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/Pin/lock.png" transparent="1" alphatest="on" />
        </screen>"""

    def __init__(self, session, title=""):
        self.session = session
        Screen.__init__(self, session)

        self["actions"] = ActionMap(["WizardActions", "DirectionActions", "NumberActions"],
        {
            "ok": self.ok_pressed,
            "back": self.back_pressed,
            "left": self.keyLeft,
            "right": self.keyRight,
            "1": self.keyNum1,
            "2": self.keyNum2,
            "3": self.keyNum3,
            "4": self.keyNum4,
            "5": self.keyNum5,
            "6": self.keyNum6,
            "7": self.keyNum7,
            "8": self.keyNum8,
            "9": self.keyNum9,
            "0": self.keyNum0
        }, -1)

        self["titel"] = Label()
        self["titel"].setText(title)

        # set icons
        self.icoDict = {}
        self.readIcons()

        # init pin list
        self.pinList = []
        for i in range(self.PIN_LEN):
            self.pinList.append('')
            strIndx = "cover_%d" % i
            printDBG(strIndx)
            self[strIndx] = Cover3()

        self.selIndx = 0
        self.onLayoutFinish.append(self.updatePinDisplay)
    #end def __init__(self, session):

    def updatePinDisplay(self):
        for i in range(len(self.pinList)):
            strIndx = "cover_%d" % i
            icoIndx = ""
            if '' != self.pinList[i]:
                icoIndx = 'Fy'
            else:
                icoIndx = 'Fn'
            if i != self.selIndx:
                icoIndx += 'Sn'
            else:
                icoIndx += 'Sy'
            self[strIndx].setPixmap(self.icoDict[icoIndx])

    def keyNumPressed(self, number):
        printDBG("Key pressed: " + str(number))

        self.pinList[self.selIndx] = str(number)

        pin = ''.join(self.pinList)
        if len(pin) == self.PIN_LEN:
            self.close(pin)
        else:
            self.nextPinItem()
        return

    def nextPinItem(self):
        self.selIndx += 1
        if self.PIN_LEN <= self.selIndx:
            self.selIndx = 0

        self.updatePinDisplay()

    def keyRight(self):
        self.nextPinItem()
        return

    def keyLeft(self):
        self.selIndx -= 1
        if self.selIndx < 0:
            self.selIndx = self.PIN_LEN - 1

        self.updatePinDisplay()
        return

    def back_pressed(self):
        self.close(None)
        return

    def ok_pressed(self):
        pin = ''.join(self.pinList)
        if len(pin) == self.PIN_LEN:
            self.close(pin)
        return

    def readIcons(self):
        for itF in ['n', 'y']:
            for itS in ['n', 'y']:
                self.icoDict['F' + itF + 'S' + itS] = LoadPixmap(GetIconDir('Pin/PinF%sS%s.png' % (itF, itS)))

    def keyNum1(self):
        self.keyNumPressed(1)

    def keyNum2(self):
        self.keyNumPressed(2)

    def keyNum3(self):
        self.keyNumPressed(3)

    def keyNum4(self):
        self.keyNumPressed(4)

    def keyNum5(self):
        self.keyNumPressed(5)

    def keyNum6(self):
        self.keyNumPressed(6)

    def keyNum7(self):
        self.keyNumPressed(7)

    def keyNum8(self):
        self.keyNumPressed(8)

    def keyNum9(self):
        self.keyNumPressed(9)

    def keyNum0(self):
        self.keyNumPressed(0)

    def Error(self, error=None):
        pass

#class IPTVPinWidget
