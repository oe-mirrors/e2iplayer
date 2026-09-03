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
from Components.MultiContent import MultiContentEntryPixmapAlphaBlend
from Screens.MessageBox import MessageBox
from Components.Sources.List import List
from Components.Sources.StaticText import StaticText
from Tools.Directories import resolveFilename, SCOPE_PLUGINS
from Tools.BoundFunction import boundFunction

from Plugins.Extensions.IPTVPlayer.components.cover import Cover3
from Plugins.Extensions.IPTVPlayer.components.iptvchoicebox import IPTVChoiceBoxWidget, IPTVChoiceBoxItem, openChoiceBox
from Plugins.Extensions.IPTVPlayer.components.iptvlist import IPTVRadioButtonList, fitPixmapInBox, IPTVPlayerSelectorContextMenuChoiceBoxList
from Plugins.Extensions.IPTVPlayer.components import skinchrome
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


def _getContextMenuHeight(numItems):
    # same tier-aware height+cap formula as e.g. iptvplayerwidget.py's
    # own _getMoviePlayerPickerHeight()/iptvdmui.py's
    # _getActionListHeight() - a plain, un-iconed options list, so the
    # standard 35/40/55 item height (not _getSearchResultsHeight()'s
    # taller logo-row height right below, which would oversize this
    # popup). Shared by both PlayerSelectorWidget variants' own
    # openContextMenu().
    itemH, scale = skinchrome.tierRowHeight(35, 40, 55)
    height = int(numItems * itemH / scale) + 146
    return min(height, 660)


def _getSearchResultsHeight(numItems):
    # same reference-space-vs-real-pixels reasoning, and the same
    # footerMargin derivation, as E2iPlayerWidget's own
    # _getMoviePlayerPickerHeight (iptvplayerwidget.py) - can't reuse
    # that method directly since it's a different class, but this one
    # module-level function is shared by both PlayerSelectorWidget
    # variants below (GRIDSUPPORT and Legacy). itemH comes from
    # _getSearchResultItemHeight() so this stays in sync with
    # IPTVHostSearchResultList's actual (enlarged) row height. Capped at
    # 660 (out of the chrome skin's 720-tall reference canvas, the same
    # reference height every tier's own PlayerSelectorWidget popup is
    # scaled up from) so a large result set scrolls
    # (scrollbarMode="showAlways" is already declared on the list widget)
    # instead of growing the popup past the screen edge.
    screenwidth = getDesktop(0).size().width()
    itemH = _getSearchResultItemHeight(screenwidth)
    scale = 2.0 if screenwidth >= 2560 else (1.5 if screenwidth >= 1920 else 1.0)
    height = int(numItems * itemH / scale) + 146
    return min(height, 660)


# icon-grid cell templates (100/120/135 marker sizes for the 3 IconsSize
# settings) - identical at every resolution tier since the marker-frame
# PNG (marker/marker145/165/180.png, loaded via setSelectionPixmap())
# isn't auto-scaled by resolution=, so the cell size has to stay a true
# fixed pixel size regardless of tier (see the HD/FHD/WQHD skin strings
# below). Shared by both grid screens that use this exact cell shape
# (PlayerSelectorWidget's own grid mode and SearchResultGridWidget).
_GRID_TEMPLATES = """<templates>
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
                    </templates>"""


# (position, size) of the central "grid" widget, per tier - identical
# between PlayerSelectorWidget's icon-grid and "List view" modes; only
# the widget declared there differs (_gridModeWidget()/_listModeWidget()
# below), everything else about the screen is shared too (see
# _buildPlayerSelectorSkin() below). List mode never needs GRIDSUPPORT's
# newer skin engine at all - only the icon-grid mode does.
_PLAYER_SELECTOR_GRID_GEOM = {
    'HD': ("20,104", "980,460"),
    'FHD': ("30,150", "1470,705"),
    'WQHD': ("40,200", "1960,940"),
}


def _gridModeWidget(tier):
    # native grid-capable Listbox (listOrientation="grid") + the shared
    # per-cell <templates> - needs GRIDSUPPORT's newer skin engine
    # support, which is exactly why the Legacy (non-GRIDSUPPORT) class
    # falls back to a hand-rolled per-cell Cover3 grid instead of this
    position, size = _PLAYER_SELECTOR_GRID_GEOM[tier]
    return """<widget source="grid" render="Listbox" position="%s" size="%s" conditional="grid" listOrientation="grid" scrollbarMode="showOnDemand" scrollbarSliderBorderWidth="1" scrollbarForegroundColor="#1b5a91" scrollbarBorderColor="#00b6b6b6" itemSpacing="20,20" itemAlignment="center" backgroundColorSelected="#24111112" transparent="1">
                    %s
                </widget>""" % (position, size, _GRID_TEMPLATES)


def _listModeWidget(tier):
    # plain single-column scrollable list - no GRIDSUPPORT/Listbox-grid
    # dependency at all, which is why "List view" mode looks identical
    # whether GRIDSUPPORT is true or false (see _buildListModeSkin()
    # below, shared by both classes for exactly that reason). Row
    # height/selection marker are set entirely in Python
    # (PlayerSelectorHostList's self.l.setItemHeight(), from
    # _getSearchResultItemHeight(screenwidth); setReorderingHighlight()'s
    # markerList56/64/90.png), so neither depends on this skin's own
    # declared numbers.
    position, size = _PLAYER_SELECTOR_GRID_GEOM[tier]
    return """<widget name="grid" position="%s" size="%s" conditional="grid" scrollbarMode="showAlways" scrollbarSliderBorderWidth="1" scrollbarForegroundColor="#1b5a91" scrollbarBorderColor="#00b6b6b6" enableWrapAround="1" transparent="1" foregroundColor="white" backgroundColor="black" backgroundColorSelected="#1b5a91" foregroundColorSelected="white" />""" % (position, size)


def _buildPlayerSelectorSkin(gridWidgetXML):
    # shared screen skeleton for PlayerSelectorWidget's two modes (icon
    # grid and "List view") - chrome (header/footer), screen size, and
    # statustext/categorytext position+size are identical between them
    # at every tier. `gridWidgetXML`: dict {'HD': ..., 'FHD': ...,
    # 'WQHD': ...}, the one part that actually differs - from
    # _gridModeWidget()/_listModeWidget() above. Returns (skinHD,
    # skinFHD, skinWQHD). Kept as explicit per-tier values rather than
    # "e"-relative auto-scale, same reason as _GRID_TEMPLATES above: the
    # original FHD/WQHD heights (705/940) are NOT exactly 1.5x/2x of
    # HD's 460 (690/920) - a small deliberate hand-tune this reproduces
    # exactly instead of approximating.
    #
    # optional header clock/date
    # (config.plugins.iptvplayer.show_header_clock) - HD-reference
    # numbers below, hand-scaled x1.5/x2.0 per tier same as every other
    # number in this function (this screen uses build_header()'s
    # explicit `scale=` variant, not resolution=-based auto-scale, so
    # nothing here scales on its own). zPosition="2" (above the
    # header's own Title label, zPosition="1") since Title's declared
    # box is much wider than its actual rendered "E2iPlayer <version>"
    # text and would otherwise paint over the clock.
    if config.plugins.iptvplayer.show_header_clock.value:
        clockHD = """<widget source="global.CurrentTime" render="Label" position="860,10" size="150,40" foregroundColor="white" backgroundColor="black" borderWidth="1" borderColor="black" transparent="1" zPosition="2" font="Regular;24" valign="center" halign="right">
                    <convert type="ClockToText">Format:%H:%M</convert>
                </widget>
                <widget source="global.CurrentTime" render="Label" position="620,20" size="300,24" foregroundColor="white" backgroundColor="black" borderWidth="1" borderColor="black" transparent="1" zPosition="2" font="Regular;16" valign="center" halign="right">
                    <convert type="ClockToText">Date</convert>
                </widget>"""
        clockFHD = """<widget source="global.CurrentTime" render="Label" position="1290,15" size="225,60" foregroundColor="white" backgroundColor="black" borderWidth="1" borderColor="black" transparent="1" zPosition="2" font="Regular;36" valign="center" halign="right">
                    <convert type="ClockToText">Format:%H:%M</convert>
                </widget>
                <widget source="global.CurrentTime" render="Label" position="930,30" size="450,36" foregroundColor="white" backgroundColor="black" borderWidth="1" borderColor="black" transparent="1" zPosition="2" font="Regular;24" valign="center" halign="right">
                    <convert type="ClockToText">Date</convert>
                </widget>"""
        clockWQHD = """<widget source="global.CurrentTime" render="Label" position="1720,20" size="300,80" foregroundColor="white" backgroundColor="black" borderWidth="1" borderColor="black" transparent="1" zPosition="2" font="Regular;48" valign="center" halign="right">
                    <convert type="ClockToText">Format:%H:%M</convert>
                </widget>
                <widget source="global.CurrentTime" render="Label" position="1240,40" size="600,48" foregroundColor="white" backgroundColor="black" borderWidth="1" borderColor="black" transparent="1" zPosition="2" font="Regular;32" valign="center" halign="right">
                    <convert type="ClockToText">Date</convert>
                </widget>"""
    else:
        clockHD = clockFHD = clockWQHD = ""

    skinHD = """
            <screen name="PlayerSelectorWidget" position="center,center" size="1020,676" title="E2iPlayer" backgroundColor="#34111112" flags="wfNoBorder">
                %s
                %s
                <widget name="statustext" position="20,570" size="980,30" font="Regular;20" valign="center" halign="center" backgroundColor="black" foregroundColor="white" transparent="1" />
                <widget name="categorytext" position="20,70" size="980,30" font="Regular;20" valign="center" halign="center" backgroundColor="black" foregroundColor="white" transparent="1" />
                %s
                %s
            </screen>
            """ % (skinchrome.build_header(scale=1.0, iconBase=skinchrome.ICON_ROOT + "/HD"), clockHD, gridWidgetXML['HD'], skinchrome.build_footer(676, scale=1.0, iconBase=skinchrome.ICON_ROOT + "/HD"))

    skinFHD = """
            <screen name="PlayerSelectorWidget" position="center,center" size="1530,1014" title="E2iPlayer" backgroundColor="#34111112" flags="wfNoBorder">
                %s
                %s
                <widget name="statustext" position="30,860" size="1470,45" font="Regular;30" valign="center" halign="center" backgroundColor="black" foregroundColor="white" transparent="1" />
                <widget name="categorytext" position="30,100" size="1470,45" font="Regular;30" valign="center" halign="center" backgroundColor="black" foregroundColor="white" transparent="1" />
                %s
                %s
            </screen>
            """ % (skinchrome.build_header(scale=1.5, iconBase=skinchrome.ICON_ROOT + "/FHD"), clockFHD, gridWidgetXML['FHD'], skinchrome.build_footer(1014, scale=1.5, iconBase=skinchrome.ICON_ROOT + "/FHD"))

    skinWQHD = """
            <screen name="PlayerSelectorWidget" position="center,center" size="2040,1352" title="E2iPlayer" backgroundColor="#34111112" flags="wfNoBorder">
                %s
                %s
                <widget name="statustext" position="40,1147" size="1960,60" font="Regular;40" valign="center" halign="center" backgroundColor="black" foregroundColor="white" transparent="1" />
                <widget name="categorytext" position="40,133" size="1960,60" font="Regular;40" valign="center" halign="center" backgroundColor="black" foregroundColor="white" transparent="1" />
                %s
                %s
            </screen>
            """ % (skinchrome.build_header(scale=2.0, iconBase=skinchrome.ICON_ROOT + "/WQHD"), clockWQHD, gridWidgetXML['WQHD'], skinchrome.build_footer(1352, scale=2.0, iconBase=skinchrome.ICON_ROOT + "/WQHD"))

    return skinHD, skinFHD, skinWQHD


def _buildGridModeSkin():
    return _buildPlayerSelectorSkin({tier: _gridModeWidget(tier) for tier in _PLAYER_SELECTOR_GRID_GEOM})


def _buildListModeSkin():
    # "List view" mode (hostsListType == "S") - shared by the GRIDSUPPORT
    # and Legacy variants of PlayerSelectorWidget below. Returns
    # (skinListHD, skinListFHD, skinListWQHD).
    return _buildPlayerSelectorSkin({tier: _listModeWidget(tier) for tier in _PLAYER_SELECTOR_GRID_GEOM})


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


def _moveListElement(lst, from_index, to_index):
    # pure list.pop()/list.insert() pair, extracted so it isn't
    # redefined as a fresh closure on every selectionChanged() call
    # (i.e. every up/down keypress while an item is picked up for
    # reordering). Used for both self.currList and self.pixmapList.
    element = lst.pop(from_index)
    lst.insert(to_index, element)
    return lst


def _setSelectionPixmap(instance, path):
    # eListbox.setSelectionPixmap() isn't available on every Enigma2 fork -
    # confirmed missing on OpenViX (AttributeError: 'eListbox' object has no
    # attribute 'setSelectionPixmap'), which only exposes the older/different
    # setSelectionPicture() there. The custom marker frame this sets is a
    # visual enhancement (plain backgroundColorSelected is barely visible on
    # its own), not required functionality, so just keep the plain default
    # highlight instead of crashing when the method is absent.
    #
    # Also guards against a missing/unreadable marker PNG on disk (e.g. an
    # incomplete install where GetAvailableIconSize() finds none of
    # marker145/165/180.png and falls back to iconSize=0, so this gets
    # asked for the nonexistent "marker45.png") - LoadPixmap() returning
    # None would otherwise crash straight through
    # eListbox_setSelectionPixmap() with a TypeError.
    if hasattr(instance, 'setSelectionPixmap'):
        pixmap = LoadPixmap(path)
        if pixmap is not None:
            instance.setSelectionPixmap(pixmap)


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
        textX = logoX + self.logoW + 10
        try:
            pix = None
            if item.description:
                logoPath = _getPlayerSelectorLogoPath(item.description)
                if not os.path.isfile(logoPath):
                    # fall back to a generic "coming soon" placeholder when
                    # there's no real logo file yet for this host/group -
                    # shared by every screen that shows a host or group
                    # name with a logo (PlayerSelectorWidget's own list
                    # view, search results, add-to-group)
                    logoPath = GetLogoDir('groups/comming-soonlogo.png')
                if os.path.isfile(logoPath):
                    pix = LoadPixmap(cached=True, path=logoPath)
            if pix is not None:
                # fitPixmapInBox() (iptvlist.py): logoW/logoH above
                # already match the real 120x40 (3:1) source logos, so
                # this is normally a no-op (scale factor 1.0, same pixels
                # a plain BT_SCALE stretch would produce) - real
                # protection only kicks in for a host logo file that
                # doesn't actually match that 3:1 ratio, instead of
                # silently squishing it
                x, y, w, h = fitPixmapInBox(pix, logoX, 0, self.logoW, height)
                res.append(MultiContentEntryPixmapAlphaBlend(pos=(x, y), size=(w, h), png=pix, flags=BT_SCALE))
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
        file = resolveFilename(SCOPE_PLUGINS, 'Extensions/IPTVPlayer/icons/PlayerSelector/marker/markerSearchList%s.png' % suffix)
        _setSelectionPixmap(self.instance, file)


class PlayerSelectorHostList(IPTVHostSearchResultList):
    # PlayerSelectorWidget's "List view" mode - reuses
    # IPTVHostSearchResultList's sizing and icons/logos/<key>logo.png
    # lookup as-is (same visual language as the search results list),
    # rather than the PlayerSelector/<key><iconSize>.png grid icons
    # PlayerSelectorWidget's grid mode uses. buildEntry()/onCreate() are
    # deliberately NOT overridden here - inheriting them unchanged from
    # IPTVHostSearchResultList (the exact class the search results/select
    # group ChoiceBox popups use) is what makes native eListbox scrolling
    # work correctly in this widget. Also exposes a couple of method
    # aliases so PlayerSelectorWidget's existing selection/update code
    # (written against Components.Sources.List's API) works unmodified
    # regardless of which list widget is actually in use. showHostKey is
    # set to False by PlayerSelectorWidget right after construction when
    # this is a group list (groupName == 'selectgroup') - group keys
    # ("german", "userdefined", ...) aren't meaningful to show, unlike
    # host keys. One cosmetic side effect of inheriting onCreate()
    # unchanged: the row highlight while just browsing (not reordering)
    # uses the search-results marker frame (markerSearchList*.png)
    # instead of this list's own (markerList*.png) -
    # setReorderingHighlight() below still overrides that highlight
    # correctly once reordering actually starts.
    showHostKey = True

    def getSelectedIndex(self):
        return self.getCurrentIndex()

    def setCurrentIndex(self, index):
        self.moveToIndex(index)

    def updateList(self, items):
        self.setList(items)

    def setReorderingHighlight(self, reorderingActive, pickedUp):
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
        file = resolveFilename(SCOPE_PLUGINS, 'Extensions/IPTVPlayer/icons/PlayerSelector/marker/' + name)
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
    # buildEntry() takes the same single-item form
    # IPTVHostSearchResultList.buildEntry() uses (rather than an older
    # 4-param shape) but still renders plain text only, no logo - "name
    # (key)" formatting happens in updateIcons() instead. Unlike
    # PlayerSelectorHostList, this class keeps its own onCreate() override
    # (no marker overlay, by design).
    def buildEntry(self, item):
        width = self.l.getItemSize().width()
        height = self.l.getItemSize().height()
        res = [None]
        # same 5px margin IPTVRadioButtonList's own icon-less rows use
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 5, 0, width - 5, height, 1, RT_HALIGN_LEFT | RT_VALIGN_CENTER, item.name))
        return res

    def onCreate(self):
        # skip both IPTVHostSearchResultList.onCreate() (search marker) and
        # PlayerSelectorHostList.onCreate()'s own setReorderingHighlight()
        # call - no marker overlay at all in this mode, just the skin's
        # own default backgroundColorSelected
        IPTVRadioButtonList.onCreate(self)


class _PlayerSelectorListMode:
    # Shared by both PlayerSelectorWidget variants below (GRIDSUPPORT and
    # Legacy) for their "List view"/"Simple list" mode. PlayerSelectorHostList/
    # -SimpleList above are defined once, module-level, with zero
    # GRIDSUPPORT dependency, and expose the same getSelectedIndex()/
    # setCurrentIndex()/updateList() names Components.Sources.List has
    # (see PlayerSelectorHostList's own class comment) specifically so
    # code written against that API - i.e. every method below - works
    # unmodified regardless of which widget self["grid"] actually is.
    #
    # Written using GRIDSUPPORT's own versions, which already handled
    # both of ITS modes via that same polymorphism - a `self.listMode`/
    # `not self.listMode` branch inside some of these is GRIDSUPPORT's
    # own icon-grid-only code, which never runs for the Legacy class (it
    # has its own, differently-named ok_pressed()/keyUp()/keyDown()/
    # keyLeft()/keyRight(), and its own separate
    # changeReorderingMode()/getSelectedItem() bodies that branch
    # internally instead - those two, plus __onClose(),
    # selectMenuCallback(), deleteItemAt() and reInitDisplayList(), stay
    # separate: they have real behavioral differences between the two
    # classes beyond the expected grid-vs-list split, e.g. pixmapList's
    # lifecycle in list mode).
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

    def selectionChanged(self):
        if not self.currList:
            return
        idx = self["grid"].getSelectedIndex()
        # kept in sync for the Legacy class's other list-mode methods
        # that still read self.lastSelection directly (harmless extra
        # assignment for the GRIDSUPPORT class, which only reads it
        # back once, at __init__, to restore the persisted position)
        self.lastSelection = idx
        if self.reorderingMode and self.moveIndex != -1:
            self["statustext"].setText(_("MOVE: %s") % self.currList[self.moveIndex][0])
            if self.moveIndex != idx:
                _moveListElement(self.currList, self.moveIndex, idx)
                # only meaningful for GRIDSUPPORT's own icon-grid mode
                # (pixmapList drives each cell's icon there); in list
                # mode PlayerSelectorHostList.buildEntry() never reads
                # the pixmap argument at all (see its own class
                # comment), so this is harmless-but-unused busywork
                # there, not a behavior change
                _moveListElement(self.pixmapList, self.moveIndex, idx)
                self.moveIndex = idx
                self.reInitDisplayList()
            return
        self["statustext"].setText(self.currList[idx][0])

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
        # GRIDSUPPORT's own icon-grid mode only - same two independent
        # states as list mode's setReorderingHighlight() above
        file = resolveFilename(SCOPE_PLUGINS, f'Extensions/IPTVPlayer/icons/PlayerSelector/marker/marker{"Sel" if self.reorderingMode else ""}{self.iconSize + 45}.png')
        _setSelectionPixmap(self["grid"].master.master.instance, file)
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

    def keyGreen(self):
        if self.simpleListMode:
            return
        self.close((_("Disable/Enable groups"), "config_groups"))

    def keyCancel(self):
        printDBG(">> PlayerSelectorWidget.keyCancel")
        self.close(None)

    def keySetup(self):
        self.close((_("Configuration"), "config"))

    def keyYellow(self):
        self.close((_("Download manager"), "IPTVDM"))

    def openSearch(self):
        from Plugins.Extensions.IPTVPlayer.components.e2ivkselector import GetVirtualKeyboard
        caps = {}
        virtualKeyboard = GetVirtualKeyboard(caps)
        if caps.get('has_additional_params'):
            self.session.openWithCallback(self.searchCallback, virtualKeyboard, title=_("Search"), text='', additionalParams={})
        else:
            self.session.openWithCallback(self.searchCallback, virtualKeyboard, title=_("Search"), text='')

    def searchResultCallback(self, ret=None):
        if not isinstance(ret, IPTVChoiceBoxItem):
            return
        idx = ret.privateData
        PlayerSelectorWidget.LAST_SELECTION[self.groupName] = idx
        self.close(self.currList[idx])

    def _getSearchResultsHeight(self, numItems):
        # module-level helper, shared by both PlayerSelectorWidget variants
        return _getSearchResultsHeight(numItems)

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

    def openContextMenu(self):
        # BLUE key - was named keyBlue() (GRIDSUPPORT) / keyMenu()
        # (Legacy), same content, renamed on the move here to avoid
        # colliding with Legacy's OWN, unrelated keyBlue() (a Download-
        # manager shortcut reused by selectMenuCallback(), left in place)
        printDBG(">> PlayerSelectorWidget.openContextMenu")
        if self.currList:
            options = []
            selItem = self.getSelectedItem()
            if not self.simpleListMode and self.groupObj is not None and selItem is not None and len(self.groupObj.getGroupsWithoutHost(selItem[1])):
                options.append((_("Add host %s to group") % selItem[0], "ADD_HOST_TO_GROUP"))

            if not self.simpleListMode:
                # ids split into :ON/:OFF for
                # IPTVPlayerSelectorContextMenuChoiceBoxList's icon
                # lookup below (ReorderModeOnItem.png/ReorderModeOffItem.png
                # need to tell the two labels apart, which a plain
                # "CHANGE_REORDERING_MODE" id alone couldn't) -
                # selectMenuCallback() below checks membership in both
                # instead of equality to one fixed id
                if not self.reorderingMode and self.numOfItems - self.numOfLockedItems > 0:
                    options.append((_("Enable reordering mode"), "CHANGE_REORDERING_MODE:ON"))
                elif self.reorderingMode:
                    options.append((_("Disable reordering mode"), "CHANGE_REORDERING_MODE:OFF"))
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
                # list_class=IPTVPlayerSelectorContextMenuChoiceBoxList -
                # most rows get an icon instead of plain text, reusing
                # icon lookups already established by other ChoiceBox
                # lists in this plugin.
                choiceItems = [IPTVChoiceBoxItem(name=opt[0], privateData=opt[1]) for opt in options]
                height = _getContextMenuHeight(len(choiceItems))
                openChoiceBox(self.session, {'width': 600, 'height': height, 'current_idx': 0, 'title': _("Select option"), 'options': choiceItems, 'list_class': IPTVPlayerSelectorContextMenuChoiceBoxList, 'chrome': True, 'footerMargin': 136}, self.selectMenuCallback)

    def searchResultBlueMenu(self, item):
        # subset of openContextMenu()'s options - just the two
        # group-management actions, since the rest (reordering/sort/
        # download manager/settings/info) don't apply to a single search
        # result. Operates on the item the user is looking at in the
        # search popup, not whatever happens to be selected in the main
        # list/grid behind it.
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
            choiceItems = [IPTVChoiceBoxItem(name=opt[0], privateData=opt[1]) for opt in options]
            height = _getContextMenuHeight(len(choiceItems))
            openChoiceBox(self.session, {'width': 600, 'height': height, 'current_idx': 0, 'title': _("Select option"), 'options': choiceItems, 'list_class': IPTVPlayerSelectorContextMenuChoiceBoxList, 'chrome': True, 'footerMargin': 136}, boundFunction(self.searchResultBlueMenuCallback, idx, selItem))

    def searchResultBlueMenuCallback(self, idx, selItem, ret):
        if ret:
            ret = ret.privateData
            if ret == "ADD_HOST_TO_GROUP":
                self.addHostToGroup(selItem)
            elif ret == "DEL_ITEM":
                self.deleteItemAt(idx)

    def addHostToGroup(self, selItem=None):
        printDBG(">> PlayerSelectorWidget.addHostToGroup")
        if selItem is None:
            selItem = self.getSelectedItem()
        groupsList = self.groupObj.getGroupsWithoutHost(selItem[1])
        options = []
        for item in groupsList:
            options.append((item.title, item.name))

        if len(options):
            # description=opt[1] (group key) so IPTVHostSearchResultList's
            # existing buildEntry() shows the group's logos/groups/<key>logo.png
            # in front of the name, same as it already does for host logos in
            # the search results popup - reused as-is, no new list_class
            # needed. Taller _getSearchResultsHeight() (not the plain-text
            # _getContextMenuHeight()) since these rows now carry a logo too.
            choiceItems = [IPTVChoiceBoxItem(name=opt[0], description=opt[1], privateData=opt[1]) for opt in options]
            height = _getSearchResultsHeight(len(choiceItems))
            openChoiceBox(self.session, {'width': 550, 'height': height, 'current_idx': 0, 'title': _("Select group"), 'options': choiceItems, 'list_class': IPTVHostSearchResultList, 'chrome': True, 'footerMargin': 136}, boundFunction(self.addHostToGroupCallback, selItem))

    def addHostToGroupCallback(self, selItem, ret):
        if ret:
            ret = ret.privateData
            self.groupObj.addHostToGroup(ret, selItem[1])

    def _initListMode(self, session, inList, outList, numOfLockedItems, groupName, groupObj, groupDisplayName):
        # Shared List-view/Simple-list constructor for BOTH
        # PlayerSelectorWidget variants. List/Simple-list mode never uses
        # any real GRIDSUPPORT-exclusive skin feature (plain
        # <widget name="grid">, no listOrientation="grid") - the class
        # fork below only exists because this constructor used to live
        # inside the same class as the actual GRIDSUPPORT-dependent
        # icon-grid mode. Each class's own icon-grid mode (the genuine
        # reason for the GRIDSUPPORT/Legacy fork - two different
        # selection/paging models, native eListbox vs. hand-rolled
        # Cover3) is completely untouched by this.
        self.session = session
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
        self.moveIndex = -1
        self.lastSelection = PlayerSelectorWidget.LAST_SELECTION.get(self.groupName, 0)
        # placeholder, not real icons - list mode's own (inherited)
        # buildEntry() never reads the pixmap field of its content tuples
        # at all, but GRIDSUPPORT's OWN updateIcons()/deleteItemAt()/
        # selectMenuCallback() (deliberately not unified with Legacy's)
        # still unconditionally index into self.pixmapList regardless of
        # mode; those only get filled with real icons by the
        # icon-grid-only "load icons" loop each class's own __init__
        # keeps below, which list mode no longer reaches.
        self.pixmapList = [None] * self.numOfItems

        skinListHD, skinListFHD, skinListWQHD = _buildListModeSkin()
        self.skin = skinListWQHD if WQHD else (skinListFHD if FHD else skinListHD)
        Screen.__init__(self, session, mandatoryWidgets=["grid"])
        # own skinName per mode - list/grid/legacy-grid have different central widgets
        self.skinName = skinchrome.forceInternalSkinName(["PlayerSelectorListScreen", "PlayerSelectorScreen", "PlayerSelectorWidget"])
        self.setTitle("E2iPlayer %s" % GetIPTVPlayerVersion())

        self["key_menu"] = StaticText(_("MENU"))
        # "Enable reordering"/"Disable reordering" once active, toggled
        # in changeReorderingMode() - each class still has its own copy
        # of that one (its icon-grid branch genuinely differs), but both
        # show/toggle the same label since both start from this same
        # text.
        self["key_red"] = StaticText("" if self.simpleListMode else _("Enable reordering"))
        self["key_green"] = StaticText("" if self.simpleListMode else _("Hide/Active Group"))
        self["key_yellow"] = StaticText(_("Download manager"))
        self["key_blue"] = StaticText(_("More"))
        if self.simpleListMode:
            self["grid"] = PlayerSelectorSimpleList()
        else:
            self["grid"] = PlayerSelectorHostList()
        # group entries' own keys ("german", "userdefined", ...) aren't
        # meaningful to show next to their name, unlike host keys - only
        # the top-level "select a group" screen has groupName ==
        # 'selectgroup', every other value here means this list is showing
        # hosts (a specific group's hosts, 'selecthost', or 'all')
        self["grid"].showHostKey = (self.groupName != 'selectgroup')
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
            "blue": (self.openContextMenu, ""),
            "up": (self.listKeyUp, ""),
            "down": (self.listKeyDown, ""),
        }, prio=0, description="")

        # NOT self.onClose.append(self.__onClose) here - name-mangling
        # would bind it as self._PlayerSelectorListMode__onClose, which
        # doesn't exist (each PlayerSelectorWidget class still has its own
        # separate __onClose(), genuinely different between the two -
        # GRIDSUPPORT's reads self["grid"].getSelectedIndex(), Legacy's
        # reads self.lastSelection and also removes its own __event nav
        # listener). Each caller registers its own right after calling
        # this method instead - same reasoning for Legacy's
        # self.session.nav.event.append(self.__event), which GRIDSUPPORT
        # has no __event() to call at all.
        self.onLayoutFinish.append(self.layoutFinished)

    def listKeyUp(self):
        # one shared name for both PlayerSelectorWidget variants' list-mode
        # up/down handler. Named listKeyUp/listKeyDown (not keyUp/keyDown)
        # because Legacy's class ALSO has its own, differently-implemented
        # icon-grid keyUp()/keyDown() (hand-rolled Cover3 paging) - a plain
        # "keyUp"/"keyDown" name here would be silently shadowed by that
        # one, since Python class bodies share one method-name namespace
        # regardless of which mode ends up running at instance time.
        # GRIDSUPPORT's class doesn't have that collision (its own
        # keyUp()/keyDown() already serve both of ITS modes), so it just
        # aliases listKeyUp/listKeyDown to those directly - see its own
        # comment.
        idx = self["grid"].getSelectedIndex()
        if idx > 0:
            self["grid"].setCurrentIndex(idx - 1)
            self["grid"].instance.invalidate()

    def listKeyDown(self):
        idx = self["grid"].getSelectedIndex()
        if idx < self.numOfItems - 1:
            self["grid"].setCurrentIndex(idx + 1)
            self["grid"].instance.invalidate()


if GRIDSUPPORT:

    class PlayerSelectorWidget(_PlayerSelectorListMode, Screen):
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
            if self.listMode:
                # unified with the Legacy class below - see
                # _PlayerSelectorListMode._initListMode()'s own comment.
                # Icon-grid mode (the rest of this method) is the only
                # mode that actually needs this class to differ from
                # Legacy's.
                self._initListMode(session, inList, outList, numOfLockedItems, groupName, groupObj, groupDisplayName)
                self.onClose.append(self.__onClose)
                return
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

            # grid content geometry (statustext/categorytext/grid position,
            # <templates> pixel sizes) is deliberately NOT auto-scaled and
            # NOT part of skinchrome: the marker-frame PNGs
            # (marker/marker145/165/180.png) are loaded via
            # setSelectionPixmap(), which Enigma2 does not auto-scale like
            # declared skin widgets, so the grid's cell size must stay a
            # true fixed pixel size (145/165/180, tied to the IconsSize
            # setting) at every tier - a higher resolution fits more
            # same-sized cells rather than fewer, bigger ones. Only the
            # chrome (header/footer) actually scales linearly per tier.
            # Both this mode and "List view" below share the same screen
            # skeleton via _buildPlayerSelectorSkin(), see its own comment.
            skinHD, skinFHD, skinWQHD = _buildGridModeSkin()
            self.skin = skinWQHD if WQHD else (skinFHD if FHD else skinHD)
            Screen.__init__(self, session, mandatoryWidgets=["grid"])
            self.skinName = skinchrome.forceInternalSkinName(["PlayerSelectorGridScreen", "PlayerSelectorScreen", "PlayerSelectorWidget"])

            self.setTitle("E2iPlayer %s" % GetIPTVPlayerVersion())
            self["key_menu"] = StaticText(_("MENU"))
            self["key_red"] = StaticText("" if self.simpleListMode else _("Enable reordering"))
            self["key_green"] = StaticText("" if self.simpleListMode else _("Hide/Active Group"))
            self["key_yellow"] = StaticText(_("Download manager"))
            self["key_blue"] = StaticText(_("More"))
            self["grid"] = List([])
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
                "blue": (self.openContextMenu, ""),
                "up": (self.keyUp, ""),
                "down": (self.keyDown, ""),
            }, prio=0, description="")

            self.onClose.append(self.__onClose)
            self.onLayoutFinish.append(self.layoutFinished)

        # layoutFinished()/selectionChanged()/setSelectionImage()/
        # keySelect()/keyGreen()/openContextMenu() (BLUE) live on
        # _PlayerSelectorListMode above, shared with the Legacy class
        # below.

        def updateIcons(self):
            if self.listMode and not self.simpleListMode:
                # "List view" ("S") only, NOT "Simple list" ("P" - own
                # branch below). PlayerSelectorHostList doesn't override
                # buildEntry() (see its own class comment), so this feeds
                # the single-item IPTVChoiceBoxItem tuples
                # IPTVHostSearchResultList.buildEntry() expects - "name
                # (key)" formatting (showHostKey) happens here since that
                # inherited buildEntry() doesn't apply it itself.
                items = []
                for idx in range(self.numOfItems):
                    name, key = self.currList[idx][0], self.currList[idx][1]
                    displayName = "%s (%s)" % (name, key) if (key and self["grid"].showHostKey) else name
                    items.append((IPTVChoiceBoxItem(name=displayName, description=key, privateData=idx),))
                self["grid"].updateList(items)
                return
            if self.simpleListMode:
                # "Simple list" ("P") - PlayerSelectorSimpleList's own
                # buildEntry() also takes the single-item form, so builds
                # the same kind of tuples as "List view" above.
                items = []
                for idx in range(self.numOfItems):
                    name, key = self.currList[idx][0], self.currList[idx][1]
                    displayName = "%s (%s)" % (name, key) if (key and self["grid"].showHostKey) else name
                    items.append((IPTVChoiceBoxItem(name=displayName, description=key, privateData=idx),))
                self["grid"].updateList(items)
                return
            # Icon-grid mode (Components.Sources.List, its own <templates>
            # block) needs the 4-tuple shape (pixmap/name/idx/key)
            items = []
            for idx in range(0, self.numOfItems):
                items.append((self.pixmapList[idx], self.currList[idx][0], idx, self.currList[idx][1]))

            self["grid"].updateList(items)

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
            PlayerSelectorWidget.LAST_SELECTION[self.groupName] = idx

        def keyUp(self):
            # explicit up/down bindings instead of relying on eListbox's
            # own focus-based key handling - confirmed necessary on at
            # least one Enigma2 fork (OpenViX), where up/down did nothing
            # without this (same portability gap as setSelectionPixmap
            # being missing there). Uses getSelectedIndex()/setCurrentIndex()
            # rather than instance.moveSelection(instance.moveUp), which
            # turned out not to move the selection on that same OpenViX box.
            # Icon-grid mode only - list mode early-returns via the shared
            # _PlayerSelectorListMode._initListMode(), which binds its own
            # listKeyUp()/listKeyDown() instead, aliased to these two
            # right below.
            idx = self["grid"].getSelectedIndex()
            if idx > 0:
                self["grid"].setCurrentIndex(idx - 1)
                self._invalidateGrid()

        def keyDown(self):
            idx = self["grid"].getSelectedIndex()
            if idx < self.numOfItems - 1:
                self["grid"].setCurrentIndex(idx + 1)
                self._invalidateGrid()

        # aliases so the shared _PlayerSelectorListMode._initListMode()'s
        # ActionMap can bind "up"/"down" to one name valid on BOTH
        # PlayerSelectorWidget variants - Legacy's own listKeyUp()/
        # listKeyDown() names were chosen specifically to avoid colliding
        # with its OWN, differently-implemented icon-grid keyUp()/keyDown()
        # (hand-rolled Cover3 paging); this class doesn't have that
        # collision (keyUp()/keyDown() above already serve both of ITS
        # modes, see _invalidateGrid()'s own self.listMode branch), so a
        # plain alias is enough here - zero behavior change.
        listKeyUp = keyUp
        listKeyDown = keyDown

        def _invalidateGrid(self):
            # setCurrentIndex() moves the eListbox's internal selection
            # index, but on that same OpenViX box the row doesn't actually
            # repaint on its own afterwards - same underlying repaint gap
            # setReorderingHighlight()/setSelectionImage() already work
            # around elsewhere in this file by calling .invalidate() right
            # after changing selection-related state
            instance = self["grid"].instance if self.listMode else self["grid"].master.master.instance
            instance.invalidate()

        def selectMenuCallback(self, ret):
            # ret is an IPTVChoiceBoxItem (not a plain (label, id) tuple) -
            # adapted back into the same plain id right here instead of
            # touching every `ret ==` comparison below.
            printDBG(">> PlayerSelectorWidget.selectMenuCallback")
            if ret:
                ret = ret.privateData
                if ret == "SORT_NAME":
                    self.moveIndex = -1
                    self.reorderingMode = False
                    self.currList = sorted(self.currList, key=lambda x: x[1])
                    self.pixmapList = []
                    for idx in range(self.numOfItems):
                        icon = _getPlayerSelectorIcon(self.currList[idx][1], self.iconSize)
                        self.pixmapList.append(LoadPixmap(icon))
                    self.reInitDisplayList()
                elif ret in ("CHANGE_REORDERING_MODE:ON", "CHANGE_REORDERING_MODE:OFF"):
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
            # reached for it (currently unreachable in practice:
            # openContextMenu() never offers "Search" when self.simpleListMode)
            if self.listMode:
                height = self._getSearchResultsHeight(len(options))
                self.session.openWithCallback(self.searchResultCallback, IPTVChoiceBoxWidget, {'width': 550, 'height': height, 'current_idx': 0, 'title': _("Search results"), 'options': options, 'list_class': IPTVHostSearchResultList, 'chrome': True, 'footerMargin': 136, 'blue_callback': self.searchResultBlueMenu})
            else:
                self.session.openWithCallback(self.searchResultCallback, SearchResultGridWidget, {'options': options, 'iconSize': self.iconSize, 'title': _("Search results"), 'blue_callback': self.searchResultBlueMenu})

        def changeReorderingMode(self):
            printDBG(">> PlayerSelectorWidget.changeReorderingMode")
            if self.simpleListMode:
                return
            if self.currList:
                if not self.reorderingMode:
                    # entering reordering only makes sense if there's
                    # something left to reorder (numOfItems - locked items
                    # > 0) - the exit branch below must only ever run
                    # when reordering was actually active, not just
                    # whenever entering wasn't possible, or it can undo
                    # state that was never set up (see the icon-grid
                    # changeReorderingMode() below for the concrete case
                    # where getting this wrong actually corrupts data).
                    if (self.numOfItems - self.numOfLockedItems) > 0:
                        self.reorderingMode = True
                        self.setSelectionImage("Sel")
                        if not self.listMode:
                            self["grid"].master.master.instance.invalidate()
                        self.moveIndex = self["grid"].getSelectedIndex()
                    else:
                        return
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
                self["key_red"].setText(_("Disable reordering") if self.reorderingMode else _("Enable reordering"))
                self.selectionChanged()

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

            # chrome (logo/title header, OK/EXIT+blue-key footer) built via
            # skinchrome, same as PlayerSelectorWidget's own grid mode -
            # keys=('blue',)/showMenu=False since this popup only ever
            # binds "blue" (no menu/red/green/yellow action here). Content
            # area (statustext/grid position+size, <templates> pixel sizes)
            # stays screen-specific for the same reason as
            # PlayerSelectorWidget's: the marker-frame PNG loaded via
            # setSelectionPixmap() isn't auto-scaled by resolution=, so grid
            # cell size must stay a true fixed pixel size per tier.
            skinHD = """
            <screen name="SearchResultGridWidget" position="center,center" size="1020,676" title="E2iPlayer" backgroundColor="#34111112" flags="wfNoBorder">
                %s
                <widget name="statustext" position="20,570" size="980,30" font="Regular;20" valign="center" halign="center" backgroundColor="black" foregroundColor="white" transparent="1" />
                <widget source="grid" render="Listbox" position="20,72" size="980,492" conditional="grid" listOrientation="grid" scrollbarMode="showOnDemand" scrollbarSliderBorderWidth="1" scrollbarForegroundColor="#1b5a91" scrollbarBorderColor="#00b6b6b6" itemSpacing="20,20" itemAlignment="center" backgroundColorSelected="#24111112" transparent="1">
                    %s
                </widget>
                %s
            </screen>
            """ % (skinchrome.build_header(scale=1.0, iconBase=skinchrome.ICON_ROOT + "/HD"), _GRID_TEMPLATES, skinchrome.build_footer(676, scale=1.0, iconBase=skinchrome.ICON_ROOT + "/HD", keys=('blue',), showMenu=False))

            skinFHD = """
            <screen name="SearchResultGridWidget" position="center,center" size="1530,1014" title="E2iPlayer" backgroundColor="#34111112" flags="wfNoBorder">
                %s
                <widget name="statustext" position="30,860" size="1470,45" font="Regular;30" valign="center" halign="center" backgroundColor="black" foregroundColor="white" transparent="1" />
                <widget source="grid" render="Listbox" position="30,108" size="1470,738" conditional="grid" listOrientation="grid" scrollbarMode="showOnDemand" scrollbarSliderBorderWidth="1" scrollbarForegroundColor="#1b5a91" scrollbarBorderColor="#00b6b6b6" itemSpacing="20,20" itemAlignment="center" backgroundColorSelected="#24111112" transparent="1">
                    %s
                </widget>
                %s
            </screen>
            """ % (skinchrome.build_header(scale=1.5, iconBase=skinchrome.ICON_ROOT + "/FHD"), _GRID_TEMPLATES, skinchrome.build_footer(1014, scale=1.5, iconBase=skinchrome.ICON_ROOT + "/FHD", keys=('blue',), showMenu=False))

            skinWQHD = """
            <screen name="SearchResultGridWidget" position="center,center" size="2040,1352" title="E2iPlayer" backgroundColor="#34111112" flags="wfNoBorder">
                %s
                <widget name="statustext" position="40,1147" size="1960,60" font="Regular;40" valign="center" halign="center" backgroundColor="black" foregroundColor="white" transparent="1" />
                <widget source="grid" render="Listbox" position="40,144" size="1960,984" conditional="grid" listOrientation="grid" scrollbarMode="showOnDemand" scrollbarSliderBorderWidth="1" scrollbarForegroundColor="#1b5a91" scrollbarBorderColor="#00b6b6b6" itemSpacing="20,20" itemAlignment="center" backgroundColorSelected="#24111112" transparent="1">
                    %s
                </widget>
                %s
            </screen>
            """ % (skinchrome.build_header(scale=2.0, iconBase=skinchrome.ICON_ROOT + "/WQHD"), _GRID_TEMPLATES, skinchrome.build_footer(1352, scale=2.0, iconBase=skinchrome.ICON_ROOT + "/WQHD", keys=('blue',), showMenu=False))

            WQHD = screenwidth and screenwidth >= 2560
            self.skin = skinWQHD if WQHD else (skinFHD if FHD else skinHD)
            Screen.__init__(self, session, mandatoryWidgets=["grid"])
            self.skinName = skinchrome.forceInternalSkinName(["SearchResultGridScreen", "SearchResultGridWidget"])

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
            file = resolveFilename(SCOPE_PLUGINS, 'Extensions/IPTVPlayer/icons/PlayerSelector/marker/marker%i.png' % (self.iconSize + 45))
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

    class PlayerSelectorWidget(_PlayerSelectorListMode, Screen):
        LAST_SELECTION = {}

        def __init__(self, session, inList, outList, numOfLockedItems=0, groupName='', groupObj=None, groupDisplayName=None):
            printDBG("PlayerSelectorWidget.__init__ --------------------------------")
            screenwidth = getDesktop(0).size().width()
            screenheight = getDesktop(0).size().height()
            iconSize = GetAvailableIconSize()
            # "S" (List view) and "P" (Simple list) reuse the exact same
            # eListboxPythonMultiContent-based list widget/chrome skin the
            # GRIDSUPPORT class's own list mode uses below. That widget has
            # no GRIDSUPPORT/OpenATV dependency at all, unlike the per-cell
            # Cover3 grid this class otherwise uses (which does need
            # eListbox.orGrid-adjacent skin support).
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
                # unified with the GRIDSUPPORT class above - see
                # _PlayerSelectorListMode._initListMode()'s own comment.
                # self.session.nav.event.append(self.__event) is a no-op
                # leftover (__event() below just does `pass`) only this
                # class's icon-grid mode/__onClose() still reference -
                # kept here rather than in the shared method, which the
                # GRIDSUPPORT class has no __event() to call at all.
                self._initListMode(session, inList, outList, numOfLockedItems, groupName, groupObj, groupDisplayName)
                self.session.nav.event.append(self.__event)
                self.onClose.append(self.__onClose)
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

            # chrome (logo/title header, OK/EXIT+color-key footer) - only
            # "blue" is ever bound in this grid mode (openContextMenu()
            # options popup - Download manager is one of its entries; MENU
            # opens config directly via keySetup(), same split GRIDSUPPORT
            # and this class's own list mode both use), so the footer only
            # needs that one slot. scale/iconBase give this mode the same
            # real per-tier distinction (HD/FHD/WQHD) the rest of the
            # chrome already has.
            scale = skinchrome.getScale(screenwidth)
            chromeIconBase = skinchrome.getIconBase(screenwidth)
            headerHeight = skinchrome.header_height(scale)
            footerHeight = skinchrome.footer_height(scale)

            # position of first img
            offsetCoverX = 25
            # stack the page-dot pagination markers and the focused item's
            # name (statustext) below the header without overlapping:
            # divider line -> dots -> statustext -> grid.
            # radio_button_on/off.png is a 32x32 user-designed icon now
            # (was a native 16x16 file before) - plain ePixmap/Pixmap
            # widgets in this codebase never scale their pixmap content to
            # the declared box (see this same file's own
            # "setSelectionPixmap() isn't auto-scaled by resolution="
            # comment above, and iptvlogo.png/e2ivk's flags/etc. always
            # shipping separate native-sized files per tier instead of
            # relying on any such scaling), so the box itself has to scale
            # explicitly here, paired with real per-tier 16/24/32 assets
            # (icons/HD|FHD|WQHD/radio_button_on|off.png).
            pageItemSize = int(round(16 * scale))
            statusTextH = int(round(30 * scale))
            # the selection marker frame is padded 45px bigger than the icon
            # itself (see markerWidth/markerHeight below), so it overhangs
            # the grid's nominal top edge by half that on a row-1 item -
            # accounted for here so the marker frame doesn't overlap
            # statustext.
            markerPadding = 45
            pageItemStartY = headerHeight + int(round(6 * scale))
            statusTextY = pageItemStartY + pageItemSize + int(round(4 * scale))
            offsetCoverY = statusTextY + statusTextH + markerPadding // 2 + int(round(6 * scale))

            # image size
            coverWidth = iconSize
            coverHeight = iconSize

            # space/distance between images
            disWidth = int(coverWidth / 3)
            disHeight = int(coverHeight / 4)

            # marker size should be larger than img
            markerWidth = markerPadding + coverWidth
            markerHeight = markerPadding + coverHeight

            # how to calculate position of image with indexes indxX, indxY:
            # posX = offsetCoverX + (coverWidth + disWidth) * indxX
            # posY = offsetCoverY + (coverHeight + disHeight) * indxY

            # how to calculate position of marker for image with posX, posY
            # markerPosX = posX - (markerWidth - coverWidth)/2
            # markerPosY = posY - (markerHeight - coverHeight)/2

            tmpX = coverWidth + disWidth
            tmpY = coverHeight + disHeight

            # clamp the column count so the window never runs off the
            # right edge of the screen - derived by solving naturalWidth's
            # own formula below for the numOfCol that makes it equal
            # screenwidth. calcDisplayVariables() already pages by
            # numOfLines/numOfRow generically (it doesn't care whether the
            # extra items came from too many rows or too many columns), so
            # shrinking numOfCol here is exactly as safe as the existing
            # numOfRow clamp below.
            # tmpX == 0 (iconSize == 0 - GetAvailableIconSize() can
            # legitimately return that on an incomplete install missing
            # marker100/120/135.png) would otherwise raise
            # ZeroDivisionError here and crash __init__ outright - skip
            # the clamp entirely in that already-broken case rather than
            # risk a fresh crash on top of it.
            if tmpX > 0:
                maxCols = int((screenwidth - offsetCoverX - offsetCoverX + disWidth) / tmpX)
                if maxCols < 1:
                    maxCols = 1
                if numOfCol > maxCols:
                    numOfCol = maxCols

            # minimum width so the chrome always fits, even for a narrow
            # 3-4 column grid. The header's title text ("E2iPlayer
            # <version>") is the real binding constraint here, not the
            # footer (blue+menu alone needs only ~400px at HD). 280 (widest
            # measured across several comparable sans-serif fonts at the
            # header's actual 20pt + ~12% safety margin) is about as far
            # as this should go without an actual on-device font to verify
            # against. Against build_header()'s titleX+titleRightMargin
            # sum (140), that's 420.
            naturalWidth = offsetCoverX + tmpX * numOfCol + offsetCoverX - disWidth
            windowWidth = max(naturalWidth, int(round(420 * scale)))
            # when the minimum width above is the wider of the two, the
            # grid itself is narrower than the window - center it instead
            # of leaving it flush left with empty space on the right.
            # onStart()'s own offsetCoverX re-derivation (from the actual
            # rendered marker widget position) already picks this shift up
            # automatically, so only the skin-declared positions built
            # below need it.
            gridOffsetX = offsetCoverX + (windowWidth - naturalWidth) // 2

            # position of first marker
            offsetMarkerX = int(gridOffsetX - (markerWidth - coverWidth) / 2)
            offsetMarkerY = int(offsetCoverY - (markerHeight - coverHeight) / 2)

            # clamp the row count so the footer never gets pushed off the
            # bottom of the screen - a bigger iconSize (120/135) can make
            # the grid tall enough to push the footer past the screen's
            # actual height even when the same numOfRow fits fine at
            # iconSize 100. The "auto" row/col heuristics above never hit
            # this because they never combine a high row count with a
            # large iconSize at HD, but a user's manual numOfRow/numOfCol
            # config bypasses that guard entirely - so clamp here
            # regardless of where numOfRow came from, and let the existing
            # pagination put any rows this removes on additional pages
            # instead of off-screen.
            # same tmpY == 0 (iconSize == 0) guard as maxCols above.
            if tmpY > 0:
                maxRows = int((screenheight - offsetCoverY - offsetCoverX + disHeight - footerHeight) / tmpY)
                if maxRows < 1:
                    maxRows = 1
                if numOfRow > maxRows:
                    numOfRow = maxRows

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

            # pagination - centered above the grid the same way the grid
            # itself is (see gridOffsetX above); Y position stacked with
            # statustext above, see offsetCoverY derivation above
            self.pageItemSize = pageItemSize
            self.pageItemStartX = (windowWidth - naturalWidth) // 2 + int((naturalWidth - self.numOfPages * self.pageItemSize) / 2)
            self.pageItemStartY = pageItemStartY

            windowHeight = offsetCoverY + tmpY * numOfRow + offsetCoverX - disHeight + footerHeight
            statusFont = int(round(20 * scale))

            skin = """
            <screen name="PlayerSelectorWidget" position="center,center" size="%d,%d" backgroundColor="#34111112" flags="wfNoBorder">
                %s
                <widget name="statustext" position="10,%d" zPosition="1" size="%d,%d" font="Regular;%d" halign="center" valign="center" transparent="1"/>
                <widget name="marker" zPosition="2" position="%d,%d" size="%d,%d" transparent="1" alphatest="blend" />
                <widget name="page_marker" zPosition="3" position="%d,%d" size="%d,%d" transparent="1" alphatest="blend" />
                """ % (
            windowWidth, windowHeight,
            skinchrome.build_header(scale=scale, iconBase=chromeIconBase),
            statusTextY, windowWidth - 20, statusTextH, statusFont,
            offsetMarkerX, offsetMarkerY,  # first marker position
            markerWidth, markerHeight,    # marker size
            self.pageItemStartX, self.pageItemStartY,  # pagination marker
            self.pageItemSize, self.pageItemSize,
            )

            for y in range(1, numOfRow + 1):
                for x in range(1, numOfCol + 1):
                    skinCoverLine = """<widget name="cover_%s%s" zPosition="4" position="%d,%d" size="%d,%d" transparent="1" alphatest="blend" />""" % (x, y,
                        (gridOffsetX + tmpX * (x - 1)),  # pos X image
                        (offsetCoverY + tmpY * (y - 1)),  # pos Y image
                        coverWidth,
                        coverHeight
                    )
                    skin += '\n' + skinCoverLine

            # add pagination items
            for pageItemOffset in range(self.numOfPages):
                pageItemX = self.pageItemStartX + pageItemOffset * self.pageItemSize
                skinCoverLine = """<ePixmap zPosition="2" position="%d,%d" size="%d,%d" pixmap="%s" transparent="1" alphatest="blend" />""" % (pageItemX, self.pageItemStartY, self.pageItemSize, self.pageItemSize, chromeIconBase + '/radio_button_off.png')
                skin += '\n' + skinCoverLine
            skin += '\n' + skinchrome.build_footer(windowHeight, scale=scale, iconBase=chromeIconBase, keys=('blue',))
            skin += '</screen>'
            self.skin = skin

            Screen.__init__(self, session)
            self.skinName = skinchrome.forceInternalSkinName(["PlayerSelectorLegacyGridScreen", "PlayerSelectorScreen", "PlayerSelectorWidget"])
            self.setTitle("E2iPlayer %s" % GetIPTVPlayerVersion())

            self.session.nav.event.append(self.__event)
            self.onClose.append(self.__onClose)

            # load icons
            self.pixmapList = []
            for idx in range(0, self.numOfItems):
                icon = _getPlayerSelectorIcon(self.currList[idx][1], self.IconsSize)
                self.pixmapList.append(LoadPixmap(icon))

            self.markerPixmap = LoadPixmap(GetIconDir('PlayerSelector/marker/marker%i.png' % self.MarkerSize))
            self.markerPixmapSel = LoadPixmap(GetIconDir('PlayerSelector/marker/markerSel%i.png' % self.MarkerSize))
            self.pageMarkerPixmap = LoadPixmap(chromeIconBase + '/radio_button_on.png')

            self["actions"] = ActionMap(["DirectionActions", "ColorActions", "IPTVPlayerListActions"],
            {
                "ok": self.ok_pressed,
                "back": self.back_pressed,
                "left": self.keyLeft,
                "right": self.keyRight,
                "up": self.keyUp,
                "down": self.keyDown,
                "blue": self.openContextMenu,
                "menu": self.keySetup,
            }, -1)

            self["key_menu"] = StaticText(_("MENU"))
            # MENU -> keySetup() (config), BLUE -> openContextMenu() (options
            # popup) - matches GRIDSUPPORT's own grid mode and this same
            # class's own list mode
            self["key_blue"] = StaticText(_("More"))
            self["marker"] = Cover3()
            self["page_marker"] = Cover3()

            for y in range(1, self.numOfRow + 1):
                for x in range(1, self.numOfCol + 1):
                    strIndex = "cover_%s%s" % (x, y)
                    self[strIndex] = Cover3()

            self["statustext"] = Label(self.currList[0][0])

            self.onLayoutFinish.append(self.onStart)
            self.visible = True

        # List view/Simple list mode's own constructor/listKeyUp()/
        # listKeyDown()/ActionMap live in
        # _PlayerSelectorListMode._initListMode()/listKeyUp()/listKeyDown()
        # instead, unified with the GRIDSUPPORT class's own list mode.
        # layoutFinished()/selectionChanged()/setSelectionImage()/
        # keySelect()/keyGreen()/openContextMenu() (BLUE) live there too.

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
            self.offsetCoverX = self['marker'].position[0] + (self.markerWidth - self.coverWidth) / 2
            self.offsetCoverY = self['marker'].position[1] + (self.markerHeight - self.coverHeight) / 2
            self.pageItemStartX = self['page_marker'].position[0]
            self.pageItemStartY = self['page_marker'].position[1]
            self.initDisplayList()
            return

        def reInitDisplayList(self):
            if self.listMode:
                # matches GRIDSUPPORT's own reInitDisplayList() - a plain
                # updateList() call preserves the widget's current native
                # selection index by itself, no explicit re-positioning
                # needed
                self.numOfItems = len(self.currList)
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
            if self.listMode and not self.simpleListMode:
                # see GRIDSUPPORT's own copy of this comment for the full
                # reasoning. "Simple list" ("P") has its own branch below.
                items = []
                for idx in range(self.numOfItems):
                    name, key = self.currList[idx][0], self.currList[idx][1]
                    displayName = "%s (%s)" % (name, key) if (key and self["grid"].showHostKey) else name
                    items.append((IPTVChoiceBoxItem(name=displayName, description=key, privateData=idx),))
                self["grid"].updateList(items)
                return
            if self.simpleListMode:
                # see GRIDSUPPORT's own copy of this comment for the full
                # reasoning - matching single-item tuple shape as "List
                # view" above.
                items = []
                for idx in range(self.numOfItems):
                    name, key = self.currList[idx][0], self.currList[idx][1]
                    displayName = "%s (%s)" % (name, key) if (key and self["grid"].showHostKey) else name
                    items.append((IPTVChoiceBoxItem(name=displayName, description=key, privateData=idx),))
                self["grid"].updateList(items)
                return
            idx = int(self.currPage * (self.numOfCol * self.numOfRow))
            for y in range(1, self.numOfRow + 1):
                for x in range(1, self.numOfCol + 1):
                    strIndex = "cover_%s%s" % (x, y)
                    printDBG("updateIcon for self[%s]" % strIndex)
                    if idx < self.numOfItems:
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
            # unrelated to openContextMenu() on _PlayerSelectorListMode
            # (also bound to the "blue" key, but only for the OTHER two
            # PlayerSelectorWidget/SearchResultGridWidget screens) - this
            # is a same-named leftover from before this class's own BLUE
            # binding was the options menu; only still reachable via
            # selectMenuCallback()'s "IPTVDM" dispatch below now
            self.close((_("Download manager"), "IPTVDM"))

        # keyMenu() (BLUE, the options-menu builder) lives as
        # openContextMenu() on _PlayerSelectorListMode above, shared with
        # the GRIDSUPPORT class - both ActionMaps in this class bind
        # "blue" to it now instead. Its own currList guard means BLUE
        # does nothing on an empty list, matching GRIDSUPPORT's behavior.

        def selectMenuCallback(self, ret):
            # ret is an IPTVChoiceBoxItem (not a plain (label, id) tuple) -
            # adapted back into the same plain id right here instead of
            # touching every `ret ==` comparison below.
            printDBG(">> PlayerSelectorWidget.selectMenuCallback")
            if ret:
                ret = ret.privateData
                if ret == "SORT_NAME":
                    self.moveIndex = -1
                    self.reorderingMode = False
                    self.currList = sorted(self.currList, key=lambda x: x[1])
                    if not self.listMode:
                        self.pixmapList = []
                        for idx in range(self.numOfItems):
                            icon = _getPlayerSelectorIcon(self.currList[idx][1], self.IconsSize)
                            self.pixmapList.append(LoadPixmap(icon))
                    self.reInitDisplayList()
                elif ret in ("CHANGE_REORDERING_MODE:ON", "CHANGE_REORDERING_MODE:OFF"):
                    self.changeReorderingMode()
                elif ret == "IPTVDM":
                    self.keyBlue()
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
                    idx = self.lastSelection if self.listMode else (self.currLine * self.numOfCol + self.dispX)
                    self.deleteItemAt(idx)
                elif ret == 'INFO':
                    self.showInfo()
                elif ret == 'SETTINGS':
                    self.keySetup()
                elif ret == 'SEARCH':
                    self.openSearch()

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
            self.session.openWithCallback(self.searchResultCallback, IPTVChoiceBoxWidget, {'width': 550, 'height': height, 'current_idx': 0, 'title': _("Search results"), 'options': options, 'list_class': IPTVHostSearchResultList, 'chrome': True, 'footerMargin': 136, 'blue_callback': self.searchResultBlueMenu})

        def deleteItemAt(self, idx):
            # searchResultBlueMenuCallback() can delete a specific search
            # result too, not just whatever's currently on-screen - same
            # idea as GRIDSUPPORT's own deleteItemAt(), which this mirrors,
            # except list mode still needs its self.lastSelection
            # bookkeeping kept in bounds since it (unlike grid mode's
            # self.pixmapList) isn't index-parallel with self.currList
            if idx < self.numOfItems:
                del self.currList[idx]
                if not self.listMode:
                    del self.pixmapList[idx]
                elif idx < self.lastSelection or self.lastSelection >= len(self.currList):
                    # keeps the cached self.lastSelection valid for the
                    # other methods that still read it directly -
                    # reInitDisplayList()'s updateList() below leaves the
                    # widget's own native cursor as-is, same as
                    # GRIDSUPPORT's deleteItemAt(). Needs shifting not only
                    # when it falls out of bounds (list shrank below it)
                    # but also whenever the deleted item sat BEFORE it -
                    # every surviving item after idx moves down one
                    # position, so lastSelection has to move with it to
                    # keep pointing at the same logical item.
                    if self.lastSelection > 0:
                        self.lastSelection -= 1
                self.reInitDisplayList()

        def changeReorderingMode(self):
            printDBG(">> PlayerSelectorWidget.changeReorderingMode")
            if self.simpleListMode:
                return
            if self.listMode:
                if not self.currList:
                    return
                if not self.reorderingMode:
                    if (self.numOfItems - self.numOfLockedItems) > 0:
                        self.reorderingMode = True
                        self.setSelectionImage("Sel")
                        self.moveIndex = self.lastSelection
                    else:
                        return
                else:
                    self.moveIndex = -1
                    self.reorderingMode = False
                    self.setSelectionImage("")
                # matches GRIDSUPPORT's own list-mode label toggle -
                # key_red starts as "Enable reordering" for both classes
                # (see the shared _initListMode()), so both need to flip
                # it the same way.
                self["key_red"].setText(_("Disable reordering") if self.reorderingMode else _("Enable reordering"))
                self.selectionChanged()
                return
            if not self.reorderingMode:
                # entering reordering only makes sense if there's
                # something left to reorder (numOfItems - locked items >
                # 0). The exit branch below must only run when reordering
                # was actually active - it APPENDS self.inList's own
                # trailing numOfLockedItems items onto self.currList,
                # which is only correct to undo an earlier "enter" that
                # actually removed them. Running it unconditionally
                # (whenever entering wasn't possible) would duplicate
                # those reserved rows in self.currList, and since
                # PlayerSelectorWidget.__onClose() copies currList
                # straight into outList, that duplication could end up
                # getting persisted as if the reserved rows were real
                # groups too (see selectGroupCallback()'s own comment in
                # iptvplayerwidget.py for the save-side half of this fix).
                if (self.numOfItems - self.numOfLockedItems) > 0:
                    self.reorderingMode = True
                    if self.numOfLockedItems > 0:
                        self.currList = self.currList[:self.numOfLockedItems * -1]
                        self.reInitDisplayList()
                else:
                    return
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
