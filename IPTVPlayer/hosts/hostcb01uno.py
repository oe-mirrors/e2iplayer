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
    return 'https://cb01.design/'

class Cb01(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'cb01.design', 'cookie':'cb01.design.cookie'})
        
        self.USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.103 Safari/537.36'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update( {'X-Requested-With':'XMLHttpRequest', 'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8'} )
        
        self.MAIN_URL = 'https://cb01.design/'
        self.DEFAULT_ICON_URL = 'https://cb01.design/wp-content/uploads/2019/03/logocb2-1.jpg'
        
        self.defaultParams = {'header':self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
    
    def getPage(self, baseUrl, addParams = {}, post_data = None):
        if addParams == {}:
            addParams = self.defaultParams

        return self.cm.getPage(baseUrl, addParams, post_data)
    
    def getFullUrl(self, url):
        if url[:1] == "/":
            url = self.MAIN_URL + url[1:]
        return url        
    
    def cleanHtmlFromCR(self, data):
        # remove all problems with new lines and spaces between tags
        data = data.replace("\n", " ")
        data = re.sub(r">[ ]{1,5}<", "><", data)
        #printDBG(data)
        return data
    
    def listMainMenu(self, cItem):
        printDBG("cb01uno.listMainMenu")
        params = dict(cItem)
        params.update({'name':'category', 'category':'list_items', 'title': _('Home'), 'url': self.MAIN_URL})
        self.addDir(params)
        
        sts, data = self.getPage(self.getMainUrl())
        if not sts: 
            return

        data = self.cleanHtmlFromCR(data)

        self.setMainUrl(self.cm.meta['url'])
        tabs = []
        
        groups = self.cm.ph.getAllItemsBeetwenNodes(data, ('<li','>','mega-menu-megamenu'), '</li></ul>', False)
        
        for group in groups:
            printDBG("-----------------------")
            categories = []
            
            items = self.cm.ph.getAllItemsBeetwenNodes(group, '<a', '</a>', True)
            for item in items:
                #printDBG(item)    
                title = self.cleanHtmlStr(item)
                url = re.findall("href=['\"]?([^>'\"]+?)['\"]?>", item)
                if url:
                    url = self.getFullUrl(url[0])
                    params = dict(cItem)
                    params.update({'name':'category', 'category':'list_items', 'title':title, 'url': url})
                    printDBG(str(params))
                    categories.append(params)
                else:
                    main_cat = title
                    printDBG("category : %s" % main_cat)
            
            params = dict(cItem)
            params.update({'name':'category', 'category':'sub_items', 'title': main_cat , 'sub_items': categories})
            printDBG(str(params))
            tabs.append(params)

        if len(tabs):
            params = dict(cItem)
            params.update({'category':'sub_items', 'title': _('Categories'), 'sub_items':tabs})
            self.addDir(params)
        
        # Search 
        MAIN_CAT_TAB = [{'category':'search',          'title': _('Search'), 'search_item':True},
                        {'category':'search_history',  'title': _('Search history')} ]
        
        self.listsTab(MAIN_CAT_TAB, cItem)
        
    def listItems(self, cItem, nextCategory):
        printDBG("cb01uno.listItems '%s'" % cItem['url'])
        printDBG(str(cItem))
        page = cItem.get('page', 1)
        postData = cItem.get('post_data')
        
        url = self.getFullUrl(cItem['url'])
        if postData:
            sts, data = self.getPage(url, post_data = postData)
        else:
            sts, data = self.getPage(url)
            
        if not sts: 
            return
        data = self.cleanHtmlFromCR(data)
        
        self.setMainUrl(self.cm.meta['url'])
        
        movies = self.cm.ph.getAllItemsBeetwenNodes(data,('<div','>','card mp-post horizontal'), '</div></div></div>', False)
        if not movies:
            movies = self.cm.ph.getAllItemsBeetwenNodes(data,('<div','>','card mp-post horizontal'), '<!-- </div>-->', False)

        
        for m in movies:
            printDBG("------------------------------------------------------------")
            printDBG(m)
            
            url = re.findall("href=\"(.*?)\"", m, re.S)
            if url:
                url = self.getFullUrl(url[0])
            else:
                url = re.findall("href=(.*?)/>", m, re.S)
                if url:
                    url = self.getFullUrl(url[0])
                else:
                    continue

            icon = re.findall("src=\"?([^ >'\"]+?)[ >'\"]", m, re.S)
            if icon:
                icon = self.getFullUrl(icon[0])
                    
            title_tmp = self.cm.ph.getDataBeetwenNodes(m, ('<h3','>'), '</h3>', False)[1]
            title = self.cleanHtmlStr(title_tmp)
            
            desc_tmp = self.cm.ph.getDataBeetwenNodes(m, ('<span','>'), '</a>', False)[1]
            desc = self.cleanHtmlStr(desc_tmp)
            
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'icon': icon, 'desc': desc})
            printDBG(str(params))
            self.addDir(params)

        #search if exsts a next page
        pntemp = re.findall("value=['\"]?([^ >'\"]+?)[ '\"]?>%s</option>" % (page + 1), data, re.S)            
        if pntemp:
            params = dict(cItem)
            params.update({'title':_("Next page"), 'page': page + 1, 'url': pntemp[0]})
            printDBG(str(params))
            self.addMore(params)
            

    def exploreCategory(self, cItem):
        printDBG("cb01uno.exploreCategory [%s] " % cItem['title'])

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
        printDBG("cb01uno.exploreItem [%s] " % cItem['title'])

        sts, data = self.getPage(cItem['url'])
        if not sts: 
            return
        
        data = self.cleanHtmlFromCR(data)
        
        self.setMainUrl(self.cm.meta['url'])
        cItem['prev_url'] = cItem['url']

        #trailer
        trailer = self.cm.ph.getDataBeetwenNodes(data, 'Guarda il Trailer:', ('</div', '>'), False)[1]
        if trailer:
            url = re.findall("src=['\"]?([^ >'\"]+?)['\"]?[ >]",trailer)
            if url:
                if self.cm.isValidUrl(url[0]):
                    title = "Trailer"
                    params = dict(cItem)
                    params.update({'good_for_fav':False, 'url':url[0], 'title':'%s %s' % (title, cItem['title'])})
                    self.addVideo(params)
 
        #video links
        urlTab = []
        
        #links = re.findall("href=['\"]?([^ '\"]+?)['\"]? target=\"?_blank\"? rel=\"[^\"]+\">(.*?)</a>", data)
        #example: <a href="http://swzz.xyz/link/479Pq/" target="_blank" rel="noopener noreferrer">Akvideo</a>
        links = re.findall("href=['\"]?([^ '\"]+?)['\"]? target=\"?_blank\"? rel=\"[^\"]+\">(.*?)</a>|<strong>(.*?)</strong>", data)
        categ = ''
        
        for l in links:
            if not l[0]:
                if 'streaming hd' in l[2].lower():
                    categ = 'HD'
                elif 'streaming' in l[2].lower():
                    categ = 'SD'
                elif 'download hd' in l[2].lower():
                    categ = 'download HD'
                elif 'download' in l[2].lower():
                    categ = 'download SD'
                    
            else:
                url = l[0]
                if url.startswith('"'):
                    url = url[1:]
                if url.endswith('"'):
                    url = url[:-1]
                if self.cm.isValidUrl(url) and not (('feeds' in url) or ('cb01' in url) or ('feedburner' in url) ):
                    url = strwithmeta(url, {'Referer':cItem['url']})
                    if l[1]:
                        urlTab.append({'name': "%s [%s]" % (l[1], categ), 'url':url, 'need_resolve':1})
                    else:
                        urlTab.append({'name': "%s [%s]" % (self.cm.getBaseUrl(url, True), categ), 'url':url, 'need_resolve':1})
                    
        if len(urlTab):
            params = dict(cItem)
            params.update({'good_for_fav':False, 'urls_tab':urlTab})
            printDBG(str(params))
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("cb01uno.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        #Verify post parrams and config bellow
        cItem['url'] = self.MAIN_URL
        cItem['post_data'] = {'s': searchPattern}
        cItem['category'] = 'list_items'
        self.listItems(cItem, 'explore_item')

    def getLinksForVideo(self, cItem):
        printDBG("cb01uno.getLinksForVideo [%s]" % cItem)

        return cItem.get('urls_tab', [])

    def getVideoLinks(self, videoUrl):
        printDBG("cb01uno.getVideoLinks [%s]" % videoUrl)
        return self.up.getVideoLinkExt(videoUrl)


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
            cItem = self.currItem
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
