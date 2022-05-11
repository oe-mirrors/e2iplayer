# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.asynccall import MainSessionWrapper
from Plugins.Extensions.IPTVPlayer.components.recaptcha_mye2i_widget import UnCaptchaReCaptchaMyE2iWidget


class UnCaptchaReCaptcha:
    def __init__(self, lang='en'):
        self.sessionEx = MainSessionWrapper()

    def processCaptcha(self, sitekey, referer='', captchaType=''):
        answer = ''
        retArg = self.sessionEx.waitForFinishOpen(UnCaptchaReCaptchaMyE2iWidget, title=_("My E2i reCAPTCHA solution"), sitekey=sitekey, referer=referer, captchaType=captchaType)
        if retArg is not None and len(retArg) and retArg[0]:
            answer = retArg[0]
        return answer
