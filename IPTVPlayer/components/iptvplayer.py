from Screens.Screen import Screen
from Screens.InfoBarGenerics import InfoBarSeek, InfoBarAudioSelection, InfoBarNotifications, InfoBarSubtitleSupport, InfoBarShowHide
   

from Screens.HelpMenu import HelpableScreen
from Components.ActionMap import HelpableActionMap
from Components.config import config
from Components.AVSwitch import eAVSwitch
from Screens.ChoiceBox import ChoiceBox
from Components.ServiceEventTracker import ServiceEventTracker
from enigma import iPlayableService, eTimer
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, eConnectCallback


class customMoviePlayer(InfoBarShowHide, InfoBarSeek, InfoBarAudioSelection, InfoBarSubtitleSupport, HelpableScreen, InfoBarNotifications, Screen):

    STATE_IDLE = 0
    STATE_PLAYING = 1
    STATE_PAUSED = 2
    ENABLE_RESUME_SUPPORT = True
    ALLOW_SUSPEND = True
    
    def __init__(self, session, service, lastPosition=None, bugEOFworkaround=0):
        Screen.__init__(self, session)
        self.skinName = "MoviePlayer"
        
        self.__event_tracker = ServiceEventTracker(screen=self, eventmap={
                iPlayableService.evEOF: self.__evEOF,
                iPlayableService.evSOF: self.__evEOF,
            })
        self["actions"] = HelpableActionMap(self, "MoviePlayerActions",
            {
                "leavePlayer": (self.leavePlayer, _("leave movie player...")),
                "leavePlayerOnExit": (self.leavePlayer, _("leave movie player...")),
            }, -5)
        
        for x in HelpableScreen, InfoBarShowHide, InfoBarSeek, InfoBarAudioSelection, InfoBarSubtitleSupport, InfoBarNotifications:
            x.__init__(self)
            
        # InfoBarServiceNotifications
                    
        self.onClose.append(self.__onClose)
        self.mainTimer = eTimer()
        self.mainTimer_conn = eConnectCallback(self.mainTimer.timeout, self.timerCallBack)
        self.mainTimer.start(1000)
        self.bugEOFworkaround = bugEOFworkaround
        
        self.session.nav.playService(service)
        if lastPosition != None and (lastPosition / 90000) > 10:
            self.position = 0
            self.lastPosition = lastPosition
            self.doSeekToLastPosition = True
        else:
            self.position = 0  
            self.lastPosition = 0
            self.doSeekToLastPosition = False
        self.waitForSeekToLastPosition = 0
        self.stopTimeFix = 0

        self.returning = False
        self.aspectratiomode = "1"
        self.isClosing = False
        
    def getPosition(self):
        time = 0
        length = 0
        service = self.session.nav.getCurrentService()
        seek = service and service.seek()
        if seek != None:
            r = seek.getLength()
            if not r[0]:
                length = r[1]
            r = seek.getPlayPosition()
            if not r[0]:
                time = r[1] #float(float(r[1]) / float(90000))
        return time, length
        
    def doSeekRelative(self, pts):
        printDBG("doSeekRelative pts[%r]" % pts)
        InfoBarSeek.doSeekRelative(self, pts)
        self.waitForSeekToLastPosition = -1
    
    def timerCallBack(self):
        try:
            position, length = self.getPosition()
            if self.doSeekToLastPosition and self.seekstate == self.SEEK_STATE_PLAY:
                printDBG("timerCallBack doSeekToLastPosition[%r]" % self.lastPosition)
                # not sure why but riginal MP doSeek method does nothing, so I use on seeking only doSeekRelative
                self.doSeekRelative(self.lastPosition - position)
                self.doSeekToLastPosition = False
                self.stopTimeFix = 0
                self.lastPosition = 0
                return
                
            if -1 == self.waitForSeekToLastPosition:
                if position > 0:
                    self.waitForSeekToLastPosition = position
                printDBG('________waitForSeekToLastPosition position[%r]' % (position))
                return
            printDBG('________timerCallBack position [%r], length[%r], seekstate[%r]' % (position, length, self.seekstate))
            if self.waitForSeekToLastPosition > 0 and self.waitForSeekToLastPosition >= position:
                return
            self.waitForSeekToLastPosition = 0
            if self.bugEOFworkaround == 0 or position == 0 or self.seekstate != self.SEEK_STATE_PLAY:
                return #== self.SEEK_STATE_PAUSE: return
            self.lastPosition = position
        except Exception:
            printExc()
            return

        if position != self.position:
            self.position = position
            self.stopTimeFix = 0
        else:
            self.stopTimeFix += 1
        if self.stopTimeFix >= self.bugEOFworkaround:
            self.mainTimer.stop()
            self.leavePlayer(True)
    
    def aspectChange(self):
        printDBG("Aspect Ratio [%r]" % self.aspectratiomode)
        if self.aspectratiomode == "1": #letterbox
            eAVSwitch.getInstance().setAspectRatio(0)
            self.aspectratiomode = "2"
            return
        elif self.aspectratiomode == "2": #nonlinear
            self.aspectratiomode = "3"
        elif self.aspectratiomode == "3": #nonlinear
            eAVSwitch.getInstance().setAspectRatio(2)
            self.aspectratiomode = "4"
        elif self.aspectratiomode == "4": #panscan
            eAVSwitch.getInstance().setAspectRatio(3)
            self.aspectratiomode = "1"
        
    def pauseBeforeClose(self):
        printDBG("pauseBeforeClose")
        service = self.session.nav.getCurrentService()
        if service is None:
            printDBG("No Service found")
            return False
        pauseable = service.pause()
        if pauseable is None:
            printDBG("not pauseable.")
        else:
            printDBG("pausable")
            pauseable.pause()
        return True
        
    def leavePlayer(self, endFile=False):
        printDBG("customMoviePlayer.leavePlayer isClosing[%r], endFile[%r]" % (self.isClosing, endFile))
        if False == self.isClosing:
            self.pauseBeforeClose()
            if endFile:
                self._doClose(None)
            else:
                self._doClose('key_stop')

    def doEofInternal(self, playing):
        printDBG("--- eofint movieplayer ---")
        self.leavePlayer(True)
        
    def _doClose(self, sts):
        printDBG("_doClose sts[%r], lastPosition[%r]" % (sts, self.lastPosition))
        try:
            self.hide()
            self.isClosing = True
            self.onShow = []
            self.onHide = []
            self.hideTimer.stop()
        except Exception:
            printExc(customMoviePlayer._doClose)
        self.close(sts, self.lastPosition)
        
    def __evEOF(self):
        printDBG("evEOF=%d" % iPlayableService.evEOF)
        self.leavePlayer(True)
        
    def __onClose(self):
        printDBG("customMoviePlayer.__onClose")
        self.mainTimer.stop()
        self.mainTimer_conn = None
        self.onClose.remove(self.__onClose)
        
    def show(self):
        if False == self.isClosing:
            Screen.show(self)
        else:
            printExc("customMoviePlayer.show")
            
    def doShow(self):
        if False == self.isClosing:
            InfoBarShowHide.doShow(self)
        else:
            printExc("customMoviePlayer.doShow")
    
    def openEventView(self, *args, **kwargs):
        pass
        

#####################################################
# movie player by j00zek
#####################################################
from Screens.InfoBar import MoviePlayer as standardMoviePlayer
from enigma import eServiceReference


class IPTVStandardMoviePlayer(standardMoviePlayer):
    def __init__(self, session, uri, title):
        self.session = session
        self.WithoutStopClose = True
        #if '://' not in uri: uri = 'file://' + uri
        fileRef = eServiceReference(4097, 0, uri)
        fileRef.setName(title)

        standardMoviePlayer.__init__(self, self.session, fileRef)
        self.skinName = "MoviePlayer"
        standardMoviePlayer.skinName = "MoviePlayer"
        self.e2iplayerEOF = False

    def doEofInternal(self, *args, **kwargs):
        if (args and args[0]) or kwargs.get('playing', False):
            self.e2iplayerEOF = True
        standardMoviePlayer.doEofInternal(self, *args, **kwargs)

    def close(self, *args, **kwargs):
        if self.e2iplayerEOF:
            standardMoviePlayer.close(self, *args, **kwargs)
        else:
            standardMoviePlayer.close(self, 'key_exit')


class IPTVMiniMoviePlayer(customMoviePlayer):
    def __init__(self, session, uri, title, lastPosition=None, bugEOFworkaround=0):
        self.session = session
        self.WithoutStopClose = True
        #if '://' not in uri: uri = 'file://' + uri
        fileRef = eServiceReference(4097, 0, uri)
        fileRef.setName(title)
        customMoviePlayer.__init__(self, self.session, fileRef, lastPosition, bugEOFworkaround)
#####################################################
