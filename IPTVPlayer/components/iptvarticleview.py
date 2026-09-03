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
    from enigma import getE2Flags
    webPEnabled = getE2Flags() & 2
except ImportError:
    webPEnabled = False

if not webPEnabled:
    try:
        from PIL import Image
        hasPIL = True
    except ImportError:
        hasPIL = False
else:
    hasPIL = False


from enigma import eTimer
from Components.ActionMap import ActionMap
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
from Plugins.Extensions.IPTVPlayer.components import skinchrome
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_binary


class IPTVArticleView(Screen):
    # chrome=True-style header/footer. resolution="1280,720" auto-scales
    # the whole layout for FHD/WQHD, same mechanism the chrome ChoiceBox
    # screens use - no fixed-pixel grid content here to fight that
    # scaling, unlike PlayerSelectorWidget.
    #
    # The screen's own chrome header shows the article's title (via
    # setTitle() in __init__, matching every other migrated screen)
    # instead of a separate content-area "title" widget. "playerlogo"
    # (the host site's own logo, e.g. "serienstream.to" - unrelated to
    # the app's own logo the chrome header normally shows) sits IN the
    # header's own logo slot (build_header_auto(logoWidgetName=
    # "playerlogo")), replacing the app logo there instead of getting its
    # own separate row - onStart() below falls back to the app's own
    # iptvlogo.png in that same slot for hosts that don't provide one, so
    # the header logo is never just empty. "spinner" (loading indicator
    # while the cover image downloads) kept its original "sits just
    # above the cover" design intent, moved down by the header's own
    # offset. showOk=False - key_ok() turned out to just start the
    # spinner animation with nothing to ever stop it again, no real
    # effect, and was removed entirely; showNav stays default True since
    # up/down (key_up()/key_down()) do something real - they page the
    # description text.
    def __prepareSkin(self):
        # iconBase is computed fresh per instance here, not cached at
        # class/module level, so it always reflects the real resolution
        # at the time the screen is opened. Every other chrome screen in
        # this plugin (IPTVChoiceBoxWidget etc.) already computes iconBase
        # fresh per instance inside its own
        # __prepareSkin() - this now matches that same, already-proven
        # pattern instead of being the one exception.
        iconBase = skinchrome.getIconBase()
        return """
        <screen name="IPTVArticleView" position="center,center" size="1200,620" resolution="1280,720" title="Info..." backgroundColor="#34111112" flags="wfNoBorder">
            %s
            <widget name="spinner" zPosition="2" position="128,64" size="16,16" transparent="1" alphatest="blend" />
            <widget name="spinner_1" zPosition="1" position="128,64" size="16,16" transparent="1" alphatest="blend" />
            <widget name="spinner_2" zPosition="1" position="144,64" size="16,16" transparent="1" alphatest="blend" />
            <widget name="spinner_3" zPosition="1" position="160,64" size="16,16" transparent="1" alphatest="blend" />
            <widget name="spinner_4" zPosition="1" position="176,64" size="16,16" transparent="1" alphatest="blend" />
            <widget name="cover" position="20,80" size="296,470" zPosition="3" alphatest="blend" />
            <widget name="text" position="340,80" size="840,470" font="Regular;20" splitPosition="330" transparent="1" backgroundColor="black" foregroundColor="white" borderWidth="1" borderColor="black" shadowColor="black" shadowOffset="-2,-2"/>
            %s
        </screen>
        """ % (skinchrome.build_header_auto(iconBase=iconBase, logoWidgetName="playerlogo"), skinchrome.build_footer_auto(620, iconBase=iconBase, showOk=False))

    def __init__(self, session, artItem, addParams):
        self.session = session
        self.artItem = artItem
        #############################################

        self.skin = self.__prepareSkin()
        Screen.__init__(self, session)
        self.skinName = skinchrome.forceInternalSkinName(["IPTVArticleView"])
        # chrome header's own source="Title" widget now shows this,
        # replacing the old separate content-area "title" widget
        self.setTitle(self.artItem.title)

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
        # per-tier assets (icons/HD|FHD|WQHD), not the flat icons/ root -
        # this spinner widget's declared "16,16" box gets auto-scaled to
        # 16/24/32 by this screen's own resolution="1280,720", but plain
        # Pixmap widgets never scale their pixmap CONTENT to that box, so
        # the source file itself has to already be the right size (same
        # bug/fix as the legacy grid's page markers, see playerselector.py)
        _spinnerIconBase = skinchrome.getIconBase()
        self.spinner["pixmap"] = [LoadPixmap(_spinnerIconBase + '/radio_button_on.png'), LoadPixmap(_spinnerIconBase + '/radio_button_off.png')]
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
        self.setText()
        # splitPosition (x where the "label | value" pairs' value column
        # starts) is NOT scaled by resolution="1280,720", so at FHD/WQHD the
        # doubled font ran the longest label into its value - set it here
        # scaled by the tier factor (the skin's own 330 is the fallback).
        # Only for our own embedded skin: an external skin (e.g. MetrixHD,
        # already scaled globally by openATV) declares its own splitPosition
        # and must not have this HD-reference number forced onto it too.
        if not skinchrome.isExternalSkin(self.skinName):
            try:
                self["text"].instance.setSplitPosition(skinchrome.scalePixels(330, skinchrome.getScale()))
            except Exception:
                printExc()
        self.hideSpinner()
        self.loadCover()
        # header logo: the host's own logo if it has one, otherwise fall
        # back to the app's own logo so the header slot is never just
        # empty
        if self.hostLogoPath and os.path.exists(self.hostLogoPath):
            self["playerlogo"].updateIcon(self.hostLogoPath)
        else:
            self["playerlogo"].updateIcon(skinchrome.getIconBase() + "/iptvlogo.png")
        self["playerlogo"].show()

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
                    elif not webPEnabled:
                        return

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

    def key_back(self):
        self.close()

    def key_up(self):
        self["text"].pageUp()

    def key_down(self):
        self["text"].pageDown()
