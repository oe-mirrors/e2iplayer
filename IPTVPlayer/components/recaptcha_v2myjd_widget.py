# -*- coding: utf-8 -*-
#

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify, GetPyScriptCmd, getDebugMode, GetPluginDir, eConnectCallback
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.captchascriptwidget import CaptchaScriptWidgetBase
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str, ensure_binary
###################################################

###################################################
# FOREIGN import
###################################################
from enigma import eConsoleAppContainer
from Components.config import config

try:
    import json
except Exception:
    import simplejson as json
import base64
###################################################


class UnCaptchaReCaptchaMyJDWidget(CaptchaScriptWidgetBase):
    # the chrome/skin building, eConsoleAppContainer wiring, and
    # stdout/stderr scaffolding are shared with the near-identical
    # `UnCaptchaReCaptchaMyE2iWidget` via `CaptchaScriptWidgetBase`. Only
    # the genuinely MyJD-specific bits remain here:
    # the MyJD login/password/jdname config lookup, the exact "fakejd"
    # command, and the plain `byteify(json.loads())` parse (unlike
    # MyE2i's regex-extracted JSON substring).
    ACTION_CONTEXTS = ["ColorActions", "SetupActions"]

    def _scriptFinishedMsg(self):
        return _('JDownloader script finished.')

    def _scriptFailedMsg(self, code):
        return _("JDownloader script execution failed.\nError code: %s\n") % (code)

    def _parseJsonLine(self, line):
        return byteify(json.loads(line))

    def startExecution(self):
        login = config.plugins.iptvplayer.myjd_login.value
        password = config.plugins.iptvplayer.myjd_password.value
        jdname = config.plugins.iptvplayer.myjd_jdname.value

        captcha = {'siteKey': self.sitekey, 'sameOrigin': True, 'siteUrl': self.referer, 'contextUrl': '/'.join(self.referer.split('/')[:3]), 'boundToDomain': True, 'stoken': None}
        try:
            # ensure_binary()/ensure_str(): json.dumps() returns str under
            # Python 3, but b64encode() needs bytes - without this it
            # would raise TypeError, silently swallowed by the except
            # below, leaving `captcha` as the raw dict instead of a
            # base64 blob. Same fix in the near-identical
            # recaptcha_mye2i_widget.py.
            captcha = ensure_str(base64.b64encode(ensure_binary(json.dumps(captcha))))
        except Exception:
            printExc()
        if getDebugMode() == '':
            debug = 0
        else:
            debug = 1

        cmd = GetPyScriptCmd('fakejd') + ' "%s" "%s" "%s" "%s" "%s" %d' % (GetPluginDir('libs/'), login, password, jdname, captcha, debug)

        self["console"].setText(_('JDownloader script execution'))

        self.workconsole['console'] = eConsoleAppContainer()
        self.workconsole['close_conn'] = eConnectCallback(self.workconsole['console'].appClosed, self._scriptClosed)
        self.workconsole['stderr_conn'] = eConnectCallback(self.workconsole['console'].stderrAvail, self._scriptStderrAvail)
        self.workconsole['stdout_conn'] = eConnectCallback(self.workconsole['console'].stdoutAvail, self._scriptStdoutAvail)
        self.workconsole["console"].execute(cmd)
        printDBG(">>> EXEC CMD [%s]" % cmd)
