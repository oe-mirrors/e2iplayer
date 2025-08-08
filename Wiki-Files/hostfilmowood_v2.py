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
###################################################

def gettytul():
    return 'https://filmowood.com/' # main url of host

class Filmowood(CBaseHostClass):
 
    def __init__(self):
        # init global variables for this class
        
        CBaseHostClass.__init__(self, {'history':'filmowood', 'cookie':'filmowood.cookie'}) # names for history and cookie files in cache
        
        # vars default values
        # various urls
        self.MAIN_URL = 'https://filmowood.com/'

        # url for default icon
        self.DEFAULT_ICON_URL = "https://www.siteshotter.com/website-thumbnail/filmowood.com"

        # default header and http params
        self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')        
        self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        
    def getPage(self, url, addParams = {}, post_data = None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    
    def getLinksForVideo(self, cItem):  #cItem is the current item selected in menu
        # mandatory function when you want to play videos, so everytime!
        printDBG("Filmowood.getLinksForVideo [%s]" % cItem)

        videoUrl = cItem['url']
        linksTab=[]
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
        printDBG('Filmowood.listMainMenu')
        MAIN_CAT_TAB = [{'category':'list_items',      'title': _('Movies') , 'url' : self.getFullUrl('/') },
                        {'category':'list_items',      'title': _('Popular'), 'url' : self.getFullUrl('/popularni-online-filmovi-sa-prevodom') },
                        {'category':'list_items',      'title': _('Series') , 'url': self.getFullUrl('/online-serije-sa-prevodom') }    ,
                        {'category':'search',          'title': _('Search'),    'search_item':True, },
                        {'category':'search_history',  'title': _('Search history'),     } ]
        self.listsTab(MAIN_CAT_TAB, cItem)  

    # here you should add the functions you need to show users list of items (dirs, videos)           
    def listItems (self, cItem):
        printDBG('Filmowood.listItems')
        #                
        # do something and add items
        # self.addDir (params) adds a directory
        # self.addVideo (params) adds a video
                        
    def listFilters (self, cItem):
        printDBG('Filmowood.listFilters')
        #                
        # do something and add items
        #
                        
    def exploreItems (self, cItem):
        printDBG('Filmowood.exploreItems')
        #               
        # do something and add items
        #
                        
    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('Filmowood.handleService start')
        
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
        CHostBase.__init__(self, Filmowood(), True, [])
    
