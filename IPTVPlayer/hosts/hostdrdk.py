# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem, RetHost, CUrlItem
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetLogoDir, byteify
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, getF4MLinksWithMeta
from Plugins.Extensions.IPTVPlayer.libs.dk_channels import TV2RChannel
###################################################

###################################################
# FOREIGN import
###################################################
try:
    import json
except Exception:
    import simplejson as json
from Components.config import config, ConfigText, getConfigListEntry
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.drdk_myip    = ConfigText(default="213.173.226.190", fixed_size=False)

def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Geolocation IP:"), config.plugins.iptvplayer.drdk_myip))
    return optionList
###################################################


def gettytul():
    return 'http://dr.dk/'

class DRDK(CBaseHostClass):
    MAIN_URL    = 'http://dr.dk/'

    MAIN_CAT_TAB = [{'category':'dr_live_channels', 'channel_type':'video', 'title': _('TV channels'), 'url':MAIN_URL+'mu-online/api/1.0/channel/all-active-dr-tv-channels', 'icon':''},
                    {'category':'dr_live_channels', 'channel_type':'audio', 'title': _('Radio stations'), 'url':MAIN_URL+'mu-online/api/1.0/channel/all-active-dr-radio-channels', 'icon':''},
                    #{'category':'latest_series',      'title': _('Latest series'), 'url':MAIN_URL, 'icon':''},
                    #{'category':'genres_movies',      'title': _('Movies'), 'url':MAIN_URL+'filmy', 'icon':''},
                    #{'category':'genres_series',      'title': _('Series'), 'url':MAIN_URL+'seriale', 'icon':''},
                    #{'category':'search',             'title': _('Search'), 'search_item':True},
                    #{'category':'search_history',     'title': _('Search history')} 
                    ]
 
    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'DRDK', 'cookie':'dr.dk.cookie'})
        if '' != config.plugins.iptvplayer.drdk_myip.value:
            self.cm.HEADER = {'X-Forwarded-For':config.plugins.iptvplayer.drdk_myip.value}
        self.tv2r = TV2RChannel()
        
    def _getFullUrl(self, url):
        if 0 < len(url) and not url.startswith('http'):
            url =  self.MAIN_URL + url
        if not self.MAIN_URL.startswith('https://'):
            url = url.replace('https://', 'http://')
        return url
        
    def _getIcon(self, Slug):
        url = MAIN_URL + 'api/1.2/asset/{0}?width={1}&height={2}&crop={3}&raw={4}'.format(Slug, )

    def listsTab(self, tab, cItem, type='dir'):
        printDBG("DRDK.listsTab")
        for item in tab:
            params = dict(cItem)
            params.update(item)
            params['name']  = 'category'
            if type == 'dir':
                self.addDir(params)
            else:
                self.addVideo(params)
            
    def listLiveChannels(self, cItem):
        printDBG("listLiveChannels")
        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return
        try:
            if 'video' == cItem['channel_type']:
                video = True
            else:
                video = False
            data = byteify(json.loads(data))
            #if video: data.sort(key=lambda item: item["WebChannel"])
            for item in data:
                if item.get("WebChannel", False):
                    continue
                item.update({'title':item['Title'], 'icon':item.get('PrimaryImageUri')})
                if video:
                    self.addVideo(item)
                else:
                    self.addAudio(item)
            if video:
                data = self.tv2r.getChannels()
                for item in data:
                    params = {'title':item['title'], 'Type':'tv2r', 'tv2r_data':item}
                    self.addVideo(params)
        except Exception:
            printExc()
        
    def getLinksForVideo(self, cItem):
        printDBG("DRDK.getLinksForVideo [%s]" % cItem)
        urlTab = []
        
        try:
            if cItem["Type"] == "Channel":
                for serv in cItem["StreamingServers"]:
                    if "HLS" not in serv["LinkType"]:
                        continue 
                    for qual in serv["Qualities"]:
                        for stream in qual["Streams"]:
                            url   = self.up.decorateUrl(serv["Server"] + "/" + stream["Stream"])
                            title = serv["LinkType"] #+ " [{0}Kbps]".format(qual["Kbps"])
                            ip    = config.plugins.iptvplayer.drdk_myip.value
                            if '' != ip:
                                url.meta['X-Forwarded-For'] = ip
                            urlTab.append({'name':title, 'url': url, 'need_resolve':1})
            elif cItem["Type"] == "tv2r":
                urls = self.tv2r.getLinksForChannel(cItem['tv2r_data'])
                for item in urls:
                    url   = self.up.decorateUrl(item['url'])
                    title = item['name']
                    ip    = config.plugins.iptvplayer.drdk_myip.value
                    if '' != ip:
                        url.meta['X-Forwarded-For'] = ip
                    urlTab.append({'name':title, 'url': url, 'need_resolve':1})
        except Exception:
            printExc()
        
        return urlTab
        
    def getVideoLinks(self, baseUrl):
        printDBG("Movie4kTO.getVideoLinks [%s]" % baseUrl)
        urlTab = []
        iptvProto = baseUrl.meta['iptv_proto']
        if iptvProto == 'm3u8':
            urlTab = getDirectM3U8Playlist(baseUrl)
        elif iptvProto == 'f4m':
            urlTab = getF4MLinksWithMeta(baseUrl)
        else:
            urlTab = [{'name':'direct', 'url':baseUrl}]
        return urlTab
        
    def getFavouriteData(self, cItem):
        return cItem['url']
        
    def getLinksForFavourite(self, fav_data):
        return self.getLinksForVideo({'url':fav_data})

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')
        
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name     = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG( "handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category) )
        self.currList = []
        
    #MAIN MENU
        if name == None:
            self.listsTab(self.MAIN_CAT_TAB, {'name':'category'})
    #MOVIES
        elif category == 'dr_live_channels':
            self.listLiveChannels(self.currItem)
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
        CHostBase.__init__(self, DRDK(), True) #, [CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO])

    def getLogoPath(self):
        return RetHost(RetHost.OK, value=[GetLogoDir('drdklogo.png')])
    
    def getLinksForVideo(self, Index=0, selItem=None):
        retCode = RetHost.ERROR
        retlist = []
        if not self.isValidIndex(Index):
            return RetHost(retCode, value=retlist)
        
        urlList = self.host.getLinksForVideo(self.host.currList[Index])
        for item in urlList:
            retlist.append(CUrlItem(item["name"], item["url"], item["need_resolve"]))

        return RetHost(RetHost.OK, value=retlist)
    # end getLinksForVideo
    
    def getResolvedURL(self, url):
        # resolve url to get direct url to video file
        retlist = []
        urlList = self.host.getVideoLinks(url)
        for item in urlList:
            need_resolve = 0
            retlist.append(CUrlItem(item["name"], item["url"], need_resolve))

        return RetHost(RetHost.OK, value=retlist)
    
    def converItem(self, cItem):
        hostList = []
        searchTypesOptions = [] # ustawione alfabetycznie
        #searchTypesOptions.append((_("Movies"), "movies"))
        #searchTypesOptions.append((_("Series"), "series"))
    
        hostLinks = []
        type = CDisplayListItem.TYPE_UNKNOWN
        possibleTypesOfSearch = None

        if 'category' == cItem['type']:
            if cItem.get('search_item', False):
                type = CDisplayListItem.TYPE_SEARCH
                possibleTypesOfSearch = searchTypesOptions
            else:
                type = CDisplayListItem.TYPE_CATEGORY
        elif cItem['type'] == 'video':
            type = CDisplayListItem.TYPE_VIDEO
        elif 'more' == cItem['type']:
            type = CDisplayListItem.TYPE_MORE
        elif 'audio' == cItem['type']:
            type = CDisplayListItem.TYPE_AUDIO
            
        if type in [CDisplayListItem.TYPE_AUDIO, CDisplayListItem.TYPE_VIDEO]:
            url = cItem.get('url', '')
            if '' != url:
                hostLinks.append(CUrlItem("Link", url, 1))
            
        title       =  cItem.get('title', '')
        description =  cItem.get('desc', '')
        icon        =  cItem.get('icon', '')
        
        return CDisplayListItem(name=title,
                                    description=description,
                                    type=type,
                                    urlItems=hostLinks,
                                    urlSeparateRequest=1,
                                    iconimage=icon,
                                    possibleTypesOfSearch=possibleTypesOfSearch)
    # end converItem

    def getSearchItemInx(self):
        try:
            list = self.host.getCurrList()
            for i in range( len(list) ):
                if list[i]['category'] == 'search':
                    return i
        except Exception:
            printDBG('getSearchItemInx EXCEPTION')
            return -1

    def setSearchPattern(self):
        try:
            list = self.host.getCurrList()
            if 'history' == list[self.currIndex]['name']:
                pattern = list[self.currIndex]['title']
                search_type = list[self.currIndex]['search_type']
                self.host.history.addHistoryItem( pattern, search_type)
                self.searchPattern = pattern
                self.searchType = search_type
        except Exception:
            printDBG('setSearchPattern EXCEPTION')
            self.searchPattern = ''
            self.searchType = ''
        return
