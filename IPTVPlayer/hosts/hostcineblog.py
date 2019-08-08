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
    return 'https://cineblog01.kim/'

class Cineblog(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'cb01', 'cookie':'cb01.cookie'})
        
        self.USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.103 Safari/537.36'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'text/html'}
        #self.AJAX_HEADER = dict(self.HEADER)
        
        self.MAIN_URL = 'https://cineblog01.kim/'
        self.AJAX_URL = self.MAIN_URL + 'wp-admin/admin-ajax.php'
        self.DEFAULT_ICON_URL = self.MAIN_URL + 'wp-content/uploads/2019/06/cineblog01pazzesca.png'
        
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
    
    def getPage(self, baseUrl, addParams = {}, post_data = None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        def _getFullUrl(url):
            if self.cm.isValidUrl(url):
                return url
            else:
                return urljoin(baseUrl, url)
        return self.cm.getPage(baseUrl, addParams, post_data)
    
    def listMainMenu(self, cItem):
        printDBG("Cineblog.listMainMenu")

        sts, data = self.getPage(self.getMainUrl())
        if not sts: return

        
        tmp = self.cm.ph.getDataBeetwenNodes(data, '<div class="head-main-nav">', '<!-- end search -->', False)[1]
        items = re.findall("<a.*?href=\"(.*?)\">(.*?)</a>",tmp)

        sub_i=[]
        for i in items:
            #printDBG(str(i))
            url = i[0]
            title = i[1]

            if url == "#":
                if len(sub_i):
                    #copy list
                    params = {'category':'sub_items', 'title':parent_title, 'sub_items': sub_i}
                    self.addDir(params)
                    # clear list
                    sub_i = []
                    parent_title = title
                else:
                    #new list
                    parent_title = title
            else:            
                url=self.getFullUrl(url)
                params = {'name':'category', 'category':'list_items', 'title': title, 'url': url}
                #printDBG(str(params))
                sub_i.append(params)
        
        params = {'category':'sub_items', 'title':parent_title, 'sub_items': sub_i}
        self.addDir(params)
        
        MAIN_CAT_TAB = [{'category':'search',          'title': _('Search'), 'search_item':True},
                        {'category':'search_history',  'title': _('Search history')} ]
        self.listsTab(MAIN_CAT_TAB, cItem)
        
    def listItems(self, cItem, nextCategory):
        printDBG("Cineblog.listItems")
        page = cItem.get('page', 1)
        postData = cItem.get('post_data')

        sts, data = self.getPage(cItem['url'], post_data=postData)
        if not sts: return
        self.setMainUrl(self.cm.meta['url'])

        nextPage = self.cm.ph.getDataBeetwenNodes(data, '<div class="pagination">', '</div>', False)[1]
        nextPage = self.cm.ph.getSearchGroups(nextPage, '''<a[^>]+?href=['"]([^'^"]+?)['"][^>]*?>%s<''' % (page + 1))[0]

        dataItem = self.cm.ph.getAllItemsBeetwenNodes(data, ('<article', '>'), "</article>", False)

        for item in dataItem:

            icon  = self.getFullIconUrl( self.cm.ph.getSearchGroups(item, '''<img[^>]+?src=['"]([^"^']+?)['"]''')[0] )
            url   = self.getFullUrl( self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0] )
            title = self.cm.ph.getAllItemsBeetwenNodes(item, "<div class=\"title\">", "</div>", False)
            if title:
                title = self.cleanHtmlStr(title[0])
            else:
                title = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category':nextCategory, 'title': title, 'url':url, 'icon':icon })
            self.addDir(params)

        if nextPage != '':
            params = dict(cItem)
            params.update({'title':_("Next page"), 'page':page+1})
            if nextPage != '#':
                params['url'] = self.getFullUrl(nextPage)
                self.addMore(params)
            elif postData != {}:
                postData = dict(postData)
                postData.pop('titleonly', None)
                postData.update({'search_start':page+1, 'full_search':'0', 'result_from':10*page+1})
                params['post_data'] = postData
                self.addMore(params)
            else:
                printDBG("NextPage [%s] not handled!!!" % nextPage)

    def listSubItems(self, cItem):
        printDBG("Cineblog.listSubItems")
        if 'sub_items' in cItem:
            for i in cItem['sub_items']:
                self.addDir(i)
                    
    def exploreItem(self, cItem):
        printDBG("Cineblog.exploreItem")

        sts, data = self.getPage(cItem['url'])
        if not sts: 
            return
        
        cItem = dict(cItem)
        cItem['prev_url'] = cItem['url']
        
        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'playeroptionsul'), ('</ul', '>'), False)[1]
        items = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li', '</li>')
        for i in items:
            printDBG(i)
            data_type = re.findall('data-type=\'(.*?)\'', i)
            data_post = re.findall('data-post=\'(.*?)\'', i)
            data_nume = re.findall('data-nume=\'(.*?)\'', i)
            if data_type and data_post and data_nume:
                title = self.cleanHtmlStr(i)
                
                params = {'title' : title, 'category': data_type[0], 'post' : data_post[0], 'nume': data_nume[0], 'url': cItem['url'], 'icon': cItem['icon'] }
                #printDBG(str(params))
                self.addVideo(params)       
        
        
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Cineblog.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.MAIN_URL
        cItem['post_data'] = {'s':searchPattern}
        cItem['category'] = 'list_items'
        self.listItems(cItem, 'explore_item')

    def getLinksForVideo(self, cItem):
        printDBG("Cineblog.getLinksForVideo [%s]" % cItem)

        urlTab=[]
        if cItem['category'] == 'movie':
            postData = {'action':'doo_player_ajax', 'type' : 'movie', 'nume': cItem['nume'], 'post' : cItem['post']}
            params = self.defaultParams
            params['header'].update({'Referer': cItem['url'], 'X-Requested-With':'XMLHttpRequest'} )

            sts, dataUrl = self.getPage(self.AJAX_URL, params , post_data = postData)
            
            if sts: 
                printDBG(dataUrl)
                frameUrl= re.findall('src=\'(.*?)\'', dataUrl)
                if frameUrl:
                    frameUrl=self.getFullUrl(frameUrl[0])
                    printDBG(frameUrl)
                    
                    params['header'].update({'Referer': frameUrl})
                    sts, data = self.getPage(self.MAIN_URL + "embed/watching", params)
                    
                    if sts:
                        url = self.cm.meta['url']
                        printDBG(url)
                        urlTab.append({'name': cItem['title'], 'url' : url, 'need_resolve': 1})
        return urlTab
        
        
    def getVideoLinks(self, videoUrl):
        printDBG("Cineblog.getVideoLinks [%s]" % videoUrl)
        return  self.up.getVideoLinkExt(videoUrl)

    def getArticleContent(self, cItem):
        printDBG("Cineblog.getVideoLinks [%s]" % cItem)
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
            self.listSubItems(self.currItem)
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
        CHostBase.__init__(self, Cineblog(), True, favouriteTypes=[]) 

