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
from Screens.ChoiceBox import ChoiceBox
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.MenuList import MenuList

from Plugins.Extensions.IPTVPlayer.components.e2ivkselector import GetVirtualKeyboard
from Tools.NumericalTextInput import NumericalTextInput

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

    skin = """
    <screen name="SearchHistoryEditor" position="center,center" size="1200,700" title="Search History">
        <widget name="status" position="20,18" size="1160,30" font="Regular;24" halign="left" valign="center" transparent="1" />
        <widget name="list" position="20,58" size="1160,587" font="Regular;32" itemHeight="44" scrollbarMode="showOnDemand" transparent="1" />

        <eLabel position="20,662" size="18,18" backgroundColor="#00f23d21" />
        <widget name="key_red" position="45,655" size="210,30" font="Regular;24" halign="left" valign="center" transparent="1" />

        <eLabel position="252,662" size="18,18" backgroundColor="#0031a500" />
        <widget name="key_green" position="277,655" size="210,30" font="Regular;24" halign="left" valign="center" transparent="1" />

        <eLabel position="484,662" size="18,18" backgroundColor="#00e5b243" />
        <widget name="key_yellow" position="509,655" size="210,30" font="Regular;24" halign="left" valign="center" transparent="1" />

        <eLabel position="716,662" size="18,18" backgroundColor="#000064c7" />
        <widget name="key_blue" position="741,655" size="210,30" font="Regular;24" halign="left" valign="center" transparent="1" />

        <widget name="key_menu" position="948,655" size="235,30" font="Regular;24" halign="left" valign="center" transparent="1" />
    </screen>
    """

    def __init__(self, session, historyFile, reverseForDisplay=True, reverseForWrite=True):
        Screen.__init__(self, session)

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
        self['key_red'] = Label('')
        self['key_green'] = Label('')
        self['key_yellow'] = Label('')
        self['key_blue'] = Label('')
        self['key_menu'] = Label('')
        self['list'] = MenuList([], enableWrapAround=True)

        self.setTitle(guiSafeStr(_(u'Edit search history')))
        self.safeSetText(self['key_red'], _(u'Delete'))
        self.safeSetText(self['key_green'], _(u'Sort'))
        self.safeSetText(self['key_yellow'], _(u'Save'))
        self.safeSetText(self['key_blue'], _(u'Rename'))
        self.safeSetText(self['key_menu'], self.IDS_MENU_OPTIONS)

        actionsDict = {
            'ok': self.keyRename,
            'back': self.keyExit,
            'cancel': self.keyExit,
            'red': self.keyDelete,
            'green': self.keyToggleSort,
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
            'menu': self.keyMenu,
        }
        for digit in '123456789':
            actionsDict[digit] = self.makeNumberJump(digit)

        # priority 0, not -1: the underlying E2iPlayerWidget also binds
        # 'menu' in the 'IPTVPlayerListActions' context at priority -1 (see
        # iptvplayerwidget.py) - matching that priority here would make it
        # ambiguous which of the two receives the key while this screen is
        # open on top of it
        self['actions'] = ActionMap(
            ['OkCancelActions', 'WizardActions', 'DirectionActions', 'ColorActions', 'NumberActions', 'IPTVPlayerListActions', 'ListboxActions'],
            actionsDict,
            0
        )
        self.onLayoutFinish.append(self.onStart)

    def makeNumberJump(self, digit):
        return lambda: self.keyNumberJump(digit)

    def safeSetText(self, widget, value):
        try:
            widget.setText(guiSafeStr(value))
        except Exception:
            printExc()

    def buildDisplayList(self):
        return [guiSafeStr(entry.displayText()) for entry in self.entries]

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
        modes = {0: u'unsorted', 1: u'A-Z', 2: u'Z-A', 3: u'manual'}
        state = _(u'changed') if self.dirty else _(u'saved')
        reuseMode = _(u'to top') if self.reorderOnReuse else _(u'fixed')
        text = _(u'Entries: %d | Sort: %s | Status: %s | Jump target: %s') % (
            len(self.entries), modes.get(self.sortMode, u'?'), state, reuseMode
        )
        self.safeSetText(self['status'], text)

    def getCurrentIndex(self):
        try:
            idx = self['list'].getSelectedIndex()
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
        # matches iptvfavouriteswidgets.py's moveItem(): always drive
        # navigation through the native eListbox moveSelection() (not
        # MenuList.up()/down()) - proven working for manual reordering on
        # oATV8. Outside of carrying an item this just moves the cursor;
        # while carrying, entries are swapped based on where the native
        # cursor actually ends up (handles wraparound correctly).
        instance = self['list'].instance
        if instance is None:
            return

        if self.manualReorderMode and self.manualReorderItemPicked:
            idx = self.getCurrentIndex()
            instance.moveSelection(key)
            newIdx = self.getCurrentIndex()
            printDBG('SearchHistoryEditor.moveCursor carrying idx=%s newIdx=%s' % (idx, newIdx))
            if idx is None or newIdx is None or idx == newIdx:
                return
            self.entries[idx], self.entries[newIdx] = self.entries[newIdx], self.entries[idx]
            self.dirty = True
            self['list'].setList(self.buildDisplayList())
            self.showCarryingStatus(newIdx)
        else:
            instance.moveSelection(key)

    def setCarryColor(self, active):
        try:
            instance = self['list'].instance
            if instance is None:
                return
            instance.setForegroundColorSelected(gRGB(0xFF0505) if active else gRGB(0xFFFFFF))
            # setForegroundColorSelected() alone doesn't force a repaint - the
            # new color only becomes visible on the next content rebuild, so
            # force one here rather than relying on the next unrelated list
            # rebuild (matches iptvfavouriteswidgets.py's _changeMode(),
            # which always calls displayList() right after the color change)
            self['list'].setList(self.buildDisplayList())
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

    def keyToggleSort(self):
        if self.manualReorderMode:
            return
        nextMode = {0: 1, 1: 2, 2: 0, 3: 1}.get(self.sortMode, 1)
        if nextMode == 0 and self.dirty:
            self.session.openWithCallback(
                self.keyToggleSortConfirmed,
                MessageBox,
                guiSafeStr(_(u'Reverting to unsorted order will discard unsaved changes. Continue?')),
                type=MessageBox.TYPE_YESNO,
                default=False
            )
            return
        self.applySortMode(nextMode)

    def keyToggleSortConfirmed(self, confirmed):
        if confirmed:
            self.applySortMode(0)

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

    def keyMenu(self):
        printDBG('SearchHistoryEditor.keyMenu manualReorderMode=%s' % self.manualReorderMode)
        try:
            if self.manualReorderMode:
                self.keyStopManualSort()
                return

            options = [
                (guiSafeStr(_(u'Add new entry')), 'ADD_NEW'),
                (guiSafeStr(_(u'Sort A-Z')), 'SORT_AZ'),
                (guiSafeStr(_(u'Sort Z-A')), 'SORT_ZA'),
                (guiSafeStr(self.IDS_ENABLE_REORDERING), 'SORT_MANUAL'),
            ]
            if self.reorderOnReuse:
                options.append((guiSafeStr(_(u'Fix jump target')), 'TOGGLE_REORDER'))
            else:
                options.append((guiSafeStr(_(u'Unfix jump target')), 'TOGGLE_REORDER'))

            self.session.openWithCallback(self.menuCallback, ChoiceBox, title=guiSafeStr(_(u'Search history - options')), list=options)
        except Exception:
            printExc()

    def menuCallback(self, ret):
        printDBG('SearchHistoryEditor.menuCallback ret=%r' % (ret,))
        if not ret:
            return
        action = ret[1]
        if action == 'ADD_NEW':
            self.keyAddNew()
        elif action == 'SORT_AZ':
            self.applySortMode(1)
        elif action == 'SORT_ZA':
            self.applySortMode(2)
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
