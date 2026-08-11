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
from enigma import eListboxPythonMultiContent, eListbox, gFont, RT_HALIGN_LEFT, RT_VALIGN_CENTER, getDesktop
from Tools.LoadPixmap import LoadPixmap
from skin import parseColor
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
        if fnc not in self.onSelectionChanged:
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
    ICONS_FILESNAMES = {
        CDisplayListItem.TYPE_MARKER: 'MarkerItem.png',
        CDisplayListItem.TYPE_SUB_PROVIDER: 'CategoryItem.png',
        CDisplayListItem.TYPE_SUBTITLE: 'ArticleItem.png',
        CDisplayListItem.TYPE_CATEGORY: 'CategoryItem.png',
        CDisplayListItem.TYPE_MORE: 'MoreItem.png',
        CDisplayListItem.TYPE_VIDEO: 'VideoItem.png',
        CDisplayListItem.TYPE_AUDIO: 'AudioItem.png',
        CDisplayListItem.TYPE_SEARCH: 'SearchItem.png',
        CDisplayListItem.TYPE_ARTICLE: 'ArticleItem.png',
        CDisplayListItem.TYPE_PICTURE: 'PictureItem.png',
        CDisplayListItem.TYPE_DATA: 'DataItem.png',
        CDisplayListItem.TYPE_SEARCH_HISTORY: 'SearchHistoryItem.png',
        CDisplayListItem.TYPE_SEARCH_HISTORY_DELETE: 'SearchHistoryDeleteItem.png',
        CDisplayListItem.TYPE_NEXT: 'NextItem.png',
        CDisplayListItem.TYPE_DOWNLOAD: 'DownloadFolder.png',
        CDisplayListItem.TYPE_MMC: 'MMCItem.png',
        CDisplayListItem.TYPE_USB: 'USBItem.png',
        CDisplayListItem.TYPE_WWW: 'GlobItem.png',
        CDisplayListItem.TYPE_JUMP: 'JumpItem.png',
        CDisplayListItem.TYPE_FIRST: 'FirstItem.png',
        CDisplayListItem.TYPE_PREVIOUS: 'PreviousItem.png',
        CDisplayListItem.TYPE_LAST: 'LastItem.png',
    }

    def __init__(self):
        IPTVListComponentBase.__init__(self)

        self.screenwidth = getDesktop(0).size().width()
        try:
            self.font = skin.fonts["iptvlistitem"]
        except Exception:
            if self.screenwidth and self.screenwidth >= 2560:
                self.font = ("Regular", 45, 55, 0)
            elif self.screenwidth and self.screenwidth == 1920:
                self.font = ("Regular", 28, 40, 0)
            else:
                self.font = ("Regular", 18, 35, 0)
        self.l.setFont(0, gFont("Regular", 40))
        self.l.setFont(1, gFont(self.font[0], self.font[1]))
        self.l.setItemHeight(self.font[2])
        self.dictPIX = {}
        self.watchedBadgePIX = None
        self.startedBadgePIX = None

    def _nullPIX(self):
        for key in self.ICONS_FILESNAMES:
            self.dictPIX[key] = None
        self.watchedBadgePIX = None
        self.startedBadgePIX = None

    def onCreate(self):
        self._nullPIX()
        for key in self.dictPIX:
            try:
                pixFile = self.ICONS_FILESNAMES.get(key, None)
                if None is not pixFile:
                    self.dictPIX[key] = LoadPixmap(cached=True, path=GetIconDir(pixFile))
            except Exception:
                printExc()
        # 32x32 watched/started overlay, centered on top of the item icon; if the
        # files aren't present LoadPixmap just leaves these None and buildEntry()
        # below skips them, so the item simply shows no watched/started indicator
        try:
            self.watchedBadgePIX = LoadPixmap(cached=True, path=GetIconDir('WatchedBadge.png'))
        except Exception:
            self.watchedBadgePIX = None
        try:
            self.startedBadgePIX = LoadPixmap(cached=True, path=GetIconDir('StartedBadge.png'))
        except Exception:
            self.startedBadgePIX = None

    def onDestroy(self):
        self._nullPIX()

    # item icon box (imageType pixmap) and the watched/started overlay drawn on top of
    # it - the overlay is designed to sit centered directly over the icon, not as a
    # small corner badge
    ICON_X, ICON_Y, ICON_W, ICON_H = 3, 1, 40, 40
    BADGE_W, BADGE_H = 32, 32
    BADGE_X = ICON_X + (ICON_W - BADGE_W) // 2
    BADGE_Y = ICON_Y + (ICON_H - BADGE_H) // 2

    def buildEntry(self, item):
        width = self.l.getItemSize().width()
        height = self.l.getItemSize().height()
        res = [None]
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 45, 0, width - 45, height, 1, RT_HALIGN_LEFT | RT_VALIGN_CENTER, item.getDisplayTitle(), item.getTextColor()))
        res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHABLEND, self.ICON_X, self.ICON_Y, self.ICON_W, self.ICON_H, self.dictPIX.get(item.imageType, None)))
        if getattr(item, 'isWatched', False) and self.watchedBadgePIX is not None:
            res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHABLEND, self.BADGE_X, self.BADGE_Y, self.BADGE_W, self.BADGE_H, self.watchedBadgePIX))
        elif getattr(item, 'isStarted', False) and self.startedBadgePIX is not None:
            res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHABLEND, self.BADGE_X, self.BADGE_Y, self.BADGE_W, self.BADGE_H, self.startedBadgePIX))
        return res


class IPTVRadioButtonList(IPTVMainNavigatorList):
    ICONS_FILESNAMES = {'on': 'radio_button_on.png', 'off': 'radio_button_off.png'}
    FAILED_TEXT_COLOR = "#FF4040"
    ERROR_BADGE_W, ERROR_BADGE_H = 32, 32

    def __init__(self):
        IPTVMainNavigatorList.__init__(self)
        self.errorBadgePIX = None

    def onCreate(self):
        IPTVMainNavigatorList.onCreate(self)
        try:
            self.errorBadgePIX = LoadPixmap(cached=True, path=GetIconDir('ErrorBadge.png'))
        except Exception:
            self.errorBadgePIX = None

    def onDestroy(self):
        IPTVMainNavigatorList.onDestroy(self)
        self.errorBadgePIX = None

    def buildEntry(self, item):
        width = self.l.getItemSize().width()
        height = self.l.getItemSize().height()
        pixmap_y = (height - 16) // 2
        res = [None]
        if None is item.type:
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 5, 0, width - 5, height, 1, RT_HALIGN_LEFT | RT_VALIGN_CENTER, item.name))
        else:
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 30, 0, width - 30, height, 1, RT_HALIGN_LEFT | RT_VALIGN_CENTER, item.name))
            res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHABLEND, 3, pixmap_y, 16, 16, self.dictPIX.get(item.type, None)))
        return res


class IPTVLinkChoiceBoxList(IPTVRadioButtonList):
    # used for the "Select link" mirror picker: always shows the regular link
    # icon (same spot/size as the main list's item icon) with the error badge
    # overlaid centered on top of it when that mirror failed to resolve - same
    # overlay pattern as the watched/started badge in IPTVMainNavigatorList
    LINK_ICON_FILENAME = 'GlobItem.png'

    def __init__(self):
        IPTVRadioButtonList.__init__(self)
        self.linkIconPIX = None

    def onCreate(self):
        IPTVRadioButtonList.onCreate(self)
        try:
            self.linkIconPIX = LoadPixmap(cached=True, path=GetIconDir(self.LINK_ICON_FILENAME))
        except Exception:
            self.linkIconPIX = None

    def onDestroy(self):
        IPTVRadioButtonList.onDestroy(self)
        self.linkIconPIX = None

    def buildEntry(self, item):
        width = self.l.getItemSize().width()
        height = self.l.getItemSize().height()
        failed = getattr(item, 'failed', False)
        textX = self.ICON_X + self.ICON_W + 5
        textArgs = (eListboxPythonMultiContent.TYPE_TEXT, textX, 0, width - textX, height, 1, RT_HALIGN_LEFT | RT_VALIGN_CENTER, item.name)
        if failed:
            try:
                textArgs = textArgs + (parseColor(self.FAILED_TEXT_COLOR).argb(),)
            except Exception:
                pass
        res = [None, textArgs]
        if self.linkIconPIX is not None:
            res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHABLEND, self.ICON_X, self.ICON_Y, self.ICON_W, self.ICON_H, self.linkIconPIX))
        if failed and self.errorBadgePIX is not None:
            res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHABLEND, self.BADGE_X, self.BADGE_Y, self.BADGE_W, self.BADGE_H, self.errorBadgePIX))
        return res
