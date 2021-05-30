# -*- coding: UTF-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.cover import Cover3, Cover2
###################################################

###################################################
# FOREIGN import
###################################################
from enigma import eListboxPythonMultiContent, gFont, RT_HALIGN_CENTER, RT_VALIGN_CENTER, getPrevAsciiCode
from Screens.Screen import Screen
from Components.ActionMap import NumberActionMap
from Components.Input import Input
from Components.Label import Label
from Components.Pixmap import Pixmap
from Components.MenuList import MenuList
from Components.MultiContent import MultiContentEntryText, MultiContentEntryPixmapAlphaTest
from Tools.Directories import resolveFilename, SCOPE_CURRENT_SKIN
from Tools.LoadPixmap import LoadPixmap
from Tools.NumericalTextInput import NumericalTextInput
###################################################


class VirtualKeyBoardList(MenuList):
    def __init__(self, list, enableWrapAround=False):
        MenuList.__init__(self, list, enableWrapAround, eListboxPythonMultiContent)
        self.l.setFont(0, gFont("Regular", 28))
        self.l.setItemHeight(45)


class IPTVVirtualKeyBoardWithCaptcha(Screen):

    def __init__(self, session, title="", text="", additionalParams={}):
        winWidth = 590
        self.skin = '''<screen position="center,center" size="%d,500" title="" >
                           <widget name="captcha" position="%d,%d" size="%d,%d" zPosition="2" transparent="1" alphatest="on" />

                           <widget name="key_red"   position="10,10" zPosition="2" size="%d,35" valign="center" halign="left"   font="Regular;22" transparent="1" foregroundColor="red" />
                           <widget name="key_ok"    position="10,10" zPosition="2" size="%d,35" valign="center" halign="center" font="Regular;22" transparent="1" foregroundColor="white" />
                           <widget name="key_green" position="10,10" zPosition="2" size="%d,35" valign="center" halign="right"  font="Regular;22" transparent="1" foregroundColor="green" />

                           <ePixmap pixmap="%s"  position="25,195" size="542,80" zPosition="-4" alphatest="on" />
                           <widget name="header" position="25,160" size="500,26" transparent="1" noWrap="1" font="Regular;20" valign="top"/>
                           <widget name="text"   position="25,200" size="536,34" transparent="1" noWrap="1" font="Regular;26" valign="center" halign="right" />
                           <widget name="list"   position="25,250" size="550,225" selectionDisabled="1" transparent="1" />
                       </screen>
                    ''' % (winWidth, 10, 55,
                            winWidth - 20, 100,
                            winWidth - 20,
                            winWidth - 20,
                            winWidth - 20,
                            GetIconDir("vk/vkey_text.png"))

        Screen.__init__(self, session)
        self.keys_list = []
        self.shiftkeys_list = []
        self.shiftMode = additionalParams.get('shift_mode', False)
        self.selectedKey = 0
        self.smsChar = None
        self.sms = NumericalTextInput(self.smsOK)

        self.key_bg = LoadPixmap(GetIconDir("vk/vkey_bg.png"))
        self.key_sel = LoadPixmap(GetIconDir("vk/vkey_sel.png"))
        self.key_backspace = LoadPixmap(GetIconDir("vk/vkey_backspace.png"))
        self.key_all = LoadPixmap(GetIconDir("vk/vkey_all.png"))
        self.key_clr = LoadPixmap(GetIconDir("vk/vkey_clr.png"))
        self.key_esc = LoadPixmap(GetIconDir("vk/vkey_esc.png"))
        self.key_ok = LoadPixmap(GetIconDir("vk/vkey_ok.png"))
        self.key_shift = LoadPixmap(GetIconDir("vk/vkey_shift.png"))
        self.key_shift_sel = LoadPixmap(GetIconDir("vk/vkey_shift_sel.png"))
        self.key_space = LoadPixmap(GetIconDir("vk/vkey_space.png"))
        self.key_left = LoadPixmap(GetIconDir("vk/vkey_left.png"))
        self.key_right = LoadPixmap(GetIconDir("vk/vkey_right.png"))

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

        self["key_green"] = Label(_("Accept"))
        self["key_ok"] = Label(_("OK"))
        self["key_red"] = Label(_("Cancel"))

        self["header"] = Label(title)
        self["text"] = Input(text=text.decode("utf-8", 'ignore'))
        self["list"] = VirtualKeyBoardList([])

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
                [u"EXIT", u"1", u"2", u"3", u"4", u"5", u"6", u"7", u"8", u"9", u"0", u"BACKSPACE"],
                [u"q", u"w", u"e", u"r", u"t", u"y", u"u", u"i", u"o", u"p", u"-", u"["],
                [u"a", u"s", u"d", u"f", u"g", u"h", u"j", u"k", u"l", u";", u"'", u"\\"],
                [u"<", u"z", u"x", u"c", u"v", u"b", u"n", u"m", u",", ".", u"/", u"CLEAR"],
                [u"SHIFT", u"SPACE", u"OK", u"LEFT", u"RIGHT"]]
        else:
            self.keys_list = additionalParams['keys_list']

        if 'shiftkeys_list' not in additionalParams:
            self.shiftkeys_list = [
                [u"EXIT", u"!", u"@", u"#", u"$", u"%", u"^", u"&", u"(", u")", u"=", u"BACKSPACE"],
                [u"Q", u"W", u"E", u"R", u"T", u"Y", u"U", u"I", u"O", u"P", u"*", u"]"],
                [u"A", u"S", u"D", u"F", u"G", u"H", u"J", u"K", u"L", u"?", u'"', u"|"],
                [u">", u"Z", u"X", u"C", u"V", u"B", u"N", u"M", u";", u":", u"_", u"CLEAR"],
                [u"SHIFT", u"SPACE", u"OK", u"LEFT", u"RIGHT"]]
        else:
            self.keys_list = additionalParams['shiftkeys_list']

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
        key_bg_width = self.key_bg and self.key_bg.size().width() or 45
        key_images = self.shiftMode and self.keyImagesShift or self.keyImages
        res = [(keys)]
        text = []
        x = 0
        for key in keys:
            png = key_images.get(key, None)
            if png:
                width = png.size().width()
                res.append(MultiContentEntryPixmapAlphaTest(pos=(x, 0), size=(width, 45), png=png))
            else:
                width = key_bg_width
                res.append(MultiContentEntryPixmapAlphaTest(pos=(x, 0), size=(width, 45), png=self.key_bg))
                text.append(MultiContentEntryText(pos=(x, 0), size=(width, 45), font=0, text=key.encode("utf-8"), flags=RT_HALIGN_CENTER | RT_VALIGN_CENTER))
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
            self.list[self.previousSelectedKey / 12] = self.list[self.previousSelectedKey / 12][:-1]
        width = self.key_sel.size().width()
        x = self.list[self.selectedKey / 12][self.selectedKey % 12 + 1][1]
        self.list[self.selectedKey / 12].append(MultiContentEntryPixmapAlphaTest(pos=(x, 0), size=(width, 45), png=self.key_sel))
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
        text = (self.shiftMode and self.shiftkeys_list or self.keys_list)[self.selectedKey / 12][self.selectedKey % 12].encode("UTF-8")

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
            self["text"].insertChar(" ".encode("UTF-8"), self["text"].currPos, False, True)
            self["text"].innerright()
            self["text"].update()

        elif text == "OK":
            self.close(self["text"].getText().encode("UTF-8"))

        elif text == "LEFT":
            self["text"].left()

        elif text == "RIGHT":
            self["text"].right()

        else:
            self["text"].insertChar(text, self["text"].currPos, False, True)
            self["text"].innerright()
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
        self.selectedKey = self.selectedKey / 12 * 12 + (self.selectedKey + 11) % 12
        if self.selectedKey > self.max_key:
            self.selectedKey = self.max_key
        self.markSelectedKey()

    def right(self):
        self.smsChar = None
        self.selectedKey = self.selectedKey / 12 * 12 + (self.selectedKey + 1) % 12
        if self.selectedKey > self.max_key:
            self.selectedKey = self.selectedKey / 12 * 12
        self.markSelectedKey()

    def up(self):
        self.smsChar = None
        self.selectedKey -= 12
        if self.selectedKey < 0:
            self.selectedKey = self.max_key / 12 * 12 + self.selectedKey % 12
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
        if self.selectAsciiKey(str(unichr(getPrevAsciiCode()).encode('utf-8'))):
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
