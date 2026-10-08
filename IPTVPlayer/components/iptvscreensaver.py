# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################

from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, eConnectCallback
from Plugins.Extensions.IPTVPlayer.components.cover import Cover

###################################################
# FOREIGN import
###################################################
from Screens.Screen import Screen
import Screens.Standby
from Components.Label import Label
from Components.config import config
from enigma import getDesktop, ePoint, eTimer, eActionMap
import os
import random
import time


def clockText():
    # the clock format of the player's info banner (12 or 24 hour)
    try:
        twelveHours = '12' == config.plugins.iptvplayer.extplayer_infobanner_clockformat.value
    except Exception:
        twelveHours = False
    return time.strftime("%I:%M %p" if twelveHours else "%H:%M")


def dateText():
    # the image's date format, else the locale's
    try:
        return time.strftime(config.usage.date.full.value)
    except Exception:
        return time.strftime("%x")


class IPTVPlayerScreenSaver(Screen):
    # Black screensaver of IPTVExtMoviePlayer (audio-only playback) and IPTVMenuScreenSaver (black mode):
    # the cover (or host logo), a title, a second text line (playback time or date) and the clock wander
    # slowly across the screen, so nothing burns in. Made by session.instantiateDialog(); it has no
    # ActionMap of its own - the owner's key hook (IPTVIdleScreenSaver.keyHook) ends it.
    # The skin is built in real pixels (scaled from 720p) because the block is moved with instance.move(),
    # which takes real pixels.
    MOVE_INTERVAL = 200  # ms

    def __init__(self, session, title, imagePaths, getTimeText):
        desktopSize = getDesktop(0).size()
        self.screenW = desktopSize.width()
        self.screenH = desktopSize.height()
        f = self.screenH / 720.0
        self.margin = int(20 * f)  # overscan of TV sets
        self.coverSize = int(160 * f)
        self.gap = int(20 * f)
        self.textW = int(420 * f)
        self.imagePath = ''
        for path in imagePaths:
            if path and os.path.isfile(path):
                self.imagePath = path
                break
        self.blockH = self.coverSize
        self.textOffsets = {'title': 0, 'time': int(76 * f), 'clock': int(106 * f)}
        self.setTextX(self.coverSize + self.gap if self.imagePath else 0)

        self.skin = """<screen name="IPTVPlayerScreenSaver" position="0,0" size="%d,%d" zPosition="15" backgroundColor="#000000" flags="wfNoBorder">
            <widget name="cover" position="0,0" size="%d,%d" zPosition="1" alphatest="blend" />
            <widget name="title" position="0,0" size="%d,%d" zPosition="1" font="Regular;%d" foregroundColor="#E0E0E0" backgroundColor="#000000" valign="top" halign="left" transparent="1" />
            <widget name="time" position="0,0" size="%d,%d" zPosition="1" font="Regular;%d" foregroundColor="#909090" backgroundColor="#000000" valign="center" halign="left" noWrap="1" transparent="1" />
            <widget name="clock" position="0,0" size="%d,%d" zPosition="1" font="Regular;%d" foregroundColor="#B0B0B0" backgroundColor="#000000" valign="center" halign="left" noWrap="1" transparent="1" />
        </screen>""" % (
            self.screenW, self.screenH,
            self.coverSize, self.coverSize,
            self.textW, int(72 * f), int(26 * f),
            self.textW, int(30 * f), int(22 * f),
            self.textW, int(54 * f), int(44 * f),
        )
        Screen.__init__(self, session)
        self['cover'] = Cover()
        self['title'] = Label(title)
        self['time'] = Label('')
        self['clock'] = Label('')
        self.getTimeText = getTimeText

        # random start position and direction - nothing security related
        step = max(1, int(round(4 * f)))
        limits = self.limits()
        self.pos = [random.randint(self.margin, limits[0]), random.randint(self.margin, limits[1])]  # NOSONAR
        self.step = [random.choice((-step, step)), random.choice((-step, step))]  # NOSONAR
        self.moveTimer = eTimer()
        self.moveTimer_conn = eConnectCallback(self.moveTimer.timeout, self.moveBlock)
        self.clockTimer = eTimer()
        self.clockTimer_conn = eConnectCallback(self.clockTimer.timeout, self.updateTexts)

        self.onLayoutFinish.append(self.layoutFinished)
        self.onShow.append(self.startTimers)
        self.onHide.append(self.stopTimers)
        self.onClose.append(self.__onClose)

    def __onClose(self):
        self.stopTimers()
        self.moveTimer_conn = None
        self.clockTimer_conn = None

    def setTextX(self, textX):
        # widget name -> offset inside the moving block
        self.blockW = textX + self.textW
        self.offsets = {'cover': (0, 0)}
        for name, offsetY in self.textOffsets.items():
            self.offsets[name] = (textX, offsetY)

    def limits(self):
        return (max(self.margin, self.screenW - self.margin - self.blockW), max(self.margin, self.screenH - self.margin - self.blockH))

    def layoutFinished(self):
        self.placeBlock()
        if not self.imagePath:
            self['cover'].hide()
            return
        try:
            if -1 == self['cover'].decodePreparedCover(self.imagePath, self.coverDecoded, 'screensaver'):
                self.noCover()
        except Exception:
            printExc()
            self.noCover()

    def coverDecoded(self, retDict):
        ptr = retDict.get('Pixmap')
        if ptr is not None:
            self['cover'].updatePixmap(ptr, retDict.get('FileName', ''))
            self['cover'].show()
        else:
            printDBG("IPTVPlayerScreenSaver cover can not be decoded [%s]" % retDict.get('FileName', ''))
            self.noCover()

    def noCover(self):
        # the texts take the place of the cover
        self['cover'].hide()
        self.setTextX(0)
        self.pos = [min(self.pos[0], self.limits()[0]), min(self.pos[1], self.limits()[1])]
        self.placeBlock()

    def startTimers(self):
        self.updateTexts()
        self.moveTimer.start(self.MOVE_INTERVAL)
        self.clockTimer.start(1000)

    def stopTimers(self):
        self.moveTimer.stop()
        self.clockTimer.stop()

    def updateTexts(self):
        self['clock'].setText(clockText())
        try:
            self['time'].setText(self.getTimeText())
        except Exception:
            printExc()

    def placeBlock(self):
        for name, (ox, oy) in self.offsets.items():
            if self[name].instance:
                self[name].instance.move(ePoint(self.pos[0] + ox, self.pos[1] + oy))

    def moveBlock(self):
        # bounces off the screen edges (inside the overscan margin)
        limits = self.limits()
        for i in (0, 1):
            self.pos[i] += self.step[i]
            if self.pos[i] <= self.margin or self.pos[i] >= limits[i]:
                self.pos[i] = min(max(self.pos[i], self.margin), limits[i])
                self.step[i] = -self.step[i]
        self.placeBlock()


class IPTVIdleScreenSaver:
    # One key hook in front of every ActionMap restarts the delay; after the delay without a key the
    # screensaver starts (activate()), and the first key only ends it - that key's later break/repeat
    # events are swallowed too. The hook stays bound while the owner lives, and the delay is read from the
    # setting every time, so switching it on or changing it needs no restart. In standby nothing starts
    # and the key that wakes the box is never swallowed.
    # Subclasses: wanted(), isActive(), activate(), deactivate(), release().

    def __init__(self, session, configItem):
        self.session = session
        self.configItem = configItem  # seconds, 0 = off
        self.swallow = False
        self.bound = False
        self.timer = eTimer()
        self.timer_conn = eConnectCallback(self.timer.timeout, self.timeout)

    def delay(self):
        try:
            return int(self.configItem.value)
        except Exception:
            return 0

    def start(self):
        if not self.bound:
            try:
                eActionMap.getInstance().bindAction('', -0x7FFFFFFF, self.keyHook)
                self.bound = True
            except Exception:
                printExc()
                return
        self.restartTimer()

    def stop(self):
        self.timer.stop()
        if self.bound:
            try:
                eActionMap.getInstance().unbindAction('', self.keyHook)
            except Exception:
                printExc()
            self.bound = False
        self.swallow = False
        self.release()

    def close(self):
        self.stop()
        self.timer_conn = None

    def restartTimer(self):
        self.timer.stop()
        delay = self.delay()
        if self.bound and delay > 0:
            self.timer.start(delay * 1000, True)

    def keyHook(self, key, flag):
        if Screens.Standby.inStandby:
            if self.isActive():
                self.deactivate()
            self.swallow = False
            return 0
        if self.isActive():
            self.deactivate()
            self.swallow = True
            return 1
        if self.swallow:
            if 1 == flag:  # break of the key that ended the screensaver
                self.swallow = False
            return 1
        self.restartTimer()
        return 0

    def timeout(self):
        if Screens.Standby.inStandby or not self.wanted():
            self.restartTimer()
            return
        try:
            self.activate()
        except Exception:
            printExc()

    def wanted(self):
        return True

    def isActive(self):
        return False

    def activate(self):
        pass

    def deactivate(self):
        self.restartTimer()

    def release(self):
        self.deactivate()


class IPTVAudioScreenSaver(IPTVIdleScreenSaver):
    # IPTVExtMoviePlayer over audio-only playback (radio, music): the black IPTVPlayerScreenSaver with the
    # cover and the playback time; the player decides when it is wanted (_screenSaverWanted)

    def __init__(self, player, imagePaths):
        IPTVIdleScreenSaver.__init__(self, player.session, config.plugins.iptvplayer.screensaver_audio)
        self.player = player
        self.imagePaths = imagePaths
        self.dialog = None

    def wanted(self):
        return self.player._screenSaverWanted()

    def isActive(self):
        return self.dialog is not None and self.dialog.shown

    def activate(self):
        if self.dialog is None:
            self.dialog = self.session.instantiateDialog(IPTVPlayerScreenSaver, self.player.title, self.imagePaths, self.player._screenSaverTimeText)
        self.dialog.show()

    def deactivate(self):
        if self.isActive():
            self.dialog.hide()
        self.restartTimer()

    def release(self):
        if self.dialog is not None:
            try:
                self.dialog.hide()
                self.session.deleteDialog(self.dialog)
            except Exception:
                printExc()
            self.dialog = None


class IPTVMenuScreenSaver(IPTVIdleScreenSaver):
    # Idle screensaver for every E2iPlayer screen - the main E2iPlayerWidget (owner, bottom of all of them)
    # and whatever is opened above it (host selector, config, download manager, info view, messages ...).
    # The players are left out, IPTVExtMoviePlayer has its own audio-only screensaver.
    # Mode "hide" (only while live TV runs behind E2iPlayer): the E2iPlayer windows are hidden, otherwise
    # the black IPTVPlayerScreenSaver. A screen opened or closed meanwhile (playback started from the web
    # interface, a message with timeout) ends it.
    PLAYER_SCREENS = ('IPTVExtMoviePlayer', 'IPTVMiniMoviePlayer', 'IPTVStandardMoviePlayer', 'IPTVPicturePlayerWidget', 'E2iPlayerBufferingWidget')

    def __init__(self, session, owner, getInfo):
        # getInfo() -> (title, [image paths]) for the black screensaver
        IPTVIdleScreenSaver.__init__(self, session, config.plugins.iptvplayer.screensaver_menu)
        self.owner = owner
        self.getInfo = getInfo
        self.dialog = None
        self.hiddenScreens = []
        self.topScreen = None
        self.watchTimer = eTimer()
        self.watchTimer_conn = eConnectCallback(self.watchTimer.timeout, self.watch)

    def close(self):
        IPTVIdleScreenSaver.close(self)
        self.watchTimer_conn = None

    def isActive(self):
        return self.dialog is not None or len(self.hiddenScreens) > 0

    def _stackScreens(self):
        screens = [item[0] for item in getattr(self.session, 'dialog_stack', [])]
        if self.session.current_dialog is not None:
            screens.append(self.session.current_dialog)
        return screens

    def _e2iScreens(self):
        # the owner and every screen above it, as long as no player is among them
        screens = self._stackScreens()
        if self.owner not in screens:
            return []
        screens = screens[screens.index(self.owner):]
        for screen in screens:
            if screen.__class__.__name__ in self.PLAYER_SCREENS:
                return []
        return screens

    def _liveTvRunning(self):
        try:
            return self.session.nav.getCurrentlyPlayingServiceReference() is not None
        except Exception:
            printExc()
            return False

    def wanted(self):
        return len(self._e2iScreens()) > 0

    def activate(self):
        self.topScreen = self.session.current_dialog
        if 'hide' == config.plugins.iptvplayer.screensaver_menu_mode.value and self._liveTvRunning():
            for screen in self._e2iScreens():
                if screen.shown:
                    screen.hide()
                    self.hiddenScreens.append(screen)
        else:
            title, imagePaths = self.getInfo()
            self.dialog = self.session.instantiateDialog(IPTVPlayerScreenSaver, title, imagePaths, dateText)
            self.dialog.show()
        self.watchTimer.start(1000)

    def watch(self):
        if self.session.current_dialog is not self.topScreen:
            self.deactivate()

    def deactivate(self):
        self.watchTimer.stop()
        self.topScreen = None
        if self.dialog is not None:
            try:
                self.dialog.hide()
                self.session.deleteDialog(self.dialog)
            except Exception:
                printExc()
            self.dialog = None
        if self.hiddenScreens:
            # the screen on top is shown again now; one that is lower in the stack meanwhile (something was
            # opened above it) is shown again by Enigma2 when it gets on top - a closed one is gone
            stack = getattr(self.session, 'dialog_stack', [])
            for screen in self.hiddenScreens:
                try:
                    if screen is self.session.current_dialog:
                        screen.show()
                    else:
                        for idx, item in enumerate(stack):
                            if item[0] is screen:
                                stack[idx] = (screen, True)
                except Exception:
                    printExc()
            self.hiddenScreens = []
        self.restartTimer()
