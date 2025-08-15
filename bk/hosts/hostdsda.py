# -*- coding: utf-8 -*-
###################################################
#                 Saracen Knight                  #
#             saracen.knight@mail.ru              #
###################################################
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
###################################################

###################################################
# FOREIGN import
###################################################
import re
import HTMLParser
###################################################

def gettytul():
    return 'https://documentari-streaming-da.com/'

class DSDA(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'DSDA', 'cookie':'DSDA.cookie'})
        
        self.USER_AGENT = 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:68.0) Gecko/20100101 Firefox/68.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'text/html'}
        
        self.MAIN_URL = 'https://documentari-streaming-da.com/'
        self.DEFAULT_ICON_URL = 'https://scontent-mxp1-1.xx.fbcdn.net/v/t1.0-9/56742587_669013310186689_7805148216235655168_n.jpg?_nc_cat=105&_nc_oc=AQljKC8dtD_B28VmidDlC1P1oUdvIyw7Ig-zCqGuD30jdIJMExgm3ct3T6EiwqTRziQ&_nc_ht=scontent-mxp1-1.xx&oh=17a67f50b311538188abd9bb7a2ed366&oe=5DD4BF01'
        
        self.defaultParams = {'header':self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
    

    def getPage(self, baseUrl, addParams = {}, post_data = None):
        printDBG("<<<<<<<<<<<<< DSDA.getPage <<<<<<<<<<<<<<<<<<<<<<")

        sts, data = self.cm.getPage(baseUrl, addParams, post_data)
        return sts, data
    
    def getFullUrl(self, url):
        printDBG("<<<<<<<<<<<<< DSDA.getFullUrl <<<<<<<<<<<<<<<<<<<<<<")
        if url[:1] == "/":
            url = self.MAIN_URL + url[1:]
        #printDBG(url)
        return url        
    
    def listMainMenu(self, cItem):
        printDBG("<<<<<<<<<<<<< DSDA.listMainMenu <<<<<<<<<<<<<<<<<<<<<<")
        printDBG(str(cItem))

        url = cItem.get('url', '')
        printDBG("url<<<<<<<< "+url)
        
        if url == "": 
            url = self.MAIN_URL

        printDBG("url<<<<<<<< "+url)
        sts, data = self.cm.getPage(url)
        if not sts: return        

        cats = re.findall('''has-menu-child"><a href=(.*)</a></li>''', str(data))
        for cat in cats:
            printDBG(str(cat))
            url = re.findall('''"(.*?)"''', cat)[0]
            #title = re.findall('''">(.*?)''', cat)[0]
            title = cat.split('"')[2]
            title = title.replace(">", "")
            liststr = ["Presentazione", "Contatto", "Sostieni DSDA", "Categorie"]

            if title not in liststr:

                if title == "Home":
                    title = "Documentari Ultime uscite"
                    url = self.MAIN_URL+"page/1/?searchtype=movie&post_type=movie&sl=lasts&s#038;post_type=movie&sl=lasts&s"

                params = dict(cItem)
                params.update({'name':'category', 'category':'list_items', 'title':title, 'url':url})
                printDBG(str(params))
                self.addDir(params)


        MAIN_CAT_TAB = [{'category':'search',          'title': _('Search'), 'search_item':True},
                        {'category':'search_history',  'title': _('Search history')} ]
        
        self.listsTab(MAIN_CAT_TAB, cItem)
        

    def listItems(self, cItem, nextCategory):
        printDBG("<<<<<<<<<<<<< DSDA.listItems <<<<<<<<<<<<<<<<<<<<<<")
        printDBG("cItem<<<<< "+str(cItem))
        page = cItem.get('page', 1)

        url = cItem.get('url', '')
        urlnext = url
        title = cItem.get('title', '')
        printDBG("title<<< "+title)

        if (title == "Search") or ("Next page" in title) or (title == "Documentari Ultime uscite"):
            #don't do any think
            searchPattern = cItem.get('searchPattern', '')
            printDBG("searchPattern<<< "+searchPattern)
            printDBG("url<<< "+url)            
            #https://documentari-streaming-da.com/?searchtype=movie&post_type=movie&s=squalo
            #url = "https://documentari-streaming-da.com/?searchtype=movie&post_type=movie&s="+searchPattern
 
        else:
            #https://documentari-streaming-da.com/page/3/?searchtype=movie&post_type=movie&sl=lasts&cat=seminari-e-conferenze&s=
            t = title.replace("Documentari ", "")
            t = t.replace(" ", "-")
            t = t.lower()
            if "serie" in t: t = "series"
            if "raccolte" in t: t = "groups"
            if "societ" in t: t = "societa"
            #t = title.replace("documentari-", "")
            printDBG("page<<< "+str(page))
            url = self.MAIN_URL+"page/"+str(page)+"/?searchtype=movie&post_type=movie&sl=lasts&cat="+t+"&s"
            urlnext = url
            printDBG(url)

        sts, data = self.cm.getPage(url)
        if not sts: return        

        pntemp = re.findall('''<div class="item col-sm-3">(.*?)<span class=''', data, re.S)
        #print (str(pntemp))

        for t in pntemp:
            #print(t)
            icon = re.findall('''src="(.*?)"''', t, re.S)[0]
            url = re.findall('''href="(.*?)"''', t, re.S)[0]
            title = re.findall('''/">(.*?)<\/a><\/h4>''', t)[0]
            title = HTMLParser.HTMLParser().unescape(title).encode('utf-8')
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category':nextCategory, 'title':title, 'url':url, 'icon':icon, 'desc':title})
            printDBG(str(params))
            self.addDir(params)


        #next page
        if "next page-numbers" in data:
            tmp = urlnext.split("/"+str(page))
            printDBG("next page-numbers<<< ")
            printDBG("urlnext<<< "+ urlnext)
            urlnext = tmp[0]+"/"+str(page+1)+tmp[1]
            printDBG("urlnext<<< "+ urlnext)
            params = dict(cItem)
            params.update({'title':_("Next page"), 'page':page+1, 'url': urlnext})
            self.addMore(params)
        
        #titems = 

    def exploreItem(self, cItem):
        printDBG("<<<<<<<<<<<<< DSDA.exploreItem <<<<<<<<<<<<<<<<<<<<<<")
        url = cItem.get('url', '')
        printDBG(url)
        sts, data = self.cm.getPage(url)
        if not sts: return        

        #video link
        d = re.findall('''</div><h2>(.*?)</div>''', data, re.S)[0]
        #printDBG("desc <<<<< "+ d+"\n<<<<<<<<<<<<<<<")
        dd = re.findall('''<p>(.*?)</p>''', data, re.S)
        ddd = ""
        for d in dd:
            d = re.sub('''<(.*?)>''', "", d)
            d = d.replace("<", "")
            d = d.replace(">", "")
            printDBG("d <<< "+d+"<<<")
            ddd = ddd+d+"\n"
        ddd = HTMLParser.HTMLParser().unescape(ddd).encode('utf-8')
        
        desc = re.findall('''<b style="color:#333333;">(.*?)</div>''', data, re.S)[0]
        desc = '''<b style="color:#333333;">'''+desc
        tmp = desc.split("</b></a> <br><br>")
        del tmp[-1]

        for t in tmp:
            t = t+'''</b>'''
            #print (str(t))
            title = re.findall('''>(.*?)</b><br>''', t, re.S)[0]
            title = HTMLParser.HTMLParser().unescape(title).encode('utf-8')
            #print (title)
            names = re.findall('''<b>(.*?)</b>''', t, re.S)
            #print(names)
            vurl = re.findall('''href="(.*?)"''', t, re.S)
            #print(vurl)

            urlTab = []
            i = 0
            for name in names:
                urlTab.append({'name':name, 'url':vurl[i], 'need_resolve':1})
                i = i + 1

            params = dict(cItem)
            params.update({'good_for_fav':False, 'title': title, 'urls_tab':urlTab, 'desc':ddd})
            #params.update({'good_for_fav':False, 'url':url, 'title':'%s %s' % (title, cItem['title'])})
            printDBG(str(params))
            self.addVideo(params)


    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("<<<<<<<<<<<<< DSDA.listSearchResult <<<<<<<<<<<<<<<<<<<<<<")
        printDBG("DSDA.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        #Verify post parrams and config bellow
        #https://documentari-streaming-da.com/?searchtype=movie&post_type=movie&s=squalo
        cItem['url'] = self.MAIN_URL+"?searchtype=movie&post_type=movie&s="+searchPattern
        cItem['category'] = 'list_items'
        self.listItems(cItem, 'explore_item')

    def getLinksForVideo(self, cItem):
        printDBG("<<<<<<<<<<<<< DSDA.getLinksForVideo <<<<<<<<<<<<<<<<<<<<<<")
        printDBG("DSDA.getLinksForVideo [%s]" % cItem)
        if 1 == self.up.checkHostSupport(cItem['url']): 
            return self.up.getVideoLinkExt(cItem['url'])
        return cItem.get('urls_tab', [])


    def getVideoLinks(self, videoUrl):
        printDBG("<<<<<<<<<<<<< DSDA.getVideoLinks <<<<<<<<<<<<<<<<<<<<<<")
        printDBG("DSDA.getVideoLinks [%s]" % videoUrl)
        return  self.up.getVideoLinkExt(videoUrl)

    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG("<<<<<<<<<<<<< DSDA.handleService <<<<<<<<<<<<<<<<<<<<<<")
        printDBG('handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name     = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode     = self.currItem.get("mode", '')
        
        printDBG( "handleService: || name[%s], category[%s] " % (name, category) )
        self.currList = []
        self.currItem = dict(self.currItem)
        self.currItem.pop('good_for_fav', None)
        
        #MAIN MENU
        if name == None:
            self.listMainMenu({'name':'category', 'type':'category'})
        elif category == 'list_items':
            self.listItems(self.currItem, 'explore_item')
        elif category == 'explore_item':
            self.exploreItem(self.currItem)
        #SEARCH
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item':False, 'name':'category'}) 
            self.listSearchResult(cItem, searchPattern, searchType)
        #HISTORIA SEARCH
        elif category == "search_history":
            self.listsHistory({'name':'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()

        printDBG('handleService end')
        CBaseHostClass.endHandleService(self, index, refresh)

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, DSDA(), True, favouriteTypes=[]) 
