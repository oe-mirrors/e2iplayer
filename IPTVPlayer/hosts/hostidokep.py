# -*- coding: utf-8 -*-
# 2022.11.24. Blindspot
###################################################
HOST_VERSION = "1.2"
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
    return 'https://www.idokep.hu/idojaras/Budapest' 

class Idokep(CBaseHostClass):
 
    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'idokep', 'cookie':'idokep.cookie'})
        self.MAIN_URL = 'https://www.idokep.hu/idojaras/Budapest'
        self.DEFAULT_ICON_URL = "http://www.blindspot.nhely.hu/Thumbnails/idokep.png"
        self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')        
        self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        
    def getPage(self, url, addParams = {}, post_data = None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)
    
    def getLinksForVideo(self, cItem):
        printDBG("Idokep.getLinksForVideo")
        videoUrls = []
        url = cItem['url']
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
        printDBG('Idokep.listMainMenu')
        MAIN_CAT_TAB = [{'category':'list_static',            'title': _('Előrejelzés')},
                        {'category':'list_filters',            'title': _('Időkép'), 'url': 'https://www.idokep.hu/idokep'},
                        {'category':'list_filters',            'title': _('Hőtérkép'), 'url': 'https://www.idokep.hu/hoterkep'},
                        {'category':'list_filters',            'title': _('Felhőkép'), 'url': 'https://www.idokep.hu/felhokep'},
                        {'category':'list_filters',            'title': _('Radar'), 'url': 'https://www.idokep.hu/radar'},
                        {'category':'list_filters',            'title': _('Kamerák'), 'url': 'https://www.idokep.hu/webkamera'},
                        {'category':'list_album',            'title': _('Képtár'), 'url': 'https://www.idokep.hu/keptar'},
                        {'category':'list_filters',            'title': _('Térképek'), 'url': 'https://www.idokep.hu/idojaras/Budapest'}]
        self.listsTab(MAIN_CAT_TAB, cItem) 
    
    def listKepek(self, cItem):
        printDBG('Idokep.listKepek')              
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="ik album-image-container col-6 col-sm-3 col-md-2 col-lg-2">', '</a>', False)
        for i in data:
            title = self.cm.ph.getDataBeetwenMarkers(i, '<div class="ik image-title">', '</div>', False)[1]
            icon = self.cm.ph.getDataBeetwenMarkers(i, '<img src="', '"', False)[1]
            icon = "https://idokep.hu" + icon
            url = self.cm.ph.getDataBeetwenMarkers(i, '<a href="', '"', False)[1]
            url = "https://idokep.hu" + url
            params = {'category': 'show_pic','title':title, 'icon': icon, 'url': url}
            self.addDir(params)
    
    def showPic(self, cItem):
        printDBG('Idokep.showPic')
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        url = self.cm.ph.getDataBeetwenMarkers(data, '<picture>', '</picture>', False)[1]
        url = self.cm.ph.getDataBeetwenMarkers(url, " src='", "'", False)[1]
        url = "https://idokep.hu" + url
        params = {'title':cItem['title'], 'icon': cItem['icon'], 'url': url}
        self.addPicture(params)
    
    def listAlbum(self, cItem):
        printDBG('Idokep.listAlbum')              
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="ik keptar-album col-6 col-md-4 col-lg-3">', '</a>', False)
        for i in data:
            title = self.cm.ph.getDataBeetwenMarkers(i, '<div class="ik text">', '</div>', False)[1]
            title = title.split()
            if len(title) == 2:
                title = title[0] + ' ' + title[1]
            else:
               title = title[0]
            icon = self.cm.ph.getDataBeetwenMarkers(i, '<img src="', '"', False)[1]
            icon = "https://idokep.hu" + icon
            url = self.cm.ph.getDataBeetwenMarkers(i, '<a href="', '"', False)[1]
            url = "https://idokep.hu" + url
            params = {'category': 'list_pics', 'title':title, 'icon': icon, 'url': url}
            self.addDir(params)
    
    def listRiaszt(self, cItem):
        printDBG('Idokep.listRiaszt')              
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        data = self.cm.ph.getDataBeetwenMarkers(data, 'Riasztás', 'c=c', False)[1]
        list = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="col-12 col-lg-4">', '</p>', False)
        for i in list:
            url = self.cm.ph.getDataBeetwenMarkers(i, '<img src="', '"', False)[1]
            if not url:
                url = self.cm.ph.getDataBeetwenMarkers(i, '<img src=', '"', False)[1]
            url = "https:" + url
            title = self.cm.ph.getDataBeetwenMarkers(i, 'title="', '"', False)[1]
            params = {'title':title, 'icon': url, 'url': url}
            self.addPicture(params)
    
    def listItems(self, cItem):
        printDBG('Idokep.listItems')              
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        backup = False
        if cItem['url'].startswith('https://idokep.eu') or cItem['url'].startswith('https://www.idokep.eu'):
            link = self.cm.ph.getDataBeetwenMarkers(data, '<source src="', '"', False)[1]
            if not link:
                link = self.cm.ph.getDataBeetwenMarkers(data, '<source type="video/mp4" src="', '"', False)[1]
            if link:
                if "https:" not in link and "//" in link:
                    vid = "https:" + link
                    sts, dat = self.getPage(vid)
                    if not sts:
                        vid = vid.replace("https://www.idokep.hu", "https://www.idokep.eu")
                        sts, dat = self.getPage(vid)
                        if not sts:
                            vid = vid.replace("https://www.idokep.eu", "https://www.idokep.hu")
                else:
                   vid = link
                   sts, dat = self.getPage(vid)
                   if not sts:
                       vid = vid.replace("https://www.idokep.hu", "https://www.idokep.eu")
                       sts, dat = self.getPage(vid)
                       if not sts:
                           vid = vid.replace("https://www.idokep.eu", "https://www.idokep.hu")
                if not vid.endswith(".webm"):
                    params = {'title':cItem['title'], 'icon': None , 'url': vid}
                    self.addVideo(params)
            if cItem['picture']:
                link = self.cm.ph.getDataBeetwenMarkers(data, '<img name', '">', False)[1]
                if not link:
                    link = self.cm.ph.getDataBeetwenMarkers(data, '<img id', '">', False)[1]
                    if not link:
                        backup = True
                link = self.cm.ph.getDataBeetwenMarkers(link, 'src="', '"', False)[1]
                if backup == True:
                    link = self.cm.ph.getDataBeetwenMarkers(data, 'autoplay muted loop poster="', '"', False)[1]
                if "https:" not in link and "//" in link:
                    img = "https:" + link
                elif "https://www.idokep.hu" not in link:
                   img = "https://www.idokep.hu" + link
                sts, dat = self.getPage(img)
                if not sts:
                    img = img.replace("https://www.idokep.hu", "https://www.idokep.eu")
                if cItem['url'] == "https://idokep.eu/ceu/hoterkep":
                    img = 'https://www.idokep.eu/terkep/fulleu/eumap.jpg?ca64b'
                sts, dat = self.getPage(img)
                if not img.endswith(".gif") and sts:
                    params = {'title':cItem['title'], 'icon': img, 'url': img}
                    self.addPicture(params)
        elif cItem['url'].startswith('https://idokep.hu') or cItem['url'].startswith('https://www.idokep.hu'):
           link = self.cm.ph.getDataBeetwenMarkers(data, '<source type="video/mp4" src="', '"', False)[1]
           if link:
               if "https:" not in link and "//" in link:
                   vid = "https:" + link
                   sts, dat = self.getPage(vid)
                   if not sts:
                       vid = vid.replace("https://www.idokep.hu", "https://www.idokep.eu")
                       sts, dat = self.getPage(vid)
                       if not sts:
                           vid = vid.replace("https://www.idokep.eu", "https://www.idokep.hu")
               elif "https:" not in link:
                  vid = "https://idokep.hu" + link
               else:
                  vid = link
                  sts, dat = self.getPage(vid)
                  if not sts:
                      vid = vid.replace("https://www.idokep.hu", "https://www.idokep.eu")
                      sts, dat = self.getPage(vid)
                      if not sts:
                          vid = vid.replace("https://www.idokep.eu", "https://www.idokep.hu")
               if not vid.endswith(".webm"):
                   params = {'title':cItem['title'], 'icon': None , 'url': vid}
                   self.addVideo(params)
           if cItem['picture']:
               if cItem['title'] == "Min/max":
                   link1 = self.cm.ph.getDataBeetwenMarkers(data, '<img name="tmax"', '>', False)[1]
                   link2 = self.cm.ph.getDataBeetwenMarkers(data, '<img name="tmin"', '>', False)[1]
                   link1 = self.cm.ph.getDataBeetwenMarkers(link1, 'src="', '"', False)[1]
                   link2 = self.cm.ph.getDataBeetwenMarkers(link2, 'src="', '"', False)[1]
                   img1 = "https://www.idokep.eu" + link1
                   img2 = "https://www.idokep.eu" + link2
                   title2 = "Minimum"
                   title1 = "Maximum"
                   params = {'title':title1, 'icon': img1, 'url': img1}
                   self.addPicture(params)
                   params = {'title':title2, 'icon': img2, 'url': img2}
                   self.addPicture(params)
                   return
               link = self.cm.ph.getDataBeetwenMarkers(data, '<img', '>', False)[1]
               link = self.cm.ph.getDataBeetwenMarkers(link, 'src="', '"', False)[1]
               if "https:" not in link and "//" in link:
                   img = "https:" + link
               elif "https://www.idokep.hu" not in link:
                  img = "https://www.idokep.hu" + link
               sts, dat = self.getPage(img)
               if not sts:
                   img = img.replace("https://www.idokep.hu", "https://www.idokep.eu")
                   if "https://www.idokep.eu" not in img:
                       img = img.replace("https://idokep.hu", "https://idokep.eu")
               sts, dat = self.getPage(img)
               if not img.endswith(".gif") and sts:
                   params = {'title':cItem['title'], 'icon': img, 'url': img}
                   self.addPicture(params)
    
    def listFilters(self, cItem):
        printDBG('Idokep.listFilters')
        picture = True
        sts, data = self.getPage(cItem['url'])
        if cItem['title'] == "Időkép":
            menu = self.cm.ph.getDataBeetwenMarkers(data, 'Időkép</a>', '</ul>', False)[1]
            list = self.cm.ph.getAllItemsBeetwenMarkers(menu, '<li>', '</li>', False)
            list.pop(0)
            list.pop(0)
            list.pop(0)
            for i in list:
                title = self.cm.ph.getDataBeetwenMarkers(i, '">', '</a>', False)[1]
                url = self.cm.ph.getDataBeetwenMarkers(i, '<a href="', '">', False)[1]
                if "https:" not in url and title == 'Magyarország':
                    url = 'https://www.idokep.eu/terkep/hu600/idokep2.jpg'
                    params = {'title':title, 'icon': url , 'url': url}
                    self.addPicture(params)
                else:
                   params = {'category':'list_items','title':title, 'icon': None , 'url': url, 'picture': picture}
                   self.addDir(params)
        elif cItem['title'] == "Hőtérkép":
            menu = self.cm.ph.getDataBeetwenMarkers(data, 'Hőtérkép</a>', '</ul>', False)[1]
            list = self.cm.ph.getAllItemsBeetwenMarkers(menu, '<li>', '</li>', False)
            list.pop(0)
            list.pop(0)
            list.pop(0)
            list.pop(0)
            for i in list:
                title = self.cm.ph.getDataBeetwenMarkers(i, '">', '</a>', False)[1]
                url = self.cm.ph.getDataBeetwenMarkers(i, '<a href="', '">', False)[1]
                if "https:" not in url and title == 'Magyarország':
                    url = 'https://www.idokep.eu/terkep/hu970/hoterkep3.jpg'
                    params = {'title':title, 'icon': url , 'url': url}
                    self.addPicture(params)
                else:
                   params = {'category':'list_items','title':title, 'icon': None , 'url': url, 'picture': picture}
                   self.addDir(params)
        elif cItem['title'] == "Felhőkép":
            menu = self.cm.ph.getDataBeetwenMarkers(data, 'Felhőkép</a>', '</ul>', False)[1]
            list = self.cm.ph.getAllItemsBeetwenMarkers(menu, '<li>', '</li>', False)
            for i in list:
                title = self.cm.ph.getDataBeetwenMarkers(i, '">', '</a>', False)[1]
                url = self.cm.ph.getDataBeetwenMarkers(i, '<a href="', '">', False)[1]
                if "https:" not in url:
                    url = "https://www.idokep.hu" + url
                params = {'category':'list_items','title':title, 'icon': None , 'url': url, 'picture': picture}
                self.addDir(params)
        elif cItem['title'] == "Radar":
            menu = self.cm.ph.getDataBeetwenMarkers(data, 'Radar</a>', '</ul>', False)[1]
            list = self.cm.ph.getAllItemsBeetwenMarkers(menu, '<li>', '</li>', False)
            list.pop(0)
            list.pop(0)
            list.pop(0)
            list.pop(-1)
            for i in list:
                title = self.cm.ph.getDataBeetwenMarkers(i, '">', '</a>', False)[1]
                url = self.cm.ph.getDataBeetwenMarkers(i, '<a href="', '">', False)[1]
                category = 'list_items'
                if list.index(i) == 0:
                    picture = False
                if list.index(i) == 1:
                    category = 'list_riaszt'
                if "https:" not in url:
                    url = "https://www.idokep.hu" + url
                params = {'category':category,'title':title, 'icon': None , 'url': url, 'picture': picture}
                picture = True
                self.addDir(params)
        elif cItem['title'] == "Kamerák":
            menu = self.cm.ph.getDataBeetwenMarkers(data, 'Kamerák</a>', '</ul>', False)[1]
            list = self.cm.ph.getAllItemsBeetwenMarkers(menu, '<li>', '</li>', False)
            for i in list:
                title = self.cm.ph.getDataBeetwenMarkers(i, '">', '</a>', False)[1]
                url = self.cm.ph.getDataBeetwenMarkers(i, '<a href="', '">', False)[1]
                if "https:" not in url:
                    url = "https://www.idokep.hu" + url
                params = {'category':'list_kamera','title':title, 'icon': None , 'url': url, 'picture': picture}
                self.addDir(params)
        elif cItem['title'] == "Térképek":
            url = 'https://www.idokep.hu/radar/sat-hu.mp4'
            title = 'Magyarország műholdképe'
            icon = 'https://www.idokep.hu/radar/sat-hu.jpg'
            params = {'title':title, 'icon': icon , 'url': url}
            self.addVideo(params)
            menu = self.cm.ph.getDataBeetwenMarkers(data, 'Térképek</a>', '</ul>', False)[1]
            list = self.cm.ph.getAllItemsBeetwenMarkers(menu, '<li>', '</li>', False)
            list.pop(-1)
            list.pop(-1)
            list.pop(5)
            for i in list:
                title = self.cm.ph.getDataBeetwenMarkers(i, '">', '</a>', False)[1]
                url = self.cm.ph.getDataBeetwenMarkers(i, '<a href="', '">', False)[1]
                if "https:" not in url:
                    url = "https://www.idokep.hu" + url
                params = {'category':'list_items','title':title, 'icon': None , 'url': url, 'picture': picture}
                self.addDir(params)
        
    def listKamera(self, cItem):
        printDBG('Idokep.listKamera')              
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="ik kamera-ajanlo">', '</a>', False)
        for i in data:
            url = self.cm.ph.getDataBeetwenMarkers(i, '<a href="', '"', False)[1]
            if "https://" not in url:
                url = "https://idokep.hu" + url
            icon = self.cm.ph.getDataBeetwenMarkers(i, '<img src="', '"', False)[1]
            if not icon:
                icon = self.cm.ph.getDataBeetwenMarkers(i, 'muted autoplay loop poster="', '"', False)[1]
                if "https://" not in icon:
                    icon = "https://idokep.hu" + icon
            title = self.cm.ph.getDataBeetwenMarkers(i, '<span>', '</span>', False)[1]
            if title == "":
                title = "Nincs elérhető cím."
            params = {'category':'picture_camera','title':title, 'icon': icon , 'url': url}
            self.addDir(params)
    
    def listPics(self, cItem):
        printDBG('Idokep.listPics')              
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        icon = ''
        data = self.cm.ph.getDataBeetwenMarkers(data, '<div id="camimg"', '</div>', False)[1]
        url = self.cm.ph.getDataBeetwenMarkers(data, '<img src="', '"', False)[1]
        if not url:
            url = self.cm.ph.getDataBeetwenMarkers(data, '<source src="', '"', False)[1]
            icon = self.cm.ph.getDataBeetwenMarkers(data, '<video poster="', '"', False)[1]
            icon = "https:" + icon 
        url = "https:" + url
        if ".m3u8" in url:
            params = {'title':cItem['title'], 'icon': icon, 'url': url}
            self.addVideo(params)
        else:
            params = {'title':cItem['title'], 'icon': url, 'url': url}
            self.addPicture(params)
        
    def listStatic(self, cItem):
        names = ['Előrejelzés holnapra', 'Előrejelzés 2 napra', 'Előrejelzés 3 napra', 'Előrejelzés 4 napra', 'Előrejelzés 5 napra', '14 napos előrejelzés', '30 napos előrejelzés']
        links = ['http://img.wetterkontor.de/karten/ungarn1.jpg', 'http://img.wetterkontor.de/karten/ungarn2.jpg', 'http://img.wetterkontor.de/karten/ungarn3.jpg', 'http://img.wetterkontor.de/karten/ungarn4.jpg', 'http://img.wetterkontor.de/karten/ungarn5.jpg', 'http://2.eumet.hu/homer_de_elemei/image002.png', 'http://esotanc.hu/30napos/30napos.jpg']
        for i in names:
            icon = links[names.index(i)]
            if "14" in i:
                icon = 'http://2.eumet.hu/Eumethu_logo.jpg'
            params = {'title':i, 'icon': icon , 'url': links[names.index(i)]}
            self.addPicture(params)
    
    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('Idokep.handleService start')
        
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
        elif category == 'list_static':
            self.listStatic(self.currItem)
        elif category == 'list_riaszt':
            self.listRiaszt(self.currItem)
        elif category == 'list_kamera':
            self.listKamera(self.currItem)
        elif category == 'picture_camera':
            self.listPics(self.currItem)
        elif category == 'list_album':
            self.listAlbum(self.currItem)
        elif category == 'list_pics':
            self.listKepek(self.currItem)
        elif category == 'show_pic':
            self.showPic(self.currItem)
        else:
            printExc()
        
        CBaseHostClass.endHandleService(self, index, refresh)
     

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Idokep(), True, [])
    