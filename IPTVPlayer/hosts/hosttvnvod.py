# -*- coding: utf-8 -*-
# Based on (root)/trunk/xbmc-addons/src/plugin.video.polishtv.live/hosts/ @ 419 - Wersja 605

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import CSelOneLink, printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.utils import clean_html
from Plugins.Extensions.IPTVPlayer.libs.crypto.cipher import aes_cbc, base
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
###################################################

###################################################
# FOREIGN import
###################################################
from Components.config import config, ConfigSelection, ConfigYesNo, getConfigListEntry
import urllib
import time
import binascii
from os import urandom as os_urandom
try:
    from hashlib import sha1
except ImportError:
    import sha
    sha1 = sha.new
###################################################


###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.TVNDefaultformat = ConfigSelection(default = "9999", choices = [("0", "Najgorsza"), ("1", "Bardzo niska"), ("2", "Niska"),  ("3", "Średnia"), ("4", "Standard"), ("5", "Wysoka"), ("6", "Bardzo wysoka"), ("7", "HD"), ("9999", "Najlepsza")])
config.plugins.iptvplayer.TVNUseDF = ConfigYesNo(default = False)
config.plugins.iptvplayer.TVNdevice = ConfigSelection(default = "_mobile_", choices = [("_mobile_", "Mobile"),("_tv_", "TV")])
config.plugins.iptvplayer.proxyenable = ConfigYesNo(default = False)
   
def GetConfigList():
    optionList = []

    optionList.append(getConfigListEntry("Domyślna jakość video:", config.plugins.iptvplayer.TVNDefaultformat))
    optionList.append(getConfigListEntry("Używaj domyślnej jakości video:", config.plugins.iptvplayer.TVNUseDF))
    #optionList.append(getConfigListEntry("TVN-Przedstaw się jako:", config.plugins.iptvplayer.TVNdevice))
    optionList.append(getConfigListEntry("TVN-korzystaj z proxy?", config.plugins.iptvplayer.proxyenable))

    return optionList
###################################################

def gettytul():
    return 'TVN Player'

class TvnVod(CBaseHostClass):
    ICON_URL     = 'http://redir.atmcdn.pl/scale/o2/tvn/web-content/m/%s?quality=50&dstw=290&dsth=287&type=1'
    
    QUALITIES_TABLE = { 
        'HD'            : 7,
        'Bardzo wysoka' : 6,
        'Wysoka'        : 5,
        'Standard'      : 4,
        'Średnia'       : 3,
        'Niska'         : 2,
        'Bardzo niska'  : 1,
    }
        
    SERVICE_MENU_TABLE = [
        "Kategorie",
        "Wyszukaj",
        "Historia wyszukiwania"
    ]
    
    def __init__(self):
        printDBG("TvnVod.__init__")
        CBaseHostClass.__init__(self, {'history':'TvnVod', 'history_store_type':True, 'proxyURL': config.plugins.iptvplayer.proxyurl.value, 'useProxy': config.plugins.iptvplayer.proxyenable.value})
        self.itemsPerPage = 30 # config.plugins.iptvplayer.tvp_itemsperpage.value
        self.DEFAULT_ICON_URL = 'https://upload.wikimedia.org/wikipedia/commons/thumb/f/fc/Player_%28TVN%29.svg/480px-Player_%28TVN%29.svg.png' 
        self.platforms = {
            'Panasonic': {
                'platform' : 'ConnectedTV',
                'terminal' : 'Panasonic',
                'authKey' : '064fda5ab26dc1dd936f5c6e84b7d3c2',
                'base_url' : 'http://api.tvnplayer.pl/api2',
                'header' : {'User-Agent':'Mozilla/5.0 (SmartHub; SMART-TV; U; Linux/SmartTV; Maple2012) AppleWebKit/534.7 (KHTML, like Gecko) SmartTV Safari/534.7', 'X-Api-Version':'3.1', 'Accept-Encoding':'gzip'},
                'api' : '3.1',
            },
            'Samsung': {
                'platform' : 'ConnectedTV',
                'terminal' : 'Samsung2',
                'authKey' : '453198a80ccc99e8485794789292f061',
                'base_url' : 'http://api.tvnplayer.pl/api2',
                'header' : {'User-Agent':'Mozilla/5.0 (SmartHub; SMART-TV; U; Linux/SmartTV; Maple2012) AppleWebKit/534.7 (KHTML, like Gecko) SmartTV Safari/534.7', 'X-Api-Version':'3.6', 'Accept-Encoding':'gzip'},
                'api' : '3.6',
            },
            'Android': {
                'platform' : 'Mobile',
                'terminal' : 'Android',
                'authKey' : 'b4bc971840de63d105b3166403aa1bea',
                'base_url' : 'http://api.tvnplayer.pl/api',
                'header' : {'User-Agent':'Apache-HttpClient/UNAVAILABLE (java 1.4)'},
                'api' : '3.0',
            },
            'Android2': {
                'platform' : 'Mobile',
                'terminal' : 'Android',
                'authKey' : 'b4bc971840de63d105b3166403aa1bea',
                'header' : {'User-Agent':'Apache-HttpClient/UNAVAILABLE (java 1.4)'},
                'base_url' : 'http://api.tvnplayer.pl/api',
                'api' : '2.0',
            },
            'Android3': {
                'platform' : 'Mobile',
                'terminal' : 'Android',
                'authKey' : '4dc7b4f711fb9f3d53919ef94c23890c',
                'base_url' : 'http://api.tvnplayer.pl/api',
                'header' : {'User-Agent':'Apache-HttpClient/UNAVAILABLE (java 1.4)'},
                'api' : '3.1',
            },
            'Android4': {
                'platform' : 'Mobile',
                'terminal' : 'Android',
                'authKey' : '4dc7b4f711fb9f3d53919ef94c23890c',
                'base_url' : 'http://api.tvnplayer.pl/api2',
                'header' : {'User-Agent':'Player/3.3.4 tablet Android/4.1.1 net/wifi', 'X-Api-Version':'3.7', 'Accept-Encoding':'gzip'},
                'api' : '3.7',
            },
        }
        
    def getDefaultPlatform(self):
        if '_tv_' == config.plugins.iptvplayer.TVNdevice.value:
            return 'Panasonic'
        return "Android4"
        
    def getBaseUrl(self, pl):
        url = self.platforms[pl]['base_url'] + '/?platform=%s&terminal=%s&format=json&authKey=%s&v=%s&' % (self.platforms[pl]['platform'], self.platforms[pl]['terminal'],  self.platforms[pl]['authKey'], self.platforms[pl]['api'] )
        if pl not in ['Android', 'Android2', 'Panasonic']:
            url += 'showContentContractor=free%2Csamsung%2Cstandard&'
        return url 
        
    def getHttpHeader(self, pl):
        return self.platforms[pl]['header']
        
    def _getJItemStr(self, item, key, default=''):
        try:
            v = item.get(key, None)
            if None == v:
                return default
        except Exception:
            return default
        return clean_html('%s' % v)
        
    def _getJItemNum(self, item, key, default=0):
        v = item.get(key, None)
        if None != v:
            try:
                NumberTypes = (int, long, float, complex)
            except NameError:
                NumberTypes = (int, long, float)
                
            if isinstance(v, NumberTypes):
                return v
        return default
        
    def _getIconUrl(self, cItem):
        iconUrl = ''
        try:
            thumbnails = cItem.get('thumbnail', [])
            if None != thumbnails:
                # prefer jpeg files
                pngUrl = ''
                for item in thumbnails:
                    tmp = self._getJItemStr(item, 'url')
                    if tmp.endswith('jpg') or tmp.endswith('jpeg'):
                        iconUrl = tmp
                        break
                    if tmp.endswith('png'): pngUrl = tmp
                if '' == iconUrl: iconUrl = pngUrl
                if '' != iconUrl: iconUrl = TvnVod.ICON_URL % iconUrl
        except Exception:
            printExc()
        return iconUrl
        
    def _generateToken(self, url):
        url = url.replace('http://redir.atmcdn.pl/http/','')
        SecretKey = 'AB9843DSAIUDHW87Y3874Q903409QEWA'
        iv = 'ab5ef983454a21bd'
        KeyStr = '0f12f35aa0c542e45926c43a39ee2a7b38ec2f26975c00a30e1292f7e137e120e5ae9d1cfe10dd682834e3754efc1733'
        salt = sha1()
        salt.update(os_urandom(16))
        salt = salt.hexdigest()[:32]
        tvncrypt = aes_cbc.AES_CBC(SecretKey, base.noPadding(), keySize=32)
        key = tvncrypt.decrypt(binascii.unhexlify(KeyStr), iv=iv)[:32]
        expire = 3600000L + long(time.time()*1000) - 946684800000L
        unencryptedToken = "name=%s&expire=%s\0" % (url, expire)
        pkcs5_pad = lambda s: s + (16 - len(s) % 16) * chr(16 - len(s) % 16)
        pkcs5_unpad = lambda s : s[0:-ord(s[-1])]
        unencryptedToken = pkcs5_pad(unencryptedToken)
        tvncrypt = aes_cbc.AES_CBC(binascii.unhexlify(key), padding=base.noPadding(), keySize=16)
        encryptedToken = tvncrypt.encrypt(unencryptedToken, iv=binascii.unhexlify(salt))
        encryptedTokenHEX = binascii.hexlify(encryptedToken).upper()
        return "http://redir.atmcdn.pl/http/%s?salt=%s&token=%s" % (url, salt, encryptedTokenHEX)
        
    def listsCategories(self, cItem, searchCategories=False):
        printDBG("TvnVod.listsCategories cItem[%s]" % cItem)
        pl = 'Panasonic' #self.getDefaultPlatform()
        
        searchMode = False
        page = 1 + cItem.get('page', 0)
        if 'search' == cItem.get('category', None):
            searchMode = True
            urlQuery  = '&sort=newest&m=getSearchItems&page=%d&query=%s' % (page, cItem['pattern'])
            if cItem.get('search_category', False):
                pl = 'Android4'

        elif None != cItem.get('category', None) and None != cItem.get('id', None):
            groupName = 'items'
            urlQuery = '&type=%s&id=%s&limit=%s&page=%s&sort=newest&m=getItems' % (cItem['category'], cItem['id'], self.itemsPerPage, page)
            if 0 < cItem.get('season', 0):
                urlQuery += "&season=%d" % cItem.get('season', 0)
        else:
            groupName = 'categories'
            urlQuery = '&m=mainInfo'
        
        try:
            url = self.getBaseUrl(pl) + urlQuery
            sts, data = self.cm.getPage(url, { 'header': self.getHttpHeader(pl) })
            data = json_loads(data)
            
            if 'success' != data['status']:
                printDBG("TvnVod.listsCategories status[%s]" % data['status'])
                return 
                
            countItem = self._getJItemNum(data, 'count_items', None)
            if None != countItem and countItem > self.itemsPerPage * page:
                showNextPage = True
            else:
                showNextPage = False
            
            catalogs = False
            if searchMode:
                seasons = None
                tmp = []
                for resItem in data.get('vodProgramItems', {}).get('category', []):
                    tmp.extend(resItem.get('items', []))
                for resItem in data.get('vodArticleItems', {}).get('program', []):
                    tmp.extend(resItem.get('items', []))
                tmp.extend(data.get('items', []))
                data = tmp
                tmp = None
            else:
                seasons  = data.get('seasons', None)
                # some fix for sub-categories
                # and 0 < len(data.get('items', []))
                if 0 < len(data.get('categories', [])) and cItem.get('previd', '') != cItem.get('id', ''):
                    catalogs = True
                    groupName = 'categories'
                    showNextPage = False
                data = data[groupName]
            
            showSeasons = False
            if None != seasons and 0 == cItem.get('season', 0):
                showSeasons = True
                numSeasons = len(seasons)
            else:
                numSeasons = 0

            if 0 != cItem.get('season', 0) or cItem.get('season', 0) == numSeasons:
                for item in data:
                    category = self._getJItemStr(item, 'type', '')
                    if category  in ['stream', 'catalog_with_widget', 'pauses', 'favorites']: continue
                    id       = self._getJItemStr(item, 'id', '')
                    # some fix for sub-categories
                    if catalogs:
                        if 'category' == category:
                            category = 'catalog'
                        if '0' == id:
                            id = cItem['id']
                    
                    # get title 
                    title = self._getJItemStr(item, 'name', '')
                    if '' == title: title = self._getJItemStr(item, 'title', '')
                    if '' == title:
                        if category == 'recommended': continue
                        else: title = 'Brak nazwy'
                    tmp = self._getJItemStr(item, 'episode', '')
                    if tmp not in ('', '0'): title += ", odcinek " + tmp
                    tmp = self._getJItemStr(item, 'season', '')
                    if tmp not in ('', '0'): title += ", sezon " + tmp
                    try:
                        tmp = self._getJItemStr(item, 'start_date', '')
                        if '' != tmp:
                            tmp = time.strptime(tmp, "%Y-%m-%d %H:%M")
                            if tmp > time.localtime():
                                title += " (planowany)"
                    except Exception:
                        printExc()
                    
                    # get description
                    desc = self._getJItemStr(item, 'lead', '')
                    # get icon
                    icon = self._getIconUrl(item)
                
                    params = { 'id'          : id,
                               'previd'      : cItem.get('id', ''),
                               'title'       : title,
                               'desc'        : desc,
                               'icon'        : icon,
                               'category'    : category,
                               'season'      : 0,
                               'good_for_fav': True, }
                    if 'episode' == category:
                        if cItem.get('search_category', False):
                            continue
                        self.addVideo(params)
                    else:
                        if title in ['SPORT', 'Live', 'STREFY', 'KONTYNUUJ OGLĄDANIE', 'ULUBIONE', 'PAKIETY']:
                            continue
                        self.addDir(params)
            else:
                showNextPage = False
            
            if showSeasons:
                for season in seasons:
                    params = { 'id'          : cItem['id'],
                               'previd'      : cItem.get('id', ''),
                               'title'       : self._getJItemStr(season, 'name', ''),
                               'desc'        : '',
                               'icon'        : self._getIconUrl(season),
                               'category'    : cItem['category'], #self._getJItemStr(season, 'type', ''),
                               'season'      : self._getJItemNum(season, 'id', 0),
                               'good_for_fav': True, }
                    self.addDir(params)
            if showNextPage:
                params = dict(cItem)
                params.update({'good_for_fav':False, 'title':_('Next page'), 'page': page, 'icon':'', 'desc':''})
                self.addDir(params)
        except Exception: 
            printExc()

        
    def listSearchResult(self, cItem, pattern, searchType):
        printDBG("TvnVod.listSearchResult pattern[%s], searchType[%s]" % (pattern, searchType))
        params = dict(cItem)
        params.update({ 'id'       : 0,
                       'title'    : '',
                       'desc'     : '',
                       'icon'     : '',
                       'category' : 'search',
                       'pattern'  : pattern,
                       'season'   : 0,
                     })
        params2 = dict(params)
        params2['search_category'] = True
        self.listsCategories(params2)
        self.listsCategories(params)

    def listsMainMenu(self):
        for item in TvnVod.SERVICE_MENU_TABLE:
            params = {'name': 'category', 'title': item, 'category': item}
            if item == 'Wyszukaj':
                params['category'] = 'search'
                params['search_item'] = True
            if item == 'Historia wyszukiwania':
                params['category'] = 'search_history'
            self.addDir(params)
    
    def getVideoLinks(self, url):
        printDBG("TvnVod.getVideoLinks url[%s]" % url)
        url = strwithmeta(url)
        pl = url.meta.get('tvn_platform', self.getDefaultPlatform())
        videoUrl = ''
        if len(url) > 0:
            if 'Android' in pl:
                videoUrl = self._generateToken(url)
            elif 'Panasonic' in pl:
                videoUrl = url
            else:
                sts, data  = self.cm.getPage(url, { 'header': self.getHttpHeader(pl) })
                if sts and data.startswith('http'):
                    videoUrl =  data.encode('utf-8')
        urlTab = []
        videoUrl = strwithmeta(videoUrl, { 'header': self.getHttpHeader(pl) })
        if self.cm.isValidUrl(videoUrl): urlTab.append({'name':'direct', 'url':videoUrl})
        return urlTab
            
    def getLinksForVideo(self, cItem):
        return self.getLinks(cItem['id'])
    
    def getLinks(self, id):
        printDBG("TvnVod.getLinks cItem.id[%r]" % id )
        videoUrls = []
        
        for pl in ['Panasonic', 'Samsung', 'Android2']:#, 'Android4']: #'Android', ''Samsung', 
            if pl in ['Android', 'Android2', 'Panasonic']:
                url = '&type=episode&id=%s&limit=%d&page=1&sort=newest&m=%s' % (id, self.itemsPerPage, 'getItem')
            else:
                url = 'm=getItem&id=%s&android23video=1&deviceType=Tablet&os=4.1.1&playlistType=&connectionType=WIFI&deviceScreenWidth=1920&deviceScreenHeight=1080&appVersion=3.3.4&manufacturer=unknown&model=androVMTablet' % id
            url = self.getBaseUrl(pl) + url
            
            sts, data = self.cm.getPage(url, { 'header': self.getHttpHeader(pl) })
            if not sts: continue
            try:
                data = json_loads(data)
                if 'success' == data['status']:
                    data = data['item']
                    # videoTime = 0
                    # tmp = self._getJItemStr(data, 'run_time', '')
                    # if '' != tmp:
                        # tmp = tmp.split(":")
                        # videoTime = int(tmp[0])*60*60+int(tmp[1])*60+int(tmp[2])
                     
                    plot = self._getJItemStr(data, 'lead', '')
                    printDBG("data:\n%s\n" % data)
                    videos = data['videos']['main']['video_content']
                    if None == videos:
                        SetIPTVPlayerLastHostError("DRM protection.")
                    else:
                        for video in videos:
                            url = self._getJItemStr(video, 'url', '')
                            if '' == url:
                                SetIPTVPlayerLastHostError("DRM protection.")
                            #    url = self._getJItemStr(video, 'src', '')
                            if '' != url:
                                url = strwithmeta(url, {'tvn_platform':pl})
                                qualityName = self._getJItemStr(video, 'profile_name', '')
                                videoUrls.append({'name':qualityName, 'profile_name':qualityName, 'url':url, 'need_resolve':1})
                    if  1 < len(videoUrls):
                        max_bitrate = int(config.plugins.iptvplayer.TVNDefaultformat.value)
                        def __getLinkQuality( itemLink ):
                            return int(TvnVod.QUALITIES_TABLE.get(itemLink['profile_name'], 9999))
                        videoUrls = CSelOneLink(videoUrls, __getLinkQuality, max_bitrate).getSortedLinks()
                        if config.plugins.iptvplayer.TVNUseDF.value:
                            videoUrls = [videoUrls[0]]
            except Exception: printExc()
            if len(videoUrls):
                break
        return videoUrls
        
    def getLinksForFavourite(self, fav_data):
        try:
            cItem = json_loads(fav_data)
            return self.getLinks(cItem['id'])
        except Exception: printExc()
        return self.getLinks(fav_data)

    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('TvnVod..handleService start')
        
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        
        # clear hosting tab cache
        self.linksCacheCache = {}

        name     = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG( "TvnVod.handleService: ---------> name[%s], category[%s] " % (name, category) )
        self.currList = []
        
    #MAIN MENU
        if name == None:
            self.listsMainMenu()
    #SEARCH
        elif category in ["search", "search_next_page"]:
            pattern = urllib.quote_plus(searchPattern)
            cItem = dict(self.currItem)
            cItem.update({'search_item':False, 'name':'category'}) 
            self.listSearchResult(cItem, pattern, searchType)
    #HISTORIA SEARCH
        elif category == "search_history":
            self.listsHistory({'name':'history', 'category': 'search'}, 'desc', _("Type: "))
    #KATEGORIE
        else:
            self.listsCategories(self.currItem)
        CBaseHostClass.endHandleService(self, index, refresh)

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, TvnVod(), True, [CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO])