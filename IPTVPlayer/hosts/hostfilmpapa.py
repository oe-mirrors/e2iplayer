# -*- coding: utf-8 -*-
# 2022.02.15. 
###################################################
HOST_VERSION = "1.1"
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
#repo.mvshrk.xyz/plugins/
def gettytul():
    return 'https://plusz.club' 

class FilmPapa(CBaseHostClass):
 
    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'filmpapa', 'cookie':'filmpapa.cookie'})
        self.MAIN_URL = 'https://plusz.club'
        self.DEFAULT_ICON_URL = "http://blindspot.nhely.hu/Thumbnails/filmpapalogo.png"
        self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')        
        self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        
    def getPage(self, url, addParams = {}, post_data = None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)
    
    def getLinksForVideo(self, cItem):
        printDBG("Filmpapa.getLinksForVideo")
        sts, data = self.getPage(cItem['url'])                        
        if not sts:
            return
        url = self.cm.ph.getDataBeetwenMarkers(data,'<div id="cn-content" class="autosize-container"><p><iframe width="560" height="315" src="','" frameborder="0" allow="autoplay" allowfullscreen></iframe></p>', False) [1]
        if not url:
            url = self.cm.ph.getDataBeetwenMarkers(data,' preload="metadata" controls="controls"><source type="video/mp4" src="','" /><a href="', False) [1]
        if "https:" not in url:
            url = "https:" + url
        videoUrls = []
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
                videoUrls.append({'name':'direct link', 'url':uri})
        return videoUrls
    
    def _uriIsValid(self, url):
        return '://' in url
    
    def listMainMenu(self, cItem):   
        printDBG('FilmPapa.listMainMenu')
        MAIN_CAT_TAB = [{'category':'list_items',            'title': _('Kategóriák')},
                        {'category':'search',          'title': _('Keresés'), 'search_item':True},
                        {'category':'search_history',  'title': _('Keresési előzmények')}]
        self.listsTab(MAIN_CAT_TAB, cItem) 

    def listItems(self, cItem):
        printDBG('FilmPapa.listItems')              
        sts, data = self.getPage(cItem['url'] + "page/" + str(cItem['page']))		
        if not sts:
            return
        lurl = cItem['url']
        page = cItem['page']
        max = self.cm.ph.getDataBeetwenMarkers(data, '</div><p class="mt10">','</p>', False) [1]
        movies = self.cm.ph.getAllItemsBeetwenMarkers(data,'<div class="movie-box">','</small></span>									</div>')
        for m in movies:
            title = self.cm.ph.getDataBeetwenMarkers(m, 'alt="','" width=', False) [1]
            if "&#8211;" in title:
                title = title.replace("&#8211;", "-")
            if "&#8217;" in title:
                title = title.replace("&#8217;", "")
            icon = self.cm.ph.getDataBeetwenMarkers(m, 'img src="','" alt="', False) [1]
            url = self.cm.ph.getDataBeetwenMarkers(m, '<a href="','">', False) [1]
            sts, data2 = self.getPage(url)
            if not sts:
                return
            desc = "IMDB pontszám: " + self.cm.ph.getDataBeetwenMarkers(m, '<span class="icon-star imdb tooltip">',' <span class=', False) [1] + ", Tartalom: " + self.cm.ph.getDataBeetwenMarkers(data2, '<div class="description">','</div>', False) [1]
            if '<br />' in desc or '</br>' in desc:
                try:
                   desc = desc.replace('<br />', "")
                   desc = desc.replace('</br>', "")
                except:
                   pass
            params = {'title':title, 'icon': icon , 'url': url, 'desc': desc}
            self.addVideo(params)
        if max != "There were no results found.":
            params = {'category': 'list_filters', 'title': "Következő oldal", 'icon': None , 'url': lurl, 'page': page+1}
            self.addDir(params)
    
    def listFilters(self, cItem):
        printDBG('FilmPapa.listFilters')
        url = 'https://plusz.club'               
        sts, data = self.getPage(url)                    
        if not sts:
            return
        cat = self.cm.ph.getAllItemsBeetwenMarkers(data,'<li class="cat-item cat-item','</li>')
        for c in cat:
            title = self.cm.ph.getDataBeetwenMarkers(c, '" >','</a>', False) [1]
            if title == "":
                title = self.cm.ph.getDataBeetwenMarkers(c, 'title=','/a>', False) [1]
                title = self.cm.ph.getDataBeetwenMarkers(title, '">','<', False) [1]
            page = 1
            icon = None
            url = self.cm.ph.getDataBeetwenMarkers(c, '<a href="','"', False) [1]
            params = {'category':'list_filters','title':title, 'icon': icon , 'url': url, 'page': page}
            self.addDir(params)
    
    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('FilmPapa.handleService start')
        
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name     = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        title = self.currItem.get("title", '')
        icon = self.currItem.get("icon", '')
        url = self.currItem.get("url", '')
        
        printDBG( "handleService: >> name[%s], category[%s], title[%s], icon[%s] " % (name, category, title, icon) )
        self.currList = []
        
        if name == None:
            self.listMainMenu({'name':'category'})
        elif category == 'list_items':
            self.listFilters(self.currItem)
        elif category == 'list_filters':
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
        printDBG("FilmPapa.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        url = 'https://plusz.club/?s=' + searchPattern
        cItem['url'] = url           
        sts, data = self.getPage(cItem['url'])		
        if not sts:
            return
        movies = self.cm.ph.getAllItemsBeetwenMarkers(data,'<div class="movie-box">','</small></span>									</div>')
        for m in movies:
            title = self.cm.ph.getDataBeetwenMarkers(m, 'alt="','" width=', False) [1]
            if "&#8211;" in title:
                title = title.replace("&#8211;", "-")
            if "&#8217;" in title:
                title = title.replace("&#8217;", "")
            icon = self.cm.ph.getDataBeetwenMarkers(m, 'img src="','" alt="', False) [1]
            url = self.cm.ph.getDataBeetwenMarkers(m, '<a href="','">', False) [1]
            sts, data2 = self.getPage(url)
            if not sts:
                return
            desc = "IMDB pontszám: " + self.cm.ph.getDataBeetwenMarkers(m, '<span class="icon-star imdb tooltip">',' <span class=', False) [1] + ", Tartalom: " + self.cm.ph.getDataBeetwenMarkers(data2, '<div class="description">','</div>', False) [1]
            if '<br />' in desc or '</br>' in desc:
                try:
                   desc = desc.replace('<br />', "")
                   desc = desc.replace('</br>', "")
                except:
                   pass
            params = {'title':title, 'icon': icon , 'url': url, 'desc': desc}
            self.addVideo(params)

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, FilmPapa(), True, [])
    