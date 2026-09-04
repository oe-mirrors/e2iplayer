# -*- coding: utf-8 -*-
#
# Shared base for the two "select the grid squares matching the puzzle"
# captcha widgets (UnCaptchaReCaptchaWidget - one image cut into a grid;
# UnCaptchahCaptchaWidget - N separate images, one per cell). Every
# grid-navigation method (keyLeft/keyRight/keyUp/keyDown/moveMarker/
# updateAccpetButton/calcMarkerPosX/calcMarkerPosY/keyCancel/keyOK/
# keyVerify) and the chrome/skin scaffolding (header/footer/statustext/
# accept/cover_XY markers) are identical between the two, and live here.
# Only how the actual puzzle image(s) are declared in skin XML and loaded
# at runtime genuinely differs (one `puzzle_image` widget spanning the
# whole grid vs `puzzle_image_0..N` widgets, one per cell) - kept as
# three small per-subclass hooks (`_buildPuzzleImageSkin()`/
# `_createPuzzleImageWidgets()`/`_loadPuzzleImages()`) rather than folded
# together.
from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from enigma import ePoint
from Tools.LoadPixmap import LoadPixmap
from Components.Label import Label
from skin import parseColor

from Plugins.Extensions.IPTVPlayer.components.cover import Cover3
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import GetIconDir
from Plugins.Extensions.IPTVPlayer.components import skinchrome


class CaptchaPuzzleGridWidgetBase(Screen):

    def __init__(self, session, windowTitle, statusText, acceptLabel, numOfRow, numOfCol, markerWidth, markerHeight, acceptRowSpan):
        self.numOfRow = numOfRow
        self.numOfCol = numOfCol
        self.markerWidth = markerWidth
        self.markerHeight = markerHeight
        self.offsetCoverX = 100
        # accept button's own Y offset below the grid - kept as a caller-
        # supplied value rather than derived here, since the two original
        # files actually used two different (and not obviously
        # equivalent) formulas: `markerWidth * numOfCol` in
        # UnCaptchaReCaptchaWidget vs `markerHeight * numOfRow` in
        # UnCaptchahCaptchaWidget. They only ever produce the same number
        # today because every real caller uses square 100x100 cells with
        # numOfCol == numOfRow (hCaptcha always has numOfRow=3 fixed and
        # numOfImg a multiple of 3) - preserved separately rather than
        # picking one and risking a silent behavior change if that ever
        # stops being true.
        self.acceptRowSpan = acceptRowSpan

        # `flags="wfNoBorder"` with a tiered `scale=` header/footer (not
        # `resolution=` auto-scale) - the puzzle grid itself is real
        # absolute pixels (`markerWidth`/`markerHeight`, a captcha image's
        # real cell size, unrelated to TV resolution), same reasoning as
        # E2iVirtualKeyBoard/E2iPlayerBufferingWidget: only the chrome
        # around it scales per device tier, the grid stays exactly the
        # size it always was so the captcha image itself never gets
        # blurrily upscaled.
        scale = skinchrome.getScale()
        iconBase = skinchrome.getIconBase()
        headerH = skinchrome.header_height(scale)
        footerH = skinchrome.footer_height(scale)
        # was a flat 100 (statustext's own row) - now also clears the new
        # header band above it, same "add the new band's height on top of
        # what already worked" approach as every other migrated screen
        self.offsetCoverY = headerH + 100

        windowWidth = self.markerWidth * self.numOfCol + self.offsetCoverX * 2
        windowHeight = self.markerWidth * self.numOfRow + self.offsetCoverY + 70 + footerH

        coversSkin = ''
        self.coversSelection = []
        for x in range(self.numOfCol):
            self.coversSelection.append([])
            for y in range(self.numOfRow):
                coversSkin += """<widget name="cover_%s%s" zPosition="5" position="%d,%d" size="%d,%d" transparent="1" alphatest="blend" />""" % (
                    x, y,
                    (self.offsetCoverX + self.markerWidth * x),  # pos X image
                    (self.offsetCoverY + self.markerHeight * y),  # pos Y image
                    self.markerWidth,
                    self.markerHeight
                )
                self.coversSelection[x].append(False)  # at start no icon is selected

        # footer: no color keys bound at all (only NAV/OK/EXIT are real -
        # arrow keys move the grid cursor, ok selects/accepts, back
        # cancels), so `keys=()`
        skin = ["""
        <screen position="center,center" size="%d,%d" title="%s" flags="wfNoBorder">""" % (windowWidth, windowHeight, windowTitle)]
        skin.append(skinchrome.build_header(scale=scale, iconBase=iconBase, showLogo=True))
        skin.append(skinchrome.build_footer(windowHeight, scale=scale, iconBase=iconBase, keys=(), showMenu=False, showNav=True, showNum=False, showOk=True, showExit=True))
        skin.append("""
            <widget name="statustext"   position="0,%d"  zPosition="2" size="%d,80"  valign="center" halign="center" font="Regular;22" transparent="1" />
            %s
            <widget name="marker"       position="%d,%d" size="%d,%d" zPosition="4" transparent="1" alphatest="blend" />
            <widget name="accept"       position="10,%d"  zPosition="2" size="%d,50"  valign="center" halign="center" font="Regular;22" foregroundColor="#FFFFFF" backgroundColor="#3A3A3A" />
            %s
        """ % (headerH + 10,
               windowWidth,
               self._buildPuzzleImageSkin(),
               self.offsetCoverX,
               self.offsetCoverY,
               self.markerWidth,
               self.markerHeight,
               self.offsetCoverY + self.acceptRowSpan + 10,
               windowWidth - 20,
               coversSkin))
        skin.append('</screen>')
        self.skin = '\n'.join(skin)

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

        self.markerPixmap = LoadPixmap(GetIconDir('PlayerSelector/marker/markerCaptchaV2.png'))
        self.selectPixmap = LoadPixmap(GetIconDir('PlayerSelector/marker/selectCaptchaV2.png'))

        self["statustext"] = Label(str(statusText))
        self["accept"] = Label(acceptLabel)

        self._createPuzzleImageWidgets()
        self["marker"] = Cover3()

        for x in range(self.numOfCol):
            for y in range(self.numOfRow):
                strIndex = "cover_%s%s" % (x, y)
                self[strIndex] = Cover3()

        self.currX = 0
        self.currY = 0
        self.focusOnAcceptButton = False
        self.onLayoutFinish.append(self.onStart)

    # --- puzzle-image hooks - see the subclasses for the two shapes ---
    def _buildPuzzleImageSkin(self):
        raise NotImplementedError

    def _createPuzzleImageWidgets(self):
        raise NotImplementedError

    def _loadPuzzleImages(self):
        raise NotImplementedError

    def onStart(self):
        self.onLayoutFinish.remove(self.onStart)
        self._loadPuzzleImages()
        self['marker'].setPixmap(self.markerPixmap)
        self['marker'].show()

        for x in range(self.numOfCol):
            for y in range(self.numOfRow):
                strIndex = "cover_%s%s" % (x, y)
                self[strIndex].setPixmap(self.selectPixmap)
                self[strIndex].hide()

    def updateAccpetButton(self):
        if self.focusOnAcceptButton and self.currY < self.numOfRow:
            # a plain, fully-opaque mid-gray ("#3A3A3A") - a translucent
            # near-black would blend into dark video content behind it
            # and become unreadable, unlike this plain 6-digit hex style
            # (matching the "#32CD32"/"#000000" focused-state pair right
            # below).
            self['accept'].instance.setForegroundColor(parseColor("#FFFFFF"))
            self['accept'].instance.setBackgroundColor(parseColor("#3A3A3A"))
            self.focusOnAcceptButton = False
            self['marker'].show()
        elif self.currY >= self.numOfRow:
            self['accept'].instance.setForegroundColor(parseColor("#000000"))
            self['accept'].instance.setBackgroundColor(parseColor("#32CD32"))
            self.focusOnAcceptButton = True
            self['marker'].hide()
        return self.focusOnAcceptButton

    # Calculate marker position Y
    def calcMarkerPosY(self):
        if self.currY > (self.numOfRow + 1 - 1):
            self.currY = 0
        elif self.currY < 0:
            self.currY = (self.numOfRow + 1 - 1)
        return

    # Calculate marker position X
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
        x = int(self.offsetCoverX + self.markerWidth * self.currX)
        y = int(self.offsetCoverY + self.markerHeight * self.currY)
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
