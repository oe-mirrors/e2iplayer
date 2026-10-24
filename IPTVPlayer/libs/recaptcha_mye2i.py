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

    def processCaptcha(self, sitekey, referer='', captchaType='', captchaAction='', captchaData='', hint=''):
        # hint: what the user has to do on the opened page (e.g. click the player of a NAV job's page) - shown on
        # the box and on the browser's start page
        answer = ''
        if captchaType == 'CF':
            title = _("MyE2i Cloudflare solution")
        elif captchaType == 'COOKIES':
            title = _("MyE2i browser check solution")
        elif captchaType == 'NAV':
            # a page whose link only the site's scripts build (ad gateway, countdown): captchaData = JSON
            # {"selector", "attr", "pattern"}, the answer is the usual base64 JSON with the link in "url"
            title = _("MyE2i: open the page in the browser")
        else:
            title = _("MyE2i reCAPTCHA solution")
        retArg = self.sessionEx.waitForFinishOpen(UnCaptchaReCaptchaMyE2iWidget, title=title, sitekey=sitekey, referer=referer, captchaType=captchaType, captchaAction=captchaAction, captchaData=captchaData, hint=hint)

        if retArg is not None and len(retArg) and retArg[0]:
            answer = retArg[0]
        return answer
