# -*- coding: utf-8 -*-
#

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.iptvlist import IPTVRadioButtonList
from Plugins.Extensions.IPTVPlayer.components import skinchrome
###################################################

###################################################
# FOREIGN import
###################################################
from Screens.Screen import Screen
from Components.Label import Label
from Components.ActionMap import ActionMap
from Components.Sources.StaticText import StaticText
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
            #
            # "e" in a size="...,e-N" is the container's full height, NOT
            # reduced by the widget's own y position first - so a list at
            # position="5,66" needs N >= 66 (its own top offset) + 64
            # (footer height - see build_footer()'s 2-line-wrap comment in
            # skinchrome.py) = 130 just to end exactly where the footer
            # begins, not 64 like a naive "container height minus footer"
            # reading would suggest.
            # 166 (36 more than that minimum, same margin the old 150
            # default kept above the old 114 floor) is MENU/INFO's default:
            # extra-safe since their height is calculated to fit their
            # content exactly. Content that's always scrollable regardless
            # (the language picker) can pass a footerMargin closer to that
            # 130 floor instead, to avoid a big empty gap above the footer.
            footerMargin = self.params.get('footerMargin', 166)
            # header/footer come from skinchrome's auto-scale variant
            # (build_header_auto()/build_footer_auto()), thin wrappers
            # around the same build_header()/build_footer() every other
            # migrated screen uses at scale=1.0 - so this screen gets the
            # same narrower title, OK/EXIT/nav icon cluster (sliding left
            # when one is missing) and 2-line color-key wrap as
            # PlayerSelectorWidget's chrome. Title goes through
            # self.setTitle() (build_header() emits a source="Title"
            # widget, not name="title") and the blue hint through
            # self["key_blue"] (a StaticText, matching build_footer()'s
            # source="key_blue" widget) - see __init__(). getIconBase()
            # picks true WQHD-tier icon sources too.
            iconBase = skinchrome.getIconBase()
            keys = ('blue',) if callable(self.params.get('blue_callback')) else ()
            # selectable=False screens (currently only the OSK's Help popup)
            # are pure info dialogs: key_ok() still closes the screen, but
            # nothing reads back the "selected" item (opened via session.
            # open(), not openWithCallback()), and there's no per-row action
            # to move to in the first place - so the OK and nav (d-pad) icons
            # don't represent anything real there; only EXIT shows for
            # that case.
            showOkNav = self.params.get('selectable', True)
            skin = """
                <screen name="IPTVChoiceBoxWidget" position="center,center" resolution="1280,720" title="%s" size="%d,%d" backgroundColor="#34111112" flags="wfNoBorder">
                    %s
                    <widget name="list"  position="5,66"  zPosition="2" size="e-10,e-%d" scrollbarMode="showAlways" scrollbarSliderBorderWidth="1" scrollbarForegroundColor="#1b5a91" scrollbarBorderColor="#00b6b6b6" enableWrapAround="1" transparent="1" foregroundColor="white" backgroundColor="black" %s borderWidth="1" borderColor="black"/>
                    %s
                </screen>""" % (
                self.params.get('title', _("Select option")),
                width, height,
                skinchrome.build_header_auto(iconBase=iconBase),
                footerMargin,
                selColors,
                skinchrome.build_footer_auto(height, iconBase=iconBase, keys=keys, showNav=showOkNav, showOk=showOkNav),
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
        self.skinName = skinchrome.forceInternalSkinName(["IPTVChoiceBoxScreen", "IPTVChoiceBoxWidget"])

        self.onShown.append(self.onStart)
        self.onClose.append(self.__onClose)

        # chrome=True's skin gets its title from build_header()'s own
        # source="Title" widget (via setTitle()), same mechanism every
        # other migrated screen uses - the plain skin still declares its
        # own name="title" widget, so it keeps the direct Label() instead.
        if self.params.get('chrome', False):
            self.setTitle(self.params.get('title', _("Select option")))
        else:
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
            blueLabel = self.params.get('blue_label', _("More"))
            if self.params.get('chrome', False):
                # matches build_footer()'s source="key_blue" widget (same
                # StaticText-driven icon+label pair every other migrated
                # screen's blue color key uses)
                self["key_blue"] = StaticText(blueLabel)
            else:
                self["key_blue_label"] = Label(blueLabel)
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


def openChoiceBox(session, params, callback=None):
    # With config.plugins.iptvplayer.skinforceallinternal ON, use E2iPlayer's
    # own IPTVChoiceBoxWidget (per-row icons, blue "More" menu, ...). With it
    # OFF (default), use the native Enigma2 ChoiceBox, which the active skin
    # styles itself, at the cost of those extras. Only for popups whose
    # options are IPTVChoiceBoxItem and whose callback wants that item back -
    # both key_ok() and native ChoiceBox hand back the same object here.
    try:
        from Components.config import config
        useNative = not config.plugins.iptvplayer.skinforceallinternal.value
    except Exception:
        useNative = False

    if not useNative:
        if callback is not None:
            session.openWithCallback(callback, IPTVChoiceBoxWidget, params)
        else:
            session.open(IPTVChoiceBoxWidget, params)
        return

    from Screens.ChoiceBox import ChoiceBox
    nativeList = []
    for opt in params.get('options', []):
        text = getattr(opt, 'name', None)
        if text is None:
            text = opt[0] if isinstance(opt, (list, tuple)) and len(opt) else str(opt)
        nativeList.append((text, opt))

    def _nativeCb(ret):
        if callback is not None:
            callback(ret[1] if ret else None)

    try:
        selection = int(params.get('current_idx', 0) or 0)
    except Exception:
        selection = 0
    session.openWithCallback(_nativeCb, ChoiceBox, title=params.get('title', '') or '',
                             list=nativeList, selection=selection)
