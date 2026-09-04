# -*- coding: utf-8 -*-
#
#  Player Selector
#
#  $Id$
#
#
from Plugins.Extensions.IPTVPlayer.components.cover import Cover2
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.captchapuzzlegridwidget import CaptchaPuzzleGridWidgetBase


class UnCaptchaReCaptchaWidget(CaptchaPuzzleGridWidgetBase):
    # the chrome/skin building and every grid-navigation method are
    # shared with the near-identical `UnCaptchahCaptchaWidget` via
    # `CaptchaPuzzleGridWidgetBase` - see that file's own comment for
    # details. Only the genuinely different bit remains here: this screen
    # gets ONE already-downloaded puzzle image and cuts it into the grid
    # visually via `puzzle_image`'s own size (`markerWidth*numOfCol` x
    # `markerHeight*numOfRow`), unlike hCaptcha's N separate images.
    def __init__(self, session, imgFilePath, message, title, additionalParams={}):
        printDBG("UnCaptchaReCaptchaWidget.__init__ --------------------------")

        self.params = additionalParams
        self.imgFilePath = imgFilePath
        numOfRow = self.params.get('rows', 3)
        numOfCol = self.params.get('cols', 3)
        markerWidth = self.params.get('marker_width', 100)
        markerHeight = self.params.get('marker_height', 100)
        acceptLabel = self.params.get('accep_label', _("Verify"))

        CaptchaPuzzleGridWidgetBase.__init__(self, session, title, message, acceptLabel, numOfRow, numOfCol, markerWidth, markerHeight, markerWidth * numOfCol)

    def __del__(self):
        printDBG("UnCaptchaReCaptchaWidget.__del__ --------------------------")

    def _buildPuzzleImageSkin(self):
        return '<widget name="puzzle_image" position="%d,%d" size="%d,%d" zPosition="3" transparent="1" alphatest="blend" />' % (
            self.offsetCoverX,  # puzzle x
            self.offsetCoverY,  # puzzle y
            self.markerWidth * self.numOfCol,  # puzzle image width
            self.markerHeight * self.numOfRow,  # puzzle image height
        )

    def _createPuzzleImageWidgets(self):
        self['puzzle_image'] = Cover2()

    def _loadPuzzleImages(self):
        self['puzzle_image'].updateIcon(self.imgFilePath)
