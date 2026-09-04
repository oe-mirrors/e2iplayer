# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import (
    printDBG,
    printExc,
    GetDefaultLang,
    GetSkinsDir,
    GetIPTVPlayerVersion,
    eConnectCallback,
    GetPluginDir,
    iptv_system,
    IsSubtitlesParserExtensionCanBeUsed,
)
from Plugins.Extensions.IPTVPlayer.components.ihost import CDisplayListItem, RetHost
from Plugins.Extensions.IPTVPlayer.components.isubprovider import ISubProvider
from Plugins.Extensions.IPTVPlayer.components.iptvlist import IPTVMainNavigatorList
from Plugins.Extensions.IPTVPlayer.components.cover import Cover3
from Plugins.Extensions.IPTVPlayer.components import skinchrome
from Plugins.Extensions.IPTVPlayer.components.e2ivkselector import GetVirtualKeyboard
from Plugins.Extensions.IPTVPlayer.libs.pCommon import CParsingHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta

###################################################

###################################################
# FOREIGN import
###################################################
from os import path as os_path
from urllib.parse import quote as urllib_quote

from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.Label import Label
from Components.ActionMap import ActionMap
from Tools.LoadPixmap import LoadPixmap
from Components.config import config
from Components.Sources.StaticText import StaticText
from Tools.BoundFunction import boundFunction
from enigma import eTimer

###################################################

####################################################
#                   IPTV components
####################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import (
    TranslateTXT as _,
    GetIPTVPlayerLastHostError,
)
import Plugins.Extensions.IPTVPlayer.components.asynccall as asynccall

###################################################

# Title patterns for discovering season and episode numbers
RE_SEASON_EPISODE_SE = r"s([0-9]+?)e([0-9]+?)[^0-9]"
RE_SEASON_EPISODE_X = r"[^0-9]([0-9]+?)x([0-9]+?)[^0-9]"


class IPTVSubDownloaderWidget(Screen):
    """Widget for downloading subtitles from various providers."""

    IPTV_VERSION = GetIPTVPlayerVersion()

    # was a class-level `screenwidth = getDesktop(0).size().width()` +
    # `if screenwidth == 1920: skin = "..." else: skin = "..."` - same
    # stale-at-import-time bug fixed everywhere else in this branch, plus
    # only 2 hand-duplicated tiers (WQHD fell through to the HD block,
    # same "== 1920 only distinguishes FHD" bug variant already fixed on
    # other screens). Both blocks were otherwise a clean x1.5 scale of
    # each other (every number in the FHD block is exactly 1.5x its HD
    # counterpart) - confirms this screen's own layout was always meant
    # to scale uniformly, exactly what `skinchrome`'s tiered `scale=`
    # helpers already do. Not `resolution="1280,720"` auto-scale though -
    # the spinner dots are real per-tier pixel assets
    # (`radio_button_on/off.png`, loaded via plain `LoadPixmap` with no
    # `BT_SCALE`, so the source file itself has to already be the tier's
    # real size), same reasoning as E2iVirtualKeyBoard/
    # E2iPlayerBufferingWidget.
    #
    # Header/footer: hand-rolled BG_Title/logo/Title-widget/shadowlines +
    # BG_Buttons/red-icon+key_red-label/ok+exit-icons replaced with
    # `build_header()`/`build_footer()`. Footer grows 48->64 (skinchrome's
    # 2-line color-key wrap, same delta as everywhere else in this branch)
    # - window height grown by that same delta (660->676 at HD) rather
    # than compressing the existing list/headertext/console/statustext
    # layout, which otherwise carries over completely unchanged (still
    # comfortably clears the taller footer with room to spare). Middle
    # divider (between the list and headertext, `y=400` at HD) has no
    # equivalent in `build_header()`/`build_footer()` - kept as its own
    # plain `<ePixmap>`, matching every other genuinely custom mid-screen
    # divider in this branch.
    #
    # Footer keys: `showMenu=False` (no "menu" action bound at all),
    # `showNav=True`/`showOk=True`/`showExit=True` (up/down aren't bound
    # explicitly, but the list navigates itself natively - same proven
    # pattern as `IPTVMainNavigatorList`/`IPTVChoiceBoxWidget` elsewhere;
    # `ok`/`back` are genuinely live). `keys=('red',)` only - `red_pressed`
    # (`self.close(None)`) is real; `green_pressed`/`yellow_pressed`/
    # `blue_pressed` are all permanent no-op stubs (`pass`), so they get
    # no color-key hint, matching this branch's policy of never hinting a
    # dead action. `hideButtons()` (referenced `self["icon_green"]` etc.,
    # which never existed even in the old skin) was already dead code -
    # never called anywhere - dropped rather than migrated.
    #
    # Custom-skin-file override (`config.plugins.iptvplayer.skin` ->
    # `subplaylist.xml`) is untouched and still works exactly as before -
    # no widget was renamed, so an existing custom skin file keeps
    # matching the same names this built-in one now produces differently.
    def __prepareSkin(self):
        scale = skinchrome.getScale()
        iconBase = skinchrome.getIconBase()
        shadowline = iconBase + '/smallshadowline.png'

        def _s(value):
            return skinchrome.scalePixels(value, scale)

        WIDTH = _s(1020)
        HEIGHT = _s(676)
        spinnerSize = _s(16)
        spinnerX = _s(508)
        spinnerY = _s(240)
        skin = ["""<screen name="IPTVSubDownloaderWidget" position="center,center" size="%d,%d" title="IPTV Sub Title Downloader" backgroundColor="#34111112" flags="wfNoBorder">""" % (WIDTH, HEIGHT)]
        skin.append(skinchrome.build_header(scale=scale, iconBase=iconBase, showLogo=True))
        skin.append(skinchrome.build_footer(HEIGHT, scale=scale, iconBase=iconBase, keys=('red',), showMenu=False, showNav=True, showNum=False, showOk=True, showExit=True))
        skin.append('<widget name="list" position="%d,%d" size="%d,%d" itemHeight="%d" font="Regular;%d" scrollbarMode="showOnDemand" scrollbarSliderBorderWidth="1" scrollbarForegroundColor="#1b5a91" scrollbarBorderColor="#00b6b6b6" enableWrapAround="1" transparent="1" foregroundColor="white" backgroundColor="black" foregroundColorSelected="white" backgroundColorSelected="#1b5a91" borderWidth="1" borderColor="black" />' % (_s(10), _s(70), _s(1000), _s(320), _s(32), _s(20)))
        skin.append('<ePixmap pixmap="%s" position="0,%d" size="%d,%d" zPosition="2" />' % (shadowline, _s(400), WIDTH, _s(2)))
        skin.append('<widget name="headertext" position="%d,%d" size="%d,%d" font="Regular;%d" foregroundColor="#0066ccff" backgroundColor="black" borderWidth="1" borderColor="black" halign="left" valign="center" transparent="1" />' % (_s(10), _s(410), _s(1000), _s(30), _s(20)))
        skin.append('<widget name="console" position="%d,%d" size="%d,%d" font="Regular;%d" transparent="1" zPosition="1" backgroundColor="black" foregroundColor="white" borderWidth="1" borderColor="black" shadowColor="black" shadowOffset="-2,-2" />' % (_s(10), _s(450), _s(1000), _s(70), _s(20)))
        skin.append('<widget name="statustext" position="%d,%d" size="%d,%d" font="Regular;%d" halign="left" valign="center" transparent="1" backgroundColor="black" foregroundColor="green" />' % (_s(10), _s(530), _s(1000), _s(70), _s(20)))
        skin.append('<widget name="spinner" zPosition="2" position="%d,%d" size="%d,%d" transparent="1" alphatest="blend" />' % (spinnerX, spinnerY, spinnerSize, spinnerSize))
        for i in range(1, 5):
            skin.append('<widget name="spinner_%d" zPosition="1" position="%d,%d" size="%d,%d" transparent="1" alphatest="blend" />' % (i, spinnerX + (i - 1) * spinnerSize, spinnerY, spinnerSize, spinnerSize))
        skin.append('</screen>')
        return '\n'.join(skin)

    def __init__(self, session, params={}):
        """
        Initialize the subtitle downloader widget.

        Args:
            session: Enigma2 session
            params: Dictionary with movie_title, movie_url and vk_title
        """
        printDBG(
            "IPTVSubDownloaderWidget.__init__ desktop IPTV_VERSION[%s]\n"
            % (IPTVSubDownloaderWidget.IPTV_VERSION)
        )
        self.session = session
        self.skin = self.__prepareSkin()
        skinName = config.plugins.iptvplayer.skin.value
        if skinName:
            path = GetSkinsDir(skinName) + "/subplaylist.xml"
            if os_path.exists(path):
                try:
                    with open(path, "r") as f:
                        self.skin = f.read()
                        f.close()
                except Exception:
                    printExc("Skin read error: " + path)

        Screen.__init__(self, session)
        self.skinName = skinchrome.forceInternalSkinName(["IPTVSubDownloaderScreen", "IPTVSubDownloaderWidget"])

        self["key_red"] = StaticText(_("Cancel"))

        self["list"] = IPTVMainNavigatorList()
        self["list"].connectSelChanged(self.onSelectionChanged)
        self["statustext"] = Label("Loading...")
        self["actions"] = ActionMap(
            ["IPTVPlayerListActions", "ColorActions"],
            {
                "red": self.red_pressed,
                "green": self.green_pressed,
                "yellow": self.yellow_pressed,
                "blue": self.blue_pressed,
                "ok": self.ok_pressed,
                "back": self.back_pressed,
            },
            -1,
        )

        self["headertext"] = Label()
        self["console"] = Label()

        try:
            for idx in range(5):
                spinnerName = "spinner"
                if idx:
                    spinnerName += "_%d" % idx
                self[spinnerName] = Cover3()
        except Exception:
            printExc()

        # per-tier assets (icons/HD, FHD or WQHD, matching __prepareSkin()'s
        # own scaled spinner box) - plain Pixmap widgets never scale their
        # pixmap content to the declared box, so the source file itself
        # has to already be the right size (same bug/fix as the legacy
        # grid's page markers in playerselector.py). Real 3-tier
        # `skinchrome.getIconBase()` now, not the old 2-tier FHD/HD-only
        # `_spinnerIconDir` (WQHD used to silently fall back to HD-sized
        # dots, same bug already fixed on the header/footer icons above).
        iconBase = skinchrome.getIconBase()
        self.spinnerPixmap = [
            LoadPixmap(iconBase + "/radio_button_on.png"),
            LoadPixmap(iconBase + "/radio_button_off.png"),
        ]
        self.showHostsErrorMessage = True

        self.onClose.append(self.__onClose)
        self.onShow.append(self.onStart)

        # Store original params and discover info from title
        self.params = dict(params)
        self.params["discover_info"] = self.discoverInfoFromTitle()
        self.params["movie_url"] = strwithmeta(self.params.get("movie_url", ""))
        self.params["url_params"] = self.params["movie_url"].meta

        # Use original movie title initially, will be updated when user confirms
        self.originalMovieTitle = self.params.get("movie_title", "")
        self.movieTitle = self.params["discover_info"]["movie_title"]

        self.workThread = None
        self.host = None
        self.hostName = ""

        self.nextSelIndex = 0
        self.currSelIndex = 0

        self.prevSelList = []
        self.categoryList = []

        self.currList = []
        self.currItem = CDisplayListItem()

        self.visible = True

        # Register function in main Queue
        if None is asynccall.gMainFunctionsQueueTab[1]:
            asynccall.gMainFunctionsQueueTab[1] = asynccall.CFunctionProxyQueue(
                self.session
            )
        asynccall.gMainFunctionsQueueTab[1].clearQueue()
        asynccall.gMainFunctionsQueueTab[1].setProcFun(self.doProcessProxyQueueItem)

        # Main Queue timer - checks every 100ms
        self.mainTimer = eTimer()
        self.mainTimer_conn = eConnectCallback(
            self.mainTimer.timeout, self.processProxyQueue
        )
        self.mainTimer_interval = 100
        self.mainTimer.start(self.mainTimer_interval, True)

        # Spinner animation timer
        self.spinnerTimer = eTimer()
        self.spinnerTimer_conn = eConnectCallback(
            self.spinnerTimer.timeout, self.updateSpinner
        )
        self.spinnerTimer_interval = 200
        self.spinnerEnabled = False

        self.downloadedSubItems = []

    def __del__(self):
        """Cleanup on object deletion."""
        printDBG("IPTVSubDownloaderWidget.__del__ --------------------------")

    def __onClose(self):
        """Cleanup when screen is closed."""
        self["list"].disconnectSelChanged(self.onSelectionChanged)
        self.mainTimer_conn = None
        self.mainTimer = None
        self.spinnerTimer_conn = None
        self.spinnerTimer = None

        try:
            asynccall.gMainFunctionsQueueTab[1].setProcFun(None)
            asynccall.gMainFunctionsQueueTab[1].clearQueue()
        except Exception:
            printExc()

    def onStart(self):
        """Called when screen is shown."""
        self.onShow.remove(self.onStart)
        self.loadSpinner()
        self.hideSpinner()
        self.confirmMovieTitle()

    def confirmMovieTitle(self):
        """Ask user to confirm or edit the movie title."""
        self.session.openWithCallback(
            self.confirmMovieTitleCallBack,
            GetVirtualKeyboard(),
            title=(_("Confirm the title of the movie")),
            text=self.movieTitle,
        )

    def confirmMovieTitleCallBack(self, text=None):
        """
        Callback after user confirms movie title.

        Updates the movie title and discovery info based on user input,
        then lists available subtitle providers.

        Args:
            text: Confirmed/edited movie title from user
        """
        if isinstance(text, str):
            self.movieTitle = text
            # Update discovered info with user-confirmed title
            self.params["discover_info"] = self.discoverInfoFromTitle(self.movieTitle)
            self.params["confirmed_title"] = self.movieTitle
            self.listSubtitlesProviders()
        else:
            self.close()

    def red_pressed(self):
        """Red button - cancel and close."""
        self.close(None)

    def green_pressed(self):
        """Green button action."""
        pass

    def yellow_pressed(self):
        """Yellow button action."""
        pass

    def blue_pressed(self):
        """Blue button action."""
        pass

    def back_pressed(self):
        """Back button - navigate to previous list or exit."""
        printDBG("IPTVSubDownloaderWidget.back_pressed")
        try:
            if self.isInWorkThread():
                if self.workThread.kill():
                    self.workThread = None
                    self["statustext"].setText(_("Operation aborted!"))
                return
        except Exception:
            return
        if self.visible:
            if len(self.prevSelList) > 0:
                self.nextSelIndex = self.prevSelList.pop()
                self.categoryList.pop()
                printDBG("back_pressed prev sel index %s" % self.nextSelIndex)
                if len(self.prevSelList) > 0:
                    self.requestListFromHost("Previous")
                else:
                    self.listSubtitlesProviders()
            else:
                # No previous categories, ask for title confirmation again
                self.confirmMovieTitle()
        else:
            self.showWindow()

    def ok_pressed(self):
        """OK button - select item or download subtitle."""
        if self.visible:
            sel = None
            try:
                sel = self["list"].l.getCurrentSelection()[0]
            except Exception:
                self.getRefreshedCurrList()
                return
            if sel is None:
                printDBG("ok_pressed sel is None")
                return

            elif len(self.currList) <= 0:
                printDBG("ok_pressed list is empty")
                self.getRefreshedCurrList()
                return
            else:
                printDBG("ok_pressed selected item: %s" % (sel.name))

                item = self.getSelItem()
                self.currItem = item

                # Get current selection index
                currSelIndex = self["list"].getCurrentIndex()
                # Remember only previous categories
                if item.type in [CDisplayListItem.TYPE_SUB_PROVIDER]:
                    try:
                        self.hostName = item.privateData["sub_provider"]
                        self.loadHost()
                    except Exception:
                        printExc()
                elif item.type in [CDisplayListItem.TYPE_SUBTITLE]:
                    self.requestListFromHost("ForDownloadSubFile", currSelIndex, "")
                elif item.type == CDisplayListItem.TYPE_CATEGORY:
                    printDBG("ok_pressed selected TYPE_CATEGORY")
                    self.currSelIndex = currSelIndex
                    self.requestListFromHost("ForItem", currSelIndex, "")
                elif item.type == CDisplayListItem.TYPE_MORE:
                    printDBG("ok_pressed selected TYPE_MORE")
                    self.currSelIndex = currSelIndex
                    self.requestListFromHost("ForMore", currSelIndex, "")
        else:
            self.showWindow()

    def loadHost(self):
        """
        Dynamically load the selected subtitle provider.

        Imports the appropriate subprovider module and initializes it
        with the confirmed movie title.
        """
        try:
            _temp = __import__(
                "Plugins.Extensions.IPTVPlayer.subproviders.subprov_" + self.hostName,
                globals(),
                locals(),
                ["IPTVSubProvider"],
                0,
            )
            params = dict(self.params)
            # Use the user-confirmed title for subtitle search
            params["confirmed_title"] = self.movieTitle
            params["movie_title"] = self.movieTitle
            params["discover_info"] = self.discoverInfoFromTitle(self.movieTitle)
            self.host = _temp.IPTVSubProvider(params)
            if not isinstance(self.host, ISubProvider):
                printDBG("Host [%r] does not inherit from ISubProvider" % self.hostName)
                self.close()
                return
        except Exception:
            printExc(
                "Cannot import class IPTVSubProvider for host [%r]" % self.hostName
            )
            self.close()
            return
        # Request initial list from host
        self.getInitialList()

    def loadSpinner(self):
        """Load spinner animation images."""
        try:
            if "spinner" in self:
                self["spinner"].setPixmap(self.spinnerPixmap[0])
                for idx in range(4):
                    spinnerName = "spinner_%d" % (idx + 1)
                    self[spinnerName].setPixmap(self.spinnerPixmap[1])
        except Exception:
            printExc()

    def showSpinner(self):
        """Show loading spinner animation."""
        if None is not self.spinnerTimer:
            self._setSpinnerVisibility(True)
            self.spinnerTimer.start(self.spinnerTimer_interval, True)

    def hideSpinner(self):
        """Hide loading spinner animation."""
        self._setSpinnerVisibility(False)

    def _setSpinnerVisibility(self, visible=True):
        """Set visibility of all spinner widgets."""
        self.spinnerEnabled = visible
        try:
            if "spinner" in self:
                for idx in range(5):
                    spinnerName = "spinner"
                    if idx:
                        spinnerName += "_%d" % idx
                    self[spinnerName].visible = visible
        except Exception:
            printExc()

    def updateSpinner(self):
        """Animate the spinner by moving the active dot."""
        try:
            if self.spinnerEnabled and None is not self.workThread:
                if self.workThread.isAlive():
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
                    message = (
                        _(
                            'It seems that the subtitle\'s provider "%s" has crashed. Do you want to report this problem?'
                        )
                        % self.hostName
                    )
                    message += "\n"
                    message += _(
                        "\nMake sure you are using the latest version of the plugin."
                    )
                    message += _(
                        "\nYou can also report problem here: \nhttps://github.com/oe-mirrors/e2iplayer/issues"
                    )
                    self.session.openWithCallback(
                        self.reportHostCrash,
                        MessageBox,
                        text=message,
                        type=MessageBox.TYPE_YESNO,
                    )
            self.hideSpinner()
        except Exception:
            printExc()

    def reportHostCrash(self, ret):
        """Report crashed subtitle provider if user agrees."""
        try:
            if ret:
                try:
                    exceptStack = self.workThread.getExceptStack()
                    reporter = GetPluginDir("iptvdm/reporthostcrash.py")
                    msg = urllib_quote(
                        "%s|%s|%s|%s"
                        % (
                            "HOST_CRASH",
                            IPTVSubDownloaderWidget.IPTV_VERSION,
                            self.hostName,
                            self.getCategoryPath(),
                        )
                    )
                    self.crashConsole = iptv_system(
                        'python "%s" "http://iptvplayer.vline.pl/reporthostcrash.php?msg=%s" "%s" 2&>1 > /dev/null'
                        % (reporter, msg, exceptStack)
                    )
                    printDBG(msg)
                except Exception:
                    printExc()
            self.workThread = None
            self.prevSelList = []
            self.back_pressed()
        except Exception:
            printExc()

    def processProxyQueue(self):
        """Process the main function proxy queue."""
        if None is not self.mainTimer:
            asynccall.gMainFunctionsQueueTab[1].processQueue()
            self.mainTimer.start(self.mainTimer_interval, True)
        return

    def doProcessProxyQueueItem(self, item):
        """Execute a callback from the proxy queue."""
        try:
            if None is item.retValue[0] or self.workThread == item.retValue[0]:
                if isinstance(item.retValue[1], asynccall.CPQParamsWrapper):
                    getattr(self, item.clientFunName)(*item.retValue[1])
                else:
                    getattr(self, item.clientFunName)(item.retValue[1])
            else:
                printDBG(
                    ">>>>>>>>>>>>>>> doProcessProxyQueueItem callback from old workThread[%r][%s]"
                    % (self.workThread, item.retValue)
                )
        except Exception:
            printDBG("Exception in doProcessProxyQueueItem")

    def getCategoryPath(self):
        """Build breadcrumb path string for current navigation."""
        def _getCat(cat, num):
            if "" == cat:
                return ""
            cat = " > " + cat
            if 1 < num:
                cat += " (x%d)" % num
            return cat

        if len(self.categoryList):
            str = self.hostName
        else:
            str = _("Select subtitles provider:")
        prevCat = ""
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
        """Refresh the current list."""
        currSelIndex = self["list"].getCurrentIndex()
        self.requestListFromHost("Refresh", currSelIndex)

    def getInitialList(self):
        """Get the initial list from the subtitle provider."""
        self.nexSelIndex = 0
        self.prevSelList = []
        self.categoryList = []
        self.currList = []
        self.currItem = CDisplayListItem()
        self["headertext"].setText(self.getCategoryPath())
        self.requestListFromHost("Initial")

    def requestListFromHost(self, type, currSelIndex=-1, privateData=""):
        """
        Request a list from the current subtitle provider.

        Args:
            type: Type of request (Initial, ForItem, ForMore, Previous, Refresh, ForDownloadSubFile)
            currSelIndex: Currently selected index
            privateData: Additional private data for the request
        """
        if not self.isInWorkThread():
            self["list"].hide()

            if type not in ["ForDownloadSubFile"]:
                # Hide bottom panel
                self["console"].setText("")

            if type in ["ForItem", "Initial"]:
                self.prevSelList.append(self.currSelIndex)
                self.categoryList.append(self.currItem.name)
                # New list, select first index
                self.nextSelIndex = 0

            selItem = None
            if currSelIndex > -1 and len(self.currList) > currSelIndex:
                selItem = self.currList[currSelIndex]
                if selItem.itemIdx > -1 and len(self.currList) > selItem.itemIdx:
                    currSelIndex = selItem.itemIdx

            dots = ""
            IDS_DOWNLOADING = _("Downloading") + dots
            IDS_REFRESHING = _("Refreshing") + dots
            try:
                if type == "Refresh":
                    self["statustext"].setText(IDS_REFRESHING)
                    self.workThread = asynccall.AsyncMethod(
                        self.host.getCurrentList,
                        boundFunction(
                            self.callbackGetList,
                            {"refresh": 1, "selIndex": currSelIndex},
                        ),
                        True,
                    )(1)
                elif type == "ForMore":
                    self["statustext"].setText(IDS_DOWNLOADING)
                    self.workThread = asynccall.AsyncMethod(
                        self.host.getMoreForItem,
                        boundFunction(
                            self.callbackGetList,
                            {"refresh": 2, "selIndex": currSelIndex},
                        ),
                        True,
                    )(currSelIndex)
                elif type == "Initial":
                    self["statustext"].setText(IDS_DOWNLOADING)
                    self.workThread = asynccall.AsyncMethod(
                        self.host.getInitList,
                        boundFunction(self.callbackGetList, {}),
                        True,
                    )()
                elif type == "Previous":
                    self["statustext"].setText(IDS_DOWNLOADING)
                    self.workThread = asynccall.AsyncMethod(
                        self.host.getPrevList,
                        boundFunction(self.callbackGetList, {}),
                        True,
                    )()
                elif type == "ForItem":
                    self["statustext"].setText(IDS_DOWNLOADING)
                    self.workThread = asynccall.AsyncMethod(
                        self.host.getListForItem,
                        boundFunction(self.callbackGetList, {}),
                        True,
                    )(currSelIndex, 0)
                elif type == "ForDownloadSubFile":
                    self["statustext"].setText(IDS_DOWNLOADING)
                    self.workThread = asynccall.AsyncMethod(
                        self.host.downloadSubtitleFile,
                        boundFunction(self.downloadSubtitleFileCallback, {}),
                        True,
                    )(currSelIndex)
                else:
                    printDBG("requestListFromHost unknown list type: " + type)
                self["headertext"].setText(self.getCategoryPath())
                self.showSpinner()
            except Exception:
                printExc("The current host crashed")

    def callbackGetList(self, addParam, thread, ret):
        """Callback after getting list from host - adds to proxy queue."""
        asynccall.gMainFunctionsQueueTab[1].addToQueue(
            "reloadList", [thread, {"add_param": addParam, "ret": ret}]
        )

    def downloadSubtitleFileCallback(self, addParam, thread, ret):
        """Callback after downloading subtitle file - adds to proxy queue."""
        asynccall.gMainFunctionsQueueTab[1].addToQueue(
            "subtitleFileDownloaded", [thread, {"add_param": addParam, "ret": ret}]
        )

    def subtitleFileDownloaded(self, params):
        """Handle downloaded subtitle file."""
        printDBG("IPTVSubDownloaderWidget.subtitleFileDownloaded")
        self["statustext"].setText("")
        self["list"].show()
        ret = params["ret"]

        if ret.status != RetHost.OK or 1 != len(ret.value):
            disMessage = _("Download subtiles failed.") + "\n"
            if ret.message and ret.message != "":
                disMessage += ret.message
            lastErrorMsg = GetIPTVPlayerLastHostError()
            if lastErrorMsg != "":
                disMessage += "\n" + _('Last error: "%s"') % lastErrorMsg
            self.session.open(MessageBox, disMessage, type=MessageBox.TYPE_ERROR)
        else:
            # Subtitle downloaded, ask to finish
            ret = ret.value[0]
            self.downloadedSubItems.append(ret)
            message = _('Subtitles "%s" downloaded correctly.') % ret.path
            message += "\n" + _("Do you want to finish?")
            self.session.openWithCallback(
                self.askFinishCallback,
                MessageBox,
                text=message,
                type=MessageBox.TYPE_YESNO,
            )

    def askFinishCallback(self, ret):
        """Callback after asking user if they want to finish."""
        try:
            if ret:
                item = self.downloadedSubItems[-1]
                track = {
                    "title": item.name,
                    "lang": item.lang,
                    "path": item.path,
                    "id": item.imdbid,
                }
                self.close(track)
        except Exception:
            printExc()

    def reloadList(self, params):
        """Reload the list with results from subtitle provider."""
        printDBG("IPTVSubDownloaderWidget.reloadList")
        refresh = params["add_param"].get("refresh", 0)
        selIndex = params["add_param"].get("selIndex", 0)
        ret = params["ret"]
        printDBG(
            "IPTVSubDownloaderWidget.reloadList refresh[%s], selIndex[%s]"
            % (refresh, selIndex)
        )
        if 0 < refresh and 0 < selIndex:
            self.nextSelIndex = selIndex

        if ret.status != RetHost.OK:
            printDBG("++++++++++++++++++++++ reloadList ret.status = %s" % ret.status)

        self.currList = ret.value
        self["list"].setList([(x,) for x in self.currList])

        self["headertext"].setText(self.getCategoryPath())
        if len(self.currList) <= 0:
            disMessage = _("No item to display. \nPress OK to refresh.\n")
            if ret.message and ret.message != "":
                disMessage += ret.message
            lastErrorMsg = GetIPTVPlayerLastHostError()
            if lastErrorMsg != "":
                disMessage += "\n" + _('Last error: "%s"') % lastErrorMsg
            disMessage += "\n\n" + _("Simplify the title and try again.")

            self["statustext"].setText(disMessage)
            self["list"].hide()
        else:
            # Restore previous selection
            if len(self.currList) > self.nextSelIndex:
                self["list"].moveToIndex(self.nextSelIndex)
            self.changeBottomPanel()

            self["statustext"].setText("")
            self["list"].show()

    def listSubtitlesProviders(self):
        """
        List all available subtitle providers.

        Orders providers based on default language and available URL parameters.
        """
        printDBG("IPTVSubDownloaderWidget.listSubtitlesProviders")
        subProvidersList = []
        napisy24pl = {"title": "Napisy24.pl", "sub_provider": "napisy24pl"}
        openSubtitles = {
            "title": "OpenSubtitles.org API",
            "sub_provider": "opensubtitlesorg",
        }
        openSubtitles2 = {
            "title": "OpenSubtitles.org WWW",
            "sub_provider": "opensubtitlesorg2",
        }
        openSubtitles3 = {
            "title": "OpenSubtitles.org REST",
            "sub_provider": "opensubtitlesorg3",
        }
        napiprojektpl = {"title": "Napiprojekt.pl", "sub_provider": "napiprojektpl"}
        podnapisinet = {"title": "Podnapisi.net", "sub_provider": "podnapisinet"}
        titlovi = {"title": "Titlovi.com", "sub_provider": "titlovicom"}
        subscene = {"title": "Subscene.com", "sub_provider": "subscenecom"}
        youtube = {"title": "Youtube.com", "sub_provider": "youtubecom"}
        popcornsubtitles = {
            "title": "PopcornSubtitles.com",
            "sub_provider": "popcornsubtitles",
        }
        subtitlesgr = {"title": "Subtitles.gr", "sub_provider": "subtitlesgr"}
        prijevodi = {"title": "Prijevodi-Online.org", "sub_provider": "prijevodi"}
        subsro = {"title": "Subs.ro", "sub_provider": "subsro"}
        subsourceapi = {"title": "SubsourceAPI", "sub_provider": "subsourceapi"}
        subdlapi = {"title": "SubDLAPI", "sub_provider": "subdlapi"}

        defaultLang = GetDefaultLang()

        if (
            "youtube_id" in self.params["url_params"]
            and "" != self.params["url_params"]["youtube_id"]
        ):
            subProvidersList.append(youtube)

        if (
            "popcornsubtitles_url" in self.params["url_params"]
            and "" != self.params["url_params"]["popcornsubtitles_url"]
        ):
            subProvidersList.append(popcornsubtitles)

        if "hr" == defaultLang:
            subProvidersList.append(prijevodi)

        if "el" == defaultLang:
            subProvidersList.append(subtitlesgr)

        if "ro" == defaultLang:
            subProvidersList.append(subsro)

        if "pl" == defaultLang:
            subProvidersList.append(napisy24pl)
            if IsSubtitlesParserExtensionCanBeUsed():
                subProvidersList.append(napiprojektpl)

        subProvidersList.append(subsourceapi)
        subProvidersList.append(subdlapi)
        subProvidersList.append(openSubtitles2)
        subProvidersList.append(openSubtitles3)
        subProvidersList.append(openSubtitles)
        subProvidersList.append(podnapisinet)
        subProvidersList.append(titlovi)
        subProvidersList.append(subscene)

        if "pl" != defaultLang:
            subProvidersList.append(napisy24pl)
            if IsSubtitlesParserExtensionCanBeUsed():
                subProvidersList.append(napiprojektpl)

        if "el" != defaultLang:
            subProvidersList.append(subtitlesgr)

        if "hr" != defaultLang:
            subProvidersList.append(prijevodi)

        if "ro" != defaultLang:
            subProvidersList.append(subsro)

        self.currList = []
        for item in subProvidersList:
            params = CDisplayListItem(
                item["title"], item.get("desc", ""), CDisplayListItem.TYPE_SUB_PROVIDER
            )
            params.privateData = {"sub_provider": item["sub_provider"]}
            self.currList.append(params)

        idx = 0
        selIndex = 0
        for idx in range(len(self.currList)):
            if self.hostName == self.currList[idx].privateData["sub_provider"]:
                selIndex = idx
                break

        self["list"].setList([(x,) for x in self.currList])
        # Restore previous selection
        if len(self.currList) > selIndex:
            self["list"].moveToIndex(selIndex)
        self.changeBottomPanel()
        self["headertext"].setText(self.getCategoryPath())
        self["statustext"].setText("")
        self["list"].show()

    def changeBottomPanel(self):
        """
        Update the bottom console text based on current selection.

        Shows description of selected item or search information
        using the user-confirmed movie title.
        """
        selItem = self.getSelItem()
        if selItem and selItem.description != "":
            data = selItem.description
            sData = data.replace("\n", "")
            sData = data.replace("[/br]", "\n")
            self["console"].setText(sData)
        else:
            # Use the user-confirmed movie title in the display
            self["console"].setText(
                _('Searching subtitles for "%s"') % self.movieTitle
            )

    def onSelectionChanged(self):
        """Update bottom panel when list selection changes."""
        self.changeBottomPanel()

    def isInWorkThread(self):
        """Check if work thread is currently active."""
        return None is not self.workThread and (
            not self.workThread.isFinished() or self.workThread.isAlive()
        )

    def getSelItem(self):
        """Get the currently selected item from the list."""
        currSelIndex = self["list"].getCurrentIndex()
        if len(self.currList) <= currSelIndex:
            printDBG(
                "ERROR: getSelItem there is no item with index: %d, listOfItems.len: %d"
                % (currSelIndex, len(self.currList))
            )
            return None
        return self.currList[currSelIndex]

    def hideWindow(self):
        """Hide the widget window."""
        self.visible = False
        self.hide()

    def showWindow(self):
        """Show the widget window."""
        self.visible = True
        self.show()

    def discoverInfoFromTitle(self, movieTitle=None):
        """
        Discover season and episode information from movie title.

        Args:
            movieTitle: Title to analyze, uses confirmed title if not provided

        Returns:
            Dictionary with movie_title, season and episode keys
        """
        dInfo = {"movie_title": None, "season": None, "episode": None}
        if movieTitle is None:
            movieTitle = self.params.get("movie_title", "")

        dInfo["movie_title"] = CParsingHelper.getNormalizeStr(movieTitle)
        # Try to guess season and episode number using SxxExx pattern
        try:
            tmp = CParsingHelper.getSearchGroups(
                " " + dInfo["movie_title"] + " ", RE_SEASON_EPISODE_SE, 2
            )
            dInfo.update({"season": int(tmp[0]), "episode": int(tmp[1])})
        except Exception:
            try:
                tmp = CParsingHelper.getSearchGroups(
                    " " + dInfo["movie_title"] + " ", RE_SEASON_EPISODE_X, 2
                )
                dInfo.update({"season": int(tmp[0]), "episode": int(tmp[1])})
            except Exception:
                pass
        return dInfo
