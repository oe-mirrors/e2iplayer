# -*- coding: utf-8 -*-
#
#  IPTV download manager List UI
#
#  $Id$
#
# 
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, formatBytes
from Plugins.Extensions.IPTVPlayer.components.iptvlist import IPTVListComponentBase
###################################################

###################################################
# FOREIGN import
###################################################
from enigma import eListboxPythonMultiContent, eListbox, gFont, RT_HALIGN_LEFT, RT_HALIGN_RIGHT, RT_VALIGN_CENTER
from Tools.LoadPixmap import LoadPixmap
import skin
###################################################

class IPTVUpdateList(IPTVListComponentBase):

    def __init__(self, iconsPaths):
        IPTVListComponentBase.__init__(self)
        
        self.fonts = {}
        try:
            self.fonts[0] = skin.fonts["iptvupdatelistitem_0"]
        except Exception:
            self.fonts[0] = ("Regular", 16, 20, 0)
        try:
            self.fonts[1] = skin.fonts["iptvupdatelistitem_1"]
        except Exception:
            self.fonts[1] = ("Regular", 26, 50, 0)
    
        self.l.setFont(0, gFont(self.fonts[0][0], self.fonts[0][1]))
        self.l.setFont(1, gFont(self.fonts[1][0], self.fonts[1][1]))

        height = self.fonts[0][2] + self.fonts[1][2]
        if height < 70:
            height = 70
        
        self.l.setItemHeight(height)
        self.iconsPaths = iconsPaths
        self.iconsPixList = [None for x in self.iconsPaths]
        self.releaseIcons()

    def onCreate(self):
        for idx in range(len(self.iconsPaths)):
            try:
                self.iconsPixList[idx] = LoadPixmap(cached=False, path=self.iconsPaths[idx])
            except Exception:
                printExc()
        
    def onDestroy(self):
        self.releaseIcons()
        
    def buildEntry(self, item):
        width = self.l.getItemSize().width()
        height = self.l.getItemSize().height()
        res = [None]
        
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 70, 0, width - 70, self.fonts[1][2], 1, RT_HALIGN_LEFT | RT_VALIGN_CENTER, item.get('title', '')))
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 70, self.fonts[1][2], width - 70, self.fonts[0][2], 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, item.get('info', '')))
        
        idx = item.get('icon', None)
        if None != idx and idx < len(self.iconsPixList):
            iconPix = self.iconsPixList[idx]
        else:
            iconPix = None
        res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHABLEND, 3, (height - 64) / 2, 64, 64, iconPix))
        return res
        
    def releaseIcons(self):
        for idx in range(len(self.iconsPixList)):
            self.iconsPixList[idx] = None
            
