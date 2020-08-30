# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm, MergeDicts
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute
from Plugins.Extensions.IPTVPlayer.libs import ph

###################################################

###################################################
# FOREIGN import
###################################################
from urllib import quote_plus
import re
###################################################

def gettytul():
    return 'https://filmynadzis.pl/'

class FilmyNaDzis(CBaseHostClass):
    
    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'filmynadzis.pl', 'cookie':'filmynadzis.pl.cookie'})
        self.filmWebEpgMap = {}
        self.MAIN_URL = 'https://filmynadzis.pl/'

        self.DEFAULT_ICON_URL = 'https://filmynadzis.pl/wp-content/uploads/2016/07/logo2.png'
        self.HTTP_HEADER = self.cm.getDefaultHeader('chrome')
        #{'Referer':self.getMainUrl(), 'Origin':self.getMainUrl()})
        self.AJAX_HEADER = MergeDicts(self.HTTP_HEADER, {'X-Requested-With': ' XMLHttpRequest', 'Accept':'*/*'} )
        self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.cacheLinks    = {}

    def getDefaultParams(self, forAjax=False):
        header = self.AJAX_HEADER if forAjax else self.HTTP_HEADER
        return MergeDicts(self.defaultParams, {'header':header})

    def getPage(self, baseUrl, params={}, post_data=None):
        if not params: 
            params = self.defaultParams
        #params['cloudflare_params'] = {'cookie_file':self.COOKIE_FILE, 'User-Agent': self.HTTP_HEADER['User-Agent']}
        
        return self.cm.getPage(baseUrl, params, post_data)

    def listMain(self, cItem):
        printDBG("FilmyNaDzis.listMainMenu")
        
        sts, data = self.getPage(self.getMainUrl())
        
        if not sts: 
            return
        
        subItems = []
        
        data = ph.find(data, ('<ul', '>', 'navbar'), '</ul>', flags=0)[1]
        items = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>', withMarkers=True)
        
        for item in items:
            printDBG("-------- >  " + item)
            
            url = self.getFullUrl(ph.getattr(item, 'href'), self.MAIN_URL)
            title = ph.clean_html(item)
            
            params = {'good_for_fav':True, 'category':'list_items', 'url':url, 'title': title}

            if '/category/' in url:
                params.update({'type':'category'})
                subItems.append(params)
                printDBG("subItem: %s" % str(params))

            else:
                printDBG("Item: %s" % str(params))
                self.addDir(params)

        if subItems:
            params = {'good_for_fav': False, 'title': _('Categories'), 'type':'category', 'category':'sub_items', 'sub_items': subItems}
            printDBG("Categories: %s" % str(params))
            self.addDir(params)

        tabs = [{'category':'search',         'title': _('Search'), 'search_item':True },
                {'category':'search_history', 'title': _('Search history'),            }]
        self.listsTab(tabs, cItem)

    def listItems(self, cItem):
        printDBG("FilmyNaDzis.listItems %s" % cItem)
        page = cItem.get('page', 1)

        sts, data = self.getPage(cItem['url'])
        if not sts: 
            return
        cUrl = self.cm.meta['url']
        self.setMainUrl(cUrl)


        # page style categories
        tmp = ph.find(data, ('<div', '>', 'listing-wrap'), ('<div','>', 'main-bottom-sidebar-wrap'), flags=0)[1]
        items = self.cm.ph.getAllItemsBeetwenMarkers(tmp, ('<article', '>'), '</article>')
        
        
        for item in items:
            #printDBG("----------------------------")
            #printDBG(item)
            
            url = ph.search(item, ph.A)[1]
            if url:
                url = self.getFullUrl(url, self.MAIN_URL)
            
            
            icon = self.cm.ph.getSearchGroups(item, '''data-src=['"]([^"^']+?)['"]''')[0]
            if icon:
                icon = self.getFullUrl(icon, self.MAIN_URL)
            
            title = ph.clean_html(ph.find(item, ('h3', '>'), '</h', flags=0)[1])
            desc = ph.clean_html(ph.find(item, ('<div', '>', 'excerpt'), '</div', flags=0)[1])

            params = dict(cItem)
            params.update({'good_for_fav':True, 'title':title, 'url':url, 'desc':desc, 'icon':icon})
            printDBG(str(params))
            self.addVideo(params)


        #nextpage
        nextPage = ph.find(data, ('<div', '>', 'pagenavi'), '</div>', flags=0)[1]
        nextPage = ph.rfind(nextPage, '>%s</a>' % (page + 1), '<a')[1]
        nextPage = self.getFullUrl(ph.getattr(nextPage, 'href'), cUrl)

        if nextPage and self.currList:
            params = dict(cItem)
            params.update({'good_for_fav':False, 'title':_('Next page'), 'url':nextPage, 'page':page + 1})
            self.addMore(params)

    def listSearch(self, cItem, searchPattern, searchType):
        url = self.getFullIconUrl('/?s=' + quote_plus(searchPattern))
        params = cItem
        params.update({'name':'category', 'type':'category', 'category':'list_items', 'url':url})
        self.listItems(params)

    def getLinksForVideo(self, cItem):
        printDBG("FilmyNaDzis.getLinksForVideo [%s]" % cItem)

        if 1 == self.up.checkHostSupport(cItem['url']):
            return self.up.getVideoLinkExt(cItem['url'])

        urlTab = []
        cacheKey = cItem['url']
        cacheTab = self.cacheLinks.get(cacheKey, [])
        if cacheTab:
            return cacheTab

        self.cacheLinks = {}

        sts, data = self.getPage(cItem['url'])
        if not sts: 
            return
        
        cUrl = self.cm.meta['url']

        token = ph.find(data, ('<meta', '>', 'token'))[1]
        token_name = ph.getattr(token, 'name')
        token_content = ph.getattr(token, 'content')
        
        printDBG("FilmyNaDzis.getLinksForVideo --> token --> name '%s' - content '%s'" % (token_name, token_content))
        
        urlParams = self.getDefaultParams(True)
        urlParams['header'] = MergeDicts(urlParams['header'], {'Referer': cUrl, 'x-csrf-' +  token_name: token_content })

        data = ph.find(data, ('<div', '>', 'video_thumbnail'), '</div>', flags=0)[1]
        printDBG("------------------------")
        printDBG(data)
        printDBG("------------------------")
        
        tmp = self.getFullUrl(ph.search(data, ph.A)[1], cUrl)
        if tmp: 
            if self.cm.getBaseUrl(tmp) != self.cm.getBaseUrl(cUrl):
                name = self.cm.getBaseUrl(tmp)
                params = {'name': name, 'url':strwithmeta(tmp, {'Referer': cUrl, 'x-csrf-' +  token_name: token_content }), 'need_resolve':1}
                printDBG("-------> link: %s" % str(params))
                urlTab.append(params)
            else:
                printDBG("-------> %s" % tmp)
        
        return urlTab

        #tmp = ph.find(data, ('<a', '>', ph.check(ph.all, 'data=', '%')))[1]
        #tmp = re.compile('''data\=([^=]=?!=['"]([^'^"]+?)('")''').findall(tmp)
        
        #sts, tmp = self.getPage(cUrl, urlParams, MergeDicts({'action':'get_video_player'}, dict(tmp)))
        #if not sts: 
        #    return

        #dumpData(tmp, cUrl, '')

        #tmp = self.getFullUrl(ph.search(tmp, ph.IFRAME)[1], cUrl)
        #if tmp and self.cm.getBaseUrl(tmp) != self.cm.getBaseUrl(cUrl):
        #    name = self.cm.getBaseUrl(tmp, 'nowww')
        #    urlTab.append({'name':name, 'url':strwithmeta(tmp, meta), 'need_resolve':1})

        #if urlTab:
        #    self.cacheLinks[cacheKey] = urlTab

        #return urlTab

    def getVideoLinks(self, videoUrl):
        printDBG("FilmyNaDzis.getVideoLinks [%s]" % videoUrl)
        #self.markSelectedLink(self.cacheLinks, videoUrl)
        return self.up.getVideoLinkExt(videoUrl)

    def getArticleContent(self, cItem, data=None, cUrl=None):
        printDBG("FilmyNaDzis.getArticleContent [%s]" % cItem)

        retTab = []
        itemsList = []
        icons = []
        
        if not data:
            url = cItem.get('prev_url', cItem['url'])
            sts, data = self.getPage(url)
            if not sts: 
                return []
            
            self.setMainUrl(self.cm.meta['url'])
            data = re.sub("<!==[\s\S]*?==>", "", data)

        desc = ph.clean_html(ph.find(data, ('<div', '>', 'body=content'), '</div', flags=0)[1])
        data = ph.find(data, ('<div', '>', 'video_thumbnail_image'), '</div>', flags=ph.BLOCK_MODE)[1]

        title = ph.clean_html(ph.find(data, ('<div', '>', 'heading'), '</div>', flags=0)[1])
        icon = self.getFullIconUrl(ph.search(data, ph.IMG3)[1], cUrl)

        data = ph.find(data, ('<div', '>', 'meta='), '</div', flags=ph.BLOCK_MODE|ph.START_S)
        for idx in xrange(1, len(data), 2):
            tmp = ph.find(data[idx], ('<h5', '>'), '</h5>', flags=0)[1].split('<span', 1)
            if len(tmp) == 2:
                label = ph.clean_html(tmp[0])
                value = ph.clean_html('<span' + tmp[1])
            elif 'categories' in data[1]:
                label = ('Categories')
                value = ph.clean_html(data[idx])
            elif 'podtytul' in data[1]:
               label = _('Alternative title')
               value = ph.clean_html(data[idx])
            else:
               continue

            if label and value:
                itemsList.append((label, value))

        if not title: 
            title = cItem['title']
        
        if not icons: 
            icons.append({'title':'', 'url':cItem.get('icon', self.DEFAULT_ICON_URL)})
        
        if not desc: 
            desc = cItem.get('desc', '')

        return [{'title':ph.clean_html( title ), 'text': ph.clean_html( desc ), 'images':icons, 'other_info':{'costom_items_list':itemsList}}]

    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        category = self.currItem.get("category", '')

        printDBG( "handleService: || category[%s] " % (category) )
        self.currList = []

    #MAIN MENU
        if not category:
            self.listMain({'name':'category'})
        elif category == 'list_items':
            self.listItems(self.currItem)

        elif category == 'sub_items':
            self.listSubItems(self.currItem)

    #SEARCH
        elif category == "search": 
            self.listSearch(self.currItem, searchPattern, searchType)
    #HISTORIA SEARCH
        elif category == "search_history":
            self.listsHistory({'name':'history', 'category': 'search', 'desc': _("Type: ")})
        else:
            printExc()
        
        CBaseHostClass.endHandleService(self, index, refresh)

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, FilmyNaDzis(), True, [])

    def withArticleContent(self, cItem):
        return 'video' == cItem.get('type')
