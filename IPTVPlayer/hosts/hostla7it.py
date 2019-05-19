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
import datetime
import HTMLParser
###################################################


def gettytul():
    return 'http://www.la7.it/'

class La7it(CBaseHostClass):
 
    def __init__(self):

        CBaseHostClass.__init__(self)
        
        self.MAIN_URL = "http://www.la7.it"
        
        self.RIVEDILA7_URL= self.MAIN_URL + "/rivedila7/{0}/{1}"
        # {0} day number (0 today, 1 yesterday and so on) 
        # {1} channel code 'la7' or 'la7d'

        self.PROGRAM_URL= self.MAIN_URL + "/tutti-i-programmi"
        self.LIVE_URL= self.MAIN_URL + "/dirette-tv"
        self.TG_LA7D_URL = "http://tg.la7.it/listing/tgla7d"
        
        self.USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/49.0.2623.110 Safari/537.36"      
        #self.defaultParams = {'header':self.HTTP_HEADER}
        #self.defaultParams = { 'header': {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; rv:17.0) Gecko/20100101 Firefox/17.0'}}
        self.defaultParams = { 'header': {'User-Agent': self.USER_AGENT}}

    def getPage(self, url, addParams = {}, post_data = None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        #printDBG(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    def getFullUrl(self, url):
        if url == "" : return ""
        
        # Add the server to the URL if missing
        if url.find("://") == -1:
            url = self.MAIN_URL + url

        return url

    
    def getLinksForVideo(self, cItem):
        printDBG("La7 getLinksForVideo [%s]" % cItem)
        linksTab=[]
        
        if cItem["category"] == 'live' or cItem["category"] == 'epg_item' :
            url = self.findUrlInPage(cItem["url"])
            linksTab.extend(getDirectM3U8Playlist(strwithmeta(url, {'User-Agent': self.USER_AGENT }), checkExt=False, variantCheck=True, checkContent=True, sortWithMaxBitrate=99999999))  
            
        else:
            printDBG("La7: video form category %s with url %s not handled" % (cItem["category"],cItem["url"]));
            linksTab.append({'url': cItem["url"], 'name': 'link1'})
        
        return linksTab

    def findUrlInPage(self, url):
        url = self.getFullUrl(url)
        link_video=""
        sts, html = self.getPage(url)
        if not sts: return ""
        
        regex1 = "vS = '(.*?)'"
        regex2 = 'm3u8" : "(.*?)"'
        regex3 = 'm3u8: "(.*?)"'
        regex4 = '  <iframe src="(.*?)"'

        if re.findall(regex1, html):
            link_video = re.findall(regex1, html)[0]
        else:
            if re.findall(regex2, html):
                link_video = re.findall(regex2, html)[0]
            elif re.findall(regex3, html):
                link_video = re.findall(regex3, html)[0]
            elif re.findall(regex4, html):
                iframe = re.findall(regex4, html)[0]
                sts, html2 = self.getPage(iframe)
                if not sts: return ""

                if re.findall(regex2, html2):
                    link_video = str("http:") + re.findall(regex2, html2)[0]
        
        return link_video
        

    def listMainMenu(self, cItem):
        self.addVideo({'title': 'Diretta Live la7', 'category':'live', 'url': self.LIVE_URL})
        MAIN_CAT_TAB = [{'category':'tg', 'title': 'Tg e meteo'},
                        {'category':'rivedila7', 'title': 'Rivedi la7'},
                        {'category':'rivedila7d', 'title': 'Rivedi la7d'},
                        {'category':'ondemand', 'title': 'Programmi'}]  
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listReplayDate (self, cItem, ch='rivedila7'):
        printDBG("La7 - start replay/EPG section")

        days = ["Domenica", "Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato"]
        months = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", 
        "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]
    
        epgEndDate = datetime.date.today()

        for n in range(7): 
            day = epgEndDate - datetime.timedelta(days = n)
            day_str = days[int(day.strftime("%w"))] + " " + day.strftime("%d") + " " + months[int(day.strftime("%m"))-1]
            label = 'epg_{0}'.format(n) + ch[6:]
            printDBG(label)
            self.addDir(MergeDicts(cItem, {'category': label, 'title': day_str , 'name': day.strftime("%d-%m-%Y")}))              
    
    def listEPG (self, cItem):
        printDBG("La7 - start replay/EPG section - single day")
        label = cItem["category"]
        day_number = label[4:5]
        ch = label[5:]
        url = self.RIVEDILA7_URL.format(day_number, ch)
        sts, html = self.getPage(url) 
        
        if not sts: return
        
        guida_tv = ph.findall(html, "<div id=\"content_guida_tv\" class=\"contentGuidaTv clearfix\">", "</ul>\n  </div>\n</div>")   
        if len(guida_tv)>0:
            items=ph.findall(guida_tv[0], '<div id="item', ' </div>\n                            </div>')
            for item in items:
                t, orario = ph.find(item,"<div class=\"orario\">", "</div>", flags=0)
                t, desc = ph.find(item,"<div class=\"descrizione\"><p>", "</p>", flags=0)
                # search for icon
                regex_icon="<img src=\"(.*?)\""
                icon = re.findall(regex_icon,item)[0]
                # search for url and title
                try:
                    regex_url="<a href=\"(.*?)\">(.*?)<"
                    url, title = re.findall(regex_url,item)[0]
                    title = "{0} {1}".format(orario,title)
                    self.addVideo(MergeDicts(cItem, {'category': 'epg_item', 'title': title , 'url': url, 'desc': desc, 'icon': icon }))              
                except:
                    regex_title="<div class=\"titolo clearfix\">\n(.*?)</div>"                    
                    title = re.findall(regex_title,item)[0].strip() 
                    title = "{0} {1}".format(orario,title)
                    self.addVideo(MergeDicts(cItem, {'category': 'epg_item_nop', 'title': title , 'url': '', 'desc': "NON DISPONIBILE \n" + desc, 'icon': icon, 'text_color': 'red' }))              
                #printDBG ('La7 add epg item ' + orario + ' ' + title + ' ' + url)
    
    def listPrograms(self,cItem):
        printDBG('La7 - start ondemand list')
        sts, html = self.getPage(self.PROGRAM_URL) 
        if not sts: return
        
        items=ph.findall(html, "<div class=\"itemTuttiProgrammi", "</a></span>")

        for item in items:
            regex_url="<a href=\"(.*?)\">(.*?)<"
            url, title = re.findall(regex_url,item)[0]
            title = HTMLParser.HTMLParser().unescape(title).encode('utf-8')
            try:
                regex_icon="<img src=\"(.*?)\""
                icon = re.findall(regex_icon,item)[0]
                self.addDir(MergeDicts(cItem, {'category': 'program', 'title': title , 'url': url, 'icon': icon }))              
            except:
                self.addDir(MergeDicts(cItem, {'category': 'program', 'title': title , 'url': url}))              

    def listTgMenu (self, cItem):
        printDBG('La7 - start news menu')
        MAIN_CAT_TAB = [{'category':'program', 'title': 'Tg La7', 'url': '/tgla7'},
                        {'category':'program', 'title': 'Tg La7d', 'url': self.TG_LA7D_URL },
                        {'category':'program', 'title': 'Bersaglio mobile', 'url': '/bersaglio-mobile' },
                        {'category':'program', 'title': 'Coffee-break', 'url': '/coffee-break'},
                        {'category':'program', 'title': 'Omnibus', 'url': '/omnibus'},
                        {'category':'program', 'title': 'Meteo La7', 'url': '/meteola7'}]  
        self.listsTab(MAIN_CAT_TAB, cItem)
                
    def showProgram(self, cItem, pagenum=0):
        printDBG('La7 - start ondemand single program list')
        url = self.getFullUrl(cItem["url"] + "/rivedila7")
        
        sts, html = self.getPage(url) 
        if not sts: return

        if pagenum == 0 : 
            # last episode
            try:
                replica = ph.findall(html, "<div class=\"contenitoreUltimaReplica", "<div class=\"clearfix\"></div>")[0]
                regex_icon="<img src=\"(.*?)\""
                icon = re.findall(regex_icon,replica)[0]
                regex_url="<a href=\"(.*?)\""
                url = re.findall(regex_url,replica)[0]
                t, title = ph.find(replica, "<div class=\"title\">", "</div>", flags=0)
                t, data = ph.find(replica, "<div class=\"dataPuntata\">", "</div>", flags=0)
                t, desc = ph.find(replica, "<div class=\"views-field views-field-field-testo-lancio\"><p>", "</", flags=0)
                title = title + " (" + data + ")"
                title = HTMLParser.HTMLParser().unescape(title).encode('utf-8')
                desc = HTMLParser.HTMLParser().unescape(desc).encode('utf-8')
                self.addVideo(MergeDicts(cItem, {'category': 'epg_item', 'title': title , 'url': url, 'icon': icon , 'desc' : desc}))              

            except:
                printDBG("la7 - no last episode video box for program '{0}'".format(cItem["title"]))
        
            # last week episodes
            url = self.getFullUrl(cItem["url"] + "/rivedila7/settimana")
            sts, html = self.getPage(url) 
            if sts:
                try:
                    repliche = ph.findall(html, "<div class=\"itemPuntata", "</span></div>")
                    for replica in repliche:
                            regex_icon="<img.*data-src=\"(.*?)\""
                            icon = re.findall(regex_icon,replica)[0]
                            regex_url="div class=\"title\"><a href=\"(.*?)\">(.*?)</a>"                
                            url, title = re.findall(regex_url,replica)[0]
                            t, data = ph.find(replica, "<div class=\"dataPuntata\">", "</div>", flags=0)
                            t, desc = ph.find(replica, "<div class=\"views-field views-field-field-testo-lancio\">", "</div>", flags=0)
                            title = title + " (" + data + ")"
                            title = HTMLParser.HTMLParser().unescape(title).encode('utf-8')
                            desc = HTMLParser.HTMLParser().unescape(desc).encode('utf-8')
                            self.addVideo(MergeDicts(cItem, {'category': 'epg_item', 'title': title , 'url': url, 'icon': icon , 'desc' : desc}))              
                except:
                    printDBG("la7 - no last week episodes for program '{0}'".format(cItem["title"]))
            else:
                printDBG("la7 - error searching last week episodes for program '{0}'".format(cItem["title"]))
        
        # older episodes
        url = self.getFullUrl(cItem["url"] + "/rivedila7/archivio?page={0}".format(pagenum))
        
        sts, html = self.getPage(url) 
        if not sts: return

        repliche = ph.findall(html, "<div class=\"itemPuntata", "</span></div>")
        for replica in repliche:
                regex_icon="<img.*data-src=\"(.*?)\""
                icon = re.findall(regex_icon,replica)[0]
                regex_url="div class=\"title\"><a href=\"(.*?)\">(.*?)</a>"                
                url, title = re.findall(regex_url,replica)[0]
                t, data = ph.find(replica, "<div class=\"dataPuntata\">", "</div>", flags=0)
                t, desc = ph.find(replica, "<div class=\"views-field views-field-field-testo-lancio\">", "</div>", flags=0)
                title = title + " (" + data + ")"
                title = HTMLParser.HTMLParser().unescape(title).encode('utf-8')
                desc = HTMLParser.HTMLParser().unescape(desc).encode('utf-8')
                self.addVideo(MergeDicts(cItem, {'category': 'epg_item', 'title': title , 'url': url, 'icon': icon , 'desc' : desc}))              
            
        # look for next button in page
        if html.find("<li class=\"pager-next\">") != -1:   
                pagenum = pagenum + 1
                self.addMore(MergeDicts(cItem, {'category': 'program_next', 'title': _('Next page'), 'page_number': pagenum}))              
                
    
    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('La7 handleService start')
        
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        self.informAboutGeoBlockingIfNeeded('IT')
        
        name     = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        
        printDBG( "handleService: >> name[%s], category[%s] " % (name, category) )
        self.currList = []
        
        #MAIN MENU
        if name == None:
            self.listMainMenu({'name':'category'})
        elif category == 'rivedila7' or category == 'rivedila7d':
            self.listReplayDate(self.currItem, category)
        elif category[:3] == 'epg':
            self.listEPG(self.currItem)
        elif category == 'tg':
            self.listTgMenu(self.currItem)
        elif category == 'ondemand':
            self.listPrograms(self.currItem)
        elif category == 'program':
            self.showProgram(self.currItem)
        elif category == 'program_next':
            self.showProgram(self.currItem, self.currItem["page_number"])
        else:
            printExc()
        
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, La7it(), True, [])
    
