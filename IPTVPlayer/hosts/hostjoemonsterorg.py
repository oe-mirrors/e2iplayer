# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
###################################################

###################################################
# FOREIGN import
###################################################
import re
try:    import json
except Exception: import simplejson as json
###################################################


def gettytul():
    return 'https://joemonster.org/'

class JoeMonster(CBaseHostClass):
 
    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'joemonster.org', 'cookie':'joemonster.org.cookie'})
        
        self.DEFAULT_ICON_URL = 'https://joemonster.org/images/logo/jm-logo-1450873307.png'
        self.HEADER = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0', 'DNT':'1', 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update( {'X-Requested-With': 'XMLHttpRequest'} )
        self.MAIN_URL = 'https://joemonster.org/'
        self.defaultParams = {'with_metadata':True, 'header':self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
    
    def getPage(self, url, addParams = {}, post_data = None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        
        return self.cm.getPage(url, addParams, post_data)
        
    def listMainMenu(self, cItem):
        MAIN_CAT_TAB = [{'category':'list_items',       'title': 'Monster TV - Najnowsze filmy',   'url':self.getFullUrl('/filmy')            },
                        {'category':'list_items',       'title': 'Monster TV - Najlepsze filmy',   'url':self.getFullUrl('/filmy/ulubione')   },
                        {'category':'list_poczekalnia', 'title': 'Monster TV - Poczekalnia',       'url':self.getFullUrl('/filmy/poczekalnia')},
                        {'category':'list_poczekalnia', 'title': 'Monster TV - Kolejka',           'url':self.getFullUrl('/filmy/kolejka')    },]
        self.listsTab(MAIN_CAT_TAB, cItem)
    
    def listItems(self, cItem):
        printDBG("JoeMonster.listItems")

        page = cItem.get('page', 1)

        sts, data = self.getPage(cItem['url'])
        if not sts: return

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'pagerNav'), ('</div', '>'), False)[1]
        nextPage = self.cm.ph.getDataBeetwenNodes(nextPage, ('<span', '>', 'highlight'), ('pagerNav', '>'), False)[1]
        nextPage = self.cm.ph.getSearchGroups(nextPage, '''href=['"]([^"^']+?)['"]''')[0]

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'mtvLeftColumn'), ('<div', '>', 'footer'))[1]
        data = self.cm.ph.rgetAllItemsBeetwenNodes(data, ('</div', '>'), ('<div id', '>', 'mtv-row'))
        for item in data:
            url = self.getFullUrl( self.cm.ph.getSearchGroups(item, '''\shref=['"]([^"^']+?)['"]''')[0] )
            title = self.cleanHtmlStr( self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'mtv-desc'), ('</b', '>'))[1])
            time  = self.cleanHtmlStr( self.cm.ph.getDataBeetwenNodes(item, ('<time', '>', 'video-time'), ('</time', '>'))[1])
            if len(time) > 0: time = '[%s] ' % time
            desc  = time + self.cleanHtmlStr( self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'mtv-desc-text'), ('</div', '>'))[1])
            if not self.cm.isValidUrl(url): continue
            icon = self.getFullIconUrl( self.cm.ph.getSearchGroups(item, '''\surl\(([^\)]+?)\)''')[0] )
            params = dict(cItem)
            params = {'good_for_fav': True, 'title':title, 'url':url, 'icon':icon, 'desc':desc}
            self.addVideo(params)

        if nextPage != '':
            params = dict(cItem)
            params.update({'title':_("Next page"), 'url':self.getFullUrl(nextPage), 'page':page+1})
            self.addDir(params)
        
    def listPoczekalnia(self, cItem):
        printDBG("JoeMonster.listPoczekalnia")

        page = cItem.get('page', 1)
        
        sts, data = self.getPage(cItem['url'])
        if not sts: return

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'pagerNav'), ('</div', '>'), False)[1]
        nextPage = self.cm.ph.getDataBeetwenNodes(nextPage, ('<span', '>', 'highlight'), ('</a', '>'), False)[1]
        nextPage = self.cm.ph.getSearchGroups(nextPage, '''href=['"]([^"^']+?)['"]''')[0]
        
        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'mtv-poczekalnia-container'), ('<br', '>'))[1]
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'mtvPoczekalniaFilm'), ('</h2', '>'))
        for item in data:
            url = self.getFullUrl( self.cm.ph.getSearchGroups(item, '''\shref=['"]([^"^']+?)['"]''')[0] )
            title  = self.cleanHtmlStr( self.cm.ph.getDataBeetwenNodes(item, ('<h2', '>'), ('</h2', '>'))[1])
            time  = self.cleanHtmlStr( self.cm.ph.getDataBeetwenNodes(item, ('<time', '>', 'video-time'), ('</time', '>'))[1])
            if len(time) > 0: time = '[%s] ' % time
            if not self.cm.isValidUrl(url): continue
            icon = self.getFullIconUrl( self.cm.ph.getSearchGroups(item, '''\ssrc=['"]([^"^']+?)['"]''')[0] )
            params = dict(cItem)
            params = {'good_for_fav': True, 'title':title, 'url':url, 'icon':icon, 'desc':time}
            self.addVideo(params)

        if nextPage != '':
            params = dict(cItem)
            params.update({'title':_("Next page"), 'url':self.getFullUrl(nextPage), 'page':page+1})
            self.addDir(params)
    
    def getLinksForVideo(self, cItem):
        printDBG("JoeMonster.getLinksForVideo [%s]" % cItem)
        urlTab = []
        
        sts, data = self.getPage(cItem['url'])
        if not sts: return

        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'mtv-player-wrapper'), ('<div', '>', 'mtvRightColumn'), False)[1]
        tmp = self.cm.ph.getDataBeetwenMarkers(tmp, '<video', '</video>', False)[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<source', '>')
        if len(tmp):
            for item in tmp:
                type = self.cm.ph.getSearchGroups(item, '''type=['"]([^'^"]+?)['"]''')[0].lower()
                url  = self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0]
                name = '%s. %s' % (str(len(urlTab)+1), type)
                
                if 'video/mp4' == type: 
                    urlTab.append({'name':name, 'url':self.getFullUrl(url), 'need_resolve':0})
                elif 'video/youtube' == type:
                    urlTab.append({'name':name, 'url':self.getFullUrl(url), 'need_resolve':1})
        if 0 == len(urlTab):
            tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<iframe', '>'), ('</iframe', '>'))
            for item in tmp:
                url  = self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0]
                urlTab.append({'name':'name', 'url':self.getFullUrl(url), 'need_resolve':1})

        return urlTab
    
    def getVideoLinks(self, videoUrl):
        printDBG("JoeMonster.getVideoLinks [%s]" % videoUrl)
        urlTab = []
        if 1 == self.up.checkHostSupport(videoUrl): 
            urlTab = self.up.getVideoLinkExt(videoUrl)
        return urlTab
        
    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('handleService start')
        
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name     = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode     = self.currItem.get("mode", '')
        
        printDBG( "handleService: >> name[%s], category[%s] " % (name, category) )
        self.currList = []
        
    #MAIN MENU
        if name == None:
            self.listMainMenu({'name':'category'})
        elif category == 'list_poczekalnia':
            self.listPoczekalnia(self.currItem)
        elif category == 'list_items':
            self.listItems(self.currItem)
        else:
            printExc()
        
        CBaseHostClass.endHandleService(self, index, refresh)

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, JoeMonster(), True, [])
    