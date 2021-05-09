# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetCookieDir, MergeDicts, rm, GetDefaultLang, GetTmpDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs import ph
###################################################

###################################################
# FOREIGN import
###################################################
import random
import re
import base64
from copy import deepcopy
from Components.config import config, ConfigText, getConfigListEntry
############################################

###################################################
# E2 GUI COMMPONENTS
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvmultipleinputbox import IPTVMultipleInputBox
from Screens.MessageBox import MessageBox
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.firstonetv_login = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.firstonetv_password = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry('firstonetv.net ' + _("email") + ':', config.plugins.iptvplayer.firstonetv_login))
    optionList.append(getConfigListEntry('firstonetv.net ' + _("password") + ':', config.plugins.iptvplayer.firstonetv_password))
    return optionList

###################################################


class FirstOneTvApi(CBaseHostClass):
    CACHE_VARS = {}

    def __init__(self):
        CBaseHostClass.__init__(self)
        self.MAIN_URL = 'https://www.firstonetv.net/'
        self.DEFAULT_ICON_URL = self.getFullIconUrl('/images/logo.png')
        self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')

        self.COOKIE_FILE = GetCookieDir('firstonetv.net.cookie')

        self.http_params = {}
        self.http_params.update({'header': self.HTTP_HEADER, 'save_cookie': True, 'load_cookie': True, 'cookiefile': self.COOKIE_FILE})
        self.loggedIn = False
        self.login = None
        self.password = None

    def tryTologin(self):
        printDBG('tryTologin start')

        if None == self.loggedIn or self.login != config.plugins.iptvplayer.firstonetv_login.value or\
            self.password != config.plugins.iptvplayer.firstonetv_password.value:

            self.login = config.plugins.iptvplayer.firstonetv_login.value
            self.password = config.plugins.iptvplayer.firstonetv_password.value

            sts, data = self.cm.getPage(self.getFullUrl('/Account/Settings'), self.http_params)
            if sts:
                self.setMainUrl(self.cm.meta['url'])
                data = ph.find(data, ('<imput', '>', 'email'))[1]
                email = ph.getattr(data, 'value')

                if email and (not self.login.strip() or not self.password.strip()):
                    self.loggedIn = False
                    rm(self.COOKIE_FILE)

                self.loggedIn = False
                if '' == self.login.strip() or '' == self.password.strip():
                    return False

                if email.lower() == self.login.lower():
                    self.loggedIn = True
                    return true

            rm(self.COOKIE_FILE)
            params = MergeDicts(self.http_params, {'use_new_session': True})
            sts, data = self.cm.getPage(self.getFullUrl('/Register-Login'), params)
            if sts:
                self.setMainUrl(self.cm.meta['url'])

            if sts:
                params = dict(self.http_params)
                params['header'] = MergeDicts(self.HTTP_HEADER, {'Referer': self.cm.meta['url']})

                post_data = {'usrmail': self.login, 'password': self.password, 'login': ''}
                sts, data = self.cm.getPage(self.getFullUrl('/Register-Login'), params, post_data)

            if sts and '/Logout' in data:
                printDBG('tryTologin OK')
                self.loggedIn = True
            else:
                msgTab = [_('Login failed.')]
                if sts:
                    msgTab.append(self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'data-abide-error'), ('</div', '>'), False)[1]))
                self.sessionEx.waitForFinishOpen(MessageBox, '\n'.join(msgTab), type=MessageBox.TYPE_ERROR, timeout=10)
                printDBG('tryTologin failed')
        return self.loggedIn

    def getList(self, cItem):
        printDBG("FirstOneTvApi.getChannelsList")
        self.tryTologin()

        channelsTab = []

        if cItem.get('priv_cat') == None:
            defLang = GetDefaultLang()
            sts, data = self.cm.getPage(self.getFullUrl('/Live'), self.http_params)
            if not sts:
                return []

            tmp = ph.find(data, ('<div', '>', 'list-group'), '</section>', flags=0)[1]
            tmp = ph.rfindall(tmp, '</div>', ('<div', '>', 'group-item-grid'), flags=0)
            for item in tmp:
                title = ph.clean_html(ph.getattr(item, 'alt'))
                icon = ph.search(item, ph.IMAGE_SRC_URI_RE)[1]
                url = ph.search(item, ph.A_HREF_URI_RE)[1]
                desc = []
                item = ph.findall(item, ('<div', '>', 'thumb-stats'), '</div>', flags=0)
                for t in item:
                    t = ph.clean_html(t)
                    if t:
                        desc.append(t)
                params = MergeDicts(cItem, {'title': title, 'priv_cat': 'list_channels', 'url': self.getFullUrl(url), 'icon': self.getFullIconUrl(icon), 'desc': ' | '.join(desc)})
                lang = icon.split('?', 1)[0].rsplit('/', 1)[-1].split('.', 1)[0].lower()
                if lang == defLang:
                    channelsTab.insert(0, params)
                else:
                    channelsTab.append(params)
            if self.loggedIn:
                sts, data = self.cm.getPage(self.getFullUrl('/Account/Favorites'), self.http_params)
                if sts:
                    data = ph.find(data, ('<div', '>', 'widgetContent'), '</div>', flags=0)[1]
                    data = ph.find(data, ('<a', '>', 'active'), '</a>')[1]
                    tmp = ph.clean_html(ph.find(data, ('<span', '>'), '</span>', flags=0)[1])
                    try:
                        if int(tmp) > 0:
                            url = ph.search(data, ph.A_HREF_URI_RE)[1]
                            title = ph.clean_html(data)
                            channelsTab.insert(0, MergeDicts(cItem, {'title': title, 'priv_cat': 'list_channels', 'url': self.getFullUrl(url)}))
                    except Exception:
                        printExc()
        else:
            reObj = re.compile('<[/\s]*?br[/\s]*?>', re.I)
            sts, data = self.cm.getPage(cItem['url'], self.http_params)
            if not sts:
                return []

            tmp = ph.find(data, ('<div', '>', 'list-group'), '</section>', flags=0)[1]
            tmp = ph.rfindall(tmp, '</div>', ('<div', '>', 'group-item-grid'), flags=0)
            for item in tmp:
                title = ph.clean_html(ph.find(item, '<h6>', '</h6>', flags=0)[1])
                if not title:
                    title = ph.clean_html(ph.getattr(item, 'alt'))
                icon = ph.search(item, ph.IMAGE_SRC_URI_RE)[1]
                url = ph.search(item, ph.A_HREF_URI_RE)[1]
                desc = []
                tmp = ph.findall(item, ('<div', '>', 'thumb-stats'), '</div>', flags=0)
                for t in tmp:
                    t = ph.clean_html(t)
                    if t:
                        desc.append(t)
                desc = ' | '.join(desc) + '[/br]' + ph.clean_html(reObj.sub('[/br]', ph.find(item, ('<a', '>'), '</a>', flags=0)[1]))
                channelsTab.append(MergeDicts(cItem, {'type': 'video', 'title': title, 'priv_cat': 'list_channels', 'url': self.getFullUrl(url), 'icon': self.getFullIconUrl(icon), 'desc': desc}))
        return channelsTab

    def _getLinks(self, cUrl, params, post_data):
        ret = -1
        links = []
        url = self.getFullUrl('/api/?cacheFucker=' + str(random.random()), cUrl)
        sts, data = self.cm.getPage(url, params, post_data)
        if not sts:
            return -1, []
        printDBG("+++_getLinks+++")
        printDBG(data)
        printDBG("+++++++++++++++")

        try:
            data = json_loads(data)
            if data['state']:
                surl = data['surl']
                if surl.startswith('{'):
                    surl = json_loads(surl)
                    for name, url in surl.iteritems():
                        url = strwithmeta(url, {'Referer': cUrl, 'name': 'firstonetv.net'})
                        links.append({'name': name, 'url': self.getFullUrl(url, cUrl), 'need_resolve': 1})
                else:
                    url = strwithmeta(surl, {'Referer': cUrl, 'name': 'firstonetv.net'})
                    links.append({'name': 'single', 'url': self.getFullUrl(url, cUrl), 'need_resolve': 1})
            else:
                ret = -2
        except Exception:
            printExc()
        return ret, links

    def getVideoLink(self, cItem):
        printDBG("FirstOneTvApi.getVideoLink")
        urlsTab = []

        sts, data = self.cm.getPage(cItem['url'], self.http_params)
        if not sts:
            return urlsTab
        cUrl = self.cm.meta['url']

        SRC_URI_RE = re.compile(r'''\s+?src=(['"])([^>]*?)(?:\1)''', re.I)
        jscode1 = '' # var LOGGEDIN
        jscode2 = '' # cToken
        streamJs = ''
        tmp = ph.findall(data, ('<script', '>'), '</script>', flags=ph.START_S)
        for idx in range(1, len(tmp), 2):
            if 'cToken' in tmp[idx]:
                jscode2 = tmp[idx]
            elif 'var LOGGEDIN' in tmp[idx]:
                jscode1 = tmp[idx]
            elif 'stream:' in tmp[idx - 1]:
                streamJs = ph.search(tmp[idx - 1], SRC_URI_RE)[1]

        country = ph.search(jscode2, '''country\s*?=\s*?['"]([^'^"]+?)['"]''')[0]
        cToken = ph.search(jscode2, '''cToken\s*?=\s*?['"]([^'^"]+?)['"]''')[0]
        channelID = ph.search(jscode2, '''channelID\s*?=\s*?['"]([^'^"]+?)['"]''')[0]
        channel_post_data = {'action': 'channel', 'ctoken': cToken, 'c': country, 'id': channelID, 'native_hls': '0', 'unsecure_hls': '0'}

        url = self.getFullUrl('/api/?cacheFucker=' + str(random.random()), cUrl)
        post_data = {'action': 'tracking', 'act': 'get', 'c': country, 'id': channelID}
        params = dict(self.http_params)
        params['header'] = MergeDicts(self.HTTP_HEADER, {'Referer': cUrl, 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'X-Requested-With': 'XMLHttpRequest'})
        sts, tmp = self.cm.getPage(url, params, post_data)
        if not sts:
            return []
        printDBG("+++++tracking+++++")
        printDBG(tmp)
        printDBG("++++++++++++++++++")

        if cToken:
            ret, links = self._getLinks(cUrl, params, channel_post_data)
            if links:
                return links

        hiroRetry = 0
        while hiroRetry < 3:
            hiroRetry += 1
            url = self.getFullUrl('/api/?cacheFucker=' + str(random.random()), cUrl)
            post_data = {'action': 'hiro', 'result': 'get'}
            sts, tmp = self.cm.getPage(url, params, post_data)
            if not sts:
                return []
            #printDBG("++++++++++++++++++++++++++++++++++")
            #printDBG(tmp)
            #printDBG("++++++++++++++++++++++++++++++++++")
            hiroErrorCode = -1
            try:
                tmp = json_loads(tmp)
                post_data = {'action': 'hiro', 'result': '', 'hash': tmp['hash'], 'time': tmp['time']}

                streamJsData = None
                tries = 0
                while tries < 5:
                    tries += 1
                    jscode = list(self.CACHE_VARS.get(streamJs, []))
                    jscode.append('try {print(eval("%s"));} catch (e) {print(e);}' % tmp['hiro'])

                    ret = js_execute('\n'.join(jscode))
                    if 'identifier' in ret['data'] and 'undefined' in ret['data']:
                        identifier = ph.search(ret['data'], "'([^']+?)'")[0]
                        sts, tmp2 = self.cm.getPage(self.getFullUrl(streamJs, cUrl), self.http_params)
                        if sts:
                            if not streamJsData:
                                jscode2 = ["top={'location':'%s'};self=top;document={'domain':'%s'};window=this;function eval(data){print(data);}" % (cUrl, self.cm.getBaseUrl(cUrl, True)), jscode1]
                                jscode2.append(tmp2)
                                ret = js_execute('\n'.join(jscode2))
                                if 0 != ret['code']:
                                    raise Exception('stream script failed')
                                streamJsData = ret['data']

                            value = ph.search(streamJsData, '[\}\s;](%s=[^;]+?;)' % identifier)[0]
                            if not value:
                                raise Exception('can not find in the "%s" stream script' % identifier)
                            if streamJs not in self.CACHE_VARS:
                                self.CACHE_VARS = {streamJs: []}
                            self.CACHE_VARS[streamJs].append(value)
                            continue
                    elif ret['code'] == 0:
                        post_data['result'] = ret['data'].strip()
                        url = self.getFullUrl('/api/?cacheFucker=' + str(random.random()), cUrl)
                        sts, tmp = self.cm.getPage(url, params, post_data)
                        if not sts:
                            Exception('can not find in the "%s" stream script' % identifier)
                        tmp = json_loads(tmp)
                        hiroErrorCode = tmp['errorCode']
                        if tmp['state']:
                            cToken = tmp['ctoken']
                            channel_post_data['ctoken'] = cToken
                            printDBG("$$$$ hiro $$$")
                            printDBG(tmp)
                            printDBG("$$$$$$$$$$$$$")
                            hiroWorks = True # {'errorCode': 801, 'msg': 'Wrong captcha.', 'state': False, 'ctoken': 'suckmydick'}
                    break
            except Exception:
                printExc()

            if hiroErrorCode == 801:
                continue
            break

        if 0 != hiroErrorCode:
            # add support for picture capcha
            statusText = 'Please solve the following captcha to verify that you are human.'
            while True:
                url = self.getFullUrl('/src/captcha/?cacheFucker=' + str(random.random()), cUrl)
                sts, data = self.cm.getPage(url, params)
                if not sts:
                    return []
                try:
                    data = json_loads(data)
                    post_data = {'action': 'captcha', 'response': '', 'hash': data['hash'], 'time': data['time']}
                    pictureMarker = 'data:image/png;base64,'
                    if not data['image'].startswith(pictureMarker):
                        SetIPTVPlayerLastHostError(_('Wrong captcha image data!'))
                        raise Exception('Wrong image data!')
                    image = base64.b64decode(data['image'][len(pictureMarker):])
                    filePath = GetTmpDir('.iptvplayer_captcha.jpg')
                    with open(filePath, 'wb') as f:
                        f.write(image)
                except Exception:
                    printExc()
                    return []

                params = deepcopy(IPTVMultipleInputBox.DEF_PARAMS)
                #params['accep_label'] = sendLabel
                params['title'] = 'Are you Human?'
                params['status_text'] = statusText
                params['status_text_hight'] = 200
                params['with_accept_button'] = True
                params['list'] = []
                item = deepcopy(IPTVMultipleInputBox.DEF_INPUT_PARAMS)
                item['label_size'] = (660, 110)
                item['input_size'] = (680, 25)
                item['icon_path'] = filePath
                item['title'] = _('Answer')
                item['input']['text'] = ''
                params['list'].append(item)
                params['vk_params'] = {'invert_letters_case': True}

                ret = 0
                retArg = self.sessionEx.waitForFinishOpen(IPTVMultipleInputBox, params)
                printDBG(retArg)
                if retArg and len(retArg) and retArg[0]:
                    printDBG(retArg[0])
                    post_data['response'] = retArg[0][0]
                else:
                    return []

                url = self.getFullUrl('/api/?cacheFucker=' + str(random.random()), cUrl)
                sts, data = self.cm.getPage(url, params, post_data)
                if sts:
                    try:
                        data = json_loads(data)
                        printDBG("$$$$ captcha $$$")
                        printDBG(data)
                        printDBG("$$$$$$$$$$$$$$$$")
                        hiroErrorCode = data['errorCode']
                        if data['state']:
                            cToken = data['ctoken']
                            channel_post_data['ctoken'] = cToken
                            break
                        statusText = data['msg'] + '\n' + 'Please try again.'
                    except Exception:
                        printExc()
                        break

        return self._getLinks(cUrl, params, channel_post_data)[1]

    def getResolvedVideoLink(self, videoUrl):
        printDBG("FirstOneTvApi.getResolvedVideoLink [%s]" % videoUrl)
        return getDirectM3U8Playlist(videoUrl)
