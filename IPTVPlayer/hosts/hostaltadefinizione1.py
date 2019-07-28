# -*- coding: utf-8 -*-
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
    return 'http://altadefinizione1.link/'

class AltadefinizioneUno(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'altadefinizione1.link', 'cookie':'altadefinizione1.link.cookie'})
        
        self.USER_AGENT = 'Mozilla/5.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update( {'X-Requested-With':'XMLHttpRequest', 'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8'} )
        
        self.MAIN_URL = 'http://www.altadefinizione1.link/'
        self.DEFAULT_ICON_URL = 'http://altadefinizione1.link/templates/Dark/img/nlogo.png'
        
        self.defaultParams = {'header':self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
    
    def getPage(self, baseUrl, addParams = {}, post_data = None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        
        #addParams['cloudflare_params'] = {'domain':self.up.getDomain(baseUrl), 'cookie_file':self.COOKIE_FILE, 'User-Agent':self.USER_AGENT}
        return self.cm.getPage(baseUrl, addParams, post_data)
    
    def getFullUrl(self, url):
        if url[:1] == "/":
            url = self.MAIN_URL + url[1:]
        return url        
    
    def listMainMenu(self, cItem):
        printDBG("Altadefinizione.listMainMenu")

        sts, data = self.getPage(self.getMainUrl())
        if not sts: 
            return
        self.setMainUrl(self.cm.meta['url'])

        tmp = self.cm.ph.getDataBeetwenNodes(data, '<ul id="menu-menu-1" class="menu"', '</ul>', False)[1]
        items = re.findall("<li class=\"menu-item\">(.*?)</li>", tmp)
        for item in items:
            url = self.getFullUrl(re.findall("href=['\"]([^\"^']+?)['\"]", item)[0] )
            
            title = self.cleanHtmlStr(item).decode('UTF-8').lower().encode('UTF-8')
            if title in ["richiedi film", "dmca"]:
                continue
            title = title[:1].upper() + title[1:]
            params = dict(cItem)
            params.update({'category':'list_items', 'title':title, 'url':url})
            printDBG(str(params))
            self.addDir(params)

        
        tmp = re.findall("<h3 class=\"titleSidebox cat\">Categorie</h3>((.|\n)*?)<h3 class=\"titleSidebox", data)[0]
        
        items = re.findall("<ul class=\"listSub((.|\n)*?)</ul>", tmp[0] )

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
        
        MAIN_CAT_TAB = [{'category':'search',          'title': _('Search'), 'search_item':True},
                        {'category':'search_history',  'title': _('Search history')} ]
        
        self.listsTab(MAIN_CAT_TAB, cItem)
        
    def listItems(self, cItem, nextCategory):
        printDBG("Altadefinizione.listItems")
        page = cItem.get('page', 1)
        postData = cItem.get('post_data')

        sts, data = self.getPage(cItem['url'], post_data=postData)
        if not sts: return
        self.setMainUrl(self.cm.meta['url'])

        if postData != None:
            printDBG("Fatta una ricerca!!")
            movies = data.split("<div class=\"box\">")
        else:
            printDBG("Non fatta una ricerca!!")
            if cItem['url'][-15:] == '/piu-visti.html':
                tmp = re.findall("<div id='dle-content'>((.|\n)*?)</section>", data)[0][0]
            else:
                tmp = re.findall("<div id='dle-content'>((.|\n)*?)<div class=\"paginationC\">", data)[0][0]

            movies = tmp.split("<div class=\"box\">")

        if len(movies) > 1:
            del movies[0]

        for m in movies:
            t = re.findall("<h2 class=\"titleFilm\">(.*?)</h2>", m)[0]
            title = self.cleanHtmlStr(t)
            url   = self.getFullUrl( self.cm.ph.getSearchGroups(t, '''href=['"]([^"^']+?)['"]''')[0] )
            icon = self.getFullUrl(re.findall("background-image:url\((.*?)\);", m)[0])

            desc = []

            if cItem['url'][-15:] == '/piu-visti.html':
                views = re.findall("<i class=\"fa fa-eye\"></i>(.*?)</span>",m)[0]
                desc.append(_("Views") + ": " + views)
            tx = re.findall("(<div class=\"ml-item-lab.*?</div>)",m)
            
            for t in tx:
                tt = self.cleanHtmlStr(t)
                if tt != '': 
                    desc.append(tt)

            desc = [' | '.join(desc)]

            t2 = re.findall("<div class=\"ml-item-text\">(.*?)</div>", m)[0]
            tt = self.cleanHtmlStr(t2)
            if tt != '': desc.append(tt)

            params = dict(cItem)
            params.update({'good_for_fav': True, 'category':nextCategory, 'title':title, 'url':url, 'icon':icon, 'desc':'[/br]'.join(desc)})
            self.addDir(params)

        #next page
        tmp = re.findall("<div class=\"pages\">((.|\n)*?)</div>", data)
        
        if len(tmp)>0:
            tmp = tmp[0][0]
            printDBG(tmp)
            nextPage = self.cm.ph.getSearchGroups(tmp, '''<a[^>]+?href=['"]([^'^"]+?)['"][^>]*?>%s<''' % (page + 1))
            if len(nextPage)>0:
                printDBG(nextPage[0])
                params = dict(cItem)
                params.update({'title':_("Next page"), 'page':page+1, 'url': nextPage[0]})
                self.addMore(params)

            #    elif postData != {}:
            #       postData = dict(postData)
            #       postData.pop('titleonly', None)
            #       postData.update({'search_start':page+1, 'full_search':'0', 'result_from':10*page+1})
            #       params['post_data'] = postData
            #       self.addDir(params)
            #   else:
            #       printDBG("NextPage [%s] not handled!!!" % nextPage)

    def exploreItem(self, cItem):
        printDBG("Altadefinizione.exploreItem")

        sts, data = self.getPage(cItem['url'])
        if not sts: return
        self.setMainUrl(self.cm.meta['url'])
        
        cItem = dict(cItem)
        cItem['prev_url'] = cItem['url']

        trailer = self.cm.ph.getDataBeetwenNodes(data, '<div class="collapse" id="trailers">', ('</div', '>'), False)[1]
        url = self.getFullUrl(self.cm.ph.getSearchGroups(trailer, '''src=['"]([^"^']+?)['"]''', 1, True)[0])
        if self.cm.isValidUrl(url):
            title = "Trailer"
            params = dict(cItem)
            params.update({'good_for_fav':False, 'url':url, 'title':'%s %s' % (title, cItem['title'])})
            self.addVideo(params)
 
        urlTab = []
        data = self.cm.ph.getAllItemsBeetwenNodes(data, '<ul class="playernav">', ('</ul', '>'), False)
        for idx in range(len(data)):
            data[idx] = self.cm.ph.getAllItemsBeetwenMarkers(data[idx], '<a', '</a>')
            for item in data[idx]:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''data\-target=['"]([^"^']+?)['"]''', 1, True)[0])
                if 1 == self.up.checkHostSupport(url): 
                    name = self.cleanHtmlStr(item)
                    url = strwithmeta(url, {'Referer':cItem['url']})
                    urlTab.append({'name':name, 'url':url, 'need_resolve':1})

        if len(urlTab):
            params = dict(cItem)
            params.update({'good_for_fav':False, 'urls_tab':urlTab})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Altadefinizione.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.MAIN_URL 
        cItem['post_data'] = {'do':'search', 'subaction':'search', 'titleonly':'3', 'story':searchPattern}
        cItem['category'] = 'list_items'
        self.listItems(cItem, 'explore_item')

    def getLinksForVideo(self, cItem):
        printDBG("Altadefinizione.getLinksForVideo [%s]" % cItem)
        if 1 == self.up.checkHostSupport(cItem['url']): 
            return self.up.getVideoLinkExt(cItem['url'])
        return cItem.get('urls_tab', [])

    def getVideoLinks(self, videoUrl):
        printDBG("Altadefinizione.getVideoLinks [%s]" % videoUrl)
        return  self.up.getVideoLinkExt(videoUrl)

    def getArticleContent(self, cItem):
        printDBG("Altadefinizione.getVideoLinks [%s]" % cItem)
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
        CHostBase.__init__(self, AltadefinizioneUno(), True, favouriteTypes=[]) 

    def withArticleContent(self, cItem):
        if 'prev_url' in cItem or cItem.get('category', '') == 'explore_item': return True
        else: return False
