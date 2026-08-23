# -*- coding: utf-8 -*-
# Last Modified: 2026-07-26 - Updated blue_pressed() and blue_pressed_next(), added YouTube user links actions in the blue menu, and fixed deleteFavouriteItem(); fixed missing key_green label display by correcting the Halidri1080p1 playlist.xml key_green binding and set default green button text to "Download".
# IplaPlayer based on SHOUTcast
#
#  $Id$
#
#

from os import path as os_path
from urllib.parse import quote as urllib_quote
from random import shuffle as random_shuffle
import traceback

####################################################
#                   E2 components
####################################################
from skin import parseColor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Screens.ChoiceBox import ChoiceBox
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.Pixmap import Pixmap
from Components.config import config
from Components.Sources.StaticText import StaticText
from Tools.BoundFunction import boundFunction
from Tools.LoadPixmap import LoadPixmap
from Tools.Directories import fileExists
from Tools.NumericalTextInput import NumericalTextInput
from enigma import getDesktop, eTimer

####################################################
#                   IPTV components
####################################################
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import ConfigMenu, GetMoviePlayer, GetAvailableMoviePlayers, GetMoviePlayerName, GetListOfHostsNames
from Plugins.Extensions.IPTVPlayer.components.confighost import ConfigHostMenu, ConfigHostsMenu
from Plugins.Extensions.IPTVPlayer.components.configgroups import ConfigGroupsMenu

from Plugins.Extensions.IPTVPlayer.components.iptvfavouriteswidgets import IPTVFavouritesAddItemWidget, IPTVFavouritesMainWidget

from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdownloadercreator import IsUrlDownloadable
from Plugins.Extensions.IPTVPlayer.libs.pCommon import CParsingHelper
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
from Plugins.Extensions.IPTVPlayer.tools.iptvfavourites import IPTVFavourites
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import FreeSpace as iptvtools_FreeSpace, \
                                                          mkdirs as iptvtools_mkdirs, GetIPTVPlayerVersion, \
                                                          printDBG, printExc, iptv_system, GetHostsList, IsHostEnabled, \
                                                          eConnectCallback, GetSkinsDir, GetIconDir, GetPluginDir, \
                                                          SortHostsList, GetHostsOrderList, CSearchHistoryHelper, \
                                                          CMoviePlayerPerHost, GetFavouritesDir, CFakeMoviePlayerOption, GetAvailableIconSize, \
                                                          GetE2VideoMode, SetE2VideoMode, TestTmpCookieDir, TestTmpJSCacheDir, \
                                                          ClearTmpCookieDir, ClearTmpJSCacheDir, SetTmpCookieDir, SetTmpJSCacheDir, \
                                                          GetEnabledHostsList, SaveHostsOrderList, formatBytes, getExcMSG, \
                                                          findT9JumpIndex
from Plugins.Extensions.IPTVPlayer.tools.iptvhostgroups import IPTVHostsGroups
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvbuffui import E2iPlayerBufferingWidget
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdmapi import IPTVDMApi, DMItem

from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, GetIPTVPlayerLastHostError, GetIPTVNotify, GetIPTVSleep

from Plugins.Extensions.IPTVPlayer.components.iptvplayer import IPTVStandardMoviePlayer, IPTVMiniMoviePlayer
from Plugins.Extensions.IPTVPlayer.components.iptvextmovieplayer import IPTVExtMoviePlayer
from Plugins.Extensions.IPTVPlayer.components.iptvpictureplayer import IPTVPicturePlayerWidget
from Plugins.Extensions.IPTVPlayer.components.iptvlist import IPTVMainNavigatorList, IPTVLinkChoiceBoxList
from Plugins.Extensions.IPTVPlayer.components.iptvarticleview import IPTVArticleView
from Plugins.Extensions.IPTVPlayer.components.ihost import IHost, CDisplayListItem, RetHost, CUrlItem, ArticleContent, CFavItem
from Plugins.Extensions.IPTVPlayer.components.searchhistoryeditor import SearchHistoryEditor
from Plugins.Extensions.IPTVPlayer.components.iconmenager import IconMenager
from Plugins.Extensions.IPTVPlayer.components.cover import Cover, Cover3
from Plugins.Extensions.IPTVPlayer.components.iptvchoicebox import IPTVChoiceBoxWidget, IPTVChoiceBoxItem
import Plugins.Extensions.IPTVPlayer.components.asynccall as asynccall
from Plugins.Extensions.IPTVPlayer.components.playerselector import PlayerSelectorWidget
from Plugins.Extensions.IPTVPlayer.components.e2ivkselector import GetVirtualKeyboard
from Plugins.Extensions.IPTVPlayer.__init__ import GRIDSUPPORT
######################################################
gDownloadManager = None


class E2iPlayerWidget(Screen):
    IPTV_VERSION = GetIPTVPlayerVersion()
    skin = """
        <screen position="center,center" size="1280,720" resolution="1280,720" title="E2iPlayer" backgroundColor="#34111112" flags="wfNoBorder">
                <ePixmap position="22,687" size="40,26" zPosition="10" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/info.png" transparent="1" alphatest="blend" />
                <ePixmap position="80,687" size="40,26" zPosition="10" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/ok.png" transparent="1" alphatest="blend" />
                <ePixmap position="138,687" size="40,26" zPosition="10" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/key_prevnext.png" transparent="1" alphatest="blend" />
                <ePixmap position="196,687" size="40,26" zPosition="10" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/key_updown.png" transparent="1" alphatest="blend" />
                <ePixmap position="254,687" size="40,26" zPosition="10" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/exit.png" transparent="1" alphatest="blend" />
                <widget source="Title" render="Label" position="160,10" size="785,40" foregroundColor="white" backgroundColor="black" borderWidth="1" borderColor="black" transparent="1" zPosition="1" font="Regular;24" valign="center" />
                <widget name="headertext" position="320,70" zPosition="1" size="940,40" font="Regular; 20" transparent="1" halign="left" valign="center" backgroundColor="black" foregroundColor="#178ef5" borderWidth="1" borderColor="black" shadowColor="black" shadowOffset="-2,-2" />
                <widget name="statustext" position="410,230" zPosition="1" size="685,90" font="Regular;30" halign="left" valign="top" transparent="1" backgroundColor="black" foregroundColor="white" />
                <widget name="list" position="320,110" zPosition="2" size="940,384" itemHeight="32" font="Regular;20" scrollbarMode="showOnDemand" scrollbarSliderBorderWidth="1" scrollbarForegroundColor="#1b5a91" scrollbarBorderColor="#00b6b6b6" enableWrapAround="1" transparent="1" foregroundColor="white" backgroundColor="black" foregroundColorSelected="white" backgroundColorSelected="#1b5a91" borderWidth="1" borderColor="black" />
                <widget name="console" position="20,500" zPosition="1" size="1240,170" font="Regular;18" transparent="1" foregroundColor="white" backgroundColor="black" borderWidth="1" borderColor="black" shadowColor="black" shadowOffset="-2,-2" halign="left" valign="center" />
                <widget name="sequencer" position="0,0" zPosition="6" size="1280,720" font="Regular;160" halign="center" valign="center" transparent="1" backgroundColor="#00000000" />
                <widget name="cover" position="20,70" size="288,420" zPosition="3" alphatest="blend" />
                <widget name="playerlogo"  zPosition="4" position="20,10" size="120,40" alphatest="blend" transparent="1" backgroundColor="black" />
                <widget name="spinner"   zPosition="2" position="463,200" size="16,16" transparent="1" alphatest="blend" />
                <widget name="spinner_1" zPosition="1" position="463,200" size="16,16" transparent="1" alphatest="blend" />
                <widget name="spinner_2" zPosition="1" position="479,200" size="16,16" transparent="1" alphatest="blend" />
                <widget name="spinner_3" zPosition="1" position="495,200" size="16,16" transparent="1" alphatest="blend" />
                <widget name="spinner_4" zPosition="1" position="511,200" size="16,16" transparent="1" alphatest="blend" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/red.png" position="340,690" size="20,20" alphatest="blend" transparent="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/green.png" position="570,690" size="20,20" alphatest="blend" transparent="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/yellow.png" position="800,690" size="20,20" alphatest="blend" transparent="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/blue.png" position="1030,690" size="20,20" alphatest="blend" transparent="1" />
                <widget source="key_red" render="Label" position="374,686" size="200,28" zPosition="1" font="Regular;20" backgroundColor="black" foregroundColor="white" halign="left" transparent="1" valign="center" noWrap="1" />
                <widget source="key_green" render="Label" position="604,686" size="200,28" zPosition="1" font="Regular;20" backgroundColor="black" foregroundColor="white" halign="left" transparent="1" valign="center" noWrap="1" />
                <widget source="key_yellow" render="Label" position="834,686" size="200,28" zPosition="1" font="Regular;20" backgroundColor="black" foregroundColor="white" halign="left" transparent="1" valign="center" noWrap="1" />
                <widget source="key_blue" render="Label" position="1064,686" size="200,28" zPosition="1" font="Regular;20" backgroundColor="black" foregroundColor="white" halign="left" transparent="1" valign="center" noWrap="1" />
                <eLabel name="BG_Title" position="0,0" size="1280,60" backgroundColor="#100d0f16" zPosition="-1" />
                <eLabel name="BG_Buttons" position="0,675" size="1280,48" backgroundColor="#100d0f16" zPosition="-1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/smallshadowline.png" position="0,60" size="1280,2" zPosition="2" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/smallshadowline.png" position="20,494" size="1240,2" zPosition="2" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/smallshadowline.png" position="0,675" size="1280,2" zPosition="2" />
                <widget source="global.CurrentTime" render="Label" position="1100,10" size="150,40" foregroundColor="white" backgroundColor="black" borderWidth="1" borderColor="black" transparent="1" zPosition="1" font="Regular;24" valign="center" halign="right">
                    <convert type="ClockToText">Format:%H:%M</convert>
                </widget>
                <widget source="global.CurrentTime" render="Label" position="860,20" size="300,24" foregroundColor="white" backgroundColor="black" borderWidth="1" borderColor="black" transparent="1" zPosition="1" font="Regular;16" valign="center" halign="right">
                    <convert type="ClockToText">Date</convert>
                </widget>
        </screen>
    """
    fullHD = getDesktop(0).size().width() == 1920
    if fullHD:
        skin = skin.replace("/HD/", "/FHD/")

    def __init__(self, session):
        printDBG("E2iPlayerWidget.__init__ desktop IPTV_VERSION[%s]\n" % (E2iPlayerWidget.IPTV_VERSION))
        self.session = session
        self.skinResolutionType = 'sd'
        screenwidth = getDesktop(0).size().width()
        if screenwidth:
            if screenwidth > 1900:
                self.skinResolutionType = 'hd'
            elif screenwidth > 1200:
                self.skinResolutionType = 'hd_ready'

        selSkin = config.plugins.iptvplayer.skin.value
        if selSkin:
            path = GetSkinsDir(selSkin) + "/playlist.xml"
            printDBG("Playlist skin path [%s]" % path)
            if fileExists(path):
                try:
                    with open(path, "r") as f:
                        self.skin = f.read()
                except Exception:
                    printExc("Skin read error: " + path)

        Screen.__init__(self, session)
        self.skinName = ["E2iPlayerWidgetScreen", "E2iPlayerWidget"]
        if config.plugins.iptvplayer.skinforceinternal.value:
            self.skinName = "_E2iPlayerWidgetScreen"

        self.recorderMode = False  # j00zek
        self.hostLogoPath = None

        self.currentService = self.session.nav.getCurrentlyPlayingServiceReference()
        if config.plugins.iptvplayer.disable_live.value:
            self.session.nav.stopService()

        self["key_red"] = StaticText(_("Close"))
        self["key_green"] = StaticText(_("Download"))

        self["key_yellow"] = StaticText(_("Refresh"))
        self["key_blue"] = StaticText(_("More"))

        self["list"] = IPTVMainNavigatorList()
        self["list"].connectSelChanged(self.onSelectionChanged)
        self["statustext"] = Label("Loading...")

        self["actions"] = ActionMap(["IPTVPlayerListActions", "ColorActions", "NumberActions"],
        {
            "red": self.red_pressed,
            "green": self.green_pressed,
            "yellow": self.yellow_pressed,
            "blue": self.blue_pressed,
            "ok": self.ok_pressed,
            "back": self.back_pressed,
            "info": self.info_pressed,
            "0": self.ok_pressed0,
            "1": self.keyT9_1,
            "2": self.keyT9_2,
            "3": self.keyT9_3,
            "4": self.keyT9_4,
            "5": self.keyT9_5,
            "6": self.keyT9_6,
            "7": self.keyT9_7,
            "8": self.keyT9_8,
            "9": self.keyT9_9,
            "play": self.startAutoPlaySequencer,
            "menu": self.menu_pressed,
            "tools": self.blue_pressed,
            "record": self.green_pressed,
            "pageUp": self.pageup_pressed,
            "pageDown": self.pagedown_pressed
        }, -1)

        self["headertext"] = Label()
        self["console"] = Label()
        self["sequencer"] = Label()

        self["cover"] = Cover()
        self["cover"].hide()
        self["playerlogo"] = Cover()

        try:
            for idx in range(5):
                spinnerName = "spinner"
                if idx:
                    spinnerName += '_%d' % idx
                self[spinnerName] = Cover3()
        except Exception:
            printExc()

        # Check for plugin update
        self.lastPluginVersion = ''
        self.checkUpdateConsole = None

        self.spinnerPixmap = [LoadPixmap(GetIconDir('radio_button_on.png')), LoadPixmap(GetIconDir('radio_button_off.png'))]
        self.useAlternativePlayer = False

        self.showMessageNoFreeSpaceForIcon = False
        self.iconMenager = None
        if config.plugins.iptvplayer.showcover.value:
            if not os_path.exists(config.plugins.iptvplayer.SciezkaCache.value):
                iptvtools_mkdirs(config.plugins.iptvplayer.SciezkaCache.value)

            if iptvtools_FreeSpace(config.plugins.iptvplayer.SciezkaCache.value, 10):
                self.iconMenager = IconMenager(True)
            else:
                self.showMessageNoFreeSpaceForIcon = True
                self.iconMenager = IconMenager(False)
            self.iconMenager.setUpdateCallBack(self.checkIconCallBack)
        self.showHostsErrorMessage = True

        self.onClose.append(self.__onClose)
        # self.onLayoutFinish.append(self.onStart)
        self.onShow.append(self.onStart)

        # Defs
        self.searchPattern = CSearchHistoryHelper.loadLastPattern()[1]
        self.searchType = None
        self.workThread = None
        self.group = None
        self.groupDisplayName = None
        self.groupObj = None
        self.host = None
        self.hostName = ''
        self.hostTitle = ''
        self.hostFavTypes = []

        self.nextSelIndex = 0
        self.currSelIndex = 0

        self.prevSelList = []
        self.categoryList = []

        self.currList = []
        self.currItem = CDisplayListItem()
        self.favouritesCurrentGroupId = ''

        # global (not per-host) memory of the last selected search-history entry,
        # see _rememberHistorySelection()/_restoreHistorySelection()
        self._lastHistorySelection = None
        self._isLoadingList = False

        self.visible = True
        self.bufferSize = config.plugins.iptvplayer.requestedBuffSize.value * 1024 * 1024

        #################################################################
        #                      Inits for Proxy Queue
        #################################################################

        # register function in main Queue
        if None is asynccall.gMainFunctionsQueueTab[0]:
            asynccall.gMainFunctionsQueueTab[0] = asynccall.CFunctionProxyQueue(self.session)
        asynccall.gMainFunctionsQueueTab[0].clearQueue()
        asynccall.gMainFunctionsQueueTab[0].setProcFun(self.doProcessProxyQueueItem)

        # main Queue
        self.mainTimer = eTimer()
        self.mainTimer_conn = eConnectCallback(self.mainTimer.timeout, self.processProxyQueue)
        # every 100ms Proxy Queue will be checked
        self.mainTimer_interval = 100
        self.mainTimer.start(self.mainTimer_interval, True)

        # delayed decode cover timer
        self.decodeCoverTimer = eTimer()
        self.decodeCoverTimer_conn = eConnectCallback(self.decodeCoverTimer.timeout, self.doStartCoverDecode)
        self.decodeCoverTimer_interval = 100

        # spinner timer
        self.spinnerTimer = eTimer()
        self.spinnerTimer_conn = eConnectCallback(self.spinnerTimer.timeout, self.updateSpinner)
        self.spinnerTimer_interval = 200
        self.spinnerEnabled = False

        #################################################################

        #################################################################
        #                      Inits for IPTV Download Manager
        #################################################################
        global gDownloadManager
        if None is gDownloadManager:
            from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdmui import GetIPTVDMNotification
            GetIPTVDMNotification().dialogInit(session)
            printDBG('============Initialize Download Menager============')
            gDownloadManager = IPTVDMApi(2, int(config.plugins.iptvplayer.IPTVDMMaxDownloadItem.value), GetIPTVDMNotification)
            if config.plugins.iptvplayer.IPTVDMRunAtStart.value:
                gDownloadManager.runWorkThread()
        # transient state for the "Select link" screen: the full list of mirrors
        # currently shown (so a resolve failure can reopen it with the failed one
        # marked) and the mirror currently being resolved. Both reset naturally
        # whenever a fresh mirror list is fetched from the host.
        self._currentLinkOptions = None
        self._resolvingLinkItem = None
        # Auto playing sequencer
        self.autoPlaySeqStarted = False
        self.autoPlaySeqTimer = eTimer()
        self.autoPlaySeqTimer_conn = eConnectCallback(self.autoPlaySeqTimer.timeout, self.autoPlaySeqTimerCallBack)
        self.autoPlaySeqTimerValue = 0

        self.activePlayer = None
        self.canRandomizeList = False

        self.prevVideoMode = None
        # no handleTimeout: we act on every press immediately (list jump,
        # not text composition), so the commit-after-timeout callback and
        # its eTimer aren't needed - only the digit-cycling in getKey() is.
        # Separate instances per list context: NumericalTextInput only resets
        # its letter-cycle position when a DIFFERENT digit is pressed, so
        # sharing one instance between the search-history and main-list T9
        # jump would leak cycle state across an unrelated list switch (e.g.
        # pressing '2' in the history list, then '2' again in the main list,
        # would resume the cycle at 'b' instead of restarting at 'a').
        self.t9HistoryInput = NumericalTextInput(handleTimeout=False)
        self.t9MainListInput = NumericalTextInput(handleTimeout=False)

        # test if path for js and cookies temporary files
        # is writable, without this plugin can not works
        try:
            TestTmpCookieDir()
            TestTmpJSCacheDir()
            ClearTmpCookieDir()
            ClearTmpJSCacheDir()
        except Exception as e:
            SetTmpCookieDir()
            SetTmpJSCacheDir()
            msg1 = _("Critical Error - cookie can't be saved!")
            msg2 = _("Last error:\n%s") % str(e)
            msg3 = _("Please make sure that the folder for cache data (set in the configuration) is writable.")
            GetIPTVNotify().push('%s\n\n%s\n\n%s' % (msg1, msg2, msg3), 'error', 20)

        self.statusTextValue = ""
        self.enabledHostsListOld = []
        asynccall.SetMainThreadId()

        self.downloadable = False
        self.colorEnabled = parseColor("#FFFFFF")
        self.colorDisabled = parseColor("#808080")

    # end def __init__(self, session):

    def updateDownloadButton(self):
        self.downloadable = False
        try:
            if self["list"].visible:
                item = self.getSelItem()
                self.downloadable = self.isDownloadableType(item.type)
                if self.downloadable and item and item.urlItems and item.urlItems[0].url.startswith('file://'):  # workaround for LocalMedia
                    self.downloadable = False
        except Exception:
            printExc()

        self["key_green"].setText(_("Download") if self.downloadable else "")

    def getSkinResolutionType(self):
        return self.skinResolutionType

    def setStatusTex(self, msg):
        self.statusTextValue = msg
        self["statustext"].setText(msg)

    def __del__(self):
        printDBG("E2iPlayerWidget.__del__")

    def __onClose(self):
        self.session.nav.playService(self.currentService)
        self["list"].disconnectSelChanged(self.onSelectionChanged)
        if None is not self.checkUpdateConsole:
            self.checkUpdateConsole.terminate()
        if None is not self.iconMenager:
            self.iconMenager.setUpdateCallBack(None)
            self.iconMenager.clearDQueue()
            self.iconMenager = None
        self.mainTimer_conn = None
        self.mainTimer = None
        self.decodeCoverTimer_conn = None
        self.decodeCoverTimer = None
        self.spinnerTimer_conn = None
        self.spinnerTimer = None

        try:
            self.stopAutoPlaySequencer()
            self.autoPlaySeqTimer_conn = None
            self.autoPlaySeqTimer = None
        except Exception:
            printExc()

        try:
            asynccall.gMainFunctionsQueueTab[0].setProcFun(None)
            asynccall.gMainFunctionsQueueTab[0].clearQueue()
            with open("/proc/sys/vm/drop_caches", "w") as f:
                f.write("1")
        except Exception:
            printExc()
        self.activePlayer = None

    def isPlayableType(self, type):
        if type in [CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO, CDisplayListItem.TYPE_ARTICLE, CDisplayListItem.TYPE_PICTURE]:
            return True
        else:
            return False

    def isDownloadableType(self, type):
        if type in [CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO, CDisplayListItem.TYPE_DATA]:
            return True
        else:
            return False

    def loadSpinner(self):
        try:
            if "spinner" in self:
                self["spinner"].setPixmap(self.spinnerPixmap[0])
                for idx in range(4):
                    spinnerName = 'spinner_%d' % (idx + 1)
                    self[spinnerName].setPixmap(self.spinnerPixmap[1])
        except Exception:
            printExc()

    def showSpinner(self):
        if None is not self.spinnerTimer:
            self._setSpinnerVisibility(True)
            self.spinnerTimer.start(self.spinnerTimer_interval, True)

    def hideSpinner(self):
        self._setSpinnerVisibility(False)

    def _setSpinnerVisibility(self, visible=True):
        self.spinnerEnabled = visible
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
            if self.spinnerEnabled and None is not self.workThread:
                if self.workThread.isAlive():
                    timeout = GetIPTVSleep().getTimeout()
                    if timeout > 0:
                        if timeout > 1:
                            msg = _("wait %s seconds") % timeout
                        else:
                            msg = _("wait %s second") % timeout
                        msg = '%s (%s)' % (self.statusTextValue, msg)
                        self["statustext"].setText(msg)
                    else:
                        self["statustext"].setText(self.statusTextValue)

                    if "spinner" in self:
                        x, y = self["spinner"].getPosition()
                        x += self["spinner"].getWidth()
                        if x > self["spinner_4"].getPosition()[0]:
                            x = self["spinner_1"].getPosition()[0]
                        self["spinner"].setPosition(x, y)
                    if None is not self.spinnerTimer:
                        self.spinnerTimer.start(self.spinnerTimer_interval, True)
                        return
                elif not self.workThread.isFinished():
                    if self.hostName not in GetHostsList(fromList=True, fromHostFolder=False):
                        message = _('It seems that the host "%s" has crashed.') % self.hostName
                        message += _('\nThis host is not integral part of the E2iPlayer plugin.\nIt is not supported by E2iPlayer team.')
                        self.session.open(MessageBox, message, type=MessageBox.TYPE_ERROR)
                    else:
                        message = _('It seems that the host "%s" has crashed. Do you want to report this problem?') % self.hostName
                        message += "\n"
                        message += _('\nMake sure you are using the latest version of the plugin.')
                        message += _('\nYou can also report problem here: \nhttps://github.com/oe-mirrors/e2iplayer/issues')
                        self.session.openWithCallback(self.reportHostCrash, MessageBox, text=message, type=MessageBox.TYPE_YESNO)
            self.hideSpinner()
        except Exception:
            printExc()

    def reportHostCrash(self, ret):
        try:
            if False:
                try:
                    exceptStack = self.workThread.getExceptStack()
                    reporter = GetPluginDir('iptvdm/reporthostcrash.py')
                    msg = urllib_quote('%s|%s|%s|%s' % ('HOST_CRASH', E2iPlayerWidget.IPTV_VERSION, self.hostName, self.getCategoryPath()))
                    self.crashConsole = iptv_system('python "%s" "http://iptvplayer.vline.pl/reporthostcrash.php?msg=%s" "%s" 2&>1 > /dev/null' % (reporter, msg, exceptStack))
                    printDBG(msg)
                except Exception:
                    printExc()
            self.workThread = None
            self.prevSelList = []
            self.back_pressed()
        except Exception:
            printExc()

    def processIPTVNotify(self, callbackArg1=None, callbackArg2=None):
        try:
            notifyObj = GetIPTVNotify()
            if not notifyObj.isEmpty():
                notification = notifyObj.pop()
                if notification:
                    typeMap = {
                        'info': MessageBox.TYPE_INFO,
                        'error': MessageBox.TYPE_ERROR,
                        'warning': MessageBox.TYPE_WARNING,
                    }
                    self.session.openWithCallback(self.processIPTVNotify, MessageBox, notification.message, type=typeMap.get(notification.type, MessageBox.TYPE_INFO), timeout=notification.timeout)
                    return
        except Exception:
            printExc()
        self.processProxyQueue()

    def processProxyQueue(self):
        if None is not self.mainTimer:
            funName = asynccall.gMainFunctionsQueueTab[0].peekClientFunName()
            notifyObj = GetIPTVNotify()
            if funName is not None and notifyObj is not None and not notifyObj.isEmpty() and funName in ['showArticleContent', 'selectMainVideoLinks', 'selectResolvedVideoLinks', 'reloadList']:
                self.processIPTVNotify()
            else:
                asynccall.gMainFunctionsQueueTab[0].processQueue()
                self.mainTimer.start(self.mainTimer_interval, True)
        return

    def doProcessProxyQueueItem(self, item):
        try:
            if None is item.retValue[0] or self.workThread == item.retValue[0]:
                if isinstance(item.retValue[1], asynccall.CPQParamsWrapper):
                    getattr(self, item.clientFunName)(*item.retValue[1])
                else:
                    getattr(self, item.clientFunName)(item.retValue[1])
            else:
                printDBG('doProcessProxyQueueItem callback from old workThread[%r][%s]' % (self.workThread, item.retValue))
        except Exception:
            printExc()

    def getArticleContentCallback(self, thread, ret):
        asynccall.gMainFunctionsQueueTab[0].addToQueue("showArticleContent", [thread, ret])

    def selectHostVideoLinksCallback(self, thread, ret):
        asynccall.gMainFunctionsQueueTab[0].addToQueue("selectMainVideoLinks", [thread, ret])

    def getResolvedURLCallback(self, thread, ret):
        asynccall.gMainFunctionsQueueTab[0].addToQueue("selectResolvedVideoLinks", [thread, ret])

    def callbackGetList(self, addParam, thread, ret):
        asynccall.gMainFunctionsQueueTab[0].addToQueue("reloadList", [thread, {'add_param': addParam, 'ret': ret}])

    # method called from IconMenager when a new icon has been dowlnoaded
    def checkIconCallBack(self, ret):
        asynccall.gMainFunctionsQueueTab[0].addToQueue("displayIcon", [None, ret])

    def isInWorkThread(self):
        return None is not self.workThread and (not self.workThread.isFinished() or self.workThread.isAlive())

    def red_pressed(self):
        self.stopAutoPlaySequencer()
        self.selectHost()
        return

    def green_pressed(self):
        self.stopAutoPlaySequencer()
        self.updateDownloadButton()
        self.recorderMode = self.downloadable
        if self.downloadable:
            self.ok_pressed('green')

    def yellow_pressed(self):
        self.stopAutoPlaySequencer()
        self.getRefreshedCurrList()
        return

    def blue_pressed(self):
        # For Keyboard test
        # if False:
        # from Plugins.Extensions.IPTVPlayer.components.e2ivksuggestion import AutocompleteSearch
        # from Plugins.Extensions.IPTVPlayer.suggestions.google import SuggestionsProvider
        # self.session.open(GetVirtualKeyboard(), additionalParams={'autocomplete':AutocompleteSearch(SuggestionsProvider(True))})
        # return

        # For subtitles test
        if False:
            from Plugins.Extensions.IPTVPlayer.components.iptvsubdownloader import IPTVSubDownloaderWidget
            self.session.open(IPTVSubDownloaderWidget, params={'movie_title': 'elementary s02e03'})
            return

        self.stopAutoPlaySequencer()
        options = []

        canAddUserLink = False
        try:
            currSelIndex = self.getSelIndex()
            if currSelIndex > -1 and hasattr(self.host, 'canAddToUserLinks') and self.host.canAddToUserLinks(currSelIndex):
                canAddUserLink = True
        except Exception:
            printExc()

        if canAddUserLink:
            options.append((_("Add to User Links"), "ADD_USER_LINK"))
            if hasattr(self.host, 'editUserLinks'):
                options.append((_("Edit User Links"), "EDIT_USER_LINKS"))

        if -1 < self.canByAddedToFavourites()[0]:
            options.append((_("Add item to favorites"), "ADD_FAV"))
            options.append((_("Edit favorites"), "EDIT_FAV"))
        elif 'favourites' == self.hostName:
            options.append((_("Edit favorites"), "EDIT_FAV"))
            options.append((_("Remove from favorites"), "DELETE_FAV"))

        if not canAddUserLink:
            try:
                if hasattr(self.host, 'editUserLinks'):
                    options.append((_("Edit User Links"), "EDIT_USER_LINKS"))
            except Exception:
                printExc()

        if None is not self.activePlayer.get('player', None):
            title = _('Change active movie player')
        else:
            title = _('Set active movie player')
        options.append((title, "SetActiveMoviePlayer"))

        if self.canRandomizeList and self.visible and len(self.currList) and not self.isInWorkThread():
            options.append((_('Randomize a playlist'), "RandomizePlayableItems"))
            options.append((_('Reverse a playlist'), "ReversePlayableItems"))

        self._hostActions = []
        try:
            host = __import__('Plugins.Extensions.IPTVPlayer.hosts.host' + self.hostName, globals(), locals(), ['GetConfigList'], 0)
            if (len(host.GetConfigList()) > 0):
                options.append((_("Configure host"), "HostConfig"))
            if hasattr(host, 'GetHostActions'):
                self._hostActions = host.GetHostActions()
                for i, action in enumerate(self._hostActions):
                    options.append((action[0], f"HostAction:{i}"))
        except Exception:
            printExc()
        if hasattr(self.host.host, 'history'):
            options.append((_("Edit search history"), "EditSearchHistory"))
        options.append((_("Download manager"), "IPTVDM"))
        options.append((_("Exit"), "CLOSE"))
        self.session.openWithCallback(self.blue_pressed_next, ChoiceBox, title=_("Select option"), list=options)

    def pause_pressed(self):
        printDBG('pause_pressed')
        self.stopAutoPlaySequencer()

    def startAutoPlaySequencer(self):
        if not self.autoPlaySeqStarted:
            self.autoPlaySeqStarted = True
            self.autoPlaySequencerNext(False)

    def stopAutoPlaySequencer(self):
        if self.autoPlaySeqStarted:
            if not config.plugins.iptvplayer.disable_live.value:
                self.session.nav.playService(self.currentService)

            if config.plugins.iptvplayer.autoplay_start_delay.value == 0:
                self.showWindow()

            self.autoPlaySeqTimer.stop()
            self["sequencer"].setText("")
            self.autoPlaySeqStarted = False
            return True
        return False

    def autoPlaySequencerNext(self, goToNext=True):
        if not self.autoPlaySeqStarted:
            printDBG("ERROR in autoPlaySequencerNext - sequencer stopped")
            return

        idx = self.getSelIndex()
        if -1 != idx:
            # find next playable item
            if goToNext:
                idx += 1
                if config.plugins.iptvplayer.autoplay_start_delay.value == 0:
                    self.hideWindow()

            while idx < len(self.currList):
                if self.currList[idx].type in [CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO, CDisplayListItem.TYPE_PICTURE, CDisplayListItem.TYPE_MORE]:
                    break
                else:
                    idx += 1
            if idx < len(self.currList):
                self["list"].moveToIndex(idx)
                self.sequencerPressOK()
                return
        self.stopAutoPlaySequencer()

    def sequencerPressOK(self):
        self.autoPlaySeqTimerValue = config.plugins.iptvplayer.autoplay_start_delay.value

        if self.autoPlaySeqTimerValue == 0:
            self.ok_pressed('sequencer')
        else:
            self["sequencer"].setText(str(self.autoPlaySeqTimerValue))
            self.autoPlaySeqTimer.start(1000)

    def autoPlaySeqTimerCallBack(self):
        self.autoPlaySeqTimerValue -= 1
        if self.autoPlaySeqTimerValue > 0:
            self["sequencer"].setText(str(self.autoPlaySeqTimerValue))
        else:
            self["sequencer"].setText("")
            self.autoPlaySeqTimer.stop()
            self.ok_pressed('sequencer')

    def checkAutoPlaySequencer(self):
        if self.autoPlaySeqStarted:
            self.autoPlaySequencerNext()
            return True
        return False

    def blue_pressed_next(self, ret):
        if ret:
            if ret[1] == "IPTVDM":
                self.runIPTVDM()
            elif ret[1] == "CLOSE":
                self.close()
            elif ret[1] == "HostConfig":
                self.runConfigHostIfAllowed()
            elif ret[1] == "SetActiveMoviePlayer":
                options = []
                options.append(IPTVChoiceBoxItem(_("Auto selection based on the settings"), "", {}))
                if config.plugins.iptvplayer.moviePlayerPickerMode.value == 'extended':
                    # every actually available player directly, not just
                    # whatever the two configured "default"/"alternative"
                    # slots resolve to - those often both land on the two
                    # external players (auto always prefers them when
                    # present), so mini/standard were never reachable here
                    # without changing Settings first
                    for buffering in (True, False):
                        for playerKey in GetAvailableMoviePlayers():
                            player = CFakeMoviePlayerOption(playerKey, GetMoviePlayerName(playerKey))
                            # keep the original combined msgid ("[%s] with/
                            # without buffering"), not a split "with
                            # buffering" + "[%s] %s" - 14 locales already
                            # have real translations for this exact string,
                            # splitting it would silently orphan every one
                            label = _("[%s] with buffering") % player.getText() if buffering else _("[%s] without buffering") % player.getText()
                            options.append(IPTVChoiceBoxItem(label, "", {'buffering': buffering, 'player': player}))
                else:
                    # "standard": only the 4 configured default/alternative
                    # slots, same as before the "extended" mode existed
                    for buffering, useAlternativePlayer in ((True, False), (True, True), (False, False), (False, True)):
                        player = self.getMoviePlayer(buffering, useAlternativePlayer)
                        label = _("[%s] with buffering") % player.getText() if buffering else _("[%s] without buffering") % player.getText()
                        options.append(IPTVChoiceBoxItem(label, "", {'buffering': buffering, 'player': player}))

                currIdx = -1
                for idx in range(len(options)):
                    try:
                        if options[idx].privateData.get('buffering', None) == self.activePlayer.activePlayer.get('buffering', None) and options[idx].privateData.get('player', CFakeMoviePlayerOption('', '')).value == self.activePlayer.activePlayer.get('player', CFakeMoviePlayerOption('', '')).value:
                            currIdx = idx
                    except Exception:
                        printExc()
                    if idx == currIdx:
                        options[idx].type = IPTVChoiceBoxItem.TYPE_ON
                    else:
                        options[idx].type = IPTVChoiceBoxItem.TYPE_OFF

                height = self._getMoviePlayerPickerHeight(len(options))
                # 120: same derivation as the keyboard's language picker -
                # the list starts at y=66 in the chrome skin's reference
                # space, and "e-N" sizes against the full container height,
                # not reduced by that 66 first, so footerMargin needs to be
                # >= 66 + 48 (footer height) = 114 just to end flush with
                # the footer; the chrome default of 150 leaves a visible
                # ~36px reference-space gap above it
                self.session.openWithCallback(self.setActiveMoviePlayer, IPTVChoiceBoxWidget, {'width': self.MOVIE_PLAYER_PICKER_WIDTH, 'height': height, 'current_idx': currIdx, 'title': _("Select movie player"), 'options': options, 'chrome': True, 'footerMargin': 120})
            elif ret[1] == 'ADD_FAV':
                currSelIndex = self.canByAddedToFavourites()[0]
                self.requestListFromHost('ForFavItem', currSelIndex, '')
            elif ret[1] == 'EDIT_FAV':
                self.session.openWithCallback(self.editFavouritesCallback, IPTVFavouritesMainWidget)
            elif ret[1] == 'DELETE_FAV':
                self.session.openWithCallback(self.deleteFavouriteItem, MessageBox, _('Definitely remove from favorites?'), type=MessageBox.TYPE_YESNO, timeout=10)
            elif ret[1] == 'ADD_USER_LINK':
                try:
                    currSelIndex = self.getSelIndex()
                    if currSelIndex > -1 and hasattr(self.host, 'addToUserLinks'):
                        self.host.addToUserLinks(self.session, currSelIndex)
                except Exception:
                    printExc()
            elif ret[1] == 'EDIT_USER_LINKS':
                try:
                    if hasattr(self.host, 'editUserLinks'):
                        self.host.editUserLinks(self.session)
                except Exception:
                    printExc()
            elif ret[1] == 'RandomizePlayableItems':
                self.randomizePlayableItems()
            elif ret[1] == 'ReversePlayableItems':
                self.reversePlayableItems()
            elif ret[1] == 'EditSearchHistory':
                try:
                    historyFile = self.host.host.history.PATH_FILE
                except Exception:
                    printExc()
                    historyFile = ''
                if historyFile:
                    self.session.open(SearchHistoryEditor, historyFile=historyFile, reverseForDisplay=True, reverseForWrite=True)
                else:
                    self.session.open(MessageBox, _('Search history is not available for this host.'), type=MessageBox.TYPE_ERROR, timeout=5)
            elif ret[1].startswith("HostAction:"):
                try:
                    idx = int(ret[1].split(":")[1])
                    if hasattr(self, '_hostActions') and idx < len(self._hostActions):
                        self._hostActions[idx][1](self.session)
                except Exception:
                    printExc()

    def deleteFavouriteItem(self, confirmed=False):
        printDBG("E2iPlayerWidget.deleteFavouriteItem")
        if confirmed is False:
            return

        if self.visible and not self.isInWorkThread() and 'favourites' == self.hostName:
            currSelIndex = self.getSelIndex()
            if currSelIndex < 0:
                return

            groupId = self.favouritesCurrentGroupId
            printDBG("deleteFavouriteItem groupId[%s] currSelIndex[%d]" % (groupId, currSelIndex))

            try:
                helper = IPTVFavourites(GetFavouritesDir())
                if not helper.load():
                    self.session.open(MessageBox, _('Error loading favorites.'), type=MessageBox.TYPE_ERROR, timeout=5)
                    return

                groups = helper.getGroups()

                def _norm(txt):
                    try:
                        txt = str(txt).strip().lower()
                    except Exception:
                        return ''
                    txt = txt.replace('_', ' ')
                    txt = ' '.join(txt.split())
                    return txt

                if not groupId:
                    selItem = self.getSelItem()
                    selTitle = ''
                    try:
                        selTitle = selItem.name
                    except Exception:
                        printExc()

                    groupIdx = -1
                    for idx in range(len(groups)):
                        group = groups[idx]
                        if not isinstance(group, dict):
                            continue
                        if group.get('title', '') == selTitle or _norm(group.get('title', '')) == _norm(selTitle):
                            groupId = group.get('group_id', '')
                            groupIdx = idx
                            break

                    if not groupId or groupIdx < 0:
                        self.session.open(MessageBox, _('Favorite group not found.'), type=MessageBox.TYPE_ERROR, timeout=5)
                        return

                    if not helper.delGroup(groupId):
                        self.session.open(MessageBox, helper.getLastError(), type=MessageBox.TYPE_ERROR, timeout=5)
                        return

                    if not helper.save():
                        self.session.open(MessageBox, _('Error saving favorites.'), type=MessageBox.TYPE_ERROR, timeout=5)
                        return

                    # the active host object (Favourites in hostfavourites.py) keeps its own
                    # helper instance loaded once at entry - reload it too, otherwise it still
                    # shows the old state after leaving/re-entering the screen (getPrevList()
                    # only pops a cached list, it never re-reads from disk)
                    try:
                        if hasattr(self.host, 'host') and hasattr(self.host.host, 'helper'):
                            self.host.host.helper.load()
                    except Exception:
                        printExc()

                    del self.currList[currSelIndex]
                    self["list"].setList([(x,) for x in self.currList])

                    if len(self.currList) <= currSelIndex:
                        currSelIndex = len(self.currList) - 1
                    if currSelIndex >= 0:
                        self["list"].moveToIndex(currSelIndex)

                    self.changeBottomPanel()
                    self.updateDownloadButton()
                    return

                realGroupId = ''
                for group in groups:
                    if not isinstance(group, dict):
                        continue

                    tmpGroupId = group.get('group_id', '')
                    tmpTitle = group.get('title', '')

                    if tmpGroupId == groupId:
                        realGroupId = tmpGroupId
                        break
                    if tmpTitle == groupId:
                        realGroupId = tmpGroupId
                        break
                    if _norm(tmpTitle) == _norm(groupId):
                        realGroupId = tmpGroupId
                        break
                    if _norm(tmpGroupId) == _norm(groupId):
                        realGroupId = tmpGroupId
                        break

                if not realGroupId:
                    self.session.open(MessageBox, _('Favorite group not found.'), type=MessageBox.TYPE_ERROR, timeout=5)
                    return

                sts, groupItems = helper.getGroupItems(realGroupId)
                if not sts:
                    self.session.open(MessageBox, _('Favorite group not found.'), type=MessageBox.TYPE_ERROR, timeout=5)
                    return

                if currSelIndex >= len(groupItems):
                    self.session.open(MessageBox, _('Favorite item not found.'), type=MessageBox.TYPE_ERROR, timeout=5)
                    return

                helper.delGroupItem(currSelIndex, realGroupId)

                if not helper.save():
                    self.session.open(MessageBox, _('Error saving favorites.'), type=MessageBox.TYPE_ERROR, timeout=5)
                    return

                # see comment above - keep the host's helper state in sync with the file
                try:
                    if hasattr(self.host, 'host') and hasattr(self.host.host, 'helper'):
                        self.host.host.helper.load()
                except Exception:
                    printExc()

                del self.currList[currSelIndex]
                self["list"].setList([(x,) for x in self.currList])

                if len(self.currList) <= currSelIndex:
                    currSelIndex = len(self.currList) - 1
                if currSelIndex >= 0:
                    self["list"].moveToIndex(currSelIndex)

                self.changeBottomPanel()
                self.updateDownloadButton()
            except Exception:
                printExc()
                self.session.open(MessageBox, _('Error deleting favorite item.'), type=MessageBox.TYPE_ERROR, timeout=5)

    def editFavouritesCallback(self, ret=False):
        if ret and 'favourites' == self.hostName:  # we must reload host
            self.loadHost()

    def setActiveMoviePlayer(self, ret):
        if not isinstance(ret, IPTVChoiceBoxItem):
            return
        self.activePlayer.set(ret.privateData)

    def runIPTVDM(self, callback=None):
        global gDownloadManager
        if None is not gDownloadManager:
            from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdmui import IPTVDMWidget
            if None is callback:
                self.session.open(IPTVDMWidget, gDownloadManager)
            else:
                self.session.openWithCallback(callback, IPTVDMWidget, gDownloadManager)
        elif None is not callback:
            callback()
        return

    def displayIcon(self, ret=None, doDecodeCover=False):
        # check if displays icon is enabled in options
        if not config.plugins.iptvplayer.showcover.value or None is self.iconMenager:
            return

        selItem = self.getSelItem()
        # when ret is != None the method is called from IconMenager
        # and in this variable the url for icon which was downloaded
        # is returned
        # if icon for other than selected item has been downloaded
        # the displayed icon will not be changed
        if ret is not None and selItem is not None and ret != selItem.iconimage:
            return

        # Display icon
        if selItem and '' != selItem.iconimage:
            self.iconMenager.addToDQueue([selItem.iconimage])
            # check if we have this icon and get the path to this icon on disk
            iconPath = self.iconMenager.getIconPathFromAAueue(selItem.iconimage)
            printDBG('displayIcon -> getIconPathFromAAueue: %s' % selItem.iconimage)
            if '' != iconPath and not self["cover"].checkDecodeNeeded(iconPath):
                self["cover"].show()
                return
            else:
                if doDecodeCover:
                    self["cover"].decodeCover(iconPath, self.updateCover, "cover")
                else:
                    self.decodeCoverTimer.start(self.decodeCoverTimer_interval, True)
        self["cover"].hide()

    def doStartCoverDecode(self):
        if self.decodeCoverTimer:
            self.displayIcon(None, doDecodeCover=True)

    def updateCover(self, retDict):
        # retDict - return dictionary  {Ident, Pixmap, FileName, Changed}
        printDBG('updateCover')
        if retDict:
            printDBG("updateCover retDict for Ident: %s " % retDict["Ident"])
            updateIcon = False
            if 'cover' == retDict["Ident"]:
                # check if we have icon for right item on list
                selItem = self.getSelItem()
                if selItem and '' != selItem.iconimage:
                    # check if we have this icon and get the path to this icon on disk
                    iconPath = self.iconMenager.getIconPathFromAAueue(selItem.iconimage)

                    if iconPath == retDict["FileName"]:
                        # now we are sure that we have right icon
                        updateIcon = True
                        self.decodeCoverTimer_interval = 100
                    else:
                        self.decodeCoverTimer_interval = 1000
            else:
                updateIcon = True
            if updateIcon:
                if None is not retDict["Pixmap"]:
                    self[retDict["Ident"]].updatePixmap(retDict["Pixmap"], retDict["FileName"])
                    self[retDict["Ident"]].show()
                else:
                    self[retDict["Ident"]].hide()
        else:
            printDBG("updateCover retDict empty")
    # end updateCover(self, retDict):

    def changeBottomPanel(self):
        self.displayIcon()
        selItem = self.getSelItem()
        if selItem and selItem.description != '':
            data = selItem.description
            sData = data.replace('\n', '')
            sData = data.replace('[/br]', '\n')
            self["console"].setText(sData)
        else:
            self["console"].setText('')

    def onSelectionChanged(self):
        self.updateDownloadButton()
        self.changeBottomPanel()
        self._rememberHistorySelection()

    def back_pressed(self):
        if self.stopAutoPlaySequencer() and self.autoPlaySeqTimerValue:
            return
        try:
            if self.isInWorkThread():
                if self.workThread.kill():
                    self.workThread = None
                    self.setStatusTex(_("Operation aborted!"))
                return
        except Exception:
            return
        if self.visible:
            if len(self.prevSelList) > 0:
                self.nextSelIndex = self.prevSelList.pop()
                self.categoryList.pop()
                if 'favourites' == self.hostName and len(self.categoryList) == 0:
                    self.favouritesCurrentGroupId = ''
                printDBG("back_pressed prev sel index %s" % self.nextSelIndex)
                self.requestListFromHost('Previous')
            else:
                # There is no prev categories, so exit
                # self.close()
                if self.group is None:
                    self.selectHost()
                else:
                    self.selectHostFromGroup()
        else:
            self.showWindow()
    # end back_pressed(self):

    def info_pressed(self):
        printDBG('info_pressed')
        if self.visible and not self.isInWorkThread():
            try:
                item = self.getSelItem()
            except Exception:
                printExc()
                item = None
            if None is not item:
                self.stopAutoPlaySequencer()
                self.currSelIndex = currSelIndex = self["list"].getCurrentIndex()
                self.requestListFromHost('ForArticleContent', currSelIndex)
    # end info_pressed(self):

    def isSearchHistoryList(self):
        """True only for the actual list of past search entries, not the
        Search category menu (which also contains one TYPE_SEARCH_HISTORY
        item - the link that navigates into that list)."""
        try:
            if not self.currList:
                return False

            hasHistoryEntry = False
            for item in self.currList:
                itemType = getattr(item, 'type', None)
                if itemType == CDisplayListItem.TYPE_SEARCH:
                    # the Search category menu always has exactly one such
                    # item; the actual history-entries list never does
                    return False
                if itemType == CDisplayListItem.TYPE_SEARCH_HISTORY:
                    hasHistoryEntry = True
            return hasHistoryEntry
        except Exception:
            printExc()

        return False

    def _rememberHistorySelection(self):
        # global (not per-host) memory of the last selected search-history
        # entry, restored by _restoreHistorySelection() in reloadList() so
        # reopening the history list lands back on it instead of index 0.
        # Skipped while a list is being (re)loaded, since moveToIndex() below
        # fires this same callback and would otherwise overwrite the value
        # we are about to restore with whatever index/name it lands on first.
        try:
            if not config.plugins.iptvplayer.rememberHistorySelection.value:
                return
            if self._isLoadingList or not self.isSearchHistoryList():
                return
            item = self.getSelItem()
            name = getattr(item, 'name', None) if item is not None else None
            if name:
                self._lastHistorySelection = name
        except Exception:
            printExc()

    def _restoreHistorySelection(self):
        # name-based, not index-based: new searches insert at the front of
        # the history list and shift every existing entry's index
        try:
            if not config.plugins.iptvplayer.rememberHistorySelection.value:
                return
            if not self.isSearchHistoryList():
                return
            wanted = self._lastHistorySelection
            if not wanted:
                return
            for idx, it in enumerate(self.currList):
                if getattr(it, 'name', None) == wanted:
                    self["list"].moveToIndex(idx)
                    break
        except Exception:
            printExc()

    def keyT9Jump(self, digit):
        # single global switch for the whole T9 letter-jump feature (this
        # method's search-history AND main-list branch alike, plus the
        # independent keyNumberJump() copies in iptvfavouriteswidgets.py and
        # searchhistoryeditor.py) - off restores plain keyT9_1/4/8 fallback
        # behaviour (ok_pressed1/4, startAutoPlaySequencer) everywhere
        if not config.plugins.iptvplayer.enableT9MainList.value:
            return False

        # search-history list: every digit press is consumed by the T9 jump
        # (always returns True), digits have no other meaning in this list
        if self.isSearchHistoryList():
            letter = self.t9HistoryInput.getKey(int(digit))
            if not letter:
                return True

            try:
                currentIdx = self['list'].getCurrentIndex()
                idx = findT9JumpIndex(len(self.currList), currentIdx, letter, lambda i: getattr(self.currList[i], 'name', ''))
                if idx >= 0:
                    self['list'].moveToIndex(idx)
                    printDBG('T9 history jump key[%s] letter[%s] index[%d]' % (digit, letter, idx))
                else:
                    printDBG('T9 history jump key[%s] letter[%s] no match' % (digit, letter))
            except Exception:
                printExc()

            return True

        # any other list (main menu, categories, series, favourites, ...):
        # only intercept the digit when it actually produced a jump, so
        # keyT9_1/4/8's secondary binding (ok_pressed1/4, startAutoPlaySequencer)
        # still fires normally when there is no match
        if not self.currList:
            return False

        try:
            letter = self.t9MainListInput.getKey(int(digit))
            if not letter:
                return True

            currentIdx = self['list'].getCurrentIndex()
            idx = findT9JumpIndex(len(self.currList), currentIdx, letter, lambda i: getattr(self.currList[i], 'name', ''))
            if idx >= 0:
                self['list'].moveToIndex(idx)
                printDBG('T9 main list jump key[%s] letter[%s] index[%d]' % (digit, letter, idx))
                return True
            printDBG('T9 main list jump key[%s] letter[%s] no match' % (digit, letter))
            return False
        except Exception:
            printExc()
            return False

    def keyT9_1(self):
        if not self.keyT9Jump('1'):
            self.ok_pressed1()

    def keyT9_2(self):
        if not self.keyT9Jump('2'):
            self.ok_pressed2()

    def keyT9_3(self):
        if not self.keyT9Jump('3'):
            self.ok_pressed3()

    def keyT9_4(self):
        if not self.keyT9Jump('4'):
            self.ok_pressed4()

    def keyT9_5(self):
        self.keyT9Jump('5')

    def keyT9_6(self):
        self.keyT9Jump('6')

    def keyT9_7(self):
        self.keyT9Jump('7')

    def keyT9_8(self):
        if not self.keyT9Jump('8'):
            self.startAutoPlaySequencer()

    def keyT9_9(self):
        self.keyT9Jump('9')

    def ok_pressed0(self):
        self.activePlayer.set({})
        self.ok_pressed(useAlternativePlayer=False)

    def ok_pressed1(self):
        player = self.getMoviePlayer(True, False)
        self.activePlayer.set({'buffering': True, 'player': player})
        self.ok_pressed(useAlternativePlayer=True)

    def ok_pressed2(self):
        player = self.getMoviePlayer(True, True)
        self.activePlayer.set({'buffering': True, 'player': player})
        self.ok_pressed(useAlternativePlayer=True)

    def ok_pressed3(self):
        player = self.getMoviePlayer(False, False)
        self.activePlayer.set({'buffering': False, 'player': player})
        self.ok_pressed(useAlternativePlayer=False)

    def ok_pressed4(self):
        player = self.getMoviePlayer(False, True)
        self.activePlayer.set({'buffering': False, 'player': player})
        self.ok_pressed(useAlternativePlayer=True)

    def ok_pressed(self, eventFrom='remote', useAlternativePlayer=False):
        self.useAlternativePlayer = useAlternativePlayer
        if eventFrom != 'green':
            self.recorderMode = False

        if 'sequencer' != eventFrom:
            self.stopAutoPlaySequencer()

        if self.visible or 'sequencer' == eventFrom:
            sel = None
            try:
                if len(self.currList) > 0 and (not self["list"].getVisible() and 'sequencer' != eventFrom):
                    printDBG("ok_pressed -> ignored /\\")
                    return
            except Exception:
                printExc()

            try:
                sel = self["list"].l.getCurrentSelection()[0]
            except Exception:
                printExc()
                self.getRefreshedCurrList()
                return
            if sel is None:
                printDBG("ok_pressed sel is None")
                self.stopAutoPlaySequencer()
                self.getInitialList()
                return
            elif len(self.currList) <= 0:
                printDBG("ok_pressed list is empty")
                self.stopAutoPlaySequencer()
                self.getRefreshedCurrList()
                return
            else:
                printDBG("ok_pressed selected item: %s" % (sel.name))

                item = self.getSelItem()
                self.currItem = item

                # Get current selection
                currSelIndex = self["list"].getCurrentIndex()
                # remember only prev categories
                if item.type in [CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO, CDisplayListItem.TYPE_PICTURE, CDisplayListItem.TYPE_DATA]:
                    if CDisplayListItem.TYPE_AUDIO == item.type:
                        self.bufferSize = config.plugins.iptvplayer.requestedAudioBuffSize.value * 1024
                    else:
                        self.bufferSize = config.plugins.iptvplayer.requestedBuffSize.value * 1024 * 1024
                    # check if separete host request is needed to get links to VIDEO
                    if item.urlSeparateRequest == 1:
                        printDBG("ok_pressed selected TYPE_VIDEO.urlSeparateRequest")
                        self.requestListFromHost('ForVideoLinks', currSelIndex)
                    else:
                        printDBG("ok_pressed selected TYPE_VIDEO.selectLinkForCurrVideo")
                        self.selectLinkForCurrVideo()
                elif item.type == CDisplayListItem.TYPE_SEARCH_HISTORY_DELETE:
                    printDBG("ok_pressed selected TYPE_SEARCH_HISTORY_DELETE")
                    self.host.host.delHistory(self.session)
                elif item.type in [CDisplayListItem.TYPE_CATEGORY, CDisplayListItem.TYPE_SEARCH_HISTORY, CDisplayListItem.TYPE_SEARCH_HISTORY_EDITOR, CDisplayListItem.TYPE_NEXT, CDisplayListItem.TYPE_JUMP, CDisplayListItem.TYPE_FIRST, CDisplayListItem.TYPE_PREVIOUS, CDisplayListItem.TYPE_LAST]:
                    printDBG("ok_pressed selected TYPE_CATEGORY")
                    self.stopAutoPlaySequencer()
                    self.currSelIndex = currSelIndex
                    if 'favourites' == self.hostName and len(self.categoryList) == 0:
                        try:
                            self.favouritesCurrentGroupId = ''
                            try:
                                groupTitle = item.name
                            except Exception:
                                groupTitle = ''

                            if groupTitle:
                                self.favouritesCurrentGroupId = groupTitle.strip().lower()

                            printDBG("ok_pressed favouritesCurrentGroupId[%s]" % self.favouritesCurrentGroupId)
                        except Exception:
                            printExc()

                    if item.pinLocked:
                        from Plugins.Extensions.IPTVPlayer.components.iptvpin import IPTVPinWidget
                        self.session.openWithCallback(boundFunction(self.checkDirPin, self.requestListFromHost, 'ForItem', currSelIndex, '', item.pinCode), IPTVPinWidget, title=_("Enter pin"))
                    else:
                        self.requestListFromHost('ForItem', currSelIndex, '')
                elif item.type == CDisplayListItem.TYPE_MORE:
                    printDBG("ok_pressed selected TYPE_MORE")
                    self.currSelIndex = currSelIndex
                    self.requestListFromHost('ForMore', currSelIndex, '')
                elif item.type == CDisplayListItem.TYPE_ARTICLE:
                    printDBG("ok_pressed selected TYPE_ARTICLE")
                    self.info_pressed()
                elif item.type == CDisplayListItem.TYPE_SEARCH:
                    printDBG("ok_pressed selected TYPE_SEARCH")
                    self.stopAutoPlaySequencer()
                    self.currSelIndex = currSelIndex
                    self.startSearchProcedure(item.possibleTypesOfSearch)
        else:
            self.showWindow()
    # end ok_pressed(self):

    def pageup_pressed(self):
        self.stopAutoPlaySequencer()
        if self.visible and self.prevSelList and self.prevSelList[-1]:
            self.nextSelIndex = self.prevSelList.pop() - len(self.currList)
            self.categoryList.pop()
            printDBG(f"back_pressed prev sel index {self.nextSelIndex}")
            self.requestListFromHost('Previous')

    def pagedown_pressed(self):
        self.stopAutoPlaySequencer()
        if self.visible:
            try:
                if len(self.currList) > 0 and (not self["list"].getVisible()):
                    printDBG("pagedown_pressed -> ignored /\\")
                    return
            except Exception:
                printExc()

            if self.currList:
                lastItem = self.currList[-1]
                if lastItem.type == CDisplayListItem.TYPE_NEXT:
                    self.currSelIndex = len(self.currList) - 1
                    self.requestListFromHost('ForItem', self.currSelIndex, '')

    def checkDirPin(self, callbackFun, arg1, arg2, arg3, pinCode, pin=None):
        if pin is not None:
            if 4 != len(pinCode):
                pinCode = config.plugins.iptvplayer.pin.value  # use default pin code if custom has wrong length
            if pin == pinCode:
                callbackFun(arg1, arg2, arg3)
            else:
                self.session.open(MessageBox, _("Pin incorrect!"), type=MessageBox.TYPE_INFO, timeout=5)

    def leaveArticleView(self):
        printDBG("leaveArticleView")
        pass

    def showArticleContent(self, ret):
        printDBG("showArticleContent")
        self.setStatusTex("")
        self["list"].show()

        artItem = None
        if ret.status != RetHost.OK or 0 == len(ret.value):
            item = self.currList[self.currSelIndex]
            if len(item.description):
                artItem = ArticleContent(title=item.name, text=item.description, images=[{'title': 'Fot.', 'url': item.iconimage}])  # richDescParams={"alternate_title":"***alternate_title", "year":"year", "rating":"rating",  "duration":"duration",  "genre":"genre",  "director":"director",  "actors":"actors",  "awards":"awards"}
        else:
            artItem = ret.value[0]
        if None is not artItem:
            self.session.openWithCallback(self.leaveArticleView, IPTVArticleView, artItem, {'buffering_path': config.plugins.iptvplayer.bufferingPath.value, 'host_name': self.hostName, 'logo_path': self.hostLogoPath, 'download_dir': self.iconMenager.currDownloadDir})

    def selectMainVideoLinks(self, ret):
        printDBG("selectMainVideoLinks")
        self.setStatusTex("")
        self["list"].show()

        # ToDo: check ret.status if not OK do something :P
        if ret.status != RetHost.OK:
            printDBG("++++++++++++++++++++++ selectHostVideoLinksCallback ret.status = %s" % ret.status)
        else:
            # update links in List
            currSelIndex = self.getSelIndex()
            if -1 == currSelIndex:
                return
            self.currList[currSelIndex].urlItems = ret.value
        self.selectLinkForCurrVideo()
    # end selectMainVideoLinks(self, ret):

    def selectResolvedVideoLinks(self, ret):
        printDBG("selectResolvedVideoLinks")
        self.setStatusTex("")
        self["list"].show()
        linkList = []
        if ret.status == RetHost.OK and isinstance(ret.value, list):
            for item in ret.value:
                if isinstance(item, CUrlItem):
                    item.urlNeedsResolve = 0  # protection from recursion
                    linkList.append(item)
                elif isinstance(item, str):
                    linkList.append(CUrlItem(item, item, 0))
                else:
                    printExc("selectResolvedVideoLinks: wrong resolved url type!")
        else:
            printExc()

        resolvingLink = self._resolvingLinkItem
        self._resolvingLinkItem = None
        # only reopen the picker on failure when there was genuinely a choice of
        # several mirrors to begin with - for a single mirror (or the non-interactive
        # autoplay sequencer, which always auto-picks the first one) reopening would
        # just re-select and re-resolve the very same failing link again
        if (0 == len(linkList) and resolvingLink is not None and self._currentLinkOptions is not None and
                len(self._currentLinkOptions) > 1 and not self.autoPlaySeqStarted):
            # resolving this particular mirror failed - mark it, tell the user, then
            # reopen the full mirror list (instead of dead-ending on "no valid links")
            # so they can see it highlighted and try another one
            resolvingLink.failed = True
            message = _("No valid links available.")
            lastErrorMsg = GetIPTVPlayerLastHostError()
            if '' != lastErrorMsg:
                message += "\n" + _('Last error: "%s"') % lastErrorMsg
            self.session.openWithCallback(self._reopenLinkPickerAfterFailure, MessageBox, message, type=MessageBox.TYPE_INFO, timeout=10)
            return
        self.selectLinkForCurrVideo(linkList)

    def _reopenLinkPickerAfterFailure(self, ret=None):
        self.selectLinkForCurrVideo(self._currentLinkOptions)

    def getSelIndex(self):
        currSelIndex = self["list"].getCurrentIndex()
        if len(self.currList) > currSelIndex:
            return currSelIndex
        return -1

    def getSelItem(self):
        currSelIndex = self["list"].getCurrentIndex()
        if len(self.currList) <= currSelIndex:
            printDBG("ERROR: getSelItem there is no item with index: %d, listOfItems.len: %d" % (currSelIndex, len(self.currList)))
            return None
        return self.currList[currSelIndex]

    def getSelectedItem(self):
        sel = None
        try:
            sel = self["list"].l.getCurrentSelection()[0]
        except Exception:
            return None
        return sel

    def onStart(self):
        self.onShow.remove(self.onStart)
        # self.onLayoutFinish.remove(self.onStart)
        self.setTitle('E2iPlayer ' + GetIPTVPlayerVersion())
        self.loadSpinner()
        self.hideSpinner()
        self.selectHost()

    def selectHost(self, arg1=None):
        printDBG(">> selectHost")
        # self.groupObj = None
        self.groupDisplayName = None
        self.group = None
        self.host = None
        self.hostName = ''
        self.nextSelIndex = 0
        self.prevSelList = []
        self.categoryList = []
        self.currList = []
        self.currItem = CDisplayListItem()

        if (config.plugins.iptvplayer.group_hosts.value is False or 0 == GetAvailableIconSize()):
            self.selectHostFromSingleList()
        else:
            self.selectGroup()

    def selectGroup(self):
        printDBG(">> selectGroup")
        self.groupObj = IPTVHostsGroups()
        self.displayGroupsList = []
        groupsList = self.groupObj.getGroupsList()
        for item in groupsList:
            self.displayGroupsList.append((item.title, item.name))
        if not GRIDSUPPORT:
            self.displayGroupsList.append((_('All'), 'all'))
            self.displayGroupsList.append((_("Configuration"), "config"))

        self.newDisplayGroupsList = []
        self.session.openWithCallback(self.selectGroupCallback, PlayerSelectorWidget, inList=self.displayGroupsList, outList=self.newDisplayGroupsList, numOfLockedItems=self.getNumOfSpecialItems(self.displayGroupsList), groupName='selectgroup')

    def selectGroupCallback(self, ret):
        printDBG(">> selectGroupCallback")
        # save groups order if user change it at player selection
        if self.newDisplayGroupsList != self.displayGroupsList:
            numOfSpecialItems = self.getNumOfSpecialItems(self.newDisplayGroupsList)
            groupList = []
            for idx in range(len(self.newDisplayGroupsList) - numOfSpecialItems):
                groupList.append(self.newDisplayGroupsList[idx][1])
            self.groupObj.setGroupList(groupList)

        self.selectItemCallback(ret, 'selectgroup')

    def selectHostFromGroup(self):
        printDBG(">> selectHostFromGroup")
        self.host = None
        self.hostName = ''
        self.nextSelIndex = 0
        self.prevSelList = []
        self.categoryList = []
        self.currList = []
        self.currItem = CDisplayListItem()

        self.displayHostsList = []
        if self.group != 'all':
            hostsList = self.groupObj.getHostsList(self.group)
        else:
            hostsList = []
            sortedList = SortHostsList(GetHostsList(fromList=False, fromHostFolder=True))
            for hostName in sortedList:
                if IsHostEnabled(hostName):
                    hostsList.append(hostName)

        brokenHostList = []
        for hostName in hostsList:
            if hostName == "localmedia":
                title = _("LocalMedia")
            elif hostName == "favourites":
                title = _("Favorites")
            else:
                try:
                    _temp = __import__('Plugins.Extensions.IPTVPlayer.hosts.host' + hostName, globals(), locals(), ['gettytul'], 0)
                    title = _temp.gettytul()
                except Exception:
                    printExc('get host name exception for host "%s"' % hostName)
                    brokenHostList.append('host' + hostName)
                    continue
            self.displayHostsList.append((title, hostName))

        # if there is no order hosts list use old behavior for all group
        if self.group == 'all' and 0 == len(GetHostsOrderList()):
            try:
                self.displayHostsList.sort(key=lambda t: tuple(str(t[1]).lower()))
            except Exception:
                self.displayHostsList.sort()

        # prepare info message when some host or update cannot be used
        errorMessage = ""
        if len(brokenHostList) > 0:
            errorMessage = _("Following host are broken or additional python modules are needed.") + '\n' + '\n'.join(brokenHostList)

        if "" != errorMessage and True is self.showHostsErrorMessage:
            self.showHostsErrorMessage = False
            self.session.openWithCallback(self.displayListOfHostsFromGroup, MessageBox, errorMessage, type=MessageBox.TYPE_INFO, timeout=10)
        else:
            self.displayListOfHostsFromGroup()
        return

    def displayListOfHostsFromGroup(self, arg=None):
        printDBG(">> displayListOfHostsFromGroup")
        self.newDisplayHostsList = []
        if len(self.displayHostsList):
            self.session.openWithCallback(self.selectHostFromGroupCallback, PlayerSelectorWidget, inList=self.displayHostsList, outList=self.newDisplayHostsList, numOfLockedItems=0, groupName=self.group, groupObj=self.groupObj, groupDisplayName=self.groupDisplayName)
        else:
            msg = _('There is no hosts in this group.')
            self.session.openWithCallback(self.selectHost, MessageBox, msg, type=MessageBox.TYPE_INFO, timeout=10)

    def selectHostFromGroupCallback(self, ret):
        printDBG(">> selectHostFromGroupCallback")

        # save hosts order if user change it at player selection
        if self.newDisplayHostsList != self.displayHostsList:
            hostsList = []
            for idx in range(len(self.newDisplayHostsList)):
                hostsList.append(self.newDisplayHostsList[idx][1])
            if self.group != 'all':
                self.groupObj.setHostsList(self.group, hostsList)
            else:
                SaveHostsOrderList(hostsList)
        self.groupObj.flushAddedHosts()
        self.selectItemCallback(ret, 'selecthostfromgroup')

    def selectHostFromSingleList(self):
        self.displayHostsList = []
        sortedList = SortHostsList(GetHostsList(fromList=False, fromHostFolder=True))
        brokenHostList = []
        for hostName in sortedList:
            if IsHostEnabled(hostName):
                try:
                    _temp = __import__('Plugins.Extensions.IPTVPlayer.hosts.host' + hostName, globals(), locals(), ['gettytul'], 0)
                    title = _temp.gettytul()
                except Exception:
                    printExc('get host name exception for host "%s"' % hostName)
                    brokenHostList.append('host' + hostName)
                    continue

                # The 'http...' in host titles is annoying on regular choiceBox and impacts sorting.
                # To simplify choiceBox usage and clearly show service is a webpage, list is build using the "<service name> (<service URL>)" schema.
                """
                if (config.plugins.iptvplayer.ListaGraficzna.value is False or 0 == GetAvailableIconSize()) and title[:4] == 'http':
                    try:
                        title = ('%s   (%s)') % ('.'.join(title.replace('://', '.').replace('www.', '').split('.')[1:-1]), title)
                    except Exception:
                        pass
                """
                self.displayHostsList.append((title, hostName))
        # if there is no order hosts list use old behavior
        if 0 == len(GetHostsOrderList()):
            try:
                self.displayHostsList.sort(key=lambda t: tuple(str(t[0]).lower()))
            except Exception:
                self.displayHostsList.sort()
        if not GRIDSUPPORT:
            self.displayHostsList.append((_("Configuration"), "config"))

        # prepare info message when some host or update cannot be used
        errorMessage = ""
        if len(brokenHostList) > 0:
            errorMessage = _("Following host are broken or additional python modules are needed.") + '\n' + '\n'.join(brokenHostList)

        if "" != errorMessage and True is self.showHostsErrorMessage:
            self.showHostsErrorMessage = False
            self.session.openWithCallback(self.displayListOfHosts, MessageBox, errorMessage, type=MessageBox.TYPE_INFO, timeout=10)
        else:
            self.displayListOfHosts()
        return

    def displayListOfHosts(self, arg=None):
        """
        if config.plugins.iptvplayer.ListaGraficzna.value is False or 0 == GetAvailableIconSize():
            self.newDisplayHostsList = None
            self.session.openWithCallback(self.selectHostCallback, ChoiceBox, title=_("Select service"), list=self.displayHostsList)
        else:
        """
        self.newDisplayHostsList = []
        self.session.openWithCallback(self.selectHostCallback, PlayerSelectorWidget, inList=self.displayHostsList, outList=self.newDisplayHostsList, numOfLockedItems=self.getNumOfSpecialItems(self.displayHostsList), groupName='selecthost')

    def getNumOfSpecialItems(self, inList, filters=['config', 'all']):
        if GRIDSUPPORT:
            return 0
        numOfSpecialItems = 0
        for item in inList:
            if item[1] in filters:
                numOfSpecialItems += 1
        return numOfSpecialItems

    def selectHostCallback(self, ret):
        printDBG(">> selectHostCallback")
        # save hosts order if user change it at player selection
        if self.newDisplayHostsList is not None and self.newDisplayHostsList != self.displayHostsList:
            numOfSpecialItems = self.getNumOfSpecialItems(self.newDisplayHostsList)
            hostsList = []
            for idx in range(len(self.newDisplayHostsList) - numOfSpecialItems):
                hostsList.append(self.newDisplayHostsList[idx][1])
            SaveHostsOrderList(hostsList)

        self.selectHostCallback2(ret)

    def selectHostCallback2(self, ret):
        printDBG(">> selectHostCallback2")
        self.selectItemCallback(ret, 'selecthost')

    def selectItemCallback(self, ret, type):
        printDBG(">> selectItemCallback ret[%s] type[%s]" % (ret, type))
        hasIcon = False
        nextFunction = None
        prevFunction = None
        protectedByPin = False
        if ret:
            if ret[1] == "config":
                nextFunction = self.runConfig
                prevFunction = self.selectHost
                protectedByPin = config.plugins.iptvplayer.configProtectedByPin.value
            elif ret[1] == "reset_group":
                self.groupObj.resetHostList(ret[2])
                self.selectHost()
            elif ret[1] == "config_hosts":
                nextFunction = self.runConfigHosts
                if type == 'selecthost':
                    prevFunction = self.selectHost
                else:
                    prevFunction = self.selectHostFromGroup
                protectedByPin = config.plugins.iptvplayer.configProtectedByPin.value
            elif ret[1] == "config_groups":
                nextFunction = self.runConfigGroupsMenu
                prevFunction = self.selectHost
                protectedByPin = config.plugins.iptvplayer.configProtectedByPin.value
            elif ret[1] == "IPTVDM":
                if type in ['selecthost', 'selectgroup']:
                    self.runIPTVDM(self.selectHost)
                elif type == 'selecthostfromgroup':
                    self.runIPTVDM(self.selectHostFromGroup)
                return
            elif type in ['selecthost', 'selecthostfromgroup']:
                self.hostTitle = ret[0]
                self.hostName = ret[1]
                self.loadHost()
            elif type == 'selectgroup':
                self.group = ret[1]
                self.groupDisplayName = ret[0]
                self.selectHostFromGroup()
                return

            if self.showMessageNoFreeSpaceForIcon and hasIcon:
                self.showMessageNoFreeSpaceForIcon = False
                self.session.open(MessageBox, (_("There is no free space on the drive [%s].") % config.plugins.iptvplayer.SciezkaCache.value) + "\n" + _("New icons will not be available."), type=MessageBox.TYPE_INFO, timeout=10)
        elif type in ['selecthost', 'selectgroup']:
            self.close()
            return
        else:
            self.selectHost()
            return

        if nextFunction and prevFunction:
            if True is protectedByPin:
                from .iptvpin import IPTVPinWidget
                self.session.openWithCallback(boundFunction(self.checkPin, nextFunction, prevFunction), IPTVPinWidget, title=_("Enter pin"))
            else:
                nextFunction()

    def runConfigHosts(self):
        self.enabledHostsListOld = GetEnabledHostsList()
        self.session.openWithCallback(self.configHostsCallback, ConfigHostsMenu, GetListOfHostsNames())

    def configHostsCallback(self, arg1=None):
        if self.group is not None:
            self.selectHostFromGroup()
        else:
            self.selectHost()

    def runConfigGroupsMenu(self):
        self.session.openWithCallback(self.selectHost, ConfigGroupsMenu)

    def runConfig(self):
        self.session.openWithCallback(self.configCallback, ConfigMenu)

    def runConfigHostIfAllowed(self):
        if config.plugins.iptvplayer.configProtectedByPin.value:
            from .iptvpin import IPTVPinWidget
            self.session.openWithCallback(boundFunction(self.checkPin, self.runConfigHost, None), IPTVPinWidget, title=_("Enter pin"))
        else:
            self.runConfigHost()

    def runConfigHost(self):
        self.session.openWithCallback(self.runConfigHostCallBack, ConfigHostMenu, hostName=self.hostName)

    def runConfigHostCallBack(self, confgiChanged=False):
        if confgiChanged:
            self.loadHost()

    def checkPin(self, callbackFun, failCallBackFun, pin=None):
        if pin is not None:
            if pin == config.plugins.iptvplayer.pin.value:
                callbackFun()
            else:
                self.session.openWithCallback(self.close, MessageBox, _("Pin incorrect!"), type=MessageBox.TYPE_INFO, timeout=5)
        else:
            if failCallBackFun:
                failCallBackFun()

    def loadHost(self, ret=None):
        self.hostFavTypes = []
        try:
            _temp = __import__('Plugins.Extensions.IPTVPlayer.hosts.host' + self.hostName, globals(), locals(), ['IPTVHost'], 0)
            self.host = _temp.IPTVHost()
            if not isinstance(self.host, IHost):
                printDBG("Host [%r] does not inherit from IHost" % self.hostName)
                self.close()
                return
        except Exception as e:
            printExc('Cannot import class IPTVHost for host [%r]' % self.hostName)
            errorMessage = [_('Loading %s failed due to following error:') % self.hostName]
            elines = traceback.format_exc().splitlines()
            errorMessage.append("%s" % '\n'.join(elines[-3:]))
            self.session.open(MessageBox, '\n'.join(errorMessage), type=MessageBox.TYPE_ERROR, timeout=10)
            self.setStatusTex(_("Failed: %s") % e)
            return

        try:
            protectedByPin = self.host.isProtectedByPinCode()
        except Exception:
            protected = False  # should never happen

        if protectedByPin:
            from .iptvpin import IPTVPinWidget
            self.session.openWithCallback(boundFunction(self.checkPin, self.loadHostData, self.selectHost), IPTVPinWidget, title=_("Enter pin"))
        else:
            self.loadHostData()

    def loadHostData(self):
        self.session.summary.setText(self.hostName)
        self.activePlayer = CMoviePlayerPerHost(self.hostName)

        # change logo for player
        self["playerlogo"].hide()
        self.session.summary.LCD_hide('LCDlogo')
        self.hostLogoPath = None
        try:
            hRet = self.host.getLogoPath()
            if hRet.status == RetHost.OK and len(hRet.value):
                logoPath = hRet.value[0]
                if logoPath != '':
                    printDBG('Logo Path: ' + logoPath)
                    self.hostLogoPath = logoPath
                    if not self["playerlogo"].checkDecodeNeeded(logoPath):
                        self["playerlogo"].show()
                    else:
                        self["playerlogo"].decodeCover(logoPath, self.updateCover, "playerlogo")
                    self.session.summary.LCD_showPic('LCDlogo', logoPath)
        except Exception:
            printExc()

        # get types of items which can be added as favourites
        self.hostFavTypes = []
        try:
            hRet = self.host.getSupportedFavoritesTypes()
            if hRet.status == RetHost.OK:
                self.hostFavTypes = hRet.value
        except Exception:
            printExc('The current host crashed')

        # request initial list from host
        self.getInitialList()
    # end selectHostCallback(self, ret):

    def selectLinkForCurrVideo(self, customUrlItems=None):
        if not self.visible and not (self.autoPlaySeqStarted and
           config.plugins.iptvplayer.autoplay_start_delay.value == 0):
            self.setStatusTex("")
            self.showWindow()

        item = self.getSelItem()
        if item.type not in [CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO,
                             CDisplayListItem.TYPE_PICTURE, CDisplayListItem.TYPE_DATA]:
            printDBG("Incorrect item type[%s]" % item.type)
            return

        if None is customUrlItems:
            links = item.urlItems
        else:
            links = customUrlItems

        # There is no free links for current video
        numOfLinks = len(links)
        if 0 == numOfLinks:
            self._currentLinkOptions = None
            if not self.checkAutoPlaySequencer():
                message = _("No valid links available.")
                lastErrorMsg = GetIPTVPlayerLastHostError()
                if '' != lastErrorMsg:
                    message += "\n" + _('Last error: "%s"') % lastErrorMsg
                lastExcMSG = getExcMSG(True)
                if lastExcMSG != '':
                    message += "\n" + _("Last Exception error: '%s'") % lastExcMSG
                self.session.open(MessageBox, message, type=MessageBox.TYPE_INFO, timeout=10)
            return
        elif 1 == numOfLinks or self.autoPlaySeqStarted:
            # call manualy selectLinksCallback - start VIDEO without links selection
            self._currentLinkOptions = links
            self.selectLinksCallback(IPTVChoiceBoxItem(" ", "", links[0]))  # name of item - not displayed so empty
            return

        self._currentLinkOptions = links
        options = []
        for link in links:
            printDBG("selectLinkForCurrVideo: |%s| |%s|" % (link.name, link.url))
            options.append(IPTVChoiceBoxItem(link.name, "", link, failed=link.failed))

        self.session.openWithCallback(self.selectLinksCallback, IPTVChoiceBoxWidget, {'width': 600, 'height': self._getLinkPickerHeight(), 'current_idx': 0, 'title': _("Select link"), 'options': options, 'list_class': IPTVLinkChoiceBoxList})

    # IPTVChoiceBoxWidget's screen declares resolution="1280,720", so the
    # skin engine already scales width/size per axis to the real screen
    # (1x HD, 1.5x FHD, 2x WQHD) - this has to be a single reference-space
    # constant, not stepped up per tier like the old code did, or it gets
    # scaled twice (which is exactly why WQHD ended up nearly full-screen)
    MOVIE_PLAYER_PICKER_WIDTH = 550

    def _getMoviePlayerPickerHeight(self, numItems):
        # same reference-space-vs-real-pixels reasoning as _getLinkPickerHeight,
        # but using IPTVRadioButtonList's (IPTVMainNavigatorList's) own real
        # per-tier item heights (35/40/55) instead of guessed constants.
        # +130 = the footerMargin passed below (120, itself derived from the
        # list's fixed y=66 + the 48px footer bar) plus a small 10px
        # breathing buffer - not the keyboard's own +160, which assumes the
        # chrome default footerMargin (150) instead of this screen's 120
        screenwidth = getDesktop(0).size().width()
        if screenwidth >= 2560:
            itemH, scale = 55, 2.0
        elif screenwidth >= 1920:
            itemH, scale = 40, 1.5
        else:
            itemH, scale = 35, 1.0
        return int(numItems * itemH / scale) + 130

    def _getLinkPickerHeight(self):
        # IPTVChoiceBoxWidget's skin is defined in a fixed 1280x720 reference space
        # and scaled per-axis to the real screen resolution by the skin engine, so
        # these are reference-space pixel heights, not real ones. Tuned so HD and
        # FullHD both show 12 rows before the list starts scrolling (up from ~6/~9
        # at the previous default of 300), and SD gets a few more rows too.
        resType = self.getSkinResolutionType()
        if resType == 'sd':
            return 370
        elif resType == 'hd':
            return 380
        elif resType == 'hd_ready':
            return 480
        return 300

    def selectLinksCallback(self, retArg):
        if retArg is None:
            # user cancelled the picker without trying any link - there's nothing
            # wrong, so don't show a "No valid links" error for it
            return
        if isinstance(retArg, IPTVChoiceBoxItem) and isinstance(retArg.privateData, CUrlItem):
            link = retArg.privateData
            videoUrl = link.url
            if isinstance(videoUrl, str) and len(videoUrl) > 3:
                # check if we need to resolve this URL (strict '1' check, same as the
                # original ChoiceBox-based code - some hosts store this as a string,
                # and a plain truthiness check would wrongly treat "0" as needing resolve)
                if str(link.urlNeedsResolve) == '1':
                    # call resolve link from host
                    self._resolvingLinkItem = link
                    self.requestListFromHost('ResolveURL', -1, videoUrl)
                else:
                    list = []
                    list.append(videoUrl)
                    self.playVideo(RetHost(status=RetHost.OK, value=list))
                return
        self.playVideo(RetHost(status=RetHost.ERROR, value=[]))
    # end selectLinksCallback(self, retArg):

    def checkBuffering(self, url):
        # check flag forcing of the using/not using buffering
        if 'iptv_buffering' in url.meta:
            if "required" == url.meta['iptv_buffering']:
                # iptv_buffering was set as required, this is done probably due to
                # extra http headers needs, at now extgstplayer and exteplayer can handle this headers,
                # so we skip forcing buffering for such links. at now this is temporary
                # solution we need to add separate filed iptv_extraheaders_need!
                if url.startswith("http") and self.getMoviePlayer(False, False).value in ['extgstplayer', 'exteplayer']:
                    pass  # skip forcing buffering
                else:
                    return True
            elif "forbidden" == url.meta['iptv_buffering']:
                return False
        if "|" in url:
            return True

        # check based on protocol
        protocol = url.meta.get('iptv_proto', '')
        protocol = url.meta.get('iptv_proto', '')
        if protocol in ['f4m', 'uds']:
            return True  # supported only in buffering mode
        elif protocol in ['http', 'https']:
            return config.plugins.iptvplayer.buforowanie.value
        elif 'rtmp' == protocol:
            return config.plugins.iptvplayer.buforowanie_rtmp.value
        elif protocol in ['m3u8', 'em3u8']:
            return config.plugins.iptvplayer.buforowanie_m3u8.value

    def isUrlBlocked(self, url, type):
        protocol = url.meta.get('iptv_proto', '')
        if ".wmv" == self.getFileExt(url, type) and config.plugins.iptvplayer.ZablokujWMV.value:
            return True, _("Format 'wmv' blocked in configuration.")
        elif '' == protocol:
            return True, _("Unknown protocol [%s]") % url
        return False, ''

    def getFileExt(self, url, type):
        format = url.meta.get('iptv_format', '')
        if '' != format:
            return '.' + format
        protocol = url.meta.get('iptv_proto', '')

        fileExtension = ''
        tmp = url.lower().split('?', 1)[0]
        for item in ['avi', 'flv', 'mp4', 'ts', 'mov', 'wmv', 'mpeg', 'mpg', 'mkv', 'vob', 'divx', 'm2ts', 'mp3', 'm4a', 'ogg', 'wma', 'fla', 'wav', 'flac']:
            if tmp.endswith('.' + item):
                fileExtension = '.' + item
                break

        if '' == fileExtension:
            if protocol in ['mms', 'mmsh', 'rtsp']:
                fileExtension = '.wmv'
            elif protocol in ['f4m', 'uds', 'rtmp']:
                fileExtension = '.flv'
            else:
                if type == CDisplayListItem.TYPE_VIDEO:
                    fileExtension = '.mp4'  # default video extension
                else:
                    fileExtension = '.mp3'  # default audio extension
        return fileExtension

    def getMoviePlayer(self, buffering=False, useAlternativePlayer=False):
        printDBG("getMoviePlayer")
        return GetMoviePlayer(buffering, useAlternativePlayer)

    def writeCurrentTitleToFile(self, title):
        titleFilePath = config.plugins.iptvplayer.curr_title_file.value
        if "" != titleFilePath:
            try:
                with open(titleFilePath, 'w') as titleFile:
                    titleFile.write(title)
            except Exception:
                printExc()
        """
        if config.plugins.iptvplayer.set_curr_title.value:
            try:
                from enigma import evfd
                title = CParsingHelper.getNormalizeStr(title)
                evfd.getInstance().vfd_write_string(title[0:17])
            except Exception:
                printExc()
        """

    def playVideo(self, ret):
        printDBG("playVideo")
        url = ''
        if RetHost.OK == ret.status:
            if len(ret.value) > 0:
                url = ret.value[0]

        self.setStatusTex("")
        self["list"].show()

        if url != '' and CDisplayListItem.TYPE_PICTURE == self.currItem.type:
            self.session.openWithCallback(self.leavePicturePlayer, IPTVPicturePlayerWidget, url, config.plugins.iptvplayer.bufferingPath.value, self.currItem.name, {'seq_mode': self.autoPlaySeqStarted})
        elif url != '' and self.isDownloadableType(self.currItem.type):
            printDBG("playVideo url[%s]" % url)
            if self.currItem.type == CDisplayListItem.TYPE_DATA:
                recorderMode = True
            else:
                recorderMode = self.recorderMode
            url = urlparser.decorateUrl(url)
            titleOfMovie = self.currItem.name.replace('/', '-').replace(':', '-').replace('*', '-').replace('?', '-').replace('"', '-').replace('<', '-').replace('>', '-').replace('|', '-')
            fileExtension = self.getFileExt(url, self.currItem.type)

            blocked, reaseon = self.isUrlBlocked(url, self.currItem.type)
            if blocked:
                self.session.open(MessageBox, reaseon, type=MessageBox.TYPE_INFO, timeout=10)
                return

            isBufferingMode = False if url.startswith('file://') else self.activePlayer.get('buffering', self.checkBuffering(url))
            bufferingPath = config.plugins.iptvplayer.bufferingPath.value
            downloadingPath = config.plugins.iptvplayer.NaszaSciezka.value
            destinationPath = downloadingPath if recorderMode else bufferingPath

            if recorderMode or isBufferingMode:
                errorTab = []
                if not os_path.exists(destinationPath):
                    iptvtools_mkdirs(destinationPath)

                if not os_path.isdir(destinationPath):
                    errorTab.append(_("Directory \"%s\" does not exists.") % destinationPath)
                    errorTab.append(_("Please set valid %s in the %s configuration.") % (_("downloads location") if recorderMode else _("buffering location"), 'E2iPlayer'))
                else:
                    requiredSpace = 3 * 512 * 1024 * 1024  # 1,5 GB
                    availableSpace = iptvtools_FreeSpace(destinationPath, requiredSpace=None, unitDiv=1)
                    if requiredSpace > availableSpace:
                        errorTab.append(_("There is no enough free space in the folder \"%s\".") % destinationPath)
                        errorTab.append(_("\tDisk space required: %s") % formatBytes(requiredSpace))
                        errorTab.append(_("\tDisk space available: %s") % formatBytes(availableSpace))

                if errorTab:
                    errorTab.append("\n")
                    errorTab.append(_("Tip! You can connect USB flash drive to fix this problem."))
                    self.stopAutoPlaySequencer()
                    self.session.open(MessageBox, '\n'.join(errorTab), type=MessageBox.TYPE_INFO, timeout=10)
                    return

            global gDownloadManager
            if recorderMode:
                if None is not gDownloadManager:
                    if IsUrlDownloadable(url):
                        fullFilePath = downloadingPath + '/' + titleOfMovie + fileExtension
                        ret = gDownloadManager.addToDQueue(DMItem(url, fullFilePath))
                    else:
                        ret = False
                        self.session.open(MessageBox, _("File can not be downloaded. Protocol [%s] is unsupported") % url.meta.get('iptv_proto', ''), type=MessageBox.TYPE_INFO, timeout=10)
                    if ret:
                        if not self.checkAutoPlaySequencer():
                            if config.plugins.iptvplayer.IPTVDMShowAfterAdd.value:
                                self.runIPTVDM()
                            else:
                                self.session.open(MessageBox, _("File [%s] was added to downloading queue.") % titleOfMovie, type=MessageBox.TYPE_INFO, timeout=10)
                    else:
                        self.stopAutoPlaySequencer()
                else:
                    self.stopAutoPlaySequencer()
            else:
                # genuinely about to stream (not download) and every earlier check
                # (blocked url, missing directory, low disk space) already passed -
                # this is the only place that marks the item "started"
                try:
                    if hasattr(self.host, 'markItemAsStarted'):
                        self.host.markItemAsStarted(self["list"].getCurrentIndex())
                except Exception:
                    printExc()

                self.prevVideoMode = GetE2VideoMode()
                printDBG("Current video mode [%s]" % self.prevVideoMode)
                gstAdditionalParams = {'defaul_videomode': self.prevVideoMode, 'host_name': self.hostName, 'external_sub_tracks': url.meta.get('external_sub_tracks', []), 'iptv_refresh_cmd': url.meta.get('iptv_refresh_cmd', '')}  # default_player_videooptions
                if self.currItem.type == CDisplayListItem.TYPE_AUDIO:
                    gstAdditionalParams['show_iframe'] = config.plugins.iptvplayer.show_iframe.value
                    gstAdditionalParams['iframe_file_start'] = config.plugins.iptvplayer.iframe_file.value
                    gstAdditionalParams['iframe_file_end'] = config.plugins.iptvplayer.clear_iframe_file.value
                    gstAdditionalParams['iframe_continue'] = False

                self.writeCurrentTitleToFile(titleOfMovie)
                if isBufferingMode:
                    self.session.nav.stopService()
                    player = self.activePlayer.get('player', self.getMoviePlayer(True, self.useAlternativePlayer))
                    self.session.openWithCallback(self.leaveMoviePlayer, E2iPlayerBufferingWidget, url, bufferingPath, downloadingPath, titleOfMovie, player.value, self.bufferSize, gstAdditionalParams, gDownloadManager, fileExtension)
                else:
                    self.session.nav.stopService()
                    player = self.activePlayer.get('player', self.getMoviePlayer(False, self.useAlternativePlayer))
                    if "mini" == player.value:
                        self.session.openWithCallback(self.leaveMoviePlayer, IPTVMiniMoviePlayer, url, titleOfMovie)
                    elif "standard" == player.value:
                        self.session.openWithCallback(self.leaveMoviePlayer, IPTVStandardMoviePlayer, url, titleOfMovie)
                    else:
                        if "extgstplayer" == player.value:
                            playerVal = 'gstplayer'
                            gstAdditionalParams['download-buffer-path'] = ''
                            gstAdditionalParams['ring-buffer-max-size'] = 0
                            gstAdditionalParams['buffer-duration'] = 18000  # 300min
                            gstAdditionalParams['buffer-size'] = 10240  # 10MB
                        else:
                            assert ("exteplayer" == player.value)
                            playerVal = 'eplayer'
                        self.session.openWithCallback(self.leaveMoviePlayer, IPTVExtMoviePlayer, url, titleOfMovie, None, playerVal, gstAdditionalParams)
        else:
            # There was problem in resolving direct link for video
            if not self.checkAutoPlaySequencer():
                self.session.open(MessageBox, _("No valid links available."), type=MessageBox.TYPE_INFO, timeout=10)
    # end playVideo(self, ret):

    def leaveMoviePlayer(self, answer=None, lastPosition=None, clipLength=None, *args, **kwargs):
        self.writeCurrentTitleToFile("")
        videoMode = GetE2VideoMode()
        printDBG("Current video mode [%s], previus video mode [%s]" % (videoMode, self.prevVideoMode))
        if None not in [self.prevVideoMode, videoMode] and self.prevVideoMode != videoMode:
            printDBG("Restore previus video mode")
            SetE2VideoMode(self.prevVideoMode)

        try:
            if answer is not None:
                self.stopAutoPlaySequencer()
        except Exception:
            printExc()

        if not config.plugins.iptvplayer.disable_live.value and not self.autoPlaySeqStarted:
            self.session.nav.playService(self.currentService)

        if lastPosition is not None and clipLength is not None and clipLength > 0:
            try:
                if config.plugins.iptvplayer.favourites_use_watched_flag.value and (lastPosition * 100 / clipLength) > 95 and hasattr(self.host, 'markItemAsViewed'):
                    currSelIndex = self["list"].getCurrentIndex()
                    self.requestListFromHost('MarkItemAsViewed', currSelIndex)
                    return
            except Exception:
                printExc()

        self.checkAutoPlaySequencer()

    def leavePicturePlayer(self, answer=None, lastPosition=None, *args, **kwargs):
        self.checkAutoPlaySequencer()

    def requestListFromHost(self, type, currSelIndex=-1, privateData=''):

        if not self.isInWorkThread():
            self["list"].hide()
            GetIPTVSleep().Reset()

            if type not in ['ForVideoLinks', 'ResolveURL', 'ForArticleContent', 'ForFavItem', 'PerformCustomAction']:
                # hide bottom panel
                self["cover"].hide()
                self["console"].setText('')

            if (type == 'ForItem' or type == 'ForSearch') and getattr(self.currItem, 'type', None) not in CDisplayListItem.NON_NAVIGATING_TYPES:
                self.prevSelList.append(self.currSelIndex)
                if type == 'ForSearch':
                    self.categoryList.append(_("Search results"))
                else:
                    self.categoryList.append(self.currItem.name)
                # new list, so select first index
                self.nextSelIndex = 0

            selItem = None
            if currSelIndex > -1 and len(self.currList) > currSelIndex:
                selItem = self.currList[currSelIndex]
                if self.isPlayableType(selItem.type) and selItem.itemIdx > -1 and len(self.currList) > selItem.itemIdx:
                    currSelIndex = selItem.itemIdx

            dots = ""  # _("...............")
            IDS_DOWNLOADING = _("Downloading") + dots
            IDS_LOADING = _("Loading") + dots
            IDS_REFRESHING = _("Refreshing") + dots
            try:
                if type == 'Refresh':
                    self.setStatusTex(IDS_REFRESHING)
                    self.workThread = asynccall.AsyncMethod(self.host.getCurrentList, boundFunction(self.callbackGetList, {'refresh': 1, 'selIndex': currSelIndex}), True)(1)
                elif type == 'ForMore':
                    self.setStatusTex(IDS_DOWNLOADING)
                    self.workThread = asynccall.AsyncMethod(self.host.getMoreForItem, boundFunction(self.callbackGetList, {'refresh': 2, 'selIndex': currSelIndex}), True)(currSelIndex)
                elif type == 'Initial':
                    self.setStatusTex(IDS_DOWNLOADING)
                    self.workThread = asynccall.AsyncMethod(self.host.getInitList, boundFunction(self.callbackGetList, {}), True)()
                elif type == 'Previous':
                    self.setStatusTex(IDS_DOWNLOADING)
                    self.workThread = asynccall.AsyncMethod(self.host.getPrevList, boundFunction(self.callbackGetList, {}), True)()
                elif type == 'ForItem':
                    self.setStatusTex(IDS_DOWNLOADING)
                    self.workThread = asynccall.AsyncMethod(self.host.getListForItem, boundFunction(self.callbackGetList, {}), True)(currSelIndex, 0, selItem)
                elif type == 'ForVideoLinks':
                    self.setStatusTex(IDS_LOADING)
                    self.workThread = asynccall.AsyncMethod(self.host.getLinksForVideo, self.selectHostVideoLinksCallback, True)(currSelIndex, selItem)
                elif type == 'ResolveURL':
                    self.setStatusTex(IDS_LOADING)
                    self.workThread = asynccall.AsyncMethod(self.host.getResolvedURL, self.getResolvedURLCallback, True)(privateData)
                elif type == 'ForSearch':
                    self.setStatusTex(IDS_LOADING)
                    self.workThread = asynccall.AsyncMethod(self.host.getSearchResults, boundFunction(self.callbackGetList, {}), True)(self.searchPattern, self.searchType)
                elif type == 'ForArticleContent':
                    self.setStatusTex(IDS_DOWNLOADING)
                    self.workThread = asynccall.AsyncMethod(self.host.getArticleContent, self.getArticleContentCallback, True)(currSelIndex)
                elif type == 'ForFavItem':
                    self.setStatusTex(IDS_LOADING)
                    self.workThread = asynccall.AsyncMethod(self.host.getFavouriteItem, self.getFavouriteItemCallback, True)(currSelIndex)
                elif type == 'PerformCustomAction':
                    self.workThread = asynccall.AsyncMethod(self.host.performCustomAction, self.performCustomActionCallback, True)(privateData)
                elif type == 'MarkItemAsViewed':
                    self.workThread = asynccall.AsyncMethod(self.host.markItemAsViewed, self.markItemAsViewedCallback, True)(currSelIndex)
                else:
                    printDBG('requestListFromHost unknown list type: ' + type)
                self.showSpinner()
            except Exception:
                printExc('The current host crashed')
    # end requestListFromHost(self, type, currSelIndex = -1, privateData = ''):

    def startSearchProcedure(self, searchTypes):
        if config.plugins.iptvplayer.osk_remember_last_search.value:
            sts, prevPattern = CSearchHistoryHelper.loadLastPattern()
            if sts:
                self.searchPattern = prevPattern
        else:
            self.searchPattern = ''
        if searchTypes:
            self.session.openWithCallback(self.selectSearchTypeCallback, ChoiceBox, title=_("Search type"), list=searchTypes)
        else:
            self.searchType = None
            self.doSearchWithVirtualKeyboard()

    def selectSearchTypeCallback(self, ret=None):
        if ret:
            self.searchType = ret[1]
            self.doSearchWithVirtualKeyboard()
        else:
            pass

    def _resolveSuggestionsProvider(self):
        # !!! NON BLOCKING !!! host suggestions call method directly on the
        # host, so it must never block. Used both for the keyboard's initial
        # provider and, via additionalParams['resolve_suggestions_provider'],
        # to re-resolve live when "Default suggestions provider" / "Allow
        # host to override suggestions provider" change while the keyboard
        # is already open (e2ivk.py calls it again from its Settings-closed
        # callback).
        suggestionsProvider = None
        try:
            if config.plugins.iptvplayer.osk_allow_host_suggestions.value and self.visible and not self.isInWorkThread():
                currSelIndex = self.getSelItem().itemIdx
                hRet = self.host.getSuggestionsProvider(currSelIndex)
                if hRet.status == RetHost.OK and hRet.value and hRet.value[0]:
                    suggestionsProvider = hRet.value[0] if hRet.value[0] is not None else False
        except Exception:
            printExc()

        if suggestionsProvider is None:
            providerAlias = config.plugins.iptvplayer.osk_default_suggestions.value
            if not providerAlias:
                if not self.groupObj:
                    self.groupObj = IPTVHostsGroups()
                if self.hostName in self.groupObj.PREDEFINED_HOSTS['moviesandseries']:
                    if self.hostName in self.groupObj.PREDEFINED_HOSTS['polish']:
                        providerAlias = 'filmweb'
                    else:
                        providerAlias = 'imdb'
                else:
                    providerAlias = 'google'

            if providerAlias == 'filmweb':
                from Plugins.Extensions.IPTVPlayer.suggestions.filmweb import SuggestionsProvider as filmweb_Provider
                suggestionsProvider = filmweb_Provider()
            elif providerAlias == 'imdb':
                from Plugins.Extensions.IPTVPlayer.suggestions.imdb import SuggestionsProvider as imdb_Provider
                suggestionsProvider = imdb_Provider()
            elif providerAlias == 'google':
                from Plugins.Extensions.IPTVPlayer.suggestions.google import SuggestionsProvider as google_Provider
                suggestionsProvider = google_Provider()
            elif providerAlias == 'bing':
                from Plugins.Extensions.IPTVPlayer.suggestions.bing import SuggestionsProvider as bing_Provider
                suggestionsProvider = bing_Provider()
            elif providerAlias == 'duckduckgo':
                from Plugins.Extensions.IPTVPlayer.suggestions.duckduckgo import SuggestionsProvider as duckduckgo_Provider
                suggestionsProvider = duckduckgo_Provider()
        return suggestionsProvider

    def doSearchWithVirtualKeyboard(self):
        printDBG("doSearchWithVirtualKeyboard")
        caps = {}
        virtualKeyboard = GetVirtualKeyboard(caps)

        if caps.get('has_additional_params'):
            try:
                additionalParams = {}
                if caps.get('has_suggestions') and config.plugins.iptvplayer.osk_allow_suggestions.value:
                    suggestionsProvider = self._resolveSuggestionsProvider()
                    if suggestionsProvider:
                        from Plugins.Extensions.IPTVPlayer.components.e2ivksuggestion import AutocompleteSearch
                        additionalParams['autocomplete'] = AutocompleteSearch(suggestionsProvider)
                        # only offered when the suggestions panel exists from
                        # the start - e2ivk.py's skin decides whether to lay
                        # out right_list/right_header once, at open time,
                        # based on additionalParams['autocomplete'] being set
                        additionalParams['resolve_suggestions_provider'] = self._resolveSuggestionsProvider

                self.session.openWithCallback(self.enterPatternCallBack, virtualKeyboard, title=(_("Your search entry")), text=self.searchPattern, additionalParams=additionalParams)
                return
            except Exception:
                printExc()
        self.session.openWithCallback(self.enterPatternCallBack, virtualKeyboard, title=(_("Your search entry")), text=self.searchPattern)

    def enterPatternCallBack(self, callback=None):
        if callback is not None and len(callback):
            self.searchPattern = callback
            if config.plugins.iptvplayer.osk_remember_last_search.value:
                CSearchHistoryHelper.saveLastPattern(self.searchPattern)
            self.requestListFromHost('ForSearch')

    def configCallback(self):
        self.selectHost()

    def randomizePlayableItems(self, randomize=True):
        printDBG("randomizePlayableItems")
        self.stopAutoPlaySequencer()
        if self.visible and len(self.currList) > 1 and not self.isInWorkThread():
            randList = []
            for item in self.currList:
                if isinstance(item, CDisplayListItem) and self.isPlayableType(item.type):
                    randList.append(item)
            if randomize:
                random_shuffle(randList)
            reloadList = False
            if len(self.currList) == len(randList):
                randList.reverse()
                self.currList = randList
                reloadList = True
            elif len(randList) > 1:
                newList = []
                for item in self.currList:
                    if isinstance(item, CDisplayListItem) and self.isPlayableType(item.type):
                        newList.append(randList.pop())
                    else:
                        newList.append(item)
                reloadList = True
                self.currList = newList
            if reloadList:
                self["list"].setList([(x,) for x in self.currList])

    def reversePlayableItems(self):
        printDBG("reversePlayableItems")
        self.randomizePlayableItems(False)

    def reloadList(self, params):
        printDBG("reloadList")
        # suppresses _rememberHistorySelection() while the list below is being
        # (re)built and its selection moved around programmatically
        self._isLoadingList = True
        refresh = params['add_param'].get('refresh', 0)
        selIndex = params['add_param'].get('selIndex', -1)
        ret = params['ret']
        printDBG("> E2iPlayerWidget.reloadList refresh[%s], selIndex[%s]" % (refresh, selIndex))
        if 0 < refresh and -1 < selIndex:
            self.nextSelIndex = selIndex
        # ToDo: check ret.status if not OK do something :P
        if ret.status != RetHost.OK:
            printDBG("+ reloadList ret.status = %s" % ret.status)
            self.stopAutoPlaySequencer()

        self.canRandomizeList = False
        numPlayableItems = 0
        for idx in range(len(ret.value)):
            if isinstance(ret.value[idx], CDisplayListItem):
                ret.value[idx].itemIdx = idx
                if self.isPlayableType(ret.value[idx].type):
                    numPlayableItems += 1

        if numPlayableItems > 1:
            self.canRandomizeList = True

        self.currList = ret.value
        self["list"].setList([(x,) for x in self.currList])

        self["headertext"].setText(self.getCategoryPath())
        if len(self.currList) <= 0:
            disMessage = _("No item to display. \nPress OK to refresh.\n")
            if ret.message and ret.message != '':
                disMessage += ret.message
            lastErrorMsg = GetIPTVPlayerLastHostError()
            if lastErrorMsg != '':
                disMessage += "\n" + _('Last error: "%s"') % lastErrorMsg
            lastExcMSG = getExcMSG(True)
            if lastExcMSG != '':
                disMessage += "\n" + _('Last Exception error: "%s"') % lastExcMSG

            self.setStatusTex(disMessage)
            self["list"].hide()
        else:
            # restor previus selection
            if len(self.currList) > self.nextSelIndex:
                self["list"].moveToIndex(self.nextSelIndex)
            # else:
            # selection will not be change so manualy call
            self.changeBottomPanel()

            self.setStatusTex("")
            self["list"].show()
        self._isLoadingList = False
        self._restoreHistorySelection()
        self.updateDownloadButton()
        if 2 == refresh:
            self.autoPlaySequencerNext(False)
        elif 1 == refresh:
            self.autoPlaySequencerNext()
    # end reloadList(self, ret):

    def getCategoryPath(self):
        def _getCat(cat, num):
            if '' == cat:
                return ''
            cat = ' > ' + cat
            if 1 < num:
                cat += (' (x%d)' % num)
            return cat

        # str = self.hostName
        str = self.hostTitle
        prevCat = ''
        prevNum = 0
        for cat in self.categoryList:
            if prevCat != cat:
                str += _getCat(prevCat, prevNum)
                prevCat = cat
                prevNum = 1
            else:
                prevNum += 1
        str += _getCat(prevCat, prevNum)
        return str

    def getRefreshedCurrList(self):
        currSelIndex = self["list"].getCurrentIndex()
        self.requestListFromHost('Refresh', currSelIndex)

    def getInitialList(self):
        self.nexSelIndex = 0
        self.prevSelList = []
        self.categoryList = []
        self.currList = []
        self.currItem = CDisplayListItem()
        self.favouritesCurrentGroupId = ''
        self["headertext"].setText(self.getCategoryPath())
        self.requestListFromHost('Initial')

    def hideWindow(self):
        self.visible = False
        self.hide()

    def showWindow(self):
        self.visible = True
        self.show()

    def createSummary(self):
        return IPTVPlayerLCDScreen

    def canByAddedToFavourites(self):
        try:
            favouritesHostActive = config.plugins.iptvplayer.hostfavourites.value
        except Exception:
            favouritesHostActive = False
        cItem = None
        index = -1
        # we need to check if fav is available
        if not self.isInWorkThread() and favouritesHostActive and self.visible:
            cItem = self.getSelItem()
            if None is not cItem and (cItem.isGoodForFavourites or cItem.type in self.hostFavTypes):
                index = self.getSelIndex()
            else:
                cItem = None
        return index, cItem

    def getFavouriteItemCallback(self, thread, ret):
        asynccall.gMainFunctionsQueueTab[0].addToQueue("handleFavouriteItemCallback", [thread, ret])

    def handleFavouriteItemCallback(self, ret):
        printDBG("E2iPlayerWidget.handleFavouriteItemCallback")
        self.setStatusTex("")
        self["list"].show()
        if ret.status == RetHost.OK and isinstance(ret.value, list) and 1 == len(ret.value) and isinstance(ret.value[0], CFavItem):
            favItem = ret.value[0]
            if CFavItem.RESOLVER_SELF == favItem.resolver:
                favItem.resolver = self.hostName
            if '' == favItem.hostName:
                favItem.hostName = self.hostName
            self.session.open(IPTVFavouritesAddItemWidget, favItem)
        else:
            self.session.open(MessageBox, _("No valid links available."), type=MessageBox.TYPE_INFO, timeout=10)

    def menu_pressed(self):
        printDBG("E2iPlayerWidget.menu_pressed")
        # we have to be careful here as we will call method
        # directly from host
        options = []
        try:
            if self.visible and not self.isInWorkThread():
                try:
                    item = self.getSelItem()
                except Exception:
                    printExc()
                    item = None
                if None is not item:
                    currSelIndex = item.itemIdx  # self["list"].getCurrentIndex()
                else:
                    currSelIndex = -1
                hRet = self.host.getCustomActions(currSelIndex)
                if hRet.status == RetHost.OK and len(hRet.value):
                    for item in hRet.value:
                        if isinstance(item, IPTVChoiceBoxItem):
                            options.append(item)

                try:
                    if -1 < self.canByAddedToFavourites()[0]:
                        options.append(IPTVChoiceBoxItem(_("Add item to favorites"), "", {'e2i_menu_action': 'ADD_FAV'}))
                    elif 'favourites' == self.hostName:
                        options.append(IPTVChoiceBoxItem(_("Remove from favorites"), "", {'e2i_menu_action': 'DELETE_FAV'}))
                except Exception:
                    printExc()
            if len(options):
                self.stopAutoPlaySequencer()
                self.session.openWithCallback(self.requestCustomActionFromHost, IPTVChoiceBoxWidget, {'width': 600, 'current_idx': 0, 'title': _("Select action"), 'options': options})
        except Exception:
            printExc()

    def requestCustomActionFromHost(self, ret):
        printDBG("E2iPlayerWidget.requestCustomActionFromHost ret[%r]" % [ret])
        if isinstance(ret, IPTVChoiceBoxItem):
            menuAction = ret.privateData.get('e2i_menu_action') if isinstance(ret.privateData, dict) else None
            if menuAction == 'ADD_FAV':
                currSelIndex = self.canByAddedToFavourites()[0]
                self.requestListFromHost('ForFavItem', currSelIndex, '')
                return
            elif menuAction == 'DELETE_FAV':
                self.session.openWithCallback(self.deleteFavouriteItem, MessageBox, _('Definitely remove from favorites?'), type=MessageBox.TYPE_YESNO, timeout=10)
                return
            self.requestListFromHost('PerformCustomAction', -1, ret.privateData)

    def performCustomActionCallback(self, thread, ret):
        asynccall.gMainFunctionsQueueTab[0].addToQueue("handlePerformCustomActionCallback", [thread, ret])

    def handlePerformCustomActionCallback(self, ret):
        printDBG("E2iPlayerWidget.handlePerformCustomActionCallback")
        self.setStatusTex("")
        self["list"].show()
        if ret.status == RetHost.OK and isinstance(ret.value, list) and 1 == len(ret.value):
           self.yellow_pressed()
        elif ret.status == RetHost.ERROR and isinstance(ret.value, list) and 1 == len(ret.value) and isinstance(ret.value[0], str):
           self.session.open(MessageBox, ret.value[0], type=MessageBox.TYPE_ERROR)

    def markItemAsViewedCallback(self, thread, ret):
        asynccall.gMainFunctionsQueueTab[0].addToQueue("handleMarkItemAsViewedCallback", [thread, ret])

    def handleMarkItemAsViewedCallback(self, ret):
        printDBG("E2iPlayerWidget.handleMarkItemAsViewedCallback")
        self.setStatusTex("")
        self["list"].show()
        if ret.status == RetHost.OK and isinstance(ret.value, list) and 1 == len(ret.value) and 'refresh' in ret.value:
           self.getRefreshedCurrList()
        elif ret.status == RetHost.ERROR and isinstance(ret.value, list) and 1 == len(ret.value) and isinstance(ret.value[0], str):
           self.session.open(MessageBox, ret.value[0], type=MessageBox.TYPE_ERROR)
        else:
            self.checkAutoPlaySequencer()

# class E2iPlayerWidget


class IPTVPlayerLCDScreen(Screen):
    try:
        summary_screenwidth = getDesktop(1).size().width()
        summary_screenheight = getDesktop(1).size().height()
    except Exception:
        summary_screenwidth = 132
        summary_screenheight = 64
    if summary_screenwidth >= 800 and summary_screenheight >= 480:
        skin = """
    <screen position="0,0" size="800,480" title="E2iPlayer">
        <widget name="text1" position="10,0"  size="800,70" font="Regular;50" halign="center" valign="center" foregroundColor="#05F7F3"/>
        <widget name="text2" position="10,80" size="800,70" font="Regular;40" halign="center" valign="center" foregroundColor="#FFFF00"/>
        <widget name="LCDlogo" position="0,210" zPosition="4" size="800,267" alphatest="blend" />
    </screen>"""
    elif summary_screenwidth >= 480 and summary_screenheight >= 320:
        skin = """
    <screen position="0,0" size="480,320" title="E2iPlayer">
        <widget name="text1" position="10,0" size="460,70" font="Regular;50" halign="center" valign="center" foregroundColor="#05F7F3"/>
        <widget name="text2" position="10,80" size="460,70" font="Regular;40" halign="center" valign="center" foregroundColor="#FFFF00"/>
        <widget name="LCDlogo" position="0,160" zPosition="4" size="480,160" alphatest="blend" />
    </screen>"""
    elif summary_screenwidth >= 220 and summary_screenheight >= 176:
        skin = """
    <screen position="0,0" size="220,176" title="E2iPlayer">
        <widget name="text1" position="5,0" size="210,26" font="Regular;24" halign="center" valign="center" foregroundColor="#05F7F3"/>
        <widget name="text2" position="5,30" size="210,65" font="Regular;22" halign="center" valign="center" foregroundColor="#FFFF00"/>
        <widget name="LCDlogo" position="5,106" size="210,70" zPosition="4" alphatest="blend" />
    </screen>"""
    else:
        skin = """
    <screen position="0,0" size="132,64" title="E2iPlayer">
        <widget name="text1" position="4,0" size="132,14" font="Regular;12" halign="center" valign="center"/>
        <widget name="text2" position="4,14" size="132,49" font="Regular;10" halign="center" valign="center"/>
        <widget name="LCDlogo" zPosition="4" position="4,70" size="240,80" alphatest="blend" />
    </screen>"""

    def __init__(self, session, parent):
        Screen.__init__(self, session)
        try:
            self["text1"] = Label("E2iPlayer")
            self["text2"] = Label("")
            self["LCDlogo"] = Pixmap()
        except Exception:
            pass

    def setText(self, text):
        try:
            self["text2"].setText(text[0:39])
        except Exception:
            pass

    def LCD_showPic(self, widgetName, picPath):
        try:
            self[widgetName].instance.setScale(1)
            self[widgetName].instance.setPixmap(LoadPixmap(picPath))
            self[widgetName].show()
        except Exception:
            pass

    def LCD_hide(self, widgetName):
        try:
            self[widgetName].hide()
        except Exception:
            pass
