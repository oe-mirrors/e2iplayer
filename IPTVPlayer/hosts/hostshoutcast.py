# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify
from Plugins.Extensions.IPTVPlayer.libs.m3uparser import ParseM3u
###################################################

###################################################
# FOREIGN import
###################################################
try:
    import json
except Exception:
    import simplejson as json
###################################################


def gettytul():
    return 'http://shoutcast.com/'


class ShoutcastCom(CBaseHostClass):
    
    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'shoutcast.com', 'cookie': 'shoutcast.com.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.MAIN_URL = 'https://directory.shoutcast.com/'
        self.DEFAULT_ICON_URL = 'http://wiki.shoutcast.com/images/b/bd/Shoutcast.png'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate', 'Referer': self.getMainUrl(), 'Origin': self.getMainUrl()}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding': 'gzip, deflate', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': '*/*', 'Origin': self.getMainUrl()[:-1]})
        
        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.cacheGenres = {}
        
    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)
    
    def listMainMenu(self, cItem):
        printDBG("ShoutcastCom.listMainMenu")
        
        MAIN_CAT_TAB = [{'category': 'genres', 'title': _('Genres'), 'url': self.getMainUrl()}, 
                        {'category': 'search', 'title': _('Search'), 'search_item': True}, 
                        {'category': 'search_history', 'title': _('Search history')}, ]
        
        self.listsTab(MAIN_CAT_TAB, cItem)
        
    def listGenres(self, cItem, nextCategory):
        printDBG("ShoutcastCom.listGenres [%s]" % cItem)
        
        self.cacheGenres = {}
        
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<li', '>', 'main-genre'), ('</ul', '>'))
        for genreItem in data:
            itemsTab = []
            tmp = self.cm.ph.getDataBeetwenMarkers(genreItem, '<a', '</a>')[1]
            genreTitle = self.cleanHtmlStr(tmp)
            url = self.getFullUrl(self.cm.ph.getSearchGroups(genreItem, '''\shref=['"]([^'^"]+?)['"]''')[0])
            itemsTab.append({'title': _('All'), 'url': url})
            
            genreItem = genreItem.split('<ul', 1)[-1]
            genreItem = self.cm.ph.getAllItemsBeetwenMarkers(genreItem, '<a', '</a>')
            for item in genreItem:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0])
                title = self.cleanHtmlStr(item)
                itemsTab.append({'title': title, 'url': url})
                
            if len(itemsTab):
                params = {'good_for_fav': False, 'name': 'category', 'category': nextCategory, 'title': genreTitle, 'items': itemsTab}
                self.addDir(params)
            
    def listSubGenres(self, cItem, nextCategory):
        printDBG("ShoutcastCom.listSubGenres [%s]" % cItem)
        
        cItem = dict(cItem)
        itemsTab = cItem.pop('items', [])
        cItem.update({'good_for_fav': True, 'category': nextCategory, })
        self.listsTab(itemsTab, cItem)
            
    def listSort(self, cItem, nextCategory):
        printDBG("ShoutcastCom.listSort [%s]" % cItem)
        
    def listItems(self, cItem, searchPattern=''):
        printDBG("ShoutcastCom.listItems [%s]" % cItem)
        
        if searchPattern == '':
            sts, data = self.getPage(cItem['url'])
            if not sts:
                return
            
            data = self.cm.ph.getDataBeetwenMarkers(data, '</footer>', '</body>')[1]
            data = self.cm.ph.getDataBeetwenMarkers(data, 'loadStationsByGenre(', ');', False)[1]
            data = data.split(',')
            params = []
            for item in data:
                item = item.strip()
                if item[0] in ['"', "'"]:
                    item = item[1:-1]
                params.append(item)
            
            url = self.getFullUrl('/Home/BrowseByGenre')
            post_data = {'genrename': params[0]}
        else:
            url = self.getFullUrl('/Search')
            post_data = {'query': searchPattern}
            sts, data = self.getPage(url, post_data=post_data)
            if not sts:
                return
            
            url = self.getFullUrl('/Search/UpdateSearch')
            post_data = {'query': searchPattern}
        
        sts, data = self.getPage(url, post_data=post_data)
        if not sts:
            return
        
        try:
            data = byteify(json.loads(data))
            for item in data:
                title = self.cleanHtmlStr(item['Name'])
                stationId = str(item['ID'])
                desc = []
                desc.append(_('Genre: %s') % item['Genre'])
                desc.append(_('Listeners: %s') % item['Listeners'])
                desc.append(_('Bitrate: %s') % item['Bitrate'])
                if item['IsAACEnabled']:
                    type = 'AAC'
                else:
                    type = 'MP3'
                desc.append(_('Type: %s') % type)
                desc = ' | '.join(desc)
                #desc += '[/br] ' + self.cleanHtmlStr(item['CurrentTrack'])
                
                params = {'good_for_fav': True, 'station_id': stationId, 'title': title, 'url': self.getFullUrl('?station_id=' + stationId), 'desc': desc}
                self.addAudio(params)
                
        except Exception:
            printExc()
        
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("ShoutcastCom.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        self.listItems({}, searchPattern)
            
    def getLinksForVideo(self, cItem):
        printDBG("ShoutcastCom.getLinksForVideo [%s]" % cItem)
        linksTab = []
        
        stationId = cItem.get('station_id', '')
        
        url = 'http://yp.shoutcast.com/sbin/tunein-station.m3u?id=%s' % stationId
        
        sts, data = self.getPage(url)
        if not sts:
            return
        
        data = ParseM3u(data)
        for item in data:
            linksTab.append({'name': item['title'], 'url': item['uri'], 'need_resolve': 0})
        
        return linksTab
    
    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')
        
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')
        
        printDBG("handleService: |||| name[%s], category[%s] " % (name, category))
        self.cacheLinks = {}
        self.currList = []
        
    #MAIN MENU
        if name == None:
            self.listMainMenu({'name': 'category'})
        elif category == 'genres':
            self.listGenres(self.currItem, 'list_sub_genres')
        elif category == 'list_sub_genres':
            self.listSubGenres(self.currItem, 'list_items')
        elif category == 'list_sort':
            self.listSort(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem)
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
        
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, ShoutcastCom(), True, [])
    
