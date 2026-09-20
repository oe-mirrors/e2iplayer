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

    def processCaptcha(self, sitekey, referer='', captchaType='', captchaAction='', captchaData=''):
        answer = ''
        if captchaType == 'CF':
            title = _("MyE2i Cloudflare solution")
        elif captchaType == 'COOKIES':
            title = _("MyE2i browser check solution")
        else:
            title = _("MyE2i reCAPTCHA solution")
        retArg = self.sessionEx.waitForFinishOpen(UnCaptchaReCaptchaMyE2iWidget, title=title, sitekey=sitekey, referer=referer, captchaType=captchaType, captchaAction=captchaAction, captchaData=captchaData)

        if retArg is not None and len(retArg) and retArg[0]:
            answer = retArg[0]
        return answer
