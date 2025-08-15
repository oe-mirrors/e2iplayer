# -*- coding: utf-8 -*-
# 2022.05.18. Blindspot
###################################################
HOST_VERSION = "1.0"
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass 
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
from Plugins.Extensions.IPTVPlayer.hosts import hosturllist as urllist
from Plugins.Extensions.IPTVPlayer.libs import ph
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
###################################################

###################################################
# FOREIGN import
###################################################
import re
import datetime
import urllib
###################################################
def gettytul():
    return 'https://www.watchseries.cyou/' 

class BlueWatch(CBaseHostClass):
 
    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'bluewatchseries', 'cookie':'bluewatchseries.cookie'})
        self.MAIN_URL = 'https://www.watchseries.cyou/'
        self.DEFAULT_ICON_URL = "http://blindspot.nhely.hu/Thumbnails/bluewatchseries.jpg"
        self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')        
        self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        
    def getPage(self, url, addParams = {}, post_data = None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)
    
    def getLinksForVideo(self, cItem):
        printDBG("BlueWatch.getLinksForVideo")
        sts, data = self.getPage(cItem['url'])
        videoUrls = []
        all = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="nav" id="videolinks">', '</div>', False)[1]
        links = self.cm.ph.getAllItemsBeetwenMarkers(all, 'href="', '"', False)
        names = self.cm.ph.getAllItemsBeetwenMarkers(all, '<strong>', '</strong>', False)
        for i in links:
            if 'https://www.watchseries.cyou' not in i:
                new = 'https://www.watchseries.cyou' + i
                sts, data = self.getPage(new)
            else:
               sts, data = self.getPage(i)
            url = self.cm.ph.getDataBeetwenMarkers(data, 'height="480" src="', '"', False)[1]
            if not url:
                url = self.cm.ph.getDataBeetwenMarkers(data, 'class="btn btn-success" href="', '"', False)[1]
                if 'https://www.watchseries.cyou' not in url:
                    url = 'https://www.watchseries.cyou' + url
                sts, data = self.getPage(url)
                url = self.cm.ph.getDataBeetwenMarkers(data, '<iframe src="', '"', False)[1]
            if url:
               uri = urlparser.decorateParamsFromUrl(url)
               protocol = uri.meta.get('iptv_proto', '')
               printDBG("PROTOCOL [%s] " % protocol)
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
                  videoUrls.append({'name':names[links.index(i)], 'url':uri})
        return videoUrls
    
    def _uriIsValid(self, url):
        return '://' in url
    
    def listMainMenu(self, cItem):   
        printDBG('BlueWatch.listMainMenu')
        MAIN_CAT_TAB = [{'category':'list_filters',            'title': _('Genres'), 'desc': "Only TV series"},
                        {'category':'list_items',            'title': _('TV Shows'), 'url': 'https://www.watchseries.cyou/tv-series?page=1'},
                        {'category':'list_items',            'title': _('Top Series'), 'url': 'https://www.watchseries.cyou/top-shows'},
                        {'category':'list_items',            'title': _('Movies'), 'url': 'https://www.watchseries.cyou/movies?page=1'},
                        {'category':'search',          'title': _('Search'), 'search_item':True},
                        {'category':'search_history',  'title': _('Search History')}
                        ]
        self.listsTab(MAIN_CAT_TAB, cItem) 

    def listItems(self, cItem):
        printDBG('BlueWatch.listItems')              
        sts, dat = self.getPage(cItem['url'])
        if not sts:
            return
        movies = self.cm.ph.getDataBeetwenMarkers(dat,'<div class="block_area-content block_area-list film_list film_list-grid">','</div></div></section>', False)[1]
        movies = self.cm.ph.getAllItemsBeetwenMarkers(movies, '<div class="film-poster">', '<div class="clearfix"></div>', False)
        for i in movies:
            url = self.cm.ph.getDataBeetwenMarkers(i, '<a href="', '"', False)[1]
            title = self.cm.ph.getDataBeetwenMarkers(i, 'title="', '"', False)[1]
            icon = self.cm.ph.getDataBeetwenMarkers(i, 'data-src="', '"', False)[1]
            time = self.cm.ph.getDataBeetwenMarkers(i, '<span class="fdi-item fdi-duration">', '</span>', False)[1]
            atype = self.cm.ph.getDataBeetwenMarkers(i, '<span class="float-right fdi-type">', '</span>', False)[1]
            if atype == "Movie":
                sts, data = self.getPage(url)
                desc = self.cm.ph.getDataBeetwenMarkers(data, '<span class="item mr-1">', '<div id=', True)[1]
                desc = self.cm.ph.getDataBeetwenMarkers(desc, '</div>', '<div id=', True)[1]
                desc = self.cm.ph.getDataBeetwenMarkers(desc, '</strong>', '<div id=', False)[1]
            else:
               sts, data = self.getPage(url)
               desc = self.cm.ph.getDataBeetwenMarkers(data, '<div class="description">', '<div class="row">', False)[1]
            desc = time + " " + atype + "\n" + desc
            if "series online" in desc:
                params = {'category': 'list_seasons', 'title':title, 'icon': icon, 'url': url, 'desc': desc}
                self.addDir(params)
            else:
                params = {'title':title, 'icon': icon, 'url': url, 'desc': desc}
                self.addVideo(params)
        if '<a title="Next"' in dat:
            url = self.cm.ph.getDataBeetwenMarkers(dat, '<a title="Next" class="page-link" href="', '"', False)[1]
            if 'https://www.watchseries.cyou' not in url:
                url = 'https://www.watchseries.cyou' + url
            params = {'category': 'list_items', 'title':"Next Page", 'icon': None, 'url': url}
            self.addDir(params)
	
    def exploreItems(self, cItem):
        printDBG('BlueWatch.listItems')
        if cItem['category'] == 'list_seasons':
            sts, data = self.getPage(cItem['url'])
            if not sts:
                return
            movies = self.cm.ph.getDataBeetwenMarkers(data,'Seasons','Episodes', False)[1]
            title = self.cm.ph.getAllItemsBeetwenMarkers(movies, 'title="', '"', False)
            descr = self.cm.ph.getAllItemsBeetwenMarkers(movies, '<span class="badge badge-light float-right">', '</span>', False)
            for i in title:
                desc = descr[title.index(i)] + "\n" + cItem['desc']
                params = {'category': 'list_episodes', 'title':i, 'icon': cItem['icon'], 'url': cItem['url'], 'desc': desc}
                self.addDir(params)
        if cItem['category'] == 'list_episodes':
            sts, data = self.getPage(cItem['url'])
            if not sts:
                return
            title = cItem['title'].replace("Season ", "")
            episodes = self.cm.ph.getDataBeetwenMarkers(data,'<div class="tab-pane " id="sstab-' + title + '" role="tabpanel" aria-labelledby="pills-home-tab">','</ul>', False)[1]
            if not episodes:
                episodes = self.cm.ph.getDataBeetwenMarkers(data,'<div class="tab-pane active" id="sstab-' + title + '" role="tabpanel" aria-labelledby="pills-home-tab">','</ul>', False)[1]
            titles = self.cm.ph.getAllItemsBeetwenMarkers(episodes, '<strong>', '</a>', False)
            urls = self.cm.ph.getAllItemsBeetwenMarkers(episodes, 'href="', '"', False)
            for i in titles:
                params = {'title':i.replace("</strong>", ""), 'icon': cItem['icon'], 'url': urls[titles.index(i)], 'desc': cItem['desc']}
                self.addVideo(params)
    
    def listFilters(self, cItem):
        printDBG('BlueWatch.listFilters')         
        sts, data = self.getPage(self.MAIN_URL)                    
        if not sts:
            return
        cat = self.cm.ph.getDataBeetwenMarkers(data, 'Genre', '</div></div></li></li>', False)[1]
        cats = self.cm.ph.getAllItemsBeetwenMarkers(cat, '<li class="nav-item">', '</li>', False)
        for i in cats:
            url = self.cm.ph.getDataBeetwenMarkers(i, '<a href="', '"', False)[1]
            title = self.cm.ph.getDataBeetwenMarkers(i, 'title="', '"', False)[1]
            if 'https://www.watchseries.cyou' not in url:
                url = 'https://www.watchseries.cyou' + url
            url = url +"?page=1"
            params = {'category':'list_items','title':title, 'icon': None , 'url': url}
            self.addDir(params)
    
    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('BlueWatch.handleService start')
        
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
        elif category == 'list_filters':
           self.listFilters(self.currItem)
        elif category == 'list_seasons' or category == 'list_episodes':
           self.exploreItems(self.currItem)
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
        printDBG("BlueWatch.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        url = 'https://www.watchseries.cyou/search/'
        s = searchPattern.replace(" ", "-")
        cItem['url']  = url +s
        self.listItems(cItem)
        

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, BlueWatch(), True, [])
    