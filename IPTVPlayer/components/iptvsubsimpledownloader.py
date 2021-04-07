# -*- coding: utf-8 -*-
#

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetDefaultLang, GetTmpDir, GetSubtitlesDir, GetIconDir, RemoveDisallowedFilenameChars, iptv_system, MapUcharEncoding
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CDisplayListItem
from Plugins.Extensions.IPTVPlayer.components.iptvlist import IPTVMainNavigatorList
from Plugins.Extensions.IPTVPlayer.components.cover import Cover3

from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdownloadercreator import DownloaderCreator
###################################################

###################################################
# FOREIGN import
###################################################
from enigma import getDesktop
from Screens.Screen import Screen
from Components.Label import Label
from Components.ActionMap import ActionMap
from Tools.LoadPixmap import LoadPixmap
from Tools.BoundFunction import boundFunction
from Components.config import config

import codecs
###################################################


class IPTVSubSimpleDownloaderWidget(Screen):
    _TMP_FILE_NAME = '.externaltmpsub'
    sz_w = getDesktop(0).size().width() - 190
    sz_h = getDesktop(0).size().height() - 195
    if sz_h < 500:
        sz_h += 4
    skin = """
        <screen name="IPTVSubSimpleDownloaderWidget" position="center,center" title="%s" size="%d,%d">
         <widget name="icon_red"    position="5,9"   zPosition="4" size="30,30" transparent="1" alphatest="on" />
         <widget name="icon_green"  position="355,9" zPosition="4" size="30,30" transparent="1" alphatest="on" />
         
         <widget name="label_red"     position="45,9"  size="175,27" zPosition="5" valign="center" halign="left" backgroundColor="black" font="Regular;21" transparent="1" foregroundColor="white" shadowColor="black" shadowOffset="-1,-1" />
         <widget name="label_green"   position="395,9" size="175,27" zPosition="5" valign="center" halign="left" backgroundColor="black" font="Regular;21" transparent="1" foregroundColor="white" shadowColor="black" shadowOffset="-1,-1" />
         
         <widget name="list"  position="5,80"  zPosition="2" size="%d,%d" scrollbarMode="showOnDemand" transparent="1"  backgroundColor="#00000000" enableWrapAround="1" />
         <widget name="title" position="5,47"  zPosition="1" size="%d,23" font="Regular;20"            transparent="1"  backgroundColor="#00000000"/>
         
         <widget name="console"      position="10,%d"   zPosition="2" size="%d,160" valign="center" halign="center"   font="Regular;24" transparent="0" foregroundColor="white" backgroundColor="black"/>
        </screen>""" % (
            _("Simple subtitles downloader"),
            sz_w, sz_h, # size
            sz_w - 10, sz_h - 105, # size list
            sz_w - 135, # size title
            (sz_h - 160) / 2, sz_w - 20, # console
            )
    
    def __init__(self, session, params={}):
        # params: movie_title, sub_list: [{'title':'', 'lang':'', 'url':''}]
        self.session = session
        Screen.__init__(self, session)
        
        self.params = params
        
        self.onShown.append(self.onStart)
        self.onClose.append(self.__onClose)
        
        self["title"] = Label(" ")
        self["console"] = Label(" ")
        
        self["label_red"] = Label(_("Cancel"))
        self["label_yellow"] = Label(_("Move group"))
        self["label_green"] = Label(_("Apply"))
        
        self["icon_red"] = Cover3()
        self["icon_green"] = Cover3()
        
        self["list"] = IPTVMainNavigatorList()
        self["list"].connectSelChanged(self.onSelectionChanged)
        
        self["actions"] = ActionMap(["ColorActions", "SetupActions", "WizardActions", "ListboxActions"],
            {
                "cancel": self.keyExit,
                "ok": self.keyOK,
                "red": self.keyRed,
                "green": self.keyGreen,
            }, -2)
        
        self.iconPixmap = {}
        for icon in ['red', 'green']:
            self.iconPixmap[icon] = LoadPixmap(GetIconDir(icon + '.png'))
            
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
        if None != self.workconsole:
            self.workconsole.kill()
        self.workconsole = None
        self.cleanDownloader()
        
    def cleanDownloader(self):
        self.downloadedSubFilePath = ""
        self.currItem = {}
        if self.downloader != None:
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
            cmd = '%s "%s"' % (config.plugins.iptvplayer.uchardetpath.value, self.downloader.getFullFileName()) 
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
                subText = fp.read().encode('utf-8').strip()
            
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
    
    def loadIcons(self):
        try:
            for icon in self.iconPixmap:
                self['icon_' + icon].setPixmap(self.iconPixmap[icon])
        except Exception:
            printExc()
        
    def hideButtons(self, buttons=['red', 'green']):
        try:
            for button in buttons:
                self['icon_' + button].hide()
                self['label_' + button].hide()
        except Exception:
            printExc()
        
    def showButtons(self, buttons=['red', 'green']):
        try:
            for button in buttons:
                self['icon_' + button].show()
                self['label_' + button].show()
        except Exception:
            printExc()
    
    def onStart(self):
        self.onShown.remove(self.onStart)
        self.setTitle(_("Subtitles for: %s") % self.params.get('movie_title', ''))
        self.loadIcons()
        tmpList = self.params.get('sub_list', [])
        if len(tmpList) > 1:
            self.displayList()
        else:   
            self.startDownload(tmpList[0])
    
    def setListMode(self, sts=False):
        if False == sts:
            self['list'].hide()
            self["title"].hide()
            self.hideButtons()
            self.showButtons(['red'])
            self["console"].show()
            self["console"].setText(" ")
        else:
            self.hideButtons(['green'])
            self["console"].hide()
            self["console"].setText(" ")
            
        self.listMode = sts
    
    def displayList(self):
        list = []
        self["title"].setText(_("Select subtitles to download"))
        self["title"].show()
        
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
        if False == self.listMode:
            if self.downloader != None and self.downloader.isDownloading():
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
        if False == self.listMode:
            return
        idx, item = self.getSelectedItem()
        if None != item:
            self.startDownload(item.privateData)
            
    def keyRed(self):
        self.close(None)
        
    def keyGreen(self):
        self.acceptSub()
    
    def acceptSub(self):
        try: 
            if self["icon_green"].visible:
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
                if None != sel:
                    return idx, sel
        except Exception: 
            printExc()
            sel = None
        return -1, None

    
