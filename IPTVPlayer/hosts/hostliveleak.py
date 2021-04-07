# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
###################################################

###################################################
# FOREIGN import
###################################################
import re
import time
try:
    import json
except Exception:
    import simplejson as json
from Components.config import config, ConfigSelection, getConfigListEntry
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.liveleak_searchsort = ConfigSelection(default="relevance", choices=[("relevance", "Najtrafniejsze"), ("date", "Najnowsze"), ("views", "Popularność"), ("votes", "Najlepiej oceniane")])

def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry("Sortuj wyniki wyszukiwania po:", config.plugins.iptvplayer.liveleak_searchsort))
    return optionList
###################################################

def gettytul():
    return 'https://liveleak.com/'

class LiveLeak(CBaseHostClass):
    
    def __init__(self):
        printDBG("LiveLeak.__init__")
        CBaseHostClass.__init__(self, {'history': 'LiveLeak.com'})
        
        self.MAIN_URL = 'https://www.liveleak.com/'
        ITEMS_BROWSE_URL = self.getFullUrl('browse?')
        CHANNEL_URL = self.getFullUrl('c/')
        self.DEFAULT_ICON_URL = 'https://cdn.liveleak.com/80281E/ll_a_u/ll3/images/img_logo.png'
        self.MAIN_CAT_TAB = [{'category': 'tab_items', 'title': _('Items')},
                             {'category': 'tab_channels', 'title': _('Channels'), },
                             {'category': 'search', 'title': _('Search'), 'search_item': True, },
                             {'category': 'search_history', 'title': _('Search history'), }]
        
        self.ITEMS_CAT_TAB = [{'category': 'recent_items', 'title': 'Recent Items (Popular)', 'url': ITEMS_BROWSE_URL + 'selection=popular'},
                              {'category': 'recent_items', 'title': 'Recent Items (All)', 'url': ITEMS_BROWSE_URL + 'selection=all'},
                              {'category': 'recent_items', 'title': 'Feature Potential Items', 'url': ITEMS_BROWSE_URL + 'upcoming=1'},
                              {'category': 'recent_items', 'title': 'Top Items (Today)', 'url': ITEMS_BROWSE_URL + 'rank_by=day'},
                              {'category': 'recent_items', 'title': 'Top Items (This Week)', 'url': ITEMS_BROWSE_URL + 'rank_by=week'},
                              {'category': 'recent_items', 'title': 'Top Items (This Month)', 'url': ITEMS_BROWSE_URL + 'rank_by=month'},
                              {'category': 'recent_items', 'title': 'Top Items (All time)', 'url': ITEMS_BROWSE_URL + 'rank_by=all_time'}]
        
        self.CHANNEL_CAT_TAB = [{'category': 'channel', 'title': 'News & Politics', 'url': CHANNEL_URL + 'news'},
                                 {'category': 'channel', 'title': 'Yoursay', 'url': CHANNEL_URL + 'yoursay'},
                                 {'category': 'channel', 'title': 'Liveleakers', 'url': CHANNEL_URL + 'liveleakers'},
                                 {'category': 'channel', 'title': 'Must See', 'url': CHANNEL_URL + 'must_see'},
                                 {'category': 'channel', 'title': 'Ukraine', 'url': CHANNEL_URL + 'ukraine'},
                                 {'category': 'channel', 'title': 'Syria', 'url': CHANNEL_URL + 'syria'},
                                 {'category': 'channel', 'title': 'Entertainment', 'url': CHANNEL_URL + 'entertainment'},
                                 {'category': 'channel', 'title': 'WTF', 'url': CHANNEL_URL + 'wtf'},
                                 {'category': 'channel', 'title': 'Russia', 'url': CHANNEL_URL + 'russia'},
                                 {'category': 'channels', 'title': 'More', 'url': self.getFullUrl('/channels')} 
                               ] 
    
    def _checkNexPage(self, data, page):
        data = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'pagination'), ('</ul', '>'), False)[1]
        url = self.cm.ph.getSearchGroups(data, '''['"]([^'^"]*?page=%s&[^'^"]*?)['"]''' % (int(page) + 1))[0]
        if url == '':
            url = self.cm.ph.getSearchGroups(data, '''['"]([^'^"]*?page=%s)['"]''' % (int(page) + 1))[0]
        if url != '':
            return self.getFullUrl(url.replace('&amp;', '&'))
        else:
            return ''
            
    def listsTab(self, tab, cItem):
        printDBG("LiveLeak.listsMainMenu")
        for item in tab:
            params = dict(cItem)
            params.update(item)
            params['name'] = 'category'
            self.addDir(params)
    
    def _listItems(self, cItem, data, nextPage, nextCategory='video'):
        printDBG('_listItems start')

        data = re.compile('''<div[^>]+?items_outer[^>]+?>''', re.I).split(data)
        if len(data):
            del data[0]
        if len(data):
            data[-1] = data[-1].split('<nav', 1)[0]
            data[-1] = data[-1].split('<script', 1)[0]
        
        for item in data:
            params = dict(cItem)
            params['name'] = 'category'
            params['title'] = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''title=['"]([^"^']+?)['"]''')[0])
            if params['title'] == '':
                params['title'] = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<a', '</a>')[1])
            params['icon'] = self.cm.ph.getSearchGroups(item, 'src="([^"]+?\.jpg[^"]*?)"')[0]
            params['url'] = self.cm.ph.getSearchGroups(item, '<a[^>]+?href="([^"]+?)"')[0]
            params['desc'] = self.cleanHtmlStr(item.split('</a>', 1)[-1].replace('</p>', '[/br]'))
            if '' != params['url'] and '' != params['title']:
                if nextCategory == 'video':
                    self.addVideo(params)
                else:
                    params['category'] = nextCategory
                    self.addDir(params)
        if nextPage != '':
            params = dict(cItem)
            params.update({'name': 'category', 'title': _('Next page'), 'url': nextPage, 'page': str(int(cItem.get('page', '1')) + 1)})
            self.addDir(params)
                
    def listRecentItems(self, cItem):
        printDBG('listRecentItems start')
        page = cItem.get('page', '1')
        sts, data = self.cm.getPage(cItem['url'])
        if sts:
            nextPage = self._checkNexPage(data, page)
            data = self.cm.ph.getDataBeetwenNodes(data, ('<section', '>', 'content_main'), ('</section', '>'))[1]
            self._listItems(cItem, data, nextPage)
        
    def listChannels(self, cItem):
        printDBG('listChannels start')
        page = cItem.get('page', '1')
        sts, data = self.cm.getPage(cItem['url'])
        if sts:
            nextPage = self._checkNexPage(data, page)
            data = self.cm.ph.getDataBeetwenNodes(data, ('<section', '>', 'content_main'), ('</section', '>'))[1]
            self._listItems(cItem, data, nextPage, 'channel')
    
    def listChannelItems(self, cItem):
        printDBG('listChannelItems start')
        page = cItem.get('page', '1')
        sts, data = self.cm.getPage(cItem['url'])
        if sts:
            nextPage = self._checkNexPage(data, page)
            if page == '1':
                data = self.cm.ph.getDataBeetwenNodes(data, ('<section', '>', 'content_main'), ('</section', '>'))[1]
            self._listItems(cItem, data, nextPage)
        
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("LiveLeak.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        
        if 'items' == searchType:
            sort = config.plugins.iptvplayer.liveleak_searchsort.value
            params = dict(cItem)
            params.update({'category': 'recent_items', 'url': self.getFullUrl('browse?q=%s&sort_by=%s' % (searchPattern.replace(' ', '+'), sort))})
            self.listRecentItems(params)
        else:
            params = dict(cItem)
            params.update({'category': 'channels', 'url': self.getFullUrl('/channel?a=list&q=' + (searchPattern.replace(' ', '+')))})
            self.listChannels(params)
        
    def getLinksForVideo(self, cItem):
        printDBG("LiveLeak.getLinksForVideo [%s]" % cItem['url'])
        return self.up.getVideoLinkExt(cItem['url'])
    
    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('LiveLeak.handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", None)
        category = self.currItem.get("category", '')
        printDBG("LiveLeak.handleService: ---------> name[%s], category[%s] " % (name, category))
        searchPattern = self.currItem.get("search_pattern", searchPattern)
        self.currList = []
        
        if None == name:
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})
    #ITEMS TAB
        elif 'tab_items' == category:
            self.listsTab(self.ITEMS_CAT_TAB, self.currItem)
    #CHANNELS TAB
        elif 'tab_channels' == category:
            self.listsTab(self.CHANNEL_CAT_TAB, self.currItem)
    #LIST ITEMS
        elif 'recent_items' == category:
            self.listRecentItems(self.currItem)
    #BROWSE CHANNELS
        elif 'channels' == category:
            self.listChannels(self.currItem)
    #LIST CHANNEL ITEMS
        elif 'channel' == category:
            self.listChannelItems(self.currItem)
            
    #SEARCH
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category'}) 
            self.listSearchResult(cItem, searchPattern, searchType)
    #HISTORIA SEARCH
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, LiveLeak(), True)
        
    def getSearchTypes(self):
        searchTypesOptions = []
        searchTypesOptions.append((_("Items"), "items"))
        searchTypesOptions.append((_("Channel"), "channel"))
        return searchTypesOptions
