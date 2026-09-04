# -*- coding: utf-8 -*-
#
# Shared base for the two "runs an external script, watches its stdout/
# stderr for a JSON status line" captcha widgets
# (UnCaptchaReCaptchaMyE2iWidget/UnCaptchaReCaptchaMyJDWidget). The two
# widgets share identical chrome/skin building, eConsoleAppContainer
# wiring, and stdout/stderr accumulation scaffolding here; only the
# actual command each one launches (`startExecution()`) and a handful of
# translatable strings/small parsing details genuinely differ. Those
# differences are kept as small per-subclass overrides (`ACTION_CONTEXTS`,
# `_scriptFinishedMsg()`/`_scriptFailedMsg()`, `_parseJsonLine()`,
# `startExecution()`) rather than folded together, so translatable string
# content stays untouched and each script's own quirks (MyE2i's
# regex-extracted JSON substring vs MyJD's plain `byteify()`, MyE2i's
# extra `ip_address`/`port` bookkeeping) stay exactly as they were.
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, eConnectCallback
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components import skinchrome
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
###################################################

###################################################
# FOREIGN import
###################################################
from enigma import eTimer
from Screens.Screen import Screen
from Components.Label import Label
from Components.Sources.StaticText import StaticText
from Components.ActionMap import ActionMap
###################################################


class CaptchaScriptWidgetBase(Screen):
    # Subclasses override this to pick the ActionMap context their
    # "cancel" binding needs (MyE2i used "OkCancelActions", MyJD used
    # "SetupActions" - a genuine, not-obviously-safe-to-unify difference,
    # so kept as-is instead of guessing one is more "correct").
    ACTION_CONTEXTS = ["ColorActions", "OkCancelActions"]

    def __prepareSkin(self):
        iconBase = skinchrome.getIconBase()
        HEIGHT = 320
        return """
        <screen position="center,center" title="%s" size="500,%d" resolution="1280,720" backgroundColor="#34111112" flags="wfNoBorder">
            %s
            <widget name="console" position="10,68" zPosition="2" size="480,%d" font="Regular;24" transparent="1" foregroundColor="white" backgroundColor="black" borderWidth="1" borderColor="black" />
            %s
        </screen>
    """ % (
            self.__class__.__name__,
            HEIGHT,
            skinchrome.build_header_auto(iconBase=iconBase),
            HEIGHT - 142,
            skinchrome.build_footer_auto(HEIGHT, iconBase=iconBase, keys=('red',), showNav=False, showNum=False, showOk=False, showExit=True),
        )

    def __init__(self, session, title, sitekey, referer, captchaType=None):
        self.session = session
        self.skin = self.__prepareSkin()
        Screen.__init__(self, session)
        self.sitekey = sitekey
        self.referer = referer
        self.captchaType = captchaType

        self.onShown.append(self.onStart)
        self.onClose.append(self.__onClose)

        self.setTitle(title)
        self["console"] = Label(" ")

        self["key_red"] = StaticText(_("Cancel"))

        self["actions"] = ActionMap(self.ACTION_CONTEXTS,
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

    # Subclasses override these two with their own exact original
    # translatable strings ("MyE2i script finished."/"JDownloader script
    # finished." etc.) - kept as separate strings per subclass rather than
    # a shared "%s script finished." template, so the existing de.po
    # translations for them keep matching unchanged.
    def _scriptFinishedMsg(self):
        return _('Script finished.')

    def _scriptFailedMsg(self, code):
        return _("Script execution failed.\nError code: %s\n") % (code)

    def _scriptClosed(self, code=0):
        if code == 0:
            self["console"].setText(self._scriptFinishedMsg())
            self.close(self.result)
        elif not self.errorCodeSet:
            self["console"].setText(self._scriptFailedMsg(code))

    # Subclasses override this to turn one accumulated stderr line into a
    # dict (or return None to skip it) - MyE2i's script prefixes its JSON
    # with other log text and needs a regex extraction first, MyJD's
    # doesn't and instead runs the parsed result through `byteify()`.
    def _parseJsonLine(self, line):
        raise NotImplementedError

    def _scriptStderrAvail(self, data):
        data = ensure_str(data)
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
            try:
                parsed = self._parseJsonLine(line)
                if parsed is None:
                    continue
                line = parsed
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
        data = ensure_str(data)
        self.workconsole['stdout'] += data
        self.workconsole['stdout'] = self.workconsole['stdout'].split('\n')
        if data.endswith('\n'):
            data = ''
        else:
            data = self.workconsole['stdout'].pop(-1)
        for line in self.workconsole['stdout']:
            printDBG(line)
        self.workconsole['stdout'] = data

    # Subclasses fully override this - the actual command/args built here
    # differ too much to share (different helper script, different
    # positional args, MyE2i's extra ip/port bookkeeping).
    def startExecution(self):
        raise NotImplementedError

    def onStart(self):
        self.onShown.remove(self.onStart)
        self.startExecution()

    def keyExit(self):
        self.close(self.result)

    def keyRed(self):
        self.close(self.result)
