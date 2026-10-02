# -*- coding: utf-8 -*-
# titulky.com: Czech / Slovak subtitles. The search is public; downloads work anonymously until
# the daily limit of the IP is reached, then the site asks for a captcha. A logged-in user gets
# a higher limit (premium accounts have no countdown).
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.isubprovider import CSubProviderBase, CBaseSubProviderClass
from Plugins.Extensions.IPTVPlayer.libs.subtitlesmatch import yearMatch, sortByRelease
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, GetDefaultLang, GetTmpDir, rm
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_urlencode

###################################################
# FOREIGN import
###################################################
import re
import time
from Components.config import config

###################################################
# E2 GUI COMMPONENTS
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvmultipleinputbox import IPTVMultipleInputBox

###################################################
# Config options for HOST (titulky_login / titulky_password are defined in iptvconfig.py)
###################################################


def GetConfigList():
    optionList = []
    return optionList
###################################################


SITE_LANGS = {'CZ': 'cs', 'SK': 'sk'}


class TitulkyProvider(CBaseSubProviderClass):

    def __init__(self, params={}):
        params['cookie'] = 'titulky.cookie'
        CBaseSubProviderClass.__init__(self, params)

        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'Referer': self.getMainUrl(), 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Encoding': 'gzip, deflate'}
        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.loggedIn = None

    def getMainUrl(self):
        return 'https://www.titulky.com/'

    def getMaxFileSize(self):
        return 1024 * 1024 * 10

    def getLanguages(self):
        lang = GetDefaultLang()
        return [lang, 'sk' if lang == 'cs' else 'cs'] if lang in ('cs', 'sk') else ['cs', 'sk']

    def getSearchList(self, cItem, nextCategory):
        printDBG("TitulkyProvider.getSearchList")
        title, year, season, episode = self.wantedInfo()
        tag = 'S%02dE%02d' % (int(season), int(episode)) if season and episode else ''
        # "<localized title> (<title>)" -> the first one
        title = title.split('(')[0].strip() or title
        query = ('%s %s' % (title, tag)) if tag else title
        sts, data = self.cm.getPage(self.getMainUrl() + '?' + urllib_urlencode({'Fulltext': query, 'FindUser': ''}), self.defaultParams)
        if not sts:
            return
        langs = self.getLanguages()
        items = []
        for row in re.findall(r'<tr class="r[^"]*">(.*?)</tr>', data, re.S | re.I):
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.S | re.I)
            if len(cells) < 6:
                continue
            subId = self.cm.ph.getSearchGroups(cells[0], r'''href="[^"]*?-(\d+)\.htm"''')[0]
            lang = SITE_LANGS.get(self.cm.ph.getSearchGroups(cells[5], r'''alt="(\w+)"''')[0].upper())
            if not subId or lang not in langs:
                continue
            name = self.cleanHtmlStr(cells[0])
            release = self.cleanHtmlStr(self.cm.ph.getSearchGroups(cells[1], r'''title="([^"]*)"''')[0])
            foundEpisode = self.cleanHtmlStr(cells[2])
            foundYear = self.cleanHtmlStr(cells[3])
            downloads = self.cleanHtmlStr(cells[4])
            if tag and foundEpisode.upper() != tag or not tag and not yearMatch(foundYear, year):
                continue
            if foundEpisode.upper() in name.upper():
                foundEpisode = ''
            label = ' '.join(x for x in (name, foundEpisode, '(%s)' % foundYear if foundYear else '') if x)
            desc = [label]
            if release:
                label = '%s - %s' % (label, release)
            if downloads:
                desc.append(_('Downloads: %s') % downloads)
            params = dict(cItem)
            params.update({'category': nextCategory, 'title': '[%s] %s' % (lang, label), 'lang': lang, 'sub_id': subId, 'release': '%s %s' % (name, release),
                           'downloads': int(downloads) if downloads.isdigit() else 0, 'desc': '[/br]'.join(desc)})
            items.append(params)
        items.sort(key=lambda x: (langs.index(x['lang']), -x['downloads']))
        for lang in langs:
            for params in sortByRelease([x for x in items if x['lang'] == lang], self.releaseName(), 'release'):
                self.addDir(params)

    def doLogin(self):
        if self.loggedIn is not None:
            return self.loggedIn
        self.loggedIn = False
        login = config.plugins.iptvplayer.titulky_login.value.strip()
        password = config.plugins.iptvplayer.titulky_password.value
        rm(self.COOKIE_FILE)
        if not login or not password:
            return False
        sts, data = self.cm.getPage(self.getFullUrl('/index.php'), self.defaultParams, {'Login': login, 'Password': password, 'foreverlog': '0', 'Detail2': ''})
        if sts and 'BadLogin' not in data and self.cm.getCookieItem(self.COOKIE_FILE, 'LogonLogin'):
            self.loggedIn = True
        else:
            SetIPTVPlayerLastHostError(_('Failed to log in user "%s". Please check your login and password.') % login)
        return self.loggedIn

    def solveCaptcha(self, subId):
        printDBG("TitulkyProvider.solveCaptcha")
        # with the session cookie: the code belongs to the session that posts it
        sts, data = self.downloadBinary(self.getFullUrl('/captcha/captcha.php'), self.defaultParams)
        if not sts or not data:
            SetIPTVPlayerLastHostError(_('Fail to get captcha data.'))
            return ''
        filePath = GetTmpDir('.iptvplayer_captcha.jpg')
        if not self.writeFile(filePath, data):
            return ''
        params = dict(IPTVMultipleInputBox.DEF_PARAMS)
        params.update({'title': _('Daily download limit reached - type the code'), 'accep_label': _('Send'), 'list': []})
        item = dict(IPTVMultipleInputBox.DEF_INPUT_PARAMS)
        item.update({'label_size': (400, 100), 'input_size': (400, 25), 'icon_path': filePath, 'title': _('Answer')})
        item['input'] = dict(item.get('input') or {}, text='')
        params['list'].append(item)
        # the callback arguments of the input box: (['<text>'],), (None,) when it was closed
        retArg = self.sessionEx.waitForFinishOpen(IPTVMultipleInputBox, params)
        printDBG(retArg)
        code = retArg[0][0].strip() if retArg and retArg[0] else ''
        if not code:
            SetIPTVPlayerLastHostError(_('Captcha was not entered.'))
            return ''
        post_data = {'downkod': code, 'securedown': '2', 'zip': 'z', 'T': '', 'titulky': subId, 'histstamp': ''}
        sts, data = self.cm.getPage(self.getFullUrl('/idown.php'), self.defaultParams, post_data)
        if not sts:
            return ''
        if 'captcha/captcha.php' in data:
            SetIPTVPlayerLastHostError(_('Wrong captcha code.'))
            return ''
        return data

    def getLink(self, cItem, nextCategory):
        printDBG("TitulkyProvider.getLink")
        subId = cItem['sub_id']
        self.doLogin()
        url = self.getFullUrl('/idown.php?') + urllib_urlencode({'R': str(int(time.time())), 'titulky': subId, 'histstamp': '', 'zip': 'z'})
        sts, data = self.cm.getPage(url, self.defaultParams)
        if not sts:
            return
        if 'captcha/captcha.php' in data:
            data = self.solveCaptcha(subId)
            if not data:
                return
        if 'CHYBA' in data:
            SetIPTVPlayerLastHostError(_('%s refused the download. Please set your login and password in the configuration.') % 'Titulky.com')
            return
        link = self.cm.ph.getSearchGroups(data, r'''id="downlink"\s+href="([^"]+)"''')[0] or self.cm.ph.getSearchGroups(data, r'''href="([^"]+)"[^>]*id="downlink"''')[0]
        if not link:
            SetIPTVPlayerLastHostError(_('Failed to get the download link.'))
            return
        wait = int(self.cm.ph.getSearchGroups(data, r'''CountDown\((\d+)\)''')[0] or 0)
        params = dict(cItem)
        params.update({'category': nextCategory, 'link': self.getFullUrl(self.cleanHtmlStr(link)), 'ready_at': time.time() + wait})
        if wait:
            # the link works only after the countdown of the site
            params.update({'title': _('Download (ready in %d seconds)') % wait})
            self.addDir(params)
        else:
            self.getFilesList(params)

    def getFilesList(self, cItem):
        printDBG("TitulkyProvider.getFilesList")
        wait = int(cItem.get('ready_at', 0) - time.time() + 0.99)
        if wait > 0:
            SetIPTVPlayerLastHostError(_('The download is ready in %d seconds. Please try again then.') % wait)
            return
        data = self.downloadFileData(cItem['link'], self.defaultParams)[0]
        if not data:
            SetIPTVPlayerLastHostError(_('Failed to download the subtitles.'))
            return
        # not downloadArchive: before the countdown is over the link gives a page ("<h2>Odkaz ještě není
        # funkční</h2>") and the user should hear "not ready yet", not "no subtitle file"
        ext = self._archiveType(data)
        if not ext:
            SetIPTVPlayerLastHostError(_('The download is not ready yet. Please try again in a few seconds.'))
            return
        tmpArchFile = GetTmpDir(self.TMP_FILE_NAME) + '.' + ext
        tmpDIR = GetTmpDir(self.TMP_DIR_NAME)
        ok = self.writeFile(tmpArchFile, data) and self.unpackArchive(tmpArchFile, tmpDIR)
        rm(tmpArchFile)
        if not ok:
            return
        cItem = dict(cItem)
        cItem.update({'category': '', 'path': tmpDIR, 'imdbid': ''})
        self.listSupportedFilesFromPath(cItem, self.getSupportedFormats(all=True))

    def handleService(self, index, refresh=0):
        printDBG('handleService start')

        CBaseSubProviderClass.handleService(self, index, refresh)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

        if name is None:
            self.getSearchList({'name': 'category'}, 'get_link')
        elif category == 'get_link':
            self.getLink(self.currItem, 'get_files')
        elif category == 'get_files':
            self.getFilesList(self.currItem)

        CBaseSubProviderClass.endHandleService(self, index, refresh)


class IPTVSubProvider(CSubProviderBase):

    def __init__(self, params={}):
        CSubProviderBase.__init__(self, TitulkyProvider(params))
