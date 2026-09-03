# -*- coding: utf-8 -*-
#

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetDefaultLang, GetTmpDir, GetSubtitlesDir, RemoveDisallowedFilenameChars, iptv_system, MapUcharEncoding
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CDisplayListItem
from Plugins.Extensions.IPTVPlayer.components.iptvlist import IPTVMainNavigatorList
from Plugins.Extensions.IPTVPlayer.components import skinchrome

from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdownloadercreator import DownloaderCreator
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
###################################################
# FOREIGN import
###################################################
from Screens.Screen import Screen
from Components.Label import Label
from Components.Sources.StaticText import StaticText
from Components.ActionMap import ActionMap

import codecs
###################################################


class IPTVSubSimpleDownloaderWidget(Screen):
    _TMP_FILE_NAME = ".externaltmpsub"

    # Uses the same `resolution="1280,720"` auto-scale `build_header_auto()`/
    # `build_footer_auto()` shape as `SearchHistoryEditor`/
    # `YouTubeUserLinksEditorScreen` (plain list, no fixed-pixel grid/
    # marker content fighting auto-scale).
    #
    # RED/GREEN now `key_red`/`key_green` StaticText sources (matching
    # `build_footer()`'s own `source="key_X"`/`ConditionalShowHide`
    # convention) instead of separate Cover3 icon + Label pairs toggled via
    # raw `.hide()`/`.show()` - icon pixmaps are baked into the footer's
    # skin XML now, no more Python-side `LoadPixmap(GetIconDir(...))`.
    # `hideButtons()`/`showButtons()` below just blank/restore the
    # StaticText itself, `ConditionalShowHide` does the rest.
    #
    # The old dual-purpose "title" widget (window title bar AND, in list
    # mode, an in-body "Select subtitles to download" caption) is split:
    # the window title is now `build_header_auto()`'s own `source="Title"`
    # (driven by `self.setTitle()`), the in-body caption gets its own
    # `status` widget - same split every other migrated list screen here
    # already uses.
    def __prepareSkin(self):
        iconBase = skinchrome.getIconBase()
        HEIGHT = 520
        contentH = HEIGHT - 108 - 64 - 10
        return """
        <screen name="IPTVSubSimpleDownloaderWidget" position="center,center" size="1080,%d" resolution="1280,720" title="%s" backgroundColor="#34111112" flags="wfNoBorder">
            %s
            <widget name="status" position="20,68" size="1040,30" font="Regular;24" halign="left" valign="center" foregroundColor="white" backgroundColor="black" borderWidth="1" borderColor="black" zPosition="1" transparent="1" />
            <widget name="list" position="20,108" size="1040,%d" itemHeight="36" font="Regular;20" scrollbarMode="showOnDemand" scrollbarSliderBorderWidth="1" scrollbarForegroundColor="#1b5a91" scrollbarBorderColor="#00b6b6b6" enableWrapAround="1" foregroundColor="white" backgroundColor="black" foregroundColorSelected="white" backgroundColorSelected="#1b5a91" borderWidth="1" borderColor="black" transparent="1" />
            <widget name="console" position="20,108" size="1040,%d" font="Regular;24" halign="center" valign="center" transparent="0" foregroundColor="white" backgroundColor="black" />
            %s
        </screen>
        """ % (
            HEIGHT,
            _("Simple subtitles downloader"),
            skinchrome.build_header_auto(iconBase=iconBase),
            contentH,
            contentH,
            skinchrome.build_footer_auto(HEIGHT, iconBase=iconBase, keys=('red', 'green')),
        )

    def __init__(self, session, params={}):
        # params: movie_title, sub_list: [{'title':'', 'lang':'', 'url':''}]
        self.session = session
        self.skin = self.__prepareSkin()
        Screen.__init__(self, session)

        self.params = params

        self.onShown.append(self.onStart)
        self.onClose.append(self.__onClose)

        self["status"] = Label(" ")
        self["console"] = Label(" ")

        self._keyLabels = {'red': _("Cancel"), 'green': _("Apply")}
        self["key_red"] = StaticText(self._keyLabels['red'])
        self["key_green"] = StaticText("")

        self["list"] = IPTVMainNavigatorList()
        self["list"].connectSelChanged(self.onSelectionChanged)

        self["actions"] = ActionMap(["ColorActions", "SetupActions"],
            {
                "cancel": self.keyExit,
                "ok": self.keyOK,
                "red": self.keyRed,
                "green": self.keyGreen,
            }, -2)

        self.movieTitle = ''
        self.stackList = []
        self.stackItems = []

        self.defaultLanguage = GetDefaultLang()

        self.listMode = False
        self.downloadedSubFilePath = ""
        self.currItem = {}
        self.downloader = None
        self.cleanDownloader()
        self.workconsole = None

    def __onClose(self):
        self["list"].disconnectSelChanged(self.onSelectionChanged)
        if None is not self.workconsole:
            self.workconsole.kill()
        self.workconsole = None
        self.cleanDownloader()

    def cleanDownloader(self):
        self.downloadedSubFilePath = ""
        self.currItem = {}
        if self.downloader is not None:
            self.downloader.unsubscribeFor_Finish(self.downloadFinished)
            self.downloader.terminate()
        self.downloader = None

    def startDownload(self, item):
        self.setListMode(False)
        self.cleanDownloader()
        self.currItem = item
        self["console"].setText(_("Downloading subtitles.\n ('%r').") % self.currItem.get('url', ''))
        # create downloader
        self.downloader = DownloaderCreator(self.currItem.get('url', ''))
        if self.downloader:
            self.downloader.isWorkingCorrectly(self._startDownloader)
        else:
            self["console"].setText(_("Download can not be started.\n Incorrect address ('%r')."))

    def _startDownloader(self, sts, reason):
        if sts:
            self.downloader.subscribeFor_Finish(self.downloadFinished)
            url, downloaderParams = DMHelper.getDownloaderParamFromUrl(self.currItem.get('url', ''))
            self.downloader.start(url, GetTmpDir(self._TMP_FILE_NAME), downloaderParams)
        else:
            self["console"].setText(_("Download can not be started.\nDownloader %s not working correctly.\nStatus[%s]"))

    def downloadFinished(self, status):
        if status != DMHelper.STS.DOWNLOADED:
            self["console"].setText(_("Download failed.\nStatus[%s]") % status)
        else:
            self["console"].setText(_('Subtitles downloaded successfully. [%s], conversion to UTF-8.') % self.downloader.getFullFileName())
            cmd = '/usr/bin/uchardet "%s"' % self.downloader.getFullFileName()
            printDBG("cmd[%s]" % cmd)
            self.workconsole = iptv_system(cmd, self.convertSubtitles)

    def convertSubtitles(self, code=127, encoding=""):
        encoding = MapUcharEncoding(encoding)
        if 0 != code or 'unknown' in encoding:
            encoding = 'utf-8'
        else:
            encoding = encoding.strip()
        try:
            with codecs.open(self.downloader.getFullFileName(), 'r', encoding, 'replace') as fp:
                subText = ensure_str(fp.read()).strip()

            ext = self.currItem.get('format', '')
            if ext == '':
                ext = self.currItem.get('url', '').split('?')[-1].split('.')[-1]
            filePath = '{0}_{1}_{2}'.format(self.params['movie_title'], self.currItem.get('title', ''), self.currItem.get('lang', ''))
            filePath = RemoveDisallowedFilenameChars(filePath)
            filePath += '.' + ext

            with open(GetSubtitlesDir(filePath), 'w') as fp:
                fp.write(subText)

            self.downloadedSubFilePath = GetSubtitlesDir(filePath)
            self.showButtons(['green'])
            tmpList = self.params.get('sub_list', [])
            if len(tmpList) == 1:
                self.acceptSub()
        except Exception:
            printExc()
            self["console"].setText(_('Subtitles conversion to UTF-8 failed.'))

    def hideButtons(self, buttons=('red', 'green')):
        try:
            for button in buttons:
                self['key_' + button].setText("")
        except Exception:
            printExc()

    def showButtons(self, buttons=('red', 'green')):
        try:
            for button in buttons:
                self['key_' + button].setText(self._keyLabels[button])
        except Exception:
            printExc()

    def onStart(self):
        self.onShown.remove(self.onStart)
        self.setTitle(_("Subtitles for: %s") % self.params.get('movie_title', ''))
        tmpList = self.params.get('sub_list', [])
        if len(tmpList) > 1:
            self.displayList()
        else:
            self.startDownload(tmpList[0])

    def setListMode(self, sts=False):
        if False is sts:
            self['list'].hide()
            self["status"].hide()
            self.hideButtons(('green',))
            self.showButtons(('red',))
            self["console"].show()
            self["console"].setText(" ")
        else:
            self.hideButtons(('green',))
            self["console"].hide()
            self["console"].setText(" ")

        self.listMode = sts

    def displayList(self):
        list = []
        self["status"].setText(_("Select subtitles to download"))
        self["status"].show()

        tmpList = self.params.get('sub_list', [])
        try:
            for item in tmpList:
                printDBG(item)
                dItem = CDisplayListItem(name=item['title'], type=CDisplayListItem.TYPE_ARTICLE)
                dItem.privateData = item
                list.append((dItem,))
        except Exception:
            printExc()
        self["list"].setList(list)
        self["list"].show()
        self.setListMode(True)

    def onSelectionChanged(self):
        pass

    def keyExit(self):
        if False is self.listMode:
            if self.downloader is not None and self.downloader.isDownloading():
                self.downloader.terminate()
            else:
                tmpList = self.params.get('sub_list', [])
                if len(tmpList) > 1:
                    self.displayList()
                else:
                    self.close(None)
        else:
            self.close(None)

    def keyOK(self):
        if False is self.listMode:
            return
        idx, item = self.getSelectedItem()
        if None is not item:
            self.startDownload(item.privateData)

    def keyRed(self):
        self.close(None)

    def keyGreen(self):
        self.acceptSub()

    def acceptSub(self):
        try:
            if self["key_green"].text:
                track = {'title': self.currItem.get('lang', _('default')), 'lang': self.currItem.get('lang', _('default')), 'path': self.downloadedSubFilePath}
                track['id'] = self.currItem.get('url', '')
                self.close(track)
        except Exception:
            printExc()

    def getSelectedItem(self):
        try:
            idx = self["list"].getCurrentIndex()
        except Exception:
            idx = 0
        sel = None
        try:
            if self["list"].visible:
                sel = self["list"].l.getCurrentSelection()[0]
                if None is not sel:
                    return idx, sel
        except Exception:
            printExc()
            sel = None
        return -1, None
