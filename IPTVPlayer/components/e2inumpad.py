# -*- coding: utf-8 -*-
#
#  E2iPlayer numeric keypad
#
#  Small digits-only counterpart of E2iVirtualKeyBoard for fields that only
#  ever take a whole number (page jumps, ConfigInteger settings). Same call
#  convention as the full keyboard - (session, title=, text=,
#  additionalParams=) in, the entered text (or None on EXIT) out - so a
#  caller can switch between the two without touching its callback.
#
from Screens.Screen import Screen
from Components.ActionMap import NumberActionMap
from Components.Label import Label
from Components.Sources.StaticText import StaticText
from enigma import gRGB, getPrevAsciiCode
from Tools.LoadPixmap import LoadPixmap

from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.cover import Cover3
from Plugins.Extensions.IPTVPlayer.components import skinchrome


class E2iNumericKeyBoard(Screen):
    # HD-reference geometry, the screen itself is auto-scaled via
    # resolution="1280,720" (same as IPTVPinWidget)
    KEY = 70
    COLS = 3
    # without a limit a page number is the only thing typed here
    DEFAULT_MAX_DIGITS = 6

    COLOR_TEXT = 0xFFFFFF
    COLOR_TEXT_PRESET = 0x8A8F9C
    COLOR_RANGE = 0xB6B6B6
    COLOR_RANGE_BAD = 0xFF4040

    def __init__(self, session, title="", text="", additionalParams={}):
        self.session = session
        self.minValue = additionalParams.get('min_value')
        self.maxValue = additionalParams.get('max_value')
        self.allowNegative = self.minValue is not None and self.minValue < 0

        # bottom row: the key left of 0 is +/- on a field that allows
        # negative values, Clear otherwise; row 5 is a full-width OK bar
        self.keyRows = [['1', '2', '3'], ['4', '5', '6'], ['7', '8', '9'], ['sign' if self.allowNegative else 'clear', '0', 'back'], ['ok']]

        self.skin = self.__prepareSkin()
        Screen.__init__(self, session)
        self.skinName = skinchrome.forceInternalSkinName(["E2iNumericKeyBoard"])
        self.setTitle(title)

        self["actions"] = NumberActionMap(["WizardActions", "DirectionActions", "ColorActions", "NumberActions", "KeyboardInputActions", "InputAsciiActions"],
        {
            "ok": self.keyOK,
            "back": self.keyBack,
            "up": self.keyUp,
            "down": self.keyDown,
            "left": self.keyLeft,
            "right": self.keyRight,
            "green": self.accept,
            "blue": self.toggleSign,
            "deleteBackward": self.backspace,
            "gotAsciiCode": self.keyGotAscii,
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

        self["text"] = Label("")
        self["range"] = Label("")
        self["input_bg"] = Cover3()
        for rowIdx, row in enumerate(self.keyRows):
            for colIdx, key in enumerate(row):
                name = self._keyName(rowIdx, colIdx)
                self[name] = Cover3()
                self[name + "_m"] = Cover3()
                self[name + "_l"] = Label(self._keyLabel(key))
        self["back_icon"] = Cover3()
        self["key_green"] = StaticText(_("Accept"))
        self["key_blue"] = StaticText("+/-" if self.allowNegative else "")

        self.maxDigits = self.DEFAULT_MAX_DIGITS
        bounds = [abs(v) for v in (self.minValue, self.maxValue) if v is not None]
        if self.maxValue is not None and bounds:
            self.maxDigits = len(str(max(bounds)))

        # the preset value (e.g. the setting's current value) is shown
        # greyed out and the first digit typed replaces it, so a new value
        # never needs a round of backspaces first
        self.text = self._sanitize(text)
        self.preset = bool(self.text)

        # start on the OK bar: OK right away keeps the preset, digits come
        # from the remote's number keys anyway
        self.rowIdx = len(self.keyRows) - 1
        self.colIdx = 0

        self.onLayoutFinish.append(self.onStart)

    def __prepareSkin(self):
        iconBase = skinchrome.getIconBase()
        keyBase = iconBase + "/e2ivk"
        key = self.KEY
        gridW = self.COLS * key
        # a +/- field also shows the blue footer key, one colour slot more
        width = 640 if self.allowNegative else 520
        gridX = (width - gridW) // 2
        inputX, inputY, inputW, inputH = 40, 76, width - 80, 50
        rangeY = inputY + inputH + 6
        gridY = rangeY + 34
        height = gridY + len(self.keyRows) * key + 16 + skinchrome.footer_height()

        parts = ['<screen name="E2iNumericKeyBoard" position="center,center" size="%d,%d" resolution="1280,720" title="E2iPlayer" backgroundColor="#34111112" flags="wfNoBorder">' % (width, height)]
        parts.append(skinchrome.build_header_auto(iconBase=iconBase))
        parts.append('<widget name="input_bg" position="%d,%d" size="%d,%d" zPosition="1" scale="1" alphatest="blend" transparent="1" />' % (inputX, inputY, inputW, inputH))
        parts.append('<widget name="text" position="%d,%d" size="%d,%d" zPosition="2" font="Regular;32" halign="center" valign="center" noWrap="1" transparent="1" foregroundColor="#ffffff" backgroundColor="#404551" />' % (inputX + 10, inputY, inputW - 20, inputH))
        parts.append('<widget name="range" position="%d,%d" size="%d,%d" zPosition="2" font="Regular;18" halign="center" valign="center" noWrap="1" transparent="1" foregroundColor="#b6b6b6" backgroundColor="#34111112" />' % (inputX, rangeY, inputW, 26))
        for rowIdx, row in enumerate(self.keyRows):
            keyW = gridW // len(row)
            for colIdx, name in enumerate(row):
                wName = self._keyName(rowIdx, colIdx)
                x, y = gridX + colIdx * keyW, gridY + rowIdx * key
                parts.append('<widget name="%s" position="%d,%d" size="%d,%d" zPosition="1" scale="1" alphatest="blend" transparent="1" />' % (wName, x, y, keyW, key))
                parts.append('<widget name="%s_m" position="%d,%d" size="%d,%d" zPosition="5" scale="1" alphatest="blend" transparent="1" />' % (wName, x, y, keyW, key))
                font = 34 if name.isdigit() else 24
                # same colours as E2iVirtualKeyBoard's normal/special keys
                bg = '#404551' if name.isdigit() else '#1688b2'
                parts.append('<widget name="%s_l" position="%d,%d" size="%d,%d" zPosition="3" font="Regular;%d" halign="center" valign="center" noWrap="1" transparent="1" foregroundColor="#ffffff" backgroundColor="%s" />' % (wName, x, y, keyW, key, font, bg))
                if name == 'back':
                    # b.png is ~6:5, same box shape E2iVirtualKeyBoard uses for it
                    iconW, iconH = 34, 29
                    parts.append('<widget name="back_icon" position="%d,%d" size="%d,%d" zPosition="3" scale="1" alphatest="blend" transparent="1" />' % (x + (keyW - iconW) // 2, y + (key - iconH) // 2, iconW, iconH))
        parts.append(skinchrome.build_footer_auto(height, iconBase=iconBase, keys=('green', 'blue'), showNav=True, showNum=True, showOk=True, showExit=True))
        parts.append('</screen>')
        self._keyBase = keyBase
        return '\n'.join(parts)

    def _keyName(self, rowIdx, colIdx):
        return "key_%d_%d" % (rowIdx, colIdx)

    def _keyLabel(self, key):
        if key == 'ok':
            return "OK"
        elif key == 'clear':
            return "C"
        elif key == 'sign':
            return "+/-"
        elif key == 'back':
            return ""
        return key

    def _sanitize(self, text):
        try:
            text = str(text).strip()
        except Exception:
            return ''
        negative = text.startswith('-') and self.allowNegative
        digits = ''.join([c for c in text if c.isdigit()])[:self.maxDigits]
        if not digits:
            return ''
        return ('-' if negative else '') + str(int(digits))

    def onStart(self):
        self.onLayoutFinish.remove(self.onStart)
        try:
            pix = {}
            for name in ('e', 'k', 'k_s', 'k_m', 'k2_s', 'k2_m', 'b'):
                pix[name] = LoadPixmap(self._keyBase + '/%s.png' % name)
            self["input_bg"].setPixmap(pix['e'])
            for rowIdx, row in enumerate(self.keyRows):
                for colIdx, key in enumerate(row):
                    name = self._keyName(rowIdx, colIdx)
                    if key == 'ok':
                        self[name].setPixmap(pix['k2_s'])
                        self[name + "_m"].setPixmap(pix['k2_m'])
                    else:
                        self[name].setPixmap(pix['k'] if key.isdigit() else pix['k_s'])
                        self[name + "_m"].setPixmap(pix['k_m'])
                    self[name + "_m"].hide()
            self["back_icon"].setPixmap(pix['b'])
        except Exception:
            printExc()
        self.moveMarker(-1, -1)
        self.updateText()

    # ---- display ----

    def moveMarker(self, oldRow, oldCol):
        if oldRow >= 0:
            self[self._keyName(oldRow, oldCol) + "_m"].hide()
        self[self._keyName(self.rowIdx, self.colIdx) + "_m"].show()

    def isInRange(self, value):
        if self.minValue is not None and value < self.minValue:
            return False
        if self.maxValue is not None and value > self.maxValue:
            return False
        return True

    def updateText(self):
        try:
            self["text"].instance.setForegroundColor(gRGB(self.COLOR_TEXT_PRESET if self.preset else self.COLOR_TEXT))
        except Exception:
            printExc()
        self["text"].setText(self.text)

        rangeText = ''
        if self.maxValue is not None:
            rangeText = "%d - %d" % (self.minValue if self.minValue is not None else 0, self.maxValue)
        bad = False
        if self.text not in ('', '-'):
            bad = not self.isInRange(int(self.text))
        try:
            self["range"].instance.setForegroundColor(gRGB(self.COLOR_RANGE_BAD if bad else self.COLOR_RANGE))
        except Exception:
            printExc()
        self["range"].setText(rangeText)

    # ---- editing ----

    def _takeOverPreset(self):
        if self.preset:
            self.preset = False
            self.text = ''

    def addDigit(self, digit):
        self._takeOverPreset()
        sign = '-' if self.text.startswith('-') else ''
        digits = self.text[len(sign):]
        if digits == '0':
            digits = ''
        if len(digits) >= self.maxDigits:
            return
        self.text = sign + digits + str(digit)
        self.updateText()

    def backspace(self):
        self.preset = False
        # "-3" becomes "-", so the sign survives retyping the digit
        self.text = self.text[:-1]
        self.updateText()

    def clear(self):
        self.preset = False
        self.text = ''
        self.updateText()

    def toggleSign(self):
        if not self.allowNegative:
            return
        self.preset = False
        if self.text.startswith('-'):
            self.text = self.text[1:]
        else:
            self.text = '-' + self.text
        self.updateText()

    def accept(self):
        if self.text in ('', '-'):
            self.close('')
            return
        value = int(self.text)
        if self.minValue is not None and value < self.minValue:
            value = self.minValue
        if self.maxValue is not None and value > self.maxValue:
            value = self.maxValue
        printDBG("E2iNumericKeyBoard.accept [%s] -> [%d]" % (self.text, value))
        self.close(str(value))

    # ---- keys ----

    def keyNumberGlobal(self, number):
        self.addDigit(number)

    def keyGotAscii(self):
        try:
            char = getPrevAsciiCode()
        except Exception:
            printExc()
            return
        if 48 <= char <= 57:
            self.addDigit(char - 48)
        elif char == 45:
            self.toggleSign()
        elif char == 8:
            self.backspace()
        elif char in (10, 13):
            self.accept()

    def keyOK(self):
        key = self.keyRows[self.rowIdx][self.colIdx]
        if key.isdigit():
            self.addDigit(int(key))
        elif key == 'back':
            self.backspace()
        elif key == 'clear':
            self.clear()
        elif key == 'sign':
            self.toggleSign()
        elif key == 'ok':
            self.accept()

    def keyBack(self):
        self.close(None)

    def _moveTo(self, rowIdx, colIdx):
        oldRow, oldCol = self.rowIdx, self.colIdx
        self.rowIdx = rowIdx
        self.colIdx = min(colIdx, len(self.keyRows[rowIdx]) - 1)
        self.moveMarker(oldRow, oldCol)

    def keyUp(self):
        rowIdx = (self.rowIdx - 1) % len(self.keyRows)
        # leaving the one-key OK bar upwards lands on the middle key (0)
        colIdx = self.COLS // 2 if len(self.keyRows[self.rowIdx]) == 1 else self.colIdx
        self._moveTo(rowIdx, colIdx)

    def keyDown(self):
        rowIdx = (self.rowIdx + 1) % len(self.keyRows)
        colIdx = self.COLS // 2 if len(self.keyRows[self.rowIdx]) == 1 else self.colIdx
        self._moveTo(rowIdx, colIdx)

    def keyLeft(self):
        row = self.keyRows[self.rowIdx]
        self._moveTo(self.rowIdx, (self.colIdx - 1) % len(row))

    def keyRight(self):
        row = self.keyRows[self.rowIdx]
        self._moveTo(self.rowIdx, (self.colIdx + 1) % len(row))
