# -*- coding: utf-8 -*-
#

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.iptvlist import IPTVRadioButtonList
###################################################

###################################################
# FOREIGN import
###################################################
from Screens.Screen import Screen
from Components.Label import Label
from Components.ActionMap import ActionMap
from enigma import getDesktop
###################################################


class IPTVChoiceBoxItem:
    TYPE_ON = "on"
    TYPE_OFF = "off"
    TYPE_NONE = None

    def __init__(self, name="",
                 description="",
                 privateData=None,
                 type=TYPE_NONE,
                 failed=False):
        self.name = name
        self.description = description
        self.type = type
        self.privateData = privateData
        self.failed = failed


class IPTVChoiceBoxWidget(Screen):

    def __prepareSkin(self):
        width = self.params.get('width', 300)
        height = self.params.get('height', 300)

        # Pure info dialogs (no per-row action, e.g. the OSK's Help screen)
        # pass selectable=False so moving through rows doesn't paint them as
        # if they were a real, actionable selection. The list itself is
        # transparent="1", so the only way to make the selected row actually
        # disappear is to match the screen's own (translucent) backgroundColor
        # exactly - an opaque color like plain "black" still shows up as a
        # solid bar against that translucent backdrop.
        if self.params.get('selectable', True):
            selColors = 'foregroundColorSelected="white" backgroundColorSelected="#1b5a91"'
        else:
            selColors = 'foregroundColorSelected="white" backgroundColorSelected="#34111112"'

        if self.params.get('chrome', False):
            # Opt-in: the logo/title bar + OK/EXIT footer bar used across the
            # rest of the player (iptvplayerwidget.py, iptvdmui.py, ...)
            # instead of this widget's own plain title-only look. Existing
            # callers (movie player / mirror pickers) don't pass this, so
            # they keep today's appearance unless they ask for it too.
            footerY = height - 48
            iconY = height - 37
            # "e" in a size="...,e-N" is the container's full height, NOT
            # reduced by the widget's own y position first - so a list at
            # position="5,66" needs N >= 66 (its own top offset) + 48 (footer
            # height) = 114 just to end exactly where the footer begins, not
            # 48 like a naive "container height minus footer" reading would
            # suggest. 150 (36 more than that minimum) is MENU/INFO's default:
            # extra-safe since their height is calculated to fit their
            # content exactly. Content that's always scrollable regardless
            # (the language picker) can pass a footerMargin closer to that
            # 114 floor instead, to avoid a big empty gap above the footer.
            footerMargin = self.params.get('footerMargin', 150)
            # This skin has a single, unscaled set of coordinates (relying on
            # resolution="1280,720" to auto-scale position/size for FHD/WQHD)
            # but the icon PIXMAPS themselves don't get auto-scaled - only
            # the box they're stretched into does. Using the tiny HD source
            # everywhere left icons soft at FHD/WQHD, so pick the higher-res
            # FHD source there instead (matching playerselector.py's own
            # per-tier icon choice) - the box size stays exactly as declared
            # below, only the source file changes.
            screenwidth = getDesktop(0).size().width()
            iconTier = "FHD" if screenwidth and screenwidth >= 1920 else "HD"
            iconBase = "/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/%s" % iconTier

            # The blue-key hint is only added when a caller opts in. It's
            # built as a plain ePixmap+Label pair (like OK/EXIT below)
            # rather than a source="key_blue"/render="Pixmap" widget with
            # ConditionalShowHide: that Source/Renderer/Converter combo was
            # tried first, but on real hardware its Pixmap content scaled
            # inconsistently across resolutions (measured too big at HD,
            # roughly right at FHD, too small at WQHD) even though its
            # position/size auto-scaled correctly - ePixmap+scale="1" is the
            # same mechanism OK/EXIT already use here and is proven correct
            # at all three tiers, so visibility is decided in Python instead
            # (include the block or don't) rather than at runtime in skin.
            blueBlock = ""
            if callable(self.params.get('blue_callback')):
                # OK/EXIT below are 40x26 boxes at y=iconY (not footerY - the
                # 26-tall box centers 3px lower than a 20-tall box at the
                # same y would). The label box matches OK/EXIT's own height
                # (26), so it uses iconY unchanged to land on the same
                # center; the icon is 20 tall, so it needs +3 to match.
                blueBlock = """
                    <ePixmap position="138,%d" size="20,20" scale="1" zPosition="10" pixmap="%s/blue.png" transparent="1" alphatest="blend" />
                    <widget name="key_blue_label" position="163,%d" size="e-173,26" backgroundColor="#000000" font="Regular;17" foregroundColor="#ffffff" zPosition="10" valign="center" halign="left" transparent="1" />""" % (iconY + 3, iconBase, iconY)
            skin = """
                <screen name="IPTVChoiceBoxWidget" position="center,center" resolution="1280,720" title="%s" size="%d,%d" backgroundColor="#34111112" flags="wfNoBorder">
                    <eLabel name="BG_Title" position="0,0" size="e,60" backgroundColor="#100d0f16" zPosition="-1" />
                    <eLabel name="BG_Buttons" position="0,%d" size="e,48" backgroundColor="#100d0f16" zPosition="-1" />
                    <ePixmap pixmap="%s/iptvlogo.png" position="12,10" size="100,40" scale="1" alphatest="blend" transparent="1" zPosition="1" />
                    <ePixmap pixmap="%s/smallshadowline.png" position="0,60" size="e,2" scale="1" zPosition="2" />
                    <ePixmap pixmap="%s/smallshadowline.png" position="0,%d" size="e,2" scale="1" zPosition="2" />
                    <ePixmap position="22,%d" size="40,26" scale="1" zPosition="10" pixmap="%s/ok.png" transparent="1" alphatest="blend" />
                    <ePixmap position="80,%d" size="40,26" scale="1" zPosition="10" pixmap="%s/exit.png" transparent="1" alphatest="blend" />%s
                    <widget name="title" position="122,14" size="e-132,30" foregroundColor="#0066ccff" backgroundColor="black" borderWidth="1" borderColor="black" transparent="1" zPosition="1" font="Regular;24" valign="center" />
                    <widget name="list"  position="5,66"  zPosition="2" size="e-10,e-%d" scrollbarMode="showAlways" scrollbarSliderBorderWidth="1" scrollbarForegroundColor="#1b5a91" scrollbarBorderColor="#00b6b6b6" enableWrapAround="1" transparent="1" foregroundColor="white" backgroundColor="black" %s borderWidth="1" borderColor="black"/>
                </screen>""" % (
                self.params.get('title', _("Select option")),
                width, height,
                footerY,
                iconBase,
                iconBase,
                iconBase, footerY,
                iconY, iconBase,
                iconY, iconBase,
                blueBlock,
                footerMargin,
                selColors
            )
        else:
            skin = """
                <screen name="IPTVChoiceBoxWidget" position="center,center" resolution="1280,720" title="%s" size="%d,%d" backgroundColor="#34111112" flags="wfNoBorder">
                    <eLabel name="BG_Title" position="0,0" size="1000,50" backgroundColor="#100d0f16" zPosition="-1" />
                    <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/smallshadowline.png" position="0,50" size="e,2" zPosition="2" />
                    <widget name="title" position="10,14" size="e-10,30" foregroundColor="#0066ccff" backgroundColor="black" borderWidth="1" borderColor="black" transparent="1" zPosition="1" font="Regular;24" valign="center" />
                    <widget name="list"  position="5,60"  zPosition="2" size="e-10,e-50" scrollbarMode="showOnDemand" scrollbarSliderBorderWidth="1" scrollbarForegroundColor="#1b5a91" scrollbarBorderColor="#00b6b6b6" enableWrapAround="1" transparent="1" foregroundColor="white" backgroundColor="black" %s borderWidth="1" borderColor="black"/>
                </screen>""" % (
                self.params.get('title', _("Select option")),
                width, height,             # size of screen
                selColors
            )
        return skin

    def __init__(self, session, params={'width': 300, 'height': 300, 'title': '', 'current_idx': 0, 'options': []}):
        self.params = params
        self.skin = self.__prepareSkin()
        Screen.__init__(self, session)
        self.skinName = ["IPTVChoiceBoxScreen", "IPTVChoiceBoxWidget"]

        self.onShown.append(self.onStart)
        self.onClose.append(self.__onClose)

        self["title"] = Label(self.params.get('title', _("Select option")))
        self["list"] = self.params.get('list_class', IPTVRadioButtonList)()

        actions = {
            "cancel": self.key_cancel,
            "ok": self.key_ok,
        }
        # opt-in: callers that pass a blue_callback (e.g. PlayerSelectorWidget's
        # search results, offering "Add to group"/"Hide group" without a
        # visible on-screen hint yet) get the blue key bound too - existing
        # callers that don't pass one are unaffected
        if callable(self.params.get('blue_callback')):
            actions["blue"] = self.key_blue
            self["key_blue_label"] = Label(self.params.get('blue_label', _("More")))
        self["actions"] = ActionMap(["SetupActions", "ColorActions"], actions, -2)

        self.prevIdx = 0
        self.reorderingMode = False

    def __onClose(self):
        try:
            self["list"].disconnectSelChanged(self.onSelectionChanged)
        except Exception:
            printExc()
        self.params = None

    def onStart(self):
        self.onShown.remove(self.onStart)

        self["list"].setList([(x,) for x in self.params['options']])
        try:
            self["list"].moveToIndex(self.params['current_idx'])
        except Exception:
            printExc()
        self["list"].connectSelChanged(self.onSelectionChanged)

    def key_ok(self):
        printDBG('IPTVChoiceBoxWidget.key_ok() getSelectedItem() = "%s"' % self.getSelectedItem())
        self.close(self.getSelectedItem())

    def key_cancel(self):
        printDBG('IPTVChoiceBoxWidget.key_cancel()')
        self.close(None)

    def key_blue(self):
        callback = self.params.get('blue_callback')
        if callable(callback):
            callback(self.getSelectedItem())

    def onSelectionChanged(self):
        callback = self.params.get('selection_changed', None)
        if callable(callback):
            callback(self.getSelectedItem())

    def getSelectedItem(self):
        sel = None
        try:
            sel = self["list"].l.getCurrentSelection()[0]
        except Exception:
            pass
        return sel
