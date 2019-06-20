# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs import ph
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib
import HTMLParser
from datetime import datetime, tzinfo
###################################################


def gettytul():
    return 'https://www.pmgsport.it/'

class PmgSport(CBaseHostClass):
 
    def __init__(self):

        CBaseHostClass.__init__(self)

        self.MAIN_URL = "https://www.pmgsport.it/"
        self.DEFAULT_ICON_URL = "https://yt3.ggpht.com/a/AGF-l781bCdM1exHda4m0Ih0VB7phr0EJOPNKxKOnw=s288-mo-c-c0xffffffff-rj-k-no"
        self.MENU_ITEMS={}
        self.defaultParams = {'header': {'User-Agent' : 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.103 Safari/537.36'}}
        
    def getPage(self, url, addParams = {}, post_data = None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    
    def getLinksForVideo(self, cItem):
        printDBG("PmgSport.getLinksForVideo [%s]" % cItem)
        
        linksTab=[]
        
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        
        vm_url = re.findall("<iframe src=['\"](.*?)['\"]", data)
        if len(vm_url) > 0:
            sts, data = self.getPage(vm_url[0])
            if not sts: return linksTab
            
            jdata = re.findall("var settings=\{(.*?)\};", data)
            if len(jdata)>0:
                printDBG("%%%%%%%")
                printDBG(jdata[0])
                jdata_mod = "{" + jdata[0].replace("false","False").replace("true","True") + "}"
                printDBG(jdata_mod)
                jdata = eval(jdata_mod)
                if 'bitrates' in jdata:
                    if 'mp4' in jdata['bitrates']:
                        v = jdata['bitrates']['mp4']
                        if isinstance(v,list):
                            for vv in v:
                                name = re.findall("/([\w-]*?).mp4", vv)
                                linksTab.append({'url': vv, 'name': name[0] })
                        else:
                            name = re.findall("/([\w-]*?).mp4", v)
                            linksTab.append({'url': v, 'name': name[0] })
                            
                    if 'hls' in jdata['bitrates']:
                        v = jdata['bitrates']['hls']
                        if isinstance(v,list): 
                            for vv in v:
                                linksTab.extend(getDirectM3U8Playlist(vv, checkExt=False, variantCheck=True, checkContent=True, sortWithMaxBitrate=99999999))  
                        else:
                            linksTab.extend(getDirectM3U8Playlist(v, checkExt=False, variantCheck=True, checkContent=True, sortWithMaxBitrate=99999999))  
                            
        return linksTab

   
    def listMainMenu(self):
        printDBG("PmgSport.listMainMenu")
        sts, data = self.getPage(self.MAIN_URL)
        if not sts: return
        
        
        menu_h = ph.findall(data, "id=\"ts_menu_topic\"", "<div id=\"ts-mobile-menu\"")
        sport_h = ph.findall(menu_h[0], "<li id=\"menu-item-", "</li>")
        
        topsports=[]
        for s in sport_h:
            url, title = re.findall("<a href=\"(.*?)\">(.*?)</a", s)[0]
            title = HTMLParser.HTMLParser().unescape(title).encode('utf-8')
            topsports.append(title)
            
            self.addDir({'category': 'sport', 'title': title , 'url': url, 'text_color': 'yellow'})              
        
        menu = ph.findall(data, "<ul id=\"menu-main-header\" class=\"main-menu \">", "</ul></nav>")   
        #printDBG(menu[0])
        sports = ph.findall(menu[0],"<li id=\"menu-item-", "</ul>")
                           
        for s in sports:
            items = ph.findall(s, "<li id=\"menu-item-", "</a>")
            url, title = re.findall("<a href=\"(.*?)\">(.*?)</a", items[0])[0]
            title = HTMLParser.HTMLParser().unescape(title).encode('utf-8')
            if not title in topsports:
                self.addDir({'category': 'sport', 'title': title , 'url': url})              

            sport_items=[]
            for i in range(1,len(items)):
                url, title_s = re.findall("<a href=\"(.*?)\">(.*?)</a", items[i])[0]
                title_s = HTMLParser.HTMLParser().unescape(title_s).encode('utf-8')
                sport_items.append({'category': 'sport_subitem', 'title': title_s , 'url': url })
                
            self.MENU_ITEMS[title]=sport_items
        
        #printDBG(str(self.MENU_ITEMS))
    
    def listSportItems(self,cItem):
        printDBG("PmgSport.listMainMenu")
        
        category = self.currItem.get("category", '')
        title     = self.currItem.get("title", '')
        url     = self.currItem.get("url", '')

        if category == 'sport':
            if title in self.MENU_ITEMS:
                for i in self.MENU_ITEMS[title]:
                    self.addDir({'category': 'sport_subitem', 'title': i['title'] , 'url': i['url'] })
                    
        sts, data = self.getPage(url)
        if not sts: return
        
        items = ph.findall(data, "<article ", "</article>")   
        for i in items:
            #printDBG(i)
            #printDBG("%%%%%%%%%%%%%%%%%")
            url, title = re.findall("<h3 class=\"entry-title\" >\n.*<a href=\"(.*?)\">\n(.*?)<i", i)[0]
            title = HTMLParser.HTMLParser().unescape(title).encode('utf-8').strip()
            
            desc = re.findall("div class=\"entry-excerpt\">\n(.*?)</div>", i)[0]
            desc = HTMLParser.HTMLParser().unescape(desc).encode('utf-8').strip()
            
            icon = re.findall("<img class=\"lazy\" data-original=\"(.*?)\"",i)
            if len(icon) > 0:
                icon = icon[0]
            else:
                icon = self.DEFAULT_ICON_URL
            self.addVideo({'title': title , 'url': url, 'desc': desc, 'icon': icon })
            
        next = re.findall("<li><a class=\"next page-numbers\" href=\"(.*?)\"", data)
        if len(next)>0 :
            self.addMore({'category': 'sport_subitem', 'title': _('Next page') , 'url': next[0] })
    
    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('PmgSport.handleService start')
        
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
            self.listMainMenu()
        elif category == 'sport' or category == 'sport_subitem':
            self.listSportItems(self.currItem)
        else:
            printExc()
        
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, PmgSport(), True, [])
   