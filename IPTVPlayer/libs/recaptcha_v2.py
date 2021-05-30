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
import urllib
import re
###################################################


class UnCaptchaReCaptcha:
    def __init__(self, lang='en'):
        self.COOKIE_FILE = GetCookieDir('google.cookie')
        self.HTTP_HEADER = {'Accept': 'text/html',
                            'Accept-Charset': 'UTF-8',
                            'Accept-Encoding': 'gzip',
                            'Accept-Language': lang,
                            'Referer': 'https://www.google.com/recaptcha/api2/demo',
                            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36'
                           }
        self.HttpParams = {'header': self.HTTP_HEADER, 'cookiefile': self.COOKIE_FILE, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True}
        self.cm = common()
        self.sessionEx = MainSessionWrapper()

    def processCaptcha(self, key, referer=None, lang='en'):
        post_data = None
        token = ''
        iteration = 0
        if referer != None:
            self.HttpParams['header']['Referer'] = referer

        #reCaptchaUrl = 'http://www.google.com/recaptcha/api/fallback?k=%s' % (key)

        #new method as in plugin kodiondemand

        reCaptchaApiUrl = "https://www.google.com/recaptcha/api.js?hl=%s" % lang
        sts, apiCode = self.cm.getPage(reCaptchaApiUrl, self.HttpParams)

        if not sts:
            SetIPTVPlayerLastHostError(_('Fail to get "%s".') % reCaptchaApiUrl)
            return ''

        apiVersionUrl = re.findall("po.src\s*=\s*'(.*?)';", apiCode)

        if not apiVersionUrl:
            SetIPTVPlayerLastHostError(_('Fail to get "%s".') % reCaptchaApiUrl)
            return ''

        version = apiVersionUrl[0].split("/")[5]
        printDBG("reCaptcha version: %s" % version)

        reCaptchaUrl = "https://www.google.com/recaptcha/api/fallback?k=" + key + "&hl=" + lang + "&v=" + version + "&t=2&ff=true"
        printDBG("reCaptchaUrl: %s " % reCaptchaUrl)

        while iteration < 20:
            #,'cookiefile':self.COOKIE_FILE, 'use_cookie': True, 'load_cookie': True, 'save_cookie':True
            #sts, data = self.cm.getPage(reCaptchaUrl, {'header':self.HTTP_HEADER, 'raw_post_data':True}, post_data=post_data)
            if post_data:
                self.HttpParams['raw_post_data'] = True
                sts, data = self.cm.getPage(reCaptchaUrl, self.HttpParams, post_data)
            else:
                sts, data = self.cm.getPage(reCaptchaUrl, self.HttpParams)

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
                post_data = urllib.urlencode({'c': cval, 'response': answer}, doseq=True)
                printDBG(str(post_data))
            else:
                break

        return token
