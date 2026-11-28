# -*- coding: utf-8 -*-
# Last Modified: 2026-11-02 - LCD skins get remaining minutes and times without seconds; playback tells
#              other plugins whether the player is open, the title, the cover and whether it is live.
# 2026-11-01 - INFO shows a panel over the running video (iptvplayerinfopanel.py).
# 2026-10-31 - colour front displays (LCD) show title, progress bar and times during playback;
#              the same screen serves the buffering screen and the download manager.
# 2026-10-28 - a remembered subtitle file that is gone (put into the MKV by the download manager) is
#              dropped without an error message, the search next to the video runs instead.
# 2026-10-25 - image subtitles (PGS / DVB / XSUB) of exteplayer3 with the exteplayer3png.so plugin.
#            - DASH links of getMPDLinksWithMeta (iptv_dash_sel) play the local filtered MPD of libs/dashmpd.py
#              (only the chosen video / audio); exteplayer3's -0 / -1 needed an ffmpeg patch OE-A dropped.
# 2026-10-17 - buffering: the skip keys stop at the end of the part downloaded so far (bufferedEnd()), the
#              watched mark takes the clip length only from a finished download.
# 2026-10-12 - a downloaded file also finds its subtitles saved as name.de.srt (box language, then English).
# 2026-07-26 Updated to ignore non-subtitle sidecar text files during automatic subtitle detection
# and to safely handle PLAYBACK_STOP when the exteplayer3 control socket is already gone. - Kamikaze24
#
#  IPTVExtMoviePlayer
#
#  $Id$
#
#

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper
from Plugins.Extensions.IPTVPlayer.iptvdm.downloaderhelpers import shellQuote, subtitleSidecarFiles
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.components.cover import Cover, Cover3
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetSubtitlesDir, eConnectCallback, \
                                                          GetE2VideoAspectChoices, GetE2VideoAspect, SetE2VideoAspect, GetE2VideoPolicyChoices, \
                                                          GetE2VideoPolicy, SetE2VideoPolicy, GetDefaultLang, GetPolishSubEncoding, iptv_system, \
                                                          GetE2AudioCodecMixOption, SetE2AudioCodecMixOption, CreateTmpFile, GetTmpDir, IsExecutable, GetGstIfdSrc, GetGstPlayerPath, MapUcharEncoding, \
                                                          GetE2VideoModeChoices, GetE2VideoMode, SetE2VideoMode, GetPlayerSkinDir, GetNice, E2PrioFix, \
                                                          StripColorCodes, mkdirs, ExtePlayer3Cap, ExtePlayer3Version, EXTEPLAYER3_PATH
from Plugins.Extensions.IPTVPlayer.tools.iptvsubtitles import IPTVSubtitlesHandler, IPTVEmbeddedSubtitlesHandler, IPTVGraphicSubtitlesHandler
from Plugins.Extensions.IPTVPlayer.tools.iptvmoviemetadata import IPTVMovieMetaDataHandler
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.iptvsubdownloader import IPTVSubDownloaderWidget
from Plugins.Extensions.IPTVPlayer.components.iptvsubsimpledownloader import IPTVSubSimpleDownloaderWidget
from Plugins.Extensions.IPTVPlayer.components.iptvchoicebox import IPTVChoiceBoxWidget, IPTVChoiceBoxItem
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinfopanel import PlayerInfoPanel, BANNER_PICTURE, makeBannerPicture, audioFormatText, audioText, badgeList, hostDisplayName, nowPlayingText, playerErrorHint, streamBitrate, stripTexts, subtitleFormatName, CHAPTERS_PROBE_CMD
from Plugins.Extensions.IPTVPlayer.components.iptvlist import IPTVPlaylistChoiceBoxList
from Plugins.Extensions.IPTVPlayer.components.iptvscreensaver import clockStrftime
from Plugins.Extensions.IPTVPlayer.components.iptvbackdrop import BackdropLoader, backdropMode, backdropOnPause
from Plugins.Extensions.IPTVPlayer.tools import listselection
from Plugins.Extensions.IPTVPlayer.components.iptvdirbrowser import IPTVFileSelectorWidget
from Plugins.Extensions.IPTVPlayer.components.configextmovieplayer import ConfigExtMoviePlayerBase, ConfigExtMoviePlayer
from Plugins.Extensions.IPTVPlayer.components.iptvlcd import IPTVExtMoviePlayerColorSummary, IPTVExtMoviePlayerSummary, addLcdSources, isLargeLcd, lcdTimeHM
from Plugins.Extensions.IPTVPlayer.components import skinchrome
from Plugins.Extensions.IPTVPlayer.libs.pCommon import CParsingHelper
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
from Plugins.Extensions.IPTVPlayer.libs import dashmpd
from Plugins.Extensions.IPTVPlayer.libs.subtitlesmatch import langCode, langName
from Plugins.Extensions.IPTVPlayer.libs.chapters import parseChapters, chapterIndexAt, chapterLabel, formatTime
from Plugins.Extensions.IPTVPlayer.components.ihost import ArticleContent
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str

# FOREIGN import
from enigma import eConsoleAppContainer, getDesktop, eTimer, eLabel, gFont, ePoint, eSize, gRGB
from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.config import config
from Components.Label import Label
from Components.ProgressBar import ProgressBar

from Screens.MessageBox import MessageBox
from Tools.LoadPixmap import LoadPixmap
from Tools.BoundFunction import boundFunction
from Tools.Directories import fileExists
from skin import parseColor

from datetime import timedelta
try:
    from math import floor, fabs
except Exception:
    printExc()

from os import path as os_path, rename as os_rename, stat as os_stat, listdir as os_listdir, remove as os_remove
import re
import threading
import time
import json
try:
    from PIL import Image, ImageDraw
except ImportError:
    Image = ImageDraw = None

###################################################

# exteplayer3 saves image subtitles (PGS / DVB / XSUB) as PNG files with -G <directory>, through the
# exteplayer3png.so plugin of e2iplayer-deps (dlopen, found in the library path); without -G it does not
# even list those tracks. Builds that do not know -G stop at the unknown option, so the getopt string
# (the one with "9:", the subtitle track option) is looked up in the binary first. The OE-A feed packs
# exteplayer3 with UPX on 32-bit boxes, the string is not readable then - those builds are recent and
# know -G (it came with the graphic subtitles in 2019).
EXTEPLAYER3PNG_PATHS = ['/usr/lib/exteplayer3png.so', '/lib/exteplayer3png.so']
graphicSubsCache = (None, False)


def LoadPlayerMessage(item):
    # one status line of the player as JSON. exteplayer3 cuts its PLAYBACK_OPEN message at about 2 KB (the url of a
    # Pluto TV stream is longer) and puts that unclosed text in front of every later message: the message is then
    # the first '{"' from which the rest of the line is valid JSON
    try:
        return json.loads(item)
    except ValueError:
        pos = item.find('{"', 1)
        while pos > 0:
            try:
                return json.loads(item[pos:])
            except ValueError:
                pos = item.find('{"', pos + 1)
        raise


def GraphicSubtitlesSupported(exteplayer3path):
    global graphicSubsCache
    if not any(os_path.isfile(path) for path in EXTEPLAYER3PNG_PATHS):
        return False
    try:
        st = os_stat(exteplayer3path)
        key = (exteplayer3path, st.st_mtime, st.st_size)
        if key != graphicSubsCache[0]:
            with open(exteplayer3path, 'rb') as f:
                data = f.read()
            if b'UPX!' in data[:4096]:
                supported, how = True, 'UPX packed'
            else:
                supported = any(b'G:' in opts for opts in re.findall(b'[0-9A-Za-z:]{20,}', data) if b'9:' in opts)
                how = 'getopt string'
            graphicSubsCache = (key, supported)
            printDBG("exteplayer3: image subtitles supported[%s] (%s)" % (supported, how))
        return graphicSubsCache[1]
    except Exception:
        printExc()
    return False


class ExtPlayerCommandsDispatcher():
    def __init__(self, owner):
        self.owner = owner

        # SEEK_SPEED_MAP = [0.125, 0.25, 0.5, 0, 2, 4, 8, 16, 32, 64, 128]
        self.SEEK_SPEED_MAP = []
        for item in reversed(config.seek.speeds_slowmotion.value):
            self.SEEK_SPEED_MAP.append(1.0 / float(item))
        self.SEEK_SPEED_MAP.append(0)
        for item in config.seek.speeds_forward.value:
            self.SEEK_SPEED_MAP.append(item)
        self.speedIdx = self.SEEK_SPEED_MAP.index(0)

    def doAddTriggers(self, arg):
        self.extPlayerSendCommand('ADD_TRIGGERS', arg)

    def stop(self):
        if self.extPlayerSendCommand('PLAYBACK_STOP'):
            self.owner = None
            return True
        return False

    def play(self):
        self.extPlayerSendCommand('PLAYBACK_CONTINUE')
        self.speedIdx = self.SEEK_SPEED_MAP.index(0)

    def pause(self):
        self.extPlayerSendCommand('PLAYBACK_PAUSE')
        self.speedIdx = self.SEEK_SPEED_MAP.index(0)

    def setAudioTrack(self, id):
        self.extPlayerSendCommand('PLAYBACK_SET_AUDIO_TRACK', id, False)

    def setSubtitleTrack(self, id):
        self.extPlayerSendCommand('PLAYBACK_SET_SUBTITLE_TRACK', id, False)

    def setForcedSubtitlesOnly(self, on):
        # exteplayer3 "forcedonly": so1 only the forced cues, so0 all of them
        self.extPlayerSendCommand('PLAYBACK_SET_FORCED_ONLY', 1 if on else 0, False)

    def setAudioChannel(self, channel):
        # exteplayer3 "achannel": dual mono 0 left, 1 stereo, 2 right
        self.extPlayerSendCommand('PLAYBACK_SET_AUDIO_CHANNEL', channel, False)

    def setDownloadFileTimeout(self, timeout):
        self.extPlayerSendCommand('PLAYBACK_SET_DOWNLOAD_FILE_TIMEOUT', timeout, False)

    def setProgressiveDownload(self, flag):
        self.extPlayerSendCommand('PLAYBACK_SET_PROGRESSIVE_DOWNLOAD', flag, False)

    def setLoopMode(self, value):
        self.extPlayerSendCommand('PLAYBACK_SET_LOOP_MODE', value, False)

    def doSeek(self, diff):
        self.extPlayerSendCommand('PLAYBACK_SEEK_RELATIVE', '%d' % diff)
        self.speedIdx = self.SEEK_SPEED_MAP.index(0)

    def doGoToSeek(self, arg):
        self.extPlayerSendCommand('PLAYBACK_SEEK_ABS', arg)
        self.speedIdx = self.SEEK_SPEED_MAP.index(0)

    def doSeekFwd(self, arg):
        self.extPlayerSendCommand('PLAYBACK_FASTFORWARD', arg)

    def doSlowMotion(self, arg):
        self.extPlayerSendCommand('PLAYBACK_SLOWMOTION', arg)

    def doUpdateInfo(self):
        self.extPlayerSendCommand('PLAYBACK_LENGTH', '', False)
        self.extPlayerSendCommand('PLAYBACK_CURRENT_TIME', '', False)

    def seekFwd(self):
        printDBG('seekFwd skipped')
        return
        self.speedIdx += 1
        self.tipMode()

    def seekBack(self):
        printDBG('seekBack skipped')
        return
        self.speedIdx -= 1
        self.tipMode()

    def tipMode(self):
        printDBG("ExtPlayerCommandsDispatcher.tipMode speedIdx[%d]" % self.speedIdx)
        if self.speedIdx >= len(self.SEEK_SPEED_MAP):
            self.speedIdx = len(self.SEEK_SPEED_MAP) - 1
        elif self.speedIdx < 0:
            self.speedIdx = 0
        val = self.SEEK_SPEED_MAP[self.speedIdx]
        printDBG("ExtPlayerCommandsDispatcher.tipMode val[%r]" % val)
        if 0 == val:
            self.play()
        elif 1 < val:
            if 'eplayer' == self.owner.player:
                val -= 1
            self.doSeekFwd(str(val))
        else:
            self.doSlowMotion(str(int(1.0 / val)))

    def extPlayerSendCommand(self, cmd, arg='', getStatus=True):
        ret = False
        if None is not self.owner:
            try:
                ret = self.owner.extPlayerSendCommand(cmd, arg)
            except Exception:
                printExc()
                if 'PLAYBACK_STOP' == cmd:
                    return False
                if getStatus:
                    self.owner = None
                    return False
        else:
            printDBG(">> extPlayerSendCommand owner NONE")
            return False

        if getStatus and None is not self.owner:
            try:
                self.owner.extPlayerSendCommand("PLAYBACK_INFO", '')
            except Exception:
                printExc()
                self.owner = None
        return ret


class IPTVExtMoviePlayer(Screen):
    NON_SUBTITLE_SIDE_EXTENSIONS = ['txt', 'sub', 'srt', 'vtt']

    Y_CROPPING_GUARD = 0
    playback = {}
    # every playerskins/*/playerskin.xml (bar "sd") is authored for this
    # canvas - see resolution="1280,720" on their <screen> tags
    REF_W = 1280
    REF_H = 720
    # startCover on the 1280x720 canvas: a 2:3 poster box in the middle, above the infobar; and the longest time it stays
    START_COVER_BOX = (500, 130, 280, 420)
    START_COVER_TIMEOUT = 60  # s
    # audioCover (setting "Poster during audio playback") on the 1280x720 canvas: in the middle above the highest
    # infobar, or the whole screen; the picture keeps its aspect ratio in the box
    AUDIO_COVER_BOXES = {'small': (440, 90, 400, 400), 'full': (0, 0, 1280, 720)}
    # the song of a radio stream: one line above the small poster (over the full one at its top)
    AUDIO_COVER_TEXT_BOX = (40, 38, 1200, 44)
    AUDIO_COVER_TEXT_FONT = 28
    # how long a stream may play before it counts as audio only: exteplayer3 reports the video track a moment after
    # the start
    AUDIO_COVER_DELAY = 1500  # ms
    # the optional widgets of a player skin's infobar ("modern"), each only where the skin declares it:
    # - infoBarPoster: the title's picture; infoBarPosterMask: a picture of the skin over it (rounded corners, frame)
    # - infoBarBadgeN: the badges of the formats, each as wide as its text, infoBarBadge1 the resolution class, the
    #   others the rest in their order; infoBarBadgeNFrame: a label behind it as its border (the badge label lies
    #   inside it, its distance to the frame is the border width), infoBarBadgeNSub: the small line under it
    # - infoBarMeta: host, length and what the host's INFO page said (year, genre)
    # - infoBarStripNKey / infoBarStripNValue: the info row (video, video codec, audio, audio codec, subtitles), the
    #   value right after its label
    # - infoBarProgressKnob: a picture of the skin (playback_knob.png) at the playback position on progressBar
    INFOBAR_POSTER = 'infoBarPoster'
    INFOBAR_POSTER_MASK = 'infoBarPosterMask'
    INFOBAR_BADGES = tuple('infoBarBadge%d' % idx for idx in range(1, 10))
    INFOBAR_BADGE_PARTS = tuple(name + part for name in INFOBAR_BADGES for part in ('Frame', 'Sub'))
    INFOBAR_META = 'infoBarMeta'
    INFOBAR_STRIP = tuple('infoBarStrip%d%s' % (idx, part) for idx in range(1, 6) for part in ('Key', 'Value'))
    INFOBAR_KNOB = 'infoBarProgressKnob'
    # the rating of the host's page beside the title ("IMDb 7.2")
    INFOBAR_RATING = 'infoBarRating'
    # the symbols of the info row, each hidden with its empty column (infobar_strip%d.png of the skin)
    INFOBAR_STRIP_ICONS = tuple('infoBarStrip%dIcon' % idx for idx in range(1, 6))
    INFOBAR_OPTIONAL = ((INFOBAR_POSTER, INFOBAR_POSTER_MASK) + INFOBAR_BADGES + INFOBAR_BADGE_PARTS + (INFOBAR_META, INFOBAR_RATING) + INFOBAR_STRIP
                        + INFOBAR_STRIP_ICONS + (INFOBAR_KNOB,))
    # rectangles of one image subtitle (MAX_RECT_DESC in exteplayer3's graphic_subtitle.c)
    GRAPHIC_SUB_RECTS = 4
    # track keys of a newer exteplayer3 kept by _mapTrack: c, d, t (v186), the track info for front ends
    TRACK_INFO_KEYS = ('c', 'd', 't', 'sr', 'br', 'cl', 'bps', 'hdr', 'pr', 'bd', 'dv', 'cr')

    # theme -> (progress, cbuff, buff) bar image in playerskins/_scaled/,
    # shipped as <name>_1920.png/<name>_2560.png - see
    # _progressBarPixmapPath(). The themes share only 7 different bar
    # images, so the scaled copies live in one folder. A new theme needs
    # an entry here (or falls back to its own unscaled images).
    SCALED_BAR_IMAGES = {
        'default': ('blue', 'dark_green', 'dark_blue'),
        'black': ('wide_red', 'wide_light_blue', 'wide_red'),
        'red': ('wide_red', 'wide_light_blue', 'wide_red'),
        'blue': ('wide_light_blue', 'wide_red', 'wide_red'),
        'green': ('dark_green', 'gradient_green_red', 'gradient_red_green'),
        'black-white': ('gradient_green_red', 'dark_green', 'gradient_red_green'),
        'cobalt': ('blue', 'dark_green', 'gradient_red_green'),
        'jersey': ('gradient_green_red', 'dark_green', 'gradient_red_green'),
        'navy': ('blue', 'dark_green', 'gradient_red_green'),
        'line': ('gradient_green_red', 'dark_green', 'gradient_red_green'),
    }

    def __prepareSkin(self):
        # REF_W/REF_H: every playerskins/*/playerskin.xml (and the inline
        # fallback below) declares its widgets for a fixed 1280x720
        # canvas; resolution="1280,720" on every non-"sd" theme's
        # <screen> tag makes Enigma2 scale all of that automatically for
        # FHD/WQHD - initGuiComponentsPos()'s own runtime centering (reads
        # back the already-scaled widget sizes) and subSynchroIcon's
        # centering already cooperate with this correctly since they read
        # real instance sizes at runtime. The <screen> tag's own size= is
        # such a reference-canvas value too (REF_W x REF_H, not the desktop
        # size) - see the skin % (...) call below.
        #
        # The subLabel widgets declared below are only ever visible for
        # the brief instant before the first real subtitle line arrives -
        # setSubtitlesText() (see its own comment) immediately re-resizes/
        # re-positions them itself using real desktop pixels
        # directly via .instance.move()/.resize(), which never goes
        # through Enigma2's skin-level resolution= scaling at all (that
        # only applies to attributes declared in the skin XML/string, not
        # later plain Python calls) - so this initial declaration doesn't
        # need to be pixel-perfect, just reasonable, and is kept in
        # 1280x720-reference terms like everything else here for
        # consistency.
        REF_W, REF_H = self.REF_W, self.REF_H
        dw = getDesktop(0).size().width()

        if self.subConfig['wrapping_enabled']:
            self.subLinesNum = 1
        else:
            self.subLinesNum = 4

        sub = self.subConfig
        if self.subLinesNum > 1 or 'transparent' != self.subConfig['background']:
            valign = "center"
        else:
            valign = sub['box_valign']
        subSkinPart = ' valign="%s" foregroundColor="%s" font="%s;%s" ' % (valign, sub['font_color'], sub['font'], sub['font_size'])
        if 'border' in sub:
            subSkinPart += ' borderColor="%s" borderWidth="%s" ' % (sub['border']['color'], sub['border']['width'])
        if 'shadow' in sub:
            subSkinPart += ' shadowColor="%s" shadowOffset="%s,%s" ' % (sub['shadow']['color'], sub['shadow']['xoffset'], sub['shadow']['yoffset'])
        subSkinPart += ' backgroundColor="%s" ' % (sub['background'])

        if self.subLinesNum > 1:
            subSkinPart += ' noWrap="1" '

        # placeholder-only geometry (see class comment above) - kept in
        # reference-space terms for consistency, actual position/size on
        # screen comes from setSubtitlesText() instead
        subX = 10
        subY = REF_H - sub['pos'] - sub['box_height']
        subW = REF_W - 20
        subBoxH = sub['box_height']
        subSkinPart = '<widget name="subLabel{0}" position="%d,%d" size="%d,%d" zPosition="1" halign="center" %s/>' % (subX, subY, subW, subBoxH, subSkinPart)
        subSkin = ''
        for idx in range(self.subLinesNum):
            subSkin += subSkinPart.format(idx + 1)
        # image subtitles: placed and sized in real pixels by updateGraphicSubtitles()
        for idx in range(self.GRAPHIC_SUB_RECTS):
            subSkin += '<widget name="subGraphic%d" position="0,0" size="1,1" zPosition="1" transparent="1" alphatest="blend" />' % (idx + 1)

        self.playbackBannerFile = "playback_banner.png"

        if dw < 800:
            # skin for SD
            self.playerSkinFolder = GetPlayerSkinDir('sd')
        else:
            self.playerSkinFolder = GetPlayerSkinDir(ConfigExtMoviePlayerBase().getPlayerSkinFolder())

        self.playerSkinPath = self.playerSkinFolder + "/playerskin.xml"

        printDBG("Player skin folder:" + self.playerSkinFolder)
        printDBG("Player skin file path:" + self.playerSkinPath)

        if os_path.exists(self.playerSkinPath):
            # read player skin xml file
            skinFile = open(self.playerSkinPath, 'r')
            skin = skinFile.read()
            skinFile.close()

            # printDBG("---------------------------------------")
            # printDBG(skin)
            # printDBG("---------------------------------------")
        else:
            skin = ""

        if len(skin) == 0:
            # use default skin in code
            skin = """
            <screen name="IPTVExtMoviePlayer"    position="center,center" size="%d,%d" resolution="1280,720" flags="wfNoBorder" backgroundColor="#FFFFFFFF" >
                    <widget name="pleaseWait"         noWrap="1" position="30,30"        size="500,36"    zPosition="3" transparent="0" foregroundColor="#E0E0E0"   backgroundColor="#40000000" font="Regular;24" halign="center"  valign="center"/>

                    <widget name="logoIcon"           position="140,30"        size="160,40"    zPosition="4"             transparent="1" alphatest="blend" />
                    <widget name="playbackInfoBaner"  position="0,0"           size="1280,177"  zPosition="2" pixmap="%s" />
                    <widget name="progressBar"        position="220,86"        size="840,7"     zPosition="5" pixmap="%s" transparent="1" borderWidth="1" borderColor="#888888" />
                    <widget name="bufferingCBar"      position="220,86"        size="840,7"     zPosition="4" pixmap="%s" transparent="1" borderWidth="1" borderColor="#888888" />
                    <widget name="bufferingBar"       position="220,86"        size="840,7"     zPosition="3" pixmap="%s" borderWidth="1" borderColor="#888888" />
                    <widget name="statusIcon"         position="150,70"        size="40,40"     zPosition="4"             transparent="1" alphatest="blend" />
                    <widget name="loopIcon"           position="150,110"       size="40,21"     zPosition="4"             transparent="1" alphatest="blend" />

                    <widget name="goToSeekPointer"    position="94,30"          size="150,60"  zPosition="8" pixmap="%s" transparent="1" alphatest="blend" />
                    <widget name="goToSeekLabel"      noWrap="1" position="94,30"         size="150,40"   zPosition="9" transparent="1" foregroundColor="white"     backgroundColor="#251f1f1f" font="Regular;24" halign="center" valign="center"/>
                    <widget name="infoBarTitle"       noWrap="1" position="220,50"        size="840,30"   zPosition="3" transparent="1" foregroundColor="white"     backgroundColor="#251f1f1f" font="Regular;24" halign="center" valign="center"/>
                    <widget name="currTimeLabel"      noWrap="1" position="220,100"       size="200,40"   zPosition="3" transparent="1" foregroundColor="#66ccff"   backgroundColor="#251f1f1f" font="Regular;30" halign="left"   valign="top"/>
                    <widget name="lengthTimeLabel"    noWrap="1" position="540,100"       size="200,40"   zPosition="3" transparent="1" foregroundColor="#999999"   backgroundColor="#251f1f1f" font="Regular;30" halign="center" valign="top"/>
                    <widget name="remainedLabel"      noWrap="1" position="860,100"       size="200,40"   zPosition="3" transparent="1" foregroundColor="#66ccff"   backgroundColor="#251f1f1f" font="Regular;30" halign="right"  valign="top"/>
                    <widget name="videoInfo"          noWrap="1" position="560,20"        size="500,30"   zPosition="3" transparent="1" foregroundColor="#999999"   backgroundColor="#251f1f1f" font="Regular;24" halign="right"  valign="top"/>
                    <widget name="playlistInfo"       noWrap="1" position="220,20"        size="330,30"   zPosition="3" transparent="1" foregroundColor="#999999"   backgroundColor="#251f1f1f" font="Regular;24" halign="left"   valign="top"/>

                    %s

                    <widget name="subSynchroIcon"     position="0,0"           size="180,66"  zPosition="4" transparent="1" alphatest="blend" />
                    <widget name="subSynchroLabel"    position="1,3"           size="135,50"  zPosition="5" transparent="1" foregroundColor="white"      backgroundColor="transparent" font="Regular;24" halign="center"  valign="center"/>

                    %s
            </screen>"""

        if self.clockFormat:
            if dw < 800:
                clockFontSize = self.skinSettings.get("clockFontSize_SD", 30)
            else:
                # clockFontSize_HD is the true 1280x720-reference value,
                # already correct as-is now that resolution="1280,720"
                # (see REF_W/REF_H comment above) makes Enigma2 scale it up
                # proportionally for real FHD/WQHD screens.
                # clockFontSize_FHD existed only as a manual, real-pixel
                # workaround for the missing resolution= scaling
                # (settings.json never even got a WQHD value either) - now
                # redundant, and would double-scale on top of Enigma2's own
                # scaling if still applied.
                clockFontSize = self.skinSettings.get("clockFontSize_HD", 30)

            self.playerClockPath = self.playerSkinFolder + "/playerclock.xml"

            printDBG("Player clock file path:" + self.playerClockPath)

            if os_path.exists(self.playerClockPath):
                # read player skin xml file
                clockFile = open(self.playerClockPath, 'r')
                clockWidget = clockFile.read()
                clockFile.close()

                # printDBG("---------------------------------------")
                # printDBG(clockWidget)
                # printDBG("---------------------------------------")

                clockWidget = clockWidget % clockFontSize
            else:
                clockWidget = ""
        else:
            clockWidget = ''

        # the screen's own size= is read by Enigma2 in the same units as
        # everything else on a resolution="1280,720" screen, i.e. it gets
        # scaled with the widgets. Handing it real desktop pixels there
        # (as the "sd" theme, which has no resolution=, still needs) made
        # the window 1.5x (FHD) / 2x (WQHD) bigger than the desktop: OpenATV
        # clamps a negative "center" offset to 0 and hides it, but skin
        # engines that don't (OpenViX/OpenBH) centre it at a negative
        # offset - infobar in the middle of the screen, left side cut off.
        self.skinUsesRefCanvas = 'resolution="' in skin
        if self.skinUsesRefCanvas:
            screenW, screenH = REF_W, REF_H
            scaledBars = self.SCALED_BAR_IMAGES.get(os_path.basename(os_path.normpath(self.playerSkinFolder)))
        else:
            screenW, screenH = dw, getDesktop(0).size().height()
            scaledBars = None

        # kept for initGuiComponentsPos(), which swaps in pre-scaled copies
        self.progressBarFiles = (
            self._progressBarPixmapPath("playback_progress", scaledBars, 0, dw),
            self._progressBarPixmapPath("playback_cbuff_progress", scaledBars, 1, dw),
            self._progressBarPixmapPath("playback_buff_progress", scaledBars, 2, dw),
        )
        skin = skin % (
            screenW,
            screenH,
            self.playerSkinFolder + "/playback_banner.png",
            self.progressBarFiles[0],
            self.progressBarFiles[1],
            self.progressBarFiles[2],
            self.playerSkinFolder + "/playback_pointer.png",
            clockWidget,
            subSkin
        )  # 00000000 bottom
        # what the infobar of this skin has of the optional widgets (the poster, the badges of the formats)
        self.skinWidgetNames = set(re.findall(r'<widget[^>]*?\sname="([^"]+)"', skin))
        # added here, not in the playerskin.xml files: every player skin gets the panel of the INFO key
        refScale = 1.0 if self.skinUsesRefCanvas else dw / float(self.REF_W)
        skin = skin.replace('</screen>', PlayerInfoPanel.skinWidgets(refScale) + '</screen>')
        # the title's poster in the middle while the stream opens (startCover), under the infobar and "Please wait";
        # the poster of audio playback (audioCover), placed by showAudioCover()
        skin = skin.replace('</screen>', '<widget name="startCover" position="%d,%d" size="%d,%d" zPosition="1" transparent="1" alphatest="blend" /></screen>'
                            % tuple(int(v * refScale) for v in self.START_COVER_BOX))
        skin = skin.replace('</screen>', '<widget name="audioCover" position="0,0" size="%d,%d" zPosition="1" transparent="1" alphatest="blend" /></screen>'
                            % (int(REF_W * refScale), int(REF_H * refScale)))
        # the title's backdrop (components/iptvbackdrop.py) under the audio poster, the infobar and the INFO panels
        skin = skin.replace('</screen>', '<widget name="backdrop" position="0,0" size="%d,%d" zPosition="0" transparent="1" /></screen>'
                            % (int(REF_W * refScale), int(REF_H * refScale)))
        # the song of a radio stream above the audio poster (exteplayer3 "m_t")
        skin = skin.replace('</screen>', '<widget name="audioCoverText" noWrap="1" position="%d,%d" size="%d,%d" zPosition="2" transparent="1" '
                            'foregroundColor="#ffffff" backgroundColor="#000000" borderColor="#000000" borderWidth="2" font="Regular;%d" '
                            'halign="center" valign="center" /></screen>'
                            % tuple(int(v * refScale) for v in self.AUDIO_COVER_TEXT_BOX + (self.AUDIO_COVER_TEXT_FONT,)))

        sub = None
        return skin

    STREAM_PROTO_LABELS = {'m3u8': 'HLS', 'em3u8': 'HLS', 'mpd': 'DASH', 'f4m': 'HDS', 'uds': 'HDS',
                           'rtmp': 'RTMP', 'rtsp': 'RTSP', 'mms': 'MMS', 'mmsh': 'MMS'}
    STREAM_CONTAINERS = ('mp4', 'm4v', 'mkv', 'webm', 'flv', 'ts', 'm2ts', 'avi', 'mov', 'wmv', 'mpg', 'mpeg', 'vob', 'divx', '3gp', 'ogv')

    def getStreamSourceUrl(self):
        # in buffering mode fileSRC is the local buffer file, the downloader has the source
        if self.downloader is not None:
            return strwithmeta(self.downloader.getUrl())
        return self.fileSRC

    def getLocalFilePath(self):
        # the file the player reads when it is one here: a download or the buffer file
        path = self.fileSRC
        if path.startswith('file://'):
            path = path[len('file://'):].replace('//', '/')
        return str(path) if '://' not in path and os_path.isfile(path) else ''

    def _getStreamTypeLabel(self, url=None):
        # short delivery type for the info bar ("HLS", "DASH", "MP4", ...)
        try:
            if url is None:
                url = self.getStreamSourceUrl()
            url = strwithmeta(url)
            proto = url.meta.get('iptv_proto', '')
            urlLower = url.lower()
            if proto == 'merge' or urlLower.startswith('merge://'):
                # separate audio/video streams: DASH renditions unless the
                # video part is itself an HLS playlist (a DASH rendition's
                # own mime=video/mp4 must not turn this into "MP4")
                videoUrl = url.meta.get('video_url', '')
                if videoUrl and self._getStreamTypeLabel(videoUrl) == 'HLS':
                    return 'HLS'
                return 'DASH'
            # rstrip: KVS sites (most of hostxxx) serve .../get_file/.../123.mp4/?rnd=...
            path = urlLower.split('?', 1)[0].split('#', 1)[0].split('|', 1)[0].rstrip('/')
            if proto in self.STREAM_PROTO_LABELS:
                return self.STREAM_PROTO_LABELS[proto]
            if path.endswith('.m3u8') or 'protocol=hls' in urlLower:
                return 'HLS'
            if path.endswith('.mpd'):
                return 'DASH'
            for scheme in ('rtmp', 'rtsp', 'mms'):
                if urlLower.startswith(scheme):
                    return self.STREAM_PROTO_LABELS.get(scheme, scheme.upper())
            ext = url.meta.get('iptv_format', '') or path.rsplit('.', 1)[-1]
            if ext in self.STREAM_CONTAINERS:
                return ext.upper()
            # playlist named only further on, e.g. proxied
            # .../m3u8-proxy?url=https://cdn/x/index.m3u8&headers=...
            if re.search(r'\.m3u8(?=$|[?&#/|;,])', urlLower):
                return 'HLS'
            if re.search(r'\.mpd(?=$|[?&#/|;,])', urlLower):
                return 'DASH'
            # no file extension (e.g. googlevideo .../videoplayback?...) -
            # the container may still be named by a mime= query parameter
            mime = re.search(r'[?&]mime=video(?:/|%2f)([a-z0-9.+-]+)', urlLower)
            if mime:
                ext = {'x-flv': 'flv', 'mp2t': 'ts', '3gpp': '3gp'}.get(mime.group(1), mime.group(1))
                if ext in self.STREAM_CONTAINERS:
                    return ext.upper()
            # ... or by a file= query parameter (KVS remote storage redirect:
            # .../remote_control.php?time=..&file=%2Fvideos%2F..%2F123_720p.mp4&cv3=..)
            fileParam = re.search(r'[?&](?:file|filename)=([^&#|]+)', urlLower)
            if fileParam:
                ext = fileParam.group(1).replace('%2e', '.').replace('%2f', '/').replace('%3f', '?')
                ext = ext.split('?', 1)[0].rstrip('/').rsplit('.', 1)[-1]
                if ext in self.STREAM_CONTAINERS:
                    return ext.upper()
        except Exception:
            printExc(WarnOnly=True)
        return ''

    def _progressBarPixmapPath(self, name, scaledBars, idx, dw):
        # progressBar/bufferingCBar/bufferingBar are eSlider widgets: the
        # filled part is computed from the widget's (resolution="1280,720"-
        # scaled) size, but the pixmap is blitted at its native size and
        # only clipped to it. With the 840px-wide 1280x720 images the fill
        # therefore stopped at 840/1260 = 2/3 of the bar on FHD (1/3 on
        # WQHD). SCALED_BAR_IMAGES points every non-"sd" theme at
        # pre-scaled _1920/_2560 copies (full-width gradients must match
        # the bar width, not just cover it); anything else falls back to
        # the theme's own image, which initGuiComponentsPos() replaces by a
        # copy resized once with PIL (_prescaledPixmap).
        if scaledBars:
            path = GetPlayerSkinDir("_scaled/%s_%d.png" % (scaledBars[idx], dw))
            if os_path.exists(path):
                return path
        return "%s/%s.png" % (self.playerSkinFolder, name)

    def _prescaledPixmap(self, widgetName, path):
        # Enigma2 draws a pixmap at its native size, so on FHD/WQHD the
        # images of the 1280x720 reference skin stayed small inside their
        # resolution="1280,720"-scaled widgets. The scale flag
        # (setScale/setPixmapScale) makes every redraw a scaled blit, which
        # froze the OSD after a few pause/play presses on some boxes
        # (Octagon SF3038) while the stream kept running - so the PNG is
        # resized once with PIL and then drawn 1:1. None = keep the native
        # pixmap (HD, "sd" theme, image already fits, no PIL).
        # A skin may ship the picture drawn for the OSD resolution beside it
        # (name_1920.png, name_2560.png): sharp, and without PIL. It is taken
        # as it is when it has the widget's size, else it is the source of
        # the resized copy (less to scale than the 1280 one).
        dw = getDesktop(0).size().width()
        if not self.skinUsesRefCanvas or dw == self.REF_W:
            return None
        root, ext = os_path.splitext(path)
        native = '%s_%d%s' % (root, dw, ext)
        if os_path.isfile(native):
            path = native
        elif Image is None:
            return None
        try:
            size = self[widgetName].instance.size()
            w, h = size.width(), size.height()
            if w <= 0 or h <= 0:
                return None
            if path == native:
                if Image is None:
                    return LoadPixmap(path)
                with Image.open(path) as img:
                    if img.size == (w, h):
                        return LoadPixmap(path)
            theme = os_path.basename(os_path.dirname(path))
            name = os_path.splitext(os_path.basename(path))[0]
            outPath = GetTmpDir('e2i_playerskin_%s_%s_%dx%d_%d.png' % (theme, name, w, h, int(os_path.getmtime(path))))
            if not os_path.exists(outPath):
                with Image.open(path) as img:
                    if img.size == (w, h):
                        return None
                    # written under a temporary name first: a cut-off file
                    # (full disk, power loss) must not be found as finished
                    img.convert('RGBA').resize((w, h), Image.LANCZOS).save(outPath + '.part', format='png')
                os_rename(outPath + '.part', outPath)
            return LoadPixmap(outPath)
        except Exception:
            printExc()
        return None

    def _prescaleSkinPixmaps(self):
        # see _prescaledPixmap() - icons are swapped in their dicts (set on
        # status changes later), the skin-loaded images directly
        folder = self.playerSkinFolder + "/"
        statusIcons = self.playback['statusIcons']
        loopIcons = self.playback['loopIcons']
        logoFile = "playback_gstreamer_logo" if 'gstplayer' == self.player else "playback_ffmpeg_logo"
        for widgetName, icons, key, fileName in (('statusIcon', statusIcons, 'Play', "playback_a_play"),
                                                 ('statusIcon', statusIcons, 'Pause', "playback_a_pause"),
                                                 ('statusIcon', statusIcons, 'FastForward', "playback_a_ff"),
                                                 ('loopIcon', loopIcons, 'On', "playback_loop_on"),
                                                 ('loopIcon', loopIcons, 'Off', "playback_loop_off"),
                                                 ('logoIcon', self.playback, 'logoIcon', logoFile),
                                                 ('subSynchroIcon', self.subHandler['synchro'], 'icon', "sub_synchro")):
            pixmap = self._prescaledPixmap(widgetName, folder + fileName + ".png")
            if pixmap:
                icons[key] = pixmap
        statusIcons['SlowMotion'] = statusIcons['FastForward']

        for widgetName, path in (('playbackInfoBaner', folder + "playback_banner.png"),
                                 ('goToSeekPointer', folder + "playback_pointer.png"),
                                 ('progressBar', self.progressBarFiles[0]),
                                 ('bufferingCBar', self.progressBarFiles[1]),
                                 ('bufferingBar', self.progressBarFiles[2])):
            pixmap = self._prescaledPixmap(widgetName, path)
            if pixmap:
                self[widgetName].instance.setPixmap(pixmap)
                if widgetName == 'playbackInfoBaner':
                    self.bannerBackdrop['default'] = pixmap

    def _subtitleScale(self):
        # setSubtitlesText()/runConfigMoviePlayerCallback()'s subtitle
        # resize block/setSubOffsetFromInfoBar() all position subtitles
        # via direct eLabel.instance.move()/.resize()/.setFont() calls
        # computed from real getDesktop(0) pixels - unlike the rest of
        # this screen, these never go through Enigma2's skin-level
        # resolution="1280,720" scaling at all, since they're plain
        # Python calls acting on an already-built instance, not
        # skin-declared attributes Enigma2 itself scales. Without their
        # own scale factor, subtitles would stay a constant absolute size
        # while the rest of the OSD grows with resolution - shrinking
        # relative to the screen at FHD/WQHD. Same 1280-wide reference as
        # everything else here.
        return getDesktop(0).size().width() / float(self.REF_W)

    def _effectiveSubLineHeight(self, scale):
        # user-configured line_height can end up no taller than font_size
        # itself - real fonts need noticeably more vertical room than
        # their point size for descenders (e.g. "g") to not get clipped,
        # independent of the scale factor (this floor is computed
        # consistently in real, already-scaled pixels wherever a line
        # height is needed). 1.3x is a common, conservative
        # line-height-to-font-size ratio - only ever makes the line taller
        # than the user's own setting, never shrinks a deliberately
        # generous one.
        lineHeight = int(self.subConfig['line_height'] * scale)
        minHeight = int(self.subConfig['font_size'] * scale * 1.3)
        return max(lineHeight, minHeight)

    def getSkinSettings(self):
        printDBG("iptvextmovieplayer.getSkinSetting")

        if getDesktop(0).size().width() < 800:
            # skin for SD
            self.playerSkinFolder = GetPlayerSkinDir('sd')
        else:
            self.playerSkinFolder = GetPlayerSkinDir(ConfigExtMoviePlayerBase().getPlayerSkinFolder())

        settingsPath = self.playerSkinFolder + "/settings.json"

        try:
            if os_path.exists(settingsPath):
                # read player skin xml file
                settingsFile = open(settingsPath, 'r')
                response = settingsFile.read()
                settingsFile.close()

                # printDBG("---------------------------------------")
                # printDBG(response)
                # printDBG("---------------------------------------")

                return json.loads(response)

            return {}
        except Exception:
            printExc()
            return {}

    def __init__(self, session, filesrcLocation, FileName, lastPosition=None, player='eplayer', additionalParams={}):
        self.configObj = ConfigExtMoviePlayerBase()
        self.subConfig = self.configObj.getSubtitleFontSettings()
        self.clockFormat = self.configObj.getInfoBannerrClockFormat()
        self.skinSettings = self.getSkinSettings()
        self.chapters, self.descriptionText = self.loadChapters(filesrcLocation, additionalParams)
        self.chapterLastIdx = -1
        self.chapterJump = None  # (position, time) of the last chapter jump, see chapterPosMs()
        self.chapterMarks = []  # eLabels on the progress bar, made when needed (refreshChapterMarks)
        self.chapterProbe = None  # ffprobe for the chapters of a local file (probeFileChapters)
        # MENU -> "Description" waits for the host's INFO page (showDescription)
        self.descriptionWaiting = False
        self.articleDownloadDir = additionalParams.get('article_download_dir', None)
        self.listDescription = additionalParams.get('info_description', '') or ''
        self.skin = self.__prepareSkin()
        Screen.__init__(self, session)
        self.skinName = skinchrome.forceInternalSkinName("IPTVExtMoviePlayer")

        self.player = player
        if 'gstplayer' == self.player:
            self.playerName = _("external gstplayer")
            self.gstAdditionalParams = {}
            self.gstAdditionalParams['download-buffer-path'] = additionalParams.get('download-buffer-path', '')  # File template to store temporary files in, should contain directory and XXXXXX
            self.gstAdditionalParams['ring-buffer-max-size'] = additionalParams.get('ring-buffer-max-size', 0)  # in MB
            self.gstAdditionalParams['buffer-duration'] = additionalParams.get('buffer-duration', -1)  # in s
            self.gstAdditionalParams['buffer-size'] = additionalParams.get('buffer-size', 0)  # in KB
            self.gstAdditionalParams['file-download-timeout'] = additionalParams.get('file-download-timeout', 0)  # in MS
            self.gstAdditionalParams['file-download-live'] = additionalParams.get('file-download-live', False)  # True or False
        else:
            self.playerName = _("external eplayer3")

        self.extAdditionalParams = {}
        self.availableDataSizeCorrection = 0
        self.totalDataSizeCorrection = 0
        if 'moov_atom_info' in additionalParams:
            if additionalParams['moov_atom_info']['offset'] == 0:
                self.availableDataSizeCorrection = additionalParams['moov_atom_info']['size']
                self.totalDataSizeCorrection = self.availableDataSizeCorrection
            else:
                self.extAdditionalParams['moov_atom_offset'] = additionalParams['moov_atom_info']['offset']
                self.extAdditionalParams['moov_atom_size'] = additionalParams['moov_atom_info']['size']
                self.extAdditionalParams['moov_atom_file'] = additionalParams['moov_atom_info']['file']
                self.totalDataSizeCorrection = self.extAdditionalParams['moov_atom_size']

        self.session.nav.playService(None)  # current service must be None to give free access to DVB Audio and Video Sinks
        self.fileSRC = strwithmeta(filesrcLocation)
        self.title = FileName
        self.hostName = additionalParams.get('host_name', '')
        self.hostLogoPath = additionalParams.get('logo_path', '')
        # "Select link automatically" has further links: an error before the first second of playback
        # closes the player without a message, E2iPlayer goes on with the next link
        self.quietStartErrors = additionalParams.get('quiet_start_errors', False)
        if lastPosition:
            self.lastPosition = lastPosition
        else:
            self.lastPosition = 0
        # exteplayer3 188: only forced subtitle cues (so1/so0), dual mono channel (am<n>: 0 left, 1 stereo, 2 right),
        # the file the player writes the embedded cover to (--cover)
        self.forcedSubtitlesOnly = False
        self.audioChannel = 1
        self.embeddedCoverPath = ''
        # resumed with --start: the infobar once the player knows the length
        self.showInfoBarAtLength = False
        # the video part of the videoInfo label (the audio format follows it in a skin without badges)
        self.videoInfoText = ''
        self.videoInfoShortText = ''
        self.downloader = additionalParams.get('downloader', None)
        self.isDownladManagerAvailable = additionalParams.get('download_manager_available', False)
        self.externalSubTracks = additionalParams.get('external_sub_tracks', [])  # [{'title':'', 'lang':'', 'url':''}, ...]
        self.refreshCmd = additionalParams.get('iptv_refresh_cmd', '')
        self.refreshCmdConsole = None
        self.extLinkProv = {}
        self.extLinkProv['console'] = None
        self.extLinkProv['close_conn'] = None
        self.extLinkProv['data_conn'] = None
        self.extLinkProv['data'] = ''
        self.extLinkProv['started'] = False

        self.iframeParams = {}
        self.iframeParams['console'] = None
        self.iframeParams['show_iframe'] = additionalParams.get('show_iframe', False)
        self.iframeParams['iframe_file_start'] = additionalParams.get('iframe_file_start', '')
        self.iframeParams['iframe_file_end'] = additionalParams.get('iframe_file_end', '')
        self.iframeParams['iframe_continue'] = additionalParams.get('iframe_continue', False)

        # CH+/CH- (and >|/|<) close the player with 'zap_next'/'zap_prev', the list (E2iPlayerWidget.zapToItem)
        # then starts the next/previous playable item; only set by the list, not for the download manager
        self.zapEnabled = additionalParams.get('zap_enabled', False)
        # a run of the autoplay sequencer of the list (tools/listselection.buildPlaylist): "Playlist 3/10" in the
        # infobar and "Show playlist" in the MENU, whose entries close the player like a zap ('zap_to', ...)
        self.playlist = additionalParams.get('playlist') if self.zapEnabled else None

        # screensaver over audio-only playback (iptvscreensaver.py), see _screenSaverWanted()
        from Plugins.Extensions.IPTVPlayer.components.iptvscreensaver import IPTVAudioScreenSaver
        self.screenSaverAudioItem = additionalParams.get('audio_item', False)
        self.screenSaver = IPTVAudioScreenSaver(self, [additionalParams.get('cover_path', ''), additionalParams.get('logo_path', '')])

        printDBG('IPTVExtMoviePlayer.__init__ lastPosition[%r]' % self.lastPosition)

        self.extPlayerCmddDispatcher = ExtPlayerCommandsDispatcher(self)

        self["actions"] = ActionMap(['IPTVAlternateVideoPlayer', 'MoviePlayerActions', 'MediaPlayerActions', 'MediaPlayerSeekActions', 'WizardActions'],
            {
                "leavePlayer": self.key_stop,
                'play': self.key_play,
                'pause': self.key_pause,
                'exit': self.key_exit,
                'back': self.key_exit,
                'info': self.key_info,
                'seekdef:1': self.key_seek1,
                'seekdef:3': self.key_seek3,
                'seekdef:4': self.key_seek4,
                'seekdef:6': self.key_seek6,
                'seekdef:7': self.key_seek7,
                'seekdef:9': self.key_seek9,
                'seekFwd': self.key_seekFwd,
                'seekBack': self.key_seekBack,
                'left_press': self.key_left_press,
                'left_repeat': self.key_left_repeat,
                'rigth_press': self.key_rigth_press,
                'rigth_repeat': self.key_rigth_repeat,

                'up_press': self.key_up_press,
                'up_repeat': self.key_up_repeat,
                'down_press': self.key_down_press,
                'down_repeat': self.key_down_repeat,

                'ok': self.key_ok,
                'subtitles': self.key_subtitles,
                'audio': self.key_audio,
                'videooptions': self.key_videooption,
                'menu': self.key_menu,
                'loop': self.key_loop,
                'record': self.key_record,
                'zap_next': self.key_zap_next,
                'zap_prev': self.key_zap_prev,
            }, -1)
        # >|/|< over the zap of the actions above: with chapters they jump between them, without (and at the end of the
        # list) the key goes on to zap_next/zap_prev
        self["chapterActions"] = ActionMap(['IPTVExtPlayerChapterActions'],
            {
                'chapter_next': self.key_nextChapter,
                'chapter_prev': self.key_prevChapter,
            }, -2)

        self.onClose.append(self.__onClose)
        self.onShow.append(self.onStart)
        self.onLayoutFinish.append(self.fixWindowGeometry)
        self.onLayoutFinish.append(self.initPleaseWaitBox)
        self.onLayoutFinish.append(self.showStartCover)
        # self.onLayoutFinish.append(self.onStart)

        self.console = None

        self.isClosing = False
        self.responseData = ""

        # playback info
        # GUI
        self.updateInfoTimer = eTimer()
        self.updateInfoTimer_conn = eConnectCallback(self.updateInfoTimer.timeout, self.updateInfo)

        # playback info bar gui elements
        self['logoIcon'] = Cover3()
        self['playbackInfoBaner'] = Cover3()
        self['statusIcon'] = Cover3()
        self['loopIcon'] = Cover3()
        self['progressBar'] = ProgressBar()
        self['bufferingCBar'] = ProgressBar()
        self['bufferingBar'] = ProgressBar()
        self['goToSeekPointer'] = Cover3()
        self['infoBarTitle'] = Label(self.title)
        self['goToSeekLabel'] = Label("0:00:00")
        self['currTimeLabel'] = Label("0:00:00")
        self['remainedLabel'] = Label("-0:00:00")
        self['lengthTimeLabel'] = Label("0:00:00")
        addLcdSources(self, self.title, currTime="0:00:00", remained="-0:00:00", length="0:00:00", percent="0%",
                      currTimeHM="0:00", remainedHM="0:00", lengthHM="0:00", remainedMin="0", remainedShort="", shortTimes=True, coverFile=additionalParams.get('cover_path'))
        self.lcdLastState = None
        self.lcdLastLength = 0
        self.lcdLengthGrowth = 0
        self['videoInfo'] = Label(" ")
        # empty without a playlist. Every playerskin.xml must declare it: initGuiComponentsPos() moves each
        # widget of the infobar (guiElemNames) and needs its instance
        self['playlistInfo'] = Label(listselection.playlistInfoText(self.playlist, _('Playlist'), _('marked'), _('shuffled'), _('reversed')))
        if self.clockFormat:
            self['clockTime'] = Label(" ")
        self['pleaseWait'] = Label(_("Opening. Please wait..."))
        # the list row's picture while the stream opens: on the black screen before the first frame only - hidden
        # as soon as playback runs, at the latest after START_COVER_TIMEOUT
        self['startCover'] = Cover()
        self.startCoverPath = additionalParams.get('cover_path', '') or ''
        self.startCoverTimer = eTimer()
        self.startCoverTimer_conn = eConnectCallback(self.startCoverTimer.timeout, self.hideStartCover)
        # the title's picture (else the host logo) during audio-only playback, see showAudioCover()
        self['audioCover'] = Cover()
        self['audioCoverText'] = Label('')
        # the backdrop of the host's INFO page: behind the INFO panels, during audio playback, on pause (setting)
        self['backdrop'] = Cover()
        self.backdropLoader = None
        # the infobar's picture over the backdrop (updateBannerBackdrop): the key of the one shown / the one made,
        # the skin's own picture to go back to
        # the infobar over the backdrop (updateBannerBackdrop): what is shown / made, the skin's own picture, the
        # picture wanted now, keys that failed, and the worker that makes one (PIL takes too long for the GUI thread)
        self.bannerBackdrop = {'shown': None, 'made': None, 'default': None, 'wanted': None, 'failed': set(), 'worker': None, 'result': None}
        self.bannerTimer = eTimer()
        self.bannerTimer_conn = eConnectCallback(self.bannerTimer.timeout, self._bannerWorkerDone)
        # known from the item's INFO page or "Select link" (iptvplayerwidget), else it comes with the host's page
        self.backdropStartUrl = additionalParams.get('backdrop_url', '') or ''
        self.audioCover = {'paths': [additionalParams.get('cover_path', '') or '', additionalParams.get('logo_path', '') or ''],
                           'shown': False, 'box': None, 'timer': eTimer()}
        self.coverIsDefault = bool(additionalParams.get('cover_is_default'))
        self.audioCover['timer_conn'] = eConnectCallback(self.audioCover['timer'].timeout, self.showAudioCover)
        # optional widgets of the infobar (only skins like "modern" declare them): the poster and the format badges
        self[self.INFOBAR_POSTER] = Cover()
        self[self.INFOBAR_POSTER_MASK] = Cover3()
        self[self.INFOBAR_KNOB] = Cover3()
        for name in self.INFOBAR_STRIP_ICONS:
            self[name] = Cover3()
        self.infoBarPosterPaths = list(self.audioCover['paths'])
        self.infoBarPosterBox = None
        for name in self.INFOBAR_BADGES + self.INFOBAR_BADGE_PARTS + (self.INFOBAR_META, self.INFOBAR_RATING) + self.INFOBAR_STRIP:
            self[name] = Label('')
        # the title as it came, the label may hold it cut off with "…"
        self.infoBarTitleText = self.title
        self.infoBarTitleRect = None
        self.infoBarRatingRect = None
        self.infoBarRatingShown = ''
        self.infoBarMetaText = None  # the text of the meta line as last set (None: not set yet)
        # the symbols of the info row that have their picture
        self.infoBarStripIcons = set()
        self.infoBarBadgeLayout = None
        self.infoBarStripLayout = None
        self.infoBarMaskLoaded = False
        self.infoBarHostTitle = additionalParams.get('host_title', '') or self.hostName
        # infobar widgets that stay hidden when the infobar shows (an empty badge, no poster)
        self.infoBarHiddenElems = set()

        # for subtitles
        self.infoBanerOffsetY = -1
        for idx in range(self.subLinesNum):
            # printf('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> ' % ('subLabel%d'%(idx+1)))
            self['subLabel%d' % (idx + 1)] = Label(" ")
        self.hideSubtitles()
        self.subHandler = {}
        self.subHandler['current_sub_time_ms'] = -1
        self.subHandler['handler'] = IPTVSubtitlesHandler()
        self.subHandler['embedded_handler'] = IPTVEmbeddedSubtitlesHandler()
        self.subHandler['handler_type'] = 'embedded_handler'
        self.subHandler['enabled'] = False
        self.subHandler['timer'] = eTimer()
        self.subHandler['timer_conn'] = eConnectCallback(self.subHandler['timer'].timeout, self.updatSubtitlesTime)
        self.subHandler['latach_time'] = -1
        self.subHandler['last_time'] = -1
        self.subHandler['marker'] = None
        self.subHandler['synchro'] = {'visible': False, 'guiElemNames': ['subSynchroLabel', 'subSynchroIcon'], 'icon': None}
        self.subHandler['pos_y_offset'] = 0
        # image subtitles, 'enabled' when exteplayer3 runs with -G
        graphicDir = GetTmpDir('e2i_graphic_subs')
        self.graphicSubs = {'enabled': False, 'dir': graphicDir, 'handler': IPTVGraphicSubtitlesHandler(graphicDir), 'marker': None}
        for idx in range(self.GRAPHIC_SUB_RECTS):
            self['subGraphic%d' % (idx + 1)] = Cover3()
            self['subGraphic%d' % (idx + 1)].hide()
        self['subSynchroLabel'] = Label("0.0s")
        self['subSynchroIcon'] = Cover3()
        try:
            self.subHandler['synchro']['icon'] = LoadPixmap(self.playerSkinFolder + "/sub_synchro.png")
        except Exception:
            printExc()
        self.hideSubSynchroControl()

        # VIDEO options
        self.defVideoOptions = {'aspect': None, 'aspect_choices': [], 'policy': None, 'policy_choices': [], 'policy2': None, 'policy2_choices': [], 'videomode': additionalParams.get('defaul_videomode', None), 'videomode_choices': GetE2VideoModeChoices()}
        self.videoOptSetters = {'aspect': SetE2VideoAspect, 'policy': SetE2VideoPolicy, 'policy2': SetE2VideoPolicy}
        self.currVideoOptions = {'aspect': None, 'policy': None, 'policy2': None, 'videomode': None}

        # AUDIO options
        self.defAudioOptions = {'ac3': None, 'aac': None}

        # meta data
        self.metaHandler = IPTVMovieMetaDataHandler(self.hostName, self.title, self.fileSRC)

        # goto seek  timer
        self.playback['GoToSeekTimer'] = eTimer()
        self.playback['GoToSeekTimer_conn'] = eConnectCallback(self.playback['GoToSeekTimer'].timeout, self.doGoToSeek)

        # notice "only loaded up to ..." for a skip key cut at the end of the buffered part
        self.seekLimitNotice = {'until': 0, 'timer': eTimer()}
        self.seekLimitNotice['timer_conn'] = eConnectCallback(self.seekLimitNotice['timer'].timeout, self.hideSeekLimitNotice)

        self.playback.update({
            "CurrentTime": 0,
            "BufferCTime": 0,
            "ConfirmedCTime": 0,
            "BufferFill": 0,
            "Length": 0,
            "LengthFromPlayerReceived": False,
            "GoToSeekTime": 0,
            "StartGoToSeekTime": 0,
            "GoToSeeking": False,
            "IsLive": False,
            "IsLoop": False,
            "Status": None,
            "VideoTrack": {},
            "AudioTrack": {},
            "AudioTracks": [],
            "SubtitleTrack": {},
            "SubtitleTracks": [],
            # for other plugins: the dict is a class attribute and keeps its values after the player closed, Active
            # tells. IsLive is only what the player reports, LiveDetected what the LCD shows as live.
            "Active": True,
            "Title": StripColorCodes(self.title),
            "CoverFile": self.lcdCoverFile,
            "LiveDetected": False
        })

        # load pixmaps for statusIcon
        self.playback['loopIcons'] = {'On': None, 'Off': None}
        self.playback['statusIcons'] = {'Play': None, 'Pause': None, 'FastForward': None, 'SlowMotion': None}
        try:
            self.playback['statusIcons']['Play'] = LoadPixmap(self.playerSkinFolder + "/playback_a_play.png")
            self.playback['statusIcons']['Pause'] = LoadPixmap(self.playerSkinFolder + "/playback_a_pause.png")
            self.playback['statusIcons']['FastForward'] = LoadPixmap(self.playerSkinFolder + "/playback_a_ff.png")
            self.playback['statusIcons']['SlowMotion'] = self.playback['statusIcons']['FastForward']
            if 'gstplayer' == self.player:
                self.playback['logoIcon'] = LoadPixmap(self.playerSkinFolder + "/playback_gstreamer_logo.png")
            else:
                self.playback['logoIcon'] = LoadPixmap(self.playerSkinFolder + "/playback_ffmpeg_logo.png")
            self.playback['loopIcons']['On'] = LoadPixmap(self.playerSkinFolder + "/playback_loop_on.png")
            self.playback['loopIcons']['Off'] = LoadPixmap(self.playerSkinFolder + "/playback_loop_off.png")
        except Exception:
            printExc()

        # show hide info bar functionality
        self.goToSeekRepeatCount = 0
        self.goToSeekStep = 0
        self.playbackInfoBar = {'visible': False, 'blocked': False, 'guiElemNames': ['playbackInfoBaner', 'progressBar', 'bufferingCBar', 'bufferingBar', 'goToSeekPointer', 'goToSeekLabel', 'infoBarTitle', 'currTimeLabel', 'remainedLabel', 'lengthTimeLabel', 'videoInfo', 'playlistInfo', 'statusIcon', 'loopIcon', 'logoIcon']}
        for name in self.INFOBAR_OPTIONAL:
            if name in self.skinWidgetNames:
                self.playbackInfoBar['guiElemNames'].append(name)
                # shown once it has its picture / text
                self.infoBarHiddenElems.add(name)
        if self.clockFormat:
            self.playbackInfoBar['guiElemNames'].append('clockTime')
            self.playbackInfoBar['clock_timer'] = eTimer()
            self.playbackInfoBar['clock_timer_conn'] = eConnectCallback(self.playbackInfoBar['clock_timer'].timeout, self.updateClock)
        self.playbackInfoBar['timer'] = eTimer()
        self.playbackInfoBar['timer_conn'] = eConnectCallback(self.playbackInfoBar['timer'].timeout, self.hidePlaybackInfoBar)

        self.isStarted = False
        self.hidePlaybackInfoBar()

        self.waitEOSAbortedFix = {'EOSaborted_received': False, 'poll_received': False, 'timer': None}
        self.waitEOSAbortedFix['timer'] = eTimer()
        self.waitEOSAbortedFix['timer_conn'] = eConnectCallback(self.waitEOSAbortedFix['timer'].timeout, self.waitEOSAbortedFixTimeoutCallback)

        self.waitCloseFix = {'waiting': False}
        self.waitCloseFix['timer'] = eTimer()
        self.waitCloseFix['timer_conn'] = eConnectCallback(self.waitCloseFix['timer'].timeout, self.waitCloseTimeoutCallback)

        self.closeRequestedByUser = None
        self.playerBinaryInfo = {'version': None, 'data': ''}
        self.messageQueue = []
        self.underMessage = False

        try:
            self.autoHideTime = 1000 * int(self.configObj.getInfoBarTimeout())
        except Exception:
            self.autoHideTime = 1000

        # INFO: the panel over the running video
        self.infoPanel = PlayerInfoPanel(self, additionalParams)

        self.fatalErrorOccurs = False
        self.delayedClosure = None
        self.childWindowsCount = 0

        self.workconsole = None
        # we will set movie player config at first use of subtitles
        # to fix problems with small subtitles at first run with custom
        # exteplayer skin
        self.setMoviePlayerConfig = True
        self.clipLength = None

    def _getChoiceBoxHeight(self, numItems):
        # shared by every plain IPTVChoiceBoxWidget popup in this class
        # (Menu/Video-Option/Video-Option-Wert/Video-Modus/Audiospur/
        # Untertitelspur, all chrome=True) - same formula/reasoning as
        # iptvplayerwidget.py's own
        # _getMoviePlayerPickerHeight()/_getLinkPickerHeight(): IPTVRadioButtonList's
        # (IPTVMainNavigatorList's) real per-tier item heights (35/40/55),
        # +146 = the footerMargin passed below (136, list's fixed y=66 +
        # 64px footer bar + 10px breathing buffer)
        itemH, scale = skinchrome.tierRowHeight(35, 40, 55)
        return int(numItems * itemH / scale) + 146

    def showMenuOptions(self):
        printDBG("showMenuOptions")
        options = []
        options.append(IPTVChoiceBoxItem(_("Configuration"), "", "menu"))
        options.append(IPTVChoiceBoxItem(_("Subtitles"), "", "subtitles"))
        if len(self.playback['AudioTracks']):
            options.append(IPTVChoiceBoxItem(_("Audio tracks"), "", "audio_tracks"))
        options.append(IPTVChoiceBoxItem(_("Video options"), "", "video_options"))
        if self.playlist:
            options.append(IPTVChoiceBoxItem(_("Show playlist"), "", "playlist"))
        if self.chapters:
            options.append(IPTVChoiceBoxItem(_("Chapters"), "", "chapters"))
        if self.hasDescription():
            options.append(IPTVChoiceBoxItem(_("Description"), "", "description"))

        if self.isDownladManagerAvailable and self.downloader:
            options.append(IPTVChoiceBoxItem(_("Stop playback with buffer save"), "", "close_with_buffer_save"))

        self.openChild(boundFunction(self.childClosed, self.showMenuOptionsCallback), IPTVChoiceBoxWidget, {'width': 500, 'height': self._getChoiceBoxHeight(len(options)), 'current_idx': 0, 'title': _("Menu"), 'options': options, 'chrome': True, 'footerMargin': 136})

    def showMenuOptionsCallback(self, ret=None):
        printDBG("showMenuOptionsCallback ret[%r]" % [ret])
        if not isinstance(ret, IPTVChoiceBoxItem):
            return

        if "menu" == ret.privateData:
            self.runConfigMoviePlayer()
        elif "subtitles" == ret.privateData:
            self.selectSubtitle()
        elif "audio_tracks" == ret.privateData:
            self.selectAudioTrack()
        elif "video_options" == ret.privateData:
            self.selectVideoOptions()
        elif "playlist" == ret.privateData:
            self.showPlaylist()
        elif "chapters" == ret.privateData:
            self.showChapterList()
        elif "description" == ret.privateData:
            self.showDescription()
        elif "close_with_buffer_save" == ret.privateData:
            self.key_stop("save_buffer")

    def showPlaylist(self):
        # the rows of the sequencer's run in play order over the video (playback goes on): the current one
        # preselected, the played ones ticked; OK on another one closes the player like a zap to it
        if not self.playlist:
            return
        options = []
        for pos, entry in enumerate(self.playlist['entries']):
            item = IPTVChoiceBoxItem(entry['title'], "", entry, used=entry.get('played', False))
            if pos == self.playlist['current']:
                item.type = IPTVChoiceBoxItem.TYPE_ON
            options.append(item)
        title = self['playlistInfo'].getText() or _('Playlist')
        self.openChild(boundFunction(self.childClosed, self.showPlaylistCallback), IPTVChoiceBoxWidget, {'width': 800, 'height': self._getChoiceBoxHeight(min(len(options), 10)), 'current_idx': self.playlist['current'], 'title': title, 'options': options, 'list_class': IPTVPlaylistChoiceBoxList, 'chrome': True, 'footerMargin': 136})

    def showPlaylistCallback(self, ret=None):
        printDBG("showPlaylistCallback ret[%r]" % [ret])
        if not isinstance(ret, IPTVChoiceBoxItem) or not isinstance(ret.privateData, dict) or IPTVChoiceBoxItem.TYPE_ON == ret.type:
            return
        if self.zapEnabled and not self.isClosing:
            self.key_stop(listselection.zapToAnswer(ret.privateData))

    def runConfigMoviePlayer(self):
        printDBG("runConfigMoviePlayerCallback")
        self.openChild(boundFunction(self.childClosed, self.runConfigMoviePlayerCallback), ConfigExtMoviePlayer, True)

    def runConfigMoviePlayerCallback(self, confgiChanged=False):
        printDBG("runConfigMoviePlayerCallback confgiChanged[%s]" % confgiChanged)
        if not confgiChanged:
            return

        # change subtitles settings
        prevSub = self.subConfig
        self.subConfig = self.configObj.getSubtitleFontSettings()
        sub = self.subConfig

        scale = self._subtitleScale()
        for idx in range(self.subLinesNum):
            subLabel = "subLabel%d" % (idx + 1)
            self[subLabel].instance.setFont(gFont(sub['font'], int(sub['font_size'] * scale)))
            self[subLabel].instance.setForegroundColor(parseColor(sub['font_color']))
            self[subLabel].instance.setBackgroundColor(parseColor(sub['background']))

            if 'border' in sub:
                self[subLabel].instance.setBorderColor(parseColor(sub['border']['color']))
                self[subLabel].instance.setBorderWidth(sub['border']['width'])
            else:
                try:
                    tmp = dir(eLabel)
                    if 'setBorderColor' in tmp:
                        self[subLabel].instance.setBorderWidth(0)
                except Exception:
                    printExc()

            if 'shadow' in sub:
                self[subLabel].instance.setShadowColor(parseColor(sub['shadow']['color']))
                self[subLabel].instance.setShadowOffset(ePoint(sub['shadow']['xoffset'], sub['shadow']['yoffset']))
            elif 'shadow' in prevSub:
                self[subLabel].instance.setShadowOffset(ePoint(0, 0))
                self[subLabel].instance.setShadowColor(gRGB())  # parseColor("#ff111111") )

            if self.subLinesNum > 1 or 'transparent' != self.subConfig['background']:
                self[subLabel].instance.setVAlign(1)
            else:
                try:
                    valignMap = {'bottom': 2, 'center': 1, 'top': 0}
                    self[subLabel].instance.setVAlign(valignMap.get(sub['box_valign'], 2))

                    scaledBoxH = max(int(sub['box_height'] * scale), int(sub['font_size'] * scale * 1.3))
                    self[subLabel].instance.resize(eSize(getDesktop(0).size().width() - 20, scaledBoxH))
                    self[subLabel].resize(eSize(getDesktop(0).size().width() - 20, scaledBoxH))
                    self[subLabel].move(ePoint(10, getDesktop(0).size().height() - int(sub['pos'] * scale) - scaledBoxH))
                    self[subLabel].instance.move(ePoint(10, getDesktop(0).size().height() - int(sub['pos'] * scale) - scaledBoxH))
                except Exception:
                    printExc()
            self.setSubtitlesText(" ", False)
        self.setSubOffsetFromInfoBar()
        if -1 != self.subHandler['current_sub_time_ms']:
            self.updateSubtitles(self.subHandler['current_sub_time_ms'], True)
        else:
            self.setSubtitlesText("", False)
            self.hideSubtitles()
        sub = None

        # set video options
        videoOptionChange = False
        videoOptions = ['aspect', 'policy', 'policy2']
        playerDefOptions = self.configObj.getDefaultPlayerVideoOptions()
        for opt in videoOptions:
            playerVal = playerDefOptions[opt]
            metaVal = self.metaHandler.getVideoOption(opt)
            currVal = self.currVideoOptions[opt]
            defVal = self.defVideoOptions[opt]

            printDBG(">>>>>>>>>>>>> 0 [%s]" % (metaVal))
            if None is metaVal:
                printDBG(">>>>>>>>>>>>> A [%s] [%s]" % (currVal, playerVal))
                if currVal != playerVal:
                    printDBG(">>>>>>>>>>>>> B")
                    if None is playerVal:
                        self.currVideoOptions[opt] = defVal
                    else:
                        self.currVideoOptions[opt] = playerVal
                    videoOptionChange = True

        if videoOptionChange:
            self.applyVideoOptions(self.currVideoOptions)

        # set auto hide options
        try:
            self.autoHideTime = 1000 * int(self.configObj.getInfoBarTimeout())
        except Exception:
            self.autoHideTime = 1000

    def getE2AudioOptions(self):
        defAudioOptions = {
            'ac3': GetE2AudioCodecMixOption('ac3'),
            'aac': GetE2AudioCodecMixOption('aac'),
        }
        printDBG(">>>>>>>>>>>>>>>>>>>>> getE2AudioOptions[%s]" % defAudioOptions)
        return defAudioOptions

    def getE2VideoOptions(self):
        defVideoOptions = {
            "aspect": GetE2VideoAspect(),
            "aspect_choices": GetE2VideoAspectChoices(),
            "policy": GetE2VideoPolicy(),
            "policy_choices": GetE2VideoPolicyChoices(),
            "policy2": GetE2VideoPolicy("2"),
            "policy2_choices": GetE2VideoPolicyChoices(),
            "active": None
        }

        printDBG(">>>>>>>>>>>>>>>>>>>>> getE2VideoOptions[%s]" % defVideoOptions)
        return defVideoOptions

    def applyVideoOptions(self, newOptions):
        printDBG("applyVideoOptions newOptions[%s] ")
        options = ['aspect', 'policy', 'policy2']
        for opt in options:
            val = newOptions.get(opt, None)
            if None is not val:
                self.videoOptSetters[opt](val)

    def selectVideoOptions(self):
        printDBG("selectVideoOptions")
        options = []
        currIdx = 0
        optionsTab = [{'title': _('Video policy'), 'name': 'policy'}, {'title': _('Video policy for 4:3'), 'name': 'policy2'}, {'title': _('Aspect'), 'name': 'aspect'}, {'title': _('Video mode'), 'name': 'videomode'}]
        for option in optionsTab:
            if len(self.defVideoOptions[option['name'] + '_choices']) < 2:
                continue
            if None is self.defVideoOptions[option['name']]:
                continue
            if self.defVideoOptions['active'] == option['name']:
                currIdx = len(options)
            options.append(IPTVChoiceBoxItem(option['title'], "", option["name"]))

        if len(options):
            self.openChild(boundFunction(self.childClosed, self.selectVideoOptionsCallback), IPTVChoiceBoxWidget, {'width': 500, 'height': self._getChoiceBoxHeight(len(options)), 'current_idx': currIdx, 'title': _("Select video option"), 'options': options, 'chrome': True, 'footerMargin': 136})

    def selectVideoOptionsCallback(self, ret=None):
        printDBG("selectVideoOptionsCallback ret[%r]" % [ret])
        if not isinstance(ret, IPTVChoiceBoxItem):
            return
        options = []
        currIdx = 0

        option = ret.privateData
        self.defVideoOptions['active'] = option

        choices = self.defVideoOptions['%s_choices' % option]
        currValue = self.currVideoOptions[option]
        if None is currValue:
            currValue = self.defVideoOptions[option]

        if option != 'videomode':
            for item in choices:
                choiceItem = IPTVChoiceBoxItem(_(item), "", item)
                if item == currValue:
                    currIdx = len(options)
                    choiceItem.type = IPTVChoiceBoxItem.TYPE_ON
                else:
                    choiceItem.type = IPTVChoiceBoxItem.TYPE_OFF
                options.append(choiceItem)
            self.openChild(boundFunction(self.childClosed, self.selectVideoOptionCallback), IPTVChoiceBoxWidget, {'selection_changed': self.videoOptionSelectionChanged, 'width': 500, 'height': self._getChoiceBoxHeight(len(options)), 'current_idx': currIdx, 'title': _("Select %s") % ret.name, 'options': options, 'chrome': True, 'footerMargin': 136})
        else:
            printDBG('choices %s' % (choices))
            filteredChoices = []
            for item in choices:
                if item in [self.defVideoOptions['videomode'], self.currVideoOptions['videomode']] or item.startswith('1080') or item.startswith('2160'):
                    filteredChoices.append(item)

            for idx in range(len(filteredChoices)):
                item = IPTVChoiceBoxItem(_(filteredChoices[idx]), "", filteredChoices[idx])
                if filteredChoices[idx] == currValue:
                    item.type = IPTVChoiceBoxItem.TYPE_ON
                    currIdx = idx
                else:
                    item.type = IPTVChoiceBoxItem.TYPE_OFF
                options.append(item)
            self.openChild(boundFunction(self.childClosed, self.selectVideoModeCallback), IPTVChoiceBoxWidget, {'width': 500, 'height': self._getChoiceBoxHeight(len(options)), 'current_idx': currIdx, 'title': _("Select %s") % ret.name, 'options': options, 'chrome': True, 'footerMargin': 136})

    def selectVideoModeCallback(self, ret=None):
        printDBG("selectVideoModeCallback ret[%r]" % [ret])
        if isinstance(ret, IPTVChoiceBoxItem):
            currValue = self.currVideoOptions['videomode']
            if None is currValue:
                currValue = self.defVideoOptions['videomode']
            if ret.privateData in self.defVideoOptions['videomode_choices'] and ret.privateData != currValue:
                SetE2VideoMode(ret.privateData)
                self.openChild(boundFunction(self.childClosed, self.confirmVideoModeCallback), MessageBox, text=_("Is this message displayed correctly?"), type=MessageBox.TYPE_YESNO, timeout=10, default=False)
                return
        self.selectVideoOptions()

    def confirmVideoModeCallback(self, ret=None):
        printDBG("confirmVideoModeCallback ret[%r]" % [ret])
        if ret:
            curVideoMode = GetE2VideoMode()
            self.currVideoOptions['videomode'] = curVideoMode
            self.metaHandler.setVideoOption('videomode', curVideoMode)
        else:
            SetE2VideoMode(self.currVideoOptions['videomode'])
        self.selectVideoOptions()

    def videoOptionSelectionChanged(self, ret=None):
        printDBG("videoOptionSelectionChanged ret[%s]" % [ret])
        if isinstance(ret, IPTVChoiceBoxItem):
            newOptions = dict(self.currVideoOptions)
            newOptions[self.defVideoOptions['active']] = ret.privateData
            self.applyVideoOptions(newOptions)

    def selectVideoOptionCallback(self, ret=None):
        printDBG("selectVideoOptionsCallback ret[%r]" % [ret])
        if isinstance(ret, IPTVChoiceBoxItem):
            self.metaHandler.setVideoOption(self.defVideoOptions['active'], ret.privateData)
            self.currVideoOptions[self.defVideoOptions['active']] = ret.privateData
        else:
            ret = IPTVChoiceBoxItem("", "", self.currVideoOptions[self.defVideoOptions['active']])
        self.videoOptionSelectionChanged(ret)
        self.selectVideoOptions()

    # _trackLabel() translates the names of subtitlesmatch.LANGUAGES through _(langName(...)) - a dynamic
    # call, invisible to xgettext. Listing them as literals makes the translation template pick them up
    # (tests/test_subtitlesmatch.py keeps this list in sync with LANGUAGES).
    LANGUAGE_NAMES = (
        _("Albanian"), _("Arabic"), _("Armenian"), _("Basque"), _("Bengali"), _("Bosnian"), _("Bulgarian"),
        _("Catalan"), _("Chinese"), _("Croatian"), _("Czech"), _("Danish"), _("Dutch"), _("English"),
        _("Estonian"), _("Persian"), _("Finnish"), _("French"), _("Galician"), _("Georgian"), _("German"),
        _("Greek"), _("Hebrew"), _("Hindi"), _("Hungarian"), _("Icelandic"), _("Indonesian"), _("Italian"),
        _("Japanese"), _("Korean"), _("Kurdish"), _("Latvian"), _("Lithuanian"), _("Macedonian"), _("Malay"),
        _("Norwegian"), _("Polish"), _("Portuguese"), _("Brazilian Portuguese"), _("Romanian"), _("Russian"),
        _("Serbian"), _("Sinhala"), _("Slovak"), _("Slovenian"), _("Spanish"), _("Swedish"), _("Tamil"),
        _("Thai"), _("Turkish"), _("Ukrainian"), _("Urdu"), _("Vietnamese"),
    )

    @staticmethod
    def _trackLabel(track, trackIdx, count):
        # "[AAC] German" for a stream language tag "ger"/"deu"; the tag "und" (ISO 639-2: undetermined, set by
        # many encoders when nobody entered a language) or an empty one leaves just the codec - with the track
        # number when there are several; any other name (a stream title like "Deutsch (AD)") as it is
        name = str(track.get('name', '')).strip()
        if name.lower() in ('', 'und', 'unknown', 'n/a'):
            name = '%d' % (trackIdx + 1) if count > 1 else ''
        elif len(name) <= 3 and langCode(name):
            name = _(langName(name))
        else:
            name = _(name)
        return ('[%s] %s' % (track.get('encode', ''), name)).strip()

    def selectAudioTrack(self):
        printDBG("selectAudioTrack")
        tracksTab = self.playback['AudioTracks']
        if len(tracksTab):
            options = []
            printDBG(">>>>>>>>>>>> AudioTrack[%s]" % self.playback['AudioTrack'])
            currentId = self.playback['AudioTrack'].get('id', -1)
            currIdx = 0
            for trackIdx in range(len(tracksTab)):
                name = self._trackLabel(tracksTab[trackIdx], trackIdx, len(tracksTab))
                item = IPTVChoiceBoxItem(name, "", {'track_id': tracksTab[trackIdx]['id'], 'track_idx': trackIdx})
                if tracksTab[trackIdx]['id'] == currentId:
                    item.type = IPTVChoiceBoxItem.TYPE_ON
                    currIdx = trackIdx
                else:
                    item.type = IPTVChoiceBoxItem.TYPE_OFF
                options.append(item)
            if self._dualMonoSelectable():
                # exteplayer3 188 "achannel": left / both / right channel of dual mono audio (two languages)
                for channel, label in ((0, _("Left")), (1, _("Stereo")), (2, _("Right"))):
                    item = IPTVChoiceBoxItem("%s: %s" % (_("Dual mono"), label), "", {'audio_channel': channel})
                    item.type = IPTVChoiceBoxItem.TYPE_ON if channel == self.audioChannel else IPTVChoiceBoxItem.TYPE_OFF
                    options.append(item)
            self.openChild(boundFunction(self.childClosed, self.selectAudioTrackCallback), IPTVChoiceBoxWidget, {'width': 500, 'height': self._getChoiceBoxHeight(len(options)), 'current_idx': currIdx, 'title': _("Select audio track"), 'options': options, 'chrome': True, 'footerMargin': 136})
        else:
            self.showMessage(_("Information about audio tracks not available."), MessageBox.TYPE_INFO, None)

    def selectAudioTrackCallback(self, ret):
        printDBG("selectAudioTrackCallback ret[%r]" % [ret])
        if isinstance(ret, IPTVChoiceBoxItem):
            ret = ret.privateData
            if 'audio_channel' in ret:
                self.audioChannel = ret['audio_channel']
                self.extPlayerCmddDispatcher.setAudioChannel(ret['audio_channel'])
            elif 'track_id' in ret and ret['track_id'] != self.playback['AudioTrack'].get('id', -1):
                self.metaHandler.setAudioTrackIdx(ret.get('track_idx', -1))
                self.extPlayerCmddDispatcher.setAudioTrack(ret['track_id'])
                if self.audioChannel != 1:
                    # a dual mono channel belongs to the track it was chosen for
                    self.audioChannel = 1
                    self.extPlayerCmddDispatcher.setAudioChannel(1)

    def _dualMonoSelectable(self):
        # a track of at most two channels (the player reports "c" since v186, 0 when unknown)
        if 'eplayer' != self.player or not ExtePlayer3Cap('achannel'):
            return False
        try:
            return int(self.playback['AudioTrack'].get('c', 0) or 0) <= 2
        except (TypeError, ValueError):
            return False

    def selectSubtitle(self):
        printDBG("IPTVExtMoviePlayer.selectSubtitle")
        options = []

        currIdx = self.metaHandler.getSubtitleIdx() + 1
        ####################################
        embeddedTrackId = self.playback['SubtitleTrack'].get('id', -1)
        embeddedTracksTab = self.playback['SubtitleTracks']
        if embeddedTrackId > -1:
            currIdx = 0
        ####################################

        # the row of the active track (embedded tracks are listed before the external ones)
        selRowIdx = 0
        item = IPTVChoiceBoxItem(_('None'), "", {'other': 'none'})
        if 0 == currIdx and -1 == embeddedTrackId:
            item.type = IPTVChoiceBoxItem.TYPE_ON
        else:
            item.type = IPTVChoiceBoxItem.TYPE_OFF
        options.append(item)

        #####################################
        for trackIdx in range(len(embeddedTracksTab)):
            name = self._trackLabel(embeddedTracksTab[trackIdx], trackIdx, len(embeddedTracksTab))
            item = IPTVChoiceBoxItem(name, "", {'track_id': embeddedTracksTab[trackIdx]['id'], 'track_idx': trackIdx})
            if embeddedTracksTab[trackIdx]['id'] == embeddedTrackId:
                item.type = IPTVChoiceBoxItem.TYPE_ON
                selRowIdx = len(options)
            else:
                item.type = IPTVChoiceBoxItem.TYPE_OFF
            options.append(item)
        #####################################

        tracksTab = self.metaHandler.getSubtitlesTracks()
        for trackIdx in range(len(tracksTab)):
            name = '[{0}] {1}'.format(tracksTab[trackIdx]['lang'], tracksTab[trackIdx]['title'])
            item = IPTVChoiceBoxItem(name, "", {'track_idx': trackIdx})
            if (trackIdx + 1) == currIdx:
                item.type = IPTVChoiceBoxItem.TYPE_ON
                selRowIdx = len(options)
            else:
                item.type = IPTVChoiceBoxItem.TYPE_OFF
            options.append(item)
        if len(embeddedTracksTab) and 'eplayer' == self.player and ExtePlayer3Cap('forcedonly'):
            # exteplayer3 188: of the embedded track only the forced cues (flagged PGS pictures, a forced track)
            item = IPTVChoiceBoxItem(_("Only forced subtitles"), "", {'other': 'forced_only'})
            item.type = IPTVChoiceBoxItem.TYPE_ON if self.forcedSubtitlesOnly else IPTVChoiceBoxItem.TYPE_OFF
            options.append(item)
        if self.subHandler['enabled'] and None is not self.metaHandler.getSubtitleTrack():
            options.append(IPTVChoiceBoxItem(_('Synchronize'), "", {'other': 'synchro'}))
        if len(self.externalSubTracks):
            for item in self.externalSubTracks:
                title = '[{0}] {1} ({2})'.format(item.get('lang', ''), item['title'], _('Download suggested'))
                options.append(IPTVChoiceBoxItem(title, "", {'other': 'download_suggested', 'track': item}))
        options.append(IPTVChoiceBoxItem(_('Load'), "", {'other': 'load'}))
        options.append(IPTVChoiceBoxItem(_('Download'), "", {'other': 'download'}))
        printDBG("IPTVExtMoviePlayer.selectSubtitle options = %s" % str(options))
        self.openChild(boundFunction(self.childClosed, self.selectSubtitleCallback), IPTVChoiceBoxWidget, {'width': 600, 'height': self._getChoiceBoxHeight(len(options)), 'current_idx': selRowIdx, 'title': _("Select subtitles track"), 'options': options, 'chrome': True, 'footerMargin': 136})

    def selectSubtitleCallback(self, ret):
        printDBG("selectSubtitleCallback ret[%r]" % [ret])
        if isinstance(ret, IPTVChoiceBoxItem):
            ret = ret.privateData
            if 'other' in ret:
                option = ret['other']
                if option == 'none':
                    # to speed up, should be set also as output from exteplayer3
                    self.playback['SubtitleTrack'] = {'id': -1}
                    self.metaHandler.setSubtitleIdx(-1)
                    self.metaHandler.setEmbeddedSubtileTrackIdx(-1)
                    self.disableSubtitles()
                elif option == 'synchro':
                    self.showSubSynchroControl()
                elif option == 'forced_only':
                    self.forcedSubtitlesOnly = not self.forcedSubtitlesOnly
                    self.extPlayerCmddDispatcher.setForcedSubtitlesOnly(self.forcedSubtitlesOnly)
                elif option == 'load':
                    self.openSubtitlesFromFile()
                elif option == 'download':
                    self.downloadSub()
                elif option == 'download_suggested' and 'track' in ret:
                    self.downloadSub([ret['track']])
            elif 'track_id' in ret:
                self.metaHandler.setEmbeddedSubtileTrackIdx(ret['track_idx'])
                self.metaHandler.setSubtitleIdx(-1)
                self.enableEmbeddedSubtitles(ret['track_id'])
            elif 'track_idx' in ret:
                self.metaHandler.setSubtitleIdx(ret['track_idx'])
                # to speed up, should be set also as output from exteplayer3
                self.playback['SubtitleTrack'] = {'id': -1}
                self.metaHandler.setEmbeddedSubtileTrackIdx(-1)
                self.extPlayerCmddDispatcher.setSubtitleTrack(-1)
                self.subHandler['embedded_handler'].flushSubtitles()
                self.flushGraphicSubtitles()
                self.enableSubtitles()

    def _looksLikeSubtitleFile(self, filePath):
        try:
            sts, reason = self._detectSubtitleFile(filePath)
            if not sts:
                printDBG("IPTVExtMoviePlayer._looksLikeSubtitleFile skip file[%s] reason[%s]" % (filePath, reason))
            return sts
        except Exception:
            printExc()
        return False

    def _detectSubtitleFile(self, filePath):
        if None is filePath or '' == filePath:
            return False, 'empty path'
        if not fileExists(filePath):
            return False, 'missing file'

        ext = os_path.splitext(filePath)[1].lower().lstrip('.')
        # every format the file picker offers (mpl always, ssa/smi/ttml/... with the parser extension)
        if ext not in self.NON_SUBTITLE_SIDE_EXTENSIONS and ext not in IPTVSubtitlesHandler.getSupportedFormats():
            return False, 'unsupported extension'

        try:
            with open(filePath, 'rb') as f:
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
            elif re.match(r'^\d+$', line):
                score += 1
            elif re.match(r'^\d{2}:\d{2}:\d{2}[,.]\d{1,3}', line):
                score += 2
            elif re.match(r'^\d{1,2}:\d{2}:\d{2}[:=]', line):  # TMPlayer
                score += 2
            elif re.match(r'^\{\d+\}\{\d*\}', line):
                score += 3
            elif 'vtt' == ext and line.upper().startswith('WEBVTT'):
                score += 3
            elif re.match(r'^\[\d+\]\[\d+\]', line):  # MPL2
                score += 3
            elif re.match(r'^(dialogue:|\[script info\]|\[events\])', line.lower()):  # SSA/ASS
                score += 3
            elif re.search(r'<(sync|sami|tt[\s>]|time\s+begin)|\sbegin="', line.lower()):  # SAMI, TTML, RealText
                score += 3
            elif re.match(r'^(\{\d+:\d{2}:\d{2}\}|\[\d{2}:\d{2}:\d{2}\])', line):  # PSB, DKS
                score += 3

        if score >= 3:
            return True, 'subtitle markers detected'
        return False, 'no subtitle markers detected'

    def openSubtitlesFromFile(self):
        printDBG("openSubtitlesFromFile")
        currDir = GetSubtitlesDir()

        fileSRC = self.fileSRC
        tmpMatch = 'file://'
        if fileSRC.startswith(tmpMatch):
            fileSRC = fileSRC[len(tmpMatch):].replace('//', '/')
        if fileExists(fileSRC) and not fileSRC.endswith('/.iptv_buffering.flv'):
            try:
                currDir, tail = os_path.split(fileSRC)
            except Exception:
                printExc()

        fileMatch = re.compile(r"^.*?(?:\.%s)$" % r'|\.'.join(IPTVSubtitlesHandler.getSupportedFormats()), re.IGNORECASE)
        self.openChild(boundFunction(self.childClosed, self.openSubtitlesFromFileCallback), IPTVFileSelectorWidget, currDir, _("Select subtitles file"), fileMatch)

    def openSubtitlesFromFileCallback(self, filePath=None):
        printDBG("openSubtitlesFromFileCallback filePath[%s]" % filePath)
        if None is not filePath:
            if not self._looksLikeSubtitleFile(filePath):
                printDBG("openSubtitlesFromFileCallback rejected non subtitle file[%s]" % filePath)
                return
            self.subHandler['handler'].removeCacheFile(filePath)
            cmd = '/usr/bin/uchardet "%s"' % shellQuote(filePath)
            self.workconsole = iptv_system(cmd, boundFunction(self.enableSubtitlesFromFile, filePath))

    def enableSubtitlesFromFile(self, filePath, code=127, encoding=""):
        encoding = MapUcharEncoding(encoding)
        if 0 != code or 'unknown' in encoding:
            encoding = ''
        else:
            encoding = encoding.strip()

        # WORKAROUND for incorrectly recognized CP1250 encoding as iso-8859-2
        # because charset do not have model for CP1250 for polish language,
        # it incorrectly recognizes such coding as iso-8859-2
        if GetDefaultLang() == 'pl' and encoding == 'iso-8859-2':
            encoding = GetPolishSubEncoding(filePath)
        elif '' == encoding:
            encoding = 'utf-8'

        printDBG("enableSubtitlesFromFile filePath[%s] encoding[%s]" % (filePath, encoding))
        if None is not filePath:
            lang = CParsingHelper.getSearchGroups(filePath, r"_([a-z]{2})_[0-9]+?_[0-9]+?_[0-9]+?(?:\.%s)$" % r'|\.'.join(IPTVSubtitlesHandler.getSupportedFormats()))[0]
            try:
                currDir, fileName = os_path.split(filePath)
            except Exception:
                printExc()
                return
            trackIdx = -1
            tracks = self.metaHandler.getSubtitlesTracks()
            for idx in range(len(tracks)):
                try:
                    if os_path.samefile(tracks[idx]['path'], filePath):
                        trackIdx = idx
                        break
                except Exception:
                    printExc()
            if -1 == trackIdx:
                trackIdx = self.metaHandler.addSubtitleTrack({"title": fileName, "id": "", "provider": "", "lang": lang, "delay_ms": 0, "path": filePath})
            self.metaHandler.setSubtitleIdx(trackIdx)
            self.enableSubtitles(encoding)

    def disableSubtitles(self):
        self.playback['SubtitleTrack'] = {'id': -1}
        self.extPlayerCmddDispatcher.setSubtitleTrack(-1)
        self.subHandler['embedded_handler'].flushSubtitles()
        self.flushGraphicSubtitles()
        self.hideSubtitles()
        self.subHandler['enabled'] = False
        self.updateSubSynchroControl()
        self.subtitlesChanged()

    def subtitlesChanged(self):
        # subtitles switched on / off / to another track: the subtitle badge, the info row, the "Playback info" page
        self.refreshInfoBarFormats()
        self.infoPanel.updateStream()

    def enableEmbeddedSubtitles(self, id):
        printDBG("enableEmbeddedSubtitles")
        if self.playback['SubtitleTrack'].get('id', -1) != id:
            self.subHandler['embedded_handler'].flushSubtitles()
            self.flushGraphicSubtitles()
            self.extPlayerCmddDispatcher.setSubtitleTrack(id)
        self.subHandler['handler_type'] = 'embedded_handler'
        self.subHandler['marker'] = None
        self.subHandler['enabled'] = True
        self.updateSubSynchroControl()
        if self.setMoviePlayerConfig:
            self.setMoviePlayerConfig = False
            self.runConfigMoviePlayerCallback(True)

    def _autoEnableSubtitleFile(self):
        # setting "auto enable": a subtitle file next to a played file
        if not self.subConfig['auto_enable']:
            return
        fileSRC = self.fileSRC
        tmpMatch = 'file://'
        if fileSRC.startswith(tmpMatch):
            fileSRC = fileSRC[len(tmpMatch):].replace('//', '/')
        if not fileExists(fileSRC) or fileSRC.endswith('/.iptv_buffering.flv'):
            return
        subFile = ''
        try:
            name, ext = os_path.splitext(fileSRC)
            # name.srt / name.vtt ... first, then the ones saved with a download: name.de.srt - the box
            # language first, then English, then any. Only files that read as subtitles: name.txt is
            # mostly the description sidecar of a download, it must not end the search
            boxLang = GetDefaultLang()
            langs = ['.%s.' % boxLang] + (['.en.'] if boxLang != 'en' else [])

            def langRank(path):
                suffix = path[len(name):].lower()
                for idx, lang in enumerate(langs):
                    if suffix.startswith(lang):
                        return idx
                return len(langs)
            candidates = [name + '.' + ext for ext in IPTVSubtitlesHandler.getSupportedFormats()]
            candidates += [path for path in sorted(subtitleSidecarFiles(name), key=langRank) if path not in candidates]
            for candidate in candidates:
                if self._detectSubtitleFile(candidate)[0]:  # also checks that the file is there
                    subFile = candidate
                    break
        except Exception:
            printExc()
        if '' != subFile:
            self.openSubtitlesFromFileCallback(subFile)

    def enableSubtitles(self, encoding='utf-8'):
        printDBG("enableSubtitles")
        if self.isClosing:
            return
        track = self.metaHandler.getSubtitleTrack()
        if None is track:
            if not self.metaHandler.hasSubtitlesTracks():
                self._autoEnableSubtitleFile()
            return

        printDBG("enableSubtitles track[%s]" % track)
        path = track['path']
        if path and not fileExists(path):
            # a remembered subtitle file that is gone (the download manager put it into the MKV, or it was deleted):
            # forgotten without an error, the search for one next to the video runs instead (also when other tracks
            # are remembered - none of them was the chosen one)
            printDBG("enableSubtitles file gone, track dropped [%s]" % path)
            self.metaHandler.removeSubtitleTrack(self.metaHandler.getSubtitleIdx())
            self._autoEnableSubtitleFile()
            return
        sts = self.subHandler['handler'].loadSubtitles(path, encoding)
        if not sts:
            # we will remove this subtitles track as it is can not be used
            self.metaHandler.removeSubtitleTrack(self.metaHandler.getSubtitleIdx())
            msg = _("An error occurred while loading a subtitle from [%s].") % path
            self.showMessage(msg, MessageBox.TYPE_ERROR)
            return
        self.subHandler['handler_type'] = 'handler'
        self.subHandler['marker'] = None
        self.subHandler['enabled'] = True
        self.updateSubSynchroControl()
        self.subtitlesChanged()
        if self.setMoviePlayerConfig:
            self.setMoviePlayerConfig = False
            self.runConfigMoviePlayerCallback(True)

    def updatSubtitlesTime(self):
        if -1 != self.subHandler['last_time'] and -1 != self.subHandler['latach_time']:
            timeMS = self.subHandler['last_time'] + int((time.time() - self.subHandler['latach_time']) * 1000)
            self.subHandler['current_sub_time_ms'] = timeMS
            self.updateSubtitles(timeMS)

    def restartSubTimer(self):
        if 'Play' != self.playback['Status']:
            return
        if not self.subHandler['enabled']:
            return
        self.subHandler['timer'].stop()
        self.subHandler['timer'].start(100)

    def latchSubtitlesTime(self, timeMS):
        self.subHandler['latach_time'] = time.time()
        self.subHandler['last_time'] = timeMS
        self.restartSubTimer()
        self.updateSubtitles(timeMS)

    def updateSubtitles(self, timeMS, force=False):
        if self.isClosing:
            return
        if not self.subHandler['enabled']:
            return
        if None is self.metaHandler.getSubtitleTrack() and 'handler' == self.subHandler['handler_type']:
            return

        # marker is used for optimization
        # we remember some kind of fingerprint for last subtitles
        # subtitles handler first check this fingerprint
        # if the previous one is the same as current and it will return None instead
        # of subtitles text
        prevMarker = self.subHandler['marker']
        if force:
            prevMarker = None

        handler_type = self.subHandler['handler_type']
        if handler_type == 'handler':
            delay_ms = self.metaHandler.getSubtitleTrackDelay()
        else:
            delay_ms = 0
            self.updateGraphicSubtitles(timeMS, force)
        marker, text = self.subHandler[handler_type].getSubtitles(timeMS + delay_ms, prevMarker)
        if None is not text:
            self.subHandler['marker'] = marker
            # printDBG("===============================================================")
            # printDBG(text)
            # printDBG("===============================================================")
            if "" == text:
                self.hideSubtitles()
            else:
                self.setSubtitlesText(text)

    def hideSubtitles(self):
        for idx in range(self.subLinesNum):
            self['subLabel%d' % (idx + 1)].hide()

    def addGraphicSubAtom(self, obj):
        # {"id":..,"s":<ms>,"e":<ms> or null,"r":[{"x","y","w","h","f":<png in the -G directory>}]}
        if not self.graphicSubs['enabled']:
            return
        try:
            rects = []
            for rect in obj['r']:
                rects.append({'x': int(rect['x']), 'y': int(rect['y']), 'w': int(rect['w']), 'h': int(rect['h']), 'f': os_path.basename(str(rect['f']))})
            end = obj.get('e')
            self.graphicSubs['handler'].addAtom(int(obj['s']), None if end is None else int(end), rects)
        except Exception:
            printExc()

    def updateGraphicSubtitles(self, timeMS, force=False):
        if not self.graphicSubs['enabled']:
            return
        handler = self.graphicSubs['handler']
        marker, rects = handler.getRects(timeMS, None if force else self.graphicSubs['marker'])
        if rects is None:
            return
        self.graphicSubs['marker'] = marker
        for idx in range(self.GRAPHIC_SUB_RECTS):
            widget = self['subGraphic%d' % (idx + 1)]
            pixmap = None
            if idx < len(rects):
                rect = rects[idx]
                try:
                    # every picture is a new file: openATV would keep each one in its pixmap cache otherwise
                    pixmap = LoadPixmap(path=handler.getPath(rect), cached=False)
                except Exception:
                    printExc()
            if pixmap and widget.instance:
                # the rectangles already are in screen pixels (exteplayer3 -W/-H)
                widget.instance.move(ePoint(rect['x'], rect['y']))
                widget.instance.resize(eSize(rect['w'], rect['h']))
                widget.setPixmap(pixmap)
                widget.show()
            else:
                widget.hide()

    def hideGraphicSubtitles(self):
        self.graphicSubs['marker'] = None
        for idx in range(self.GRAPHIC_SUB_RECTS):
            self['subGraphic%d' % (idx + 1)].hide()

    def flushGraphicSubtitles(self):
        self.graphicSubs['handler'].flushSubtitles()
        self.hideGraphicSubtitles()

    def clearGraphicSubtitlesDir(self):
        # PNG files left by an exteplayer3 that was killed
        try:
            for name in os_listdir(self.graphicSubs['dir']):
                if name.endswith('.png'):
                    os_remove(os_path.join(self.graphicSubs['dir'], name))
        except Exception:
            pass

    def setSubtitlesText(self, text, stripLine=True, breakToLongLine=True):
        # back = True
        desktopW = getDesktop(0).size().width()
        desktopH = getDesktop(0).size().height()
        # this method positions every subtitle line via direct
        # .instance.move()/.resize() calls computed from real desktop
        # pixels - see _subtitleScale()'s own comment for why that needs
        # its own scale factor, separate from the resolution="1280,720"
        # skin-level scaling. _effectiveSubLineHeight() additionally
        # floors the configured line_height against font_size so
        # descenders (e.g. "g") don't get clipped when the two are set
        # too close together.
        scale = self._subtitleScale()

        dW = desktopW - 20
        dH = int(self.subConfig['box_height'] * scale)

        if stripLine:
            text = text.strip()

        if self.subLinesNum == 1 and 'transparent' == self.subConfig['background']:
            self['subLabel1'].setText(text)
            self['subLabel1'].show()
        else:
            if text.startswith('{\\an8}'):
                text = text[6:]
                subOnTopHack = True
            else:
                subOnTopHack = False

            if self.subLinesNum == 1:
                lineHeight = self._effectiveSubLineHeight(scale) * (text.count('\n') + 1)
                text = [text]
            else:
                text = text.split('\n')
                if not subOnTopHack:
                    text.reverse()
                lineHeight = self._effectiveSubLineHeight(scale)
            y = int(self.subConfig['pos'] * scale)
            if not subOnTopHack:
                y += self.subHandler['pos_y_offset']
            for lnIdx in range(self.subLinesNum):
                subLabel = 'subLabel%d' % (lnIdx + 1)
                if lnIdx < len(text):
                    lnText = text[lnIdx]
                    if stripLine:
                        lnText = lnText.strip()
                else:
                    lnText = ''

                if '' == lnText:
                    self[subLabel].hide()
                    continue
                try:
                    self[subLabel].instance.resize(eSize(dW, dH))
                    self[subLabel].resize(eSize(dW, dH))

                    self[subLabel].setText(lnText)
                    textSize = self[subLabel].getSize()

                    printDBG("lines [%d] width[%d] worlds[%d]" % (len(text), textSize[0], lnText.count(' ')))
                    if breakToLongLine and len(text) == 1 and textSize[0] >= dW and lnText.count(' ') > 4:
                        lnText = lnText.split(' ')
                        splitWord = len(lnText) // 2 + 1
                        lnText = '%s\n%s' % (' '.join(lnText[:splitWord]), ' '.join(lnText[splitWord:]))
                        self.setSubtitlesText(lnText, False, False)
                        return

                    lW = textSize[0] + int(self.subConfig['font_size'] * scale) / 2
                    lH = lineHeight  # textSize[1] + self.subConfig['font_size'] / 2
                    self[subLabel].instance.resize(eSize(int(lW), int(lH)))
                    if not subOnTopHack:
                        self[subLabel].instance.move(ePoint(int((desktopW - lW) / 2), int(desktopH - y - lH)))
                    else:
                        self[subLabel].instance.move(ePoint(int((desktopW - lW) / 2), int(y)))
                    y += lH + int(self.subConfig['line_spacing'] * scale)
                    self[subLabel].show()
                except Exception:
                    printExc()

    def updateInfo(self):
        self.extPlayerCmddDispatcher.doUpdateInfo()
        self.updateBufferFill()

    def updateBufferFill(self):
        if None is not self.downloader:
            if self.downloader.hasDurationInfo() and self.downloader.getTotalFileDuration() > 0:
                totalDuration = self.downloader.getTotalFileDuration()
                downloadDuration = self.downloader.getDownloadedFileDuration()
                if 0 < totalDuration and 0 < downloadDuration:
                    self.playback['BufferFill'] = int(downloadDuration * 100000 // totalDuration)
                    self['bufferingBar'].value = self.playback['BufferFill']
                    if self.playback['Length'] is not None and self.playback['Length'] < totalDuration:
                        self.setPlaybackLength(totalDuration)
                    # the watched mark compares the stop position with this; every update, the player's length
                    # messages (the file written so far) must not shrink it again
                    self.clipLength = totalDuration
                return

            remoteFileSize = self.downloader.getRemoteFileSize() - self.totalDataSizeCorrection
            if 0 < remoteFileSize:
                localFileSize = self.downloader.getLocalFileSize(True) - self.availableDataSizeCorrection
                if 0 < localFileSize:
                    self.playback['BufferFill'] = int(localFileSize * 100000 // remoteFileSize)
                    self['bufferingBar'].value = self.playback['BufferFill']

    def showMessage(self, message, type, callback=None):
        printDBG("IPTVExtMoviePlayer.showMessage")
        if self.isClosing and type is not None:
            return
        messageItem = {'msg': message, 'type': type, 'callback': callback}
        self.messageQueue.append(messageItem)
        self.processMessageQueue()

    def processMessageQueue(self):
        if self.underMessage or 0 == len(self.messageQueue):
            return
        self.underMessage = True
        while len(self.messageQueue):
            messageItem = self.messageQueue.pop(0)
            message, type, callback = messageItem['msg'], messageItem['type'], messageItem['callback']
            if None is type and None is not callback:
                callback()
            else:
                if self.isClosing and None is not callback:
                    continue  # skip message with callback
                else:
                    self.screenSaver.deactivate()
                    self.session.openWithCallback(boundFunction(self.messageClosedCallback, callback), MessageBox, text=message, type=type)
            return

    def messageClosedCallback(self, callback, arg=None):
        self.underMessage = False
        if None is not callback:
            callback()
        else:
            self.processMessageQueue()

    def waitEOSAbortedFixTimeoutCallback(self):
        if self.waitEOSAbortedFix['EOSaborted_received']:
            self.extPlayerCmddDispatcher.stop()

    def setPlaybackLength(self, newLength):
        # fix 071026: eSlider.setRange() only takes int - a float length from a downloader crashed enigma2
        newLength = int(newLength)
        self.playback['Length'] = newLength
        self['progressBar'].range = (0, newLength)
        self['bufferingCBar'].range = (0, newLength)
        self['lengthTimeLabel'].setText(str(timedelta(seconds=newLength)))
        self.updateLcdInfo()
        self.refreshChapterMarks()
        try:
            self.updateInfoBarMeta()
            self.updateInfoBarKnob()
        except Exception:
            printExc()

    def updateLcdInfo(self):
        # feeds the colour LCD summary with position, remaining time and progress
        try:
            length = int(self.playback.get('Length') or 0)
            curr = int(self.playback.get('CurrentTime') or 0)
            # the player reports a normal length for most live streams: buffered ones play a growing file (only the
            # downloader knows), of a direct HLS stream it sees the growing playlist (the link's mark tells, without
            # one a length that keeps growing ahead of the position: setPlaybackLength() also follows a position
            # running past the length, at the end of a film or without a known length, that is length == position)
            if self.downloader is None and length > self.lcdLastLength > 0 and length > curr:
                self.lcdLengthGrowth += 1
            elif length < self.lcdLastLength:
                self.lcdLengthGrowth = 0
            self.lcdLastLength = length
            live = (self.playback.get('IsLive', False) or self.fileSRC.meta.get('iptv_livestream') or self.lcdLengthGrowth >= 3
                    or (self.downloader is not None and self.downloader.isLiveStream() is True))
            self.playback['LiveDetected'] = bool(live)
            known = length > 0 and not live
            percent = max(0, min(100, curr * 100 // length)) if known else 0
            state = (curr, length, live)
            if state == self.lcdLastState:
                return
            self.lcdLastState = state
            self['lcdProgress'].value = percent
            self['lcdCurrTime'].setText(str(timedelta(seconds=curr)))
            self['lcdCurrTimeHM'].setText(lcdTimeHM(curr))
            if known:
                remained = max(0, length - curr)
                self['lcdRemained'].setText('-' + str(timedelta(seconds=remained)))
                self['lcdRemainedHM'].setText(lcdTimeHM(remained))
                self['lcdRemainedMin'].setText('%d' % (remained // 60) if remained > 60 else '+%ds' % remained)
                self['lcdRemainedShort'].setText('+%d %s' % (remained // 60, _('min')) if remained >= 60 else '+%ds' % remained)
                self['lcdLength'].setText(str(timedelta(seconds=length)))
                self['lcdLengthHM'].setText(lcdTimeHM(length))
                self['lcdPercent'].setText('%d%%' % percent)
            elif live:
                self['lcdRemained'].setText(_('Live'))
                self['lcdRemainedHM'].setText(_('Live'))
                self['lcdRemainedMin'].setText(_('Live'))
                self['lcdRemainedShort'].setText(_('Live'))
                self['lcdLength'].setText('')
                self['lcdLengthHM'].setText('')
                self['lcdPercent'].setText('')
            else:
                # length not known yet: show placeholders, so the fields do not pop up later
                self['lcdRemained'].setText('-0:00:00')
                self['lcdRemainedHM'].setText('0:00')
                self['lcdRemainedMin'].setText('0')
                self['lcdRemainedShort'].setText('')
                self['lcdLength'].setText('0:00:00')
                self['lcdLengthHM'].setText('0:00')
                self['lcdPercent'].setText('0%')
        except Exception:
            printExc()

    def playbackUpdateInfo(self, stsObj):
        # fix TypeError: '>' not supported between instances of 'NoneType' and 'int'
        try:
            # workaround for missing playback length info for under muxing MKV
            if self.playback['Length'] > 0 and self.downloader is not None and self.downloader.getName() == 'ffmpeg':
                stsObj['Length'] = self.playback['Length']

            for key, val in stsObj.items():
                if 'Length' == key:
                    if 0 > val:
                        printDBG('IPTVExtMoviePlayer.playbackUpdateInfo Length[%d] - live stream?' % val)
                        val = 0
                        self.playback['IsLive'] = True
                    else:
                        self.playback['IsLive'] = False
                    if 0 < val and self.showInfoBarAtLength:
                        self.showInfoBarAtLength = False
                        self.showPlaybackInfoBar()
                    if 0 < val:
                        # restore last position
                        if 10 < self.lastPosition and self.lastPosition < (self.playback['Length'] - 10):
                            self.updateBufferFill()
                            if self.playback['BufferFill'] > 0:
                                max = self.playback['Length'] * self.playback['BufferFill'] / 100000
                                if max > self.playback['Length']:
                                    max = self.playback['Length']
                            else:
                                max = self.playback['Length']

                            if self.lastPosition <= max:
                                self.showPlaybackInfoBar()
                                self.extPlayerCmddDispatcher.doGoToSeek(str(self.lastPosition - 5))
                                self.lastPosition = 0
                        tmpLength = self.playback['BufferCTime']
                        if self.playback['CurrentTime'] > tmpLength:
                            tmpLength = self.playback['CurrentTime']
                        if val > tmpLength:
                            tmpLength = val
                            # buffering: the player plays the file written so far, its length is no clip length while
                            # the download runs (an episode stopped after 3 of 53 minutes counted as watched) -
                            # updateBufferFill() sets the known total then; once the file is complete it is
                            if None is self.downloader or not self.downloader.isDownloading():
                                self.clipLength = val
                        if self.playback['Length'] is not None and self.playback['Length'] < tmpLength:
                            if None is self.downloader or not self.downloader.hasDurationInfo():
                                self.setPlaybackLength(tmpLength)
                        self.playback['LengthFromPlayerReceived'] = True
                elif 'CurrentTime' == key:
                    if self.playback['Length'] is not None and self.playback['Length'] < val and val > self.playback['BufferCTime']:
                        self.setPlaybackLength(val)
                    self['progressBar'].value = val
                    prevCTime = self.playback['CurrentTime']
                    self.playback['CurrentTime'] = stsObj['CurrentTime']
                    if 0 < self.playback['CurrentTime']:
                        self.hideStartCover()
                        self.scheduleAudioCover()
                        self.playback['StartGoToSeekTime'] = self.playback['CurrentTime']
                        diff = self.playback['CurrentTime'] - prevCTime
                        if diff > 0 and diff < 3:  # CurrentTime in seconds
                            self.playback['ConfirmedCTime'] = self.playback['CurrentTime']
                    self['currTimeLabel'].setText(str(timedelta(seconds=self.playback['CurrentTime'])))
                    self['remainedLabel'].setText('-' + str(timedelta(seconds=self.playback['Length'] - self.playback['CurrentTime'])))
                    self.updateLcdInfo()
                    self.updateChapterTitle()
                    if time.time() >= self.seekLimitNotice['until']:
                        self['pleaseWait'].hide()
                elif 'BufferCTime' == key:
                    if self.playback['Length'] is not None and self.playback['Length'] < val:
                        self.setPlaybackLength(val)
                    self.playback['BufferCTime'] = val
                    self['bufferingCBar'].value = val
                elif 'Status' == key:
                    # curSts = self.playback['Status']
                    if self.playback['Status'] != val[0]:
                        if 'Play' == val[0]:
                            self.showPlaybackInfoBar()
                        elif val[0] in ['Pause', 'FastForward', 'SlowMotion']:
                            self.showPlaybackInfoBar(blocked=True)
                        self.playback['Status'] = val[0]
                        self.updateBackdrop()
                        self['statusIcon'].setPixmap(self.playback['statusIcons'].get(val[0], None))
                elif 'IsLoop' == key:
                    if self.playback['IsLoop'] != val:
                        self.playback['IsLoop'] = val
                        icon = 'Off'
                        if val:
                            icon = 'On'
                        self['loopIcon'].setPixmap(self.playback['loopIcons'].get(icon, None))
                        self.showPlaybackInfoBar()

                elif 'VideoTrack' == key:
                    self.playback[key] = val
                    codec = val['encode'].split('/')[-1]
                    text = "%s %sx%s" % (codec, val['width'], val['height'])
                    if val['progressive']:
                        text += 'p'
                    elif False is val['progressive']:
                        text += 'i'
                    fps = self.currentFrameRate()
                    if fps == floor(fps):
                        fps = int(fps)
                    if fps:
                        text += ', %sfps' % fps
                    # without the aspect ratio: for the audio format when the line has no room (skin without badges)
                    shortText = text
                    text += ', %s' % val['aspect_ratio'].replace('_', ':')
                    streamType = self._getStreamTypeLabel()
                    if streamType:
                        text += ', %s' % streamType
                        shortText += ', %s' % streamType
                    self.videoInfoText = text
                    self.videoInfoShortText = shortText
                    self['videoInfo'].setText(text)
                else:
                    self.playback[key] = val
                    printDBG(">>> playback[%s] = %s" % (key, val))
            if ('VideoTrack' in stsObj or 'AudioTrack' in stsObj) and self.infoBarBadgeLayout is None:
                # a skin without format badges: the audio format after the video line ("... | E-AC3 5.1")
                self._setVideoInfoWithAudio()
            if 'VideoTrack' in stsObj or 'AudioTrack' in stsObj or 'SubtitleTrack' in stsObj:
                self.infoPanel.updateStream()
                self.refreshInfoBarFormats()
            if ('VideoTrack' in stsObj or 'AudioTrack' in stsObj) and self.infoBarBadgeLayout is not None:
                # a local file: ffprobe fills in what an older player does not report (once the player could read it,
                # the buffer file has its header then)
                self.infoPanel.startProbe()
            if 'CurrentTime' in stsObj:
                self.updateInfoBarKnob()
            if 'NowPlaying' in stsObj:
                self.updateNowPlaying()
            if 'VideoTrack' in stsObj:
                # the picture is decoded: no audio poster over it
                self.hideAudioCover()
        except Exception:
            printExc(WarnOnly=True)

    def currentFrameRate(self):
        fps = (self.playback.get('VideoTrack') or {}).get('frame_rate', 0) or 0
        if not 0 < fps <= 120:
            # exteplayer3 takes ffmpeg's guess, for a DASH time base of 1/200 (BBC) that is 200 fps - the frame rate
            # of the link list then, else none
            try:
                fps = float(strwithmeta(self.fileSRC).meta.get('iptv_frame_rate') or 0)
            except Exception:
                fps = 0
        return fps

    def trackLanguageName(self, name):
        # "ger" / "deu" -> "German" as in the track lists (_trackLabel), any other name as it is
        name = str(name or '').strip()
        if len(name) <= 3 and langCode(name):
            return _(langName(name))
        return name

    def currentSubtitleInfo(self):
        # the shown subtitles for the "Playback info" page: an embedded track or a file
        embedded = self.playback.get('SubtitleTrack') or {}
        if embedded.get('id', -1) > -1:
            tracks = self.playback.get('SubtitleTracks') or []
            index = 0
            for idx, track in enumerate(tracks):
                if track.get('id') == embedded['id']:
                    index = idx + 1
                    break
            return {'kind': 'embedded', 'index': index, 'count': len(tracks), 'lang': embedded.get('name', ''),
                    'title': embedded.get('t', ''), 'format': subtitleFormatName(embedded.get('encode', '')), 'forced': embedded.get('forced', False)}
        track = self.metaHandler.getSubtitleTrack() if self.subHandler['enabled'] else None
        if track:
            path = track.get('path', '') or ''
            return {'kind': 'file', 'lang': track.get('lang', ''), 'title': track.get('title', ''),
                    'format': subtitleFormatName(os_path.splitext(path)[1].lstrip('.').upper())}
        return {}

    def doGoToSeek(self):
        self.playback['GoToSeekTimer'].stop()
        if self.playback['GoToSeeking']:
            self.showPlaybackInfoBar()
            self.playback['StartGoToSeekTime'] = self.playback['GoToSeekTime']
            printDBG("IPTVExtMoviePlayer.doGoToSeek current[%r] target[%r] length[%r]" % (self.playback['CurrentTime'], self.playback['GoToSeekTime'], self.playback['Length']))
            # a seek of the user's own: the position no longer belongs to the last chapter jump (chapterPosMs)
            self.chapterJump = None
            self.extPlayerCmddDispatcher.doGoToSeek(str(self.playback['GoToSeekTime']))
            self.playback['GoToSeeking'] = False
            self['goToSeekPointer'].hide()
            self["goToSeekLabel"].hide()

    def doGoToSeekPointerMove(self, seek):
        printDBG('IPTVExtMoviePlayer.doGoToSeekPointerMove seek[%r], LengthFromPlayerReceived[%r], GoToSeeking[%r]' % (seek, self.playback['LengthFromPlayerReceived'], self.playback['GoToSeeking']))
        self.playback['GoToSeekTimer'].stop()
        if not self.playback['LengthFromPlayerReceived']:
            return
        if self.playback['Length'] <= 0:
            # live streams report a zero length, no seek bar to move
            return
        if not self.playback['GoToSeeking']:
            self.playback['GoToSeeking'] = True
            self.playback['GoToSeekTime'] = self.playback['StartGoToSeekTime']
            self.showPlaybackInfoBar([], True)
            self['goToSeekPointer'].show()
            self["goToSeekLabel"].show()

        # update data
        if self.playback['BufferFill'] > 0:
            max = self.playback['Length'] * self.playback['BufferFill'] // 100000
            if max > self.playback['Length']:
                max = self.playback['Length']
            if max < self.playback['BufferCTime']:
                max = self.playback['BufferCTime']
        else:
            max = self.playback['Length']
        # buffering: never onto the end of the downloaded part (bufferedEnd(), like the skip keys) - exteplayer3 stood
        # still at the end of the file still being written
        bufEnd = self.bufferedEnd()
        if bufEnd is not None and max > bufEnd:
            max = bufEnd if bufEnd > self.playback['CurrentTime'] else self.playback['CurrentTime']

        pos = self.playback['GoToSeekTime'] + seek
        wanted = pos
        if pos > max:
            pos = max
        if pos < 0:
            pos = 0
        printDBG("IPTVExtMoviePlayer.doGoToSeekPointerMove seek[%r] current[%r] limit[%r] length[%r] wanted[%r] pointer[%r]" % (seek, self.playback['CurrentTime'], max, self.playback['Length'], wanted, pos))
        if seek > 0 and wanted > max and max < self.playback['Length']:
            # the seek bar is cut at the end of the downloaded part (buffering): say so, so the key does not look broken
            self.showSeekLimitNotice(max)

        self.playback['GoToSeekTime'] = pos
        self["goToSeekLabel"].setText(str(timedelta(seconds=int(self.playback['GoToSeekTime']))))

        # update position
        # convert time to width
        relativeX = self["progressBar"].instance.size().width() * self.playback['GoToSeekTime'] / self.playback['Length']
        x = self['progressBar'].position[0] - self["goToSeekPointer"].getWidth() / 2 + relativeX

        self['goToSeekPointer'].setPosition(x, self['goToSeekPointer'].position[1])
        self["goToSeekLabel"].setPosition(x, self['goToSeekLabel'].position[1])

        # trigger delayed seek
        self.playback['GoToSeekTimer'].start(1000)

    def saveLastPlaybackTime(self):
        lastPosition = self.playback.get('ConfirmedCTime', 0)
        length = self.playback['Length'] or 0
        if config.plugins.iptvplayer.remember_last_position.value and lastPosition > 0 and length > (config.plugins.iptvplayer.remember_last_position_time.value * 60):
            # watched to the end: the next start begins at 0 instead of at the old position. With buffering the length
            # is only the length of the part written so far, unless the downloader knows the whole duration
            # (a length the player did not report, or of a live stream, follows the position: always "at the end")
            lengthKnown = (None is self.downloader or self.downloader.hasDurationInfo()) and self.playback['LengthFromPlayerReceived'] and not self.playback['LiveDetected']
            if lengthKnown and lastPosition >= length - max(30, length * 0.03):
                printDBG("saveLastPlaybackTime position[%r] length[%r] watched to the end -> reset" % (lastPosition, length))
                lastPosition = -1
            self.metaHandler.setLastPosition(lastPosition)

    def loadLastPlaybackTime(self):
        if config.plugins.iptvplayer.remember_last_position.value and self.lastPosition < 1:
            self.lastPosition = self.metaHandler.getLastPosition()

    # handling of RCU keys
    def key_stop(self, requestedByUser="key_stop"):
        self.setPleaseWait(_("Closing. Please wait..."))
        self.closeRequestedByUser = requestedByUser
        if self.console is not None:
            if self.extPlayerCmddDispatcher.stop():
                self.saveLastPlaybackTime()
        else:
            self.isClosing = True

    def key_play(self):
        self.extPlayerCmddDispatcher.play()

    def key_pause(self):
        # remotes with one play/pause key send pause in both states
        if 'Pause' == self.playback['Status']:
            self.extPlayerCmddDispatcher.play()
        else:
            self.extPlayerCmddDispatcher.pause()

    def key_exit(self):
        self.doExit()

    def key_info(self):
        self.doInfo()

    def key_seek1(self):
        self.doSeek(config.seek.selfdefined_13.value * -1)

    def key_seek3(self):
        self.doSeek(config.seek.selfdefined_13.value)

    def key_seek4(self):
        self.doSeek(config.seek.selfdefined_46.value * -1)

    def key_seek6(self):
        self.doSeek(config.seek.selfdefined_46.value)

    def key_seek7(self):
        self.doSeek(config.seek.selfdefined_79.value * -1)

    def key_seek9(self):
        self.doSeek(config.seek.selfdefined_79.value)

    def key_seekFwd(self):
        self.extPlayerCmddDispatcher.seekFwd()

    def key_seekBack(self):
        self.extPlayerCmddDispatcher.seekBack()

    def key_left_press(self):
        self.goToSeekKey(-1, "press")

    def key_left_repeat(self):
        self.goToSeekKey(-1, "repeat")

    def key_rigth_press(self):
        self.goToSeekKey(1, "press")

    def key_rigth_repeat(self):
        self.goToSeekKey(1, "repeat")

    def key_up_press(self):
        self.goSubKey(-1, "press")

    def key_up_repeat(self):
        self.goSubKey(-1, "repeat")

    def key_down_press(self):
        self.goSubKey(1, "press")

    def key_down_repeat(self):
        self.goSubKey(1, "repeat")

    def bufferedEnd(self):
        # buffering: the last second of the part downloaded so far (like the seek pointer's limit), None without buffering
        # or when the downloaded part is not known
        if None is self.downloader or self.playback['BufferFill'] <= 0 or not self.playback['Length']:
            return None
        end = min(self.playback['Length'] * self.playback['BufferFill'] // 100000, self.playback['Length'])
        end = max(end, self.playback['BufferCTime'])
        # a few seconds before the end: a jump right onto it would stop again at once
        return max(0, end - 5) if end < self.playback['Length'] else end

    def showSeekLimitNotice(self, loadedUpTo):
        # a skip key was cut at the end of the downloaded part: a short notice, so the key does not look broken
        try:
            self.seekLimitNotice['text'] = _("Only loaded up to %s") % str(timedelta(seconds=int(loadedUpTo)))
            self.setPleaseWait(self.seekLimitNotice['text'])
            self.seekLimitNotice['until'] = time.time() + 3
            self.seekLimitNotice['timer'].start(3000, True)  # singleshot
        except Exception:
            printExc()

    def hideSeekLimitNotice(self):
        self.seekLimitNotice['until'] = 0
        # only the notice itself: "Closing. Please wait..." or "Opening..." that replaced it stays
        if not self.isClosing and self['pleaseWait'].getText() == self.seekLimitNotice.get('text'):
            self['pleaseWait'].hide()

    def doSeek(self, val):
        # the skip keys: with buffering never beyond the part downloaded so far - exteplayer3 stopped at the end of the
        # file still being written and the picture froze. An absolute jump sets the position at once: the player reports
        # it only every second, a second key press before that adds to the first one
        # (a skip key: the position no longer belongs to the last chapter jump; seekToChapter() sets it again)
        self.chapterJump = None
        bufferedEnd = self.bufferedEnd()
        current = self.playback['CurrentTime']
        wanted = None
        if None is not self.downloader and self.downloader.hasDurationInfo() and current >= 0 and self.playback['Length'] > 10:
            target = wanted = min(max(current + val, 0), self.playback['Length'] - 10)
            if bufferedEnd is not None:
                target = min(target, max(bufferedEnd, current))
        elif bufferedEnd is not None and val > 0 and current >= 0:
            # (inside the last seconds of the buffered part a forward key must not jump back)
            target = wanted = current + val
            target = min(target, max(bufferedEnd, current))
        else:
            printDBG("IPTVExtMoviePlayer.doSeek val[%r] current[%r] bufferedEnd[%r] -> relative seek" % (val, current, bufferedEnd))
            self.extPlayerCmddDispatcher.doSeek(val)
            return
        printDBG("IPTVExtMoviePlayer.doSeek val[%r] current[%r] bufferedEnd[%r] length[%r] wanted[%r] target[%r]" % (val, current, bufferedEnd, self.playback['Length'], wanted, target))
        if val > 0 and bufferedEnd is not None and wanted is not None and int(target) < int(wanted):
            self.showSeekLimitNotice(max(bufferedEnd, current))
        if int(target) != int(current):
            self.playback['CurrentTime'] = int(target)
            self.extPlayerCmddDispatcher.doGoToSeek(str(int(target)))

    def key_ok(self):
        self.key_pause()

    def key_loop(self):
        if self.playback['IsLoop']:
            self.extPlayerCmddDispatcher.setLoopMode(0)
        else:
            self.extPlayerCmddDispatcher.setLoopMode(1)

    def key_subtitles(self):
        self.selectSubtitle()

    def key_audio(self):
        self.selectAudioTrack()

    def key_videooption(self):
        self.selectVideoOptions()

    def key_menu(self):
        self.showMenuOptions()

    def key_record(self):
        if self.isDownladManagerAvailable and self.downloader:
            self.key_stop("save_buffer")
            return
        return 0

    def key_zap_next(self):
        self.doZap("zap_next")

    def key_zap_prev(self):
        self.doZap("zap_prev")

    def doZap(self, sts):
        if self.zapEnabled and not self.isClosing:
            self.key_stop(sts)

    # ---------------------------------------------------------------- chapters
    CHAPTER_MAX_MARKS = 60
    # |< in the first seconds of a chapter: to the chapter before, later to the start of this one
    CHAPTER_RESTART_SEC = 3
    # how far before the chapter start a jump may land (the key frame before it, one GOP: 6 s seen)
    CHAPTER_JUMP_SLACK = 10
    DESCRIPTION_MAX_BYTES = 64 * 1024

    def loadChapters(self, filesrcLocation, additionalParams):
        # (chapters, description): the description of the link (e2i_sidecar_txt, YouTube) - with buffering on the
        # downloader's url, the player plays the buffer file - or the sidecar .txt next to a downloaded file
        text = ''
        try:
            downloader = additionalParams.get('downloader', None)
            url = strwithmeta(downloader.getUrl() if downloader is not None else filesrcLocation)
            text = url.meta.get('e2i_sidecar_txt', '') or ''
            path = str(filesrcLocation)
            if path.startswith('file://'):
                path = path[len('file://'):].replace('//', '/')
            if not text and downloader is None and '://' not in path and not path.endswith('/.iptv_buffering.flv'):
                txtPath = os_path.splitext(path)[0] + '.txt'
                # (a .txt can also be MicroDVD subtitles)
                if os_path.isfile(txtPath) and not self._detectSubtitleFile(txtPath)[0]:
                    with open(txtPath, 'rb') as f:
                        text = f.read(self.DESCRIPTION_MAX_BYTES).decode('utf-8', 'ignore')
            text = ensure_str(text).strip()
        except Exception:
            printExc()
            text = ''
        # (the list row's description in front of it breaks its lines with [/br])
        chapters = parseChapters(text.replace('[/br]', '\n'))
        printDBG('IPTVExtMoviePlayer.loadChapters description[%d] chapters[%d]' % (len(text), len(chapters)))
        return chapters, text

    def setChapters(self, chapters, source):
        # chapters known only after the start (ffprobe of a local file): title line, marks and MENU follow
        printDBG('IPTVExtMoviePlayer.setChapters source[%s] chapters[%d]' % (source, len(chapters)))
        self.chapters = chapters
        self.chapterLastIdx = -1
        self.chapterJump = None
        self.updateChapterTitle()
        self.refreshChapterMarks()

    def probeFileChapters(self):
        # a local MKV/MP4 (download, recording) without a chapter list in its description: the file's own chapters
        path = self.getLocalFilePath()
        if self.chapters or not path or path.endswith('/.iptv_buffering.flv') or self.chapterProbe is not None:
            return
        try:
            self.chapterProbe = iptv_system(CHAPTERS_PROBE_CMD % shellQuote(path), self._fileChaptersProbed)
        except Exception:
            printExc()
            self.chapterProbe = None

    def _fileChaptersProbed(self, code, data):
        self.chapterProbe = None
        if self.isClosing or self.chapters:
            return
        chapters = []
        try:
            for item in json.loads(data or '{}').get('chapters', []):
                start = int(round(float(item.get('start_time', 0)) * 1000))
                title = ensure_str((item.get('tags') or {}).get('title', '') or '').strip()
                chapters.append({'start': max(0, start), 'title': title or '%s %d' % (_('Chapter'), len(chapters) + 1)})
        except Exception:
            printExc(WarnOnly=True)
            chapters = []
        chapters.sort(key=lambda c: c['start'])
        if len(chapters) >= 2:
            self.setChapters(chapters, 'file')
        else:
            printDBG('IPTVExtMoviePlayer._fileChaptersProbed code[%r] chapters[%d]' % (code, len(chapters)))

    def playerChaptersReceived(self, items):
        # exteplayer3's own chapter list ("c_l", MKV/MP4 chapters also of streams), at the start: used when the
        # description gave none; [{"id": 0, "s": <start ms>, "e": <end ms>, "t": "<title>"}, ...]
        if self.chapters or self.isClosing or not isinstance(items, list):
            return
        chapters = []
        try:
            for item in items:
                title = ensure_str(item.get('t', '') or '').strip()
                chapters.append({'start': max(0, int(item.get('s', 0))), 'title': title or '%s %d' % (_('Chapter'), len(chapters) + 1)})
        except Exception:
            printExc(WarnOnly=True)
            return
        chapters.sort(key=lambda c: c['start'])
        if len(chapters) >= 2:
            self.setChapters(chapters, 'player')

    def _chapterMark(self, idx):
        # the marks are plain eLabels on the screen (not skin widgets): their number is known only with the chapters
        while len(self.chapterMarks) <= idx:
            mark = eLabel(self.instance)
            mark.setBackgroundColor(parseColor('#00202020'))
            mark.setZPosition(6)
            mark.hide()
            self.chapterMarks.append(mark)
        return self.chapterMarks[idx]

    def refreshChapterMarks(self):
        # a mark at each chapter boundary inside the known length; none for live streams or an unknown length
        if not self.chapters and not self.chapterMarks:
            return
        try:
            length = int(self.playback.get('Length') or 0)
            show = length > 0 and self.playbackInfoBar['visible'] and not self.playback.get('LiveDetected', False) and self.instance is not None
            starts = [c['start'] / 1000.0 for c in self.chapters[1:self.CHAPTER_MAX_MARKS + 1]] if show else []
            starts = [s for s in starts if s < length]
            if starts:
                bar = self['progressBar'].instance
                barPos, barSize = bar.position(), bar.size()
                width = max(2, barSize.height() // 3)
                for idx, startSec in enumerate(starts):
                    mark = self._chapterMark(idx)
                    mark.resize(eSize(width, barSize.height()))
                    mark.move(ePoint(barPos.x() + int(barSize.width() * startSec / length) - width // 2, barPos.y()))
                    mark.show()
            for mark in self.chapterMarks[len(starts):]:
                mark.hide()
        except Exception:
            printExc()

    def updateChapterTitle(self):
        # the infobar's title line: the current chapter in front of the title, changes at the chapter boundary
        if not self.chapters:
            return
        try:
            idx = chapterIndexAt(self.chapters, self.chapterPosMs())
            if idx != self.chapterLastIdx:
                self.chapterLastIdx = idx
                text = '%s  –  %s' % (chapterLabel(self.chapters[idx]), self.title)
                self.infoBarTitleText = text
                if self.INFOBAR_META in self.skinWidgetNames:
                    # a skin like "modern": the title ends with "…" and leaves room for the rating behind it
                    self.updateInfoBarTitle()
                else:
                    self['infoBarTitle'].setText(text)
        except Exception:
            printExc()

    def chapterPosMs(self):
        # the position for the chapter: right after a jump the player still reports the old one for a moment, and the
        # seek lands on the key frame before the chapter start (4:26 for 4:27) - both count as the chapter jumped to
        pos = int(self.playback.get('CurrentTime') or 0)
        if self.chapterJump is not None:
            landed, at = self.chapterJump
            if time.time() - at < 3 or landed - self.CHAPTER_JUMP_SLACK <= pos < landed:
                pos = landed
            else:
                self.chapterJump = None
        return pos * 1000

    def seekToChapter(self, idx):
        target = self.chapters[idx]['start'] // 1000
        current = int(self.playback['CurrentTime'] or 0)
        self.showPlaybackInfoBar()
        if self.downloader is not None:
            # buffering: the skip keys' seek, never beyond the part downloaded so far
            self.doSeek(target - current)
            landed = self.playback['CurrentTime'] if self.playback['CurrentTime'] != current else target
        else:
            # absolute: a relative seek counts from the position of up to a second ago and missed the chapter start
            landed = target
            self.playback['CurrentTime'] = target
            # the key frame before the chapter start (chapterPosMs() counts it to the chapter), not the one after it:
            # "ga" of newer exteplayer3 landed 6 s into the chapter with a long GOP. With "seekms" to the millisecond
            if self.playerBinaryInfo.get('seekms'):
                self.extPlayerCmddDispatcher.doGoToSeek('%.3f' % (self.chapters[idx]['start'] / 1000.0))
            else:
                self.extPlayerCmddDispatcher.doGoToSeek(str(target))
        printDBG('IPTVExtMoviePlayer.seekToChapter idx[%d] current[%d] target[%d] landed[%d] ms[%s]' % (idx, current, target, landed, bool(self.playerBinaryInfo.get('seekms')) and self.downloader is None))
        self.chapterJump = (int(landed), time.time())
        self.updateChapterTitle()

    def _chapterKeyUsable(self):
        return bool(self.chapters) and self.isStarted and not self.isClosing and self.childWindowsCount < 1 \
            and self.playback['Length'] and not self.playback.get('LiveDetected', False)

    def key_nextChapter(self):
        # 0 = not handled: on the last chapter (or without chapters) >| zaps to the next item like before
        if not self._chapterKeyUsable():
            return 0
        idx = chapterIndexAt(self.chapters, self.chapterPosMs()) + 1
        if idx >= len(self.chapters) or self.chapters[idx]['start'] // 1000 >= self.playback['Length']:
            return 0
        self.seekToChapter(idx)

    def key_prevChapter(self):
        # |< at the very start (first seconds of the first chapter) zaps to the previous item like before
        if not self._chapterKeyUsable():
            return 0
        posMs = self.chapterPosMs()
        idx = chapterIndexAt(self.chapters, posMs)
        if posMs - self.chapters[idx]['start'] <= self.CHAPTER_RESTART_SEC * 1000:
            if idx == 0:
                return 0
            idx -= 1
        self.seekToChapter(idx)

    def showChapterList(self):
        current = chapterIndexAt(self.chapters, self.chapterPosMs())
        options = []
        for idx, chapter in enumerate(self.chapters):
            item = IPTVChoiceBoxItem('%s  %s' % (formatTime(chapter['start']), chapter['title']), "", idx)
            item.type = IPTVChoiceBoxItem.TYPE_ON if idx == current else IPTVChoiceBoxItem.TYPE_OFF
            options.append(item)
        self.openChild(boundFunction(self.childClosed, self.showChapterListCallback), IPTVChoiceBoxWidget, {'width': 900, 'height': self._getChoiceBoxHeight(min(len(options), 10)), 'current_idx': current, 'title': _("Chapters"), 'options': options, 'chrome': True, 'footerMargin': 136})

    def showChapterListCallback(self, ret=None):
        if isinstance(ret, IPTVChoiceBoxItem) and not self.isClosing:
            self.seekToChapter(ret.privateData)

    def hasDescription(self):
        # MENU -> "Description": a host to ask for its INFO page, the link's / file's description or the list row's
        return bool(self.descriptionText or self.listDescription or self.infoPanel.provider is not None or self.infoPanel.article is not None)

    def showDescription(self):
        # the INFO page of the list for the running video: the host's own (cover, year, genre ...) - asked once,
        # the INFO panel shares it - else the description of the link or file, else the list row's
        if self.descriptionWaiting:
            return
        self.descriptionWaiting = True
        self.setPleaseWait(_("Loading..."))
        self.infoPanel.getArticle(self._descriptionArticleReady)

    def _descriptionArticleReady(self, article):
        self.descriptionWaiting = False
        if self['pleaseWait'].getText() == _("Loading...") and not self.isClosing:
            self['pleaseWait'].hide()
        if self.isClosing or self.childWindowsCount > 0:
            return
        from Plugins.Extensions.IPTVPlayer.components.iptvarticleview import IPTVArticleView
        title = StripColorCodes(self.title)
        if article is not None and (article.text or article.richDescParams):
            # a copy: the INFO panel keeps the host's page as it came
            text = article.text or (self._plainDescription() if self.descriptionText else '')
            artItem = ArticleContent(title=article.title or title, text=text, images=list(article.images), richDescParams=article.richDescParams)
        elif self.descriptionText or self.listDescription:
            text = self._plainDescription() if self.descriptionText else self.listDescription
            artItem = ArticleContent(title=title, text=text, images=[])
        else:
            self.showMessage(_("No description available."), MessageBox.TYPE_INFO, None)
            return
        if not [image for image in artItem.images if str(image.get('url', '')).startswith(('http', 'data:image/'))]:
            # no picture to load: the cover of the list row, already on the box
            cover = self.infoPanel.coverPath
            artItem.images = [{'title': '', 'url': cover}] if cover and os_path.isfile(cover) else []
        printDBG('IPTVExtMoviePlayer.showDescription from[%s] images[%d]' % ('host' if article is not None and (article.text or article.richDescParams) else 'text', len(artItem.images)))
        self.openChild(boundFunction(self.childClosed, self.showDescriptionCallback), IPTVArticleView, artItem,
                       {'buffering_path': config.plugins.iptvplayer.bufferingPath.value, 'host_name': self.hostName, 'logo_path': self.hostLogoPath,
                        'download_dir': self.articleDownloadDir})

    def _plainDescription(self):
        # the link's / file's description for the INFO page: markdown links as the bare url, "|" is a line break there
        return re.sub(r'\[([^\]]*)\]\((https?://[^)\s]+)\)', r'\2', self.descriptionText).replace('|', '/')

    def showDescriptionCallback(self, *args):
        pass

    # audio screensaver (IPTVAudioScreenSaver): wanted while audio-only playback runs and nothing is open above
    def _screenSaverWanted(self):
        if not self.isStarted or self.isClosing or self.childWindowsCount > 0 or self.underMessage:
            return False
        if self.screenSaverAudioItem:
            return True
        # exteplayer3 reports the video track ("v_c") of every stream that has one; an audio track and no video
        # track is a radio/music stream. gstplayer is left out: it does not always report the video track.
        return 'eplayer' == self.player and bool(self.playback['AudioTrack']) and not self.playback['VideoTrack']

    def _screenSaverTimeText(self):
        # playback time and the audio format of the stream ("0:01:23 / 0:03:45 | MP3"; "AAC (eng)"); the song of a
        # radio stream first ("Artist - Title | 0:01:23 | MP3", the line cuts off what does not fit)
        currTime = self['currTimeLabel'].getText()
        length = self.playback.get('Length') or 0
        text = "%s / %s" % (currTime, self['lengthTimeLabel'].getText()) if length > 0 else currTime
        audio = audioText(self.playback.get('AudioTrack'))
        return " | ".join(x for x in (self.playback.get('NowPlaying', ''), text, audio) if x)

    def goSubKey(self, direction, state='press'):
        if not self.subHandler['enabled'] or None is self.metaHandler.getSubtitleTrack():
            self.hideSubSynchroControl()
            return
        if self.subHandler['synchro']['visible']:
            currentDelay = self.metaHandler.getSubtitleTrackDelay()
            currentDelay += direction * 500  # in MS
            self.metaHandler.setSubtitleTrackDelay(currentDelay)
            self.updateSubSynchroControl()
        else:
            if 'orig_pos' not in self.subConfig:
                self.subConfig['orig_pos'] = self.subConfig['pos']
            self.subConfig['pos'] += (-5 * direction)
            self.setSubOffsetFromInfoBar()
            if -1 != self.subHandler['current_sub_time_ms']:
                self.updateSubtitles(self.subHandler['current_sub_time_ms'], True)

    def updateSubSynchroControl(self):
        if not self.subHandler['synchro']['visible'] or not self.subHandler['enabled'] or None is self.metaHandler.getSubtitleTrack():
            self.hideSubSynchroControl()
            return
        currentDelay = self.metaHandler.getSubtitleTrackDelay()
        if currentDelay > 0:
            textDelay = '+'
        else:
            textDelay = ''
        textDelay += "%.1fs" % (currentDelay / 1000.0)
        self['subSynchroLabel'].setText(textDelay)
        if -1 != self.subHandler['current_sub_time_ms']:
            self.updateSubtitles(self.subHandler['current_sub_time_ms'])

    def goToSeekKey(self, direction, state='press'):
        if 'press' == state:
            self.goToSeekStep = 5
            self.goToSeekRepeatCount = 1
        elif 3 <= self.goToSeekRepeatCount:
            self.goToSeekRepeatCount = 1
            self.goToSeekStep *= 2
        else:
            self.goToSeekRepeatCount += 1

        # not allow faster than (0.1 * playback length)
        # floor division: a py3 float step (e.g. 1535 / 10 = 153.5) made the
        # seek label read "0:20:59.500000" while the key was held
        if self.goToSeekStep > (self.playback['Length'] // 10):
            self.goToSeekStep = self.playback['Length'] // 10
        if 0 >= self.goToSeekStep:
            self.goToSeekStep = 1

        self.doGoToSeekPointerMove(self.goToSeekStep * direction)

    def doExit(self, fromInfo=False):
        if not fromInfo and self.subHandler['synchro']['visible']:
            self.hideSubSynchroControl()
        elif self.playbackInfoBar['visible'] or self.infoPanel.visible:
            self.infoPanel.hide()
            self.playbackInfoBar['blocked'] = False
            self.hidePlaybackInfoBar()
        else:
            self.key_stop("key_exit")

    def doInfo(self):
        # INFO: the page of the source and texts, again: "Playback info", once more: closed
        if self.infoPanel.visible and self.infoPanel.page == 1:
            self.infoPanel.showTech()
        elif self.infoPanel.visible:
            self.doExit(True)
        elif self.isStarted and not self.isClosing:
            self.playbackInfoBar['blocked'] = True
            self.showPlaybackInfoBar()
            self.infoPanel.show()

    def eplayer3Finished(self, code):
        printDBG("IPTVExtMoviePlayer.eplayer3Finished code[%r]" % code)
        if self.isClosing:
            return

        msg = _("It seems that the video player \"%s\" does not work properly.\n\nSTS: %s\nERROR CODE: %r")
        if None is self.playerBinaryInfo['version']:
            msg = msg % (self.playerName, self.playerBinaryInfo['data'], code)
            self.showMessage(msg, MessageBox.TYPE_ERROR, self.onLeavePlayer)
        elif 'gstplayer' == self.player and 246 == code:
            msg = msg % (self.playerName, _("ERROR: pipeline could not be constructed: no element \"playbin2\" \nPlease check if gstreamer plugins are available in your system."), code)
            self.showMessage(msg, MessageBox.TYPE_ERROR, self.onLeavePlayer)
        else:
            self.onLeavePlayer()

    def waitCloseTimeoutCallback(self):
        printDBG("IPTVExtMoviePlayer.waitCloseTimeoutCallback")
        if None is not self.console:
            printDBG("Force close movie player by sending CtrlC")
            self.console.sendCtrlC()
        self.onLeavePlayer()

    def eplayer3DataAvailable2(self, data):
        if None is data or self.isClosing:
            return

        if 'got buffer empty from driver!' in data:
            self.extPlayerCmddDispatcher.stop()

        # work around to catch EOF event after seeking, pause .etc
        if 'wait EOS aborted!!' in data:
            self.waitEOSAbortedFix['EOSaborted_received'] = True
            self.waitEOSAbortedFix['timer'].start(2000, True)  # singleshot

        if self.waitEOSAbortedFix['EOSaborted_received'] and 'poll' in data:
            self.waitEOSAbortedFix['timer'].stop()
            self.waitEOSAbortedFix['timer'].start(2000, True)

    def eplayer3DataAvailable(self, data):

        def _mapTrack(obj, video=False):
            printDBG('>>>> _mapTrack [%s]' % obj)
            params = {}
            params['id'] = int(obj['id'])
            # exteplayer3 names start with "A_" / "V_" / "S_" (A_MP3), gstplayer sends the plain name (audio/mpeg)
            encode = str(obj['e'])
            params['encode'] = encode[2:] if encode[:2] in ('A_', 'V_', 'S_') else encode
            params['name'] = str(obj['n'])
            # what a newer exteplayer3 adds (iptvplayerinfopanel.py names them): the infobar badges and the
            # "Playback info" page; an older player or gstplayer sends none of them
            for extraKey in self.TRACK_INFO_KEYS:
                if extraKey in obj:
                    params[extraKey] = obj[extraKey]
            if not video and 'f' in obj:
                params['forced'] = bool(obj['f'])  # subtitle tracks: "f" is the forced flag
            if video:
                params['frame_rate'] = float(obj['f']) / 1000.0
                params['width'] = int(obj['w'])
                params['height'] = int(obj['h'])
                params['progressive'] = None
                try:
                    if int(obj['p']):
                        params['progressive'] = True
                    else:
                        params['progressive'] = False

                except Exception:
                    printExc(WarnOnly=True)
                params['aspect_ratio'] = 'unknown'
                # gstplayer2 reports a DASH video track first without its size (0x0), the size follows
                if params['width'] and params['height']:
                    try:
                        DAR = float((obj.get('an') or 1) * params['width']) / float((obj.get('ad') or 1) * params['height'])
                        aTab = []
                        for item in [(16, 9, '16_9'), (4, 3, '4_3'), (16, 10, '16_10'), (3, 2, '3_2'), (5, 4, '5_4'), (1.85, 1, '1.85'), (2.35, 1, '2.35'), (1, 1, '1_1'), (3, 4, '3_4'), (9, 16, '9_16')]:
                            diff = fabs(float(item[0]) / item[1] - DAR)
                            aTab.append((diff, item[2]))
                        aTab.sort(key=lambda item: item[0])
                        params['aspect_ratio'] = aTab[0][1]
                    except Exception:
                        printExc()

            return params

        def _mapSubAtom(obj):
            printDBG('>>>> _mapTrack [%s]' % obj)
            params = {}
            params['id'] = int(obj['id'])
            params['start'] = int(obj['s'])
            params['end'] = int(obj['e'])
            params['text'] = str(obj['t'])
            return params

        if None is data or self.isClosing:
            return
        data = ensure_str(data)
        data = data.replace('"ifd"', "'ifd'")
        # data = data.decode('utf-8', 'strict').replace('"ifd"', '(ifd)')
        if None is self.playerBinaryInfo['version']:
            self.playerBinaryInfo['data'] += data
        data = self.responseData + data
        if '\n' != data[-1]:
            truncated = True
        else:
            truncated = False
        data = data.split('\n')
        if truncated:
            self.responseData = data[-1]
            del data[-1]
        msgText = ''
        msgType = MessageBox.TYPE_INFO
        for item in data:
            # printDBG('item= %s' % item)
            item = item.strip().replace('{"PLAYBACK_LENGTH":{"PLAYBACK_LENGTH":', '{"PLAYBACK_LENGTH":').replace('{"PLAYBACK_LENGTH":{"J":', '{"J":')
            if item.endswith(':'):
                item = item[:-1]
            if item.startswith('{'):
                try:
                    obj = LoadPlayerMessage(item)
                    # printDBG("Status object [%r]" % obj)
                    key = list(obj.keys())[0]
                    obj = obj[key]
                except Exception:
                    printExc(item)
                    continue

                if "T" == key:  # ADD_TRIGGERS
                    self.latchSubtitlesTime(obj['c'])
                elif "PLAYBACK_PLAY" == key:
                    self.onStartPlayer()
                    # if 'gstplayer' != self.player:
                    self.updateInfoTimer.start(1000)
                    if 0 == obj['sts']:
                        self.playbackUpdateInfo({'Status': ['Play', '1']})
                        # the stream is open: some live streams (Pluto TV without buffering) never report a
                        # playback time, which is what hid "Opening. Please wait..." until now
                        if not self.isClosing:
                            self['pleaseWait'].hide()
                elif "PLAYBACK_STOP" == key:
                    self.onLeavePlayer()
                elif "PLAYBACK_LENGTH" == key and 0 == obj['sts']:
                    self.playbackUpdateInfo({'Length': int(obj['length'])})
                elif "PLAYBACK_CURRENT_TIME" == key and 0 == obj['sts']:
                    self.playbackUpdateInfo({'CurrentTime': int(obj['sec'])})
                elif "J" == key and obj['ms'] > 0:
                    updateInfoParams = {'CurrentTime': int(obj['ms'] / 1000)}
                    if 'lms' in obj:
                        updateInfoParams['BufferCTime'] = int(obj['lms'] / 1000)
                    self.playbackUpdateInfo(updateInfoParams)
                    self.latchSubtitlesTime(obj['ms'])
                # CURRENT VIDEO TRACK
                elif "v_c" == key:
                    tmpTrack = _mapTrack(obj, True)
                    if tmpTrack.get('id', -1) > -1:
                        self.playbackUpdateInfo({'VideoTrack': tmpTrack})
                        # the picture is decoded from now on
                        self.hideStartCover()
                elif "a_c" == key:
                    tmpTrack = _mapTrack(obj)
                    if tmpTrack.get('id', -1) > -1:
                        self.playbackUpdateInfo({'AudioTrack': tmpTrack})
                elif "a_l" == key:
                    tracks = []
                    for item in obj:
                        tracks.append(_mapTrack(item))
                    self.playbackUpdateInfo({'AudioTracks': tracks})
                elif "s_c" == key:
                    tmpTrack = _mapTrack(obj)
                    if tmpTrack.get('id', -1) > -1:
                        self.playbackUpdateInfo({'SubtitleTrack': tmpTrack})
                        self.enableEmbeddedSubtitles(tmpTrack['id'])
                elif "s_l" == key:
                    tracks = []
                    for item in obj:
                        tracks.append(_mapTrack(item))
                    self.playbackUpdateInfo({'SubtitleTracks': tracks})
                elif "s_a" == key:
                    if self.subHandler['enabled']:
                        if 'r' in obj:
                            self.addGraphicSubAtom(obj)
                        else:
                            subAtom = _mapSubAtom(obj)
                            self.subHandler['embedded_handler'].addSubAtom(subAtom)
                elif "s_f" == key:
                    self.subHandler['embedded_handler'].flushSubtitles()
                    self.flushGraphicSubtitles()
                elif "e_plugin" == key:
                    # the PNG plugin could not be loaded: image subtitles stay empty
                    printDBG("exteplayer3 plugin error %s" % obj)
                elif "m_t" == key:
                    # the song of a radio stream (exteplayer3 v187: ICY StreamTitle or the stream's title / artist tags)
                    self.playbackUpdateInfo({'NowPlaying': nowPlayingText(obj)})
                elif "N" == key:
                    self.playbackUpdateInfo({'IsLoop': obj['isLoop']})
                elif "PLAYBACK_INFO" == key:
                    if obj['isPaused']:
                        self.playbackUpdateInfo({'Status': ['Pause', '0']})
                        # if 'gstplayer' == self.player: self.updateInfoTimer.stop()
                        self.subHandler['timer'].stop()
                    else:
                        # if 'gstplayer' == self.player: self.updateInfoTimer.start(1000)
                        if obj['isForwarding']:
                            self.playbackUpdateInfo({'Status': ['FastForward', str(obj['Speed'])]})
                        elif 0 < obj['SlowMotion']:
                            self.playbackUpdateInfo({'Status': ['SlowMotion', '1/%d' % obj['SlowMotion']]})
                        elif obj['isPlaying']:  # and 1 == obj['Speed']:
                            self.playbackUpdateInfo({'Status': ['Play', '1']})
                        else:
                            printDBG('eplayer3DataAvailable PLAYBACK_INFO not handled')
                elif "GSTPLAYER_EXTENDED" == key:
                    self.playerBinaryInfo['version'] = obj['version']
                elif "EPLAYER3_EXTENDED" == key:
                    self.playerBinaryInfo['version'] = obj['version']
                    # newer exteplayer3: "c_l" chapter list at the start, "seekms" seeks with decimals
                    self.playerBinaryInfo['seekms'] = bool(obj.get('seekms'))
                elif "c_l" == key:
                    self.playerChaptersReceived(obj)
                elif "cover" == key:
                    # exteplayer3 188 --cover: the embedded cover was written
                    self.embeddedCoverReceived(obj)
                elif "s_o" == key:
                    # answer to so1/so0: only forced subtitle cues on/off
                    self.forcedSubtitlesOnly = bool(obj.get('o'))
                elif "a_m" == key:
                    # answer to am<n>: the dual mono channel
                    self.audioChannel = obj.get('m', self.audioChannel)
                elif "DRM_KEY_DROP" == key:
                    # no key for a track of the stream (--key): an audio track is switched over, others dropped
                    printDBG("exteplayer3 DRM_KEY_DROP %s" % obj)
                elif "GST_ERROR" == key:
                    printDBG('GST_ERROR: %s, code %s\n' % (ensure_str(obj['msg']), obj['code']))
                    msgType = MessageBox.TYPE_ERROR
                    msgText += self._playerErrorText(key, obj, 'GST_ERROR: %s (code %s)\n' % (ensure_str(obj['msg']), obj['code']))
                    # 'ifd' from the replace() above for gstplayer builds that do not escape
                    # their JSON, "ifd" from builds that do
                    if ensure_str(obj['msg']) in ("No URI handler implemented for 'ifd'.", 'No URI handler implemented for "ifd".'):
                        msgText += _('Try to change extplayer or reinstall gst-ifdsrc')
                elif "FF_ERROR" == key:
                    printDBG('FF_ERROR: %s, code %s\n' % (ensure_str(obj['msg']), obj['code']))
                    msgType = MessageBox.TYPE_ERROR
                    msgText += self._playerErrorText(key, obj, 'FF_ERROR: %s, code %s\n' % (ensure_str(obj['msg']), obj['code']))
                elif "GST_MISSING_PLUGIN" == key:
                    printDBG('GST_MISSING_PLUGIN: %s\n' % ensure_str(obj['msg']))
                    msgText += self._playerErrorText(key, obj, 'GST_MISSING_PLUGIN: %s\n' % ensure_str(obj['msg']))

                # {u'PLAYBACK_INFO':
                # {u'isSeeking': False,
                # u'BackWard': 0.0,
                # u'isForwarding': False,
                # u'mayWriteToFramebuffer': True,
                # u'AVSync': 1,
                # u'isTeletext': False,
                # u'isAudio': True,
                # u'isCreationPhase': False,
                # u'abortRequested': False,
                # u'isVideo': True,
                # u'isPaused': False,
                # u'SlowMotion': 0,
                # u'isPlaying': True,
                # u'Speed': 1,
                # u'isSubtitle': False,
                # u'isDvbSubtitle': False}}
        if msgText != '':
            if MessageBox.TYPE_ERROR == msgType and self.quietStartErrors and not self.playback.get('ConfirmedCTime', 0):
                printDBG("IPTVExtMoviePlayer error before playback, next link follows - message not shown")
                self.quietStartErrors = False
                self.waitCloseTimeoutCallback()
            else:
                self.showMessage(msgText, msgType, None)

    def onDownloadFinished(self, sts):
        printDBG("IPTVExtMoviePlayer.onDownloadFinished sts[%s]" % sts)
        if None is not self.extPlayerCmddDispatcher:
            if 'gstplayer' == self.player:
                self.extPlayerCmddDispatcher.setDownloadFileTimeout(0)
            else:
                self.extPlayerCmddDispatcher.setProgressiveDownload(0)

    def __onClose(self):
        printDBG(">>>>>>>>>>>>>>>>>>>>>> __onClose")
        self.isClosing = True
        self.playback['Active'] = False
        self.hideStartCover()
        self.startCoverTimer_conn = None
        self.hideAudioCover()
        self.audioCover['timer_conn'] = None
        self.screenSaver.close()
        self._removeEmbeddedCover()
        # normally done by onLeavePlayer(); a screen closed another way must not leave the panel's timers / ffprobe
        # and the backdrop's callback bound (both are safe to call twice)
        try:
            self.infoPanel.close()
            if self.backdropLoader is not None:
                self.backdropLoader.close()
        except Exception:
            printExc()
        self.bannerTimer.stop()
        self.bannerTimer_conn = None
        worker = self.bannerBackdrop.get('worker')
        if worker is not None:
            # its picture would stay in /tmp after the removal below
            worker.join(3)
        try:
            os_remove(BANNER_PICTURE)
        except Exception:
            pass
        if None is not self.workconsole:
            self.workconsole.kill()
        self.workconsole = None
        if None is not self.chapterProbe:
            self.chapterProbe.kill()
        self.chapterProbe = None
        # the marks are children of the screen's instance: freed here, while it still exists
        for mark in self.chapterMarks:
            mark.hide()
        self.chapterMarks = []

        if None is not self.refreshCmdConsole:
            self.refreshCmdConsole.kill()
        self.refreshCmdConsole = None

        if None is not self.extLinkProv['console']:
            self.extLinkProv['close_conn'] = None
            self.extLinkProv['data_conn'] = None
            self.extLinkProv['console'].sendCtrlC()
            self.extLinkProv['console'] = None

        if None is not self.iframeParams['console']:
            self.iframeParams['console'].kill()
        self.iframeParams['console'] = None

        if None is not self.console:
            self.console_appClosed_conn = None
            self.console_stderrAvail_conn = None
            self.console_stdoutAvail_conn = None
            self.console.sendCtrlC()
            self.console = None
        if self.graphicSubs['enabled']:
            self.graphicSubs['handler'].flushSubtitles()
            self.clearGraphicSubtitlesDir()
        if None is not self.downloader:
            self.downloader.unsubscribeFor_Finish(self.onDownloadFinished)
        self.downloader = None

        if self.clockFormat:
            self.playbackInfoBar['clock_timer'].stop()
            self.playbackInfoBar['clock_timer_conn'] = None
        self.playbackInfoBar['timer'].stop()
        self.playbackInfoBar['timer_conn'] = None
        self.waitEOSAbortedFix['timer_conn'] = None
        self.waitCloseFix['timer_conn'] = None

        self.subHandler['timer'].stop()
        self.subHandler['timer_conn'] = None

        self.updateInfoTimer_conn = None
        for key in self.playback.keys():
            self.playback[key] = None
        self.onClose.remove(self.__onClose)
        self.messageQueue = []

        # RESTORE DEFAULT VIDEO OPTION
        printDBG(">>>>>>>>>>>>>>>>>>>>> __onClose[%s]" % self.defVideoOptions)
        printDBG(">>>>>>>>>>>>>>>>>>>>> __onClose[%s]" % self.currVideoOptions)
        videoOptionChange = False
        for opt in ['aspect', 'policy', 'policy2']:
            val = self.defVideoOptions[opt]
            val2 = self.currVideoOptions[opt]
            if val in self.defVideoOptions['%s_choices' % opt] and val != val2:
                videoOptionChange = True
                break

        if videoOptionChange:
            self.applyVideoOptions(self.defVideoOptions)

        # RESTORE DEFAULT AUDIO OPTION
        playerDefOptions = self.getE2AudioOptions()
        audioOptions = ['ac3', 'aac']
        for opt in audioOptions:
            if playerDefOptions[opt] is not None and playerDefOptions[opt] != self.defAudioOptions[opt]:
                SetE2AudioCodecMixOption(opt, self.defAudioOptions[opt])
        self.metaHandler.save()

        # SAVE SUBTITLES POSITION IF CHANGED
        if 'orig_pos' in self.subConfig and self.subConfig['orig_pos'] != self.subConfig['pos']:
            self.configObj.setSubtitleFontSettings(self.subConfig)

        try:
            self.extPlayerCmddDispatcher.owner = None
        except Exception:
            printExc()

    def onStartPlayer(self):
        self.isStarted = True
        self.showPlaybackInfoBar()
        self.screenSaver.start()
        self.scheduleAudioCover()

    def onLeavePlayer(self):
        printDBG("IPTVExtMoviePlayer.onLeavePlayer")
        # also the ends that are not STOP/EXIT (end of the film, player crash, close timeout): save, or reset at the end
        if not self.isClosing:
            try:
                self.saveLastPlaybackTime()
            except Exception:
                printExc()
        self.screenSaver.stop()
        self.hideAudioCover()
        self.seekLimitNotice['timer'].stop()
        if self.waitCloseFix['waiting'] and None is not self.waitCloseFix['timer']:
            self.waitCloseFix['timer'].stop()
        self.updateInfoTimer.stop()
        self.subHandler['timer'].stop()
        self.infoPanel.close()
        if self.backdropLoader is not None:
            self.backdropLoader.close()
        self['backdrop'].hide()
        self.playbackInfoBar['blocked'] = False
        self.hidePlaybackInfoBar()

        self.isClosing = True
        self.showMessage(None, None, boundFunction(self.extmovieplayerClose, self.closeRequestedByUser, self.playback.get('ConfirmedCTime', 0)))

    def extmovieplayerClose(self, sts, currentTime):
        if self.childWindowsCount > 0:
            self.delayedClosure = boundFunction(self.closeWithIframeClear, sts, currentTime)
        else:
            self.closeWithIframeClear(sts, currentTime)

    def closeWithIframeClear(self, sts, currentTime):
        blankIframeFilePath = ''
        if self.iframeParams['show_iframe']:
            blankIframeFilePath = self.iframeParams['iframe_file_end']
        elif self.configObj.clearVideoByIframeInjection():
            blankIframeFilePath = self.configObj.getBlankIframeFilePath()

        if blankIframeFilePath != '' and IsExecutable('showiframe') and fileExists(blankIframeFilePath):
            if not self.iframeParams['iframe_continue']:
                self.iframeParams['console'] = iptv_system('showiframe "{0}"'.format(shellQuote(blankIframeFilePath)), boundFunction(self.iptvDoClose, sts, currentTime))
                return
        self.iptvDoClose(sts, currentTime)

    def iptvDoClose(self, sts, currentTime, code=None, data=None):
        if None is not self.extLinkProv['console']:
            self.extLinkProv['console'].sendCtrlC()

        if None is not self.refreshCmdConsole:
            self.refreshCmdConsole.kill()
        self.refreshCmdConsole = None

        if None is not self.iframeParams['console']:
            self.iframeParams['console'].kill()
        self.iframeParams['console'] = None

        self.close(sts, currentTime, self.clipLength)

    def openChild(self, *args, **kwargs):
        self.childWindowsCount += 1
        self.screenSaver.deactivate()
        self.session.openWithCallback(*args, **kwargs)

    def childClosed(self, callback, *args):
        self.childWindowsCount -= 1
        callback(*args)

        if None is not self.delayedClosure and self.childWindowsCount < 1:
            self.delayedClosure()

    def downloadSub(self, simpleTracksTab=[]):
        if self.downloader is not None:
            url = strwithmeta(self.downloader.getUrl())
        else:
            url = strwithmeta(self.fileSRC)
        # colour codes of the list title would end up in the subtitle search and the subtitle file name
        movieTitle = StripColorCodes(self.title)
        if 0 == len(simpleTracksTab):
            self.openChild(boundFunction(self.childClosed, self.downloadSubCallback), IPTVSubDownloaderWidget, {'duration_sec': self.playback['Length'], 'movie_url': url, 'movie_title': movieTitle})
        else:
            self.openChild(boundFunction(self.childClosed, self.downloadSubCallback), IPTVSubSimpleDownloaderWidget, {'movie_url': url, 'movie_title': movieTitle, 'sub_list': simpleTracksTab})

    def downloadSubCallback(self, ret=None):
        if None is not ret:
            self.subHandler['handler'].removeCacheFile(ret.get('path', ''))
            idx = self.metaHandler.addSubtitleTrack(ret)
            self.metaHandler.setSubtitleIdx(idx)
            self.enableSubtitles()

    def onStart(self):
        self.onShow.remove(self.onStart)
        # self.onLayoutFinish.remove(self.onStart)

        if '' != self.refreshCmd and (self.downloader is not None or not self.fileSRC.startswith('ext://')):
            self.refreshCmdConsole = iptv_system(self.refreshCmd)

        if self.iframeParams['show_iframe'] and IsExecutable('showiframe')\
           and fileExists(self.iframeParams['iframe_file_start']):
            if self.iframeParams['iframe_continue']:
                self.iframeParams['console'] = iptv_system('showiframe "{0}"'.format(shellQuote(self.iframeParams['iframe_file_start'])))
            else:
                self.iframeParams['console'] = iptv_system('showiframe "{0}"'.format(shellQuote(self.iframeParams['iframe_file_start'])), self.iptvGetUrlStart)
                return
        self.iptvGetUrlStart()

    def iptvGetUrlStart(self, code=None, data=None):
        if self.isClosing:
            self.onLeavePlayer()
            return

        if self.downloader is None and self.refreshCmd != '' and self.fileSRC.startswith('ext://'):
            self.extLinkProv['console'] = eConsoleAppContainer()
            self.extLinkProv['close_conn'] = eConnectCallback(self.extLinkProv['console'].appClosed, self._updateGetUrlFinished)
            self.extLinkProv['data_conn'] = eConnectCallback(self.extLinkProv['console'].stderrAvail, self._updateGetUrlDataAvail)
            self.extLinkProv['console'].execute(self.refreshCmd)
        else:
            self.iptvDoStart()

    def _updateGetUrlFinished(self, code=0):
        printDBG('_updateGetUrlFinished update code[%d]--- ' % (code))
        if not self.extLinkProv['started']:
            self.onLeavePlayer()

    def _updateGetUrlDataAvail(self, data):
        if self.isClosing:
            return
        if None is not data and 0 < len(data):
            # the console delivers bytes on Python 3
            self.extLinkProv['data'] += ensure_str(data)
            if self.extLinkProv['data'].endswith('\n'):
                data = self.extLinkProv['data'].split('\n')
                url = ''
                for item in data:
                    if item.startswith('http'):
                        url = item.strip()
                if url.startswith('http'):
                    if not self.extLinkProv['started']:
                        self.fileSRC = strwithmeta(url, self.fileSRC.meta)
                        self.extLinkProv['started'] = True
                        self.iptvDoStart()
                self.extLinkProv['data'] = ''

    def iptvDoStart(self):
        if self.isClosing:
            self.onLeavePlayer()
            return

        self['progressBar'].value = 0
        self['bufferingCBar'].value = 0
        self['bufferingBar'].range = (0, 100000)
        self['bufferingBar'].value = 0
        self.initGuiComponentsPos()
        self.metaHandler.load()
        self.loadLastPlaybackTime()

        defVideoMode = self.defVideoOptions['videomode']
        videoModes = self.defVideoOptions['videomode_choices']

        if defVideoMode is not None and defVideoMode in videoModes:
            curVideoMode = GetE2VideoMode()
            videoMode = self.metaHandler.getVideoOption('videomode')
            if videoMode != curVideoMode and videoMode in videoModes:
                SetE2VideoMode(videoMode)
            self.currVideoOptions['videomode'] = GetE2VideoMode()

        if None is not self.downloader:
            self.downloader.subscribeFor_Finish(self.onDownloadFinished)

        if 'gstplayer' == self.player:
            if self.fileSRC.startswith('merge://'):
                msg = _("Link is not supported by the gstplayer. Please use the extelayer3 if available.")
                self.showMessage(msg, MessageBox.TYPE_ERROR)

            # active audio track
            audioTrackIdx = self.metaHandler.getAudioTrackIdx()

            # file download timeout, 0 keeps gstplayer away from ifd://
            timeout = 0
            if None is not self.downloader and self.downloader.isDownloading():
                if not GetGstIfdSrc()[1]:
                    printDBG("gstplayer: libgstifdsrc.so missing or not loadable, playing the buffer file without IFD")
                else:
                    timeout = self.gstAdditionalParams['file-download-timeout']
            isLive = 1 if self.gstAdditionalParams['file-download-live'] else 0

            # http headers + proxy, gstplayer takes both as "key=value" fields
            httpFields = []
            if "://" in self.fileSRC:
                tmp = strwithmeta(self.fileSRC)
                url, httpParams = DMHelper.getDownloaderParamFromUrlWithMeta(tmp, True)
                for key in httpParams:
                    if key == 'http_proxy':
                        # the proxy fields below, not an "http_proxy:" request header
                        continue
                    httpFields.append((key, httpParams[key]))
                if 'http_proxy' in tmp.meta:
                    tmp = tmp.meta['http_proxy']
                    if '://' in tmp:
                        if '@' in tmp:
                            tmp = re.search('([^:]+?://)([^:]+?):([^@]+?)@(.+?)$', tmp)
                            if tmp:
                                httpFields.extend([('proxy', tmp.group(1) + tmp.group(4)), ('proxy-id', tmp.group(2)), ('proxy-pw', tmp.group(3))])
                        else:
                            httpFields.append(('proxy', tmp))

            gstplayerPath = GetGstPlayerPath()
            # a DASH link: the MPD with only the chosen video / audio representation
            playSrc = dashmpd.localManifestUrl(self.fileSRC) or self.fileSRC
            # 'export GST_DEBUG="*:6" &&' +
            cmd = gstplayerPath + ' "%s"' % shellQuote(playSrc)
            if gstplayerPath.endswith('gstplayer2'):
                # getopt command line; buffer options are only passed when set,
                # gstplayer2 treats 0 as "turned off" and takes the ring buffer in KB
                if audioTrackIdx >= 0:
                    cmd += ' -i %d' % audioTrackIdx
                if timeout > 0:
                    cmd += ' -t %d -l %d' % (timeout, isLive)
                if "://" in self.fileSRC:
                    bufferPath = self.gstAdditionalParams['download-buffer-path']
                    ringBufferMB = int(self.gstAdditionalParams['ring-buffer-max-size'])
                    bufferDuration = int(self.gstAdditionalParams['buffer-duration'])
                    bufferSize = int(self.gstAdditionalParams['buffer-size'])
                    if bufferPath:
                        cmd += ' -p "%s"' % shellQuote(bufferPath)
                    if ringBufferMB > 0:
                        cmd += ' -r %d' % (ringBufferMB * 1024)
                    if bufferDuration > 0:
                        cmd += ' -d %d' % bufferDuration
                    if bufferSize > 0:
                        cmd += ' -s %d' % bufferSize
                    for key, value in httpFields:
                        cmd += ' -H "%s=%s"' % (key, shellQuote(value))
            else:
                # positional command line of the original gstplayer
                cmd += ' %d ' % audioTrackIdx
                cmd += ' {0} '.format(timeout)
                cmd += ' {0} '.format(isLive)
                if "://" in self.fileSRC:
                    cmd += ' "%s" "%s"  "%s"  "%s" ' % (shellQuote(self.gstAdditionalParams['download-buffer-path']), shellQuote(self.gstAdditionalParams['ring-buffer-max-size']), shellQuote(self.gstAdditionalParams['buffer-duration']), shellQuote(self.gstAdditionalParams['buffer-size']))
                    for key, value in httpFields:
                        cmd += (' "%s=%s" ' % (key, shellQuote(value)))
            cmd += " > /dev/null"
        else:
            exteplayer3path = EXTEPLAYER3_PATH
            cmd = exteplayer3path
            if GraphicSubtitlesSupported(exteplayer3path) and mkdirs(self.graphicSubs['dir']):
                # image subtitles as PNG files, the rectangles scaled to the screen
                self.graphicSubs['enabled'] = True
                self.clearGraphicSubtitlesDir()
                desktopSize = getDesktop(0).size()
                cmd += ' -G "%s" -W %d -H %d' % (shellQuote(self.graphicSubs['dir']), desktopSize.width(), desktopSize.height())
            tmpUri = strwithmeta(self.fileSRC)

            audioUri = ''
            videoUri = self.fileSRC
            if self.fileSRC.startswith('merge://') and 'audio_url' in tmpUri.meta and 'video_url' in tmpUri.meta:
                audioUri = tmpUri.meta['audio_url']
                videoUri = tmpUri.meta['video_url']
                sts, audioUri = CreateTmpFile('.iptv_audio_uri', audioUri)
                sts, videoUri = CreateTmpFile('.iptv_video_uri', videoUri)
                audioUri = 'iptv://' + audioUri
                videoUri = 'iptv://' + videoUri
                if not sts:
                    msg = _("An error occurred while writing into: %s") % GetTmpDir()
                    self.showMessage(msg, MessageBox.TYPE_ERROR)
            elif tmpUri.meta.get('iptv_dash_sel'):
                # the MPD with only the chosen video / audio representation (dashdec opens all of them otherwise)
                videoUri = dashmpd.localManifestUrl(tmpUri) or videoUri
            if "://" in self.fileSRC:
                ramBufferSizeMB = config.plugins.iptvplayer.rambuffer_sizemb_network_proto.value
                url, httpParams = DMHelper.getDownloaderParamFromUrlWithMeta(tmpUri, True)
                # cmd += ' ""' # cookies for now will be send in headers
                headers = ''
                for key in httpParams:
                    if key == 'Range':  # Range is always used by ffmpeg
                        continue
                    elif key == 'User-Agent':
                        cmd += ' -u "%s"' % shellQuote(httpParams[key])
                    elif key == 'http_proxy':
                        # ffmpeg's http option (also for the HLS / DASH segments), it used to go
                        # out as an "http_proxy:" request header and no proxy was used
                        cmd += ' -f "http_proxy=%s"' % shellQuote(httpParams[key])
                    else:
                        headers += ('%s: %s\r\n' % (key, httpParams[key]))
                if len(headers):
                    cmd += ' -h "%s"' % shellQuote(headers)
                if url.startswith('http'):
                    url = urlparser.decorateParamsFromUrl(url)
                    if '1' == url.meta.get('MPEGTS-Live', '0'):
                        cmd += ' -v '
                programId = url.meta.get('PROGRAM-ID', '')
                if programId != '':
                    cmd += ' -P "%s" ' % shellQuote(programId)
            else:
                ramBufferSizeMB = config.plugins.iptvplayer.rambuffer_sizemb_files.value

            if ramBufferSizeMB > 0:
                cmd += ' -b %s ' % ramBufferSizeMB

            if config.plugins.iptvplayer.stereo_software_decode.value:
                cmd += ' -s '

            if config.plugins.iptvplayer.dts_software_decode.value:
                cmd += ' -d '

            if config.plugins.iptvplayer.wma_software_decode.value:
                cmd += ' -w '
            if config.plugins.iptvplayer.mp3_software_decode.value:
                cmd += ' -m '
            if config.plugins.iptvplayer.eac3_software_decode.value:
                cmd += ' -e '
            if config.plugins.iptvplayer.ac3_software_decode.value:
                cmd += ' -3 '
            if 'lpcm' == config.plugins.iptvplayer.software_decode_as.value:
                cmd += ' -l '

            if config.plugins.iptvplayer.aac_software_decode.value:
                cmd += ' -a 3 -p 10'
            else:
                cmd += ' -p 2'
                if None is not self.downloader:
                    cmd += ' -o 1 '

            audioTrackIdx = self.metaHandler.getAudioTrackIdx()
            printDBG(">>>>>>>>>>>>>>>>>>>>>>>> audioTrackIdx[%d]" % audioTrackIdx)
            if audioTrackIdx >= 0:
                cmd += ' -t %d ' % audioTrackIdx

            subtitleTrackIdx = self.metaHandler.getEmbeddedSubtileTrackIdx()
            printDBG(">>>>>>>>>>>>>>>>>>>>>>>> subtitleTrackIdx[%d]" % subtitleTrackIdx)
            if subtitleTrackIdx >= 0:
                cmd += ' -9 %d ' % subtitleTrackIdx

            cmd += self._extePlayer3NewOptions(tmpUri)

            if audioUri != '':
                cmd += ' -x "%s" ' % shellQuote(audioUri)

            if 'iptv_m3u8_live_start_index' in tmpUri.meta:
                cmd += ' -f "live_start_index=%s" ' % shellQuote(tmpUri.meta['iptv_m3u8_live_start_index'])

            if 'iptv_m3u8_key_uri_replace_old' in tmpUri.meta and 'iptv_m3u8_key_uri_replace_new' in tmpUri.meta:
                cmd += ' -f "key_uri_old=%s" -f "key_uri_new=%s" ' % (shellQuote(tmpUri.meta['iptv_m3u8_key_uri_replace_old']), shellQuote(tmpUri.meta['iptv_m3u8_key_uri_replace_new']))

            if self.extAdditionalParams.get('moov_atom_file', '') != '':
                cmd += ' -F "%s" -S %s -O %s' % (shellQuote(self.extAdditionalParams['moov_atom_file']), self.extAdditionalParams['moov_atom_offset'] + self.extAdditionalParams['moov_atom_size'], self.extAdditionalParams['moov_atom_offset'])

            cmd += (' "%s"' % shellQuote(videoUri)) + " > /dev/null"

        self.console = eConsoleAppContainer()
        self.console_appClosed_conn = eConnectCallback(self.console.appClosed, self.eplayer3Finished)
        self.console_stderrAvail_conn = eConnectCallback(self.console.stderrAvail, self.eplayer3DataAvailable)
        # if 'gstplayer' == self.player:
        #    self.console_stdoutAvail_conn = eConnectCallback(self.console.stdoutAvail, self.eplayer3DataAvailable2 ) # work around to catch EOF event after seeking, pause .etc
        printDBG("->||||||| onStart cmd[%s]" % cmd)
        if hasattr(self.console, "setNice"):
            self.console.setNice(GetNice() + 1)
            self.console.execute(cmd)
        else:
            self.console.execute(E2PrioFix(cmd, 1))
        self['statusIcon'].setPixmap(self.playback['statusIcons']['Play'])  # sulge for test
        self['loopIcon'].setPixmap(self.playback['loopIcons']['Off'])
        self['logoIcon'].setPixmap(self.playback['logoIcon'])
        self['subSynchroIcon'].setPixmap(self.subHandler['synchro']['icon'])
        # at least the stream type until the player reports the video track ("v_c" overwrites it) -
        # gstplayer2 reports none for a buffer file ffmpeg is still writing (merged audio/video)
        streamType = self._getStreamTypeLabel()
        if streamType and not self.playback['VideoTrack']:
            self['videoInfo'].setText(streamType)

        # SET Video option
        videoOptions = ['aspect', 'policy', 'policy2']
        playerDefOptions = self.configObj.getDefaultPlayerVideoOptions()
        for opt in videoOptions:
            val = self.metaHandler.getVideoOption(opt)
            if val is not None:
                self.currVideoOptions[opt] = val
            elif playerDefOptions[opt] is not None:
                self.currVideoOptions[opt] = playerDefOptions[opt]

        videoOptionChange = False
        self.defVideoOptions.update(self.getE2VideoOptions())
        for opt in videoOptions:
            val = self.currVideoOptions[opt]
            if val in self.defVideoOptions['%s_choices' % opt] and val != self.defVideoOptions[opt]:
                videoOptionChange = True
                self.currVideoOptions[opt] = val
            else:
                self.currVideoOptions[opt] = self.defVideoOptions[opt]

        if videoOptionChange:
            self.applyVideoOptions(self.currVideoOptions)

        # SET Audio option
        self.defAudioOptions = self.getE2AudioOptions()
        playerDefOptions = self.configObj.getDefaultAudioOptions()
        audioOptions = ['ac3', 'aac']
        for opt in audioOptions:
            if playerDefOptions[opt] is not None and playerDefOptions[opt] != self.defAudioOptions[opt]:
                SetE2AudioCodecMixOption(opt, playerDefOptions[opt])

        self.enableSubtitles()
        self.probeFileChapters()

    def fixWindowGeometry(self):
        # initGuiComponentsPos() places the infobar in real desktop pixels,
        # so the window itself must cover exactly the desktop at 0,0.
        #
        # resolution="1280,720" is not honoured the same way everywhere:
        # OpenATV scales every position=/size= (the window's own included),
        # OpenHDF 7.5 (OpenPLi-style SkinContext, which turns position=/
        # size= into final pixel tuples before the scale is applied) scales
        # the fonts only. There the window stayed 1280x720 in the middle
        # of a FHD desktop and clipped the infobar away, and the widgets
        # kept their 1280x720 boxes with 1.5x fonts in them. A window that
        # still has the reference size on a bigger desktop tells the two
        # apart - the widgets are then scaled here instead.
        try:
            desktopW = getDesktop(0).size().width()
            desktopH = getDesktop(0).size().height()
            windowW = self.instance.size().width()
            windowH = self.instance.size().height()
            printDBG("IPTVExtMoviePlayer window %dx%d at %d,%d -> desktop %dx%d" % (windowW, windowH, self.instance.position().x(), self.instance.position().y(), desktopW, desktopH))
            self.instance.move(ePoint(0, 0))
            self.instance.resize(eSize(desktopW, desktopH))
            if not self.skinUsesRefCanvas or (windowW, windowH) != (self.REF_W, self.REF_H) or (desktopW, desktopH) == (self.REF_W, self.REF_H):
                return
            scaleX = desktopW / float(self.REF_W)
            scaleY = desktopH / float(self.REF_H)
            printDBG("IPTVExtMoviePlayer skin engine did not scale the widgets - scaling them by %.2fx%.2f" % (scaleX, scaleY))
            done = set()
            for widget in list(self.values()) + list(getattr(self, 'renderer', [])) + list(getattr(self, 'additionalWidgets', [])):
                instance = getattr(widget, 'instance', None)
                if instance is None or id(widget) in done:
                    continue
                done.add(id(widget))
                try:
                    pos = instance.position()
                    size = instance.size()
                    instance.resize(eSize(int(size.width() * scaleX), int(size.height() * scaleY)))
                    instance.move(ePoint(int(pos.x() * scaleX), int(pos.y() * scaleY)))
                except Exception:
                    printExc()
        except Exception:
            printExc()

    def showStartCover(self):
        cover = self['startCover']
        if cover.instance is None:
            return
        cover.hide()
        if not self.startCoverPath or not os_path.isfile(self.startCoverPath):
            return
        try:
            if -1 != cover.decodePreparedCover(self.startCoverPath, self.startCoverDecoded, 'startCover'):
                self.startCoverTimer.start(self.START_COVER_TIMEOUT * 1000, True)
        except Exception:
            printExc()

    def startCoverDecoded(self, ret):
        # decoded after the stream already started: not shown any more
        if ret.get('Pixmap') is not None and self.startCoverPath and not self.isClosing:
            self['startCover'].updatePixmap(ret['Pixmap'], ret.get('FileName', self.startCoverPath))
            self['startCover'].show()

    def hideStartCover(self):
        # playback runs (first frame / position / video track), the player closes or the time is up
        if self.startCoverPath:
            self.startCoverPath = ''
            self.startCoverTimer.stop()
            if self['startCover'].instance is not None:
                self['startCover'].hide()

    # audio playback: the title's picture (else the host logo) stays on the screen, small in the middle or on the
    # whole screen (setting "Poster during audio playback"). Over a still image of "Show iframe during audio playback"
    # (radio.mvi) it lies on top; the screensaver still starts after its own time.
    def _audioCoverMode(self):
        try:
            mode = config.plugins.iptvplayer.audio_cover.value
        except Exception:
            # setting not registered: an update without an enigma2 restart (issue #689)
            mode = 'small'
        if mode in self.AUDIO_COVER_BOXES and self.backdropReady():
            # the backdrop fills the screen, the poster lies small in front of it
            return 'small'
        return mode if mode in self.AUDIO_COVER_BOXES else ''

    def _audioOnly(self):
        # what the screensaver counts as audio playback (_screenSaverWanted), without its conditions of the moment
        if self.playback['VideoTrack']:
            return False
        return self.screenSaverAudioItem or ('eplayer' == self.player and bool(self.playback['AudioTrack']))

    def scheduleAudioCover(self):
        # an audio row of the list right away, any other stream once it played a moment without a video track
        if self.isClosing or self.audioCover['shown'] or self.audioCover.get('nothing') or self.playback['VideoTrack'] or not self._audioCoverMode():
            return
        if self.screenSaverAudioItem:
            self.showAudioCover()
        elif not self.audioCover['timer'].isActive():
            self.audioCover['timer'].start(self.AUDIO_COVER_DELAY, True)

    def _audioCoverBox(self, mode):
        # AUDIO_COVER_BOXES[mode] in real pixels
        desktop = getDesktop(0).size()
        x, y, w, h = self.AUDIO_COVER_BOXES[mode]
        scaleX, scaleY = desktop.width() / float(self.REF_W), desktop.height() / float(self.REF_H)
        return (int(x * scaleX), int(y * scaleY), int(w * scaleX), int(h * scaleY))

    def showAudioCover(self):
        mode = self._audioCoverMode()
        cover = self['audioCover']
        if self.isClosing or self.audioCover['shown'] or not mode or cover.instance is None or not self._audioOnly():
            return
        path = ''
        for candidate in self.audioCover['paths']:
            if candidate and os_path.isfile(candidate):
                path = candidate
                break
        if not path:
            # no picture and no logo: not looked for again every second (scheduleAudioCover)
            self.audioCover['nothing'] = True
            return
        box = self._audioCoverBox(mode)
        self.audioCover['box'] = box
        self.audioCover['shown'] = True
        try:
            self._decodeAudioCover(cover, path, box)
        except Exception:
            printExc()
            self.audioCover['shown'] = False

    def _decodeAudioCover(self, cover, path, box):
        # the picture is fitted to the widget's size: the whole box first. A pixmap decoded for another box (full
        # screen, then small in front of the backdrop) is decoded again - Cover skips a file it decoded before.
        cover.instance.move(ePoint(box[0], box[1]))
        cover.instance.resize(eSize(box[2], box[3]))
        if self.audioCover.get('pixmapBox') != box:
            cover.currIcon = {}
            self.audioCover['pixmap'] = None
        self.audioCover['decodeBox'] = box
        self.audioCover['path'] = path
        ret = cover.decodePreparedCover(path, self.audioCoverDecoded, 'audioCover')
        if -1 == ret:
            self.audioCover['shown'] = False
        elif ret is False and self.audioCover.get('pixmap') is not None:
            # decoded before for this box (shown again after a video track that went away)
            self._centerPixmap(cover, self.audioCover['pixmap'], box)
            cover.show()
            self._updateAudioCoverText()
            self.updateBackdrop()

    def audioCoverDecoded(self, ret):
        if ret.get('Pixmap') is None or self.isClosing or not self.audioCover['shown']:
            return
        cover = self['audioCover']
        if self.audioCover.get('decodeBox') != self.audioCover['box']:
            # the box changed while this decoding ran: decode again for the new one
            try:
                self._decodeAudioCover(cover, self.audioCover['path'], self.audioCover['box'])
            except Exception:
                printExc()
            return
        self.audioCover['pixmap'] = ret['Pixmap']
        self.audioCover['pixmapBox'] = self.audioCover['box']
        cover.updatePixmap(ret['Pixmap'], ret.get('FileName', ''))
        self._centerPixmap(cover, ret['Pixmap'], self.audioCover['box'])
        cover.show()
        self._updateAudioCoverText()
        self.updateBackdrop()

    def hideAudioCover(self):
        self.audioCover['timer'].stop()
        if self.audioCover['shown']:
            self.audioCover['shown'] = False
            if self['audioCover'].instance is not None:
                self['audioCover'].hide()
        self._updateAudioCoverText()
        self.updateBackdrop()

    def _updateAudioCoverText(self):
        # the song of a radio stream above the poster: only together with the poster
        label = self['audioCoverText']
        if label.instance is None:
            return
        text = self.playback.get('NowPlaying', '') if self.audioCover['shown'] else ''
        label.setText(text)
        if text:
            label.show()
        else:
            label.hide()

    def setBackdropUrl(self, url):
        # the host's INFO page came in (PlayerInfoPanel): its backdrop is downloaded and prepared in a worker thread
        if not url or self.isClosing or self['backdrop'].instance is None:
            return
        if self.backdropLoader is None:
            self.backdropLoader = BackdropLoader(self['backdrop'], self._backdropLoaded)
        self.backdropLoader.load(url)

    def backdropReady(self):
        return self.backdropLoader is not None and self.backdropLoader.ready

    def backdropFile(self):
        # the prepared picture of the screen's size, for the background of the INFO panels
        return self.backdropLoader.path if self.backdropReady() else ''

    def _backdropLoaded(self, ok):
        printDBG("IPTVExtMoviePlayer backdrop ready[%r]" % ok)
        if ok:
            self.infoPanel.backgroundChanged()
        if ok and self.audioCover['shown'] and self.audioCover['box'] != self._audioCoverBox('small'):
            # a poster on the whole screen moves into the middle of the backdrop
            self.hideAudioCover()
            self.showAudioCover()
        self.updateBackdrop()

    def updateBackdrop(self):
        # shown behind the INFO panels, during audio playback (behind the poster) and - setting - over a paused film
        if self['backdrop'].instance is None:
            return
        wanted = self.backdropReady() and not self.isClosing and (
            self.infoPanel.visible or self.audioCover['shown']
            or (self.playback.get('Status') == 'Pause' and backdropOnPause()))
        if wanted:
            self['backdrop'].show()
        else:
            self['backdrop'].hide()
        self.updateBannerBackdrop(wanted)

    def _bannerFile(self):
        # the infobar's picture drawn for the OSD's width when the skin has one, else the 1280 one
        path = self.playerSkinFolder + "/" + self.playbackBannerFile
        native = '%s_%d.png' % (path[:-4], getDesktop(0).size().width())
        return native if os_path.isfile(native) else path

    def updateBannerBackdrop(self, shown):
        # over the backdrop the infobar is laid over the piece of the backdrop under it (makeBannerPicture, in a
        # worker thread), else it shows the skin's picture again
        widget = self['playbackInfoBaner']
        if widget.instance is None or Image is None:
            return
        state = self.bannerBackdrop
        key = None
        if shown:
            x, y, w, h = self._rect(widget)
            if w > 0 and h > 0:
                key = (self.backdropFile(), x, y, w, h)
        state['wanted'] = key
        if key == state['shown']:
            return
        if key is None or key in state['failed']:
            # the skin's picture (also when the picture over this backdrop could not be made: not tried again)
            self._setBannerPixmap(None)
        elif key == state['made'] and os_path.isfile(BANNER_PICTURE):
            self._setBannerPixmap(key)
        elif state['worker'] is None:
            def make(key=key, banner=self._bannerFile()):
                try:
                    makeBannerPicture(BANNER_PICTURE, banner, key[3], key[4], key[0], (key[1], key[2]))
                    state['result'] = (key, True)
                except Exception:
                    printExc()
                    state['result'] = (key, False)
            state['result'] = None
            state['worker'] = threading.Thread(target=make, name='E2iInfobarBackdrop')
            state['worker'].start()
            self.bannerTimer.start(100, False)

    def _bannerWorkerDone(self):
        state = self.bannerBackdrop
        if state['result'] is None:
            return
        self.bannerTimer.stop()
        key, ok = state['result']
        state['worker'] = state['result'] = None
        if self.isClosing:
            return
        if ok:
            state['made'] = key
        else:
            state['failed'].add(key)
        # the picture wanted meanwhile (backdrop hidden, another backdrop): shown or made next
        self.updateBannerBackdrop(state['wanted'] is not None)

    def _setBannerPixmap(self, key):
        widget = self['playbackInfoBaner']
        state = self.bannerBackdrop
        try:
            if key:
                pixmap = LoadPixmap(BANNER_PICTURE, cached=False)
            else:
                if state['default'] is None:
                    # the skin's picture as loaded at the start (a prescaled one when there was none to scale)
                    state['default'] = LoadPixmap(self.playerSkinFolder + "/" + self.playbackBannerFile)
                pixmap = state['default']
            if pixmap is None:
                return
            widget.instance.setPixmap(pixmap)
            state['shown'] = key
        except Exception:
            printExc()

    def updateNowPlaying(self):
        # exteplayer3 v187 reports a new song ("m_t"): above the audio poster, in the infobar's meta line of a skin
        # like "modern", on the "Playback info" page
        printDBG("IPTVExtMoviePlayer.updateNowPlaying [%s]" % self.playback.get('NowPlaying', ''))
        self._updateAudioCoverText()
        self.updateInfoBarMeta()
        self.infoPanel.updateStream()

    def initPleaseWaitBox(self):
        # the notice has a half-transparent backdrop (plain grey text straight on the video
        # looked pixelated): remember the skin's box once, setPleaseWait() shrinks it to the text
        try:
            instance = self['pleaseWait'].instance
            pos = instance.position()
            size = instance.size()
            desktopW = getDesktop(0).size().width()
            centered = abs(pos.x() + size.width() / 2.0 - desktopW / 2.0) < 3
            self.pleaseWaitBox = (pos.x(), pos.y(), size.width(), size.height(), centered)
            self.fitPleaseWaitBox()
        except Exception:
            printExc()

    def fitPleaseWaitBox(self):
        box = getattr(self, 'pleaseWaitBox', None)
        if box is None:
            return
        try:
            x, y, w, h, centered = box
            instance = self['pleaseWait'].instance
            # calculateSize() measures the box first, so it starts from the full skin width
            instance.resize(eSize(w, h))
            pad = max(8, h // 2)
            newW = min(w, instance.calculateSize().width() + 2 * pad)
            if centered:
                x += (w - newW) // 2
            instance.resize(eSize(newW, h))
            instance.move(ePoint(x, y))
        except Exception:
            printExc()

    def setPleaseWait(self, text):
        self['pleaseWait'].setText(text)
        self.fitPleaseWaitBox()
        self['pleaseWait'].show()

    def initGuiComponentsPos(self):
        # widget sizes are final here (the instances don't exist in __init__)
        try:
            self._prescaleSkinPixmaps()
        except Exception:
            printExc()

        # info bar gui elements
        # calculate offset
        offset_x = (getDesktop(0).size().width() - self['playbackInfoBaner'].instance.size().width()) / 2
        offset_y = (getDesktop(0).size().height() - self['playbackInfoBaner'].instance.size().height()) - self.Y_CROPPING_GUARD
        if offset_x < 0:
            offset_x = 0
        if offset_y < 0:
            offset_y = 0

        self.infoBanerOffsetY = offset_y + self['playbackInfoBaner'].position[1]
        tmp = offset_y + self['logoIcon'].position[1]
        if tmp < self.infoBanerOffsetY:
            self.infoBanerOffsetY = tmp

        for elem in self.playbackInfoBar['guiElemNames']:
            self[elem].setPosition(self[elem].position[0] + offset_x, self[elem].position[1] + offset_y)
        try:
            for elem in ('playbackInfoBaner', 'progressBar', 'currTimeLabel'):
                printDBG("IPTVExtMoviePlayer %s at %d,%d size %dx%d" % (elem, self[elem].instance.position().x(), self[elem].instance.position().y(), self[elem].instance.size().width(), self[elem].instance.size().height()))
        except Exception:
            printExc()

        # sub synchro elements
        # calculate offset
        offset_x = (getDesktop(0).size().width() - self['subSynchroIcon'].instance.size().width()) / 2
        offset_y = (getDesktop(0).size().height() - self['subSynchroIcon'].instance.size().height()) / 2
        if offset_x < 0:
            offset_x = 0
        if offset_y < 0:
            offset_y = 0

        for elem in self.subHandler['synchro']['guiElemNames']:
            self[elem].setPosition(self[elem].position[0] + offset_x, self[elem].position[1] + offset_y)

        # the optional widgets have their final place now
        try:
            self.initInfoBarExtras()
        except Exception:
            printExc()

    # optional infobar widgets of a player skin (INFOBAR_OPTIONAL) - everything in real pixels here,
    # instance.move()/resize() are not scaled by the skin engine
    @staticmethod
    def _rect(widget):
        instance = widget.instance
        return instance.position().x(), instance.position().y(), instance.size().width(), instance.size().height()

    def _setOptionalVisible(self, name, visible):
        # an optional infobar widget with something to show is shown with the infobar, an empty one stays hidden
        if visible:
            self.infoBarHiddenElems.discard(name)
            if self.playbackInfoBar['visible']:
                self[name].show()
        else:
            self.infoBarHiddenElems.add(name)
            self[name].hide()

    def _skinPixmap(self, name, fileName):
        path = os_path.join(self.playerSkinFolder, fileName)
        if not os_path.isfile(path):
            return None
        return self._prescaledPixmap(name, path) or LoadPixmap(path)

    def _declared(self, name):
        # an optional widget the player skin names: enigma2 8.1 gives a widget the skin does not declare an instance too
        # (size -1), the classic skins then counted as skins with badges, info row, poster and knob
        return name in self.skinWidgetNames and self[name].instance is not None

    def initInfoBarExtras(self):
        # the backdrop only shows once it is there and wanted (updateBackdrop)
        self['backdrop'].hide()
        if self.backdropStartUrl and backdropMode() != 'off':
            self.setBackdropUrl(self.backdropStartUrl)
        poster = self[self.INFOBAR_POSTER]
        if self._declared(self.INFOBAR_POSTER):
            self.infoBarPosterBox = self._rect(poster)
            for path in self.infoBarPosterPaths:
                if path and os_path.isfile(path):
                    if -1 != poster.decodePreparedCover(path, self.infoBarPosterDecoded, 'infoBarPoster'):
                        break
        for name, fileName in ((self.INFOBAR_POSTER_MASK, 'infobar_poster_mask.png'), (self.INFOBAR_KNOB, 'playback_knob.png')):
            if self._declared(name):
                pixmap = self._skinPixmap(name, fileName)
                if pixmap is not None:
                    self[name].setPixmap(pixmap)
                    self.infoBarMaskLoaded = self.infoBarMaskLoaded or name == self.INFOBAR_POSTER_MASK
        badges = [name for name in self.INFOBAR_BADGES if self._declared(name)]
        if badges:
            first = self._rect(self[badges[0]])
            frameName = badges[0] + 'Frame'
            frame = self._rect(self[frameName]) if self._declared(frameName) else None
            border = max(0, first[0] - frame[0]) if frame else 0
            outer = frame or first
            lastName = badges[-1]
            last = self._rect(self[lastName + 'Frame']) if self._declared(lastName + 'Frame') else self._rect(self[lastName])
            nextOuter = None
            if len(badges) > 1:
                nextName = badges[1]
                nextOuter = self._rect(self[nextName + 'Frame']) if self._declared(nextName + 'Frame') else self._rect(self[nextName])
            gap = nextOuter[0] - outer[0] - outer[2] if nextOuter else 0
            sub = self._rect(self[badges[0] + 'Sub']) if self._declared(badges[0] + 'Sub') else None
            self.infoBarBadgeLayout = {'x': outer[0], 'y': outer[1], 'h': first[3], 'border': border, 'gap': max(gap, 4),
                                       'maxX': last[0] + last[2], 'pad': max(3, first[3] // 5),
                                       'subY': sub[1] if sub else 0, 'subH': sub[3] if sub else 0}
        strip = []
        for idx in range(1, 6):
            key, value = self['infoBarStrip%dKey' % idx], self['infoBarStrip%dValue' % idx]
            if self._declared('infoBarStrip%dKey' % idx) and self._declared('infoBarStrip%dValue' % idx):
                keyRect, valueRect = self._rect(key), self._rect(value)
                strip.append((idx, keyRect, valueRect[0] + valueRect[2], max(4, keyRect[3] // 5)))
            icon = 'infoBarStrip%dIcon' % idx
            if self._declared(icon):
                pixmap = self._skinPixmap(icon, 'infobar_strip%d.png' % idx)
                if pixmap is not None:
                    self[icon].setPixmap(pixmap)
                    self.infoBarStripIcons.add(icon)
        self.infoBarStripLayout = strip
        if self['infoBarTitle'].instance is not None:
            self.infoBarTitleRect = self._rect(self['infoBarTitle'])
        if self.INFOBAR_RATING in self.skinWidgetNames:
            self.infoBarRatingRect = self._rect(self[self.INFOBAR_RATING])
        self.updateInfoBarTitle()
        self.refreshInfoBarFormats()
        self.updateInfoBarMeta()
        if self.INFOBAR_META in self.skinWidgetNames or self.INFOBAR_RATING in self.skinWidgetNames or backdropMode() != 'off':
            # year, genre and rating of the host's page without waiting for the first INFO; its backdrop is there
            # then for audio playback and the first INFO
            self.infoPanel.requestArticle()

    def updateInfoBarTitle(self):
        # a skin with a meta line under the title has no room for a cut-off title: it ends with "…". The rating of the
        # host's page follows the title's text, the title leaves room for it.
        title = self['infoBarTitle']
        if self.INFOBAR_META not in self.skinWidgetNames or self.infoBarTitleRect is None:
            return
        rating = self.infoPanel.rating
        ratingRect = self.infoBarRatingRect
        ratingW = 0
        if rating and ratingRect is not None:
            label = self[self.INFOBAR_RATING]
            label.setText(rating)
            label.instance.resize(eSize(self.infoBarTitleRect[2], ratingRect[3]))
            ratingW = label.instance.calculateSize().width() + 2 * max(4, ratingRect[3] // 4)
        gap = max(6, self.infoBarTitleRect[3] // 4)
        maxWidth = self.infoBarTitleRect[2] - (ratingW + gap if ratingW else 0)
        textW = self._ellipsizeLabel(title, self.infoBarTitleText, maxWidth)
        if not ratingW:
            if ratingRect is not None:
                self._setOptionalVisible(self.INFOBAR_RATING, False)
            return
        label = self[self.INFOBAR_RATING]
        label.instance.resize(eSize(ratingW, ratingRect[3]))
        label.instance.move(ePoint(self.infoBarTitleRect[0] + (textW or maxWidth) + gap, ratingRect[1]))
        self._setOptionalVisible(self.INFOBAR_RATING, True)

    @staticmethod
    def _ellipsizeLabel(label, text=None, maxWidth=0):
        # a noWrap label clips its text at the edge: as much of it as fits (into maxWidth, else the label), then "…".
        # Returns the width of the text it shows, 0 when it can't tell.
        instance = label.instance
        if text is None:
            text = label.getText()
        else:
            label.setText(text)
        if instance is None or not text:
            return 0
        size = instance.size()
        maxWidth = min(maxWidth or size.width(), size.width())
        try:
            instance.resize(eSize(size.width() * 4, size.height()))
            width = instance.calculateSize().width()
            if width <= maxWidth:
                return width
            shortest, longest = 0, len(text)
            while shortest < longest:
                middle = (shortest + longest + 1) // 2
                label.setText(text[:middle].rstrip() + '…')
                if instance.calculateSize().width() <= maxWidth:
                    shortest = middle
                else:
                    longest = middle - 1
            label.setText(text[:shortest].rstrip() + '…')
            return instance.calculateSize().width()
        except Exception:
            printExc()
            label.setText(text)
            return 0
        finally:
            instance.resize(size)

    def infoBarPosterDecoded(self, ret):
        if ret.get('Pixmap') is None or self.isClosing or self.infoBarPosterBox is None:
            return
        poster = self[self.INFOBAR_POSTER]
        poster.updatePixmap(ret['Pixmap'], ret.get('FileName', ''))
        self._centerPixmap(poster, ret['Pixmap'], self.infoBarPosterBox)
        self._setOptionalVisible(self.INFOBAR_POSTER, True)
        if self.infoBarMaskLoaded:
            # the mask (rounded corners, frame) lies over the picture: as the skin drew it for a picture that fills the
            # box, one made for the picture's own size when it is smaller (a 16:9 picture in a 2:3 box)
            mask = self[self.INFOBAR_POSTER_MASK]
            box = self.infoBarPosterBox
            # ePicLoad hands out the picture centred in a pixmap of the whole box: its own size comes from the file
            picture = self._fittedRect(ret.get('FileName', ''), box) or self._rect(poster)
            if abs(picture[2] - box[2]) > 2 or abs(picture[3] - box[3]) > 2:
                pixmap = self._posterMaskPixmap(picture[2], picture[3])
                if pixmap is None:
                    self._setOptionalVisible(self.INFOBAR_POSTER_MASK, False)
                    return
                mask.instance.move(ePoint(picture[0], picture[1]))
                mask.instance.resize(eSize(picture[2], picture[3]))
                mask.setPixmap(pixmap)
            self._setOptionalVisible(self.INFOBAR_POSTER_MASK, True)

    @staticmethod
    def _fittedRect(path, box):
        # where a picture lands in the box when it keeps its aspect ratio (as ePicLoad scales it), None without PIL
        if Image is None or not path or not os_path.isfile(path):
            return None
        try:
            with Image.open(path) as img:
                imgW, imgH = img.size
        except Exception:
            return None
        x, y, w, h = box
        if imgW <= 0 or imgH <= 0:
            return None
        scale = min(w / float(imgW), h / float(imgH))
        picW, picH = min(w, int(round(imgW * scale))), min(h, int(round(imgH * scale)))
        return x + (w - picW) // 2, y + (h - picH) // 2, picW, picH

    def _posterMaskPixmap(self, width, height):
        # the skin's mask (infobar_poster_mask.png) for another picture size, drawn with PIL in the same colours: the
        # panel colour of its corner, the frame colour of the middle of its left edge, the corner radius of
        # "posterMaskRadius" in the skin's settings.json (on the 1280x720 canvas). None without PIL.
        if Image is None:
            return None
        try:
            source = os_path.join(self.playerSkinFolder, 'infobar_poster_mask.png')
            outPath = GetTmpDir('e2i_playerskin_postermask_%s_%dx%d_%d.png' % (os_path.basename(os_path.normpath(self.playerSkinFolder)), width, height, int(os_path.getmtime(source))))
            if not os_path.exists(outPath):
                with Image.open(source) as img:
                    img = img.convert('RGBA')
                    panel = img.getpixel((0, 0))
                    frame = img.getpixel((0, img.size[1] // 2))
                ss = 4
                scale = getDesktop(0).size().width() / float(self.REF_W)
                radius = float(self.skinSettings.get('posterMaskRadius', 10)) * scale * ss
                line = max(1, int(round(scale))) * ss
                big = Image.new('RGBA', (width * ss, height * ss), panel)
                draw = ImageDraw.Draw(big)
                draw.rounded_rectangle([0, 0, width * ss - 1, height * ss - 1], radius, fill=(0, 0, 0, 0))
                draw.rounded_rectangle([0, 0, width * ss - 1, height * ss - 1], radius, outline=frame, width=line)
                big.resize((width, height), Image.LANCZOS).save(outPath + '.part', format='png')
                os_rename(outPath + '.part', outPath)
            return LoadPixmap(outPath)
        except Exception:
            printExc()
        return None

    def refreshInfoBarFormats(self):
        # the badges and the info row follow the tracks and the shown subtitles
        try:
            self.updateInfoBarBadges()
            self.updateInfoBarStrip()
        except Exception:
            printExc()

    def updateInfoBarMeta(self):
        # "Host  ·  1h 29m  ·  Year: 2023  ·  Genre: Drama" - the last parts once INFO loaded the host's page
        if not self._declared(self.INFOBAR_META):
            return
        parts = []
        host = hostDisplayName(StripColorCodes(self.infoBarHostTitle or ''))
        if host:
            parts.append(host)
        length = int(self.playback.get('Length') or 0)
        if length >= 60:
            hours, minutes = length // 3600, (length % 3600) // 60
            parts.append(('%dh %02dm' % (hours, minutes)) if hours else ('%d min' % minutes))
        # the song of a radio stream, before the data of the host's page
        nowPlaying = self.playback.get('NowPlaying', '')
        if nowPlaying:
            parts.append(nowPlaying)
        meta = self.infoPanel.shortMeta
        if meta:
            parts.append(meta)
        text = '  ·  '.join(parts)
        if text != self.infoBarMetaText:
            # the length of a growing file comes every second, the text changes once a minute / song at most
            self.infoBarMetaText = text
            self._ellipsizeLabel(self[self.INFOBAR_META], text)
            self._setOptionalVisible(self.INFOBAR_META, bool(text))
        rating = self.infoPanel.rating
        if rating != self.infoBarRatingShown:
            # the host's page came in: the rating beside the title
            self.infoBarRatingShown = rating
            self.updateInfoBarTitle()

    def updateInfoBarKnob(self):
        knob = self[self.INFOBAR_KNOB]
        if not self._declared(self.INFOBAR_KNOB):
            return
        length = self.playback.get('Length') or 0
        if length <= 0 or self['progressBar'].instance is None:
            self._setOptionalVisible(self.INFOBAR_KNOB, False)
            return
        barX, barY, barW, barH = self._rect(self['progressBar'])
        knobW, knobH = knob.instance.size().width(), knob.instance.size().height()
        fraction = min(1.0, max(0.0, float(self.playback.get('CurrentTime') or 0) / length))
        knob.instance.move(ePoint(int(barX + barW * fraction - knobW / 2.0), int(barY + barH / 2.0 - knobH / 2.0)))
        self._setOptionalVisible(self.INFOBAR_KNOB, True)

    def updateInfoBarStrip(self):
        if not self.infoBarStripLayout:
            return
        video, audio = self.infoPanel.probedTracks()
        texts = stripTexts(video, audio, self.currentSubtitleInfo(), self.trackLanguageName)
        for idx, keyRect, valueEnd, gap in self.infoBarStripLayout:
            keyName, valueName, iconName = 'infoBarStrip%dKey' % idx, 'infoBarStrip%dValue' % idx, 'infoBarStrip%dIcon' % idx
            label, value = texts[idx - 1] if idx <= len(texts) else ('', '')
            if iconName in self.infoBarStripIcons:
                self._setOptionalVisible(iconName, bool(value))
            if not value:
                self._setOptionalVisible(keyName, False)
                self._setOptionalVisible(valueName, False)
                continue
            key = self[keyName]
            key.setText('%s:' % label)
            key.instance.resize(eSize(valueEnd - keyRect[0], keyRect[3]))
            keyW = min(key.instance.calculateSize().width() + 2, valueEnd - keyRect[0])
            key.instance.resize(eSize(keyW, keyRect[3]))
            self[valueName].setText(value)
            valueX = keyRect[0] + keyW + gap
            self[valueName].instance.move(ePoint(valueX, self[valueName].instance.position().y()))
            self[valueName].instance.resize(eSize(max(1, valueEnd - valueX), self[valueName].instance.size().height()))
            self._setOptionalVisible(keyName, True)
            self._setOptionalVisible(valueName, True)

    @staticmethod
    def _centerPixmap(widget, pixmap, box):
        # ePicLoad keeps the aspect ratio inside the widget's size and the pixmap is drawn at its top left: the widget
        # becomes as big as the picture, in the middle of its box
        x, y, w, h = box
        try:
            size = pixmap.size()
            picW, picH = min(size.width(), w), min(size.height(), h)
        except Exception:
            picW, picH = w, h
        if picW > 0 and picH > 0:
            widget.instance.resize(eSize(picW, picH))
            widget.instance.move(ePoint(x + (w - picW) // 2, y + (h - picH) // 2))

    def updateInfoBarBadges(self):
        layout = self.infoBarBadgeLayout
        if layout is None:
            return
        video, audio = self.infoPanel.probedTracks()
        # the video track's bitrate (a newer player, ffprobe), else the one of the HLS variant for video and audio
        bitrate = video.get('br') or streamBitrate(self.getStreamSourceUrl())
        badges = badgeList(video, audio, self.currentFrameRate(), self.currentSubtitleInfo(), bitrate)
        # infoBarBadge1 (its own colours in the skin) only takes the resolution class
        texts = {}
        others = [(text, sub) for kind, text, sub in badges if kind != 'res']
        resolution = [(text, sub) for kind, text, sub in badges if kind == 'res']
        if resolution:
            texts[self.INFOBAR_BADGES[0]] = resolution[0]
        for name, item in zip(self.INFOBAR_BADGES[1:], others):
            texts[name] = item
        border = layout['border']
        x = layout['x']
        overflow = False
        for name in self.INFOBAR_BADGES:
            widget, frame, subLabel = self[name], self[name + 'Frame'], self[name + 'Sub']
            if widget.instance is None:
                continue
            # after the first badge without room none follows (no narrower one after a gap, the order stays)
            text, sub = ('', '') if overflow else texts.get(name, ('', ''))
            width = subWidth = 0
            if text:
                widget.setText(text)
                widget.instance.resize(eSize(layout['maxX'] - layout['x'], layout['h']))
                width = max(widget.instance.calculateSize().width() + 2 * layout['pad'], layout['h'])
            if sub and subLabel.instance is not None:
                subLabel.setText(sub)
                subLabel.instance.resize(eSize(layout['maxX'] - layout['x'], layout['subH']))
                subWidth = subLabel.instance.calculateSize().width() + 2
            outerW = width + 2 * border
            slotW = max(outerW, subWidth)
            if text and x + slotW > layout['maxX']:
                overflow = True
            if not text or overflow:
                for part in (name, name + 'Frame', name + 'Sub'):
                    if self[part].instance is not None:
                        self[part].setText('')
                        self._setOptionalVisible(part, False)
                continue
            left = x + (slotW - outerW) // 2
            if frame.instance is not None:
                frame.instance.move(ePoint(left, layout['y']))
                frame.instance.resize(eSize(outerW, layout['h'] + 2 * border))
                self._setOptionalVisible(name + 'Frame', True)
            widget.instance.resize(eSize(width, layout['h']))
            widget.instance.move(ePoint(left + border, layout['y'] + border))
            self._setOptionalVisible(name, True)
            if subLabel.instance is not None:
                if sub:
                    subLabel.instance.move(ePoint(x + (slotW - subWidth) // 2, layout['subY']))
                    subLabel.instance.resize(eSize(subWidth, layout['subH']))
                else:
                    subLabel.setText('')
                self._setOptionalVisible(name + 'Sub', bool(sub))
            x += slotW + layout['gap']

    def showPlaybackInfoBar(self, excludeElems=['goToSeekPointer', 'goToSeekLabel'], blocked=None):
        self.playbackInfoBar['timer'].stop()

        for elem in self.playbackInfoBar['guiElemNames']:
            if elem not in excludeElems and elem not in self.infoBarHiddenElems:
                self[elem].show()

        if None is blocked or self.playbackInfoBar['blocked']:
            blocked = self.playbackInfoBar['blocked']

        self.playbackInfoBar['visible'] = True
        self.refreshChapterMarks()

        if not blocked:
            self.playbackInfoBar['timer'].start(self.autoHideTime, True)  # singleshot
        self.setSubOffsetFromInfoBar()
        if -1 != self.subHandler['current_sub_time_ms']:
            self.updateSubtitles(self.subHandler['current_sub_time_ms'], True)

        if self.clockFormat:
            self.updateClock()
            self.playbackInfoBar['clock_timer'].start(1000)

    def hidePlaybackInfoBar(self, excludeElems=[], force=False):
        self.playbackInfoBar['timer'].stop()

        if self.playbackInfoBar['blocked'] and not force:
            return

        for elem in self.playbackInfoBar['guiElemNames']:
            if elem not in excludeElems:
                self[elem].hide()

        self.playbackInfoBar['visible'] = False
        self.refreshChapterMarks()
        self.setSubOffsetFromInfoBar()
        if -1 != self.subHandler['current_sub_time_ms']:
            self.updateSubtitles(self.subHandler['current_sub_time_ms'], True)

        if self.clockFormat:
            self.playbackInfoBar['clock_timer'].stop()

    def updateClock(self):
        if self.clockFormat == '24':
            timeFormatString = self.skinSettings.get("clockFormat_24H", "%H:%M")
            self['clockTime'].setText(clockStrftime(timeFormatString))
        elif self.clockFormat == '12':
            timeFormatString = self.skinSettings.get("clockFormat_12H", "%I:%M")
            self['clockTime'].setText(clockStrftime(timeFormatString))

    def _showHideSubSynchroControl(self, show=True):
        for elem in self.subHandler['synchro']['guiElemNames']:
            if show:
                self[elem].show()
            else:
                self[elem].hide()
        self.subHandler['synchro']['visible'] = show

    def setSubOffsetFromInfoBar(self):
        if self.playbackInfoBar['visible']:
            desktopH = getDesktop(0).size().height()
            if self.subLinesNum > 1:
                # calc sub pos - scale/_effectiveSubLineHeight here
                # must match setSubtitlesText()'s own real-pixel math
                # exactly, or this overlap check against
                # self.infoBanerOffsetY (already real, correctly-scaled
                # pixels from initGuiComponentsPos()) would compare
                # mismatched units at FHD/WQHD
                scale = self._subtitleScale()
                lineHeight = self._effectiveSubLineHeight(scale)
                subY = desktopH - int(self.subConfig['pos'] * scale) - lineHeight
                subH = lineHeight

                yOffset = subY + subH - self.infoBanerOffsetY
                if yOffset > 0:
                    self.subHandler['pos_y_offset'] = yOffset
                    return
        self.subHandler['pos_y_offset'] = 0

    def showSubSynchroControl(self):
        self._showHideSubSynchroControl(True)
        self.updateSubSynchroControl()

    def hideSubSynchroControl(self, excludeElems=[], force=False):
        self._showHideSubSynchroControl(False)

    def __onShow(self):
        pass
        # Screen.hide(self) # we do not need window at now maybe in future

    def fatalErrorHandler(self, msg):
        if self.fatalErrorOccurs:
            return
        self.fatalErrorOccurs = True
        self.showMessage(msg, MessageBox.TYPE_ERROR, self._fatalErrorCallback)

    def _fatalErrorCallback(self):
        self.waitCloseTimeoutCallback()

    def consoleWrite(self, data):
        try:
            self.console.write(data, len(data))
            return
        except Exception:
            try:
                self.console.write(data)
                return
            except Exception:
                printExc()
        msg = _("Fatal error: consoleWrite failed!")
        self.fatalErrorHandler(msg)

    def extPlayerSendCommand(self, command, arg1=''):
        # printDBG("IPTVExtMoviePlayer.extPlayerSendCommand command[%s] arg1[%s]" % (command, arg1))
        if None is self.console:
            printExc("IPTVExtMoviePlayer.extPlayerSendCommand console not available")
            return False

        if 'ADD_TRIGGERS' == command:
            self.consoleWrite("t{0}\n".format(arg1))
        elif 'PLAYBACK_SET_LOOP_MODE' == command:
            self.consoleWrite("n%s\n" % arg1)
        elif 'PLAYBACK_LENGTH' == command:
            self.consoleWrite("l\n")
        elif 'PLAYBACK_CURRENT_TIME' == command:
            self.consoleWrite("j\n")
        elif 'PLAYBACK_INFO' == command:
            self.consoleWrite("i\n")
        elif 'PLAYBACK_SET_DOWNLOAD_FILE_TIMEOUT' == command:
            self.consoleWrite("t%s\n" % arg1)
        elif 'PLAYBACK_SET_PROGRESSIVE_DOWNLOAD' == command:
            self.consoleWrite("o%s\n" % arg1)
        elif 'PLAYBACK_SET_SUBTITLE_TRACK' == command:
            if ('%s' % arg1) != '-1':
                # we need be in play mode to switch/enabled embedded subtitles
                self.consoleWrite("c\n")
            self.consoleWrite("s%s\n" % arg1)
            self.consoleWrite("sc\n")
        elif 'PLAYBACK_SET_FORCED_ONLY' == command:
            self.consoleWrite("so%s\n" % arg1)
        elif 'PLAYBACK_SET_AUDIO_CHANNEL' == command:
            self.consoleWrite("am%s\n" % arg1)
        else:
            # All below commands require that 'PLAY ' status,
            # so we first send command to resume playback
            self.consoleWrite("c\n")

            if 'PLAYBACK_CONTINUE' == command:
                pass  # the "c" above already resumed
            elif 'PLAYBACK_PAUSE' == command:
                self.consoleWrite("p\n")
            elif 'PLAYBACK_SET_AUDIO_TRACK' == command:
                self.consoleWrite("a%s\n" % arg1)
                self.consoleWrite("ac\n")
            elif 'PLAYBACK_SEEK_RELATIVE' == command:
                self.consoleWrite("kc%s\n" % (arg1))
            elif 'PLAYBACK_SEEK_ABS' == command:
                self.consoleWrite("gf%s\n" % (arg1))
            elif 'PLAYBACK_FASTFORWARD' == command:
                self.consoleWrite("f%s\n" % arg1)
            elif 'PLAYBACK_FASTBACKWARD' == command:
                self.consoleWrite("b%s\n" % arg1)
            elif 'PLAYBACK_SLOWMOTION' == command:
                self.consoleWrite("m%s\n" % arg1)
            elif 'PLAYBACK_STOP' == command:
                printDBG("IPTVExtMoviePlayer.extPlayerSendCommand PLAYBACK_STOP")
                if not self.waitCloseFix['waiting']:
                    self.waitCloseFix['waiting'] = True
                    self.waitCloseFix['timer'].start(5000, True)  # singleshot
                self.consoleWrite("q\n")
            else:
                printDBG("IPTVExtMoviePlayer.extPlayerSendCommand unknown command[%s]" % command)
                return False
        return True

    def _playerErrorText(self, kind, obj, original):
        # the player's error in plain words (translated) in front of its original message, which stays for the log
        hint = ''
        try:
            hint = playerErrorHint(kind, ensure_str(obj.get('msg', '')), obj.get('code'))
        except Exception:
            printExc()
        return '%s\n%s' % (hint, original) if hint else original

    def _setVideoInfoWithAudio(self):
        # the video line of a skin without format badges plus the audio format; the first variant that fits the label:
        # full ("AVC 1920x1080p, 60fps, 16:9, DASH | AAC-LC 2.0"), short codec ("... | AAC 2.0"), without the aspect ratio
        track = self.playback.get('AudioTrack')
        audioFull, audioShort = audioFormatText(track), audioFormatText(track, True)
        streamType = self._getStreamTypeLabel()
        base, shortBase = self.videoInfoText or streamType, self.videoInfoShortText or streamType
        if not audioFull:
            # a track of unknown format: not the format of the track before
            self['videoInfo'].setText(base or '')
            return
        variants = []
        for video, audio in ((base, audioFull), (base, audioShort), (shortBase, audioShort)):
            text = '%s | %s' % (video, audio) if video else audio
            if text not in variants:
                variants.append(text)
        label = self['videoInfo']
        chosen = variants[-1]
        try:
            width = label.instance.size().width() if label.instance is not None else 0
            for text in variants:
                label.setText(text)
                if width <= 0 or label.instance.calculateSize().width() <= width:
                    chosen = text
                    break
        except Exception:
            printExc()
        label.setText(chosen)

    def _extePlayer3NewOptions(self, tmpUri):
        # options of exteplayer3 188, each only when the installed player reports it in EPLAYER3_EXTENDED (older
        # players stop at an option they do not know)
        opts = ''
        # resume: the position before the first packet instead of a jump a moment after the start (not while
        # buffering - the downloaded part decides there - and not for live streams)
        if self.lastPosition > 10 and self.downloader is None and not tmpUri.meta.get('iptv_livestream') and ExtePlayer3Cap('start'):
            opts += ' --start %d' % (self.lastPosition - 5)
            printDBG("IPTVExtMoviePlayer: resume with --start %d" % (self.lastPosition - 5))
            self.lastPosition = 0
            # the infobar shows where it goes on, like the jump of the older way did
            self.showInfoBarAtLength = True
        if ExtePlayer3Cap('cover'):
            # the cover embedded in the file (MP3 / FLAC / M4A / MKV): audio poster, screensaver, infobar. A name of
            # its own per start: Cover skips a file it decoded before (the cover of the title played before)
            self._removeEmbeddedCover()
            self.embeddedCoverPath = GetTmpDir('.iptv_embedded_cover_%d.img' % int(time.time() * 1000))
            opts += ' --cover "%s"' % shellQuote(self.embeddedCoverPath)
        if ExtePlayer3Cap('forcedonly') and config.plugins.iptvplayer.exteplayer_forced_subtitles.value:
            opts += ' --forced-only'
            self.forcedSubtitlesOnly = True
        xcode = ExtePlayer3Cap('xcode')
        for value, ac3Opt, eac3Opt in ((config.plugins.iptvplayer.exteplayer_dts_transcode.value, '-Z', '--dts-eac3'),
                                       (config.plugins.iptvplayer.exteplayer_truehd_transcode.value, '-X', '--truehd-eac3')):
            if 'eac3' == value and xcode & 4:
                opts += ' ' + eac3Opt
            elif value in ('ac3', 'eac3') and xcode & 1:
                # E-AC-3 without the encoder in this FFmpeg: AC3
                opts += ' ' + ac3Opt
        if xcode & 2 and config.plugins.iptvplayer.exteplayer_heaac_transcode.value:
            opts += ' -Y'
        if ExtePlayer3Version() >= 188:
            if '1' == config.plugins.iptvplayer.exteplayer_hls_quality.value:
                opts += ' -Q 1'
            if config.plugins.iptvplayer.exteplayer_default_audio_only.value:
                opts += ' -D 1'
            if '0x0' != config.plugins.iptvplayer.exteplayer_h264_limit.value:
                opts += ' -M %s' % config.plugins.iptvplayer.exteplayer_h264_limit.value
        keys = tmpUri.meta.get('iptv_drm_keys', '')
        if keys and ExtePlayer3Cap('drmkey') & 1:
            # CENC (ClearKey) keys of the host, "kid:key" each
            for pair in keys.split(','):
                if pair.strip():
                    opts += ' --key "%s"' % shellQuote(pair.strip())
        return opts

    def _removeEmbeddedCover(self):
        # this playback's cover and those a killed player left behind
        tmpDir = GetTmpDir()
        try:
            names = [name for name in os_listdir(tmpDir) if name.startswith('.iptv_embedded_cover')]
        except Exception:
            names = []
        for name in names:
            try:
                os_remove(os_path.join(tmpDir, name))
            except Exception:
                printExc()

    def embeddedCoverReceived(self, obj):
        # {"cover": {"file", "type", "w", "h"}} of exteplayer3 --cover, {"cover": {}} when the file has none: the
        # list row's own picture stays first (not the host's picture for rows without one, e.g. local files), the
        # embedded one comes before the host logo
        path = obj.get('file', '') if isinstance(obj, dict) else ''
        if not path or path != self.embeddedCoverPath or self.isClosing or not os_path.isfile(path):
            return
        printDBG("IPTVExtMoviePlayer: embedded cover %s" % obj)
        index = 0 if self.coverIsDefault else 1
        for paths in (self.audioCover['paths'], self.infoBarPosterPaths, getattr(self.screenSaver, 'imagePaths', None)):
            if isinstance(paths, list) and path not in paths:
                paths.insert(index, path)
        own = self.audioCover['paths'][0]
        if index and own and os_path.isfile(own):
            return
        self.audioCover['nothing'] = False
        if self.audioCover['shown']:
            # the host logo is shown: the cover instead
            self.audioCover['shown'] = False
            self.showAudioCover()
        poster = self[self.INFOBAR_POSTER]
        if poster.instance is not None and self.infoBarPosterBox is not None:
            poster.decodePreparedCover(path, self.infoBarPosterDecoded, 'infoBarPoster')

    def createSummary(self):
        summary = config.plugins.iptvplayer.extplayer_summary.value
        create = False
        if summary == 'yes':
            create = True
        elif summary == 'auto':
            try:
                if getDesktop(1).size().width() > 132:
                    create = True
            except Exception:
                pass
        if create:
            return IPTVExtMoviePlayerColorSummary if isLargeLcd() else IPTVExtMoviePlayerSummary
        return None
