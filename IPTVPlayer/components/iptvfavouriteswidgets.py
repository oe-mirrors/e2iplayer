# -*- coding: utf-8 -*-
# Last Modified: 2026-07-26 - Added blue key "Edit" option in favourites manager. - Kamikaze24
########################################################
# 29.07.2026 - HD Skin - WQHD Skin added by @stein17
########################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, IsValidFileName, GetFavouritesDir, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvfavourites import IPTVFavourites
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CDisplayListItem
from Plugins.Extensions.IPTVPlayer.components.iptvmultipleinputbox import IPTVMultipleInputBox
from Plugins.Extensions.IPTVPlayer.components.iptvlist import IPTVMainNavigatorList
###################################################

###################################################
# FOREIGN import
###################################################
from enigma import getDesktop, gRGB
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Screens.ChoiceBox import ChoiceBox
from Components.Label import Label
from Components.ActionMap import ActionMap
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
            options.append((item['title'], item['group_id']))
        if self.canAddNewGroup:
            options.append((_("Add new group of favorites"), None))
        if len(options):
            self.session.openWithCallback(self.addFavouriteToGroup, ChoiceBox, title=_("Select favorite group"), list=options)
        else:
            self.session.openWithCallback(self.iptvDoFinish, MessageBox, _("There are no other favorite groups"), type=MessageBox.TYPE_INFO, timeout=10)

    def addFavouriteToGroup(self, retArg):
        if retArg and 2 == len(retArg):
            if None is not retArg[1]:
                sts = self.favourites.loadGroupItems(retArg[1], force=False)
                if sts:
                    sts = self.favourites.addGroupItem(self.favItem, retArg[1])
                if sts:
                    sts = self.favourites.saveGroupItems(retArg[1])
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
                self.addFavouriteToGroup((group['title'], group['group_id']))
            else:
                self.session.openWithCallback(self.iptvDoFinish, MessageBox, self.favourites.getLastError(), type=MessageBox.TYPE_ERROR, timeout=10)
        else:
            self.iptvDoFinish()

    def iptvDoFinish(self, ret=None):
        self.close(self.result)


class IPTVFavouritesMainWidget(Screen):
    screenwidth = getDesktop(0).size().width()

    if screenwidth >= 2560:
        # WQHD 2560x1440 - FHD icons are scaled because no WQHD icon set exists.
        skin = """
        <screen name="IPTVFavouritesMainWidget" position="center,center" size="2240,1300" title="Favorites manager" backgroundColor="#34111112" flags="wfNoBorder">
            <widget source="Title" render="Label" position="360,20" size="1570,80" foregroundColor="white" backgroundColor="black" borderWidth="2" borderColor="black" transparent="1" zPosition="1" font="Regular;48" valign="center" />

            <widget name="title" position="40,136" size="2160,60" font="Regular;48" halign="left" valign="center" foregroundColor="white" backgroundColor="black" borderWidth="2" borderColor="black" zPosition="1" transparent="1" />

            <widget name="list" position="40,220" size="2160,936" itemHeight="72" font="Regular;40" scrollbarMode="showOnDemand" scrollbarSliderBorderWidth="2" scrollbarForegroundColor="#1b5a91" scrollbarBorderColor="#00b6b6b6" enableWrapAround="1" foregroundColor="white" backgroundColor="black" foregroundColorSelected="white" backgroundColorSelected="#1b5a91" borderWidth="2" borderColor="black" transparent="1" />

            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/red.png" position="280,1230" size="40,40" alphatest="blend" scale="1" transparent="1" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/green.png" position="730,1230" size="40,40" alphatest="blend" scale="1" transparent="1" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/yellow.png" position="1270,1230" size="40,40" alphatest="blend" scale="1" transparent="1" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/blue.png" position="1820,1230" size="40,40" alphatest="blend" scale="1" transparent="1" />

            <widget name="label_red" position="330,1222" size="400,56" zPosition="1" font="Regular;40" backgroundColor="black" foregroundColor="white" halign="left" transparent="1" valign="center" noWrap="1" />
            <widget name="label_green" position="780,1222" size="490,56" zPosition="1" font="Regular;40" backgroundColor="black" foregroundColor="white" halign="left" transparent="1" valign="center" noWrap="1" />
            <widget name="label_yellow" position="1320,1222" size="490,56" zPosition="1" font="Regular;40" backgroundColor="black" foregroundColor="white" halign="left" transparent="1" valign="center" noWrap="1" />
            <widget name="label_blue" position="1870,1222" size="400,56" zPosition="1" font="Regular;40" backgroundColor="black" foregroundColor="white" halign="left" transparent="1" valign="center" noWrap="1" />

            <eLabel name="BG_Title" position="0,0" size="2240,120" backgroundColor="#100d0f16" zPosition="-1" />
            <eLabel name="BG_Buttons" position="0,1200" size="2240,96" backgroundColor="#100d0f16" zPosition="-1" />

            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/smallshadowline.png" position="0,120" size="2240,4" scale="1" zPosition="2" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/smallshadowline.png" position="0,1200" size="2240,4" scale="1" zPosition="2" />

            <ePixmap position="40,1224" size="80,52" zPosition="10" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/ok.png" transparent="1" scale="1" alphatest="blend" />
            <ePixmap position="148,1224" size="80,52" zPosition="10" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/exit.png" transparent="1" scale="1" alphatest="blend" />
            <ePixmap name="playerlogo" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/logos/favouriteslogo.png" zPosition="4" position="40,20" size="240,80" scale="1" alphatest="blend" transparent="1" backgroundColor="black" />

            <widget source="global.CurrentTime" render="Label" position="1920,20" size="300,80" foregroundColor="white" backgroundColor="black" borderWidth="2" borderColor="black" transparent="1" zPosition="1" font="Regular;48" valign="center" halign="right">
                <convert type="ClockToText">Format:%H:%M</convert>
            </widget>

            <widget source="global.CurrentTime" render="Label" position="1440,40" size="600,48" foregroundColor="white" backgroundColor="black" borderWidth="2" borderColor="black" transparent="1" zPosition="1" font="Regular;32" valign="center" halign="right">
                <convert type="ClockToText">Date</convert>
            </widget>
        </screen>
        """

    elif screenwidth >= 1920:
        # FHD 1920x1080
        skin = """
        <screen name="IPTVFavouritesMainWidget" position="center,center" size="1680,975" title="Favorites manager" backgroundColor="#34111112" flags="wfNoBorder">
            <widget source="Title" render="Label" position="240,15" size="1178,60" foregroundColor="white" backgroundColor="black" borderWidth="2" borderColor="black" transparent="1" zPosition="1" font="Regular;36" valign="center" />

            <widget name="title" position="30,102" size="1620,45" font="Regular;36" halign="left" valign="center" foregroundColor="white" backgroundColor="black" borderWidth="2" borderColor="black" zPosition="1" transparent="1" />

            <widget name="list" position="30,165" size="1620,702" itemHeight="54" font="Regular;30" scrollbarMode="showOnDemand" scrollbarSliderBorderWidth="1" scrollbarForegroundColor="#1b5a91" scrollbarBorderColor="#00b6b6b6" enableWrapAround="1" foregroundColor="white" backgroundColor="black" foregroundColorSelected="white" backgroundColorSelected="#1b5a91" borderWidth="2" borderColor="black" transparent="1" />

             <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/red.png" position="200,923" size="30,30" alphatest="blend" transparent="1" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/green.png" position="550,923" size="30,30" alphatest="blend" transparent="1" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/yellow.png" position="950,923" size="30,30" alphatest="blend" transparent="1" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/blue.png" position="1350,923" size="30,30" alphatest="blend" transparent="1" />

            <widget name="label_red" position="240,917" size="300,42" zPosition="1" font="Regular;30" backgroundColor="black" foregroundColor="white" halign="left" transparent="1" valign="center" noWrap="1" />
            <widget name="label_green" position="590,917" size="350,42" zPosition="1" font="Regular;30" backgroundColor="black" foregroundColor="white" halign="left" transparent="1" valign="center" noWrap="1" />
            <widget name="label_yellow" position="990,917" size="350,42" zPosition="1" font="Regular;30" backgroundColor="black" foregroundColor="white" halign="left" transparent="1" valign="center" noWrap="1" />
            <widget name="label_blue" position="1390,917" size="300,42" zPosition="1" font="Regular;30" backgroundColor="black" foregroundColor="white" halign="left" transparent="1" valign="center" noWrap="1" />

            <eLabel name="BG_Title" position="0,0" size="1680,90" backgroundColor="#100d0f16" zPosition="-1" />
            <eLabel name="BG_Buttons" position="0,900" size="1680,72" backgroundColor="#100d0f16" zPosition="-1" />

            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/smallshadowline.png" position="0,90" size="1680,3" zPosition="2" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/smallshadowline.png" position="0,900" size="1680,3" zPosition="2" />

            <ePixmap position="30,918" size="60,38" zPosition="10" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/ok.png" transparent="1" alphatest="blend" />
            <ePixmap position="111,918" size="60,38" zPosition="10" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/FHD/exit.png" transparent="1" alphatest="blend" />
            <ePixmap name="playerlogo" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/logos/favouriteslogo.png" zPosition="4" position="30,15" size="180,60" scale="1" alphatest="blend" transparent="1" backgroundColor="black" />

            <widget source="global.CurrentTime" render="Label" position="1440,15" size="225,60" foregroundColor="white" backgroundColor="black" borderWidth="2" borderColor="black" transparent="1" zPosition="1" font="Regular;36" valign="center" halign="right">
                <convert type="ClockToText">Format:%H:%M</convert>
            </widget>

            <widget source="global.CurrentTime" render="Label" position="1080,30" size="450,36" foregroundColor="white" backgroundColor="black" borderWidth="2" borderColor="black" transparent="1" zPosition="1" font="Regular;24" valign="center" halign="right">
                <convert type="ClockToText">Date</convert>
            </widget>
        </screen>
        """

    else:
        # HD 1280x720
        skin = """
        <screen name="IPTVFavouritesMainWidget" position="center,center" size="1120,650" title="Favorites manager" backgroundColor="#34111112" flags="wfNoBorder">
            <widget source="Title" render="Label" position="180,9" size="785,40" foregroundColor="white" backgroundColor="black" borderWidth="1" borderColor="black" transparent="1" zPosition="1" font="Regular;24" valign="center" />

            <widget name="title" position="20,68" size="1080,30" font="Regular;24" halign="left" valign="center" foregroundColor="white" backgroundColor="black" borderWidth="1" borderColor="black" zPosition="1" transparent="1" />

            <widget name="list" position="20,110" size="1080,468" itemHeight="36" font="Regular;20" scrollbarMode="showOnDemand" scrollbarSliderBorderWidth="1" scrollbarForegroundColor="#1b5a91" scrollbarBorderColor="#00b6b6b6" enableWrapAround="1" foregroundColor="white" backgroundColor="black" foregroundColorSelected="white" backgroundColorSelected="#1b5a91" borderWidth="1" borderColor="black" transparent="1" />

            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/red.png" position="140,615" size="20,20" alphatest="blend" transparent="1" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/green.png" position="370,615" size="20,20" alphatest="blend" transparent="1" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/yellow.png" position="640,615" size="20,20" alphatest="blend" transparent="1" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/blue.png" position="910,615" size="20,20" alphatest="blend" transparent="1" />

            <widget name="label_red" position="170,611" size="200,28" zPosition="1" font="Regular;20" backgroundColor="black" foregroundColor="white" halign="left" transparent="1" valign="center" noWrap="1" />
            <widget name="label_green" position="395,611" size="240,28" zPosition="1" font="Regular;20" backgroundColor="black" foregroundColor="white" halign="left" transparent="1" valign="center" noWrap="1" />
            <widget name="label_yellow" position="665,611" size="240,28" zPosition="1" font="Regular;20" backgroundColor="black" foregroundColor="white" halign="left" transparent="1" valign="center" noWrap="1" />
            <widget name="label_blue" position="935,611" size="200,28" zPosition="1" font="Regular;20" backgroundColor="black" foregroundColor="white" halign="left" transparent="1" valign="center" noWrap="1" />

            <eLabel name="BG_Title" position="0,0" size="1120,60" backgroundColor="#100d0f16" zPosition="-1" />
            <eLabel name="BG_Buttons" position="0,600" size="1120,48" backgroundColor="#100d0f16" zPosition="-1" />

            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/smallshadowline.png" position="0,60" size="1120,2" zPosition="2" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/smallshadowline.png" position="0,600" size="1120,2" zPosition="2" />

            <ePixmap position="20,612" size="40,26" zPosition="10" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/ok.png" transparent="1" alphatest="blend" />
            <ePixmap position="74,612" size="40,26" zPosition="10" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/exit.png" transparent="1" alphatest="blend" />
            <ePixmap name="playerlogo" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/logos/favouriteslogo.png" zPosition="4" position="20,10" size="120,40" alphatest="blend" transparent="1" backgroundColor="black" />


            <widget source="global.CurrentTime" render="Label" position="960,10" size="150,40" foregroundColor="white" backgroundColor="black" borderWidth="1" borderColor="black" transparent="1" zPosition="1" font="Regular;24" valign="center" halign="right">
                <convert type="ClockToText">Format:%H:%M</convert>
            </widget>

            <widget source="global.CurrentTime" render="Label" position="720,20" size="300,24" foregroundColor="white" backgroundColor="black" borderWidth="1" borderColor="black" transparent="1" zPosition="1" font="Regular;16" valign="center" halign="right">
                <convert type="ClockToText">Date</convert>
            </widget>
        </screen>
        """

    def __init__(self, session):
        self.session = session
        Screen.__init__(self, session)
        self.setTitle(_("Favorites manager"))

        self.onShown.append(self.onStart)
        self.onClose.append(self.__onClose)
        self.favourites = None
        self.started = False
        self.menu = ":groups:"  # "items"
        self.modified = False

        self.IDS_ENABLE_REORDERING = _('Enable reordering')
        self.IDS_DISABLE_REORDERING = _('Disable reordering')
        self.reorderingMode = False

        self["title"] = Label(_("Favorites groups"))
        self["label_red"] = Label(_("Remove group"))
        self["label_yellow"] = Label(self.IDS_ENABLE_REORDERING)
        self["label_green"] = Label(_("Add new group"))
        self["label_blue"] = Label(_("Edit"))

        self["list"] = IPTVMainNavigatorList()
        self["list"].connectSelChanged(self.onSelectionChanged)

        self["actions"] = ActionMap(["ColorActions", "WizardActions", "ListboxActions"],
            {
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
            }, -2)

        self.prevIdx = 0
        self.duringMoving = False

    def __onClose(self):
        self["list"].disconnectSelChanged(self.onSelectionChanged)

    def onStart(self):
        self.onShown.remove(self.onStart)
        self.favourites = IPTVFavourites(GetFavouritesDir())
        sts = self.favourites.load(groupsOnly=True)
        if not sts:
            self.session.openWithCallback(self.iptvDoFinish, MessageBox, self.favourites.getLastError(), type=MessageBox.TYPE_ERROR, timeout=10)
            return
        self.displayList()

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
            self["label_red"].setText(_("Remove group"))
            self["label_green"].setText(_("Add new group"))
            self["label_blue"].setText(_("Edit"))

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
            self["label_red"].setText(_("Remove item"))
            self["label_green"].setText(_("Add item to group"))
            self["label_blue"].setText(_("Edit"))

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
                self["label_yellow"].setText(self.IDS_ENABLE_REORDERING)
            else:
                self.reorderingMode = True
                self["label_yellow"].setText(self.IDS_DISABLE_REORDERING)

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
                if ":groups:" == self.menu:
                    sts = self.favourites.moveGroup(curIndex, newIndex)
                else:
                    sts = self.favourites.moveGroupItem(curIndex, newIndex, self.menu)
                if sts:
                    self.modified = True
                    self.displayList()
            else:
                self["list"].instance.moveSelection(key)

    def keyUp(self):
        if self["list"].instance is not None:
            self.moveItem(self["list"].instance.moveUp)

    def keyDown(self):
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
