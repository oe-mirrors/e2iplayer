# -*- coding: utf-8 -*-
#
#  IPTV download manager UI
#
#  $Id$
#
#
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.cover import SimpleAnimatedCover
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta, enum
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, formatBytes, touch, eConnectCallback, ReadUint32
from Plugins.Extensions.IPTVPlayer.components.iptvplayer import IPTVStandardMoviePlayer, IPTVMiniMoviePlayer
from Plugins.Extensions.IPTVPlayer.components.iptvextmovieplayer import IPTVExtMoviePlayer
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdownloadercreator import DownloaderCreator
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.cover import Cover3
from Plugins.Extensions.IPTVPlayer.components import skinchrome
###################################################

###################################################
# FOREIGN import
###################################################
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from enigma import getDesktop
from enigma import eTimer
from Components.config import config
from Components.ActionMap import ActionMap
from Components.Label import Label
# from Components.Sources.StaticText import StaticText
from Tools.LoadPixmap import LoadPixmap
from Tools.Directories import fileExists
from os import remove as os_remove
from datetime import timedelta
###################################################


class E2iPlayerBufferingWidget(Screen):
    NUM_OF_ICON_FRAMES = 8

    # `__prepareSkin()` is per-instance, using the screen's own real
    # desktop size directly (`getDesktop()` pixels, not an HD-reference +
    # `resolution=` auto-scale), since it deliberately draws itself larger
    # than the desktop with no border.
    #
    # Header band (no logo - this is a transient full-screen playback
    # overlay, not a navigable app screen) via
    # `skinchrome.build_header(showLogo=False)`, using this screen's own
    # tier `scale` (same explicit-scale variant PlayerSelectorWidget's
    # grid mode uses, since this screen isn't `resolution=`-auto-scaled
    # either). The content block centers within the space BELOW the
    # header instead of the full screen height.
    #
    # The buffering icon/percentage/console/addinfo box sizes AND fonts
    # both scale together via `skinchrome.scalePixels()`, using real
    # per-tier buffering frames (`icons/HD|FHD|WQHD/buffering/
    # buffering_N.png`, upscaled from the original 128x128 HD set via
    # Lanczos resampling to the same 1.0/1.5/2.0 scale every other chrome
    # asset uses) - scaling box and font from the same `scale` keeps them
    # in sync at every tier.
    #
    # OK/REC/EXIT sit in the standard left-icon-cluster slots (same
    # 40x26/60x38/80x51 `leftIconGeometry()` math every other chrome
    # footer's menu/nav/ok/exit cluster uses) rather than a hand-picked
    # bottom-right offset, on top of skinchrome's own footer background
    # band + shadow divider. OK/REC/EXIT still toggle their own
    # visibility at runtime (updateOKButton()/updateRecButton()), so
    # build_footer() itself only supplies the background band + divider
    # line here (showOk/showExit/showMenu/showNav/showNum all False, no
    # color keys) - the actual button pixmaps stay separate named widgets
    # like before. `rec.png` (real 40x26/60x38/80x51 tiered files
    # matching ok.png/exit.png's own convention exactly) lives in
    # `icons/HD|FHD|WQHD/` alongside them - all 3 buttons load the same
    # way (Cover3 + LoadPixmap(iconBase + ...) in __init__ below).
    def __prepareSkin(self):
        scale = skinchrome.getScale()
        iconBase = skinchrome.getIconBase()
        sz_w = getDesktop(0).size().width()
        sz_h = getDesktop(0).size().height()
        headerH = skinchrome.header_height(scale)
        footerH = skinchrome.footer_height(scale)
        # icon - real per-tier frame size (128/192/256), matching the
        # actual buffering_N.png assets for this tier
        i_w = skinchrome.scalePixels(128, scale)
        i_h = i_w
        # percentage
        p_w = skinchrome.scalePixels(120, scale)
        p_h = p_w
        # console
        c_w = sz_w
        c_h = skinchrome.scalePixels(80, scale)
        # addinfo
        a_w = sz_w - 10
        a_h = skinchrome.scalePixels(80, scale)
        fontSize = skinchrome.scalePixels(21, scale)

        availableH = sz_h - headerH - footerH
        start_y = headerH + (availableH - (i_h + c_h)) / 2
        # icon
        i_x = (sz_w - i_w) / 2
        i_y = start_y
        # percentage
        p_x = (sz_w - p_w) / 2
        p_y = start_y + (i_h - p_h) / 2
        # console
        c_x = 0
        c_y = i_y + i_h
        # addinfo - sits just above the footer band now
        a_x = 10
        a_y = sz_h - footerH - a_h - 10

        # footer - background band + shadow divider only, no left icons/
        # color keys of its own (OK/REC/EXIT stay separate, runtime-
        # toggleable widgets - see comment above)
        footerPart = skinchrome.build_footer(sz_h, scale=scale, iconBase=iconBase, keys=(),
                                              showMenu=False, showNav=False, showNum=False,
                                              showOk=False, showExit=False)
        okGeom = skinchrome.leftIconGeometry(sz_h, 0, scale)
        recGeom = skinchrome.leftIconGeometry(sz_h, 1, scale)
        exitGeom = skinchrome.leftIconGeometry(sz_h, 2, scale)

        printDBG("[E2iPlayerBufferingWidget] desktop size %dx%d" % (sz_w, sz_h))
        return """
        <screen name="E2iPlayerBufferingWidget"  position="center,center" flags="wfNoBorder" size="%d,%d" title="%s">
         %s
         <widget name="percentage" size="%d,%d"   position="%d,%d"  zPosition="5" valign="center" halign="center"  font="Regular;%d" backgroundColor="black" transparent="1" /> #foregroundColor="white" shadowColor="black" shadowOffset="-1,-1"
         <widget name="console"    size="%d,%d"   position="%d,%d"  zPosition="5" valign="center" halign="center"  font="Regular;%d" backgroundColor="black" transparent="1" />
         <widget name="icon"       size="%d,%d"   position="%d,%d"  zPosition="4" transparent="1" alphatest="blend" />
         <widget name="addinfo"    size="%d,%d"   position="%d,%d"  zPosition="5" valign="center" halign="center"  font="Regular;%d" backgroundColor="black" transparent="1" />
         %s
         <widget name="ok_button"        position="%d,%d"                     size="%d,%d"   zPosition="8" transparent="1" alphatest="blend" />
         <widget name="rec_button"       position="%d,%d"                     size="%d,%d"   zPosition="8" transparent="1" alphatest="blend" />
         <widget name="exit_button"      position="%d,%d"                     size="%d,%d"   zPosition="8" transparent="1" alphatest="blend" />
        </screen>""" % (sz_w, sz_h, _("%s buffering...") % "E2iPlayer",  # screen
                        skinchrome.build_header(scale=scale, iconBase=iconBase, showLogo=False),  # header
                        p_w, p_h, p_x, p_y, fontSize,  # percentage
                        c_w, c_h, c_x, c_y, fontSize,  # console
                        i_w, i_h, i_x, i_y,  # icon
                        a_w, a_h, a_x, a_y, fontSize,  # addinfo
                        footerPart,  # footer band

                        okGeom['x'], okGeom['y'], okGeom['w'], okGeom['h'],      # OK
                        recGeom['x'], recGeom['y'], recGeom['w'], recGeom['h'],  # REC
                        exitGeom['x'], exitGeom['y'], exitGeom['w'], exitGeom['h'],  # EXIT
                      )

    def __init__(self, session, url, pathForBuffering, pathForDownloading, movieTitle, activMoviePlayer, requestedBuffSize, playerAdditionalParams={}, downloadManager=None, fileExtension=''):
        self.session = session
        self.skin = self.__prepareSkin()
        Screen.__init__(self, session)
        # explicit name so an external skin can target the buffering overlay
        self.skinName = skinchrome.forceInternalSkinName(["E2iPlayerBufferingWidget"])
        self.setTitle(_("%s buffering...") % "E2iPlayer")
        self.onStartCalled = False

        self.downloadingPath = pathForDownloading
        self.bufferingPath = pathForBuffering
        self.filePath = pathForBuffering + '/.iptv_buffering.flv'
        self.url = url
        self.movieTitle = movieTitle
        self.downloadManager = downloadManager
        self.fileExtension = fileExtension

        self.currentService = self.session.nav.getCurrentlyPlayingServiceReference()
        self.activMoviePlayer = activMoviePlayer

        self.onClose.append(self.__onClose)
        self.onLayoutFinish.append(self.__loadButtonIcons)
        self.onShow.append(self.onWindowShow)
        # self.onHide.append(self.onWindowHide)

        self["actions"] = ActionMap(["IPTVAlternateVideoPlayer", "WizardActions", "MoviePlayerActions"],
        {
            "ok": self.ok_pressed,
            "back": self.back_pressed,
            "leavePlayer": self.back_pressed,
            "record": self.record_pressed,
        }, -1)

        self["console"] = Label()
        self["percentage"] = Label()
        self["addinfo"] = Label()
        self['ok_button'] = Cover3()
        self['rec_button'] = Cover3()
        self['exit_button'] = Cover3()
        # none of the 3 carry a static pixmap= in the skin - loaded from
        # this branch's own tiered chrome icons instead (rec.png ships
        # real 40x26/60x38/80x51 files matching ok.png/exit.png's own
        # convention). setPixmap() can't be called here in __init__ -
        # these Cover3 widgets' .instance is only created once Enigma2
        # actually applies the skin to the screen, which happens AFTER
        # __init__ returns, not during it. Loading happens in
        # onLayoutFinish instead, the standard hook for touching widget
        # instances post-skin-apply.

        self["icon"] = SimpleAnimatedCover()
        # prepare icon frames path - tiered per-resolution frames
        # (icons/HD|FHD|WQHD/buffering/buffering_N.png), same iconBase as
        # every other chrome asset, instead of one un-tiered 128x128 set
        # shared by every resolution
        _iconBase = skinchrome.getIconBase()
        frames = []
        for idx in range(1, self.NUM_OF_ICON_FRAMES + 1):
            frames.append(_iconBase + '/buffering/buffering_%d.png' % idx)
        self["icon"].loadFrames(frames)

        self.inMoviePlayer = False
        self.canRunMoviePlayer = False  # used in function updateDisplay, so must be first initialized
        # main Timer
        self.mainTimer = eTimer()
        self.mainTimerEnabled = False
        self.mainTimer_conn = eConnectCallback(self.mainTimer.timeout, self.updateDisplay)
        self.mainTimerInterval = 1000  # by default 1s

        self.requestedBuffSize = requestedBuffSize
        self.playerAdditionalParams = playerAdditionalParams

        self.clipLength = None
        self.lastPosition = None
        self.lastSize = 0

        # Some MP4 files are not prepared for streaming
        # MOOV atom is needed to start playback
        # if it is located at the end of file, then
        # will try to download it separately to start playback
        # without downloading the whole file
        self.clouldBeMP4 = False
        self.isMOOVAtomAtTheBeginning = None
        self.checkMOOVAtom = True
        self.maxMOOVAtomSize = 10 * 1024 * 1024  # 10 MB max moov atom size
        self.moovAtomOffset = 0
        self.moovAtomSize = 0

        self.MOOV_STS = enum(UNKNOWN=0,
                              WAITING=1,
                              DOWNLOADING=2,
                              DOWNLOADED=3,
                              ERROR=4)
        self.moovAtomStatus = self.MOOV_STS.UNKNOWN
        self.moovAtomDownloader = None
        self.moovAtomPath = pathForBuffering + '/.iptv_buffering_moov.flv'
        self.closeRequestedByUser = None

        printDBG(">> activMoviePlayer[%s]" % self.activMoviePlayer)

    # end def __init__(self, session):

    def onStart(self):
        '''
            this method is called once like __init__ but in __init__ we cannot display MessageBox
        '''
        self['rec_button'].hide()
        self['ok_button'].hide()

        # create downloader
        self.downloader = DownloaderCreator(self.url)
        self._cleanedUp()

        if self.downloader:
            self.downloader.isWorkingCorrectly(self._startDownloader)
        else:
            self.session.openWithCallback(self.iptvDoClose, MessageBox, _("Downloading can not be started.\n The address ('%r') is incorrect.") % self.url, type=MessageBox.TYPE_ERROR, timeout=10)

    def _startDownloader(self, sts, reason):
        if sts:
            url, downloaderParams = DMHelper.getDownloaderParamFromUrl(self.url)
            if url.split('?', 1)[0].lower().endswith('.mp4'):
                self.clouldBeMP4 = True
            self.downloader.start(url, self.filePath, downloaderParams)
            self.setMainTimerSts(True)
            self.canRunMoviePlayer = True
        else:
            self.session.openWithCallback(self.iptvDoClose, MessageBox, _("Downloading can not be started.\n Downloader %s does not work properly.\nStatus[%s]") % (self.downloader.getName(), reason.strip()), type=MessageBox.TYPE_ERROR, timeout=10)

    def _isInLiveMode(self):
        if isinstance(self.url, strwithmeta):
            if 'iptv_livestream' in self.url.meta:
                return self.url.meta['iptv_livestream']
        # if we do not have information if it is live try to figure out from other sources
        if self.downloader:
            tmp = self.downloader.isLiveStream()
            if None is not tmp:
                return tmp
        if self.url.startswith('rtmp'):
            return True

    def onEnd(self):
        self.setMainTimerSts(False)
        if self.downloader:
            self.downloader.terminate()
            self.downloader = None

        if self.moovAtomDownloader:
            self.moovAtomDownloader.terminate()
            self.moovAtomDownloader = None
        self._cleanedUp()

    def leaveMoviePlayer(self, ret=None, lastPosition=None, clipLength=None, *args, **kwargs):
        printDBG("leaveMoviePlayer ret[%r], lastPosition[%r]" % (ret, lastPosition))
        # There is need to set None for current service
        # otherwise there is a problem with resuming play
        self.session.nav.playService(None)
        self.lastPosition = lastPosition
        self.clipLength = clipLength
        self.canRunMoviePlayer = False
        self.inMoviePlayer = False

        self.closeRequestedByUser = ret

        if 'save_buffer' == ret:
            self.moveToDownloadManager()
        elif ret in ['key_exit', None]:
            if DMHelper.STS.DOWNLOADING == self.downloader.getStatus():
                self.lastSize = self.downloader.getLocalFileSize(True)
                printDBG("E2iPlayerBufferingWidget.leaveMoviePlayer: movie player consume all data from buffer - still downloading")
                self.confirmExitCallBack()  # continue
            else:
                printDBG("E2iPlayerBufferingWidget.leaveMoviePlayer: movie player consume all data from buffer - downloading finished")
                if DMHelper.STS.DOWNLOADED != self.downloader.getStatus():
                    self.session.openWithCallback(self.iptvDoClose, MessageBox, text=_("Error occurs during download."), type=MessageBox.TYPE_ERROR, timeout=5)
                else:
                    self.iptvDoClose()
        elif ret in ['key_stop']:
            # ask if we should close
            self.lastSize = self.downloader.getLocalFileSize(True)
            # list = [ (_("Yes"), True), (_("No"), False) ]
            # if self.downloadManager and self.downloader and self.downloader.getPlayableFileSize() > 0:
            #    list.append((_("yes, move playback buffer to the download manager"), 'move'))
            self.session.openWithCallback(self.confirmExitCallBack, MessageBox, text=_("Stop playing?"), type=MessageBox.TYPE_YESNO)

    def confirmExitCallBack(self, ret=None):
        if ret is True:
            self.iptvDoClose()
        elif ret == 'move':
            self.moveToDownloadManager()
        else:
            if not self._isInLiveMode():
                self.canRunMoviePlayer = True
                self.setMainTimerSts(True)
            else:
                # for live streams we will remove old buffer and start downloader once again
                self.lastSize = 0
                self.onEnd()
                self.onStart()

    def moveToDownloadManager(self, fromPlayer=True):
        fullFilesPaths = [self.downloadingPath + '/' + self.movieTitle + self.fileExtension, self.bufferingPath + '/' + self.movieTitle + self.fileExtension]
        bRet, msg = self.downloadManager.addBufferItem(self.downloader, fullFilesPaths)
        if bRet:
            self.downloader = None
            message = _('The playback buffer has been moved to the download manager.\nIt will be saved in the file:\n\"%s\"') % msg
            self.session.openWithCallback(self.iptvDoClose, MessageBox, text=message, type=MessageBox.TYPE_INFO, timeout=5)
        else:
            # show error message and ask user what to do
            message = _("Moving playback buffer to the download manager failed with the following error \"%s\"") % msg
            # message += '\n\n' + _("What do you want to do?")
            # list = [ (_("Continue playback"), True), (_("Stop playback"), False) ]
            if fromPlayer:
                message += '\n\n' + _("Stop playing?")
                self.session.openWithCallback(self.confirmExitCallBack, MessageBox, text=message, type=MessageBox.TYPE_YESNO)
            else:
                self.session.openWithCallback(self.iptvContinue, MessageBox, text=message, type=MessageBox.TYPE_INFO)

    def iptvContinue(self, *args, **kwargs):
            self.setMainTimerSts(True)
            self.canRunMoviePlayer = True

    def back_pressed(self):
        self.closeRequestedByUser = 'key_exit'
        self.iptvDoClose()

    def record_pressed(self):
        if self.canRunMoviePlayer:  # and self.downloader.getPlayableFileSize() > 0:
            self.canRunMoviePlayer = False
            self.setMainTimerSts(False)
            self.closeRequestedByUser = 'save_buffer'
            self.moveToDownloadManager(False)

    def iptvDoClose(self, *args, **kwargs):
        self.onEnd()
        self.close(self.closeRequestedByUser, self.lastPosition, self.clipLength)

    def ok_pressed(self):
        if self.canRunMoviePlayer and self.downloader.getPlayableFileSize() > 0:
            self.runMovePlayer()

    def runMovePlayer(self):
        # this shoudl not happen but to make sure
        if not self.canRunMoviePlayer:
            printDBG('called runMovePlayer with canRunMoviePlayer set to False')
            return

        self.inMoviePlayer = True
        buffSize = self.downloader.getLocalFileSize() - self.lastSize
        printDBG("Run MoviePlayer with buffer size [%s]" % formatBytes(float(buffSize)))
        self.setMainTimerSts(False)

        player = self.activMoviePlayer
        printDBG('E2iPlayerBufferingWidget.runMovePlayer [%r]' % player)
        playerAdditionalParams = dict(self.playerAdditionalParams)
        playerAdditionalParams['downloader'] = self.downloader
        if self.isMOOVAtomAtTheBeginning:
            playerAdditionalParams['moov_atom_info'] = {'offset': 0, 'size': self.moovAtomOffset + self.moovAtomSize, 'file': ''}
        elif self.moovAtomStatus == self.MOOV_STS.DOWNLOADED and \
             DMHelper.STS.DOWNLOADED != self.downloader.getStatus():
            playerAdditionalParams['moov_atom_info'] = {'offset': self.moovAtomOffset, 'size': self.moovAtomSize, 'file': self.moovAtomPath}

        if strwithmeta(self.url).meta.get('iptv_proto', '') in ['f4m', 'uds', 'm3u8']:
            playerAdditionalParams['file-download-timeout'] = 90000  # 90s
        else:
            playerAdditionalParams['file-download-timeout'] = 10000  # 10s
        playerAdditionalParams['file-download-live'] = self._isInLiveMode()
        playerAdditionalParams['download_manager_available'] = self.downloadManager is not None
        if "mini" == player:
            self.session.openWithCallback(self.leaveMoviePlayer, IPTVMiniMoviePlayer, self.filePath, self.movieTitle, self.lastPosition, 4)
        elif "exteplayer" == player:
            self.session.openWithCallback(self.leaveMoviePlayer, IPTVExtMoviePlayer, self.filePath, self.movieTitle, self.lastPosition, 'eplayer', playerAdditionalParams)
        elif "extgstplayer" == player:
            self.session.openWithCallback(self.leaveMoviePlayer, IPTVExtMoviePlayer, self.filePath, self.movieTitle, self.lastPosition, 'gstplayer', playerAdditionalParams)
        else:
            self.session.openWithCallback(self.leaveMoviePlayer, IPTVStandardMoviePlayer, self.filePath, self.movieTitle)
        playerAdditionalParams = None

    def setMainTimerSts(self, start):
        try:
            if start:
                if not self.mainTimerEnabled:
                    self.mainTimer.start(self.mainTimerInterval)
                    self.mainTimerEnabled = True
                    self.updateDisplay()
            else:
                if self.mainTimerEnabled:
                    self.mainTimer.stop()
                    self.mainTimerEnabled = False
        except Exception:
            printDBG("setMainTimerSts status[%r] EXCEPTION" % start)

    def updateRecButton(self):
        if self.canRunMoviePlayer:  # and self.downloader.getPlayableFileSize() > 0:
            self['rec_button'].show()
        else:
            self['rec_button'].hide()

    def updateOKButton(self):
        if self.canRunMoviePlayer and False is self.checkMOOVAtom and (self.isMOOVAtomAtTheBeginning is None or self.moovAtomStatus == self.MOOV_STS.DOWNLOADED):
            self['ok_button'].show()
        else:
            self['rec_button'].hide()

    def updateDisplay(self):
        printDBG("updateDisplay")
        if self.inMoviePlayer:
            printDBG("updateDisplay aborted - we are in moviePlayer")
            return

        self.updateRecButton()

        if not self.mainTimerEnabled:
            printDBG("updateDisplay aborted - timer stoped")
            return

        self.downloader.updateStatistic()
        localSize = self.downloader.getLocalFileSize()
        remoteSize = self.downloader.getRemoteFileSize()

        if self.checkMOOVAtom and \
           localSize > 10240:
            self.checkMOOVAtom = False

            if remoteSize > self.maxMOOVAtomSize and \
               self.downloader.getName() == "wget" and \
               (self.clouldBeMP4 or (None is not self.downloader.getMimeType() and
               'mp4' in self.downloader.getMimeType())):
                # check moov atom position
                # if it is located at the begining of MP4 file
                # it should be just after ftyp atom
                try:
                    with open(self.filePath, "rb") as f:
                        currOffset = 0
                        while currOffset < localSize:
                            rawSize = ReadUint32(f.read(4), False)
                            rawType = f.read(4)
                            printDBG(">> rawType [%s]" % rawType)
                            printDBG(">> rawSize [%d]" % rawSize)
                            if currOffset == 0 and rawType != b"ftyp":
                                # this does not looks like MP4 file
                                break
                            else:
                                if rawType == b"moov":
                                    self.moovAtomOffset = currOffset
                                    self.moovAtomSize = rawSize
                                    self.isMOOVAtomAtTheBeginning = True
                                    break
                                elif rawType == b"mdat":
                                    # we are not sure if after mdat will be moov atom but
                                    # if this will be max last 10MB of file then
                                    # we will download it
                                    self.moovAtomOffset = currOffset + rawSize
                                    self.moovAtomSize = remoteSize - self.moovAtomOffset
                                    self.isMOOVAtomAtTheBeginning = False
                                    break
                                currOffset += rawSize
                            f.seek(currOffset, 0)
                    printDBG(">> moovAtomOffset[%d]" % self.moovAtomOffset)
                    printDBG(">> moovAtomSize[%d]" % self.moovAtomSize)
                except Exception:
                    printExc()

        if None is not self.downloader and self.downloader.hasDurationInfo() \
           and self.downloader.getTotalFileDuration() > 0:
            totalDuration = self.downloader.getTotalFileDuration()
            downloadDuration = self.downloader.getDownloadedFileDuration()
            rFileSize = str(timedelta(seconds=totalDuration))
            lFileSize = str(timedelta(seconds=downloadDuration))
            if rFileSize.startswith('0:'):
                rFileSize = rFileSize[2:]
            if lFileSize.startswith('0:'):
                lFileSize = lFileSize[2:]
        else:
            # remote size
            if -1 == remoteSize:
                rFileSize = '??'
            else:
                rFileSize = formatBytes(float(remoteSize))
            # local size
            if -1 == localSize:
                lFileSize = '??'
            else:
                lFileSize = formatBytes(float(localSize))

        # download speed
        dSpeed = self.downloader.getDownloadSpeed()
        if dSpeed > -1 and localSize > 0:
            dSpeed = formatBytes(float(dSpeed))
        else:
            dSpeed = ''

        speed = self.downloader.getDownloadSpeed()
        tmpStr = ''
        if '??' != lFileSize:
            if '??' != rFileSize:
                tmpStr = "\n%s/%s" % (lFileSize, rFileSize)
            else:
                tmpStr = "\n%s" % (lFileSize)
            if '' != dSpeed:
               tmpStr += "\n%s/s" % (dSpeed)
        else:
            tmpStr += '\n\n'

        self["console"].setText(self.movieTitle + tmpStr)

        handled = False
        percentage = 0
        requestedBuffSize = -1
        tmpBuffSize = 0
        if self.isMOOVAtomAtTheBeginning is True:
            moovAtomDataSize = self.moovAtomOffset + self.moovAtomSize
            if moovAtomDataSize > localSize:
                if self.moovAtomStatus != self.MOOV_STS.DOWNLOADING:
                    self["addinfo"].setText(_("Please wait for initialization data."))
                    self.moovAtomStatus = self.MOOV_STS.DOWNLOADING
                remoteSize = self.moovAtomOffset + self.moovAtomSize
                if localSize > remoteSize:
                    percentage = 100
                else:
                    percentage = (100 * localSize) / remoteSize
            else:
                requestedBuffSize = self.requestedBuffSize
                if self.lastSize > moovAtomDataSize:
                    tmpBuffSize = localSize - self.lastSize
                else:
                    tmpBuffSize = localSize - moovAtomDataSize
                if tmpBuffSize > requestedBuffSize:
                    percentage = 100
                else:
                    percentage = (100 * tmpBuffSize) / requestedBuffSize
                if self.moovAtomStatus != self.MOOV_STS.DOWNLOADED:
                    self["addinfo"].setText("")
                    self.moovAtomStatus = self.MOOV_STS.DOWNLOADED
            handled = True
        elif self.isMOOVAtomAtTheBeginning is False and self.moovAtomStatus not in [self.MOOV_STS.WAITING, self.MOOV_STS.ERROR, self.MOOV_STS.DOWNLOADED]:
            # At now only exteplayer3 is able to use moov atom in separate file
            if self.activMoviePlayer == 'exteplayer' and self.moovAtomStatus == self.MOOV_STS.UNKNOWN:
                url, downloaderParams = DMHelper.getDownloaderParamFromUrl(self.url)
                downloaderParams['start_pos'] = self.moovAtomOffset
                self.moovAtomDownloader = DownloaderCreator(self.url)
                self.moovAtomDownloader.start(url, self.moovAtomPath, downloaderParams)
                self.moovAtomStatus = self.MOOV_STS.DOWNLOADING
                self["addinfo"].setText(_("Please wait - downloading initialization data."))
            elif self.moovAtomStatus == self.MOOV_STS.DOWNLOADING:
                self.moovAtomDownloader.updateStatistic()
                status = self.moovAtomDownloader.getStatus()
                moovLocalSize = self.moovAtomDownloader.getLocalFileSize()
                moovRemoteSize = self.moovAtomDownloader.getRemoteFileSize()
                if status == DMHelper.STS.DOWNLOADING:
                    if moovLocalSize > 0 and self.moovAtomSize > 0:
                        if moovLocalSize > self.moovAtomSize:
                            percentage = 100
                        else:
                            percentage = (100 * moovLocalSize) / self.moovAtomSize
                elif status == DMHelper.STS.DOWNLOADED or (status == DMHelper.STS.INTERRUPTED and moovLocalSize == self.moovAtomSize):
                    self.moovAtomStatus = self.MOOV_STS.DOWNLOADED
                    self["addinfo"].setText("")
                else:
                    self.moovAtomStatus = self.MOOV_STS.ERROR

            handled = True
            if self.moovAtomStatus in [self.MOOV_STS.UNKNOWN, self.MOOV_STS.ERROR]:
                printDBG(">> [%s] [%s]" % (self.activMoviePlayer, self.moovAtomStatus))
                msg = [_("Whole file must be downloaded to start playback!")]
                if self.moovAtomStatus == self.MOOV_STS.UNKNOWN and self.activMoviePlayer != 'exteplayer':
                    msg.append(_("You can use external eplayer to start playback faster."))
                self["addinfo"].setText('\n'.join(msg))
                self.moovAtomStatus = self.MOOV_STS.WAITING
                handled = False

        if not handled and self.moovAtomStatus != self.MOOV_STS.WAITING:
            tmpBuffSize = localSize - self.lastSize + 1  # simple when getLocalFileSize() returns -1
            if self.downloader.getPlayableFileSize() > 0:
                requestedBuffSize = self.requestedBuffSize
                if tmpBuffSize > requestedBuffSize:
                    percentage = 100
                else:
                    percentage = (100 * tmpBuffSize) / requestedBuffSize
                handled = True

        if not handled and localSize > 0 and remoteSize > 0:
            if localSize > remoteSize:
                percentage = 100
            else:
                percentage = (100 * localSize) / remoteSize

        # every branch above computes percentage via "/" (true division
        # under Python 3) - int() before str() avoids showing something
        # like "45.3125" instead of "45", which would be wide enough to
        # wrap inside the small percentage box and visually collide with
        # the icon behind it.
        self["percentage"].setText(str(int(percentage)))
        self["icon"].nextFrame()

        # check if we start movie player
        if self.canRunMoviePlayer:
            if (requestedBuffSize > -1 and tmpBuffSize >= requestedBuffSize) or \
               (self.downloader.getStatus() == DMHelper.STS.DOWNLOADED and 0 < localSize):
                self.runMovePlayer()
                return

        # check if it is downloading
        if self.downloader.getStatus() not in [DMHelper.STS.POSTPROCESSING, DMHelper.STS.DOWNLOADING, DMHelper.STS.WAITING]:
            # messageTab = [_("Error occurs during download. \nStatus[%s], tmpBuffSize[%r], canRunMoviePlayer[%r]") % (self.downloader.getStatus(), tmpBuffSize, self.canRunMoviePlayer)]
            messageTab = [_("Error occurs during download.")]
            errorCode, errorDesc = self.downloader.getLastError()
            if errorCode is not None:
                messageTab.append(_('%s returned %s: %s') % (self.downloader.getName(), errorCode, _(errorDesc)))
            self.session.openWithCallback(self.iptvDoClose, MessageBox, '\n'.join(messageTab), type=MessageBox.TYPE_ERROR, timeout=10)
            self.canRunMoviePlayer = False
            # stop timer before message
            self.setMainTimerSts(False)

        self.updateOKButton()
        self.updateRecButton()
        return

    def __del__(self):
        printDBG('E2iPlayerBufferingWidget.__del__ --------------------------------------')

    def __loadButtonIcons(self):
        _iconBase = skinchrome.getIconBase()
        self['ok_button'].setPixmap(LoadPixmap(_iconBase + '/ok.png'))
        self['rec_button'].setPixmap(LoadPixmap(_iconBase + '/rec.png'))
        self['exit_button'].setPixmap(LoadPixmap(_iconBase + '/exit.png'))

    def __onClose(self):
        printDBG('E2iPlayerBufferingWidget.__onClose ------------------------------------')
        self.onEnd()
        self.session.nav.playService(self.currentService)
        try:
            self.mainTimer_conn = None
            self.mainTimer = None
        except Exception:
            printExc()

        self.onClose.remove(self.__onClose)
        self.onLayoutFinish.remove(self.__loadButtonIcons)
        self.onShow.remove(self.onWindowShow)
        # self.onHide.remove(self.onWindowHide)
        self.downloadManager = None

    def _cleanedUp(self):
        if fileExists(self.filePath):
            try:
                os_remove(self.filePath)
            except Exception:
                printDBG('Problem with removing old buffering file (%s)' % self.filePath)

        if fileExists(self.moovAtomPath):
            try:
                os_remove(self.moovAtomPath)
            except Exception:
                printDBG('Problem with removing old buffering file (%s)' % self.moovAtomPath)
    '''
    def doStart(self):
        if not self.onStartCalled:
            self.onStartCalled = True
            self.onStart()


    def onWindowHide(self):
        self.visible = False
    '''

    def onWindowShow(self):
        if not self.onStartCalled:
            self.onStartCalled = True
            self.onStart()
