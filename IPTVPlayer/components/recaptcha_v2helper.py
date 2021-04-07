# -*- coding: utf-8 -*-
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetDefaultLang

from Plugins.Extensions.IPTVPlayer.libs.recaptcha_v2_9kw import UnCaptchaReCaptcha as UnCaptchaReCaptcha_9kw
from Plugins.Extensions.IPTVPlayer.libs.recaptcha_v2_2captcha import UnCaptchaReCaptcha as UnCaptchaReCaptcha_2captcha
from Plugins.Extensions.IPTVPlayer.libs.recaptcha_v2_myjd import UnCaptchaReCaptcha as UnCaptchaReCaptcha_myjd
from Plugins.Extensions.IPTVPlayer.libs.recaptcha_v2 import UnCaptchaReCaptcha as UnCaptchaReCaptcha_fallback

from Screens.MessageBox import MessageBox
from Components.config import config


class CaptchaHelper():

    def processCaptcha(self, sitekey, refUrl, bypassCaptchaService=None, userAgent=None, baseErrMsgTab=None, beQuaiet=False):
        if isinstance(baseErrMsgTab, list):
            errorMsgTab = list(baseErrMsgTab)
        else:
            errorMsgTab = [_('Link protected with Google ReCaptcha v2')]
        
        if userAgent == None:
            try:
                userAgent = self.USER_AGENT
            except Exception:
                pass
        
        if userAgent == None:
            try:
                userAgent = self.defaultParams['header']['User-Agent']
            except Exception:
                pass
        
        recaptcha = UnCaptchaReCaptcha_fallback(lang=GetDefaultLang())
        recaptcha.HTTP_HEADER['Referer'] = refUrl
        if userAgent != None:
            recaptcha.HTTP_HEADER['User-Agent'] = userAgent
        token = recaptcha.processCaptcha(sitekey)
        
        if token == '':
            recaptcha = None
            if config.plugins.iptvplayer.captcha_bypass.value != '' and bypassCaptchaService == None:
                bypassCaptchaService = config.plugins.iptvplayer.captcha_bypass.value
            if bypassCaptchaService == '9kw.eu':
                recaptcha = UnCaptchaReCaptcha_9kw()
            elif bypassCaptchaService == '2captcha.com':
                recaptcha = UnCaptchaReCaptcha_2captcha()
            elif config.plugins.iptvplayer.myjd_login.value != '' and config.plugins.iptvplayer.myjd_password.value != '':
                recaptcha = UnCaptchaReCaptcha_myjd()
            
            if recaptcha != None:
                token = recaptcha.processCaptcha(sitekey, refUrl)
            else:
                errorMsgTab.append(_('Please visit %s to learn how to redirect this task to the external device.') % 'http://zadmario.gitlab.io/captcha.html')
                if not beQuaiet:
                    self.sessionEx.waitForFinishOpen(MessageBox, '\n'.join(errorMsgTab), type=MessageBox.TYPE_ERROR, timeout=20)
                if bypassCaptchaService != None:
                    errorMsgTab.append(_(' or '))
                    errorMsgTab.append(_('You can use \"%s\" or \"%s\" services for automatic solution.') % ("http://2captcha.com/", "https://9kw.eu/", ) + ' ' + _('Go to the host configuration available under blue button.'))
        return token, errorMsgTab

