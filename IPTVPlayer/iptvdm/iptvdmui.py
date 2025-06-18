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
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, eConnectCallback, GetIconDir, GetNice, formatBytes, E2PrioFix
from Plugins.Extensions.IPTVPlayer.components.iptvplayer import IPTVStandardMoviePlayer, IPTVMiniMoviePlayer
from Plugins.Extensions.IPTVPlayer.components.iptvextmovieplayer import IPTVExtMoviePlayer
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import GetMoviePlayer
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _

from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper, DMItemBase
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
###################################################
# FOREIGN import
###################################################
from Screens.Screen import Screen
from Screens.ChoiceBox import ChoiceBox
from enigma import eTimer, eConsoleAppContainer, getDesktop
from Components.config import config
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.Sources.List import List
from Components.Sources.StaticText import StaticText
from Tools.LoadPixmap import LoadPixmap

from datetime import timedelta

from os import path as os_path, remove as os_remove
###################################################

#########################################################
#                    GLOBALS
#########################################################
gIPTVDM_listChanged = False


class IPTVDMWidget(Screen):

    ICONS_FILESNAMES = {DMHelper.STS.WAITING: 'iconwait1.png',
                        DMHelper.STS.DOWNLOADING: 'iconwait2.png',
                        DMHelper.STS.DOWNLOADED: 'icondone.png',
                        DMHelper.STS.INTERRUPTED: 'iconerror.png',
                        DMHelper.STS.ERROR: 'iconwarning.png',
                        }

    fullHD = getDesktop(0).size().width() == 1920

    skin = """
        <screen name="IPTVDMWidget" position="center,center" title="%s" size="1180,680" resolution="1280,720" flags="wfNoBorder">
            <widget source="Title" render="Label" position="160,10" size="600,40" foregroundColor="white" backgroundColor="black" borderWidth="1" borderColor="black" transparent="1" zPosition="1" font="Regular;24" valign="center" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/iptvlogo.png" position="12,10" size="100,40" alphatest="blend" transparent="1" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/red.png" position="240,648" size="20,20" alphatest="blend" transparent="1" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/green.png" position="470,648" size="20,20" alphatest="blend" transparent="1" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/yellow.png" position="700,648" size="20,20" alphatest="blend" transparent="1" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/blue.png" position="930,648" size="20,20" alphatest="blend" transparent="1" />
            <widget source="key_red" render="Label" position="274,644" size="200,28" zPosition="1" font="Regular;20" backgroundColor="black" foregroundColor="white" halign="left" transparent="1" valign="center" noWrap="1" />
            <widget source="key_green" render="Label" position="504,644" size="200,28" zPosition="1" font="Regular;20" backgroundColor="black" foregroundColor="white" halign="left" transparent="1" valign="center" noWrap="1" />
            <widget source="key_yellow" render="Label" position="734,644" size="200,28" zPosition="1" font="Regular;20" backgroundColor="black" foregroundColor="white" halign="left" transparent="1" valign="center" noWrap="1" />
            <widget source="key_blue" render="Label" position="964,644" size="200,28" zPosition="1" font="Regular;20" backgroundColor="black" foregroundColor="white" halign="left" transparent="1" valign="center" noWrap="1" />
            <eLabel name="BG_Title" position="0,0" size="1180,60" backgroundColor="#100d0f16" zPosition="-1" />
            <eLabel name="BG_Buttons" position="0,632" size="1180,48" backgroundColor="#100d0f16" zPosition="-1" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/smallshadowline.png" position="0,60" size="1180,2" zPosition="2" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/smallshadowline.png" position="0,630" size="1180,2" zPosition="2" />
            <ePixmap position="22,644" size="40,26" zPosition="10" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/ok.png" transparent="1" alphatest="blend" />
            <ePixmap position="80,644" size="40,26" zPosition="10" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/exit.png" transparent="1" alphatest="blend" />
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
           <widget name="titel" position="800,10" size="370,40" foregroundColor="white" backgroundColor="black" borderWidth="1" borderColor="black" transparent="1" zPosition="1" font="Regular;24" valign="center" />
        </screen>""" % (_("%s download manager") % "E2iPlayer")

    if fullHD:
        skin = skin.replace("/HD/", "/FHD/")

    def __init__(self, session, downloadmanager):
        self.session = session
        Screen.__init__(self, session, mandatoryWidgets=["downloadlist"])
        self.skinName = ["IPTVDMScreen", "IPTVDMWidget"]

        self.currentService = self.session.nav.getCurrentlyPlayingServiceReference()
        self.session.nav.event.append(self.__event)

        self["key_red"] = StaticText(_("Stop"))
        self["key_green"] = StaticText(_("Start"))
        self["key_yellow"] = StaticText(_("Archive"))
        self["key_blue"] = StaticText(_("Downloads"))

        self["downloadlist"] = List()
        # self["list"] = IPTVDownloadManagerList()
        # self["list"].connectSelChanged(self.onSelectionChanged)
        self["actions"] = ActionMap(["WizardActions", "DirectionActions", "ColorActions"],
        {
            "ok": self.ok_pressed,
            "back": self.back_pressed,
            "red": self.red_pressed,
            "green": self.green_pressed,
            "yellow": self.yellow_pressed,
            "blue": self.blue_pressed,

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
            if len(params[0]) > 3 and params[0].lower()[-4:] in ['.flv', '.mp4']:
                fileName = os_path.join(config.plugins.iptvplayer.NaszaSciezka.value, params[0])
                skip = False
                for item2 in self.currList:
                    printDBG("AAA:[%s]\nBBB:[%s]" % (item2.fileName, fileName))
                    if fileName == item2.fileName.replace('//', '/'):
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

    def leaveMoviePlayer(self, answer=None, position=None, *args, **kwargs):
        self.DM.setUpdateProgress(True)
        self.session.nav.playService(self.currentService)
        return

    def setManagerStatus(self):
        status = _("Manager status: ")
        if self.DM.isRunning():
            self["titel"].setText(status + _("STARTED"))
        else:
            self["titel"].setText(status + _("STOPPED"))

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

    def red_pressed(self):
        self.DM.stopWorkThread()
        self.setManagerStatus()
        return

    def green_pressed(self):
        self.DM.runWorkThread()
        self.setManagerStatus()
        return

    def yellow_pressed(self):
        if self.iptvclosing:
            return
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
        self.reloadList(True)
        return

    def blue_pressed(self):
        if self.iptvclosing:
            return
        self.localMode = False
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

        options = []
        item = self.getSelItem()
        if item is not None:
            if self.localMode:
                options.extend(play)
                options.extend(remove)
            elif DMHelper.STS.DOWNLOADED == item.status:
                options.extend(play)
                options.extend(remove)
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

            self.session.openWithCallback(self.makeActionOnDownloadItem, ChoiceBox, title=_("Select action"), list=options)

        return

    def makeActionOnDownloadItem(self, ret):
        item = self.getSelItem()
        if None is not ret and None is not item:
            printDBG("makeActionOnDownloadItem " + ret[1] + (" for downloadIdx[%d]" % item.downloadIdx))
            if ret[1] == "play":
                title = item.fileName
                try:
                    title = os_path.basename(title)
                    title = os_path.splitext(title)[0]
                except Exception:
                    printExc()
                # when we watch we no need update sts
                self.DM.setUpdateProgress(False)
                player = ret[2]
                if "mini" == player:
                    self.session.openWithCallback(self.leaveMoviePlayer, IPTVMiniMoviePlayer, item.fileName, title)
                elif player in ["exteplayer", "extgstplayer"]:
                    additionalParams = {}
                    if item.fileName.split('.')[-1] in ['mp3', 'm4a', 'ogg', 'wma', 'fla', 'wav', 'flac']:
                        additionalParams['show_iframe'] = config.plugins.iptvplayer.show_iframe.value
                        additionalParams['iframe_file_start'] = config.plugins.iptvplayer.iframe_file.value
                        additionalParams['iframe_file_end'] = config.plugins.iptvplayer.clear_iframe_file.value
                        additionalParams['iframe_continue'] = False

                    if "exteplayer" == player:
                        self.session.openWithCallback(self.leaveMoviePlayer, IPTVExtMoviePlayer, item.fileName, title, None, 'eplayer', additionalParams)
                    else:
                        self.session.openWithCallback(self.leaveMoviePlayer, IPTVExtMoviePlayer, item.fileName, title, None, 'gstplayer', additionalParams)
                else:
                    self.session.openWithCallback(self.leaveMoviePlayer, IPTVStandardMoviePlayer, item.fileName, title)
            elif self.localMode:
                if ret[1] == "remove":
                    try:
                        os_remove(item.fileName)
                        for idx in range(len(self.localFiles)):
                            if item.fileName == self.localFiles[idx].fileName:
                                del self.localFiles[idx]
                                self.reloadList(True)
                                break
                    except Exception:
                        printExc()
            elif ret[1] == "continue":
                self.DM.continueDownloadItem(item.downloadIdx)
            elif ret[1] == "retry":
                self.DM.retryDownloadItem(item.downloadIdx)
            elif ret[1] == "stop":
                self.DM.stopDownloadItem(item.downloadIdx)
            elif ret[1] == "remove":
                self.DM.removeDownloadItem(item.downloadIdx)
            elif ret[1] == "delet":
                self.DM.deleteDownloadItem(item.downloadIdx)
            elif ret[1] == "move":
                self.DM.moveToTopDownloadItem(item.downloadIdx)

    def getSelIndex(self):
        currSelIndex = self["downloadlist"].getCurrentIndex()
        return currSelIndex

    def getSelItem(self):
        currSelIndex = self["downloadlist"].getCurrentIndex()
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

    skin = """<screen name="IPTVDMNotificationWidget" position="800,10" zPosition="10" size="70,40" title="IPTVPlayer downloader" backgroundColor="#34111112" flags="wfNoBorder" >
            <widget name="message_label" font="Regular;24" position="0,0" zPosition="2" valign="center" halign="center" size="370,40" foregroundColor="green" backgroundColor="#34111112" borderWidth="1" borderColor="black" shadowColor="black" shadowOffset="-2,-2" transparent="1" />
        </screen>"""

    def __init__(self, session):
        Screen.__init__(self, session)
        self.skin = IPTVDMNotificationWidget.skin
        self.skinName = ["IPTVDMNotificationScreen", "IPTVDMNotificationWidget"]
        self['message_label'] = Label(_(" "))

    def setText(self, text):
        self['message_label'].setText(text)


class IPTVDMNotification():
    def __init__(self):
        self.dialog = None
        self.mainTimer = eTimer()
        self.mainTimer_conn = eConnectCallback(self.mainTimer.timeout, self.notifyHide)

    def dialogInit(self, session):
        printDBG("> IPTVDMNotification.dialogInit")
        self.dialog = session.instantiateDialog(IPTVDMNotificationWidget)

    def notifyHide(self):
        if self.dialog:
            self.dialog.setText("")
            self.dialog.hide()

    def showNotify(self, text):
        if self.dialog:
            printDBG("> IPTVDMNotification.showNotify[%s]" % text)
            self.dialog.setText(text)
            self.dialog.show()
            self.mainTimer.start(5000, 1)


gIPTVDMNotification = IPTVDMNotification()


def GetIPTVDMNotification():
    return gIPTVDMNotification
