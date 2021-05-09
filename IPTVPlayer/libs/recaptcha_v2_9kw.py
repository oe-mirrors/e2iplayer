# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, GetIPTVSleep
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
from Plugins.Extensions.IPTVPlayer.components.asynccall import MainSessionWrapper
from Screens.MessageBox import MessageBox
from Components.config import config
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
###################################################
# FOREIGN import
###################################################
import time
import urllib
from Components.config import config
###################################################


class UnCaptchaReCaptcha:
    def __init__(self, lang='en'):
        self.cm = common()
        self.sessionEx = MainSessionWrapper()
        self.MAIN_URL = 'https://www.9kw.eu/'

    def getMainUrl(self):
        return self.MAIN_URL

    def getFullUrl(self, url, mainUrl=None):
        if mainUrl == None:
            mainUrl = self.getMainUrl()
        return self.cm.getFullUrl(url, mainUrl)

    def processCaptcha(self, sitekey, referer=''):
        sleepObj = None
        token = ''
        errorMsgTab = []
        apiKey = config.plugins.iptvplayer.api_key_9kweu.value
        apiUrl = self.getFullUrl('/index.cgi?apikey=') + apiKey + '&action=usercaptchaupload&interactive=1&json=1&file-upload-01=' + sitekey + '&oldsource=recaptchav2&pageurl=' + urllib.quote(referer)
        try:
            token = ''
            sts, data = self.cm.getPage(apiUrl)
            if sts:
                printDBG('API DATA:\n%s\n' % data)
                data = json_loads(data)
                if 'captchaid' in data:
                    captchaid = data['captchaid']
                    sleepObj = GetIPTVSleep()
                    sleepObj.Sleep(300, False)
                    tries = 0
                    while True:
                        tries += 1
                        timeout = sleepObj.getTimeout()
                        if tries == 1:
                            timeout = 10
                        elif timeout > 10:
                            timeout = 5
                        time.sleep(timeout)

                        apiUrl = self.getFullUrl('/index.cgi?apikey=') + apiKey + '&action=usercaptchacorrectdata&json=1&id=' + captchaid
                        sts, data = self.cm.getPage(apiUrl)
                        if not sts:
                            continue
                            # maybe simple continue here ?
                            errorMsgTab.append(_('Network failed %s.') % '2')
                            break
                        else:
                            printDBG('API DATA:\n%s\n' % data)
                            data = json_loads(data)
                            token = data['answer']
                            if token != '':
                                break
                        if sleepObj.getTimeout() == 0:
                            errorMsgTab.append(_('%s timeout.') % self.getMainUrl())
                            break
                else:
                    errorMsgTab.append(data['error'])
            else:
                errorMsgTab.append(_('Network failed %s.') % '1')
        except Exception as e:
            errorMsgTab.append(str(e))
            printExc()

        if sleepObj != None:
            sleepObj.Reset()

        if token == '':
            self.sessionEx.waitForFinishOpen(MessageBox, (_('Resolving reCaptcha with %s failed!\n\n') % self.getMainUrl()) + '\n'.join(errorMsgTab), type=MessageBox.TYPE_ERROR, timeout=10)
        return token
