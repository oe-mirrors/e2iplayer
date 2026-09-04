# -*- coding: utf-8 -*-
#
#  IPTV pin window
#
#  $Id$
#
#

from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Tools.LoadPixmap import LoadPixmap

from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG
from Plugins.Extensions.IPTVPlayer.components import skinchrome
from .cover import Cover3


#########################################################
#                    GLOBALS
#########################################################

class IPTVPinWidget(Screen):
    PIN_LEN = 4
    WIDTH = 450
    HEIGHT = 340

    def _getPinIconBase(self):
        # dot/lock icon geometry auto-scales with resolution="1280,720"
        # (16/24/32-style tiers), but - like every other plain Pixmap/
        # ePixmap widget in this plugin - never scales the pixmap CONTENT
        # to match, so the source files themselves have to already be the
        # right size per tier; PinF*S*.png/lock.png ship as real 60/90/120
        # and 100/150/200 files per tier instead of one flat 60x60/100x100
        # set. NOT the plain chrome iconBase (icons/HD etc.) that
        # ok.png/exit.png/iptvlogo.png live in - Pin's own marker set
        # lives in its own "pin" subfolder (icons/HD|FHD|WQHD/pin), for
        # consistency with every other per-tier-then-feature icon set in
        # this branch (icons/HD/buffering/, icons/HD/e2ivk/, ...).
        return skinchrome.getIconBase() + "/pin"

    def __prepareSkin(self):
        # per-instance, not class-level - matches every other chrome
        # screen's own __prepareSkin() pattern; a class-level iconBase
        # would only ever be evaluated once at module import time and
        # could go stale for later instances at a different real
        # resolution.
        iconBase = skinchrome.getIconBase()
        pinIconBase = self._getPinIconBase()
        return """
        <screen name="IPTVPinWidget" position="center,center" size="%d,%d" resolution="1280,720" title="E2iPlayer" backgroundColor="#34111112" flags="wfNoBorder">
            %s
            <widget name="cover_0" zPosition="4" position="82,76" size="60,60" transparent="1" alphatest="blend" />
            <widget name="cover_1" zPosition="4" position="157,76" size="60,60" transparent="1" alphatest="blend" />
            <widget name="cover_2" zPosition="4" position="232,76" size="60,60" transparent="1" alphatest="blend" />
            <widget name="cover_3" zPosition="4" position="307,76" size="60,60" transparent="1" alphatest="blend" />
            <ePixmap position="175,156" zPosition="4" size="100,100" pixmap="%s/lock.png" transparent="1" alphatest="blend" />
            %s
        </screen>
        """ % (self.WIDTH, self.HEIGHT, skinchrome.build_header_auto(iconBase=iconBase), pinIconBase, skinchrome.build_footer_auto(self.HEIGHT, iconBase=iconBase, showNav=True, showNum=True, showOk=True, showExit=True))

    def __init__(self, session, title=""):
        self.session = session

        self.skin = self.__prepareSkin()
        Screen.__init__(self, session)
        self.skinName = skinchrome.forceInternalSkinName(["IPTVPinWidget"])
        self.setTitle(title)

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
    # end def __init__(self, session):

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
        pinIconBase = self._getPinIconBase()
        for itF in ['n', 'y']:
            for itS in ['n', 'y']:
                self.icoDict['F' + itF + 'S' + itS] = LoadPixmap(pinIconBase + '/PinF%sS%s.png' % (itF, itS))

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

# class IPTVPinWidget
