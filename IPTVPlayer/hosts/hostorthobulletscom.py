# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib.request
import urllib.parse
import urllib.error
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
config.plugins.iptvplayer.orthobulletscom_login = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.orthobulletscom_password = ConfigText(default="", fixed_size=False)

def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("login") + ":", config.plugins.iptvplayer.orthobulletscom_login))
    optionList.append(getConfigListEntry(_("password") + ":", config.plugins.iptvplayer.orthobulletscom_password))
    return optionList
###################################################


def gettytul():
    return 'https://orthobullets.com/'

class OrthoBullets(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'orthobullets.com', 'cookie':'orthobullets.com.cookie'})
        
        self.USER_AGENT = 'Mozilla/5.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With':'XMLHttpRequest', 'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8'})
        
        self.MAIN_URL = 'https://www.orthobullets.com/'
        self.DEFAULT_ICON_URL = 'http://pic.accessify.com/thumbnails/777x423/o/orthobullets.com.png'
        
        self.defaultParams = {'header':self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.loggedIn = None
        self.login = ''
        self.password = ''
    
    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        def _getFullUrl(url):
            if self.cm.isValidUrl(url):
                return url
            else:
                return urljoin(baseUrl, url)
        addParams['cloudflare_params'] = {'domain':self.up.getDomain(baseUrl), 'cookie_file':self.COOKIE_FILE, 'User-Agent':self.USER_AGENT, 'full_url_handle':_getFullUrl}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)
    
    def listMainMenu(self, cItem):
        printDBG("OrthoBullets.listMainMenu")

        sts, data = self.getPage(self.getFullUrl('/video/list.aspx'))
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])
        
        reObj = re.compile('''<ul[^>]+?subMenu[^>]*?>''')
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<ul', '>', 'dropList'), ('</ul', '>'))
        printDBG(data)
        for sItem in data:
            sItem = reObj.split(sItem, 1)
            if len(sItem) < 2:
                continue
            sTitle = self.cleanHtmlStr(sItem[0])
            categories = []
            sItem = self.cm.ph.getAllItemsBeetwenMarkers(sItem[1], '<li', '</li>')
            for item in sItem:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
                title = self.cleanHtmlStr(item)
                params = dict(cItem)
                params.update({'name':'category', 'category':'list_sort', 'title':title, 'url':url})
                categories.append(params)
            
            if len(categories):
                params = dict(cItem)
                params.update({'name':'category', 'category':'sub_items', 'title':sTitle, 'sub_items':categories})
                self.addDir(params)

        MAIN_CAT_TAB = [{'category':'search', 'title': _('Search'), 'search_item':True},
                        {'category':'search_history', 'title': _('Search history')}]
        self.listsTab(MAIN_CAT_TAB, cItem)
        
    def listSort(self, cItem, nextCategory):
        printDBG("OrthoBullets.listItems [%s]" % cItem)
        
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])
        
        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'tabNavigation'), ('</div', '>'), False)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            title = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'name':'category', 'category':nextCategory, 'title':title, 'url':url})
            self.addDir(params)
    
    def listItems(self, cItem):
        printDBG("OrthoBullets.listItems [%s]" % cItem)
        page = cItem.get('page', 1)
        
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])
        
        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'dashboardPaging'), ('</div', '>'))[1]
        nextPage = self.cm.ph.getSearchGroups(nextPage, '''<a[^>]+?href=['"]([^'^"]+?)['"][^>]*?>%s</a>''' % (page + 1))[0]
        
        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'videos'), ('<script', '>'), False)[1].split('data-video-id')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0])
            if url == '':
                continue
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''\ssrc=['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h3', '</h3>')[1])
            
            desc = []
            tmp = self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'dashboardItem-right'), ('</div', '>'), False)[1]
            t = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(tmp, '<time', '</time>')[1])
            if t != '':
                desc.append(t)
            t = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(tmp, '<span', '</span>')[1])
            if t != '':
                desc.append(t)
            stars = tmp.count('blank')
            desc.append('%s/%s' % (5 - stars, 5))
            desc = [' | '.join(desc)]
            
            tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<ul', '</ul>')[1])
            if tmp != '':
                desc.append(tmp)
            
            tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<p', '</p>')[1])
            if tmp != '':
                desc.append(tmp)
            
            params = dict(cItem)
            params.update({'good_for_fav':True, 'title':title, 'url':url, 'icon':icon, 'desc':'[/br]'.join(desc)})
            self.addVideo(params)
        
        if nextPage:
            params = dict(cItem)
            params.update({'good_for_fav':False, 'title':_("Next page"), 'page':page + 1, 'url':self.getFullUrl(nextPage)})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("OrthoBullets.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        self.tryTologin()
        
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('/video/list?search=') + urllib.parse.quote(searchPattern) 
        cItem['category'] = 'list_items'
        self.listItems(cItem)

    def getLinksForVideo(self, cItem):
        printDBG("OrthoBullets.getLinksForVideo [%s]" % cItem)
        self.tryTologin()
        
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return []
        self.setMainUrl(self.cm.meta['url'])
        
        url = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0])
        return self.up.getVideoLinkExt(strwithmeta(url, {'Referer':self.cm.meta['url']}))

    def tryTologin(self):
        printDBG('tryTologin start')
        if None == self.loggedIn or self.login != config.plugins.iptvplayer.orthobulletscom_login.value or\
            self.password != config.plugins.iptvplayer.orthobulletscom_password.value:
            
            self.login = config.plugins.iptvplayer.orthobulletscom_login.value
            self.password = config.plugins.iptvplayer.orthobulletscom_password.value
            
            rm(self.COOKIE_FILE)
            
            self.loggedIn = False
            
            if '' == self.login.strip() or '' == self.password.strip():
                self.sessionEx.open(MessageBox, _('The host %s requires registration. \nPlease fill your login and password in the host configuration. Available under blue button.' % self.getMainUrl()), type=MessageBox.TYPE_ERROR, timeout=10)
                return False
            
            sts, data = self.getPage(self.getFullUrl('/login'))
            if not sts:
                return False
            cUrl = self.cm.meta['url']
            
            sts, data = self.cm.ph.getDataBeetwenNodes(data, ('<form', '>'), ('</form', '>'))
            if not sts:
                return False
            actionUrl = self.cm.getFullUrl(self.cm.ph.getSearchGroups(data, '''action=['"]([^'^"]+?)['"]''')[0], self.cm.getBaseUrl(cUrl))
            if actionUrl == '':
                actionUrl = cUrl
            
            post_data = {}
            inputData = self.cm.ph.getAllItemsBeetwenMarkers(data, '<input', '>')
            inputData.extend(self.cm.ph.getAllItemsBeetwenMarkers(data, '<button', '>'))
            for item in inputData:
                name = self.cm.ph.getSearchGroups(item, '''name=['"]([^'^"]+?)['"]''')[0]
                value = self.cm.ph.getSearchGroups(item, '''value=['"]([^'^"]+?)['"]''')[0].replace('&amp;', '&')
                post_data[name] = value
            
            post_data.update({'Username':self.login, 'Password':self.password})
            
            httpParams = dict(self.defaultParams)
            httpParams['header'] = dict(httpParams['header'])
            httpParams['header']['Referer'] = cUrl
            sts, data = self.cm.getPage(actionUrl, httpParams, post_data)
            if sts:
                cUrl = self.cm.meta['url']
                sts, data = self.cm.ph.getDataBeetwenNodes(data, ('<form', '>'), ('</form', '>'))
                if not sts:
                    return False
                actionUrl = self.cm.getFullUrl(self.cm.ph.getSearchGroups(data, '''action=['"]([^'^"]+?)['"]''')[0], self.cm.getBaseUrl(cUrl))
                if actionUrl == '':
                    actionUrl = cUrl
                
                post_data = {}
                inputData = self.cm.ph.getAllItemsBeetwenMarkers(data, '<input', '>')
                inputData.extend(self.cm.ph.getAllItemsBeetwenMarkers(data, '<button', '>'))
                for item in inputData:
                    name = self.cm.ph.getSearchGroups(item, '''name=['"]([^'^"]+?)['"]''')[0]
                    value = self.cm.ph.getSearchGroups(item, '''value=['"]([^'^"]+?)['"]''')[0].replace('&amp;', '&')
                    post_data[name] = value
                
                httpParams['header']['Referer'] = cUrl
                sts, data = self.cm.getPage(actionUrl, httpParams, post_data)
                if sts and '/logout' in data and self.cm.getBaseUrl(self.getMainUrl(), True) in self.cm.getBaseUrl(self.cm.meta['url'], True):
                    printDBG('tryTologin OK')
                    self.loggedIn = True
            
            if not self.loggedIn:
                self.sessionEx.open(MessageBox, _('Login failed.'), type=MessageBox.TYPE_ERROR, timeout=10)
                printDBG('tryTologin failed')
        return self.loggedIn
    
    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')
        
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        self.tryTologin()

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')
        
        printDBG("handleService: || name[%s], category[%s] " % (name, category))
        self.currList = []
        
    #MAIN MENU
        if name == None:
            self.listMainMenu({'name':'category', 'type':'category'})
        elif category == 'list_sort':
            self.listSort(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem)
        elif category == 'sub_items':
            self.currList = self.currItem.get('sub_items', [])
    #SEARCH
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item':False, 'name':'category'}) 
            self.listSearchResult(cItem, searchPattern, searchType)
    #HISTORIA SEARCH
        elif category == "search_history":
            self.listsHistory({'name':'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()
        
        CBaseHostClass.endHandleService(self, index, refresh)

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, OrthoBullets(), True, favouriteTypes=[]) 

