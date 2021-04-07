# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.asynccall import MainSessionWrapper
from Plugins.Extensions.IPTVPlayer.components.recaptcha_v2myjd_widget import UnCaptchaReCaptchaMyJDWidget


class UnCaptchaReCaptcha:
    def __init__(self, lang='en'):
        self.sessionEx = MainSessionWrapper()
    
    def processCaptcha(self, sitekey, referer=''):
        answer = ''
        retArg = self.sessionEx.waitForFinishOpen(UnCaptchaReCaptchaMyJDWidget, title=_("My JDownloader reCAPTCHA v2 solution"), sitekey=sitekey, referer=referer)
        if retArg is not None and len(retArg) and retArg[0]:
            answer = retArg[0]
        return answer
