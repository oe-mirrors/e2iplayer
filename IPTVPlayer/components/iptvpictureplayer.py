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
from Plugins.Extensions.IPTVPlayer.components.cover import SimpleAnimatedCover, Cover
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir, eConnectCallback, E2PrioFix
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdownloadercreator import DownloaderCreator
###################################################

###################################################
# FOREIGN import
###################################################
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from enigma import getDesktop, eTimer, eServiceReference, eConsoleAppContainer
from Components.config import config
from Components.ActionMap import ActionMap, HelpableActionMap
from Components.Label import Label
from Tools.Directories import fileExists, resolveFilename, SCOPE_PLUGINS
import os
import time

###################################################


class IPTVSimpleAudioPlayer():
    def __init__(self):
        additionalParams = {}
        self.gstAdditionalParams = {'buffer-duration': 2}
        self.gstAdditionalParams['download-buffer-path'] = additionalParams.get('download-buffer-path', '') # File template to store temporary files in, should contain directory and XXXXXX
        self.gstAdditionalParams['ring-buffer-max-size'] = additionalParams.get('ring-buffer-max-size', 0) # in MB
        self.gstAdditionalParams['buffer-duration'] = additionalParams.get('buffer-duration', -1) # in s
        self.gstAdditionalParams['buffer-size'] = additionalParams.get('buffer-size', 0)

        self.uri = ""
        self.playMode = ""
        self.console = None

        self.isClosing = False
        self.stopped = True

    def start(self, uri, mode='loop'):
        self.uri = uri
        self.playMode = mode

        gstplayerPath = config.plugins.iptvplayer.gstplayerpath.value
        #'export GST_DEBUG="*:6" &&' +
        cmd = gstplayerPath + ' "%s"' % self.uri
        if "://" in self.uri:
            cmd += ' "%s" "%s"  "%s"  "%s" ' % (self.gstAdditionalParams['download-buffer-path'], self.gstAdditionalParams['ring-buffer-max-size'], self.gstAdditionalParams['buffer-duration'], self.gstAdditionalParams['buffer-size'])
            tmp = strwithmeta(self.uri)
            url, httpParams = DMHelper.getDownloaderParamFromUrl(tmp)
            for key in httpParams:
                cmd += (' "%s=%s" ' % (key, httpParams[key]))
            if 'http_proxy' in tmp.meta:
                tmp = tmp.meta['http_proxy']
                if '://' in tmp:
                    if '@' in tmp:
                        tmp = re.search('([^:]+?://)([^:]+?):([^@]+?)@(.+?)$', tmp)
                        if tmp:
                            cmd += (' "proxy=%s" "proxy-id=%s" "proxy-pw=%s" ' % (tmp.group(1) + tmp.group(4), tmp.group(2), tmp.group(3)))
                    else:
                        cmd += (' "proxy=%s" ' % tmp)
        else:
            cmd = 'exteplayer3 "%s"' % self.uri + " > /dev/null"
        self.console = eConsoleAppContainer()
        self.console_appClosed_conn = eConnectCallback(self.console.appClosed, self._playerFinished)
        printDBG("IPTVSimpleAudioPlayer.start cmd[%s]" % cmd)
        self.console.execute(E2PrioFix(cmd))
        self.stopped = False

    def _playerFinished(self, code):
        printDBG("IPTVSimpleAudioPlayer.eplayer3Finished code[%r]" % code)
        if self.isClosing:
            return
        if self.playMode == 'loop' and not self.stopped:
            self.start(self.uri, self.playMode)

    def stop(self):
        if None == self.console:
            return
        self.stopped = True
        self.console.write("q\n")

    def close(self):
        self.isClosing = True
        if None != self.console:
            self.stop()
            time.sleep(1) # YES I know this is bad, but for now must be enough ;) Some, day I will fix this
            self.console.sendCtrlC()
            self.console_appClosed_conn = None
            self.console = None

#class IPTVSimpleAudioPlayer


class IPTVPicturePlayerWidget(Screen):
    NUM_OF_ICON_FRAMES = 8
    #######################
    #       SIZES
    #######################
    # screen size
    # we do not want borders, so make the screen lager than a desktop
    sz_w = getDesktop(0).size().width()
    sz_h = getDesktop(0).size().height()
    # percentage
    s_w = 120
    s_h = 120
    # icon
    i_w = 128
    i_h = 128
    # console
    c_w = sz_w
    c_h = 80
    # picture
    p_w = sz_w - 20
    p_h = sz_h - 20
    #######################
    #     POSITIONS
    #######################
    start_y = (sz_h - (i_h + c_h)) / 2
    # percentage
    s_x = (sz_w - s_w) / 2
    s_y = start_y + (i_h - s_h) / 2
    # icon
    i_x = (sz_w - i_w) / 2
    i_y = start_y
    # console
    c_x = 0
    c_y = i_y + i_h
    # picture
    p_x = 10
    p_y = 10

    printDBG("[IPTVPicturePlayerWidget] desktop size %dx%d" % (sz_w, sz_h))
    skin = """
        <screen name="IPTVPicturePlayerWidget"  position="center,center" size="%d,%d" title="IPTV Picture Player...">
         <widget name="status"     size="%d,%d"   position="%d,%d"  zPosition="5" valign="center" halign="center"  font="Regular;21" backgroundColor="black" transparent="1" /> #foregroundColor="white" shadowColor="black" shadowOffset="-1,-1"
         <widget name="console"    size="%d,%d"   position="%d,%d"  zPosition="5" valign="center" halign="center"  font="Regular;21" backgroundColor="black" transparent="1" />
         <widget name="icon"       size="%d,%d"   position="%d,%d"  zPosition="4" transparent="1" alphatest="on" />
         <widget name="picture"    size="%d,%d"   position="%d,%d"  zPosition="6" transparent="1" alphatest="on" />
        </screen>""" % (sz_w, sz_h,         # screen
                        s_w, s_h, s_x, s_y, # status
                        c_w, c_h, c_x, c_y, # console
                        i_w, i_h, i_x, i_y, # icon
                        p_w, p_h, p_x, p_y  # picture
                      )

    def __init__(self, session, url, pathForRecordings, pictureTitle, addParams={}):
        self.session = session
        Screen.__init__(self, session)
        self.onStartCalled = False

        self.recordingPath = pathForRecordings
        try:
            self.filePath = os.path.join(pathForRecordings, '.iptv_buffering.jpg')
        except Exception:
            self.filePath = ''
            printExc()

        self.addParams = {'seq_mode': False}
        self.addParams.update(addParams)

        self.url = url
        self.pictureTitle = pictureTitle
        self.audioUrl = strwithmeta(url).meta.get("iptv_audio_url", '')

        self["actions"] = ActionMap(['IPTVAlternateVideoPlayer', 'MoviePlayerActions', 'MediaPlayerActions', 'WizardActions', 'DirectionActions'],
        {
            'leavePlayer': self.key_exit,
            'play': self.key_play,
            'pause': self.key_pause,
            'exit': self.key_exit,
            'back': self.key_exit,
            'ok': self.key_ok,
        }, -1)

        self["status"] = Label()
        self["console"] = Label()
        self["icon"] = SimpleAnimatedCover()
        self["picture"] = Cover()

        # prepare icon frames path
        frames = []
        for idx in range(1, self.NUM_OF_ICON_FRAMES + 1):
            frames.append(GetIconDir('/buffering/buffering_%d.png' % idx))
        self["icon"].loadFrames(frames)

        #main Timer
        self.mainTimer = eTimer()
        self.mainTimerEnabled = False

        if self.addParams['seq_mode']:
            self.canAutoClose = True
            self.mainTimer_conn = eConnectCallback(self.mainTimer.timeout, self.closeAfterTimeout)
            self.mainTimerInterval = 1000 * 10 #10s
        else:
            self.mainTimer_conn = eConnectCallback(self.mainTimer.timeout, self.updateDisplay)
            self.mainTimerInterval = 100 # by default 0,1s
        # download
        self.downloader = DownloaderCreator(self.url)

        self.onClose.append(self.__onClose)
        self.onShow.append(self.doStart)
        #self.onLayoutFinish.append(self.doStart)

        self.autoRefresh = False
        self.refreshPostfixes = ['_0', '_1']
        self.refreshCount = 0
        self.refreshing = False

        if len(self.audioUrl) and len(config.plugins.iptvplayer.gstplayerpath.value):
            self.audioPlayer = IPTVSimpleAudioPlayer()
        else:
            self.audioPlayer = None

    #end def __init__(self, session):

    def __del__(self):
        printDBG('IPTVPicturePlayerWidget.__del__ --------------------------------------')

    def __onClose(self):
        printDBG('IPTVPicturePlayerWidget.__onClose ------------------------------------')
        if None != self.audioPlayer:
            self.audioPlayer.close()
        self.onEnd()
        if None != self.mainTimer:
            try:
                self.mainTimer.stop()
            except Exception:
                pass
        self.mainTimer_conn = None
        self.mainTimer = None

        self.onClose.remove(self.__onClose)
        #self.onLayoutFinish.remove(self.doStart)

    def _getDownloadFilePath(self):
        return self.filePath + self.refreshPostfixes[self.refreshCount % len(self.refreshPostfixes)]

    def closeAfterTimeout(self):
        if self.canAutoClose:
            self.close()

    def onStart(self):
        '''
            this method is called once like __init__ but in __init__ we cannot display MessageBox
        '''
        self["picture"].hide()
        self["console"].setText(self.pictureTitle)
        self["status"].setText(_("--"))
        self._cleanedUp()

        if self.url.startswith('file://'):
            self.filePath = self.url[7:]
            self["status"].setText(_("++"))
            if -1 == self["picture"].decodeCover(self.filePath, self.decodePictureEnd, ' '):
                self.decodePictureEnd()
        else:
            if self.downloader:
                self.downloader.isWorkingCorrectly(self._startDownloader)
            else:
                self.session.openWithCallback(self.close, MessageBox, _("Downloading cannot be started.\n Invalid URI[%s].") % self.url, type=MessageBox.TYPE_ERROR, timeout=10)

    def _doStart(self, force=False):
        if self.addParams['seq_mode']:
            self.mainTimer.start(self.mainTimerInterval, True) #single shot
            return
        if self.autoRefresh or force:
            self.refreshing = True
            self.downloader = DownloaderCreator(self.url)

            url, downloaderParams = DMHelper.getDownloaderParamFromUrl(self.url)
            self.downloader.subscribeFor_Finish(self.downloaderEnd)
            self.downloader.start(url, self._getDownloadFilePath(), downloaderParams)
            self.setMainTimerSts(True)
        else:
            self.refreshing = False

    def _startDownloader(self, sts, reason):
        if sts:
            self._doStart(True)
        else:
            self.session.openWithCallback(self.close, MessageBox, _("Downloading cannot be started.\n Downloader [%s] not working properly.\n Status[%s]") % (self.downloader.getName(), reason.strip()), type=MessageBox.TYPE_ERROR, timeout=10)

    def onEnd(self, withCleanUp=True):
        self.setMainTimerSts(False)
        if self.downloader:
            self.downloader.unsubscribeFor_Finish(self.downloaderEnd)
            downloader = self.downloader
            self.downloader = None
            downloader.terminate()
            downloader = None
        if withCleanUp:
            self._cleanedUp()

    def key_exit(self):
        self.close('key_exit')

    def key_play(self):
        if self.addParams['seq_mode']:
            self.canAutoClose = False
            return

        if not self.autoRefresh and not self.url.startswith('file://'):
            if None != self.audioPlayer:
                self.audioPlayer.start(self.audioUrl)
            self.autoRefresh = True
            if not self.refreshing:
                self._doStart()

    def key_pause(self):
        if self.addParams['seq_mode']:
            self.canAutoClose = False
            return
        if self.autoRefresh:
            if None != self.audioPlayer:
                self.audioPlayer.stop()
            self.autoRefresh = False

    def key_ok(self):
        if self.addParams['seq_mode']:
            self.canAutoClose = False
            return
        if self.autoRefresh:
            self.key_pause()
        else:
            self.key_play()

    def downloaderEnd(self, status):
        if None != self.downloader:
            self.onEnd(False)
            if DMHelper.STS.DOWNLOADED == status:
                self["status"].setText(_("++"))
                if -1 == self["picture"].decodeCover(self._getDownloadFilePath(), self.decodePictureEnd, ' '):
                    self.decodePictureEnd()
            else:
                if 0 == self.refreshCount:
                    self.session.openWithCallback(self.close, MessageBox, (_("Downloading file [%s] problem.") % self.url) + (" sts[%r]" % status), type=MessageBox.TYPE_ERROR, timeout=10)
                self._doStart()

    def decodePictureEnd(self, ret={}):
        printDBG('IPTVPicturePlayerWidget.decodePictureEnd')
        if None == ret.get('Pixmap', None):
            if 0 == self.refreshCount:
                self.session.openWithCallback(self.close, MessageBox, _("Decode file [%s] problem.") % self.filePath, type=MessageBox.TYPE_ERROR, timeout=10)
        else:
            self.refreshCount += 1
            self["status"].hide()
            self["console"].hide()
            self["icon"].hide()
            self["picture"].updatePixmap(ret.get('Pixmap', None), ret.get('FileName', self.filePath))
            self["picture"].show()
        self.setMainTimerSts(False)
        self._doStart()

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
            printExc("IPTVPicturePlayerWidget.setMainTimerSts status[%r] EXCEPTION" % start)

    def updateDisplay(self):
        printDBG("updateDisplay")
        if not self.mainTimerEnabled:
            printDBG("updateDisplay aborted - timer stopped")
            return
        self["icon"].nextFrame()
        return

    def _cleanedUp(self):
        for item in self.refreshPostfixes:
            filePath = self.filePath + item
            if fileExists(filePath):
                try:
                    os.remove(filePath)
                except Exception:
                    printDBG('Problem with removing old buffering file')

    def doStart(self):
        self.onShow.remove(self.doStart)
        if not self.onStartCalled:
            self.onStartCalled = True
            self.onStart()
