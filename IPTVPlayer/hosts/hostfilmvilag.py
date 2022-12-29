# -*- coding: utf-8 -*-
# 2022.05.16. Blindspot
###################################################
HOST_VERSION = "1.4"
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
    return 'https://www.onlinefilmvilag2.eu/' 

class FilmVilag(CBaseHostClass):
 
    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'filmvilag', 'cookie':'filmvilag.cookie'})
        self.MAIN_URL = 'https://www.onlinefilmvilag2.eu/'
        self.DEFAULT_ICON_URL = "https://www.onlinefilmvilag2.eu/img/portrait.1.1586208455.jpeg"
        self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')        
        self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        
    def getPage(self, url, addParams = {}, post_data = None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)
    
    def getLinksForVideo(self, cItem):
        printDBG("FilmVilag.getLinksForVideo")
        if "https://www.onlinefilmvilag2.eu" in cItem['url']:
            sts, data = self.getPage(cItem['url'])                        
            if not sts:
                return
            url = self.cm.ph.getDataBeetwenMarkers(data,'height="315" src="','" width', False) [1]
            if "https:" not in url:
                url = "https:" + url
        else:
           url = cItem['url']
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
        printDBG('FilmVilag.listMainMenu')
        MAIN_CAT_TAB = [{'category':'list_items',            'title': _('Kategóriák'), 'desc': "Egyes videómegosztók pillanatnyilag nem támogatottak"},
                        {'category':'search',          'title': _('Keresés'), 'search_item':True, 'desc': "Egyes videómegosztók pillanatnyilag nem támogatottak"},
                        {'category':'search_history',  'title': _('Keresési előzmények'), 'desc': "Egyes videómegosztók pillanatnyilag nem támogatottak"}]
        self.listsTab(MAIN_CAT_TAB, cItem) 

    def getdesc(self, iurl):
        sts, data = self.getPage(iurl)
        ogdesc = self.cm.ph.getDataBeetwenMarkers(data, '<meta property="og:description" content="', '" />', False)[1]
        desc = self.cm.ph.getDataBeetwenMarkers(data, '<div class="editor-area">', '<div class="article-cont-clear clear">', False)[1]
        while '<' in desc and '>' in desc:
           kill = self.cm.ph.getDataBeetwenMarkers(desc, '<', '>')[1]
           desc = desc.replace(kill, '')
        while "&" in desc and ";" in desc:
           kill = self.cm.ph.getDataBeetwenMarkers(desc, '&', ';')[1]
           desc = desc.replace(kill, '')
        while "adsbygoogle" in desc:
           desc = desc.replace('(adsbygoogle = window.adsbygoogle || []).push({});', '')
        printDBG(desc)
        desc = desc.split("\n")
        printDBG(desc)
        var = 0
        while var != len(desc):
           if "," not in desc[var]:
               if ":" not in desc[var]:
                   desc.pop(var)
                   var = var-1
           var = var+1
        printDBG(desc)
        if "Letöltés" in desc[0]:
            desc.pop(0)
        printDBG(desc)
        desc = "\n".join(desc)
        return (ogdesc + "\n" + desc)

    def listItems(self, cItem):
        printDBG('FilmVilag.listItems')              
        sts, data = self.getPage(cItem['url'] + "." + str(cItem['page']) + "/")
        if not sts:
            return
        lurl = cItem['url']
        page = cItem['page']
        movies = self.cm.ph.getAllItemsBeetwenMarkers(data,'<div class="article">',' <span class="section"><span class="art-delimit-wa"><span> | </span></span>')
        for m in movies:
            title = self.cm.ph.getDataBeetwenMarkers(m, '<span class="decoration" title="','"></span>', False) [1]
            icon = self.cm.ph.getDataBeetwenMarkers(m, '<img src="','" width', False) [1]
            url = self.MAIN_URL + self.cm.ph.getDataBeetwenMarkers(m, '<a href="','">', False) [1]
            desc = self.getdesc(url)
            params = {'title':title, 'icon': icon , 'url': url, 'desc': desc}
            self.addVideo(params)
        if "Következő &raquo" in data:
            params = {'category': 'list_filters', 'title': "Következő oldal", 'icon': None , 'url': lurl, 'page': page+1}
            self.addDir(params)
    
    def upp(self, item):
        item = item.upper()
        if "á" in item:
            item = item.replace("á", "Á")
        if "é" in item:
            item = item.replace("é", "É")
        if "ö" in item:
            item = item.replace("ö", "Ö")
        if "ü" in item:
            item = item.replace("ü", "Ü")
        if "ó" in item:
            item = item.replace("ó", "Ó")
        if "ő" in item:
            item = item.replace("ő", "Ő")
        if "ű" in item:
            item = item.replace("ű", "Ű")
        if "ú" in item:
            item = item.replace("ú", "Ú")
        if "í" in item:
            item = item.replace("í", "Í")
        return item
	
    def listFilters(self, cItem):
        printDBG('FilmVilag.listFilters')
        utl = 'https://www.onlinefilmvilag2.eu/'               
        sts, data = self.getPage(utl)                    
        if not sts:
            return
        cat = self.cm.ph.getAllItemsBeetwenMarkers(data,'<li class="">','</li>', False)
        for c in cat:
            if c != cat[0] and c != cat[1] and c != cat[2] and c != cat[3] and c != cat[-1] and c != cat[-2] and c != cat[-5]:
                title = self.cm.ph.getDataBeetwenMarkers(c, '">','</a>', False) [1]
                if "amp;" in title:
                    title = title.replace("amp;", "")
                title = self.upp(title)
                if "SOROZAT" not in title:
                    icon = None
                    url = utl + self.cm.ph.getDataBeetwenMarkers(c, '<a href="/','/">', False) [1]
                    page = 1
                    params = {'category':'list_filters','title':title, 'icon': icon , 'url': url, 'page': page}
                    self.addDir(params)
    
    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('FilmVilag.handleService start')
        
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
        printDBG("FilmVilag.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        url = 'http://katalogus.eoldal.hu/'
        s = searchPattern.replace(" ", "+")
        sts, data = self.getPage(url, self.defaultParams, {'uid':664389, 'key': s})
        if not sts:
            return
        results = self.cm.ph.getDataBeetwenMarkers(data, '<ul>', '</ul>', False) [1]
        printDBG(results)
        results = self.cm.ph.getAllItemsBeetwenMarkers(results, 'a href="', '">', False)
        printDBG(results)
        for n in results:
            if results.index(n) != 0:
                sts, data = self.getPage(n)
                result = self.cm.ph.getDataBeetwenMarkers(data, '<div class="article">', '<div class="article-cont-clear clear">', False) [1]
                printDBG(result)
                title = self.cm.ph.getDataBeetwenMarkers(result, 'span class="span-a-title">','</span>', False) [1]
                printDBG(title)
                icon = self.cm.ph.getDataBeetwenMarkers(result, 'height="169" src="','"', False) [1]
                url = self.cm.ph.getDataBeetwenMarkers(result, '" src="','"', False) [1]
                desc = self.getdesc(title, n)
                params = {'title':title, 'icon': icon , 'url': url, 'desc': desc}
                self.addVideo(params)

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, FilmVilag(), True, [])
    