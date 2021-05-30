# -*- coding: utf-8 -*-
#
#  IPTV InputBox window
#
#  $Id$
#
#
from Screens.InputBox import InputBox
from cover import Cover3
from Components.Label import Label
from Tools.LoadPixmap import LoadPixmap

from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from cover import Cover2


#########################################################
#                    GLOBALS
#########################################################

class IPTVInputBoxWidget(InputBox):

    def __init__(self, session, icon={}, size=None, title="", windowTitle=_("Input"), useableChars=None, **kwargs):
        self.session = session
        InputBox.__init__(self, session, title, windowTitle, useableChars, **kwargs)
        width = 300
        height = 260
        if None != size:
            width = size[0]
            height = size[1]
        if 'size' not in icon:
            icon['size'] = [width - 10, height - 70]
        skin = """
            <screen name="IPTVInputBoxWidget" position="center,center" title="Input" size="%d,%d">
            <widget name="text" position="center,10" size="%d,30" font="Regular;24" valign="center" halign="center" />
            <widget name="input" position="center,60" size="%d,50" font="Regular;40" valign="center" halign="center" />
            <widget name="cover" zPosition="4" position="center,%d" size="%d,%d" transparent="1" alphatest="on" />
            </screen>""" % (width, height,
                             width - 20,
                             width - 20,
                             85 + (height - 85 - icon['size'][1]) / 2,
                             icon['size'][0],
                             icon['size'][1])
        self.skin = skin
        self.icon = icon
        self["cover"] = Cover2()
        self.onShown.append(self.setIcon)
    #end def __init__(self, session):

    def setIcon(self):
        if 0 < len(self.icon.get('icon_path', '')):
            try:
                self["cover"].updateIcon(self.icon['icon_path'])
            except Exception:
                printExc()
#class IPTVInputBoxWidget
