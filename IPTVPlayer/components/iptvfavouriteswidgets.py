# -*- coding: utf-8 -*-
# Last Modified: 2026-07-26 - Added blue key "Edit" option in favourites manager. - Kamikaze24
########################################################
# 29.07.2026 - HD Skin - WQHD Skin added by @stein17
########################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, IsValidFileName, GetFavouritesDir, GetIconDir, findT9JumpIndex
from Plugins.Extensions.IPTVPlayer.tools.iptvfavourites import IPTVFavourites
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CDisplayListItem
from Plugins.Extensions.IPTVPlayer.components.iptvmultipleinputbox import IPTVMultipleInputBox
from Plugins.Extensions.IPTVPlayer.components.iptvlist import IPTVMainNavigatorList
from Plugins.Extensions.IPTVPlayer.components import skinchrome
from Plugins.Extensions.IPTVPlayer.components.cover import Cover
from Plugins.Extensions.IPTVPlayer.components.iptvchoicebox import IPTVChoiceBoxWidget, IPTVChoiceBoxItem, openChoiceBox
###################################################

###################################################
# FOREIGN import
###################################################
from enigma import gRGB
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.config import config
from Components.Label import Label
from Components.ActionMap import ActionMap
from Components.Sources.StaticText import StaticText
from Tools.NumericalTextInput import NumericalTextInput
###################################################


class IPTVFavouritesAddNewGroupWidget(Screen):
    def __init__(self, session, favourites):
        self.session = session
        Screen.__init__(self, session)

        self.onShown.append(self.onStart)
        self.favourites = favourites
        self.started = False
        self.group = None

    def onStart(self):
        self.onShown.remove(self.onStart)
        from copy import deepcopy
        params = deepcopy(IPTVMultipleInputBox.DEF_PARAMS)
        params['title'] = _("Add new group of favorites")
        params['with_accept_button'] = True
        params['list'] = []

        for input in [[self._validate, _("Name:"), _("Group %d") % (len(self.favourites.getGroups()) + 1), ], [None, _("Description:"), " "]]:
            item = deepcopy(IPTVMultipleInputBox.DEF_INPUT_PARAMS)
            item['validator'] = input[0]
            item['title'] = input[1]
            item['input']['text'] = input[2]
            params['list'].append(item)
        self.session.openWithCallback(self.iptvRetCallback, IPTVMultipleInputBox, params)

    def _validate(self, text):
        if 0 == len(text):
            return False, _("Name cannot be empty.")
        elif not IsValidFileName(text):
            return False, _("Name is not valid.\nPlease remove special characters.")
        else:
            group_id = text.lower()
            idx = self.favourites._getGroupIdx(group_id)
            if -1 != idx:
                return False, _("Group \"%s\" already exists.") % group_id
        return True, ""

    def iptvRetCallback(self, retArg):
        self.group = None
        if retArg and 2 == len(retArg):
            group = {"title": retArg[0], "group_id": retArg[0].lower(), "desc": retArg[1]}
            result = self.favourites.addGroup(group)
            if result:
                self.group = group
            else:
                self.session.openWithCallback(self.iptvDoFinish, MessageBox, self.favourites.getLastError(), type=MessageBox.TYPE_ERROR, timeout=10)
                return
        self.iptvDoFinish()

    def iptvDoFinish(self, ret=None):
        self.close(self.group)


class IPTVFavouritesAddItemWidget(Screen):
    def __init__(self, session, favItem, favourites=None, canAddNewGroup=True, ignoredGroups=[]):
        self.session = session
        Screen.__init__(self, session)

        self.onShown.append(self.onStart)
        self.started = False
        self.result = False

        self.favItem = favItem
        if None is not favourites:
            self.saveLoad = False
        else:
            self.saveLoad = True
        self.favourites = favourites
        self.canAddNewGroup = canAddNewGroup
        self.ignoredGroups = ignoredGroups

    def onStart(self):
        self.onShown.remove(self.onStart)
        if None is self.favourites:
            self.favourites = IPTVFavourites(GetFavouritesDir())
            sts = self.favourites.load(groupsOnly=True)
            if not sts:
                self.session.openWithCallback(self.iptvDoFinish, MessageBox, self.favourites.getLastError(), type=MessageBox.TYPE_ERROR, timeout=10)
                return
        options = []
        groups = self.favourites.getGroups()
        for item in groups:
            if item['group_id'] in self.ignoredGroups:
                continue
            options.append(IPTVChoiceBoxItem(name=item['title'], privateData=item['group_id']))
        if self.canAddNewGroup:
            options.append(IPTVChoiceBoxItem(name=_("Add new group of favorites"), privateData=None))
        if len(options):
            height = self._getGroupPickerHeight(len(options))
            openChoiceBox(self.session, {'width': 600, 'height': height, 'current_idx': 0, 'title': _("Select favorite group"), 'options': options, 'chrome': True}, self.addFavouriteToGroup)
        else:
            self.session.openWithCallback(self.iptvDoFinish, MessageBox, _("There are no other favorite groups"), type=MessageBox.TYPE_INFO, timeout=10)

    def _getGroupPickerHeight(self, numItems):
        # same tier-aware height+cap formula ConfigBaseWidget's own
        # _getSelectionListHeight() (configbase.py) uses - a "pick a
        # favorites group" list is anywhere from 1 to a dozen+ groups, no
        # single fixed height fits both; capped at 660 (chrome's own
        # 720-tall reference canvas convention) so it scrolls
        # (scrollbarMode="showAlways" already on the list) instead of
        # growing the popup past the screen edge
        #
        # Floored at 2 - same "empty window" issue ConfigBaseWidget's own
        # _getSelectionListHeight() guards against: with numItems=1
        # (exactly one other group, canAddNewGroup False) the computed
        # list area is smaller than one real item row at FHD/WQHD, so the
        # single row can't render at all.
        numItems = max(numItems, 2)
        itemH, scale = skinchrome.tierRowHeight(35, 40, 55)
        height = int(numItems * itemH / scale) + 176
        return min(height, 660)

    def addFavouriteToGroup(self, retArg):
        if retArg is not None:
            if None is not retArg.privateData:
                sts = self.favourites.loadGroupItems(retArg.privateData, force=False)
                if sts:
                    sts = self.favourites.addGroupItem(self.favItem, retArg.privateData)
                if sts:
                    sts = self.favourites.saveGroupItems(retArg.privateData)
                if sts:
                    self.result = True
                    self.iptvDoFinish()
                    return
                else:
                    self.session.openWithCallback(self.iptvDoFinish, MessageBox, self.favourites.getLastError(), type=MessageBox.TYPE_ERROR, timeout=10)
            else:  # addn new group
                self.session.openWithCallback(self.addNewFavouriteGroup, IPTVFavouritesAddNewGroupWidget, self.favourites)
        else:
            self.iptvDoFinish()

    def addNewFavouriteGroup(self, group):
        if None is not group:
            sts = True
            if self.saveLoad:
                sts = self.favourites.save(True)
            if sts:
                # addFavouriteToGroup() expects an IPTVChoiceBoxItem-like
                # object (.privateData) since the group picker uses
                # IPTVChoiceBoxWidget, not the native ChoiceBox's plain
                # tuples - this call site (a brand-new group just created
                # via the "Add new group of favorites" option, not a
                # ChoiceBox selection) needs the same wrapping.
                self.addFavouriteToGroup(IPTVChoiceBoxItem(name=group['title'], privateData=group['group_id']))
            else:
                self.session.openWithCallback(self.iptvDoFinish, MessageBox, self.favourites.getLastError(), type=MessageBox.TYPE_ERROR, timeout=10)
        else:
            self.iptvDoFinish()

    def iptvDoFinish(self, ret=None):
        self.close(self.result)


class IPTVFavouritesMainWidget(Screen):
    # was 3 hand-duplicated per-tier skin blocks (**Dupliziert** in the
    # TODO), built off a class-level `screenwidth = getDesktop(0)...`
    # (same stale-at-import-time bug already fixed everywhere else in
    # this branch) - every declared size in all 3 already scaled in
    # exact 1x/1.5x/2x lockstep (e.g. itemHeight 36/54/72, font 20/30/40),
    # so there was never a real need for 3 separate blocks: one
    # `resolution="1280,720"`-auto-scaled skin does the same job, same
    # pattern as e.g. `iptvarticleview.py`/`iptvchoicebox.py`.
    #
    # "title" (secondary heading row: "Favorites groups"/"Items in group
    # X") sits directly below the header, full width - same convention
    # `iptvdirbrowser.py`'s "curr_dir" row now uses too. Footer (OK/EXIT
    # + all 4 color keys) now comes from `skinchrome.build_footer_auto()`
    # instead of the old hand-placed icons/labels - footer grows from
    # 48px to 64px like every other screen this branch touches (2-line
    # color-key label wrap), so window height grows by the same +14
    # (650->664) while every widget above the footer keeps its exact old
    # position/size.
    #
    # "playerlogo" (this screen's own `favouriteslogo.png`, distinct from
    # the app's default `iptvlogo.png`) sits in the header's own logo
    # slot (`build_header_auto(logoWidgetName="playerlogo")`, same trick
    # `iptvarticleview.py`/`iptvplayerwidget.py` already use) instead of
    # its own separate ePixmap. Rather than baking separate HD/FHD/WQHD
    # copies of the source PNG, this reuses `iptvplayerwidget.py`'s own
    # `Cover()` (`ePicLoad`-backed, decodes+resizes to
    # `self.instance.size()` at runtime, same mechanism used for cover
    # art) via the same `decodeCover()`/`updateLogoCover()` pattern - one
    # image fits whatever box the widget actually has at any resolution,
    # so the file itself stays a single, un-tiered PNG under
    # `icons/logos/`.
    #
    # `global.CurrentTime` clock/date widgets keep their old position
    # (already right-aligned, so their declared boxes overlapping the
    # header's own much-wider Title box was already true before too) -
    # `zPosition="2"` added so they paint above the Title label's
    # background, same fix already shipped for `iptvplayerwidget.py`'s
    # own header.
    def __prepareSkin(self):
        iconBase = skinchrome.getIconBase()
        # header clock/date is an opt-out via
        # config.plugins.iptvplayer.show_header_clock (Skin configuration
        # section).
        clockPart = """<widget source="global.CurrentTime" render="Label" position="960,10" size="150,40" foregroundColor="white" backgroundColor="black" borderWidth="1" borderColor="black" transparent="1" zPosition="2" font="Regular;24" valign="center" halign="right">
                <convert type="ClockToText">Format:%H:%M</convert>
            </widget>
            <widget source="global.CurrentTime" render="Label" position="720,20" size="300,24" foregroundColor="white" backgroundColor="black" borderWidth="1" borderColor="black" transparent="1" zPosition="2" font="Regular;16" valign="center" halign="right">
                <convert type="ClockToText">Date</convert>
            </widget>""" if config.plugins.iptvplayer.show_header_clock.value else ""
        return """
        <screen name="IPTVFavouritesMainWidget" position="center,center" size="1120,664" resolution="1280,720" title="Favorites manager" backgroundColor="#34111112" flags="wfNoBorder">
            %s
            <widget name="title" position="20,68" size="1080,30" font="Regular;24" halign="left" valign="center" foregroundColor="white" backgroundColor="black" borderWidth="1" borderColor="black" zPosition="1" transparent="1" />
            <widget name="list" position="20,110" size="1080,468" itemHeight="36" font="Regular;20" scrollbarMode="showOnDemand" scrollbarSliderBorderWidth="1" scrollbarForegroundColor="#1b5a91" scrollbarBorderColor="#00b6b6b6" enableWrapAround="1" foregroundColor="white" backgroundColor="black" foregroundColorSelected="white" backgroundColorSelected="#1b5a91" borderWidth="1" borderColor="black" transparent="1" />
            %s
            %s
        </screen>
        """ % (
            skinchrome.build_header_auto(iconBase=iconBase, logoWidgetName="playerlogo"),
            clockPart,
            skinchrome.build_footer_auto(664, iconBase=iconBase, keys=('red', 'green', 'yellow', 'blue'), showNav=False),
        )

    def __init__(self, session):
        self.session = session
        self.skin = self.__prepareSkin()
        Screen.__init__(self, session)
        self.skinName = skinchrome.forceInternalSkinName(["IPTVFavouritesMainWidget"])
        self.setTitle(_("Favorites manager"))

        self["playerlogo"] = Cover()
        self["playerlogo"].hide()

        self.onShown.append(self.onStart)
        self.onClose.append(self.__onClose)
        self.favourites = None
        self.started = False
        self.menu = ":groups:"  # "items"
        self.modified = False

        self.IDS_ENABLE_REORDERING = _('Enable reordering')
        self.IDS_DISABLE_REORDERING = _('Disable reordering')
        self.reorderingMode = False
        self.t9Input = NumericalTextInput(handleTimeout=False)

        self["title"] = Label(_("Favorites groups"))
        self["key_red"] = StaticText(_("Remove group"))
        self["key_yellow"] = StaticText(self.IDS_ENABLE_REORDERING)
        self["key_green"] = StaticText(_("Add new group"))
        self["key_blue"] = StaticText(_("Edit"))

        self["list"] = IPTVMainNavigatorList()
        self["list"].connectSelChanged(self.onSelectionChanged)

        actions = {
            "back": self.keyExit,
            "cancel": self.keyExit,
            "ok": self.keyOK,
            "red": self.keyRed,
            "yellow": self.keyYellow,
            "green": self.keyGreen,
            "blue": self.keyBlue,

            "up": self.keyUp,
            "down": self.keyDown,
            "left": self.keyLeft,
            "right": self.keyRight,
            "moveUp": self.keyDrop,
            "moveDown": self.keyDrop,
            "moveTop": self.keyDrop,
            "moveEnd": self.keyDrop,
            "home": self.keyDrop,
            "end": self.keyDrop,
            "pageUp": self.keyDrop,
            "pageDown": self.keyDrop
        }
        for digit in '123456789':
            actions[digit] = self.makeNumberJump(digit)

        self["actions"] = ActionMap(["ColorActions", "WizardActions", "ListboxActions", "NumberActions"],
            actions, -2)

        self.prevIdx = 0
        self.duringMoving = False

    def __onClose(self):
        self["list"].disconnectSelChanged(self.onSelectionChanged)

    def onStart(self):
        self.onShown.remove(self.onStart)
        logoPath = GetIconDir('logos/favouriteslogo.png')
        if self["playerlogo"].checkDecodeNeeded(logoPath):
            self["playerlogo"].decodeCover(logoPath, self.updateLogoCover, "playerlogo")
        else:
            self["playerlogo"].show()
        self.favourites = IPTVFavourites(GetFavouritesDir())
        sts = self.favourites.load(groupsOnly=True)
        if not sts:
            self.session.openWithCallback(self.iptvDoFinish, MessageBox, self.favourites.getLastError(), type=MessageBox.TYPE_ERROR, timeout=10)
            return
        self.displayList()

    def updateLogoCover(self, retDict):
        # single static asset, always the same file - unlike
        # iptvplayerwidget.py's own updateCover() this never needs to
        # check "is this still the right icon for the current selection",
        # it's the only thing ever decoded into "playerlogo" here
        if retDict and retDict["Pixmap"] is not None:
            self["playerlogo"].updatePixmap(retDict["Pixmap"], retDict["FileName"])
            self["playerlogo"].show()

    def iptvDoFinish(self, ret=None):
        self.close()

    def displayList(self):
        list = []
        if ":groups:" == self.menu:
            groups = self.favourites.getGroups()
            for item in groups:
                dItem = CDisplayListItem(name=item['title'], type=CDisplayListItem.TYPE_CATEGORY)
                dItem.privateData = item['group_id']
                list.append((dItem,))
        else:
            if not self.loadGroupItems(self.menu):
                return
            sts, items = self.favourites.getGroupItems(self.menu)
            if not sts:
                self.session.open(MessageBox, self.favourites.getLastError(), type=MessageBox.TYPE_ERROR, timeout=10)
                return
            for idx in range(len(items)):
                item = items[idx]
                dItem = CDisplayListItem(name=item.name, type=item.type)
                dItem.privateData = idx
                list.append((dItem,))
        self["list"].setList(list)

    def loadGroupItems(self, groupId):
        sts = self.favourites.loadGroupItems(groupId)
        if not sts:
            self.session.open(MessageBox, self.favourites.getLastError(), type=MessageBox.TYPE_ERROR, timeout=10)
            return False
        return True

    def onSelectionChanged(self):
        pass

    def keyExit(self):
        if ":groups:" == self.menu:
            if self.duringMoving:
                self._changeMode()
            if self.modified:
                self.askForSave()
            else:
                self.close(False)
        else:
            self["title"].setText(_("Favorites groups"))
            self["key_red"].setText(_("Remove group"))
            self["key_green"].setText(_("Add new group"))
            self["key_blue"].setText(_("Edit"))

            self.menu = ":groups:"
            self.displayList()
            try:
                self["list"].moveToIndex(self.prevIdx)
            except Exception:
                pass

    def askForSave(self):
        self.session.openWithCallback(self.save, MessageBox, text=_("Save changes?"), type=MessageBox.TYPE_YESNO)

    def save(self, ret):
        if ret:
            if not self.favourites.save():
                self.session.openWithCallback(self.closeAfterSave, MessageBox, self.favourites.getLastError(), type=MessageBox.TYPE_ERROR, timeout=10)
                return
            self.closeAfterSave()
        self.close(False)

    def closeAfterSave(self):
        self.close(True)

    def keyOK(self):
        if self.reorderingMode:
            if None is not self.getSelectedItem():
                self._changeMode()
            return
        if ":groups:" == self.menu:
            sel = self.getSelectedItem()
            if None is sel:
                return

            self.menu = sel.privateData
            try:
                self["title"].setText(_("Items in group \"%s\"") % self.favourites.getGroup(self.menu)['title'])
            except Exception:
                printExc()
            self["key_red"].setText(_("Remove item"))
            self["key_green"].setText(_("Add item to group"))
            self["key_blue"].setText(_("Edit"))

            try:
                self.prevIdx = self["list"].getCurrentIndex()
            except Exception:
                self.prevIdx = 0
            self.displayList()
            try:
                self["list"].moveToIndex(0)
            except Exception:
                pass

    def keyRed(self):
        if self.duringMoving:
            return
        sel = self.getSelectedItem()
        if None is sel:
            return
        sts = True
        if ":groups:" == self.menu:
            sts = self.favourites.delGroup(sel.privateData)
        else:
            sts = self.favourites.delGroupItem(sel.privateData, self.menu)
        if not sts:
            self.session.open(MessageBox, self.favourites.getLastError(), type=MessageBox.TYPE_ERROR, timeout=10)
            return
        self.modified = True
        self.displayList()

    def keyYellow(self):
        if None is not self.getSelectedItem():
            if self.reorderingMode:
                self.reorderingMode = False
                self["key_yellow"].setText(self.IDS_ENABLE_REORDERING)
            else:
                self.reorderingMode = True
                self["key_yellow"].setText(self.IDS_DISABLE_REORDERING)

            if self.duringMoving and not self.reorderingMode:
                self._changeMode()
            elif not self.duringMoving and self.reorderingMode:
                self._changeMode()

    def keyGreen(self):
        printDBG(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> keyGreen 1")
        if ":groups:" == self.menu:
            self.session.openWithCallback(self._groupAdded, IPTVFavouritesAddNewGroupWidget, self.favourites)
        else:
            if None is self.getSelectedItem():
                return
            if not self.loadGroupItems(self.menu):
                return
            sts, items = self.favourites.getGroupItems(self.menu)
            if not sts:
                self.session.open(MessageBox, self.favourites.getLastError(), type=MessageBox.TYPE_ERROR, timeout=10)
                return
            favItem = items[self["list"].getCurrentIndex()]
            self.session.openWithCallback(self._itemCloned, IPTVFavouritesAddItemWidget, favItem, self.favourites, False, [self.menu])

    def keyBlue(self):
        if self.duringMoving:
            return
        sel = self.getSelectedItem()
        if None is sel:
            return

        from copy import deepcopy
        params = deepcopy(IPTVMultipleInputBox.DEF_PARAMS)
        params['with_accept_button'] = True
        params['list'] = []

        if ":groups:" == self.menu:
            group = self.favourites.getGroup(sel.privateData)
            if None is group:
                return

            params['title'] = _("Edit favorite group")

            item = deepcopy(IPTVMultipleInputBox.DEF_INPUT_PARAMS)
            item['validator'] = self._validateGroup
            item['title'] = _("Name:")
            item['input']['text'] = group.get('title', '')
            params['list'].append(item)

            item = deepcopy(IPTVMultipleInputBox.DEF_INPUT_PARAMS)
            item['validator'] = None
            item['title'] = _("Description:")
            item['input']['text'] = group.get('desc', '')
            params['list'].append(item)

            self.session.openWithCallback(self._groupEdited, IPTVMultipleInputBox, params)
        else:
            if not self.loadGroupItems(self.menu):
                return
            sts, items = self.favourites.getGroupItems(self.menu)
            if not sts:
                self.session.open(MessageBox, self.favourites.getLastError(), type=MessageBox.TYPE_ERROR, timeout=10)
                return

            idx = self["list"].getCurrentIndex()
            if idx < 0 or idx >= len(items):
                return

            params['title'] = _("Edit favorite item")

            item = deepcopy(IPTVMultipleInputBox.DEF_INPUT_PARAMS)
            item['validator'] = self._validateItem
            item['title'] = _("Name:")
            item['input']['text'] = items[idx].name
            params['list'].append(item)

            self.session.openWithCallback(self._itemEdited, IPTVMultipleInputBox, params)

    def _validateGroup(self, text):
        if 0 == len(text):
            return False, _("Name cannot be empty.")
        elif not IsValidFileName(text):
            return False, _("Name is not valid.\nPlease remove special characters.")
        return True, ""

    def _validateItem(self, text):
        if 0 == len(text):
            return False, _("Name cannot be empty.")
        return True, ""

    def _groupEdited(self, retArg):
        sel = self.getSelectedItem()
        if None is sel or not retArg or 2 != len(retArg):
            return

        group = self.favourites.getGroup(sel.privateData)
        if None is group:
            return

        group['title'] = retArg[0]
        group['desc'] = retArg[1]
        self.modified = True
        self.displayList()

    def _itemEdited(self, retArg):
        sel = self.getSelectedItem()
        if None is sel or not retArg or 1 > len(retArg):
            return
        if not self.loadGroupItems(self.menu):
            return

        sts, items = self.favourites.getGroupItems(self.menu)
        if not sts:
            self.session.open(MessageBox, self.favourites.getLastError(), type=MessageBox.TYPE_ERROR, timeout=10)
            return

        idx = self["list"].getCurrentIndex()
        if idx < 0 or idx >= len(items):
            return

        items[idx].name = retArg[0]
        self.modified = True
        self.displayList()
        try:
            self["list"].moveToIndex(idx)
        except Exception:
            pass

    def _groupAdded(self, group):
        if None is not group:
            self.modified = True
            self.displayList()
            try:
                self["list"].moveToIndex(len(self.favourites.getGroups()) - 1)
            except Exception:
                pass

    def _itemCloned(self, ret):
        if ret:
            self.modified = True

    def _changeMode(self):
        if not self.duringMoving:
            self["list"].instance.setForegroundColorSelected(gRGB(0xFF0505))
            self.duringMoving = True
        else:
            self["list"].instance.setForegroundColorSelected(gRGB(0xFFFFFF))
            self.duringMoving = False
        self.displayList()

    def moveItem(self, key):
        if self["list"].instance is not None:
            if self.duringMoving:
                curIndex = self["list"].getCurrentIndex()
                self["list"].instance.moveSelection(key)
                newIndex = self["list"].getCurrentIndex()
                printDBG('IPTVFavouritesMainWidget.moveItem carrying curIndex=%s newIndex=%s' % (curIndex, newIndex))
                if ":groups:" == self.menu:
                    sts = self.favourites.moveGroup(curIndex, newIndex)
                else:
                    sts = self.favourites.moveGroupItem(curIndex, newIndex, self.menu)
                if sts:
                    self.modified = True
                    self.displayList()
            else:
                printDBG('IPTVFavouritesMainWidget.moveItem plain move (not carrying)')
                self["list"].instance.moveSelection(key)

    def keyUp(self):
        printDBG('IPTVFavouritesMainWidget.keyUp reorderingMode=%s duringMoving=%s' % (self.reorderingMode, self.duringMoving))
        if self["list"].instance is not None:
            self.moveItem(self["list"].instance.moveUp)

    def keyDown(self):
        printDBG('IPTVFavouritesMainWidget.keyDown reorderingMode=%s duringMoving=%s' % (self.reorderingMode, self.duringMoving))
        if self["list"].instance is not None:
            self.moveItem(self["list"].instance.moveDown)

    def keyLeft(self):
        if self["list"].instance is not None:
            self.moveItem(self["list"].instance.pageUp)

    def keyRight(self):
        if self["list"].instance is not None:
            self.moveItem(self["list"].instance.pageDown)

    def keyDrop(self):
        pass

    def getSelectedItem(self):
        sel = None
        try:
            sel = self["list"].l.getCurrentSelection()[0]
        except Exception:
            pass
        return sel

    def makeNumberJump(self, digit):
        return lambda: self.keyNumberJump(digit)

    def keyNumberJump(self, digit):
        if self.reorderingMode:
            return
        if not config.plugins.iptvplayer.enableT9MainList.value:
            return

        letter = self.t9Input.getKey(int(digit))
        if not letter:
            return

        try:
            currentIdx = self["list"].getCurrentIndex()
            if ":groups:" == self.menu:
                groups = self.favourites.getGroups()
                total = len(groups)

                def getTitle(i):
                    return groups[i].get('title', '')
            else:
                if not self.loadGroupItems(self.menu):
                    return
                sts, items = self.favourites.getGroupItems(self.menu)
                if not sts:
                    return
                total = len(items)

                def getTitle(i):
                    return getattr(items[i], 'name', '')

            idx = findT9JumpIndex(total, currentIdx, letter, getTitle)
            if idx >= 0:
                self["list"].moveToIndex(idx)
        except Exception:
            printExc()
