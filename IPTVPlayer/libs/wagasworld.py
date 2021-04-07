# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify, GetCookieDir
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs import ph
###################################################

###################################################
# FOREIGN import
###################################################
from time import time
import re
from os import path as os_path
############################################

###################################################
# E2 GUI COMMPONENTS 
###################################################
from Components.config import config, ConfigText, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.asynccall import MainSessionWrapper
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass
from Screens.MessageBox import MessageBox
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.wagasworld_login = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.wagasworld_password = ConfigText(default="", fixed_size=False)

def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry('wagasworld.com ' + _("login") + ':', config.plugins.iptvplayer.wagasworld_login))
    optionList.append(getConfigListEntry('wagasworld.com ' + _("password") + ':', config.plugins.iptvplayer.wagasworld_password))
    return optionList
    
###################################################


class WagasWorldApi(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self)
        self.sessionEx = MainSessionWrapper()
        self.MAIN_URL = 'http://www.wagasworld.com/'
        self.HTTP_HEADER = {'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux i686; rv:12.0) Gecko/20100101 Firefox/12.0', 'Referer': self.MAIN_URL}
        self.COOKIE_FILE = GetCookieDir('wagasworld.cookie')
        self.http_params = {'header': dict(self.HTTP_HEADER), 'save_cookie': True, 'load_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.DEFAULT_URL_ICON = self.getFullIconUrl('/sites/default/files/styles/slideshow_full/public/12_0.jpg?itok=LHobtpyX')

    def getMainCategories(self, cItem):
        printDBG("WagasWorldApi.getMainCategories")
        list = []
        list.append({'type': 'waga_cat', 'waga_cat': 'groups', 'title': _('Channel'), 'url': self.MAIN_URL + 'channel'})
        list.append({'type': 'waga_cat', 'waga_cat': 'groups', 'title': _('LiveTv'), 'url': self.MAIN_URL + 'LiveTv'})
        return list

    def getGroups(self, cItem):
        printDBG("WagasWorldApi.getGroups")
        list = []
        sts, data = self.cm.getPage(cItem['url'], self.http_params)
        if not sts:
            return list
        data = ph.find(data, ('<div', '>', 'form-item'), '<select', flags=0)[1]
        data = re.compile('<a[^>]+?href="([^"]+?)"[^>]*?>([^<]+?)</a>').findall(data)
        for item in data:
            list.append({'type': 'waga_cat', 'waga_cat': 'items', 'title': ph.clean_html(item[1]), 'icon': self.DEFAULT_URL_ICON, 'url': self.getFullUrl(item[0])})
        return list

    def getItems(self, cItem):
        printDBG("WagasWorldApi.getItems")
        list = []
        page = cItem.get('page', 0)
        url = cItem['url']
        if page > 0:
            if '?' in url:
                url += '&'
            else:
                url += '?'
            url += 'page={0}'.format(page)
        sts, data = self.cm.getPage(url, self.http_params)
        if not sts:
            return list
        
        nextPage = False
        if '&amp;page={0}"'.format(page + 1) in data:
            nextPage = True
        data = ph.find(data, '<div class="view-content">', '</section>')[1]
        data = data.split('</span>')
        if len(data):
            del data[-1]
        for item in data:
            title = ph.search(item, '>([^<]+?)</a>')[0]
            url = self.getFullUrl(ph.getattr(item, 'href'))
            icon = self.getFullIconUrl(ph.search(item, ph.IMG)[1])
            if '' != url and '' != title:
                list.append({'waga_cat': 'explore', 'type': 'waga_cat', 'title': ph.clean_html(title), 'icon': icon, 'url': url})
        if nextPage:
            list.append({'type': 'waga_cat', 'waga_cat': 'items', 'title': _('Next page'), 'url': cItem['url'], 'page': page + 1})
        return list
        
    def getChannelsList(self, cItem):
        printDBG("WagasWorldApi.getChannelsList waga_cat[%s]" % cItem.get('waga_cat', ''))
        list = []
        waga_cat = cItem.get('waga_cat', '')
        if '' == waga_cat:
            login = config.plugins.iptvplayer.wagasworld_login.value
            password = config.plugins.iptvplayer.wagasworld_password.value
            if login != '' and password != '':        
                if self.doLogin(login, password):
                    self.loggedIn = True
                    self.http_params.update({'save_cookie': True, 'load_cookie': True, 'cookiefile': self.COOKIE_FILE})
                else:
                    self.sessionEx.open(MessageBox, _('"%s" login failed! Please check your login and password.') % login, type=MessageBox.TYPE_INFO, timeout=10)
        
            list = self.getGroups({'url': self.MAIN_URL + 'channel'})
            #list = self.getMainCategories(cItem)
        elif 'groups' == waga_cat:
            list = self.getGroups(cItem)
        elif 'items' == waga_cat:
            list = self.getItems(cItem)
        elif 'explore' == waga_cat:
            list = self.exploreItem(cItem)
        elif 'more' == waga_cat:
            list = self.loadMore(cItem)
        return list
        
    def _getEpisode(self, baseUrl, episode=-1):
        tmp = baseUrl.split('/')
        url = '/'.join(tmp[:-2]) + '/x.php?%s=%s&' % (tmp[-2], tmp[-1])
        
        if episode > -1:
            url += 'episode=%s&' % episode
        
        url += 'v=%s' % (int(time() * 1000))
        
        HTTP_HEADER = dict(self.HTTP_HEADER)
        HTTP_HEADER['Referer'] = baseUrl
        HTTP_HEADER['X-Requested-With'] = 'XMLHttpRequest'
        sts, data = self.cm.getPage(url, {'header': HTTP_HEADER})
        if not sts:
            return []
        
        ret = None
        errorMsg = ''
        try:
            data = json_loads(data)
            errorMsg = self.cleanHtmlStr(data.get('err', ''))
            ret = {'url': data['url'], 'episode': data['episode'], 'title': data['name']}
        except Exception:
            printExc()
            if errorMsg != '':
                self.sessionEx.open(MessageBox, errorMsg, type=MessageBox.TYPE_ERROR, timeout=10)
        return ret

    def exploreItem(self, cItem):
        printDBG("WagasWorldApi.exploreItem url[%s]" % cItem['url'])
        sts, data = self.cm.getPage(cItem['url'], self.http_params)
        if not sts:
            return []

        desc = ph.clean_html(ph.find(data, ('<div', '>', 'alert-danger'), '</div>', flags=0)[1])
        data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="videoWrapper">', ' </section>', False)[1]
        if 'pr3v4t.tk' not in data:
            params = dict(cItem)
            params['type'] = 'video'
            params['desc'] = desc
            return [params]

        retTab = [] 
        url = self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=["'](https?://[^"^']*?pr3v4t\.tk[^"^']+)["']''', 1, True)[0]
        data = self._getEpisode(url)
        if data:
            params = dict(cItem)
            params.update({'type': 'video', 'title': cItem['title'] + ' ' + data['title'], 'waga_url': url, 'waga_episode': int(data['episode'])})
            retTab.append(params)

            params = dict(cItem)
            params.update({'type': 'more', 'waga_cat': 'more', 'title': _('More'), 'waga_title': cItem['title'], 'waga_url': url, 'waga_episode': int(data['episode']) + 1})
            retTab.append(params)
        return retTab

    def loadMore(self, cItem):
        printDBG("WagasWorldApi.loadMore cItem[%s]" % cItem)
        
        episode = cItem.get('waga_episode', 1)
        baseUrl = cItem.get('waga_url', '')
        title = cItem.get('waga_title', '')
        
        retTab = [] 
        data = self._getEpisode(baseUrl, episode)
        if data:
            params = dict(cItem)
            params.update({'type': 'video', 'title': title + ' ' + data['title'], 'waga_url': baseUrl, 'waga_episode': int(data['episode'])})
            retTab.append(params)
            
            params = dict(cItem)
            params.update({'waga_episode': int(data['episode']) + 1})
            retTab.append(params)
        
        return retTab
    
    def getVideoLink(self, cItem):
        printDBG("WagasWorldApi.getVideoLink cItem[%s]" % cItem)
        baseUrl = cItem['url']
        url = cItem.get('waga_url', '')
        
        if url != '':
            data = self._getEpisode(url, cItem.get('waga_episode', 1))
            if data:
                return [{'name': data['title'], 'url':data['url']}]
        else:
            sts, data = self.cm.getPage(baseUrl, self.http_params)
            if not sts:
                return []
            data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="videoWrapper">', '</section>', False)[1]
            return self.up.getAutoDetectedStreamLink(baseUrl, data)
        return []
        
    def doLogin(self, login, password):
        logged = False
        loginUrl = self.MAIN_URL + '?q=user'
        
        params = dict(self.http_params)
        params['load_cookie'] = False
        sts, data = self.cm.getPage(loginUrl, params)
        if not sts:
            return False
        
        data = self.cm.ph.getDataBeetwenMarkers(data, '<form', '</form>', False, False)[1]
        action = self.cm.ph.getSearchGroups(data, '''action=['"]([^'^"]+?)['"]''')[0]
        if action.startswith('/'):
            action = self.MAIN_URL + action[1:]
        
        printDBG(data)
        post_data = dict(re.findall(r'<(?:input|button)[^>]*name="([^"]*)"[^>]*value="([^"]*)"[^>]*>', data))
        post_data.update({'name': login, 'pass': password})
        
        HTTP_HEADER = dict(self.HTTP_HEADER)
        HTTP_HEADER.update({'Referer': loginUrl})
        
        params = {'header': HTTP_HEADER, 'cookiefile': self.COOKIE_FILE, 'save_cookie': True, 'load_cookie': True}
        sts, data = self.cm.getPage(loginUrl, params, post_data)
        if sts:
            if os_path.isfile(self.COOKIE_FILE):
                if 'user/logout' in data:
                    printDBG('WagasWorldApi.doLogin login as [%s]' % login)
                    logged = True
                else:
                    printDBG('WagasWorldApi.doLogin login failed - wrong user or password?')
            else:
                printDBG('WagasWorldApi.doLogin there is no cookie file after login')
        return logged
