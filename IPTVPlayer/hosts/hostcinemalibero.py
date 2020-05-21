# -*- coding: utf-8 -*-
#
# Host by Mark - Thanks to my bro, and to Maxbambi
# 
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
            if not url.endswith('/'): 
                url += '/'
            
            url += 'page/%s/' % (page)
            if len(tmp) == 2: url += '?' + tmp[1]
        
        sts, data = self.getPage(url)
        if not sts: return
        
        if 'page/{0}/'.format(page+1) in data:
            nextPage = True
        else:
            nextPage = False
        
        tmp = self.cm.ph.getDataBeetwenMarkers(data, ('<div','>','class="card shadow border-0 mb-4"') , ('<div', '>', 'class="container"'), False)[1]
        printDBG(tmp)

        if not tmp:
            tmp = self.cm.ph.getDataBeetwenMarkers(data, '<div id="content" role="main">' , ('<div', '>', 'nav-previous'), False)[1]
        if not tmp:
            tmp = self.cm.ph.getDataBeetwenMarkers(data, ('<main','>','main'), ('<div', '>', 'nav-previous'), False)[1]

        if not tmp:
            tmp = self.cm.ph.getDataBeetwenMarkers(data, '<div class="container">', '<footer>', False)[1]
        
        movies = self.cm.ph.getAllItemsBeetwenMarkers(tmp,'<a','</a>')
        
        for m in movies:
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(m, '<div class="titolo"', '</div>')[1])
            if not title:
                continue
            
            url = self.cm.ph.getSearchGroups(m, "href=['\"]([^'^\"]+?)['\"]")[0]
            icon = self.cm.ph.getSearchGroups(m, "background-image: url['\(]([^'^\"]+?)['\)]")[0]
            params = {'category':'explore_item', 'title': title, 'icon': icon , 'url': url}
            printDBG(str(params))
            self.addDir(params)
            
        if nextPage:
            params = dict(cItem)
            params.update({'category':'list_items', 'good_for_fav': False, 'title':_('Next page'), 'page':page+1})
            self.addMore(params)
            
    def exploreItems (self, cItem):
        printDBG('Cinemalibero.exploreItem %s' % cItem)
        url = cItem['url']
                        
        sts, data = self.getPage(url)
        #printDBG(data)                
        if not sts:
            return
        
        # check if is a series
        is_serie = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<a href="https://cinemalibero.plus/category/serie-tv/" rel="category tag">', '</a>')[1])
        #printDBG(is_serie)
        if 'Serie' in is_serie:
            # it is a series
            seasons={}
            tmp_seasons = self.cm.ph.getDataBeetwenMarkers(data, '<div class="at-above-post addthis_tool"', '<div class="at-below-post addthis_tool"')[1]
            tmp_seasons = tmp_seasons.split('<strong>')
            if len(tmp_seasons)>1:
                del(tmp_seasons[0])
            
            #printDBG("tmp_seasons: %s" % tmp_seasons)
            
            for s in tmp_seasons:
                s = '<strong>' + s
                seasonName = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(s, '<strong>' , '</strong>', False)[1])
                seasons[seasonName]=[]
                printDBG("new season: '%s'" % seasonName)
                
                #eps = self.cm.ph.getAllItemsBeetwenMarkers(s, '&#215;', '<br />')
                eps = s.split('<br />')
                
                for ep in eps:
                    printDBG('----------------------')
                    printDBG(ep)
                    printDBG('----------------------')

                    i1 = ep.find('<p>')
                    if i1 > 0:
                        ep = ep[i1+3:]
                    ep = ep.strip().encode('utf-8')
                    
                    if '&#215;' not in ep:
                        continue
                    
                    printDBG('-----------dopo modifiche -----------')
                    printDBG(ep)
                    printDBG('-------------------------------------')
                    
                    
                    epName = self.cleanHtmlStr(ep.split('<a')[0])
                    epName = epName.replace('\xe2\x80\x93',"-")

                    if epName.endswith("-"): 
                        epName = epName[:-1]
                    
                    printDBG("new episode: '%s' of season '%s' " % (epName, seasonName))
                    
                    linksTab = []

                    links = self.cm.ph.getAllItemsBeetwenMarkers(ep,'<a target','</a>')
                    for l in links:
                        url = self.cm.ph.getSearchGroups(l, "href=['\"]([^'^\"]+?)['\"]")[0]
                        
                        host = self.cleanHtmlStr(l)
                        host = host.strip().encode('utf-8').replace('\xe2\x80\x93',"-")
                        if host.startswith("-"): 
                            host = host[1:]
                        
                        #printDBG("url: %s" % url)
                        #printDBG("host: %s" % host)
                        #printDBG("epname: %s" % epName)
                        title = "%s - %s - %s" % (seasonName, epName, host)
                        params = MergeDicts(cItem, {'title': title, 'url' : url})
                        printDBG(str(params))
                        linksTab.append(params)

                    seasons[seasonName].append({'title': epName, 'category':'episode','links':linksTab})

                    
                self.addDir({'category':'season','episodes_list': seasons[seasonName], 'title': seasonName})
                    
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
        
    def listEpisodes(self, cItem):
        printDBG("Cinemalibero.listEpisodes cItem[%s]" % cItem)

        for e in cItem.get('episodes_list',[]):
            printDBG(json_dumps(e))
            epName = e.get('title','')
            if epName:
                self.addDir ({'category':'episode','links': e['links'], 'title': epName})

    def exploreEpisode(self, cItem):
        printDBG("Cinemalibero.exploreEpisode cItem[%s]" % cItem)
    
        for l in cItem.get('links',[]):
            printDBG(json_dumps(l))
            self.addVideo(l)
            
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
        elif category == 'season':
            self.listEpisodes(self.currItem)
        elif category == 'episode':
            self.exploreEpisode(self.currItem)
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
    
