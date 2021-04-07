# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.ihost import ArticleContent
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
###################################################

###################################################
# FOREIGN import
###################################################
from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.ScrollLabel import ScrollLabel
from enigma import getDesktop
###################################################


class ArticleView(Screen):
    sz_w = getDesktop(0).size().width() - 200
    sz_h = getDesktop(0).size().height() - 200
    
    skin = """
        <screen position="center,center" size="%d,%d" title="Info..." >
            <widget name="text" position="10,10" size="%d,%d" font="Regular;24" />
        </screen>""" % (sz_w, sz_h, sz_w - 20, sz_h - 20)
        
    def __init__(self, session, artItem):
        printDBG("ArticleView.__init__ -------------------------------")
        self.session = session
        Screen.__init__(self, session)

        self["text"] = ScrollLabel("")
        self["actions"] = ActionMap(["WizardActions", "DirectionActions"], 
        {
            "ok": self.cancel,
            "back": self.cancel,
            "up": self["text"].pageUp,
            "down": self["text"].pageDown
        }, -1)
        
        self.title = artItem.title
        self.textContent = artItem.text
        
        self.onClose.append(self.__onClose)
        self.onShown.append(self.updateTitle)
        self.onLayoutFinish.append(self.startRun) # dont start before gui is finished
        
    def __del__(self):
        printDBG("ArticleView.__del__ -------------------------------")
        
    def __onClose(self):
        printDBG("ArticleView.__onClose -----------------------------")
        self.onClose.remove(self.__onClose)
        self.onShown.remove(self.updateTitle)
        self.onLayoutFinish.remove(self.startRun)
        
    def updateTitle(self):
        self.setTitle(self.title)

    def startRun(self):
        self["text"].setText(self.textContent)

    def cancel(self):
        self.close()
