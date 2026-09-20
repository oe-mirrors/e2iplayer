# -*- coding: utf-8 -*-
#

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm, GetTmpDir, GetPyScriptCmd, get_ip, is_port_in_use, eConnectCallback
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.captchascriptwidget import CaptchaScriptWidgetBase
from Plugins.Extensions.IPTVPlayer.libs.web_qr import make_qr_png
from Plugins.Extensions.IPTVPlayer.components import skinchrome
###################################################

###################################################
# FOREIGN import
###################################################
from enigma import eConsoleAppContainer
from Components.ActionMap import ActionMap
from Components.config import config
from Components.Label import Label
from Components.Pixmap import Pixmap
from Components.Sources.StaticText import StaticText
from Screens.Screen import Screen
from Tools.LoadPixmap import LoadPixmap

from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str, ensure_binary

try:
    import json
except Exception:
    import simplejson as json
import re
import base64
import binascii
import os
###################################################

# HD-reference width the QR pixmap strip adds next to the shared console box,
# and the square QR pixmap's own size within that strip - kept equal to the
# console's own height (see `_prepareSkin`'s HEIGHT - 142) so it lines up
# with the console box instead of reaching down into the footer below it.
_QR_STRIP_WIDTH = 220
_QR_SIZE = 178

WIKI_URL = 'https://github.com/oe-mirrors/e2iplayer/wiki/Solve-Cloudflare-hCaptcha-reCAPTCHA-with-MyE2i'


class MyE2iHelpScreen(Screen):
    # Small help window of the MyE2i captcha screen (YELLOW / INFO / HELP): what to do,
    # and a QR code that leads to the wiki page.
    WIDTH = 860
    HEIGHT = 440
    QR_SIZE = 220

    def __init__(self, session):
        iconBase = skinchrome.getIconBase()
        textWidth = self.WIDTH - self.QR_SIZE - 50
        self.skin = """
        <screen position="center,center" title="%s" size="%d,%d" resolution="1280,720" backgroundColor="#34111112" flags="wfNoBorder">
            %s
            <widget name="text" position="10,68" zPosition="2" size="%d,%d" font="Regular;20" transparent="1" foregroundColor="white" backgroundColor="black" borderWidth="1" borderColor="black" />
            <widget name="qrcode" position="%d,78" size="%d,%d" zPosition="2" scale="1" alphatest="blend" transparent="1" />
            %s
        </screen>
    """ % (
            self.__class__.__name__, self.WIDTH, self.HEIGHT,
            skinchrome.build_header_auto(iconBase=iconBase),
            textWidth, self.HEIGHT - 142,
            self.WIDTH - self.QR_SIZE - 20, self.QR_SIZE, self.QR_SIZE,
            skinchrome.build_footer_auto(self.HEIGHT, iconBase=iconBase, keys=(), showNav=False, showNum=False, showOk=False, showExit=True),
        )
        Screen.__init__(self, session)
        self.setTitle(_("MyE2i - how to solve a captcha"))
        self["text"] = Label(self._helpText())
        self["qrcode"] = Pixmap()
        self["qrcode"].hide()
        self["actions"] = ActionMap(["OkCancelActions"], {"cancel": self.close, "ok": self.close}, -2)
        self._qrPath = GetTmpDir("mye2i_help_qr.png")
        self.onLayoutFinish.append(self._showQr)
        self.onClose.append(self._removeQrFile)

    @staticmethod
    def _helpText():
        return "\n".join((
            _("How to solve a captcha:"),
            _("1. On a phone or PC in the same network, open the address shown in the captcha window (or scan its QR code) in a browser with the MyE2i extension installed. If it asks for a code, you find it in the title of the captcha window."),
            _("2. Click the big green button on that page. A new tab opens with the captcha or the website's browser check."),
            _("3. Solve it. The result goes back to the receiver by itself and the captcha window closes."),
            _("The QR code leads to the wiki page with pictures and the extension download."),
        ))

    def _showQr(self):
        try:
            make_qr_png(WIKI_URL, self._qrPath, scale=8, border=3)
            self["qrcode"].instance.setPixmap(LoadPixmap(self._qrPath))
            self["qrcode"].show()
        except Exception:
            printExc()

    def _removeQrFile(self):
        rm(self._qrPath)


class UnCaptchaReCaptchaMyE2iWidget(CaptchaScriptWidgetBase):
    # the chrome/skin building, eConsoleAppContainer wiring, and
    # stdout/stderr scaffolding are shared with the near-identical
    # `UnCaptchaReCaptchaMyJDWidget` via `CaptchaScriptWidgetBase`. Only
    # the genuinely MyE2i-specific bits remain here:
    # `ip_address`/`port` bookkeeping, the exact `mye2iserver` command,
    # the regex-based JSON-substring extraction its script's log output
    # actually needs (unlike MyJD's plain `byteify(json.loads())`), and a
    # QR code of the local URL the script prints, so it can be scanned with
    # a phone instead of typed in by hand.
    ACTION_CONTEXTS = ["ColorActions", "OkCancelActions"]

    # Status texts printed by scripts/mye2iserver.py arrive here as plain
    # English strings and are translated by the base class through
    # _(str(data)) - a dynamic call, invisible to xgettext. Listing them as
    # literals makes the translation template pick them up.
    SERVER_STATUS_MESSAGES = (
        _("MyE2i extension is outdated - please update it."),
        _("MyE2i debug snapshot received - see the debug log."),
    )

    def __init__(self, session, title, sitekey, referer, captchaType, captchaAction='', captchaData=''):
        # scale="1" is required here - without it Enigma2 draws the loaded
        # pixmap at its native size (see make_qr_png()'s own `scale` factor,
        # much bigger than this box) instead of fitting it into the widget.
        qrWidget = '<widget name="qrcode" position="%d,68" size="%d,%d" zPosition="2" scale="1" alphatest="blend" transparent="1" />' % (500 + (_QR_STRIP_WIDTH - _QR_SIZE) // 2, _QR_SIZE, _QR_SIZE)
        self.skin = CaptchaScriptWidgetBase._prepareSkin(self, extraWidth=_QR_STRIP_WIDTH, extraBody=qrWidget, keys=('red', 'yellow'))
        CaptchaScriptWidgetBase.__init__(self, session, title, sitekey, referer, captchaType)
        self.captchaAction = captchaAction
        self.captchaData = captchaData
        # Setting "MyE2i extension: increase security": a random per-session key (carried by the
        # QR code) and a short code (for the address typed by hand, shown in the window title);
        # mye2iserver.py then only accepts pages, results, debug lines and dumps that come with
        # one of them, so another device in the network cannot inject anything.
        # Off: no key, no code - the plain address opens the page directly.
        if config.plugins.iptvplayer.mye2i_security.value:
            self.sessionToken = binascii.hexlify(os.urandom(8)).decode('ascii')
            self.sessionPin = '%06d' % (int(binascii.hexlify(os.urandom(4)), 16) % 1000000)
            self.setTitle('%s   -   %s: %s' % (title, _("Code"), self.sessionPin))
        else:
            self.sessionToken = ''
            self.sessionPin = ''
        self["key_yellow"] = StaticText(_("Help"))
        self["helpactions"] = ActionMap(["ColorActions", "IPTVPlayerListActions"], {"yellow": self.keyHelp, "info": self.keyHelp}, -2)
        self["qrcode"] = Pixmap()
        self["qrcode"].hide()  # shown once startExecution() has an image to put in it
        self.ip_address = get_ip()
        self.port = 9001
        self._qrPath = GetTmpDir("mye2i_web_access_qr.png")
        self.onClose.append(self._removeQrFile)

    def _serverTexts(self):
        # Everything mye2iserver.py and the browser extension show in the browser
        # (see DEFAULT_TEXTS there - the keys and the English texts must match).
        # The server is a stand-alone script without translation, so the plugin
        # translates here and hands the result over; a text without translation
        # simply stays English.
        return {
            'pin_prompt': _("Enter the code shown in the title of the window on your receiver's screen (or scan the QR code shown there - no code needed then):"),
            'pin_continue': _("Continue"),
            'pin_no_session_code': _("This session has no code - scan the QR code on the receiver screen."),
            'pin_locked': _("Too many wrong codes - scan the QR code on the receiver screen instead."),
            'pin_wrong': _("Wrong code."),
            'extension_outdated': _("Your MyE2i extension is outdated or unknown (v%s or newer needed). Please update:"),
            'extension_download': _("Download new version"),
            'job_cloudflare': _("Get Cloudflare job"),
            'job_cookies': _("Get cookies job"),
            'job_captcha': _("Get captcha job"),
            'status_waiting': _("Waiting for the result ..."),
            'debug_pill': _("debug"),
            'debug_title': _("Debug snapshot (for site development)"),
            'debug_text': _("Needs extension v1.18+. Opens the page in this browser, waits until it is fully rendered (Cloudflare challenge included, solve it if it shows up) and sends the rendered HTML, the fetch/XHR calls and the cookie names to the box debug log."),
            'debug_button': _("Debug snapshot"),
            'err_title': _("Error"),
            'err_forbidden': _("Access denied - open the page with the QR code or the code shown on the receiver screen."),
            'err_not_found': _("Page not found - please check the address."),
            'err_bad_length': _("The request has no valid length."),
            'err_too_large': _("The data is too large."),
            'x_done': _("Done - the result was sent to the box, you can close this page."),
            'x_send_failed': _("Sending the result to the box failed."),
            'x_dump_ok': _('Debug snapshot: "%s" received by the box'),
            'x_dump_failed': _('Debug snapshot: sending "%s" failed'),
            'x_error': _("Error occurs:"),
            'header_please_solve': _("Please solve to continue downloads with:"),
            'help_whats_happening_header': _("What's happening?"),
            'help_whats_happening_description': _("wants you to solve a captcha. Only after solving this captcha, you are allowed to continue with your downloads. E2iPlayer is not able to auto-solve these captchas, so we need to pass the captcha to you."),
            'help_whats_happening_link': _("Find out more."),
            'button_i_am_no_robot': _("I am no robot"),
            'button_please_wait': _("Please wait..."),
            'captcha_error': _("Captcha error:"),
        }

    def _scriptFinishedMsg(self):
        return _('MyE2i script finished.')

    def _scriptFailedMsg(self, code):
        return _("MyE2i script execution failed.\nError code: %s\n") % (code)

    def _parseJsonLine(self, line):
        matches = re.findall("{.*}", line)
        if not matches:
            return None
        return json.loads(matches[0])

    def _removeQrFile(self):
        rm(self._qrPath)

    def keyHelp(self):
        self.session.open(MyE2iHelpScreen)

    def _scriptStderrAvail(self, data):
        hadResult = bool(self.result)
        CaptchaScriptWidgetBase._scriptStderrAvail(self, data)
        if not hadResult and self.result:
            # captcha just got solved - the QR code (and the file behind it)
            # served its purpose, drop both instead of leaving them lying around.
            self["qrcode"].hide()
            self._removeQrFile()

    def startExecution(self):
        captcha = {'siteKey': self.sitekey, 'sameOrigin': True, 'siteUrl': self.referer, 'contextUrl': '/'.join(self.referer.split('/')[:3]), 'boundToDomain': True, 'stoken': None, 'captchaType': self.captchaType, 'captchaAction': self.captchaAction, 'captchaData': self.captchaData, 'token': self.sessionToken, 'pin': self.sessionPin, 'i18n': self._serverTexts(), 'tmpDir': GetTmpDir()}
        try:
            captcha = ensure_str(base64.b64encode(ensure_binary(json.dumps(captcha))))
        except Exception:
            printExc()

        while is_port_in_use(self.ip_address, self.port):
            self.port += 1

        cmd = GetPyScriptCmd('mye2iserver') + ' "%s" "%s" "%s"' % (captcha, self.ip_address, self.port)

        try:
            # scale=10 -> a 370x370 native PNG, comfortably above the qrcode
            # widget's box even at WQHD (_QR_SIZE=178 HD-reference * 2.0 =
            # 356px there) so Enigma2's scale="1" only ever downscales it,
            # never blows it up past its native resolution.
            make_qr_png("http://%s:%s/%s" % (self.ip_address, self.port, ('?t=' + self.sessionToken) if self.sessionToken else ''), self._qrPath, scale=10, border=4)  # NOSONAR - LAN-only mye2iserver.py has no TLS support
            self["qrcode"].instance.setPixmap(LoadPixmap(self._qrPath))
            self["qrcode"].show()
        except Exception:
            printExc()

        self["console"].setText(_('Please Open site:\nhttp://{0}:{1}\nin a web browser with the MyE2i extension installed').format(self.ip_address, self.port))

        self.workconsole['console'] = eConsoleAppContainer()
        self.workconsole['close_conn'] = eConnectCallback(self.workconsole['console'].appClosed, self._scriptClosed)
        self.workconsole['stderr_conn'] = eConnectCallback(self.workconsole['console'].stderrAvail, self._scriptStderrAvail)
        self.workconsole['stdout_conn'] = eConnectCallback(self.workconsole['console'].stdoutAvail, self._scriptStdoutAvail)
        self.workconsole["console"].execute(cmd)
        printDBG(">>> EXEC CMD [%s]" % cmd.replace(str(captcha), '<%d bytes of settings>' % len(str(captcha))))
