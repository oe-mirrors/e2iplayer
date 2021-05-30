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
from Plugins.Extensions.IPTVPlayer.components.ihost import ArticleContent
from Plugins.Extensions.IPTVPlayer.components.cover import SimpleAnimatedCover, Cover
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir, eConnectCallback
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdownloadercreator import DownloaderCreator
from Plugins.Extensions.IPTVPlayer.components.cover import Cover, Cover3
###################################################

###################################################
# FOREIGN import
###################################################
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from enigma import getDesktop, eTimer, ePoint
from Components.ActionMap import ActionMap, HelpableActionMap
from Components.Label import Label
from Components.ScrollLabel import ScrollLabel
from Tools.Directories import fileExists
import os
from Tools.LoadPixmap import LoadPixmap
###################################################


class IPTVArticleRichVisualizer(Screen):
    MAX_RICH_DESC_ROW_NUM = 5

    def __prepareSkin(self):
        skin = """
                    <screen name="IPTVArticleRichVisualizerWidget" position="center,center" size="1050,625" title="Info...">
                        <widget name="title" position="5,10"  zPosition="1" size="1040,70"  font="Regular;30" halign="center" valign="center"   transparent="1" backgroundColor="transparent" foregroundColor="#000E83F5" shadowColor="black" shadowOffset="-1,-1" />
                        <widget name="cover"     zPosition="1" position="10,110"  size="236,357" alphatest="blend" borderWidth="2" borderColor="white" backgroundColor="black" />
                        <widget name="spinner"   zPosition="3" position="98,232"  size="16,16"   transparent="1"  alphatest="blend" />
                        <widget name="spinner_1" zPosition="2" position="98,232"  size="16,16"   transparent="1"  alphatest="blend" />
                        <widget name="spinner_2" zPosition="2" position="114,232" size="16,16"   transparent="1"  alphatest="blend" />
                        <widget name="spinner_3" zPosition="2" position="130,232" size="16,16"   transparent="1"  alphatest="blend" />
                        <widget name="spinner_4" zPosition="2" position="146,232" size="16,16"   transparent="1"  alphatest="blend" />
                """
        # adds rows items
        self.richDesc['row_label_x'] = 260
        self.richDesc['row_label_w'] = 190
        self.richDesc['row_text_x'] = 455
        self.richDesc['row_text_w'] = 590
        self.richDesc['row_y'] = 110
        self.richDesc['row_h'] = 30

        y = self.richDesc['row_y']
        for idx in range(self.richDesc['rows_count']):
            skin += """<widget name="dsc_label_%d" noWrap="1" position="%d,%d"  zPosition="1" size="%d,%d"  font="Regular;20" halign="right" valign="center"   transparent="1" backgroundColor="transparent" foregroundColor="#000E83F5" shadowColor="black" shadowOffset="-1,-1" />""" % (idx + 1, self.richDesc['row_label_x'], y, self.richDesc['row_label_w'], self.richDesc['row_h'])
            skin += """<widget name="dsc_text_%d"  noWrap="1" position="%d,%d"  zPosition="1" size="%d,%d"  font="Regular;20" halign="left"  valign="center"   transparent="1" backgroundColor="transparent" foregroundColor="#00EFEFEF" shadowColor="black" shadowOffset="-1,-1" />""" % (idx + 1, self.richDesc['row_text_x'], y, self.richDesc['row_text_w'], self.richDesc['row_h'])
            y += self.richDesc['row_h']
        if y != self.richDesc['row_y']:
            y += self.richDesc['row_h']
        skin += """<widget name="text"        position="260,%d" zPosition="1" size="780,%d" font="Regular;26" halign="left"  valign="top"      transparent="1" backgroundColor="transparent" foregroundColor="#00EFEFEF" />""" % (y, 625 - y - 5)

        # adds pagination items
        if self.richDesc['pages_count'] > 1:
            x1 = self.richDesc['row_label_x']
            x2 = self.richDesc['row_text_x'] + self.richDesc['row_text_w'] - self.richDesc['row_label_x']

            self.richDesc['page_item_size'] = 16
            self.richDesc['page_item_start_x'] = x1 + (x2 - x1 - (self.richDesc['page_item_size'] * self.richDesc['pages_count'])) / 2
            self.richDesc['page_item_start_y'] = self.richDesc['row_y'] - 20

            for idx in range(self.richDesc['pages_count']):
                pageItemX = self.richDesc['page_item_start_x'] + idx * self.richDesc['page_item_size']
                if 0 == idx:
                    skin += """<widget name="page_marker" zPosition="3" position="%d,%d" size="%d,%d" transparent="1" alphatest="blend" />""" % (pageItemX, self.richDesc['page_item_start_y'], self.richDesc['page_item_size'], self.richDesc['page_item_size'])
                skin += """<ePixmap zPosition="2" position="%d,%d" size="%d,%d" pixmap="%s" transparent="1" alphatest="blend" />\n""" % (pageItemX, self.richDesc['page_item_start_y'], self.richDesc['page_item_size'], self.richDesc['page_item_size'], GetIconDir('radio_button_off.png'))
        skin += '</screen>'
        self.skin = skin
        self.skinName = "IPTVArticleRichVisualizerWidget"

    def __init__(self, session, artItem, addParams):
        self.session = session
        self.artItem = artItem

        #############################################
        # calculate num of rich desc items and pages
        #############################################
        self.richDesc = {'items_count': 0, 'pages_count': 0, 'page': 0, 'avalable_params': []}
        try:
            if 'custom_items_list' in artItem.richDescParams:
                self.richDesc['custom_items_list'] = artItem.richDescParams['custom_items_list']
                self.richDesc['items_count'] = len(self.richDesc['custom_items_list'])
            else:
                for item in ArticleContent.RICH_DESC_PARAMS:
                    if item in artItem.richDescParams:
                        self.richDesc['items_count'] += 1
                        self.richDesc['avalable_params'].append(item)
                # yes I know, len(self.richDesc['avalable_params']) == self.richDesc['items_count']
        except Exception:
            printExc()

        self.richDesc['pages_count'] = self.richDesc['items_count'] / self.MAX_RICH_DESC_ROW_NUM
        if self.richDesc['items_count'] % self.MAX_RICH_DESC_ROW_NUM > 0:
            self.richDesc['pages_count'] += 1
        if self.richDesc['items_count'] < self.MAX_RICH_DESC_ROW_NUM:
            self.richDesc['rows_count'] = self.richDesc['items_count']
        else:
            self.richDesc['rows_count'] = self.MAX_RICH_DESC_ROW_NUM
        #############################################

        self.__prepareSkin()
        Screen.__init__(self, session)

        for idx in range(self.richDesc['rows_count']):
            self["dsc_label_{0}".format(idx + 1)] = Label("")
            self["dsc_text_{0}".format(idx + 1)] = Label("")

        self["title"] = Label("")
        self["text"] = ScrollLabel(" ")
        self["page_marker"] = Cover3()
        #############################################
        # COVER
        #############################################
        self["cover"] = Cover()
        self.cover = {'src': '', 'downloader': None, 'files_to_remove': [], 'image_path': ''}
        try:
            self.cover['image_path'] = os.path.join(addParams['buffering_path'], '.iptv_buffering.jpg')
        except Exception:
            printExc()
        #############################################

        #############################################
        # SPINER
        #############################################
        try:
            for idx in range(5):
                spinnerName = "spinner"
                if idx:
                    spinnerName += '_%d' % idx
                self[spinnerName] = Cover3()
        except Exception:
            printExc()
        self.spinner = {}
        self.spinner["pixmap"] = [LoadPixmap(GetIconDir('radio_button_on.png')), LoadPixmap(GetIconDir('radio_button_off.png'))]
        # spinner timer
        self.spinner["timer"] = eTimer()
        self.spinner["timer_conn"] = eConnectCallback(self.spinner["timer"].timeout, self.updateSpinner)
        self.spinner["timer_interval"] = 200
        self.spinner["enabled"] = False
        #############################################

        self["actions"] = ActionMap(['IPTVAlternateVideoPlayer', 'MoviePlayerActions', 'MediaPlayerActions', 'WizardActions', 'DirectionActions'],
        {
            "ok": self.key_ok,
            "back": self.key_back,
            "left": self.key_left,
            "right": self.key_right,
            "up": self.key_up,
            "down": self.key_down,
        }, -1)

        self.onClose.append(self.__onClose)
        #self.onShow.append(self.onStart)
        self.onLayoutFinish.append(self.onStart)

    #end def __init__(self, session):

    def __del__(self):
        printDBG('IPTVArticleRichVisualizer.__del__ --------------------------------------')

    def __onClose(self):
        printDBG('IPTVArticleRichVisualizer.__onClose ------------------------------------')
        self.onClose.remove(self.__onClose)
        self.onEnd()
        self.hideSpinner()
        self.spinner["timer"] = None
        self.spinner["timer_conn"] = None

    def onStart(self):
        self.onLayoutFinish.remove(self.onStart)
        self.loadSpinner()
        self["page_marker"].setPixmap(self.spinner["pixmap"][0]) # the same png file is used by page_maker as spinner
        #self.setTitle(self.artItem.title)
        self["title"].setText(self.artItem.title)
        self.setText()
        self.setRichDesc()
        self.hideSpinner()
        self.loadCover()

    #############################################
    # COVER
    #############################################
    def loadCover(self):
        self["cover"].hide()
        if 0 == len(self.artItem.images):
            return
        self.cover['src'] = self.artItem.images[0].get('url', '')
        if not self.cover['src'].startswith('http'):
            return

        self.cover['downloader'] = DownloaderCreator(self.cover['src'])
        if self.cover['downloader']:
            self.cover['downloader'].isWorkingCorrectly(self.startDownloader)
        else:
            self.session.openWithCallback(self.close, MessageBox, _("Downloading cannot be started.\n Invalid URI[%s].") % self.cover['src'], type=MessageBox.TYPE_ERROR, timeout=10)

    def startDownloader(self, sts, reason):
        if sts:
            url, downloaderParams = DMHelper.getDownloaderParamFromUrl(self.cover['src'])
            self.cover['downloader'] .subscribeFor_Finish(self.downloaderEnd)
            self.cover['downloader'] .start(url, self._getDownloadFilePath(), downloaderParams)
            self.showSpinner()
        else:
            self.session.openWithCallback(self.close, MessageBox, _("Downloading cannot be started.\n Downloader [%s] not working properly.\n Status[%s]") % (self.cover['downloader'].getName(), reason.strip()), type=MessageBox.TYPE_ERROR, timeout=10)

    def _getDownloadFilePath(self):
        self.cover['files_to_remove'].append(self.cover['image_path'])
        return self.cover['image_path']

    def downloaderEnd(self, status):
        if None != self.cover['downloader']:
            if DMHelper.STS.DOWNLOADED == status:
                if self["cover"].decodeCover(self._getDownloadFilePath(), self.decodePictureEnd, ' '):
                    return
            else:
                self.session.open(MessageBox, (_("Downloading file [%s] problem.") % self.cover['src']) + (" sts[%r]" % status), type=MessageBox.TYPE_ERROR, timeout=10)
        self.hideSpinner()

    def decodePictureEnd(self, ret={}):
        if None == ret.get('Pixmap', None):
            self.session.openWithCallback(self.close, MessageBox, _("Downloading file [%s] problem.") % self._getDownloadFilePath(), type=MessageBox.TYPE_ERROR, timeout=10)
        else:
            self["cover"].updatePixmap(ret.get('Pixmap', None), ret.get('FileName', self._getDownloadFilePath()))
            self["cover"].show()
        self.hideSpinner()

    def onEnd(self):
        if self.cover['downloader']:
            self.cover['downloader'].unsubscribeFor_Finish(self.downloaderEnd)
            downloader = self.cover['downloader']
            self.downloader = None
            downloader.terminate()
            downloader = None

        for filePath in self.cover['files_to_remove']:
            if fileExists(filePath):
                try:
                    os.remove(filePath)
                except Exception:
                    printDBG('Problem with removing old buffering file')
    #################################################

    #######################################################################
    # SPINER
    #######################################################################
    def loadSpinner(self):
        try:
            if "spinner" in self:
                self["spinner"].setPixmap(self.spinner["pixmap"][0])
                for idx in range(4):
                    spinnerName = 'spinner_%d' % (idx + 1)
                    self[spinnerName].setPixmap(self.spinner["pixmap"][1])
        except Exception:
            printExc()

    def showSpinner(self):
        if None != self.spinner["timer"]:
            self._setSpinnerVisibility(True)
            self.spinner["timer"].start(self.spinner["timer_interval"], True)

    def hideSpinner(self):
        self._setSpinnerVisibility(False)

    def _setSpinnerVisibility(self, visible=True):
        self.spinner["enabled"] = visible
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
            if self.spinner["enabled"]:
                if "spinner" in self:
                    x, y = self["spinner"].getPosition()
                    x += self["spinner"].getWidth()
                    if x > self["spinner_4"].getPosition()[0]:
                        x = self["spinner_1"].getPosition()[0]
                    self["spinner"].setPosition(x, y)
                if None != self.spinner["timer"]:
                    self.spinner["timer"].start(self.spinner["timer_interval"], True)
                    return
            self.hideSpinner()
        except Exception:
            printExc()
    #######################################################################

    #######################################################################
    # RICH DESC HANDLING
    #######################################################################
    def setText(self):
        self["text"].setText(self.artItem.text.replace('[/br]', '\n'))

    def setRichDesc(self):
        printDBG("IPTVArticleRichVisualizer.setRichDesc")
        if 0 == self.richDesc['items_count']:
            return
        firstIdx = self.richDesc['rows_count'] * self.richDesc['page']
        if firstIdx >= self.richDesc['items_count']:
            return

        printDBG("IPTVArticleRichVisualizer.setRichDesc firstIdx[%d]" % firstIdx)
        try:
            if 'custom_items_list' in self.richDesc:
                params = self.richDesc['custom_items_list'][firstIdx:]
                for idx in range(self.richDesc['rows_count']):
                    if idx < len(params):
                        label = str(params[idx][0])
                        text = str(params[idx][1])
                    else:
                        label = " "
                        text = " "
                    self["dsc_label_{0}".format(idx + 1)].setText(label)
                    self["dsc_text_{0}".format(idx + 1)].setText(text)
            else:
                params = self.richDesc['avalable_params'][firstIdx:]
                for idx in range(self.richDesc['rows_count']):
                    if idx < len(params):
                        label = _(ArticleContent.RICH_DESC_LABELS[params[idx]]) # we call _() to translate label
                        text = self.artItem.richDescParams[params[idx]]
                    else:
                        label = " "
                        text = " "
                    self["dsc_label_{0}".format(idx + 1)].setText(label)
                    self["dsc_text_{0}".format(idx + 1)].setText(text)
        except Exception:
            printExc()

    def newPage(self, page):
        if page != self.richDesc['page'] and 'page_item_start_x' in self.richDesc and 'page_item_start_y' in self.richDesc:
            self.richDesc['page'] = page
            self.setRichDesc()

            x = self.richDesc['page_item_start_x'] + page * self.richDesc['page_item_size']
            y = self.richDesc['page_item_start_y']
            self["page_marker"].instance.move(ePoint(x, y))

    def nextRichDescPage(self):
        page = self.richDesc['page']
        page += 1
        if page >= self.richDesc['pages_count']:
            page = 0
        self.newPage(page)

    def prevRichDescPage(self):
        page = self.richDesc['page']
        page -= 1
        if page < 0:
            page = self.richDesc['pages_count'] - 1
        self.newPage(page)

    #######################################################################

    def key_ok(self):
        self.showSpinner()
        pass

    def key_back(self):
        self.close()

    def key_left(self):
        self.prevRichDescPage()

    def key_right(self):
        self.nextRichDescPage()

    def key_up(self):
        self["text"].pageUp()

    def key_down(self):
        self["text"].pageDown()
