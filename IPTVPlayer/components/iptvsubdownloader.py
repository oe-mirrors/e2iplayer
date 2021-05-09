# -*- coding: utf-8 -*-
#

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetDefaultLang, IsValidFileName, \
                                                          GetTmpDir, GetSubtitlesDir, GetIconDir, GetSkinsDir, \
                                                          GetIPTVPlayerVerstion, eConnectCallback, GetPluginDir, \
                                                          iptv_system, IsSubtitlesParserExtensionCanBeUsed
from Plugins.Extensions.IPTVPlayer.tools.iptvfavourites import IPTVFavourites
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CDisplayListItem, RetHost
from Plugins.Extensions.IPTVPlayer.components.isubprovider import ISubProvider
from Plugins.Extensions.IPTVPlayer.components.iptvmultipleinputbox import IPTVMultipleInputBox
from Plugins.Extensions.IPTVPlayer.components.iptvlist import IPTVMainNavigatorList
from Plugins.Extensions.IPTVPlayer.components.cover import Cover3
from Plugins.Extensions.IPTVPlayer.components.e2ivkselector import GetVirtualKeyboard
from Plugins.Extensions.IPTVPlayer.libs.pCommon import CParsingHelper
from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.utils import clean_html
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
###################################################

###################################################
# FOREIGN import
###################################################
from time import sleep as time_sleep
from os import remove as os_remove, path as os_path
from urllib import quote as urllib_quote
from random import shuffle as random_shuffle

from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.Label import Label
from Components.ActionMap import ActionMap
from Tools.LoadPixmap import LoadPixmap
from Components.config import config, configfile
from Components.Sources.StaticText import StaticText
from Tools.BoundFunction import boundFunction
from enigma import getDesktop, eTimer
###################################################

####################################################
#                   IPTV components
####################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, IPTVPlayerNeedInit, GetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
import Plugins.Extensions.IPTVPlayer.components.asynccall as asynccall
###################################################


class IPTVSubDownloaderWidget(Screen):
    IPTV_VERSION = GetIPTVPlayerVerstion()
    screenwidth = getDesktop(0).size().width()
    if screenwidth and screenwidth == 1920:
        skin = """
                    <screen name="IPTVSubDownloaderWidget" position="center,center" size="1590,825" title="E2iPlayer v%s">
                            <ePixmap position="5,9" zPosition="4" size="30,30" pixmap="%s" transparent="1" alphatest="on" />
                            <widget render="Label" source="key_red" position="45,9" size="140,32" zPosition="5" valign="center" halign="left" backgroundColor="black" font="Regular;32" transparent="1" foregroundColor="white" shadowColor="black" shadowOffset="-1,-1" />
                            <widget name="headertext" position="15,55" zPosition="1" size="1580,30" font="Regular;30" transparent="1" backgroundColor="#00000000" />
                            <widget name="statustext" position="15,148" zPosition="1" size="1580,180" font="Regular;30" halign="center" valign="center" transparent="1" backgroundColor="#00000000" />
                            <widget name="list" position="5,115" zPosition="2" size="1580,410" enableWrapAround="1" scrollbarMode="showOnDemand" transparent="1" backgroundColor="#00000000" />
                            <widget name="console" position="5,570" zPosition="1" size="1580,140" font="Regular;26" transparent="1" backgroundColor="#00000000" />
                            <ePixmap zPosition="4" position="5,535" size="1580,5" pixmap="%s" transparent="1" />
                            <widget name="spinner"   zPosition="2" position="508,240" size="16,16" transparent="1" alphatest="blend" />
                            <widget name="spinner_1" zPosition="1" position="508,240" size="16,16" transparent="1" alphatest="blend" />
                            <widget name="spinner_2" zPosition="1" position="524,240" size="16,16" transparent="1" alphatest="blend" />
                            <widget name="spinner_3" zPosition="1" position="540,240" size="16,16" transparent="1" alphatest="blend" />
                            <widget name="spinner_4" zPosition="1" position="556,240" size="16,16" transparent="1" alphatest="blend" />
                    </screen>
                """ % (IPTV_VERSION, GetIconDir('red.png'), GetIconDir('line.png'))
    else:
        skin = """
                    <screen name="IPTVSubDownloaderWidget" position="center,center" size="1090,525" title="E2iPlayer v%s">
                            <ePixmap position="30,9" zPosition="4" size="30,30" pixmap="%s" transparent="1" alphatest="on" />
                            <widget render="Label" source="key_red"    position="65,9"  size="210,27" zPosition="5" valign="center" halign="left" backgroundColor="black" font="Regular;21" transparent="1" foregroundColor="white" shadowColor="black" shadowOffset="-1,-1" />
                            <widget name="headertext" position="5,47" zPosition="1" size="1080,23" font="Regular;20" transparent="1" backgroundColor="#00000000" />
                            <widget name="statustext" position="5,140" zPosition="1" size="1080,180" font="Regular;20" halign="center" valign="center" transparent="1" backgroundColor="#00000000" />
                            <widget name="list" position="5,100" zPosition="2" size="1080,280" enableWrapAround="1" scrollbarMode="showOnDemand" transparent="1" backgroundColor="#00000000" />
                            <widget name="console" position="5,400" zPosition="1" size="1080,170" font="Regular;20" transparent="1" backgroundColor="#00000000" />
                            <ePixmap zPosition="4" position="5,395" size="1080,5" pixmap="%s" transparent="1" />
                            <widget name="spinner"   zPosition="2" position="508,240" size="16,16" transparent="1" alphatest="blend" />
                            <widget name="spinner_1" zPosition="1" position="508,240" size="16,16" transparent="1" alphatest="blend" />
                            <widget name="spinner_2" zPosition="1" position="524,240" size="16,16" transparent="1" alphatest="blend" />
                            <widget name="spinner_3" zPosition="1" position="540,240" size="16,16" transparent="1" alphatest="blend" />
                            <widget name="spinner_4" zPosition="1" position="556,240" size="16,16" transparent="1" alphatest="blend" />
                    </screen>
                """ % (IPTV_VERSION, GetIconDir('red.png'), GetIconDir('line.png'))

    def __init__(self, session, params={}):
        # params: vk_title, movie_title
        printDBG("IPTVSubDownloaderWidget.__init__ desktop IPTV_VERSION[%s]\n" % (IPTVSubDownloaderWidget.IPTV_VERSION))
        self.session = session
        path = GetSkinsDir(config.plugins.iptvplayer.skin.value) + "/subplaylist.xml"
        if os_path.exists(path):
            try:
                with open(path, "r") as f:
                    self.skin = f.read()
                    f.close()
            except Exception:
                printExc("Skin read error: " + path)

        Screen.__init__(self, session)

        self["key_red"] = StaticText(_("Cancel"))

        self["list"] = IPTVMainNavigatorList()
        self["list"].connectSelChanged(self.onSelectionChanged)
        self["statustext"] = Label("Loading...")
        self["actions"] = ActionMap(["IPTVPlayerListActions", "WizardActions", "DirectionActions", "ColorActions", "NumberActions"],
        {
            "red": self.red_pressed,
            "green": self.green_pressed,
            "yellow": self.yellow_pressed,
            "blue": self.blue_pressed,
            "ok": self.ok_pressed,
            "back": self.back_pressed,
        }, -1)

        self["headertext"] = Label()
        self["console"] = Label()
        self["sequencer"] = Label()

        try:
            for idx in range(5):
                spinnerName = "spinner"
                if idx:
                    spinnerName += '_%d' % idx
                self[spinnerName] = Cover3()
        except Exception:
            printExc()

        self.spinnerPixmap = [LoadPixmap(GetIconDir('radio_button_on.png')), LoadPixmap(GetIconDir('radio_button_off.png'))]
        self.showHostsErrorMessage = True

        self.onClose.append(self.__onClose)
        #self.onLayoutFinish.append(self.onStart)
        self.onShow.append(self.onStart)

        #Defs
        self.params = dict(params)
        self.params['discover_info'] = self.discoverInfoFromTitle()
        self.params['movie_url'] = strwithmeta(self.params.get('movie_url', ''))
        self.params['url_params'] = self.params['movie_url'].meta
        self.movieTitle = self.params['discover_info']['movie_title']

        self.workThread = None
        self.host = None
        self.hostName = ''

        self.nextSelIndex = 0
        self.currSelIndex = 0

        self.prevSelList = []
        self.categoryList = []

        self.currList = []
        self.currItem = CDisplayListItem()

        self.visible = True

        #################################################################
        #                      Inits for Proxy Queue
        #################################################################

        # register function in main Queue
        if None == asynccall.gMainFunctionsQueueTab[1]:
            asynccall.gMainFunctionsQueueTab[1] = asynccall.CFunctionProxyQueue(self.session)
        asynccall.gMainFunctionsQueueTab[1].clearQueue()
        asynccall.gMainFunctionsQueueTab[1].setProcFun(self.doProcessProxyQueueItem)

        #main Queue
        self.mainTimer = eTimer()
        self.mainTimer_conn = eConnectCallback(self.mainTimer.timeout, self.processProxyQueue)
        # every 100ms Proxy Queue will be checked
        self.mainTimer_interval = 100
        self.mainTimer.start(self.mainTimer_interval, True)

        # spinner timer
        self.spinnerTimer = eTimer()
        self.spinnerTimer_conn = eConnectCallback(self.spinnerTimer.timeout, self.updateSpinner)
        self.spinnerTimer_interval = 200
        self.spinnerEnabled = False

        #################################################################

        self.downloadedSubItems = []

    #end def __init__(self, session):

    def __del__(self):
        printDBG("IPTVSubDownloaderWidget.__del__ --------------------------")

    def __onClose(self):
        self["list"].disconnectSelChanged(self.onSelectionChanged)
        self.mainTimer_conn = None
        self.mainTimer = None
        self.spinnerTimer_conn = None
        self.spinnerTimer = None

        try:
            asynccall.gMainFunctionsQueueTab[1].setProcFun(None)
            asynccall.gMainFunctionsQueueTab[1].clearQueue()
        except Exception:
            printExc()

    def onStart(self):
        self.onShow.remove(self.onStart)
        #self.onLayoutFinish.remove(self.onStart)
        self.loadSpinner()
        self.hideSpinner()
        #self.hideButtons()
        self.confirmMovieTitle()

    def confirmMovieTitle(self):
        # first ask user to provide movie title
        self.session.openWithCallback(self.confirmMovieTitleCallBack, GetVirtualKeyboard(), title=(_("Confirm the title of the movie")), text=self.movieTitle)

    def confirmMovieTitleCallBack(self, text=None):
        if isinstance(text, basestring):
            self.movieTitle = text
            self.listSubtitlesProviders()
        else:
            self.close()

    def hideButtons(self, buttons=['green', 'yellow', 'blue']):
        try:
            for button in buttons:
                self['icon_' + button].hide()
                self['label_' + button].hide()
        except Exception:
            printExc()

    def red_pressed(self):
        self.close(None)

    def green_pressed(self):
        pass

    def yellow_pressed(self):
        pass

    def blue_pressed(self):
        pass

    def back_pressed(self):
        printDBG("IPTVSubDownloaderWidget.back_pressed")
        try:
            if self.isInWorkThread():
                if self.workThread.kill():
                    self.workThread = None
                    self["statustext"].setText(_("Operation aborted!"))
                return
        except Exception:
            return
        if self.visible:
            if len(self.prevSelList) > 0:
                self.nextSelIndex = self.prevSelList.pop()
                self.categoryList.pop()
                printDBG("back_pressed prev sel index %s" % self.nextSelIndex)
                if len(self.prevSelList) > 0:
                    self.requestListFromHost('Previous')
                else:
                    self.listSubtitlesProviders()
            else:
                #There is no prev categories, so exit
                self.confirmMovieTitle()
        else:
            self.showWindow()
    #end back_pressed(self):

    def ok_pressed(self):
        if self.visible:
            sel = None
            try:
                sel = self["list"].l.getCurrentSelection()[0]
            except Exception:
                self.getRefreshedCurrList()
                return
            if sel is None:
                printDBG("ok_pressed sel is None")
                return

            elif len(self.currList) <= 0:
                printDBG("ok_pressed list is empty")
                self.getRefreshedCurrList()
                return
            else:
                printDBG("ok_pressed selected item: %s" % (sel.name))

                item = self.getSelItem()
                self.currItem = item

                #Get current selection
                currSelIndex = self["list"].getCurrentIndex()
                #remember only prev categories
                if item.type in [CDisplayListItem.TYPE_SUB_PROVIDER]:
                    try:
                        self.hostName = item.privateData['sub_provider']
                        self.loadHost()
                    except Exception:
                        printExc()
                elif item.type in [CDisplayListItem.TYPE_SUBTITLE]:
                    self.requestListFromHost('ForDownloadSubFile', currSelIndex, '')
                elif item.type == CDisplayListItem.TYPE_CATEGORY:
                    printDBG("ok_pressed selected TYPE_CATEGORY")
                    self.currSelIndex = currSelIndex
                    self.requestListFromHost('ForItem', currSelIndex, '')
                elif item.type == CDisplayListItem.TYPE_MORE:
                    printDBG("ok_pressed selected TYPE_MORE")
                    self.currSelIndex = currSelIndex
                    self.requestListFromHost('ForMore', currSelIndex, '')
        else:
            self.showWindow()
    #end ok_pressed(self):

    def loadHost(self):
        try:
            _temp = __import__('Plugins.Extensions.IPTVPlayer.subproviders.subprov_' + self.hostName, globals(), locals(), ['IPTVSubProvider'], -1)
            params = dict(self.params)
            params['confirmed_title'] = self.movieTitle
            self.host = _temp.IPTVSubProvider(params)
            if not isinstance(self.host, ISubProvider):
                printDBG("Host [%r] does not inherit from ISubProvider" % self.hostName)
                self.close()
                return
        except Exception:
            printExc('Cannot import class IPTVSubProvider for host [%r]' % self.hostName)
            self.close()
            return
        # request initial list from host
        self.getInitialList()

    def loadSpinner(self):
        try:
            if "spinner" in self:
                self["spinner"].setPixmap(self.spinnerPixmap[0])
                for idx in range(4):
                    spinnerName = 'spinner_%d' % (idx + 1)
                    self[spinnerName].setPixmap(self.spinnerPixmap[1])
        except Exception:
            printExc()

    def showSpinner(self):
        if None != self.spinnerTimer:
            self._setSpinnerVisibility(True)
            self.spinnerTimer.start(self.spinnerTimer_interval, True)

    def hideSpinner(self):
        self._setSpinnerVisibility(False)

    def _setSpinnerVisibility(self, visible=True):
        self.spinnerEnabled = visible
        try:
            if "spinner" in self:
                for idx in range(5):
                    spinnerName = "spinner"
                    if idx:
                        spinnerName += '_%d' % idx
                    self[spinnerName].visible = visible
        except Exception:
            printExc()

    def updateSpinner(self):
        try:
            if self.spinnerEnabled and None != self.workThread:
                if self.workThread.isAlive():
                    if "spinner" in self:
                        x, y = self["spinner"].getPosition()
                        x += self["spinner"].getWidth()
                        if x > self["spinner_4"].getPosition()[0]:
                            x = self["spinner_1"].getPosition()[0]
                        self["spinner"].setPosition(x, y)
                    if None != self.spinnerTimer:
                        self.spinnerTimer.start(self.spinnerTimer_interval, True)
                        return
                elif not self.workThread.isFinished():
                    message = _("It seems that the subtitle's provider \"%s\" has crashed. Do you want to report this problem?") % self.hostName
                    message += "\n"
                    message += _('\nMake sure you are using the latest version of the plugin.')
                    message += _('\nYou can also report problem here: \nhttps://gitlab.com/iptvplayer-for-e2/iptvplayer-for-e2/issues\nor here: samsamsam@o2.pl')
                    self.session.openWithCallback(self.reportHostCrash, MessageBox, text=message, type=MessageBox.TYPE_YESNO)
            self.hideSpinner()
        except Exception:
            printExc()

    def reportHostCrash(self, ret):
        try:
            if ret:
                try:
                    exceptStack = self.workThread.getExceptStack()
                    reporter = GetPluginDir('iptvdm/reporthostcrash.py')
                    msg = urllib_quote('%s|%s|%s|%s' % ('HOST_CRASH', IPTVSubDownloaderWidget.IPTV_VERSION, self.hostName, self.getCategoryPath()))
                    self.crashConsole = iptv_system('python "%s" "http://iptvplayer.vline.pl/reporthostcrash.php?msg=%s" "%s" 2&>1 > /dev/null' % (reporter, msg, exceptStack))
                    printDBG(msg)
                except Exception:
                    printExc()
            self.workThread = None
            self.prevSelList = []
            self.back_pressed()
        except Exception:
            printExc()

    def processProxyQueue(self):
        if None != self.mainTimer:
            asynccall.gMainFunctionsQueueTab[1].processQueue()
            self.mainTimer.start(self.mainTimer_interval, True)
        return

    def doProcessProxyQueueItem(self, item):
        try:
            if None == item.retValue[0] or self.workThread == item.retValue[0]:
                if isinstance(item.retValue[1], asynccall.CPQParamsWrapper):
                    getattr(self, method)(*item.retValue[1])
                else:
                    getattr(self, item.clientFunName)(item.retValue[1])
            else:
                printDBG('>>>>>>>>>>>>>>> doProcessProxyQueueItem callback from old workThread[%r][%s]' % (self.workThread, item.retValue))
        except Exception:
            printExc()

    def getCategoryPath(self):
        def _getCat(cat, num):
            if '' == cat:
                return ''
            cat = ' > ' + cat
            if 1 < num:
                cat += (' (x%d)' % num)
            return cat

        if len(self.categoryList):
            str = self.hostName
        else:
            str = _("Select subtitles provider:")
        prevCat = ''
        prevNum = 0
        for cat in self.categoryList:
            if prevCat != cat:
                str += _getCat(prevCat, prevNum)
                prevCat = cat
                prevNum = 1
            else:
                prevNum += 1
        str += _getCat(prevCat, prevNum)
        return str

    def getRefreshedCurrList(self):
        currSelIndex = self["list"].getCurrentIndex()
        self.requestListFromHost('Refresh', currSelIndex)

    def getInitialList(self):
        self.nexSelIndex = 0
        self.prevSelList = []
        self.categoryList = []
        self.currList = []
        self.currItem = CDisplayListItem()
        self["headertext"].setText(self.getCategoryPath())
        self.requestListFromHost('Initial')

    def requestListFromHost(self, type, currSelIndex=-1, privateData=''):

        if not self.isInWorkThread():
            self["list"].hide()

            if type not in ['ForDownloadSubFile']:
                #hide bottom panel
                self["console"].setText('')

            if type in ['ForItem', 'Initial']:
                self.prevSelList.append(self.currSelIndex)
                self.categoryList.append(self.currItem.name)
                #new list, so select first index
                self.nextSelIndex = 0

            selItem = None
            if currSelIndex > -1 and len(self.currList) > currSelIndex:
                selItem = self.currList[currSelIndex]
                if selItem.itemIdx > -1 and len(self.currList) > selItem.itemIdx:
                    currSelIndex = selItem.itemIdx

            dots = ""#_("...............")
            IDS_DOWNLOADING = _("Downloading") + dots
            IDS_LOADING = _("Loading") + dots
            IDS_REFRESHING = _("Refreshing") + dots
            try:
                if type == 'Refresh':
                    self["statustext"].setText(IDS_REFRESHING)
                    self.workThread = asynccall.AsyncMethod(self.host.getCurrentList, boundFunction(self.callbackGetList, {'refresh': 1, 'selIndex': currSelIndex}), True)(1)
                elif type == 'ForMore':
                    self["statustext"].setText(IDS_DOWNLOADING)
                    self.workThread = asynccall.AsyncMethod(self.host.getMoreForItem, boundFunction(self.callbackGetList, {'refresh': 2, 'selIndex': currSelIndex}), True)(currSelIndex)
                elif type == 'Initial':
                    self["statustext"].setText(IDS_DOWNLOADING)
                    self.workThread = asynccall.AsyncMethod(self.host.getInitList, boundFunction(self.callbackGetList, {}), True)()
                elif type == 'Previous':
                    self["statustext"].setText(IDS_DOWNLOADING)
                    self.workThread = asynccall.AsyncMethod(self.host.getPrevList, boundFunction(self.callbackGetList, {}), True)()
                elif type == 'ForItem':
                    self["statustext"].setText(IDS_DOWNLOADING)
                    self.workThread = asynccall.AsyncMethod(self.host.getListForItem, boundFunction(self.callbackGetList, {}), True)(currSelIndex, 0)
                elif type == 'ForDownloadSubFile':
                    self["statustext"].setText(IDS_DOWNLOADING)
                    self.workThread = asynccall.AsyncMethod(self.host.downloadSubtitleFile, boundFunction(self.downloadSubtitleFileCallback, {}), True)(currSelIndex)
                else:
                    printDBG('requestListFromHost unknown list type: ' + type)
                self["headertext"].setText(self.getCategoryPath())
                self.showSpinner()
            except Exception:
                printExc('The current host crashed')
    #end requestListFromHost(self, type, currSelIndex = -1, privateData = ''):

    def callbackGetList(self, addParam, thread, ret):
        asynccall.gMainFunctionsQueueTab[1].addToQueue("reloadList", [thread, {'add_param': addParam, 'ret': ret}])

    def downloadSubtitleFileCallback(self, addParam, thread, ret):
        asynccall.gMainFunctionsQueueTab[1].addToQueue("subtitleFileDownloaded", [thread, {'add_param': addParam, 'ret': ret}])

    def subtitleFileDownloaded(self, params):
        printDBG("IPTVSubDownloaderWidget.subtitleFileDownloaded")
        self["statustext"].setText("")
        self["list"].show()
        ret = params['ret']

        if ret.status != RetHost.OK or 1 != len(ret.value):
            disMessage = _('Download subtiles failed.') + '\n'
            if ret.message and ret.message != '':
                disMessage += ret.message
            lastErrorMsg = GetIPTVPlayerLastHostError()
            if lastErrorMsg != '':
                disMessage += "\n" + _('Last error: "%s"') % lastErrorMsg
            self.session.open(MessageBox, disMessage, type=MessageBox.TYPE_ERROR)
        else:
            # subtitle downloaded, ask for finish
            ret = ret.value[0]
            self.downloadedSubItems.append(ret)
            message = _('Subtitles \"%s\" downloaded correctly.') % ret.path
            message += '\n' + _('Do you want to finish?')
            self.session.openWithCallback(self.askFinishCallback, MessageBox, text=message, type=MessageBox.TYPE_YESNO)

    def askFinishCallback(self, ret):
        try:
            if ret:
                item = self.downloadedSubItems[-1]
                track = {'title': item.name, 'lang': item.lang, 'path': item.path, 'id': item.imdbid}
                self.close(track)
        except Exception:
            printExc()

    def reloadList(self, params):
        printDBG("IPTVSubDownloaderWidget.reloadList")
        refresh = params['add_param'].get('refresh', 0)
        selIndex = params['add_param'].get('selIndex', 0)
        ret = params['ret']
        printDBG("IPTVSubDownloaderWidget.reloadList refresh[%s], selIndex[%s]" % (refresh, selIndex))
        if 0 < refresh and 0 < selIndex:
            self.nextSelIndex = selIndex

        if ret.status != RetHost.OK:
            printDBG("++++++++++++++++++++++ reloadList ret.status = %s" % ret.status)

        self.currList = ret.value
        self["list"].setList([(x,) for x in self.currList])

        self["headertext"].setText(self.getCategoryPath())
        if len(self.currList) <= 0:
            disMessage = _("No item to display. \nPress OK to refresh.\n")
            if ret.message and ret.message != '':
                disMessage += ret.message
            lastErrorMsg = GetIPTVPlayerLastHostError()
            if lastErrorMsg != '':
                disMessage += "\n" + _('Last error: "%s"') % lastErrorMsg
            disMessage += '\n\n' + _('Simplify the title and try again.')

            self["statustext"].setText(disMessage)
            self["list"].hide()
        else:
            #restor previus selection
            if len(self.currList) > self.nextSelIndex:
                self["list"].moveToIndex(self.nextSelIndex)
            #else:
            #selection will not be change so manualy call
            self.changeBottomPanel()

            self["statustext"].setText("")
            self["list"].show()
    #end reloadList(self, ret):

    def listSubtitlesProviders(self):
        printDBG("IPTVSubDownloaderWidget.listSubtitlesProviders")
        subProvidersList = []
        napisy24pl = {'title': "Napisy24.pl", 'sub_provider': 'napisy24pl'}
        openSubtitles = {'title': "OpenSubtitles.org API", 'sub_provider': 'opensubtitlesorg'}
        openSubtitles2 = {'title': "OpenSubtitles.org WWW", 'sub_provider': 'opensubtitlesorg2'}
        openSubtitles3 = {'title': "OpenSubtitles.org REST", 'sub_provider': 'opensubtitlesorg3'}
        napiprojektpl = {'title': "Napiprojekt.pl", 'sub_provider': 'napiprojektpl'}
        podnapisinet = {'title': "Podnapisi.net", 'sub_provider': 'podnapisinet'}
        titlovi = {'title': "Titlovi.com", 'sub_provider': 'titlovicom'}
        subscene = {'title': "Subscene.com", 'sub_provider': 'subscenecom'}
        youtube = {'title': "Youtube.com", 'sub_provider': 'youtubecom'}
        popcornsubtitles = {'title': "PopcornSubtitles.com", 'sub_provider': 'popcornsubtitles'}
        subtitlesgr = {'title': "Subtitles.gr", 'sub_provider': 'subtitlesgr'}
        prijevodi = {'title': "Prijevodi-Online.org", 'sub_provider': 'prijevodi'}
        subsro = {'title': "Subs.ro", 'sub_provider': 'subsro'}

        defaultLang = GetDefaultLang()

        if 'youtube_id' in self.params['url_params'] and '' != self.params['url_params']['youtube_id']:
            subProvidersList.append(youtube)

        if 'popcornsubtitles_url' in self.params['url_params'] and '' != self.params['url_params']['popcornsubtitles_url']:
            subProvidersList.append(popcornsubtitles)

        if 'hr' == defaultLang:
            subProvidersList.append(prijevodi)

        if 'el' == defaultLang:
            subProvidersList.append(subtitlesgr)

        if 'ro' == defaultLang:
            subProvidersList.append(subsro)

        if 'pl' == defaultLang:
            subProvidersList.append(napisy24pl)
            if IsSubtitlesParserExtensionCanBeUsed():
                subProvidersList.append(napiprojektpl)

        subProvidersList.append(openSubtitles2)
        subProvidersList.append(openSubtitles3)
        subProvidersList.append(openSubtitles)
        subProvidersList.append(podnapisinet)
        subProvidersList.append(titlovi)
        subProvidersList.append(subscene)

        if 'pl' != defaultLang:
            subProvidersList.append(napisy24pl)
            if IsSubtitlesParserExtensionCanBeUsed():
                subProvidersList.append(napiprojektpl)

        if 'el' != defaultLang:
            subProvidersList.append(subtitlesgr)

        if 'hr' != defaultLang:
            subProvidersList.append(prijevodi)

        if 'ro' != defaultLang:
            subProvidersList.append(subsro)

        self.currList = []
        for item in subProvidersList:
            params = CDisplayListItem(item['title'], item.get('desc', ''), CDisplayListItem.TYPE_SUB_PROVIDER)
            params.privateData = {'sub_provider': item['sub_provider']}
            self.currList.append(params)

        idx = 0
        selIndex = 0
        for idx in range(len(self.currList)):
            if self.hostName == self.currList[idx].privateData['sub_provider']:
                selIndex = idx
                break

        self["list"].setList([(x,) for x in self.currList])
        #restor previus selection
        if len(self.currList) > selIndex:
            self["list"].moveToIndex(selIndex)
        self.changeBottomPanel()
        self["headertext"].setText(self.getCategoryPath())
        self["statustext"].setText("")
        self["list"].show()

    def changeBottomPanel(self):
        selItem = self.getSelItem()
        if selItem and selItem.description != '':
            data = selItem.description
            sData = data.replace('\n', '')
            sData = data.replace('[/br]', '\n')
            self["console"].setText(sData)
        else:
            self["console"].setText(_('Searching subtitles for "%s"') % self.params['movie_title'])

    def onSelectionChanged(self):
        self.changeBottomPanel()

    def isInWorkThread(self):
        return None != self.workThread and (not self.workThread.isFinished() or self.workThread.isAlive())

    def getSelItem(self):
        currSelIndex = self["list"].getCurrentIndex()
        if len(self.currList) <= currSelIndex:
            printDBG("ERROR: getSelItem there is no item with index: %d, listOfItems.len: %d" % (currSelIndex, len(self.currList)))
            return None
        return self.currList[currSelIndex]

    def hideWindow(self):
        self.visible = False
        self.hide()

    def showWindow(self):
        self.visible = True
        self.show()

    def discoverInfoFromTitle(self, movieTitle=None):
        dInfo = {'movie_title': None, 'season': None, 'episode': None}
        if movieTitle == None:
            movieTitle = self.params.get('movie_title', '')

        # discovered information
        dInfo = {'movie_title': None, 'season': None, 'episode': None}
        dInfo['movie_title'] = CParsingHelper.getNormalizeStr(movieTitle)
        # try to guess season and episode number
        try:
            tmp = CParsingHelper.getSearchGroups(' ' + dInfo['movie_title'] + ' ', 's([0-9]+?)e([0-9]+?)[^0-9]', 2)
            dInfo.update({'season': int(tmp[0]), 'episode': int(tmp[1])})
        except Exception:
            try:
                tmp = CParsingHelper.getSearchGroups(' ' + dInfo['movie_title'] + ' ', '[^0-9]([0-9]+?)x([0-9]+?)[^0-9]', 2)
                dInfo.update({'season': int(tmp[0]), 'episode': int(tmp[1])})
            except Exception:
                pass
        return dInfo
