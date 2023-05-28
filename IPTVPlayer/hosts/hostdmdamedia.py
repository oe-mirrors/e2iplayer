# -*- coding: utf-8 -*-
# Blindspot - 2023.05.14. 
###################################################
HOST_VERSION = "2.1"
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
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_unquote, urllib_quote_plus
###################################################

###################################################
# FOREIGN import
###################################################
import re
import datetime
import urllib
###################################################

###################################################
# E2 GUI COMPONENTS 
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvmultipleinputbox import IPTVMultipleInputBox
from Screens.MessageBox import MessageBox
###################################################
def gettytul():
    return 'https://dmdamedia.hu' 

class Dmdamedia(CBaseHostClass):
 
    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'dmdamedia', 'cookie':'dmdamedia.cookie'})
        self.MAIN_URL = 'https://dmdamedia.hu'
        self.DEFAULT_ICON_URL = "https://dmdamedia.hu/kepek/dmdamediahu.png"
        self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')        
        self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        
    def getPage(self, url, addParams = {}, post_data = None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)
    
    def getLinksForVideo(self, cItem):
        printDBG("Dmdamedia.getLinksForVideo")
        sts, data = self.getPage(cItem['url'])        
        if not sts:
            return
        share = self.cm.ph.getDataBeetwenMarkers(data,'<div class="beagyazas">','" FRAMEBORDER', False) [1]
        share = share.replace('<iframe src="', '')
        if share != '':
            if 'https:' not in share:
                share = 'https:'+share
        else:
           share = self.cm.ph.getDataBeetwenMarkers(data,'<div class="beagyazas">','" allowfullscreen', False) [1]
           if '<iframe width="640" height="360" frameborder="0" src="' in share:
               share = share.replace('<iframe width="640" height="360" frameborder="0" src="', '')
           share = share.replace('<iframe width="640" height="360" src="', '')
           if share != '':
               if 'https:' not in share:
                   share = 'https:'+share
           else:
              share = self.cm.ph.getDataBeetwenMarkers(data,'<div class="beagyazas">','" scrolling=', False) [1]
              share = share.replace('<iframe src="', '')
              if share != '':
                  if 'https:' not in share:
                      share = 'https:'+share
              else:
                 share = self.cm.ph.getDataBeetwenMarkers(data,'<div class="filmbeagyazas">','" FRAMEBORDER', False) [1]
                 share = share.replace('<iframe src="', '')
                 if share != '':
                     if 'https:' not in share:
                         share = 'https:'+share
                 else:
                    share = self.cm.ph.getDataBeetwenMarkers(data,'<div class="filmbeagyazas">','" allowfullscreen', False) [1]
                    share = share.replace('<iframe width="640" height="360" src="', '')
                    if share != '':
                        if 'https:' not in share:
                            share = 'https:'+share
                    else:
                       share = self.cm.ph.getDataBeetwenMarkers(data,'<div class="filmbeagyazas">','" scrolling=', False) [1]
                       share = share.replace('<iframe src="', '')
                       if 'https:' not in share:
                           share = 'https:'+share
        video = self.cm.ph.getDataBeetwenMarkers(data, '<div class="video">', '</iframe>', False) [1]
        share = self.cm.ph.getDataBeetwenMarkers(video, '<iframe src="', '"', False) [1]
        if 'https:' not in share:
            share = 'https:'+share
        share = " ".join(share.split())
        printDBG(share)
        share = share.replace(' ', '')
        
        printDBG("Dmdamedia.getLinksForVideo url[%s]" % share)
        videoUrls = []
        uri = urlparser.decorateParamsFromUrl(share)
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
        printDBG('Dmdamedia.listMainMenu')
        MAIN_CAT_TAB = [{'category':'list_filters',            'title': _('Kategóriák'), 'desc':'Figyelem: A Videa és Playtube megosztók pillanatnyilag nem támogatottak.', 'url': 'https://dmdamedia.hu/'},
                        {'category':'list_items',            'title': _('Filmek'), 'desc':'Figyelem: A Videa és Playtube megosztók pillanatnyilag nem támogatottak.', 'url': 'https://dmdamedia.hu/film', 'page': '1'},
                        {'category':'list_items',            'title': _('Sorozatok'), 'desc':'Figyelem: A Videa és Playtube megosztók pillanatnyilag nem támogatottak.', 'url': 'https://dmdamedia.hu/', 'page': '1'},
                        {'category':'list_items',            'title': _('Friss'), 'desc':'Figyelem: A Videa és Playtube megosztók pillanatnyilag nem támogatottak.', 'url': 'https://dmdamedia.hu/friss', 'page': '1'},
                        {'category':'search',          'title': _('Keresés'), 'search_item':True},
                        {'category':'search_history',  'title': _('Keresési előzmények')}]
        self.listsTab(MAIN_CAT_TAB, cItem) 
    
    def listFilters(self, cItem):
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        cat = self.cm.ph.getDataBeetwenMarkers(data, '<div id="catlist" class="catmenu">', '</div>', False)[1]
        cats = self.cm.ph.getAllItemsBeetwenMarkers(cat, '<a', '/a>', False)
        for i in cats:
            title = self.cm.ph.getDataBeetwenMarkers(i, '">', '<', False)[1]
            url = self.cm.ph.getDataBeetwenMarkers(i, 'href="', '">', False)[1]
            if "https://dmdamedia.hu" not in url:
                url = "https://dmdamedia.hu" + url
            params = {'category':'list_items','title':title, 'icon': None , 'url': url, 'page': '1'}
            self.addDir(params)
    
    def listItems(self, cItem):
        printDBG('Dmdamedia.listItems')
        url = cItem['url'][0:cItem['url'].index('=')+1] + urllib_quote_plus(cItem['url'][cItem['url'].index('=')+1:])
        page = cItem['page']     
        params = False     
        sts, data = self.getPage(url)                
        if not sts:
            return
        found = self.cm.ph.getAllItemsBeetwenMarkers(data,'<div class="sorozatok">','/></a></div>')
        b = 0
        num = 28*int(page)-28
        for m in found:
            if (b < 28*int(page) or b == 28*int(page)) and (b > num or b == num):
                 title = self.cm.ph.getDataBeetwenMarkers(m, '><h1>','</h1>', False) [1]
                 icon = self.cm.ph.getDataBeetwenMarkers(m, 'data-src="','"', False) [1]
                 if not icon:
                     icon = self.cm.ph.getDataBeetwenMarkers(m, '<img class="poster-load" src="','"', False) [1]
                 icon = "https://dmdamedia.hu" + icon
                 if "https://dmdamedia.hu/" not in icon:
                     icon = icon.replace("https://dmdamedia.hu", "https://dmdamedia.hu/")
                 newurl = self.cm.ph.getDataBeetwenMarkers(m, '<a href="', '"', False) [1]
                 if "https://dmdamedia.eu/" not in newurl:
                     newurl = "https://dmdamedia.hu" + newurl
                 sts, data = self.getPage(newurl)
                 desc = self.cm.ph.getDataBeetwenMarkers(data, "<p>", "</p>", False) [1]
                 params = {'category':'explore_item','title':title, 'icon': icon , 'url': newurl, 'desc': desc}
                 self.addDir(params)
            b = b+1
        if params:
            if 28*int(page) != len(found):
                params = {'category': 'list_items', 'title': "Következő oldal", 'icon': None , 'url': url, 'page': int(page)+1}
                self.addDir(params)
        else:
           msg = 'A megadott kategóriában sajnos nem találtam semmit. Próbáld újra később.'
           ret = self.sessionEx.waitForFinishOpen(MessageBox, msg, type=MessageBox.TYPE_INFO)        
    
    def exploreItemsF(self, cItem, title, icon):
        printDBG('Dmdamedia.exploreItems - Filmek')
        url = 'https://dmdamedia.hu/' 
        self.cim = title
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        meg = self.cm.ph.getAllItemsBeetwenMarkers(data,'<div class="lista">Videómegosztók:','div class="video">')
        mega = self.cm.ph.getAllItemsBeetwenMarkers(data,'<div class="lista">Megosztók - feliratos','div class="video">')
        for m in meg:
            utl = self.cm.ph.getAllItemsBeetwenMarkers(m,'<a class="','</a>')
            printDBG(m)
            for u in utl:
                ult = self.cm.ph.getAllItemsBeetwenMarkers(u,'" a href="','">')
                printDBG(u)
                for i in ult:
                    printDBG(i)
                    i = i.replace('" a href="', '')
                    i = i.replace('">', '')
                    title = self.cim + " - " + i.replace('?a=', '')
                    url = cItem['url'] + i
                    params = {'title': title,  'icon': icon, 'url': url, 'desc': cItem['desc']}
                    self.addVideo(params)
        for o in mega:
            uzl = self.cm.ph.getAllItemsBeetwenMarkers(o,'<a class="','</a>')
            printDBG(o)
            for k in uzl:
                ui = self.cm.ph.getAllItemsBeetwenMarkers(k,'" a href="','">')
                printDBG(k)
                for b in ui:
                    printDBG(b)
                    b = b.replace('" a href="', '')
                    b = b.replace('">', '')
                    title = self.cim + '(' + self.cm.ph.getDataBeetwenMarkers(data, '<div class="infotab-time">','</div>', False) [1] + ')' + " - " + b.replace('?a=', '')
                    url = cItem['url'] + b
                    params = {'title': title,  'icon': icon, 'url': url, 'desc': cItem['desc']}
                    self.addVideo(params)
    
    def exploreItemsS(self, cItem, title, icon):
        printDBG('Dmdamedia.exploreItems - Sorozatok')
        url = 'https://dmdamedia.hu/' 
        self.realtitle = title
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        meg = self.cm.ph.getAllItemsBeetwenMarkers(data,'<div class="season">','</div>')
        for m in meg:
            utl = self.cm.ph.getAllItemsBeetwenMarkers(m,'<a class="evad"','</a>')
            printDBG(m)
            for u in utl:
                ult = self.cm.ph.getAllItemsBeetwenMarkers(u,'href="','">')
                for i in ult:
                    i = i.replace('href="', '')
                    i = i.replace('">', '')
                    title = self.cm.ph.getDataBeetwenMarkers(u,'">','</a>', False) [1] + ".évad"
                    newurl = url.replace("/", "") + i
                    if "https:dmdamedia.hu" in newurl:
                        newurl = newurl.replace("https:", "https://")
                    sts, data = self.getPage(newurl)
                    desc = self.cm.ph.getDataBeetwenMarkers(data, '<p>', '</p>', False)[1]
                    params = {'category':'explore_item', 'title': title,  'icon': icon, 'url': newurl, 'desc':desc}
                    self.addDir(params)
    
    def exploreItemsE(self, cItem, title, icon):
        printDBG('Dmdamedia.exploreItems - Epizódok')
        url = cItem['url']
        sts, data = self.getPage(url)
        if not sts:
            return
        res = self.cm.ph.getAllItemsBeetwenMarkers(data,'<div class="reszek">','</div>')
        for r in res:
            ep = self.cm.ph.getAllItemsBeetwenMarkers(r,'<a class="episode','</a>')
            if ep == '':
                ep = self.cm.ph.getAllItemsBeetwenMarkers(r,'<a class="sub episode','</a>')
            for e in ep:
                fin = self.cm.ph.getAllItemsBeetwenMarkers(e,'" href="','">')
                for f in fin:
                    f = f.replace('" href="', '')
                    f = f.replace('">', '')
                    title = self.cm.ph.getDataBeetwenMarkers(e,'">','</a>', False) [1] + ".rész" + " - " + self.cm.ph.getDataBeetwenMarkers(e,'title="','" href=', False) [1]
                    if "- feliratos rész" not in title:
                        title = title.replace("-", "")
                    if "https://dmdamedia.hu" in f or "https://dmdamedia.eu" in f or "http://dmdamedia.eu" in f or "http://dmdamedia.hu" in f:
                         newurl = f
                    else:
                       newurl = "https://dmdamedia.hu" + f
                    sts, data = self.getPage(newurl)
                    desc = self.cm.ph.getDataBeetwenMarkers(data, '<p style="text-align:left;margin:20px;">', '</p>', False)[1]
                    if not desc:
                        desc = cItem['desc']
                    params = {'category':'explore_item', 'title': title,  'icon': icon, 'url': newurl, 'desc': desc}
                    self.addDir(params)
    
    def exploreItemsEL(self, cItem, title, icon):
        printDBG('Dmdamedia.exploreItems - EpizódLinkek')
        url = cItem['url']
        sts, data = self.getPage(url)
        normurl = url
        meg = self.cm.ph.getAllItemsBeetwenMarkers(data,'<div class="lista">Videómegosztók</div>	','<div class="video">')
        mega = self.cm.ph.getAllItemsBeetwenMarkers(data,'<div class="lista">Megosztók - feliratos</div>	','<div class="video">')
        for m in meg:
            utl = self.cm.ph.getAllItemsBeetwenMarkers(m,'<a class="','</a>')
            printDBG(m)
            for u in utl:
                ult = self.cm.ph.getAllItemsBeetwenMarkers(u,'" a href="','">')
                printDBG(u)
                for i in ult:
                    printDBG(i)
                    i = i.replace('" a href="', '')
                    i = i.replace('">', '')
                    title = self.realtitle + '(' + self.cm.ph.getDataBeetwenMarkers(data, '<div class="infotab-time">','</div>', False) [1] + ')' + " - " + i.replace('?a=', '')
                    url = normurl + i
                    printDBG(url)
                    params = {'title': title,  'icon': icon, 'url': url, 'desc':cItem['desc']}
                    self.addVideo(params)
                    printDBG(params) 
        for e in mega:
            uti = self.cm.ph.getAllItemsBeetwenMarkers(e,'<a class="','</a>')
            printDBG(e)
            for k in uti:
                ukl = self.cm.ph.getAllItemsBeetwenMarkers(k,'" a href="','">')
                printDBG(k)
                for v in ukl:
                    printDBG(v)
                    v = v.replace('" a href="', '')
                    v = v.replace('">', '')
                    title = self.realtitle + '(' + self.cm.ph.getDataBeetwenMarkers(data, '<div class="infotab-time">','</div>', False) [1] + ')' + " - " + v.replace('?a=', '')
                    url = normurl + v
                    printDBG(url)
                    desc = "Tartalom:" + self.cm.ph.getDataBeetwenMarkers(data, '<div class="leiras">','</div>', False) [1]
                    params = {'title': title,  'icon': icon, 'url': url, 'desc':desc}
                    self.addVideo(params)
                    printDBG(params) 
	
    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('Dmdamedia.handleService start')
        
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
        elif category == 'explore_item' and "dmdamedia.eu" in url:
            self.exploreItemsF(self.currItem, title, icon)
        elif category == 'explore_item' and "évad" in title:
            self.exploreItemsE(self.currItem, title, icon)
        elif category == 'explore_item' and "rész" in title:
            self.exploreItemsEL(self.currItem, title, icon)			
        elif category == 'explore_item' and "dmdamedia.hu" in url:
            self.exploreItemsS(self.currItem, title, icon)
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
        printDBG("Dmdamedia.listSearchResult - Filmek cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        printDBG(cItem)
        url = 'https://dmdamedia.hu/film'
        sts, data = self.getPage(url)           
        if not sts:
            return
        searchPattern = urllib_quote_plus(searchPattern)
        found = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="wrap">', "</a></div>")
        point = searchPattern.split()
        for p in point:
            printDBG(p)
            p = p.lower()
            for m in found:
                title = self.cm.ph.getDataBeetwenMarkers(m, '><h1>','</h1>', False) [1]
                titl = title.lower()
                if p in titl:
                     icon = self.cm.ph.getDataBeetwenMarkers(m, 'data-src="','" title', False) [1]
                     cleanurl = url.strip("/film")
                     icon = cleanurl + icon
                     newurl = self.cm.ph.getDataBeetwenMarkers(m, '<a href="', '"><img', False) [1]
                     if "https://dmdamedia.eu/" not in newurl:
                         newurl = "https://dmdamedia.hu" + newurl
                     sts, data = self.getPage(newurl)
                     desc = self.cm.ph.getDataBeetwenMarkers(m, "<p>", "</p>", False) [1]
                     params = {'category':'explore_item','title':title, 'icon': icon , 'url': newurl, 'desc': desc}
                     self.addDir(params)
        printDBG("Dmdamedia.listSearchResult - Sorozatok cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        printDBG(cItem)
        url = 'https://dmdamedia.hu/'	
        sts, data = self.getPage(url)           
        if not sts:
            return
        movies = self.cm.ph.getAllItemsBeetwenMarkers(data,'<div class="sorozatok">','</a></div>')
        point = searchPattern.split()
        for p in point:
            printDBG(p)
            p = p.lower()
            for m in movies:
                title = self.cm.ph.getDataBeetwenMarkers(m, '><h1>','</h1>', False) [1]
                tik = title.lower()				    
                if p in tik:
                     icon = self.cm.ph.getDataBeetwenMarkers(m, 'data-src="','" title', False) [1]
                     icon = url + icon
                     newurl = self.cm.ph.getDataBeetwenMarkers(m, '<a href="', '"><img', False) [1]
                     if "https://dmdamedia.eu/" not in newurl:
                         newurl = "https://dmdamedia.hu" + newurl
                     sts, data = self.getPage(newurl)
                     desc = self.cm.ph.getDataBeetwenMarkers(data, "<p>", "</p>", False) [1]
                     params = {'category':'explore_item','title':title, 'icon': icon , 'url': newurl, 'desc': desc}
                     self.addDir(params)

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Dmdamedia(), True, [])
    