# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, GetCookieDir, MergeDicts, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass
###################################################

###################################################
# FOREIGN import
###################################################
from Components.config import config, ConfigText, getConfigListEntry
############################################

###################################################
# E2 GUI COMMPONENTS 
###################################################
from Screens.MessageBox import MessageBox
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.internetowa_login = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.internetowa_password = ConfigText(default="", fixed_size=False)

def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry('internetowa.ws ' + _("email") + ':', config.plugins.iptvplayer.internetowa_login))
    optionList.append(getConfigListEntry('internetowa.ws ' + _("password") + ':', config.plugins.iptvplayer.internetowa_password))
    return optionList
    
###################################################

class InternetowaApi(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self)
        self.MAIN_URL = 'https://internetowa.ws/'
        self.DEFAULT_ICON_URL = self.getFullIconUrl('/img/internetowa-logo-new-3.png')
        self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')

        self.COOKIE_FILE = GetCookieDir('internetowa.ws.cookie')

        self.http_params = {}
        self.http_params.update({'header': self.HTTP_HEADER, 'save_cookie': True, 'load_cookie': True, 'cookiefile': self.COOKIE_FILE})
        self.loggedIn = False
        self.login = None
        self.password = None

    def tryTologin(self):
        printDBG('tryTologin start')
        
        if None == self.loggedIn or self.login != config.plugins.iptvplayer.internetowa_login.value or\
            self.password != config.plugins.iptvplayer.internetowa_password.value:

            rm(self.COOKIE_FILE)

            self.login = config.plugins.iptvplayer.internetowa_login.value
            self.password = config.plugins.iptvplayer.internetowa_password.value

            rm(self.COOKIE_FILE)
            sts, data = self.cm.getPage(self.getFullUrl('/logowanie/'), self.http_params)
            if sts:
                self.setMainUrl(self.cm.meta['url'])

            self.loggedIn = False
            if '' == self.login.strip() or '' == self.password.strip():
                return False

            if sts:
                params = dict(self.http_params)
                params['header'] = MergeDicts(self.HTTP_HEADER, {'Referer': self.getFullUrl('/logowanie/')})

                post_data = {'email': self.login, 'password': self.password}
                sts, data = self.cm.getPage(self.getFullUrl('/logowanie/'), params, post_data)

            if sts and '/wyloguj' in data:
                printDBG('tryTologin OK')
                self.loggedIn = True
            else:
                msgTab = [_('Login failed.')]
                if sts:
                    msgTab.append(self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'errorBox'), ('</div', '>'), False)[1]))
                self.sessionEx.waitForFinishOpen(MessageBox, '\n'.join(msgTab), type=MessageBox.TYPE_ERROR, timeout=10)
                printDBG('tryTologin failed')
        return self.loggedIn
    
    def getList(self, cItem):
        printDBG("InternetowaApi.getChannelsList")
        self.tryTologin()

        channelsTab = []
        
        if cItem.get('priv_cat') == None:
            sts, data = self.cm.getPage(self.getMainUrl(), self.http_params)
            if not sts:
                return []

            sectionsTitles = {}
            tmp = self.cm.ph.getDataBeetwenNodes(data, ('<select', '>', 'switchView'), ('</select', '>'), False)[1]
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<option', '</option>')
            for item in tmp:
                marker = self.cm.ph.getSearchGroups(item, '''value=['"]([^"^']+?)['"]''')[0]
                sectionsTitles[marker] = self.cleanHtmlStr(item)

            data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'channelbiggrid'), ('<style', '>'))[1]
            data = self.cm.ph.rgetAllItemsBeetwenNodes(data, ('</div', '>'), ('<div', '>', 'channelbiggrid'))
            for section in data:
                tmp = self.cm.ph.getSearchGroups(section, '''<div[^>]+?id=['"]([^'^"]+?)home['"]''')[0]
                sTitle = sectionsTitles.get(tmp, tmp.upper())
                subItems = []
                section = section.split('</h2>')

                for idx in range(1, len(section), 2):
                    sTitle2 = self.cleanHtmlStr(section[idx - 1])
                    subItems2 = []
                    subSections = self.cm.ph.getAllItemsBeetwenMarkers(section[idx], '<a', '</a>')
                    for item in subSections:
                        url = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
                        if not self.cm.isValidUrl(url):
                            continue
                        title = self.cleanHtmlStr(item)
                        if title == '':
                            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''title=['"]([^'^"]+?)['"]''')[0])
                        icon = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''')[0])
                        type = title.lower()
                        type = 'audio' if 'radio' in type or 'rmf ' in type else 'video'
                        subItems2.append(MergeDicts(cItem, {'type': type, 'title': title, 'url': url, 'icon': icon}))
                    if len(subItems2):
                        subItems.append(MergeDicts(cItem, {'priv_cat': 'sub_items', 'title': sTitle2, 'sub_items': subItems2}))
                if len(subItems) == 1:
                    channelsTab.append(subItems[0])
                elif len(subItems):
                    channelsTab.append(MergeDicts(cItem, {'priv_cat': 'sub_items', 'title': sTitle, 'sub_items': subItems}))
        else:
            channelsTab = cItem['sub_items']
        return channelsTab
        
    def getVideoLink(self, cItem):
        printDBG("InternetowaApi.getVideoLink")
        urlsTab = []

        sts, data = self.cm.getPage(cItem['url'], self.http_params)
        if not sts:
            return urlsTab
        cUrl = self.cm.meta['url']

        SetIPTVPlayerLastHostError(self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'nostream'), ('</div', '>'), False)[1]))

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<iframe', '>', caseSensitive=False)
        printDBG(data)
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0])
            if not self.cm.isValidUrl(url):
                continue
            if 1 == self.up.checkHostSupport(url):
                url = strwithmeta(url, {'Referer': cUrl})
                urlsTab.extend(self.up.getVideoLinkExt(url))
            else:
                params = dict(self.http_params)
                params['header'] = MergeDicts(self.HTTP_HEADER, {'Referer': cUrl})
                sts, tmp = self.cm.getPage(url, params)
                if not sts:
                    continue
                tmp2 = self.cm.ph.getDataBeetwenMarkers(tmp, '<audio', '</audio>', False)[1]
                tmp2 = self.cm.ph.getDataBeetwenMarkers(tmp, '<audio', '</audio>', False)[1]
                tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp2, '<source', '>')
                for it in tmp:
                    printDBG(it)
                    type = self.cm.ph.getSearchGroups(it, '''type=['"]([^"^']+?)['"]''')[0].lower().split('/', 1)
                    mediaUrl = self.cm.getFullUrl(self.cm.ph.getSearchGroups(it, '''src=['"]([^"^']+?)['"]''')[0], self.cm.meta['url'])
                    if type[0] in ('audio', 'video'):
                        mediaUrl = strwithmeta(mediaUrl, {'User-Agent': params['header']['User-Agent'], 'Referer': self.cm.meta['url']})
                        urlsTab.append({'name': '[%s] %s' % (type[1], self.cm.getBaseUrl(url, True)), 'url': mediaUrl, 'need_resolve': 0})
        return urlsTab
