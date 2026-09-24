# -*- coding: utf-8 -*-
# added: 25.07.2026  - YouTube user links module (ytlist.txt), extracted from hostyoutube.py - Kamikaze24
######################################################
# 02.08.2026 - HD Skin - WQHD Skin added by @stein17 #
######################################################
# 23.09.2026 - generic editor for the "[group] title;url;;icon;;;desc" link
# lists read by IPTVFileHost (ytlist.txt, urllist.txt/.stream/.user,
# xxxlist.txt). YouTubeUserLinksManager at the end adds the YouTube
# "Add to User Links" action.
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.components.e2ivkselector import GetVirtualKeyboard
from Plugins.Extensions.IPTVPlayer.components.cover import Cover
from Plugins.Extensions.IPTVPlayer.components import skinchrome
from Plugins.Extensions.IPTVPlayer.components.iptvchoicebox import IPTVChoiceBoxItem, openChoiceBox, openSortChoiceBox, sortOrderTitle

###################################################

###################################################
# FOREIGN import
###################################################
import re
import os
import codecs

###################################################

###################################################
# E2 GUI COMMPONENTS
###################################################
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.Sources.StaticText import StaticText
from Components.config import config
from Components.MenuList import MenuList
from enigma import gRGB

###################################################


try:
    text_type = unicode
    binary_type = str
    PY2 = True
except NameError:
    text_type = str
    binary_type = bytes
    PY2 = False


class LinkListEditorScreen(Screen):
    # One resolution="1280,720" auto-scaled skin block with the chrome
    # header/footer, like IPTVFavouritesMainWidget. The logo goes into the
    # header's "playerlogo" slot through Cover(), the clock follows
    # show_header_clock. Footer: RED delete, GREEN reorder rows, YELLOW move
    # to group, BLUE sort A-Z / Z-A.
    def __prepareSkin(self):
        iconBase = skinchrome.getIconBase()
        HEIGHT = 666
        clockPart = """<widget source="global.CurrentTime" render="Label" position="960,10" size="150,40" foregroundColor="white" backgroundColor="black" borderWidth="1" borderColor="black" transparent="1" zPosition="2" font="Regular;24" valign="center" halign="right">
                <convert type="ClockToText">Format:%H:%M</convert>
            </widget>
            <widget source="global.CurrentTime" render="Label" position="720,20" size="300,24" foregroundColor="white" backgroundColor="black" borderWidth="1" borderColor="black" transparent="1" zPosition="2" font="Regular;16" valign="center" halign="right">
                <convert type="ClockToText">Date</convert>
            </widget>""" if config.plugins.iptvplayer.show_header_clock.value else ""
        return """
        <screen name="LinkListEditorScreen" position="center,center" size="1120,%d" resolution="1280,720" title="Edit User Links" backgroundColor="#34111112" flags="wfNoBorder">
            %s
            <widget name="status" position="20,68" size="1080,30" font="Regular;24" halign="left" valign="center" foregroundColor="white" backgroundColor="black" borderWidth="1" borderColor="black" zPosition="1" transparent="1" />
            <widget name="list" position="20,120" size="1080,468" itemHeight="36" font="Regular;20" scrollbarMode="showOnDemand" scrollbarSliderBorderWidth="1" scrollbarForegroundColor="#1b5a91" scrollbarBorderColor="#00b6b6b6" enableWrapAround="1" foregroundColor="white" backgroundColor="black" foregroundColorSelected="white" backgroundColorSelected="#1b5a91" borderWidth="1" borderColor="black" transparent="1" />
            %s
            %s
        </screen>
        """ % (
            HEIGHT,
            skinchrome.build_header_auto(iconBase=iconBase, logoWidgetName="playerlogo"),
            clockPart,
            skinchrome.build_footer_auto(HEIGHT, iconBase=iconBase, keys=('red', 'green', 'yellow', 'blue')),
        )

    def __init__(self, session, manager):
        self.session = session
        self.skin = self.__prepareSkin()
        Screen.__init__(self, session)
        # explicit name so an external skin can target this screen
        self.skinName = skinchrome.forceInternalSkinName([manager.skinName])
        self.manager = manager
        self.entries = []
        self.reorderMode = False

        self["status"] = Label("")
        self["key_red"] = StaticText(self.forceUiText(_("Delete")))
        self["key_green"] = StaticText(self.forceUiText(_(u"Enable reordering")))
        self["key_yellow"] = StaticText(self.forceUiText(_("Move")))
        self["key_blue"] = StaticText(self.forceUiText(sortOrderTitle()))
        self["list"] = MenuList([])
        self["playerlogo"] = Cover()
        self["playerlogo"].hide()

        self.setTitle(self.forceUiText(manager.editorTitle))

        self.safeSetText(self["status"], "")

        self["actions"] = ActionMap(
            ["WizardActions", "DirectionActions", "ColorActions"],
            {
                "back": self.keyBack,
                "red": self.keyDelete,
                "green": self.keyReorder,
                "yellow": self.keyMove,
                "blue": self.keySort,
                "ok": self.keyOK,
                "up": self.keyUp,
                "down": self.keyDown,
            },
            -1
        )

        self.onLayoutFinish.append(self.onStart)

    def forceUnicodeText(self, value):
        return self.manager.toUnicode(value)

    def forceUiText(self, value):
        return self.manager.guiSafeStr(value)

    def safeSetText(self, widget, value):
        try:
            widget.setText(self.forceUiText(value))
        except Exception:
            printExc()

    def cleanDisplayText(self, value, emptyValue=u" "):
        text = self.forceUnicodeText(value)
        text = text.replace(u"\n", u" ").replace(u"\r", u" ").strip()
        if text == u"":
            return emptyValue
        return text

    def formatDisplayLine(self, item):
        try:
            if item.get("kind", "link") != "link":
                return self.cleanDisplayText(item.get("raw_line", ""))

            rawLine = self.cleanDisplayText(item.get("raw_line", ""), u"")
            if rawLine:
                return rawLine

            group = self.cleanDisplayText(item.get("group", ""), u"")
            title = self.cleanDisplayText(item.get("title", ""), u"")
            url = self.cleanDisplayText(item.get("url", ""), u"")

            if group:
                return self.cleanDisplayText(u"[%s] %s;%s" % (group, title, url))
            return self.cleanDisplayText(u"%s;%s" % (title, url))
        except Exception:
            printExc()
        return u" "

    def openInfoMessage(self, text, msgType=MessageBox.TYPE_INFO, timeout=5):
        self.session.open(
            MessageBox,
            self.forceUiText(text),
            type=msgType,
            timeout=timeout
        )

    def onStart(self):
        logoPath = GetIconDir('logos/' + self.manager.logoName)
        if self["playerlogo"].checkDecodeNeeded(logoPath):
            self["playerlogo"].decodeCover(logoPath, self.updateLogoCover, "playerlogo")
        else:
            self["playerlogo"].show()
        self.reloadList()

    def updateLogoCover(self, retDict):
        # single static asset, always the same file - same reasoning as
        # IPTVFavouritesMainWidget's own updateLogoCover()
        if retDict and retDict["Pixmap"] is not None:
            self["playerlogo"].updatePixmap(retDict["Pixmap"], retDict["FileName"])
            self["playerlogo"].show()

    def reloadList(self, selectIdx=None):
        try:
            self.entries = self.manager.read()
            self.showEntries(selectIdx)
        except Exception:
            printExc()
            self.entries = []
            self["list"].setList([])
            self.safeSetText(self["status"], _("Loading failed."))

    def showEntries(self, selectIdx=None):
        displayList = []

        for item in self.entries:
            if not isinstance(item, dict):
                continue
            displayList.append(self.forceUiText(self.formatDisplayLine(item)))

        self["list"].setList(displayList)
        if selectIdx is not None and 0 <= selectIdx < len(displayList):
            self["list"].moveToIndex(selectIdx)

        if self.reorderMode:
            self.safeSetText(self["status"], _("Reordering: UP/DOWN moves the row, OK saves, EXIT cancels."))
        else:
            numLinks = len([item for item in self.entries if isinstance(item, dict) and item.get("kind", "link") == "link"])
            self.safeSetText(self["status"], _("User-Links: %d") % numLinks)

    def currentIndex(self):
        try:
            idx = self["list"].getSelectedIndex()
            if idx is not None:
                return int(idx)
        except Exception:
            printExc()
        return None

    def keyReorder(self):
        if self.reorderMode:
            self.stopReorder(True)
            return

        if len(self.entries) < 2:
            return

        self.reorderMode = True
        self.safeSetText(self["key_green"], _(u"Disable reordering"))
        self.setCarryColor(True)
        self.showEntries(self.currentIndex())

    def setCarryColor(self, carrying):
        # red text on the carried row, like the favourites manager's reordering
        try:
            self["list"].instance.setForegroundColorSelected(gRGB(0xFF0505 if carrying else 0xFFFFFF))
        except Exception:
            printExc()

    def stopReorder(self, save):
        idx = self.currentIndex()
        self.reorderMode = False
        self.safeSetText(self["key_green"], _(u"Enable reordering"))
        self.setCarryColor(False)

        if save and not self.manager.write(self.entries):
            self.openInfoMessage(_("The user link could not be updated."), MessageBox.TYPE_ERROR)

        self.reloadList(idx)

    def moveRow(self, delta):
        try:
            idx = self.currentIndex()
            if idx is None:
                return

            newIdx = idx + delta
            if newIdx < 0 or newIdx >= len(self.entries):
                return

            self.entries[idx], self.entries[newIdx] = self.entries[newIdx], self.entries[idx]
            self.showEntries(newIdx)
        except Exception:
            printExc()

    def keySort(self):
        if self.reorderMode:
            return

        openSortChoiceBox(self.session, self.onSortOrderSelected)

    def onSortOrderSelected(self, reverse):
        if reverse is None:
            return

        self.session.openWithCallback(
            lambda ret: self.sortConfirmed(ret, reverse),
            MessageBox,
            self.forceUiText(_("Sort the links now? The order of the lines in the file will change.")),
            type=MessageBox.TYPE_YESNO
        )

    def sortConfirmed(self, ret, reverse):
        if not ret:
            return

        sts, msg = self.manager.sortLinks(reverse)
        self.actionFinished(sts, msg)

    def getCurrentItem(self):
        idx = self.currentIndex()
        if idx is not None and 0 <= idx < len(self.entries) and isinstance(self.entries[idx], dict):
            return self.entries[idx]
        return None

    def keyBack(self):
        if self.reorderMode:
            self.stopReorder(False)
            return
        self.close()

    # the list wraps around by itself (enableWrapAround="1" in the skin)
    def keyUp(self):
        if self.reorderMode:
            self.moveRow(-1)
        else:
            self["list"].up()

    def keyDown(self):
        if self.reorderMode:
            self.moveRow(1)
        else:
            self["list"].down()

    def keyDelete(self):
        if self.reorderMode:
            return

        item = self.getCurrentItem()
        if not item:
            self.openInfoMessage(_("Select option"))
            return

        try:
            text = self.cleanDisplayText(_("Remove item"), u"Remove item") + u"\n" + self.formatDisplayLine(item)
        except Exception:
            printExc()
            text = _("Remove item")

        self.session.openWithCallback(
            self.deleteConfirmed,
            MessageBox,
            self.forceUiText(text),
            type=MessageBox.TYPE_YESNO
        )

    def deleteConfirmed(self, ret):
        if not ret:
            return

        item = self.getCurrentItem()
        if not item:
            return

        sts, msg = self.manager.delete(item)
        self.openInfoMessage(msg)
        if sts:
            self.reloadList()

    def keyMove(self):
        if self.reorderMode:
            return

        item = self.getCurrentItem()
        if not item:
            self.openInfoMessage(_("Select option"))
            return

        if item.get("kind", "link") != "link":
            self.openInfoMessage(_("Only links can be moved to a group."))
            return

        try:
            self.manager.selectTargetGroup(self.session, item, self.actionFinished)
        except Exception:
            printExc()
            self.openInfoMessage(_("Move failed."))

    def actionFinished(self, sts, msg):
        self.openInfoMessage(msg)
        if sts:
            self.reloadList()

    def keyOK(self):
        if self.reorderMode:
            self.stopReorder(True)
            return

        item = self.getCurrentItem()
        if not item:
            self.openInfoMessage(_("Select option"))
            return

        try:
            self.manager.editRaw(self.session, item, self.actionFinished)
        except Exception:
            printExc()
            self.openInfoMessage(_("Edit failed."))


class LinkListManager(object):
    def __init__(self, listPathProvider, editorTitle=None, logoName="iptvlogo.png", skinName="LinkListEditorScreen"):
        self.listPathProvider = listPathProvider
        self.editorTitle = editorTitle or _("Edit User Links")
        self.logoName = logoName
        self.skinName = skinName

    def getUserLinksPath(self):
        return self.listPathProvider()

    def ensureUserLinksDir(self):
        try:
            path = self.getUserLinksPath()
            directory = os.path.dirname(path)
            if directory and not os.path.isdir(directory):
                os.makedirs(directory)
        except Exception:
            printExc()

    def toUnicode(self, value):
        try:
            if value is None:
                return u""
            if isinstance(value, text_type):
                return value
            if isinstance(value, binary_type):
                return value.decode("utf-8", "ignore")
            return text_type(value)
        except Exception:
            try:
                if PY2:
                    return text_type(str(value), "utf-8", "ignore")
                return text_type(value)
            except Exception:
                printExc()
        return u""

    def guiSafeStr(self, value):
        try:
            if value is None:
                return ""
            text = self.toUnicode(value)
            if PY2:
                return text.encode("utf-8")
            return text
        except Exception:
            try:
                if PY2 and isinstance(value, text_type):
                    return value.encode("utf-8")
                return str(value)
            except Exception:
                printExc()
        return ""

    def cleanValue(self, value):
        value = self.toUnicode(value)
        value = value.replace(u"\r", u" ").replace(u"\n", u" ").replace(u";", u" ").strip()
        return value

    def cleanGroup(self, value):
        value = self.cleanValue(value)
        value = value.replace(u"[", u"").replace(u"]", u"").strip()
        return value

    def normalizeUrl(self, value):
        try:
            value = self.toUnicode(value).strip()
            value = value.replace(u" ", u"")
            return value
        except Exception:
            printExc()
        return u""

    def sameItem(self, item1, item2):
        try:
            if not isinstance(item1, dict) or not isinstance(item2, dict):
                return False
            return (
                self.cleanGroup(item1.get("group", "")) == self.cleanGroup(item2.get("group", "")) and
                self.cleanValue(item1.get("title", "")) == self.cleanValue(item2.get("title", "")) and
                self.normalizeUrl(item1.get("url", "")) == self.normalizeUrl(item2.get("url", ""))
            )
        except Exception:
            printExc()
        return False

    def parseLine(self, line):
        # Same rules as IPTVFileHost.addFile(), which is what the host list
        # is built from: "[group] title;url" plus the optional
        # ";;icon;;;description" tail, which is kept verbatim in "extra".
        try:
            rawLine = self.toUnicode(line).strip()
            if not rawLine or rawLine.startswith(u"#"):
                return None

            idx = rawLine.find(u";")
            if idx < 0:
                return None

            fullTitle = rawLine[:idx].strip()
            rest = rawLine[idx + 1:]
            extra = u""
            idxExtra = rest.find(u";;")
            if idxExtra >= 0:
                extra = rest[idxExtra:].rstrip()
                rest = rest[:idxExtra]

            group = u""
            title = fullTitle
            if 2 < len(fullTitle) and fullTitle[0] == u"[":
                idxGroup = fullTitle.find(u"]")
                if idxGroup >= 0:
                    group = self.cleanGroup(fullTitle[1:idxGroup])
                    title = fullTitle[idxGroup + 1:]

            title = self.cleanValue(title)
            url = self.normalizeUrl(rest)

            if not title or not url:
                return None

            return {
                "kind": u"link",
                "group": group,
                "title": title,
                "url": url,
                "extra": extra,
                "raw_line": rawLine,
            }
        except Exception:
            printExc()
        return None

    def parseRow(self, line):
        # Every line of the file is a row of the editor: a link, or "text"
        # (comment, empty line or anything that is not a link), so that
        # saving never drops a line.
        item = self.parseLine(line)
        if item is not None:
            return item
        return {"kind": u"text", "raw_line": self.toUnicode(line).strip()}

    def isLink(self, item):
        return isinstance(item, dict) and item.get("kind", u"link") == u"link"

    def sameRow(self, item1, item2):
        if not isinstance(item1, dict) or not isinstance(item2, dict):
            return False
        if self.isLink(item1) != self.isLink(item2):
            return False
        if self.isLink(item1):
            return self.sameItem(item1, item2)
        return item1.get("raw_line", u"") == item2.get("raw_line", u"")

    def locate(self, rows, item):
        try:
            rowId = item.get("id")
            if isinstance(rowId, int) and 0 <= rowId < len(rows) and self.sameRow(rows[rowId], item):
                return rowId
            for idx in range(len(rows)):
                if self.sameRow(rows[idx], item):
                    return idx
        except Exception:
            printExc()
        return -1

    def buildLine(self, group, title, url, extra=u""):
        group = self.cleanGroup(group)
        title = self.cleanValue(title)
        url = self.normalizeUrl(url)

        if group:
            line = u"[%s] %s;%s" % (group, title, url)
        else:
            line = u"%s;%s" % (title, url)
        return line + self.toUnicode(extra)

    def read(self):
        rows = []
        path = self.getUserLinksPath()

        try:
            if not os.path.isfile(path):
                return rows

            with open(path, "rb") as f:
                for line in f:
                    # a line that is not UTF-8 (old latin-1 lists) is read as
                    # latin-1, so saving converts it instead of writing U+FFFD
                    try:
                        line = line.decode("utf-8")
                    except UnicodeDecodeError:
                        line = line.decode("latin-1")
                    row = self.parseRow(line)
                    row["id"] = len(rows)
                    rows.append(row)
        except Exception:
            printExc()

        return rows

    def write(self, rows):
        try:
            self.ensureUserLinksDir()
            path = self.getUserLinksPath()
            lines = []

            for item in rows:
                if not isinstance(item, dict):
                    continue
                if not self.isLink(item) or item.get("raw_line"):
                    # rows read from the file keep their line as it was;
                    # only new or edited links (no raw_line) are rebuilt
                    lines.append(self.toUnicode(item.get("raw_line", u"")))
                else:
                    lines.append(self.buildLine(
                        item.get("group", ""),
                        item.get("title", ""),
                        item.get("url", ""),
                        item.get("extra", u"")
                    ))

            # write a temp file and rename it, so a crash can't leave a half-written list
            tmpPath = path + ".tmp"
            with codecs.open(tmpPath, "w", "utf-8") as f:
                for line in lines:
                    f.write(line + u"\n")
            os.rename(tmpPath, path)

            return True
        except Exception:
            printExc()
            return False

    def getGroups(self):
        groups = []
        try:
            for item in self.read():
                group = self.cleanGroup(item.get("group", ""))
                if group and group not in groups:
                    groups.append(group)
            groups.sort()
        except Exception:
            printExc()
        return groups

    def existsUrlAnywhere(self, url, skipItem=None):
        try:
            url = self.normalizeUrl(url)

            for item in self.read():
                if not self.isLink(item):
                    continue
                if skipItem is not None and self.sameItem(item, skipItem):
                    continue
                if self.normalizeUrl(item.get("url", "")) == url:
                    return True
        except Exception:
            printExc()
        return False

    def add(self, group, title, url):
        try:
            group = self.cleanGroup(group)
            title = self.cleanValue(title)
            url = self.normalizeUrl(url)

            if not title or not url:
                return False, _("Invalid name.")

            if self.existsUrlAnywhere(url):
                return False, _("The channel already exists in User Links.")

            entries = self.read()
            newItem = {
                "kind": u"link",
                "group": group,
                "title": title,
                "url": url,
                "extra": u"",
            }

            insertIdx = len(entries)

            if group:
                lastGroupIdx = -1
                for idx in range(len(entries)):
                    if not self.isLink(entries[idx]):
                        continue
                    itemGroup = self.cleanGroup(entries[idx].get("group", ""))
                    if itemGroup == group:
                        lastGroupIdx = idx
                if lastGroupIdx >= 0:
                    insertIdx = lastGroupIdx + 1

            entries.insert(insertIdx, newItem)

            if self.write(entries):
                return True, _("User link added.")
        except Exception:
            printExc()

        return False, _("Could not add the user link.")

    def update(self, oldItem, newGroup, newTitle, newUrl, newExtra=None):
        try:
            entries = self.read()

            newGroup = self.cleanGroup(newGroup)
            newTitle = self.cleanValue(newTitle)
            newUrl = self.normalizeUrl(newUrl)

            if not newTitle or not newUrl:
                return False, _("Invalid name.")

            if self.existsUrlAnywhere(newUrl, skipItem=oldItem):
                return False, _("The element already exists in User Links.")

            idx = self.locate(entries, oldItem)
            if idx < 0:
                return False, _("File Not Found.")

            if newExtra is None:
                # keep the ";;icon;;;description" tail when only the group changes
                newExtra = entries[idx].get("extra", u"") if self.isLink(entries[idx]) else u""

            entries[idx] = {
                "kind": u"link",
                "group": newGroup,
                "title": newTitle,
                "url": newUrl,
                "extra": self.toUnicode(newExtra),
            }

            if self.write(entries):
                return True, _("User link updated.")
        except Exception:
            printExc()

        return False, _("The user link could not be updated.")

    def updateText(self, oldItem, newText):
        try:
            entries = self.read()

            idx = self.locate(entries, oldItem)
            if idx < 0:
                return False, _("File Not Found.")

            text = re.sub(r"[\r\n]+", u" ", self.toUnicode(newText)).strip()
            entries[idx] = {"kind": u"text", "raw_line": text}

            if self.write(entries):
                return True, _("User link updated.")
        except Exception:
            printExc()

        return False, _("The user link could not be updated.")

    def delete(self, itemToDelete):
        try:
            entries = self.read()

            idx = self.locate(entries, itemToDelete)
            if idx < 0:
                return False, _("File Not Found.")

            del entries[idx]

            if self.write(entries):
                return True, _("User link deleted.")
        except Exception:
            printExc()

        return False, _("The user link could not be deleted.")

    def sortLinks(self, reverse=False):
        # Sorts the links by group, then title. Comment / empty rows stay on
        # their own line: only the link rows swap places among themselves.
        # Links without a group go last, like in the alphabetical host list.
        try:
            rows = self.read()
            slots = [idx for idx in range(len(rows)) if self.isLink(rows[idx])]

            def sortKey(item):
                group = self.cleanGroup(item.get("group", "")).lower()
                return (group, self.cleanValue(item.get("title", "")).lower(), self.normalizeUrl(item.get("url", "")).lower())

            links = [rows[idx] for idx in slots]
            # sorted apart, so the ungrouped links stay last for Z-A too
            grouped = sorted([item for item in links if self.cleanGroup(item.get("group", ""))], key=sortKey, reverse=bool(reverse))
            ungrouped = sorted([item for item in links if not self.cleanGroup(item.get("group", ""))], key=sortKey, reverse=bool(reverse))
            for slot, link in zip(slots, grouped + ungrouped):
                rows[slot] = link

            if self.write(rows):
                return True, _("User links sorted.")
        except Exception:
            printExc()

        return False, _("Could not sort the user links.")

    def askNewGroup(self, session, callback):
        session.openWithCallback(
            lambda text=None: self.onNewGroupEntered(text, callback),
            GetVirtualKeyboard(),
            title=self.guiSafeStr(_("Enter name")),
            text=""
        )

    def onNewGroupEntered(self, text, callback):
        group = self.cleanGroup(text or "")
        if not group:
            callback("", False)
            return
        callback(group, True)

    def selectTargetGroupAction(self, session, groups, callback):
        # chrome-skinned IPTVChoiceBoxWidget, same pattern as
        # iptvfavouriteswidgets.py's own "Select favorite group" popup, so
        # this gets the app's header/footer instead of looking like a
        # bare OpenATV system dialog. "new"/"" sentinel values are
        # IPTVChoiceBoxItem's `privateData`.
        options = [
            IPTVChoiceBoxItem(name=self.guiSafeStr(_("Add new group")), privateData="new"),
            IPTVChoiceBoxItem(name=self.guiSafeStr(_("--All--")), privateData=""),
        ]

        for group in groups:
            if group:
                options.append(IPTVChoiceBoxItem(name=self.guiSafeStr(group), privateData=self.guiSafeStr(group)))

        height = skinchrome.choiceBoxHeight(len(options))
        openChoiceBox(
            session,
            {'width': 600, 'height': height, 'current_idx': 0, 'title': self.guiSafeStr(_("Select group")), 'options': options, 'chrome': True},
            lambda ret=None: self.onTargetGroupActionSelected(session, ret, callback)
        )

    def onTargetGroupActionSelected(self, session, ret, callback):
        if ret is None:
            callback("", False)
            return

        value = ret.privateData
        if value == "new":
            self.askNewGroup(session, callback)
        else:
            callback(value, True)

    def selectTargetGroup(self, session, item, callback):
        groups = self.getGroups()
        self.selectTargetGroupAction(
            session,
            groups,
            lambda group, accepted: self.onMoveTargetGroupSelected(item, group, accepted, callback)
        )

    def onMoveTargetGroupSelected(self, item, group, accepted, callback):
        if not accepted:
            callback(False, _("Aborted"))
            return

        sts, msg = self.update(
            item,
            group,
            item.get("title", ""),
            item.get("url", "")
        )
        callback(sts, msg)

    def getRawLine(self, item):
        try:
            rawLine = self.toUnicode(item.get("raw_line", "")).strip()
            if rawLine:
                return rawLine
            return self.buildLine(
                item.get("group", ""),
                item.get("title", ""),
                item.get("url", "")
            )
        except Exception:
            printExc()
        return u""

    def editRaw(self, session, item, callback):
        try:
            rawLine = self.getRawLine(item)
            session.openWithCallback(
                lambda text=None: self.onEditRawEntered(item, text, callback),
                GetVirtualKeyboard(),
                title=self.guiSafeStr(_("Edit User Links")),
                text=self.guiSafeStr(rawLine)
            )
        except Exception:
            printExc()
            callback(False, _("Unknown error."))

    def onEditRawEntered(self, oldItem, text, callback):
        try:
            if text is None:
                callback(False, _("Operation aborted!"))
                return

            newRaw = self.toUnicode(text).strip()
            if not newRaw:
                callback(False, _("Invalid name."))
                return

            parsed = self.parseLine(newRaw)
            if parsed is None:
                if newRaw.startswith(u"#"):
                    # a comment line, or a link that gets commented out
                    sts, msg = self.updateText(oldItem, newRaw)
                    callback(sts, msg)
                    return
                callback(False, _("Wrong uri."))
                return

            sts, msg = self.update(
                oldItem,
                parsed.get("group", ""),
                parsed.get("title", ""),
                parsed.get("url", ""),
                parsed.get("extra", u"")
            )
            callback(sts, msg)
        except Exception:
            printExc()
            callback(False, _("The user link could not be updated."))

    def openEditor(self, session):
        session.open(LinkListEditorScreen, self)


def openLinkListFileEditor(session, filePath, logoName, skinName="LinkListEditorScreen"):
    # editor for one list file, titled with the file name so the user sees which one it is
    manager = LinkListManager(lambda: filePath, u"%s - %s" % (_("Edit User Links"), os.path.basename(filePath)), logoName, skinName)
    manager.openEditor(session)


class YouTubeUserLinksManager(LinkListManager):
    def __init__(self, listPathProvider, categoryResolver, channelNameResolver):
        LinkListManager.__init__(self, listPathProvider, _("YouTube User Links Editor"), "youtubelogo.png", "YouTubeUserLinksEditorScreen")
        self.categoryResolver = categoryResolver
        self.channelNameResolver = channelNameResolver

    def isChannelItem(self, cItem):
        try:
            if not cItem:
                return False
            if cItem.get("category", "") == "channel":
                return True

            url = cItem.get("url", "")
            if url and self.categoryResolver(str(url)) == "channel":
                return True
        except Exception:
            printExc()
        return False

    def getCandidateFromItem(self, cItem):
        if not self.isChannelItem(cItem):
            return None

        try:
            title = self.channelNameResolver(cItem)
            if not title:
                title = cItem.get("title", "")

            title = self.cleanValue(title)
            url = self.normalizeUrl(cItem.get("url", ""))

            if not title or not url:
                return None

            return {
                "group": "",
                "title": title,
                "url": url,
            }
        except Exception:
            printExc()
        return None

    def openAddCurrentItem(self, session, cItem=None, callback=None):
        if callback is None:
            def callback(sts, msg):
                session.open(
                    MessageBox,
                    msg,
                    type=MessageBox.TYPE_INFO if sts else MessageBox.TYPE_ERROR,
                    timeout=5
                )

        item = self.getCandidateFromItem(cItem)
        if item is None:
            callback(False, _("Current item is not a channel."))
            return

        groups = self.getGroups()
        self.selectTargetGroupAction(
            session,
            groups,
            lambda group, accepted: self.onAddCurrentItemTargetGroupSelected(item, group, accepted, callback)
        )

    def onAddCurrentItemTargetGroupSelected(self, item, group, accepted, callback):
        if not accepted:
            callback(False, _("Aborted"))
            return

        sts, msg = self.add(
            group,
            item.get("title", ""),
            item.get("url", "")
        )
        callback(sts, msg)
