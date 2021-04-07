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
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, eConnectCallback, GetIconDir, GetBinDir, E2PrioFix
from Plugins.Extensions.IPTVPlayer.components.iptvplayer import IPTVStandardMoviePlayer, IPTVMiniMoviePlayer
from Plugins.Extensions.IPTVPlayer.components.iptvextmovieplayer import IPTVExtMoviePlayer
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import ConfigMenu, GetMoviePlayer
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _

from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper, DMItemBase
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvlist import IPTVDownloadManagerList
###################################################

###################################################
# FOREIGN import
###################################################
from Screens.Screen import Screen
from Screens.ChoiceBox import ChoiceBox
from enigma import getDesktop, eTimer, eConsoleAppContainer
from Components.config import config
from Components.ActionMap import ActionMap, HelpableActionMap
from Components.Label import Label
from Components.Sources.StaticText import StaticText
from Components.config import config

from os import chmod as os_chmod, path as os_path, remove as os_remove
###################################################

#########################################################
#                    GLOBALS
#########################################################
gIPTVDM_listChanged = False


class IPTVDMWidget(Screen):

    sz_w = getDesktop(0).size().width() - 190
    sz_h = getDesktop(0).size().height() - 195
    if sz_h < 500:
        sz_h += 4
    skin = """
        <screen name="IPTVDMWidget" position="center,center" title="%s" size="%d,%d">
         <ePixmap position="5,9"   zPosition="4" size="30,30" pixmap="%s" transparent="1" alphatest="on" />
         <ePixmap position="180,9" zPosition="4" size="30,30" pixmap="%s" transparent="1" alphatest="on" />
         <ePixmap position="385,9" zPosition="4" size="30,30" pixmap="%s" transparent="1" alphatest="on" />
         <ePixmap position="590,9" zPosition="4" size="35,30" pixmap="%s" transparent="1" alphatest="on" />
         <widget render="Label" source="key_red"    position="45,9"  size="140,27" zPosition="5" valign="center" halign="left" backgroundColor="black" font="Regular;21" transparent="1" foregroundColor="white" shadowColor="black" shadowOffset="-1,-1" />
         <widget render="Label" source="key_green"  position="225,9" size="300,27" zPosition="5" valign="center" halign="left" backgroundColor="black" font="Regular;21" transparent="1" foregroundColor="white" shadowColor="black" shadowOffset="-1,-1" />
         <widget render="Label" source="key_yellow" position="425,9" size="300,27" zPosition="5" valign="center" halign="left" backgroundColor="black" font="Regular;21" transparent="1" foregroundColor="white" shadowColor="black" shadowOffset="-1,-1" />
         <widget render="Label" source="key_blue"   position="635,9" size="300,27" zPosition="5" valign="center" halign="left" backgroundColor="black" font="Regular;21" transparent="1" foregroundColor="white" shadowColor="black" shadowOffset="-1,-1" />
         <widget name="list" position="5,100" zPosition="2" size="%d,%d" scrollbarMode="showOnDemand" transparent="0"  backgroundColor="#00000000" enableWrapAround="1" />
         <widget name="titel" position="5,47" zPosition="1" size="%d,23" font="Regular;20" transparent="1"  backgroundColor="#00000000"/>
        </screen>""" % (_("%s download manager") % "E2iPlayer",
            sz_w, sz_h, # size
            GetIconDir('red.png'), GetIconDir('green.png'), GetIconDir('yellow.png'), GetIconDir('blue.png'),
            sz_w - 10, sz_h - 20, # size list
            sz_w - 135, # size titel
            )
        # <widget render="Label" source="key_yellow" position="220,9" size="180,27" zPosition="5" valign="center" halign="left" backgroundColor="black" font="Regular;21" transparent="1" foregroundColor="white" shadowColor="black" shadowOffset="-1,-1" />
        # <widget render="Label" source="key_blue" position="630,9" size="140,27" zPosition="5" valign="center" halign="left" backgroundColor="black" font="Regular;21" transparent="1" foregroundColor="white" shadowColor="black" shadowOffset="-1,-1" />

    def __init__(self, session, downloadmanager):
        self.session = session
        Screen.__init__(self, session)

        self.currentService = self.session.nav.getCurrentlyPlayingServiceReference()
        self.session.nav.event.append(self.__event)

        self["key_red"] = StaticText(_("Stop"))
        self["key_green"] = StaticText(_("Start"))
        self["key_yellow"] = StaticText(_("Archive"))
        self["key_blue"] = StaticText(_("Downloads"))

        self["list"] = IPTVDownloadManagerList()
        self["list"].connectSelChanged(self.onSelectionChanged)
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

        self.DM = downloadmanager
        self.DM.connectListChanged(self.onListChanged)
        self.DM.setUpdateProgress(True)
        self.setManagerStatus()

        self.started = 0
        global gIPTVDM_listChanged
        gIPTVDM_listChanged = True

        self.onClose.append(self.__onClose)
        self.onShow.append(self.onStart)

        #main Timer to refresh liar
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

    #end def __init__(self, session):

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
        self.tmpData += data
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
                continue # do not list hidden items
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
        if None != self.console:
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
            self["list"].disconnectSelChanged(self.onSelectionChanged)

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
            lsdirPath = GetBinDir("lsdir")
            try:
                os_chmod(lsdirPath, 0o777)
            except Exception:
                printExc()
            cmd = '%s "%s" rl r' % (lsdirPath, config.plugins.iptvplayer.NaszaSciezka.value)
            printDBG("cmd[%s]" % cmd)
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
        if item != None:
            if self.localMode:
                options.extend(play)
                options.extend(remove)
            elif DMHelper.STS.DOWNLOADED == item.status:
                options.extend(play)
                options.extend(remove)
                options.extend(retry)
            elif DMHelper.STS.INTERRUPTED == item.status:
                options.extend(play)
                #options.extend(cont)
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
        if None != ret and None != item:
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
                        if 'sh4' == config.plugins.iptvplayer.plarform.value:
                            additionalParams['iframe_continue'] = True
                        else:
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
        currSelIndex = self["list"].getCurrentIndex()
        return currSelIndex

    def getSelItem(self):
        currSelIndex = self["list"].getCurrentIndex()
        if not self.localMode:
            list = self.currList
        else:
            list = self.localFiles
        if len(list) <= currSelIndex:
            printDBG("ERROR: getSelItem there is no item with index: %d, listOfItems.len: %d" % (currSelIndex, len(list)))
            return None
        return list[currSelIndex]

    def getSelectedItem(self):
        sel = None
        try:
            sel = self["list"].l.getCurrentSelection()[0]
        except Exception:
            return None
        return sel

    def onStart(self):
        if self.started == 0:
            # pobierz liste
            self.started = 1
        return

    def reloadList(self, force=False):
        if not self.localMode:
            global gIPTVDM_listChanged
            if True == gIPTVDM_listChanged or force:
                printDBG("IPTV_DM_UI reload downloads list")
                self["list"].hide()
                gIPTVDM_listChanged = False
                # get current List from api
                self.currList = self.DM.getList()
                self["list"].setList([(x,) for x in self.currList])
                self["list"].show()
        elif force:
            printDBG("IPTV_DM_UI reload archive list")
            self["list"].hide()
            self["list"].setList([(x,) for x in self.localFiles])
            self["list"].show()
    #end reloadList

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
    d_w = getDesktop(0).size().width() - 20
    #d_h = getDesktop(0).size().height()

    skin = """<screen name="IPTVDMNotificationWidget" position="%d,%d" zPosition="10" size="350,60" title="IPTVPlayer downloader" backgroundColor="#31000000" >
            <widget name="message_label" font="Regular;24" position="0,0" zPosition="2" valign="center" halign="center" size="350,60" backgroundColor="#31000000" transparent="1" />
        </screen>""" % (d_w - 350, 60)

    def __init__(self, session):
        Screen.__init__(self, session)
        self.skin = IPTVDMNotificationWidget.skin
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
    global gIPTVDMNotification
    return gIPTVDMNotification
