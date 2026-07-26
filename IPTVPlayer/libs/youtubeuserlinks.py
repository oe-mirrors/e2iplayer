# -*- coding: utf-8 -*-
# added: 25.07.2026  - Separate YouTube user links module for ytlist.txt handling, including add-to-user-links action,
# folder selection or new folder creation, raw editor and user links editor integration, extracted from hostyoutube.py
# to keep hostyoutube.py cleaner - Kamikaze24
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc

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
from Screens.ChoiceBox import ChoiceBox
from Screens.VirtualKeyBoard import VirtualKeyBoard
from Components.MenuList import MenuList

###################################################


try:
    text_type = unicode
    binary_type = str
    string_types = (basestring,)
    PY2 = True
except NameError:
    text_type = str
    binary_type = bytes
    string_types = (str, bytes)
    PY2 = False


class YouTubeUserLinksEditorScreen(Screen):
    skin = """
    <screen name="YouTubeUserLinksEditorScreen" position="center,center" size="1120,650" title="YouTube User Links Editor">
        <widget name="status" position="20,18" size="1080,30" font="Regular;24" halign="left" valign="center" transparent="1" />
        <widget name="list" position="20,58" size="1080,502" itemHeight="36" scrollbarMode="showOnDemand" transparent="1" />
        <widget name="hint" position="20,570" size="1080,28" font="Regular;22" halign="center" valign="center" foregroundColor="#00b0b0b0" transparent="1" />

        <eLabel position="20,612" size="18,18" backgroundColor="#00f23d21" />
        <widget name="key_red" position="45,605" size="220,30" font="Regular;24" halign="left" valign="center" transparent="1" />

        <eLabel position="295,612" size="18,18" backgroundColor="#0031a500" />
        <widget name="key_green" position="320,605" size="220,30" font="Regular;24" halign="left" valign="center" transparent="1" />

        <eLabel position="570,612" size="18,18" backgroundColor="#00e5b243" />
        <widget name="key_yellow" position="595,605" size="220,30" font="Regular;24" halign="left" valign="center" transparent="1" />

        <eLabel position="845,612" size="18,18" backgroundColor="#000064c7" />
        <widget name="key_blue" position="870,605" size="220,30" font="Regular;24" halign="left" valign="center" transparent="1" />
    </screen>
    """

    def __init__(self, session, manager):
        Screen.__init__(self, session)
        self.manager = manager
        self.entries = []

        self["status"] = Label("")
        self["hint"] = Label("")
        self["key_red"] = Label("")
        self["key_green"] = Label("")
        self["key_yellow"] = Label("")
        self["key_blue"] = Label("")
        self["list"] = MenuList([])

        self.setTitle(self.forceUiText(_("YouTube User Links Editor")))

        self.safeSetText(self["status"], "")
        self.safeSetText(self["hint"], _("OK=Edit RED=%s YELLOW=%s EXIT=Exit") % (_("Delete"), _("Move")))
        self.safeSetText(self["key_red"], _("Delete"))
        self.safeSetText(self["key_green"], "")
        self.safeSetText(self["key_yellow"], _("Move"))
        self.safeSetText(self["key_blue"], "")

        self["actions"] = ActionMap(
            ["WizardActions", "DirectionActions", "ColorActions"],
            {
                "back": self.keyBack,
                "red": self.keyDelete,
                "yellow": self.keyMove,
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
        self.reloadList()

    def reloadList(self):
        try:
            self.entries = self.manager.read()
            displayList = []

            for item in self.entries:
                if not isinstance(item, dict):
                    continue
                displayList.append(self.forceUiText(self.formatDisplayLine(item)))

            self["list"].setList(displayList)
            self.safeSetText(self["status"], _("User-Links: %d") % len(displayList))
        except Exception:
            printExc()
            self.entries = []
            self["list"].setList([])
            self.safeSetText(self["status"], _("Loading failed."))

    def getCurrentItem(self):
        try:
            idx = self["list"].getSelectedIndex()
            if idx is None:
                return None
            idx = int(idx)
            if idx < 0 or idx >= len(self.entries):
                return None
            item = self.entries[idx]
            if isinstance(item, dict):
                return item
        except Exception:
            printExc()
        return None

    def keyBack(self):
        self.close()

    def keyUp(self):
        try:
            if len(self.entries) <= 0:
                return

            idx = self["list"].getSelectedIndex()
            if idx is None:
                idx = 0
            idx = int(idx)

            if idx <= 0:
                self["list"].moveToIndex(len(self.entries) - 1)
            else:
                self["list"].up()
        except Exception:
            printExc()

    def keyDown(self):
        try:
            if len(self.entries) <= 0:
                return

            idx = self["list"].getSelectedIndex()
            if idx is None:
                idx = 0
            idx = int(idx)

            if idx >= (len(self.entries) - 1):
                self["list"].moveToIndex(0)
            else:
                self["list"].down()
        except Exception:
            printExc()

    def keyDelete(self):
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
        item = self.getCurrentItem()
        if not item:
            self.openInfoMessage(_("Select option"))
            return

        try:
            self.manager.selectTargetGroup(self.session, item, self.moveFinished)
        except Exception:
            printExc()
            self.openInfoMessage(_("Move failed."))

    def moveFinished(self, sts, msg):
        self.openInfoMessage(msg)
        if sts:
            self.reloadList()

    def keyOK(self):
        item = self.getCurrentItem()
        if not item:
            self.openInfoMessage(_("Select option"))
            return

        try:
            self.manager.editRaw(self.session, item, self.editFinished)
        except Exception:
            printExc()
            self.openInfoMessage(_("Edit failed."))

    def editFinished(self, sts, msg):
        self.openInfoMessage(msg)
        if sts:
            self.reloadList()


class YouTubeUserLinksManager(object):
    def __init__(self, listPathProvider, categoryResolver, channelNameResolver):
        self.listPathProvider = listPathProvider
        self.categoryResolver = categoryResolver
        self.channelNameResolver = channelNameResolver

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
        try:
            rawLine = self.toUnicode(line).strip()
            if not rawLine or rawLine.startswith(u"#"):
                return None

            group = u""
            title = u""
            url = u""

            match = re.match(r"^\[([^\]]+)\]\s*(.*?)\s*;\s*(https?://.+?)\s*$", rawLine, re.IGNORECASE)
            if match:
                group = self.cleanGroup(match.group(1))
                title = self.cleanValue(match.group(2))
                url = self.normalizeUrl(match.group(3))
            else:
                match = re.match(r"^(.*?)\s*;\s*(https?://.+?)\s*$", rawLine, re.IGNORECASE)
                if match:
                    title = self.cleanValue(match.group(1))
                    url = self.normalizeUrl(match.group(2))
                else:
                    return None

            if not title or not url:
                return None

            return {
                "group": group,
                "title": title,
                "url": url,
                "raw_line": rawLine,
            }
        except Exception:
            printExc()
        return None

    def buildLine(self, group, title, url):
        group = self.cleanGroup(group)
        title = self.cleanValue(title)
        url = self.normalizeUrl(url)

        if group:
            return u"[%s] %s;%s" % (group, title, url)
        return u"%s;%s" % (title, url)

    def read(self):
        entries = []
        path = self.getUserLinksPath()

        try:
            if not os.path.isfile(path):
                return entries

            with codecs.open(path, "r", "utf-8") as f:
                for line in f:
                    item = self.parseLine(line)
                    if item is not None:
                        entries.append(item)
        except Exception:
            printExc()

        return entries

    def sortEntries(self, entries):
        try:
            def sortKey(item):
                group = self.cleanGroup(item.get("group", "")).lower()
                title = self.cleanValue(item.get("title", "")).lower()
                url = self.normalizeUrl(item.get("url", "")).lower()
                return (group, title, url)

            return sorted(entries, key=sortKey)
        except Exception:
            printExc()
            return entries

    def write(self, entries):
        try:
            self.ensureUserLinksDir()
            path = self.getUserLinksPath()
            entries = self.sortEntries(entries)
            lines = []

            for item in entries:
                if not isinstance(item, dict):
                    continue
                line = self.buildLine(
                    item.get("group", ""),
                    item.get("title", ""),
                    item.get("url", "")
                )

                if line.strip():
                    lines.append(line)

            with codecs.open(path, "w", "utf-8") as f:
                for line in lines:
                    f.write(line + u"\n")

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

    def exists(self, group, title, url, skipItem=None):
        try:
            group = self.cleanGroup(group)
            title = self.cleanValue(title)
            url = self.normalizeUrl(url)

            for item in self.read():
                if skipItem is not None and self.sameItem(item, skipItem):
                    continue
                if (
                    self.cleanGroup(item.get("group", "")) == group and
                    self.cleanValue(item.get("title", "")) == title and
                    self.normalizeUrl(item.get("url", "")) == url
                ):
                    return True
        except Exception:
            printExc()
        return False

    def existsUrlAnywhere(self, url, skipItem=None):
        try:
            url = self.normalizeUrl(url)

            for item in self.read():
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
                "group": group,
                "title": title,
                "url": url,
            }

            insertIdx = len(entries)

            if group:
                lastGroupIdx = -1
                for idx in range(len(entries)):
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

    def update(self, oldItem, newGroup, newTitle, newUrl):
        try:
            entries = self.read()
            found = False

            newGroup = self.cleanGroup(newGroup)
            newTitle = self.cleanValue(newTitle)
            newUrl = self.normalizeUrl(newUrl)

            if not newTitle or not newUrl:
                return False, _("Invalid name.")

            if self.existsUrlAnywhere(newUrl, skipItem=oldItem):
                return False, _("The element already exists in User Links.")

            for idx in range(len(entries)):
                item = entries[idx]
                if self.sameItem(item, oldItem):
                    entries[idx] = {
                        "group": newGroup,
                        "title": newTitle,
                        "url": newUrl,
                    }
                    found = True
                    break

            if not found:
                return False, _("File Not Found.")

            if self.write(entries):
                return True, _("User link updated.")
        except Exception:
            printExc()

        return False, _("The user link could not be updated.")

    def delete(self, itemToDelete):
        try:
            entries = self.read()
            newEntries = []

            for item in entries:
                if self.sameItem(item, itemToDelete):
                    continue
                newEntries.append(item)

            if len(newEntries) == len(entries):
                return False, _("File Not Found.")

            if self.write(newEntries):
                return True, _("User link deleted.")
        except Exception:
            printExc()

        return False, _("The user link could not be deleted.")

    def askNewGroup(self, session, callback):
        session.openWithCallback(
            lambda text=None: self.onNewGroupEntered(text, callback),
            VirtualKeyBoard,
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
        options = [
            (self.guiSafeStr(_("Add new group")), "new"),
            (self.guiSafeStr(_("--All--")), ""),
        ]

        for group in groups:
            if group:
                options.append((self.guiSafeStr(group), self.guiSafeStr(group)))

        session.openWithCallback(
            lambda ret=None: self.onTargetGroupActionSelected(session, ret, callback),
            ChoiceBox,
            title=self.guiSafeStr(_("Select group")),
            list=options
        )

    def onTargetGroupActionSelected(self, session, ret, callback):
        if ret is None:
            callback("", False)
            return

        value = ret[1]
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
                VirtualKeyBoard,
                title=self.guiSafeStr(_("Edit favourites")),
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
                callback(False, _("Wrong uri."))
                return

            sts, msg = self.update(
                oldItem,
                parsed.get("group", ""),
                parsed.get("title", ""),
                parsed.get("url", "")
            )
            callback(sts, msg)
        except Exception:
            printExc()
            callback(False, _("The user link could not be updated."))

    def openAddCurrentItem(self, session, cItem=None, callback=None):
        if callback is None:
            def callback(sts, msg):
                session.open(
                    MessageBox,
                    msg,
                    type=MessageBox.TYPE_INFO,
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

    def openEditor(self, session):
        session.open(YouTubeUserLinksEditorScreen, self)
