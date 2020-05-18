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
try:    import json
except Exception: import simplejson as json
###################################################

def gettytul():
    return 'https://www.cb01.run/'

class Cb01(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'cb01.run', 'cookie':'cb01.run.cookie'})
        
        self.USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update( {'X-Requested-With':'XMLHttpRequest', 'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8'} )
        
        self.MAIN_URL = 'https://www.cb01.run/'
        self.DEFAULT_ICON_URL = 'https://www.yourlifeupdated.net/wp-content/uploads/2019/04/Cineblog01.jpg'
        
        self.defaultParams = {'header':self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
    
    def getPage(self, baseUrl, addParams = {}, post_data = None):
        printDBG("<<<<<<<<<<<<< CB01.getPage <<<<<<<<<<<<<<<<<<<<<<")
        if addParams == {}:
            addParams = dict(self.defaultParams)
        
        addParams['cloudflare_params'] = {'domain':'cb01.run', 'cookie_file':self.COOKIE_FILE, 'User-Agent':self.USER_AGENT}
        printDBG("<<<<< post_data: "+str(post_data))
        printDBG("<<<<< baseUrl: "+str(baseUrl))
        printDBG("<<<<< addParams: "+str(addParams))
        printDBG("<<<<< self: "+str(self))

        #addParams['cloudflare_params'] = {'domain':self.up.getDomain(baseUrl), 'cookie_file':self.COOKIE_FILE, 'User-Agent':self.USER_AGENT, 'full_url_handle':self.MAIN_URL}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)
    
    def getFullUrl(self, url):
        if url[:1] == "/":
            url = self.MAIN_URL + url[1:]
        return url        
    
    def listMainMenu(self, cItem):
        printDBG("<<<<<<<<<<<<<<<<<<<<<<<<<<< CB01.listMainMenu <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<")

        sts, data = self.getPage(self.getMainUrl())
        printDBG("<<<<<<<<<<<<<<< data ")
        printDBG(str(data))

        if not sts: 
            return
        self.setMainUrl(self.cm.meta['url'])

        tmp = self.cm.ph.getDataBeetwenNodes(data, '<ul class="nav navbar-nav"', '</ul>', False)[1]
        items = re.findall("<li>(.*?)</li>", tmp)
        printDBG(str(items))
        for item in items:
            url = self.getFullUrl(re.findall("href=['\"]([^\"^']+?)['\"]", item)[0] )
            
            title = self.cleanHtmlStr(item).decode('UTF-8').lower().encode('UTF-8')
            if title in ["richieste", "dmca"]:
                continue
            title = title[:1].upper() + title[1:]
            params = dict(cItem)
            params.update({'category':'list_items', 'title':title, 'url':url})
            printDBG(str(params))
            self.addDir(params)

        
        tmp = re.findall("<div id=\"category-menu\" class=\"container\"((.|\n)*?)</div>", data)[0]
        #tmp = self.cm.ph.getDataBeetwenNodes(data, '<div id="category-menu" class="container">', '</div>', False)[0]
        printDBG(str(tmp))
        
        items = re.findall("<div class=\"col-md-3\">((.|\n)*?)</div>", tmp[0] )
        printDBG(str(items))
        tabs=[]    
        for i in items:
            main_cat = re.findall("Cat\" id=\"(.*?)\">", i[0])[0]
            sub_items = re.findall("<li>(.*?)</li>", i[0] ) 

            categories = []

            for si in sub_items:
                url = self.getFullUrl(re.findall("href=['\"]([^\"^']+?)['\"]", si)[0] )
                title = self.cleanHtmlStr(si)
                params = dict(cItem)
                params.update({'name':'category', 'category':'list_items', 'title':title, 'url':url})
                categories.append(params)
                
            if len(categories):
                params = dict(cItem)
                params.update({'name':'category', 'category':'sub_items', 'title': main_cat , 'sub_items':categories})
                tabs.append(params)

        if len(tabs):
            params = dict(cItem)
            params.update({'category':'sub_items', 'title': _('Categories'), 'sub_items':tabs})
            self.addDir(params)

        # Film per ....
        tmp = re.findall('''<select class="form-control">(.*?)</select>''', data, re.S)
        for tmp2 in tmp:
            tmp3 = re.findall('''<option(.*?)option>''', tmp2, re.S)[0]
            title = re.findall('''">(.*?)</''', tmp3, re.S)[0]
            print (title)
            params = dict(cItem)
            params.update({'category':'explore_category', 'title':title})
            self.addDir(params)

        # Search 
        MAIN_CAT_TAB = [{'category':'search',          'title': _('Search'), 'search_item':True},
                        {'category':'search_history',  'title': _('Search history')} ]
        
        self.listsTab(MAIN_CAT_TAB, cItem)
        
    def listItems(self, cItem, nextCategory):
        printDBG("<<<<<<<<<<<<<<<< CB01.listItems <<<<<<<<<<<<<<<<<<<<<<<<<")
        printDBG("<<<<<<<<<< print cItem <<<<<<<<<<<<<<<<<<")
        printDBG(str(cItem))
        printDBG("<<<<<<<<<< fine cItem <<<<<<<<<<<<<<<<<<\n") 
        page = cItem.get('page', 1)
        postData = cItem.get('post_data')

#<<<<<<<<<< print cItem <<<<<<<<<<<<<<<<<<
#{'category': 'list_items', 'name': 'category', 'title': 'Search', 'url': 'https://cb01.run/', 
#'post_data': {'do': 'search', 'story': 'pirati', 'titleonly': '3', 'subaction': 'search'}, 'type': 'category', 'search_item': False}

        sts, data = self.getPage(cItem['url'], post_data=postData)
        if not sts: return
        self.setMainUrl(self.cm.meta['url'])
        
        """
        if postData != None:
            printDBG("Fatta una ricerca!!")
            movies = data.split("<div class=\"box\">")
        else:
            printDBG("Non fatta una ricerca!!")
            if cItem['url'][-15:] == '/piu-visti.html':
                tmp = re.findall("<div id='dle-content'>((.|\n)*?)</section>", data)[0][0]
            else:
                tmp = re.findall('''<div class="col-md-4">(.*?)</div>''', data, re.S)
        """           
        printDBG("<<<<<<<<<< print data <<<<<<<<<<<<<<<<<<")
        printDBG(str(data))
        printDBG("<<<<<<<<<< fine data <<<<<<<<<<<<<<<<<<")
        movies = re.findall('''<div class="col-md-4">(.*?)</div>''', data, re.S)
        movies2 = re.findall('''<div class="col-md-8">(.*?)</div>''', data, re.S)
        del movies2[0]
        del movies2[0]

        i = 0
        for m in movies:
            if "sidebar-box" in m:
                continue
            printDBG("<<<<<<<<<< print m <<<<<<<<<<<<<<<<<<")
            printDBG(str(m)) 
            printDBG("<<<<<<<<<<<<<<<<<<<<<")
            #printDBG("movies2 <<<<<<<<<<\n"+str(movies2[i])
            #regx = '''<h1>(.*?)</h1>'''###title of the movie
            t = re.findall('''<h1>(.*?)</h1>''',str(movies2[i]), re.M|re.I)[0]
            t = re.sub('''\[(.*?)\] ''', "", t)
            printDBG('title: '+str(t))
            title = self.cleanHtmlStr(t)
            printDBG(str(t))
            url   = self.getFullUrl( self.cm.ph.getSearchGroups(str(m), '''href=['"]([^"^']+?)['"]''')[0] )
            printDBG(str(url))  
            icon = self.getFullUrl(re.findall("img src=\"(.*?)\"", str(m), re.M|re.I)[0])
            printDBG(str(icon))
            regx = '''<p>(.*?)</p>'''###title of the movie
            title2 = self.cleanHtmlStr(re.findall('''<h1>(.*?)</h1>''',str(movies2[i]), re.M|re.I)[0])            
            des1 = re.findall('''>(.*?)</h2>''',str(movies2[i]), re.M|re.I)[0]            
            des = re.findall(regx,str(movies2[i]), re.M|re.I)[0]
            desc = self.cleanHtmlStr(title2+"\n"+des1+"\n"+des)
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category':nextCategory, 'title':title, 'url':url, 'icon':icon, 'desc':desc})
            self.addDir(params)
            i = i +1


        #mext page
        try:
            #if there are next page:

            pntemp = re.findall('''<div class="page_numbers">(.*?)</div>''', data, re.S)[0]
            pntemp = re.findall('''<span>[0-9]</span>''', pntemp, re.S)[0]
            pntemp = re.findall('''[0-9]''', pntemp, re.S)[0]
            params = dict(cItem)
            printDBG(str(params))

            if pntemp == "1":
                url = str(cItem['url'])+"page/2/"
            else:
                url = str(cItem['url'])
                url = url[:-2]
                url = url+str(int(pntemp)+1)+"/"

            params.update({'title':_("Next page"), 'page':page+1, 'url': url})
            self.addMore(params)
        
        except IndexError:
            printDBG("<<<<<<<<<< Next Page Not Exist")

    def exploreCategory(self, cItem):
        printDBG("<<<<<<<<<< CB01.exploreCategory <<<<<<<<<<")
        printDBG("cItem <<<<<<\n"+str(cItem))

        sts, data = self.getPage(self.MAIN_URL)
        if not sts: return

        cat = cItem.get('title', '')
        printDBG("category <<<<<<\n"+str(cat))

        tmp = re.findall('''<select class="form-control">(.*?)</select>''', data, re.S)
        printDBG("<<<<<<<<<< cat :"+cat)
        for tmp2 in tmp:
            printDBG(">>>>>> tmp2 "+tmp2)
            if cat in tmp2:
                tmp3 = tmp2

        tmp4 = re.findall('''<option(.*?)option>''', tmp3, re.S)
        del tmp4[0]
        for t in tmp4:

            title = re.findall('''">(.*?)</''', t, re.S)[0]
            url = re.findall('''"(.*?)"''', t, re.S)[0]
            printDBG (title)
            printDBG(url)
            params = dict(cItem)
            params.update({'category':'list_items', 'title':title, 'url':self.getFullUrl(url)})
            printDBG(str(params))
            self.addDir(params)


    def exploreItem(self, cItem):
        printDBG("<<<<<<<<<< CB01.exploreItem <<<<<<<<<<")
        printDBG("cItem <<<<<<\n"+str(cItem))

        sts, data = self.getPage(cItem['url'])
        if not sts: return
        self.setMainUrl(self.cm.meta['url'])
        
        cItem = dict(cItem)
        cItem['prev_url'] = cItem['url']

        #trailer
        trailer = self.cm.ph.getDataBeetwenNodes(data, '<p>Guarda il Trailer:</p>', ('</div', '>'), False)[1]
        url = "https:"+self.cm.ph.getSearchGroups(trailer, '''src=['"]([^"^']+?)['"]''', 1, True)[0]
        printDBG("url <<<<<<  "+str(url))
        if self.cm.isValidUrl(url):
            title = "Trailer"
            params = dict(cItem)
            params.update({'good_for_fav':False, 'url':url, 'title':'%s %s' % (title, cItem['title'])})
            self.addVideo(params)
 
        #video link
        urlTab = []
        temp = re.findall('''div role="tabpanel" class="tab-pane fade"(.*?)</div>''', data, re.S)
        printDBG("<<<<<<<< temp "+str(temp))

        for tt in temp:
            printDBG("tt <<<<<<  "+str(tt))
            url = "https:"+self.cm.ph.getSearchGroups(tt, '''src=['"]([^"^']+?)['"]''', 1, True)[0]
            printDBG("url <<<<<<  "+str(url))
            name = re.findall('''id="(.*?)"''', tt, re.S)[0]
            printDBG("name <<<<<<  "+str(name))
            url = strwithmeta(url, {'Referer':cItem['url']})
            urlTab.append({'name':name, 'url':url, 'need_resolve':1})

        if len(urlTab):
            params = dict(cItem)
            params.update({'good_for_fav':False, 'urls_tab':urlTab})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("CB01.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        #Verify post parrams and config bellow
        cItem['url'] = self.MAIN_URL
        cItem['post_data'] = {'do':'search', 'subaction':'search', 'story':searchPattern}
        cItem['category'] = 'list_items'
        self.listItems(cItem, 'explore_item')

    def getLinksForVideo(self, cItem):
        printDBG("CB01.getLinksForVideo [%s]" % cItem)
        if 1 == self.up.checkHostSupport(cItem['url']): 
            return self.up.getVideoLinkExt(cItem['url'])
        return cItem.get('urls_tab', [])

    def getVideoLinks(self, videoUrl):
        printDBG("CB01.getVideoLinks [%s]" % videoUrl)
        return  self.up.getVideoLinkExt(videoUrl)

    def getArticleContent(self, cItem):
        printDBG("CB01.getVideoLinks [%s]" % cItem)
        retTab = []
        itemsList = []
        
        if 'prev_url' in cItem: url = cItem['prev_url']
        else: url = cItem['url']

        sts, data = self.cm.getPage(url)
        if not sts: return

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 's_left'), ('<div', '>', 'comment'), False)[1]
        
        icon = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'imagen'), ('</div', '>'), False)[1]
        icon = self.getFullUrl( self.cm.ph.getSearchGroups(icon, '''<img[^>]+?src=['"]([^'^"]+?)['"]''')[0] )
        title = self.cleanHtmlStr( self.cm.ph.getDataBeetwenNodes(data, ('<p', '>', 'title'), ('</p', '>'), False)[1] )
        desc = self.cleanHtmlStr( self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'entry-content'), ('</div', '>'), False)[1] )

        tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<p', '>', 'meta_dd'), ('</p', '>'), False)
        for item in tmp:
            if 'title' in item:
                item = [self.cm.ph.getSearchGroups(item, '''title=['"]([^'^"]+?)['"]''')[0], item]
            else:
                item = item.split('</b>', 1)
                if len(item) < 2: continue
            key = self.cleanHtmlStr(item[0])
            val = self.cleanHtmlStr(item[1])
            if key == '' or val == '': continue
            itemsList.append((key, val))

        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<span', '>', 'dato'), ('</span', '>'), False)[1])
        if tmp != '': itemsList.append((_('Rating'), tmp))

        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<p', '>', 'views'), ('</p', '>'), False)[1])
        if tmp != '': itemsList.append((_('Views'), tmp))
        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<p', '>', 'date'), ('</p', '>'), False)[1])
        if tmp != '': itemsList.append((_('Relese'), tmp))

        if title == '': title = cItem['title']
        if icon == '':  icon  = cItem.get('icon', self.DEFAULT_ICON_URL)
        if desc == '':  desc  = cItem.get('desc', '')
        
        return [{'title':self.cleanHtmlStr( title ), 'text': self.cleanHtmlStr( desc ), 'images':[{'title':'', 'url':self.getFullUrl(icon)}], 'other_info':{'custom_items_list':itemsList}}]

    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
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
        elif category == 'sub_items':
            self.currList = self.currItem.get('sub_items', [])
        elif category == 'explore_category':
            self.exploreCategory(self.currItem)
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
        
        CBaseHostClass.endHandleService(self, index, refresh)

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Cb01(), True, favouriteTypes=[]) 

    def withArticleContent(self, cItem):
        if 'prev_url' in cItem or cItem.get('category', '') == 'explore_item': return True
        else: return False
