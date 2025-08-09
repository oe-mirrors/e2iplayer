# -*- coding: utf-8 -*-
#

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir, eConnectCallback, GetPyScriptCmd, getDebugMode, get_ip, is_port_in_use
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
###################################################

###################################################
# FOREIGN import
###################################################
from enigma import eConsoleAppContainer, eTimer, getDesktop
from Screens.Screen import Screen
from Components.Label import Label
from Components.ActionMap import ActionMap

from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str, ensure_binary

try:
    import json
except Exception:
    import simplejson as json
import re
import base64
###################################################


class UnCaptchaReCaptchaMyE2iWidget(Screen):
    skin = """
        <screen position="center,center" title="UnCaptchaReCaptchaMyE2iWidget" size="500,300" resolution="1280,720" backgroundColor="#34111112" flags="wfNoBorder">
            <eLabel name="BG_Title" position="0,0" size="500,50" backgroundColor="#100d0f16" zPosition="-1" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/smallshadowline.png" position="0,50" size="e,2" zPosition="2" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/smallshadowline.png" position="0,260" size="e,2" zPosition="2" />
            <ePixmap position="20,272" size="20,20" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/HD/red.png" alphatest="blend" transparent="1" />
            <widget name="label_red" position="54,268" size="200,28" zPosition="1" font="Regular;20" backgroundColor="black" foregroundColor="white" halign="left" transparent="1" valign="center" noWrap="1" />
            <widget name="title" position="10,14" size="e-10,30" foregroundColor="#0066ccff" backgroundColor="black" borderWidth="1" borderColor="black" transparent="1" zPosition="1" font="Regular;24" valign="center" />
            <widget name="console" position="5,60" zPosition="2" size="490,200" font="Regular;24" scrollbarMode="showOnDemand" scrollbarSliderBorderWidth="1" scrollbarForegroundColor="#001B5A91" scrollbarBorderColor="#00b6b6b6" enableWrapAround="1" transparent="1" foregroundColor="white" backgroundColor="black" borderWidth="1" borderColor="black" />
        </screen>
    """
    fullHD = getDesktop(0).size().width() == 1920
    if fullHD:
        skin = skin.replace("/HD/", "/FHD/")

    def __init__(self, session, title, sitekey, referer, captchaType):
        self.session = session
        Screen.__init__(self, session)
        self.sitekey = sitekey
        self.referer = referer
        self.captchaType = captchaType

        self.onShown.append(self.onStart)
        self.onClose.append(self.__onClose)

        self["title"] = Label(title)
        self["console"] = Label(" ")

        self["label_red"] = Label(_("Cancel"))

        self["actions"] = ActionMap(["ColorActions", "OKCancelActions"],
        {
            "cancel": self.keyExit,
            # "ok"    : self.keyOK,
            "red": self.keyRed,
        }, -2)

        self.workconsole = {'console': None, 'close_conn': None, 'stderr_conn': None, 'stdout_conn': None, 'stderr': '', 'stdout': ''}
        self.result = ''

        self.timer = {'timer': eTimer(), 'is_started': False}
        self.timer['callback_conn'] = eConnectCallback(self.timer['timer'].timeout, self._timoutCallback)
        self.errorCodeSet = False

        self.ip_address = get_ip()
        self.port = 9001

    def _timoutCallback(self):
        self.timer['is_started'] = False
        self.close(self.result)

    def __onClose(self):
        self.workconsole['close_conn'] = None
        self.workconsole['stderr_conn'] = None
        self.workconsole['stdout_conn'] = None
        if self.workconsole['console']:
            self.workconsole['console'].sendCtrlC()
        self.workconsole['console'] = None

        if self.timer['is_started']:
            self.timer['timer'].stop()
        self.timer['callback_conn'] = None
        self.timer = None

    def _scriptClosed(self, code=0):
        if code == 0:
            self["console"].setText(_('MyE2i script finished.'))
            self.close(self.result)
        elif not self.errorCodeSet:
            self["console"].setText(_("MyE2i script execution failed.\nError code: %s\n") % (code))

    def _scriptStderrAvail(self, data):
        data = data.decode()
        self.workconsole['stderr'] += data
        self.workconsole['stderr'] = self.workconsole['stderr'].split('\n')
        if data.endswith('\n'):
            data = ''
        else:
            data = self.workconsole['stderr'].pop(-1)
        for line in self.workconsole['stderr']:
            line = line.strip()
            if line == '':
                continue
            line = re.findall("{.*}", line)
            if len(line) == 0:
                continue
            try:
                line = json.loads(line[0])
                if line['type'] == 'captcha_result':
                    self.result = line['data']
                    # timeout timer
                    if self.timer['is_started']:
                        self.timer['timer'].stop()
                    # start timeout timer 3s
                    self.timer['timer'].start(3000, True)
                    self.timer['is_started'] = True
                    self["console"].setText(_('Captcha solved.\nWaiting for notification.'))
                elif line['type'] == 'status':
                    self["console"].setText(_(str(line['data'])))
                elif line['type'] == 'error':
                    if line['code'] == 500:
                        self["console"].setText(_('Invalid email.'))
                    elif line['code'] == 403:
                        self["console"].setText(_('Access denied. Please check password.'))
                    else:
                        self["console"].setText(_("Error code: %s\nError message: %s") % (line['code'], line['data']))
                    self.errorCodeSet = True
            except Exception:
                printExc('Current line |%s|' % str(line))
        self.workconsole['stderr'] = data

    def _scriptStdoutAvail(self, data):
        data = data.decode()
        self.workconsole['stdout'] += data
        self.workconsole['stdout'] = self.workconsole['stdout'].split('\n')
        if data.endswith('\n'):
            data = ''
        else:
            data = self.workconsole['stdout'].pop(-1)
        for line in self.workconsole['stdout']:
            printDBG(line)
        self.workconsole['stdout'] = data

    def startExecution(self):
        captcha = {'siteKey': self.sitekey, 'sameOrigin': True, 'siteUrl': self.referer, 'contextUrl': '/'.join(self.referer.split('/')[:3]), 'boundToDomain': True, 'stoken': None, 'captchaType': self.captchaType}
        try:
            captcha = ensure_str(base64.b64encode(ensure_binary(json.dumps(captcha))))
        except Exception:
            printExc()

        if getDebugMode() == '':
            debug = 0
        else:
            debug = 1

        while is_port_in_use(self.ip_address, self.port):
            self.port += 1

        cmd = GetPyScriptCmd('mye2iserver') + ' "%s" "%s" "%s"' % (captcha, self.ip_address, self.port)

        self["console"].setText(_('Please Open site:\nhttp://{0}:{1}\nin a web browser with the MyE2i extension installed').format(self.ip_address, self.port))

        self.workconsole['console'] = eConsoleAppContainer()
        self.workconsole['close_conn'] = eConnectCallback(self.workconsole['console'].appClosed, self._scriptClosed)
        self.workconsole['stderr_conn'] = eConnectCallback(self.workconsole['console'].stderrAvail, self._scriptStderrAvail)
        self.workconsole['stdout_conn'] = eConnectCallback(self.workconsole['console'].stdoutAvail, self._scriptStdoutAvail)
        self.workconsole["console"].execute(cmd)
        printDBG(">>> EXEC CMD [%s]" % cmd)

    def onStart(self):
        self.onShown.remove(self.onStart)
        self.startExecution()

    def keyExit(self):
        self.close(self.result)

    def keyRed(self):
        self.close(self.result)
