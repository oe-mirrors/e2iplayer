# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, GetTmpDir, GetCookieDir
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
from Plugins.Extensions.IPTVPlayer.components.asynccall import MainSessionWrapper
from Plugins.Extensions.IPTVPlayer.components.recaptcha_v2widget import UnCaptchaReCaptchaWidget
from Plugins.Extensions.IPTVPlayer.libs import ph

###################################################
# FOREIGN import
###################################################
import urllib.request
import urllib.parse
import urllib.error
###################################################


class UnCaptchaReCaptcha:
    def __init__(self, lang='en'):
        self.HTTP_HEADER = {'Accept-Language': lang, 'Referer': 'https://www.google.com/recaptcha/api2/demo', 'User-Agent': 'Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.9.2.18) Gecko/20110621 Mandriva Linux/1.9.2.18-0.1mdv2010.2 (2010.2) Firefox/3.6.18'}
        self.cm = common()
        self.sessionEx = MainSessionWrapper() 
        self.COOKIE_FILE = GetCookieDir('google.cookie')
        
    def processCaptcha(self, key, referer=None):
        post_data = None
        token = ''
        iteration = 0
        if referer != None:
            self.HTTP_HEADER['Referer'] = referer
        reCaptchaUrl = 'http://www.google.com/recaptcha/api/fallback?k=%s' % (key)
        while iteration < 20:
            #,'cookiefile':self.COOKIE_FILE, 'use_cookie': True, 'load_cookie': True, 'save_cookie':True
            sts, data = self.cm.getPage(reCaptchaUrl, {'header': self.HTTP_HEADER, 'raw_post_data': True}, post_data=post_data)
            if not sts: 
                SetIPTVPlayerLastHostError(_('Fail to get "%s".') % reCaptchaUrl)
                return ''

            printDBG("+++++++++++++++++++++++++++++++++++++++++")
            printDBG(data)
            printDBG("+++++++++++++++++++++++++++++++++++++++++")
            imgUrl = ph.search(data, '"(/recaptcha/api2/payload[^"]+?)"')[0]
            iteration += 1

            message = ph.clean_html(ph.find(data, ('<div', '>', 'imageselect-desc'), '</div>', flags=0)[1])
            if not message:
                message = ph.clean_html(ph.find(data, ('<label', '>', 'fbc-imageselect-message-text'), '</label>', flags=0)[1])
            if not message:
                message = ph.clean_html(ph.find(data, ('<div', '>', 'imageselect-message'), '</div>', flags=0)[1])
            if '' == message:
                token = ph.find(data, ('<div', '>', 'verification-token'), '</div>', flags=0)[1]
                token = ph.find(data, ('<textarea', '>'), '</textarea>', flags=0)[1].strip()
                if token == '':
                    token = ph.search(data, '"this\.select\(\)">(.*?)</textarea>')[0]
                if token == '':
                    token = ph.find(data, ('<textarea', '>'), '</textarea>', flags=0)[1].strip()
                if '' != token:
                    printDBG('>>>>>>>> Captcha token[%s]' % (token))
                else:
                    printDBG('>>>>>>>> Captcha Failed\n\n%s\n\n' % data)
                break

            cval = ph.search(data, 'name="c"\s+value="([^"]+)')[0]
            imgUrl = 'https://www.google.com%s' % (imgUrl.replace('&amp;', '&'))
            message = ph.clean_html(message)
            accepLabel = ph.clean_html(ph.search(data, 'type="submit"\s+value="([^"]+)')[0])
            
            filePath = GetTmpDir('.iptvplayer_captcha.jpg')
            printDBG(">>>>>>>> Captcha message[%s]" % (message))
            printDBG(">>>>>>>> Captcha accep label[%s]" % (accepLabel))
            printDBG(">>>>>>>> Captcha imgUrl[%s] filePath[%s]" % (imgUrl, filePath))
            
            params = {'maintype': 'image', 'subtypes': ['jpeg'], 'check_first_bytes': ['\xFF\xD8', '\xFF\xD9']}
            ret = self.cm.saveWebFile(filePath, imgUrl, params)
            if not ret.get('sts'):
                SetIPTVPlayerLastHostError(_('Fail to get "%s".') % imgUrl)
                break
            
            retArg = self.sessionEx.waitForFinishOpen(UnCaptchaReCaptchaWidget, imgFilePath=filePath, message=message, title="reCAPTCHA v2", additionalParams={'accep_label': accepLabel})
            printDBG('>>>>>>>> Captcha response[%s]' % (retArg))
            if retArg is not None and len(retArg) and retArg[0]:
                answer = retArg[0]
                printDBG('>>>>>>>> Captcha answer[%s]' % (answer))
                post_data = urllib.parse.urlencode({'c': cval, 'response': answer}, doseq=True)
            else:
                break
        
        return token
