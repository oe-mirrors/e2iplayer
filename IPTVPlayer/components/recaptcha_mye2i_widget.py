# -*- coding: utf-8 -*-
#

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetPyScriptCmd, getDebugMode, get_ip, is_port_in_use, eConnectCallback
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.captchascriptwidget import CaptchaScriptWidgetBase
###################################################

###################################################
# FOREIGN import
###################################################
from enigma import eConsoleAppContainer

from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str, ensure_binary

try:
    import json
except Exception:
    import simplejson as json
import re
import base64
###################################################


class UnCaptchaReCaptchaMyE2iWidget(CaptchaScriptWidgetBase):
    # the chrome/skin building, eConsoleAppContainer wiring, and
    # stdout/stderr scaffolding are shared with the near-identical
    # `UnCaptchaReCaptchaMyJDWidget` via `CaptchaScriptWidgetBase`. Only
    # the genuinely MyE2i-specific bits remain here:
    # `ip_address`/`port` bookkeeping, the exact `mye2iserver` command,
    # and the regex-based JSON-substring extraction its script's log
    # output actually needs (unlike MyJD's plain `byteify(json.loads())`).
    ACTION_CONTEXTS = ["ColorActions", "OkCancelActions"]

    def __init__(self, session, title, sitekey, referer, captchaType):
        CaptchaScriptWidgetBase.__init__(self, session, title, sitekey, referer, captchaType)
        self.ip_address = get_ip()
        self.port = 9001

    def _scriptFinishedMsg(self):
        return _('MyE2i script finished.')

    def _scriptFailedMsg(self, code):
        return _("MyE2i script execution failed.\nError code: %s\n") % (code)

    def _parseJsonLine(self, line):
        matches = re.findall("{.*}", line)
        if not matches:
            return None
        return json.loads(matches[0])

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
