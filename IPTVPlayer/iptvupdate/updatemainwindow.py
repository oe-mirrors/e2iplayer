# -*- coding: utf-8 -*-
#
#  Update iptv main window
#


###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools          import printDBG, printExc, mkdirs, rmtree, FreeSpace, formatBytes, iptv_system, \
                                                                   GetIPTVDMImgDir, GetIPTVPlayerVerstion, GetShortPythonVersion, GetTmpDir, \
                                                                   GetHostsList, GetEnabledHostsList, WriteTextFile, IsExecutable, GetUpdateServerUri, \
                                                                   GetIconsHash, SetIconsHash, GetGraphicsHash, SetGraphicsHash, rm, GetPyScriptCmd
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes          import enum
from Plugins.Extensions.IPTVPlayer.iptvupdate.iptvlist      import IPTVUpdateList
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdownloadercreator import UpdateDownloaderCreator
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh            import DMHelper
from Plugins.Extensions.IPTVPlayer.libs.pCommon             import CParsingHelper

from Plugins.Extensions.IPTVPlayer.components.articleview   import ArticleView
from Plugins.Extensions.IPTVPlayer.components.ihost         import ArticleContent
from Plugins.Extensions.IPTVPlayer.libs.pCommon             import common
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
###################################################

###################################################
# FOREIGN import
###################################################
from Tools.Directories import fileExists
from Screens.MessageBox import MessageBox
from Screens.ChoiceBox import ChoiceBox
from Screens.Screen import Screen
from Components.config import config
from Components.ActionMap import ActionMap
from Components.Label import Label
from Tools.BoundFunction import boundFunction
from Tools.Directories import resolveFilename, SCOPE_PLUGINS

try:    import json
except Exception: import simplejson as json

from os import path as os_path, remove as os_remove, listdir as os_listdir
###################################################

class IPTVUpdateWindow(Screen):

    skin = """
    <screen name="IPTVUpdateMainWindow" position="center,center" size="620,440" title="" >
            <widget name="sub_title"    position="10,10" zPosition="2" size="600,35"  valign="center" halign="left"   font="Regular;22" transparent="1" foregroundColor="white" />
            <widget name="list"         position="10,50" zPosition="1" size="600,380" enableWrapAround="1" transparent="1" scrollbarMode="showOnDemand" />
            <widget name="console"      position="40,200"   zPosition="2" size="540,80" valign="center" halign="center"   font="Regular;34" transparent="0" foregroundColor="white" backgroundColor="black"/>
    </screen>"""

    ICONS = ['iconwait1.png', 'iconwait2.png', 'iconwait3.png', 'icondone.png', 'iconerror.png', 'iconwarning.png', 'iconcancelled.png']
    ICON  = enum( WAITING = 0, PROCESSING = 1, PROCESSING_NOT_BREAK = 2, PROCESSED = 3, ERROR = 4, WARNING = 5, CANCELLED = 6 )
    
    def __init__(self, session, updateObjImpl, autoStart=True):
        printDBG("IPTVUpdateMainWindow.__init__ -------------------------------")
        Screen.__init__(self, session)
        self.autoStart = autoStart
        
        self.updateObjImpl = updateObjImpl
        self.updateObjImpl.setStepFinishedCallBack(self.stepFinished)

        self.setup_title = self.updateObjImpl.getSetupTitle()
        self["sub_title"] = Label(_(" "))
        self["console"] = Label(_("> Press OK to start <"))
        self["actions"] = ActionMap(["SetupActions", "ColorActions"],
            {
                "cancel": self.keyExit,
                "ok"    : self.keyOK,
            }, -2)
        self.list = []
        self["list"] = IPTVUpdateList( [GetIPTVDMImgDir(x) for x in IPTVUpdateWindow.ICONS] )
        self.currStep = 0
        self.onShow.append(self.onStart)
        self.onClose.append(self.__onClose)
        self.status =  None
        
        self.messages = {}
        self.messages['not_interrupt']   = _("During processing, please do not interrupt.")
        self.messages['please_wait']     = _("During processing, please wait.")
        self.messages['not_aborted']     = _("Step [%s] cannot be aborted. Please wait.")

    def __del__(self):
        printDBG("IPTVUpdateMainWindow.__del__ -------------------------------")

    def __onClose(self):
        printDBG("IPTVUpdateMainWindow.__onClose -----------------------------")
        self.updateObjImpl.setStepFinishedCallBack(None)
        self.updateObjImpl.terminate()
        self.onClose.remove(self.__onClose)
        self.updateObjImpl = None
        self.list = []
        self["list"].setList([])

    def onStart(self):
        self.onShow.remove(self.onStart)
        self.setTitle( self.updateObjImpl.getTitle() )
        self["sub_title"].setText( self.updateObjImpl.getSubTitle() )
        self["list"].setSelectionState(enabled = False)
        self.preparUpdateStepsList()
        if self.autoStart:
            self.doStart()
        else:
            self["console"].show()
        
    def doStart(self):
        if 0 < len(self.list):
            self.currStep = 0
            self.status     = 'working'
            self.stepExecute()
            self["console"].hide()
        else:
            self["console"].setText(_("No steps to execute."))

    def reloadList(self):
        self["list"].hide()
        self["list"].setList([ (x,) for x in self.list])
        self["list"].show()
      
    def keyOK(self):
        if not self.autoStart and None == self.status:
            self.doStart()
        else:
            currItem = self["list"].getCurrent()
            if  self.status not in [None, 'working']:
                artItem = ArticleContent(title = currItem['title'], text = currItem['info'], images = [])
                self.session.open(ArticleView, artItem)

    def keyExit(self):
        if 'working' == self.status and not self.list[self.currStep].get('breakable', False):
            self.session.open(MessageBox, self.messages['not_aborted'], type = MessageBox.TYPE_INFO, timeout = 5 )
        else:
            self.close()

    def preparUpdateStepsList(self):
        self.list = self.updateObjImpl.getStepsList()
        self.reloadList()
        
    def stepExecute(self):
        self["list"].moveToIndex(self.currStep)
        if self.list[self.currStep].get('breakable', False):
            self.list[self.currStep].update( {'info': self.messages['please_wait'], 'icon': self.ICON.PROCESSING} )
        else:
            self.list[self.currStep].update( {'info': self.messages['not_interrupt'], 'icon': self.ICON.PROCESSING_NOT_BREAK} )
        self.reloadList()
        if self.updateObjImpl.isReadyToExecuteStep(self.currStep):
            self.list[self.currStep]['execFunction']()
        else:
            raise Exception("IPTVUpdateMainWindow.stepExecute seems that last step has not been finished.")
        
    def stepFinished(self, stsCode, msg):
        printDBG('IPTVUpdateMainWindow.stepFinished stsCode[%d], msg[%s]' % (stsCode, msg))
        nextStep = True
        if 0 != stsCode and self.list[self.currStep].get('repeatCount', 0) > 0:
            self.list[self.currStep]['repeatCount'] -= 1
            self.stepExecute()
            return

        if -1 == stsCode and not self.list[self.currStep]['ignoreError']:
            nextStep = False
            self.status = 'error'
            self.list[self.currStep].update( {'info': msg, 'icon': self.ICON.ERROR} )
            # cancel other steps
            currStep = self.currStep + 1
            while currStep < len(self.list):
                self.list[currStep].update( {'info': _("Aborted"), 'icon': self.ICON.CANCELLED} )
                currStep += 1
        elif 0 != stsCode:
            self.list[self.currStep].update( {'info': msg, 'icon': self.ICON.WARNING} )
        else:
            self.list[self.currStep].update( {'info': msg, 'icon': self.ICON.PROCESSED} )
        if nextStep:
            if self.currStep + 1 < len(self.list):
               self.currStep += 1 
               self.stepExecute()
            else:
                self.status = 'done'
                if  self.updateObjImpl.finalize():
                    self.close()
                    return
                else:
                    self["list"].setSelectionState(enabled = True)
        else:
            self.status = 'error'
            if  self.updateObjImpl.finalize(False, msg):
                self.close()
                return
            else:
                self["list"].setSelectionState(enabled = True)
        self.reloadList()
                
class IUpdateObjectInterface():
    def __init__(self, session):
        printDBG("IUpdateObjectInterface.__init__ -------------------------------")
    def __del__(self):
        printDBG("IUpdateObjectInterface.__del__ -------------------------------")
    def getSetupTitle(self):
        return " "
    def getTitle(self):
        return _(" ")
    def getSubTitle(self):
        return _(" ")
    def finalize(self, success=True):
        return
    def terminate(self):
        return
    def getStepsList(self):
        return []
    def isReadyToExecuteStep(currStepIdx):
        return False
    def setStepFinishedCallBack(self, stepFinishedCallbackFun):
        self.stepFinishedHandler = stepFinishedCallbackFun
    def stepFinished(self, stsCode=-1, msg=''):
        if self.stepFinishedHandler:
            self.stepFinishedHandler(stsCode, msg)
    def createPath(self, path):
        sts = True
        msg = ''
        try:
            if not os_path.isdir(path) and not os_path.islink(path):
                if not mkdirs(path):
                    msg = _("The problem with creating a directory [%s].") % path
                    sts = False
        except Exception:
            printExc()
            msg = _("Problem with the directory [%s].") % path
            sts = False
        return sts, msg

    def checkForFreeSpace(self, dir, requairedSpace):
        sts = True
        msg = ''
        if not FreeSpace(dir, requairedSpace, 1):
            sts = False
            msg = _("There is no space in the directory [%s]\n Available[%s], required [%s].") % (dir, formatBytes(FreeSpace(dir, None, 1)), formatBytes(requairedSpace))
        return sts, msg
    
class UpdateMainAppImpl(IUpdateObjectInterface):
    VERSION_PATTERN   = 'IPTV_VERSION="([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)"'
    
    def __init__(self, session, allowTheSameVersion=False):
        printDBG("UpdateMainAppImpl.__init__ -------------------------------")
        self.SERVERS_LIST_URLS = [GetUpdateServerUri('serwerslist.json')]

        self.session = session
        IUpdateObjectInterface.__init__(self, session)
        self.cm = common()

        self.allowTheSameVersion = allowTheSameVersion
        self.setup_title = _("IPTVPlayer - update")
        self.tmpDir = GetTmpDir('iptv_update')
        self.ExtensionPath = resolveFilename(SCOPE_PLUGINS, 'Extensions/')
        self.ExtensionTmpPath = None
        
        self.terminating = False
        self.status      = 'none'
        self.downloader  = None
        self.cmd         = None
        self.serversList = []
        self.gitlabList  = {}

        self.serverGraphicsHash = ''
        self.serverIconsHash = ''
        self.localGraphicsHash = ''
        self.localIconsHash = ''
        self.currServIdx = 0

        self.sourceArchive      = None
        self.graphicsSourceArchive = None
        self.iconsSourceArchive = None

        self.decKey = None
        self.decKeyFilePath = None

        self.destinationArchive = None
        self.serverIdx          = 0

        self.messages = {}
        self.messages['completed']       = _("Completed.")
        self.messages['problem_removal'] = _("Problem with the removal of the previous version.\nStatus[%d], outData[%s].")
        self.messages['problem_install'] = _("Problem with installing the new version.\nStatus[%d], outData[%s]")
        self.messages['problem_copy']    = _("Problem with copy files.\nStatus[%d], outData[%s]")

        self.list = []
        self.user = config.plugins.iptvplayer.iptvplayer_login.value
        self.password = config.plugins.iptvplayer.iptvplayer_password.value

    def checkVersionFile(self, newVerPath):
        code = 0
        msg  = _('Correct version.')
        
        newVerFile = os_path.join(newVerPath, 'version.py')
        if os_path.isfile(newVerFile):
            verPattern = self.VERSION_PATTERN
        else:
            newVerFile = os_path.join(newVerPath, 'version.pyo')
            verPattern = '([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)'

        try:
            # get new version
            with open (newVerFile, "r") as verFile: data = verFile.read()
            newVerNum = CParsingHelper.getSearchGroups(data, verPattern)[0]
            if newVerNum != self.serversList[self.currServIdx]['version']:
                code = -1
                msg  = _("Wrong version. \n downloaded version [%s] is different from the requested [%s].") % (newVerNum, self.serversList[self.currServIdx]['version'])
        except Exception:
            printExc()
            code = -1
            msg  = _("File [%s] reading failed.") % newVerFile
        return code, msg
        
    def doRestart(self, *args):
        try:
            try:
                from Screens.Standby import TryQuitMainloop
                self.session.openWithCallback(self.doRestartFailed, TryQuitMainloop, retvalue=3)
            except Exception:
                printExc()
                msgtxt = _("Please remember that you use this plugin at your own risk.")
                self.session.open(MessageBox, _("E2 GUI restart after IPTVPlayer update to version[%s].\n\n") % self.serversList[self.currServIdx]['version'] + msgtxt, type = MessageBox.TYPE_INFO, timeout = 5 )
                from enigma import quitMainloop
                quitMainloop(3)
        except Exception:
            printExc()
            self.doRestartFailed()
    
    def doRestartFailed(self, *args):
        try:
            self.list[currStep].update( {'info': _("Aborted"), 'icon': self.ICON.CANCELLED} )
        except Exception:
            printExc()
        self.session.open(MessageBox, _("Restart GUI failed. \nPlease restart STB manually."), type = MessageBox.TYPE_INFO, timeout=5 )

    #########################################################
    # INREFACE IMPLEMENTATION METHODS
    #########################################################
    def getSetupTitle(self):
        return _("IPTVPlayer - update")
        
    def getTitle(self):
        return _("IPTVPlayer - update")
        
    def getSubTitle(self):
        return _("Currently you have version [%s].") % GetIPTVPlayerVerstion()
        
    def finalize(self, success=True, errorMsg=""):
        if success:
            self.session.openWithCallback(self.doRestart, MessageBox, _("Update completed successfully. For the moment, the system will reboot."), type = MessageBox.TYPE_INFO, timeout=10 )
            return False
        else:
            message = errorMsg 
            # Failed message:
            message += "\n\n" + _("Update failed.\nCheck the status by selecting interesting and pressing OK.") 
            self.session.open(MessageBox, message, type = MessageBox.TYPE_ERROR, timeout = -1)
            return False

    def terminate(self):
        self.terminating = True
        if self.downloader:
            self.downloader.terminate()
            self.downloader = None
        if self.cmd:
            self.cmd.kill()
        self.clearTmpData()
    
    def __getStepDesc(self, title, execFunction, breakable=True, ignoreError=False, repeatCount=0):
        return  { 'title': title, 'execFunction': execFunction, 'breakable': breakable, 'ignoreError': ignoreError, 'info': _("Pending"), 'progressFun': None, 'repeatCount': repeatCount, 'icon': IPTVUpdateWindow.ICON.WAITING }
    
    def getStepsList(self):
        self.list = []
        if config.plugins.iptvplayer.gitlab_repo.value and config.plugins.iptvplayer.preferredupdateserver.value == '2':
            self.list.append( self.__getStepDesc(title = _("Add repository last version."),   execFunction = self.stepGetGitlab, ignoreError=True ) )
        self.list.append( self.__getStepDesc(title = _("Obtaining server list."),          execFunction = self.stepGetServerLists ) )
        self.list.append( self.__getStepDesc(title = _("Downloading an update packet."),   execFunction = self.stepGetArchive ) )
        self.list.append( self.__getStepDesc(title = _("Extracting an update packet."),    execFunction = self.stepUnpackArchive ) )
        self.list.append( self.__getStepDesc(title = _("Copy post installed binaries."),   execFunction = self.stepCopyPostInatalledBinaries, breakable=True, ignoreError=True ) )
        self.list.append( self.__getStepDesc(title = _("Executing user scripts."),         execFunction = self.stepExecuteUserScripts ) )
        self.list.append( self.__getStepDesc(title = _("Checking version."),               execFunction = self.stepCheckFiles ) )
        self.list.append( self.__getStepDesc(title = _("Removing unnecessary files."),     execFunction = self.stepRemoveUnnecessaryFiles, breakable=True, ignoreError=True) )
        self.list.append( self.__getStepDesc(title = _("Confirmation of installation."),   execFunction = self.stepConfirmInstalation) )
        self.list.append( self.__getStepDesc(title = _("Removing the old version."),       execFunction = self.stepRemoveOldVersion, breakable=False, ignoreError=True, repeatCount=2) )
        self.list.append( self.__getStepDesc(title = _("Installing new version."),         execFunction = self.stepInstallNewVersion,   breakable=False, ignoreError=False, repeatCount=3) )
        return self.list
        
    def isReadyToExecuteStep(self, currStepIdx):
        if not self.downloader and not self.cmd:
            return True
        else:
            return False

    #########################################################
    # STEPS IMPLEMENTATION METHODS
    #########################################################
    def stepGetServerLists(self):
        printDBG('UpdateMainAppImpl.stepGetServerLists')
        self.clearTmpData()
        sts, msg = self.createPath(self.tmpDir)
        if not sts:
            self.stepFinished(-1, msg)
            return
        serverUrl = self.SERVERS_LIST_URLS[self.serverIdx]
        self.downloader = UpdateDownloaderCreator(serverUrl)
        self.downloader.subscribersFor_Finish.append( boundFunction(self.downloadFinished, self.__serversListDownloadFinished, None))
        self.downloader.start(serverUrl, os_path.join(self.tmpDir, 'serwerslist2.json'))

    def stepGetGitlab(self):
        printDBG('UpdateMainAppImpl.stepGetGitlab')
        self.clearTmpData()
        sts, msg = self.createPath(self.tmpDir)
        if not sts:
            self.stepFinished(-1, msg)
            return
        serverUrl = "https://gitlab.com/{0}/e2iplayer/raw/master/IPTVPlayer/version.py".format(config.plugins.iptvplayer.gitlab_repo.value)
        self.downloader = UpdateDownloaderCreator(serverUrl)
        self.downloader.subscribersFor_Finish.append( boundFunction(self.downloadFinished, self.__serversListGitlabFinished, None))
        self.downloader.start(serverUrl, os_path.join(self.tmpDir, 'lastversion.py'))
        
    def stepGetArchive(self):
        self.downloader = UpdateDownloaderCreator(self.serversList[self.currServIdx]['url'])
        self.downloader.subscribersFor_Finish.append( boundFunction(self.downloadFinished, self.__archiveDownloadFinished, None))
        self.sourceArchive = os_path.join(self.tmpDir, 'iptvplayer_archive.tar.gz')
        url = self.serversList[self.currServIdx]['url']

        if self.decKey:
            from hashlib import sha256
            url += '&' if '?' in url else '?'
            url += 'hash=%s' % sha256(self.user).hexdigest()

        self.downloader.start(url, self.sourceArchive)

    def stepUnpackArchive(self):
        self.destinationArchive  = os_path.join(self.tmpDir , 'iptv_archive')
        self.ExtensionTmpPath    = os_path.join(self.destinationArchive, self.serversList[self.currServIdx]['subdir'])
        printDBG('UpdateMainAppImpl.stepUnpackArchive: sourceArchive[%s] -> destinationArchive[%s] -> ExtensionTmpPath[%s]' % (self.sourceArchive, self.destinationArchive, self.ExtensionTmpPath) )
        sts, msg = self.createPath(self.destinationArchive)
        if not sts:
            self.stepFinished(-1, msg)
            return
        
        cmd = 'rm -f "%s/*" > /dev/null 2>&1; tar -xzf "%s" -C "%s" 2>&1; PREV_RET=$?; rm -f "%s" > /dev/null 2>&1; (exit $PREV_RET)' % (self.destinationArchive, self.sourceArchive, self.destinationArchive, self.sourceArchive)
        self.cmd = iptv_system( cmd, self.__unpackCmdFinished )
        
    def stepGetEncKey(self):
        printDBG('UpdateMainAppImpl.stepGetEncKey')
        from hashlib import sha256
        nameHash = sha256(self.user).hexdigest()

        self.downloader = UpdateDownloaderCreator(self.serversList[self.currServIdx]['graphics_url'])
        self.downloader.subscribersFor_Finish.append( boundFunction(self.downloadFinished, self.__encKeyDownloadFinished, None))
        encKeyBin = os_path.join(self.tmpDir, 'iptvplayer_enc_key.bin')
        self.downloader.start(self.serversList[self.currServIdx]['enc_url_tmp'].format(nameHash), encKeyBin)

    def stepDecryptArchive(self):
        printDBG('UpdateMainAppImpl.stepDecryptArchive: sourceArchive[%s]' % (self.sourceArchive) )
        from hashlib import sha256
        try:
            self.decKeyFilePath = GetTmpDir(sha256(self.user).hexdigest()[:16])
            with open(self.decKeyFilePath, "wb") as f:
                f.write(self.decKey)
            cmd = GetPyScriptCmd('decrypt') + ' "%s" "%s" "%s" ' % (resolveFilename(SCOPE_PLUGINS, 'Extensions/IPTVPlayer/libs/'), self.sourceArchive, self.decKeyFilePath)
        except Exception:
            printExc()
            cmd = 'fake'
        
        self.cmd = iptv_system( cmd, self.__decryptionCmdFinished )

    def stepGetGraphicsArchive(self):
        if '' == self.serversList[self.currServIdx]['graphics_url']:
            self.stepFinished(0, _('Skipped.'))
            return
        
        packageName = 'graphics.tar.gz'
        self.downloader = UpdateDownloaderCreator(self.serversList[self.currServIdx]['graphics_url'])
        self.downloader.subscribersFor_Finish.append( boundFunction(self.downloadFinished, self.__archiveDownloadFinished, None))
        self.graphicsSourceArchive = os_path.join(self.tmpDir, 'iptvplayer_graphics_archive.tar.gz')
        self.downloader.start(self.serversList[self.currServIdx]['graphics_url'] + packageName, self.graphicsSourceArchive)
    
    def stepUnpackGraphicsArchive(self):
        if '' == self.serversList[self.currServIdx]['graphics_url']:
            self.stepFinished(0, _('Skipped.'))
            return
        
        cmd = 'tar -xzf "%s" -C "%s" 2>&1; PREV_RET=$?; rm -f "%s" > /dev/null 2>&1; (exit $PREV_RET)' % (self.graphicsSourceArchive, os_path.join(self.ExtensionTmpPath, 'IPTVPlayer/'), self.graphicsSourceArchive)
        self.cmd = iptv_system( cmd, self.__unpackCmdFinished )
        
    def stepGetIconsArchive(self):
        if '' == self.serversList[self.currServIdx]['icons_url'] or \
            not config.plugins.iptvplayer.ListaGraficzna.value:
            self.stepFinished(0, _('Skipped.'))
            return
        
        packageName = 'icons%s.tar.gz' % config.plugins.iptvplayer.IconsSize.value
        self.downloader = UpdateDownloaderCreator(self.serversList[self.currServIdx]['icons_url'])
        self.downloader.subscribersFor_Finish.append( boundFunction(self.downloadFinished, self.__archiveDownloadFinished, None))
        self.iconsSourceArchive = os_path.join(self.tmpDir, 'iptvplayer_icons_archive.tar.gz')
        self.downloader.start(self.serversList[self.currServIdx]['icons_url'] + packageName, self.iconsSourceArchive)
    
    def stepUnpackIconsArchive(self):
        if '' == self.serversList[self.currServIdx]['icons_url'] or \
            not config.plugins.iptvplayer.ListaGraficzna.value:
            self.stepFinished(0, _('Skipped.'))
            return
        
        cmd = 'tar -xzf "%s" -C "%s" 2>&1; PREV_RET=$?; rm -f "%s" > /dev/null 2>&1; (exit $PREV_RET)' % (self.iconsSourceArchive, os_path.join(self.ExtensionTmpPath, 'IPTVPlayer/'), self.iconsSourceArchive)
        self.cmd = iptv_system( cmd, self.__unpackCmdFinished )
        
    def stepCheckFiles(self):
        code, msg = self.checkVersionFile( os_path.join(self.ExtensionTmpPath, 'IPTVPlayer') )
        self.stepFinished(code, msg)
        
    def stepRemoveUnnecessaryFiles(self):
        printDBG("stepRemoveUnnecessaryFiles")
        playerSelectorPath = os_path.join(self.ExtensionTmpPath, 'IPTVPlayer/icons/PlayerSelector/')
        logosPath = os_path.join(self.ExtensionTmpPath, 'IPTVPlayer/icons/logos/')
        hostsPath = os_path.join(self.ExtensionTmpPath, 'IPTVPlayer/hosts/')
        webPath   = os_path.join(self.ExtensionTmpPath, 'IPTVPlayer/Web/')
        cmds = []
        iconSize = int(config.plugins.iptvplayer.IconsSize.value)
        if not config.plugins.iptvplayer.ListaGraficzna.value:
            iconSize = 0
        for size in [135, 120, 100]:
            if size != iconSize:
                cmds.append('rm -f %s' % (playerSelectorPath + '*{0}.png'.format(size)) )
                cmds.append('rm -f %s' % (playerSelectorPath + 'marker{0}.png'.format(size + 45)) )
        
        # remove Web iterface module if not needed
        if not config.plugins.iptvplayer.IPTVWebIterface.value:
            cmds.append('rm -rf %s' % (webPath))
        
        # removing not needed hosts
        if config.plugins.iptvplayer.remove_diabled_hosts.value:
            enabledHostsList = GetEnabledHostsList()
            hostsFromList    = GetHostsList(fromList=True, fromHostFolder=False)
            hostsFromFolder  = GetHostsList(fromList=False, fromHostFolder=True)
            hostsToRemove = []
            for hostItem in hostsFromList:
                if hostItem not in enabledHostsList and hostItem in hostsFromFolder:
                    cmds.append('rm -f %s' % (playerSelectorPath + '{0}*.png'.format(hostItem)) )
                    cmds.append('rm -f %s' % (logosPath + '{0}logo.png'.format(hostItem)) )
                    cmds.append('rm -f %s' % (hostsPath + 'host{0}.py*'.format(hostItem)) )
                
            # we need to prepare temporary file with removing cmds because cmd can be to long
            cmdFilePath = GetTmpDir('.iptv_remove_cmds.sh')
            cmds.insert(0, '#!/bin/sh')
            cmds.append('exit 0\n')
            text = '\n'.join(cmds)
            WriteTextFile(cmdFilePath, text, 'ascii')
            cmd = '/bin/sh "{0}" '.format(cmdFilePath)
            #cmd = '/bin/sh "{0}" && rm -rf "{1}" '.format(cmdFilePath, cmdFilePath)
        else:
            cmd = ' && '.join(cmds)
        printDBG("stepRemoveUnnecessaryFiles cmdp[%s]" % cmd)
        self.cmd = iptv_system( cmd, self.__removeUnnecessaryFilesCmdFinished )
    
    def stepCopyGraphicsWithoutIcons(self):
        # copy whole old icon directory
        # remove IPTVPlayer/icons/PlayerSelector dir, it will be replaced by new one
        oldIconsDir = os_path.join(self.ExtensionPath, 'IPTVPlayer', 'icons')
        newIconsDir = os_path.join(self.ExtensionTmpPath, 'IPTVPlayer', 'icons')
        newPlayerSelectorDir = os_path.join(newIconsDir, 'PlayerSelector')
        cmd = 'mkdir -p "%s" && cp -rf "%s"/* "%s"/ && rm -rf "%s"' % (newIconsDir, oldIconsDir, newIconsDir, newPlayerSelectorDir)
        printDBG('UpdateMainAppImpl.stepCopyGraphicsWithoutIcons cmd[%s]' % cmd)
        self.cmd = iptv_system( cmd, self.__copyOldCmdFinished )
    
    def stepCopyAllGraphics(self):
        # copy whole old icon directory
        oldIconsDir = os_path.join(self.ExtensionPath, 'IPTVPlayer', 'icons')
        newIconsDir = os_path.join(self.ExtensionTmpPath, 'IPTVPlayer', 'icons')
        cmd = 'mkdir -p "%s" && cp -rf "%s"/* "%s"/' % (newIconsDir, oldIconsDir, newIconsDir)
        printDBG('UpdateMainAppImpl.stepCopyAllGraphics cmd[%s]' % cmd)
        self.cmd = iptv_system( cmd, self.__copyOldCmdFinished )
    
    def stepCopyOnlyIcons(self):
        # create subdir IPTVPlayer/icons/ and copy only PlayerSelector dir to it
        cmd = 'rm -rf "%s"/*' % ( os_path.join(self.ExtensionPath, 'IPTVPlayer') )
        oldPlayerSelectorDir = os_path.join(self.ExtensionPath, 'IPTVPlayer', 'icons', 'PlayerSelector')
        newPlayerSelectorDir = os_path.join(self.ExtensionTmpPath, 'IPTVPlayer', 'icons', 'PlayerSelector')
        cmd = 'mkdir -p "%s" && cp -rf "%s"/* "%s"/' % (newPlayerSelectorDir, oldPlayerSelectorDir, newPlayerSelectorDir)
        printDBG('UpdateMainAppImpl.stepCopyOnlyIcons cmd[%s]' % cmd)
        self.cmd = iptv_system( cmd, self.__copyOldCmdFinished )
    
    def stepCopyPostInatalledBinaries(self, init=True, code=0, msg=''):
        # get users scripts
        if init:
            self.copyBinariesCmdList = []
            if fileExists("%s/libs/iptvsubparser/_subparser.so" % os_path.join(self.ExtensionPath, 'IPTVPlayer')):
                self.copyBinariesCmdList.append( 'cp -f "%s/libs/iptvsubparser/_subparser.so" "%s/libs/iptvsubparser/_subparser.so"  2>&1 ' % (os_path.join(self.ExtensionPath, 'IPTVPlayer'), os_path.join(self.ExtensionTmpPath, 'IPTVPlayer')) )

            if fileExists("%s/libs/e2icjson/e2icjson.so" % os_path.join(self.ExtensionPath, 'IPTVPlayer')):
                self.copyBinariesCmdList.append( 'cp -f "%s/libs/e2icjson/e2icjson.so" "%s/libs/e2icjson/e2icjson.so"  2>&1 ' % (os_path.join(self.ExtensionPath, 'IPTVPlayer'), os_path.join(self.ExtensionTmpPath, 'IPTVPlayer')) )

            binPath = "%s/bin/" % (os_path.join(self.ExtensionPath, 'IPTVPlayer'))
            binariesTab = [('exteplayer3', config.plugins.iptvplayer.exteplayer3path.value), \
                           ('gstplayer', config.plugins.iptvplayer.gstplayerpath.value), \
                           ('wget', config.plugins.iptvplayer.wgetpath.value), \
                           ('hlsdl', config.plugins.iptvplayer.hlsdlpath.value), \
                           ('cmdwrap', config.plugins.iptvplayer.cmdwrappath.value), \
                           ('duk', config.plugins.iptvplayer.dukpath.value), \
                           ('f4mdump', config.plugins.iptvplayer.f4mdumppath.value), \
                           ('uchardet', config.plugins.iptvplayer.uchardetpath.value)]
            for binItem in binariesTab:
                if binPath in binItem[1]:
                    self.copyBinariesCmdList.append( 'cp -f "%s/%s" "%s/bin/"  2>&1 ' % (binPath, binItem[0], os_path.join(self.ExtensionTmpPath, 'IPTVPlayer')) )
            
            if 0 < len(self.copyBinariesCmdList):
                self.copyBinariesMsg = ''
            else:
                self.copyBinariesMsg = _("Nothing to do here.")

        self.copyBinariesMsg += msg
        if 0 != code:
            self.stepFinished(-1, _("Problem with copy binary.\n") + self.copyBinariesMsg)
        elif 0 < len(self.copyBinariesCmdList):
            cmd = self.copyBinariesCmdList.pop()
            self.cmd = iptv_system( cmd, self.__copyBinariesCmdFinished )
        else:
            self.stepFinished(0, _("Completed.\n") + self.copyBinariesMsg)
        
    def stepExecuteUserScripts(self, init=True, code=0, msg=''):
        # get users scripts
        if init:
            self.customUserCmdList = self.__getUserCmdsList()
            if 0 <len(self.customUserCmdList):
                self.customUserMsg = ''
            else:
                self.customUserMsg = _("No user scripts.")

        self.customUserMsg += msg
        if 0 != code:
            self.stepFinished(-1, _("Problem with user script execution.\n") + self.customUserMsg)
        elif 0 < len(self.customUserCmdList):
            cmd = self.customUserCmdList.pop()
            self.cmd = iptv_system( cmd, self.__userCmdFinished )
        else:
            self.stepFinished(0, _("Completed.\n") + self.customUserMsg)
        
    def stepConfirmInstalation(self, confirmed=None):
        if None == confirmed:
            self.session.openWithCallback(self.stepConfirmInstalation, MessageBox, _("Version [%s] is ready for installation. After installation, restart of the system will be done.\nDo you want to continue?") % self.serversList[self.currServIdx]['version'], type = MessageBox.TYPE_YESNO, timeout = -1)
        else:
            if confirmed:
                self.stepFinished(0, _("Installation has been confirmed."))
            else:
                self.stepFinished(-1, _("Installation has been aborted."))
        
    def stepRemoveOldVersion(self):
        cmd = 'rm -rf "%s"/*' % ( os_path.join(self.ExtensionPath, 'IPTVPlayer') )
        printDBG('UpdateMainAppImpl.stepRemoveOldVersion cmd[%s]' % cmd)
        self.cmd = iptv_system( cmd, self.__removeOldVersionCmdFinished )

    def stepInstallNewVersion(self):
        cmd = ''
        try: 
            url = "http://iptvplayer.vline.pl/check.php?ver=%s&type=%s" % (self.serversList[self.currServIdx]['version'], self.serversList[self.currServIdx]['pyver'])
            cmd = '%s "%s" -t 1 -T 10 -O - > /dev/null 2>&1; ' % (config.plugins.iptvplayer.wgetpath.value, url)
        except Exception: 
            printExc()
        
        cmd += 'cp -rf "%s"/* "%s"/ 2>&1' % (os_path.join(self.ExtensionTmpPath, 'IPTVPlayer'), os_path.join(self.ExtensionPath, 'IPTVPlayer'))
        printDBG('UpdateMainAppImpl.stepInstallNewVersion cmd[%s]' % cmd)
        self.cmd = iptv_system( cmd, self.__installNewVersionCmdFinished )

    def downloadFinished(self, callBackFun, arg, status):
        printDBG('UpdateMainAppImpl.downloadFinished file[%s], status[%s]' % (file, status))
        self.downloader.subscribersFor_Finish = []
        if self.terminating:
            printDBG('UpdateMainAppImpl.downloadFinished closing')
            return
        callBackFun(arg, status)
        
    def clearTmpData(self):
        try:
            rmtree(self.tmpDir)
        except Exception:
            printExc()
    
    ##############################################################################
    # SERWERS LISTS STEP'S PRIVATES METHODS
    ############################################################################## 
    def __addLastVersion(self, servers):
        mainUrl = "https://gitlab.com/iptvplayer-for-e2/iptvplayer-for-e2"
        sts, data = self.cm.getPage(mainUrl + '/tree/master')
        if sts:
            crcSum = CParsingHelper.getSearchGroups(data, '"/iptvplayer-for-e2/iptvplayer-for-e2/commit/([^"]+?)">')[0]
            if 40 == len(crcSum):
                finalurl = mainUrl + '/blob/%s/IPTVPlayer/version.py' % crcSum
                sts, data = self.cm.getPage(finalurl)
                if sts:
                    newVerNum = CParsingHelper.getSearchGroups(data, '&quot;([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)&quot;')[0]
                    sourceUrl = mainUrl + "/repository/archive.tar.gz?ref=%s" % crcSum
                    server = {'name':'gitlab.com', 'version':newVerNum, 'url':sourceUrl, 'subdir':'iptvplayer-for-e2.git/', 'pyver':'X.X', 'packagetype':'sourcecode'}
                    printDBG("UpdateMainAppImpl.__addLastVersion server: [%s]" % str(server))
                    servers.append(server)
            else:
                printDBG("Wrong crcSum[%s]" % crcSum)

    def __serversListGitlabFinished(self, arg, status):
        url            = self.downloader.getUrl()
        filePath       = self.downloader.getFullFileName()
        self.downloader = None
        printDBG('UpdateMainAppImpl.__serversListGitlabFinished url[%s], filePath[%s] ' % (url, filePath))
        if DMHelper.STS.DOWNLOADED != status:
            msg = _("Problem with downloading the packet:\n[%s].") % url
            self.stepFinished(-1, msg)
        else:
            newVerNum = ''
            newVerFile = os_path.join(self.tmpDir, 'lastversion.py')
            verPattern = self.VERSION_PATTERN
            if os_path.isfile(newVerFile):
                try:
                    with open (newVerFile, "r") as verFile: data = verFile.read()
                    newVerNum = CParsingHelper.getSearchGroups(data, verPattern)[0]
                except Exception:
                    printExc()
                if 13 == len(newVerNum):
                    sourceUrl = "https://gitlab.com/{0}/e2iplayer/-/archive/master/e2iplayer-master.tar.gz".format(config.plugins.iptvplayer.gitlab_repo.value)
                    self.gitlabList = {'name':'gitlab.com', 'version':newVerNum, 'url':sourceUrl, 'subdir':'e2iplayer-master/', 'pyver':'X.X', 'packagetype':'sourcecode'}
                    printDBG("__serversListGitlabFinished: [%s]" % str(self.gitlabList))
                else:
                    msg = _("Wrong version: [%s].") % str(self.gitlabList)
                    self.stepFinished(-1, msg)
            else:
                msg = _("File not found:\n[%s].") % filePath
                self.stepFinished(-1, msg)
            self.stepFinished(0, _("GitLab version from {0} was downloaded successfully.".format(config.plugins.iptvplayer.gitlab_repo.value)))
        return

    def __serversListDownloadFinished(self, arg, status):
        def ServerComparator(x, y):
            try:    val1 = int(x['version'].replace('.', ''))
            except Exception: val1 = 0
            try:    val2 = int(y['version'].replace('.', ''))
            except Exception: val2 = 0
            #printDBG("ServerComparator val1[%d], val2[%d]" % (val1, val2))
            return cmp(val1, val2)
        try:
            currVerNum = int(GetIPTVPlayerVerstion().replace('.', ''))
        except Exception:
            printDBG('Version of the current instalation [%s]' % GetIPTVPlayerVerstion())
            currVerNum = 0
        pythonVer = GetShortPythonVersion()

        url      = self.downloader.getUrl()
        filePath = self.downloader.getFullFileName()
        self.downloader = None
        if DMHelper.STS.DOWNLOADED != status:
            self.serverIdx += 1
            if self.serverIdx <  len(self.SERVERS_LIST_URLS):
                self.stepGetServerLists()
            else:
                urls = ""
                for idx in range(self.serverIdx):
                    urls += "%s, " % (self.SERVERS_LIST_URLS[idx])
                if 1 < len(urls): urls = urls[:-2]
                self.stepFinished(-1, _("Problem with downloading the server list from [%s].") % urls)
        else:
            # process servers list
            serverGraphicsHash = ''
            serverIconsHash = ''
            serversList = []
            try:
                with open(filePath) as fileHandle:    
                    jsonData = json.load(fileHandle, 'utf-8')
                #printDBG("__serversListDownloadFinished jsonData [%r]" % jsonData)
                for server in jsonData['servers']:
                    serverOK = True
                    extServer = {}
                    for key in ['name', 'version', 'url', 'subdir', 'pyver', 'packagetype', 'graphics_url', 'icons_url']:
                        if key not in server.iterkeys():
                            serverOK = False
                            break
                        else:
                            extServer[key] = server[key].encode('utf8')
                            
                    #printDBG("")
                    if not serverOK: continue
                    enc = server.get('enc')
                    encUrlTmp = server.get('enc_url_tmp')
                    if enc:
                        if (not self.user or not self.password):
                            continue
                        else:
                            extServer['enc'] = enc.encode('utf8')
                            extServer['enc_url_tmp'] = encUrlTmp.encode('utf8')

                    newServer = dict(extServer)
                    serversList.append(newServer)
                serverGraphicsHash = str(jsonData.get('graphics_hash', ''))
                serverIconsHash = str(jsonData.get('icons_hash', ''))
            except Exception:
                printExc()
                self.serverIdx += 1
                if self.serverIdx <  len(self.SERVERS_LIST_URLS):
                    self.stepGetServerLists()
                else:
                    self.stepFinished(-1, _("Problem with parsing the server list."))
                return
            if config.plugins.iptvplayer.hiddenAllVersionInUpdate.value:
                self.__addLastVersion(serversList) # get last version from gitlab.com only for developers

            if config.plugins.iptvplayer.gitlab_repo.value and config.plugins.iptvplayer.preferredupdateserver.value == '2':
                serversList.append(self.gitlabList)

            self.serversList = serversList
            self.serverGraphicsHash = serverGraphicsHash
            self.serverIconsHash = serverIconsHash
            if 0 < len(serversList):
                options = []
                self.serversList.sort(cmp=ServerComparator, reverse=True)
                for idx in range(len(serversList)):
                    server = serversList[idx]
                    if not config.plugins.iptvplayer.hiddenAllVersionInUpdate.value:
                        try: newVerNum = int(server['version'].replace('.', ''))
                        except Exception: continue
                        #printDBG("newVerNum[%s], currVerNum[%s]" % (newVerNum, currVerNum))
                        if newVerNum < currVerNum and not config.plugins.iptvplayer.downgradePossible.value:
                            continue
                        if newVerNum == currVerNum and not self.allowTheSameVersion:
                            continue
                        if 'X.X' != server['pyver'] and pythonVer != server['pyver']:
                            continue
                        if config.plugins.iptvplayer.possibleUpdateType.value not in [server['packagetype'], 'all']: #"sourcecode", "precompiled"
                            continue

                    name = "| %s | python %s | %s | %s |" % (server['version'], server['pyver'], server['packagetype'], server['name'])
                    #printDBG("server list: " + name)
                    options.append((name, idx))
                if 1 == len(options) and not config.plugins.iptvplayer.downgradePossible.value:
                    self.__selServerCallBack(options[0])
                elif 0 < len(options):
                    self.session.openWithCallback(self.__selServerCallBack, ChoiceBox, title=_("Select update server"), list = options)
                else:
                    self.stepFinished(-1, _("There is no update for the current configuration."))
            else:
                self.stepFinished(-1, _("Update not available."))
        
    def __selServerCallBack(self, retArg):
        if retArg and len(retArg) == 2:
            self.localIconsHash = GetIconsHash()
            self.localGraphicsHash = GetGraphicsHash()
            
            self.currServIdx = retArg[1]
            list = []
            if 'graphics_url' in self.serversList[self.currServIdx]:
                if  self.localGraphicsHash == '' or self.serverGraphicsHash == '' or \
                    self.localGraphicsHash != self.serverGraphicsHash:
                    list.append( self.__getStepDesc(title = _("Downloading graphics package."),   execFunction = self.stepGetGraphicsArchive ) )
                    list.append( self.__getStepDesc(title = _("Extracting graphics package."),    execFunction = self.stepUnpackGraphicsArchive ) )
                    oldGraphics = False
                else:
                    oldGraphics = True

                if self.localIconsHash == '' or self.serverIconsHash == '' or \
                   self.localIconsHash != self.serverIconsHash:
                    if oldGraphics:
                        list.append( self.__getStepDesc(title = _("Copy graphics without icons."),    execFunction = self.stepCopyGraphicsWithoutIcons ) )

                    if config.plugins.iptvplayer.ListaGraficzna.value:
                        list.append( self.__getStepDesc(title = _("Downloading icons package."),      execFunction = self.stepGetIconsArchive ) )
                        list.append( self.__getStepDesc(title = _("Extracting icons package."),       execFunction = self.stepUnpackIconsArchive ) )
                else:
                    if oldGraphics:
                        if config.plugins.iptvplayer.ListaGraficzna.value:
                            list.append( self.__getStepDesc(title = _("Copy all graphics."),    execFunction = self.stepCopyAllGraphics ) )
                        else:
                            list.append( self.__getStepDesc(title = _("Copy graphics without icons."),    execFunction = self.stepCopyGraphicsWithoutIcons ) )
                    elif config.plugins.iptvplayer.ListaGraficzna.value:
                        list.append( self.__getStepDesc(title = _("Copy icons."),    execFunction = self.stepCopyOnlyIcons ) )

            self.list[3:3] = list
            if 'enc' in self.serversList[self.currServIdx]:
                self.list.insert(1, self.__getStepDesc(title = _("Get decryption key."),    execFunction = self.stepGetEncKey ) )
                self.list.insert(3, self.__getStepDesc(title = _("Decrypt archive."),       execFunction = self.stepDecryptArchive ) )
            
            self.stepFinished(0, _("Selected version [%s].") % retArg[0])
        else:
            self.stepFinished(-1, _("Update server not selected."))
    
    ##############################################################################
    # GET ARCHIVE STEP'S PRIVATES METHODS
    ############################################################################## 
    def __archiveDownloadFinished(self, arg, status):
        url            = self.downloader.getUrl()
        filePath       = self.downloader.getFullFileName()
        remoteFileSize = self.downloader.getRemoteFileSize()
        localFileSize  = self.downloader.getLocalFileSize(True)
        self.downloader = None
        printDBG('UpdateMainAppImpl.__archiveDownloadFinished url[%s], filePath[%s], remoteFileSize[%d], localFileSize[%d] ' % (url, filePath, remoteFileSize, localFileSize))
        if DMHelper.STS.DOWNLOADED != status and remoteFileSize > localFileSize:
            sts, msg = self.checkForFreeSpace(self.tmpDir, remoteFileSize - localFileSize)
            if sts:
                msg = _("Problem with downloading the packet:\n[%s].") % url
            self.stepFinished(-1, msg)
        else:
            self.stepFinished(0, _("Update packet was downloaded successfully."))
        return

    ##############################################################################
    # GET ARCHIVE STEP'S PRIVATES METHODS
    ############################################################################## 
    def __encKeyDownloadFinished(self, arg, status):
        url            = self.downloader.getUrl()
        filePath       = self.downloader.getFullFileName()
        remoteFileSize = self.downloader.getRemoteFileSize()
        localFileSize  = self.downloader.getLocalFileSize(True)
        self.downloader = None
        printDBG('UpdateMainAppImpl.__encKeyDownloadFinished url[%s], filePath[%s], remoteFileSize[%d], localFileSize[%d] ' % (url, filePath, remoteFileSize, localFileSize))
        if DMHelper.STS.DOWNLOADED != status and remoteFileSize > localFileSize:
            self.stepFinished(-1, _("Problem with downloading the encryption key:\n[%s].") % url)
        elif localFileSize != 16:
            self.stepFinished(-1, _("Wrong the encryption key size: %s\n") % localFileSize)
        else:
            try:
                from Plugins.Extensions.IPTVPlayer.libs.crypto.cipher.aes import AES
                from Plugins.Extensions.IPTVPlayer.libs.crypto.cipher.base import noPadding
                from hashlib import sha256, md5

                with open(filePath, "rb") as f:
                    data = f.read()

                userKey = sha256(self.password).digest()[:16]
                cipher = AES(userKey, keySize=len(userKey), padding=noPadding())
                data  = cipher.decrypt(data)
                check = md5(data).hexdigest()[:16]
                if check != self.serversList[self.currServIdx]['enc']:
                    self.stepFinished(-1, _("Problem with decryption the key."))
                    return
                self.decKey = data
            except Exception:
                printExc()
                self.stepFinished(-1, _("Problem with decryption the key."))
                return

            self.stepFinished(0, _("Encryption key was downloaded successfully."))
        return

    ##############################################################################
    # UNPACK ARCHIVE STEP'S PRIVATES METHODS
    ##############################################################################
    def __unpackCmdFinished(self, status, outData):
        code = -1
        msg  = ""
        self.cmd = None
        if 0 != status:
            code = -1
            msg  = _("Problem with extracting the archive. Return code [%d]\n%s.") % (status, outData)
        else:
            try:
                os_remove
            except Exception:
                printExc()
            code = 0
            msg  = _("Unpacking the archive completed successfully.")
        self.stepFinished(code, msg)

    ##############################################################################
    # DECRYPTION ARCHIVE STEP'S PRIVATES METHODS
    ##############################################################################
    def __decryptionCmdFinished(self, status, outData):
        if self.decKeyFilePath: rm(self.decKeyFilePath)
        code = -1
        msg  = ""
        self.cmd = None
        if 0 != status:
            code = -1
            msg  = _("Problem with decryption the archive. Return code [%d]\n%s.") % (status, outData)
        else:
            try:
                os_remove
            except Exception:
                printExc()
            code = 0
            msg  = _("Decryption the archive completed successfully.")
        self.stepFinished(code, msg)

    ##############################################################################
    # REMOVE UNNECESSARY FILES STEP'S PRIVATES METHODS
    ##############################################################################
    def __removeUnnecessaryFilesCmdFinished(self, status, outData):
        code = -1
        msg  = ""
        self.cmd = None
        if 0 != status:
            code = -1
            msg  = _("Error. Return code [%d]\n%s.") % (status, outData)
        else:
            code = 0
            msg  = _("Success.")
        self.stepFinished(code, msg)
        
    ##############################################################################
    # ExecuteUserScripts STEP'S PRIVATES METHODS
    ##############################################################################
    def __getUserCmdsList(self):
        printDBG('UpdateMainAppImpl.__getScriptsList begin')
        cmdList = [] 
        try:
            pathWithUserScripts =  os_path.join(self.ExtensionPath, 'IPTVPlayer/iptvupdate/custom/')
            fileList = os_listdir( pathWithUserScripts )
            for wholeFileName in fileList:
                # separate file name and file extension
                fileName, fileExt = os_path.splitext(wholeFileName)
                filePath = os_path.join(pathWithUserScripts, wholeFileName) 
                if os_path.isfile(filePath):
                    if fileExt in ['.pyo', '.pyc', '.py']:
                        interpreterBinName = 'python'
                    elif '.sh' == fileExt:
                        interpreterBinName = 'sh'
                    else:
                        continue 
                    cmdList.append('%s "%s" "%s" "%s" 2>&1 ' % (interpreterBinName, filePath, os_path.join(self.ExtensionPath, 'IPTVPlayer/'), os_path.join(self.ExtensionTmpPath, 'IPTVPlayer/')) )
            cmdList.sort()
        except Exception:
            printExc()
        printDBG('UpdateMainAppImpl.__getScriptsList [%r]' % cmdList)
        return cmdList
        
    def __copyBinariesCmdFinished(self, status, outData):
        self.cmd = None
        if 0 != status:
            code = -1
        else:
            code = 0
        msg  = '------------\nstatus[%d]\n[%s]\n------------\n' % (status, outData)
        self.stepCopyPostInatalledBinaries(init=False, code=code, msg=msg)
     
    def __userCmdFinished(self, status, outData):
        self.cmd = None
        if 0 != status:
            code = -1
        else:
            code = 0
        msg  = '------------\nstatus[%d]\n[%s]\n------------\n' % (status, outData)
        self.stepExecuteUserScripts(init=False, code=code, msg=msg)
        
    ##############################################################################
    # Instalation new version STEP'S PRIVATES METHODS
    ##############################################################################
    def __copyOldCmdFinished(self, status, outData):
        self.cmd = None
        if 0 != status:
            code = -1
            msg = self.messages['problem_copy'] % (status, outData)
        else:
            code = 0
            msg = self.messages['completed']
        self.stepFinished(code, msg)
    
    def __removeOldVersionCmdFinished(self, status, outData):
        self.cmd = None
        if 0 != status:
            code = -1
            msg = self.messages['problem_removal'] % (status, outData)
        else:
            code = 0
            msg = self.messages['completed']
        self.stepFinished(code, msg)
        
    def __installNewVersionCmdFinished(self, status, outData):
        self.cmd = None
        if 0 != status:
            msg = self.messages['problem_install'] % (status, outData)
            self.stepFinished(-1, msg)
        else:
            if self.localIconsHash != self.serverIconsHash:
                SetIconsHash(self.serverIconsHash)

            if self.localGraphicsHash != self.serverGraphicsHash:
                SetGraphicsHash(self.serverGraphicsHash)

            self.cmd = iptv_system( 'rm -rf ' + self.tmpDir + " && sync" , self.__doSyncCallBack )
        return

    def __doSyncCallBack(self, status, outData):
        self.cmd = None
        code, msg = self.checkVersionFile( os_path.join(self.ExtensionPath, 'IPTVPlayer') )
        self.stepFinished(code, msg)
