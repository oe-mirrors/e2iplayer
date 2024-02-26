# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError, GetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetTmpDir
from Plugins.Extensions.IPTVPlayer.components.iptvmultipleinputbox import IPTVMultipleInputBox
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
###################################################
# FOREIGN import
###################################################
import re
try:
    import json
except Exception:
    import simplejson as json
from Components.config import config, ConfigText, getConfigListEntry
###################################################


###################################################
# E2 GUI COMMPONENTS
###################################################
from Screens.MessageBox import MessageBox
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.streamliveto_login = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.streamliveto_password = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Login") + ": ", config.plugins.iptvplayer.streamliveto_login))
    optionList.append(getConfigListEntry(_("Password") + ": ", config.plugins.iptvplayer.streamliveto_password))
    return optionList


def gettytul():
    return 'https://streamlive.to/'


class StreamLiveTo(CBaseHostClass):
    HTTP_HEADER = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:46.0) Gecko/20100101 Firefox/46.0', 'Accept': 'text/html'}
    HTTP_MOBILE_HEADER = {'User-Agent': 'Mozilla/5.0 (iPad; U; CPU OS 3_2 like Mac OS X; en-us) AppleWebKit/531.21.10 (KHTML, like Gecko) Version/4.0.4 Mobile/7B334b Safari/531.21.10', 'Accept': 'text/html'}
    MAIN_URL = 'https://www.streamlive.to/'

    MAIN_CAT_TAB = [{'category': 'list_filters', 'title': 'Live Channels', 'icon': ''},
                    {'category': 'search', 'title': _('Search'), 'search_item': True},
                    {'category': 'search_history', 'title': _('Search history')}]

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'StreamLiveTo.tv', 'cookie': 'streamliveto.cookie'})
        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.cacheFilters = {}
        self.cacheFiltersKeys = []
        self.DEFAULT_ICON_URL = self.MAIN_URL + 'images/logo.png'

    def _getFullUrl(self, url):
        if 0 < len(url):
            if url.startswith('//'):
                url = 'https:' + url
            elif not url.startswith('http'):
                url = self.MAIN_URL + url
        return url

    def getPage(self, url, params={}, post_data=None):
        return self.cm.getPage(url, params, post_data)
        return self.checkBotProtection(url, params)

    def cleanHtmlStr(self, data):
        data = data.replace('&nbsp;', ' ')
        data = data.replace('&nbsp', ' ')
        return CBaseHostClass.cleanHtmlStr(data)

    def listsTab(self, tab, cItem, type='dir'):
        printDBG("StreamLiveTo.listsTab")
        for item in tab:
            params = dict(cItem)
            params.update(item)
            params['name'] = 'category'
            if type == 'dir':
                self.addDir(params)
            else:
                self.addVideo(params)

    def fillCacheFilters(self):
        printDBG("StreamLiveTo.fillCacheFilters")
        self.cacheFilters = {}
        self.cacheFiltersKeys = []

        sts, data = self.getPage(self._getFullUrl('channels'), self.defaultParams)
        #sts, data = self.getPage(self.MAIN_URL, self.defaultParams)
        if not sts:
            return

        tmpTab = []
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<select name="category"', '</select>', False)[1]
        tmp = re.compile('<option [^>]*?value="([^"]*?)"[^>]*?>([^<]+?)</option>').findall(tmp)
        for item in tmp:
            tmpTab.append({'title': item[1], 'f_cat': urllib_quote(item[0])})
        if len(tmpTab):
            self.cacheFilters['f_cat'] = tmpTab
            self.cacheFiltersKeys.append('f_cat')

        tmpTab = []
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<select name="language"', '</select>', False)[1]
        tmp = re.compile('<option [^>]*?value="([^"]*?)"[^>]*?>([^<]+?)</option>').findall(tmp)
        for item in tmp:
            tmpTab.append({'title': item[1], 'f_lang': item[0]})
        if len(tmpTab):
            self.cacheFilters['f_lang'] = tmpTab
            self.cacheFiltersKeys.append('f_lang')

        tmpTab = []
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<select name="sortBy"', '</select>', False)[1]
        tmp = re.compile('<option [^>]*?value="([^"]*?)"[^>]*?>([^<]+?)</option>').findall(tmp)
        for item in tmp:
            tmpTab.append({'title': item[1], 'f_sort': item[0]})

        if len(tmpTab):
            self.cacheFilters['f_sort'] = tmpTab
            self.cacheFiltersKeys.append('f_sort')

        sts, data = self.getPage(self._getFullUrl('channelsPages.php'), self.defaultParams)
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenMarkers(data, '<h2', '</h2>')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
        tmpTab = []
        for item in data:
            val = self.cm.ph.getSearchGroups(item, '''[\?&]list=([^'^"^&]+?)['"&]''')[0]
            title = self.cleanHtmlStr(item)
            tmpTab.append({'title': title, 'f_type': val})
        if len(tmpTab) == 0:
            for item in [(_('Any'), ''), (_('Free'), 'free'), (_('Premium'), 'premium')]:
                tmpTab.append({'title': item[0], 'f_type': item[1]})
        if len(tmpTab):
            self.cacheFilters['f_type'] = tmpTab
            self.cacheFiltersKeys.insert(0, 'f_type')

    def listFilters(self, cItem, nextCategory):
        printDBG("StreamLiveTo.listFilters")
        cItem = dict(cItem)

        f_idx = cItem.get('f_idx', 0)
        if f_idx == 0:
            self.fillCacheFilters()

        if f_idx >= len(self.cacheFiltersKeys):
            return

        filter = self.cacheFiltersKeys[f_idx]
        f_idx += 1
        cItem['f_idx'] = f_idx
        if f_idx == len(self.cacheFiltersKeys):
            cItem['category'] = nextCategory
        self.listsTab(self.cacheFilters.get(filter, []), cItem)

    def listChannels(self, cItem):
        printDBG("StreamLiveTo.listChannels")
        page = cItem.get('page', 1)
        post_data = {'page': page}

        keysMap = {'cat': 'category', 'lang': 'language', 'sort': 'sortBy', 'q': 'query', 'type': 'list'}
        if 'f_q' in cItem:
            keys = ['f_q']
        else:
            keys = []
        keys.extend(self.cacheFiltersKeys)
        for item in keys:
            if item not in cItem:
                continue
            key = keysMap.get(item[2:], item[2:])
            post_data[key] = cItem[item]

        url = self.getFullUrl('channelsPages.php')

        sts, data = self.getPage(url, self.defaultParams, post_data)
        if not sts:
            return

        if 'data-page="{0}"'.format(page + 1) in data:
            nextPage = True
        else:
            nextPage = False

        data = self.cm.ph.rgetAllItemsBeetwenNodes(data.split('<nav>', 1)[0], ('</div', '>'), ('<div', '>', 'item'))
        for item in data:
            url = self._getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0])
            icon = self._getFullUrl(self.cm.ph.getSearchGroups(item, 'src="([^"]+?)"')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<strong>', '</strong>', False)[1])
            if '' == title:
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'title="([^"]+?)"')[0])
            if 'class="premium_only"' in item or 'Premium Only' in item:
                postfix = 'PREMIUM ONLY'
            elif 'glyphicon-king' in item:
                postfix = 'KING'
            else:
                postfix = ''
            if postfix != '':
                title += ' [%s]' % postfix
            desc = []
            tmp = self.cm.ph.getAllItemsBeetwenNodes(item, ('<div', '>', '"jt'), ('</div', '>'))
            for t in tmp:
                if 'bottom' in t:
                    continue
                t = self.cleanHtmlStr(t)
                if t != '':
                    desc.append(t)
            desc = ' | '.join(desc)
            tmp = self.cm.ph.getAllItemsBeetwenNodes(item, ('<div', '>', 'block'), ('</div', '>'), False)
            for t in tmp:
                t = self.cleanHtmlStr(t)
                if t != '':
                    desc += '[/br]' + t
            if self.cm.isValidUrl(url):
                params = {'title': title, 'url': url, 'desc': desc, 'icon': icon}
                self.addVideo(params)
        if nextPage:
            params = dict(cItem)
            params.update({'title': _("Next page"), 'page': page + 1})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("StreamLiveTo.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['f_q'] = urllib_quote(searchPattern)
        self.listChannels(cItem)

    def getLinksForVideo(self, cItem):
        printDBG("StreamLiveTo.getLinksForVideo [%s]" % cItem)
        urlTab = []
        videoUrl = cItem['url']
        if videoUrl.startswith('http'):
            '''
            httpParams = dict(self.defaultParams)
            httpParams['header'] = dict(self.HTTP_HEADER)
            httpParams['header']['Referer'] = videoUrl

            _url_re = re.compile("http(s)?://(\w+\.)?(ilive.to|streamlive.to)/.*/(?P<channel>\d+)")
            channel = _url_re.match(videoUrl).group("channel")

            sts, data = self.getPage('http://www.streamlive.to/view/%s' % channel, httpParams)

            sts, data = self.getPage(videoUrl, self.defaultParams)
            if not sts: []
            '''
            while True:
                urlTab = self.up.getVideoLinkExt(videoUrl)
                for idx in range(len(urlTab)):
                    urlTab[idx]['need_resolve'] = 0
                if 0 == len(urlTab) and 'get more FREE credits' in GetIPTVPlayerLastHostError(False):
                    ret = -1
                    while ret == -1:
                        ret = self.listGetFreeCredits()
                    if ret == 1:
                        continue
                break
        return urlTab

    def getFavouriteData(self, cItem):
        return cItem['url']

    def getLinksForFavourite(self, fav_data):
        return self.getLinksForVideo({'url': fav_data})

    def listGetFreeCredits(self):
        printDBG("StreamLiveTo.listGetFreeCredits")
        baseUrl = self._getFullUrl('get_free_credits')
        httpParams = dict(self.defaultParams)
        httpParams['header'] = dict(self.HTTP_HEADER)
        httpParams['header']['Referer'] = baseUrl

        sts, data = self.getPage(baseUrl, httpParams)
        if not sts:
            SetIPTVPlayerLastHostError(_('Fail to get "%s".') % baseUrl)
            return 0
        sts, data = self.cm.ph.getDataBeetwenMarkers(data, '<form method="post">', '</form>')
        m1 = 'recaptcha_challenge_field'
        m2 = 'recaptcha_response_field'
        errMsg1 = _('Fail to get captcha data.')
        if sts:
            captchaUrl = self.cm.ph.getSearchGroups(data, '''['"](http[^"']+?recaptcha/api[^"']*?)["']''')[0]
        if not sts or '' == captchaUrl or m1 not in data or m2 not in data:
            SetIPTVPlayerLastHostError(errMsg1)
            return 0
        sts, data = self.getPage(captchaUrl, httpParams)
        if not sts:
            SetIPTVPlayerLastHostError(_('Fail to get "%s".') % captchaUrl)
            return 0
        challenge = self.cm.ph.getSearchGroups(data, '''challenge\s*:\s*['"]([^'^"]+?)['"]''')[0]
        lang = self.cm.ph.getSearchGroups(data, '''lang\s*:\s*['"]([^'^"]+?)['"]''')[0]
        server = self.cm.ph.getSearchGroups(data, '''server\s*:\s*['"]([^'^"]+?)['"]''')[0]
        site = self.cm.ph.getSearchGroups(data, '''site\s*:\s*['"]([^'^"]+?)['"]''')[0]
        if '' == challenge or '' == lang or '' == server or '' == site:
            SetIPTVPlayerLastHostError(errMsg1)
            return 0

        captchaUrl = server + 'reload?c=%s&k=%s&reason=i&type=image&lang=%s&th=' % (challenge, site, lang)
        sts, data = self.getPage(captchaUrl, httpParams)
        if not sts:
            SetIPTVPlayerLastHostError(_('Fail to get "%s".') % captchaUrl)
            return 0

        sts, challenge = self.cm.ph.getDataBeetwenMarkers(data, "finish_reload('", "'", False)
        if not sts:
            SetIPTVPlayerLastHostError(errMsg1)
            return 0

        imgUrl = 'http://www.google.com/recaptcha/api/image?c=' + challenge
        #return
        params = {'maintype': 'image', 'subtypes': ['jpeg'], 'check_first_bytes': [b'\xFF\xD8', b'\xFF\xD9']}
        filePath = GetTmpDir('.iptvplayer_captcha.jpg')
        ret = self.cm.saveWebFile(filePath, imgUrl, params)
        if not ret.get('sts'):
            SetIPTVPlayerLastHostError(_('Fail to get "%s".') % imgUrl)
            return 0

        from copy import deepcopy
        params = deepcopy(IPTVMultipleInputBox.DEF_PARAMS)
        params['accep_label'] = _('Send')
        params['title'] = _('Answer')
        params['list'] = []
        item = deepcopy(IPTVMultipleInputBox.DEF_INPUT_PARAMS)
        item['label_size'] = (300, 57)
        item['input_size'] = (300, 25)
        item['icon_path'] = filePath
        item['input']['text'] = ''
        params['list'].append(item)

        ret = 0
        retArg = self.sessionEx.waitForFinishOpen(IPTVMultipleInputBox, params)
        printDBG(retArg)
        if retArg and len(retArg) and retArg[0]:
            printDBG(retArg[0])
            sts, data = self.cm.getPage(baseUrl, httpParams, {'recaptcha_challenge_field': challenge, 'recaptcha_response_field': retArg[0], 'submit': 'Get Free 10 Credits'})
            printDBG(data)
            if 'got free' in data:
                ret = 1
            elif 'incorrect' in data:
                ret = -1
            if sts:
                msg = self.cm.ph.getDataBeetwenMarkers(data, '<div style="color:', '</div>')[1]
                SetIPTVPlayerLastHostError(self.cleanHtmlStr(msg))
            else:
                SetIPTVPlayerLastHostError(_('Fail to get "%s".') % baseUrl)
        else:
            SetIPTVPlayerLastHostError(_('Wrong answer.'))
        return ret

    def checkBotProtection(self, url, httpParams):
        printDBG("StreamLiveTo.checkBotProtection")
        captchaMarker = 'name="captcha"'
        sts, data = self.cm.getPage(url, httpParams)
        if not sts:
            return False, None
        if captchaMarker not in data:
            return True, data
        data = self.cm.ph.getDataBeetwenReMarkers(data, re.compile('<form [^>]+?>'), re.compile('</form>'), True)[1]
        title = self.cm.ph.getDataBeetwenMarkers(data, '<h1>', '</h1>')[1]
        question = self.cm.ph.getDataBeetwenReMarkers(data, re.compile('</h1>'), re.compile('</form>'), True)[1]

        title = self.cleanHtmlStr(title)
        question = self.cleanHtmlStr(question)

        from copy import deepcopy
        params = deepcopy(IPTVMultipleInputBox.DEF_PARAMS)
        params['accep_label'] = _('Send')
        params['title'] = title
        params['list'] = []
        item = deepcopy(IPTVMultipleInputBox.DEF_INPUT_PARAMS)
        item['label_size'] = (550, 50 + 25 * question.count('\n'))
        item['title'] = question
        item['input']['text'] = ''
        params['list'].append(item)

        retArg = self.sessionEx.waitForFinishOpen(IPTVMultipleInputBox, params)
        printDBG(retArg)
        if retArg and 1 == len(retArg) and retArg[0] and 1 == len(retArg[0]):
            answer = '%s' % retArg[0][0]

            newHttpParams = dict(httpParams)
            newHeader = dict(self.HTTP_HEADER)
            newHeader['Referer'] = url
            newHttpParams['header'] = newHttpParams

            sts, data = self.cm.getPage(url, newHttpParams, {'captcha': answer})
            if not sts:
                return False, None
            resultMarker = 'Your answer is wrong.'
            if resultMarker in data:
                self.sessionEx.open(MessageBox, resultMarker, type=MessageBox.TYPE_ERROR, timeout=10)
            else:
                return True, data
        return False, None

    def doLogin(self, login, password):
        logged = False
        HTTP_HEADER = dict(self.HTTP_MOBILE_HEADER)
        HTTP_HEADER.update({'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'X-Requested-With': 'XMLHttpRequest'})

        post_data = {'username': login, 'password': password, 'accessed_by': 'web', 'submit': 'Login', 'x': 0, 'y': 0}
        params = {'header': HTTP_HEADER, 'cookiefile': self.COOKIE_FILE, 'save_cookie': True}
        loginUrl = 'https://www.streamlive.to/login.php'
        sts, data = self.cm.getPage(loginUrl, params, post_data)
        if sts and ('/logout"' in data or '/logout.php"' in data):
            logged = True
        return logged

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            login = config.plugins.iptvplayer.streamliveto_login.value
            passwd = config.plugins.iptvplayer.streamliveto_password.value
            logged = False
            if '' != login.strip() and '' != passwd.strip():
                logged = self.doLogin(login, passwd)
                if not logged:
                    self.sessionEx.open(MessageBox, _('Login failed.'), type=MessageBox.TYPE_INFO, timeout=10)
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})
            #if logged:
            #    self.addDir({'name':'category', 'title':_('Get free credits'), 'category':'get_free_credits'})
        elif category == 'get_free_credits':
            self.listGetFreeCredits()
        elif category == 'list_filters':
            self.listFilters(self.currItem, 'list_channels')
        elif category == 'list_channels':
            self.listChannels(self.currItem)
    #SEARCH
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category'})
            self.listSearchResult(cItem, searchPattern, searchType)
    #HISTORIA SEARCH
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, StreamLiveTo(), True, [CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO])
