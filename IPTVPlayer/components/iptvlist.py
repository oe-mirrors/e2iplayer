# -*- coding: utf-8 -*-
#
#  IPTV List Component
#
#  $Id$
#
#
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir, eConnectCallback
from Plugins.Extensions.IPTVPlayer.components.ihost import CDisplayListItem
###################################################

###################################################
# FOREIGN import
###################################################
from Components.GUIComponent import GUIComponent
from enigma import eListboxPythonMultiContent, eListbox, gFont, RT_HALIGN_LEFT, RT_HALIGN_RIGHT, RT_VALIGN_CENTER, getDesktop
from Tools.LoadPixmap import LoadPixmap
import skin
###################################################


class IPTVListComponentBase(GUIComponent, object):
    def __init__(self):
        printDBG("IPTVListComponent.__init__ ----------------------------------------------------")
        GUIComponent.__init__(self)
        self.l = eListboxPythonMultiContent()
        self.l.setBuildFunc(self.buildEntry)
        self.onSelectionChanged = []

    def __del__(self):
        printDBG("IPTVListComponent.__del__ ----------------------------------------------------")

    def onCreate(self):
        ''' Should be implemented in the derived class '''
        printExc("IPTVListComponentBase.onCreate should be overwritten in the derived class")

    def onDestroy(self):
        ''' Should be implemented in the derived class '''
        printExc("IPTVListComponentBase.onDestroy should be overwritten in the derived class")

    def buildEntry(self, item):
        ''' Must be implemented in the derived class!!! '''
        raise Exception("IPTVListComponentBase.buildEntry must be overwritten in the derived class!")

    def connectSelChanged(self, fnc):
        if not fnc in self.onSelectionChanged:
            self.onSelectionChanged.append(fnc)

    def disconnectSelChanged(self, fnc):
        if fnc in self.onSelectionChanged:
            self.onSelectionChanged.remove(fnc)

    def selectionChanged(self):
        for x in self.onSelectionChanged:
            x()

    def getCurrent(self):
        cur = self.l.getCurrentSelection()
        return cur and cur[0]

    def postWidgetCreate(self, instance):
        instance.setContent(self.l)
        self.selectionChanged_conn = eConnectCallback(instance.selectionChanged, self.selectionChanged)
        self.onCreate()

    def preWidgetRemove(self, instance):
        instance.setContent(None)
        self.selectionChanged_conn = None
        self.onDestroy()

    def moveToIndex(self, index):
        self.instance.moveSelectionTo(index)

    def getCurrentIndex(self):
        return self.instance.getCurrentIndex()

    def setList(self, list):
        self.l.setList(list)

    def setSelectionState(self, enabled):
        self.instance.setSelectionEnable(enabled)

    GUI_WIDGET = eListbox
    currentIndex = property(getCurrentIndex, moveToIndex)
    currentSelection = property(getCurrent)


class IPTVMainNavigatorList(IPTVListComponentBase):
    ICONS_FILESNAMES = {CDisplayListItem.TYPE_MARKER: 'MarkerItem.png', CDisplayListItem.TYPE_SUB_PROVIDER: 'CategoryItem.png', CDisplayListItem.TYPE_SUBTITLE: 'ArticleItem.png', CDisplayListItem.TYPE_CATEGORY: 'CategoryItem.png', CDisplayListItem.TYPE_MORE: 'MoreItem.png', CDisplayListItem.TYPE_VIDEO: 'VideoItem.png', CDisplayListItem.TYPE_AUDIO: 'AudioItem.png', CDisplayListItem.TYPE_SEARCH: 'SearchItem.png', CDisplayListItem.TYPE_ARTICLE: 'ArticleItem.png', CDisplayListItem.TYPE_PICTURE: 'PictureItem.png', CDisplayListItem.TYPE_DATA: 'DataItem.png'}

    def __init__(self):
        IPTVListComponentBase.__init__(self)

        self.screenwidth = getDesktop(0).size().width()
        try:
            self.font = skin.fonts["iptvlistitem"]
        except Exception:
            if self.screenwidth and self.screenwidth == 1920:
                self.font = ("Regular", 28, 40, 0)
            else:
                self.font = ("Regular", 18, 35, 0)
        self.l.setFont(0, gFont("Regular", 40))
        self.l.setFont(1, gFont(self.font[0], self.font[1]))
        self.l.setItemHeight(self.font[2])
        self.dictPIX = {}

    def _nullPIX(self):
        for key in self.ICONS_FILESNAMES:
            self.dictPIX[key] = None

    def onCreate(self):
        self._nullPIX()
        for key in self.dictPIX:
            try:
                pixFile = self.ICONS_FILESNAMES.get(key, None)
                if None != pixFile:
                    self.dictPIX[key] = LoadPixmap(cached=True, path=GetIconDir(pixFile))
            except Exception:
                printExc()

    def onDestroy(self):
        self._nullPIX()

    def buildEntry(self, item):
        width = self.l.getItemSize().width()
        height = self.l.getItemSize().height()
        res = [None]
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 45, 0, width - 45, height, 1, RT_HALIGN_LEFT | RT_VALIGN_CENTER, item.getDisplayTitle(), item.getTextColor()))
        res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHABLEND, 3, 1, 40, 40, self.dictPIX.get(item.type, None)))
        return res


class IPTVRadioButtonList(IPTVMainNavigatorList):
    ICONS_FILESNAMES = {'on': 'radio_button_on.png', 'off': 'radio_button_off.png'}

    def __init__(self):
        IPTVMainNavigatorList.__init__(self)

    def buildEntry(self, item):
        width = self.l.getItemSize().width()
        height = self.l.getItemSize().height()
        pixmap_y = (height - 16) / 2
        res = [None]
        if None == item.type:
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 5, 0, width - 5, height, 1, RT_HALIGN_LEFT | RT_VALIGN_CENTER, item.name))
        else:
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 30, 0, width - 30, height, 1, RT_HALIGN_LEFT | RT_VALIGN_CENTER, item.name))
            res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHABLEND, 3, pixmap_y, 16, 16, self.dictPIX.get(item.type, None)))
        return res
