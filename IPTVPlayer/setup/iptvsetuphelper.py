# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, iptv_system, IsExecutable
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper
###################################################

###################################################
# FOREIGN import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Components.config import configfile
###################################################


def SetupDownloaderCmdCreator(url, file):
    printDBG("SetupDownloaderCreator url[%s]" % url)
    if url.startswith('https'):
        if IsExecutable(DMHelper.GET_WGET_PATH()):
            printDBG("SetupDownloaderCreator WgetDownloader")
            return '%s "%s" -O "%s" ' % (DMHelper.GET_WGET_PATH(), url, file)
        elif IsExecutable('python'):
            printDBG("SetupDownloaderCreator PwgetDownloader")
            return 'python "%s" "%s" "%s" ' % (DMHelper.GET_PWGET_PATH(), url, file)
    else:
        if IsExecutable(DMHelper.GET_WGET_PATH()):
            printDBG("SetupDownloaderCreator WgetDownloader")
            return '%s "%s" -O "%s" ' % (DMHelper.GET_WGET_PATH(), url, file)
        elif IsExecutable('wget'):
            printDBG("SetupDownloaderCreator BuxyboxWgetDownloader")
            return 'wget "%s" -O "%s" ' % (url, file)
        elif IsExecutable('python'):
            printDBG("SetupDownloaderCreator PwgetDownloader")
            return 'python "%s" "%s" "%s" ' % (DMHelper.GET_PWGET_PATH(), url, file)
    printDBG("SetupDownloaderCreator downloader not available")
    return 'python "%s" "%s" "%s" ' % (DMHelper.GET_PWGET_PATH(), url, file)


class CCmdValidator:
    def __init__(self, finishCallback, validatorFun, cmdTabs):
        printDBG("CCmdValidator.__init__ ---------------------------------")
        self.cmdTabs = cmdTabs
        self.stsTab = []
        self.dataTab = []
        self.finishCallback = finishCallback
        self.validatorFun = validatorFun
        self.detectIdx = 0

        self.outData = ""
        # flags
        self.termination = False
        self.cmd = None

    def __del__(self):
        printDBG("CCmdValidator.__del__ ---------------------------------")

    def start(self):
        printDBG("CCmdValidator.start")
        self.outData = ""
        self.detectIdx = 0
        self._detect()

    def terminate(self):
        self.termination = True
        self.finishCallback = None
        self.validatorFun = None
        if self.cmd:
            self.cmd.kill(False)
        self.cmd = None

    def finish(self):
        printDBG('CCmdValidator.finish detectIdx[%r]' % self.detectIdx)
        if self.termination:
            return

        finishCallback = self.finishCallback
        self.finishCallback = None
        self.validatorFun = None

        self.cmdTabs = []
        self.outData = ""
        finishCallback(self.stsTab, self.dataTab)

    def _cmdFinished(self, code, data):
        printDBG("CCmdValidator._cmdFinished cmd[%r] code[%r], data[%r]" % (self.cmdTabs[self.detectIdx], code, data))
        if self.termination:
            return
        self.cmd = None
        sts, cont = self.validatorFun(code, data)
        self.stsTab.append(sts)
        self.dataTab.append(data)
        if cont and (self.detectIdx + 1) < len(self.cmdTabs):
            self.detectIdx += 1
            self._detect()
        else:
            self.finish()

    def _detect(self):
        self.cmd = iptv_system(self.cmdTabs[self.detectIdx], self._cmdFinished)


class CBinaryStepHelper:
    def __init__(self, name, platform, openSSLVersion, configOption):
        # members
        self.name = name
        self.platform = platform
        self.openSSLVersion = openSSLVersion
        self.configOption = configOption

        self.paths = []
        self.debugMessagesAllowed = False
        self.installChoiseList = []

        # handlers to functions
        self.detectCmdBuilder = self._detectCmdBuilder
        self.detectValidator = self._detectValidator

        self.downloadCmdBuilder = self._downloadCmdBuilder
        self.downloadValidator = self._downloadValidator

        self.installCmdBuilder = self._installCmdBuilder
        self.installValidator = self._installValidator

        self.saveConfigOptionHandler = self._saveConfigOptionHandler
        self.deprecatedHandler = None
        self.finishHandler = None

        self.messages = {'detection': [_('Detection of the "%s" utility.') % self.name, _('The "%s" utility is used by IPTVPlayer.') % self.name],
                         'download': [_('Downloading "%s".') % self.name, None],
                         'dwn_failed': [None, _('Downloading "%s" failed. \nDo you want to retry?') % self.name],
                         'not_detected_1': [None, _('Utility "%s" has not been detected. \nWhat do you want to do?') % self.name],
                         'not_detected_2': [None, _('Utility "%s" has not been detected. \nDo you want to install it?') % self.name],
                         'deprecated_1': [None, _('Utility "%s" is deprecated. \nWhat do you want to do?') % self.name],
                         'deprecated_2': [None, _('Utility "%s" is deprecated. \nDo you want to install new one?') % self.name],
                         'install': [_('Installing "%s".') % self.name, None]}

    def _detectCmdBuilder(self, path):
        return path + " 2>&1 "

    def _detectValidator(self, code, data):
        if 0 == code:
            return True, False
        else:
            return False, True

    def _downloadCmdBuilder(self, binName, platform, openSSLVersion, server, tmpPath):
        url = server + 'bin/' + platform + ('/%s_openssl' % binName) + openSSLVersion
        tmpFile = tmpPath + binName
        cmd = SetupDownloaderCmdCreator(url, tmpFile) + ' > /dev/null 2>&1'
        return cmd

    def _downloadValidator(self, code, data):
        if 0 == code:
            return True, False
        else:
            return False, True

    def _installCmdBuilder(self, binName, binaryInstallPath, tmpPath):
        srcFile = tmpPath + binName
        cmd = 'cp "%s" "%s" && chmod 777 "%s"' % (srcFile, binaryInstallPath, binaryInstallPath)
        return cmd

    def _installValidator(self, code, data):
        if 0 == code:
            return True, False
        else:
            return False, True

    def _saveConfigOptionHandler(self, configOption, value):
        if None != configOption:
            configOption.value = value
            configOption.save()
            configfile.save()

    def getMessage(self, key, num):
        return self.messages[key][num]

    def getDetectCmds(self):
        cmdTabs = []
        for path in self.paths:
            cmdTabs.append(self.detectCmdBuilder(path))
        return cmdTabs

    def getName(self):
        return self.name

    def getConfigOption(self):
        return self.configOption

    def getInstallChoiseList(self):
        return self.installChoiseList

    def getPaths(self):
        return self.paths

    def getDetectCmdBuilder(self):
        return self.detectCmdBuilder

    def getDetectValidator(self):
        return self.detectValidator

    def getDownloadCmdBuilder(self):
        return self.downloadCmdBuilder

    def getDownloadValidator(self):
        return self.downloadValidator

    def getInstallCmdBuilder(self):
        return self.installCmdBuilder

    def getInstallValidator(self):
        return self.installValidator

    def getSaveConfigOptionHandler(self):
        return self.saveConfigOptionHandler

    def getDeprecatedHandler(self):
        return self.deprecatedHandler

    def getFinishHandler(self):
        return self.finishHandler

    def isDebugMessagesAllowed(self):
        return self.debugMessagesAllowed

    # set
    def updateMessage(self, key, message, id=1):
        self.messages[key][id] = message

    def setInstallChoiseList(self, list):
        self.installChoiseList = list

    def setPaths(self, list):
        self.paths = list

    def setDetectCmdBuilder(self, callback):
        self.detectCmdBuilder = callback

    def setDetectValidator(self, callback):
        self.detectValidator = callback

    def setDownloadCmdBuilder(self, callback):
        self.downloadCmdBuilder = callback

    def setDownloadValidator(self, callback):
        self.downloadValidator = callback

    def setInstallCmdBuilder(self, callback):
        self.installCmdBuilder = callback

    def setInstallValidator(self, callback):
        self.installValidator = callback

    def setSaveConfigOptionHandler(self, callback):
        self.saveConfigOptionHandler = callback

    def setDeprecatedHandler(self, callback):
        self.deprecatedHandler = callback

    def setFinishHandler(self, callback):
        self.finishHandler = callback

    def setDebugMessagesAllowed(self, flag):
        self.debugMessagesAllowed = flag


'''
    ###################################################
    # STEP: WGET
    ###################################################
    def wgetStep(self, ret=None):
        printDBG("IPTVSetupImpl.wgetStep")
        def _detectValidator(code, data):
            if 'BusyBox' not in data and '+https' in data: return True,False
            else: return False,True

        def _downloadCmdBuilder(binName, platform, openSSLVersion, server, tmpPath):
            url = server + 'bin/' + platform + ('/%s_openssl' % binName) + openSSLVersion
            tmpFile = tmpPath + binName
            cmd = 'wget "%s" -O "%s" > /dev/null 2>&1' % (url, tmpFile)
            return cmd

        def _baseValidator(self, code, data):
            if 0==code: return True,False
            else: return False,True

        def _installCmdBuilder(binName, binaryInstallPath, tmpPath):
            srcFile = tmpPath + binName
            cmd = 'cp "%s" "%s" && chmod 777 "%s"' % (srcFile, binaryInstallPath, binaryInstallPath)
            return cmd

        def _saveConfigOptionHandler(configOption, value):
            configOption.value = value
            configOption.save()
            configfile.save()

        def _deprecatedHandler(paths, stsTab, dataTab):
            sts, retPath = False, ""
            for idx in range(len(dataTab)):
                if 'samsamsam@o2.pl' in dataTab[idx]: sts, retPath = True, paths[idx]
            return sts, retPath

        self.stepHelper = CBinaryStepHelper("wget", self.platform, self.openSSLVersion, config.plugins.iptvplayer.wgetpath)
        self.stepHelper.setInstallChoiseList(        self._wgetInstallChoiseList )
        self.stepHelper.setPaths(                    self.wgetpaths              )
        self.stepHelper.setDetectCmdBuilder(         lambda path: path + " 2>&1 ")
        self.stepHelper.setDetectValidator(          _detectValidator            )
        self.stepHelper.setDownloadCmdBuilder(       _downloadCmdBuilder         )
        self.stepHelper.setDownloadValidator(        _baseValidator              )
        self.stepHelper.setInstallCmdBuilder(        _installCmdBuilder          )
        self.stepHelper.setInstallValidator(         _baseValidator              )
        self.stepHelper.setSaveConfigOptionHandler(  _saveConfigOptionHandler    )
        #self.stepHelper.setDeprecatedHandler(        _deprecatedHandler          )
        self.stepHelper.setFinishHandler(            self.wgetStepFinished       )
        self.stepHelper.setDebugMessagesAllowed(     False                       )
        self.binaryDetect()
'''
