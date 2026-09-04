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
from Components.MultiContent import MultiContentEntryPixmapAlphaBlend
from enigma import eListboxPythonMultiContent, eListbox, gFont, RT_HALIGN_LEFT, RT_VALIGN_CENTER, getDesktop, BT_SCALE
from Tools.LoadPixmap import LoadPixmap
from skin import parseColor
import skin
###################################################


def fitPixmapInBox(icon, boxX, boxY, boxW, boxH):
    # shared by every buildEntry() in this file (and E2iVKOptionsList in
    # e2ivk.py, which already depended on this module for
    # IPTVListComponentBase) that draws a fixed-size icon box via
    # MultiContentEntryPixmapAlphaBlend(flags=BT_SCALE) - BT_SCALE alone
    # stretches the source pixmap to fill (boxW, boxH) exactly regardless
    # of its own aspect ratio, which visibly squishes any icon whose
    # native size isn't already the same ratio as the box - e.g.
    # E2iVKOptionsList's Options/Help screens, which mix wide 40x26 icons
    # with square 32x32/26x26 ones in the same box. Returns (x, y, w, h)
    # for a fit-within-box size computed
    # from the icon's own native dimensions instead, centered in
    # (boxX, boxY, boxW, boxH) - an icon whose native size already
    # matches the box's aspect ratio is unaffected (scale factor 1.0,
    # same pixels as a plain stretch would produce), everything else
    # renders as a true, unstretched fit instead. Falls back to the box
    # unchanged (same pixels a plain BT_SCALE stretch would draw) if icon
    # is None or its size can't be read for any reason.
    fitW, fitH = boxW, boxH
    try:
        srcSize = icon.size()
        srcW, srcH = srcSize.width(), srcSize.height()
        if srcW > 0 and srcH > 0:
            scale = min(boxW / float(srcW), boxH / float(srcH))
            fitW, fitH = int(srcW * scale), int(srcH * scale)
    except Exception:
        pass
    x = boxX + (boxW - fitW) // 2
    y = boxY + (boxH - fitH) // 2
    return x, y, fitW, fitH


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
        CDisplayListItem.TYPE_SEARCH_HISTORY_EDITOR: 'SearchHistoryEditorItem.png',
        CDisplayListItem.TYPE_SEARCH_HISTORY_DELETE: 'SearchHistoryDeleteItem.png',
        CDisplayListItem.TYPE_NEXT: 'NextItem.png',
        CDisplayListItem.TYPE_DOWNLOAD: 'DownloadFolderItem.png',
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

        # item icon box (imageType pixmap) and the watched/started overlay
        # drawn on top of it, sized to the row's own itemHeight instead of
        # a fixed 40x40 at every tier - so the icon scales together with
        # the surrounding text/row at FHD/WQHD instead of staying the
        # same absolute size. Derived from self.font[2] (itemHeight)
        # rather than a screenwidth tier lookup so a custom
        # skin.fonts["iptvlistitem"] override (see the try/except above)
        # scales proportionally too, not just the three HD/FHD/WQHD
        # fallback values. itemHeight itself is intentionally NOT part of
        # this change - it's tuned for text and shared by every screen
        # that uses this list (main navigator, sub-downloader, favourites,
        # ...), so changing it would shift how many rows fit on screen
        # everywhere, not just make room for a bigger icon.
        itemHeight = self.font[2]
        self.ICON_X = 3
        self.ICON_W = self.ICON_H = max(itemHeight - 4, 16)
        self.ICON_Y = (itemHeight - self.ICON_H) // 2
        # WatchedBadge/StartedBadge/ErrorBadge/CheckBadge.png are all
        # "corner badge" designs whose actual visible circle only fills
        # ~14 of their own 32x32 canvas
        # (measured), so even though this box scales correctly at every
        # tier, the rendered circle only ever works out to ~35% of the
        # icon's own size - looked fine at HD but reads as too small once
        # the icon itself is visibly bigger at WQHD. 1.1 (badge box
        # slightly LARGER than the icon box, still centered on it) brings
        # the visible circle to ~48% of the icon's size instead - checked
        # BADGE_X stays >= 0 at every tier (HD 1, FHD 1, WQHD 0), so the
        # box never runs off the row's left edge.
        self.BADGE_W = self.BADGE_H = max(int(round(self.ICON_W * 1.1)), 12)
        self.BADGE_X = self.ICON_X + (self.ICON_W - self.BADGE_W) // 2
        self.BADGE_Y = self.ICON_Y + (self.ICON_H - self.BADGE_H) // 2

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

    def buildEntry(self, item):
        width = self.l.getItemSize().width()
        height = self.l.getItemSize().height()
        textX = self.ICON_X + self.ICON_W + 5
        res = [None]
        res.append((eListboxPythonMultiContent.TYPE_TEXT, textX, 0, width - textX, height, 1, RT_HALIGN_LEFT | RT_VALIGN_CENTER, item.getDisplayTitle(), item.getTextColor()))
        icon = self.dictPIX.get(item.imageType, None)
        if icon is not None:
            x, y, w, h = fitPixmapInBox(icon, self.ICON_X, self.ICON_Y, self.ICON_W, self.ICON_H)
            res.append(MultiContentEntryPixmapAlphaBlend(pos=(x, y), size=(w, h), png=icon, flags=BT_SCALE))
        if getattr(item, 'isWatched', False) and self.watchedBadgePIX is not None:
            x, y, w, h = fitPixmapInBox(self.watchedBadgePIX, self.BADGE_X, self.BADGE_Y, self.BADGE_W, self.BADGE_H)
            res.append(MultiContentEntryPixmapAlphaBlend(pos=(x, y), size=(w, h), png=self.watchedBadgePIX, flags=BT_SCALE))
        elif getattr(item, 'isStarted', False) and self.startedBadgePIX is not None:
            x, y, w, h = fitPixmapInBox(self.startedBadgePIX, self.BADGE_X, self.BADGE_Y, self.BADGE_W, self.BADGE_H)
            res.append(MultiContentEntryPixmapAlphaBlend(pos=(x, y), size=(w, h), png=self.startedBadgePIX, flags=BT_SCALE))
        return res


class IPTVRadioButtonList(IPTVMainNavigatorList):
    # WQHD copy used as the single source (32x32, highest res of the 3
    # per-tier variants) - buildEntry() scales it down cleanly via
    # fitPixmapInBox()/BT_SCALE for HD/FHD, so no separate flat-root copy
    # is needed alongside the per-tier ones the plain-widget users need
    ICONS_FILESNAMES = {'on': 'WQHD/radio_button_on.png', 'off': 'WQHD/radio_button_off.png'}
    FAILED_TEXT_COLOR = "#FF4040"
    ERROR_BADGE_W, ERROR_BADGE_H = 32, 32

    def __init__(self):
        IPTVMainNavigatorList.__init__(self)
        self.errorBadgePIX = None
        # on/off radio dot box - deliberately its own smaller box, not
        # the main ICON_*/BADGE_* one above (a compact indicator, not a
        # full content icon). Uses fitPixmapInBox()/BT_SCALE like the
        # main icon box so radio_button_on/off.png is properly scaled to
        # fit the declared box rather than relying on a raw pixel size.
        # Derived from self.font[2] (itemHeight) to reproduce the
        # original 16px box at HD while scaling proportionally at
        # FHD/WQHD, same approach IPTVMainNavigatorList's own ICON_W/H
        # use.
        self.dotSize = max(int(round(self.font[2] * 16.0 / 35.0)), 12)

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
        res = [None]
        if None is item.type:
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 5, 0, width - 5, height, 1, RT_HALIGN_LEFT | RT_VALIGN_CENTER, item.name))
        else:
            # same 3px left margin / 11px gap-after-dot the original fixed
            # 16x16-at-x=3/text-at-x=30 layout used, now scaled with
            # self.dotSize instead of hardcoded numbers
            dotX = 3
            dotY = (height - self.dotSize) // 2
            textX = dotX + self.dotSize + 11
            res.append((eListboxPythonMultiContent.TYPE_TEXT, textX, 0, width - textX, height, 1, RT_HALIGN_LEFT | RT_VALIGN_CENTER, item.name))
            icon = self.dictPIX.get(item.type, None)
            if icon is not None:
                x, y, w, h = fitPixmapInBox(icon, dotX, dotY, self.dotSize, self.dotSize)
                res.append(MultiContentEntryPixmapAlphaBlend(pos=(x, y), size=(w, h), png=icon, flags=BT_SCALE))
        return res


class IPTVLinkChoiceBoxList(IPTVRadioButtonList):
    # used for the "Select link" mirror picker: always shows the regular link
    # icon (same spot/size as the main list's item icon) with the error badge
    # overlaid centered on top of it when that mirror failed to resolve - same
    # overlay pattern as the watched/started badge in IPTVMainNavigatorList.
    # LinkItem.png is the purpose-built icon for this exact screen;
    # GlobItem.png stays for the generic web/link CDisplayListItem.TYPE_WWW
    # use elsewhere
    LINK_ICON_FILENAME = 'LinkItem.png'

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
            x, y, w, h = fitPixmapInBox(self.linkIconPIX, self.ICON_X, self.ICON_Y, self.ICON_W, self.ICON_H)
            res.append(MultiContentEntryPixmapAlphaBlend(pos=(x, y), size=(w, h), png=self.linkIconPIX, flags=BT_SCALE))
        if failed and self.errorBadgePIX is not None:
            x, y, w, h = fitPixmapInBox(self.errorBadgePIX, self.BADGE_X, self.BADGE_Y, self.BADGE_W, self.BADGE_H)
            res.append(MultiContentEntryPixmapAlphaBlend(pos=(x, y), size=(w, h), png=self.errorBadgePIX, flags=BT_SCALE))
        return res


class IPTVMoviePlayerChoiceBoxList(IPTVMainNavigatorList):
    # used for the "Select movie player" popup (iptvplayerwidget.py's
    # SetActiveMoviePlayer): every row shows the same PlayerItem.png icon
    # (same ICON_X/Y/W/H spot/size as the main list's own item icon, from
    # IPTVMainNavigatorList above) instead of IPTVRadioButtonList's on/off
    # dot, with CheckBadge.png overlaid centered on top of it for whichever
    # row is the currently active player (item.type ==
    # IPTVChoiceBoxItem.TYPE_ON) - same centered-overlay mechanism
    # IPTVLinkChoiceBoxList above uses for its failed-mirror badge, just
    # keyed off .type instead of .failed and a different icon/badge pair.
    # Deliberately extends IPTVMainNavigatorList directly, not
    # IPTVRadioButtonList - the on/off radio dots it would otherwise load
    # into dictPIX are never used here. item.type is compared against the
    # literal "on" (not IPTVChoiceBoxItem.TYPE_ON) to avoid importing
    # iptvchoicebox.py here, which itself imports this module - same
    # approach IPTVRadioButtonList.buildEntry() above already relies on.
    PLAYER_ICON_FILENAME = 'PlayerItem.png'
    CHECK_BADGE_FILENAME = 'CheckBadge.png'

    def __init__(self):
        IPTVMainNavigatorList.__init__(self)
        self.playerIconPIX = None
        self.checkBadgePIX = None

    def onCreate(self):
        IPTVMainNavigatorList.onCreate(self)
        try:
            self.playerIconPIX = LoadPixmap(cached=True, path=GetIconDir(self.PLAYER_ICON_FILENAME))
        except Exception:
            self.playerIconPIX = None
        try:
            self.checkBadgePIX = LoadPixmap(cached=True, path=GetIconDir(self.CHECK_BADGE_FILENAME))
        except Exception:
            self.checkBadgePIX = None

    def onDestroy(self):
        IPTVMainNavigatorList.onDestroy(self)
        self.playerIconPIX = None
        self.checkBadgePIX = None

    def buildEntry(self, item):
        width = self.l.getItemSize().width()
        height = self.l.getItemSize().height()
        textX = self.ICON_X + self.ICON_W + 5
        res = [None, (eListboxPythonMultiContent.TYPE_TEXT, textX, 0, width - textX, height, 1, RT_HALIGN_LEFT | RT_VALIGN_CENTER, item.name)]
        if self.playerIconPIX is not None:
            x, y, w, h = fitPixmapInBox(self.playerIconPIX, self.ICON_X, self.ICON_Y, self.ICON_W, self.ICON_H)
            res.append(MultiContentEntryPixmapAlphaBlend(pos=(x, y), size=(w, h), png=self.playerIconPIX, flags=BT_SCALE))
        if item.type == 'on' and self.checkBadgePIX is not None:
            x, y, w, h = fitPixmapInBox(self.checkBadgePIX, self.BADGE_X, self.BADGE_Y, self.BADGE_W, self.BADGE_H)
            res.append(MultiContentEntryPixmapAlphaBlend(pos=(x, y), size=(w, h), png=self.checkBadgePIX, flags=BT_SCALE))
        return res


class IPTVActionChoiceBoxList(IPTVMainNavigatorList):
    # used for the "Select action" popup (iptvplayerwidget.py's
    # menu_pressed()/requestCustomActionFromHost()): options come from two
    # sources - the core itself adds "Add/Remove favorites"
    # (item.privateData == {'e2i_menu_action': 'ADD_FAV'/'DELETE_FAV'}),
    # the rest comes from whatever the currently active host's own
    # getCustomActions() returns, which is genuinely host-specific and has
    # no single fixed set. Only one cross-host convention actually exists
    # in this codebase: iptvwatchedhelper.py's shared "watched" mixin
    # (used by hostyoutube.py/hostfilmpalast.py/hostserienstreamto.py) and
    # hostfavourites.py's own near-identical logic both always use
    # privateData == {'action': 'set_watched_flag'/'unset_watched_flag',
    # ...}. Anything else (e.g. hostlocalmedia.py's own {'action':
    # 'paste_file', ...}) isn't a known pattern, so it falls back to no
    # icon - same plain look this screen had before this class existed.
    ICON_MAP = {
        'ADD_FAV': 'BookmarkPlusItem.png',
        'DELETE_FAV': 'BookmarkMinusItem.png',
    }
    ACTION_ICON_MAP = {
        'set_watched_flag': 'MovieWatchedItem.png',
        'unset_watched_flag': 'MovieUnwatchedItem.png',
    }

    def __init__(self):
        IPTVMainNavigatorList.__init__(self)
        self.actionIconPIX = {}

    def onCreate(self):
        IPTVMainNavigatorList.onCreate(self)
        self.actionIconPIX = {}
        allFilenames = set(self.ICON_MAP.values()) | set(self.ACTION_ICON_MAP.values())
        for filename in allFilenames:
            try:
                self.actionIconPIX[filename] = LoadPixmap(cached=True, path=GetIconDir(filename))
            except Exception:
                self.actionIconPIX[filename] = None

    def onDestroy(self):
        IPTVMainNavigatorList.onDestroy(self)
        self.actionIconPIX = {}

    def _iconForItem(self, item):
        privateData = getattr(item, 'privateData', None)
        if not isinstance(privateData, dict):
            return None
        filename = self.ICON_MAP.get(privateData.get('e2i_menu_action'))
        if filename is None:
            filename = self.ACTION_ICON_MAP.get(privateData.get('action'))
        if filename is None:
            return None
        return self.actionIconPIX.get(filename)

    def buildEntry(self, item):
        width = self.l.getItemSize().width()
        height = self.l.getItemSize().height()
        icon = self._iconForItem(item)
        textX = self.ICON_X + self.ICON_W + 5 if icon is not None else 5
        res = [None, (eListboxPythonMultiContent.TYPE_TEXT, textX, 0, width - textX, height, 1, RT_HALIGN_LEFT | RT_VALIGN_CENTER, item.name)]
        if icon is not None:
            x, y, w, h = fitPixmapInBox(icon, self.ICON_X, self.ICON_Y, self.ICON_W, self.ICON_H)
            res.append(MultiContentEntryPixmapAlphaBlend(pos=(x, y), size=(w, h), png=icon, flags=BT_SCALE))
        return res


class IPTVDMActionChoiceBoxList(IPTVMainNavigatorList):
    # used for iptvdmui.py's IPTVDMWidget.ok_pressed() "Select action"
    # popup - unlike IPTVActionChoiceBoxList above (host-specific,
    # dict-shaped privateData), every option here comes from the same
    # fixed, closed set of download-manager actions, and privateData is
    # a plain `(action, player)` tuple, not a dict - `action` is what
    # picks the icon here, `player` (only meaningful for the 2 "play"
    # rows) is irrelevant to it. One icon per real action id actually
    # used in ok_pressed()'s option lists ('continue' has no icon - that
    # option is permanently commented out there, so it never actually
    # appears).
    # 'remove' ("Remove file"/"Datei löschen") deletes a real file
    # already on disk - the trash can (DeleteItem.png) fits that
    # permanence. 'delet' ("Remove item"/"Eintrag entfernen") only drops
    # a still-WAITING, not-yet-downloaded queue entry that has no file
    # yet - the plain minus (RemoveItem.png) fits a "just take it off
    # the list" action better.
    ACTION_ICON_MAP = {
        'play': 'PlayItem.png',
        'retry': 'RetryItem.png',
        'stop': 'StopItem.png',
        'remove': 'DeleteItem.png',
        'delet': 'RemoveItem.png',
        'move': 'PromoteItem.png',
        'rename': 'RenameItem.png',
    }

    def __init__(self):
        IPTVMainNavigatorList.__init__(self)
        self.actionIconPIX = {}

    def onCreate(self):
        IPTVMainNavigatorList.onCreate(self)
        self.actionIconPIX = {}
        for filename in set(self.ACTION_ICON_MAP.values()):
            try:
                self.actionIconPIX[filename] = LoadPixmap(cached=True, path=GetIconDir(filename))
            except Exception:
                self.actionIconPIX[filename] = None

    def onDestroy(self):
        IPTVMainNavigatorList.onDestroy(self)
        self.actionIconPIX = {}

    def _iconForItem(self, item):
        privateData = getattr(item, 'privateData', None)
        if not isinstance(privateData, tuple) or not privateData:
            return None
        filename = self.ACTION_ICON_MAP.get(privateData[0])
        if filename is None:
            return None
        return self.actionIconPIX.get(filename)

    def buildEntry(self, item):
        width = self.l.getItemSize().width()
        height = self.l.getItemSize().height()
        icon = self._iconForItem(item)
        textX = self.ICON_X + self.ICON_W + 5 if icon is not None else 5
        res = [None, (eListboxPythonMultiContent.TYPE_TEXT, textX, 0, width - textX, height, 1, RT_HALIGN_LEFT | RT_VALIGN_CENTER, item.name)]
        if icon is not None:
            x, y, w, h = fitPixmapInBox(icon, self.ICON_X, self.ICON_Y, self.ICON_W, self.ICON_H)
            res.append(MultiContentEntryPixmapAlphaBlend(pos=(x, y), size=(w, h), png=icon, flags=BT_SCALE))
        return res


class IPTVPlayerSelectOptionChoiceBoxList(IPTVMainNavigatorList):
    # used for iptvplayerwidget.py's E2iPlayerWidget.blue_pressed()
    # "Select option" popup (BLUE in the main host/category list) -
    # privateData here is a plain string (the option id itself, e.g.
    # "ADD_FAV"/"HELP"), not a dict like IPTVActionChoiceBoxList or a
    # tuple like IPTVDMActionChoiceBoxList, so its own small class again.
    # Icon choices reuse whatever this codebase's OTHER ChoiceBox lists
    # (or e2ivk.py's own options list) already established for the same
    # concept rather than inventing new ones: ADD_FAV/DELETE_FAV match
    # IPTVActionChoiceBoxList's own ICON_MAP exactly, SetActiveMoviePlayer
    # reuses IPTVMoviePlayerChoiceBoxList's PlayerItem.png (same concept,
    # one menu level up), ADD_USER_LINK reuses IPTVLinkChoiceBoxList's
    # LinkItem.png, EDIT_USER_LINKS gets its own LinkEditItem.png
    # (distinct from "add" - same "Edit" pencil-overlay idea as
    # EDIT_FAV's own BookmarkEditItem.png). HostConfig reuses
    # SettingsItem.png (already e2ivk.py's own "Settings" row icon),
    # EditSearchHistory/IPTVDM reuse CDisplayListItem's own
    # SearchHistoryEditorItem.png/DownloadFolderItem.png (list-navigator
    # icons for the same actual screens). CustomItem.png stands in for
    # the open-ended, per-host "HostAction:%d" rows - genuinely
    # unpredictable, but a generic "custom action" glyph beats none.
    # HELP/CLOSE use HelpItem.png/ExitItem.png; EDIT_FAV/
    # RandomizePlayableItems/ReversePlayableItems get their own icons
    # (BookmarkEditItem.png/RandomizeItem.png/ReverseItem.png) - every
    # row has one.
    ACTION_ICON_MAP = {
        'ADD_FAV': 'BookmarkPlusItem.png',
        'DELETE_FAV': 'BookmarkMinusItem.png',
        'EDIT_FAV': 'BookmarkEditItem.png',
        'HostConfig': 'SettingsItem.png',
        'EditSearchHistory': 'SearchHistoryEditorItem.png',
        'IPTVDM': 'DownloadFolderItem.png',
        'SetActiveMoviePlayer': 'PlayerItem.png',
        'ADD_USER_LINK': 'LinkItem.png',
        'EDIT_USER_LINKS': 'LinkEditItem.png',
        'RandomizePlayableItems': 'RandomizeItem.png',
        'ReversePlayableItems': 'ReverseItem.png',
        'HELP': 'HelpItem.png',
        'CLOSE': 'ExitItem.png',
    }
    # dynamic per-host rows ("HostAction:0", "HostAction:1", ...) all
    # share this one fallback icon instead of getting their own entries
    HOST_ACTION_ICON = 'CustomItem.png'

    def __init__(self):
        IPTVMainNavigatorList.__init__(self)
        self.actionIconPIX = {}

    def onCreate(self):
        IPTVMainNavigatorList.onCreate(self)
        self.actionIconPIX = {}
        filenames = set(self.ACTION_ICON_MAP.values())
        filenames.add(self.HOST_ACTION_ICON)
        for filename in filenames:
            try:
                self.actionIconPIX[filename] = LoadPixmap(cached=True, path=GetIconDir(filename))
            except Exception:
                self.actionIconPIX[filename] = None

    def onDestroy(self):
        IPTVMainNavigatorList.onDestroy(self)
        self.actionIconPIX = {}

    def _iconForItem(self, item):
        privateData = getattr(item, 'privateData', None)
        if not isinstance(privateData, str):
            return None
        filename = self.ACTION_ICON_MAP.get(privateData)
        if filename is None and privateData.startswith('HostAction:'):
            filename = self.HOST_ACTION_ICON
        if filename is None:
            return None
        return self.actionIconPIX.get(filename)

    def buildEntry(self, item):
        width = self.l.getItemSize().width()
        height = self.l.getItemSize().height()
        icon = self._iconForItem(item)
        textX = self.ICON_X + self.ICON_W + 5 if icon is not None else 5
        res = [None, (eListboxPythonMultiContent.TYPE_TEXT, textX, 0, width - textX, height, 1, RT_HALIGN_LEFT | RT_VALIGN_CENTER, item.name)]
        if icon is not None:
            x, y, w, h = fitPixmapInBox(icon, self.ICON_X, self.ICON_Y, self.ICON_W, self.ICON_H)
            res.append(MultiContentEntryPixmapAlphaBlend(pos=(x, y), size=(w, h), png=icon, flags=BT_SCALE))
        return res


class IPTVPlayerSelectorContextMenuChoiceBoxList(IPTVMainNavigatorList):
    # used for playerselector.py's shared _PlayerSelectorListMode.
    # openContextMenu() "Select option" popup (BLUE in PlayerSelectorWidget) -
    # privateData is a plain string again (the option id, e.g.
    # "SEARCH"/"SETTINGS"), same shape as IPTVPlayerSelectOptionChoiceBoxList
    # above but a different, unrelated set of ids, hence its own class.
    # Icons reused where a good match already exists: SEARCH matches
    # CDisplayListItem's own SearchItem.png, IPTVDM/SETTINGS reuse the
    # exact same icons IPTVPlayerSelectOptionChoiceBoxList already uses
    # for the equivalent "Download manager"/"Configure host" rows,
    # DEL_ITEM reuses RemoveItem.png (same "soft removal, not a real
    # file" convention as IPTVDMActionChoiceBoxList's own 'delet' row).
    # ADD_HOST_TO_GROUP/SORT_NAME/reset_group/CHANGE_REORDERING_MODE got
    # their own dedicated icons instead of reusing looser matches
    # (reset_group used RetryItem.png before this - genuinely different
    # concept, just "close enough"). CHANGE_REORDERING_MODE's id is split
    # into :ON/:OFF
    # in openContextMenu() specifically so the two mutually-exclusive
    # labels ("Enable"/"Disable reordering mode") can each get their own
    # icon here (ReorderModeOnItem.png/ReorderModeOffItem.png) - plain
    # "CHANGE_REORDERING_MODE" alone couldn't tell them apart.
    # config_hosts/config_groups ("Disable/Enable services"/"...groups" -
    # each a single fixed label naming BOTH actions, not a toggle between
    # two different label texts like reordering) reuse the new
    # EnableItem.png/DisableItem.png pair, one each, purely to keep the
    # two rows visually distinct from each other.
    ACTION_ICON_MAP = {
        'ADD_HOST_TO_GROUP': 'AddHostToGroupItem.png',
        'CHANGE_REORDERING_MODE:ON': 'ReorderModeOnItem.png',
        'CHANGE_REORDERING_MODE:OFF': 'ReorderModeOffItem.png',
        'SORT_NAME': 'SortByNameItem.png',
        'SEARCH': 'SearchItem.png',
        'IPTVDM': 'DownloadFolderItem.png',
        'config_hosts': 'EnableItem.png',
        'config_groups': 'DisableItem.png',
        'reset_group': 'ResetGroupItem.png',
        'DEL_ITEM': 'RemoveItem.png',
        'SETTINGS': 'SettingsItem.png',
        'INFO': 'InfoItem.png',
    }

    def __init__(self):
        IPTVMainNavigatorList.__init__(self)
        self.actionIconPIX = {}

    def onCreate(self):
        IPTVMainNavigatorList.onCreate(self)
        self.actionIconPIX = {}
        for filename in set(self.ACTION_ICON_MAP.values()):
            try:
                self.actionIconPIX[filename] = LoadPixmap(cached=True, path=GetIconDir(filename))
            except Exception:
                self.actionIconPIX[filename] = None

    def onDestroy(self):
        IPTVMainNavigatorList.onDestroy(self)
        self.actionIconPIX = {}

    def _iconForItem(self, item):
        privateData = getattr(item, 'privateData', None)
        if not isinstance(privateData, str):
            return None
        filename = self.ACTION_ICON_MAP.get(privateData)
        if filename is None:
            return None
        return self.actionIconPIX.get(filename)

    def buildEntry(self, item):
        width = self.l.getItemSize().width()
        height = self.l.getItemSize().height()
        icon = self._iconForItem(item)
        textX = self.ICON_X + self.ICON_W + 5 if icon is not None else 5
        res = [None, (eListboxPythonMultiContent.TYPE_TEXT, textX, 0, width - textX, height, 1, RT_HALIGN_LEFT | RT_VALIGN_CENTER, item.name)]
        if icon is not None:
            x, y, w, h = fitPixmapInBox(icon, self.ICON_X, self.ICON_Y, self.ICON_W, self.ICON_H)
            res.append(MultiContentEntryPixmapAlphaBlend(pos=(x, y), size=(w, h), png=icon, flags=BT_SCALE))
        return res
