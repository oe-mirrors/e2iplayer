# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, GetTmpDir
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.utils import clean_html
from Plugins.Extensions.IPTVPlayer.components.asynccall import MainSessionWrapper
from Plugins.Extensions.IPTVPlayer.components.iptvmultipleinputbox import IPTVMultipleInputBox

###################################################
# FOREIGN import
###################################################
import urllib
from copy import deepcopy
###################################################


class UnCaptchaReCaptcha:
    def __init__(self, lang='en'):
        self.HTTP_HEADER = {'Accept-Language': lang, 'Referer': 'https://www.google.com/recaptcha/demo/', 'User-Agent': 'Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.9.2.18) Gecko/20110621 Mandriva Linux/1.9.2.18-0.1mdv2010.2 (2010.2) Firefox/3.6.18'}
        self.cm = common()
        self.sessionEx = MainSessionWrapper()
        self.challenge = ''
        self.response = ''

    def processCaptcha(self, key):
        post_data = None
        token = ''
        iteration = 0
        reCaptchaUrl = 'https://www.google.com/recaptcha/api/noscript?k=%s' % (key)
        while iteration < 20:
            sts, data = self.cm.getPage(reCaptchaUrl, {'header': self.HTTP_HEADER, 'raw_post_data': True}, post_data=post_data)
            if not sts:
                SetIPTVPlayerLastHostError(_('Fail to get "%s".') % reCaptchaUrl)
                return ''

            imgUrl = self.cm.ph.getSearchGroups(data, 'src="(image[^"]+?)"')[0]
            iteration += 1
            message = self.cm.ph.getSearchGroups(data, '<p[^>]*>([^<]+?)</p>')[0]
            token = self.cm.ph.getSearchGroups(data, '<textarea[^>]*>([^<]+?)</textarea>')[0]
            if '' != token:
                printDBG('>>>>>>>> Captcha token[%s]' % (token))
                break
            elif message == '':
                printDBG('>>>>>>>> Captcha Failed')
                break

            recaptcha_challenge_field = self.cm.ph.getSearchGroups(data, 'name="recaptcha_challenge_field"[^>]+?value="([^"]+)"')[0]
            imgUrl = 'https://www.google.com/recaptcha/api/%s' % (imgUrl.replace('&amp;', '&'))
            message = clean_html(message)
            accepLabel = clean_html(self.cm.ph.getSearchGroups(data, 'type="submit"[^>]+?value="([^"]+)"')[0])

            filePath = GetTmpDir('.iptvplayer_captcha.jpg')
            printDBG(">>>>>>>> Captcha message[%s]" % (message))
            printDBG(">>>>>>>> Captcha accep label[%s]" % (accepLabel))
            printDBG(">>>>>>>> Captcha imgUrl[%s] filePath[%s]" % (imgUrl, filePath))

            params = {'maintype': 'image', 'subtypes': ['jpeg'], 'check_first_bytes': ['\xFF\xD8', '\xFF\xD9']}
            ret = self.cm.saveWebFile(filePath, imgUrl, params)
            if not ret.get('sts'):
                SetIPTVPlayerLastHostError(_('Fail to get "%s".') % imgUrl)
                break

            params = deepcopy(IPTVMultipleInputBox.DEF_PARAMS)
            params['accep_label'] = _('Send')
            params['title'] = accepLabel
            params['list'] = []
            item = deepcopy(IPTVMultipleInputBox.DEF_INPUT_PARAMS)
            item['label_size'] = (300, 57)
            item['input_size'] = (300, 25)
            item['icon_path'] = filePath
            item['input']['text'] = ''
            params['list'].append(item)

            ret = 0
            retArg = self.sessionEx.waitForFinishOpen(IPTVMultipleInputBox, params)
            printDBG('>>>>>>>> Captcha response[%s]' % (retArg))
            if retArg is not None and len(retArg) and retArg[0]:
                recaptcha_response_field = retArg[0]
                printDBG('>>>>>>>> Captcha recaptcha_response_field[%s]' % (recaptcha_response_field))
                post_data = urllib.urlencode({'recaptcha_challenge_field': recaptcha_challenge_field, 'recaptcha_response_field': recaptcha_response_field, 'submit': accepLabel}, doseq=True)
            else:
                break

        return token
