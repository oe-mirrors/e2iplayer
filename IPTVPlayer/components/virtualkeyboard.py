# -*- coding: UTF-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.cover import Cover3, Cover2
from Plugins.Extensions.IPTVPlayer.components import skinchrome
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
###################################################
# FOREIGN import
###################################################
from enigma import eListboxPythonMultiContent, gFont, RT_HALIGN_CENTER, RT_VALIGN_CENTER, getPrevAsciiCode
from Screens.Screen import Screen
from Components.ActionMap import NumberActionMap
from Components.Input import Input
from Components.Label import Label
from Components.Sources.StaticText import StaticText
from Components.Pixmap import Pixmap
from Components.MenuList import MenuList
from Components.MultiContent import MultiContentEntryText, MultiContentEntryPixmapAlphaTest
from Tools.Directories import resolveFilename, SCOPE_CURRENT_SKIN
from Tools.LoadPixmap import LoadPixmap
from Tools.NumericalTextInput import NumericalTextInput
###################################################


class VirtualKeyBoardList(MenuList):
    def __init__(self, list, enableWrapAround=False, itemHeight=45, fontSize=28):
        MenuList.__init__(self, list, enableWrapAround, eListboxPythonMultiContent)
        self.l.setFont(0, gFont("Regular", fontSize))
        self.l.setItemHeight(itemHeight)


class IPTVVirtualKeyBoardWithCaptcha(Screen):

    def __init__(self, session, title="", text="", additionalParams={}):
        # Uses real `build_header()`/`build_footer()` with `flags="wfNoBorder"` -
        # tiered `scale=` (not `resolution=` auto-scale), same as the other
        # 4 screens in this family. RED/GREEN/BLUE map to real actions
        # (`exit`/`ok`/`shiftClicked`) and get color-key hints; there's no
        # separate "key_ok" hint text - `build_footer()`'s own OK icon
        # already says the same thing, same as every other screen that
        # drops a redundant hand-rolled hint. YELLOW (`switchLang`) is a
        # permanent no-op stub - no hint for it, matching this branch's
        # policy on dead actions.
        #
        # Content block (captcha image/header caption/text field/keyboard
        # grid): every content number goes through the same `_s()` scaling
        # the chrome uses, so the keyboard itself scales up on FHD/WQHD
        # too instead of staying pinned at its HD-reference pixel size.
        # `icons/vk/*.png` ships per-tier sized art (45x45/68x68/90x90,
        # see self.keyPx below) matching this scale exactly, same as
        # every other per-tier icon set in this codebase.
        scale = skinchrome.getScale()
        iconBase = skinchrome.getIconBase()

        def _s(v):
            return skinchrome.scalePixels(v, scale)

        headerH = skinchrome.header_height(scale)
        footerH = skinchrome.footer_height(scale)
        contentTop = headerH + _s(10)
        HEIGHT = headerH + footerH + _s(440)

        # each keyboard tile (both the plain-background+text ones and the
        # icon ones like EXIT/OK/arrows) is forced to this same scaled
        # square size - see virtualKeyBoardEntryComponent()/
        # markSelectedKey() below, which use this instead of querying
        # each pixmap's own native size.
        self.keyPx = _s(45)
        keyFont = _s(28)

        # winWidth: unlike the other 4 captcha screens (plain NAV/OK/EXIT
        # icons only), this is the only one in the family with 3 color
        # keys (RED/GREEN/BLUE), whose row can be wider than the keyboard
        # content itself at higher tiers, since colorKeyGeometry()'s slot
        # positions scale up with `scale`. Compute the actual scaled
        # right edge of the last (blue) key's label via the
        # same colorKeyGeometry() build_footer() itself uses, and widen
        # the window to fit it (plus a small margin) whenever that's
        # bigger than the content's own (now also scaled) width.
        numLeftIcons = 3  # nav + ok + exit (showMenu/showNum are False below)
        lastKeyGeom = skinchrome.colorKeyGeometry(HEIGHT, numLeftIcons, 2, scale)  # slot 2 = blue, the 3rd/last of ('red','green','blue')
        CONTENT_WIDTH = _s(590)  # the content block's own original design width, now scaled like everything else in it
        winWidth = max(CONTENT_WIDTH, lastKeyGeom['labelX'] + lastKeyGeom['labelW'] + 20)
        # re-center the (now scaled, but still not necessarily as wide as
        # the footer's color-key row) content block inside the window,
        # instead of leaving it pinned to the left with a large empty gap
        # on the right whenever winWidth grew past CONTENT_WIDTH above.
        contentLeft = (winWidth - CONTENT_WIDTH) // 2

        # list widget height is derived directly from `5 * self.keyPx`
        # (5 keyboard rows) rather than independently scaling the
        # original 225 (`= 5*45` at HD) - `_s()`'s per-call rounding can
        # make those two numbers disagree by a couple pixels at some
        # scales (e.g. 1.5x: `_s(225)`=338 but `5*_s(45)`=340), which
        # would clip the last row. Width doesn't have this problem (550's
        # original ~10px buffer over the exact `12*45`=540 stays enough
        # buffer at every tier), so that one still just scales directly.
        listWidth = _s(550)
        listHeight = 5 * self.keyPx

        skin = ['<screen position="center,center" size="%d,%d" title="" flags="wfNoBorder">' % (winWidth, HEIGHT)]
        skin.append(skinchrome.build_header(scale=scale, iconBase=iconBase, showLogo=True))
        skin.append(skinchrome.build_footer(HEIGHT, scale=scale, iconBase=iconBase, keys=('red', 'green', 'blue'), showMenu=False, showNav=True, showNum=False, showOk=True, showExit=True))
        skin.append('''
                           <widget name="captcha" position="%d,%d" size="%d,%d" zPosition="2" transparent="1" alphatest="on" />
                           <ePixmap pixmap="%s"  position="%d,%d" size="%d,%d" zPosition="-4" alphatest="on" />
                           <widget name="header" position="%d,%d" size="%d,%d" transparent="1" noWrap="1" font="Regular;%d" valign="top"/>
                           <widget name="text"   position="%d,%d" size="%d,%d" transparent="1" noWrap="1" font="Regular;%d" valign="center" halign="right" />
                           <widget name="list"   position="%d,%d" size="%d,%d" selectionDisabled="1" transparent="1" />
                       ''' % (
            contentLeft + _s(10), contentTop, CONTENT_WIDTH - _s(20), _s(100),
            iconBase + "/vk/vkey_text.png", contentLeft + _s(25), contentTop + _s(140), _s(542), _s(80),
            contentLeft + _s(25), contentTop + _s(105), _s(500), _s(26), _s(20),
            contentLeft + _s(25), contentTop + _s(145), _s(536), _s(34), _s(26),
            contentLeft + _s(25), contentTop + _s(195), listWidth, listHeight,
        ))
        skin.append('</screen>')
        self.skin = '\n'.join(skin)

        Screen.__init__(self, session)
        self.keys_list = []
        self.shiftkeys_list = []
        self.shiftMode = additionalParams.get('shift_mode', False)
        self.selectedKey = 0
        self.smsChar = None
        self.sms = NumericalTextInput(self.smsOK)

        # every vk/*.png ships per-tier (45x45/68x68/90x90, matching
        # self.keyPx above exactly), loaded via `iconBase` (already
        # resolved to .../icons/HD|FHD|WQHD by skinchrome.getIconBase()
        # above), same idiom as every other per-tier icon load in this
        # codebase (e.g. iptvbuffui.py's `_iconBase + '/buffering/...'`).
        self.key_bg = LoadPixmap(iconBase + "/vk/vkey_bg.png")
        self.key_sel = LoadPixmap(iconBase + "/vk/vkey_sel.png")
        self.key_backspace = LoadPixmap(iconBase + "/vk/vkey_backspace.png")
        self.key_all = LoadPixmap(iconBase + "/vk/vkey_all.png")
        self.key_clr = LoadPixmap(iconBase + "/vk/vkey_clr.png")
        self.key_esc = LoadPixmap(iconBase + "/vk/vkey_esc.png")
        self.key_ok = LoadPixmap(iconBase + "/vk/vkey_ok.png")
        self.key_shift = LoadPixmap(iconBase + "/vk/vkey_shift.png")
        self.key_shift_sel = LoadPixmap(iconBase + "/vk/vkey_shift_sel.png")
        self.key_space = LoadPixmap(iconBase + "/vk/vkey_space.png")
        self.key_left = LoadPixmap(iconBase + "/vk/vkey_left.png")
        self.key_right = LoadPixmap(iconBase + "/vk/vkey_right.png")

        self.keyImages = {
                "BACKSPACE": self.key_backspace,
                "CLEAR": self.key_clr,
                "ALL": self.key_all,
                "EXIT": self.key_esc,
                "OK": self.key_ok,
                "SHIFT": self.key_shift,
                "SPACE": self.key_space,
                "LEFT": self.key_left,
                "RIGHT": self.key_right
            }
        self.keyImagesShift = {
                "BACKSPACE": self.key_backspace,
                "CLEAR": self.key_clr,
                "ALL": self.key_all,
                "EXIT": self.key_esc,
                "OK": self.key_ok,
                "SHIFT": self.key_shift_sel,
                "SPACE": self.key_space,
                "LEFT": self.key_left,
                "RIGHT": self.key_right
            }

        self["key_green"] = StaticText(_("Accept"))
        self["key_red"] = StaticText(_("Cancel"))
        self["key_blue"] = StaticText(_("Shift"))

        self["header"] = Label(title)
        self["text"] = Input(text=ensure_str(text))  # in p3 str is always unicode, ensure_str used in case it would be a bytes.
        self["list"] = VirtualKeyBoardList([], itemHeight=self.keyPx, fontSize=keyFont)

        self["actions"] = NumberActionMap(["OkCancelActions", "WizardActions", "ColorActions", "KeyboardInputActions", "InputBoxActions", "InputAsciiActions"],
            {
                "gotAsciiCode": self.keyGotAscii,
                "ok": self.okClicked,
                "cancel": self.exit,
                "left": self.left,
                "right": self.right,
                "up": self.up,
                "down": self.down,
                "red": self.exit,
                "green": self.ok,
                "yellow": self.switchLang,
                "blue": self.shiftClicked,
                "deleteBackward": self.backClicked,
                "deleteForward": self.forwardClicked,
                "back": self.exit,
                "pageUp": self.cursorRight,
                "pageDown": self.cursorLeft,
                "1": self.keyNumberGlobal,
                "2": self.keyNumberGlobal,
                "3": self.keyNumberGlobal,
                "4": self.keyNumberGlobal,
                "5": self.keyNumberGlobal,
                "6": self.keyNumberGlobal,
                "7": self.keyNumberGlobal,
                "8": self.keyNumberGlobal,
                "9": self.keyNumberGlobal,
                "0": self.keyNumberGlobal,
            }, -2)
        self.startText = text
        self.setLang(additionalParams)
        self.onExecBegin.append(self.setKeyboardModeAscii)
        self.onLayoutFinish.append(self.buildVirtualKeyBoard)

        self.captchaPath = additionalParams['captcha_path']
        self['captcha'] = Cover2()
        self.onShown.append(self.loadCaptcha)

    def loadCaptcha(self):
        self.onShown.remove(self.loadCaptcha)
        self.setTitle(_('Virtual Keyboard'))
        self["text"].right()
        self["text"].currPos = len(self.startText)
        self["text"].right()
        try:
            self['captcha'].updateIcon(self.captchaPath)
        except Exception:
            printExc()

    def switchLang(self):
        pass

    def setLang(self, additionalParams):
        if 'keys_list' not in additionalParams:
            self.keys_list = [
                ["EXIT", "1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "BACKSPACE"],
                ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p", "-", "["],
                ["a", "s", "d", "f", "g", "h", "j", "k", "l", ";", "'", "\\"],
                ["<", "z", "x", "c", "v", "b", "n", "m", ",", ".", "/", "CLEAR"],
                ["SHIFT", "SPACE", "OK", "LEFT", "RIGHT"]]
        else:
            self.keys_list = additionalParams['keys_list']

        if 'shiftkeys_list' not in additionalParams:
            self.shiftkeys_list = [
                ["EXIT", "!", "@", "#", "$", "%", "^", "&", "(", ")", "=", "BACKSPACE"],
                ["Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P", "*", "]"],
                ["A", "S", "D", "F", "G", "H", "J", "K", "L", "?", '"', "|"],
                [">", "Z", "X", "C", "V", "B", "N", "M", ";", ":", "_", "CLEAR"],
                ["SHIFT", "SPACE", "OK", "LEFT", "RIGHT"]]
        else:
            # was `self.keys_list = ...` - copy-paste from the branch
            # above, silently discarding the just-set normal keys_list
            # instead of setting shiftkeys_list. No current caller passes
            # 'shiftkeys_list' in additionalParams (grepped), so this
            # never fired in practice, but it's a clear typo - fixed
            # while already in this method for the encode()/"<no" bug.
            self.shiftkeys_list = additionalParams['shiftkeys_list']

        if additionalParams.get('invert_letters_case', False):
            for keys_list in [self.keys_list, self.shiftkeys_list]:
                for row in range(len(keys_list)):
                    for idx in range(len(keys_list[row])):
                        if len(keys_list[row][idx]) != 1:
                            continue
                        upper = keys_list[row][idx].upper()
                        if upper == keys_list[row][idx]:
                            keys_list[row][idx] = keys_list[row][idx].lower()
                        else:
                            keys_list[row][idx] = upper

        self.max_key = 47 + len(self.keys_list[4])

    def virtualKeyBoardEntryComponent(self, keys):
        # every tile is forced to the same scaled self.keyPx square
        # rather than each pixmap's own native size, so the keyboard
        # actually grows on FHD/WQHD instead of staying pinned at 45px
        # regardless of tier.
        width = self.keyPx
        key_images = self.shiftMode and self.keyImagesShift or self.keyImages
        res = [(keys)]
        text = []
        x = 0
        for key in keys:
            png = key_images.get(key, None)
            if png:
                res.append(MultiContentEntryPixmapAlphaTest(pos=(x, 0), size=(width, width), png=png))
            else:
                res.append(MultiContentEntryPixmapAlphaTest(pos=(x, 0), size=(width, width), png=self.key_bg))
                # was key.encode("utf-8") - a leftover Python 2 habit
                # (str was bytes there). MultiContentEntryText wants a
                # native str under Python 3; passing bytes instead made
                # every plain-text key (anything not covered by
                # keyImages, i.e. every letter/digit) render as some
                # internal "cannot convert" placeholder truncated to
                # "<no" in each key's cell.
                text.append(MultiContentEntryText(pos=(x, 0), size=(width, width), font=0, text=key, flags=RT_HALIGN_CENTER | RT_VALIGN_CENTER))
            x += width
        return res + text

    def buildVirtualKeyBoard(self):
        self.previousSelectedKey = None
        self.list = []
        for keys in self.shiftMode and self.shiftkeys_list or self.keys_list:
            self.list.append(self.virtualKeyBoardEntryComponent(keys))
        self.markSelectedKey()

    def markSelectedKey(self):
        if self.previousSelectedKey is not None:
            self.list[self.previousSelectedKey // 12] = self.list[self.previousSelectedKey // 12][:-1]
        width = self.keyPx  # was self.key_sel.size().width() (native, unscaled) - see virtualKeyBoardEntryComponent()
        x = self.list[self.selectedKey // 12][self.selectedKey % 12 + 1][1]
        self.list[self.selectedKey // 12].append(MultiContentEntryPixmapAlphaTest(pos=(x, 0), size=(width, width), png=self.key_sel))
        self.previousSelectedKey = self.selectedKey
        self["list"].setList(self.list)

    def backClicked(self):
        self["text"].deleteBackward()

    def forwardClicked(self):
        self["text"].deleteForward()

    def shiftClicked(self):
        self.smsChar = None
        self.shiftMode = not self.shiftMode
        self.buildVirtualKeyBoard()

    def okClicked(self):
        self.smsChar = None
        # plain str, not `.encode("UTF-8")`: comparing bytes against a
        # str literal ("EXIT", "SPACE", ...) is always False under
        # Python 3, so none of the special keys (EXIT/BACKSPACE/ALL/
        # CLEAR/SHIFT/SPACE/OK/LEFT/RIGHT) would ever fire - every
        # keypress would fall through to the plain-character `else`
        # branch instead. `ok()` right below already does this correctly
        # (plain `getText()`, no encode) - matched here too.
        text = (self.shiftMode and self.shiftkeys_list or self.keys_list)[self.selectedKey // 12][self.selectedKey % 12]

        if text == "EXIT":
            self.close(None)

        elif text == "BACKSPACE":
            self["text"].deleteBackward()

        elif text == "ALL":
            self["text"].setMarkedPos(-2)

        elif text == "CLEAR":
            self["text"].deleteAllChars()
            self["text"].update()

        elif text == "SHIFT":
            self.shiftClicked()

        elif text == "SPACE":
            self["text"].insertChar(" ", self["text"].currPos, False, True)
            self["text"].innerRight()
            self["text"].update()

        elif text == "OK":
            self.close(self["text"].getText())

        elif text == "LEFT":
            self["text"].left()

        elif text == "RIGHT":
            self["text"].right()

        else:
            self["text"].insertChar(text, self["text"].currPos, False, True)
            self["text"].innerRight()
            self["text"].update()

    def ok(self):
        self.close(self["text"].getText())

    def exit(self):
        self.close(None)

    def cursorRight(self):
        self["text"].right()

    def cursorLeft(self):
        self["text"].left()

    def left(self):
        self.smsChar = None
        self.selectedKey = self.selectedKey // 12 * 12 + (self.selectedKey + 11) % 12
        if self.selectedKey > self.max_key:
            self.selectedKey = self.max_key
        self.markSelectedKey()

    def right(self):
        self.smsChar = None
        self.selectedKey = self.selectedKey // 12 * 12 + (self.selectedKey + 1) % 12
        if self.selectedKey > self.max_key:
            self.selectedKey = self.selectedKey // 12 * 12
        self.markSelectedKey()

    def up(self):
        self.smsChar = None
        self.selectedKey -= 12
        if self.selectedKey < 0:
            self.selectedKey = self.max_key // 12 * 12 + self.selectedKey % 12
            if self.selectedKey > self.max_key:
                self.selectedKey -= 12
        self.markSelectedKey()

    def down(self):
        self.smsChar = None
        self.selectedKey += 12
        if self.selectedKey > self.max_key:
            self.selectedKey = self.selectedKey % 12
        self.markSelectedKey()

    def keyNumberGlobal(self, number):
        self.smsChar = self.sms.getKey(number)
        self.selectAsciiKey(self.smsChar)

    def smsOK(self):
        if self.smsChar and self.selectAsciiKey(self.smsChar):
            self.okClicked()

    def keyGotAscii(self):
        self.smsChar = None
        # chr() already returns a native str under Python 3 - encoding it
        # and wrapping in str() again would produce "b'x'" instead of
        # "x", which would never match anything in selectAsciiKey()'s
        # keys_list/shiftkeys_list.
        if self.selectAsciiKey(chr(getPrevAsciiCode())):
            self.okClicked()

    def selectAsciiKey(self, char):
        if char == " ":
            char = "SPACE"
        for keyslist in (self.shiftkeys_list, self.keys_list):
            selkey = 0
            for keys in keyslist:
                for key in keys:
                    if key == char:
                        self.selectedKey = selkey
                        if self.shiftMode != (keyslist is self.shiftkeys_list):
                            self.shiftMode = not self.shiftMode
                            self.buildVirtualKeyBoard()
                        else:
                            self.markSelectedKey()
                        return True
                    selkey += 1
        return False
