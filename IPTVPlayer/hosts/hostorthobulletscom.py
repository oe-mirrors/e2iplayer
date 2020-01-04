# -*- coding: utf-8 -*-
# Codermik (codermik@tuta.io)

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs import ph
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib
try:    import json
except Exception: import simplejson as json
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
config.plugins.iptvplayer.orthobulletscom_login    = ConfigText(default = "", fixed_size = False)
config.plugins.iptvplayer.orthobulletscom_password = ConfigText(default = "", fixed_size = False)

def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("login")+":",    config.plugins.iptvplayer.orthobulletscom_login))
    optionList.append(getConfigListEntry(_("password")+":", config.plugins.iptvplayer.orthobulletscom_password))
    return optionList
###################################################


def gettytul():
    return 'https://orthobullets.com/'

class OrthoBullets(CBaseHostClass):

    def __init__(self):
        printDBG("..:: E2iStream ::..   __init__(self):")
        CBaseHostClass.__init__(self, {'history':'orthobullets.com', 'cookie':'orthobullets.com.cookie'})
        
        self.USER_AGENT = 'Mozilla/5.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update( {'X-Requested-With':'XMLHttpRequest', 'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8'} )
        
        self.MAIN_URL = 'https://www.orthobullets.com/'
        self.DEFAULT_ICON_URL = 'http://pic.accessify.com/thumbnails/777x423/o/orthobullets.com.png'
        
        self.defaultParams = {'header':self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.loggedIn = None
        self.login    = ''
        self.password = ''
             
        self.MAIN_CAT_TAB =     [
                                    {'category':'categories',           'title': _('Categories'),       'url':self.MAIN_URL, 'icon':self.DEFAULT_ICON_URL},
                                    {'category':'subspeciality',        'title': _('Subspecialities'),    'url':self.MAIN_URL, 'icon':self.DEFAULT_ICON_URL},
                                    {'category':'search',           'title': _('Search'), 'search_item':True},
                                    {'category':'search_history',   'title': _('Search history')} 
                                ]



        self.CATEGORIES_TAB =   [
                                    {'category':'list_categories',  'title': _('All'), 'url':self.MAIN_URL + 'video/list.aspx'},
                                    {'category':'list_categories',  'title': _('Board Review'), 'url':self.MAIN_URL + 'video/list.aspx?c=7'},
                                    {'category':'list_categories',  'title': _('CME SAE'), 'url':self.MAIN_URL + 'video/list.aspx?c=20'},
                                    {'category':'list_categories',  'title': _('Educational Animation'), 'url':self.MAIN_URL + 'video/list.aspx?c=109'},
                                    {'category':'list_categories',  'title': _('Ethical & Legal'), 'url':self.MAIN_URL + 'video/list.aspx?c=10'},
                                    {'category':'list_categories',  'title': _('Exam Review'), 'url':self.MAIN_URL + 'video/list.aspx?c=19'},
                                    {'category':'list_categories',  'title': _('Humanitarian'), 'url':self.MAIN_URL + 'video/list.aspx?c=8'},
                                    {'category':'list_categories',  'title': _('Industry'), 'url':self.MAIN_URL + 'video/list.aspx?c=107'},
                                    {'category':'list_categories',  'title': _('Interactive Learning Center(ILC)'), 'url':self.MAIN_URL + 'video/list.aspx?c=17'},
                                    {'category':'list_categories',  'title': _('Jobs & Positions'), 'url':self.MAIN_URL + 'video/list.aspx?c=14'},
                                    {'category':'list_categories',  'title': _('Journal Club'), 'url':self.MAIN_URL + 'video/list.aspx?c=9'},
                                    {'category':'list_categories',  'title': _('Medtryx Marketing'), 'url':self.MAIN_URL + 'video/list.aspx?c=24'},
                                    {'category':'list_categories',  'title': _('Meetings'), 'url':self.MAIN_URL + 'video/list.aspx?c=12'},
                                    {'category':'list_categories',  'title': _('Pathology Rounds'), 'url':self.MAIN_URL + 'video/list.aspx?c=16'},
                                    {'category':'list_categories',  'title': _('Physical Exam'), 'url':self.MAIN_URL + 'video/list.aspx?c=5'},
                                    {'category':'list_categories',  'title': _('Powerpoint Presentation'), 'url':self.MAIN_URL + 'video/list.aspx?c=108'},
                                    {'category':'list_categories',  'title': _('Practice Management'), 'url':self.MAIN_URL + 'video/list.aspx?c=11'},
                                    {'category':'list_categories',  'title': _('Professional Networks'), 'url':self.MAIN_URL + 'video/list.aspx?c=13'},
                                    {'category':'list_categories',  'title': _('Radiology Rounds'), 'url':self.MAIN_URL + 'video/list.aspx?c=15'},
                                    {'category':'list_categories',  'title': _('Study Plan'), 'url':self.MAIN_URL + 'video/list.aspx?c=21'},
                                    {'category':'list_categories',  'title': _('Surgical Approaches'), 'url':self.MAIN_URL + 'video/list.aspx?c=3'},
                                    {'category':'list_categories',  'title': _('Surgical Cases'), 'url':self.MAIN_URL + 'video/list.aspx?c=100'},
                                    {'category':'list_categories',  'title': _('Surgical Complications'), 'url':self.MAIN_URL + 'video/list.aspx?c=4'},
                                    {'category':'list_categories',  'title': _('Surgical Techniques'), 'url':self.MAIN_URL + 'video/list.aspx?c=2'},
                                    {'category':'list_categories',  'title': _('Techniques'), 'url':self.MAIN_URL + 'video/list.aspx?c=106'},
                                    {'category':'list_categories',  'title': _('Treatment Consult'), 'url':self.MAIN_URL + 'video/list.aspx?c=1'},
                                    {'category':'list_categories',  'title': _('Written Boards Review'), 'url':self.MAIN_URL + 'video/list.aspx?c=102'}
                                ]

        self.SPECIALITY_TAB =   [
                                    {'category':'list_speciality',  'title': _('Trauma'), 'url':self.MAIN_URL + 'video/list.aspx?s=1'},
                                    {'category':'list_speciality',  'title': _('Spine'), 'url':self.MAIN_URL + 'video/list.aspx?s=2'},
                                    {'category':'list_speciality',  'title': _('Shoulder & Elbow'), 'url':self.MAIN_URL + 'video/list.aspx?s=3'},
                                    {'category':'list_speciality',  'title': _('Knee & Sports'), 'url':self.MAIN_URL + 'video/list.aspx?s=225'},
                                    {'category':'list_speciality',  'title': _('Pediatrics'), 'url':self.MAIN_URL + 'video/list.aspx?s=4'},
                                    {'category':'list_speciality',  'title': _('Recon'), 'url':self.MAIN_URL + 'video/list.aspx?s=5'},
                                    {'category':'list_speciality',  'title': _('Hand'), 'url':self.MAIN_URL + 'video/list.aspx?s=6'},
                                    {'category':'list_speciality',  'title': _('Foot & Ankle'), 'url':self.MAIN_URL + 'video/list.aspx?s=7'},
                                    {'category':'list_speciality',  'title': _('Pathology'), 'url':self.MAIN_URL + 'video/list.aspx?s=8'},
                                    {'category':'list_speciality',  'title': _('Basic Science'), 'url':self.MAIN_URL + 'video/list.aspx?s=9'},
                                    {'category':'list_speciality',  'title': _('Anatomy'), 'url':self.MAIN_URL + 'video/list.aspx?s=10'},
                                    {'category':'list_speciality',  'title': _('Approaches'), 'url':self.MAIN_URL + 'video/list.aspx?s=12'},
                                    {'category':'list_speciality',  'title': _('General'), 'url':self.MAIN_URL + 'video/list.aspx?s=13'},
                                ]
        
    def getPage(self, baseUrl, addParams = {}, post_data = None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        def _getFullUrl(url):
            if self.cm.isValidUrl(url):
                return url
            else:
                return urljoin(baseUrl, url)            
        addParams['cloudflare_params'] = {'domain':self.up.getDomain(baseUrl), 'cookie_file':self.COOKIE_FILE, 'User-Agent':self.USER_AGENT, 'full_url_handle':_getFullUrl}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)


    def listItems(self, cItem):
        printDBG("..:: E2iStream ::.. -  listItems(self, cItem): [%s]" % cItem)         
        i = 0    
           
        page = cItem.get('page', 1)
        
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        self.setMainUrl(self.cm.meta['url'])

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<div class=', '>', 'paging paging--right paging--padding'), ('</div', '>'))[1]
        nextPage = self.cm.ph.getSearchGroups(nextPage, '''<a[^>]+?href=['"]([^'^"]+?)['"][^>]*?>%s</a>''' % (page + 1))[0]
        nextPage = ph.clean_html(nextPage)   
                     
        block = self.cm.ph.getAllItemsBeetwenNodes(data, '<div class="videos ">', '<div class="group-items-list__bottom-paging"',False)[0]  
        block = self.cm.ph.getAllItemsBeetwenNodes(block, '<a class="dashboard-item__link"', '</a>')     

        for videos in block:
            title = self.cm.ph.getAllItemsBeetwenNodes(videos, '<div class="dashboard-item__title">', '</div>',False)
            title = map(lambda cleanTitle: cleanTitle.replace('\r\n                    ', ''), title)
            title = map(lambda cleanTitle: cleanTitle.replace('\r\n                ', ''), title)
            title = title[0]
            title  = ph.clean_html(title)
            videourl = self.MAIN_URL + self.cm.ph.getSearchGroups(videos, 'href="([^"]+?)"')[0]
            imageurl = self.cm.ph.getAllItemsBeetwenNodes(videos,'style="background-image: url(\'', ('\');">'),False)[1]
            viddate = self.cm.ph.getAllItemsBeetwenNodes(videos, '<div class="dashboard-item__date">', '</div>',False)[0]
            viddate = viddate.strip()
            vidviews = self.cm.ph.getAllItemsBeetwenNodes(videos, '<div class="dashboard-item__views">', '</div>',False)[0]
            vidviews = vidviews.strip()
            desc = '\c00????00 Title: \c00??????%s\\n \c00????00Date: \c00??????%s\\n \c00????00Views: \c00??????%s\\n' %(title, viddate, vidviews)
            params = dict(cItem)
            params.update({'good_for_fav':True, 'title':title, 'url':videourl, 'icon':imageurl, 'desc':desc})
            self.addVideo(params)                    
            
        if nextPage:
            params = dict(cItem)
            params.update({'good_for_fav':False, 'title':_("Next page"), 'page':page+1, 'url':self.getFullUrl(nextPage)})
            self.addDir(params)  
              
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("OrthoBullets.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        self.tryTologin()
        
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('/video/list?search=') + urllib.quote(searchPattern) 
        cItem['category'] = 'list_items'
        self.listItems(cItem)

    def getLinksForVideo(self, cItem):
        printDBG("OrthoBullets.getLinksForVideo [%s]" % cItem)
        self.tryTologin()
        
        sts, data = self.getPage(cItem['url'])
        if not sts: return []
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
                self.sessionEx.open(MessageBox, _('The host %s requires registration. \nPlease fill your login and password in the host configuration. Available under blue button.' % self.getMainUrl()), type = MessageBox.TYPE_ERROR, timeout = 10)
                return False
            
            sts, data = self.getPage(self.getFullUrl('/login'))
            if not sts: return False
            cUrl = self.cm.meta['url']
            
            sts, data = self.cm.ph.getDataBeetwenNodes(data, ('<form', '>'), ('</form', '>'))
            if not sts: return False
            actionUrl = self.cm.getFullUrl(self.cm.ph.getSearchGroups(data, '''action=['"]([^'^"]+?)['"]''')[0], self.cm.getBaseUrl(cUrl))
            if actionUrl == '': actionUrl = cUrl
            
            post_data = {}
            inputData = self.cm.ph.getAllItemsBeetwenMarkers(data, '<input', '>')
            inputData.extend(self.cm.ph.getAllItemsBeetwenMarkers(data, '<button', '>'))
            for item in inputData:
                name  = self.cm.ph.getSearchGroups(item, '''name=['"]([^'^"]+?)['"]''')[0]
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
                if not sts: return False
                actionUrl = self.cm.getFullUrl(self.cm.ph.getSearchGroups(data, '''action=['"]([^'^"]+?)['"]''')[0], self.cm.getBaseUrl(cUrl))
                if actionUrl == '': actionUrl = cUrl
                
                post_data = {}
                inputData = self.cm.ph.getAllItemsBeetwenMarkers(data, '<input', '>')
                inputData.extend(self.cm.ph.getAllItemsBeetwenMarkers(data, '<button', '>'))
                for item in inputData:
                    name  = self.cm.ph.getSearchGroups(item, '''name=['"]([^'^"]+?)['"]''')[0]
                    value = self.cm.ph.getSearchGroups(item, '''value=['"]([^'^"]+?)['"]''')[0].replace('&amp;', '&')
                    post_data[name] = value
                
                httpParams['header']['Referer'] = cUrl
                sts, data = self.cm.getPage(actionUrl, httpParams, post_data)
                if sts and '/logout' in data and self.cm.getBaseUrl(self.getMainUrl(), True) in self.cm.getBaseUrl(self.cm.meta['url'], True):
                    printDBG('tryTologin OK')
                    self.loggedIn = True
            
            if not self.loggedIn:
                self.sessionEx.open(MessageBox, _('Login failed.'), type = MessageBox.TYPE_ERROR, timeout = 10)
                printDBG('tryTologin failed')
                
        return self.loggedIn
    
    
    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        self.tryTologin()

        name     = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode     = self.currItem.get("mode", '')
        
        printDBG( "handleService: || name [%s], category [%s], mode [%s] " % (name, category, mode) )
        
        self.currList = []
        
        # First Menu
    
        if name == None:
            self.listsTab(self.MAIN_CAT_TAB, self.currItem)
        elif category == 'categories':
            printDBG("handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):   Category = %s" % category)
            self.listsTab(self.CATEGORIES_TAB, self.currItem)
        elif category == 'subspeciality':
            printDBG("handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):   Category = %s" % category)
            self.listsTab(self.SPECIALITY_TAB, self.currItem)
        elif category == 'list_items':
            self.listItems(self.currItem)
        elif category == 'list_categories':
            self.listItems(self.currItem)
        elif category == 'list_speciality':
            self.listItems(self.currItem)

        # Searching / Search History
        
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item':False, 'name':'category'}) 
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({'name':'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()
        
        CBaseHostClass.endHandleService(self, index, refresh)

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, OrthoBullets(), True, favouriteTypes=[]) 

