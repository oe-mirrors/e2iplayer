# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
###################################################

###################################################
# FOREIGN import
###################################################
import random
###################################################



def gettytul():
    return 'http://radiostacja.pl/'

class RadiostacjaPl(CBaseHostClass):
    
    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'radiostacja.pl', 'cookie':'radiostacja.pl.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.MAIN_URL = 'http://www.radiostacja.pl/'
        self.DEFAULT_ICON_URL = 'http://is3.mzstatic.com/image/thumb/Purple122/v4/82/c4/6f/82c46f38-3532-e414-530e-33e5d0be2614/source/392x696bb.jpg'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT':'1', 'Accept': 'text/html', 'Accept-Encoding':'gzip, deflate', 'Referer':self.getMainUrl(), 'Origin':self.getMainUrl()}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding':'gzip, deflate', 'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8', 'Accept':'*/*', 'Origin':self.getMainUrl()[:-1]})
        
        self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.cache = {}
        
    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)
    
    def listMainMenu(self, cItem):
        printDBG("RadiostacjaPl.listMainMenu")
        
        MAIN_CAT_TAB = [{'category':'live', 'title': 'Stacje Radiowe', 'f_cache':'live', 'url':self.getFullUrl('/data/mobile/live.json')}, 
                        {'category':'channels', 'title': 'Kanały Muzyczne', 'f_cache':'muzyczne', 'url':self.getFullUrl('/data/mobile/muzyczne_android.json')}, 
                        {'category':'djsety', 'title': 'Sety Muzyczne', 'f_cache':'podcasty', 'url':self.getFullUrl('/data/mobile/podcasty_android.json'), 'f_key':'djsety'}, 
                       ]
        
        self.listsTab(MAIN_CAT_TAB, cItem)
        TAB = [{'good_for_fav':True, 'url':'http://weszlo.fm/audycja-na-zywo/', 'title':'http://weszlo.fm/', 'icon':'https://images.radio.co/station_logos/s7d70a7895.20180131023319.jpg', 'desc':'http://weszlo.fm/audycja-na-zywo/'}, ]
        for item in TAB:
            params = dict(cItem)
            params.update(item)
            self.addAudio(params)
    
    def listLive(self, cItem, nextCategory1, nextCategory2):
        printDBG("RadiostacjaPl.listGenres [%s]" % cItem)
        
        params = dict(cItem)
        params.update({'good_for_fav':True, 'title': 'Radia RMFON', 'category':nextCategory2, 'f_cache':'rmfon', 'url':'http://rmfon.pl/json/app.txt', 'icon':'http://www.programosy.pl/download/screens/13748/android-rmfon-1_s.png'})
        self.addDir(params)
        
        CAT_TAB = [{'good_for_fav':True, 'title': 'Radia ZET', 'f_key':'eurozet'},
                   {'good_for_fav':True, 'title': 'Radia Lokalne', 'f_key':'lokalne'}]
        
        cItem = dict(cItem)
        cItem['category'] = nextCategory1
        self.listsTab(CAT_TAB, cItem)
        
    def _fillCache(self, cItem):
        if cItem['f_cache'] not in self.cache:
            sts, data = self.getPage(cItem['url'])
            if not sts:
                return
            
            try:
                data = json_loads(data)
                self.cache[cItem['f_cache']] = data
            except Exception:
                printExc()
        
    def listItemsFromCache(self, cItem):
        printDBG("RadiostacjaPl.listItems [%s]" % cItem)
        self._fillCache(cItem)
        
        try:
            cacheKey = cItem['f_cache']
            tabKey = cItem['f_key']
            data = self.cache[cacheKey][tabKey]
            self.listItems(cItem, data)
        except Exception:
            printExc()
        
    def listItems(self, cItem, data):
        printDBG("RadiostacjaPl.listItems [%s]" % cItem)
        for item in data:
            title = self.cleanHtmlStr(item['name'])
            icon = self.cleanHtmlStr(item['image'])
            url = self.cleanHtmlStr(item['stream'])
            params = {'title':title, 'url':url, 'icon':icon}
            self.addAudio(params)
            
    def listChannels(self, cItem):
        printDBG("RadiostacjaPl.listGenres [%s]" % cItem)
        self._fillCache(cItem)
        
        CAT_TAB = [{'good_for_fav':True, 'category':'list_items', 'title': 'Wszystkie', 'f_key':'muzyczne'},
                   {'good_for_fav':True, 'category':'list_genres', 'title': 'Nastroje', 'f_key':'kategorie'}]
        
        cItem = dict(cItem)
        cItem.pop('category', None)
        self.listsTab(CAT_TAB, cItem)
            
    def listGenres(self, cItem, nextCategory):
        printDBG("RadiostacjaPl.listGenres [%s]" % cItem)
        self._fillCache(cItem)
        
        try:
            cacheKey = cItem['f_cache']
            tabKey = cItem['f_key']
            
            for idx in range(len(self.cache[cacheKey][tabKey])):
                channel = self.cache[cacheKey][tabKey][idx]
                title = self.cleanHtmlStr(channel['name'])
                icon = self.cleanHtmlStr(channel['logo'])
                params = dict(cItem)
                params.update({'good_for_fav':False, 'category':nextCategory, 'title':title, 'icon':icon, 'f_idx':idx})
                self.addDir(params)
        except Exception:
            printExc()
            
    def listChannel(self, cItem):
        printDBG("RadiostacjaPl.listChannelsItems [%s]" % cItem)
        try:
            cacheKey = cItem['f_cache']
            tabKey = cItem['f_key']
            idx = cItem['f_idx']
            data = self.cache[cacheKey][tabKey][idx]['channels']
            self.listItems(cItem, data)
        except Exception:
            printExc()
            
    def listDJSety(self, cItem, nextCategory):
        printDBG("RadiostacjaPl.listDJSety [%s]" % cItem)
        self._fillCache(cItem)
        
        try:
            cacheKey = cItem['f_cache']
            tabKey = cItem['f_key']
            for idx in range(len(self.cache[cacheKey][tabKey])):
                content = self.cache[cacheKey][tabKey][idx]['content']
                title = self.cleanHtmlStr(content['name'])
                icon = self.cleanHtmlStr(content['logo'])
                params = dict(cItem)
                params.update({'good_for_fav':False, 'category':nextCategory, 'title':title, 'icon':icon, 'f_idx':idx})
                self.addDir(params)
        except Exception:
            printExc()
            
    def listDJ(self, cItem):
        printDBG("RadiostacjaPl.listDJ [%s]" % cItem)
        try:
            cacheKey = cItem['f_cache']
            tabKey = cItem['f_key']
            idx = cItem['f_idx']
            data = self.cache[cacheKey][tabKey][idx]['content']['data']
            for item in data:
                title = self.cleanHtmlStr(item['name'])
                url = self.cleanHtmlStr(item['file'])
                params = {'title':title, 'url':url, 'icon':cItem.get('icon', '')}
                self.addAudio(params)
        except Exception:
            printExc()
            
    ############################################################
    def listRMF(self, cItem, nextCategory):
        printDBG("RadiostacjaPl.listRMF [%s]" % cItem)
        self._fillCache(cItem)
        
        try:
            cacheKey = cItem['f_cache']
            for item in self.cache[cacheKey]['categories']:
                if 0 == len(item['ids']):
                    continue
                title = self.cleanHtmlStr(item['name'])
                params = dict(cItem)
                params.update({'good_for_fav':True, 'category':nextCategory, 'title':title, 'f_id':item['id']})
                self.addDir(params)
        except Exception:
            printExc()
            
    def listRMFItems(self, cItem):
        printDBG("RadiostacjaPl.listRMFItems [%s]" % cItem)
        self._fillCache(cItem)
        
        try:
            cacheKey = cItem['f_cache']
            ids = None
            if 'f_id' in cItem:
                for item in self.cache[cacheKey]['categories']:
                    if item['id'] == cItem['f_id']:
                        ids = item['ids']
            
            for item in self.cache[cacheKey]['stations']:
                if ids != None and item['id'] not in ids:
                    continue
                title = self.cleanHtmlStr(item['name'])
                icon = item['defaultart']
                params = {'good_for_fav':True, 'title':title, 'url':'http://www.rmfon.pl/play,%s' % item['id'], 'icon':icon}
                self.addAudio(params)
        except Exception:
            printExc()
        
    def getLinksForVideo(self, cItem):
        printDBG("RadiostacjaPl.getLinksForVideo [%s]" % cItem)
        linksTab = []
        if 'weszlo.fm' in cItem['url']:
            sts, data = self.getPage(cItem['url'])
            if not sts:
                return []
            data = self.cm.ph.getDataBeetwenNodes(data, ('<div ', '>', 'radioplayer'), ('<', '>'))[1]
            url = self.cm.ph.getSearchGroups(data, '''\sdata\-src=['"](https?://[^'^"]+?)['"]''')[0]
            linksTab.append({'name':'direct', 'url':url, 'need_resolve':0})
        elif 'rmfon.pl' in cItem['url']:
            url = 'http://www.rmfon.pl/stacje/flash_aac_%s.xml.txt' % cItem['url'].split(',')[-1]
            sts, data = self.getPage(url)
            if not sts:
                return []
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<playlist', '</playlist')
            for playlistItem in data:
                if 'playlistMp3' in playlistItem:
                    title = 'MP3'
                else:
                    title = 'AAC'
                tmp = []
                playlistItem = self.cm.ph.getAllItemsBeetwenNodes(playlistItem, ('<item', '>'), ('</item', '>'), False)
                for item in playlistItem:
                    url = item.strip()
                    if not self.cm.isValidUrl(url):
                        continue
                    tmp.append({'name':title, 'url':url, 'need_resolve':0})
                if len(tmp):
                    linksTab.append(random.choice(tmp))
        else:
            linksTab = [{'name':'stream', 'url':cItem['url'], 'need_resolve':0}]
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
            self.listMainMenu({'name':'category'})
    # LIVE
        elif category == 'live':
            self.listLive(self.currItem, 'list_items', 'list_rmf')
        elif category == 'list_items':
            self.listItemsFromCache(self.currItem)
    # CHANNELS
        elif category == 'channels':
            self.listChannels(self.currItem)
        elif category == 'list_genres':
            self.listGenres(self.currItem, 'list_channel')
        elif category == 'list_channel':
            self.listChannel(self.currItem)
    # DJSETY
        elif category == 'djsety':
            self.listDJSety(self.currItem, 'list_dj')
        elif category == 'list_dj':
            self.listDJ(self.currItem)
    # RMFON
        elif category == 'list_rmf':
            self.listRMF(self.currItem, 'list_rmf_items')
        elif category == 'list_rmf_items':
            self.listRMFItems(self.currItem)
        
        CBaseHostClass.endHandleService(self, index, refresh)

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, RadiostacjaPl(), True, [])
    
