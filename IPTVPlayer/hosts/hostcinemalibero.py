# -*- coding: utf-8 -*-
# typical import for a standard host
###################################################
# LOCAL import
###################################################
# localization library
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
# host main class
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
# tools - write on log, write exception infos and merge dicts 
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts
# add metadata to url
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
# library for json (instead of standard json.loads and json.dumps) 
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
# library for parsing html
from Plugins.Extensions.IPTVPlayer.libs import ph
# read informations in m3u8
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
###################################################

# space for importing standand python libraries
###################################################
# FOREIGN import
###################################################
import re
import datetime
import urllib
###################################################

def gettytul():
    return 'https://cinemalibero.plus/' # main url of host

class Cinemalibero(CBaseHostClass):
 
    def __init__(self):
        # init global variables for this class
        
        CBaseHostClass.__init__(self, {'history':'cinemalibero', 'cookie':'cinemalibero.cookie'}) # names for history and cookie files in cache
        
        # vars default values
        # various urls
        self.MAIN_URL = 'https://cinemalibero.plus/'

        # url for default icon
        self.DEFAULT_ICON_URL = "https://cinemalibero.plus/wp-content/themes/Cinemalibero%202.0/images/logo02.png"

        # default header and http params
        self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')        
        self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        
    def getPage(self, url, addParams = {}, post_data = None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    
    def getLinksForVideo(self, cItem):  #cItem is the current item selected in menu
        # mandatory function when you want to play videos, so everytime!
        printDBG("Cinemalibero.getLinksForVideo [%s]" % cItem)

        linksTab=[]
        if 'links_tab' in cItem:
            for l in cItem['links_tab']:
                if self.up.checkHostSupport(l['url']) == 1:
                    linksTab.extend(self.up.getVideoLinkExt(l['url']))
            
            return linksTab
        
        videoUrl = cItem['url']
        # if is enough to pass url to urlparser (because is from a known server)
        # use these functions
        if self.up.checkHostSupport(videoUrl) == 1:
            return self.up.getVideoLinkExt(videoUrl)
        else:
            printDBG(videoUrl)
            # do something to find streaming links in page
            # ....
            # ....  
            # ....
            
        return linksTab

    
    def listMainMenu(self, cItem):   
        printDBG('Cinemalibero.listMainMenu')
        MAIN_CAT_TAB = [{'category':'list_items',      'title': _('Movies') , 'url' : self.getFullUrl('/category/film') },
                        {'category':'list_items',      'title': _('Popular'), 'url' : self.getFullUrl('/popularni-online-filmovi-sa-prevodom') },
                        {'category':'list_items',      'title': _('Series') , 'url': self.getFullUrl('/category/serie-tv') }    ,
                        {'category':'search',          'title': _('Search'),    'search_item':True, },
                        {'category':'search_history',  'title': _('Search history'),     }]
        self.listsTab(MAIN_CAT_TAB, cItem)  

    # here you should add the functions you need to show users list of items (dirs, videos)           
    def listItems (self, cItem):
        printDBG('Cinemalibero.listItems')
        url  = cItem['url']
        page = cItem.get('page', 1)
        if page > 1:
            tmp = url.split('?')
            url = tmp[0]
            if not url.endswith('/'): url += '/'
            url += 'page/%s/' % (page)
            if len(tmp) == 2: url += '?' + tmp[1]
        
        sts, data = self.getPage(url)
        if not sts: return
        
        if 'page/{0}/'.format(page+1) in data:
            nextPage = True
        else:
            nextPage = False
        
        #tmp = self.cm.ph.getDataBeetwenMarkers(data, '<div class="card shadow border-0 mb-4"', '</div>')[1]
        #tmp = self.cm.ph.getDataBeetwenMarkers(data, '<div class="container"', '</div>', False)[2]
        tmp = self.cm.ph.getDataBeetwenMarkers(data, ('<div','>','class="card shadow border-0 mb-4"') , ('<div', '>', 'class="container"'), False)[1]
        printDBG(tmp)
        if not tmp:
            tmp = self.cm.ph.getDataBeetwenMarkers(data, '<div id="content" role="main">' , ('<div', '>', 'nav-previous'), False)[1]
        if not tmp:
            tmp = self.cm.ph.getDataBeetwenMarkers(data, ('<main','>','main'), ('<div', '>', 'nav-previous'), False)[1]
        
        #next_page = self.cm.ph.getDataBeetwenMarkers(data, '<a class="next page-numbers"', '</a>')[1]
        #printDBG('Cinemalibero.nextPage %s' % next_page)
        #next_url = self.cm.ph.getSearchGroups(next_page, "href=['\"]([^'^\"]+?)['\"]")[0]
        #printDBG('Cinemalibero.nextPageUrl %s' % next_url)
        #next_params = {'title': _('Next page'), 'url': next_url}
        #self.addDir(next_params)
        
        movies = self.cm.ph.getAllItemsBeetwenMarkers(tmp,'<a','</a>')
        
        for m in movies:
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(m, '<div class="titolo"', '</div>')[1])
            #title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(m, '<div class="card-body p-0"', '</a>')[1])
            #title = self.cm.ph.getSearchGroups(m, "title=['\"]([^'^\"]+?)['\"]")[0]
            url = self.cm.ph.getSearchGroups(m, "href=['\"]([^'^\"]+?)['\"]")[0]
            icon = self.cm.ph.getSearchGroups(m, "background-image: url['\(]([^'^\"]+?)['\)]")[0]
            params = {'category':'explore_item', 'title': title, 'icon': icon , 'url': url}
            printDBG(str(params))
            self.addDir(params)
            
        if nextPage:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title':_('Next page'), 'page':page+1})
            self.addDir(params)
            
    def exploreItems (self, cItem):
        printDBG('Cinemalibero.exploreItem %s' % cItem)
        url = cItem['url']
                        
        sts, data = self.getPage(url)
                        
        if not sts:
            return
        
        # check if is a series
        tmp_seasons = self.cm.ph.getDataBeetwenMarkers(data, '<div bis_skin_checked' , '<div style', False)[1]
        printDBG(tmp_seasons)
        if tmp_seasons:
            # it is a series
            #printDBG(tmp_seasons)
            tmp_seasons = tmp_seasons.split('<strong>')
            if len(tmp_seasons)>1:
                del(tmp_seasons[0])
            for s in tmp_seasons:
                s = '<strong>' +s
                seasonName = self.cm.ph.getDataBeetwenMarkers(data, '<strong>' , '</strong>', False)[1]
                printDBG("Season name: %s" % seasonName)
                eps = self.cm.ph.getAllItemsBeetwenMarkers(s,('<p','>'),'</p>') 
                for ep in eps:
                    printDBG('----------------------')
                    printDBG(ep)
                    printDBG('----------------------')
                    epName = self.cleanHtmlStr(ep)
                    # data-open="ssksk" data-very="sjsjs" data-only="sssh"
                    linksTab = []
                    video_id_openload = self.cm.ph.getSearchGroups(ep, "data-open=['\"]([^'^\"]+?)['\"]")[0]
                    
                    video_id_verystream = self.cm.ph.getSearchGroups(ep, "data-very=['\"]([^'^\"]+?)['\"]")[0]
                    
                    video_id_onlystream = self.cm.ph.getSearchGroups(ep, "data-only=['\"]([^'^\"]+?)['\"]")[0]
                    if video_id_onlystream:
                        url_onlystream="https://onlystream.tv/e/%s" % video_id_onlystream
                        linksTab.append({'name':'Onlystream', 'url': url_onlystream}) 
                    
                    title = "%s %s %s" % (cItem['title'], seasonName, epName)
                    params = MergeDicts(cItem, {'title': title, 'url' : cItem['url'], 'links_tab': linksTab})
                    printDBG(params)
                    self.addVideo(params)
                    
        else:
            #it is a movie
            links = self.cm.ph.getAllItemsBeetwenMarkers(data,'<a target','</a>') 
            for l in links:
                url = self.cm.ph.getSearchGroups(l, "href=['\"]([^'^\"]+?)['\"]")[0]    
                host = self.cleanHtmlStr(l)
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<h1', '</a>')[1])
                
                printDBG("found url %s" % url)

                if not ('facebook' in url):
                    params = MergeDicts(cItem, {'title': title + " - " + host, 'host': host, 'url': url})
                    printDBG(str(params))
                    self.addVideo(params)
        
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Cinemalibero.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('/?s=') + urllib.quote_plus(searchPattern)
        cItem['category'] = 'search_items'
        self.listItems(cItem)

                        
    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('Cinemalibero.handleService start')
        
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name     = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        
        printDBG( "handleService: >> name[%s], category[%s] " % (name, category) )
        self.currList = []
        
        #MAIN MENU
        if name == None:
            self.listMainMenu({'name':'category'})
        elif category == 'list_items':
            self.listItems(self.currItem)
        elif category == 'explore_item':
            self.exploreItems(self.currItem)       
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
        CHostBase.__init__(self, Cinemalibero(), True, [])
    
