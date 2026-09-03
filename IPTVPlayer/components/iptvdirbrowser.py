# -*- coding: utf-8 -*-
#
#  Directory selector
#
#  $Id$
#
#
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.iptvlist import IPTVMainNavigatorList
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, mkdir, IsValidFileName, eConnectCallback, GetNice, E2PrioFix
from Plugins.Extensions.IPTVPlayer.components.e2ivkselector import GetVirtualKeyboard
from Plugins.Extensions.IPTVPlayer.components import skinchrome
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
###################################################
# FOREIGN import
###################################################
from enigma import eConsoleAppContainer

from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.Label import Label
from Components.ActionMap import ActionMap
from Components.Sources.StaticText import StaticText
from Tools.BoundFunction import boundFunction
from os import path as os_path
###################################################


class CListItem:
    def __init__(self, name='', fullDir='', type='dir'):
        self.type = type
        self.name = name
        self.fullDir = fullDir
        self.imageType = type

    def getDisplayTitle(self):
        return self.name

    def getTextColor(self):
        return None


class IPTVDirBrowserList(IPTVMainNavigatorList):
    def __init__(self):
        self.ICONS_FILESNAMES = {'dir': 'CategoryItem.png', 'file': 'ArticleItem.png'}
        IPTVMainNavigatorList.__init__(self)


def _buildBrowserSkin(screenName, colorKeys):
    # shared by IPTVDirectorySelectorWidget and IPTVFileSelectorWidget
    # below - the two screens are visually near-identical, only the
    # footer's color keys differ. Module-level, not a method -
    # __prepareSkin() on each class still has to stay its own
    # name-mangled method (see each class's own __init__ comment for
    # why), this is just the part they both call into.
    #
    # Uses the shared skinchrome.build_header() with a real bound
    # source="Title" widget, so self.setTitle() (already called in
    # layoutFinished(), title already translated to e.g. "Wähle das
    # Verzeichnis"/"Wähle Datei aus" via locale/de) actually shows.
    # "curr_dir" (the current path) is its own full-width row directly
    # below the header/divider (position/spacing matches the equivalent
    # row in iptvfavouriteswidgets.py's own skin), with the list + footer
    # shifted down by that row's height (34px) so the list keeps its full
    # 528px/~16-row capacity.
    iconBase = skinchrome.getIconBase()
    return """
    <screen name="%s" position="center,center" size="840,714" resolution="1280,720" title="" backgroundColor="#34111112" flags="wfNoBorder">
        %s
        <widget name="curr_dir" position="20,68" size="800,30" foregroundColor="white" backgroundColor="black" borderWidth="1" borderColor="black" transparent="1" zPosition="1" font="Regular;20" valign="center" halign="left" />
        <widget name="list" position="20,110" zPosition="2" size="800,528" itemHeight="32" font="Regular;20" scrollbarMode="showOnDemand" scrollbarSliderBorderWidth="1" scrollbarForegroundColor="#1b5a91" scrollbarBorderColor="#00b6b6b6" enableWrapAround="1" transparent="1" foregroundColor="white" backgroundColor="black" foregroundColorSelected="white" backgroundColorSelected="#1b5a91" borderWidth="1" borderColor="black" />
        %s
    </screen>
    """ % (
        screenName,
        skinchrome.build_header(scale=1.0, iconBase=iconBase),
        skinchrome.build_footer(714, scale=1.0, iconBase=iconBase, keys=colorKeys, showMenu=False, showNav=False, showOk=True, showExit=True),
    )


class IPTVDirectorySelectorWidget(Screen):
    # iconBase is computed per-instance via skinchrome.getIconBase(), not
    # cached at class/module level, so it always reflects the real
    # resolution. Footer (OK/EXIT icons, red/green/blue color keys) uses
    # skinchrome.build_footer() - see _buildBrowserSkin() above for the
    # actual skin string, shared with IPTVFileSelectorWidget below.
    def __prepareSkin(self):
        return _buildBrowserSkin("IPTVDirectorySelectorWidget", ('red', 'green', 'blue'))

    def __init__(self, session, currDir, title="Directory browser"):
        printDBG("IPTVDirectorySelectorWidget.__init__ -------------------------------")
        # only for this exact class - IPTVFileSelectorWidget (subclass,
        # own smaller footer: just "red") sets self.skin itself before
        # calling this __init__, and __prepareSkin() name-mangles to
        # this class's own version regardless of self's real type, so
        # setting it unconditionally here would silently clobber the
        # subclass's already-assigned skin
        if type(self) is IPTVDirectorySelectorWidget:
            self.skin = self.__prepareSkin()
        Screen.__init__(self, session)
        self.skinName = skinchrome.forceInternalSkinName(["IPTVDirectorySelectorScreen", "IPTVDirectorySelectorWidget"])
        if type(self) is IPTVDirectorySelectorWidget:
            self["key_red"] = StaticText(_("Cancel"))
            # self["key_yellow"] = StaticText(_("Odśwież"))
            self["key_blue"] = StaticText(_("New dir"))
            self["key_green"] = StaticText(_("Apply"))
            self["curr_dir"] = Label()
            self["list"] = IPTVDirBrowserList()
            self["FilelistActions"] = ActionMap(["ColorActions", "SetupActions"],
                {
                    "red": self.requestCancel,
                    "green": self.requestApply,
                    "yellow": self.requestRefresh,
                    "blue": self.requestNewDir,
                    "ok": self.requestOk,
                    "cancel": self.requestBack
                })

        self.title = title
        self.onLayoutFinish.append(self.layoutFinished)
        self.onClose.append(self.__onClose)

        self.console = eConsoleAppContainer()
        self.console_appClosed_conn = eConnectCallback(self.console.appClosed, self.refreshFinished)
        self.console_stderrAvail_conn = eConnectCallback(self.console.stderrAvail, self.refreshNewData)
        self.underRefreshing = False
        self.underClosing = False
        self.deferredAction = None

        try:
            while not os_path.isdir(currDir):
                tmp = os_path.dirname(currDir)
                if tmp == currDir:
                    break
                currDir = tmp
        except Exception:
            currDir = ''
            printExc()

        self.currDir = currDir
        self.currList = []

        self.tmpData = ''
        self.tmpList = []

    def __del__(self):
        printDBG("IPTVDirectorySelectorWidget.__del__ -------------------------------")

    def __onClose(self):
        printDBG("IPTVDirectorySelectorWidget.__onClose -----------------------------")
        if None is not self.console:
            self.console_appClosed_conn = None
            self.console_stderrAvail_conn = None
            self.console_stdoutAvail_conn = None
            self.console.sendCtrlC()
            self.console = None

        self.onClose.remove(self.__onClose)
        self.onLayoutFinish.remove(self.layoutFinished)

    def _iptvDoClose(self, ret=None):
        if self.console:
            self.console.sendCtrlC()
        self.close(ret)

    def _getSelItem(self):
        currSelIndex = self["list"].getCurrentIndex()
        if len(self.currList) <= currSelIndex:
            return None
        return self.currList[currSelIndex]

    def prepareCmd(self):
        cmd = '%s "%s" dl d' % ("/usr/bin/lsdir", self.currDir)
        return cmd

    def doAction(self, action):
        if not self.underRefreshing:
            action()
        else:
            self.deferredAction = action
            self.console.sendCtrlC()

    def layoutFinished(self):
        printDBG("IPTVDirectorySelectorWidget.layoutFinished -------------------------------")
        self.setTitle(_(self.title))
        self.currDirChanged()

    def currDirChanged(self):
        printDBG("IPTVDirectorySelectorWidget.currDirChanged")
        self.currDir = self.getCurrentDirectory()
        self["curr_dir"].setText(_(self.currDir))
        self["list"].setList([])
        self.requestRefresh()

    def getCurrentDirectory(self):
        if self.currDir and os_path.isdir(self.currDir):
            if '/' != self.currDir[-1]:
                self.currDir += '/'
            return self.currDir
        else:
            return "/"

    def refreshFinished(self, code):
        printDBG("IPTVDirectorySelectorWidget.refreshFinished")
        self.underRefreshing = False
        if None is not self.deferredAction:
            deferredAction = self.deferredAction
            self.deferredAction = None
            deferredAction()
        else:
            printDBG("IPTVDirectorySelectorWidget.refreshFinished fill list")
            # sort list and set
            self.currList = []
            self.tmpList.sort(key=lambda x: x.name.lower())
            self.currList = self.tmpList
            if ('/' != self.currDir):
                self.currList.insert(0, CListItem(name='..', fullDir='', type='dir'))  # add back item
            self["list"].setList([(x,) for x in self.currList])
            self.tmpList = []
            self.tmpData = ''

    def refreshNewData(self, data):
        self.tmpData += ensure_str(data)
        newItems = self.tmpData.split('\n')
        if self.tmpData.endswith('\n'):
            self.tmpData = ''
        else:
            self.tmpData = newItems[-1]
            del newItems[-1]
        self.doRefreshNewData(newItems)

    def doRefreshNewData(self, newItems):
        for item in newItems:
            params = item.split('//')
            if item.startswith('.'):
                continue  # do not list hidden items
            # printDBG(params)
            if 4 == len(params):
                # if '0' == params[2]: type = 'dir'
                # else: type = 'linkdir'
                self.tmpList.append(CListItem(name=params[0], fullDir=params[3], type='dir'))

    def requestApply(self):
        if self.underClosing:
            return
        self.doAction(boundFunction(self._iptvDoClose, self.getCurrentDirectory()))

    def requestCancel(self):
        printDBG(">>>REQUEST CANCEL<<<")
        try:
            running = self.console.running()
        except Exception:
            running = True
        if not self.console or not running:
            self._iptvDoClose(None)
        else:
            self.doAction(boundFunction(self._iptvDoClose, None))

    def requestRefresh(self):
        if self.underClosing:
            return
        if self.underRefreshing:
            return
        self.underRefreshing = True
        self.tmpList = []
        self.tmpData = ''
        cmd = self.prepareCmd()
        printDBG("IPTVDirectorySelectorWidget.requestRefresh cmd[%s]" % cmd)
        if hasattr(self.console, "setNice"):
            self.console.setNice(GetNice() + 2)
            self.console.execute(cmd)
        else:
            self.console.execute(E2PrioFix(cmd))

    def requestNewDir(self):
        if self.underClosing:
            return
        self.doAction(self.newDir)

    def requestOk(self):
        if self.underClosing:
            return
        self.doAction(self.ok)

    def requestBack(self):
        if self.underClosing:
            return
        self.doAction(self.back)

    def ok(self):
        item = self._getSelItem()
        if None is item or '' == item.name:
            return
        fullDirName = os_path.join(self.currDir, item.name)
        if '..' == item.name:
            return self.back()
        if os_path.isdir(fullDirName):
            self.currDir = fullDirName
            self.currDirChanged()

    def back(self):
        if '/' == self.currDir:
            self._iptvDoClose(None)
        else:
            self.currDir = self.currDir[:self.currDir[:-1].rfind('/')]
            self.currDirChanged()

    def newDir(self):
        self.session.openWithCallback(self.enterPatternCallBack, GetVirtualKeyboard(), title=(_("Enter name")), text="")

    def enterPatternCallBack(self, newDirName=None):
        if None is not self.currDir and newDirName is not None:
            sts = False
            if IsValidFileName(newDirName):
                try:
                    sts, msg = mkdir(os_path.join(self.currDir, newDirName))
                except Exception:
                    sts, msg = False, _("Exception occurs")
            else:
                msg = _("Invalid name.")
            if sts:
                self.requestRefresh()
            else:
                self.session.open(MessageBox, msg, type=MessageBox.TYPE_INFO, timeout=5)


class IPTVFileSelectorWidget(IPTVDirectorySelectorWidget):
    def __prepareSkin(self):
        return _buildBrowserSkin("IPTVFileSelectorWidget", ('red',))

    def __init__(self, session, currDir, title="File browser", fileMatch=None):
        printDBG("IPTVFileSelectorWidget.__init__ -------------------------------")
        self.skin = self.__prepareSkin()
        IPTVDirectorySelectorWidget.__init__(self, session, currDir, title)

        if type(self) is IPTVFileSelectorWidget:
            self["key_red"] = StaticText(_("Cancel"))
            self["curr_dir"] = Label()
            self["list"] = IPTVDirBrowserList()
            self["FilelistActions"] = ActionMap(["ColorActions", "SetupActions"],
                {
                    "red": self.requestCancel,
                    "yellow": self.requestRefresh,
                    "ok": self.requestOk,
                    "cancel": self.requestBack
                })
        self.fileMatch = fileMatch

    def prepareCmd(self):
        cmd = '%s "%s" drl dr' % ("/usr/bin/lsdir", self.currDir)
        return cmd

    def doRefreshNewData(self, newItems):
        for item in newItems:
            params = item.split('//')
            if item.startswith('.'):
                continue  # do not list hidden items
            # printDBG(params)
            if 4 == len(params):
                if 'd' == params[1]:
                    type = 'dir'
                else:
                    type = 'file'
                    try:
                        if None is not self.fileMatch and None is self.fileMatch.match(params[0]):
                            continue
                    except Exception:
                        printExc()
                        continue
                self.tmpList.append(CListItem(name=params[0], fullDir=params[3], type=type))

    def ok(self):
        item = self._getSelItem()
        if None is item or '' == item.name:
            return
        fullPath = os_path.join(self.currDir, item.name)
        if item.type == 'dir':
            if '..' == item.name:
                return self.back()
            if os_path.isdir(fullPath):
                self.currDir = fullPath
                self.currDirChanged()
        elif item.type == 'file':
            self.requestApply(fullPath)

    def requestApply(self, fullPath):
        if self.underClosing:
            return
        self.doAction(boundFunction(self._iptvDoClose, fullPath))
