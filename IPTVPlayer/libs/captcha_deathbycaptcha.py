# -*- coding: utf-8 -*-
#
# deathbycaptcha.com: paid captcha solving service, account login + password.
# Token captchas only: reCAPTCHA v2 (type 4), v3 (type 5, needs the action),
# reCAPTCHA v2 Enterprise (type 25) and Cloudflare Turnstile (type 12). The
# service has no hCaptcha any more. Upload with POST /api/captcha, then poll
# GET /api/captcha/<id> until "text" holds the token (docs: deathbycaptcha.com/api).

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, GetIPTVSleep
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
from Plugins.Extensions.IPTVPlayer.components.asynccall import MainSessionWrapper
from Screens.MessageBox import MessageBox
from Components.config import config
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
###################################################
# FOREIGN import
###################################################
import time
###################################################

API_URL = 'https://api.dbcapi.me/api/captcha'
SERVICE_NAME = 'https://deathbycaptcha.com/'
V3_MIN_SCORE = 0.3


def buildTask(sitekey, pageUrl, captchaType='', captchaAction=''):
    # (type, name of the JSON field, its content) for the captcha types of CaptchaHelper.processCaptcha,
    # None for the types the service cannot solve (hCaptcha 'h1', MyE2i's 'CF' / 'COOKIES' page checks)
    if captchaType == 'cf_re':
        params = {'sitekey': sitekey, 'pageurl': pageUrl}
        if captchaAction:
            params['action'] = captchaAction
        return 12, 'turnstile_params', params
    if captchaType == 'ENTERPRISE':
        # the docs list a proxy as required here; without one the service may turn it down
        return 25, 'token_enterprise_params', {'googlekey': sitekey, 'pageurl': pageUrl}
    if captchaType == '':
        if captchaAction:
            return 5, 'token_params', {'googlekey': sitekey, 'pageurl': pageUrl, 'action': captchaAction, 'min_score': V3_MIN_SCORE}
        return 4, 'token_params', {'googlekey': sitekey, 'pageurl': pageUrl}
    return None


def parseAnswer(data):
    # API answer (JSON) -> (captcha id, token, error); id 0 when there is none, error '' when all is fine
    try:
        data = json_loads(data) if data else {}
    except Exception:
        return 0, '', _('Invalid answer from %s.') % SERVICE_NAME
    if not isinstance(data, dict):
        return 0, '', _('Invalid answer from %s.') % SERVICE_NAME
    error = data.get('error') or ''
    if error:
        if error == 'not-logged-in':
            error = _('Login or password is wrong.')
        elif error == 'banned':
            error = _('The account is banned.')
        elif error == 'insufficient-funds':
            error = _('The balance of the account is too low.')
        elif error == 'service-overload':
            error = _('The service is overloaded. Please try again later.')
        return 0, '', error
    try:
        captchaId = int(data.get('captcha') or 0)
    except (TypeError, ValueError):
        captchaId = 0
    token = data.get('text') or ''
    if captchaId and not token and data.get('is_correct') is False:
        # solving failed for good, polling further does not help
        return captchaId, '', _('%s could not solve the captcha.') % SERVICE_NAME
    return captchaId, token, ''


class UnCaptchaReCaptcha:
    def __init__(self, lang='en'):
        self.cm = common()
        self.sessionEx = MainSessionWrapper()

    def getMainUrl(self):
        return SERVICE_NAME

    def _request(self, url, postData=None):
        # 4xx/5xx come with a JSON error body ({"error": "not-logged-in", "status": 255}), so they are read too
        params = {'header': {'Accept': 'application/json'}, 'ignore_http_code_ranges': [(400, 599)]}
        sts, data = self.cm.getPage(url, params, postData)
        if not sts and data:
            # without PycURL an HTTP error gives sts False; the body of a 403 is only in meta['body_head']
            body = getattr(data, 'meta', {}).get('body_head') or data
            if str(body).lstrip().startswith('{'):
                sts, data = True, str(body)
        printDBG('DeathByCaptcha API DATA:\n%s\n' % data)
        return sts, data

    def processCaptcha(self, sitekey, referer='', captchaType='', captchaAction=''):
        sleepObj = None
        token = ''
        errorMsgTab = []
        login = config.plugins.iptvplayer.deathbycaptcha_login.value.strip()
        password = config.plugins.iptvplayer.deathbycaptcha_password.value.strip()
        task = buildTask(sitekey, referer, captchaType, captchaAction)
        try:
            if not login or not password:
                errorMsgTab.append(_('Please enter the %s login and password in the E2iPlayer settings (Captcha).') % SERVICE_NAME)
            elif task is None:
                errorMsgTab.append(_('%s cannot solve this type of captcha.') % SERVICE_NAME)
            else:
                taskType, field, params = task
                postData = {'username': login, 'password': password, 'type': str(taskType), field: json_dumps(params)}
                sts, data = self._request(API_URL, postData)
                if not sts:
                    errorMsgTab.append(_('Network failed %s.') % '1')
                else:
                    captchaId, token, error = parseAnswer(data)
                    if error:
                        errorMsgTab.append(error)
                    elif not captchaId:
                        errorMsgTab.append(_('Invalid answer from %s.') % SERVICE_NAME)
                    elif not token:
                        sleepObj = GetIPTVSleep()
                        sleepObj.Sleep(300, False)
                        tries = 0
                        while True:
                            tries += 1
                            # the service asks for no more than one request every few seconds
                            time.sleep(15 if tries == 1 else 5)
                            sts, data = self._request('%s/%d' % (API_URL, captchaId))
                            if sts:
                                _cid, token, error = parseAnswer(data)
                                if token:
                                    break
                                if error:
                                    errorMsgTab.append(error)
                                    break
                            if sleepObj.getTimeout() == 0:
                                errorMsgTab.append(_('%s timeout.') % SERVICE_NAME)
                                break
        except Exception as e:
            errorMsgTab.append(str(e))
            printExc()

        if sleepObj is not None:
            sleepObj.Reset()

        if token == '':
            self.sessionEx.waitForFinishOpen(MessageBox, (_('Resolving reCaptcha with %s failed!\n\n') % SERVICE_NAME) + '\n'.join(errorMsgTab), type=MessageBox.TYPE_ERROR, timeout=10)
        return token
