# -*- coding: utf-8 -*-
# 2021.04.14. Blindspot
###################################################
HOST_VERSION = "1.0"
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
from Plugins.Extensions.IPTVPlayer.hosts import hosturllist as urllist
from Plugins.Extensions.IPTVPlayer.libs import ph
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
###################################################

###################################################
# FOREIGN import
###################################################
import urllib
import os
###################################################

def gettytul():
    return 'http://streamstat.net/' 

class StreamStat(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'streamstat', 'cookie':'streamstat.cookie'})
        self.MAIN_URL = 'http://streamstat.net/'
        self.DEFAULT_ICON_URL = "http://blindspot.nhely.hu/Thumbnails/streamstat.jpg"
        self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')        
        self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        
    def getPage(self, url, addParams = {}, post_data = None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)
    
    def _uriIsValid(self, url):
        return '://' in url
    
    def getLinksForVideo(self, cItem):
        printDBG('StreamStat.getLinksForVideo')
        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return
        videoUrls = []
        data = data.split()
        dat = data[2]
        uri = urlparser.decorateParamsFromUrl(dat)
        protocol = uri.meta.get('iptv_proto', '')
        urlSupport = self.up.checkHostSupport( uri )
        if 1 == urlSupport:
             retTab = self.up.getVideoLinkExt( uri )
             videoUrls.extend(retTab)
        elif 0 == urlSupport and self._uriIsValid(uri):
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
              videoUrls.append({'name':'direct link', 'url':uri})
        return videoUrls
    
    def listMainMenu(self, cItem):   
        printDBG('StreamStat.listMainMenu')
        page = 1
        MAIN_CAT_TAB = [{'category':'list_items',            'title': _('YP connected'), 'url':'http://streamstat.net/main.cgi?mode=yp&search=&page=1&fp=50', 'page': page},
                        {'category':'list_items',            'title': _('Collected streams only'), 'url':'http://streamstat.net/main.cgi?mode=col&search=&page=1&fp=50', 'page': page},
                        {'category':'list_items',            'title': _('Free IPTV list'), 'url':'http://streamstat.net/main.cgi?mode=hls&search=&page=1&fp=50', 'page': page},
                        {'category':'list_items',            'title': _('All streams'), 'url':'http://streamstat.net/main.cgi?mode=all&search=&page=1&fp=50', 'page': page},
                        {'category':'list_items',            'title': _('Random selection'), 'url':'http://streamstat.net/main.cgi?mode=&search=&page=1&fp=50', 'page': page},
                        {'category':'search',          'title': _('Keresés'), 'search_item':True},
                        {'category':'search_history',  'title': _('Keresési előzmények')}]
        self.listsTab(MAIN_CAT_TAB, cItem) 
        
    def listItems(self, cItem):
        printDBG('StreamStat.listItems')
        page = self.cm.ph.getDataBeetwenMarkers(cItem['url'], 'page=', '&', False)[1]
        mainurl = cItem['url'].replace('page=' + page, 'page=' + str(cItem['page']))
        sts, dat = self.getPage(mainurl)
        if not sts:
            return
        page = cItem['page']
        web = self.cm.ph.getAllItemsBeetwenMarkers(dat, 'Select playlist link:</li><li><a target="_blank" href="','">', False)
        titles = self.cm.ph.getAllItemsBeetwenMarkers(dat, '<p class="allomasnev_sorszam hidden-sm hidden-md hidden-lg">', '</p>', False)
        id = self.cm.ph.getAllItemsBeetwenMarkers(dat, '<td class="sorszam lista_th_hidden-xs">', '.</td>', False)
        links = self.cm.ph.getAllItemsBeetwenMarkers(dat, '<div class="logo_logo" style="background-image: url(', ');', False)
        descs = self.cm.ph.getAllItemsBeetwenMarkers(dat, '<p class="allomasnev_mufaj">', '</p>', False)
        quality = self.cm.ph.getAllItemsBeetwenMarkers(dat, '<p class="allomasnev_minoseg hidden-lg"><b>', '</b>', False)
        icons = []
        printDBG(str(descs))
        for i in id:
            try:
               icons.append({i: links[id.index(i)]})
            except:
               pass
        for i in web:
            title = titles[web.index(i)]
            title = title.replace('&nbsp;', ' ')
            url = 'http://streamstat.net' + i
            try:
               icon = icons[id.index(web.index(i))]
            except:
               icon = None
            try:
               desc = descs[web.index(i)]
               desc = desc.replace("&nbsp;", " ")
            except:
               desc = "No description available currently."
            printDBG(str(desc))
            if title == "":
                title = "Unnamed"
            params = {'title':title, 'icon': icon , 'url': url, 'desc': desc}
            if "HLS" in quality[web.index(i)]:
                self.addVideo(params)
            else:
               self.addAudio(params)
        if '<li class="disabled"><a><span class="glyphicon glyphicon-chevron-right"' not in dat:
            params = {'category': 'list_items', 'title': "Next page", 'icon': None , 'url': cItem['url'], 'page': page+1}
            self.addDir(params)
    
    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('StreamStat.handleService start')
        
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name     = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        title = self.currItem.get("title", '')
        icon = self.currItem.get("icon", '')
        url = self.currItem.get("url", '')
        desc = self.currItem.get("desc", '')
        
        printDBG( "handleService: >> name[%s], category[%s], title[%s], icon[%s] " % (name, category, title, icon) )
        self.currList = []
        
        if name == None:
            self.listMainMenu({'name':'category'})
        elif category == 'list_items':
            self.listItems(self.currItem)
        elif category == 'search':
            cItem = dict(self.currItem)
            cItem.update({'search_item':False, 'name':'category'}) 
            self.listSearchResult(cItem, searchPattern, searchType)			
        elif category == "search_history":
            self.listsHistory({'name':'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()
        
        CBaseHostClass.endHandleService(self, index, refresh)
    
    
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("StreamStat.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        searchPattern = searchPattern.replace(" ", "+")
        url = 'http://streamstat.net/main.cgi?mode=all&search=' + searchPattern + '&page=1&fp=50'
        cItem['url'] = url
        cItem['page'] = 1
        self.listItems(cItem)

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, StreamStat(), True, [])
    