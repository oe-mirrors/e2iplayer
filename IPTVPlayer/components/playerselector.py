# -*- coding: utf-8 -*-
#
#  Player Selector
#
#  $Id$
#  Page Punkte weiter ausseinander - 132
#  Version dazu gebaut , skin 14 , 227-229
import os
from Screens.Screen import Screen
from Components.ActionMap import ActionMap, HelpableActionMap
from enigma import ePoint, getDesktop, eListboxPythonMultiContent, RT_HALIGN_LEFT, RT_VALIGN_CENTER, BT_SCALE
from Tools.LoadPixmap import LoadPixmap
from skin import parseColor
from Components.Label import Label
from Components.config import config
from Components.MultiContent import MultiContentEntryPixmapAlphaBlend, MultiContentEntryText
from Screens.ChoiceBox import ChoiceBox
from Screens.MessageBox import MessageBox
from Components.Sources.List import List
from Components.Sources.StaticText import StaticText
from Tools.Directories import resolveFilename, SCOPE_PLUGINS
from Tools.BoundFunction import boundFunction

from Plugins.Extensions.IPTVPlayer.components.cover import Cover3
from Plugins.Extensions.IPTVPlayer.components.iptvchoicebox import IPTVChoiceBoxWidget, IPTVChoiceBoxItem
from Plugins.Extensions.IPTVPlayer.components.iptvlist import IPTVRadioButtonList
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIPTVPlayerVersion, GetIconDir, GetLogoDir, GetAvailableIconSize
from Plugins.Extensions.IPTVPlayer.__init__ import _, GRIDSUPPORT


def _getSearchResultItemHeight(screenwidth):
    # taller than IPTVMainNavigatorList's own default item height
    # (35/40/55), which IPTVHostSearchResultList would otherwise inherit -
    # gives the logo more room to grow. Shared with _getSearchResultsHeight
    # below so the popup is always sized to fit these taller rows. Matches
    # PlayerSelectorHostList's row height (list mode) so both places that
    # show a host/group logo in front of a name look the same
    if screenwidth >= 2560:
        return 90
    elif screenwidth == 1920:
        return 64
    return 56


def _getListVisibleRows(screenwidth):
    # how many list mode rows actually fit in the "grid" widget's visible
    # area - used by the legacy class's manual scroll-window handling
    # (self.windowStart) since that platform's eListbox doesn't move its
    # own selection/scroll position via moveSelectionTo(). The three
    # heights are skinListHD/FHD/WQHD's own "grid" widget size, kept in
    # sync by hand the same way skinListHD/FHD/WQHD themselves are.
    itemHeight = _getSearchResultItemHeight(screenwidth)
    if screenwidth >= 2560:
        listHeight = 940
    elif screenwidth == 1920:
        listHeight = 705
    else:
        listHeight = 460
    return max(1, listHeight // itemHeight)


def _getPlayerSelectorIcon(key, iconSize):
    # group icons (flags/categories - PREDEFINED_GROUPS in
    # iptvhostgroups.py, plus "all"/"config") live in their own
    # PlayerSelector/groups/ subfolder, separate from the much larger set
    # of per-host site icons in PlayerSelector/ itself. Tried first rather
    # than hardcoding the group key list here (which would need a new
    # import/dependency on iptvhostgroups.py) - a given key only ever
    # exists in one of the two locations, never both
    icon = GetIconDir('PlayerSelector/groups/%s%i.png' % (key, iconSize))
    if not os.path.isfile(icon):
        icon = GetIconDir('PlayerSelector/%s%i.png' % (key, iconSize))
    if not os.path.isfile(icon):
        icon = GetIconDir('PlayerSelector/groups/comming-soon.%i.png' % iconSize)
    return icon


def _getPlayerSelectorLogoPath(key):
    # same idea as _getPlayerSelectorIcon() above, for the logos/<key>logo.png
    # files list mode and search results show in front of a name - group
    # logos live in their own logos/groups/ subfolder. Returns a path that
    # may not exist (same as the plain GetLogoDir() calls this replaces) -
    # callers already check os.path.isfile() themselves before using it
    logoPath = GetLogoDir('groups/' + key + 'logo.png')
    if not os.path.isfile(logoPath):
        logoPath = GetLogoDir(key + 'logo.png')
    return logoPath


def _setSelectionPixmap(instance, path):
    # eListbox.setSelectionPixmap() isn't available on every Enigma2 fork -
    # confirmed missing on OpenViX (AttributeError: 'eListbox' object has no
    # attribute 'setSelectionPixmap'), which only exposes the older/different
    # setSelectionPicture() there. The custom marker frame this sets is a
    # visual enhancement (plain backgroundColorSelected is barely visible on
    # its own), not required functionality, so just keep the plain default
    # highlight instead of crashing when the method is absent.
    if hasattr(instance, 'setSelectionPixmap'):
        instance.setSelectionPixmap(LoadPixmap(path))


class IPTVHostSearchResultList(IPTVRadioButtonList):
    # host logos (icons/logos/<hostkey>logo.png) shown before the name in
    # search results. Raw eListboxPythonMultiContent tuples don't auto-scale
    # like the chrome skin's XML does, so the box itself has to be sized per
    # real resolution tier here. Logo size matches PlayerSelectorHostList's
    # (list mode) - both keep the real 120x40 (3:1) source logos undistorted
    def __init__(self):
        IPTVRadioButtonList.__init__(self)
        screenwidth = getDesktop(0).size().width()
        itemHeight = _getSearchResultItemHeight(screenwidth)
        self.l.setItemHeight(itemHeight)
        if screenwidth >= 2560:
            self.logoW, self.logoH = 180, 60
        elif screenwidth == 1920:
            self.logoW, self.logoH = 126, 42
        else:
            self.logoW, self.logoH = 108, 36

    def buildEntry(self, item):
        width = self.l.getItemSize().width()
        height = self.l.getItemSize().height()
        res = [None]
        logoX = 5
        logoY = (height - self.logoH) // 2
        textX = logoX + self.logoW + 10
        try:
            pix = None
            if item.description:
                logoPath = _getPlayerSelectorLogoPath(item.description)
                if os.path.isfile(logoPath):
                    pix = LoadPixmap(cached=True, path=logoPath)
            if pix is not None:
                res.append(MultiContentEntryPixmapAlphaBlend(pos=(logoX, logoY), size=(self.logoW, self.logoH), png=pix, flags=BT_SCALE))
            else:
                textX = logoX
            res.append((eListboxPythonMultiContent.TYPE_TEXT, textX, 0, width - textX - 5, height, 1, RT_HALIGN_LEFT | RT_VALIGN_CENTER, item.name))
        except Exception:
            printExc()
        return res

    def onCreate(self):
        IPTVRadioButtonList.onCreate(self)
        # active-row marker frame, same idea as PlayerSelectorWidget's grid
        # marker - plain backgroundColorSelected alone is barely visible.
        # No "picked up for reordering" state here (search results don't
        # support reordering), so always the plain (non-Sel) variant
        screenwidth = getDesktop(0).size().width()
        if screenwidth >= 2560:
            suffix = "90"
        elif screenwidth == 1920:
            suffix = "64"
        else:
            suffix = "56"
        file = resolveFilename(SCOPE_PLUGINS, 'Extensions/IPTVPlayer/icons/PlayerSelector/Marker/markerSearchList%s.png' % suffix)
        _setSelectionPixmap(self.instance, file)


class PlayerSelectorHostList(IPTVHostSearchResultList):
    # PlayerSelectorWidget's "List view" mode - reuses IPTVHostSearchResultList's
    # sizing and icons/logos/<key>logo.png lookup as-is (same visual language
    # as the search results list, __init__ inherited unchanged), rather than
    # the PlayerSelector/<key><iconSize>.png grid icons PlayerSelectorWidget's
    # grid mode uses. Only buildEntry() differs, since this list is fed
    # differently-shaped tuples (see below) and adds a comming-soon fallback.
    # Also exposes a couple of method aliases so PlayerSelectorWidget's
    # existing selection/update code (written against Components.Sources.List's
    # API) works unmodified regardless of which list widget is actually in use.
    # Set to False by PlayerSelectorWidget right after construction when this
    # is a group list (groupName == 'selectgroup') - group keys ("german",
    # "userdefined", ...) aren't meaningful to show, unlike host keys
    showHostKey = True
    # opt-in, unused unless a caller explicitly sets it (see legacy
    # PlayerSelectorWidget's list mode): draws a plain text marker in
    # front of this row instead of relying on eListbox's native
    # selection highlight, for platforms where moveSelectionTo()/
    # getCurrentIndex() don't actually move/track the real selection
    # (confirmed on at least one Enigma2 fork - OpenViX). -1 means "no
    # override", so this is a complete no-op for every other caller.
    selectedIdx = -1
    # color used for the selectedIdx bar above - a caller doing its own
    # highlighting (see useNativeHighlight below) can switch this to
    # yellow while an item is picked up for reordering
    highlightColor = "#1b5a91"
    # sets whether onCreate() below also applies eListbox's own native
    # setBackgroundColorSelected()/marker pixmap highlighting. Legacy
    # PlayerSelectorWidget's list mode turns this off (see
    # __initListMode()) since that highlighting tracks eListbox's own
    # (broken, on that platform) selection cursor rather than
    # self.selectedIdx - left on unchanged for every other caller.
    useNativeHighlight = True

    def buildEntry(self, pixmap, name, idx, key):
        # unlike the other buildEntry() methods in this file, this list is
        # fed 4-item tuples (see updateIcons() below, shared with grid mode's
        # Components.Sources.List) - eListboxPythonMultiContent unpacks each
        # tuple's elements as separate positional args to the build function
        # instead of passing the tuple itself, so this needs 4 params (pixmap
        # and idx aren't used here - pixmap is the preloaded grid icon, only
        # used by grid mode's own skin template) rather than the single
        # "item" the other single-element-tuple-fed lists in this file receive
        width = self.l.getItemSize().width()
        height = self.l.getItemSize().height()
        res = [None]
        logoX = 5
        logoY = (height - self.logoH) // 2
        textX = logoX + self.logoW + 10
        try:
            pix = None
            if key:
                logoPath = _getPlayerSelectorLogoPath(key)
                if not os.path.isfile(logoPath):
                    logoPath = GetLogoDir('groups/comming-soonlogo.png')
                if os.path.isfile(logoPath):
                    pix = LoadPixmap(cached=True, path=logoPath)
            if idx == self.selectedIdx:
                # full-width bar behind the logo/text below, same accent
                # blue used for selection elsewhere in this UI - drawn
                # first so the later entries render on top of it
                res.append(MultiContentEntryText(pos=(0, 0), size=(width, height), backcolor=self.highlightColor))
            if pix is not None:
                res.append(MultiContentEntryPixmapAlphaBlend(pos=(logoX, logoY), size=(self.logoW, self.logoH), png=pix, flags=BT_SCALE))
            else:
                textX = logoX
            # same "name (key)" format the search results list already uses
            # (searchCallback() builds its items as "%s (%s)" % (name, hostKey))
            displayName = "%s (%s)" % (name, key) if (key and self.showHostKey) else name
            res.append((eListboxPythonMultiContent.TYPE_TEXT, textX, 0, width - textX - 5, height, 1, RT_HALIGN_LEFT | RT_VALIGN_CENTER, displayName))
        except Exception:
            printExc()
        return res

    def getSelectedIndex(self):
        return self.getCurrentIndex()

    def setCurrentIndex(self, index):
        self.moveToIndex(index)

    def updateList(self, items):
        self.setList(items)

    def onCreate(self):
        # skip IPTVHostSearchResultList.onCreate() - it would set the
        # smaller search-results marker here instead of this list's own
        IPTVRadioButtonList.onCreate(self)
        self.setReorderingHighlight(False, False)

    def setReorderingHighlight(self, reorderingActive, pickedUp):
        if not self.useNativeHighlight:
            # eListbox's own selection cursor doesn't move on this
            # platform, so its skin-declared backgroundColorSelected
            # ("#1b5a91", same as the skin's normal foregroundColor/
            # backgroundColor block) can't be trusted to land on the
            # right row - it would otherwise always sit on whichever row
            # is at position 0 of the current window (see
            # PlayerSelectorWidget.updateIcons()'s manual scroll window),
            # which looked like "the first row is permanently blue".
            # Cancel it by matching it to the normal (unselected)
            # background instead, and drive the real highlight through
            # self.highlightColor/selectedIdx above (updateIcons() must
            # be called by the caller afterwards to actually repaint with
            # the new color - this only cancels the native one).
            self.instance.setBackgroundColorSelected(parseColor("black"))
            self.instance.invalidate()
            self.highlightColor = "#ffcc00" if pickedUp else "#1b5a91"
            return
        # grid mode shows the currently picked-up item via a custom marker
        # pixmap (PlayerSelectorWidget.setSelectionImage()) - same idea here,
        # just sized for a list row instead of a square grid cell, plus a
        # background color change list mode has room for and grid mode
        # doesn't. Two independent states: the marker frame is yellow for
        # the whole reordering session (reorderingActive, from entering it
        # to leaving it), while the row's background only turns yellow
        # while an item is actually picked up and being dragged along
        # (pickedUp) - both green/normal otherwise
        screenwidth = getDesktop(0).size().width()
        if screenwidth >= 2560:
            suffix = "90"
        elif screenwidth == 1920:
            suffix = "64"
        else:
            suffix = "56"
        name = ("markerListSel%s.png" if reorderingActive else "markerList%s.png") % suffix
        file = resolveFilename(SCOPE_PLUGINS, 'Extensions/IPTVPlayer/icons/PlayerSelector/Marker/' + name)
        _setSelectionPixmap(self.instance, file)
        self.instance.setBackgroundColorSelected(parseColor("#ffcc00" if pickedUp else "#1b5a91"))
        # without this, the already-selected row only repaints with the new
        # marker/color once the selection actually moves to a different row -
        # same reason grid mode's setSelectionImage() calls .invalidate()
        # itself right after setSelectionPixmap()
        self.instance.invalidate()


class PlayerSelectorSimpleList(PlayerSelectorHostList):
    # PlayerSelectorWidget's "Simple list" mode - deliberately the bare
    # minimum: plain text rows (no host logo), no selection marker/frame
    # overlay (just the skin's own default backgroundColorSelected), and no
    # reordering or search (both disabled at the PlayerSelectorWidget level -
    # this class only needs to stop drawing the parts List view normally
    # adds on top of that). Reuses everything else from PlayerSelectorHostList
    # (getSelectedIndex/setCurrentIndex/updateList/showHostKey) unchanged.
    def buildEntry(self, pixmap, name, idx, key):
        width = self.l.getItemSize().width()
        height = self.l.getItemSize().height()
        res = [None]
        displayName = "%s (%s)" % (name, key) if (key and self.showHostKey) else name
        if idx == self.selectedIdx:
            res.append(MultiContentEntryText(pos=(0, 0), size=(width, height), backcolor=self.highlightColor))
        # same 5px margin IPTVRadioButtonList's own icon-less rows use
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 5, 0, width - 5, height, 1, RT_HALIGN_LEFT | RT_VALIGN_CENTER, displayName))
        return res

    def onCreate(self):
        # skip both IPTVHostSearchResultList.onCreate() (search marker) and
        # PlayerSelectorHostList.onCreate()'s own setReorderingHighlight()
        # call - no marker overlay at all in this mode. On platforms where
        # useNativeHighlight is off (see PlayerSelectorHostList above),
        # the caller (PlayerSelectorWidget.layoutFinished()) cancels the
        # skin's own static backgroundColorSelected itself instead, since
        # this class never calls setReorderingHighlight() at all.
        IPTVRadioButtonList.onCreate(self)


if GRIDSUPPORT:

    class PlayerSelectorWidget(Screen):
        LAST_SELECTION = {}

        def __init__(self, session, inList, outList, numOfLockedItems=0, groupName='', groupObj=None, groupDisplayName=None):
            printDBG("PlayerSelectorWidget.__init__ --------------------------------")
            self.iconSize = GetAvailableIconSize()
            # "S" (List view) and "P" (Simple list) both use the list skin
            # and PlayerSelectorHostList-family widget; simpleListMode picks
            # the further-stripped-down variant (no logos, no marker
            # overlay, no reordering, no search) within that
            self.listMode = config.plugins.iptvplayer.hostsListType.value in ("S", "P")
            self.simpleListMode = config.plugins.iptvplayer.hostsListType.value == "P"
            screenwidth = getDesktop(0).size().width()
            FHD = screenwidth and screenwidth == 1920
            WQHD = screenwidth and screenwidth >= 2560
            self.inList = list(inList)
            self.currList = self.inList
            self.numOfItems = len(self.currList)
            self.outList = outList

            self.groupName = groupName
            self.groupObj = groupObj
            self.numOfLockedItems = numOfLockedItems
            self.reorderingMode = False
            self.reorderingItemSelected = False

            self.lastSelection = PlayerSelectorWidget.LAST_SELECTION.get(self.groupName, 0)

            # load icons
            self.pixmapList = []
            for idx in range(self.numOfItems):
                icon = _getPlayerSelectorIcon(self.currList[idx][1], self.iconSize)
                self.pixmapList.append(LoadPixmap(icon))

            skinHD = """
            <screen name="PlayerSelectorWidget" position="center,center" size="1020,660" resolution="1280,720" title="E2iPlayer" backgroundColor="#34111112" flags="wfNoBorder">
                <widget source="Title" render="Label" position="160,10" size="780,40" foregroundColor="white" backgroundColor="black" borderWidth="1" borderColor="black" transparent="1" zPosition="1" font="Regular;24" valign="center" />
                <widget name="statustext" position="20,570" size="980,30" font="Regular;20" valign="center" halign="center" backgroundColor="black" foregroundColor="white" transparent="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/iptvlogo.png" position="12,10" size="100,40" zPosition="10" alphatest="blend" transparent="1" />
                <eLabel name="BG_Title" position="0,0" size="1020,60" backgroundColor="#100d0f16" zPosition="-1" />
                <eLabel name="BG_Buttons" position="0,612" size="1020,48" backgroundColor="#100d0f16" zPosition="-1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/smallshadowline.png" position="0,60" size="1020,2" zPosition="2" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/smallshadowline.png" position="0,610" size="1020,2" zPosition="2" />
                <widget name="categorytext" position="20,70" size="980,30" font="Regular;20" valign="center" halign="center" backgroundColor="black" foregroundColor="white" transparent="1" />
                <widget source="grid" render="Listbox" position="20,104" size="980,460" conditional="grid" listOrientation="grid" scrollbarMode="showOnDemand" scrollbarSliderBorderWidth="1" scrollbarForegroundColor="#1b5a91" scrollbarBorderColor="#00b6b6b6" itemSpacing="20,20" itemAlignment="center" backgroundColorSelected="#24111112" transparent="1">
                    <templates>
                        <template name="Default" fonts="Regular;20">
                            <mode name="default" itemHeight="145" itemWidth="145">
                                <pixmap index="0" position="22,22" size="100,100" alpha="blend" scale="centerScaled" />
                            </mode>
                            <mode name="120" itemHeight="165" itemWidth="165">
                                <pixmap index="0" position="22,22" size="120,120" alpha="blend" scale="centerScaled" />
                            </mode>
                            <mode name="135" itemHeight="180" itemWidth="180">
                                <pixmap index="0" position="22,22" size="135,135" alpha="blend" scale="centerScaled" />
                            </mode>
                        </template>
                    </templates>
                </widget>
                <widget source="key_menu" render="Pixmap" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/menu.png" position="16,624" size="40,26" conditional="key_menu" alphatest="blend">
                    <convert type="ConditionalShowHide" />
                </widget>
                <widget source="key_red" render="Pixmap" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/red.png" position="180,628" size="20,20" alphatest="blend" objectTypes="key_red,StaticText" transparent="1">
                    <convert type="ConditionalShowHide" />
                </widget>
                <widget source="key_red" render="Label" position="210,626" size="180,24" backgroundColor="#000000" font="Regular;17" foregroundColor="#ffffff" zPosition="+1" valign="center" halign="left" objectTypes="key_red,StaticText" transparent="1" />
                <widget source="key_green" render="Pixmap" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/green.png" position="390,628" size="20,20" alphatest="blend" objectTypes="key_green,StaticText" transparent="1">
                    <convert type="ConditionalShowHide" />
                </widget>
                <widget source="key_green" render="Label" position="420,626" size="180,24" backgroundColor="#000000" font="Regular;17" foregroundColor="#ffffff" zPosition="+1" valign="center" halign="left" objectTypes="key_green,StaticText" transparent="1" />
                <widget source="key_yellow" render="Pixmap" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/yellow.png" position="600,628" size="20,20" alphatest="blend" objectTypes="key_yellow,StaticText" transparent="1">
                    <convert type="ConditionalShowHide" />
                </widget>
                <widget source="key_yellow" render="Label" position="630,626" size="180,24" backgroundColor="#000000" font="Regular;17" foregroundColor="#ffffff" zPosition="+1" valign="center" halign="left" objectTypes="key_yellow,StaticText" transparent="1" />
                <widget source="key_blue" render="Pixmap" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/blue.png" position="810,628" size="20,20" alphatest="blend" objectTypes="key_blue,StaticText" transparent="1">
                    <convert type="ConditionalShowHide" />
                </widget>
                <widget source="key_blue" render="Label" position="840,626" size="180,24" backgroundColor="#000000" font="Regular;17" foregroundColor="#ffffff" zPosition="+1" valign="center" halign="left" objectTypes="key_blue,StaticText" transparent="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/key_prevnext.png" position="70,624" size="40,26" alphatest="blend" transparent="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/ok.png" position="124,624" size="40,26" alphatest="blend" transparent="1" />
            </screen>
            """

            skinFHD = """
            <screen name="PlayerSelectorWidget" position="center,center" size="1530,990" title="E2iPlayer" backgroundColor="#34111112" flags="wfNoBorder">
                <widget source="Title" render="Label" position="240,15" size="1170,60" foregroundColor="white" backgroundColor="black" borderWidth="2" borderColor="black" transparent="1" zPosition="1" font="Regular;36" valign="center" />
                <widget name="statustext" position="30,860" size="1470,45" font="Regular;30" valign="center" halign="center" backgroundColor="black" foregroundColor="white" transparent="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/iptvlogo.png" position="18,15" size="150,60" zPosition="10" alphatest="blend" transparent="1" />
                <eLabel name="BG_Title" position="0,0" size="1530,90" backgroundColor="#100d0f16" zPosition="-1" />
                <eLabel name="BG_Buttons" position="0,918" size="1530,72" backgroundColor="#100d0f16" zPosition="-1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/smallshadowline.png" position="0,90" size="1530,3" zPosition="2" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/smallshadowline.png" position="0,915" size="1530,3" zPosition="2" />
                <widget name="categorytext" position="30,100" size="1470,45" font="Regular;30" valign="center" halign="center" backgroundColor="black" foregroundColor="white" transparent="1" />
                <widget source="grid" render="Listbox" position="30,150" size="1470,705" conditional="grid" listOrientation="grid" scrollbarMode="showOnDemand" scrollbarSliderBorderWidth="1" scrollbarForegroundColor="#1b5a91" scrollbarBorderColor="#00b6b6b6" itemSpacing="20,20" itemAlignment="center" backgroundColorSelected="#24111112" transparent="1">
                    <templates>
                        <template name="Default" fonts="Regular;20">
                            <mode name="default" itemHeight="145" itemWidth="145">
                                <pixmap index="0" position="22,22" size="100,100" alpha="blend" scale="centerScaled" />
                            </mode>
                            <mode name="120" itemHeight="165" itemWidth="165">
                                <pixmap index="0" position="22,22" size="120,120" alpha="blend" scale="centerScaled" />
                            </mode>
                            <mode name="135" itemHeight="180" itemWidth="180">
                                <pixmap index="0" position="22,22" size="135,135" alpha="blend" scale="centerScaled" />
                            </mode>
                        </template>
                    </templates>
                </widget>
                <widget source="key_menu" render="Pixmap" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/menu.png" position="24,936" size="60,39" conditional="key_menu" alphatest="blend">
                    <convert type="ConditionalShowHide" />
                </widget>
                <widget source="key_red" render="Pixmap" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/red.png" position="270,942" size="30,30" alphatest="blend" objectTypes="key_red,StaticText" transparent="1">
                    <convert type="ConditionalShowHide" />
                </widget>
                <widget source="key_red" render="Label" position="315,939" size="270,36" backgroundColor="#000000" font="Regular;26" foregroundColor="#ffffff" zPosition="+1" valign="center" halign="left" objectTypes="key_red,StaticText" transparent="1" />
                <widget source="key_green" render="Pixmap" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/green.png" position="585,942" size="30,30" alphatest="blend" objectTypes="key_green,StaticText" transparent="1">
                    <convert type="ConditionalShowHide" />
                </widget>
                <widget source="key_green" render="Label" position="630,939" size="270,36" backgroundColor="#000000" font="Regular;26" foregroundColor="#ffffff" zPosition="+1" valign="center" halign="left" objectTypes="key_green,StaticText" transparent="1" />
                <widget source="key_yellow" render="Pixmap" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/yellow.png" position="900,942" size="30,30" alphatest="blend" objectTypes="key_yellow,StaticText" transparent="1">
                    <convert type="ConditionalShowHide" />
                </widget>
                <widget source="key_yellow" render="Label" position="945,939" size="270,36" backgroundColor="#000000" font="Regular;26" foregroundColor="#ffffff" zPosition="+1" valign="center" halign="left" objectTypes="key_yellow,StaticText" transparent="1" />
                <widget source="key_blue" render="Pixmap" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/blue.png" position="1215,942" size="30,30" alphatest="blend" objectTypes="key_blue,StaticText" transparent="1">
                    <convert type="ConditionalShowHide" />
                </widget>
                <widget source="key_blue" render="Label" position="1260,939" size="270,36" backgroundColor="#000000" font="Regular;26" foregroundColor="#ffffff" zPosition="+1" valign="center" halign="left" objectTypes="key_blue,StaticText" transparent="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/key_prevnext.png" position="105,936" size="60,39" alphatest="blend" transparent="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/ok.png" position="186,936" size="60,39" alphatest="blend" transparent="1" />
            </screen>
            """

            # native WQHD coordinates (no resolution= auto-scale attribute,
            # same reasoning as skinListWQHD) - every number here is
            # skinFHD's own value scaled by 2560/1920 (4/3), reusing the FHD
            # icon assets, and matches skinListWQHD's chrome layout exactly
            # since both share the same title/footer bar design and only
            # differ in the "grid" content widget. The <templates> block is
            # the one deliberate exception: itemHeight/itemWidth and the
            # icon pixmap size are a fixed, resolution-independent size tied
            # to the IconsSize setting (145/165/180 - already identical
            # between skinHD and skinFHD above), not something to scale up
            # further here - a higher resolution just fits more same-sized
            # cells on screen, the same way skinFHD does relative to skinHD.
            skinWQHD = """
            <screen name="PlayerSelectorWidget" position="center,center" size="2040,1320" title="E2iPlayer" backgroundColor="#34111112" flags="wfNoBorder">
                <widget source="Title" render="Label" position="320,20" size="1560,80" foregroundColor="white" backgroundColor="black" borderWidth="2" borderColor="black" transparent="1" zPosition="1" font="Regular;48" valign="center" />
                <widget name="statustext" position="40,1147" size="1960,60" font="Regular;40" valign="center" halign="center" backgroundColor="black" foregroundColor="white" transparent="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/iptvlogo.png" position="24,20" size="200,80" scale="1" zPosition="10" alphatest="blend" transparent="1" />
                <eLabel name="BG_Title" position="0,0" size="2040,120" backgroundColor="#100d0f16" zPosition="-1" />
                <eLabel name="BG_Buttons" position="0,1224" size="2040,96" backgroundColor="#100d0f16" zPosition="-1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/smallshadowline.png" position="0,120" size="2040,4" scale="1" zPosition="2" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/smallshadowline.png" position="0,1220" size="2040,4" scale="1" zPosition="2" />
                <widget name="categorytext" position="40,133" size="1960,60" font="Regular;40" valign="center" halign="center" backgroundColor="black" foregroundColor="white" transparent="1" />
                <widget source="grid" render="Listbox" position="40,200" size="1960,940" conditional="grid" listOrientation="grid" scrollbarMode="showOnDemand" scrollbarSliderBorderWidth="1" scrollbarForegroundColor="#1b5a91" scrollbarBorderColor="#00b6b6b6" itemSpacing="20,20" itemAlignment="center" backgroundColorSelected="#24111112" transparent="1">
                    <templates>
                        <template name="Default" fonts="Regular;20">
                            <mode name="default" itemHeight="145" itemWidth="145">
                                <pixmap index="0" position="22,22" size="100,100" alpha="blend" scale="centerScaled" />
                            </mode>
                            <mode name="120" itemHeight="165" itemWidth="165">
                                <pixmap index="0" position="22,22" size="120,120" alpha="blend" scale="centerScaled" />
                            </mode>
                            <mode name="135" itemHeight="180" itemWidth="180">
                                <pixmap index="0" position="22,22" size="135,135" alpha="blend" scale="centerScaled" />
                            </mode>
                        </template>
                    </templates>
                </widget>
                <widget source="key_menu" render="Pixmap" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/WQHD/menu.png" position="32,1248" size="80,52" conditional="key_menu" alphatest="blend">
                    <convert type="ConditionalShowHide" />
                </widget>
                <widget source="key_red" render="Pixmap" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/WQHD/red.png" position="360,1256" size="40,40" alphatest="blend" objectTypes="key_red,StaticText" transparent="1">
                    <convert type="ConditionalShowHide" />
                </widget>
                <widget source="key_red" render="Label" position="412,1252" size="360,48" backgroundColor="#000000" font="Regular;35" foregroundColor="#ffffff" zPosition="+1" valign="center" halign="left" objectTypes="key_red,StaticText" transparent="1" />
                <widget source="key_green" render="Pixmap" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/WQHD/green.png" position="780,1256" size="40,40" alphatest="blend" objectTypes="key_green,StaticText" transparent="1">
                    <convert type="ConditionalShowHide" />
                </widget>
                <widget source="key_green" render="Label" position="832,1252" size="360,48" backgroundColor="#000000" font="Regular;35" foregroundColor="#ffffff" zPosition="+1" valign="center" halign="left" objectTypes="key_green,StaticText" transparent="1" />
                <widget source="key_yellow" render="Pixmap" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/WQHD/yellow.png" position="1200,1256" size="40,40" alphatest="blend" objectTypes="key_yellow,StaticText" transparent="1">
                    <convert type="ConditionalShowHide" />
                </widget>
                <widget source="key_yellow" render="Label" position="1252,1252" size="360,48" backgroundColor="#000000" font="Regular;35" foregroundColor="#ffffff" zPosition="+1" valign="center" halign="left" objectTypes="key_yellow,StaticText" transparent="1" />
                <widget source="key_blue" render="Pixmap" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/WQHD/blue.png" position="1620,1256" size="40,40" alphatest="blend" objectTypes="key_blue,StaticText" transparent="1">
                    <convert type="ConditionalShowHide" />
                </widget>
                <widget source="key_blue" render="Label" position="1672,1252" size="360,48" backgroundColor="#000000" font="Regular;35" foregroundColor="#ffffff" zPosition="+1" valign="center" halign="left" objectTypes="key_blue,StaticText" transparent="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/key_prevnext.png" position="140,1248" size="80,52" scale="1" alphatest="blend" transparent="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/ok.png" position="248,1248" size="80,52" scale="1" alphatest="blend" transparent="1" />
            </screen>
            """

            # "List view" mode (hostsListType == "S"): identical chrome frame
            # (title/logo/footer) as the grid skins above, but the "grid"
            # widget is a plain single-column list with the logo shown before
            # the name on each row - same visual language as the search
            # results list (IPTVHostSearchResultList/_getSearchResultItemHeight)
            skinListHD = """
            <screen name="PlayerSelectorWidget" position="center,center" size="1020,660" resolution="1280,720" title="E2iPlayer" backgroundColor="#34111112" flags="wfNoBorder">
                <widget source="Title" render="Label" position="160,10" size="780,40" foregroundColor="white" backgroundColor="black" borderWidth="1" borderColor="black" transparent="1" zPosition="1" font="Regular;24" valign="center" />
                <widget name="statustext" position="20,570" size="980,30" font="Regular;20" valign="center" halign="center" backgroundColor="black" foregroundColor="white" transparent="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/iptvlogo.png" position="12,10" size="100,40" zPosition="10" alphatest="blend" transparent="1" />
                <eLabel name="BG_Title" position="0,0" size="1020,60" backgroundColor="#100d0f16" zPosition="-1" />
                <eLabel name="BG_Buttons" position="0,612" size="1020,48" backgroundColor="#100d0f16" zPosition="-1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/smallshadowline.png" position="0,60" size="1020,2" zPosition="2" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/smallshadowline.png" position="0,610" size="1020,2" zPosition="2" />
                <widget name="categorytext" position="20,70" size="980,30" font="Regular;20" valign="center" halign="center" backgroundColor="black" foregroundColor="white" transparent="1" />
                <widget name="grid" position="20,104" size="980,460" conditional="grid" scrollbarMode="showAlways" scrollbarSliderBorderWidth="1" scrollbarForegroundColor="#1b5a91" scrollbarBorderColor="#00b6b6b6" enableWrapAround="1" transparent="1" foregroundColor="white" backgroundColor="black" backgroundColorSelected="#1b5a91" foregroundColorSelected="white" />
                <widget source="key_menu" render="Pixmap" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/menu.png" position="16,624" size="40,26" conditional="key_menu" alphatest="blend">
                    <convert type="ConditionalShowHide" />
                </widget>
                <widget source="key_red" render="Pixmap" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/red.png" position="180,628" size="20,20" alphatest="blend" objectTypes="key_red,StaticText" transparent="1">
                    <convert type="ConditionalShowHide" />
                </widget>
                <widget source="key_red" render="Label" position="210,626" size="180,24" backgroundColor="#000000" font="Regular;17" foregroundColor="#ffffff" zPosition="+1" valign="center" halign="left" objectTypes="key_red,StaticText" transparent="1" />
                <widget source="key_green" render="Pixmap" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/green.png" position="390,628" size="20,20" alphatest="blend" objectTypes="key_green,StaticText" transparent="1">
                    <convert type="ConditionalShowHide" />
                </widget>
                <widget source="key_green" render="Label" position="420,626" size="180,24" backgroundColor="#000000" font="Regular;17" foregroundColor="#ffffff" zPosition="+1" valign="center" halign="left" objectTypes="key_green,StaticText" transparent="1" />
                <widget source="key_yellow" render="Pixmap" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/yellow.png" position="600,628" size="20,20" alphatest="blend" objectTypes="key_yellow,StaticText" transparent="1">
                    <convert type="ConditionalShowHide" />
                </widget>
                <widget source="key_yellow" render="Label" position="630,626" size="180,24" backgroundColor="#000000" font="Regular;17" foregroundColor="#ffffff" zPosition="+1" valign="center" halign="left" objectTypes="key_yellow,StaticText" transparent="1" />
                <widget source="key_blue" render="Pixmap" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/blue.png" position="810,628" size="20,20" alphatest="blend" objectTypes="key_blue,StaticText" transparent="1">
                    <convert type="ConditionalShowHide" />
                </widget>
                <widget source="key_blue" render="Label" position="840,626" size="180,24" backgroundColor="#000000" font="Regular;17" foregroundColor="#ffffff" zPosition="+1" valign="center" halign="left" objectTypes="key_blue,StaticText" transparent="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/key_prevnext.png" position="70,624" size="40,26" alphatest="blend" transparent="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/ok.png" position="124,624" size="40,26" alphatest="blend" transparent="1" />
            </screen>
            """

            skinListFHD = """
            <screen name="PlayerSelectorWidget" position="center,center" size="1530,990" title="E2iPlayer" backgroundColor="#34111112" flags="wfNoBorder">
                <widget source="Title" render="Label" position="240,15" size="1170,60" foregroundColor="white" backgroundColor="black" borderWidth="2" borderColor="black" transparent="1" zPosition="1" font="Regular;36" valign="center" />
                <widget name="statustext" position="30,860" size="1470,45" font="Regular;30" valign="center" halign="center" backgroundColor="black" foregroundColor="white" transparent="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/iptvlogo.png" position="18,15" size="150,60" zPosition="10" alphatest="blend" transparent="1" />
                <eLabel name="BG_Title" position="0,0" size="1530,90" backgroundColor="#100d0f16" zPosition="-1" />
                <eLabel name="BG_Buttons" position="0,918" size="1530,72" backgroundColor="#100d0f16" zPosition="-1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/smallshadowline.png" position="0,90" size="1530,3" zPosition="2" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/smallshadowline.png" position="0,915" size="1530,3" zPosition="2" />
                <widget name="categorytext" position="30,100" size="1470,45" font="Regular;30" valign="center" halign="center" backgroundColor="black" foregroundColor="white" transparent="1" />
                <widget name="grid" position="30,150" size="1470,705" conditional="grid" scrollbarMode="showAlways" scrollbarSliderBorderWidth="1" scrollbarForegroundColor="#1b5a91" scrollbarBorderColor="#00b6b6b6" enableWrapAround="1" transparent="1" foregroundColor="white" backgroundColor="black" backgroundColorSelected="#1b5a91" foregroundColorSelected="white" />
                <widget source="key_menu" render="Pixmap" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/menu.png" position="24,936" size="60,39" conditional="key_menu" alphatest="blend">
                    <convert type="ConditionalShowHide" />
                </widget>
                <widget source="key_red" render="Pixmap" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/red.png" position="270,942" size="30,30" alphatest="blend" objectTypes="key_red,StaticText" transparent="1">
                    <convert type="ConditionalShowHide" />
                </widget>
                <widget source="key_red" render="Label" position="315,939" size="270,36" backgroundColor="#000000" font="Regular;26" foregroundColor="#ffffff" zPosition="+1" valign="center" halign="left" objectTypes="key_red,StaticText" transparent="1" />
                <widget source="key_green" render="Pixmap" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/green.png" position="585,942" size="30,30" alphatest="blend" objectTypes="key_green,StaticText" transparent="1">
                    <convert type="ConditionalShowHide" />
                </widget>
                <widget source="key_green" render="Label" position="630,939" size="270,36" backgroundColor="#000000" font="Regular;26" foregroundColor="#ffffff" zPosition="+1" valign="center" halign="left" objectTypes="key_green,StaticText" transparent="1" />
                <widget source="key_yellow" render="Pixmap" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/yellow.png" position="900,942" size="30,30" alphatest="blend" objectTypes="key_yellow,StaticText" transparent="1">
                    <convert type="ConditionalShowHide" />
                </widget>
                <widget source="key_yellow" render="Label" position="945,939" size="270,36" backgroundColor="#000000" font="Regular;26" foregroundColor="#ffffff" zPosition="+1" valign="center" halign="left" objectTypes="key_yellow,StaticText" transparent="1" />
                <widget source="key_blue" render="Pixmap" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/blue.png" position="1215,942" size="30,30" alphatest="blend" objectTypes="key_blue,StaticText" transparent="1">
                    <convert type="ConditionalShowHide" />
                </widget>
                <widget source="key_blue" render="Label" position="1260,939" size="270,36" backgroundColor="#000000" font="Regular;26" foregroundColor="#ffffff" zPosition="+1" valign="center" halign="left" objectTypes="key_blue,StaticText" transparent="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/key_prevnext.png" position="105,936" size="60,39" alphatest="blend" transparent="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/ok.png" position="186,936" size="60,39" alphatest="blend" transparent="1" />
            </screen>
            """

            # native WQHD coordinates (no resolution= auto-scale attribute,
            # same reasoning as skinListFHD) - every number here is
            # skinListFHD's own value scaled by 2560/1920 (4/3), reusing the
            # FHD icon assets (Pixmap/ePixmap widgets scale their source
            # image to fit the declared size regardless of source resolution)
            skinListWQHD = """
            <screen name="PlayerSelectorWidget" position="center,center" size="2040,1320" title="E2iPlayer" backgroundColor="#34111112" flags="wfNoBorder">
                <widget source="Title" render="Label" position="320,20" size="1560,80" foregroundColor="white" backgroundColor="black" borderWidth="2" borderColor="black" transparent="1" zPosition="1" font="Regular;48" valign="center" />
                <widget name="statustext" position="40,1147" size="1960,60" font="Regular;40" valign="center" halign="center" backgroundColor="black" foregroundColor="white" transparent="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/iptvlogo.png" position="24,20" size="200,80" scale="1" zPosition="10" alphatest="blend" transparent="1" />
                <eLabel name="BG_Title" position="0,0" size="2040,120" backgroundColor="#100d0f16" zPosition="-1" />
                <eLabel name="BG_Buttons" position="0,1224" size="2040,96" backgroundColor="#100d0f16" zPosition="-1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/smallshadowline.png" position="0,120" size="2040,4" scale="1" zPosition="2" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/smallshadowline.png" position="0,1220" size="2040,4" scale="1" zPosition="2" />
                <widget name="grid" position="40,200" size="1960,940" conditional="grid" scrollbarMode="showAlways" scrollbarSliderBorderWidth="1" scrollbarForegroundColor="#1b5a91" scrollbarBorderColor="#00b6b6b6" enableWrapAround="1" transparent="1" foregroundColor="white" backgroundColor="black" backgroundColorSelected="#1b5a91" foregroundColorSelected="white" />
                <widget source="key_menu" render="Pixmap" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/WQHD/menu.png" position="32,1248" size="80,52" conditional="key_menu" alphatest="blend">
                    <convert type="ConditionalShowHide" />
                </widget>
                <widget source="key_red" render="Pixmap" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/WQHD/red.png" position="360,1256" size="40,40" alphatest="blend" objectTypes="key_red,StaticText" transparent="1">
                    <convert type="ConditionalShowHide" />
                </widget>
                <widget source="key_red" render="Label" position="412,1252" size="360,48" backgroundColor="#000000" font="Regular;35" foregroundColor="#ffffff" zPosition="+1" valign="center" halign="left" objectTypes="key_red,StaticText" transparent="1" />
                <widget source="key_green" render="Pixmap" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/WQHD/green.png" position="780,1256" size="40,40" alphatest="blend" objectTypes="key_green,StaticText" transparent="1">
                    <convert type="ConditionalShowHide" />
                </widget>
                <widget source="key_green" render="Label" position="832,1252" size="360,48" backgroundColor="#000000" font="Regular;35" foregroundColor="#ffffff" zPosition="+1" valign="center" halign="left" objectTypes="key_green,StaticText" transparent="1" />
                <widget source="key_yellow" render="Pixmap" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/WQHD/yellow.png" position="1200,1256" size="40,40" alphatest="blend" objectTypes="key_yellow,StaticText" transparent="1">
                    <convert type="ConditionalShowHide" />
                </widget>
                <widget source="key_yellow" render="Label" position="1252,1252" size="360,48" backgroundColor="#000000" font="Regular;35" foregroundColor="#ffffff" zPosition="+1" valign="center" halign="left" objectTypes="key_yellow,StaticText" transparent="1" />
                <widget source="key_blue" render="Pixmap" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/WQHD/blue.png" position="1620,1256" size="40,40" alphatest="blend" objectTypes="key_blue,StaticText" transparent="1">
                    <convert type="ConditionalShowHide" />
                </widget>
                <widget source="key_blue" render="Label" position="1672,1252" size="360,48" backgroundColor="#000000" font="Regular;35" foregroundColor="#ffffff" zPosition="+1" valign="center" halign="left" objectTypes="key_blue,StaticText" transparent="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/key_prevnext.png" position="140,1248" size="80,52" scale="1" alphatest="blend" transparent="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/ok.png" position="248,1248" size="80,52" scale="1" alphatest="blend" transparent="1" />
            </screen>
            """

            if self.listMode:
                self.skin = skinListWQHD if WQHD else (skinListFHD if FHD else skinListHD)
            else:
                self.skin = skinWQHD if WQHD else (skinFHD if FHD else skinHD)
            Screen.__init__(self, session, mandatoryWidgets=["grid"])
            self.skinName = ["PlayerSelectorScreen", "PlayerSelectorWidget"]

            self.setTitle("E2iPlayer %s" % GetIPTVPlayerVersion())
            self["key_menu"] = StaticText(_("MENU"))
            self["key_red"] = StaticText("" if self.simpleListMode else _("Sort Mode"))
            self["key_green"] = StaticText("" if self.simpleListMode else _("Hide/Active Group"))
            self["key_yellow"] = StaticText(_("Download manager"))
            self["key_blue"] = StaticText(_("More"))
            if self.simpleListMode:
                self["grid"] = PlayerSelectorSimpleList()
            elif self.listMode:
                self["grid"] = PlayerSelectorHostList()
            else:
                self["grid"] = List([])
            if self.listMode:
                # group entries' own keys ("german", "userdefined", ...)
                # aren't meaningful to show next to their name, unlike host
                # keys - only the top-level "select a group" screen has
                # groupName == 'selectgroup', every other value here means
                # this list is showing hosts (a specific group's hosts,
                # 'selecthost', or 'all')
                self["grid"].showHostKey = (groupName != 'selectgroup')
            self["grid"].onSelectionChanged.append(self.selectionChanged)

            self["statustext"] = Label(self.currList[0][0] if self.currList else "")
            self["categorytext"] = Label(groupDisplayName if groupDisplayName else "")

            self["actions"] = HelpableActionMap(self, ["OkCancelActions", "MenuActions", "ColorActions", "DirectionActions", "NavigationActions"], {
                "ok": (self.keySelect, ""),
                "cancel": (self.keyCancel, ""),
                "menu": (self.keySetup, ""),
                "red": (self.changeReorderingMode, ""),
                "green": (self.keyGreen, ""),
                "yellow": (self.keyYellow, ""),
                "blue": (self.keyBlue, ""),
                "up": (self.keyUp, ""),
                "down": (self.keyDown, ""),
            }, prio=0, description="")

            self.onClose.append(self.__onClose)
            self.onLayoutFinish.append(self.layoutFinished)

        def layoutFinished(self):
            self.updateIcons()
            # PlayerSelectorHostList (list mode) always renders itself in
            # Python via buildEntry() - it has no skin-defined <templates>
            # modes to switch between, unlike the grid's zoom-level styles
            if not self.listMode:
                self["grid"].setStyle(str(self.iconSize) if self.iconSize in [120, 135] else "default")
            self.setSelectionImage("")
            if self.currList and self.lastSelection and self.lastSelection < self.numOfItems:
                self["grid"].setCurrentIndex(self.lastSelection)
            else:
                self.selectionChanged()

        def updateIcons(self):
            items = []
            for idx in range(0, self.numOfItems):
                items.append((self.pixmapList[idx], self.currList[idx][0], idx, self.currList[idx][1]))

            self["grid"].updateList(items)

        def selectionChanged(self):
            if self.currList:
                idx = self["grid"].getSelectedIndex()
                if self.reorderingMode:
                    if self.moveIndex != -1:
                        self["statustext"].setText(_("MOVE: %s") % self.currList[self.moveIndex][0])
                        if self.moveIndex != idx:
                            def move_element(lst, from_index, to_index):
                                element = lst.pop(from_index)
                                lst.insert(to_index, element)
                                return lst
                            move_element(self.currList, self.moveIndex, idx)
                            move_element(self.pixmapList, self.moveIndex, idx)
                            self.moveIndex = idx
                            self.reInitDisplayList()
                        return
                self["statustext"].setText(self.currList[idx][0])

        def __onClose(self):
            self.onClose.remove(self.__onClose)
            try:
                if self.reorderingMode and self.numOfLockedItems > 0:
                    self.currList.extend(self.inList[len(self.inList) - self.numOfLockedItems:])

                if self.outList != self.currList:
                    for item in self.currList:
                        self.outList.append(item)
            except Exception:
                printExc()
            idx = self["grid"].getSelectedIndex()
            printDBG(">>>>>>>>>>>>>>>>>>>>>>>>>>> __onClose idx[%s]" % idx)
            PlayerSelectorWidget.LAST_SELECTION[self.groupName] = idx

        def keyCancel(self):
            printDBG(">> PlayerSelectorWidget.keyCancel")
            self.close(None)

        def keyUp(self):
            # explicit up/down bindings instead of relying on eListbox's
            # own focus-based key handling - confirmed necessary on at
            # least one Enigma2 fork (OpenViX), where up/down did nothing
            # without this (same portability gap as setSelectionPixmap
            # being missing there). Uses getSelectedIndex()/setCurrentIndex()
            # rather than instance.moveSelection(instance.moveUp), which
            # turned out not to move the selection on that same OpenViX box.
            idx = self["grid"].getSelectedIndex()
            if idx > 0:
                self["grid"].setCurrentIndex(idx - 1)
                self._invalidateGrid()

        def keyDown(self):
            idx = self["grid"].getSelectedIndex()
            if idx < self.numOfItems - 1:
                self["grid"].setCurrentIndex(idx + 1)
                self._invalidateGrid()

        def _invalidateGrid(self):
            # setCurrentIndex() moves the eListbox's internal selection
            # index, but on that same OpenViX box the row doesn't actually
            # repaint on its own afterwards - same underlying repaint gap
            # setReorderingHighlight()/setSelectionImage() already work
            # around elsewhere in this file by calling .invalidate() right
            # after changing selection-related state
            instance = self["grid"].instance if self.listMode else self["grid"].master.master.instance
            instance.invalidate()

        def setSelectionImage(self, move):
            if self.simpleListMode:
                # no marker/frame overlay in simple mode - just the plain
                # default listbox highlight from the skin's own
                # backgroundColorSelected, and reordering never triggers
                # this with move == "Sel" anyway since it can't be entered
                return
            if self.listMode:
                # frame: yellow for the whole reordering session (from
                # entering it until leaving it), not just while an item is
                # actively picked up - background: yellow only while an
                # item is actually picked up for moving (move == "Sel")
                self["grid"].setReorderingHighlight(self.reorderingMode, move == "Sel")
                return
            # same two independent states as list mode's setReorderingHighlight():
            # frame yellow ("Sel" marker) for the whole reordering session,
            # not just while an item is actively picked up - background
            # yellow only while move == "Sel" (actually picked up)
            file = resolveFilename(SCOPE_PLUGINS, f'Extensions/IPTVPlayer/icons/PlayerSelector/Marker/marker{"Sel" if self.reorderingMode else ""}{self.iconSize + 45}.png')
            _setSelectionPixmap(self["grid"].master.master.instance, file)
            # same yellow-while-picked-up background as list mode - "#24111112"
            # is the skin's own normal backgroundColorSelected for this widget
            self["grid"].master.master.instance.setBackgroundColorSelected(parseColor("#ffcc00" if move == "Sel" else "#24111112"))

        def keySelect(self):
            if self.reorderingMode:
                if self.moveIndex == -1:
                    self.setSelectionImage("Sel")
                    if not self.listMode:
                        self["grid"].master.master.instance.invalidate()
                    self.moveIndex = self["grid"].getSelectedIndex()
                else:
                    self.moveIndex = -1
                    self.setSelectionImage("")
                    self.reInitDisplayList()
                self.selectionChanged()
                return

            idx = self["grid"].getSelectedIndex()
            PlayerSelectorWidget.LAST_SELECTION[self.groupName] = idx

            if idx < self.numOfItems:
                self.close(self.currList[idx])
            else:
                self.close(None)
            return

        def keySetup(self):
            self.close((_("Configuration"), "config"))

        def keyBlue(self):
            printDBG(">> PlayerSelectorWidget.keyMenu")
            if self.currList:
                options = []
                selItem = self.getSelectedItem()
                if not self.simpleListMode and self.groupObj is not None and selItem is not None and len(self.groupObj.getGroupsWithoutHost(selItem[1])):
                    options.append((_("Add host %s to group") % selItem[0], "ADD_HOST_TO_GROUP"))

                if not self.simpleListMode:
                    if not self.reorderingMode and self.numOfItems - self.numOfLockedItems > 0:
                        options.append((_("Enable reordering mode"), "CHANGE_REORDERING_MODE"))
                    elif self.reorderingMode:
                        options.append((_("Disable reordering mode"), "CHANGE_REORDERING_MODE"))
                    options.append((_("Sort by name"), "SORT_NAME"))
                    options.append((_("Search"), "SEARCH"))
                options.append((_("Download manager"), "IPTVDM"))
                if not self.simpleListMode:
                    if self.groupName in ['selecthost', 'all']:
                        options.append((_("Disable/Enable services"), "config_hosts"))
                    elif self.groupName in ['selectgroup']:
                        options.append((_("Disable/Enable groups"), "config_groups"))
                    else:
                        options.append((_("Reset group"), "reset_group"))

                if not self.simpleListMode:
                    if self.groupName == 'selecthost':
                        pass
                    elif self.groupName == 'selectgroup':
                        if selItem[1] not in ['update', 'config', 'all']:
                            options.append((_('Hide "%s" group') % selItem[0], "DEL_ITEM"))
                    elif self.groupName not in ['all']:
                        options.append((_('Remove "%s" item') % selItem[0], "DEL_ITEM"))

                options.append((_("Settings"), "SETTINGS"))
                options.append((_("Info"), "INFO"))

                if len(options):
                    self.session.openWithCallback(self.selectMenuCallback, ChoiceBox, title=_("Select option"), list=options)

        def selectMenuCallback(self, ret):
            printDBG(">> PlayerSelectorWidget.selectMenuCallback")
            if ret:
                ret = ret[1]
                if ret == "SORT_NAME":
                    self.moveIndex = -1
                    self.reorderingMode = False
                    self.currList = sorted(self.currList, key=lambda x: x[1])
                    self.pixmapList = []
                    for idx in range(self.numOfItems):
                        icon = _getPlayerSelectorIcon(self.currList[idx][1], self.iconSize)
                        self.pixmapList.append(LoadPixmap(icon))
                    self.reInitDisplayList()
                elif ret == "CHANGE_REORDERING_MODE":
                    self.changeReorderingMode()
                elif ret == "IPTVDM":
                    self.close((_("Download manager"), "IPTVDM"))
                elif ret == "reset_group":
                    def keyDefaultsConfirm(result):
                        if result:
                            self.close((_("Disable not used services"), "reset_group", self.groupName))
                    message = _("Are you sure you want to reset all hosts in this group to defaults?")
                    self.session.openWithCallback(keyDefaultsConfirm, MessageBox, text=message, type=MessageBox.TYPE_YESNO)
                elif ret in ["config_hosts", "config_groups"]:
                    self.close((_("Disable not used services"), ret))
                elif ret == "ADD_HOST_TO_GROUP":
                    self.addHostToGroup()
                elif ret == 'DEL_ITEM':
                    self.deleteItemAt(self["grid"].getSelectedIndex())
                elif ret == 'INFO':
                    self.showInfo()
                elif ret == 'SETTINGS':
                    self.keySetup()
                elif ret == 'SEARCH':
                    self.openSearch()

        def openSearch(self):
            from Plugins.Extensions.IPTVPlayer.components.e2ivkselector import GetVirtualKeyboard
            caps = {}
            virtualKeyboard = GetVirtualKeyboard(caps)
            if caps.get('has_additional_params'):
                self.session.openWithCallback(self.searchCallback, virtualKeyboard, title=_("Search"), text='', additionalParams={})
            else:
                self.session.openWithCallback(self.searchCallback, virtualKeyboard, title=_("Search"), text='')

        def searchCallback(self, searchText=None):
            if not searchText:
                return
            query = searchText.strip().lower()
            if not query:
                return
            matches = [(item[0], item[1], idx) for idx, item in enumerate(self.currList) if query in item[0].lower() or query in item[1].lower()]
            if not matches:
                self.session.open(MessageBox, _("No matching entries found."), type=MessageBox.TYPE_INFO, timeout=5)
                return
            # picks straight from self.currList by index, so this only ever
            # shows/hides matches for this one search - it never touches
            # currList/pixmapList/outList itself, so reordering and the
            # group's persisted host list are completely unaffected
            options = [IPTVChoiceBoxItem("%s (%s)" % (name, hostKey), hostKey, idx) for name, hostKey, idx in matches]
            # self.listMode, not a direct "S" check - "P" (Simple list) is
            # also list-style and should get the same popup if this is ever
            # reached for it (currently unreachable in practice: keyBlue()
            # never offers "Search" when self.simpleListMode)
            if self.listMode:
                height = self._getSearchResultsHeight(len(options))
                self.session.openWithCallback(self.searchResultCallback, IPTVChoiceBoxWidget, {'width': 550, 'height': height, 'current_idx': 0, 'title': _("Search results"), 'options': options, 'list_class': IPTVHostSearchResultList, 'chrome': True, 'footerMargin': 120, 'blue_callback': self.searchResultBlueMenu})
            else:
                self.session.openWithCallback(self.searchResultCallback, SearchResultGridWidget, {'options': options, 'iconSize': self.iconSize, 'title': _("Search results"), 'blue_callback': self.searchResultBlueMenu})

        def searchResultCallback(self, ret=None):
            if not isinstance(ret, IPTVChoiceBoxItem):
                return
            idx = ret.privateData
            PlayerSelectorWidget.LAST_SELECTION[self.groupName] = idx
            self.close(self.currList[idx])

        def searchResultBlueMenu(self, item):
            # subset of keyBlue()'s options - just the two group-management
            # actions, since the rest (reordering/sort/download manager/
            # settings/info) don't apply to a single search result. Operates
            # on the item the user is looking at in the search popup, not
            # whatever happens to be selected in the main list behind it
            if not isinstance(item, IPTVChoiceBoxItem):
                return
            idx = item.privateData
            if idx >= self.numOfItems:
                return
            selItem = self.currList[idx]
            options = []
            if self.groupObj is not None and len(self.groupObj.getGroupsWithoutHost(selItem[1])):
                options.append((_("Add host %s to group") % selItem[0], "ADD_HOST_TO_GROUP"))
            if self.groupName == 'selecthost':
                pass
            elif self.groupName == 'selectgroup':
                if selItem[1] not in ['update', 'config', 'all']:
                    options.append((_('Hide "%s" group') % selItem[0], "DEL_ITEM"))
            elif self.groupName not in ['all']:
                options.append((_('Remove "%s" item') % selItem[0], "DEL_ITEM"))

            if options:
                self.session.openWithCallback(boundFunction(self.searchResultBlueMenuCallback, idx, selItem), ChoiceBox, title=_("Select option"), list=options)

        def searchResultBlueMenuCallback(self, idx, selItem, ret):
            if ret:
                ret = ret[1]
                if ret == "ADD_HOST_TO_GROUP":
                    self.addHostToGroup(selItem)
                elif ret == "DEL_ITEM":
                    self.deleteItemAt(idx)

        def _getSearchResultsHeight(self, numItems):
            # same reference-space-vs-real-pixels reasoning, and the same
            # footerMargin derivation, as E2iPlayerWidget's own
            # _getMoviePlayerPickerHeight (iptvplayerwidget.py) - can't
            # reuse that method directly since this is a different class,
            # so it's duplicated here instead. itemH comes from
            # _getSearchResultItemHeight() so this stays in sync with
            # IPTVHostSearchResultList's actual (enlarged) row height
            screenwidth = getDesktop(0).size().width()
            itemH = _getSearchResultItemHeight(screenwidth)
            scale = 2.0 if screenwidth >= 2560 else (1.5 if screenwidth >= 1920 else 1.0)
            height = int(numItems * itemH / scale) + 130
            # capped at skinListHD/skinHD's own reference-space height (660,
            # out of the chrome skin's 720-tall canvas) - with enough
            # matches this would otherwise grow past the screen edge. The
            # list widget already declares scrollbarMode="showOnDemand", so
            # once capped it scrolls instead of clipping. Since every tier's
            # own PlayerSelectorWidget popup is scaled up from this exact
            # same 660 reference value (see skinListHD/FHD/WQHD above), this
            # also keeps the search popup from ever growing taller than the
            # main list/grid popup, at any resolution.
            return min(height, 660)

        def showInfo(self):
            TextMSG = _('version') + " :\n" + GetIPTVPlayerVersion() + '\n\n'
            TextMSG += _("www:") + " " + "\nhttps://github.com/oe-mirrors/e2iplayer" + '\n\n'
            TextMSG += _("Developers:") + " " + "\n"
            developers = [
                'samsamsam',
                'zdzislaw22',
                'mamrot',
                'MarcinO',
                'skalita',
                'atilaks',
                'huball',
                'matzg',
                'tomashj291',
                'a4tech',
                'Blindspot76',
                'Max (maxbambi)',
                '-=Mario=- (zadmario)',
                'Lululla (Belfagor2005)',
                'jbleyel',
                'and others'
            ]
            TextMSG += ", ".join(developers)
            TextMSG += '\n\n' + _("Skinners:") + " " + "\n"
            TextMSG += ", ".join(('stein17', 'and others'))
            self.session.open(MessageBox, TextMSG, type=MessageBox.TYPE_INFO)

        def changeReorderingMode(self):
            printDBG(">> PlayerSelectorWidget.changeReorderingMode")
            if self.simpleListMode:
                return
            if self.currList:
                if not self.reorderingMode and (self.numOfItems - self.numOfLockedItems) > 0:
                    self.reorderingMode = True
                    self.setSelectionImage("Sel")
                    if not self.listMode:
                        self["grid"].master.master.instance.invalidate()
                    self.moveIndex = self["grid"].getSelectedIndex()
                else:
                    self.moveIndex = -1
                    self.reorderingMode = False
                    # reset the marker/highlight back to normal - without
                    # this, leaving reordering mode without ever dropping
                    # the picked-up item first left it stuck on the "Sel"
                    # (yellow/moving) look
                    self.setSelectionImage("")
                    if not self.listMode:
                        self["grid"].master.master.instance.invalidate()
                self.selectionChanged()

        def addHostToGroup(self, selItem=None):
            printDBG(">> PlayerSelectorWidget.addHostToGroup")
            if selItem is None:
                selItem = self.getSelectedItem()
            groupsList = self.groupObj.getGroupsWithoutHost(selItem[1])
            options = []
            for item in groupsList:
                options.append((item.title, item.name))

            if len(options):
                self.session.openWithCallback(boundFunction(self.addHostToGroupCallback, selItem), ChoiceBox, title=_("Select group"), list=options)

        def addHostToGroupCallback(self, selItem, ret):
            if ret:
                ret = ret[1]
                self.groupObj.addHostToGroup(ret, selItem[1])

        def deleteItemAt(self, idx):
            if idx < self.numOfItems:
                del self.currList[idx]
                del self.pixmapList[idx]
                self.reInitDisplayList()

        def getSelectedItem(self):
            printDBG(">> PlayerSelectorWidget.getSelectedItem")
            idx = self["grid"].getSelectedIndex()
            if idx < self.numOfItems:
                return self.currList[idx]
            return None

        def reInitDisplayList(self):
            self.numOfItems = len(self.currList)
            self.initDisplayList()

        def initDisplayList(self):
            self.updateIcons()

        def keyYellow(self):
            self.close((_("Download manager"), "IPTVDM"))

        def keyGreen(self):
            if self.simpleListMode:
                return
            self.close((_("Disable/Enable groups"), "config_groups"))

    class SearchResultGridWidget(Screen):
        # grid-mode counterpart to searchCallback()'s IPTVChoiceBoxWidget
        # popup (list mode) - used instead when hostsListType is "Graphic
        # services selector". Reuses PlayerSelectorWidget's own grid Listbox
        # widget/template block verbatim (same skin, position and sizing),
        # just with a trimmed-down footer (blue + ok/exit only - no sort/
        # reordering/download-manager/settings here). Closes with the
        # selected IPTVChoiceBoxItem, same as the list variant, so
        # PlayerSelectorWidget.searchResultCallback()/searchResultBlueMenu()
        # handle both without any changes
        def __init__(self, session, params):
            self.params = params
            self.options = params.get('options', [])
            self.numOfItems = len(self.options)
            self.iconSize = params.get('iconSize') or GetAvailableIconSize()
            screenwidth = getDesktop(0).size().width()
            FHD = screenwidth and screenwidth == 1920

            self.pixmapList = []
            for item in self.options:
                icon = _getPlayerSelectorIcon(item.description, self.iconSize)
                self.pixmapList.append(LoadPixmap(icon))

            skinHD = """
            <screen name="SearchResultGridWidget" position="center,center" size="1020,660" resolution="1280,720" title="E2iPlayer" backgroundColor="#34111112" flags="wfNoBorder">
                <widget source="Title" render="Label" position="160,10" size="780,40" foregroundColor="white" backgroundColor="black" borderWidth="1" borderColor="black" transparent="1" zPosition="1" font="Regular;24" valign="center" />
                <widget name="statustext" position="20,570" size="980,30" font="Regular;20" valign="center" halign="center" backgroundColor="black" foregroundColor="white" transparent="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/iptvlogo.png" position="12,10" size="100,40" zPosition="10" alphatest="blend" transparent="1" />
                <eLabel name="BG_Title" position="0,0" size="1020,60" backgroundColor="#100d0f16" zPosition="-1" />
                <eLabel name="BG_Buttons" position="0,612" size="1020,48" backgroundColor="#100d0f16" zPosition="-1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/smallshadowline.png" position="0,60" size="1020,2" zPosition="2" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/smallshadowline.png" position="0,610" size="1020,2" zPosition="2" />
                <widget source="grid" render="Listbox" position="20,72" size="980,492" conditional="grid" listOrientation="grid" scrollbarMode="showOnDemand" scrollbarSliderBorderWidth="1" scrollbarForegroundColor="#1b5a91" scrollbarBorderColor="#00b6b6b6" itemSpacing="20,20" itemAlignment="center" backgroundColorSelected="#24111112" transparent="1">
                    <templates>
                        <template name="Default" fonts="Regular;20">
                            <mode name="default" itemHeight="145" itemWidth="145">
                                <pixmap index="0" position="22,22" size="100,100" alpha="blend" scale="centerScaled" />
                            </mode>
                            <mode name="120" itemHeight="165" itemWidth="165">
                                <pixmap index="0" position="22,22" size="120,120" alpha="blend" scale="centerScaled" />
                            </mode>
                            <mode name="135" itemHeight="180" itemWidth="180">
                                <pixmap index="0" position="22,22" size="135,135" alpha="blend" scale="centerScaled" />
                            </mode>
                        </template>
                    </templates>
                </widget>
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/key_prevnext.png" position="22,624" size="40,26" alphatest="blend" transparent="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/ok.png" position="80,624" size="40,26" alphatest="blend" transparent="1" />
                <widget source="key_blue" render="Pixmap" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/blue.png" position="138,628" size="20,20" alphatest="blend" objectTypes="key_blue,StaticText" transparent="1">
                    <convert type="ConditionalShowHide" />
                </widget>
                <widget source="key_blue" render="Label" position="168,626" size="480,24" backgroundColor="#000000" font="Regular;17" foregroundColor="#ffffff" zPosition="+1" valign="center" halign="left" objectTypes="key_blue,StaticText" transparent="1" />
            </screen>
            """

            skinFHD = """
            <screen name="SearchResultGridWidget" position="center,center" size="1530,990" title="E2iPlayer" backgroundColor="#34111112" flags="wfNoBorder">
                <widget source="Title" render="Label" position="240,15" size="1170,60" foregroundColor="white" backgroundColor="black" borderWidth="2" borderColor="black" transparent="1" zPosition="1" font="Regular;36" valign="center" />
                <widget name="statustext" position="30,860" size="1470,45" font="Regular;30" valign="center" halign="center" backgroundColor="black" foregroundColor="white" transparent="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/iptvlogo.png" position="18,15" size="150,60" zPosition="10" alphatest="blend" transparent="1" />
                <eLabel name="BG_Title" position="0,0" size="1530,90" backgroundColor="#100d0f16" zPosition="-1" />
                <eLabel name="BG_Buttons" position="0,918" size="1530,72" backgroundColor="#100d0f16" zPosition="-1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/smallshadowline.png" position="0,90" size="1530,3" zPosition="2" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/smallshadowline.png" position="0,915" size="1530,3" zPosition="2" />
                <widget source="grid" render="Listbox" position="30,108" size="1470,738" conditional="grid" listOrientation="grid" scrollbarMode="showOnDemand" scrollbarSliderBorderWidth="1" scrollbarForegroundColor="#1b5a91" scrollbarBorderColor="#00b6b6b6" itemSpacing="20,20" itemAlignment="center" backgroundColorSelected="#24111112" transparent="1">
                    <templates>
                        <template name="Default" fonts="Regular;20">
                            <mode name="default" itemHeight="145" itemWidth="145">
                                <pixmap index="0" position="22,22" size="100,100" alpha="blend" scale="centerScaled" />
                            </mode>
                            <mode name="120" itemHeight="165" itemWidth="165">
                                <pixmap index="0" position="22,22" size="120,120" alpha="blend" scale="centerScaled" />
                            </mode>
                            <mode name="135" itemHeight="180" itemWidth="180">
                                <pixmap index="0" position="22,22" size="135,135" alpha="blend" scale="centerScaled" />
                            </mode>
                        </template>
                    </templates>
                </widget>
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/key_prevnext.png" position="33,936" size="60,39" alphatest="blend" transparent="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/ok.png" position="120,936" size="60,39" alphatest="blend" transparent="1" />
                <widget source="key_blue" render="Pixmap" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/blue.png" position="207,942" size="30,30" alphatest="blend" objectTypes="key_blue,StaticText" transparent="1">
                    <convert type="ConditionalShowHide" />
                </widget>
                <widget source="key_blue" render="Label" position="252,939" size="720,36" backgroundColor="#000000" font="Regular;26" foregroundColor="#ffffff" zPosition="+1" valign="center" halign="left" objectTypes="key_blue,StaticText" transparent="1" />
            </screen>
            """

            # native WQHD coordinates (no resolution= auto-scale attribute),
            # same reasoning and technique as PlayerSelectorWidget's own
            # skinWQHD above: every value is skinFHD's own value scaled by
            # 2560/1920 (4/3). ePixmap elements (logo/shadowlines/prevnext/
            # ok) get scale="1" so they actually stretch to their enlarged
            # box instead of rendering at native FHD size (the WQHD footer
            # bug fixed for PlayerSelectorWidget) - key_blue is a
            # source=/render="Pixmap" widget (needed for
            # ConditionalShowHide), which has shown unreliable stretching,
            # so its size stays at the FHD-native 30x30 rather than scaling
            # further.
            skinWQHD = """
            <screen name="SearchResultGridWidget" position="center,center" size="2040,1320" title="E2iPlayer" backgroundColor="#34111112" flags="wfNoBorder">
                <widget source="Title" render="Label" position="320,20" size="1560,80" foregroundColor="white" backgroundColor="black" borderWidth="2" borderColor="black" transparent="1" zPosition="1" font="Regular;48" valign="center" />
                <widget name="statustext" position="40,1147" size="1960,60" font="Regular;40" valign="center" halign="center" backgroundColor="black" foregroundColor="white" transparent="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/iptvlogo.png" position="24,20" size="200,80" scale="1" zPosition="10" alphatest="blend" transparent="1" />
                <eLabel name="BG_Title" position="0,0" size="2040,120" backgroundColor="#100d0f16" zPosition="-1" />
                <eLabel name="BG_Buttons" position="0,1224" size="2040,96" backgroundColor="#100d0f16" zPosition="-1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/smallshadowline.png" position="0,120" size="2040,4" scale="1" zPosition="2" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/smallshadowline.png" position="0,1220" size="2040,4" scale="1" zPosition="2" />
                <widget source="grid" render="Listbox" position="40,144" size="1960,984" conditional="grid" listOrientation="grid" scrollbarMode="showOnDemand" scrollbarSliderBorderWidth="1" scrollbarForegroundColor="#1b5a91" scrollbarBorderColor="#00b6b6b6" itemSpacing="20,20" itemAlignment="center" backgroundColorSelected="#24111112" transparent="1">
                    <templates>
                        <template name="Default" fonts="Regular;20">
                            <mode name="default" itemHeight="145" itemWidth="145">
                                <pixmap index="0" position="22,22" size="100,100" alpha="blend" scale="centerScaled" />
                            </mode>
                            <mode name="120" itemHeight="165" itemWidth="165">
                                <pixmap index="0" position="22,22" size="120,120" alpha="blend" scale="centerScaled" />
                            </mode>
                            <mode name="135" itemHeight="180" itemWidth="180">
                                <pixmap index="0" position="22,22" size="135,135" alpha="blend" scale="centerScaled" />
                            </mode>
                        </template>
                    </templates>
                </widget>
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/key_prevnext.png" position="44,1248" size="80,52" scale="1" alphatest="blend" transparent="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/ok.png" position="160,1248" size="80,52" scale="1" alphatest="blend" transparent="1" />
                <widget source="key_blue" render="Pixmap" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/WQHD/blue.png" position="276,1256" size="40,40" alphatest="blend" objectTypes="key_blue,StaticText" transparent="1">
                    <convert type="ConditionalShowHide" />
                </widget>
                <widget source="key_blue" render="Label" position="328,1252" size="960,48" backgroundColor="#000000" font="Regular;35" foregroundColor="#ffffff" zPosition="+1" valign="center" halign="left" objectTypes="key_blue,StaticText" transparent="1" />
            </screen>
            """

            WQHD = screenwidth and screenwidth >= 2560
            self.skin = skinWQHD if WQHD else (skinFHD if FHD else skinHD)
            Screen.__init__(self, session, mandatoryWidgets=["grid"])
            self.skinName = ["SearchResultGridScreen", "SearchResultGridWidget"]

            self.setTitle(params.get('title', _("Search results")))
            self["key_blue"] = StaticText(_("More") if params.get('blue_callback') else "")
            self["grid"] = List([])
            self["grid"].onSelectionChanged.append(self.selectionChanged)
            self["statustext"] = Label(self.options[0].name if self.options else "")

            self["actions"] = ActionMap(["OkCancelActions", "ColorActions"], {
                "ok": self.keySelect,
                "cancel": self.keyCancel,
                "blue": self.keyBlue,
            }, -1)

            self.onLayoutFinish.append(self.layoutFinished)

        def layoutFinished(self):
            self.updateIcons()
            self["grid"].setStyle(str(self.iconSize) if self.iconSize in [120, 135] else "default")
            # same active-cell marker frame PlayerSelectorWidget's own grid
            # mode uses (plain backgroundColorSelected on its own is barely
            # visible) - no reordering here, so only ever the "not picked
            # up" variant, never markerSel...
            file = resolveFilename(SCOPE_PLUGINS, 'Extensions/IPTVPlayer/icons/PlayerSelector/Marker/marker%i.png' % (self.iconSize + 45))
            _setSelectionPixmap(self["grid"].master.master.instance, file)
            if self.options:
                self["grid"].setCurrentIndex(0)
            else:
                self.selectionChanged()

        def updateIcons(self):
            items = []
            for idx in range(self.numOfItems):
                items.append((self.pixmapList[idx], self.options[idx].name, idx))
            self["grid"].updateList(items)

        def selectionChanged(self):
            if self.options:
                idx = self["grid"].getSelectedIndex()
                if idx < self.numOfItems:
                    self["statustext"].setText(self.options[idx].name)

        def keySelect(self):
            idx = self["grid"].getSelectedIndex()
            if idx < self.numOfItems:
                self.close(self.options[idx])
            else:
                self.close(None)

        def keyCancel(self):
            self.close(None)

        def keyBlue(self):
            callback = self.params.get('blue_callback')
            if callable(callback) and self.options:
                idx = self["grid"].getSelectedIndex()
                if idx < self.numOfItems:
                    callback(self.options[idx])


else:

    class PlayerSelectorWidget(Screen):
        LAST_SELECTION = {}

        def __init__(self, session, inList, outList, numOfLockedItems=0, groupName='', groupObj=None, groupDisplayName=None):
            printDBG("PlayerSelectorWidget.__init__ --------------------------------")
            screenwidth = getDesktop(0).size().width()
            iconSize = GetAvailableIconSize()
            # "S" (List view) and "P" (Simple list) reuse the exact same
            # eListboxPythonMultiContent-based list widget/chrome skin the
            # GRIDSUPPORT class's own list mode uses below. That widget has
            # no GRIDSUPPORT/OpenATV dependency at all, unlike the per-cell
            # Cover3 grid this class otherwise uses (which does need
            # eListbox.orGrid-adjacent skin support) - proof: this class's
            # own search-results popup (searchCallback() below) already
            # uses the identical widget/chrome without issue today.
            self.listMode = config.plugins.iptvplayer.hostsListType.value in ("S", "P")
            self.simpleListMode = config.plugins.iptvplayer.hostsListType.value == "P"

            self.inList = list(inList)
            self.currList = self.inList
            self.outList = outList
            self.numOfItems = len(self.currList)

            self.groupName = groupName
            self.groupObj = groupObj
            self.numOfLockedItems = numOfLockedItems

            self.IconsSize = iconSize  # do ladowania ikon
            self.MarkerSize = self.IconsSize + 45

            self.lastSelection = PlayerSelectorWidget.LAST_SELECTION.get(self.groupName, 0)

            self.session = session
            self.reorderingMode = False
            self.reorderingItemSelected = False
            self.moveIndex = -1

            if self.listMode:
                self.__initListMode(groupDisplayName, screenwidth)
                return

            if len(inList) >= 30 and iconSize == 100 and screenwidth and screenwidth > 1100:
                numOfRow = 4
                numOfCol = 8
            elif len(inList) > 16 and iconSize == 100:
                numOfRow = 4
                numOfCol = 5
            elif len(inList) > 12 and iconSize == 100:
                numOfRow = 4
                numOfCol = 4
            elif len(inList) > 9:
                if screenwidth and screenwidth == 1920:
                    numOfRow = 4
                    numOfCol = 8
                else:
                    numOfRow = 3
                    numOfCol = 4
            elif len(inList) > 6:
                numOfRow = 3
                numOfCol = 3
            elif len(inList) > 3:
                numOfRow = 2
                numOfCol = 3
            else:
                numOfRow = 1
                numOfCol = 3

            try:
                confNumOfRow = int(config.plugins.iptvplayer.numOfRow.value)
                confNumOfCol = int(config.plugins.iptvplayer.numOfCol.value)
                # 0 - means AUTO
                if confNumOfRow > 0:
                    numOfRow = confNumOfRow
                if confNumOfCol > 0:
                    numOfCol = confNumOfCol
            except Exception:
                pass

            # position of first img
            offsetCoverX = 25
            if screenwidth and screenwidth == 1920:
                offsetCoverY = 100
            else:
                offsetCoverY = 80

            # image size
            coverWidth = iconSize
            coverHeight = iconSize

            # space/distance between images
            disWidth = int(coverWidth / 3)
            disHeight = int(coverHeight / 4)

            # marker size should be larger than img
            markerWidth = 45 + coverWidth
            markerHeight = 45 + coverHeight

            # position of first marker
            offsetMarkerX = int(offsetCoverX - (markerWidth - coverWidth) / 2)
            offsetMarkerY = int(offsetCoverY - (markerHeight - coverHeight) / 2)

            # how to calculate position of image with indexes indxX, indxY:
            # posX = offsetCoverX + (coverWidth + disWidth) * indxX
            # posY = offsetCoverY + (coverHeight + disHeight) * indxY

            # how to calculate position of marker for image with posX, posY
            # markerPosX = posX - (markerWidth - coverWidth)/2
            # markerPosY = posY - (markerHeight - coverHeight)/2

            tmpX = coverWidth + disWidth
            tmpY = coverHeight + disHeight

            self.numOfRow = numOfRow
            self.numOfCol = numOfCol
            # position of first cover
            self.offsetCoverX = offsetCoverX
            self.offsetCoverY = offsetCoverY
            # space/distance between images
            self.disWidth = disWidth
            self.disHeight = disHeight
            # image size
            self.coverWidth = coverWidth
            self.coverHeight = coverHeight
            # marker size should be larger than img
            self.markerWidth = markerWidth
            self.markerHeight = markerHeight

            self.calcDisplayVariables()

            # pagination
            self.pageItemSize = 16
            self.pageItemStartX = int((offsetCoverX + tmpX * numOfCol + offsetCoverX - disWidth - self.numOfPages * self.pageItemSize) / 2)
            if screenwidth and screenwidth == 1920:
                self.pageItemStartY = 60
            else:
                self.pageItemStartY = 40

            if screenwidth and screenwidth == 1920:
                # wenn einer die version einbauen will <widget name="IptvVersion" position="40,0" zPosition="1" size="250,50" font="Regular;36" halign="center" valign="center" transparent="1"/>
                skin = """
                <screen name="PlayerSelectorWidget" position="center,center" title="E2iPlayer %s" size="%d,%d">
                <widget name="statustext" position="0,0" zPosition="1" size="%d,50" font="Regular;36" halign="center" valign="center" transparent="1"/>
                <widget name="marker" zPosition="2" position="%d,%d" size="%d,%d" transparent="1" alphatest="blend" />
                <widget name="page_marker" zPosition="3" position="%d,%d" size="%d,%d" transparent="1" alphatest="blend" />
                <widget name="menu" zPosition="3" position="%d,10" size="70,30" transparent="1" alphatest="blend" />
                """ % (
                GetIPTVPlayerVersion(),
                offsetCoverX + tmpX * numOfCol + offsetCoverX - disWidth,  # width of window
                offsetCoverY + tmpY * numOfRow + offsetCoverX - disHeight,  # height of window
                offsetCoverX + tmpX * numOfCol + offsetCoverX - disWidth,  # width of status line
                offsetMarkerX, offsetMarkerY,  # first marker position
                markerWidth, markerHeight,    # marker size
                self.pageItemStartX, self.pageItemStartY,  # pagination marker
                self.pageItemSize, self.pageItemSize,
                offsetCoverX + tmpX * numOfCol + offsetCoverX - disWidth - 70,
                )
            else:
                skin = """
                <screen name="PlayerSelectorWidget" position="center,center" title="E2iPlayer %s" size="%d,%d">
                <widget name="statustext" position="0,0" zPosition="1" size="%d,50" font="Regular;26" halign="center" valign="center" transparent="1"/>
                <widget name="marker" zPosition="2" position="%d,%d" size="%d,%d" transparent="1" alphatest="blend" />
                <widget name="page_marker" zPosition="3" position="%d,%d" size="%d,%d" transparent="1" alphatest="blend" />
                <widget name="menu" zPosition="3" position="%d,10" size="70,30" transparent="1" alphatest="blend" />
                """ % (
                GetIPTVPlayerVersion(),
                offsetCoverX + tmpX * numOfCol + offsetCoverX - disWidth,  # width of window
                offsetCoverY + tmpY * numOfRow + offsetCoverX - disHeight,  # height of window
                offsetCoverX + tmpX * numOfCol + offsetCoverX - disWidth,  # width of status line
                offsetMarkerX, offsetMarkerY,  # first marker position
                markerWidth, markerHeight,    # marker size
                self.pageItemStartX, self.pageItemStartY,  # pagination marker
                self.pageItemSize, self.pageItemSize,
                offsetCoverX + tmpX * numOfCol + offsetCoverX - disWidth - 70,
                )

            for y in range(1, numOfRow + 1):
                for x in range(1, numOfCol + 1):
                    skinCoverLine = """<widget name="cover_%s%s" zPosition="4" position="%d,%d" size="%d,%d" transparent="1" alphatest="blend" />""" % (x, y,
                        (offsetCoverX + tmpX * (x - 1)),  # pos X image
                        (offsetCoverY + tmpY * (y - 1)),  # pos Y image
                        coverWidth,
                        coverHeight
                    )
                    skin += '\n' + skinCoverLine

            # add pagination items
            for pageItemOffset in range(self.numOfPages):
                pageItemX = self.pageItemStartX + pageItemOffset * self.pageItemSize
                skinCoverLine = """<ePixmap zPosition="2" position="%d,%d" size="%d,%d" pixmap="%s" transparent="1" alphatest="blend" />""" % (pageItemX, self.pageItemStartY, self.pageItemSize, self.pageItemSize, GetIconDir('radio_button_off.png'))
                skin += '\n' + skinCoverLine
            skin += '</screen>'
            self.skin = skin

            Screen.__init__(self, session)

            self.session.nav.event.append(self.__event)
            self.onClose.append(self.__onClose)

            # load icons
            self.pixmapList = []
            for idx in range(0, self.numOfItems):
                icon = _getPlayerSelectorIcon(self.currList[idx][1], self.IconsSize)
                self.pixmapList.append(LoadPixmap(icon))

            self.markerPixmap = LoadPixmap(GetIconDir('PlayerSelector/Marker/marker%i.png' % self.MarkerSize))
            self.markerPixmapSel = LoadPixmap(GetIconDir('PlayerSelector/Marker/markerSel%i.png' % self.MarkerSize))
            self.pageMarkerPixmap = LoadPixmap(GetIconDir('radio_button_on.png'))
            self.menuPixmap = LoadPixmap(GetIconDir('menu.png'))

            self["actions"] = ActionMap(["DirectionActions", "ColorActions", "IPTVPlayerListActions"],
            {
                "ok": self.ok_pressed,
                "back": self.back_pressed,
                "left": self.keyLeft,
                "right": self.keyRight,
                "up": self.keyUp,
                "down": self.keyDown,
                "blue": self.keyBlue,
                "menu": self.keyMenu,
            }, -1)

            self["marker"] = Cover3()
            self["page_marker"] = Cover3()
            self['IptvVersion'] = Label(GetIPTVPlayerVersion())
            self["menu"] = Cover3()

            for y in range(1, self.numOfRow + 1):
                for x in range(1, self.numOfCol + 1):
                    strIndex = "cover_%s%s" % (x, y)
                    self[strIndex] = Cover3()

            self["statustext"] = Label(self.currList[0][0])

            self.onLayoutFinish.append(self.onStart)
            self.visible = True

        # "List view"/"Simple list" mode - same chrome skin and
        # PlayerSelectorHostList/PlayerSelectorSimpleList widget as the
        # GRIDSUPPORT class's own list mode (skinListHD/FHD/WQHD copied
        # verbatim from there - already proven this session, and matching
        # them exactly keeps both classes' list mode looking identical).
        # Grid mode above (numOfRow/numOfCol Cover3 layout) is completely
        # untouched by this - __init__ returns right after calling this.
        def __initListMode(self, groupDisplayName, screenwidth):
            FHD = screenwidth and screenwidth == 1920
            WQHD = screenwidth and screenwidth >= 2560
            # manual scroll window (self.windowStart) - see updateIcons()
            # and _updateScrollWindow() below
            self.visibleRows = _getListVisibleRows(screenwidth)
            self.windowStart = 0

            skinListHD = """
            <screen name="PlayerSelectorWidget" position="center,center" size="1020,660" resolution="1280,720" title="E2iPlayer" backgroundColor="#34111112" flags="wfNoBorder">
                <widget source="Title" render="Label" position="160,10" size="780,40" foregroundColor="white" backgroundColor="black" borderWidth="1" borderColor="black" transparent="1" zPosition="1" font="Regular;24" valign="center" />
                <widget name="statustext" position="20,570" size="980,30" font="Regular;20" valign="center" halign="center" backgroundColor="black" foregroundColor="white" transparent="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/iptvlogo.png" position="12,10" size="100,40" zPosition="10" alphatest="blend" transparent="1" />
                <eLabel name="BG_Title" position="0,0" size="1020,60" backgroundColor="#100d0f16" zPosition="-1" />
                <eLabel name="BG_Buttons" position="0,612" size="1020,48" backgroundColor="#100d0f16" zPosition="-1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/smallshadowline.png" position="0,60" size="1020,2" zPosition="2" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/smallshadowline.png" position="0,610" size="1020,2" zPosition="2" />
                <widget name="categorytext" position="20,70" size="980,30" font="Regular;20" valign="center" halign="center" backgroundColor="black" foregroundColor="white" transparent="1" />
                <widget name="grid" position="20,104" size="980,460" conditional="grid" scrollbarMode="showAlways" scrollbarSliderBorderWidth="1" scrollbarForegroundColor="#1b5a91" scrollbarBorderColor="#00b6b6b6" enableWrapAround="1" transparent="1" foregroundColor="white" backgroundColor="black" backgroundColorSelected="#1b5a91" foregroundColorSelected="white" />
                <widget source="key_menu" render="Pixmap" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/menu.png" position="16,624" size="40,26" conditional="key_menu" alphatest="blend">
                    <convert type="ConditionalShowHide" />
                </widget>
                <widget source="key_red" render="Pixmap" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/red.png" position="180,628" size="20,20" alphatest="blend" objectTypes="key_red,StaticText" transparent="1">
                    <convert type="ConditionalShowHide" />
                </widget>
                <widget source="key_red" render="Label" position="210,626" size="180,24" backgroundColor="#000000" font="Regular;17" foregroundColor="#ffffff" zPosition="+1" valign="center" halign="left" objectTypes="key_red,StaticText" transparent="1" />
                <widget source="key_green" render="Pixmap" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/green.png" position="390,628" size="20,20" alphatest="blend" objectTypes="key_green,StaticText" transparent="1">
                    <convert type="ConditionalShowHide" />
                </widget>
                <widget source="key_green" render="Label" position="420,626" size="180,24" backgroundColor="#000000" font="Regular;17" foregroundColor="#ffffff" zPosition="+1" valign="center" halign="left" objectTypes="key_green,StaticText" transparent="1" />
                <widget source="key_yellow" render="Pixmap" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/yellow.png" position="600,628" size="20,20" alphatest="blend" objectTypes="key_yellow,StaticText" transparent="1">
                    <convert type="ConditionalShowHide" />
                </widget>
                <widget source="key_yellow" render="Label" position="630,626" size="180,24" backgroundColor="#000000" font="Regular;17" foregroundColor="#ffffff" zPosition="+1" valign="center" halign="left" objectTypes="key_yellow,StaticText" transparent="1" />
                <widget source="key_blue" render="Pixmap" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/blue.png" position="810,628" size="20,20" alphatest="blend" objectTypes="key_blue,StaticText" transparent="1">
                    <convert type="ConditionalShowHide" />
                </widget>
                <widget source="key_blue" render="Label" position="840,626" size="180,24" backgroundColor="#000000" font="Regular;17" foregroundColor="#ffffff" zPosition="+1" valign="center" halign="left" objectTypes="key_blue,StaticText" transparent="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/key_prevnext.png" position="70,624" size="40,26" alphatest="blend" transparent="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/ok.png" position="124,624" size="40,26" alphatest="blend" transparent="1" />
            </screen>
            """

            skinListFHD = """
            <screen name="PlayerSelectorWidget" position="center,center" size="1530,990" title="E2iPlayer" backgroundColor="#34111112" flags="wfNoBorder">
                <widget source="Title" render="Label" position="240,15" size="1170,60" foregroundColor="white" backgroundColor="black" borderWidth="2" borderColor="black" transparent="1" zPosition="1" font="Regular;36" valign="center" />
                <widget name="statustext" position="30,860" size="1470,45" font="Regular;30" valign="center" halign="center" backgroundColor="black" foregroundColor="white" transparent="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/iptvlogo.png" position="18,15" size="150,60" zPosition="10" alphatest="blend" transparent="1" />
                <eLabel name="BG_Title" position="0,0" size="1530,90" backgroundColor="#100d0f16" zPosition="-1" />
                <eLabel name="BG_Buttons" position="0,918" size="1530,72" backgroundColor="#100d0f16" zPosition="-1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/smallshadowline.png" position="0,90" size="1530,3" zPosition="2" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/smallshadowline.png" position="0,915" size="1530,3" zPosition="2" />
                <widget name="categorytext" position="30,100" size="1470,45" font="Regular;30" valign="center" halign="center" backgroundColor="black" foregroundColor="white" transparent="1" />
                <widget name="grid" position="30,150" size="1470,705" conditional="grid" scrollbarMode="showAlways" scrollbarSliderBorderWidth="1" scrollbarForegroundColor="#1b5a91" scrollbarBorderColor="#00b6b6b6" enableWrapAround="1" transparent="1" foregroundColor="white" backgroundColor="black" backgroundColorSelected="#1b5a91" foregroundColorSelected="white" />
                <widget source="key_menu" render="Pixmap" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/menu.png" position="24,936" size="60,39" conditional="key_menu" alphatest="blend">
                    <convert type="ConditionalShowHide" />
                </widget>
                <widget source="key_red" render="Pixmap" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/red.png" position="270,942" size="30,30" alphatest="blend" objectTypes="key_red,StaticText" transparent="1">
                    <convert type="ConditionalShowHide" />
                </widget>
                <widget source="key_red" render="Label" position="315,939" size="270,36" backgroundColor="#000000" font="Regular;26" foregroundColor="#ffffff" zPosition="+1" valign="center" halign="left" objectTypes="key_red,StaticText" transparent="1" />
                <widget source="key_green" render="Pixmap" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/green.png" position="585,942" size="30,30" alphatest="blend" objectTypes="key_green,StaticText" transparent="1">
                    <convert type="ConditionalShowHide" />
                </widget>
                <widget source="key_green" render="Label" position="630,939" size="270,36" backgroundColor="#000000" font="Regular;26" foregroundColor="#ffffff" zPosition="+1" valign="center" halign="left" objectTypes="key_green,StaticText" transparent="1" />
                <widget source="key_yellow" render="Pixmap" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/yellow.png" position="900,942" size="30,30" alphatest="blend" objectTypes="key_yellow,StaticText" transparent="1">
                    <convert type="ConditionalShowHide" />
                </widget>
                <widget source="key_yellow" render="Label" position="945,939" size="270,36" backgroundColor="#000000" font="Regular;26" foregroundColor="#ffffff" zPosition="+1" valign="center" halign="left" objectTypes="key_yellow,StaticText" transparent="1" />
                <widget source="key_blue" render="Pixmap" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/blue.png" position="1215,942" size="30,30" alphatest="blend" objectTypes="key_blue,StaticText" transparent="1">
                    <convert type="ConditionalShowHide" />
                </widget>
                <widget source="key_blue" render="Label" position="1260,939" size="270,36" backgroundColor="#000000" font="Regular;26" foregroundColor="#ffffff" zPosition="+1" valign="center" halign="left" objectTypes="key_blue,StaticText" transparent="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/key_prevnext.png" position="105,936" size="60,39" alphatest="blend" transparent="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/ok.png" position="186,936" size="60,39" alphatest="blend" transparent="1" />
            </screen>
            """

            skinListWQHD = """
            <screen name="PlayerSelectorWidget" position="center,center" size="2040,1320" title="E2iPlayer" backgroundColor="#34111112" flags="wfNoBorder">
                <widget source="Title" render="Label" position="320,20" size="1560,80" foregroundColor="white" backgroundColor="black" borderWidth="2" borderColor="black" transparent="1" zPosition="1" font="Regular;48" valign="center" />
                <widget name="statustext" position="40,1147" size="1960,60" font="Regular;40" valign="center" halign="center" backgroundColor="black" foregroundColor="white" transparent="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/iptvlogo.png" position="24,20" size="200,80" scale="1" zPosition="10" alphatest="blend" transparent="1" />
                <eLabel name="BG_Title" position="0,0" size="2040,120" backgroundColor="#100d0f16" zPosition="-1" />
                <eLabel name="BG_Buttons" position="0,1224" size="2040,96" backgroundColor="#100d0f16" zPosition="-1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/smallshadowline.png" position="0,120" size="2040,4" scale="1" zPosition="2" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/smallshadowline.png" position="0,1220" size="2040,4" scale="1" zPosition="2" />
                <widget name="grid" position="40,200" size="1960,940" conditional="grid" scrollbarMode="showAlways" scrollbarSliderBorderWidth="1" scrollbarForegroundColor="#1b5a91" scrollbarBorderColor="#00b6b6b6" enableWrapAround="1" transparent="1" foregroundColor="white" backgroundColor="black" backgroundColorSelected="#1b5a91" foregroundColorSelected="white" />
                <widget source="key_menu" render="Pixmap" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/WQHD/menu.png" position="32,1248" size="80,52" conditional="key_menu" alphatest="blend">
                    <convert type="ConditionalShowHide" />
                </widget>
                <widget source="key_red" render="Pixmap" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/WQHD/red.png" position="360,1256" size="40,40" alphatest="blend" objectTypes="key_red,StaticText" transparent="1">
                    <convert type="ConditionalShowHide" />
                </widget>
                <widget source="key_red" render="Label" position="412,1252" size="360,48" backgroundColor="#000000" font="Regular;35" foregroundColor="#ffffff" zPosition="+1" valign="center" halign="left" objectTypes="key_red,StaticText" transparent="1" />
                <widget source="key_green" render="Pixmap" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/WQHD/green.png" position="780,1256" size="40,40" alphatest="blend" objectTypes="key_green,StaticText" transparent="1">
                    <convert type="ConditionalShowHide" />
                </widget>
                <widget source="key_green" render="Label" position="832,1252" size="360,48" backgroundColor="#000000" font="Regular;35" foregroundColor="#ffffff" zPosition="+1" valign="center" halign="left" objectTypes="key_green,StaticText" transparent="1" />
                <widget source="key_yellow" render="Pixmap" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/WQHD/yellow.png" position="1200,1256" size="40,40" alphatest="blend" objectTypes="key_yellow,StaticText" transparent="1">
                    <convert type="ConditionalShowHide" />
                </widget>
                <widget source="key_yellow" render="Label" position="1252,1252" size="360,48" backgroundColor="#000000" font="Regular;35" foregroundColor="#ffffff" zPosition="+1" valign="center" halign="left" objectTypes="key_yellow,StaticText" transparent="1" />
                <widget source="key_blue" render="Pixmap" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/WQHD/blue.png" position="1620,1256" size="40,40" alphatest="blend" objectTypes="key_blue,StaticText" transparent="1">
                    <convert type="ConditionalShowHide" />
                </widget>
                <widget source="key_blue" render="Label" position="1672,1252" size="360,48" backgroundColor="#000000" font="Regular;35" foregroundColor="#ffffff" zPosition="+1" valign="center" halign="left" objectTypes="key_blue,StaticText" transparent="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/key_prevnext.png" position="140,1248" size="80,52" scale="1" alphatest="blend" transparent="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/ok.png" position="248,1248" size="80,52" scale="1" alphatest="blend" transparent="1" />
            </screen>
            """

            self.skin = skinListWQHD if WQHD else (skinListFHD if FHD else skinListHD)
            Screen.__init__(self, self.session, mandatoryWidgets=["grid"])
            self.skinName = ["PlayerSelectorScreen", "PlayerSelectorWidget"]

            self.session.nav.event.append(self.__event)
            self.onClose.append(self.__onClose)

            self["key_menu"] = StaticText(_("MENU"))
            self["key_red"] = StaticText("" if self.simpleListMode else _("Sort Mode"))
            self["key_green"] = StaticText("" if self.simpleListMode else _("Hide/Active Group"))
            self["key_yellow"] = StaticText(_("Download manager"))
            self["key_blue"] = StaticText(_("More"))
            if self.simpleListMode:
                self["grid"] = PlayerSelectorSimpleList()
            else:
                self["grid"] = PlayerSelectorHostList()
            # this platform's eListbox doesn't move its own selection
            # cursor (see layoutFinished()/setReorderingHighlight() below)
            self["grid"].useNativeHighlight = False
            self["grid"].showHostKey = (self.groupName != 'selectgroup')
            self["grid"].onSelectionChanged.append(self.selectionChanged)

            self["statustext"] = Label(self.currList[0][0] if self.currList else "")
            self["categorytext"] = Label(groupDisplayName if groupDisplayName else "")

            self["actions"] = ActionMap(["OkCancelActions", "MenuActions", "ColorActions", "DirectionActions", "NavigationActions"], {
                "ok": self.keySelect,
                "cancel": self.keyCancel,
                "menu": self.keySetup,
                "red": self.changeReorderingMode,
                "green": self.keyGreen,
                "yellow": self.keyYellow,
                "blue": self.keyMenu,
                "up": self.listKeyUp,
                "down": self.listKeyDown,
            }, -1)

            self.onLayoutFinish.append(self.layoutFinished)

        def layoutFinished(self):
            # list mode's current position is tracked entirely in Python
            # (self.lastSelection) rather than via the eListbox's own
            # selection cursor - confirmed on at least one Enigma2 fork
            # (OpenViX) that moveSelectionTo()/getCurrentIndex() don't
            # actually move/track the real selection at all (same
            # portability gap as setSelectionPixmap being missing there,
            # just deeper: the index silently never changes, with no
            # error). self["grid"].selectedIdx (see PlayerSelectorHostList/
            # PlayerSelectorSimpleList.buildEntry()) draws the blue
            # highlight bar for the tracked row instead.
            if not (self.currList and self.lastSelection and self.lastSelection < self.numOfItems):
                self.lastSelection = 0
            self["grid"].selectedIdx = self.lastSelection
            # cancel the skin's own static backgroundColorSelected="#1b5a91"
            # (it would otherwise always highlight whichever row sits at
            # eListbox's stuck internal position 0 - see setReorderingHighlight()
            # above). Simple list never calls setSelectionImage()/
            # setReorderingHighlight() at all, so this has to happen here
            # to cover it too, not just the non-simple list path below.
            self["grid"].instance.setBackgroundColorSelected(parseColor("black"))
            self._updateScrollWindow()
            self.updateIcons()
            self.setSelectionImage("")
            self.selectionChanged()

        def _updateScrollWindow(self):
            # keeps self.lastSelection inside the range of rows updateIcons()
            # actually passes to the widget (self.windowStart .. +visibleRows)
            # - a manual stand-in for the auto-scroll-into-view behavior
            # eListbox would normally provide via a working moveSelectionTo()
            if self.lastSelection < self.windowStart:
                self.windowStart = self.lastSelection
            elif self.lastSelection >= self.windowStart + self.visibleRows:
                self.windowStart = self.lastSelection - self.visibleRows + 1
            maxStart = max(0, self.numOfItems - self.visibleRows)
            self.windowStart = max(0, min(self.windowStart, maxStart))

        def keySelect(self):
            if self.reorderingMode:
                if self.moveIndex == -1:
                    self.setSelectionImage("Sel")
                    self.moveIndex = self.lastSelection
                else:
                    self.moveIndex = -1
                    self.setSelectionImage("")
                    self.reInitDisplayList()
                self.selectionChanged()
                return

            idx = self.lastSelection
            PlayerSelectorWidget.LAST_SELECTION[self.groupName] = idx
            if idx < self.numOfItems:
                self.close(self.currList[idx])
            else:
                self.close(None)

        def keyCancel(self):
            self.close(None)

        def listKeyUp(self):
            # named listKeyUp/listKeyDown (not keyUp/keyDown) to avoid
            # colliding with the Cover3 grid mode's own keyUp/keyDown
            # further below in this same class
            if self.lastSelection > 0:
                self.lastSelection -= 1
                self["grid"].selectedIdx = self.lastSelection
                self._updateScrollWindow()
                self.updateIcons()
                self.selectionChanged()

        def listKeyDown(self):
            if self.lastSelection < self.numOfItems - 1:
                self.lastSelection += 1
                self["grid"].selectedIdx = self.lastSelection
                self._updateScrollWindow()
                self.updateIcons()
                self.selectionChanged()

        def keySetup(self):
            self.close((_("Configuration"), "config"))

        def keyGreen(self):
            if self.simpleListMode:
                return
            self.close((_("Disable/Enable groups"), "config_groups"))

        def keyYellow(self):
            self.close((_("Download manager"), "IPTVDM"))

        def setSelectionImage(self, move):
            if self.simpleListMode:
                return
            self["grid"].setReorderingHighlight(self.reorderingMode, move == "Sel")
            # setReorderingHighlight() only updates self["grid"].highlightColor
            # on this platform (see its useNativeHighlight branch) - needs an
            # actual rebuild to show the new color right away, not just on
            # the next up/down press
            self.updateIcons()

        def selectionChanged(self):
            if self.currList:
                idx = self.lastSelection
                if self.reorderingMode:
                    if self.moveIndex != -1:
                        self["statustext"].setText(_("MOVE: %s") % self.currList[self.moveIndex][0])
                        if self.moveIndex != idx:
                            def move_element(lst, from_index, to_index):
                                element = lst.pop(from_index)
                                lst.insert(to_index, element)
                                return lst
                            move_element(self.currList, self.moveIndex, idx)
                            self.moveIndex = idx
                            self.reInitDisplayList()
                        return
                self["statustext"].setText(self.currList[idx][0])

        def __del__(self):
            printDBG("PlayerSelectorWidget.__del__ --------------------------")

        def __onClose(self):
            self.session.nav.event.remove(self.__event)
            self.onClose.remove(self.__onClose)
            try:
                if self.reorderingMode and self.numOfLockedItems > 0:
                    self.currList.extend(self.inList[len(self.inList) - self.numOfLockedItems:])

                if self.outList != self.currList:
                    for item in self.currList:
                        self.outList.append(item)
            except Exception:
                printExc()
            idx = self.lastSelection if self.listMode else (self.currLine * self.numOfCol + self.dispX)
            printDBG(">>>>>>>>>>>>>>>>>>>>>>>>>>> __onClose idx[%s]" % idx)
            PlayerSelectorWidget.LAST_SELECTION[self.groupName] = idx

        # Calculate marker position Y
        def calcMarkerPosY(self):

            if self.currLine > (self.numOfLines - 1):
                self.currLine = 0
            elif self.currLine < 0:
                self.currLine = (self.numOfLines - 1)

            # calculate new page number
            newPage = int(self.currLine / self.numOfRow)
            if newPage != self.currPage:
                self.currPage = newPage
                self.updateIcons()

            # calculate dispY pos
            self.dispY = self.currLine - self.currPage * self.numOfRow

            # if we are in last line dispX pos
            # must be also corrected
            if self.currLine == (self.numOfLines - 1):
                self.numItemsInLine = self.numOfItems - ((self.numOfLines - 1) * self.numOfCol)
                if self.dispX > (self.numItemsInLine - 1):
                    self.dispX = self.numItemsInLine - 1

            return

        # Calculate marker position X
        def calcMarkerPosX(self):
            if self.currLine == self.numOfLines - 1:
                # calculate num of item in last line
                self.numItemsInLine = self.numOfItems - ((self.numOfLines - 1) * self.numOfCol)
            else:
                self.numItemsInLine = self.numOfCol

            if self.dispX > (self.numItemsInLine - 1):
                self.dispX = 0
            elif self.dispX < 0:
                self.dispX = self.numItemsInLine - 1

            return

        def onStart(self):
            self.onLayoutFinish.remove(self.onStart)
            self["marker"].setPixmap(self.markerPixmap)
            self["page_marker"].setPixmap(self.pageMarkerPixmap)
            self["menu"].setPixmap(self.menuPixmap)
            self.offsetCoverX = self['marker'].position[0] + (self.markerWidth - self.coverWidth) / 2
            self.offsetCoverY = self['marker'].position[1] + (self.markerHeight - self.coverHeight) / 2
            self.pageItemStartX = self['page_marker'].position[0]
            self.pageItemStartY = self['page_marker'].position[1]
            self.initDisplayList()
            return

        def reInitDisplayList(self):
            if self.listMode:
                self.numOfItems = len(self.currList)
                self._updateScrollWindow()
                self.updateIcons()
                return
            self.lastSelection = self.currLine * self.numOfCol + self.dispX
            self.calcDisplayVariables()
            self.initDisplayList()

        def initDisplayList(self):
            self.updateIcons()
            self.setIdx(self.lastSelection)

        def calcDisplayVariables(self):
            # numbers of items in self.currList
            self.numOfItems = len(self.currList)

            if self.lastSelection >= self.numOfItems:
                self.lastSelection = self.numOfItems - 1

            # numbers of lines
            self.numOfLines = int(self.numOfItems / self.numOfCol)
            if self.numOfItems % self.numOfCol > 0:
                self.numOfLines += 1

            # numbers of pages
            self.numOfPages = int(self.numOfLines / self.numOfRow)
            if self.numOfLines % self.numOfRow > 0:
                self.numOfPages += 1

            self.currPage = 0
            self.currLine = 0

            self.dispX = 0
            self.dispY = 0

        def updateIconsList(self, rangeList):
            idx = int(self.currPage * (self.numOfCol * self.numOfRow))
            for y in range(1, self.numOfRow + 1):
                for x in range(1, self.numOfCol + 1):
                    if idx >= rangeList[0] and idx <= rangeList[1]:
                        strIndex = "cover_%s%s" % (x, y)
                        printDBG("updateIconsList [%s]" % strIndex)
                        self[strIndex].setPixmap(self.pixmapList[idx])
                    idx += 1

        def updateIcons(self):
            if self.listMode:
                # only the current scroll window (self.windowStart ..
                # +visibleRows) is actually handed to the widget - see
                # _updateScrollWindow(). idx stays the real index into
                # self.currList (needed so buildEntry()'s idx == selectedIdx
                # check still lines up), only which rows get shown at all
                # is windowed
                end = min(self.numOfItems, self.windowStart + self.visibleRows)
                items = [(None, self.currList[idx][0], idx, self.currList[idx][1]) for idx in range(self.windowStart, end)]
                self["grid"].updateList(items)
                return
            idx = int(self.currPage * (self.numOfCol * self.numOfRow))
            for y in range(1, self.numOfRow + 1):
                for x in range(1, self.numOfCol + 1):
                    strIndex = "cover_%s%s" % (x, y)
                    printDBG("updateIcon for self[%s]" % strIndex)
                    if idx < self.numOfItems:
                        # self[strIndex].updateIcon( resolveFilename(SCOPE_PLUGINS, 'Extensions/IPTVPlayer/icons/PlayerSelector/' + self.currList[idx][1] + '.png'))
                        self[strIndex].setPixmap(self.pixmapList[idx])
                        self[strIndex].show()
                        idx += 1
                    else:
                        self[strIndex].hide()
            x = self.pageItemStartX + self.currPage * self.pageItemSize
            y = self.pageItemStartY
            self["page_marker"].instance.move(ePoint(int(x), y))

        def setIdx(self, selIdx):
            if selIdx > self.numOfItems:
                selIdx = self.numOfItems

            self.dispX = selIdx % self.numOfCol
            self.currLine = int(selIdx / self.numOfCol)

            self.calcMarkerPosX()
            self.calcMarkerPosY()
            self.moveMarker()
            return

        def keyRight(self):
            prev_idx = self.currLine * self.numOfCol + self.dispX
            self.dispX += 1
            self.calcMarkerPosX()
            self.moveMarker(prev_idx)
            return

        def keyLeft(self):
            prev_idx = self.currLine * self.numOfCol + self.dispX
            self.dispX -= 1
            self.calcMarkerPosX()
            self.moveMarker(prev_idx)
            return

        def keyDown(self):
            prev_idx = self.currLine * self.numOfCol + self.dispX
            self.currLine += 1
            self.calcMarkerPosY()
            self.moveMarker(prev_idx)
            return

        def keyUp(self):
            prev_idx = self.currLine * self.numOfCol + self.dispX
            self.currLine -= 1
            self.calcMarkerPosY()
            self.moveMarker(prev_idx)
            return

        def moveMarker(self, prev_idx=0):
            new_idx = int(self.currLine * self.numOfCol + self.dispX)

            if self.reorderingItemSelected:
                if prev_idx != new_idx:
                    prevHost = self.currList[prev_idx]
                    prevPixmap = self.pixmapList[prev_idx]
                    del self.currList[prev_idx]
                    del self.pixmapList[prev_idx]

                    self.currList.insert(new_idx, prevHost)
                    self.pixmapList.insert(new_idx, prevPixmap)
                    self.updateIconsList(sorted([prev_idx, new_idx]))

            # calculate position of image
            imgPosX = self.offsetCoverX + (self.coverWidth + self.disWidth) * self.dispX
            imgPosY = self.offsetCoverY + (self.coverHeight + self.disHeight) * self.dispY

            # calculate postion of marker for current image
            x = int(imgPosX - (self.markerWidth - self.coverWidth) / 2)
            y = int(imgPosY - (self.markerHeight - self.coverHeight) / 2)

            # x =  30 + self.dispX * 180
            # y = 130 + self.dispY * 125
            self["marker"].instance.move(ePoint(x, y))
            self["statustext"].setText(self.currList[new_idx][0])
            return

        def getSelectedItem(self):
            printDBG(">> PlayerSelectorWidget.getSelectedItem")
            idx = self.lastSelection if self.listMode else (self.currLine * self.numOfCol + self.dispX)
            if idx < self.numOfItems:
                return self.currList[idx]
            return None

        def back_pressed(self):
            self.close(None)
            return

        def ok_pressed(self):
            if self.reorderingMode:
                if self.reorderingItemSelected:
                    self["marker"].setPixmap(self.markerPixmap)
                    self.reorderingItemSelected = False
                else:
                    self["marker"].setPixmap(self.markerPixmapSel)
                    self.reorderingItemSelected = True
                return

            idx = int(self.currLine * self.numOfCol + self.dispX)
            PlayerSelectorWidget.LAST_SELECTION[self.groupName] = idx

            if idx < self.numOfItems:
                self.close(self.currList[idx])
            else:
                self.close(None)
            return

        def keyBlue(self):
            self.close((_("Download manager"), "IPTVDM"))

        def keyMenu(self):
            printDBG(">> PlayerSelectorWidget.keyMenu")
            options = []
            selItem = self.getSelectedItem()
            if not self.simpleListMode and self.groupObj is not None and selItem is not None and len(self.groupObj.getGroupsWithoutHost(selItem[1])):
                options.append((_("Add host %s to group") % selItem[0], "ADD_HOST_TO_GROUP"))

            if not self.simpleListMode:
                if not self.reorderingMode and self.numOfItems - self.numOfLockedItems > 0:
                    options.append((_("Enable reordering mode"), "CHANGE_REORDERING_MODE"))
                elif self.reorderingMode:
                    options.append((_("Disable reordering mode"), "CHANGE_REORDERING_MODE"))
                options.append((_("Search"), "SEARCH"))
            options.append((_("Download manager"), "IPTVDM"))
            if not self.simpleListMode:
                if self.groupName in ['selecthost', 'all']:
                    options.append((_("Disable/Enable services"), "config_hosts"))
                elif self.groupName in ['selectgroup']:
                    options.append((_("Disable/Enable groups"), "config_groups"))

            if not self.simpleListMode:
                if self.groupName == 'selecthost':
                    pass
                elif self.groupName == 'selectgroup':
                    if selItem[1] not in ['update', 'config', 'all']:
                        options.append((_('Hide "%s" group') % selItem[0], "DEL_ITEM"))
                elif self.groupName not in ['all']:
                    options.append((_('Remove "%s" item') % selItem[0], "DEL_ITEM"))

            if len(options):
                self.session.openWithCallback(self.selectMenuCallback, ChoiceBox, title=_("Select option"), list=options)

        def selectMenuCallback(self, ret):
            printDBG(">> PlayerSelectorWidget.selectMenuCallback")
            if ret:
                ret = ret[1]
                if ret == "CHANGE_REORDERING_MODE":
                    self.changeReorderingMode()
                elif ret == "IPTVDM":
                    self.keyBlue()
                elif ret in ["config_hosts", "config_groups"]:
                    self.close((_("Disable not used services"), ret))
                elif ret == "ADD_HOST_TO_GROUP":
                    self.addHostToGroup()
                elif ret == 'DEL_ITEM':
                    idx = self.lastSelection if self.listMode else (self.currLine * self.numOfCol + self.dispX)
                    if idx < self.numOfItems:
                        del self.currList[idx]
                        if not self.listMode:
                            del self.pixmapList[idx]
                        elif self.lastSelection >= len(self.currList) and self.lastSelection > 0:
                            self.lastSelection -= 1
                        if self.listMode:
                            self["grid"].selectedIdx = self.lastSelection
                        self.reInitDisplayList()
                elif ret == 'SEARCH':
                    self.openSearch()

        def openSearch(self):
            from Plugins.Extensions.IPTVPlayer.components.e2ivkselector import GetVirtualKeyboard
            caps = {}
            virtualKeyboard = GetVirtualKeyboard(caps)
            if caps.get('has_additional_params'):
                self.session.openWithCallback(self.searchCallback, virtualKeyboard, title=_("Search"), text='', additionalParams={})
            else:
                self.session.openWithCallback(self.searchCallback, virtualKeyboard, title=_("Search"), text='')

        def searchCallback(self, searchText=None):
            if not searchText:
                return
            query = searchText.strip().lower()
            if not query:
                return
            matches = [(item[0], item[1], idx) for idx, item in enumerate(self.currList) if query in item[0].lower() or query in item[1].lower()]
            if not matches:
                self.session.open(MessageBox, _("No matching entries found."), type=MessageBox.TYPE_INFO, timeout=5)
                return
            # picks straight from self.currList by index, so this only ever
            # shows/hides matches for this one search - it never touches
            # currList/pixmapList/outList itself, so reordering and the
            # group's persisted host list are completely unaffected
            options = [IPTVChoiceBoxItem("%s (%s)" % (name, hostKey), hostKey, idx) for name, hostKey, idx in matches]
            height = self._getSearchResultsHeight(len(options))
            self.session.openWithCallback(self.searchResultCallback, IPTVChoiceBoxWidget, {'width': 550, 'height': height, 'current_idx': 0, 'title': _("Search results"), 'options': options, 'list_class': IPTVHostSearchResultList, 'chrome': True, 'footerMargin': 120})

        def searchResultCallback(self, ret=None):
            if not isinstance(ret, IPTVChoiceBoxItem):
                return
            idx = ret.privateData
            PlayerSelectorWidget.LAST_SELECTION[self.groupName] = idx
            self.close(self.currList[idx])

        def _getSearchResultsHeight(self, numItems):
            # itemH comes from _getSearchResultItemHeight() so this stays in
            # sync with IPTVHostSearchResultList's actual (enlarged) row height
            screenwidth = getDesktop(0).size().width()
            itemH = _getSearchResultItemHeight(screenwidth)
            scale = 2.0 if screenwidth >= 2560 else (1.5 if screenwidth >= 1920 else 1.0)
            height = int(numItems * itemH / scale) + 130
            # capped at 660 (out of IPTVChoiceBoxWidget's chrome skin's
            # 720-tall reference canvas) so a large result set scrolls
            # (scrollbarMode="showOnDemand" is already declared on the list
            # widget) instead of growing the popup past the screen edge
            return min(height, 660)

        def addHostToGroup(self):
            printDBG(">> PlayerSelectorWidget.addHostToGroup")
            selItem = self.getSelectedItem()
            groupsList = self.groupObj.getGroupsWithoutHost(selItem[1])
            options = []
            for item in groupsList:
                options.append((item.title, item.name))

            if len(options):
                self.session.openWithCallback(self.addHostToGroupCallback, ChoiceBox, title=_("Select group"), list=options)

        def addHostToGroupCallback(self, ret):
            if ret:
                ret = ret[1]
                selItem = self.getSelectedItem()
                self.groupObj.addHostToGroup(ret, selItem[1])

        def changeReorderingMode(self):
            printDBG(">> PlayerSelectorWidget.changeReorderingMode")
            if self.simpleListMode:
                return
            if self.listMode:
                if not self.currList:
                    return
                if not self.reorderingMode and (self.numOfItems - self.numOfLockedItems) > 0:
                    self.reorderingMode = True
                    self.setSelectionImage("Sel")
                    self.moveIndex = self.lastSelection
                else:
                    self.moveIndex = -1
                    self.reorderingMode = False
                    self.setSelectionImage("")
                self.selectionChanged()
                return
            if not self.reorderingMode and (self.numOfItems - self.numOfLockedItems) > 0:
                self.reorderingMode = True
                if self.numOfLockedItems > 0:
                    self.currList = self.currList[:self.numOfLockedItems * -1]
                    self.reInitDisplayList()
            else:
                if self.reorderingItemSelected:
                    self["marker"].setPixmap(self.markerPixmap)
                self.reorderingMode = False
                if self.numOfLockedItems > 0:
                    self.currList.extend(self.inList[len(self.inList) - self.numOfLockedItems:])
                    self.reInitDisplayList()

            self.reorderingItemSelected = False

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
