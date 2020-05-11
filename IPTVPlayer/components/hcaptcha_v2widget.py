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
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, GetIconDir, GetTmpDir, GetCookieDir

class UnCaptchahCaptchaWidget(Screen):
    
    def __init__(self, session, hCaptcha, additionalParams = {}):
        printDBG("UnCaptchahCaptchaWidget.__init__ --------------------------")
        
        self.params = additionalParams
        self.imgFilePath = GetTmpDir('.iptvplayer_hcaptcha_0.jpg')
        self.numOfImg = hCaptcha['imgNumber']

        self.numOfCol = self.numOfImg / 3
        self.numOfRow = 3 

        self.markerWidth  = self.params.get('marker_width', 100)
        self.markerHeight = self.params.get('marker_height', 100)
        self.offsetCoverX = 100
        self.offsetCoverY = 100
        
        windowWidth  = self.markerWidth * self.numOfCol + self.offsetCoverX * 2
        windowHeight = self.markerWidth * self.numOfRow + self.offsetCoverY + 70
        

        coversSkin = ''
        self.coversSelection = []
        for x in range(self.numOfCol):
            self.coversSelection.append([])
            for y in range(self.numOfRow):
                coversSkin += """<widget name="cover_%s%s" zPosition="5" position="%d,%d" size="%d,%d" transparent="1" alphatest="blend" />""" % (x, y, 
                    (self.offsetCoverX + self.markerWidth  * x ), # pos X image
                    (self.offsetCoverY + self.markerHeight * y ), # pos Y image
                    self.markerWidth, 
                    self.markerHeight
                )
                self.coversSelection[x].append(False) # at start no icon is selected
        
        
        skin_puzzle_part=""
        for n_img in range(self.numOfImg):
            r = n_img / self.numOfCol
            c = n_img % self.numOfCol
            skin_puzzle_part+= "            <widget name=\"puzzle_image_%d\" position=\"%d,%d\" size=\"%d,%d\" zPosition=\"3\" transparent=\"1\" alphatest=\"blend\" />\n" % (n_img, self.offsetCoverX + c * self.markerWidth, self.offsetCoverY + r * self.markerHeight,self.markerWidth, self.markerHeight)

        
        self.skin = """
        <screen position="center,center" size="%d,%d" title="%s">
            <widget name="statustext"   position="0,10"  zPosition="2" size="%d,80"  valign="center" halign="center" font="Regular;22" transparent="1" />
#puzzle_part#
            <widget name="marker"       position="%d,%d" size="%d,%d" zPosition="4" transparent="1" alphatest="blend" />
            <widget name="accept"       position="10,%d"  zPosition="2" size="%d,50"  valign="center" halign="center" font="Regular;22" foregroundColor="#00FFFFFF" backgroundColor="#FFFFFFFF" />
            %s
        </screen>
        """ % (windowWidth, 
               windowHeight, 
               "hCaptcha",
               windowWidth,
               self.offsetCoverX,
               self.offsetCoverY,
               self.markerWidth,
               self.markerHeight,
               self.offsetCoverY + self.markerHeight * self.numOfRow + 10,
               windowWidth-20,
               coversSkin)

        self.skin=self.skin.replace("#puzzle_part#", skin_puzzle_part)
        self.session = session
        Screen.__init__(self, session)
        
        self["actions"] = ActionMap(["WizardActions", "DirectionActions", "ColorActions"],
        {
            "left"  : self.keyLeft,
            "right" : self.keyRight,
            "up"    : self.keyUp,
            "down"  : self.keyDown,
            "ok"    : self.keyOK,
            "back"  : self.keyCancel,
        }, -1)
        
        self.markerPixmap = LoadPixmap(GetIconDir('markerCaptchaV2.png'))
        self.selectPixmap = LoadPixmap(GetIconDir('selectCaptchaV2.png'))
        
        self["statustext"] = Label(str(hCaptcha['question']))
        self["accept"] = Label(self.params.get('accep_label', _("Verify")))
        
        for n_img in range(self.numOfImg):
            self['puzzle_image_%d' % n_img] = Cover2()
 
        self["marker"]       = Cover3()
        
        for x in range(self.numOfCol):
            for y in range(self.numOfRow):
                strIndex = "cover_%s%s" % (x,y)
                self[strIndex] = Cover3()
                
        self.currX = 0
        self.currY = 0
        self.focusOnAcceptButton = False
        self.onLayoutFinish.append(self.onStart)
        
    def __del__(self):
        printDBG("UnCaptchahCaptchaWidget.__del__ --------------------------")    
        
    def onStart(self):
        self.onLayoutFinish.remove(self.onStart)
        
        for n_img in range(self.numOfImg):
            self['puzzle_image_%d' % n_img].updateIcon( GetTmpDir('.iptvplayer_hcaptcha_%d.jpg' % n_img))
        self['marker'].setPixmap(self.markerPixmap)
        self['marker'].show()
        
        for x in range(self.numOfCol):
            for y in range(self.numOfRow):
                strIndex = "cover_%s%s" % (x,y)
                self[strIndex].setPixmap(self.selectPixmap)
                self[strIndex].hide()
                
    def updateAccpetButton(self):
        if self.focusOnAcceptButton and self.currY < self.numOfRow:
            self['accept'].instance.setForegroundColor( parseColor("#FFFFFF") )
            self['accept'].instance.setBackgroundColor( parseColor("#FFFFFFFF") )
            self.focusOnAcceptButton = False
            self['marker'].show()
        elif self.currY >= self.numOfRow:
            self['accept'].instance.setForegroundColor( parseColor("#000000") )
            self['accept'].instance.setBackgroundColor( parseColor("#32CD32") )
            self.focusOnAcceptButton = True
            self['marker'].hide()
        return self.focusOnAcceptButton

    #Calculate marker position Y
    def calcMarkerPosY(self):
        if self.currY >  (self.numOfRow+1 - 1):
            self.currY = 0
        elif self.currY < 0:
            self.currY = (self.numOfRow+1 - 1)
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
        if self.updateAccpetButton(): return
        # calculate position of image
        x = self.offsetCoverX + self.markerWidth * self.currX
        y = self.offsetCoverY + self.markerHeight * self.currY
        self["marker"].instance.move(ePoint(x,y))
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
