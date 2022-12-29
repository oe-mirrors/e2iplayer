# -*- coding: utf-8 -*-
# 2022.07.01. Blindspot
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
    return 'https://filmtar.online/' 

class FilmTar(CBaseHostClass):
 
    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'filmtar', 'cookie':'filmtar.cookie'})
        self.MAIN_URL = 'https://filmtar.online/'
        self.DEFAULT_ICON_URL = "http://www.blindspot.nhely.hu/Thumbnails/filmtar.png"
        self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')        
        self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        
    def getPage(self, url, addParams = {}, post_data = None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)
    
    def getLinksForVideo(self, cItem):
        printDBG("FilmTar.getLinksForVideo")
        videoUrls = []
        url = cItem['url']
        if url.startswith == "https://sbot.cf":
            url = urllib.unquote(url)
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
        printDBG('FilmTar.listMainMenu')
        MAIN_CAT_TAB = [{'category':'list_filters',            'title': _('Film Kategóriák'), 'url': 'https://filmtar.online/filmek/kategoriak'},
                        {'category':'list_filters',            'title': _('Sorozat Kategóriák'), 'url': 'https://filmtar.online/sorozatok/kategoriak'},
                        {'category':'search',          'title': _('Keresés'), 'search_item':True},
                        {'category':'search_history',  'title': _('Keresési előzmények')}]
        self.listsTab(MAIN_CAT_TAB, cItem) 

    def listItems(self, cItem):
        printDBG('FilmTar.listItems')              
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        movies = self.cm.ph.getDataBeetwenMarkers(data, '<section class="container-fluid">', '</section>', False)[1]
        movies = self.cm.ph.getAllItemsBeetwenMarkers(movies,'<div class="col ">','</a>')
        for m in movies:
            title = self.cm.ph.getDataBeetwenMarkers(m, '<h5 class="movie-box__title" data-toggle="tooltip" data-placement="top" title="', '"', False) [1]
            if not title:
                title = self.cm.ph.getDataBeetwenMarkers(m, '" alt="', '"', False) [1]
            icon = self.cm.ph.getDataBeetwenMarkers(m, 'data-src="', '"', False) [1]
            url = self.cm.ph.getDataBeetwenMarkers(m, '<a href="', '"', False) [1]
            desc = "Kategória: " + self.cm.ph.getDataBeetwenMarkers(m, '<br />','</li>', False) [1] + "\n" + "Játékidő: " + self.cm.ph.getDataBeetwenMarkers(m, 'Játékidő:</strong><br />','</li>', False) [1] + "\n" + "Nyelv: " + self.cm.ph.getDataBeetwenMarkers(m, '<div class="icon-language" data-toggle="tooltip" data-placement="top" title="','"', False) [1] + "\n" + "IMDb: " + self.cm.ph.getDataBeetwenMarkers(m, '<i class="fa fa-star"></i> ','</span>', False) [1] + "\n" + "Megjelenés: " + self.cm.ph.getDataBeetwenMarkers(m, '<span class="movie-box__year">','</span>', False)[1].strip()
            if "sorozatok" in url:
                params = {'category': 'list_sorozat', 'title':title, 'icon': icon , 'url': url, 'desc': desc}
            if "filmek" in url:
                params = {'category': 'list_film', 'title':title, 'icon': icon , 'url': url, 'desc': desc}
            self.addDir(params)
        if 'Következő &raquo;' in data:
            next = self.cm.ph.getSearchGroups(data, '''href=['"]([^"^']+?)['"] rel="next"''', 1, True)[0]
            params = {'category': 'list_items', 'title':"Következő oldal", 'icon': None , 'url': next}
            self.addDir(params)
    
    def listFilm(self, cItem):
        printDBG('FilmTar.listFilm')              
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        desc = self.cm.ph.getDataBeetwenMarkers(data, '<meta property="og:description"  content="', '"', False) [1]
        url = self.cm.ph.getDataBeetwenMarkers(data, '<div class="d-flex align-items-center justify-content-between flex-wrap mb-3">', 'rel="nofollow"', False) [1]
        url = self.cm.ph.getDataBeetwenMarkers(url, '<a href="', '"', False) [1]
        sts, data = self.getPage(url)
        links = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="movie-source__header">', '<li class="movie-source">', False)
        if not links:
            links = self.cm.ph.getDataBeetwenMarkers(data, '<div class="movie-source__header">', 'Lejátszás', False)[1]
            title = self.cm.ph.getDataBeetwenMarkers(links, '<span class="movie-source__title">', '</span>', False) [1]
            url = self.cm.ph.getDataBeetwenMarkers(links, 'href="', '"', False) [1]
            params = {'title':title, 'icon': cItem['icon'], 'url': url, 'desc': desc}
            self.addVideo(params)
            return
        for l in links:
            title = self.cm.ph.getDataBeetwenMarkers(l, '<span class="movie-source__title">', '</span>', False) [1]
            if title:
                url = self.cm.ph.getDataBeetwenMarkers(l, 'href="', '"', False) [1]
                params = {'title':title, 'icon': cItem['icon'], 'url': url, 'desc': desc}
                self.addVideo(params)
    
    def listSeries(self, cItem):
        printDBG('FilmTar.listSeries')              
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        desc = self.cm.ph.getDataBeetwenMarkers(data, '<meta property="og:description"  content="', '"', False) [1]
        lists = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="list-numbers">', '</ul>', False)[1]
        list = self.cm.ph.getAllItemsBeetwenMarkers(lists, '<a class="number-item"', '</a>', False)
        if not list:
            title = self.cm.ph.getDataBeetwenMarkers(lists, '<strong><span>', '</strong>', False)[1].replace('</span>', '') + " - ", + self.cm.ph.getDataBeetwenMarkers(lists.replace('<strong><span>',''), '<span>', '</span>', False)[1]
            url = self.cm.ph.getDataBeetwenMarkers(lists, 'href="', '"', False)[1]
            params = {'category': 'list_episodes', 'title':title, 'icon': cItem['icon'], 'url': url, 'desc': desc}
            self.addDir(params)
            return
        for i in list:
            title = self.cm.ph.getDataBeetwenMarkers(i, '<strong><span>', '</strong>', False)[1].replace('</span>', '') + " - " + self.cm.ph.getDataBeetwenMarkers(i.replace('<strong><span>',''), '<span>', '</span>', False)[1]
            url = self.cm.ph.getDataBeetwenMarkers(i, 'href="', '"', False)[1]
            params = {'category': 'list_episodes', 'title': title, 'icon': cItem['icon'], 'url': url, 'desc': desc}
            self.addDir(params)
    
    def listEpisodes(self, cItem):
        printDBG('FilmTar.listEpisodes')              
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        url = self.cm.ph.getDataBeetwenMarkers(data, '<div class="d-flex align-items-center', 'rel="nofollow"', False) [1]
        url = self.cm.ph.getDataBeetwenMarkers(url, '<a href="', '"', False) [1]
        sts, data = self.getPage(url)
        episodes = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="accordion__item">', '</ul>', False)
        if episodes:
            num = 1
            for i in episodes:
                title = str(num) + "." + " epizód"
                params = {'category':'list_links','title':title, 'icon': cItem['icon'] , 'url': url, 'desc': cItem['desc']}
                self.addDir(params)
                num = num+1
        else:
           title = "1.epizód"
           params = {'category':'list_links','title':title, 'icon': cItem['icon'] , 'url': cItem['url'], 'desc': cItem['desc']}
           self.addDir(params)
    
    def listLinks(self, cItem):
        printDBG('FilmTar.listLinks')
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        episodes = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="accordion__item">', '</ul>')
        if episodes:
            num = 1
            num2 = int(cItem['title'][0])
            for i in episodes:
                if num == num2:
                    links = self.cm.ph.getAllItemsBeetwenMarkers(i, '<div class="movie-source__header">', '</a>')
                    if not links:
                        links = self.cm.ph.getDataBeetwenMarkers(i, '<div class="movie-source__header">', 'Lejátszás', False)[1]
                        title = self.cm.ph.getDataBeetwenMarkers(links, '<span class="movie-source__title">', '</span>', False) [1]
                        url = self.cm.ph.getDataBeetwenMarkers(links, 'href="', '"', False) [1]
                        params = {'title':title, 'icon': cItem['icon'], 'url': url, 'desc': cItem['desc']}
                        self.addVideo(params)
                        return
                    for l in links:
                        title = self.cm.ph.getDataBeetwenMarkers(l, '<span class="movie-source__title">', '</span>', False) [1]
                        if title:
                            url = self.cm.ph.getDataBeetwenMarkers(l, 'href="', '"', False) [1]
                            params = {'title':title, 'icon': cItem['icon'], 'url': url, 'desc': cItem['desc']}
                            self.addVideo(params)
                num = num+1
        else:
           links = self.cm.ph.getDataBeetwenMarkers(data, '<div class="movie-source__header">', 'Lejátszás', False)[1]
           title = self.cm.ph.getDataBeetwenMarkers(links, '<span class="movie-source__title">', '</span>', False) [1]
           url = self.cm.ph.getDataBeetwenMarkers(links, 'href="', '"', False) [1]
           params = {'title':title, 'icon': cItem['icon'], 'url': url, 'desc': cItem['desc']}
           self.addVideo(params)
    
    def listFilters(self, cItem):
        printDBG('FilmTar.listFilters')        
        url2 = cItem['url'].replace('/kategoriak', '')
        sts, data = self.getPage(url2)
        title = "Összes " + self.cm.ph.getDataBeetwenMarkers(data, '<h1 class="section-title mb-3 mb-md-0">', '<span class="font-weight-normal pl-4">', False)[1].strip()
        icon = None
        desc = self.cm.ph.getDataBeetwenMarkers(data, '<span class="font-weight-normal pl-4">', '</span>', False)[1].strip() + "\n" + "Rendezve feltöltés ideje szerint"
        params = {'category':'list_items','title':title, 'icon': icon , 'url': url2, 'desc': desc}
        self.addDir(params)
        sts, data = self.getPage(cItem['url'])                    
        if not sts:
            return
        cat = self.cm.ph.getAllItemsBeetwenMarkers(data,'<div class="col mb-4">','</div>', False)
        for c in cat:
                title = self.cm.ph.getDataBeetwenMarkers(c, '<span>','</span>', False) [1]
                icon = None
                url = self.cm.ph.getDataBeetwenMarkers(c, '<a href="','"', False) [1]
                desc = self.cm.ph.getDataBeetwenMarkers(c, '<span class="font-weight-normal opacity--7">', '</span>', False) [1]
                params = {'category':'list_items','title':title, 'icon': icon , 'url': url, 'desc': desc}
                self.addDir(params)
    
    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('FilmTar.handleService start')
        
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
        elif category == 'list_film':
            self.listFilm(self.currItem)
        elif category == 'list_sorozat':
            self.listSeries(self.currItem)
        elif category == 'list_episodes':
            self.listEpisodes(self.currItem)
        elif category == 'list_links':
            self.listLinks(self.currItem)
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
        printDBG("FilmTar.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        url = 'https://filmtar.online/filmek?kulcsszo=' + searchPattern + '&miben=cim'
        url2 = 'https://filmtar.online/sorozatok?kulcsszo=' + searchPattern + '&miben=cim'
        cItem['url'] = url
        self.listItems(cItem)
        cItem['url'] = url2
        self.listItems(cItem)
        

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, FilmTar(), True, [])
    