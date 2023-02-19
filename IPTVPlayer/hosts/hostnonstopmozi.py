# -*- coding: utf-8 -*-
###################################################
# 2023-02-15 - modified NonstopMozi
###################################################
HOST_VERSION = "1.3"
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm, GetTmpDir, GetIPTVPlayerVersion, MergeDicts
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
from Plugins.Extensions.IPTVPlayer.libs import ph
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib
import random
import os
import datetime
import time
import zlib
import base64
import traceback
from copy import deepcopy
try:
    import json
except Exception:
    import simplejson as json
from Components.config import config, ConfigText, ConfigYesNo, getConfigListEntry
from Tools.Directories import resolveFilename, fileExists, SCOPE_PLUGINS
from datetime import datetime
from hashlib import sha1
###################################################

def gettytul():
    return 'https://nonstopmozi.com/'

class NonstopMozi(CBaseHostClass):
 
    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'nonstopmozi', 'cookie':'nonstopmozi.cookie'})
        self.DEFAULT_ICON_URL = 'http://www.figyelmeztetes.hu/nonstopmozi_logo.png'
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:68.0) Gecko/20100101 Firefox/68.0'
        self.HEADER = self.cm.getDefaultHeader()
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update( {'X-Requested-With': 'XMLHttpRequest'} )
        self.MAIN_URL = 'https://nonstopmozi.com'
        self.basicurl = 'https://nonstopmozi.com/online-filmek'
        self.defaultParams = {'header':self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}        
    
    def getPage(self, url, addParams = {}, post_data = None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)
    
    def getStringToLowerWithout(self, szoveg):
        szoveg = szoveg.lower()
        szoveg = szoveg.replace('á','a').replace('é','e').replace('í','i').replace('ó','o').replace('ö','o').replace('ő','o').replace('ú','u').replace('ü','u').replace('ű','u')
        return szoveg
        
    def listMainMenu(self, cItem):
        MAIN_CAT_TAB = [ {'category':'list_categories', 'title': _('Filmek')}, 
        {'category':'list_categories', 'title': _('Sorozatok') },
        {'category':'search', 'title': _('Keresés'), 'search_item':True},
        {'category':'search_history', 'title': _('Keresési előzmények')}]
        self.listsTab(MAIN_CAT_TAB, cItem)
        
    def listCategories(self, cItem, title):
        printDBG("Nonstopmozi - listCategories start " + title)
        url = 'https://nonstopmozi.com/online-filmek'
        sts, data = self.cm.getPage(url)
        if not sts: 
            return
        if title == 'Filmek':
            data = self.cm.ph.getDataBeetwenMarkers(data, '<a href="/online-filmek" class="dropdown-toggle', '<div class="clearfix"></div>', False)[1]
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li><a', '/li>')
        if title == 'Sorozatok':
            data = self.cm.ph.getDataBeetwenMarkers(data, '<a href="/online-sorozatok" class="dropdown-toggle', '<div class="clearfix"></div>', False)[1]
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li><a', '/li>')
        for item in data:
            url = self.MAIN_URL + self.cm.ph.getDataBeetwenMarkers(item, 'href="', '" title=', False)[1]
            title = self.cm.ph.getDataBeetwenMarkers(item, '">', '</a', False)[1]
            params = {'category': 'list_items', 'title':title, 'url':url}
            self.addDir(params)
    
    def listItems(self, cItem, title):
        printDBG("Nonstopmozi - listItems start " + title)
        url = cItem['url']
        lasturl = url
        page = cItem.get('page', 1)
        url = url + '/oldal/' + str(page)
        sts, data = self.cm.getPage(url)
        if not sts: 
            return
        Pgntr = self.cm.ph.getDataBeetwenMarkers(data, '<div class="blog-pagenat-wthree">', '</div>')[1]
        if 'Következő' in Pgntr:
            nextPage = True
        else:
            nextPage = False
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, "<div class='col-md-2 w3l-movie-gride-agile'", "div class='clearfix'>")
        for item in data:
            url = self.MAIN_URL + self.cm.ph.getDataBeetwenMarkers(item, 'href="', '">')[1]
            url = url.replace('href="', '')
            url = url.replace('">', '')
            title = self.cm.ph.getDataBeetwenMarkers(item, "movie-text'><h3>", '</h3></div>')[1] + self.cm.ph.getDataBeetwenMarkers(item, "<div class='mid-2'>", "</a>")[1]
            title = title.replace("movie-text'><h3>", "")
            title = title.replace("</h3></div>", "")
            title = title.replace("<div class='mid-2'>", "")
            title = title.replace("</a>", "")
            icon = self.cm.ph.getDataBeetwenMarkers(item, '" src=" ', '" width')[1]
            icon = icon.replace('" src=" ', '')
            icon = icon.replace('" width', '')
            params = {'category': 'explore_item', 'title':title, 'url':url, 'icon':icon}
            self.addDir(params)
        if nextPage:
            params = {'category': 'list_items','title':_("Következő oldal"), 'page':page+1, 'url': lasturl}
            self.addDir(params)
    
    def exploreItem(self, cItem):
        printDBG("Nonstopmozi - exploreItem start " + cItem['title'])
        sts, data = self.cm.getPage(cItem['url'])
        if not sts: 
            return
        share = self.cm.ph.getDataBeetwenMarkers(data, 'div width = "100%">', '</center>', False)[1]
        share = self.cm.ph.getAllItemsBeetwenMarkers(share, "<td style = 'width:10;'></td><td align", "' target='_blank")
        for s in share:
            url = self.MAIN_URL + self.cm.ph.getDataBeetwenMarkers(s, "href='", "' target='_blank", False)[1]
            sts, dat = self.cm.getPage(url)
            if not sts:
                return
            url = self.cm.ph.getDataBeetwenMarkers(dat, "<script>window.location.href = '", "';</script>", False)[1]
            title = self.cm.ph.getDataBeetwenMarkers(data, "<h1 style='font-size:35px; font-weight: bold; padding-bottom:15px; color:black; text-shadow: 0 5px 5px rgb(255,255,255);'>", "</h1></b>", False)[1] + " - " + self.cm.ph.getDataBeetwenMarkers(url, "https://", "/", False)[1]
            desc = "IMDB pontszám: " + self.cm.ph.getDataBeetwenMarkers(data, "</a><strong>", "</strong>", False)[1] + "/10" + "  " + self.cm.ph.getDataBeetwenMarkers(data, "<h4 style='font-size:20px; font-weight: bold; color:black; text-shadow: 2px 2px 3px #FFFFFF;'><p style='font-size: 110%;' itemprop='description'>", "</p>			</h4>", False)[1]
            params = {'title':title, 'url':url, 'icon':cItem['icon'], 'desc':desc}
            self.addVideo(params)
    
    def exploreItems(self, cItem):
        printDBG("Nonstopmozi - exploreItems - Évadok start " + cItem['title'])
        sts, data = self.cm.getPage(cItem['url'])
        if not sts: 
            return
        share = self.cm.ph.getDataBeetwenMarkers(data, "<li style='background-color: #FF8D1B;'", "</ul>", False)[1]
        share = self.cm.ph.getAllItemsBeetwenMarkers(share, "<a href='", "</a></li>")
        for s in share:
            url = self.MAIN_URL + self.cm.ph.getDataBeetwenMarkers(s, "<a href='", "'>", False)[1]
            title = self.cm.ph.getDataBeetwenMarkers(s, "'>", "</a>", False)[1] + ".évad"
            params = {'category': 'explore_item', 'title':title, 'url':url, 'icon':cItem['icon']}
            self.addDir(params)
    
    def exploreItemd(self, cItem):
        printDBG("Nonstopmozi - exploreItems - Epizódok start " + cItem['title'])
        sts, data = self.cm.getPage(cItem['url'])
        if not sts: 
            return
        share = self.cm.ph.getDataBeetwenMarkers(data, '<br><h4 id="b" style="padding-left: 15px;">Epizód:</h4>', "</div>", False)[1]
        share = self.cm.ph.getAllItemsBeetwenMarkers(share, "<a href='", "</a></li>")
        for s in share:
            url = self.MAIN_URL + self.cm.ph.getDataBeetwenMarkers(s, "<a href='", "'>", False)[1]
            title = self.cm.ph.getDataBeetwenMarkers(s, "'>", "</a>", False)[1] + ".epizód"
            params = {'category': 'explore_item', 'title':title, 'url':url, 'icon':cItem['icon']}
            self.addDir(params)
    
    def exploreItema(self, cItem):
        printDBG("Nonstopmozi - exploreItem - Linkek start " + cItem['title'])
        sts, data = self.cm.getPage(cItem['url'])
        if not sts: 
            return
        share = self.cm.ph.getDataBeetwenMarkers(data, 'div width = "100%">', '</center>', False)[1]
        share = self.cm.ph.getAllItemsBeetwenMarkers(share, "<td style = 'width:10;'></td><td align", "' target='_blank")
        for s in share:
            url = self.MAIN_URL + self.cm.ph.getDataBeetwenMarkers(s, "href='", "' target='_blank", False)[1]
            sts, dat = self.cm.getPage(url)
            if not sts:
                return
            url = self.cm.ph.getSearchGroups(data, '''href=['"]([^"^']+?)['"].target''', 1, True)[0]
            title = self.cm.ph.getDataBeetwenMarkers(data, "<h1 style='font-size:35px; font-weight: bold; padding-bottom:15px; color:black; text-shadow: 0 5px 5px rgb(255,255,255);'>", "</h1><b", False)[1] + " - " + self.cm.ph.getDataBeetwenMarkers(url, "https://", "/", False)[1]
            desc = "IMDB pontszám: " + self.cm.ph.getDataBeetwenMarkers(data, "</a><strong>", "</strong>", False)[1] + "/10" + "  " + self.cm.ph.getDataBeetwenMarkers(data, "<h4 style='font-size:20px; font-weight: bold; color:black; text-shadow: 2px 2px 3px #FFFFFF;'><p style='font-size: 110%;' itemprop='description'>", "</p>			</h4>", False)[1]
            params = {'title':title, 'url':url, 'icon':cItem['icon'], 'desc':desc}
            self.addVideo(params)
    
    def _uriIsValid(self, url):
        return '://' in url
    
    def getLinksForVideo(self, cItem):
        printDBG("NonstopMozi.getLinksForVideo url[%s]" % cItem['url'])
        videoUrls = []
        uri = urlparser.decorateParamsFromUrl(cItem['url'])
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
    
    def listSearchResult(self, cItem, searchPattern, searchType):
        uagnt = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:68.0) Gecko/20100101 Firefox/68.0'
        phdre = {'User-Agent':uagnt, 'DNT':'1', 'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Encoding':'gzip, deflate, br', 'Accept-Language':'hu-HU,hu;q=0.8,en-US;q=0.5,en;q=0.3', 'Host':'nonstopmozi.com', 'Upgrade-Insecure-Requests':'1', 'Connection':'keep-alive', 'Content-Type':'application/x-www-form-urlencoded', 'Referer':'https://nonstopmozi.com'}
        phdr = {'header':phdre, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE} 
        krsstr = searchPattern
        krsstr_lnk = self.getStringToLowerWithout(searchPattern.replace(' ', '-'))
        uhe = 'https://nonstopmozi.com/online-filmek/kereses/' + krsstr_lnk
        pstd = {'keres':krsstr, 'submit':'Keresés'}
        sts, data = self.cm.getPage(uhe, phdr, pstd)
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, "<div class='col-md-2 w3l-movie-gride-agile'", "div class='clearfix'>")
        for item in data:
            url = self.MAIN_URL + self.cm.ph.getDataBeetwenMarkers(item, 'href="', '">', False)[1]
            title = self.cm.ph.getDataBeetwenMarkers(item, "movie-text'><h3>", '</h3></div>', False)[1] + self.cm.ph.getDataBeetwenMarkers(item, "<div class='mid-2'>", "</a>", False)[1]
            icon = self.cm.ph.getDataBeetwenMarkers(item, '" src=" ', '" width', False)[1]
            params = {'category': 'explore_item', 'title':title, 'url':url, 'icon':icon}
            self.addDir(params)
    
    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG("Nonstopmozi - handleService start")
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", '')
        url = self.currItem.get("url", '')
        category = self.currItem.get("category", '')
        title = self.currItem.get("title", '')
        self.currList = []
        if name == None:
            self.listMainMenu( {'name':'category'} )
        elif category == 'list_categories':
            self.listCategories(self.currItem, title)
        elif category == 'list_items':
            self.listItems(self.currItem, title)
        elif category == 'explore_item' and "film" in url:
            self.exploreItem(self.currItem)
        elif category == 'explore_item' and "évad" in title:
            self.exploreItemd(self.currItem)
        elif category == 'explore_item' and "epizód" in title:
            self.exploreItema(self.currItem)
        elif category == 'explore_item' and "film" not in url:
            self.exploreItems(self.currItem)
        elif category == "search":
            self.listSearchResult(self.currItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({'name':'history', 'category': 'search', 'tab_id':'', 'tps':'0'}, 'desc', _("Type: "))
        else:
            return
        CBaseHostClass.endHandleService(self, index, refresh)

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, NonstopMozi(), True, [])
        