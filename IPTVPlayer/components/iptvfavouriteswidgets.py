# -*- coding: utf-8 -*-
#

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, IsValidFileName, GetFavouritesDir, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvfavourites import IPTVFavourites
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CFavItem, CDisplayListItem
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
        params['title'] = _("Add new group of favourites")
        params['with_accept_button'] = True
        params['list'] = []
        
        for input in [[self._validate, _("Name:"), _("Group %d") % (len(self.favourites.getGroups()) + 1), ], [None, _("Description:"), _(" ")]]:
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
        if None != favourites:
            self.saveLoad = False
        else:
            self.saveLoad = True
        self.favourites = favourites
        self.canAddNewGroup = canAddNewGroup
        self.ignoredGroups = ignoredGroups
    
    def onStart(self):
        self.onShown.remove(self.onStart)
        if None == self.favourites: 
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
            options.append((_("Add new group of favourites"), None))
        if len(options):
            self.session.openWithCallback(self.addFavouriteToGroup, ChoiceBox, title=_("Select favourite group"), list=options)
        else:
            self.session.openWithCallback(self.iptvDoFinish, MessageBox, _("There are no other favourite groups"), type=MessageBox.TYPE_INFO, timeout=10)
        
    def addFavouriteToGroup(self, retArg):
        if retArg and 2 == len(retArg):
            if None != retArg[1]:
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
            else: # addn new group
                self.session.openWithCallback(self.addNewFavouriteGroup, IPTVFavouritesAddNewGroupWidget, self.favourites)
        else:
            self.iptvDoFinish()
                
    def addNewFavouriteGroup(self, group):
        if None != group:
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
    sz_w = getDesktop(0).size().width() - 190
    sz_h = getDesktop(0).size().height() - 195
    if sz_h < 500:
        sz_h += 4
    skin = """
        <screen name="IPTVFavouritesMainWidget" position="center,center" title="%s" size="%d,%d">
         <ePixmap position="5,9"   zPosition="4" size="30,30" pixmap="%s" transparent="1" alphatest="on" />
         <ePixmap position="335,9" zPosition="4" size="30,30" pixmap="%s" transparent="1" alphatest="on" />
         <ePixmap position="665,9" zPosition="4" size="30,30" pixmap="%s" transparent="1" alphatest="on" />
         
         <widget name="label_red"     position="45,9"  size="300,27" zPosition="5" valign="center" halign="left" backgroundColor="black" font="Regular;21" transparent="1" foregroundColor="white" shadowColor="black" shadowOffset="-1,-1" />
         <widget name="label_green"   position="375,9" size="300,27" zPosition="5" valign="center" halign="left" backgroundColor="black" font="Regular;21" transparent="1" foregroundColor="white" shadowColor="black" shadowOffset="-1,-1" />
         <widget name="label_yellow"  position="705,9" size="300,27" zPosition="5" valign="center" halign="left" backgroundColor="black" font="Regular;21" transparent="1" foregroundColor="white" shadowColor="black" shadowOffset="-1,-1" />

         <widget name="list"  position="5,80"  zPosition="2" size="%d,%d" scrollbarMode="showOnDemand" transparent="1"  backgroundColor="#00000000" enableWrapAround="1" />
         <widget name="title" position="5,47"  zPosition="1" size="%d,23" font="Regular;20"            transparent="1"  backgroundColor="#00000000"/>
        </screen>""" % (
            _("Favourites manager"),
            sz_w, sz_h, # size
            GetIconDir("red.png"),
            GetIconDir("green.png"),
            GetIconDir("yellow.png"),
            sz_w - 10, sz_h - 105, # size list
            sz_w - 135, # size title
            )
            
    def __init__(self, session):
        self.session = session
        Screen.__init__(self, session)
        
        self.onShown.append(self.onStart)
        self.onClose.append(self.__onClose)
        self.favourites = None
        self.started = False
        self.menu = ":groups:" # "items"
        self.modified = False
        
        self.IDS_ENABLE_REORDERING = _('Enable reordering')
        self.IDS_DISABLE_REORDERING = _('Disable reordering')
        self.reorderingMode = False
        
        self["title"] = Label(_("Favourites groups"))
        self["label_red"] = Label(_("Remove group"))
        self["label_yellow"] = Label(self.IDS_ENABLE_REORDERING)
        self["label_green"] = Label(_("Add new group"))
        
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
            self["title"].setText(_("Favourites groups"))
            self["label_red"].setText(_("Remove group"))
            self["label_green"].setText(_("Add new group"))
        
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
            if None != self.getSelectedItem():
                self._changeMode()
            return
        if ":groups:" == self.menu:
            sel = self.getSelectedItem()
            if None == sel:
                return
            
            self.menu = sel.privateData
            try:
                self["title"].setText(_("Items in group \"%s\"") % self.favourites.getGroup(self.menu)['title'])
            except Exception:
                printExc()
            self["label_red"].setText(_("Remove item"))
            self["label_green"].setText(_("Add item to group"))
            
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
        if None == sel:
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
        if None != self.getSelectedItem():
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
            if None == self.getSelectedItem():
                return
            if not self.loadGroupItems(self.menu):
                return 
            sts, items = self.favourites.getGroupItems(self.menu)
            if not sts:
                self.session.open(MessageBox, self.favourites.getLastError(), type=MessageBox.TYPE_ERROR, timeout=10)
                return
            favItem = items[self["list"].getCurrentIndex()]
            self.session.openWithCallback(self._itemCloned, IPTVFavouritesAddItemWidget, favItem, self.favourites, False, [self.menu])
            
    def _groupAdded(self, group):
        if None != group:
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
    
    
