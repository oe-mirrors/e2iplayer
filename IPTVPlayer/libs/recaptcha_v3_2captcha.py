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
        self.MAIN_URL = 'https://2captcha.com/'

    def getMainUrl(self):
        return self.MAIN_URL

    def getFullUrl(self, url, mainUrl=None):
        if mainUrl == None:
            mainUrl = self.getMainUrl()
        return self.cm.getFullUrl(url, mainUrl)

    def processCaptcha(self, sitekey, referer='', action='verify'):
        sleepObj = None
        token = ''
        errorMsgTab = []
        apiKey = config.plugins.iptvplayer.api_key_2captcha.value
        apiUrl = self.getFullUrl('/in.php?key=') + apiKey + '&method=userrecaptcha&version=v3&action=' + action + '&min_score=0.3&googlekey=' + sitekey + '&json=1&pageurl=' + urllib.quote(referer)
        try:
            token = ''
            sts, data = self.cm.getPage(apiUrl)
            if sts:
                printDBG('API DATA:\n%s\n' % data)
                data = json_loads(data, '', True)
                if data['status'] == '1':
                    captchaid = data['request']
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

                        apiUrl = self.getFullUrl('/res.php?key=') + apiKey + '&action=get&json=1&id=' + captchaid
                        sts, data = self.cm.getPage(apiUrl)
                        if not sts:
                            continue
                            # maybe simple continue here ?
                            errorMsgTab.append(_('Network failed %s.') % '2')
                            break
                        else:
                            printDBG('API DATA:\n%s\n' % data)
                            data = json_loads(data, '', True)
                            if data['status'] == '1' and data['request'] != '':
                                token = data['request']
                                break
                        if sleepObj.getTimeout() == 0:
                            errorMsgTab.append(_('%s timeout.') % self.getMainUrl())
                            break
                else:
                    errorMsgTab.append(data['request'])
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
