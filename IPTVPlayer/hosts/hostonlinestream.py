# -*- coding: utf-8 -*-
# 2022.07.15. Blindspot
###################################################
HOST_VERSION = "1.4"
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

###################################################
# E2 GUI COMPONENTS 
###################################################
from Screens.MessageBox import MessageBox
###################################################

def gettytul():
    return 'https://onlinestream.live/' 

class OnlineStream(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'onlinestream', 'cookie':'onlinestream.cookie'})
        self.MAIN_URL = 'https://onlinestream.live/'
        self.DEFAULT_ICON_URL = "http://blindspot.nhely.hu/Thumbnails/onlinestream.jpg"
        self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')        
        self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        
    def getPage(self, url, addParams = {}, post_data = None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)
    
    def _uriIsValid(self, url):
        return '://' in url
    
    def _isPicture(self, url):
        def _checkExtension(url):
            return url.endswith(".jpeg") or url.endswith(".jpg") or url.endswith(".png") or url.endswith(".mjpg") or url.endswith(".cgi")
        if _checkExtension(url):
            return True
        if _checkExtension(url.split('|')[0]):
            return True
        if _checkExtension(url.split('?')[0]):
            return True
        return False
    
    def getLinksForVideo(self, cItem):
        printDBG('OnlineStream.getLinksForVideo')
        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return
        videoUrls = []
        dat = self.cm.ph.getDataBeetwenMarkers(data, '<li><a target="_blank" href="', '">', False) [1]
        if dat == "":
            dat = self.cm.ph.getDataBeetwenMarkers(data, '<li><a href="', '">', False) [1]
            dat = "https://onlinestream.live" + dat
            sts, data = self.cm.getPage(dat)
            if not sts:
                return
            dat = self.cm.ph.getDataBeetwenMarkers(data, "https://", "m3u8")[1]
        if cItem['title'] == 'M3':
            url = "https://archivum.mtva.hu/api/m3/v3/stream?target=live"
            sts, data = self.cm.getPage(url)
            dat = self.cm.ph.getDataBeetwenMarkers(data, '"url":"', '","', False)[1]
            dat = dat.replace('\/', '/').replace("HLS.smil", "nodrm.smil")
        if self._isPicture(dat):
            dat = dat.replace("mjpg", "jpg")
            dat = dat.replace("video", "image")
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
           elif dat.endswith(".jpg"):
                uri = urlparser.decorateParamsFromUrl(dat, True)
                videoUrls.append({'name':'picture link', 'url':uri})
           else:
              videoUrls.append({'name':'direct link', 'url':uri})
        return videoUrls
    
    def listMainMenu(self, cItem):   
        printDBG('OnlineStream.listMainMenu')
        page = 1
        MAIN_CAT_TAB = [{'category':'list_items',            'title': _('Sugárzó rádiók listázása'), 'url':'https://onlinestream.live/main.cgi?search=&broad=1&feat=&chtype=&server=&format=&sort=listen&fp=20&p=', 'page': page},
                        {'category':'list_items',            'title': _('Internetes rádiók listázása'), 'url':'https://onlinestream.live/main.cgi?search=&broad=0&feat=&chtype=&server=&format=&sort=listen&fp=20&p=', 'page': page},
                        {'category':'list_items',            'title': _('TV-k listázása'), 'url':'https://onlinestream.live/?search=&broad=7&feat=&chtype=&server=&format=&sort=listenpeak&fp=20&p=', 'page': page},
                        {'category':'list_items',            'title': _('Webkamerák listázása'), 'url':'https://onlinestream.live/?search=&broad=4&feat=&chtype=&server=&format=&sort=&fp=20&p=', 'page': page},
                        {'category':'search',          'title': _('Keresés'), 'search_item':True},
                        {'category':'search_history',  'title': _('Keresési előzmények')}]
        self.listsTab(MAIN_CAT_TAB, cItem) 
        
    def listItems(self, cItem):
        printDBG('OnlineStream.listItems')    
        sts, dat = self.getPage(cItem['url'] + str(cItem['page']))
        if not sts:
            return
        page = cItem['page']
        web = self.cm.ph.getDataBeetwenMarkers(dat, '>Lejátszás</th>','<span class="glyphicon glyphicon-chevron-left">', False)[1]
        web = str(web)
        listurl = self.cm.ph.getAllItemsBeetwenMarkers(web, 'href="', '"', False)
        for i in listurl:
            if 'online' not in i:
                listurl.remove(i)
        listurls = []
        listitle = []
        for a in listurl:
            if "https://onlinestream.live" not in a:
                a = "https://onlinestream.live" + a
            test = self.cm.ph.getDataBeetwenMarkers(a, "https://onlinestream.live/", "/online", False)[1]
            if test not in listitle:
                listurls.append(a)
                listitle.append(test)
        listurl = listurls
        listurl.pop(0)
        for i in listurl:
            sts, data = self.getPage(i)
            if not sts:
                return
            inf = self.cm.ph.getDataBeetwenMarkers(data, 'Állomás általános információi', 'Állapot:')[1]
            title = self.cm.ph.getDataBeetwenMarkers(inf, 'Név:</td><th>', '</th></tr>', False)[1]
            url = i
            icon = self.cm.ph.getDataBeetwenMarkers(inf, 'src="', '"', False)[1]
            if "https://onlinestream.live" not in icon:
                icon = "https://onlinestream.live" + icon
            if icon == 'https://onlinestream.live':
                icon = None
            desc = self.cm.ph.getDataBeetwenMarkers(inf, 'Leírás, szlogen:</td><th>', '</th></tr>', False)[1]
            printDBG(str(desc))
            descs = self.cm.ph.getDataBeetwenMarkers(data, 'Műsorlista (utolsó 10)', 'Mégtöbb műsor visszamenőleg', False)[1]
            desctime = self.cm.ph.getAllItemsBeetwenMarkers(descs, '<span class="badge">', '</span>', False)
            descstr = self.cm.ph.getAllItemsBeetwenMarkers(descs, '<div class="info_tracklist_szamcim">', '</div>', False)
            odesc = ""
            if desc:
                odesc = desc
                desc = desc + "\n" + "Műsorlista (utolsó 10):"
            else:
               desc = "Műsorlista (utolsó 10):"
            for i in descstr:
                if i == "":
                   descstr[descstr.index(i)] = "Jelenleg nem elérhető a műsortartalom."
            for i in desctime:
                desc = str(desc) + "\n" + str(i) + "   " + str(descstr[desctime.index(i)])
            if desc == odesc + "\n" + "Műsorlista (utolsó 10):":
                desc = odesc
            if desc == "Műsorlista (utolsó 10):":
                desc = "Jelenleg nincs elérhető információ."
            if title == "":
                title = "Névtelen"
            params = {'category':'list_more','title':title, 'icon': icon , 'url': url, 'desc': desc}
            self.addDir(params)
        if '<li class="disabled"><a><span class="glyphicon glyphicon-chevron-right">' not in dat:
            params = {'category': 'list_items', 'title': "Következő oldal", 'icon': None , 'url': cItem['url'], 'page': page+1}
            self.addDir(params)
    
    def exploreItems(self, cItem):
        printDBG('OnlineStream.exploreItems')    
        sts, dat = self.getPage(cItem['url'])
        if not sts:
            return
        data = self.cm.ph.getDataBeetwenMarkers(dat, '<div class="dropdown info_csatornalista_select">', '</a></li></ul></div></div>')[1]
        printDBG("data " + str(data))
        if '<a class="ajax_link" href="' not in str(data):
            params = {'title': cItem['title'], 'icon': cItem['icon'] , 'url': cItem['url'], 'desc': cItem['desc'], 'type': None}
            sts, data = self.cm.getPage(cItem['url'])
            type = self.cm.ph.getDataBeetwenMarkers(data, '<title>', '</title>', False)[1]
            if "Online rádió" in type:
                self.addAudio(params)
            elif 'MJPEG' in data:
               params.update({'desc':cItem['desc'] + "\n" + "Az OK gomb lenyomásával a kép automatikusan frissül!"})
               self.addPicture(params)
            else:
               self.addVideo(params)
            return
        urllist = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a class="ajax_link" href="', '"', False)
        printDBG("urllist " + str(urllist))
        help = self.cm.ph.getAllItemsBeetwenMarkers(data, 'data-ajax_link="', '">')
        printDBG("help " + str(help))
        for i in urllist:
            url = "https://onlinestream.live" + i
            printDBG("url " + url)
            title = self.cm.ph.getDataBeetwenMarkers(data,  help[urllist.index(i)], '</a>', False)[1]
            printDBG("title " + title)
            title = title.replace('&nbsp;', '')
            printDBG("title " + title)
            params = {'title': title, 'icon': cItem['icon'] , 'url': url,'desc': cItem['desc']}
            type = self.cm.ph.getDataBeetwenMarkers(dat, '<title>', '</title>', False)[1]
            if "Online rádió" in type:
                self.addAudio(params)
            else:
               self.addVideo(params)
    
    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('OnlineStream.handleService start')
        
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
        elif category == 'list_more':
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
        printDBG("FilmVilag.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        searchPattern = searchPattern.replace(" ", "+")
        url = 'https://onlinestream.live/?search=' + searchPattern + '&broad=&feat=&chtype=&server=&format=&sort=&fp=20&p='
        cItem['url'] = url
        cItem['page'] = 1
        self.listItems(cItem)

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, OnlineStream(), True, [])
    