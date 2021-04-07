# -*- coding: utf-8 -*-
#
#  Update iptv setup main window
#


###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools           import printDBG, printExc, GetIPTVPlayerVerstion, GetIconDir
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, IPTVPlayerNeedInit
from Plugins.Extensions.IPTVPlayer.components.cover          import Cover3
from Plugins.Extensions.IPTVPlayer.setup.iptvsetupimpl       import IPTVSetupImpl
###################################################

###################################################
# FOREIGN import
###################################################
from enigma import getDesktop, eTimer
from Screens.MessageBox import MessageBox
from Screens.ChoiceBox import ChoiceBox
from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Label import Label
from Tools.BoundFunction import boundFunction
from Tools.LoadPixmap import LoadPixmap
###################################################

class IPTVSetupMainWidget(Screen):
    IPTV_VERSION = GetIPTVPlayerVerstion()
    skin = """
    <screen position="center,center" size="600,300" title="E2iPlayer setup version %s">
            <widget name="sub_title"    position="10,10" zPosition="2" size="580,90"   valign="center" halign="center" font="Regular;24" transparent="1" foregroundColor="white" />
            <widget name="info_field"   position="10,100" zPosition="2" size="580,200" valign="top" halign="center"   font="Regular;22" transparent="1" foregroundColor="white" />
            
            <widget name="spinner"   zPosition="2" position="463,200" size="16,16" transparent="1" alphatest="blend" />
            <widget name="spinner_1" zPosition="1" position="463,200" size="16,16" transparent="1" alphatest="blend" />
            <widget name="spinner_2" zPosition="1" position="479,200" size="16,16" transparent="1" alphatest="blend" />
            <widget name="spinner_3" zPosition="1" position="495,200" size="16,16" transparent="1" alphatest="blend" />
            <widget name="spinner_4" zPosition="1" position="511,200" size="16,16" transparent="1" alphatest="blend" />
    </screen>""" %(IPTV_VERSION)

    def __init__(self, session, autoStart=False):
        printDBG("IPTVUpdateMainWindow.__init__ -------------------------------")
        Screen.__init__(self, session)
        self["sub_title"]  = Label(_(" "))
        self["info_field"] = Label(_(" "))
        
        self["actions"] = ActionMap(["SetupActions", "ColorActions"],
            {
                "cancel":  self.cancelPressed,
                "ok":  self.startPressed,
            }, -1)
        try:
            for idx in range(5):
                spinnerName = "spinner"
                if idx:
                    spinnerName += '_%d' % idx 
                self[spinnerName] = Cover3()
        except Exception:
            printExc()
        self.spinnerPixmap = [LoadPixmap(GetIconDir('radio_button_on.png')), LoadPixmap(GetIconDir('radio_button_off.png'))]
        
        self.onClose.append(self.__onClose)
        #self.onLayoutFinish.append(self.onStart)
        self.onShow.append(self.onStart)
        
        #flags
        self.autoStart          = autoStart
        self.underCloseMessage  = False
        self.underClosing       = False
        self.deferredAction     = None
        self.started            = False

        self.setupImpl = IPTVSetupImpl(self.finished, self.chooseQuestion, self.showMessage, self.setInfo)

    def __del__(self):
        printDBG("IPTVSetupMainWidget.__del__ -------------------------------")

    def __onClose(self):
        printDBG("IPTVSetupMainWidget.__onClose -----------------------------")
        self.setupImpl.terminate()
        IPTVPlayerNeedInit(False)

    def onStart(self):
        self.onShow.remove(self.onStart)
        printDBG("IPTVSetupMainWidget.onStart")
        self["sub_title"].setText(_("Information"))
        self["info_field"].setText(_("IPTVPlayer need some additional setup.\nSuch as downloading and installation additional binaries.\nPress OK to start."))
        if self.autoStart:
            self.startPressed()
        
    def cancelPressed(self):
        printDBG("IPTVSetupMainWidget.cancelPressed")
        if self.underClosing:
            return
        self.underCloseMessage = True
        message = _("Skipping IPTVPlayer setup may cause problems.\nAre you sure to skip IPTVPlayer setup?")
        self.session.openWithCallback(self.cancelAnswer, MessageBox, text=message, type=MessageBox.TYPE_YESNO)

    def startPressed(self):
        printDBG("IPTVSetupMainWidget.startPressed")
        if self.underClosing:
            return
        if self.started:
            return
        self.started = True
        self.setupImpl.start()
        
    def cancelAnswer(self, ret):
        printDBG("IPTVSetupMainWidget.cancelAnswer")
        if self.underClosing:
            return
        if ret: 
            self.underClosing = True
            self.close()
        else:
            if None != self.deferredAction:
                deferredAction = self.deferredAction
                self.deferredAction = None
                deferredAction()
            
    def showMessage(self, message, type, callback):
        printDBG("IPTVSetupMainWidget.showMessage")
        if self.underClosing:
            return
        if self.underCloseMessage:
            self.deferredAction =  boundFunction(self.doShowMessage, message, type, callback)
        else:
            self.doShowMessage(message, type, callback)
        
    def doShowMessage(self, message, type, callback):
        self.session.openWithCallback(callback, MessageBox, text=message, type=type)
        
    def chooseQuestion(self, title, list, callback):
        printDBG("IPTVSetupMainWidget.chooseQuestion")
        if self.underClosing:
            return
        if self.underCloseMessage:
            self.deferredAction =  boundFunction(self.dochooseQuestion, title, list, callback)
        else:
            self.dochooseQuestion(title, list, callback)
        
    def dochooseQuestion(self, title, list, callback):
        title += "                                                                         " # workaround for truncation message by stupid E2
        title = title.replace('\n', ' ').replace(' ', chr(160))
        self.session.openWithCallback(callback, ChoiceBox, title=title, list=list)
        
    def setInfo(self, title, message):
        if self.underClosing:
            return
        if None != title:
            self["sub_title"].setText(title)
        if None != message:
            self["info_field"].setText(message)
        
    def finished(self):
        if self.underClosing:
            return
        if self.underCloseMessage:
            self.deferredAction = self.doFinished
        else:
            self.doFinished()
        
    def doFinished(self):
        self.close()
