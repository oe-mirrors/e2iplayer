# -*- coding: utf-8 -*-
#
#  Player Selector
#
#  $Id$
#
# 
from Screens.Screen import Screen
from Components.ActionMap import ActionMap, HelpableActionMap
from enigma import ePoint, getDesktop
from Tools.LoadPixmap import LoadPixmap
from Components.Label import Label
from Components.config import config
from Screens.MessageBox import MessageBox
from Screens.ChoiceBox import ChoiceBox

from Plugins.Extensions.IPTVPlayer.components.cover import Cover3
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIPTVPlayerVerstion, GetIconDir, GetAvailableIconSize
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _

class PlayerSelectorWidget(Screen):
    LAST_SELECTION = {}
    def __init__(self, session, inList, outList, numOfLockedItems=0, groupName='', groupObj=None):
        printDBG("PlayerSelectorWidget.__init__ --------------------------------")
        screenwidth = getDesktop(0).size().width()
        iconSize = GetAvailableIconSize()
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
        offsetMarkerX = offsetCoverX - (markerWidth - coverWidth) / 2
        offsetMarkerY = offsetCoverY - (markerHeight - coverHeight) / 2
        
        # how to calculate position of image with indexes indxX, indxY:
        #posX = offsetCoverX + (coverWidth + disWidth) * indxX
        #posY = offsetCoverY + (coverHeight + disHeight) * indxY
        
        # how to calculate position of marker for image with posX, posY
        #markerPosX = posX - (markerWidth - coverWidth)/2
        #markerPosY = posY - (markerHeight - coverHeight)/2
        
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
        
        self.inList = list(inList)
        self.currList = self.inList
        self.outList = outList

        self.groupName = groupName
        self.groupObj = groupObj
        self.numOfLockedItems = numOfLockedItems
        
        self.IconsSize = iconSize #do ladowania ikon
        self.MarkerSize = self.IconsSize + 45
        
        self.lastSelection = PlayerSelectorWidget.LAST_SELECTION.get(self.groupName, 0)
        self.calcDisplayVariables()
        
        # pagination 
        self.pageItemSize = 16
        self.pageItemStartX = (offsetCoverX + tmpX * numOfCol + offsetCoverX - disWidth - self.numOfPages * self.pageItemSize) / 2
        if screenwidth and screenwidth == 1920:
            self.pageItemStartY = 60
        else:
            self.pageItemStartY = 40

        if screenwidth and screenwidth == 1920:
            skin = """
            <screen name="IPTVPlayerPlayerSelectorWidget" position="center,center" title="E2iPlayer %s" size="%d,%d">
            <widget name="statustext" position="0,0" zPosition="1" size="%d,50" font="Regular;36" halign="center" valign="center" transparent="1"/>
            <widget name="marker" zPosition="2" position="%d,%d" size="%d,%d" transparent="1" alphatest="blend" />
            <widget name="page_marker" zPosition="3" position="%d,%d" size="%d,%d" transparent="1" alphatest="blend" />
            <widget name="menu" zPosition="3" position="%d,10" size="70,30" transparent="1" alphatest="blend" />
            """ % (
              GetIPTVPlayerVerstion(),
              offsetCoverX + tmpX * numOfCol + offsetCoverX - disWidth,  # width of window
              offsetCoverY + tmpY * numOfRow + offsetCoverX - disHeight, # height of window
              offsetCoverX + tmpX * numOfCol + offsetCoverX - disWidth,  # width of status line
              offsetMarkerX, offsetMarkerY, # first marker position
              markerWidth, markerHeight,    # marker size
              self.pageItemStartX, self.pageItemStartY, # pagination marker
              self.pageItemSize, self.pageItemSize,
              offsetCoverX + tmpX * numOfCol + offsetCoverX - disWidth - 70,
              )  
        else:
            skin = """
            <screen name="IPTVPlayerPlayerSelectorWidget" position="center,center" title="E2iPlayer %s" size="%d,%d">
            <widget name="statustext" position="0,0" zPosition="1" size="%d,50" font="Regular;26" halign="center" valign="center" transparent="1"/>
            <widget name="marker" zPosition="2" position="%d,%d" size="%d,%d" transparent="1" alphatest="blend" />
            <widget name="page_marker" zPosition="3" position="%d,%d" size="%d,%d" transparent="1" alphatest="blend" />
            <widget name="menu" zPosition="3" position="%d,10" size="70,30" transparent="1" alphatest="blend" />
            """ % (
              GetIPTVPlayerVerstion(),
              offsetCoverX + tmpX * numOfCol + offsetCoverX - disWidth,  # width of window
              offsetCoverY + tmpY * numOfRow + offsetCoverX - disHeight, # height of window
              offsetCoverX + tmpX * numOfCol + offsetCoverX - disWidth,  # width of status line
              offsetMarkerX, offsetMarkerY, # first marker position
              markerWidth, markerHeight,    # marker size
              self.pageItemStartX, self.pageItemStartY, # pagination marker
              self.pageItemSize, self.pageItemSize,
              offsetCoverX + tmpX * numOfCol + offsetCoverX - disWidth - 70,
              )
        
        for y in range(1, numOfRow + 1):
            for x in range(1, numOfCol + 1):
                skinCoverLine = """<widget name="cover_%s%s" zPosition="4" position="%d,%d" size="%d,%d" transparent="1" alphatest="blend" />""" % (x, y, 
                    (offsetCoverX + tmpX * (x - 1)), # pos X image
                    (offsetCoverY + tmpY * (y - 1)), # pos Y image
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
            
        self.session = session
        Screen.__init__(self, session)
        
        self.session.nav.event.append(self.__event)
        self.onClose.append(self.__onClose)
        
        # load icons
        self.pixmapList = []
        for idx in range(0, self.numOfItems):
            self.pixmapList.append(LoadPixmap(GetIconDir('PlayerSelector/' + self.currList[idx][1] + '%i.png' % self.IconsSize)))

        self.markerPixmap = LoadPixmap(GetIconDir('PlayerSelector/marker%i.png' % self.MarkerSize))
        self.markerPixmapSel = LoadPixmap(GetIconDir('PlayerSelector/markerSel%i.png' % self.MarkerSize))
        self.pageMarkerPixmap = LoadPixmap(GetIconDir('radio_button_on.png'))
        self.menuPixmap = LoadPixmap(GetIconDir('menu.png'))
        
        self["actions"] = ActionMap(["WizardActions", "DirectionActions", "ColorActions", "IPTVPlayerListActions"],
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
        self["menu"] = Cover3()
        
        
        for y in range(1, self.numOfRow + 1):
            for x in range(1, self.numOfCol + 1):
                strIndex = "cover_%s%s" % (x, y)
                self[strIndex] = Cover3()
                
        self["statustext"] = Label(self.currList[0][0])
    
        self.onLayoutFinish.append(self.onStart)
        self.visible = True
        self.reorderingMode = False
        self.reorderingItemSelected = False
        
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
        idx = self.currLine * self.numOfCol + self.dispX
        printDBG(">>>>>>>>>>>>>>>>>>>>>>>>>>> __onClose idx[%s]" % idx)
        PlayerSelectorWidget.LAST_SELECTION[self.groupName] = idx
    
    #Calculate marker position Y
    def calcMarkerPosY(self):
        
        if self.currLine > (self.numOfLines - 1):
            self.currLine = 0
        elif self.currLine < 0:
            self.currLine = (self.numOfLines - 1)
        
        # calculate new page number 
        newPage = self.currLine / self.numOfRow
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

    #Calculate marker position X
    def calcMarkerPosX(self):
        if self.currLine == self.numOfLines - 1:
            #calculate num of item in last line
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
        self.numOfLines = self.numOfItems / self.numOfCol
        if self.numOfItems % self.numOfCol > 0:
            self.numOfLines += 1

        # numbers of pages
        self.numOfPages = self.numOfLines / self.numOfRow
        if self.numOfLines % self.numOfRow > 0:
            self.numOfPages += 1

        self.currPage = 0
        self.currLine = 0

        self.dispX = 0
        self.dispY = 0
        
    def updateIconsList(self, rangeList):
        idx = self.currPage * (self.numOfCol * self.numOfRow)
        for y in range(1, self.numOfRow + 1):
            for x in range(1, self.numOfCol + 1):
                if idx >= rangeList[0] and idx <= rangeList[1]:
                    strIndex = "cover_%s%s" % (x, y)
                    printDBG("updateIconsList [%s]" % strIndex)
                    self[strIndex].setPixmap(self.pixmapList[idx])
                idx += 1
    
    def updateIcons(self):
        idx = self.currPage * (self.numOfCol * self.numOfRow)
        for y in range(1, self.numOfRow + 1):
            for x in range(1, self.numOfCol + 1):
                strIndex = "cover_%s%s" % (x, y)
                printDBG("updateIcon for self[%s]" % strIndex)
                if idx < self.numOfItems:
                    #self[strIndex].updateIcon( resolveFilename(SCOPE_PLUGINS, 'Extensions/IPTVPlayer/icons/PlayerSelector/' + self.currList[idx][1] + '.png'))
                    self[strIndex].setPixmap(self.pixmapList[idx])
                    self[strIndex].show()
                    idx += 1
                else:
                    self[strIndex].hide()
        x = self.pageItemStartX + self.currPage * self.pageItemSize
        y = self.pageItemStartY
        self["page_marker"].instance.move(ePoint(x, y))
        
    def setIdx(self, selIdx):
        if selIdx > self.numOfItems:
            selIdx = self.numOfItems
    
        self.dispX = selIdx % self.numOfCol
        self.currLine = selIdx / self.numOfCol
        
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
        new_idx = self.currLine * self.numOfCol + self.dispX
        
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
        x = imgPosX - (self.markerWidth - self.coverWidth) / 2
        y = imgPosY - (self.markerHeight - self.coverHeight) / 2
        
        #x =  30 + self.dispX * 180
        #y = 130 + self.dispY * 125
        self["marker"].instance.move(ePoint(x, y))
        self["statustext"].setText(self.currList[new_idx][0])
        return
        
    def getSelectedItem(self):
        printDBG(">> PlayerSelectorWidget.getSelectedItem")
        idx = self.currLine * self.numOfCol + self.dispX
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
        
        idx = self.currLine * self.numOfCol + self.dispX
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
        if self.groupObj != None and selItem != None and len(self.groupObj.getGroupsWithoutHost(selItem[1])):
            options.append((_("Add host %s to group") % selItem[0], "ADD_HOST_TO_GROUP"))
        
        if not self.reorderingMode and self.numOfItems - self.numOfLockedItems > 0:
            options.append((_("Enable reordering mode"), "CHANGE_REORDERING_MODE"))
        elif self.reorderingMode:
            options.append((_("Disable reordering mode"), "CHANGE_REORDERING_MODE"))
        options.append((_("Download manager"), "IPTVDM"))
        if self.groupName in ['selecthost', 'all']:
            options.append((_("Disable/Enable services"), "config_hosts"))
        if self.groupName in ['selectgroup']:
            options.append((_("Disable/Enable groups"), "config_groups"))
        
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
                idx = self.currLine * self.numOfCol + self.dispX
                if idx < self.numOfItems:
                    del self.currList[idx]
                    del self.pixmapList[idx]
                    self.reInitDisplayList()
    
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
