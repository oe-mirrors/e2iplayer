# -*- coding: utf-8 -*-
#

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm, GetIconDir
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.cover import Cover3

from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdownloadercreator import DownloaderCreator
###################################################

###################################################
# FOREIGN import
###################################################
from enigma import getDesktop
from Screens.Screen import Screen
from Components.Label import Label
from Components.ActionMap import ActionMap
from Tools.LoadPixmap import LoadPixmap
###################################################


class SingleFileDownloaderWidget(Screen):
    sz_w = getDesktop(0).size().width() - 190
    sz_h = getDesktop(0).size().height() - 195
    if sz_h < 500:
        sz_h += 4
    skin = """
        <screen position="center,center" title="%s" size="%d,%d">
         <widget name="icon_red"    position="5,9"   zPosition="4" size="30,30" transparent="1" alphatest="on" />
         <widget name="icon_green"  position="355,9" zPosition="4" size="30,30" transparent="1" alphatest="on" />

         <widget name="label_red"     position="45,9"  size="175,27" zPosition="5" valign="center" halign="left" backgroundColor="black" font="Regular;21" transparent="1" foregroundColor="white" shadowColor="black" shadowOffset="-1,-1" />
         <widget name="label_green"   position="395,9" size="175,27" zPosition="5" valign="center" halign="left" backgroundColor="black" font="Regular;21" transparent="1" foregroundColor="white" shadowColor="black" shadowOffset="-1,-1" />

         <widget name="title" position="5,47"  zPosition="1" size="%d,23" font="Regular;20"            transparent="1"  backgroundColor="#00000000"/>

         <widget name="console"      position="10,%d"   zPosition="2" size="%d,160" valign="center" halign="center"   font="Regular;24" transparent="0" foregroundColor="white" backgroundColor="black"/>
        </screen>""" % (
            _("Single file downloader"),
            sz_w, sz_h, # size
            sz_w - 135, # size title
            (sz_h - 160) / 2, sz_w - 20, # console
            )

    def __init__(self, session, uri, outFile, title=''):
        self.session = session
        Screen.__init__(self, session)

        self.uri = uri
        self.outFile = outFile
        self.title = title

        self.onShown.append(self.onStart)
        self.onClose.append(self.__onClose)

        self["title"] = Label(" ")
        self["console"] = Label(" ")

        self["label_red"] = Label(_("Cancel"))
        self["label_green"] = Label(_("Apply"))

        self["icon_red"] = Cover3()
        self["icon_green"] = Cover3()

        self["actions"] = ActionMap(["ColorActions", "SetupActions", "WizardActions", "ListboxActions"],
            {
                "cancel": self.keyExit,
                "red": self.keyRed,
                "green": self.keyGreen,
            }, -2)

        self.iconPixmap = {}
        for icon in ['red', 'green']:
            self.iconPixmap[icon] = LoadPixmap(GetIconDir(icon + '.png'))

        self.downloader = None
        self.cleanDownloader()

    def __onClose(self):
        self.cleanDownloader()

    def cleanDownloader(self):
        if self.downloader != None:
            self.downloader.unsubscribeFor_Finish(self.downloadFinished)
            self.downloader.terminate()
        self.downloader = None

    def startDownload(self):
        self.cleanDownloader()
        self["console"].setText(_("Downloading file:\n%r.") % self.uri)

        self.downloader = DownloaderCreator(self.uri)
        if self.downloader:
            self.downloader.isWorkingCorrectly(self._startDownloader)
        else:
            self["console"].setText(_("Download can not be started.\nIncorrect address \"%r\".") % self.uri)

    def _startDownloader(self, sts, reason):
        if sts:
            self.downloader.subscribeFor_Finish(self.downloadFinished)
            url, downloaderParams = DMHelper.getDownloaderParamFromUrl(self.uri)
            self.downloader.start(url, self.outFile, downloaderParams)
        else:
            error, desc = self.downloader.getLastError()
            self["console"].setText(_("Download can not be started.\nDownloader %s not working correctly.\nLast error \"%s (%s)\".") % (self.downloader.getName(), desc, error))

    def downloadFinished(self, status):
        if status != DMHelper.STS.DOWNLOADED:
            error, desc = self.downloader.getLastError()
            self["console"].setText(_("Download failed.\nLast error \"%s (%s)\".") % (desc, error))
            rm(self.outFile)
        else:
            self.close(True)

    def loadIcons(self):
        try:
            for icon in self.iconPixmap:
                self['icon_' + icon].setPixmap(self.iconPixmap[icon])
        except Exception:
            printExc()

    def hideButtons(self, buttons=['green']):
        try:
            for button in buttons:
                self['icon_' + button].hide()
                self['label_' + button].hide()
        except Exception:
            printExc()

    def showButtons(self, buttons=['red', 'green']):
        try:
            for button in buttons:
                self['icon_' + button].show()
                self['label_' + button].show()
        except Exception:
            printExc()

    def onStart(self):
        self.onShown.remove(self.onStart)
        self.setTitle(self.title)
        self.loadIcons()
        self.hideButtons()
        self.startDownload()

    def keyExit(self):
        if self.downloader != None and self.downloader.isDownloading():
            self.downloader.terminate()
        else:
            self.close(None)

    def keyRed(self):
        self.keyExit()

    def keyGreen(self):
        pass
