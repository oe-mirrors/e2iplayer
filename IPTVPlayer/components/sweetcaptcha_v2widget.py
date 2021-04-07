# -*- coding: utf-8 -*-
#
#  Player Selector
#
#  $Id$
#
# 
from Screens.Screen import Screen
from Components.ActionMap import ActionMap, HelpableActionMap
from enigma import ePoint
from Tools.LoadPixmap import LoadPixmap
from Components.Label import Label
from skin import parseColor

from Plugins.Extensions.IPTVPlayer.components.cover import Cover2, Cover3
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, GetIconDir
    

#########################################################
#                    GLOBALS
#########################################################

class UnCaptchaSweetCaptchaWidget(Screen):
   
    def __init__(self, session, params):
        self.session = session
        self.markerWidth = 100
        
        self.skin = """
            <screen position="center,center" title="%s" size="500,200">
             <widget name="statustext" position="5,5" zPosition="1" size="490,60" font="Regular;24" transparent="1" halign="center" valign="center" backgroundColor="black"/>
             <widget name="marker"  zPosition="4" position="5,75"  size="100,100" transparent="1" alphatest="blend" />
             <widget name="cover_0" zPosition="2" position="10,80"  size="90,90" transparent="1" alphatest="blend" />
             <widget name="cover_1" zPosition="2" position="115,80" size="90,90" transparent="1" alphatest="blend" />
             <widget name="cover_2" zPosition="2" position="220,80" size="90,90" transparent="1" alphatest="blend" />
             <widget name="cover_3" zPosition="2" position="325,80" size="90,90" transparent="1" alphatest="blend" />
             <widget name="cover"   zPosition="2" position="430,80" size="65,68" transparent="1" alphatest="blend" />
            </screen>""" % (params.get('title', ''))
        
        Screen.__init__(self, session)

        self["actions"] = ActionMap(["WizardActions", "DirectionActions", "ColorActions"],
        {
            "left": self.keyLeft,
            "right": self.keyRight,
            "ok": self.keyOK,
            "back": self.keyCancel,
        }, -1)
        
        self["statustext"] = Label(params.get('challenge', ''))
        self.markerPixmap = LoadPixmap(GetIconDir('markerCaptchaV2.png'))
        
        self.iconList = params.get('icon_list')
        
        for i in range(4):
            strIndx = "cover_%d" % i
            self[strIndx] = Cover2()
        self['cover'] = Cover2()
        self["marker"] = Cover3()
        
        self.selIdx = 0
        self.maxIcons = len(self.iconList) - 1
        self.onLayoutFinish.append(self.onStart)
    
    def __del__(self):
        printDBG("UnCaptchaSweetCaptchaWidget.__del__ --------------------------")    
        
    def onStart(self):
        self.onLayoutFinish.remove(self.onStart)
        
        for idx in range(4):
            strIndx = "cover_%d" % idx
            self[strIndx].updateIcon(self.iconList[idx])
            self[strIndx].show()
        
        self['cover'].updateIcon(self.iconList[-1])
        self['cover'].show()
        
        self['marker'].setPixmap(self.markerPixmap)
        self['marker'].show()
        
    def moveMarker(self, m):
        x, y = self["marker"].getPosition()
        cx, cy = self["cover_%d" % self.selIdx].getPosition()

        self.selIdx += m
        
        # correct new selection idx
        if self.selIdx < 0:
            self.selIdx = self.maxIcons - 1
        elif self.selIdx >= self.maxIcons:
            self.selIdx = 0
        
        offset = x - cx
        cx, cy = self["cover_%d" % self.selIdx].getPosition()
        x = cx + offset
        self["marker"].instance.move(ePoint(x, y))
    
    def keyRight(self):
        self.moveMarker(1)

    def keyLeft(self):
        self.moveMarker(-1)
        return
 
    def keyCancel(self):
        self.close(None)
        return

    def keyOK(self):
        self.close({'resp_idx': self.selIdx})
        return
