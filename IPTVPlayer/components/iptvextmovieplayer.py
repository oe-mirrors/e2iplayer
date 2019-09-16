# -*- coding: utf-8 -*-
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
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.components.cover import Cover3
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIPTVDMImgDir, GetBinDir, GetSubtitlesDir, eConnectCallback, \
                                                          GetE2VideoAspectChoices, GetE2VideoAspect, SetE2VideoAspect, GetE2VideoPolicyChoices, \
                                                          GetE2VideoPolicy, SetE2VideoPolicy, GetDefaultLang, GetPolishSubEncoding, E2PrioFix, iptv_system, \
                                                          GetE2AudioCodecMixOption, SetE2AudioCodecMixOption, CreateTmpFile, GetTmpDir, IsExecutable, MapUcharEncoding, \
                                                          GetE2VideoModeChoices, GetE2VideoMode, SetE2VideoMode
from Plugins.Extensions.IPTVPlayer.tools.iptvsubtitles import IPTVSubtitlesHandler, IPTVEmbeddedSubtitlesHandler
from Plugins.Extensions.IPTVPlayer.tools.iptvmoviemetadata import IPTVMovieMetaDataHandler
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.iptvsubdownloader import IPTVSubDownloaderWidget
from Plugins.Extensions.IPTVPlayer.components.iptvsubsimpledownloader import IPTVSubSimpleDownloaderWidget
from Plugins.Extensions.IPTVPlayer.components.iptvchoicebox import IPTVChoiceBoxWidget, IPTVChoiceBoxItem
from Plugins.Extensions.IPTVPlayer.components.iptvdirbrowser import IPTVFileSelectorWidget
from Plugins.Extensions.IPTVPlayer.components.configextmovieplayer import ConfigExtMoviePlayerBase, ConfigExtMoviePlayer
from Plugins.Extensions.IPTVPlayer.libs.pCommon import CParsingHelper
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
###################################################

###################################################
# FOREIGN import
###################################################
from enigma import eServiceReference, eConsoleAppContainer, getDesktop, eTimer, eLabel, gFont, ePoint, eSize, gRGB
from Screens.Screen import Screen
from Screens.ChoiceBox import ChoiceBox
from Components.AVSwitch import AVSwitch
from Components.ActionMap import ActionMap
from Components.config import config
from Components.Label import Label
from Components.ProgressBar import ProgressBar

from Components.config import config # temporary player should not use config directly
from Screens.MessageBox import MessageBox
from Tools.LoadPixmap import LoadPixmap
from Tools.BoundFunction import boundFunction
from Tools.Directories import fileExists
from skin import parseColor, parseFont

from datetime import timedelta
try:
    from math import floor, fabs
    try:    import json
    except Exception: import simplejson as json
except Exception:
    printExc()
from os import chmod as os_chmod, path as os_path
import re
import time
import socket
###################################################

class ExtPlayerCommandsDispatcher():
    def __init__(self, owner):
        self.owner = owner
        
        #SEEK_SPEED_MAP = [0.125, 0.25, 0.5, 0, 2, 4, 8, 16, 32, 64, 128]
        self.SEEK_SPEED_MAP = []
        for item in reversed(config.seek.speeds_slowmotion.value):
            self.SEEK_SPEED_MAP.append(1.0 / float(item))
        self.SEEK_SPEED_MAP.append(0)
        for item in config.seek.speeds_forward.value:
            self.SEEK_SPEED_MAP.append( item )
        self.speedIdx = self.SEEK_SPEED_MAP.index(0)
        
    def doAddTriggers(self, arg): self.extPlayerSendCommand('ADD_TRIGGERS', arg)
        
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
    
    def setDownloadFileTimeout(self, timeout):
        self.extPlayerSendCommand('PLAYBACK_SET_DOWNLOAD_FILE_TIMEOUT', timeout, False)
        
    def setProgressiveDownload(self, flag):
        self.extPlayerSendCommand('PLAYBACK_SET_PROGRESSIVE_DOWNLOAD', flag, False)
        
    def setLoopMode(self, value):
        self.extPlayerSendCommand('PLAYBACK_SET_LOOP_MODE', value, False)
    
    def doSeek(self, diff):       
        self.extPlayerSendCommand('PLAYBACK_SEEK_RELATIVE', '%d' %diff)
        self.speedIdx = self.SEEK_SPEED_MAP.index(0)
    def doGoToSeek(self, arg):       
        self.extPlayerSendCommand('PLAYBACK_SEEK_ABS', arg)
        self.speedIdx = self.SEEK_SPEED_MAP.index(0)
    def doSeekFwd(self, arg):    self.extPlayerSendCommand('PLAYBACK_FASTFORWARD', arg)
    def doSlowMotion(self, arg): self.extPlayerSendCommand('PLAYBACK_SLOWMOTION', arg)
    
    def doUpdateInfo(self):
        self.extPlayerSendCommand('PLAYBACK_LENGTH', '', False)
        self.extPlayerSendCommand('PLAYBACK_CURRENT_TIME', '', False)
        
    ##############################################
    
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
        if self.speedIdx >= len(self.SEEK_SPEED_MAP): self.speedIdx = len(self.SEEK_SPEED_MAP) - 1
        elif self.speedIdx < 0: self.speedIdx = 0
        val = self.SEEK_SPEED_MAP[self.speedIdx]
        printDBG("ExtPlayerCommandsDispatcher.tipMode val[%r]" % val)
        if 0 == val:  self.play()
        elif 1 < val:
            if 'eplayer' == self.owner.player: val -= 1
            self.doSeekFwd(str(val))
        else: self.doSlowMotion(str(int(1.0 / val)))
    
    def extPlayerSendCommand(self, cmd, arg='', getStatus=True):
        ret = False
        if None != self.owner: 
            ret = self.owner.extPlayerSendCommand(cmd, arg)
            if getStatus: 
                self.owner.extPlayerSendCommand("PLAYBACK_INFO", '')
        else:
            printDBG(">> extPlayerSendCommand owner NONE")
        return ret

class IPTVExtMoviePlayer(Screen):
    Y_CROPPING_GUARD = 0
    playback = {}
    def __prepareSkin(self):
        
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
        
        subSkinPart = '<widget name="subLabel{0}" position="10,%d" size="%d,%d" zPosition="1" halign="center" %s/>' % (getDesktop(0).size().height()-sub['pos']-sub['box_height'], getDesktop(0).size().width()-20, sub['box_height'], subSkinPart)
        subSkin = ''
        for idx in range(self.subLinesNum):
            subSkin += subSkinPart.format(idx+1)
        
        # skin for SD
        if getDesktop(0).size().width() < 800:
            playbackBannerFile = "playback_banner_sd.png"
            skin = """
            <screen name="IPTVExtMoviePlayer"    position="center,center" size="%d,%d" flags="wfNoBorder" backgroundColor="#FFFFFFFF" >
                    <widget name="pleaseWait"         noWrap="1" position="30,30"        size="500,30"    zPosition="3" transparent="1" foregroundColor="#999999"   backgroundColor="transparent" font="Regular;24" halign="left"  valign="top"/>
                    
                    <widget name="logoIcon"           position="0,0"           size="160,40"    zPosition="4" transparent="1" alphatest="blend" />
                    <widget name="playbackInfoBaner"  position="0,30"          size="650,112"   zPosition="2" pixmap="%s" />
                    <widget name="progressBar"        position="94,54"         size="544,7"     zPosition="5" pixmap="%s" transparent="1" borderWidth="1" borderColor="#888888" />
                    <widget name="bufferingCBar"      position="94,54"         size="544,7"     zPosition="4" pixmap="%s" transparent="1" borderWidth="1" borderColor="#888888" />
                    <widget name="bufferingBar"       position="94,54"         size="544,7"     zPosition="3" pixmap="%s" borderWidth="1" borderColor="#888888" />
                    <widget name="statusIcon"         position="20,45"         size="40,40"     zPosition="4"             transparent="1" alphatest="blend" />
                    <widget name="loopIcon"           position="43,30"         size="40,40"     zPosition="4"             transparent="1" alphatest="blend" />
                    
                    <widget name="goToSeekPointer"    position="94,0"                     size="150,60"   zPosition="8" pixmap="%s" transparent="1" alphatest="blend" />
                    <widget name="goToSeekLabel"      noWrap="1" position="94,0"          size="150,40"   zPosition="9" transparent="1" foregroundColor="white"     backgroundColor="#251f1f1f" font="Regular;24" halign="center" valign="center"/>
                    <widget name="infoBarTitle"       noWrap="1" position="82,30"         size="568,23"   zPosition="3" transparent="1" foregroundColor="white"     backgroundColor="#251f1f1f" font="Regular;18" halign="center" valign="center"/>
                    <widget name="currTimeLabel"      noWrap="1" position="94,62"         size="568,23"   zPosition="3" transparent="1" foregroundColor="#66ccff"   backgroundColor="#251f1f1f" font="Regular;24" halign="left"   valign="top"/>
                    <widget name="lengthTimeLabel"    noWrap="1" position="307,62"        size="120,30"   zPosition="3" transparent="1" foregroundColor="#999999"   backgroundColor="#251f1f1f" font="Regular;24" halign="center" valign="top"/>
                    <widget name="remainedLabel"      noWrap="1" position="518,62"        size="120,30"   zPosition="3" transparent="1" foregroundColor="#66ccff"   backgroundColor="#251f1f1f" font="Regular;24" halign="right"  valign="top"/>
                    <widget name="videoInfo"          noWrap="1" position="0,0"           size="650,30"   zPosition="3" transparent="1" foregroundColor="#999999"   backgroundColor="#251f1f1f" font="Regular;24" halign="right"  valign="top"/>
                    
                    %s
                    
                    <widget name="subSynchroIcon"     position="0,0"           size="180,66"  zPosition="4" transparent="1" alphatest="blend" />
                    <widget name="subSynchroLabel"    position="1,3"           size="135,50"  zPosition="5" transparent="1" foregroundColor="white"      backgroundColor="transparent" font="Regular;24" halign="center"  valign="center"/>
                    
                    %s
            </screen>""" 
        else:
            playbackBannerFile = "playback_banner.png"
            skin = """
            <screen name="IPTVExtMoviePlayer"    position="center,center" size="%d,%d" flags="wfNoBorder" backgroundColor="#FFFFFFFF" >
                    <widget name="pleaseWait"         noWrap="1" position="30,30"        size="500,30"    zPosition="3" transparent="1" foregroundColor="#999999"   backgroundColor="transparent" font="Regular;24" halign="left"  valign="top"/>
                    
                    <widget name="logoIcon"           position="140,30"        size="160,40"    zPosition="4"             transparent="1" alphatest="blend" />
                    <widget name="playbackInfoBaner"  position="0,0"           size="1280,177"  zPosition="2" pixmap="%s" />
                    <widget name="progressBar"        position="220,86"        size="840,7"     zPosition="5" pixmap="%s" transparent="1" borderWidth="1" borderColor="#888888" />
                    <widget name="bufferingCBar"      position="220,86"        size="840,7"     zPosition="4" pixmap="%s" transparent="1" borderWidth="1" borderColor="#888888" />
                    <widget name="bufferingBar"       position="220,86"        size="840,7"     zPosition="3" pixmap="%s" borderWidth="1" borderColor="#888888" />
                    <widget name="statusIcon"         position="150,70"        size="40,40"     zPosition="4"             transparent="1" alphatest="blend" />
                    <widget name="loopIcon"           position="150,110"       size="40,40"     zPosition="4"             transparent="1" alphatest="blend" />
                    
                    <widget name="goToSeekPointer"    position="94,30"          size="150,60"  zPosition="8" pixmap="%s" transparent="1" alphatest="blend" />
                    <widget name="goToSeekLabel"      noWrap="1" position="94,30"         size="150,40"   zPosition="9" transparent="1" foregroundColor="white"     backgroundColor="#251f1f1f" font="Regular;24" halign="center" valign="center"/>
                    <widget name="infoBarTitle"       noWrap="1" position="220,50"        size="840,30"   zPosition="3" transparent="1" foregroundColor="white"     backgroundColor="#251f1f1f" font="Regular;24" halign="center" valign="center"/>
                    <widget name="currTimeLabel"      noWrap="1" position="220,100"       size="200,40"   zPosition="3" transparent="1" foregroundColor="#66ccff"   backgroundColor="#251f1f1f" font="Regular;30" halign="left"   valign="top"/>
                    <widget name="lengthTimeLabel"    noWrap="1" position="540,100"       size="200,40"   zPosition="3" transparent="1" foregroundColor="#999999"   backgroundColor="#251f1f1f" font="Regular;30" halign="center" valign="top"/>
                    <widget name="remainedLabel"      noWrap="1" position="860,100"       size="200,40"   zPosition="3" transparent="1" foregroundColor="#66ccff"   backgroundColor="#251f1f1f" font="Regular;30" halign="right"  valign="top"/>
                    <widget name="videoInfo"          noWrap="1" position="560,20"        size="500,30"   zPosition="3" transparent="1" foregroundColor="#999999"   backgroundColor="#251f1f1f" font="Regular;24" halign="right"  valign="top"/>
                    
                    %s
                    
                    <widget name="subSynchroIcon"     position="0,0"           size="180,66"  zPosition="4" transparent="1" alphatest="blend" />
                    <widget name="subSynchroLabel"    position="1,3"           size="135,50"  zPosition="5" transparent="1" foregroundColor="white"      backgroundColor="transparent" font="Regular;24" halign="center"  valign="center"/>
                    
                    %s
            </screen>""" 

        if self.clockFormat:
            clockFontSize = 30 if getDesktop(0).size().width() == 1920 else 24
            clockWidget = '<widget name="clockTime" noWrap="1" position="37,69" size="100,40" zPosition="3" transparent="1" foregroundColor="white" backgroundColor="#251f1f1f" font="Regular;%d" halign="center" valign="center" />' % clockFontSize
        else:
            clockWidget = ''
        
        skin =  skin % ( getDesktop(0).size().width(), 
                         getDesktop(0).size().height(),
                         GetIPTVDMImgDir(playbackBannerFile),
                         GetIPTVDMImgDir("playback_progress.png"),
                         GetIPTVDMImgDir("playback_cbuff_progress.png"),
                         GetIPTVDMImgDir("playback_buff_progress.png"),
                         GetIPTVDMImgDir('playback_pointer.png'),
                         clockWidget,
                         subSkin
                         ) ##00000000 bottom
        sub = None
        return skin
    
    def __init__(self, session, filesrcLocation, FileName, lastPosition=None, player='eplayer', additionalParams={}):
        self.configObj = ConfigExtMoviePlayerBase()
        self.subConfig = self.configObj.getSubtitleFontSettings()
        self.clockFormat = self.configObj.getInfoBannerrClockFormat()
        self.skin = self.__prepareSkin()
        Screen.__init__(self, session)
        self.skinName = "IPTVExtMoviePlayer"
        
        self.player = player
        if 'gstplayer' == self.player: 
            self.playerName = _("external gstplayer")
            self.gstAdditionalParams = {}
            self.gstAdditionalParams['download-buffer-path'] = additionalParams.get('download-buffer-path', '') # File template to store temporary files in, should contain directory and XXXXXX
            self.gstAdditionalParams['ring-buffer-max-size'] = additionalParams.get('ring-buffer-max-size', 0) # in MB
            self.gstAdditionalParams['buffer-duration']      = additionalParams.get('buffer-duration', -1) # in s
            self.gstAdditionalParams['buffer-size']          = additionalParams.get('buffer-size', 0) # in KB
            self.gstAdditionalParams['file-download-timeout']= additionalParams.get('file-download-timeout', 0) # in MS
            self.gstAdditionalParams['file-download-live']   = additionalParams.get('file-download-live', False) # True or False
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

        self.session.nav.playService(None) # current service must be None to give free access to DVB Audio and Video Sinks
        self.fileSRC      = strwithmeta(filesrcLocation)
        self.title        = FileName
        self.hostName     = additionalParams.get('host_name', '')
        if lastPosition:
            self.lastPosition = lastPosition
        else:
            self.lastPosition = 0 
        self.downloader = additionalParams.get('downloader', None)
        self.isDownladManagerAvailable = additionalParams.get('download_manager_available', False)
        self.externalSubTracks = additionalParams.get('external_sub_tracks', []) #[{'title':'', 'lang':'', 'url':''}, ...]
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
        
        printDBG('IPTVExtMoviePlayer.__init__ lastPosition[%r]' % self.lastPosition)
        
        self.extPlayerCmddDispatcher = ExtPlayerCommandsDispatcher(self)
        
        self["actions"] = ActionMap(['IPTVAlternateVideoPlayer', 'MoviePlayerActions', 'MediaPlayerActions', 'MediaPlayerSeekActions', 'WizardActions'],
            {
                "leavePlayer"  : self.key_stop,
                'play'         : self.key_play,
                'pause'        : self.key_pause,
                'exit'         : self.key_exit,
                'back'         : self.key_exit,
                'info'         : self.key_info,
                'seekdef:1'    : self.key_seek1,
                'seekdef:3'    : self.key_seek3,
                'seekdef:4'    : self.key_seek4,
                'seekdef:6'    : self.key_seek6,
                'seekdef:7'    : self.key_seek7,
                'seekdef:9'    : self.key_seek9,
                'seekFwd'      : self.key_seekFwd,
                'seekBack'     : self.key_seekBack,
                'left_press'   : self.key_left_press,
                'left_repeat'  : self.key_left_repeat,
                'rigth_press'  : self.key_rigth_press,
                'rigth_repeat' : self.key_rigth_repeat,
               
                'up_press'     : self.key_up_press,
                'up_repeat'    : self.key_up_repeat,
                'down_press'   : self.key_down_press,
                'down_repeat'  : self.key_down_repeat,
                
                'ok'           : self.key_ok,
                'subtitles'    : self.key_subtitles,
                'audio'        : self.key_audio,
                'videooptions' : self.key_videooption,
                'menu'         : self.key_menu,
                'loop'         : self.key_loop,
                'record'       : self.key_record,
            }, -1)
        
        self.onClose.append(self.__onClose)
        self.onShow.append(self.onStart)
        #self.onLayoutFinish.append(self.onStart)
        
        self.console = None
        
        self.isClosing = False
        self.responseData = ""
        
        # playback info
        # GUI
        self.updateInfoTimer = eTimer()
        self.updateInfoTimer_conn = eConnectCallback(self.updateInfoTimer.timeout, self.updateInfo)
        
        # playback info bar gui elements
        self['logoIcon']          = Cover3()
        self['playbackInfoBaner'] = Cover3()
        self['statusIcon']        = Cover3()
        self['loopIcon']          = Cover3()
        self['progressBar']       = ProgressBar()
        self['bufferingCBar']     = ProgressBar()
        self['bufferingBar']      = ProgressBar()
        self['goToSeekPointer']   = Cover3() 
        self['infoBarTitle']      = Label(self.title)
        self['goToSeekLabel']     = Label("0:00:00")
        self['currTimeLabel']     = Label("0:00:00")
        self['remainedLabel']     = Label("-0:00:00")
        self['lengthTimeLabel']   = Label("0:00:00")
        self['videoInfo']         = Label(" ")
        if self.clockFormat: self['clockTime'] = Label(" ")
        self['pleaseWait']        = Label(_("Opening. Please wait..."))
        
        # for subtitles
        self.infoBanerOffsetY = -1
        for idx in range(self.subLinesNum):
            #printf('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> ' % ('subLabel%d'%(idx+1)))
            self['subLabel%d'%(idx+1)] = Label(" ")
        self.hideSubtitles()
        self.subHandler = {}
        self.subHandler['current_sub_time_ms'] = -1
        self.subHandler['handler'] = IPTVSubtitlesHandler()
        self.subHandler['embedded_handler'] = IPTVEmbeddedSubtitlesHandler()
        self.subHandler['handler_type'] = 'embedded_handler'
        self.subHandler['enabled'] = False
        self.subHandler['timer']   = eTimer()
        self.subHandler['timer_conn']  =  eConnectCallback(self.subHandler['timer'].timeout, self.updatSubtitlesTime)
        self.subHandler['latach_time'] = -1
        self.subHandler['last_time']   = -1
        self.subHandler['marker']      = None
        self.subHandler['synchro']     = {'visible':False, 'guiElemNames':['subSynchroLabel', 'subSynchroIcon'], 'icon':None}
        self.subHandler['pos_y_offset'] = 0
        self['subSynchroLabel']        = Label("0.0s")
        self['subSynchroIcon']         = Cover3() 
        try: self.subHandler['synchro']['icon'] = LoadPixmap( GetIPTVDMImgDir("sub_synchro.png") )
        except Exception: printExc()
        self.hideSubSynchroControl()
        
        # VIDEO options
        self.defVideoOptions  = {'aspect':None, 'aspect_choices':[], 'policy':None, 'policy_choices':[], 'policy2':None, 'policy2_choices':[], 'videomode':additionalParams.get('defaul_videomode', None), 'videomode_choices':GetE2VideoModeChoices()}
        self.videoOptSetters  = {'aspect':SetE2VideoAspect, 'policy':SetE2VideoPolicy, 'policy2':SetE2VideoPolicy} 
        self.currVideoOptions = {'aspect':None, 'policy':None, 'policy2':None, 'videomode':None}
        
        # AUDIO options
        self.defAudioOptions  = {'ac3':None, 'aac':None}
        
        # meta data
        self.metaHandler = IPTVMovieMetaDataHandler( self.hostName, self.title, self.fileSRC )
        
        # goto seek  timer
        self.playback['GoToSeekTimer'] = eTimer()
        self.playback['GoToSeekTimer_conn'] = eConnectCallback(self.playback['GoToSeekTimer'].timeout, self.doGoToSeek)
        
        self.playback.update( {'CurrentTime':    0,
                               'BufferCTime':    0,
                               'ConfirmedCTime': 0,
                               'BufferFill':     0,
                               'Length':         0,
                               'LengthFromPlayerReceived': False,
                               'GoToSeekTime':      0,
                               'StartGoToSeekTime': 0,
                               'GoToSeeking':    False,
                               'IsLive':         False,
                               'IsLoop':         False,
                               'Status':         None,
                               'VideoTrack':     {},
                               'AudioTrack':     {},
                               'AudioTracks':    [],
                               'SubtitleTrack':  {},
                               'SubtitleTracks': [],
                              } )
        # load pixmaps for statusIcon
        self.playback['loopIcons'] = {'On':None, 'Off':None}
        self.playback['statusIcons'] = {'Play':None, 'Pause':None, 'FastForward':None, 'SlowMotion':None}
        try:
            self.playback['statusIcons']['Play']        = LoadPixmap( GetIPTVDMImgDir("playback_a_play.png") )
            self.playback['statusIcons']['Pause']       = LoadPixmap( GetIPTVDMImgDir("playback_a_pause.png") )
            self.playback['statusIcons']['FastForward'] = LoadPixmap( GetIPTVDMImgDir("playback_a_ff.png") )
            self.playback['statusIcons']['SlowMotion']  = self.playback['statusIcons']['FastForward']
            if 'gstplayer' == self.player: 
                self.playback['logoIcon']               = LoadPixmap( GetIPTVDMImgDir("playback_gstreamer_logo.png") )
            else: self.playback['logoIcon']             = LoadPixmap( GetIPTVDMImgDir("playback_ffmpeg_logo.png") )
            self.playback['loopIcons']['On']  = LoadPixmap( GetIPTVDMImgDir("playback_loop_on.png") )
            self.playback['loopIcons']['Off'] = LoadPixmap( GetIPTVDMImgDir("playback_loop_off.png") )
        except Exception:
            printExc()
        
        # show hide info bar functionality
        self.goToSeekRepeatCount = 0
        self.goToSeekStep = 0
        self.playbackInfoBar = {'visible':False, 'blocked':False, 'guiElemNames':['playbackInfoBaner', 'progressBar', 'bufferingCBar', 'bufferingBar', 'goToSeekPointer', 'goToSeekLabel', 'infoBarTitle', 'currTimeLabel', 'remainedLabel', 'lengthTimeLabel', 'videoInfo', 'statusIcon', 'loopIcon', 'logoIcon'] }
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
        
        self.waitCloseFix = {'waiting':False}
        self.waitCloseFix['timer'] = eTimer()
        self.waitCloseFix['timer_conn'] = eConnectCallback(self.waitCloseFix['timer'].timeout, self.waitCloseTimeoutCallback)
        
        self.closeRequestedByUser = None
        self.playerBinaryInfo = {'version':None, 'data':''}
        self.messageQueue = []
        self.underMessage = False
        
        try: self.autoHideTime = 1000 * int(self.configObj.getInfoBarTimeout())
        except Exception: self.autoHideTime = 1000
        
        self.fatalErrorOccurs  = False
        self.delayedClosure    = None
        self.childWindowsCount = 0
        
        self.workconsole = None
        # we will set movie player config at first use of subtitles
        # to fix problems with small subtitles at first run with custom 
        # exteplayer skin
        self.setMoviePlayerConfig = True
        self.clipLength = None
        
    def showMenuOptions(self):
        printDBG("showMenuOptions")
        options = []
        options.append(IPTVChoiceBoxItem(_("Configuration"), "", "menu"))
        options.append(IPTVChoiceBoxItem(_("Subtitles"), "", "subtitles"))
        if len(self.playback['AudioTracks']): options.append(IPTVChoiceBoxItem(_("Audio tracks"), "", "audio_tracks"))
        options.append(IPTVChoiceBoxItem(_("Video options"), "", "video_options"))
        
        if self.isDownladManagerAvailable and self.downloader:
            options.append(IPTVChoiceBoxItem(_("Stop playback with buffer save"), "", "close_with_buffer_save"))
        
        self.openChild(boundFunction(self.childClosed, self.showMenuOptionsCallback), IPTVChoiceBoxWidget, {'width':500, 'height':340, 'current_idx':0, 'title':_("Menu"), 'options':options})
        
    def showMenuOptionsCallback(self, ret=None):
        printDBG("showMenuOptionsCallback ret[%r]" % [ret])
        if not isinstance(ret, IPTVChoiceBoxItem): return
        
        if "menu" == ret.privateData:
            self.runConfigMoviePlayer()
        elif "subtitles" == ret.privateData:
            self.selectSubtitle()
        elif "audio_tracks" == ret.privateData:
            self.selectAudioTrack()
        elif "video_options" == ret.privateData:
            self.selectVideoOptions()
        elif "close_with_buffer_save" == ret.privateData:
            self.key_stop("save_buffer")
        
    def runConfigMoviePlayer(self):
        printDBG("runConfigMoviePlayerCallback")
        self.openChild(boundFunction(self.childClosed, self.runConfigMoviePlayerCallback), ConfigExtMoviePlayer, True)
        
    def runConfigMoviePlayerCallback(self, confgiChanged=False):
        printDBG("runConfigMoviePlayerCallback confgiChanged[%s]" % confgiChanged)
        if not confgiChanged: return
        
        # change subtitles settings
        prevSub = self.subConfig
        self.subConfig = self.configObj.getSubtitleFontSettings()
        sub = self.subConfig
        
        for idx in range(self.subLinesNum):
            subLabel = "subLabel%d"%(idx+1)
            self[subLabel].instance.setFont( gFont(sub['font'], sub['font_size']) )
            self[subLabel].instance.setForegroundColor( parseColor(sub['font_color']) )
            self[subLabel].instance.setBackgroundColor( parseColor(sub['background']) )

            if 'border' in sub:
                self[subLabel].instance.setBorderColor( parseColor(sub['border']['color']) )
                self[subLabel].instance.setBorderWidth( sub['border']['width'] )
            else:
                try:
                    tmp = dir(eLabel)
                    if 'setBorderColor' in tmp:
                        self[subLabel].instance.setBorderWidth( 0 )
                except Exception: printExc()
            
            if 'shadow' in sub:
                self[subLabel].instance.setShadowColor( parseColor(sub['shadow']['color']) )
                self[subLabel].instance.setShadowOffset( ePoint(sub['shadow']['xoffset'], sub['shadow']['yoffset']) )
            elif 'shadow' in prevSub:
                self[subLabel].instance.setShadowOffset( ePoint(0, 0) )
                self[subLabel].instance.setShadowColor( gRGB() ) # parseColor("#ff111111") )
            
            if self.subLinesNum > 1 or 'transparent' != self.subConfig['background']:
                self[subLabel].instance.setVAlign(1)
            else:
                try:
                    valignMap = {'bottom':2,'center':1, 'top':0}
                    self[subLabel].instance.setVAlign(valignMap.get(sub['box_valign'], 2))
                    
                    self[subLabel].instance.resize(eSize(getDesktop(0).size().width()-20, sub['box_height']))
                    self[subLabel].resize(eSize(getDesktop(0).size().width()-20, sub['box_height']))
                    self[subLabel].move( ePoint(10, getDesktop(0).size().height()-sub['pos']-sub['box_height']) )
                    self[subLabel].instance.move( ePoint(10, getDesktop(0).size().height()-sub['pos']-sub['box_height']) )
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
            metaVal   = self.metaHandler.getVideoOption(opt)
            currVal   = self.currVideoOptions[opt]
            defVal    = self.defVideoOptions[opt]
            
            printDBG(">>>>>>>>>>>>> 0 [%s]" % (metaVal) )
            if None == metaVal:
                printDBG(">>>>>>>>>>>>> A [%s] [%s]" % (currVal, playerVal) )
                if currVal != playerVal:
                    printDBG(">>>>>>>>>>>>> B")
                    if None == playerVal:
                        self.currVideoOptions[opt] = defVal
                    else:
                        self.currVideoOptions[opt] = playerVal
                    videoOptionChange = True
        
        if videoOptionChange:
            self.applyVideoOptions(self.currVideoOptions)
        
        # set auto hide options
        try: self.autoHideTime = 1000 * int(self.configObj.getInfoBarTimeout())
        except Exception: self.autoHideTime = 1000
        
    def getE2AudioOptions(self):
        defAudioOptions  = {'ac3': GetE2AudioCodecMixOption('ac3'), 
                            'aac': GetE2AudioCodecMixOption('aac'), 
                           }
        printDBG(">>>>>>>>>>>>>>>>>>>>> getE2AudioOptions[%s]" % defAudioOptions)
        return defAudioOptions
        
    def getE2VideoOptions(self):
        defVideoOptions  = {'aspect':         GetE2VideoAspect(), 
                            'aspect_choices': GetE2VideoAspectChoices(), 
                            'policy':         GetE2VideoPolicy(), 
                            'policy_choices': GetE2VideoPolicyChoices(), 
                            'policy2':        GetE2VideoPolicy('2'), 
                            'policy2_choices':GetE2VideoPolicyChoices(),
                            'active':         None
                           }
        printDBG(">>>>>>>>>>>>>>>>>>>>> getE2VideoOptions[%s]" % defVideoOptions)
        return defVideoOptions
        
    def applyVideoOptions(self, newOptions):
        printDBG("applyVideoOptions newOptions[%s] ")
        options = ['aspect', 'policy', 'policy2']
        for opt in options:
            val = newOptions.get(opt, None)
            if None != val:
                self.videoOptSetters[opt](val)
        
    def selectVideoOptions(self):
        printDBG("selectVideoOptions")
        options = []
        currIdx = 0
        optionsTab = [{'title':_('Video policy'), 'name': 'policy'}, {'title':_('Video policy for 4:3'), 'name': 'policy2'}, {'title':_('Aspect'), 'name': 'aspect'}, {'title':_('Video mode'), 'name': 'videomode'}]
        for option in optionsTab:
            if len(self.defVideoOptions[option['name']+'_choices' ]) < 2: continue
            if None == self.defVideoOptions[option['name']]: continue
            if self.defVideoOptions['active'] == option['name']:
                currIdx = len(options)
            options.append(IPTVChoiceBoxItem(option['title'], "", option["name"]))
        
        if len(options):
            self.openChild(boundFunction(self.childClosed, self.selectVideoOptionsCallback), IPTVChoiceBoxWidget, {'width':500, 'current_idx':currIdx, 'title':_("Select video option"), 'options':options})
        
    def selectVideoOptionsCallback(self, ret=None):
        printDBG("selectVideoOptionsCallback ret[%r]" % [ret])
        if not isinstance(ret, IPTVChoiceBoxItem): return
        options = []
        currIdx = 0

        option = ret.privateData
        self.defVideoOptions['active'] = option
        
        choices = self.defVideoOptions['%s_choices' % option]
        currValue = self.currVideoOptions[option]
        if None == currValue: currValue = self.defVideoOptions[option]
        
        if option != 'videomode':
            for item in choices:
                if item == currValue:
                    currIdx = len(options)
                options.append(IPTVChoiceBoxItem(_(item), "", item))
            self.openChild(boundFunction(self.childClosed, self.selectVideoOptionCallback), IPTVChoiceBoxWidget, {'selection_changed':self.videoOptionSelectionChanged, 'width':500, 'current_idx':currIdx, 'title':_("Select %s") % ret.name, 'options':options})
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
                options.append( item )
            self.openChild(boundFunction(self.childClosed, self.selectVideoModeCallback), IPTVChoiceBoxWidget, {'width':500, 'current_idx':currIdx, 'title':_("Select %s") % ret.name, 'options':options})
        
    def selectVideoModeCallback(self, ret=None):
        printDBG("selectVideoModeCallback ret[%r]" % [ret])
        if isinstance(ret, IPTVChoiceBoxItem):
            currValue = self.currVideoOptions['videomode']
            if None == currValue: currValue = self.defVideoOptions['videomode']
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
            ret = IPTVChoiceBoxItem("", "", self.currVideoOptions[self.defVideoOptions['active']] )
        self.videoOptionSelectionChanged(ret)
        self.selectVideoOptions()
        
    def selectAudioTrack(self):
        printDBG("selectAudioTrack")
        tracksTab = self.playback['AudioTracks']
        if len(tracksTab):
            options = []
            printDBG(">>>>>>>>>>>> AudioTrack[%s]" % self.playback['AudioTrack'])
            currentId = self.playback['AudioTrack'].get('id', -1)
            currIdx = 0
            for trackIdx in range(len(tracksTab)):
                name = '[{0}] {1}'.format(tracksTab[trackIdx]['encode'], _(tracksTab[trackIdx]['name']))
                item = IPTVChoiceBoxItem(name, "", {'track_id':tracksTab[trackIdx]['id'], 'track_idx':trackIdx})
                if tracksTab[trackIdx]['id'] == currentId:
                    item.type = IPTVChoiceBoxItem.TYPE_ON
                    currIdx = trackIdx
                else:
                    item.type = IPTVChoiceBoxItem.TYPE_OFF
                options.append( item )
            self.openChild(boundFunction(self.childClosed, self.selectAudioTrackCallback), IPTVChoiceBoxWidget, {'width':500, 'height':240, 'current_idx':currIdx, 'title':_("Select audio track"), 'options':options})
        else:
            self.showMessage(_("Information about audio tracks not available."), MessageBox.TYPE_INFO, None)
            
    def selectAudioTrackCallback(self, ret):
        printDBG("selectAudioTrackCallback ret[%r]" % [ret])
        if isinstance(ret, IPTVChoiceBoxItem):
            ret = ret.privateData
            if 'track_id' in ret and ret['track_id'] != self.playback['AudioTrack'].get('id', -1):
                self.metaHandler.setAudioTrackIdx( ret.get('track_idx', -1) )
                self.extPlayerCmddDispatcher.setAudioTrack( ret['track_id'] )
            
    def selectSubtitle(self):
        printDBG("selectSubtitle")
        options = []
        
        currIdx = self.metaHandler.getSubtitleIdx()+1
        ####################################
        embeddedTrackId  = self.playback['SubtitleTrack'].get('id', -1)
        embeddedTracksTab = self.playback['SubtitleTracks']
        if embeddedTrackId > -1:
            currIdx = 0
        ####################################
        
        item = IPTVChoiceBoxItem(_('None'), "", {'other':'none'})
        if 0 == currIdx and -1 == embeddedTrackId:
            item.type = IPTVChoiceBoxItem.TYPE_ON
        else:
            item.type = IPTVChoiceBoxItem.TYPE_OFF
        options.append( item )
        
        #####################################
        for trackIdx in range(len(embeddedTracksTab)):
            name = '[{0}] {1}'.format(embeddedTracksTab[trackIdx]['encode'], _(embeddedTracksTab[trackIdx]['name']))
            item = IPTVChoiceBoxItem(name, "", {'track_id': embeddedTracksTab[trackIdx]['id'], 'track_idx':trackIdx})
            if embeddedTracksTab[trackIdx]['id'] == embeddedTrackId:
                item.type = IPTVChoiceBoxItem.TYPE_ON
            else:
                item.type = IPTVChoiceBoxItem.TYPE_OFF
            options.append( item )
        #####################################
        
        tracksTab = self.metaHandler.getSubtitlesTracks()
        for trackIdx in range(len(tracksTab)):
            name = '[{0}] {1}'.format(tracksTab[trackIdx]['lang'], tracksTab[trackIdx]['title'])
            item = IPTVChoiceBoxItem(name, "", {'track_idx':trackIdx})
            if (trackIdx + 1) == currIdx:
                item.type = IPTVChoiceBoxItem.TYPE_ON
            else:
                item.type = IPTVChoiceBoxItem.TYPE_OFF
            options.append( item )
        if self.subHandler['enabled'] and None != self.metaHandler.getSubtitleTrack():
            options.append( IPTVChoiceBoxItem(_('Synchronize'), "", {'other':'synchro'}) )
        if len(self.externalSubTracks):
            for item in self.externalSubTracks:
                title = '[{0}] {1} ({2})'.format(item.get('lang', ''), item['title'], _('Download suggested'))
                options.append( IPTVChoiceBoxItem(title, "", {'other':'download_suggested', 'track':item}) )
        options.append( IPTVChoiceBoxItem(_('Load'), "", {'other':'load'}) )
        options.append( IPTVChoiceBoxItem(_('Download'), "", {'other':'download'}) )
        self.openChild(boundFunction(self.childClosed, self.selectSubtitleCallback), IPTVChoiceBoxWidget, {'width':600, 'current_idx':currIdx, 'title':_("Select subtitles track"), 'options':options})
    
    def selectSubtitleCallback(self, ret):
        printDBG("selectSubtitleCallback ret[%r]" % [ret])
        if isinstance(ret, IPTVChoiceBoxItem):
            ret = ret.privateData
            if 'other' in ret:
                option = ret['other']
                if option == 'none':
                    # to speed up, should be set also as output from exteplayer3
                    self.playback['SubtitleTrack']= {'id':-1}
                    self.metaHandler.setSubtitleIdx(-1)
                    self.metaHandler.setEmbeddedSubtileTrackIdx(-1)
                    self.disableSubtitles()
                elif option == 'synchro':
                    self.showSubSynchroControl()
                elif option == 'load':
                    self.openSubtitlesFromFile()
                elif option == 'download':
                    self.downloadSub()
                elif option == 'download_suggested' and 'track' in ret:
                    self.downloadSub([ret['track']])
            elif 'track_id' in ret:
                self.metaHandler.setEmbeddedSubtileTrackIdx( ret['track_idx'] )
                self.metaHandler.setSubtitleIdx(-1)
                self.enableEmbeddedSubtitles(ret['track_id'])
            elif 'track_idx' in ret:
                self.metaHandler.setSubtitleIdx( ret['track_idx'] )
                # to speed up, should be set also as output from exteplayer3
                self.playback['SubtitleTrack'] = {'id':-1}
                self.metaHandler.setEmbeddedSubtileTrackIdx( -1 )
                self.extPlayerCmddDispatcher.setSubtitleTrack( -1 )
                self.subHandler['embedded_handler'].flushSubtitles()
                self.enableSubtitles()
    
    def openSubtitlesFromFile(self):
        printDBG("openSubtitlesFromFile")
        currDir = GetSubtitlesDir()
        
        fileSRC = self.fileSRC
        tmpMatch = 'file://'
        if fileSRC.startswith(tmpMatch): 
            fileSRC = fileSRC[len(tmpMatch):].replace('//', '/')
        if fileExists(fileSRC) and not fileSRC.endswith('/.iptv_buffering.flv'):
            try: currDir, tail = os_path.split(fileSRC)
            except Exception: printExc()
            
            
        fileMatch = re.compile("^.*?(:?\.%s)$" % '|\.'.join( IPTVSubtitlesHandler.getSupportedFormats() ),  re.IGNORECASE)
        self.openChild(boundFunction(self.childClosed, self.openSubtitlesFromFileCallback), IPTVFileSelectorWidget, currDir, _("Select subtitles file"), fileMatch)
        
    def openSubtitlesFromFileCallback(self, filePath=None):
        printDBG("openSubtitlesFromFileCallback filePath[%s]" % filePath)
        if None != filePath:
            self.subHandler['handler'].removeCacheFile(filePath)
            cmd = '%s "%s"' % (config.plugins.iptvplayer.uchardetpath.value, filePath) 
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
        if None != filePath:
            lang = CParsingHelper.getSearchGroups(filePath, "_([a-z]{2})_[0-9]+?_[0-9]+?_[0-9]+?(:?\.%s)$" % '|\.'.join( IPTVSubtitlesHandler.getSupportedFormats() ))[0]
            try: currDir, fileName = os_path.split(filePath)
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
                except Exception: printExc()
            if -1 == trackIdx:
                trackIdx = self.metaHandler.addSubtitleTrack( {"title":fileName, "id":"", "provider":"", "lang":lang, "delay_ms":0, "path":filePath} )
            self.metaHandler.setSubtitleIdx( trackIdx )
            self.enableSubtitles(encoding)

    def disableSubtitles(self):
        self.playback['SubtitleTrack'] = {'id': -1}
        self.extPlayerCmddDispatcher.setSubtitleTrack( -1 )
        self.subHandler['embedded_handler'].flushSubtitles()
        self.hideSubtitles()
        self.subHandler['enabled'] = False
        self.updateSubSynchroControl()
        
    def enableEmbeddedSubtitles(self, id):
        printDBG("enableEmbeddedSubtitles")
        if self.playback['SubtitleTrack'].get('id', -1) != id:
            self.subHandler['embedded_handler'].flushSubtitles()
            self.extPlayerCmddDispatcher.setSubtitleTrack( id )
        self.subHandler['handler_type'] = 'embedded_handler'
        self.subHandler['marker']  = None
        self.subHandler['enabled'] = True
        self.updateSubSynchroControl()
        if self.setMoviePlayerConfig:
            self.setMoviePlayerConfig = False
            self.runConfigMoviePlayerCallback(True)
        
    def enableSubtitles(self, encoding='utf-8'):
        printDBG("enableSubtitles")
        if self.isClosing: return
        track = self.metaHandler.getSubtitleTrack()
        if None == track:
            if not self.metaHandler.hasSubtitlesTracks() and self.subConfig['auto_enable']:
                fileSRC = self.fileSRC
                tmpMatch = 'file://'
                if fileSRC.startswith(tmpMatch): 
                    fileSRC = fileSRC[len(tmpMatch):].replace('//', '/')
                if fileExists(fileSRC) and not fileSRC.endswith('/.iptv_buffering.flv'):
                    subFile = ''
                    try:
                        name, ext = os_path.splitext(fileSRC)
                        for ext in IPTVSubtitlesHandler.getSupportedFormats():
                            if fileExists(name + '.' + ext):
                                subFile = name + '.' + ext
                                break
                    except Exception:
                        printExc()
                    if '' != subFile:
                        self.openSubtitlesFromFileCallback(subFile)
            return
        
        printDBG("enableSubtitles track[%s]" % track)
        path = track['path']
        sts = self.subHandler['handler'].loadSubtitles(path, encoding)
        if not sts:
            # we will remove this subtitles track as it is can not be used
            self.metaHandler.removeSubtitleTrack(self.metaHandler.getSubtitleIdx())
            msg = _("An error occurred while loading a subtitle from [%s].") % path
            self.showMessage(msg, MessageBox.TYPE_ERROR)
            return
        self.subHandler['handler_type'] = 'handler'
        self.subHandler['marker']  = None
        self.subHandler['enabled'] = True
        self.updateSubSynchroControl()
        if self.setMoviePlayerConfig:
            self.setMoviePlayerConfig = False
            self.runConfigMoviePlayerCallback(True)
        
    def updatSubtitlesTime(self):
        if -1 != self.subHandler['last_time'] and -1 != self.subHandler['latach_time']:
            timeMS = self.subHandler['last_time'] + int((time.time() - self.subHandler['latach_time']) * 1000)
            self.subHandler['current_sub_time_ms'] = timeMS
            self.updateSubtitles(timeMS)
            
    def restartSubTimer(self):
        if 'Play' != self.playback['Status']: return
        if not self.subHandler['enabled']: return
        self.subHandler['timer'].stop()
        self.subHandler['timer'].start(100)
        
    def latchSubtitlesTime(self, timeMS):
        self.subHandler['latach_time'] = time.time()
        self.subHandler['last_time']   = timeMS
        self.restartSubTimer()
        self.updateSubtitles(timeMS)
    
    def updateSubtitles(self, timeMS, force = False):
        if self.isClosing: return
        if not self.subHandler['enabled']: return
        if None == self.metaHandler.getSubtitleTrack() and 'handler' == self.subHandler['handler_type']: return
        
        # marker is used for optimization 
        # we remember some kind of fingerprint for last subtitles 
        # subtitles handler first check this fingerprint 
        # if the previous one is the same as current and it will return None instead 
        # of subtitles text
        prevMarker = self.subHandler['marker']
        if force: prevMarker = None
        
        handler_type = self.subHandler['handler_type']
        if handler_type == 'handler':
            delay_ms = self.metaHandler.getSubtitleTrackDelay()
        else:
            delay_ms = 0
        marker, text = self.subHandler[handler_type].getSubtitles(timeMS + delay_ms, prevMarker)
        if None != text:
            self.subHandler['marker'] = marker
            #printDBG("===============================================================")
            #printDBG(text)
            #printDBG("===============================================================")
            if "" == text:
                self.hideSubtitles()
            else:
                self.setSubtitlesText(text)
                
    def hideSubtitles(self):
        for idx in range(self.subLinesNum):
            self['subLabel%d'%(idx+1)].hide()
    
    def setSubtitlesText(self, text, stripLine = True, breakToLongLine=True):
        back = True
        desktopW = getDesktop(0).size().width()
        desktopH = getDesktop(0).size().height()
        
        dW = desktopW - 20
        dH = self.subConfig['box_height']
        
        if stripLine: text = text.strip()
        
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
                lineHeight = self.subConfig['line_height'] * text.count('\n')
                text = [text]
            else:
                text = text.split('\n')
                if not subOnTopHack: text.reverse()
                lineHeight = self.subConfig['line_height']
            y = self.subConfig['pos'] 
            if not subOnTopHack: y += self.subHandler['pos_y_offset']
            for lnIdx in range(self.subLinesNum):
                subLabel = 'subLabel%d' % (lnIdx+1)
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
                        splitWord = len(lnText) / 2 + 1
                        lnText = '%s\n%s' % (' '.join(lnText[:splitWord]), ' '.join(lnText[splitWord:]))
                        self.setSubtitlesText(lnText, False, False)
                        return
                    
                    lW = textSize[0] + self.subConfig['font_size'] / 2
                    lH = lineHeight #textSize[1] + self.subConfig['font_size'] / 2
                    self[subLabel].instance.resize(eSize(lW, lH))
                    if not subOnTopHack: self[subLabel].instance.move( ePoint((desktopW-lW) / 2, desktopH - y - lH) )
                    else: self[subLabel].instance.move( ePoint((desktopW-lW) / 2, y) )
                    y += lH + self.subConfig['line_spacing']
                    self[subLabel].show()
                except Exception:
                    printExc()
        
    def updateInfo(self):
        self.extPlayerCmddDispatcher.doUpdateInfo()
        self.updateBufferFill()
        
    def updateBufferFill(self):
        if None != self.downloader:
            if self.downloader.hasDurationInfo() and self.downloader.getTotalFileDuration() > 0:
                totalDuration = self.downloader.getTotalFileDuration()
                downloadDuration = self.downloader.getDownloadedFileDuration()
                if 0 < totalDuration and 0 < downloadDuration:
                    self.playback['BufferFill'] = (downloadDuration * 100000) / totalDuration
                    self['bufferingBar'].value = self.playback['BufferFill']
                    if self.playback['Length'] < totalDuration:
                        self.setPlaybackLength(totalDuration)
                        self.clipLength = totalDuration
                return
            
            remoteFileSize = self.downloader.getRemoteFileSize() - self.totalDataSizeCorrection
            if 0 < remoteFileSize:
                localFileSize = self.downloader.getLocalFileSize(True) - self.availableDataSizeCorrection
                if 0 < localFileSize:
                    self.playback['BufferFill'] = (localFileSize * 100000) / remoteFileSize
                    self['bufferingBar'].value = self.playback['BufferFill']
        
    def showMessage(self, message, type, callback=None):
        printDBG("IPTVExtMoviePlayer.showMessage")
        if self.isClosing and type != None: return
        messageItem = {'msg':message, 'type':type, 'callback':callback}
        self.messageQueue.append(messageItem)
        self.processMessageQueue()
        
    def processMessageQueue(self):
        if self.underMessage or 0 == len(self.messageQueue): return
        self.underMessage = True
        while len(self.messageQueue):
            messageItem = self.messageQueue.pop(0)
            message, type, callback = messageItem['msg'], messageItem['type'], messageItem['callback']
            if None == type and None != callback: 
                callback()
            else:
                if self.isClosing and None != callback: continue # skip message with callback
                else: self.session.openWithCallback(boundFunction(self.messageClosedCallback, callback), MessageBox, text=message, type=type)
            return
        
    def messageClosedCallback(self, callback, arg=None):
        self.underMessage = False
        if None != callback: callback()
        else: self.processMessageQueue()
            
    def waitEOSAbortedFixTimeoutCallback(self):
        if self.waitEOSAbortedFix['EOSaborted_received']:
            self.extPlayerCmddDispatcher.stop()
            
    def setPlaybackLength(self, newLength):
        self.playback['Length'] = newLength
        self['progressBar'].range = (0, newLength)
        self['bufferingCBar'].range = (0, newLength)
        self['lengthTimeLabel'].setText( str(timedelta(seconds=newLength)) )
        
    def playbackUpdateInfo(self, stsObj):
        # workaround for missing playback length info for under muxing MKV
        if self.playback['Length'] > 0 and self.downloader != None and self.downloader.getName() == 'ffmpeg':
            stsObj['Length'] = self.playback['Length']
        
        for key, val in stsObj.iteritems():
            if 'Length' == key:
                if 0 > val:
                    printDBG('IPTVExtMoviePlayer.playbackUpdateInfo Length[%d] - live stream?' % val )
                    val = 0
                    self.playback['IsLive'] = True
                else:
                    self.playback['IsLive'] = False
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
                            self.extPlayerCmddDispatcher.doGoToSeek(str(self.lastPosition-5))
                            self.lastPosition = 0
                    tmpLength = self.playback['BufferCTime']
                    if self.playback['CurrentTime'] > tmpLength:
                        tmpLength = self.playback['CurrentTime']
                    if val > tmpLength: 
                        tmpLength = val
                        self.clipLength = val
                    if self.playback['Length'] < tmpLength:
                        if None == self.downloader or not self.downloader.hasDurationInfo():
                            self.setPlaybackLength(tmpLength)
                    self.playback['LengthFromPlayerReceived'] = True
            elif 'CurrentTime' == key:
                if self.playback['Length'] < val and val > self.playback['BufferCTime']:
                    self.setPlaybackLength(val)
                self['progressBar'].value = val
                prevCTime = self.playback['CurrentTime'] 
                self.playback['CurrentTime'] = stsObj['CurrentTime']
                if 0 < self.playback['CurrentTime']: 
                    self.playback['StartGoToSeekTime'] = self.playback['CurrentTime']
                    diff = self.playback['CurrentTime'] - prevCTime
                    if diff > 0 and diff < 3: # CurrentTime in seconds
                        self.playback['ConfirmedCTime'] = self.playback['CurrentTime']
                self['currTimeLabel'].setText( str(timedelta(seconds=self.playback['CurrentTime'])) )
                self['remainedLabel'].setText( '-' + str(timedelta(seconds=self.playback['Length']-self.playback['CurrentTime'])) )
                self['pleaseWait'].hide()
            elif 'BufferCTime' == key:
                if self.playback['Length'] < val:
                    self.setPlaybackLength(val)
                self.playback['BufferCTime'] = val
                self['bufferingCBar'].value = val
            elif 'Status' == key:
                curSts = self.playback['Status']
                if self.playback['Status'] != val[0]:
                    if 'Play' == val[0]:
                        self.showPlaybackInfoBar()
                    elif val[0] in ['Pause', 'FastForward', 'SlowMotion']:
                        self.showPlaybackInfoBar(blocked=True)
                    self.playback['Status'] = val[0]
                    self['statusIcon'].setPixmap( self.playback['statusIcons'].get(val[0], None) )
            elif 'IsLoop' == key:
                if self.playback['IsLoop'] != val:
                    self.playback['IsLoop'] = val
                    icon = 'Off'
                    if val: icon = 'On'
                    self['loopIcon'].setPixmap( self.playback['loopIcons'].get(icon, None) )
                    self.showPlaybackInfoBar()
                
            elif 'VideoTrack' == key:
                self.playback[key] = val
                codec = val['encode'].split('/')[-1]
                text = "%s %sx%s" % (codec, val['width'], val['height'])
                if val['progressive']: text += 'p'
                elif False == val['progressive']: text += 'i'
                fps = val['frame_rate']
                if fps == floor(fps): fps = int(fps)
                text += ', %sfps' % fps
                text += ', %s' % val['aspect_ratio'].replace('_', ':')
                self['videoInfo'].setText( text )
            else:
                self.playback[key] = val
                printDBG(">>> playback[%s] = %s" % (key, val))
                
    def doGoToSeek(self):
        self.playback['GoToSeekTimer'].stop()
        if self.playback['GoToSeeking']:
            self.showPlaybackInfoBar()
            self.playback['StartGoToSeekTime'] = self.playback['GoToSeekTime']
            self.extPlayerCmddDispatcher.doGoToSeek(str(self.playback['GoToSeekTime']))
            self.playback['GoToSeeking'] = False
            self['goToSeekPointer'].hide()
            self["goToSeekLabel"].hide()

    def doGoToSeekPointerMove(self, seek):
        printDBG('IPTVExtMoviePlayer.doGoToSeekPointerMove seek[%r], LengthFromPlayerReceived[%r], GoToSeeking[%r]' % (seek, self.playback['LengthFromPlayerReceived'], self.playback['GoToSeeking']))
        self.playback['GoToSeekTimer'].stop()
        if not self.playback['LengthFromPlayerReceived']: return
        if not self.playback['GoToSeeking']:
            self.playback['GoToSeeking']  = True
            self.playback['GoToSeekTime'] = self.playback['StartGoToSeekTime']
            self.showPlaybackInfoBar([], True)
            self['goToSeekPointer'].show()
            self["goToSeekLabel"].show()
        
        # update data
        if self.playback['BufferFill'] > 0:
            max = self.playback['Length'] * self.playback['BufferFill'] / 100000
            if max > self.playback['Length']:
                max = self.playback['Length']
            if max < self.playback['BufferCTime']:
                max = self.playback['BufferCTime']
        else:
            max = self.playback['Length']
        
        pos = self.playback['GoToSeekTime'] + seek
        if pos > max: pos = max
        if pos < 0: pos = 0
        
        self.playback['GoToSeekTime'] = pos
        self["goToSeekLabel"].setText( str(timedelta(seconds=self.playback['GoToSeekTime'])) )
        
        # update position
        # convert time to width
        relativeX = self["progressBar"].instance.size().width() * self.playback['GoToSeekTime'] / self.playback['Length']
        x = self['progressBar'].position[0] - self["goToSeekPointer"].getWidth()/2 + relativeX

        self['goToSeekPointer'].setPosition(x, self['goToSeekPointer'].position[1])
        self["goToSeekLabel"].setPosition(x, self['goToSeekLabel'].position[1])
        
        # trigger delayed seek
        self.playback['GoToSeekTimer'].start(1000)
        
    def saveLastPlaybackTime(self):
        lastPosition = self.playback.get('ConfirmedCTime', 0)
        if config.plugins.iptvplayer.remember_last_position.value and lastPosition > 0 and self.playback['Length'] > (config.plugins.iptvplayer.remember_last_position_time.value * 60):
                self.metaHandler.setLastPosition( lastPosition )

    def loadLastPlaybackTime(self):
        if config.plugins.iptvplayer.remember_last_position.value and self.lastPosition < 1:
            self.lastPosition = self.metaHandler.getLastPosition()

    # handling of RCU keys
    def key_stop(self, requestedByUser="key_stop"):
        self['pleaseWait'].setText(_("Closing. Please wait..."))
        self['pleaseWait'].show()
        self.closeRequestedByUser = requestedByUser
        if self.console != None:
            if self.extPlayerCmddDispatcher.stop():
                self.saveLastPlaybackTime()
        else:
            self.isClosing = True
    
    def key_play(self):         self.extPlayerCmddDispatcher.play()
    def key_pause(self):        self.extPlayerCmddDispatcher.pause()  
    def key_exit(self):         self.doExit()
    def key_info(self):         self.doInfo()
    def key_seek1(self):        self.doSeek(config.seek.selfdefined_13.value * -1)
    def key_seek3(self):        self.doSeek(config.seek.selfdefined_13.value) 
    def key_seek4(self):        self.doSeek(config.seek.selfdefined_46.value * -1)
    def key_seek6(self):        self.doSeek(config.seek.selfdefined_46.value)
    def key_seek7(self):        self.doSeek(config.seek.selfdefined_79.value * -1)
    def key_seek9(self):        self.doSeek(config.seek.selfdefined_79.value)  
    def key_seekFwd(self):      self.extPlayerCmddDispatcher.seekFwd()   
    def key_seekBack(self):     self.extPlayerCmddDispatcher.seekBack()   
    def key_left_press(self):   self.goToSeekKey(-1, 'press')
    def key_left_repeat(self):  self.goToSeekKey(-1, 'repeat')
    def key_rigth_press(self):  self.goToSeekKey(1, 'press')
    def key_rigth_repeat(self): self.goToSeekKey(1, 'repeat')
    def key_up_press(self):     self.goSubKey(-1, 'press')
    def key_up_repeat(self):    self.goSubKey(-1, 'repeat') 
    def key_down_press(self):   self.goSubKey(1, 'press')
    def key_down_repeat(self):  self.goSubKey(1, 'repeat')
    
    def doSeek(self, val):
        if None != self.downloader and self.downloader.hasDurationInfo() \
           and self.playback['CurrentTime'] >= 0 and self.playback['Length'] > 10:
            val += self.playback['CurrentTime']
            if val < 0: val = 0
            elif val > self.playback['Length'] - 10:
                val = self.playback['Length'] - 10
            self.extPlayerCmddDispatcher.doGoToSeek(str(val))
            return
        self.extPlayerCmddDispatcher.doSeek(val)
    
    def key_ok(self):
        if 'Pause' == self.playback['Status']: self.extPlayerCmddDispatcher.play()
        else: self.extPlayerCmddDispatcher.pause()
        
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
        
    def goSubKey(self, direction, state='press'):
        if not self.subHandler['enabled'] or None == self.metaHandler.getSubtitleTrack():
            self.hideSubSynchroControl()
            return
        if self.subHandler['synchro']['visible']:
            currentDelay = self.metaHandler.getSubtitleTrackDelay()
            currentDelay += direction * 500 # in MS
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
        if not self.subHandler['synchro']['visible'] or not self.subHandler['enabled'] or None == self.metaHandler.getSubtitleTrack():
            self.hideSubSynchroControl()
            return
        currentDelay = self.metaHandler.getSubtitleTrackDelay()
        if currentDelay > 0:
            textDelay = '+'
        else: textDelay = '' 
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
        if self.goToSeekStep > (self.playback['Length'] / 10):
            self.goToSeekStep = self.playback['Length'] / 10
        if 0 >= self.goToSeekStep:
            self.goToSeekStep = 1
        
        self.doGoToSeekPointerMove(self.goToSeekStep * direction)
        
    def doExit(self, fromInfo=False):
        if not fromInfo and self.subHandler['synchro']['visible']:
            self.hideSubSynchroControl()
        elif self.playbackInfoBar['visible']:
            self.playbackInfoBar['blocked'] = False
            self.hidePlaybackInfoBar()
        else:
            self.key_stop("key_exit")
            
    def doInfo(self):
        if not self.playbackInfoBar['visible']:
            if self.isStarted and not self.isClosing:
                self.playbackInfoBar['blocked'] = True
                self.showPlaybackInfoBar()
        else: self.doExit(True)
    
    def eplayer3Finished(self, code):
        printDBG("IPTVExtMoviePlayer.eplayer3Finished code[%r]" % code)
        if self.isClosing: return
        
        msg = _("It seems that the video player \"%s\" does not work properly.\n\nSTS: %s\nERROR CODE: %r")
        if None == self.playerBinaryInfo['version']:
            msg = msg % (self.playerName, self.playerBinaryInfo['data'], code)
            self.showMessage(msg, MessageBox.TYPE_ERROR, self.onLeavePlayer)
        elif 'gstplayer' == self.player and 246 == code:
            msg = msg % (self.playerName, _("ERROR: pipeline could not be constructed: no element \"playbin2\" \nPlease check if gstreamer plugins are available in your system."), code)
            self.showMessage(msg, MessageBox.TYPE_ERROR, self.onLeavePlayer)
        else: self.onLeavePlayer()
        
    def waitCloseTimeoutCallback(self):
        printDBG("IPTVExtMoviePlayer.waitCloseTimeoutCallback")
        if None != self.console:
            printDBG("Force close movie player by sending CtrlC")
            self.console.sendCtrlC()
        self.onLeavePlayer()
        
    def eplayer3DataAvailable2(self, data):
        if None == data or self.isClosing:
            return
            
        if 'got buffer empty from driver!' in data:
            self.extPlayerCmddDispatcher.stop()

        # work around to catch EOF event after seeking, pause .etc
        if 'wait EOS aborted!!' in data:
            self.waitEOSAbortedFix['EOSaborted_received'] = True
            self.waitEOSAbortedFix['timer'].start(2000, True) # singleshot

        if self.waitEOSAbortedFix['EOSaborted_received'] and 'poll' in data:
            self.waitEOSAbortedFix['timer'].stop()
            self.waitEOSAbortedFix['timer'].start(2000, True)

    def eplayer3DataAvailable(self, data):
        
        def _mapTrack(obj, video=False):
            printDBG('>>>> _mapTrack [%s]' % obj)
            params = {}
            params['id']         = int(obj['id'])
            params['encode']     = str(obj['e'][2:])
            params['name']       = str(obj['n'])
            if video:
                params['frame_rate'] = float(obj['f'])/1000.0
                params['width']      = int(obj['w'])
                params['height']     = int(obj['h'])
                params['progressive']= None
                try:
                    if int(obj['p']): params['progressive'] = True
                    else: params['progressive'] = False
                        
                except Exception: 
                    printExc()
                try:
                    DAR = float(obj.get('an', 1) * params['width']) / float(obj.get('ad', 1) * params['height'])
                    aTab = []
                    for item in [(16,9,'16_9'), (4,3,'4_3'), (16,10,'16_10'), (3,2,'3_2'), (5,4,'5_4'), (1.85,1,'1.85'), (2.35,1,'2.35')]:
                        diff = fabs(float(item[0])/item[1] - DAR)
                        aTab.append((diff, item[2]))
                    aTab.sort(key=lambda item: item[0])
                    params['aspect_ratio'] = aTab[0][1]
                except Exception: 
                    params['aspect_ratio'] = 'unknown'
                    printExc()
                    
            return params
            
        def _mapSubAtom(obj):
            printDBG('>>>> _mapTrack [%s]' % obj)
            params = {}
            params['id']         = int(obj['id'])
            params['start']      = int(obj['s'])
            params['end']        = int(obj['e'])
            params['text']       = str(obj['t'])
            return params
        
        if None == data or self.isClosing:
            return
        if None == self.playerBinaryInfo['version']: self.playerBinaryInfo['data'] += data
        data = self.responseData + data
        if '\n' != data[-1]: truncated = True
        else:                truncated = False
        data = data.split('\n')
        if truncated: 
            self.responseData = data[-1]
            del data[-1]
        for item in data:
            #printDBG(item)
            if item.startswith('{'): 
                try:
                    obj = json.loads(item.strip())
                    #printDBG("Status object [%r]" % obj)
                    key = obj.keys()[0]
                    obj = obj[key]
                except Exception: 
                    printExc(item)
                    continue
                    
                if "T" == key: #ADD_TRIGGERS
                    self.latchSubtitlesTime(obj['c'])
                elif "PLAYBACK_PLAY" == key:
                    self.onStartPlayer()
                    #if 'gstplayer' != self.player: 
                    self.updateInfoTimer.start(1000)
                    if 0 == obj['sts']:
                        self.playbackUpdateInfo({'Status': ['Play', '1']})
                elif "PLAYBACK_STOP" == key:
                    self.onLeavePlayer()
                elif "PLAYBACK_LENGTH" == key and 0 == obj['sts']:
                    self.playbackUpdateInfo({'Length':int(obj['length'])})
                elif "PLAYBACK_CURRENT_TIME" == key and 0 == obj['sts']:
                    self.playbackUpdateInfo({'CurrentTime':int(obj['sec'])})
                elif "J" == key and obj['ms'] > 0:
                    updateInfoParams = {'CurrentTime':int(obj['ms']/1000)}
                    if 'lms' in obj: updateInfoParams['BufferCTime'] = int(obj['lms']/1000)
                    self.playbackUpdateInfo(updateInfoParams)
                    self.latchSubtitlesTime(obj['ms'])
                # CURRENT VIDEO TRACK
                elif "v_c" == key:
                    tmpTrack = _mapTrack(obj, True)
                    if tmpTrack.get('id', -1) > -1: self.playbackUpdateInfo({'VideoTrack':tmpTrack})
                elif "a_c" == key:
                    tmpTrack = _mapTrack(obj)
                    if tmpTrack.get('id', -1) > -1: self.playbackUpdateInfo({'AudioTrack':tmpTrack})
                elif "a_l" == key:
                    tracks = []
                    for item in obj:
                        tracks.append( _mapTrack(item) )
                    self.playbackUpdateInfo({'AudioTracks':tracks})
                elif "s_c" == key:
                    tmpTrack = _mapTrack(obj)
                    if tmpTrack.get('id', -1) > -1: 
                        self.playbackUpdateInfo({'SubtitleTrack':tmpTrack})
                        self.enableEmbeddedSubtitles(tmpTrack['id'])
                elif "s_l" == key:
                    tracks = []
                    for item in obj:
                        tracks.append( _mapTrack(item) )
                    self.playbackUpdateInfo({'SubtitleTracks':tracks})
                elif "s_a" == key:
                    if self.subHandler['enabled']:
                        subAtom = _mapSubAtom(obj)
                        self.subHandler['embedded_handler'].addSubAtom( subAtom )
                elif "s_f" == key:
                    self.subHandler['embedded_handler'].flushSubtitles()
                elif "N" == key:
                    self.playbackUpdateInfo({'IsLoop': obj['isLoop']})
                elif "PLAYBACK_INFO" == key:
                    if obj['isPaused']:
                        self.playbackUpdateInfo({'Status': ['Pause', '0']})
                        #if 'gstplayer' == self.player: self.updateInfoTimer.stop()
                        self.subHandler['timer'].stop()
                    else:
                        #if 'gstplayer' == self.player: self.updateInfoTimer.start(1000)
                        if obj['isForwarding']:
                            self.playbackUpdateInfo({'Status': ['FastForward', str(obj['Speed'])]})
                        elif 0 < obj['SlowMotion']:
                            self.playbackUpdateInfo({'Status': ['SlowMotion', '1/%d' % obj['SlowMotion']]})
                        elif obj['isPlaying']: # and 1 == obj['Speed']:
                            self.playbackUpdateInfo({'Status': ['Play', '1']})
                        else:
                            printDBG('eplayer3DataAvailable PLAYBACK_INFO not handled')
                elif "GSTPLAYER_EXTENDED" == key: self.playerBinaryInfo['version'] = obj['version']
                elif "EPLAYER3_EXTENDED" == key: self.playerBinaryInfo['version'] = obj['version']
                elif "GST_ERROR" == key or "FF_ERROR" == key: self.showMessage('%s\ncode:%s' % (obj['msg'].encode('utf-8'), obj['code']), MessageBox.TYPE_ERROR, None)
                elif "GST_MISSING_PLUGIN" == key: self.showMessage(obj['msg'].encode('utf-8'), MessageBox.TYPE_INFO, None)

                        
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
                
    def onDownloadFinished(self, sts):
        printDBG("IPTVExtMoviePlayer.onDownloadFinished sts[%s]" % sts)
        if None != self.extPlayerCmddDispatcher:
            if 'gstplayer' == self.player:
                self.extPlayerCmddDispatcher.setDownloadFileTimeout(0)
            else:
                self.extPlayerCmddDispatcher.setProgressiveDownload(0)

    def __onClose(self):
        printDBG(">>>>>>>>>>>>>>>>>>>>>> __onClose")
        self.isClosing = True
        if None != self.workconsole:
            self.workconsole.kill()
        self.workconsole = None
        
        if None != self.refreshCmdConsole:
            self.refreshCmdConsole.kill()
        self.refreshCmdConsole = None
        
        if None != self.extLinkProv['console']:
            self.extLinkProv['close_conn'] = None
            self.extLinkProv['data_conn']  = None
            self.extLinkProv['console'].sendCtrlC()
            self.extLinkProv['console'] = None
        
        if None != self.iframeParams['console']:
            self.iframeParams['console'].kill()
        self.iframeParams['console'] = None
        
        if None != self.console:
            self.console_appClosed_conn   = None
            self.console_stderrAvail_conn = None
            self.console_stdoutAvail_conn = None
            self.console.sendCtrlC()
            self.console = None
        if None != self.downloader:
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
        for key in self.playback.iterkeys():
            self.playback[key] = None
        self.onClose.remove(self.__onClose)
        self.messageQueue = []
        
        # RESTORE DEFAULT VIDEO OPTION
        printDBG(">>>>>>>>>>>>>>>>>>>>> __onClose[%s]" % self.defVideoOptions)
        printDBG(">>>>>>>>>>>>>>>>>>>>> __onClose[%s]" % self.currVideoOptions)
        videoOptionChange = False
        for opt in ['aspect', 'policy', 'policy2']:
            val  = self.defVideoOptions[opt] 
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
            if playerDefOptions[opt] != None and playerDefOptions[opt] != self.defAudioOptions[opt]:
                SetE2AudioCodecMixOption(opt, self.defAudioOptions[opt])
        self.metaHandler.save()
        
        # SAVE SUBTITLES POSITION IF CHANGED
        if 'orig_pos' in self.subConfig and self.subConfig['orig_pos'] != self.subConfig['pos']:
            self.configObj.setSubtitleFontSettings(self.subConfig)
        
        try: self.extPlayerCmddDispatcher.owner = None
        except Exception: printExc()
        
    def onStartPlayer(self):
        self.isStarted = True
        self.showPlaybackInfoBar()

    def onLeavePlayer(self):
        printDBG("IPTVExtMoviePlayer.onLeavePlayer")
        if self.waitCloseFix['waiting'] and None != self.waitCloseFix['timer']: self.waitCloseFix['timer'].stop()
        self.updateInfoTimer.stop()
        self.subHandler['timer'].stop()
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
                self.iframeParams['console'] = iptv_system( 'showiframe "{0}"'.format(blankIframeFilePath), boundFunction(self.iptvDoClose, sts, currentTime))
                return
        self.iptvDoClose(sts, currentTime)
    
    def iptvDoClose(self, sts, currentTime, code=None, data=None):
        if None != self.extLinkProv['console']:
            self.extLinkProv['console'].sendCtrlC()
    
        if None != self.refreshCmdConsole:
            self.refreshCmdConsole.kill()
        self.refreshCmdConsole = None
        
        if None != self.iframeParams['console']:
            self.iframeParams['console'].kill()
        self.iframeParams['console'] = None
        
        self.close(sts, currentTime, self.clipLength)
        
    def openChild(self, *args, **kwargs):
        self.childWindowsCount += 1
        self.session.openWithCallback(*args, **kwargs)
    
    def childClosed(self, callback, *args):
        self.childWindowsCount -= 1
        callback(*args)
        
        if None != self.delayedClosure and self.childWindowsCount < 1:
            self.delayedClosure()
            
    def downloadSub(self, simpleTracksTab=[]):
        if self.downloader != None:
            url = strwithmeta(self.downloader.getUrl())
        else:
            url = strwithmeta(self.fileSRC)
        if 0 == len(simpleTracksTab):
            self.openChild(boundFunction(self.childClosed, self.downloadSubCallback), IPTVSubDownloaderWidget, {'duration_sec':self.playback['Length'], 'movie_url':url, 'movie_title':self.title})
        else:
            self.openChild(boundFunction(self.childClosed, self.downloadSubCallback), IPTVSubSimpleDownloaderWidget, {'movie_url':url, 'movie_title':self.title, 'sub_list':simpleTracksTab})
        
    def downloadSubCallback(self, ret = None):
        if None != ret:
            self.subHandler['handler'].removeCacheFile(ret.get('path', ''))
            idx = self.metaHandler.addSubtitleTrack(ret)
            self.metaHandler.setSubtitleIdx( idx )
            self.enableSubtitles()
        
    def onStart(self):
        self.onShow.remove(self.onStart)
        #self.onLayoutFinish.remove(self.onStart)
        
        if '' != self.refreshCmd and (self.downloader != None or not self.fileSRC.startswith('ext://')):
            self.refreshCmdConsole = iptv_system( self.refreshCmd )
            
        if self.iframeParams['show_iframe'] and IsExecutable('showiframe')\
           and fileExists(self.iframeParams['iframe_file_start']):
            if self.iframeParams['iframe_continue']:
                self.iframeParams['console'] = iptv_system( 'showiframe "{0}"'.format(self.iframeParams['iframe_file_start']))
            else:
                self.iframeParams['console'] = iptv_system( 'showiframe "{0}"'.format(self.iframeParams['iframe_file_start']), self.iptvGetUrlStart)
                return
        self.iptvGetUrlStart()
        
    def iptvGetUrlStart(self, code=None, data=None):
        if self.isClosing: 
            self.onLeavePlayer()
            return
        
        if self.downloader == None and self.refreshCmd != '' and self.fileSRC.startswith('ext://'):
            self.extLinkProv['console']    = eConsoleAppContainer()
            self.extLinkProv['close_conn'] = eConnectCallback(self.extLinkProv['console'].appClosed, self._updateGetUrlFinished)
            self.extLinkProv['data_conn']  = eConnectCallback(self.extLinkProv['console'].stderrAvail, self._updateGetUrlDataAvail)
            self.extLinkProv['console'].execute( self.refreshCmd )
        else:
            self.iptvDoStart()
            
    def _updateGetUrlFinished(self, code=0):
        printDBG('_updateGetUrlFinished update code[%d]--- ' % (code))
        if not self.extLinkProv['started']:
            self.onLeavePlayer()
        
    def _updateGetUrlDataAvail(self, data):
        if self.isClosing: return
        if None != data and 0 < len(data):
            self.extLinkProv['data'] += data
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
        
        if defVideoMode != None and defVideoMode in videoModes:
            curVideoMode = GetE2VideoMode()
            videoMode    = self.metaHandler.getVideoOption('videomode')
            if videoMode != curVideoMode and videoMode in videoModes:
                SetE2VideoMode(videoMode)
            self.currVideoOptions['videomode'] = GetE2VideoMode()
        
        if None != self.downloader:
            self.downloader.subscribeFor_Finish(self.onDownloadFinished)
        
        if 'gstplayer' == self.player:
            if self.fileSRC.startswith('merge://'):
                msg = _("Link is not supported by the gstplayer. Please use the extelayer3 if available.")
                self.showMessage(msg, MessageBox.TYPE_ERROR)
            
            gstplayerPath = config.plugins.iptvplayer.gstplayerpath.value
            #'export GST_DEBUG="*:6" &&' + 
            cmd = gstplayerPath  + ' "%s"' % self.fileSRC
            
            # active audio track 
            audioTrackIdx = self.metaHandler.getAudioTrackIdx()
            cmd += ' %d ' % audioTrackIdx
            
            # file download timeout
            if None != self.downloader and self.downloader.isDownloading():
                timeout = self.gstAdditionalParams['file-download-timeout']
            else: timeout = 0
            cmd += ' {0} '.format( timeout )
            
            # file download live
            if self.gstAdditionalParams['file-download-live']:
                cmd += ' {0} '.format(1)
            else: cmd += ' {0} '.format(0)
            
            if "://" in self.fileSRC: 
                cmd += ' "%s" "%s"  "%s"  "%s" ' % (self.gstAdditionalParams['download-buffer-path'], self.gstAdditionalParams['ring-buffer-max-size'], self.gstAdditionalParams['buffer-duration'], self.gstAdditionalParams['buffer-size'])
                tmp = strwithmeta(self.fileSRC)
                url,httpParams = DMHelper.getDownloaderParamFromUrlWithMeta(tmp, True)
                for key in httpParams: cmd += (' "%s=%s" ' % (key, httpParams[key]) )
                if 'http_proxy' in tmp.meta:
                    tmp = tmp.meta['http_proxy']
                    if '://' in tmp:
                        if '@' in tmp:
                            tmp = re.search('([^:]+?://)([^:]+?):([^@]+?)@(.+?)$', tmp)
                            if tmp: cmd += (' "proxy=%s" "proxy-id=%s" "proxy-pw=%s" ' % (tmp.group(1)+tmp.group(4), tmp.group(2), tmp.group(3)) )
                        else: cmd += (' "proxy=%s" ' % tmp)
            cmd += " > /dev/null"
        else:
            exteplayer3path = config.plugins.iptvplayer.exteplayer3path.value
            cmd = exteplayer3path
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
            if "://" in self.fileSRC:
                ramBufferSizeMB = config.plugins.iptvplayer.rambuffer_sizemb_network_proto.value
                url,httpParams = DMHelper.getDownloaderParamFromUrlWithMeta(tmpUri, True)
                #cmd += ' ""' # cookies for now will be send in headers
                headers = ''
                for key in httpParams:
                    if key == 'Range': #Range is always used by ffmpeg
                        continue
                    elif key == 'User-Agent':
                        cmd += ' -u "%s"' %  httpParams[key]
                    else:
                        headers += ('%s: %s\r\n' % (key, httpParams[key]) )
                if len(headers):
                    cmd += ' -h "%s"' % headers
                if url.startswith('http'):
                    url = urlparser.decorateParamsFromUrl(url)
                    if '1' == url.meta.get('MPEGTS-Live', '0'):
                        cmd += ' -v '
                programId = url.meta.get('PROGRAM-ID', '')
                if programId != '':
                    cmd += ' -P "%s" ' % programId
            else:
                ramBufferSizeMB = config.plugins.iptvplayer.rambuffer_sizemb_files.value
                
            if ramBufferSizeMB > 0:
                cmd += ' -b %s ' % ramBufferSizeMB
            
            if config.plugins.iptvplayer.stereo_software_decode.value:
                cmd += ' -s '
            
            if config.plugins.iptvplayer.dts_software_decode.value:
                cmd += ' -d '
                
            if config.plugins.iptvplayer.plarform.value in ('sh4', 'mipsel', 'armv7', 'armv5t'):
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
            elif config.plugins.iptvplayer.plarform.value in ('sh4', 'mipsel', 'armv7', 'armv5t'):
                cmd += ' -p 2'
                if None != self.downloader:
                    cmd += ' -o 1 '
            
            audioTrackIdx = self.metaHandler.getAudioTrackIdx()
            printDBG(">>>>>>>>>>>>>>>>>>>>>>>> audioTrackIdx[%d]" % audioTrackIdx)
            if audioTrackIdx >= 0:
                cmd += ' -t %d ' % audioTrackIdx
                
            if config.plugins.iptvplayer.plarform.value in ('sh4', 'mipsel', 'armv7', 'armv5t'):
                subtitleTrackIdx = self.metaHandler.getEmbeddedSubtileTrackIdx()
                printDBG(">>>>>>>>>>>>>>>>>>>>>>>> subtitleTrackIdx[%d]" % subtitleTrackIdx)
                if subtitleTrackIdx >= 0:
                    cmd += ' -9 %d ' % subtitleTrackIdx
                
            if audioUri != '':
                cmd += ' -x "%s" ' % audioUri
            
            if 'iptv_video_rep_idx' in tmpUri.meta:
                cmd += ' -0 %s ' % tmpUri.meta['iptv_video_rep_idx']
            
            if 'iptv_audio_rep_idx' in tmpUri.meta:
                cmd += ' -1 %s ' % tmpUri.meta['iptv_audio_rep_idx']
                
            if 'iptv_m3u8_live_start_index' in tmpUri.meta:
                cmd += ' -f "live_start_index=%s" ' % tmpUri.meta['iptv_m3u8_live_start_index']
                
            if 'iptv_m3u8_key_uri_replace_old' in tmpUri.meta and 'iptv_m3u8_key_uri_replace_new' in tmpUri.meta:
                cmd += ' -f "key_uri_old=%s" -f "key_uri_new=%s" ' % (tmpUri.meta['iptv_m3u8_key_uri_replace_old'], tmpUri.meta['iptv_m3u8_key_uri_replace_new'])
            
            if self.extAdditionalParams.get('moov_atom_file', '') != '':
                 cmd += ' -F "%s" -S %s -O %s' % (self.extAdditionalParams['moov_atom_file'], self.extAdditionalParams['moov_atom_offset'] + self.extAdditionalParams['moov_atom_size'], self.extAdditionalParams['moov_atom_offset'])
            
            cmd += (' "%s"' % videoUri) + " > /dev/null"
        
        self.console = eConsoleAppContainer()
        self.console_appClosed_conn = eConnectCallback(self.console.appClosed, self.eplayer3Finished)
        self.console_stderrAvail_conn = eConnectCallback(self.console.stderrAvail, self.eplayer3DataAvailable)
        #if 'gstplayer' == self.player: 
        #    self.console_stdoutAvail_conn = eConnectCallback(self.console.stdoutAvail, self.eplayer3DataAvailable2 ) # work around to catch EOF event after seeking, pause .etc
        printDBG("->||||||| onStart cmd[%s]" % cmd)
        self.console.execute( E2PrioFix( cmd, 1 ) )
        self['statusIcon'].setPixmap( self.playback['statusIcons']['Play'] ) # sulge for test
        self['loopIcon'].setPixmap( self.playback['loopIcons']['Off'] )
        self['logoIcon'].setPixmap( self.playback['logoIcon'] )
        self['subSynchroIcon'].setPixmap( self.subHandler['synchro']['icon'] )
        
        # SET Video option
        videoOptions = ['aspect', 'policy', 'policy2']
        playerDefOptions = self.configObj.getDefaultPlayerVideoOptions()
        for opt in videoOptions:
            val = self.metaHandler.getVideoOption(opt)
            if val != None:
                self.currVideoOptions[opt] = val
            elif playerDefOptions[opt] != None:
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
            if playerDefOptions[opt] != None and playerDefOptions[opt] != self.defAudioOptions[opt]:
                SetE2AudioCodecMixOption(opt, playerDefOptions[opt])
        
        self.enableSubtitles()
            
    def initGuiComponentsPos(self):
        # info bar gui elements
        # calculate offset
        offset_x = (getDesktop(0).size().width() - self['playbackInfoBaner'].instance.size().width()) / 2
        offset_y = (getDesktop(0).size().height() - self['playbackInfoBaner'].instance.size().height()) - self.Y_CROPPING_GUARD
        if offset_x < 0: offset_x = 0
        if offset_y < 0: offset_y = 0
        
        self.infoBanerOffsetY = offset_y + self['playbackInfoBaner'].position[1]
        tmp = offset_y + self['logoIcon'].position[1]
        if tmp < self.infoBanerOffsetY:
            self.infoBanerOffsetY = tmp

        for elem in self.playbackInfoBar['guiElemNames']:
            self[elem].setPosition(self[elem].position[0]+offset_x, self[elem].position[1]+offset_y)
            
        # sub synchro elements
        # calculate offset
        offset_x = (getDesktop(0).size().width() - self['subSynchroIcon'].instance.size().width()) / 2
        offset_y = (getDesktop(0).size().height() - self['subSynchroIcon'].instance.size().height()) / 2
        if offset_x < 0: offset_x = 0
        if offset_y < 0: offset_y = 0

        for elem in self.subHandler['synchro']['guiElemNames']:
            self[elem].setPosition(self[elem].position[0]+offset_x, self[elem].position[1]+offset_y)

    def showPlaybackInfoBar(self, excludeElems=['goToSeekPointer', 'goToSeekLabel'], blocked=None):
        self.playbackInfoBar['timer'].stop()
        
        for elem in self.playbackInfoBar['guiElemNames']:
            if elem not in excludeElems:
                self[elem].show()
        
        if None == blocked or self.playbackInfoBar['blocked']:
            blocked = self.playbackInfoBar['blocked']

        self.playbackInfoBar['visible'] = True

        if not blocked:
            self.playbackInfoBar['timer'].start(self.autoHideTime, True) # singleshot
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
        self.setSubOffsetFromInfoBar()
        if -1 != self.subHandler['current_sub_time_ms']:
            self.updateSubtitles(self.subHandler['current_sub_time_ms'], True)
        
        if self.clockFormat: 
            self.playbackInfoBar['clock_timer'].stop()
    
    def updateClock(self):
        if self.clockFormat == '24':
            self['clockTime'].setText(time.strftime("%H:%M"))
        elif self.clockFormat == '12':
            self['clockTime'].setText(time.strftime("%I:%M"))
        
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
                # calc sub pos
                subY = desktopH - self.subConfig['pos'] - self.subConfig['line_height']
                subH = self.subConfig['line_height']
                
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
        #Screen.hide(self) # we do not need window at now maybe in future
        
    def fatalErrorHandler(self, msg):
        if self.fatalErrorOccurs: return
        self.fatalErrorOccurs = True
        self.showMessage(msg, MessageBox.TYPE_ERROR, self._fatalErrorCallback)
        
    def _fatalErrorCallback(self):
        self.waitCloseTimeoutCallback()
        
    def consoleWrite(self, data):
        try:
            self.console.write( data, len(data) )
            return
        except Exception:
            try: 
                self.console.write( data )
                return
            except Exception:
                printExc()
        msg = _("Fatal error: consoleWrite failed!")
        self.fatalErrorHandler(msg)
    
    def extPlayerSendCommand(self, command, arg1=''):
        #printDBG("IPTVExtMoviePlayer.extPlayerSendCommand command[%s] arg1[%s]" % (command, arg1))
        if None == self.console: 
            printExc("IPTVExtMoviePlayer.extPlayerSendCommand console not available")
            return False
        
        if 'ADD_TRIGGERS' == command:
            self.consoleWrite( "t{0}\n".format(arg1) )
        elif 'PLAYBACK_SET_LOOP_MODE'  == command:
            self.consoleWrite( "n%s\n" % arg1 )
        elif   'PLAYBACK_LENGTH'       == command: 
            self.consoleWrite( "l\n" )
        elif 'PLAYBACK_CURRENT_TIME' == command: 
            self.consoleWrite( "j\n" )
        elif 'PLAYBACK_INFO'         == command: 
            self.consoleWrite( "i\n" )
        elif 'PLAYBACK_SET_DOWNLOAD_FILE_TIMEOUT' == command:
            self.consoleWrite( "t%s\n" % arg1)
        elif 'PLAYBACK_SET_PROGRESSIVE_DOWNLOAD' == command:
            self.consoleWrite( "o%s\n" % arg1)
        elif 'PLAYBACK_SET_SUBTITLE_TRACK' == command:
            if ('%s' % arg1) != '-1':
                # we need be in play mode to switch/enabled embedded subtitles
                self.consoleWrite( "c\n" )
            self.consoleWrite( "s%s\n" % arg1)
            self.consoleWrite( "sc\n")
        else:
            # All below commands require that 'PLAY ' status, 
            # so we first send command to resume playback
            self.consoleWrite( "c\n" )
            
            if 'PLAYBACK_PAUSE'           == command: 
                self.consoleWrite( "p\n" )
            elif 'PLAYBACK_SET_AUDIO_TRACK' == command:
                self.consoleWrite( "a%s\n" % arg1)
                self.consoleWrite( "ac\n")
            elif 'PLAYBACK_SEEK_RELATIVE' == command: 
                self.consoleWrite( "kc%s\n" % (arg1) ) 
            elif 'PLAYBACK_SEEK_ABS'      == command: 
                self.consoleWrite( "gf%s\n" % (arg1) )
            elif 'PLAYBACK_FASTFORWARD'   == command:
                self.consoleWrite( "f%s\n" % arg1 )
            elif 'PLAYBACK_FASTBACKWARD'  == command: 
                self.consoleWrite( "b%s\n" % arg1 )
            elif 'PLAYBACK_SLOWMOTION'    == command: 
                self.consoleWrite( "m%s\n" % arg1 )
            elif 'PLAYBACK_STOP'          == command: 
                printDBG("IPTVExtMoviePlayer.extPlayerSendCommand PLAYBACK_STOP")
                if not self.waitCloseFix['waiting']:
                    self.waitCloseFix['waiting'] = True
                    self.waitCloseFix['timer'].start(5000, True) # singleshot
                try:
                    socket_path = "/tmp/iptvplayer_extplayer_term_fd";
                    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    sock.connect(socket_path)
                    #sock.sendall("q")
                except Exception:
                    printExc()
                finally:
                    sock.close()
                self.consoleWrite( "q\n" )
            else:
                printDBG("IPTVExtMoviePlayer.extPlayerSendCommand unknown command[%s]" % command)
                return False
        return True

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
            return IPTVExtMoviePlayerSummary
        return None

class IPTVExtMoviePlayerSummary(Screen):
    try:
        summary_screenwidth = getDesktop(1).size().width()
        summary_screenheight = getDesktop(1).size().height()
    except Exception:
        summary_screenwidth = 132
        summary_screenheight = 64
    if summary_screenwidth > 132 and summary_screenheight > 64:
        skin = """
            <screen position="0,0" size="%s,%s">
                <widget source="parent.Title" render="Label" position="6,4" size="%s,%s" font="Regular;42" />
            </screen>""" % (summary_screenwidth,summary_screenheight,summary_screenwidth-12,summary_screenheight-8)
    else:
        skin = """
            <screen position="0,0" size="132,64">
                <widget source="global.CurrentTime" render="Label" position="0,0" size="120,42" font="Regular;18" noWrap="1">
                        <convert type="ClockToText"></convert>
                </widget>
            </screen>"""
        def __init__(self, session, parent):
                Screen.__init__(self, session, parent = parent)
