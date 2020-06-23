# -*- coding: utf-8 -*-
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetDefaultLang

# recaptcha 
from Plugins.Extensions.IPTVPlayer.libs.recaptcha_v2_9kw import UnCaptchaReCaptcha as UnCaptchaReCaptcha_9kw
from Plugins.Extensions.IPTVPlayer.libs.recaptcha_v2_2captcha import UnCaptchaReCaptcha as UnCaptchaReCaptcha_2captcha
from Plugins.Extensions.IPTVPlayer.libs.recaptcha_v2_myjd import UnCaptchaReCaptcha as UnCaptchaReCaptcha_myjd
from Plugins.Extensions.IPTVPlayer.libs.recaptcha_v2 import UnCaptchaReCaptcha as  UnCaptchaReCaptcha_fallback

from Plugins.Extensions.IPTVPlayer.libs.recaptcha_v3_2captcha import UnCaptchaReCaptcha as UnCaptchaReCaptchav3_2captcha

# hcaptcha
from Plugins.Extensions.IPTVPlayer.libs.hcaptcha import UnCaptchahCaptcha 
from Plugins.Extensions.IPTVPlayer.libs.hcaptcha_2captcha import UnCaptchahCaptcha as  UnCaptchaReCaptcha_hcaptcha_2captcha


from Screens.MessageBox import MessageBox
from Components.config import config

class CaptchaHelper():

    def processCaptcha(self, sitekey, refUrl, bypassCaptchaService=None,  userAgent=None, baseErrMsgTab=None, beQuiet=False, captchaType="v2", challengeForm=""):

        recaptcha = None
        token = ""
        
        #captcha name
        if captchaType=="h":
            captchaName = 'hCaptcha'
        elif captchaType == "v3":
            captchaName = 'ReCaptcha v3'
        else:
            captchaName = 'ReCaptcha v2'

        # read error messages in input
        
        if isinstance(baseErrMsgTab, list):
            errorMsgTab = list(baseErrMsgTab)
        else:
            errorMsgTab = [_('Link protected with %s') % captchaName]

        if bypassCaptchaService:
            printDBG("Captcha_Helper_Max.bypassCaptchaService in input: %s " % bypassCaptchaService)
            # service selected in input
            bypassCaptchaService = bypassCaptchaService.lower()

            if '2captcha' in bypassCaptchaService:
                if captchaType == "h":
                    recaptcha = UnCaptchahCaptcha_2captcha()    
                elif captchaType == "v3":
                    recaptcha = UnCaptchaReCaptchav3_2captcha()
                else:
                    recaptcha = UnCaptchaReCaptcha_2captcha()
            elif '9kw' in bypassCaptchaService:
                if captchaType == "h" or captchaType == "v3":
                    errorMsgTab =[_('Solution of %s with %s has not been implemented yet') % (captchaName, bypassCaptchaService)]
                else:
                    recaptcha = UnCaptchaReCaptcha_9kw()
            elif 'myjd' in bypassCaptchaService:
                if captchaType == "h" or captchaType == "v3":
                    errorMsgTab =[_('Solution of %s with %s has not been implemented yet') % (captchaName, bypassCaptchaService)]
                else:
                    recaptcha = UnCaptchaReCaptcha_myjd()
            
            # call selected captcha solver
            if recaptcha:
                token = recaptcha.processCaptcha(sitekey, refUrl)
            
            return token, errorMsgTab

        else:
            printDBG("Captcha_Helper_Max: No bypassCaptchaService in input")

            # follow general settings  
            captchaOrder = config.plugins.iptvplayer.captcha_bypass_order.value 
            captchaFree = config.plugins.iptvplayer.captcha_bypass_free.value 
            captchaPay = config.plugins.iptvplayer.captcha_bypass_pay.value 

            printDBG("Captcha_Helper_Max: captchaOrder: '%s', captchaFree: '%s', captchaPay: '%s'" % (captchaOrder, captchaFree, captchaPay ))

            if not captchaOrder:
                # try with internal render
                printDBG("Captcha_Helper_Max: try with internal render")
                if captchaType == "h":
                    recaptcha = UnCaptchahCaptcha()
                    token = recaptcha.processCaptcha(challenge_form = challengeForm, referer = refUrl)
                    return token, errorMsgTab
                elif captchaType != "v3":
                    printDBG("Captcha_Helper_Max: try with internal render Recaptcha v2")
                    recaptcha = UnCaptchaReCaptcha_fallback(lang=GetDefaultLang())
                    if userAgent != None:
                        recaptcha.HTTP_HEADER['User-Agent'] = userAgent
                    token = recaptcha.processCaptcha(sitekey)
                    
            if token:
                # success with internal solver
                printDBG("Captcha_Helper_Max: exit from internal solver ---> token: %s" % token)

                return token, errorMsgTab
                    
            # no success... try external services
            recaptcha = None
            
            if not captchaFree and not captchaPay:
                # no external services to use
                errorMsgTab.append(_('Please visit %s to learn how to redirect this task to the external device.') % 'http://www.iptvplayer.gitlab.io/captcha.html')
                if not beQuiet:
                    self.sessionEx.waitForFinishOpen(MessageBox, '\n'.join(errorMsgTab), type=MessageBox.TYPE_ERROR, timeout=20)
                if bypassCaptchaService != None:
                    errorMsgTab.append(_(' or '))
                    errorMsgTab.append(_('You can use \"%s\" or \"%s\" services for automatic solution.') % ("http://2captcha.com/", "https://9kw.eu/", ) + ' ' + _('Go to the host configuration available under blue button.'))

                return token, errorMsgTab
            
            if ("free" in captchaOrder or not captchaOrder) and captchaFree:
                # try free external solver (ex. myjdownloader)
                printDBG("Captcha_Helper_Max: try with external free service: %s " % captchaFree)
                if ('myjd' in captchaFree.lower()) and captchaType == "v2":
                    printDBG("Captcha_Helper_Max: myjd 1")
                    if config.plugins.iptvplayer.myjd_login.value != '' and config.plugins.iptvplayer.myjd_password.value != '':
                        printDBG("Captcha_Helper_Max: myjd 2")
                        recaptcha = UnCaptchaReCaptcha_myjd()
                        printDBG("Captcha_Helper_Max: myjd 3")

                    else:
                        errorMsgTab.append(_('If you want to use MyJDownloader, fill login and password in settings menu'))
            
                if recaptcha:
                    printDBG("Captcha_Helper_Max: myjd 4")
                    token = recaptcha.processCaptcha(sitekey, refUrl)
                    printDBG("Captcha_Helper_Max: myjd 5")
                    
            if token:
                # success with free external services
                printDBG("Captcha_Helper_Max: exit after external free solver ---> token: %s" % token)
                
                return token, errorMsgTab
        
            recaptcha = None
            if ("pay" in captchaOrder or not captchaOrder) and captchaPay:
                # try with a paid service
                printDBG("Captcha_Helper_Max: try with external free service: %s " % captchaPay)

                if '2captcha' in captchaPay and captchaType=="h":
                    recaptcha = UnCaptchahCaptcha_2captcha()
                elif '2captcha' in captchaPay and captchaType=="v3":
                   recaptcha = UnCaptchaReCaptchav3_2captcha()
                elif '2captcha' in captchaPay:
                    recaptcha = UnCaptchaReCaptcha_2captcha()
                elif '9kw' in captchaPay:
                    if captchaType=="h" or captchaType=="v3":
                        errorMsgTab =[_('Solution of %s with %s has not been implemented yet') % (captchaName, bypassCaptchaService)]
                    else:
                        recaptcha = UnCaptchaReCaptcha_9kw()


                if recaptcha:
                    token = recaptcha.processCaptcha(sitekey, refUrl)
                
                if token:
                    printDBG("Captcha_Helper_Max: exit after external paid solver ---> token: %s" % token)
                    return token, errorMsgTab
                
            else:
                # no paid services 
                errorMsgTab.append(_('You can use \"%s\" or \"%s\" services for automatic solution.') % ("http://2captcha.com/", "https://9kw.eu/", ) + ' ' + _('Go to the host configuration available under blue button.'))
                
        return token, errorMsgTab

