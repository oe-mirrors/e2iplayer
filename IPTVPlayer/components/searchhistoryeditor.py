# -*- coding: utf-8 -*-
# added: 18.08.2026 - Kamikaze24

import os
import codecs

from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, getReorderOnReuseEnabled, setReorderOnReuseEnabled, findT9JumpIndex
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str

from enigma import gRGB

from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.config import config
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.Sources.StaticText import StaticText

from Plugins.Extensions.IPTVPlayer.components.e2ivkselector import GetVirtualKeyboard
from Plugins.Extensions.IPTVPlayer.components import skinchrome
from Tools.NumericalTextInput import NumericalTextInput
from Tools.LoadPixmap import LoadPixmap

try:
    text_type = unicode
    binary_type = str
    PY2 = True
except NameError:
    text_type = str
    binary_type = bytes
    PY2 = False

TYPE_SEP = u'|--TYPE--|'


def toUnicode(value):
    try:
        if value is None:
            return u''
        if isinstance(value, text_type):
            return value
        if isinstance(value, binary_type):
            return value.decode('utf-8', 'ignore')
        return text_type(value)
    except Exception:
        try:
            if PY2:
                return text_type(str(value), 'utf-8', 'ignore')
            return text_type(value)
        except Exception:
            printExc()
            return u''


def guiSafeStr(value):
    try:
        if value is None:
            return ''
        return ensure_str(toUnicode(value))
    except Exception:
        try:
            if PY2 and isinstance(value, text_type):
                return value.encode('utf-8')
            return str(value)
        except Exception:
            printExc()
            return ''


class HistoryEntry(object):
    __slots__ = ('title', 'searchtype')

    def __init__(self, title, searchtype=None):
        self.title = toUnicode(title).strip()
        self.searchtype = toUnicode(searchtype).strip() if searchtype else None

    def toLine(self):
        if self.searchtype:
            return self.title + TYPE_SEP + self.searchtype
        return self.title

    def displayText(self):
        return self.title


def parseHistoryFile(path, reverseForDisplay=False):
    entries = []
    try:
        if not os.path.isfile(path):
            return entries

        with codecs.open(path, 'r', 'utf-8', 'ignore') as f:
            raw = f.read()

        raw = toUnicode(raw)
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            if TYPE_SEP in line:
                title, searchtype = line.split(TYPE_SEP, 1)
                entries.append(HistoryEntry(title, searchtype))
            else:
                entries.append(HistoryEntry(line))

        if reverseForDisplay:
            entries.reverse()
    except Exception:
        printExc()

    return entries


def writeHistoryFile(path, entries, reverseForWrite=False):
    try:
        dirName = os.path.dirname(path)
        if dirName and not os.path.isdir(dirName):
            os.makedirs(dirName)

        entriesToWrite = list(entries)
        if reverseForWrite:
            entriesToWrite.reverse()

        tmpPath = path + '.tmp'
        with codecs.open(tmpPath, 'w', 'utf-8', 'replace') as f:
            for entry in entriesToWrite:
                f.write(entry.toLine() + u'\n')

        try:
            os.rename(tmpPath, path)
        except OSError:
            if os.path.isfile(path):
                os.remove(path)
            os.rename(tmpPath, path)

        return True
    except Exception:
        printExc()
        return False


class SearchHistoryEditor(Screen):
    # Uses `skinchrome`'s `resolution="1280,720"` auto-scale
    # `build_header_auto()`/`build_footer_auto()`-shaped approach, same as
    # `IPTVFavouritesMainWidget`/`YouTubeUserLinksEditorScreen` (plain
    # `MenuList`, no fixed-pixel grid/marker content fighting auto-scale).
    #
    # Footer uses `build_footer()` directly (not `build_footer_auto()`)
    # with `showMenu=True` - the auto variant hardcodes `showMenu=False`
    # since none of ITS callers ever bind a live MENU action, but this
    # screen does (`keyMenu()`'s options popup) - same reasoning
    # `iptvplayerwidget.py` already documents for its own identical
    # choice. MENU only ever shows an icon in this chrome (the word is
    # baked into `menu.png` itself), no adjacent text label the way color
    # keys get one - `self.IDS_MENU_OPTIONS`/`self.IDS_DISABLE_REORDERING`
    # still get pushed into `key_menu`'s source (keeps `key_menu`
    # non-empty so `ConditionalShowHide` keeps the icon visible in both
    # states), their actual text just no longer renders anywhere.
    #
    # OK now shows an icon too (`build_footer()`'s own default) - this
    # was never hinted on screen before despite already being live and
    # doing the exact same thing as BLUE (`'ok': self.keyRename` and
    # `'blue': self.keyRename` were already the same handler), so this
    # is a correctness fix, not just chrome parity.
    #
    # `self['list']` uses `IPTVMainNavigatorList` (`iptvlist.py`, not a
    # plain `Components.MenuList.MenuList`) - the same icon+text list
    # component `IPTVFavouritesMainWidget`/the sub-downloader/the main
    # navigator itself all share, so this picks up both the icon (via
    # `CDisplayListItem(type=TYPE_SEARCH_HISTORY)`, its own existing
    # `ICONS_FILESNAMES` mapping) and that component's smaller, tier-
    # aware font/row height for free, instead of hand-tuning either. The
    # skin's own `itemHeight`/`font` on the `list` widget are superseded
    # by this component's Python-side `self.l.setItemHeight()`/
    # `setFont()` (same as `IPTVFavouritesMainWidget`'s own skin, which
    # keeps a close-but-inexact approximation there too) - left set to a
    # reasonable value rather than removed, for a reader glancing at the
    # skin string alone.
    def __prepareSkin(self):
        iconBase = skinchrome.getIconBase()
        HEIGHT = 700
        clockPart = """<widget source="global.CurrentTime" render="Label" position="960,10" size="150,40" foregroundColor="white" backgroundColor="black" borderWidth="1" borderColor="black" transparent="1" zPosition="2" font="Regular;24" valign="center" halign="right">
                <convert type="ClockToText">Format:%H:%M</convert>
            </widget>
            <widget source="global.CurrentTime" render="Label" position="720,20" size="300,24" foregroundColor="white" backgroundColor="black" borderWidth="1" borderColor="black" transparent="1" zPosition="2" font="Regular;16" valign="center" halign="right">
                <convert type="ClockToText">Date</convert>
            </widget>""" if config.plugins.iptvplayer.show_header_clock.value else ""
        return """
        <screen name="SearchHistoryEditor" position="center,center" size="1200,%d" resolution="1280,720" title="Search History" backgroundColor="#34111112" flags="wfNoBorder">
            %s
            <widget name="status" position="20,68" size="1160,30" font="Regular;24" halign="left" valign="center" foregroundColor="white" backgroundColor="black" borderWidth="1" borderColor="black" zPosition="1" transparent="1" />
            <widget name="list" position="20,108" size="1160,518" itemHeight="36" font="Regular;20" scrollbarMode="showOnDemand" scrollbarSliderBorderWidth="1" scrollbarForegroundColor="#1b5a91" scrollbarBorderColor="#00b6b6b6" enableWrapAround="1" foregroundColor="white" backgroundColor="black" foregroundColorSelected="white" backgroundColorSelected="#1b5a91" borderWidth="1" borderColor="black" transparent="1" />
            %s
            %s
        </screen>
        """ % (
            HEIGHT,
            skinchrome.build_header_auto(iconBase=iconBase),
            clockPart,
            skinchrome.build_footer(HEIGHT, scale=1.0, iconBase=iconBase, keys=('red', 'green', 'yellow', 'blue'), showMenu=True, showNav=False),
        )

    def __init__(self, session, historyFile, reverseForDisplay=True, reverseForWrite=True):
        self.session = session
        self.skin = self.__prepareSkin()
        Screen.__init__(self, session)
        # explicit name so an external skin can target this screen
        self.skinName = skinchrome.forceInternalSkinName(["SearchHistoryEditor"])

        self.historyFile = toUnicode(historyFile)
        self.reverseForDisplay = bool(reverseForDisplay)
        self.reverseForWrite = bool(reverseForWrite)

        self.entries = []
        self.sortMode = 0
        self.dirty = False
        self.numberInput = NumericalTextInput(handleTimeout=False)
        self.reorderOnReuse = getReorderOnReuseEnabled(self.historyFile)
        self.manualReorderMode = False
        self.manualReorderItemPicked = False

        # reuse the exact strings from iptvfavouriteswidgets.py's reordering
        # toggle so translators don't need new entries for this screen
        self.IDS_ENABLE_REORDERING = _(u'Enable reordering')
        self.IDS_DISABLE_REORDERING = _(u'Disable reordering')
        self.IDS_MENU_OPTIONS = _(u'MENU=Options')

        printDBG('SearchHistoryEditor init file=%s' % self.historyFile)

        self['status'] = Label('')
        self['key_red'] = StaticText('')
        self['key_green'] = StaticText('')
        self['key_yellow'] = StaticText('')
        self['key_blue'] = StaticText('')
        self['key_menu'] = StaticText('')
        # shared icon+text list component every other main-navigation-
        # style list uses (favourites, sub-downloader, ...), so each row
        # shows the same "SearchHistoryItem.png" icon E2iPlayerWidget's
        # own search-history category list already uses, and picks up
        # that component's smaller, tier-aware font/row height for free
        # (import kept local - IPTVMainNavigatorList lives in iptvlist.py,
        # which imports ihost.py, which imports THIS module at load time;
        # a module-level import here would be the exact same circular
        # import iptvchoicebox.py's own local-import fix in keyMenu()
        # already had to work around).
        from Plugins.Extensions.IPTVPlayer.components.iptvlist import IPTVMainNavigatorList
        self['list'] = IPTVMainNavigatorList()

        self.setTitle(guiSafeStr(_(u'Edit search history')))
        self.safeSetText(self['key_red'], _(u'Delete'))
        # GREEN toggles manual reordering directly; A-Z/Z-A/reset live in
        # the MENU popup instead. Its label follows the same enable/
        # disable pair MENU's own reordering entry uses - kept in sync by
        # keyStartManualSort()/keyStopManualSort() below
        self.safeSetText(self['key_green'], self.IDS_ENABLE_REORDERING)
        self.safeSetText(self['key_yellow'], _(u'Save'))
        self.safeSetText(self['key_blue'], _(u'Rename'))
        self.safeSetText(self['key_menu'], self.IDS_MENU_OPTIONS)

        actionsDict = {
            'ok': self.keyRename,
            'back': self.keyExit,
            'cancel': self.keyExit,
            'red': self.keyDelete,
            'green': self.keyToggleManualSort,
            'yellow': self.keySave,
            'blue': self.keyRename,
            'up': self.keyUp,
            'down': self.keyDown,
            # neutralize the ListboxActions page/home/end keys instead of
            # leaving them unbound - matches iptvfavouriteswidgets.py's
            # moveItem()/keyDrop() pattern, which is the one confirmed
            # working for manual reordering on oATV8. Without an explicit
            # (no-op) handler these fall through unhandled on some cores.
            'moveUp': self.keyIgnoreListboxNav,
            'moveDown': self.keyIgnoreListboxNav,
            'moveTop': self.keyIgnoreListboxNav,
            'moveEnd': self.keyIgnoreListboxNav,
            'home': self.keyIgnoreListboxNav,
            'end': self.keyIgnoreListboxNav,
            'pageUp': self.keyIgnoreListboxNav,
            'pageDown': self.keyIgnoreListboxNav,
            # 'menu' moved to its own ActionMap below (see the comment
            # there) - not bound here anymore
        }
        for digit in '123456789':
            actionsDict[digit] = self.makeNumberJump(digit)

        # Mirrors IPTVFavouritesMainWidget's own ActionMap context list
        # and priority exactly: ["ColorActions", "WizardActions",
        # "ListboxActions", "NumberActions"] at priority -2 - WizardActions
        # alone already covers up/down/ok/back, so 'DirectionActions' is
        # pure duplication and left out. 'IPTVPlayerListActions' (needed
        # only for MENU) is deliberately NOT bundled into this same
        # ActionMap - see the separate 'menuActions' ActionMap below for
        # why.
        self['actions'] = ActionMap(
            ['OkCancelActions', 'WizardActions', 'ColorActions', 'NumberActions', 'ListboxActions'],
            actionsDict,
            -2
        )
        # 'info' -> keyHelp() bound here too, not in the main actionsDict
        # above - 'IPTVPlayerListActions' (this plugin's own keymap.xml)
        # is where KEY_INFO/KEY_EPG/KEY_HELP actually map to 'info' for
        # this whole app, and keeping it isolated to this already-
        # separate MENU ActionMap avoids reintroducing that context into
        # the main navigation ActionMap above.
        self['menuActions'] = ActionMap(['IPTVPlayerListActions'], {'menu': self.keyMenu, 'info': self.keyHelp}, 0)
        self.onLayoutFinish.append(self.onStart)

    def makeNumberJump(self, digit):
        return lambda: self.keyNumberJump(digit)

    def safeSetText(self, widget, value):
        try:
            widget.setText(guiSafeStr(value))
        except Exception:
            printExc()

    def buildDisplayList(self):
        # local import - see the matching comment on self['list'] in
        # __init__ for why (circular import via ihost.py)
        from Plugins.Extensions.IPTVPlayer.components.ihost import CDisplayListItem
        return [
            (CDisplayListItem(name=guiSafeStr(entry.displayText()), type=CDisplayListItem.TYPE_SEARCH_HISTORY),)
            for entry in self.entries
        ]

    def setEntriesList(self, displayList, selectedIndex=None):
        self['list'].setList(displayList)
        if selectedIndex is not None and displayList:
            selectedIndex = max(0, min(selectedIndex, len(displayList) - 1))
            self['list'].moveToIndex(selectedIndex)

    def loadEntriesFromFile(self):
        return parseHistoryFile(self.historyFile, self.reverseForDisplay)

    def removeDuplicates(self):
        cleanEntries = []
        knownEntries = set()
        removed = 0

        for entry in self.entries:
            entry.title = toUnicode(entry.title).strip()

            if not entry.title:
                removed += 1
                continue

            compareKey = (entry.title.lower(), (entry.searchtype or u'').lower())
            if compareKey in knownEntries:
                removed += 1
                continue

            knownEntries.add(compareKey)
            cleanEntries.append(entry)

        if removed:
            self.entries = cleanEntries
            self.dirty = True
            printDBG('SearchHistoryEditor removed duplicate/empty entries: %d' % removed)

        return removed

    def onStart(self):
        self.reloadList()

    def reloadList(self):
        try:
            self.entries = self.loadEntriesFromFile()
            self.setEntriesList(self.buildDisplayList())
            self.updateStatus()
        except Exception:
            printExc()
            self.entries = []
            self.setEntriesList([])
            self.safeSetText(self['status'], _(u'Loading failed.'))

    def updateStatus(self):
        # every user-facing string in this file goes through _() for
        # consistency, "A-Z"/"Z-A" included even though they're closer to
        # notation than words that need translating.
        modes = {0: _(u'unsorted'), 1: _(u'A-Z'), 2: _(u'Z-A'), 3: _(u'manual')}
        state = _(u'changed') if self.dirty else _(u'saved')
        reuseMode = _(u'to top') if self.reorderOnReuse else _(u'fixed')
        text = _(u'Entries: %d | Sort: %s | Status: %s | Jump target: %s') % (
            len(self.entries), modes.get(self.sortMode, u'?'), state, reuseMode
        )
        self.safeSetText(self['status'], text)

    def getCurrentIndex(self):
        try:
            # IPTVMainNavigatorList (IPTVListComponentBase) exposes
            # getCurrentIndex(), not MenuList's getSelectedIndex()
            idx = self['list'].getCurrentIndex()
            if idx is None:
                return None
            idx = int(idx)
            if idx < 0 or idx >= len(self.entries):
                return None
            return idx
        except Exception:
            printExc()
            return None

    def keyIgnoreListboxNav(self):
        pass

    def keyUp(self):
        try:
            if not self.entries:
                return
            instance = self['list'].instance
            if instance is None:
                return
            self.moveCursor(instance.moveUp)
        except Exception:
            printExc()

    def keyDown(self):
        try:
            if not self.entries:
                return
            instance = self['list'].instance
            if instance is None:
                return
            self.moveCursor(instance.moveDown)
        except Exception:
            printExc()

    def moveCursor(self, key):
        # Outside of carrying an item this just moves the cursor via the
        # native eListbox moveSelection().
        #
        # While carrying, this deliberately does NOT round-trip through
        # the native cursor (unlike iptvfavouriteswidgets.py's moveItem(),
        # which lets moveSelection() move the cursor and reads the new
        # position back via getCurrentIndex()) - the target index is
        # computed directly from the index already known (idx-1/idx+1,
        # wrapped - matches enableWrapAround=True), entries are swapped,
        # the list is rebuilt, and the cursor is force-set to that
        # computed index.
        instance = self['list'].instance
        if instance is None:
            return

        if self.manualReorderMode and self.manualReorderItemPicked:
            idx = self.getCurrentIndex()
            if idx is None:
                return
            count = len(self.entries)
            if key == instance.moveUp:
                newIdx = idx - 1 if idx > 0 else count - 1
            elif key == instance.moveDown:
                newIdx = idx + 1 if idx < count - 1 else 0
            else:
                instance.moveSelection(key)
                return
            if newIdx == idx:
                return
            self.entries[idx], self.entries[newIdx] = self.entries[newIdx], self.entries[idx]
            self.dirty = True
            self['list'].setList(self.buildDisplayList())
            self['list'].moveToIndex(newIdx)
            self.showCarryingStatus(newIdx)
        else:
            instance.moveSelection(key)

    def setCarryColor(self, active):
        try:
            instance = self['list'].instance
            if instance is None:
                return
            idx = self.getCurrentIndex()
            instance.setForegroundColorSelected(gRGB(0xFF0505) if active else gRGB(0xFFFFFF))
            # setForegroundColorSelected() alone doesn't force a repaint - the
            # new color only becomes visible on the next content rebuild, so
            # force one here rather than relying on the next unrelated list
            # rebuild (matches iptvfavouriteswidgets.py's _changeMode(),
            # which always calls displayList() right after the color change)
            self['list'].setList(self.buildDisplayList())
            # same moveToIndex()-after-setList() pin as moveCursor() above -
            # without it, picking an item up (keyManualPickOrDrop() calls
            # this first) could itself reset the cursor away from the row
            # just picked, before the first UP/DOWN carry-move even happens
            if idx is not None:
                self['list'].moveToIndex(idx)
        except Exception:
            printExc()

    def showCarryingStatus(self, idx):
        text = _(u'Carrying: %s | UP/DOWN=Move, OK=Drop') % self.entries[idx].title
        self.safeSetText(self['status'], text)

    def keyNumberJump(self, digit):
        if self.manualReorderMode:
            return
        if not self.entries:
            return
        if not config.plugins.iptvplayer.enableT9MainList.value:
            return

        letter = self.numberInput.getKey(int(digit))
        if not letter:
            return

        currentIdx = self.getCurrentIndex()

        try:
            idx = findT9JumpIndex(len(self.entries), currentIdx, letter, lambda i: toUnicode(self.entries[i].title))
            if idx >= 0:
                self['list'].moveToIndex(idx)
        except Exception:
            printExc()

    def keyResetSort(self):
        # "reset to saved order" (mode 0 - reloads self.entries from
        # disk, discarding any in-memory sort/reorder) - reachable from
        # the MENU popup as its own explicit entry, alongside A-Z/Z-A;
        # GREEN is a separate, dedicated manual-reordering toggle (see
        # keyToggleManualSort()).
        if self.manualReorderMode:
            return
        if self.dirty:
            self.session.openWithCallback(
                self.keyResetSortConfirmed,
                MessageBox,
                guiSafeStr(_(u'Reverting to unsorted order will discard unsaved changes. Continue?')),
                type=MessageBox.TYPE_YESNO,
                default=False
            )
            return
        self.applySortMode(0)

    def keyResetSortConfirmed(self, confirmed):
        if confirmed:
            self.applySortMode(0)

    def keyToggleManualSort(self):
        # GREEN is a direct toggle for manual reordering - a faster
        # shortcut for the same MENU -> "Enable/Disable reordering" entry
        # (still there too, unchanged).
        if self.manualReorderMode:
            self.keyStopManualSort()
        else:
            self.keyStartManualSort()

    def applySortMode(self, mode):
        try:
            currentIdx = self.getCurrentIndex()
            if currentIdx is None:
                currentIdx = 0

            removed = self.removeDuplicates()
            fixedJumpTarget = False

            if mode == 1:
                self.entries.sort(key=lambda entry: toUnicode(entry.title).lower())
                fixedJumpTarget = self.fixJumpTargetAfterSort()
            elif mode == 2:
                self.entries.sort(key=lambda entry: toUnicode(entry.title).lower(), reverse=True)
                fixedJumpTarget = self.fixJumpTargetAfterSort()
            else:
                mode = 0
                self.entries = self.loadEntriesFromFile()
                removed = self.removeDuplicates()

            self.sortMode = mode
            self.dirty = (mode != 0) or bool(removed)
            self.setEntriesList(self.buildDisplayList(), currentIdx)
            self.updateStatus()

            self.notifyAfterSort(removed, fixedJumpTarget)
        except Exception:
            printExc()

    def fixJumpTargetAfterSort(self):
        # sorting is a deliberate, explicit ordering - don't let a later
        # casual reuse (MRU bump-to-top) undo it silently
        if self.reorderOnReuse:
            self.reorderOnReuse = False
            setReorderOnReuseEnabled(self.historyFile, False)
            return True
        return False

    def notifyAfterSort(self, removed, fixedJumpTarget):
        parts = []
        if removed:
            parts.append(_(u'%d duplicate entries removed.') % removed)
        if fixedJumpTarget:
            parts.append(_(u'Jump target was fixed so the sort order is preserved.'))
        if parts:
            self.openInfoMessage(u' '.join(parts))

    def keyStartManualSort(self):
        printDBG('SearchHistoryEditor.keyStartManualSort ENTER')
        try:
            removed = self.removeDuplicates()
            fixedJumpTarget = self.fixJumpTargetAfterSort()
            self.manualReorderMode = True
            self.manualReorderItemPicked = False
            self.sortMode = 3
            self.setEntriesList(self.buildDisplayList(), self.getCurrentIndex())
            self.safeSetText(self['key_menu'], self.IDS_DISABLE_REORDERING)
            self.safeSetText(self['key_green'], self.IDS_DISABLE_REORDERING)
            self.updateStatus()

            self.notifyAfterSort(removed, fixedJumpTarget)
            printDBG('SearchHistoryEditor.keyStartManualSort OK manualReorderMode=%s' % self.manualReorderMode)
        except Exception:
            printExc()

    def keyStopManualSort(self):
        printDBG('SearchHistoryEditor.keyStopManualSort')
        self.manualReorderMode = False
        self.manualReorderItemPicked = False
        self.setCarryColor(False)
        self.safeSetText(self['key_menu'], self.IDS_MENU_OPTIONS)
        self.safeSetText(self['key_green'], self.IDS_ENABLE_REORDERING)
        self.updateStatus()

    def keyManualPickOrDrop(self):
        idx = self.getCurrentIndex()
        printDBG('SearchHistoryEditor.keyManualPickOrDrop idx=%s pickedBefore=%s' % (idx, self.manualReorderItemPicked))
        if idx is None:
            return
        self.manualReorderItemPicked = not self.manualReorderItemPicked
        self.setCarryColor(self.manualReorderItemPicked)
        if self.manualReorderItemPicked:
            self.showCarryingStatus(idx)
        else:
            self.dirty = True
            self.updateStatus()
        printDBG('SearchHistoryEditor.keyManualPickOrDrop pickedAfter=%s' % self.manualReorderItemPicked)

    def _getMenuOptionsHeight(self, numItems):
        # same tier-aware height+cap formula iptvfavouriteswidgets.py's own
        # _getGroupPickerHeight()/configbase.py's _getSelectionListHeight()
        # use - this popup's item count is fixed (4 or 5, depending on
        # reorderOnReuse), but the per-tier row height still needs scaling
        itemH, scale = skinchrome.tierRowHeight(35, 40, 55)
        height = int(numItems * itemH / scale) + 176
        return min(height, 660)

    def _getHelpHeight(self, numItems):
        # same formula iptvplayerwidget.py's own _getOptionsPickerHeight()
        # uses for its keyHelp() (itemH 44/62/83 - E2iVKOptionsList's real
        # per-tier row height, not _getMenuOptionsHeight()'s plain
        # IPTVChoiceBoxItem row height above) - capped at 660 like every
        # other picker height in this file, since this list has enough
        # rows (button hints + menu explanations) to otherwise overflow
        # a 720-tall HD screen; the list scrolls on its own past that.
        itemH, scale = skinchrome.tierRowHeight(44, 62, 83)
        height = int(numItems * itemH / scale) + 176
        return min(height, 660)

    def keyHelp(self):
        # same read-only icon+explanation list pattern as e2ivk.py's/
        # iptvplayerwidget.py's own keyHelp(), reusing their shared
        # GetKeyHelpItem()/_keyHelpLabels() (via GetKeyHelpItem, which
        # calls it internally) so button names aren't retranslated here.
        # Imports kept local - e2ivk.py imports iptvlist.py at module
        # level, which imports ihost.py, which imports THIS module - the
        # same circular import every other local import in this file
        # already works around.
        #
        # The MENU's own functions get explained in detail too, not just
        # what each physical button does - especially the jump-target
        # fix/unfix toggle, which isn't self-explanatory from its short
        # menu label alone. Those get their own rows below the button
        # hints, sharing the MENU icon instead of a per-button one, so
        # they read as a visually distinct group.
        from Plugins.Extensions.IPTVPlayer.components.iptvchoicebox import IPTVChoiceBoxWidget
        from Plugins.Extensions.IPTVPlayer.components.e2ivk import E2iVKOptionsList, GetKeyHelpItem, GetVKOptionItem
        iconBase = skinchrome.getIconBase()

        def icon(name):
            return LoadPixmap(iconBase + '/%s.png' % name)

        menuIcon = icon('menu')
        # E2iVKOptionsList.buildEntry() (e2ivk.py) renders each row as a
        # single TYPE_TEXT entry with no wrap flag at all, fixed one-line
        # itemHeight - true for every keyHelp() screen in the app, so
        # every description below is kept short enough to comfortably fit
        # one line at the popup's width. The jump-target explanation is
        # split across 4 short rows instead of one long paragraph for the
        # same reason - still covers what/unfixed/fixed/auto-fix in full,
        # just as separate sentences rather than a wall of text in a
        # widget that can't wrap it.
        options = [
            GetKeyHelpItem('ok', "edit the selected entry (same as BLUE) - or drop it while manually reordering", icon('ok')),
            GetKeyHelpItem('exit', "close the editor - or stop manual reordering if it's active", icon('exit')),
            GetKeyHelpItem('red', "delete the selected entry", icon('red')),
            GetKeyHelpItem('green', "enable / disable manual reordering", icon('green')),
            GetKeyHelpItem('yellow', "save all changes to disk", icon('yellow')),
            GetKeyHelpItem('blue', "edit the selected entry (same as OK)", icon('blue')),
            GetKeyHelpItem('menu', "open the options menu - see below", icon('menu')),
            GetKeyHelpItem('info', "show this help", icon('info')),
            GetKeyHelpItem('num', "jump to entries starting with that letter (if enabled in the settings)", icon('key_0-9')),
            GetKeyHelpItem('updown', "move the selection - or move it while manually reordering", icon('key_updown')),
            GetVKOptionItem(_(u"MENU → Add new entry: type a new search term to add to the history."), None, menuIcon),
            GetVKOptionItem(_(u"MENU → Sort A-Z / Sort Z-A: sort all entries alphabetically."), None, menuIcon),
            GetVKOptionItem(_(u"MENU → Reset to saved order: undo unsaved changes, reload from disk."), None, menuIcon),
            GetVKOptionItem(_(u"MENU → Enable/Disable reordering: same as GREEN (pick up/move/drop with OK, UP/DOWN)."), None, menuIcon),
            GetVKOptionItem(_(u"MENU → Fix/Unfix jump target: sets what happens when an entry is reused elsewhere."), None, menuIcon),
            GetVKOptionItem(_(u"  • Unfixed (default): the entry jumps back to the top of the list."), None, menuIcon),
            GetVKOptionItem(_(u"  • Fixed: order never changes - useful for browsing by letter jump (0-9)."), None, menuIcon),
            GetVKOptionItem(_(u"  • Sorting or reordering fixes this automatically, so your order stays."), None, menuIcon),
        ]
        height = self._getHelpHeight(len(options))
        self.session.open(IPTVChoiceBoxWidget, {'width': 1200, 'height': height, 'current_idx': 0, 'title': _(u'Help'), 'options': options, 'list_class': E2iVKOptionsList, 'selectable': False, 'chrome': True})

    def keyMenu(self):
        # chrome-skinned IPTVChoiceBoxWidget popup, same
        # IPTVChoiceBoxItem(name=, privateData=)/retArg.privateData shape
        # as iptvfavouriteswidgets.py's "Select favorite group" popup.
        #
        # Import kept local: a module-level import here would create a
        # real circular import - ihost.py imports SearchHistoryEditor at
        # module level (its "TYPE_SEARCH_HISTORY_EDITOR" menu action), and
        # ihost.py is itself imported by iptvlist.py before iptvlist.py
        # finishes defining IPTVRadioButtonList - so a module-level `from
        # iptvchoicebox import ...` here (iptvchoicebox.py itself imports
        # IPTVRadioButtonList from iptvlist.py) would try to read that
        # name off iptvlist while it's still mid-import.
        # iptvfavouriteswidgets.py imports iptvchoicebox at module level
        # fine since nothing in THAT early chain ever imports
        # iptvfavouriteswidgets.py - this file's own case is different
        # because ihost.py imports it directly.
        from Plugins.Extensions.IPTVPlayer.components.iptvchoicebox import IPTVChoiceBoxWidget, IPTVChoiceBoxItem, openChoiceBox
        printDBG('SearchHistoryEditor.keyMenu manualReorderMode=%s' % self.manualReorderMode)
        try:
            if self.manualReorderMode:
                self.keyStopManualSort()
                return

            options = [
                IPTVChoiceBoxItem(name=_(u'Add new entry'), privateData='ADD_NEW'),
                IPTVChoiceBoxItem(name=_(u'Sort A-Z'), privateData='SORT_AZ'),
                IPTVChoiceBoxItem(name=_(u'Sort Z-A'), privateData='SORT_ZA'),
                IPTVChoiceBoxItem(name=_(u'Reset to saved order'), privateData='RESET_SORT'),
                IPTVChoiceBoxItem(name=self.IDS_ENABLE_REORDERING, privateData='SORT_MANUAL'),
            ]
            if self.reorderOnReuse:
                options.append(IPTVChoiceBoxItem(name=_(u'Fix jump target'), privateData='TOGGLE_REORDER'))
            else:
                options.append(IPTVChoiceBoxItem(name=_(u'Unfix jump target'), privateData='TOGGLE_REORDER'))

            height = self._getMenuOptionsHeight(len(options))
            openChoiceBox(
                self.session,
                {'width': 600, 'height': height, 'current_idx': 0, 'title': _(u'Search history - options'), 'options': options, 'chrome': True},
                self.menuCallback
            )
        except Exception:
            printExc()

    def menuCallback(self, retArg):
        printDBG('SearchHistoryEditor.menuCallback retArg=%r' % (retArg,))
        if retArg is None:
            return
        action = retArg.privateData
        if action == 'ADD_NEW':
            self.keyAddNew()
        elif action == 'SORT_AZ':
            self.applySortMode(1)
        elif action == 'SORT_ZA':
            self.applySortMode(2)
        elif action == 'RESET_SORT':
            self.keyResetSort()
        elif action == 'SORT_MANUAL':
            self.keyStartManualSort()
        elif action == 'TOGGLE_REORDER':
            self.keyToggleReorderOnReuse()

    def keyAddNew(self):
        virtualKeyboard = GetVirtualKeyboard()
        self.session.openWithCallback(
            self.addNewCallback,
            virtualKeyboard,
            title=guiSafeStr(_(u'New entry')),
            text=''
        )

    def addNewCallback(self, newTitle=None):
        if newTitle is None:
            return

        newTitle = toUnicode(newTitle).strip()

        if not newTitle:
            self.openInfoMessage(_(u'Empty title is not allowed.'), MessageBox.TYPE_ERROR)
            return

        self.entries.insert(0, HistoryEntry(newTitle))
        removed = self.removeDuplicates()
        self.dirty = True
        self.setEntriesList(self.buildDisplayList(), 0)
        self.updateStatus()

        if removed:
            self.openInfoMessage(_(u'%d duplicate entry removed.') % removed)

    def keyToggleReorderOnReuse(self):
        try:
            self.reorderOnReuse = not self.reorderOnReuse
            setReorderOnReuseEnabled(self.historyFile, self.reorderOnReuse)
            self.updateStatus()

            if self.reorderOnReuse:
                msg = _(u'Reused entries move back to the top again.')
            else:
                msg = _(u'Order stays fixed - useful for T9 browsing.')
            self.openInfoMessage(msg)
        except Exception:
            printExc()

    def keyRename(self):
        printDBG('SearchHistoryEditor.keyRename manualReorderMode=%s' % self.manualReorderMode)
        if self.manualReorderMode:
            self.keyManualPickOrDrop()
            return

        idx = self.getCurrentIndex()
        if idx is None:
            self.openInfoMessage(_(u'Please select an entry.'))
            return

        entry = self.entries[idx]
        virtualKeyboard = GetVirtualKeyboard()
        self.session.openWithCallback(
            lambda newTitle=None: self.renameCallback(idx, newTitle),
            virtualKeyboard,
            title=guiSafeStr(_(u'Edit title')),
            text=guiSafeStr(entry.title)
        )

    def renameCallback(self, idx, newTitle):
        if newTitle is None:
            return

        newTitle = toUnicode(newTitle).strip()

        if not newTitle:
            self.openInfoMessage(_(u'Empty title is not allowed.'), MessageBox.TYPE_ERROR)
            return

        if 0 <= idx < len(self.entries):
            self.entries[idx].title = newTitle

            removed = self.removeDuplicates()
            self.dirty = True
            self.setEntriesList(self.buildDisplayList(), min(idx, max(0, len(self.entries) - 1)))
            self.updateStatus()

            if removed:
                self.openInfoMessage(_(u'%d duplicate entry removed.') % removed)

    def keyDelete(self):
        if self.manualReorderMode:
            return

        idx = self.getCurrentIndex()
        if idx is None:
            self.openInfoMessage(_(u'Please select an entry.'))
            return

        entry = self.entries[idx]
        message = toUnicode(_(u'Delete entry')) + u'\n' + toUnicode(entry.title)

        self.session.openWithCallback(
            lambda ret=None: self.deleteCallback(ret, idx),
            MessageBox,
            guiSafeStr(message),
            type=MessageBox.TYPE_YESNO
        )

    def deleteCallback(self, ret, idx):
        if not ret:
            return
        if 0 <= idx < len(self.entries):
            del self.entries[idx]
            self.dirty = True
            self.setEntriesList(self.buildDisplayList(), idx)
            self.updateStatus()

    def keySave(self):
        if self.manualReorderMode:
            return
        try:
            removed = self.removeDuplicates()
            sts = writeHistoryFile(self.historyFile, self.entries, self.reverseForWrite)

            if sts:
                self.dirty = False
                self.setEntriesList(self.buildDisplayList(), self.getCurrentIndex())
                self.updateStatus()

                if removed:
                    self.openInfoMessage(
                        _(u'Search history saved. %d duplicate entries removed.') % removed
                    )
                else:
                    self.openInfoMessage(_(u'Search history saved.'))
            else:
                self.openInfoMessage(_(u'Error while saving.'), MessageBox.TYPE_ERROR)
        except Exception:
            printExc()
            self.openInfoMessage(_(u'Error while saving.'), MessageBox.TYPE_ERROR)

    def openInfoMessage(self, text, msgType=MessageBox.TYPE_INFO, timeout=4):
        try:
            self.session.open(MessageBox, guiSafeStr(text), type=msgType, timeout=timeout)
        except Exception:
            printExc()

    def keyExit(self):
        if self.manualReorderMode:
            self.keyStopManualSort()
            return
        if self.dirty:
            self.session.openWithCallback(
                self.exitCallback,
                MessageBox,
                guiSafeStr(_(u'There are unsaved changes. Save now?')),
                type=MessageBox.TYPE_YESNO
            )
        else:
            self.close(None)

    def exitCallback(self, ret):
        if ret:
            self.keySave()
        self.close(None)
