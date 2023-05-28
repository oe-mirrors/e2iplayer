# -*- coding: utf-8 -*-
# 2023.04.07. WhiteWolf
###################################################
HOST_VERSION = "1.4"
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass 
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
from Plugins.Extensions.IPTVPlayer.libs import ph
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
###################################################
# FOREIGN import
###################################################
import base64
###################################################
def gettytul():
    return 'https://wofvideo.pro/' 

class WOFvideo(CBaseHostClass):
 
    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'wofvideo', 'cookie':'wofvideo.cookie'})
        self.MAIN_URL = 'https://wofvideo.pro/'
        self.DEFAULT_ICON_URL = "https://wofvideo.pro/wp-content/uploads/2022/12/cropped-cropped-cropped-cropped-logo-light-1-1.png"
        self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        
    def getPage(self, url, addParams = {}, post_data = None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)
    
    def getLinksForVideo(self, cItem):
        printDBG("Wofvideo.getLinksForVideo")
        sts, data = self.getPage(cItem['url'])                        
        if not sts:
            return
        encodedurl = self.cm.ph.getDataBeetwenMarkers(data,'<li data-video-source="',',', False) [1]
        url = self.cm.ph.getDataBeetwenMarkers(encodedurl,'encrypt:',"'", False) [1]
        if not url:
            url = self.cm.ph.getDataBeetwenMarkers(encodedurl,"source:'","'", False) [1]
        else:
            url = url.encode('ascii')
            url = base64.b64decode(url)
            url = url.decode("ascii")
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
        printDBG('Wofvideo.listMainMenu')
        MAIN_CAT_TAB = [{'category':'list_filters',            'title': _('Kategóriák')},
                        {'category':'search',          'title': _('Keresés'), 'search_item':True},
                        {'category':'search_history',  'title': _('Keresési előzmények')}]
        self.listsTab(MAIN_CAT_TAB, cItem) 

    def listItems(self, cItem):
        printDBG('Wofvideo.listItems')
        sts, odata = self.getPage(cItem['url'])
        if not sts:
            return
        stop = 0
        film = self.cm.ph.getDataBeetwenMarkers(odata, '<div id="movies-a" class="aa-tb hdd on">', '<nav class="navigation pagination">', False)[1]
        films = self.cm.ph.getAllItemsBeetwenMarkers(film, '<article class="post dfx fcl movies">', '</article>', False)
        for i in films:
            title = self.cm.ph.getDataBeetwenMarkers(i, '<h2 class="entry-title">', '</h2>', False)[1]
            url = self.cm.ph.getDataBeetwenMarkers(i, '<a href="', '"', False)[1]
            icon = self.cm.ph.getDataBeetwenMarkers(i, '" src="', '"', False)[1]
            desc = self.cm.ph.getDataBeetwenMarkers(i, '<span class="vote"><span>', ' </div>', False)[1]
            desc = desc.replace("</span>", " ")
            if 'movies' in url:
                sts, data = self.getPage(url)
                predesc = self.cm.ph.getDataBeetwenMarkers(data, '<div class="description">', '/p', False)[1]
                desc = desc + "\n" + self.cm.ph.getDataBeetwenMarkers(predesc, '<p>', '<', False)[1]
                url = self.cm.ph.getDataBeetwenMarkers(data, 'maxbutton-b1" target="_blank" rel="noopener" href="', '"', False)[1]
                if url:
                    sts, data = self.getPage(url)
                    url = self.cm.ph.getDataBeetwenMarkers(data, "<iframe src='", "'", False)[1]
                    url = url.replace("#", "")
                    url = url.replace("038;", "")
                else:
                    stop = 1
            params = {'category':'seasons','title':title, 'icon': icon , 'url': url, 'desc': desc}
            if not stop:
                if 'series' in url:
                    self.addDir(params)
                else:
                    self.addVideo(params)
            else:
                stop = 0
        if '<div class="nav-links">' in odata:
            next = self.cm.ph.getDataBeetwenMarkers(odata, '<div class="nav-links">', '</nav>', False)[1]
            next = self.cm.ph.getSearchGroups(next, '''href=['"]([^"^']+?)['"].+NEXT''', 1, True)[0]
            params = {'category':'list_items','title':"Következő oldal", 'icon': None, 'url': next}
            self.addDir(params)
    
    def listFilters(self, cItem):
        printDBG('Wofvideo.listFilters')              
        sts, data = self.getPage(self.MAIN_URL)                    
        if not sts:
            return
        cat = self.cm.ph.getDataBeetwenMarkers(data,'<section id="categories-3"','</section>', False)[1]
        cat = self.cm.ph.getAllItemsBeetwenMarkers(cat,'<a href=','/a>', False)
        stop = 0
        for c in cat:
            title = self.cm.ph.getDataBeetwenMarkers(c, '">','<', False) [1]
            if "&amp;" in title:
                title = title.replace("&amp;", "&")
            if "&nbsp;" in title:
                title = title.replace("&nbsp;", " ")
            if "Hírek" in title:
                stop = 1
            page = 1
            icon = None
            url = self.cm.ph.getDataBeetwenMarkers(c, '"','">', False) [1]
            if not stop:
                params = {'category':'list_items','title':title, 'icon': icon , 'url': url, 'page': page}
                self.addDir(params)
            if stop:
                stop = 0
    
    def listSeasons(self, cItem):
        sts, data = self.getPage(cItem['url'])
        desc = self.cm.ph.getDataBeetwenMarkers(data, '<div class="description">', '/p>', False)[1]
        desc = self.cm.ph.getDataBeetwenMarkers(desc, '<p>', '<', False)[1]
        link = self.cm.ph.getDataBeetwenMarkers(data, 'target="_blank" rel="noopener" href="', '"', False)[1]
        if link == "":
            return
        sts, data = self.getPage(link)
        seasons = self.cm.ph.getDataBeetwenMarkers(data, 'IDE A MEGTEKINTÉSHEZ', '<script', False)[1]
        if "2.évad" in seasons:
            seasons = self.cm.ph.getAllItemsBeetwenMarkers(seasons, '<ul>', '</ul>', False)
            for i in seasons:
                title = str(seasons.index(i)+1) + ".évad"
                params = {'category':'list_episodes','title':title, 'icon': cItem['icon'] , 'url': link, 'desc': desc}
                self.addDir(params)
        else:
           title = "1.évad"
           params = {'category':'list_episodes','title':title, 'icon': cItem['icon'] , 'url': link, 'desc': desc}
           self.addDir(params)
    
    def listEpisodes(self, cItem):
        sts, data = self.getPage(cItem['url'])
        episodes = self.cm.ph.getDataBeetwenMarkers(data, cItem['title'], '</ul>', False)[1]
        episodes = self.cm.ph.getAllItemsBeetwenMarkers(episodes, '<a href=', '</a>', False)
        for i in episodes:
            url = self.cm.ph.getDataBeetwenMarkers(i, '"', '"', False)[1]
            sts, data = self.getPage(url)
            url = self.cm.ph.getDataBeetwenMarkers(data, "<iframe src='", "'", False)[1]
            url = url.replace("#", "")
            url = url.replace("038;", "")
            title = self.cm.ph.getDataBeetwenMarkers(i, '<strong>', '</strong>', False)[1]
            params = {'title':title, 'icon': cItem['icon'] , 'url': url, 'desc': cItem['desc']}
            self.addVideo(params)
    
    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('Wofvideo.handleService start')
        
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
            self.listItems(self.currItem)
        elif category == 'list_filters':
            self.listFilters(self.currItem)
        elif category == 'seasons':
            self.listSeasons(self.currItem)
        elif category == 'list_episodes':
            self.listEpisodes(self.currItem)
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
        printDBG("Wofvideo.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        url = 'https://wofvideo.pro/?s=' + searchPattern.replace(" ", "+")
        cItem['url'] = url           
        self.listItems(cItem)

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, WOFvideo(), True, [])
    