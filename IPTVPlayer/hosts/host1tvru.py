# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs import ph
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, getMPDLinksWithMeta
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib
import datetime
import HTMLParser
###################################################


def gettytul():
    return 'https://1tv.ru/'

class OneTvRu(CBaseHostClass):
 
    def __init__(self):

        CBaseHostClass.__init__(self, {'history':'1TvRu', 'cookie':'1TvRu.cookie'})
        self.MAIN_URL = "https://1tv.ru/"
        self.SHOW_URL = self.MAIN_URL + "shows?all"
        self.NEWS_URL = self.MAIN_URL + "news/issue"
        self.SPORT_URL = self.MAIN_URL + "sport?all"
        self.LIVE_URL = "https://edge2.1internet.tv/dash-live11/streams/1tv/1tvdash.mpd"
        
        self.DEFAULT_ICON_URL = "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a7/1%D0%BA%D0%B0%D0%BD%D0%B0%D0%BB-5.svg/800px-1%D0%BA%D0%B0%D0%BD%D0%B0%D0%BB-5.svg.png"

        self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')        

        #self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.defaultParams = {'header':self.HTTP_HEADER}
        
    def getPage(self, url, addParams = {}, post_data = None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        
        return self.cm.getPage(url, addParams, post_data)

    def getUrlFromJson(self, item):
        res = 0
            
        url_item = ''
        try:
            url_parts = item['mbr'][res]['src'].rsplit('_', 1)
            url_parts1 = url_parts[1].split('.')
            bitrate = url_parts1[0]
            extension = url_parts1[1]
            url_item = "https:" + url_parts[0] + "_," + bitrate + ",." + extension + ".urlset/master.m3u8"
        except IndexError:
            print "Cannot find link for current resolution"

        if not url_item:
            url_item = 'https:' + item['mbr'][res]['src']

        return url_item


    def getLinksForVideo(self, cItem):
        printDBG("1TvRu.getLinksForVideo [%s]" % cItem)
        linksTab=[]
        
        if cItem.get('category','') == 'live':
            #live
            #linksTab.extend(getMPDLinksWithMeta(self.LIVE_URL, False, sortWithMaxBandwidth=999999999))  
            playerUrl = strwithmeta(self.LIVE_URL, {'User-Agent':self.HTTP_HEADER['User-Agent'], 'iptv_proto':'dash'})
            linksTab.extend(getMPDLinksWithMeta(playerUrl, False,sortWithMaxBandwidth=99999999)) 
            
            #linksTab.append({'name': 'mpd', 'url': playerUrl})
        
        url = cItem.get("url","")
        if url:
            
            if ".m3u8" in url:
                linksTab.extend(getDirectM3U8Playlist(url, checkExt=False, variantCheck=True, checkContent=True, sortWithMaxBitrate=99999999))  
            elif ".mpd" in url:
                linksTab.extend(getMPDLinksWithMeta(url, False))  
           
        return linksTab

    def listMainMenu(self, cItem):
        self.addVideo({'category':'live', 'title' : _('Live')})
        MAIN_CAT_TAB = [
                        {'category':'shows', 'title': _('Shows')},
                        {'category':'news', 'title': _('News')},
                        {'category':'sport', 'title': _('Sport')}
                        ]  
        self.listsTab(MAIN_CAT_TAB, cItem)  

    def listShow(self,cItem):
        printDBG('1TvRu - listShow')

        sts, data = self.getPage(self.SHOW_URL)
        
        if not sts:
            return

        # find links
        #<a target="_self" href="/shows/101-vopros-vzroslomu">101 вопрос взрослому</a>
        
        archive = self.cm.ph.getDataBeetwenNodes(data, ('<section','>', 'archive'), '</section>')[1]    
        anchors = self.cm.ph.getAllItemsBeetwenMarkers(archive, '<a', '</a>')
        
        for item in anchors:
            if "/shows/" in item:
                title = self.cleanHtmlStr(item)
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])

                params = dict(cItem)
                params.update({'category': 'show_item', 'title':title, 'url':url})
                #printDBG(str(params))
                self.addDir(params)
    
    def exploreItem(self, cItem):
        printDBG('1TvRu - exploreShowItem %s' % cItem)
        
        if cItem.get("category","") == "news":
            url = self.NEWS_URL
        else:
            url = cItem.get("url", "")
        
        if not url:
            return
            
        sts, data = self.getPage(url)
        
        if not sts:
            return
            
        # find plylist url
        #data-playlist-url="/playlist?admin=false&amp;collection_id=151&amp;single=false&amp;sort=none&amp;video_id=49363"
        
        playlistUrl = self.cm.ph.getSearchGroups(data, '''data-playlist-url=['"]([^'^"]+?)['"]''')[0]
        
        if not playlistUrl:
            return
        
        playlistUrl = self.getFullUrl(playlistUrl)
        
        sts, data = self.getPage(playlistUrl)
        
        if not sts:
            return
            
        try:
            response = json_loads(data)

            for show_item in response:
                matType = show_item.get("material_type","")
                title = show_item.get('title','')
                
                if matType == "video_material" :
                    # video
                    url_item = self.getUrlFromJson(show_item)
                elif matType == "stream_material" :
                    # live stream
                    url_item =  self.LIVE_URL + "?e=%s" % show_item["stream_begin_at"]
                    title = title + " (Livestream)"
                else:
                    url_item = ""
                
                if len(url_item) > 0:
                    
                    icon = show_item.get('poster','')
                    
                    params = dict(cItem)
                    params.update({'title': title, 'icon': icon, 'url': url_item})
                    printDBG(params)
                    self.addVideo(params)
                    
        except:
            printExc()
    
    def listSport(self, cItem):
        printDBG('1TvRu - listSport')
        
        sts, data = self.getPage(self.SPORT_URL)
        
        if not sts:
            return

        # find links
        #<a target="_self" href="/sport/figurnoe-katanie-na-pervom">⛸️ Фигурное катание</a>
        
        archive = self.cm.ph.getDataBeetwenNodes(data, ('<div','>', 'project-sport-menu'), '</div>')[1]    
        anchors = self.cm.ph.getAllItemsBeetwenMarkers(archive, '<a', '</a>')
        
        for item in anchors:
            if "/sport/" in item:
                title = self.cleanHtmlStr(item)
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])

                params = dict(cItem)
                params.update({'category': 'sport_item', 'title':title, 'url':url})
                #printDBG(str(params))
                self.addDir(params)
        
                
    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('1TvRu - handleService start')
        
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        self.informAboutGeoBlockingIfNeeded('IT')

        name     = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode     = self.currItem.get("mode", '')
        subtype  = self.currItem.get("sub-type",'')
        
        printDBG( "handleService: >> name[%s], category[%s] " % (name, category) )
        self.currList = []
        
        #MAIN MENU
        if name == None:
            self.listMainMenu({'name':'category'})
        elif category == "shows":
            self.listShow(self.currItem)
        elif category in ["show_item", "news", "sport_item"]:
            self.exploreItem(self.currItem)
        elif category == "sport":
            self.listSport(self.currItem)
        else:
            printExc()
        
        CBaseHostClass.endHandleService(self, index, refresh)

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, OneTvRu(), True, [])
    
