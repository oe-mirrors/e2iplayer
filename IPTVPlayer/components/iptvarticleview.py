# -*- coding: utf-8 -*-
#
#  IPTV Article UI
#
#  $Id$
#
#
from hashlib import md5
import os

try:
    from PIL import Image
    hasPIL = True
except ImportError:
    hasPIL = False

from enigma import eTimer, getDesktop
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.ScrollLabel import ScrollLabel
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Tools.Directories import fileExists
from Tools.LoadPixmap import LoadPixmap


from Plugins.Extensions.IPTVPlayer.components.ihost import ArticleContent
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir, eConnectCallback
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdownloadercreator import DownloaderCreator
from Plugins.Extensions.IPTVPlayer.components.cover import Cover3, Cover2, Cover
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_binary


class IPTVArticleView(Screen):

    skin = """
        <screen name="IPTVArticleView" position="center,center" size="1200,580" resolution="1280,720" title="Info..." backgroundColor="#34111112" flags="wfNoBorder">
            <widget name="title" position="340,20" size="840,40" foregroundColor="#0066ccff" backgroundColor="black" borderWidth="1" borderColor="black" transparent="1" zPosition="1" font="Regular;24" valign="center" />
            <widget name="cover" position="20,80" size="296,470" zPosition="3" alphatest="blend" />
            <widget name="spinner" zPosition="2" position="252,34" size="16,16" transparent="1" alphatest="blend" />
            <widget name="spinner_1" zPosition="1" position="252,34" size="16,16" transparent="1" alphatest="blend" />
            <widget name="spinner_2" zPosition="1" position="268,34" size="16,16" transparent="1" alphatest="blend" />
            <widget name="spinner_3" zPosition="1" position="284,34" size="16,16" transparent="1" alphatest="blend" />
            <widget name="spinner_4" zPosition="1" position="300,34" size="16,16" transparent="1" alphatest="blend" />
            <widget name="text" position="340,80" size="840,470" font="Regular;20" splitPosition="200" transparent="1" backgroundColor="black" foregroundColor="white" borderWidth="1" borderColor="black" shadowColor="black" shadowOffset="-2,-2"/>
            <widget name="playerlogo" zPosition="4" position="110,20" size="120,40" alphatest="blend" transparent="1" backgroundColor="black" />
        </screen>
        """

    fullHD = getDesktop(0).size().width() == 1920
    if fullHD:
        skin = skin.replace("/HD/", "/FHD/")

    def __init__(self, session, artItem, addParams):
        self.session = session
        self.artItem = artItem
        #############################################

        Screen.__init__(self, session)
        self.skinName = ["IPTVArticleView"]

        self["title"] = Label("")
        self["text"] = ScrollLabel(" ")
        #############################################
        # COVER
        #############################################
        self["cover"] = Cover()
        self["playerlogo"] = Cover2()
        self["playerlogo"].hide()

        self.cover = {'src': '', 'downloader': None, 'files_to_remove': [], 'image_path': ''}
        try:
            self.cover['image_path'] = os.path.join(addParams['buffering_path'], '.iptv_buffering.jpg')
        except Exception:
            printExc()
        #############################################

        #############################################
        # SPINER
        #############################################
        try:
            for idx in range(5):
                spinnerName = "spinner"
                if idx:
                    spinnerName += '_%d' % idx
                self[spinnerName] = Cover3()
        except Exception:
            printExc()
        self.spinner = {}
        self.spinner["pixmap"] = [LoadPixmap(GetIconDir('radio_button_on.png')), LoadPixmap(GetIconDir('radio_button_off.png'))]
        # spinner timer
        self.spinner["timer"] = eTimer()
        self.spinner["timer_conn"] = eConnectCallback(self.spinner["timer"].timeout, self.updateSpinner)
        self.spinner["timer_interval"] = 200
        self.spinner["enabled"] = False
        #############################################

        self.hostName = addParams.get('host_name')
        self.hostLogoPath = addParams.get('logo_path')
        self.downloadDir = addParams.get('download_dir')
        self.coverPath = None

        self["actions"] = ActionMap(['OkCancelActions', 'DirectionActions'],
        {
            "ok": self.key_ok,
            "cancel": self.key_back,
            "up": self.key_up,
            "down": self.key_down,
        }, -1)

        self.onClose.append(self.__onClose)
        self.onLayoutFinish.append(self.onStart)

    # end def __init__(self, session):

    def __del__(self):
        printDBG('IPTVArticleView.__del__ --------------------------------------')

    def __onClose(self):
        printDBG('IPTVArticleView.__onClose ------------------------------------')
        self.onClose.remove(self.__onClose)
        self.onEnd()
        self.hideSpinner()
        self.spinner["timer"] = None
        self.spinner["timer_conn"] = None

    def onStart(self):
        self.onLayoutFinish.remove(self.onStart)
        self.loadSpinner()
        self["title"].setText(self.artItem.title)
        self.setText()
        self.hideSpinner()
        self.loadCover()
        if self.hostLogoPath and os.path.exists(self.hostLogoPath):
            self["playerlogo"].updateIcon(self.hostLogoPath)

    #############################################
    # COVER
    #############################################

    def loadCover(self):
        self["cover"].hide()
        if 0 == len(self.artItem.images):
            return
        self.cover['src'] = self.artItem.images[0].get('url', '')
        if not self.cover['src'].startswith('http'):
            return

        if self.downloadDir:
            filename = md5(ensure_binary(self.cover['src'])).hexdigest() + '.jpg'
            self.coverPath = os.path.join(self.downloadDir, filename)
            if os.path.exists(self.coverPath):
                if self["cover"].decodeCover(self.coverPath, self.decodePictureEnd, ' '):
                    return
            self.coverPath = None

        self.cover['downloader'] = DownloaderCreator(self.cover['src'])
        if self.cover['downloader']:
            self.cover['downloader'].isWorkingCorrectly(self.startDownloader)
        else:
            self.session.open(MessageBox, _("Downloading cannot be started.\n Invalid URI[%s].") % self.cover['src'], type=MessageBox.TYPE_ERROR, timeout=10)

    def startDownloader(self, sts, reason):
        if sts:
            url, downloaderParams = DMHelper.getDownloaderParamFromUrl(self.cover['src'])
            self.cover['downloader'].subscribeFor_Finish(self.downloaderEnd)
            self.cover['downloader'].start(url, self._getDownloadFilePath(), downloaderParams)
            self.showSpinner()
        else:
            self.session.open(MessageBox, _("Downloading cannot be started.\n Downloader [%s] not working properly.\n Status[%s]") % (self.cover['downloader'].getName(), reason.strip()), type=MessageBox.TYPE_ERROR, timeout=10)

    def _getDownloadFilePath(self):
        if self.coverPath:
            return self.coverPath
        self.cover['files_to_remove'].append(self.cover['image_path'])
        return self.cover['image_path']

    def downloaderEnd(self, status):
        if None is not self.cover['downloader']:
            if DMHelper.STS.DOWNLOADED == status:
                if ".webp" in self.cover['src']:
                    if hasPIL:
                        file_path = self._getDownloadFilePath()
                        try:
                            img = Image.open(file_path)
                            img.save(file_path, format="jpeg", quality=80)
                            img.close()
                        except:
                            printExc()

                if self["cover"].decodeCover(self._getDownloadFilePath(), self.decodePictureEnd, ' '):
                    return
            else:
                self.session.open(MessageBox, (_("Downloading file [%s] problem.") % self.cover['src']) + (" sts[%r]" % status), type=MessageBox.TYPE_ERROR, timeout=10)
        self.hideSpinner()

    def decodePictureEnd(self, ret={}):
        if None is ret.get('Pixmap', None):
            self.session.open(MessageBox, _("Downloading file [%s] problem.") % self._getDownloadFilePath(), type=MessageBox.TYPE_ERROR, timeout=10)
        else:
            self["cover"].updatePixmap(ret.get('Pixmap', None), ret.get('FileName', self._getDownloadFilePath()))
            self["cover"].show()
        self.hideSpinner()

    def onEnd(self):
        if self.cover['downloader']:
            self.cover['downloader'].unsubscribeFor_Finish(self.downloaderEnd)
            downloader = self.cover['downloader']
            self.downloader = None
            downloader.terminate()
            downloader = None

        for filePath in self.cover['files_to_remove']:
            if fileExists(filePath):
                try:
                    os.remove(filePath)
                except Exception:
                    printDBG('Problem with removing old buffering file')
    #################################################

    #######################################################################
    # SPINER
    #######################################################################
    def loadSpinner(self):
        try:
            if "spinner" in self:
                self["spinner"].setPixmap(self.spinner["pixmap"][0])
                for idx in range(4):
                    spinnerName = 'spinner_%d' % (idx + 1)
                    self[spinnerName].setPixmap(self.spinner["pixmap"][1])
        except Exception:
            printExc()

    def showSpinner(self):
        if None is not self.spinner["timer"]:
            self._setSpinnerVisibility(True)
            self.spinner["timer"].start(self.spinner["timer_interval"], True)

    def hideSpinner(self):
        self._setSpinnerVisibility(False)

    def _setSpinnerVisibility(self, visible=True):
        self.spinner["enabled"] = visible
        try:
            if "spinner" in self:
                for idx in range(5):
                    spinnerName = "spinner"
                    if idx:
                        spinnerName += '_%d' % idx
                    self[spinnerName].visible = visible
        except Exception:
            printExc()

    def updateSpinner(self):
        try:
            if self.spinner["enabled"]:
                if "spinner" in self:
                    x, y = self["spinner"].getPosition()
                    x += self["spinner"].getWidth()
                    if x > self["spinner_4"].getPosition()[0]:
                        x = self["spinner_1"].getPosition()[0]
                    self["spinner"].setPosition(x, y)
                if None is not self.spinner["timer"]:
                    self.spinner["timer"].start(self.spinner["timer_interval"], True)
                    return
            self.hideSpinner()
        except Exception:
            printExc()
    #######################################################################

    #######################################################################
    # RICH DESC HANDLING
    #######################################################################
    def setText(self):

        LC = 0x0066ccff
        TC = 0x00ffffff

        info = []
        if 'custom_items_list' in self.artItem.richDescParams:
            for item in self.artItem.richDescParams['custom_items_list']:
                if item and isinstance(item, tuple) and len(item) == 2:
                    itemText = item[1].replace("|", " ")
                    info.append(r"\c%08x%s|\c%08x%s" % (LC, item[0], TC, itemText))
        else:
            for item in ArticleContent.RICH_DESC_PARAMS:
                if item in self.artItem.richDescParams:
                    label = _(ArticleContent.RICH_DESC_LABELS[item])
                    itemText = self.artItem.richDescParams[item].replace("|", " ")
                    info.append(r"\c%08x%s|\c%08x%s" % (LC, label, TC, itemText))

        text = "\n".join(info) + "\n\n" + r"\c%08x%s" % (TC, self.artItem.text.replace("[/br]", "\n").replace("|", "\n"))
        self["text"].setText(text)

    #######################################################################

    def key_ok(self):
        self.showSpinner()
        pass

    def key_back(self):
        self.close()

    def key_up(self):
        self["text"].pageUp()

    def key_down(self):
        self["text"].pageDown()
