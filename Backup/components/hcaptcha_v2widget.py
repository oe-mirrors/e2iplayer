# -*- coding: utf-8 -*-
#
#  Player Selector
#
#  $Id$
#
#
from Plugins.Extensions.IPTVPlayer.components.cover import Cover2
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, GetTmpDir
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.captchapuzzlegridwidget import CaptchaPuzzleGridWidgetBase


class UnCaptchahCaptchaWidget(CaptchaPuzzleGridWidgetBase):
    # the chrome/skin building and every grid-navigation method are
    # shared with the near-identical `UnCaptchaReCaptchaWidget` via
    # `CaptchaPuzzleGridWidgetBase` - see that file's own comment for
    # details. Only the genuinely different bit remains here: this screen
    # gets N separate already-downloaded images (one per cell, from fixed
    # tmp paths), unlike ReCaptchaV2's one image cut into the grid
    # visually.
    def __init__(self, session, hCaptcha, additionalParams={}):
        printDBG("UnCaptchahCaptchaWidget.__init__ --------------------------")

        self.params = additionalParams
        self.numOfImg = hCaptcha['imgNumber']

        # integer division: this value is fed straight into range() at 7
        # call sites (and used as a list index), both of which require an
        # int - a plain "/" here would crash with "TypeError: 'float'
        # object cannot be interpreted as an integer".
        # max(1, ...) guard: imgNumber comes straight from a live hCaptcha
        # API response (len(response["tasklist"])) with no lower-bound
        # guarantee - numOfImg < 3 would make numOfCol 0, crashing every
        # // and % by numOfCol in _buildPuzzleImageSkin() with
        # ZeroDivisionError.
        numOfCol = max(1, self.numOfImg // 3)
        numOfRow = 3
        markerWidth = self.params.get('marker_width', 100)
        markerHeight = self.params.get('marker_height', 100)
        acceptLabel = self.params.get('accep_label', _("Verify"))

        CaptchaPuzzleGridWidgetBase.__init__(self, session, "hCaptcha", hCaptcha['question'], acceptLabel, numOfRow, numOfCol, markerWidth, markerHeight, markerHeight * numOfRow)

    def __del__(self):
        printDBG("UnCaptchahCaptchaWidget.__del__ --------------------------")

    def _buildPuzzleImageSkin(self):
        parts = []
        for n_img in range(self.numOfImg):
            r = n_img // self.numOfCol
            c = n_img % self.numOfCol
            parts.append('<widget name="puzzle_image_%d" position="%d,%d" size="%d,%d" zPosition="3" transparent="1" alphatest="blend" />' % (
                n_img, self.offsetCoverX + c * self.markerWidth, self.offsetCoverY + r * self.markerHeight, self.markerWidth, self.markerHeight))
        return '\n'.join(parts)

    def _createPuzzleImageWidgets(self):
        for n_img in range(self.numOfImg):
            self['puzzle_image_%d' % n_img] = Cover2()

    def _loadPuzzleImages(self):
        for n_img in range(self.numOfImg):
            self['puzzle_image_%d' % n_img].updateIcon(GetTmpDir('.iptvplayer_hcaptcha_%d.jpg' % n_img))
