# -*- coding: utf-8 -*-
# Last Modified: 2026-07-26 - Updated to resolve renamed video files (.mp4 -> .mkv and similar) for play/remove actions, extend archive video detection, ignore non-subtitle sidecar text files,  and delete related sidecar files with immediate list refresh on remove. - Kamikaze24
#
#  IPTV download manager UI
#
#  $Id$
#
#
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, eConnectCallback, GetIconDir, GetNice, formatBytes, E2PrioFix
from Plugins.Extensions.IPTVPlayer.components.iptvplayer import IPTVStandardMoviePlayer, IPTVMiniMoviePlayer
from Plugins.Extensions.IPTVPlayer.components.iptvextmovieplayer import IPTVExtMoviePlayer
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import GetMoviePlayer
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _

from Plugins.Extensions.IPTVPlayer.components.e2ivkselector import GetVirtualKeyboard

from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper, DMItemBase
from Plugins.Extensions.IPTVPlayer.components import skinchrome
from Plugins.Extensions.IPTVPlayer.components.iptvchoicebox import IPTVChoiceBoxWidget, IPTVChoiceBoxItem, openChoiceBox
from Plugins.Extensions.IPTVPlayer.components.iptvlist import IPTVDMActionChoiceBoxList
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
###################################################
# FOREIGN import
###################################################
from Screens.Screen import Screen
from enigma import eTimer, eConsoleAppContainer
from Components.config import config
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.Sources.List import List
from Components.Sources.StaticText import StaticText
from Tools.LoadPixmap import LoadPixmap

from datetime import timedelta
from Screens.MessageBox import MessageBox
from os import path as os_path, remove as os_remove, rename as os_rename
from glob import glob
from re import match as re_match
###################################################

#########################################################
#                    GLOBALS
#########################################################
gIPTVDM_listChanged = False


class IPTVDMWidget(Screen):

    VIDEO_FILE_EXTENSIONS = ('.flv', '.mp4', '.mkv', '.avi', '.mov', '.ts', '.m2ts', '.wmv', '.mpeg', '.mpg', '.m4v', '.webm')
    ICONS_FILESNAMES = {DMHelper.STS.WAITING: 'iconwait1.png',
                        DMHelper.STS.DOWNLOADING: 'iconwait2.png',
                        DMHelper.STS.DOWNLOADED: 'icondone.png',
                        DMHelper.STS.INTERRUPTED: 'iconerror.png',
                        DMHelper.STS.ERROR: 'iconwarning.png',
                        }

    # Header/footer use skinchrome.build_header_auto()/build_footer_auto() -
    # this screen already declares `resolution="1280,720"` and uses plain
    # HD-reference pixel values throughout, exactly the shape those are
    # for (no fixed-pixel grid content fighting the auto-scale, unlike
    # PlayerSelectorWidget). "titel" (the "Manager status: STARTED/STOPPED"
    # label) sits in the header's top-right corner with zPosition="2" so
    # it paints above the header's own much-wider Title label background -
    # same convention as iptvplayerwidget.py/iptvfavouriteswidgets.py/
    # playerselector.py's own headers.
    def __prepareSkin(self):
        iconBase = skinchrome.getIconBase()
        return """
        <screen name="IPTVDMWidget" position="center,center" title="%s" size="1180,696" resolution="1280,720" flags="wfNoBorder">
            %s
            <widget name="titel" position="800,10" size="370,40" foregroundColor="white" backgroundColor="black" borderWidth="1" borderColor="black" transparent="1" zPosition="2" font="Regular;24" valign="center" />
            <widget source="downloadlist" render="Listbox" position="10,66" zPosition="2" size="1160,560" scrollbarMode="showOnDemand" scrollbarSliderBorderWidth="1" scrollbarForegroundColor="#1b5a91" scrollbarBorderColor="#00b6b6b6" transparent="1" foregroundColor="white" backgroundColor="black" foregroundColorSelected="white" backgroundColorSelected="#1b5a91" shadowColor="black" shadowOffset="-2,-2" enableWrapAround="1">
                <convert type="TemplatedMultiContent">
                {"template": [
                    MultiContentEntryPixmapAlphaBlend(pos = (10, 10), size = (42, 42), flags = BT_SCALE, png = 0),  # Flag.
                    MultiContentEntryText(pos = (80, 0), size = (1140, 32), font = 0, flags = RT_HALIGN_LEFT | RT_VALIGN_CENTER, text = 1),  # title
                    MultiContentEntryText(pos = (80, 32), size = (500, 26), font = 1, color=0xa4c400,color_sel=0xffaf17, flags = RT_HALIGN_LEFT | RT_VALIGN_CENTER, text = 3),  # size
                    MultiContentEntryText(pos = (820, 32), size = (300, 26), font = 1, color=0x7e93ae,color_sel=0x19f4eb, flags = RT_HALIGN_RIGHT | RT_VALIGN_CENTER, text = 4),  # status
                    ],
                    "fonts": [gFont("Regular",22), gFont("Regular",18)],
                    "itemHeight": 56
                }
                </convert>
             </widget>
            %s
        </screen>""" % (
            _("%s download manager") % "E2iPlayer",
            skinchrome.build_header_auto(iconBase=iconBase),
            # RED (Stop) + GREEN (Start) merged into one alternating
            # GREEN toggle, YELLOW (Archive) + BLUE (Downloads) merged
            # into one alternating YELLOW toggle - see
            # green_pressed()/yellow_pressed() below. RED/BLUE are free.
            skinchrome.build_footer_auto(696, iconBase=iconBase, keys=('green', 'yellow'), showNav=False),
        )

    def __init__(self, session, downloadmanager):
        self.session = session
        self.skin = self.__prepareSkin()
        Screen.__init__(self, session, mandatoryWidgets=["downloadlist"])
        self.skinName = skinchrome.forceInternalSkinName(["IPTVDMScreen", "IPTVDMWidget"])

        self.currentService = self.session.nav.getCurrentlyPlayingServiceReference()
        self.session.nav.event.append(self.__event)

        # key_green's real initial text comes from setManagerStatus() below
        # (reads self.DM.isRunning()); key_yellow starts as "Archive" -
        # self.localMode always starts False, matching _updateYellowLabel()'s
        # own condition, see green_pressed()/yellow_pressed() for the toggle.
        self["key_green"] = StaticText(_("Start"))
        self["key_yellow"] = StaticText(_("Archive"))

        self["downloadlist"] = List()
        # self["list"] = IPTVDownloadManagerList()
        # self["list"].connectSelChanged(self.onSelectionChanged)
        self["actions"] = ActionMap(["WizardActions", "DirectionActions", "ColorActions"],
        {
            "ok": self.ok_pressed,
            "back": self.back_pressed,
            "green": self.green_pressed,
            "yellow": self.yellow_pressed,

        }, -1)

        self["titel"] = Label()

        self.dictPIX = {}
        for key in self.ICONS_FILESNAMES.keys():
            try:
                pixFile = self.ICONS_FILESNAMES.get(key, None)
                if pixFile:
                    self.dictPIX[key] = LoadPixmap(cached=True, path=GetIconDir(pixFile))
            except Exception:
                printExc()

        self.DM = downloadmanager
        self.DM.connectListChanged(self.onListChanged)
        self.DM.setUpdateProgress(True)
        self.setManagerStatus()

        self.started = 0
        global gIPTVDM_listChanged
        gIPTVDM_listChanged = True

        self.onClose.append(self.__onClose)
        self.onShow.append(self.onStart)

        # main Timer to refresh liar
        self.mainTimer = eTimer()
        self.mainTimer_conn = eConnectCallback(self.mainTimer.timeout, self.reloadList)
        # every 500ms Proxy Queue will be checked
        self.mainTimer.start(500)

        self.localMode = False
        self.localFiles = []
        self.console = eConsoleAppContainer()
        self.console_appClosed_conn = eConnectCallback(self.console.appClosed, self.refreshFinished)
        self.console_stderrAvail_conn = eConnectCallback(self.console.stderrAvail, self.refreshNewData)
        self.underRefreshing = False

        self.iptvclosing = False
        self.currList = []

    # end def __init__(self, session):

    def refreshFinished(self, code):
        printDBG("IPTVDMWidget.refreshFinished")
        if self.iptvclosing:
            return
        self.localFiles = []
        self.tmpList.sort(key=lambda x: x.fileName.lower())
        self.localFiles = self.tmpList
        self.tmpList = []
        self.tmpData = ''
        self.underRefreshing = False
        self.reloadList(True)

    def refreshNewData(self, data):
        printDBG("IPTVDMWidget.refreshNewData")
        if self.iptvclosing:
            return
        self.tmpData += ensure_str(data)
        newFiles = self.tmpData.split('\n')
        if not self.tmpData.endswith('\n'):
            self.tmpData = newFiles[-1]
            del newFiles[-1]
        else:
            self.tmpData = ''

        for item in newFiles:
            params = item.split('//')
            if 4 > len(params):
                continue
            if item.startswith('.'):
                continue  # do not list hidden items

            fileName = self._getArchiveFilePath(params[0])
            if not fileName:
                continue

            skip = False
            for item2 in self.currList:
                item2FileName = self._getExistingFilePath(item2.fileName)
                printDBG("AAA:[%s]\nBBB:[%s]" % (item2FileName, fileName))
                if fileName == item2FileName:
                    skip = True
                    break
            if skip:
                continue

            listItem = DMItemBase(url=fileName, fileName=fileName)
            try:
                listItem.downloadedSize = os_path.getsize(fileName)
            except Exception:
                listItem.downloadedSize = 0
            listItem.status = DMHelper.STS.DOWNLOADED
            listItem.downloadIdx = -1
            self.tmpList.append(listItem)

    def _getArchiveFilePath(self, fileName):
        fileName = ensure_str(fileName).strip()
        if fileName.startswith('.'):
            return None

        fullPath = os_path.join(config.plugins.iptvplayer.NaszaSciezka.value, fileName)
        if self._isVideoFile(fullPath):
            return fullPath

        baseName, ext = os_path.splitext(fullPath)
        if ext.lower() in self.VIDEO_FILE_EXTENSIONS:
            return None

        for candidate in self._getPossibleVideoFiles(baseName):
            if os_path.exists(candidate):
                printDBG("IPTVDMWidget._getArchiveFilePath substitute [%s] -> [%s]" % (fullPath, candidate))
                return candidate
        return None

    def _isVideoFile(self, fileName):
        return os_path.isfile(fileName) and os_path.splitext(fileName)[1].lower() in self.VIDEO_FILE_EXTENSIONS

    def _getPossibleVideoFiles(self, baseName):
        candidates = []
        for ext in self.VIDEO_FILE_EXTENSIONS:
            candidates.append(baseName + ext)
        return candidates

    def _isSubtitleFile(self, fileName):
        return os_path.splitext(fileName)[1].lower() in ['.srt', '.sub', '.txt', '.vtt']

    def _looksLikeSubtitleFile(self, fileName):
        try:
            sts, reason = self._detectSubtitleFile(fileName)
            return sts
        except Exception:
            printExc()
        return False

    def _detectSubtitleFile(self, fileName):
        if not os_path.isfile(fileName):
            return False, 'missing file'

        ext = os_path.splitext(fileName)[1].lower()
        if ext not in ['.srt', '.sub', '.txt', '.vtt']:
            return False, 'unsupported extension'

        try:
            with open(fileName, 'rb') as f:
                data = f.read(8192)
        except Exception:
            printExc()
            return False, 'read error'

        if not data:
            return False, 'empty file'

        try:
            text = ensure_str(data)
        except Exception:
            try:
                text = data.decode('utf-8', 'ignore')
            except Exception:
                printExc()
                return False, 'decode error'

        lines = [line.strip() for line in text.replace('\r', '\n').split('\n') if line.strip()]
        if not lines:
            return False, 'no text lines'

        score = 0
        for line in lines[:40]:
            if '-->' in line:
                score += 3
            elif re_match(r'^\d+$', line):
                score += 1
            elif re_match(r'^\d{2}:\d{2}:\d{2}[,.]\d{1,3}', line):
                score += 2
            elif re_match(r'^\{\d+\}\{\d*\}', line):
                score += 3
            elif ext == '.vtt' and line.upper().startswith('WEBVTT'):
                score += 3

        if score >= 3:
            return True, 'subtitle markers detected'
        return False, 'no subtitle markers detected'

    def _removeRelatedFiles(self, fileName):
        removed = False
        baseName = os_path.splitext(fileName)[0]
        candidates = [fileName]
        for ext in ['.mp4', '.mkv', '.flv', '.avi', '.ts', '.mov', '.wmv', '.txt', '.jpg', '.jpeg']:
            candidate = baseName + ext
            if candidate not in candidates:
                candidates.append(candidate)
        for candidate in candidates:
            try:
                if os_path.exists(candidate):
                    os_remove(candidate)
                    removed = True
                    printDBG('IPTVDMWidget._removeRelatedFiles removed [%s]' % candidate)
            except Exception:
                printExc()
        return removed

    def _renameRelatedSidecarFiles(self, oldFileName, newFileName):
        oldBase = os_path.splitext(oldFileName)[0]
        newBase = os_path.splitext(newFileName)[0]
        if oldBase == newBase:
            return
        for ext in ['.txt', '.jpg', '.jpeg']:
            oldSidecar = oldBase + ext
            newSidecar = newBase + ext
            try:
                if not os_path.isfile(oldSidecar):
                    continue
                if os_path.isfile(newSidecar) or os_path.islink(newSidecar):
                    printDBG('IPTVDMWidget._renameRelatedSidecarFiles skip, target exists [%s]' % newSidecar)
                    continue
                os_rename(oldSidecar, newSidecar)
                printDBG('IPTVDMWidget._renameRelatedSidecarFiles renamed [%s] -> [%s]' % (oldSidecar, newSidecar))
            except Exception:
                printExc()

    def _getSidecarSubtitles(self, fileName):
        subtitles = []
        baseName = os_path.splitext(fileName)[0]
        for ext in ['.srt', '.sub', '.txt', '.vtt']:
            candidate = baseName + ext
            if not os_path.isfile(candidate):
                continue
            if self._looksLikeSubtitleFile(candidate):
                subtitles.append(candidate)
            else:
                printDBG('IPTVDMWidget._getSidecarSubtitles skip non subtitle file [%s]' % candidate)
        return subtitles

    def _getExistingFilePath(self, fileName):
        fileName = ensure_str(fileName).replace('//', '/')
        if self._isVideoFile(fileName):
            return fileName

        baseName, ext = os_path.splitext(fileName)
        if ext.lower() in self.VIDEO_FILE_EXTENSIONS:
            for candidate in self._getPossibleVideoFiles(baseName):
                if os_path.exists(candidate):
                    printDBG("IPTVDMWidget._getExistingFilePath substitute [%s] -> [%s]" % (fileName, candidate))
                    return candidate

        try:
            matches = glob(baseName + '.*')
            for candidate in matches:
                if self._isVideoFile(candidate):
                    printDBG("IPTVDMWidget._getExistingFilePath glob substitute [%s] -> [%s]" % (fileName, candidate))
                    return candidate
        except Exception:
            printExc()
        return fileName

    def leaveMoviePlayer(self, answer=None, position=None, *args, **kwargs):
        self.DM.setUpdateProgress(True)
        self.session.nav.playService(self.currentService)
        return

    def setManagerStatus(self):
        status = _("Manager status:") + " "
        # key_green's label mirrors the same isRunning() check this
        # already makes for the title - describes the action pressing it
        # performs, same "what will happen" convention as e.g.
        # ConfigHostsMenu's reordering toggle.
        if self.DM.isRunning():
            self["titel"].setText(status + _("STARTED"))
            self["key_green"].setText(_("Stop"))
        else:
            self["titel"].setText(status + _("STOPPED"))
            self["key_green"].setText(_("Start"))

    def onListChanged(self):
        global gIPTVDM_listChanged
        gIPTVDM_listChanged = True
        return

    def __del__(self):
        printDBG("IPTVDMWidget.__del__ ---------------------------------------")

    def __onClose(self):
        # unsubscribe callback functions and break cycles references
        self.iptvclosing = True
        if None is not self.console:
            self.console_appClosed_conn = None
            self.console_stderrAvail_conn = None
            self.console_stdoutAvail_conn = None
            self.console.sendCtrlC()
            self.console = None
        self.DM.disconnectListChanged(self.onListChanged)
        self.DM.setUpdateProgress(False)
        self.DM = None
        try:
            self.mainTimer_conn = None
            self.mainTimer.stop()
            self.mainTimer = None
        except Exception:
            printExc()
        try:
            self.currentService = None
            self.session.nav.event.remove(self.__event)
            # self["list"].disconnectSelChanged(self.onSelectionChanged)

            self.onClose.remove(self.__onClose)
            self.onShow.remove(self.onStart)
        except Exception:
            printExc()

    def green_pressed(self):
        # RED (Stop) + GREEN (Start) merged into one alternating toggle
        # on GREEN, RED freed up entirely.
        if self.DM.isRunning():
            self.DM.stopWorkThread()
        else:
            self.DM.runWorkThread()
        self.setManagerStatus()
        return

    def _updateYellowLabel(self):
        self["key_yellow"].setText(_("Downloads") if self.localMode else _("Archive"))

    def yellow_pressed(self):
        # YELLOW (Archive, switch into local/archive browsing) + BLUE
        # (Downloads, switch back) merged into one alternating toggle on
        # YELLOW, BLUE freed up entirely. Label shows exactly the target
        # view's name, picked at runtime instead of being two separate
        # fixed labels.
        if self.iptvclosing:
            return
        if not self.localMode:
            if not self.underRefreshing:
                self.underRefreshing = True
                self.tmpList = []
                self.tmpData = ''
                cmd = '%s "%s" rl r' % ("/usr/bin/lsdir", config.plugins.iptvplayer.NaszaSciezka.value)
                printDBG("cmd[%s]" % cmd)
                if hasattr(self.console, "setNice"):
                    self.console.setNice(GetNice() + 2)
                    self.console.execute(cmd)
                else:
                    self.console.execute(E2PrioFix(cmd))
            self.localMode = True
        else:
            self.localMode = False
        self._updateYellowLabel()
        self.reloadList(True)
        return

    def onSelectionChanged(self):
        return

    def back_pressed(self):
        if self.console:
            self.console.sendCtrlC()
        self.close()
        return

    def ok_pressed(self):
        if self.iptvclosing:
            return

        # wszystkie dostepne opcje
        play = []
        play.append((_('Play with [%s] player') % GetMoviePlayer(True, False).getText(), 'play', GetMoviePlayer(True, False).value))
        play.append((_('Play with [%s] player') % GetMoviePlayer(True, True).getText(), 'play', GetMoviePlayer(True, True).value))

        cont = ((_('Continue downloading'), 'continue'),)
        retry = ((_('Download again'), 'retry'),)
        stop = ((_('Stop downloading'), 'stop'),)
        remove = ((_('Remove file'), 'remove'),)
        delet = ((_('Remove item'), 'delet'),)
        move = ((_('Promote item'), 'move'),)
        rename = ((_('Rename file'), 'rename'),)  # add lululla 20250911

        options = []
        item = self.getSelItem()
        if item is not None:
            if self.localMode:
                options.extend(play)
                options.extend(remove)
                options.extend(rename)  # add lululla 20250911
            elif DMHelper.STS.DOWNLOADED == item.status:
                options.extend(play)
                options.extend(remove)
                options.extend(rename)  # add lululla 20250911
                options.extend(retry)
            elif DMHelper.STS.INTERRUPTED == item.status:
                options.extend(play)
                # options.extend(cont)
                options.extend(retry)
                options.extend(remove)
            elif DMHelper.STS.DOWNLOADING == item.status:
                options.extend(play)
                options.extend(stop)
            elif DMHelper.STS.WAITING == item.status:
                options.extend(move)
                options.extend(delet)
            elif DMHelper.STS.ERROR == item.status:
                options.extend(retry)
                options.extend(remove)

            # chrome-skinned IPTVChoiceBoxWidget. The tuple-building above
            # is untouched; only converted right before opening, into
            # IPTVChoiceBoxItem(privateData=(action, player)) - `player`
            # is None for every option except the 2 "play" ones, same
            # optional-3rd-tuple-element shape as before, just addressed
            # as privateData[0]/[1] now instead of ret[1]/ret[2].
            choiceItems = [IPTVChoiceBoxItem(name=opt[0], privateData=(opt[1], opt[2] if len(opt) > 2 else None)) for opt in options]
            height = self._getActionListHeight(len(choiceItems))
            # list_class=IPTVDMActionChoiceBoxList shows the matching
            # icon per row instead of plain text, same pattern as the
            # "Select action" popup in iptvplayerwidget.py already uses.
            openChoiceBox(self.session, {'width': 600, 'height': height, 'current_idx': 0, 'title': _("Select action"), 'options': choiceItems, 'list_class': IPTVDMActionChoiceBoxList, 'chrome': True}, self.makeActionOnDownloadItem)

        return

    def _getActionListHeight(self, numItems):
        # same tier-aware height+cap formula as every other IPTVChoiceBoxWidget
        # caller in this codebase (e.g. configbase.py's _getSelectionListHeight()) -
        # floored at 2 since numItems=1 renders an unusably small list at
        # FHD/WQHD, smaller than a single real row.
        numItems = max(numItems, 2)
        itemH, scale = skinchrome.tierRowHeight(35, 40, 55)
        height = int(numItems * itemH / scale) + 176
        return min(height, 660)

    def makeActionOnDownloadItem(self, ret):
        # ret is an IPTVChoiceBoxItem - adapted back into the plain
        # (label, action, player) tuple shape the rest of this method
        # expects, instead of touching every ret[1]/ret[2] reference below
        # (this method doesn't read ret[0]/the label at all, so a
        # placeholder there is fine).
        if ret is not None:
            ret = (None, ret.privateData[0], ret.privateData[1])
        item = self.getSelItem()
        if None is not ret and None is not item:
            playFileName = self._getExistingFilePath(item.fileName)
            printDBG("makeActionOnDownloadItem " + ret[1] + (" for downloadIdx[%d]" % item.downloadIdx))
            if playFileName != item.fileName:
                printDBG("makeActionOnDownloadItem substitute fileName [%s] -> [%s]" % (item.fileName, playFileName))
            if ret[1] == "play":
                title = playFileName
                try:
                    title = os_path.basename(title)
                    title = os_path.splitext(title)[0]
                except Exception:
                    printExc()
                # when we watch we no need update sts
                self.DM.setUpdateProgress(False)
                player = ret[2]
                subtitles = self._getSidecarSubtitles(playFileName)
                if "mini" == player:
                    self.session.openWithCallback(self.leaveMoviePlayer, IPTVMiniMoviePlayer, playFileName, title)
                elif player in ["exteplayer", "extgstplayer"]:
                    additionalParams = {}
                    if playFileName.split('.')[-1] in ['mp3', 'm4a', 'ogg', 'wma', 'fla', 'wav', 'flac']:
                        additionalParams['show_iframe'] = config.plugins.iptvplayer.show_iframe.value
                        additionalParams['iframe_file_start'] = config.plugins.iptvplayer.iframe_file.value
                        additionalParams['iframe_file_end'] = config.plugins.iptvplayer.clear_iframe_file.value
                        additionalParams['iframe_continue'] = False

                    subtitleFile = None
                    if len(subtitles):
                        subtitleFile = subtitles[0]

                    if "exteplayer" == player:
                        self.session.openWithCallback(self.leaveMoviePlayer, IPTVExtMoviePlayer, playFileName, title, subtitleFile, 'eplayer', additionalParams)
                    else:
                        self.session.openWithCallback(self.leaveMoviePlayer, IPTVExtMoviePlayer, playFileName, title, subtitleFile, 'gstplayer', additionalParams)
                else:
                    self.session.openWithCallback(self.leaveMoviePlayer, IPTVStandardMoviePlayer, playFileName, title)
            elif ret[1] == "rename":  # add lululla 20250911
                try:
                    path, fileName = os_path.split(item.fileName)
                    name, ext = os_path.splitext(fileName)
                    caps = {}
                    virtualKeyboard = GetVirtualKeyboard(caps)
                    self.session.openWithCallback(self.renameFileCallback, virtualKeyboard, title=_('Set file name'), text=name)

                except Exception as e:
                    printExc()
                    self.session.open(MessageBox, _("Error getting file name: %s") % str(e), type=MessageBox.TYPE_ERROR)
            elif self.localMode:
                if ret[1] == "remove":
                    try:
                        self._removeRelatedFiles(playFileName)
                        for idx in range(len(self.localFiles)):
                            if playFileName == self.localFiles[idx].fileName or item.fileName == self.localFiles[idx].fileName:
                                del self.localFiles[idx]
                                break
                        self.reloadList(True)
                    except Exception:
                        printExc()
            elif ret[1] == "continue":
                self.DM.continueDownloadItem(item.downloadIdx)
            elif ret[1] == "retry":
                self.DM.retryDownloadItem(item.downloadIdx)
            elif ret[1] == "stop":
                self.DM.stopDownloadItem(item.downloadIdx)
            elif ret[1] == "remove":
                try:
                    self._removeRelatedFiles(playFileName)
                    if playFileName != item.fileName:
                        self._removeRelatedFiles(item.fileName)
                except Exception:
                    printExc()
                self.DM.removeDownloadItem(item.downloadIdx)
            elif ret[1] == "delet":
                self.DM.deleteDownloadItem(item.downloadIdx)
            elif ret[1] == "move":
                self.DM.moveToTopDownloadItem(item.downloadIdx)

    def renameFileCallback(self, callback=None):  # add lululla 20250911
        if callback is None or not callback:
            return

        item = self.getSelItem()
        if item is None:
            return

        try:
            path, fileName = os_path.split(item.fileName)
            name, ext = os_path.splitext(fileName)
            newName = callback.strip()

            if not newName:
                self.session.open(MessageBox, _("File name cannot be empty!"), type=MessageBox.TYPE_ERROR)
                return

            newPath = os_path.join(path, newName + ext)
            printDBG('rename_file new path[%s]' % newPath)

            if os_path.isfile(newPath) or os_path.islink(newPath):
                self.session.open(MessageBox, _('File "%s" already exists!') % newPath, type=MessageBox.TYPE_ERROR)
                return

            os_rename(item.fileName, newPath)
            self._renameRelatedSidecarFiles(item.fileName, newPath)

            if self.localMode:
                for idx, local_item in enumerate(self.localFiles):
                    if local_item.fileName == item.fileName:
                        self.localFiles[idx].fileName = newPath
                        break
            else:
                if hasattr(self.DM, 'renameDownloadItem'):
                    self.DM.renameDownloadItem(item.downloadIdx, newPath)
                else:
                    for idx, dm_item in enumerate(self.DM.getList()):
                        if dm_item.fileName == item.fileName:
                            self.DM.getList()[idx].fileName = newPath
                            break

            self.reloadList(True)

            self.session.open(MessageBox, _("File renamed successfully!"), type=MessageBox.TYPE_INFO)

        except Exception as e:
            printExc()
            self.session.open(MessageBox, _("Error renaming file: %s") % str(e), type=MessageBox.TYPE_ERROR)

    def getSelIndex(self):
        currSelIndex = self["downloadlist"].getIndex()
        return currSelIndex

    def getSelItem(self):
        currSelIndex = self["downloadlist"].getIndex()
        if not self.localMode:
            list = self.currList
        else:
            list = self.localFiles
        if len(list) <= currSelIndex:
            printDBG("ERROR: getSelItem there is no item with index: %d, listOfItems.len: %d" % (currSelIndex, len(list)))
            return None
        return list[currSelIndex]

#    def getSelectedItem(self):
#        sel = None
#        try:
#            sel = self["list"].l.getCurrentSelection()[0]
#        except Exception:
#            return None
#        return sel

    def onStart(self):
        if self.started == 0:
            # pobierz liste
            self.started = 1
        return

    def buildEntry(self, item):
        # width = self.l.getItemSize().width()
        # height = self.l.getItemSize().height()
        # res = [None]

        # Downloaded Size
        info1 = formatBytes(item.downloadedSize)

        # File Size
        if item.fileSize > 0:
            info1 += "/" + formatBytes(item.fileSize)

        elif item.totalFileDuration > 0 and item.downloadedFileDuration > 0:
            totalDuration = item.totalFileDuration
            downloadDuration = item.downloadedFileDuration
            totalDuration = str(timedelta(seconds=totalDuration))
            downloadDuration = str(timedelta(seconds=downloadDuration))
            if totalDuration.startswith('0:'):
                totalDuration = totalDuration[2:]
            if downloadDuration.startswith('0:'):
                downloadDuration = downloadDuration[2:]
            info1 = "{0}/{1} ({2})".format(downloadDuration, totalDuration, info1)

        # Downloaded Procent
        if item.downloadedProcent >= 0:
            info1 += ", " + str(item.downloadedProcent) + "%"

        # Download Speed
        info2 = info1 + ", " + formatBytes(item.downloadedSpeed) + "/s"

        try:
            fileName = item.fileName.split('/')[-1]
        except Exception:
            fileName = ''
        # res.append((eListboxPythonMultiContent.TYPE_TEXT, 70, 0, width - 70, self.fonts[0][2], 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, fileName))
        # res.append((eListboxPythonMultiContent.TYPE_TEXT, 70, self.fonts[0][2], width - 70, self.fonts[1][2], 1, RT_HALIGN_LEFT | RT_VALIGN_CENTER, item.url))

        status = ""
        info = ""
        if DMHelper.STS.WAITING == item.status:
            status += _("PENDING")
        elif DMHelper.STS.DOWNLOADING == item.status:
            status += _("DOWNLOADING")
            info = info2
        elif DMHelper.STS.DOWNLOADED == item.status:
            status += _("DOWNLOADED")
            info = info1
        elif DMHelper.STS.INTERRUPTED == item.status:
            status += _("ABORTED")
            info = info1
        elif DMHelper.STS.ERROR == item.status:
            status += _("DOWNLOAD ERROR")

#        res.append((eListboxPythonMultiContent.TYPE_TEXT, width - 240, self.fonts[0][2] + self.fonts[1][2], 240, self.fonts[2][2], 2, RT_HALIGN_RIGHT | RT_VALIGN_CENTER, status))
#        res.append((eListboxPythonMultiContent.TYPE_TEXT, 45, self.fonts[0][2] + self.fonts[1][2], width - 45 - 240, self.fonts[2][2], 2, RT_HALIGN_LEFT | RT_VALIGN_CENTER, info))
#        res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHABLEND, 3, 1, 64, 64, self.dictPIX.get(item.status, None)))

        return (self.dictPIX.get(item.status, None), fileName, item.url, info, status)

    def buildEnties(self, items):
        listItems = []
        for x in items:
            listItems.append(self.buildEntry(x))
        return listItems

    def reloadList(self, force=False):
        if not self.localMode:
            global gIPTVDM_listChanged
            if True is gIPTVDM_listChanged or force:
                printDBG("IPTV_DM_UI reload downloads list")
                # self["list"].hide()
                gIPTVDM_listChanged = False
                # get current List from api
                self.currList = self.DM.getList()
                self["downloadlist"].setList(self.buildEnties(self.currList))
                # self["list"].setList([(x,) for x in self.currList])
                # self["list"].show()
        elif force:
            printDBG("IPTV_DM_UI reload archive list")
            self["downloadlist"].setList(self.buildEnties(self.localFiles))
            # self["list"].hide()
            # self["list"].setList([(x,) for x in self.localFiles])
            # self["list"].show()
    # end reloadList

    def hideWindow(self):
        self.visible = False
        self.hide()

    def showWindow(self):
        self.visible = True
        self.show()

    def Error(self, error=None):
        pass

    def __event(self, ev):
        pass


class IPTVDMNotificationWidget(Screen):
    # flags="wfNoBorder", same as every other chrome screen in this
    # branch, plus a chrome header via skinchrome.build_header_auto().
    #
    # Width is computed fresh per call (__prepareSkin(text), driven by
    # IPTVDMNotification.showNotify() below rebuilding this dialog from
    # scratch every time instead of reusing one persistent instance) so
    # the window tracks how long the download text actually is, instead
    # of a fixed width. True per-pixel font measurement
    # (Tools.TextBoundary.getTextBoundarySize) needs an already-existing
    # widget instance to measure against, which doesn't exist yet at the
    # point a brand new dialog's skin has to be built - so this uses a
    # simple chars-times-average-glyph-width estimate instead (generous
    # padding, capped at 1200), same class of heuristic
    # IPTVMultipleInputBox's own maxWidth already uses elsewhere in this
    # file's neighborhood, not exact font metrics.
    #
    # status ("FERTIG"/"ABGEBROCHEN"/...) gets its own line below the
    # filename text rather than being appended to it on one line - both
    # lines colored per outcome (statusColor, chosen by the caller -
    # iptvdmapi.py's updateDownloadedItemStatus()), filename line
    # centered and Regular weight, status line Bold, so the whole
    # notification reads as one colored unit per outcome.
    # neither label below sets noWrap, so Enigma2's default Label behavior
    # wraps text that doesn't fit its box onto a second line - fine
    # normally, but these boxes are a fixed single-line height, so a
    # wrapped line would just overflow into (or past) the line below it.
    # Truncating to whatever the capped MAX_WIDTH can show on one line
    # guarantees it never has to wrap, independent of whatever the caller
    # already truncated to (iptvdmapi.py caps at 100 chars, close to but
    # not guaranteed under this limit once combined with a long status
    # word). Used by both __prepareSkin() (sizing) and __init__() (the
    # actual Label text) so the two can never disagree on what fits.
    MAX_WIDTH = 1200
    MAX_CHARS = (MAX_WIDTH - 40) // 11

    @staticmethod
    def __fitOneLine(s):
        if len(s) > IPTVDMNotificationWidget.MAX_CHARS:
            return s[:IPTVDMNotificationWidget.MAX_CHARS - 3] + '...'
        return s

    def __prepareSkin(self, text, status, statusColor):
        iconBase = skinchrome.getIconBase()
        headerMinWidth = 420  # same minimum build_header() needs for logo+title, see its own comment
        longer = max(len(text), len(status))
        textWidth = int(longer * 11) + 40  # ~11px/glyph at Regular;20, plus 20px padding each side
        width = max(headerMinWidth, min(textWidth, self.MAX_WIDTH))
        return """<screen name="IPTVDMNotificationWidget" position="e-%d,60" resolution="1280,720" zPosition="10" size="%d,140" title="%s" backgroundColor="#34111112" flags="wfNoBorder">
            %s
            <widget name="message_label" font="Regular;20" position="20,68" zPosition="2" valign="center" halign="center" size="%d,32" foregroundColor="%s" backgroundColor="#34111112" borderWidth="1" borderColor="black" shadowColor="black" shadowOffset="-2,-2" transparent="1" />
            <widget name="status_label" font="Bold;18" position="20,102" zPosition="2" valign="center" halign="center" size="%d,28" foregroundColor="%s" backgroundColor="#34111112" borderWidth="1" borderColor="black" shadowColor="black" shadowOffset="-2,-2" transparent="1" />
        </screen>""" % (
            width + 20, width, _("E2iPlayer downloader"),
            skinchrome.build_header_auto(iconBase=iconBase),
            width - 40, statusColor,
            width - 40, statusColor,
        )

    def __init__(self, session, text="", status="", statusColor="white"):
        text = self.__fitOneLine(text)
        status = self.__fitOneLine(status)
        self.skin = self.__prepareSkin(text, status, statusColor)
        Screen.__init__(self, session)
        self.setTitle(_("E2iPlayer downloader"))
        self.skinName = skinchrome.forceInternalSkinName(["IPTVDMNotificationScreen", "IPTVDMNotificationWidget"])
        self['message_label'] = Label(text)
        self['status_label'] = Label(status)

    def setText(self, text, status=""):
        self['message_label'].setText(self.__fitOneLine(text))
        self['status_label'].setText(self.__fitOneLine(status))


class IPTVDMNotification():
    # Does NOT keep one persistent dialog instance reused across every
    # showNotify() call - the window needs a different width per call
    # (see IPTVDMNotificationWidget's own comment above), and Enigma2
    # skins are only ever parsed once at construction (the header's own
    # "e"-relative sizes wouldn't follow a live resize of an already-built
    # dialog). Each notification instead closes whatever notification is
    # still open (deleteDialog(), same counterpart instantiateDialog()
    # itself expects) and builds a brand new one sized for the new text.
    #
    # Notifications are queued rather than immediately replacing whatever
    # is currently showing - several downloads finishing close together
    # would otherwise stomp each other's notification before anyone saw
    # it. A new showNotify() while one is already showing just appends;
    # the timer's own completion advances to the next queued text instead
    # of closing for good, so every completion gets its own full time on
    # screen.
    def __init__(self):
        self.session = None
        self.dialog = None
        self.queue = []
        self.mainTimer = eTimer()
        self.mainTimer_conn = eConnectCallback(self.mainTimer.timeout, self._advance)

    def dialogInit(self, session):
        printDBG("> IPTVDMNotification.dialogInit")
        self.session = session

    def notifyHide(self):
        self.queue = []
        self._advance()

    def _advance(self):
        if self.dialog:
            self.session.deleteDialog(self.dialog)
            self.dialog = None
        if not self.queue:
            return
        text, status, statusColor = self.queue.pop(0)
        printDBG("> IPTVDMNotification._advance[%s][%s]" % (text, status))
        self.dialog = self.session.instantiateDialog(IPTVDMNotificationWidget, text, status, statusColor)
        self.dialog.show()
        duration = int(config.plugins.iptvplayer.IPTVDMNotificationDuration.value) * 1000
        self.mainTimer.start(duration, 1)

    def showNotify(self, text, status="", statusColor="white"):
        if self.session is None or not config.plugins.iptvplayer.IPTVDMShowNotification.value:
            return
        printDBG("> IPTVDMNotification.showNotify[%s][%s]" % (text, status))
        self.queue.append((text, status, statusColor))
        if self.dialog is None:
            self._advance()


gIPTVDMNotification = IPTVDMNotification()


def GetIPTVDMNotification():
    return gIPTVDMNotification
