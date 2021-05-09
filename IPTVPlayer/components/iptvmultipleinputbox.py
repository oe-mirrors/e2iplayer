# -*- coding: utf-8 -*-
#
#  IPTVMultipleInputBox
#
#  $Id$
#
#

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.components.cover import Cover3, Cover2
from Plugins.Extensions.IPTVPlayer.components.VirtualKeyBoard import IPTVVirtualKeyBoardWithCaptcha
from Plugins.Extensions.IPTVPlayer.components.e2ivkselector import GetVirtualKeyboard
###################################################

###################################################
# FOREIGN import
###################################################
from enigma import eRCInput, getPrevAsciiCode
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ActionMap import NumberActionMap
from Components.Label import Label
from Components.Input import Input
from Tools.BoundFunction import boundFunction
from Tools.LoadPixmap import LoadPixmap
from enigma import gRGB
from skin import parseColor
###################################################


class IPTVMultipleInputBox(Screen):
    DEF_INPUT_PARAMS = {'validator': None, 'title': '', 'useable_chars': None, 'label_font': 'Regular;23', 'label_size': (550, 25), 'input_font': 'Regular;20', 'input_size': (550, 25), 'input': dict(text="", maxSize=False, visible_width=False, type=Input.TEXT)}
    DEF_PARAMS = {'title': _("Input"), 'with_accept_button': False, 'accep_label': _("Save"), 'list': []}

    def __init__(self, session, params={}):

        # Skin generator
        maxWidth = 0
        pX = 40
        pY = 60
        dY = 10
        skinItems = ''
        self.icons = []
        self.list = params['list']
        self.withAcceptButton = params.get('with_accept_button', False)
        self.statusText = params.get('status_text', '')
        statusTextHight = params.get('status_text_hight', 80)
        # calcl maxWidth size
        for idx in range(len(self.list)):
            item = self.list[idx]
            if item['label_size'][0] > maxWidth:
                maxWidth = item['label_size'][0]
            if item['input_size'][0] > maxWidth:
                maxWidth = item['input_size'][0]
        maxWidth += pX * 2

        if len(self.statusText):
            skinItems = '<widget name="statustext"   position="10,%d"  zPosition="2" size="%d,%d"  valign="center" halign="center" font="Regular;22" transparent="1" />' % (pY + dY, maxWidth - 20, statusTextHight)
            pY += statusTextHight + dY * 2

        for idx in range(len(self.list)):
            item = self.list[idx]
            if 'icon_path' in item:
                self["cover_%d" % idx] = Cover2()
                self.icons.append({'name': "cover_%d" % idx, 'path': item['icon_path']})
            else:
                self["text_%d" % idx] = Label(item.get('title', ''))
            self["input_%d" % idx] = Input(**item['input'])
            self["border_%d" % idx] = Label("")
            if item.get('useable_chars', None) is not None:
                self["input_%d" % idx].setUseableChars(item['useable_chars'])

            if 'icon_path' in item:
                skinItems += '<widget name="cover_%d" position="%d,%d" size="%d,%d" zPosition="8" />' % (idx, (maxWidth - item['label_size'][0]) / 2, pY, item['label_size'][0], item['label_size'][1])
            else:
                skinItems += '<widget name="text_%d" position="%d,%d" size="%d,%d" font="%s" zPosition="2" />' % (idx, 10, pY, item['label_size'][0], item['label_size'][1], item['label_font'])

            pY += dY + item['label_size'][1]
            skinItems += '<widget name="input_%d" position="%d,%d" size="%d,%d" font="%s" zPosition="2" />' % (idx, pX, pY, item['input_size'][0], item['input_size'][1], item['input_font'])
            skinItems += '<widget name="border_%d" position="%d,%d" size="%d,%d" font="%s" zPosition="1" transparent="0" backgroundColor="#331F93B9" />' % (idx, pX - 5, pY - 5, item['input_size'][0] + 10, item['input_size'][1] + 10, item['input_font'])
            if 0 == idx:
                self['marker'] = Cover3()
                skinItems += '<widget name="marker" zPosition="2" position="10,%d" size="16,16" transparent="1" alphatest="blend" />' % (pY + (item['input_size'][1] - 16) / 2)
            skinItems += '<widget name="marker_%d" zPosition="1" position="10,%d" size="16,16" transparent="1" alphatest="blend" />' % (idx, pY + (item['input_size'][1] - 16) / 2)
            self['marker_%d' % idx] = Cover3()
            pY += dY * 2 + item['input_size'][1]

        if self.withAcceptButton:
            skinItems += '<widget name="accept_button"  position="10,%d"  zPosition="2" size="%d,50"  valign="center" halign="center" font="Regular;22" foregroundColor="#00FFFFFF" backgroundColor="#320F0F0F" />' % (pY, maxWidth - 20)
            pY += dY * 2 + 50
        self.skin = """
        <screen name="IPTVMultipleInputBox" position="center,center" size="%d,%d" title="%s">
            <widget name="key_red"   position="10,10" zPosition="2" size="%d,35" valign="center" halign="left"   font="Regular;22" transparent="1" foregroundColor="red" />
            <widget name="key_ok"    position="10,10" zPosition="2" size="%d,35" valign="center" halign="center" font="Regular;22" transparent="1" foregroundColor="white" />
            <widget name="key_green" position="10,10" zPosition="2" size="%d,35" valign="center" halign="right"  font="Regular;22" transparent="1" foregroundColor="green" />
            %s
        </screen>
        """ % (maxWidth, pY, params.get('title', _("Input")), maxWidth - 20, maxWidth - 20, maxWidth - 20, skinItems)

        self["key_green"] = Label(params.get('accep_label', _("Save")))
        self["key_ok"] = Label(_("OK"))
        self["key_red"] = Label(_("Cancel"))
        if len(self.statusText):
            self["statustext"] = Label(str(self.statusText))
        if self.withAcceptButton:
            self["accept_button"] = Label(params.get('accep_label', _("Verify")))

        self.params = params

        Screen.__init__(self, session)
        self.onShown.append(self.onStart)
        self.onClose.append(self.__onClose)

        self["actions"] = NumberActionMap(["ColorActions", "WizardActions", "InputBoxActions", "InputAsciiActions", "KeyboardInputActions"],
        {
            "gotAsciiCode": self.gotAsciiCode,
            "green": self.keySave,
            "ok": self.keyOK,
            "red": self.keyCancel,
            "back": self.keyCancel,
            "left": self.keyLeft,
            "right": self.keyRight,
            "up": self.keyUp,
            "down": self.keyDown,
            "right": self.keyRight,
            "home": self.keyHome,
            "end": self.keyEnd,
            "deleteForward": self.keyDelete,
            "deleteBackward": self.keyBackspace,
            "tab": self.keyTab,
            "toggleOverwrite": self.keyInsert,
            "1": self.keyNumberGlobal,
            "2": self.keyNumberGlobal,
            "3": self.keyNumberGlobal,
            "4": self.keyNumberGlobal,
            "5": self.keyNumberGlobal,
            "6": self.keyNumberGlobal,
            "7": self.keyNumberGlobal,
            "8": self.keyNumberGlobal,
            "9": self.keyNumberGlobal,
            "0": self.keyNumberGlobal
        }, -1)

        self.idx = 0
        self.activeInput = "input_0"
        self.markerPixmap = [LoadPixmap(GetIconDir('radio_button_on.png')), LoadPixmap(GetIconDir('radio_button_off.png'))]

        self.started = False

    def __onClose(self):
        if self.started:
            rcinput = eRCInput.getInstance()
            rcinput.setKeyboardMode(self.keyboardMode)

    def onStart(self):
        self.onShown.remove(self.onStart)
        self.loadMarkers()
        self.setMarker()
        self.setIcons()
        rcinput = eRCInput.getInstance()
        self.keyboardMode = rcinput.getKeyboardMode()
        rcinput = None
        self.setKeyboardMode()
        self.started = True

    def setIcons(self):
        for item in self.icons:
            try:
                printDBG('Update icon: [%s]' % item['path'])
                self[item['name']].updateIcon(item['path'])
            except Exception:
                printExc()

    def loadMarkers(self):
        try:
            if "marker" in self:
                self["marker"].setPixmap(self.markerPixmap[0])
                for idx in range(len(self.list)):
                    self['marker_%d' % idx].setPixmap(self.markerPixmap[1])
        except Exception:
            printExc()

    def keyUp(self):
        if not self.started:
            return
        prevIdx = self.idx
        self.idx -= 1
        if self.idx < 0:
            if self.withAcceptButton:
                self.idx = len(self.list)
            else:
                self.idx = len(self.list) - 1
        if self.idx < len(self.list):
            self.activeInput = "input_%d" % self.idx
            self.setKeyboardMode()
        else:
            self.activeInput = ''
        self.setMarker(prevIdx)

    def keyDown(self):
        if not self.started:
            return
        prevIdx = self.idx
        self.idx += 1
        if self.idx >= len(self.list):
            if self.idx == len(self.list) and self.withAcceptButton:
                self.idx = len(self.list)
            else:
                self.idx = 0
        if self.idx < len(self.list):
            self.activeInput = "input_%d" % self.idx
            self.setKeyboardMode()
        else:
            self.activeInput = ''
        self.setMarker(prevIdx)

    def setMarker(self, prevIdx=None):
        if self.withAcceptButton:
            if self.idx == len(self.list):
                self['accept_button'].instance.setForegroundColor(parseColor("#000000"))
                self['accept_button'].instance.setBackgroundColor(parseColor("#32CD32"))
            else:
                self['accept_button'].instance.setForegroundColor(parseColor("#FFFFFF"))
                self['accept_button'].instance.setBackgroundColor(parseColor("#320F0F0F"))

        if "marker" in self:
            if self.idx < len(self.list):
                x, y = self["marker_%d" % self.idx].getPosition()
                self["marker"].setPosition(x, y)
                self["marker"].show()
            else:
                self["marker"].hide()
        try:
            if None != prevIdx:
                if prevIdx < len(self.list):
                    self["border_%d" % prevIdx].hide()
            else:
                for idx in range(len(self.list)):
                    self["border_%d" % idx].hide()
            if self.idx < len(self.list):
                self["border_%d" % self.idx].show()
        except Exception:
            printExc()

    def setKeyboardMode(self):
        if self.activeInput == '':
            return

        rcinput = eRCInput.getInstance()
        printDBG("setKeyboardMode current_mode[%r] ASCI[%r] none[%r] type_text[%r] intput_type[%r]" % (rcinput.getKeyboardMode(), rcinput.kmAscii, rcinput.kmNone, Input.TEXT, self[self.activeInput].type))
        rcinput.setKeyboardMode(rcinput.kmNone)
        return
        if self[self.activeInput].type == Input.TEXT:
            rcinput.setKeyboardMode(rcinput.kmAscii)
        else:
            rcinput.setKeyboardMode(rcinput.kmNone)

    def gotAsciiCode(self):
        if self.activeInput == '':
            return
        self[self.activeInput].handleAscii(getPrevAsciiCode())

    def keyLeft(self):
        if self.activeInput == '':
            return
        self[self.activeInput].left()

    def keyRight(self):
        if self.activeInput == '':
            return
        self[self.activeInput].right()

    def keyNumberGlobal(self, number):
        if self.activeInput == '':
            return
        self[self.activeInput].number(number)

    def keyDelete(self):
        if self.activeInput == '':
            return
        self[self.activeInput].delete()

    def keySave(self):
        retList = []
        for idx in range(len(self.list)):
            if None != self.list[idx]['validator']:
                sts, msg = self.list[idx]['validator'](self["input_%d" % idx].getText())
                if not sts:
                    self.session.open(MessageBox, msg, type=MessageBox.TYPE_ERROR)
                    self.idx = idx
                    self.activeInput = "input_%d" % idx
                    self.setMarker()
                    return
            retList.append(self["input_%d" % idx].getText())
        self.close(retList)

    def keyOK(self):
        if self.idx == len(self.list):
            self.keySave()
            return

        def VirtualKeyBoardCallBack(newTxt):
            if isinstance(newTxt, basestring):
                self[self.activeInput].setText(newTxt)
            self.setKeyboardMode()

        # title
        try:
            title = self.list[self.idx]['title']
        except Exception:
            title = ''

        # virtual keyboard type
        captchaKeyBoard = False
        try:
            if 'icon_path' in self.list[self.idx] and (self.list[self.idx]['icon_path'].endswith('.jpg') or self.list[self.idx]['icon_path'].endswith('.png')):
                captchaKeyBoard = True
                captchaSize = self.list[self.idx]['label_size']
                captchaPath = self.list[self.idx]['icon_path']
                params = dict(self.params.get('vk_params', {}))
                params.update({'captcha_size': captchaSize, 'captcha_path': captchaPath})
        except Exception:
            printExc()

        if not captchaKeyBoard:
            self.session.openWithCallback(VirtualKeyBoardCallBack, GetVirtualKeyboard(), title=title, text=self[self.activeInput].getText())
        else:
            self.session.openWithCallback(VirtualKeyBoardCallBack, IPTVVirtualKeyBoardWithCaptcha, title=title, text=self[self.activeInput].getText(), additionalParams=params)

    def keyCancel(self):
        self.close(None)

    def keyHome(self):
        if self.activeInput == '':
            return
        self[self.activeInput].home()

    def keyEnd(self):
        if self.activeInput == '':
            return
        self[self.activeInput].end()

    def keyBackspace(self):
        if self.activeInput == '':
            return
        self[self.activeInput].deleteBackward()

    def keyTab(self):
        if self.activeInput == '':
            return
        self[self.activeInput].tab()

    def keyInsert(self):
        if self.activeInput == '':
            return
        self[self.activeInput].toggleOverwrite()
