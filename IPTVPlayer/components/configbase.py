# -*- coding: utf-8 -*-
#
#  Konfigurator dla iptv 2013
#  autorzy: j00zek, samsamsam
#


###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.components.iptvdirbrowser import IPTVDirectorySelectorWidget, IPTVFileSelectorWidget
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.e2ivkselector import GetVirtualKeyboard
from Plugins.Extensions.IPTVPlayer.components import skinchrome
from Plugins.Extensions.IPTVPlayer.components.cover import Cover3
from Plugins.Extensions.IPTVPlayer.components.iptvchoicebox import IPTVChoiceBoxWidget, IPTVChoiceBoxItem, openChoiceBox
###################################################

###################################################
# FOREIGN import
###################################################
import re
from enigma import ePoint
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen

from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.config import ConfigDirectory, ConfigText, ConfigPassword, ConfigBoolean, ConfigSelection, configfile
from Components.ConfigList import ConfigListScreen
from Components.Sources.StaticText import StaticText
from Tools.BoundFunction import boundFunction
from Tools.LoadPixmap import LoadPixmap
###################################################
COLORS_DEFINITONS = [("#000000", _("black")), ("#C0C0C0", _("silver")), ("#808080", _("gray")), ("#FFFFFF", _("white")), ("#800000", _("maroon")), ("#FF0000", _("red")), ("#800080", _("purple")), ("#FF00FF", _("fuchsia")),
                     ("#008000", _("green")), ("#00FF00", _("lime")), ("#808000", _("olive")), ("#FFFF00", _("yellow")), ("#000080", _("navy")), ("#0000FF", _("blue")), ("#008080", _("teal")), ("#00FFFF", _("aqua"))]


class ConfigIPTVFileSelection(ConfigDirectory):
    def __init__(self, ignoreCase=True, fileMatch=None, default="", visible_width=60):
        self.fileMatch = fileMatch
        self.ignoreCase = ignoreCase
        ConfigDirectory.__init__(self, default, visible_width)


class ConfigBaseWidget(Screen, ConfigListScreen):
    # icon base is computed per-instance via skinchrome.getIconBase(),
    # not cached at class/module level, so it always reflects the real
    # screen resolution. Header (logo/title/divider) deliberately left as
    # its own markup for now: this screen's title starts further right
    # (240 vs skinchrome's standard 124) to leave room for "footnote"
    # (the "< OK >" selectability hint) next to it, which skinchrome's
    # build_header() has no parameter for yet.
    #
    # Footer's background/divider comes from build_footer(), but every
    # icon/label is a plain repositionable name= widget instead of
    # build_footer()'s own source=/ConditionalShowHide ones - Enigma2's
    # own ConfigListScreen manages self["key_menu"]'s text, showing/
    # hiding MENU per selected config entry, and OK/EXIT and the color
    # keys after it need to slide over to fill the gap when it's hidden,
    # the same "ConditionalShowHide only hides in place" reflow
    # E2iPlayerWidget's own footer needs (see _footerSlots() below).
    #
    # The footer's own "is this entry also LEFT/RIGHT-adjustable?" hint
    # (mirrors "footnote" up in the header, which stays text-based) uses
    # key_prevnext.png (the existing "<>" icon, same one E2iPlayerWidget's
    # footer already uses) instead of literal "< >" characters, so it
    # stays consistent with every other footer hint here being an icon,
    # not text - it's just one more conditional icon in the same
    # fixed-pitch LEFT_ICON_SLOTS cluster as MENU/OK/EXIT, no special
    # label-width-aware positioning needed.
    # Opt-in for a 4th (blue) color key - every subclass so far only ever
    # used red/green/yellow, so this stays off by default; a subclass
    # that wants a blue key (e.g. ConfigHostsMenu's direct "Enable/
    # Disable reordering mode" toggle) sets this to True as a class
    # attribute.
    HAS_BLUE_KEY = False

    def __prepareSkin(self):
        iconBase = skinchrome.getIconBase()
        # built assuming MENU/prevnext both start hidden (the safe,
        # conservative default - ConfigListScreen/onSelectionChanged()
        # only decide the real values once the config list is actually
        # populated) - _repositionFooterKeys() is always called once
        # explicitly at the end of layoutFinished(), before the screen
        # is ever shown, so this initial guess is corrected immediately
        # either way and never visibly wrong
        slots = self._footerSlots(False, False)
        geomMenu = skinchrome.leftIconGeometry(660, 0, 1.0)
        geomOk = skinchrome.leftIconGeometry(660, slots['ok'], 1.0)
        geomPrevNext = skinchrome.leftIconGeometry(660, slots['prevNext'], 1.0)
        geomExit = skinchrome.leftIconGeometry(660, slots['exit'], 1.0)
        geomRed = skinchrome.colorKeyGeometry(660, slots['leftIconCount'], 0, 1.0)
        geomGreen = skinchrome.colorKeyGeometry(660, slots['leftIconCount'], 1, 1.0)
        geomYellow = skinchrome.colorKeyGeometry(660, slots['leftIconCount'], 2, 1.0)
        skin = ["""
        <screen position="center,center" size="1020,660" resolution="1280,720" title="" backgroundColor="#34111112" flags="wfNoBorder">
            <widget source="Title" render="Label" position="240,10" size="780,40" foregroundColor="white" backgroundColor="black" borderWidth="1" borderColor="black" transparent="1" zPosition="1" font="Regular;24" valign="center" />
            <widget name="config" position="10,64" size="1000,530" itemHeight="32" font="Regular;20" scrollbarMode="showOnDemand" scrollbarSliderBorderWidth="1" scrollbarForegroundColor="#1b5a91" scrollbarBorderColor="#00b6b6b6" enableWrapAround="1" transparent="1" foregroundColor="white" backgroundColor="black" foregroundColorSelected="white" backgroundColorSelected="#1b5a91" borderWidth="1" borderColor="black" shadowColor="black" shadowOffset="-2,-2" />
            <widget name="footnote" position="150,12" size="100,30" foregroundColor="white" backgroundColor="black" borderWidth="1" borderColor="black" transparent="1" zPosition="1" font="Regular;24" valign="center" />
            <ePixmap pixmap="%s/iptvlogo.png" position="12,10" size="100,40" alphatest="blend" transparent="1" />
            <eLabel name="BG_Title" position="0,0" size="1020,60" backgroundColor="#100d0f16" zPosition="-1" />
            <ePixmap pixmap="%s/smallshadowline.png" position="0,60" size="1020,2" zPosition="2" />
            <widget name="key_menu_icon" position="%d,%d" size="%d,%d" zPosition="1" transparent="1" alphatest="blend" />
            <widget name="key_ok_icon" position="%d,%d" size="%d,%d" zPosition="1" transparent="1" alphatest="blend" />
            <widget name="key_prevnext_icon" position="%d,%d" size="%d,%d" zPosition="1" transparent="1" alphatest="blend" />
            <widget name="key_exit_icon" position="%d,%d" size="%d,%d" zPosition="1" transparent="1" alphatest="blend" />
            <widget name="key_red_icon" position="%d,%d" size="%d,%d" zPosition="1" transparent="1" alphatest="blend" />
            <widget name="key_red" position="%d,%d" size="%d,%d" backgroundColor="#000000" font="Regular;%d" foregroundColor="#ffffff" zPosition="2" valign="center" halign="left" transparent="1" />
            <widget name="key_green_icon" position="%d,%d" size="%d,%d" zPosition="1" transparent="1" alphatest="blend" />
            <widget name="key_green" position="%d,%d" size="%d,%d" backgroundColor="#000000" font="Regular;%d" foregroundColor="#ffffff" zPosition="2" valign="center" halign="left" transparent="1" />
            <widget name="key_yellow_icon" position="%d,%d" size="%d,%d" zPosition="1" transparent="1" alphatest="blend" />
            <widget name="key_yellow" position="%d,%d" size="%d,%d" backgroundColor="#000000" font="Regular;%d" foregroundColor="#ffffff" zPosition="2" valign="center" halign="left" transparent="1" />
        """ % (
            iconBase, iconBase,
            geomMenu['x'], geomMenu['y'], geomMenu['w'], geomMenu['h'],
            geomOk['x'], geomOk['y'], geomOk['w'], geomOk['h'],
            geomPrevNext['x'], geomPrevNext['y'], geomPrevNext['w'], geomPrevNext['h'],
            geomExit['x'], geomExit['y'], geomExit['w'], geomExit['h'],
            geomRed['iconX'], geomRed['iconY'], geomRed['iconSize'], geomRed['iconSize'],
            geomRed['labelX'], geomRed['labelY'], geomRed['labelW'], geomRed['labelH'], geomRed['font'],
            geomGreen['iconX'], geomGreen['iconY'], geomGreen['iconSize'], geomGreen['iconSize'],
            geomGreen['labelX'], geomGreen['labelY'], geomGreen['labelW'], geomGreen['labelH'], geomGreen['font'],
            geomYellow['iconX'], geomYellow['iconY'], geomYellow['iconSize'], geomYellow['iconSize'],
            geomYellow['labelX'], geomYellow['labelY'], geomYellow['labelW'], geomYellow['labelH'], geomYellow['font'],
        )]
        if self.HAS_BLUE_KEY:
            geomBlue = skinchrome.colorKeyGeometry(660, slots['leftIconCount'], 3, 1.0)
            skin.append("""
            <widget name="key_blue_icon" position="%d,%d" size="%d,%d" zPosition="1" transparent="1" alphatest="blend" />
            <widget name="key_blue" position="%d,%d" size="%d,%d" backgroundColor="#000000" font="Regular;%d" foregroundColor="#ffffff" zPosition="2" valign="center" halign="left" transparent="1" />
            """ % (
                geomBlue['iconX'], geomBlue['iconY'], geomBlue['iconSize'], geomBlue['iconSize'],
                geomBlue['labelX'], geomBlue['labelY'], geomBlue['labelW'], geomBlue['labelH'], geomBlue['font'],
            ))
        skin.append("""
            %s
        </screen>
        """ % (
            # keys=(), showMenu/showOk/showExit=False - every icon/label
            # above is a plain repositionable widget instead now, this
            # only still provides the footer's background/divider
            skinchrome.build_footer(660, scale=1.0, iconBase=iconBase, keys=(), showMenu=False, showNav=False, showOk=False, showExit=False),
        ))
        return "".join(skin)

    @staticmethod
    def _footerSlots(hasMenu, hasPrevNext):
        # single source of truth for this footer's slot assignment,
        # shared by __prepareSkin() (build-time initial position) and
        # _repositionFooterKeys() (runtime, on every selection change) -
        # same pattern as E2iPlayerWidget's own _footerSlots() this
        # session. Sequence: menu?, ok, prevnext?, exit, then colors
        okSlot = 1 if hasMenu else 0
        prevNextSlot = okSlot + 1
        exitSlot = prevNextSlot + (1 if hasPrevNext else 0)
        return {'ok': okSlot, 'prevNext': prevNextSlot, 'exit': exitSlot, 'leftIconCount': exitSlot + 1}

    def _repositionFooterKeys(self, hasMenu, hasPrevNext):
        if self._externalSkin:
            # external skin draws its own footer - no key_*_icon widgets
            return
        if self["key_ok_icon"].instance is None:
            # not laid out yet
            return
        scale = skinchrome.getScale()
        height = skinchrome.scalePixels(660, scale)
        slots = self._footerSlots(hasMenu, hasPrevNext)
        geomOk = skinchrome.leftIconGeometry(height, slots['ok'], scale)
        geomExit = skinchrome.leftIconGeometry(height, slots['exit'], scale)
        self["key_ok_icon"].instance.move(ePoint(geomOk['x'], geomOk['y']))
        self["key_exit_icon"].instance.move(ePoint(geomExit['x'], geomExit['y']))
        if hasMenu:
            geomMenu = skinchrome.leftIconGeometry(height, 0, scale)
            self["key_menu_icon"].instance.move(ePoint(geomMenu['x'], geomMenu['y']))
            self["key_menu_icon"].show()
        else:
            self["key_menu_icon"].hide()
        if hasPrevNext:
            geomPrevNext = skinchrome.leftIconGeometry(height, slots['prevNext'], scale)
            self["key_prevnext_icon"].instance.move(ePoint(geomPrevNext['x'], geomPrevNext['y']))
            self["key_prevnext_icon"].show()
        else:
            self["key_prevnext_icon"].hide()
        leftIconCount = slots['leftIconCount']
        geomRed = skinchrome.colorKeyGeometry(height, leftIconCount, 0, scale)
        geomGreen = skinchrome.colorKeyGeometry(height, leftIconCount, 1, scale)
        geomYellow = skinchrome.colorKeyGeometry(height, leftIconCount, 2, scale)
        self["key_red_icon"].instance.move(ePoint(geomRed['iconX'], geomRed['iconY']))
        self["key_red"].instance.move(ePoint(geomRed['labelX'], geomRed['labelY']))
        self["key_green_icon"].instance.move(ePoint(geomGreen['iconX'], geomGreen['iconY']))
        self["key_green"].instance.move(ePoint(geomGreen['labelX'], geomGreen['labelY']))
        self["key_yellow_icon"].instance.move(ePoint(geomYellow['iconX'], geomYellow['iconY']))
        self["key_yellow"].instance.move(ePoint(geomYellow['labelX'], geomYellow['labelY']))
        if self.HAS_BLUE_KEY:
            geomBlue = skinchrome.colorKeyGeometry(height, leftIconCount, 3, scale)
            self["key_blue_icon"].instance.move(ePoint(geomBlue['iconX'], geomBlue['iconY']))
            self["key_blue"].instance.move(ePoint(geomBlue['labelX'], geomBlue['labelY']))

    def __init__(self, session):
        printDBG("ConfigBaseWidget.__init__ -------------------------------")

        self.skin = self.__prepareSkin()
        Screen.__init__(self, session)

        self.skinName = skinchrome.forceInternalSkinName(["ConfigBaseWidgetScreen", "ConfigBaseWidget"])
        # an active Enigma2 skin shipping its own ConfigBaseWidgetScreen draws
        # the footer itself and has no key_*_icon widgets - use plain StaticText
        # keys and skip the runtime .move() reflow
        self._externalSkin = skinchrome.isExternalSkin(self.skinName)

        self.onChangedEntry = []
        self.list = []
        ConfigListScreen.__init__(self, self.list, session=session, on_change=self.changedEntry)
        self.setup_title = (_("E2iPlayer - settings"))

        self["footnote"] = Label()
        if self._externalSkin:
            self["key_green"] = StaticText(_("Save"))
            self["key_red"] = StaticText(_("Cancel"))
            self["key_yellow"] = StaticText(_("Defaults"))
            if self.HAS_BLUE_KEY:
                self["key_blue"] = StaticText("")
            self["key_menu"] = StaticText("")
            self["actions"] = ActionMap(["ColorActions", "ListboxActions", "IPTVPlayerListActions"],
                {
                    "back": self.keyExit,
                    "green": self.keySave,
                    "ok": self.keyOK,
                    "red": self.keyCancel,
                    "yellow": self.keyDefaults,
                    "blue": self.keyBlue,
                    "menu": self.keyMenu,
                    "up": self.keyUp,
                    "down": self.keyDown,
                    "moveUp": self.keyUp,
                    "moveDown": self.keyDown,
                    "moveTop": self.keyHome,
                    "moveEnd": self.keyEnd,
                    "home": self.keyHome,
                    "end": self.keyEnd,
                    "pageUp": self.keyPageUp,
                    "pageDown": self.keyPageDown
                }, -2)
            self.onClose.append(self.__onClose)
            self.isOkEnabled = False
            self.isSelectable = False
            self.onLayoutFinish.append(self.layoutFinished)
            return

        self["key_green_icon"] = Cover3()
        self["key_green"] = Label(_("Save"))
        self["key_red_icon"] = Cover3()
        self["key_red"] = Label(_("Cancel"))
        self["key_yellow_icon"] = Cover3()
        self["key_yellow"] = Label(_("Defaults"))
        if self.HAS_BLUE_KEY:
            self["key_blue_icon"] = Cover3()
            self["key_blue"] = Label("")
        self["key_ok_icon"] = Cover3()
        self["key_exit_icon"] = Cover3()
        self["key_menu_icon"] = Cover3()
        self["key_menu_icon"].hide()
        # "this entry is also LEFT/RIGHT-adjustable" hint - conditional
        # like MENU, driven by isSelectableActive() via onSelectionChanged()
        self["key_prevnext_icon"] = Cover3()
        self["key_prevnext_icon"].hide()
        # not bound to any skin widget itself (key_menu_icon above is
        # the actual displayed icon) - kept purely so ConfigListScreen's
        # own per-selection logic still has somewhere to write MENU's
        # real availability, which onSelectionChanged() below reads back
        self["key_menu"] = StaticText("")

        self["actions"] = ActionMap(["ColorActions", "ListboxActions", "IPTVPlayerListActions"],
            {
                "back": self.keyExit,
                "green": self.keySave,
                "ok": self.keyOK,
                "red": self.keyCancel,
                "yellow": self.keyDefaults,
                "blue": self.keyBlue,
                "menu": self.keyMenu,

                "up": self.keyUp,
                "down": self.keyDown,
                "moveUp": self.keyUp,
                "moveDown": self.keyDown,
                "moveTop": self.keyHome,
                "moveEnd": self.keyEnd,
                "home": self.keyHome,
                "end": self.keyEnd,
                "pageUp": self.keyPageUp,
                "pageDown": self.keyPageDown
            }, -2)

        self.onLayoutFinish.append(self.layoutFinished)
        self.onClose.append(self.__onClose)
        self.isOkEnabled = False
        self.isSelectable = False

    def __del__(self):
        printDBG("ConfigBaseWidget.__del__ -------------------------------")

    def __onClose(self):
        printDBG("ConfigBaseWidget.__onClose -----------------------------")
        self.onClose.remove(self.__onClose)
        self.onLayoutFinish.remove(self.layoutFinished)
        if self.onSelectionChanged in self["config"].onSelectionChanged:
            self["config"].onSelectionChanged.remove(self.onSelectionChanged)

    def layoutFinished(self):
        self.setTitle(_("E2iPlayer - settings"))
        # static icons, set once - only their positions (and, for MENU,
        # visibility) change afterward, via _repositionFooterKeys().
        # Skipped for an external skin (no key_*_icon widgets).
        if not self._externalSkin:
            _footerIconBase = skinchrome.getIconBase()
            self["key_menu_icon"].setPixmap(LoadPixmap(_footerIconBase + '/menu.png'))
            self["key_ok_icon"].setPixmap(LoadPixmap(_footerIconBase + '/ok.png'))
            self["key_prevnext_icon"].setPixmap(LoadPixmap(_footerIconBase + '/key_prevnext.png'))
            self["key_exit_icon"].setPixmap(LoadPixmap(_footerIconBase + '/exit.png'))
            self["key_red_icon"].setPixmap(LoadPixmap(_footerIconBase + '/red.png'))
            self["key_green_icon"].setPixmap(LoadPixmap(_footerIconBase + '/green.png'))
            self["key_yellow_icon"].setPixmap(LoadPixmap(_footerIconBase + '/yellow.png'))
            if self.HAS_BLUE_KEY:
                self["key_blue_icon"].setPixmap(LoadPixmap(_footerIconBase + '/blue.png'))
        if self.onSelectionChanged not in self["config"].onSelectionChanged:
            self["config"].onSelectionChanged.append(self.onSelectionChanged)
        self.runSetup()
        # ConfigListScreen's own selection-changed hook (registered
        # during its __init__, ahead of ours above) already ran once as
        # part of runSetup() populating the list, so self["key_menu"]'s
        # real value and self.isSelectable are already known here -
        # reposition explicitly before the screen is ever shown instead
        # of waiting for the next user-triggered selection change
        self._repositionFooterKeys(bool(self["key_menu"].text), self.isSelectable)

    def onSelectionChanged(self):
        self.isOkEnabled = self.isOkActive()
        self.isSelectable = self.isSelectableActive()
        self.setOKLabel()
        # ConfigListScreen (Enigma2 core) manages self["key_menu"]'s text
        # itself, per selected config entry - same convention every
        # ConfigListScreen-based screen uses. key_menu_icon is wired to
        # that same source (see _repositionFooterKeys()) so it shows/
        # hides and the icons after it reflow to fill the gap instead of
        # the icon staying visible regardless. key_prevnext_icon mirrors
        # self.isSelectable the same way, using the existing "<>" icon
        # instead of literal text for this one.
        self._repositionFooterKeys(bool(self["key_menu"].text), self.isSelectable)

    def setOKLabel(self):
        if self.isSelectable:
            labelText = "<  %s  >"
        else:
            labelText = "   %s   "
        if self.isOkEnabled:
            labelText = labelText % "OK"
        else:
            labelText = labelText % "  "
        self["footnote"].setText(_(labelText))

    def isOkActive(self):
        if self["config"].getCurrent() is not None:
            currItem = self["config"].getCurrent()[1]
            if isinstance(currItem, ConfigText) or isinstance(currItem, ConfigPassword):
                try:
                    # I really do not like this "help screen" NumericalTextInputHelpDialog which cover others options
                    # it is much easier to type text with VK after OK press, but maybe option need to be added to allow user to have this "help"
                    currItem.help_window.hide()
                except Exception:
                    pass
                return True
        return False

    def isSelectableActive(self):
        if self["config"].getCurrent() is not None:
            currItem = self["config"].getCurrent()[1]
            if currItem and isinstance(currItem, ConfigSelection) or isinstance(currItem, ConfigBoolean):
                return True
        return False

    def runSetup(self):
        self["config"].list = self.list
        self["config"].setList(self.list)

    def isChanged(self):
        bChanged = False
        for item in self["config"].list:
            if len(item) > 1 and item[1].isChanged():
                bChanged = True
                break
        printDBG("ConfigMenu.isChanged bChanged[%r]" % bChanged)
        return bChanged

    def getMessageAfterSave(self):
        return ''

    def getMessageBeforeClose(self):
        return ''

    def askForSave(self, callbackYesFun, callBackNoFun):
        self.session.openWithCallback(boundFunction(self.saveOrCancelChanges, callbackYesFun, callBackNoFun), MessageBox, text=_('Save changes?'), type=MessageBox.TYPE_YESNO)
        return

    def saveOrCancelChanges(self, callbackFun=None, failCallBackFun=None, answer=None):
        if answer:
            self.save()
            if callbackFun:
                callbackFun()
        else:
            self.cancel()
            if failCallBackFun:
                failCallBackFun()

    def keySave(self):
        self.saveAndClose()

    def saveOrCancel(self, operation="save"):
        for item in self["config"].list:
            if len(item) > 1:
                if "save" == operation:
                    item[1].save()
                else:
                    item[1].cancel()
        if "save" == operation:
            configfile.save()

    def save(self):
        self.saveOrCancel("save")

    def cancel(self):
        self.saveOrCancel("cancel")
        self.runSetup()

    def saveAndClose(self):
        self.save()
        self.performCloseWithMessage(True)

    def performCloseWithMessage(self, afterSave=True):
        if afterSave:
            message = self.getMessageAfterSave()
        else:
            message = self.getMessageBeforeClose()
        if message == '':
            self.close()
        else:
            self.session.openWithCallback(self.closeAfterMessage, MessageBox, text=message, type=MessageBox.TYPE_INFO)

    def closeAfterMessage(self, arg=None):
        self.close()

    def cancelAndClose(self):
        self.cancel()
        self.performCloseWithMessage()

    def keyOK(self):
        if not self.isOkEnabled:
            return

        curIndex = self["config"].getCurrentIndex()
        currItem = self["config"].list[curIndex][1]

        if isinstance(currItem, ConfigIPTVFileSelection):
            def SetFilePathCallBack(curIndex, newPath):
                if None is not newPath:
                    self["config"].list[curIndex][1].value = newPath
            try:
                if None is not currItem.fileMatch:
                    if currItem.ignoreCase:
                        fileMatch = re.compile(currItem.fileMatch, re.IGNORECASE)
                    else:
                        fileMatch = re.compile(currItem.fileMatch)
                else:
                    fileMatch = None
            except Exception:
                printExc()
                return
            self.session.openWithCallback(boundFunction(SetFilePathCallBack, curIndex), IPTVFileSelectorWidget, currItem.value, _('Select the file'), fileMatch)
            return

        elif isinstance(currItem, ConfigDirectory):
            def SetDirPathCallBack(curIndex, newPath):
                if None is not newPath:
                    self["config"].list[curIndex][1].value = newPath
            self.session.openWithCallback(boundFunction(SetDirPathCallBack, curIndex), IPTVDirectorySelectorWidget, currDir=currItem.value, title=_('Select the directory'))
            return
        elif isinstance(currItem, ConfigText):
            def VirtualKeyBoardCallBack(curIndex, newTxt):
                if isinstance(newTxt, str):
                    self["config"].list[curIndex][1].value = newTxt
            try:
                # we need hide NumericalTextInputHelpDialog before
                self["config"].list[curIndex][1].help_window.hide()
            except Exception:
                printExc()
            self.session.openWithCallback(boundFunction(VirtualKeyBoardCallBack, curIndex), GetVirtualKeyboard(), title=(_("Enter a value")), text=currItem.value)
            return

        ConfigListScreen.keyOK(self)

    def keyExit(self):
        if self.isChanged():
            self.askForSave(self.saveAndClose, self.cancelAndClose)
        else:
            self.performCloseWithMessage()

    def keyCancel(self):
        self.cancelAndClose()

    def keyMenu(self):
        # replaces Enigma2 core's own ConfigListScreen.keyMenu() (same
        # guard/logic, verbatim - from openatv/enigma2's
        # lib/python/Components/ConfigList.py) so this popup uses our own
        # chrome-skinned IPTVChoiceBoxWidget instead of the system skin's
        # plain ChoiceBox. Only ever fires for config elements with a
        # `description` attribute (ConfigSelection and its subclasses,
        # e.g. ConfigYesNo/ConfigOnOff) - every other type
        # (ConfigText/ConfigInteger/ConfigDirectory/...) silently does
        # nothing here too, exactly like the native version did.
        #
        # `self.isSelectable` guard: without it, ConfigMenu's "Services
        # configuration"/"External movie player config" rows would open
        # an empty-looking ChoiceBox on MENU. Both are real
        # `ConfigSelection` objects (config.plugins.iptvplayer.
        # fakeHostsList/fakExtMoviePlayerList in iptvconfigmenu.py) with a
        # single placeholder choice whose description is just "  " (blank
        # spaces) - they exist purely so OK can open a different screen,
        # not as a real adjustable setting, so `hasattr(...,'description')`
        # alone doesn't exclude them. ConfigMenu.onSelectionChanged()
        # already forces `self.isSelectable = False` for exactly these
        # rows (governs the "<  OK  >" bracket hint) - reusing that
        # existing, already-correct signal here instead of teaching this
        # shared base class about specific fake config entries it has no
        # business knowing about.
        currConfig = self["config"].getCurrent()
        if not (currConfig and currConfig[1].enabled and hasattr(currConfig[1], "description") and self.isSelectable):
            return
        configElement = currConfig[1]
        options = [IPTVChoiceBoxItem(name=desc, privateData=choice) for desc, choice in zip(configElement.description, configElement.choices)]
        height = self._getSelectionListHeight(len(options))
        openChoiceBox(self.session, {'width': 600, 'height': height, 'current_idx': configElement.getIndex(), 'title': currConfig[0], 'options': options, 'chrome': True}, self._keyMenuCallback)

    def _keyMenuCallback(self, answer):
        if answer is None:
            return
        # real accessors are the config element's own .value and this
        # class's own changedEntry() - self.getCurrentValue()/
        # self.entryChanged() don't exist on this class or any base.
        configElement = self["config"].getCurrent(full=False)[1]
        prev = str(configElement.value)
        configElement.setValue(answer.privateData)
        self["config"].invalidateCurrent()
        if str(answer.privateData) != prev:
            self.changedEntry()

    def _getSelectionListHeight(self, numItems):
        # same reference-space-vs-real-pixels reasoning as
        # E2iPlayerWidget's own _getMoviePlayerPickerHeight() -
        # IPTVRadioButtonList's (the ChoiceBox's default list_class) real
        # per-tier item heights (35/40/55); +176 assumes the chrome
        # default footerMargin (166, not overridden above) - same margin
        # e2ivk.py's _getOptionsPickerHeight() uses for that same reason.
        # Capped at 660 (out of the chrome skin's own 720-tall reference
        # canvas, same cap playerselector.py's _getSearchResultsHeight()
        # uses) so a config item with many choices scrolls
        # (scrollbarMode="showAlways" is already declared on the list
        # widget) instead of growing the popup past the screen edge.
        #
        # Floored at 2: with numItems=1, the computed list area at
        # FHD/WQHD ends up SMALLER than one real item row (e.g. WQHD: 37px
        # of list space for a 55px-tall row), so the single row can't
        # render at all - an empty-looking window, not just a tight fit.
        # 2 is the smallest count every other caller of this method
        # exercises, and this floor is a no-op for every numItems >= 2
        # call.
        numItems = max(numItems, 2)
        itemH, scale = skinchrome.tierRowHeight(35, 40, 55)
        height = int(numItems * itemH / scale) + 176
        return min(height, 660)

    def keyDefaults(self):
        pass

    def keyBlue(self):
        # no-op default - only a subclass with HAS_BLUE_KEY = True (and
        # its own key_blue/key_blue_icon widgets, see __prepareSkin())
        # actually shows a blue hint at all, so BLUE doing nothing on
        # every other ConfigBaseWidget screen is expected, not a bug.
        pass

    def keyUp(self):
        if self["config"].instance is not None:
            self["config"].instance.moveSelection(self["config"].instance.moveUp)

    def keyDown(self):
        if self["config"].instance is not None:
            self["config"].instance.moveSelection(self["config"].instance.moveDown)

    def keyPageUp(self):
        if self["config"].instance is not None:
            self["config"].instance.moveSelection(self["config"].instance.pageUp)

    def keyPageDown(self):
        if self["config"].instance is not None:
            self["config"].instance.moveSelection(self["config"].instance.pageDown)

    def keyHome(self):
        pass

    def keyEnd(self):
        pass

    def keyLeft(self):
        ConfigListScreen.keyLeft(self)

    def keyRight(self):
        ConfigListScreen.keyRight(self)

    def getSubOptionsList(self):
        tab = []
        return tab

    def changeSubOptions(self):
        if self["config"].getCurrent()[1] in self.getSubOptionsList():
            self.runSetup()

    def changedEntry(self):
        self.changeSubOptions()
        for x in self.onChangedEntry:
            x()
