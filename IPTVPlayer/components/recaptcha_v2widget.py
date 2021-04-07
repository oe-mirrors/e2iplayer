# -*- coding: utf-8 -*-
#
#  Player Selector
#
#  $Id$
#
# 
from Screens.Screen import Screen
from Components.ActionMap import ActionMap, HelpableActionMap
from enigma import ePoint
from Tools.LoadPixmap import LoadPixmap
from Components.Label import Label
from skin import parseColor

from Plugins.Extensions.IPTVPlayer.components.cover import Cover2, Cover3
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, GetIconDir


class UnCaptchaReCaptchaWidget(Screen):
    
    def __init__(self, session, imgFilePath, message, title, additionalParams={}):
        printDBG("UnCaptchaReCaptchaWidget.__init__ --------------------------")
        
        self.params = additionalParams
        self.imgFilePath = imgFilePath
        self.numOfRow = self.params.get('rows', 3)
        self.numOfCol = self.params.get('cols', 3)
        self.markerWidth = self.params.get('marker_width', 100)
        self.markerHeight = self.params.get('marker_height', 100)
        self.offsetCoverX = 100
        self.offsetCoverY = 100
        
        windowWidth = self.markerWidth * self.numOfCol + self.offsetCoverX * 2
        windowHeight = self.markerWidth * self.numOfRow + self.offsetCoverY + 70
        

        coversSkin = ''
        self.coversSelection = []
        for x in range(self.numOfCol):
            self.coversSelection.append([])
            for y in range(self.numOfRow):
                coversSkin += """<widget name="cover_%s%s" zPosition="5" position="%d,%d" size="%d,%d" transparent="1" alphatest="blend" />""" % (x, y, 
                    (self.offsetCoverX + self.markerWidth * x), # pos X image
                    (self.offsetCoverY + self.markerHeight * y), # pos Y image
                    self.markerWidth, 
                    self.markerHeight
                )
                self.coversSelection[x].append(False) # at start no icon is selected
                
        self.skin = """
        <screen position="center,center" size="%d,%d" title="%s">
            <widget name="statustext"   position="0,10"  zPosition="2" size="%d,80"  valign="center" halign="center" font="Regular;22" transparent="1" />
            <widget name="puzzle_image" position="%d,%d" size="%d,%d" zPosition="3" transparent="1" alphatest="blend" />
            <widget name="marker"       position="%d,%d" size="%d,%d" zPosition="4" transparent="1" alphatest="blend" />
            <widget name="accept"       position="10,%d"  zPosition="2" size="%d,50"  valign="center" halign="center" font="Regular;22" foregroundColor="#00FFFFFF" backgroundColor="#FFFFFFFF" />
            %s
        </screen>
        """ % (windowWidth, 
               windowHeight, 
               title,
               windowWidth,
               self.offsetCoverX, # puzzle x
               self.offsetCoverY, # puzzle y
               self.markerWidth * self.numOfCol, # puzzle image width
               self.markerHeight * self.numOfRow, # puzzle image height
               self.offsetCoverX,
               self.offsetCoverY,
               self.markerWidth,
               self.markerHeight,
               self.offsetCoverY + self.markerWidth * self.numOfCol + 10,
               windowWidth - 20,
               coversSkin)
        
        self.session = session
        Screen.__init__(self, session)
        
        self["actions"] = ActionMap(["WizardActions", "DirectionActions", "ColorActions"],
        {
            "left": self.keyLeft,
            "right": self.keyRight,
            "up": self.keyUp,
            "down": self.keyDown,
            "ok": self.keyOK,
            "back": self.keyCancel,
        }, -1)
        
        self.markerPixmap = LoadPixmap(GetIconDir('markerCaptchaV2.png'))
        self.selectPixmap = LoadPixmap(GetIconDir('selectCaptchaV2.png'))
        
        self["statustext"] = Label(str(message))
        self["accept"] = Label(self.params.get('accep_label', _("Verify")))
        
        self['puzzle_image'] = Cover2()
        self["marker"] = Cover3()
        
        for x in range(self.numOfCol):
            for y in range(self.numOfRow):
                strIndex = "cover_%s%s" % (x, y)
                self[strIndex] = Cover3()
                
        self.currX = 0
        self.currY = 0
        self.focusOnAcceptButton = False
        self.onLayoutFinish.append(self.onStart)
        
    def __del__(self):
        printDBG("UnCaptchaReCaptchaWidget.__del__ --------------------------")    
        
    def onStart(self):
        self.onLayoutFinish.remove(self.onStart)
        self['puzzle_image'].updateIcon(self.imgFilePath)
        self['marker'].setPixmap(self.markerPixmap)
        self['marker'].show()
        
        for x in range(self.numOfCol):
            for y in range(self.numOfRow):
                strIndex = "cover_%s%s" % (x, y)
                self[strIndex].setPixmap(self.selectPixmap)
                self[strIndex].hide()
                
    def updateAccpetButton(self):
        if self.focusOnAcceptButton and self.currY < self.numOfRow:
            self['accept'].instance.setForegroundColor(parseColor("#FFFFFF"))
            self['accept'].instance.setBackgroundColor(parseColor("#FFFFFFFF"))
            self.focusOnAcceptButton = False
            self['marker'].show()
        elif self.currY >= self.numOfRow:
            self['accept'].instance.setForegroundColor(parseColor("#000000"))
            self['accept'].instance.setBackgroundColor(parseColor("#32CD32"))
            self.focusOnAcceptButton = True
            self['marker'].hide()
        return self.focusOnAcceptButton

    #Calculate marker position Y
    def calcMarkerPosY(self):
        if self.currY > (self.numOfRow + 1 - 1):
            self.currY = 0
        elif self.currY < 0:
            self.currY = (self.numOfRow + 1 - 1)
        return

    #Calculate marker position X
    def calcMarkerPosX(self):
        if self.currX > (self.numOfCol - 1):
            self.currX = 0
        elif self.currX < 0:
            self.currX = self.numOfCol - 1
        return
        
    def keyRight(self):
        self.currX += 1
        self.calcMarkerPosX()
        self.moveMarker()
        return
    def keyLeft(self):
        self.currX -= 1
        self.calcMarkerPosX()
        self.moveMarker()
        return

    def keyDown(self):
        self.currY += 1
        self.calcMarkerPosY()
        self.moveMarker()
        return
    def keyUp(self):
        self.currY -= 1
        self.calcMarkerPosY()
        self.moveMarker()
        return
    
    def moveMarker(self):
        if self.updateAccpetButton():
            return
        # calculate position of image
        x = self.offsetCoverX + self.markerWidth * self.currX
        y = self.offsetCoverY + self.markerHeight * self.currY
        self["marker"].instance.move(ePoint(x, y))
        return

    def keyCancel(self):
        self.close(None)
        return

    def keyOK(self):
        if self.updateAccpetButton():
            self.keyVerify()
            return
        
        strIndex = "cover_%s%s" % (self.currX, self.currY)
        self.coversSelection[self.currX][self.currY] = not self.coversSelection[self.currX][self.currY]
        if self.coversSelection[self.currX][self.currY]:
            self[strIndex].show()
        else:
            self[strIndex].hide()
        return
        
    def keyVerify(self):
        retList = []
        # order of iteration must be: from left to do right, from top to bottom
        num = 0
        for y in range(self.numOfRow):
            for x in range(self.numOfCol):
                if self.coversSelection[x][y]:
                    retList.append(num)
                num += 1
        self.close(retList)
