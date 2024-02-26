# -*- coding: utf-8 -*-
###################################################
# 2019-02-27 Celeburdi
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, getF4MLinksWithMeta, getMPDLinksWithMeta
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.p2p3.pVer import isPY2
if isPY2():
    import cookielib
else:
    import http.cookiejar as cookielib
###################################################
# FOREIGN import
###################################################
import os
import datetime
import time
import zlib
import base64
from hashlib import sha1
from Components.config import config, ConfigText, getConfigListEntry
###################################################


###################################################
# E2 GUI COMMPONENTS
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvmultipleinputbox import IPTVMultipleInputBox
from Screens.MessageBox import MessageBox
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.rtlmosthu_login = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.rtlmosthu_password = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Email") + ":", config.plugins.iptvplayer.rtlmosthu_login))
    optionList.append(getConfigListEntry(_("password") + ":", config.plugins.iptvplayer.rtlmosthu_password))
    return optionList
###################################################


def gettytul():
    return 'https://rtlmost.hu/'


def _getImageExtKey(images, role):
    try:
        for i in images:
            if i.get('role') == role:
                return i['external_key']
    except:
        pass
    return None


def _updateOtherInfo(otherInfo, item):
    try:
        otherInfo['duration'] = str(datetime.timedelta(seconds=item['duration']))
    except:
        pass
    try:
        otherInfo['age_limit'] = str(item['csa']['sort_index'])
    except:
        pass


class RtlMostHU(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'rtlmost.hu', 'cookie': 'rtlmosthu.cookie'})

        self.SEARCH_TYPES = [
            (_("Program"), "Program"),
            (_("Video"), "Video"),
            (_("Preview"), "Preview"),
            (_("Playlist"), "Playlist")
        ]

        self.DEFAULT_ICON_URL = 'https://dl.dropboxusercontent.com/s/bfdyotdpo66cide/rtlmostlogo.png?dl=0'
        self.HEADER = self.cm.getDefaultHeader()
        self.MAIN_URL = 'https://rtlmost.hu/'
        self.API_URL = zlib.decompress(base64.b64decode(
            'eJwdxkEKwCAMBdEb+aELF72MWI21oChJVHr7SjfzJqt2OYEeTH1iLLQ8k7G9+Nckxj+YB7aaGldB'
            'tTe30d2iC0I8n0AC1pKH23W1ieIDaJggkw=='))
        self.API_HEADER = dict(self.HEADER)
        self.API_HEADER.update({'x-customer-name': 'rtlhu'})
        self.MENU_URL = self.API_URL + zlib.decompress(base64.b64decode(
            'eJxLy89JSS0qts/JzM0ssa2uVctPSytOBbEAjDgKZQ=='))
        self.PROGRAMS_URL = self.API_URL + zlib.decompress(base64.b64decode(
            'eJxLy89JSS0q1q+u1S8oyk8vSswtts/JzM0ssa2uVctPSytOBbOSixNtTdXKM0sybAsSi1LzSpLz'
            '80pSK0oAFDYYow=='))
        self.SUBCATS_URL = self.API_URL + zlib.decompress(base64.b64decode(
            'eJwrKMpPL0rMLdavrrUvzyzJsM3JzMsu1ikuTUpOLCnWKcpMzygpBgAacg7K'))
        self.EPISODES_URL = self.API_URL + zlib.decompress(base64.b64decode(
            'eJwlyjEKwzAMBdDbeDJk6ih6FlWVU1EbC3/FIYTcvZBub3g++jq4YTmvZdpbO54CpkfaLT4k1Ry5'
            'DNVmW3OWL1IcrjQtT8le+aiGSNhewkHnlao1u9FLgd5CH0H/8QMyYSqT'))
        self.VIDEO_URL = self.API_URL + zlib.decompress(base64.b64decode(
            'eJwtyDEKgDAMAMDfOBWcHItPKSGNNbShIdGKiH938cYbnKn7/LwrOsRluvjYIzZWD5sRCZ+igNWD'
            'Wi8GkligkAcnG4yUMrs2uP/+AKaUHqw='))
        self.ICON_PATH = zlib.decompress(base64.b64decode(
            'eJzTLzPSz8xNTE8t1q+u1S9KLLcvz0wpybCtrlXLSM1MzygBsdIywVRhaWJOZkklWCS/KDcRLJiZ'
            'V5JalJOYnArkAABkJB19'))
        self.ICON_HASH = zlib.decompress(base64.b64decode(
            'eJwzNUkyNTUxsEg0NTawNAVxjNPSzC1TLS0AVI4Gfg=='))
        self.ICON_URL = zlib.decompress(base64.b64decode(
            'eJzLKCkpKLbS18/MTUxPLdYzK8hJrNRLK6quVctILM6wra4FAM7fDFk='))
        self.LOGIN_URL = zlib.decompress(base64.b64decode(
            'eJwdjN0KgjAYQN9md2pkCAUSiCIaxcIo6ybmsjndj2yf2Q+9e+TN4cCB0wD0duV5QjOuXANCagtu'
            'M3iEUj0osO5U1hOzOPx8UU+sHbW5/R2IYTUk6hFKXXFRo7s2kkDYWq0Q6fmmfoX+FePB2c7bTuPD'
            'GRZSOc0xSgOV4qgdkzLIczYWuwtflg5j772ZCfX0U/BZksWWFsUJUSJERWg3fX939EE8'))
        self.ACCOUNT_URL = zlib.decompress(base64.b64decode(
            'eJwlxt0KgjAUAOC38U6NDKFAokhEo1gYZd3IGHPz7xzZjtgPvXtE39WniQa78v0OVQ2eoa5HS54e'
            'fS4EjkDWU5I2/6dQ4Rr5SLokbCVE749jpTCSfqvQ9JyixiI4fKj38hkFJWOje5g3LbLzjRY9uPqy'
            'TUJI2LaZ4iLMMjXlx3u9LFylXicz6+ARJBSoON1ZkefXL7XkOfU='))
        self.queryFiltered = zlib.decompress(base64.b64decode(
            'eJylzLEKwjAQBuB3CcTRoUUHoYNVnPsG4VqvbTAx8S6paOm7m4KDc4SfO/7h++dZeCCwLA7iEZFe'
            '1bxsPAy4/lEHbpCab+2hw3DRJiBxJXf1mqIAMzijYesNhN6RVYw06Q5lebT7gVz06omtLGsKZowq'
            'XXUzsU1SFqc8r/U/OoFrru+cM7mW30jIbB2H3Ik7Tj8Lu3OKWJYP1PGh/Q=='))
        self.query = zlib.decompress(base64.b64decode(
            'eJyrrlYqSCxKzC1WslIqLE0tqrStrlUrSExPBdEZmSXFAalFARCuUm0tAJJjEVE='))
        self.QUERY_URL = zlib.decompress(base64.b64decode(
            'eJxVy00LgjAYwPGv4qnbXPmSFkhIl16gSyDe5HGb+uCYa86hRN+9Qx3q+If/r7NWj3tKVQfMoZvn'
            'nvBR+SDbQSL4Sli6oai4mMVIjZXdVGkz8GqrJSyVC6vniz4mYZbDTL6IQCuUzfJPec1gPAcKpQTv'
            'Ag7uzKC2XugHkZ+sfpTWEhlYHBRBnt1O+bE4F2V5/XuQ9GLJ4oaJdcDqMNk2dcA4JElYixTSaB3F'
            'uxTeF2ZLTA=='))
        self.queryParams = {'header': self.HEADER, 'raw_post_data': True}
        self.apiParams = {'header': self.API_HEADER}
        self.loginParams = {'header': self.HEADER}
        self.loggedIn = False

        self.login = config.plugins.iptvplayer.rtlmosthu_login.value
        self.password = config.plugins.iptvplayer.rtlmosthu_password.value
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

    def getFullIconUrl(self, url):
        if not url:
            return self.DEFAULT_ICON_URL
        # hardcoded jpeg bug correction 'Alvilág'
        if url == 'tj2078967':
            url = 'tp2078967'
        if url[:1] == 't':
            width = 250
            height = 617
        else:
            width = 480
            height = 360
        if url[1:2] == 'p':
            format = 'png'
        else:
            format = 'jpeg'
        path = self.ICON_PATH.format(url[2:], width, height, 'scale_crop', 60, format, 1)
        return self.ICON_URL.format(path, sha1(path + self.ICON_HASH).hexdigest())

    def getPage(self, url, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        baseUrl = self.cm.iriToUri(url)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def listMainMenu(self, cItem):
        printDBG("RtlMostHU.listMainMenu")
        sts, data = self.cm.getPage(self.MENU_URL.format(100, 0), self.apiParams)
        if not sts:
            return
        try:
            data = json_loads(data)
            for i in data:
                title = i['name']
                url = str(i['id'])
                params = dict(cItem)
                params.update({'category': 'list_programs', 'title': title, 'url': url})
                self.addDir(params)
        except Exception:
            printExc()
        MAIN_CAT_TAB = [{'category': 'search', 'title': _('Search'), 'search_item': True},
                        {'category': 'search_history', 'title': _('Search history'), }]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listPrograms(self, cItem):
        printDBG("RtlMostHU.listPrograms")
        url = cItem['url']
        sts, data = self.cm.getPage(self.PROGRAMS_URL.format(url, 100, 0), self.apiParams)
        if not sts:
            return
        try:
            data = json_loads(data)
            for i in data:
                title = i['title']
                url = str(i['id'])
                desc = i.get('description', '')
                icon = _getImageExtKey(i['images'], 'totem')
                params = dict(cItem)
                if icon:
                    params['icon'] = 'tj' + icon
                params.update({'good_for_fav': True, 'category': 'list_subcategories', 'title': title, 'url': url, 'desc': desc, 'other_info': {}})
                self.addDir(params)
        except Exception:
            printExc()

    def listPlaylist(self, cItem):
        printDBG("RtlMostHU.listPlaylist")
        url = cItem['url']
        sts, data = self.cm.getPage(self.VIDEO_URL.format(url), self.apiParams)
        if not sts:
            return
        try:
            data = json_loads(data)
            for c in data['clips']:
                title = c['title']
                otherInfo = dict(cItem['other_info'])
                _updateOtherInfo(otherInfo, c)
                desc = c.get('description')
                icon = _getImageExtKey(c['images'], 'vignette')
                params = dict(cItem)
                if desc:
                    params['desc'] = desc
                if icon:
                    params['icon'] = 'vj' + icon
                params.update({'good_for_fav': True, 'title': title, 'url': c['video_id'], 'other_info': otherInfo})
                self.addVideo(params)
        except Exception:
            printExc()

    def listEpisodes(self, cItem, subcat):
        printDBG("RtlMostHU.listEpisodes")
        url = cItem['url']
        sts, data = self.cm.getPage(self.EPISODES_URL.format(url, subcat, 100, 0), self.apiParams)
        if not sts:
            return
        try:
            data = json_loads(data)
            for i in data:
                clips = i['clips']
                if 0 == len(clips):
                    continue
                otherInfo = dict(cItem['other_info'])
                if 1 == len(clips):
                    c = clips[0]
                    isVideo = True
                    url = c['video_id']
                else:
                    c = i
                    isVideo = False
                    url = c['id']
                _updateOtherInfo(otherInfo, c)
                title = c['title']
                desc = c.get('description')
                icon = _getImageExtKey(c['images'], 'vignette')
                params = dict(cItem)
                params.pop('subcat', None)
                if desc:
                    params['desc'] = desc
                if icon:
                    params['icon'] = 'vj' + icon
                params.update({'good_for_fav': True, 'title': title, 'url': url, 'other_info': otherInfo})
                if isVideo:
                    self.addVideo(params)
                else:
                    params['category'] = 'list_playlist'
                    self.addDir(params)
        except Exception:
            printExc()

    def listSubcategories(self, cItem):
        printDBG("RtlMostHU.listSubcategories")
        url = cItem['url']
        sts, data = self.cm.getPage(self.SUBCATS_URL.format(url), self.apiParams)
        if not sts:
            return
        try:
            data = json_loads(data)
            subcats = data['program_subcats']
            if 0 == len(subcats):
                return
            if 1 == len(subcats):
                i = subcats[0]
                self.listEpisodes(cItem, str(i['id']))
                return
            for i in subcats:
                title = i['title']
                subcat = str(i['id'])
                params = dict(cItem)
                params.update({'good_for_fav': True, 'category': 'list_episodes', 'title': title, 'url': url, 'subcat': subcat})
                self.addDir(params)
        except Exception:
            printExc()

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("RtlMostHU.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        if searchType == 'Program':
            queryType = 'program'
            role = 'totem'
            isVideo = False
            query = self.query
            next_category = 'list_subcategories'
        elif searchType == 'Playlist':
            queryType = 'playlist'
            role = 'vignette'
            isVideo = False
            query = self.queryFiltered
            next_category = 'list_playlist'
        elif searchType == 'Video':
            queryType = 'vi'
            role = 'vignette'
            isVideo = True
            query = self.queryFiltered
        elif searchType == 'Preview':
            queryType = 'vc'
            role = 'vignette'
            isVideo = True
            query = self.queryFiltered
        else:
            return
        page = cItem.get('page', 0)
        sts, data = self.cm.getPage(self.QUERY_URL.format(queryType), self.queryParams,
          query.format(urllib_quote(searchPattern), page, 50))
        if not sts:
            return
        try:
            data = json_loads(data)
            hits = data['hits']
            nbPages = data.get('nbPages')
            for i in hits:
                otherInfo = {}
                _updateOtherInfo(otherInfo, i)
                title = i['title']
                params = dict(cItem)
                params.pop('page', None)
                icon = _getImageExtKey(i['images'], role)
                if icon:
                    params['icon'] = role[:1] + 'j' + icon
                elif role == 'vignette':
                    icon = _getImageExtKey(i['program']['images'], 'totem')
                    if icon:
                        params['icon'] = 'tj' + icon
                params.update({'good_for_fav': True, 'title': title, 'url': i['id'], 'desc': i.get('description', ''), 'other_info': otherInfo})
                if isVideo:
                    self.addVideo(params)
                else:
                    params['category'] = next_category
                    self.addDir(params)
            page += 1
            if page < nbPages and len(self.currList) > 0:
                params = dict(cItem)
                params.update({'title': _("Next page"), 'page': page})
                self.addDir(params)

        except Exception:
            printExc()

    def getLinksForVideo(self, cItem):
        url = cItem['url']
        printDBG("RtlMostHU.getLinksForVideo url[%s]" % url)
        videoUrls = []
        if not self.tryTologin():
            return videoUrls
        sts, data = self.cm.getPage(self.VIDEO_URL.format(url), self.apiParams)

        if not sts:
            return videoUrls
        try:
            data = json_loads(data)
            assets = data['clips'][0].get('assets')
            url = assets[0].get('full_physical_path')
        except Exception:
            printExc()

        uri = urlparser.decorateParamsFromUrl(url)
        protocol = uri.meta.get('iptv_proto', '')
        printDBG("PROTOCOL [%s] " % protocol)
        if protocol == 'm3u8':
            retTab = getDirectM3U8Playlist(uri, checkExt=False, checkContent=True)
            videoUrls.extend(retTab)
        elif protocol == 'f4m':
            retTab = getF4MLinksWithMeta(uri)
            videoUrls.extend(retTab)
        elif protocol == 'mpd':
            retTab = getMPDLinksWithMeta(uri, False)
            videoUrls.extend(retTab)
        else:
            videoUrls.append({'name': 'direct link', 'url': uri})
        return videoUrls

    def getFavouriteData(self, cItem):
        printDBG('RtlMostHU.getFavouriteData')
        params = {'type': cItem['type'], 'category': cItem.get('category', ''), 'title': cItem['title'], 'url': cItem['url'], 'desc': cItem['desc'], 'icon': cItem['icon']}
        if 'subcat' in cItem:
            params['subcat'] = cItem['subcat']
        if 'other_info' in cItem:
            params['other_info'] = cItem['other_info']
        return json_dumps(params)

    def getArticleContent(self, cItem):
        printDBG("RtlMostHU.getArticleContent [%s]" % cItem)
        retTab = {'title': cItem['title'], 'text': cItem['desc'], 'images': [{'title': '', 'url': self.getFullIconUrl(cItem.get('icon'))}]}
        if 'other_info' in cItem:
            retTab['other_info'] = cItem['other_info']
        return [retTab]

    def tryTologin(self):
        printDBG('tryTologin start')

        needLogin = False
        if self.login != config.plugins.iptvplayer.rtlmosthu_login.value or self.password != config.plugins.iptvplayer.rtlmosthu_password.value:
            needLogin = True
            self.login = config.plugins.iptvplayer.rtlmosthu_login.value
            self.password = config.plugins.iptvplayer.rtlmosthu_password.value

        if self.loggedIn and not needLogin:
            return True

        self.loggedIn = False

        if '' == self.login.strip() or '' == self.password.strip():
            printDBG('tryTologin wrong login data')
            self.sessionEx.open(MessageBox, _('The host %s requires registration. \nPlease fill your login and password in the host configuration. Available under blue button.') % self.getMainUrl(), type=MessageBox.TYPE_ERROR, timeout=10)
            return False

        try:
            if os.path.exists(self.COOKIE_FILE):
                cj = self.cm.getCookie(self.COOKIE_FILE)
            else:
                cj = cookielib.MozillaCookieJar()

            cookieNames = ['sessionToken', 'sessionSecret', 'loginHash', 'loginValid']
            cookies = [None, None, None, None]

            for cookie in cj:
                if cookie.domain == 'vpv.jf7ekt7r6rbm2.hu':
                    try:
                        i = cookieNames.index(cookie.name)
                        if cookies[i]:
                            cookie.discard = True
                        else:
                            cookies[i] = cookie
                    except ValueError:
                        cookie.discard = True
            for i, cookie in enumerate(cookies):
                if not cookie:
                    cookie = cookielib.Cookie(version=0, name=cookieNames[i], value=None, port=None, port_specified=False,
                        domain='vpv.jf7ekt7r6rbm2.hu', domain_specified=False, domain_initial_dot=False, path='/', path_specified=True, secure=True,
                        expires=2147483647, discard=False, comment=None, comment_url=None, rest={'HttpOnly': None}, rfc2109=False)
                    cookies[i] = cookie
                    cj.set_cookie(cookie)
            token = cookies[0]
            secret = cookies[1]
            hash = cookies[2]
            valid = cookies[3]
            needLogin = needLogin or not(token.value and secret.value and hash.value
                        and sha1(self.login + self.password + token.value + secret.value).hexdigest() == hash.value)
            if not needLogin:
                if valid.value == '1':
                    self.loggedIn = True
                    return True
                sts, data = self.cm.getPage(self.ACCOUNT_URL.format(token.value, secret.value), self.loginParams)
                if not sts:
                    raise Exception('Can not Get Account page!')
                data = json_loads(data)
                needLogin = data['errorCode'] != 0
            if needLogin:
                sts, data = self.cm.getPage(self.LOGIN_URL.format(self.login, self.password), self.loginParams)
                if not sts:
                    raise Exception('Can not Get Login page!')
                data = json_loads(data)
                if data['errorCode'] != 0:
                    raise Exception(data.get('errorMessage'))
                token.value = data['sessionInfo']['sessionToken']
                secret.value = data['sessionInfo']['sessionSecret']
                hash.value = sha1(self.login + self.password + token.value + secret.value).hexdigest()
            valid.value = '1'
            valid.expires = int(time.time()) + 86400
            cj.save(self.COOKIE_FILE)
            self.loggedIn = True
            return True
        except:
           printExc()
           self.sessionEx.open(MessageBox, _('Login failed.'), type=MessageBox.TYPE_ERROR, timeout=10)
        return False

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []
        if self.tryTologin():
    #MAIN MENU
            if name == None:
                self.listMainMenu({'name': 'category'})
            elif category == 'list_programs':
                self.listPrograms(self.currItem)
            elif category == 'list_subcategories':
                self.listSubcategories(self.currItem)
            elif category == 'list_episodes':
                self.listEpisodes(self.currItem, self.currItem['subcat'])
            elif category == 'list_playlist':
                self.listPlaylist(self.currItem)
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
        CHostBase.__init__(self, RtlMostHU(), True, [])

    def getSearchTypes(self):
        return self.host.SEARCH_TYPES

    def withArticleContent(self, cItem):
        if (cItem['type'] != 'video' and cItem['category'] not in ['list_playlist', 'list_episodes', 'list_subcategories']):
            return False
        return True
