# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.ihost import IHost, CDisplayListItem, RetHost, CUrlItem
import Plugins.Extensions.IPTVPlayer.libs.pCommon as pCommon
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, GetLogoDir, GetTmpDir, GetCookieDir, printExc, GetPluginDir, CSearchHistoryHelper, byteify, IsExecutable, iptv_system
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser 
from Plugins.Extensions.IPTVPlayer.libs.m3uparser import ParseM3u
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import decorateUrl, getDirectM3U8Playlist, unpackJSPlayerParams, TEAMCASTPL_decryptPlayerParams
from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.utils import clean_html 
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError, GetIPTVNotify, GetIPTVSleep
from Plugins.Extensions.IPTVPlayer.libs import ph
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute
###################################################
# FOREIGN import
###################################################
import re, urllib, base64, urllib2
try:
    import simplejson
except:
    import json as simplejson 
from Tools.Directories import resolveFilename, SCOPE_PLUGINS
from Components.config import config, ConfigSelection, ConfigYesNo, ConfigInteger, getConfigListEntry, ConfigText
from os import remove as os_remove, path as os_path, system as os_system
###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.ilepozycji = ConfigInteger(8, (1, 99))  
config.plugins.iptvplayer.religia = ConfigYesNo(default = True)  
config.plugins.iptvplayer.natanek = ConfigInteger(8, (1, 999))  
config.plugins.iptvplayer.infoupdate = ConfigYesNo(default = False)

def GetConfigList():
    optionList = []
    optionList.append( getConfigListEntry( "Info IPTV Player ile pozycji:", config.plugins.iptvplayer.ilepozycji) )
    optionList.append( getConfigListEntry( "Transmisje religijne:", config.plugins.iptvplayer.religia) )
    optionList.append( getConfigListEntry( "Natanek ile pozycji:", config.plugins.iptvplayer.natanek) )
    optionList.append( getConfigListEntry( "Wyświetlaj ZMIANY W WERSJI :", config.plugins.iptvplayer.infoupdate) )

    return optionList
###################################################
###################################################
# Title of HOST
###################################################
def gettytul():
    return 'Info version'


class IPTVHost(IHost):
    LOGO_NAME = 'infologo.png'

    def __init__(self):
        printDBG( "init begin" )
        self.host = Host()
        self.prevIndex = []
        self.currList = []
        self.prevList = []
        printDBG( "init end" )
    
    def getLogoPath(self):  
        return RetHost(RetHost.OK, value = [ GetLogoDir(self.LOGO_NAME) ])

    def getInitList(self):
        printDBG( "getInitList begin" )
        self.prevIndex = []
        self.currList = self.host.getInitList()
        self.prevList = []
        printDBG( "getInitList end" )
        return RetHost(RetHost.OK, value = self.currList)

    def getListForItem(self, Index = 0, refresh = 0, selItem = None):
        printDBG( "getListForItem begin" )
        self.prevIndex.append(Index)
        self.prevList.append(self.currList)
        self.currList = self.host.getListForItem(Index, refresh, selItem)
        printDBG( "getListForItem end" )
        return RetHost(RetHost.OK, value = self.currList)

    def getPrevList(self, refresh = 0):
        printDBG( "getPrevList begin" )
        if(len(self.prevList) > 0):
            self.prevIndex.pop()
            self.currList = self.prevList.pop()
            self.host.setCurrList(self.currList)
            printDBG( "getPrevList end OK" )
            return RetHost(RetHost.OK, value = self.currList)
        else:
            printDBG( "getPrevList end ERROR" )
            return RetHost(RetHost.ERROR, value = [])

    def getCurrentList(self, refresh = 0):
        printDBG( "getCurrentList begin" )
        #if refresh == 1
        #self.prevIndex[-1] #ostatni element prevIndex
        #self.prevList[-1]  #ostatni element prevList
        #tu pobranie listy dla dla elementu self.prevIndex[-1] z listy self.prevList[-1]  
        printDBG( "getCurrentList end" )
        return RetHost(RetHost.OK, value = self.currList)

    def getLinksForVideo(self, Index = 0, item = None):
        return RetHost(RetHost.NOT_IMPLEMENTED, value = [])
        
    def getResolvedURL(self, url):
        printDBG( "getResolvedURL begin" )
        if url != None and url != '':        
            ret = self.host.getResolvedURL(url)
            if ret != None and ret != '':        
               printDBG( "getResolvedURL ret: "+str(ret))
               list = []
               list.append(ret)
               printDBG( "getResolvedURL end OK" )
               return RetHost(RetHost.OK, value = list)
            else:
               printDBG( "getResolvedURL end" )
               return RetHost(RetHost.NOT_IMPLEMENTED, value = [])                
        else:
            printDBG( "getResolvedURL end" )
            return RetHost(RetHost.NOT_IMPLEMENTED, value = [])

    def getSearchResults(self, pattern, searchType = None):
        printDBG( "getSearchResults begin" )
        printDBG( "getSearchResults pattern: " +pattern)
        self.prevIndex.append(0)
        self.prevList.append(self.currList)
        self.currList = self.host.getSearchResults(pattern, searchType)
        printDBG( "getSearchResults end" )
        return RetHost(RetHost.OK, value = self.currList) 
    ###################################################
    # Additional functions on class IPTVHost
    ###################################################

class Host:
    infoversion = "2020.05.24"
    inforemote  = "0.0.0"
    currList = []
    SEARCH_proc = ''

    def __init__(self):
        printDBG( 'Host __init__ begin' )
        self.cm = pCommon.common()
        self.up = urlparser() 
        self.history = CSearchHistoryHelper('infoversion')
        self.currList = []
        printDBG( 'Host __init__ begin' )
        
    def setCurrList(self, list):
        printDBG( 'Host setCurrList begin' )
        self.currList = list
        printDBG( 'Host setCurrList end' )
        return 
    def getInitList(self):
        printDBG( 'Host getInitList begin' )
        _url = 'https://gitlab.com/mosz_nowy/infoversion/raw/master/hosts/hostinfoversion.py'
        query_data = { 'url': _url, 'use_host': False, 'use_cookie': False, 'use_post': False, 'return_data': True }
        try:
           data = self.cm.getURLRequestData(query_data)
           #printDBG( 'Host init data: '+data )
           r = self.cm.ph.getSearchGroups(data, '''infoversion\s=\s['"]([^"^']+?)['"]''')[0] 
           if r:
              printDBG( 'r: '+r)
              self.inforemote=r
        except:
           printDBG( 'Host init query error' )
        self.currList = self.listsItems(-1, '', 'main-menu')
        printDBG( 'Host getInitList end' )
        return self.currList

    def getListForItem(self, Index = 0, refresh = 0, selItem = None):
        printDBG( 'Host getListForItem begin' )
        valTab = []
        if len(self.currList[Index].urlItems) == 0:
           return valTab
        valTab = self.listsItems(Index, self.currList[Index].urlItems[0], self.currList[Index].urlSeparateRequest)
        self.currList = valTab
        printDBG( 'Host getListForItem end' )
        return self.currList

    def getSearchResults(self, pattern, searchType = None):
        printDBG( "Host getSearchResults begin" )
        printDBG( "Host getSearchResults pattern: " +pattern)
        valTab = []
        valTab = self.listsItems(-1, pattern, 'SEARCH')
        self.currList = valTab
        printDBG( "Host getSearchResults end" )
        return self.currList 

    def getLinksForVideo(self, url):
        printDBG("Urllist.getLinksForVideo url[%s]" % url)
        videoUrls = []
        uri, params   = DMHelper.getDownloaderParamFromUrl(url)
        printDBG(params)
        uri = urlparser.decorateUrl(uri, params)
       
        urlSupport = self.up.checkHostSupport( uri )
        if 1 == urlSupport:
            retTab = self.up.getVideoLinkExt( uri )
            videoUrls.extend(retTab)
            printDBG("Video url[%s]" % videoUrls)
            return videoUrls

    def _cleanHtmlStr(self, str):
        str = str.replace('<', ' <').replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
        return clean_html(str).strip()

    def getPage(self, baseUrl, cookie_domain, cloud_domain, params={}, post_data=None):
        COOKIEFILE = os_path.join(GetCookieDir(), cookie_domain)
#        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; rv:17.0) Gecko/20100101 Firefox/17.0'
        self.USER_AGENT = 'Mozilla/5.0 (X11; Linux i686) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/37.0.2062.120 Chrome/37.0.2062.120 Safari/537.36'
#        self.USER_AGENT = 'Mozilla/5.0 (iPhone; CPU iPhone OS 5_0 like Mac OS X) AppleWebKit/534.46 (KHTML, like Gecko) Version/5.1 Mobile/9A334 Safari/7534.48.3'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'text/html'}
        params['cloudflare_params'] = {'domain':cloud_domain, 'cookie_file':COOKIEFILE, 'User-Agent':self.USER_AGENT}
        return self.cm.getPageCFProtection(baseUrl, params, post_data)

    def get_Page(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}: addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def listsItems(self, Index, url, name = ''):
        printDBG( 'Host listsItems begin' )
        valTab = []

        if name == 'main-menu':
           printDBG( 'Host listsItems begin name='+name )
           valTab.append(CDisplayListItem('Kamery', 'Kamery', CDisplayListItem.TYPE_CATEGORY, ['Kamery'], 'Kamery', 'https://www.mielno.pl/assets/mielno/media/files/0ee5adaf-6ee7-4274-afca-558b813541f6/kamera-10.jpg', None)) 
           valTab.append(CDisplayListItem('TV polskie', 'TV polskie', CDisplayListItem.TYPE_CATEGORY, ['TVpolskie'], 'TV_polskie', 'https://grafik.rp.pl/grafika2/1521141.jpg', None)) 
           valTab.append(CDisplayListItem('TV zagraniczne', 'TV zagraniczne', CDisplayListItem.TYPE_CATEGORY, ['TVzagraniczne'], 'TV_zagraniczne', 'https://www.jazami.pl/img/products/98/4_max.jpg', None)) 
           valTab.append(CDisplayListItem('Darmowa TV', '', CDisplayListItem.TYPE_CATEGORY, ['https://hdontap.com/index.php/video'], 'darmowa', '', None)) 
           valTab.append(CDisplayListItem('Stream - MP3', 'http://musicmp3.ru', CDisplayListItem.TYPE_CATEGORY, ['http://musicmp3.ru/artists.html'], 'musicmp3-cat', 'https://musicmp3.ru/i/logo.png', None)) 
           valTab.append(CDisplayListItem('Repozytorium Kinematografii Polskiej',     'http://filmypolskie999.blogspot.com', CDisplayListItem.TYPE_CATEGORY, ['http://filmypolskie999.blogspot.com'],'filmypolskie999', '', None)) 
           valTab.append(CDisplayListItem('IPLAX', '', CDisplayListItem.TYPE_CATEGORY, ['https://iplax.eu/'], 'iplax', 'https://iplax.eu/themes/youplay/img/logo-light.png', None)) 
           valTab.append(CDisplayListItem('Milanos', 'https://milanos.pl', CDisplayListItem.TYPE_CATEGORY, ['https://milanos.pl'], 'milanos', 'http://www.userlogos.org/files/logos/zolw_podroznik/milanos.png', None)) 

           if config.plugins.iptvplayer.religia.value:
              valTab.append(CDisplayListItem('Religijne', 'Religijne', CDisplayListItem.TYPE_CATEGORY, ['Religijne'], 'Religijne', 'http://wakcji24.pl/wp-content/uploads/2019/01/RELIGIA-e1548150968793.png', None)) 
           Image = 'http://newsblog.pl/wp-content/uploads/2019/09/Najlepszy-VPN-IPTV-w-2019-roku-aby-odblokowac-szybkie-predkosci.jpg'
           valTab.insert(0,CDisplayListItem('Info o E2iPlayer - samsamsam', 'Wersja hostinfoversion: '+self.infoversion, CDisplayListItem.TYPE_CATEGORY, ['http://www.e2iplayer.gitlab.io/update2/log.txt'], 'info', Image, None)) 
           valTab.insert(0,CDisplayListItem('Info o E2iPlayer - fork maxbambi', 'Wersja hostinfoversion: '+self.infoversion, CDisplayListItem.TYPE_CATEGORY, ['https://gitlab.com/maxbambi/e2iplayer/commits/master.atom'], 'info', Image, None)) 
           valTab.insert(0,CDisplayListItem('Info o E2iPlayer - fork mosz_nowy', 'Wersja hostinfoversion: '+self.infoversion, CDisplayListItem.TYPE_CATEGORY, ['https://gitlab.com/mosz_nowy/e2iplayer/commits/master.atom'], 'info', Image, None)) 
           valTab.insert(0,CDisplayListItem('Info o E2iPlayer - fork -=Mario=-', 'Wersja hostinfoversion: '+self.infoversion, CDisplayListItem.TYPE_CATEGORY, ['https://gitlab.com/zadmario/e2iplayer/commits/master.atom'], 'info', Image, None)) 
           #valTab.insert(0,CDisplayListItem('Info o E2iPlayer - projekt zamknięty 19 maja 2019r', 'Wersja hostinfoversion: '+self.infoversion, CDisplayListItem.TYPE_CATEGORY, ['https://gitlab.com/e2i/e2iplayer/commits/master.atom'], 'info', 'http://www.cam-sats.com/images/forumicons/ip.png', None)) 
           if self.infoversion <> self.inforemote and self.inforemote <> "0.0.0":
              valTab.insert(0,CDisplayListItem('---UPDATE---','UPDATE MENU',        CDisplayListItem.TYPE_CATEGORY,           [''], 'UPDATE',  '', None)) 
           if config.plugins.iptvplayer.infoupdate.value:
               valTab.append(CDisplayListItem('ZMIANY W WERSJI',                    'ZMIANY W WERSJI',   CDisplayListItem.TYPE_CATEGORY, ['https://gitlab.com/mosz_nowy/infoversion/commits/master.atom'], 'UPDATE-ZMIANY', '', None)) 
           valTab.insert(0,CDisplayListItem(_('PROSZĘ PRZEKAŻ 1% PODATKU NA KRS 0000049063'),  _('KRS 0000049063\nSTOWARZYSZENIE "OTWÓRZMY PRZED NIMI ŻYCIE"\nUL. KOŚCIUSZKI 43   32-065 KRZESZOWICE\nPRZEKAŻ 1 % SWOJEGO PODATKU\nPODARUJ NASZYM NIEPEŁNOSPRAWNYM SŁOŃCE'),             CDisplayListItem.TYPE_MORE,             [''], '',        '', None)) 
           return valTab

        if 'HISTORY' == name:
           printDBG( 'Host listsItems begin name='+name )
           for histItem in self.history.getHistoryList():
               valTab.append(CDisplayListItem(histItem['pattern'], 'Szukaj ', CDisplayListItem.TYPE_CATEGORY, [histItem['pattern'],histItem['type']], 'SEARCH', '', None))          
           return valTab 

        if 'SEARCH' == name:
           printDBG( 'Host listsItems begin name='+name )
           pattern = url 
           if Index==-1: 
              self.history.addHistoryItem( pattern, 'video')
           if self.SEARCH_proc == '': return []
           valTab = self.listsItems(-1, url, self.SEARCH_proc)
           return valTab 

        if 'Kamery' == name:
           valTab.append(CDisplayListItem('Kamery Toya GO', 'https://go.toya.net.pl/25', CDisplayListItem.TYPE_CATEGORY, ['https://go.toya.net.pl/25'], 'toyago', 'https://go.toya.net.pl/public/images/top_menu/logo-4.png?t=1494325022', None)) 
           valTab.append(CDisplayListItem('Kamery Worldcam.live', 'https://worldcam.live/pl/list', CDisplayListItem.TYPE_CATEGORY, ['https://worldcam.live/pl/kamery'], 'worldcam', 'https://worldcam.live/img/logo-wcam.png', None)) 
           #valTab.append(CDisplayListItem('LTV9 Łotwa', 'https://ltv.lsm.lv', CDisplayListItem.TYPE_CATEGORY, ['https://ltv.lsm.lv/lv/tieshraide/visiemltv.lv/live.1480/'], 'ltv', 'https://ltv.lsm.lv/public/assets/design/logo.png', None)) 
           valTab.append(CDisplayListItem('Kamery Animallive.tv', 'http://animallive.tv', CDisplayListItem.TYPE_CATEGORY, ['http://animallive.tv/pl/kamery-online.html'], 'animallive', 'https://pbs.twimg.com/profile_images/935924816082866177/oYFAlqKG_400x400.jpg', None)) 
           valTab.append(CDisplayListItem('Kamery San Diego ZOO', 'http://zoo.sandiegozoo.org', CDisplayListItem.TYPE_CATEGORY, ['http://zoo.sandiegozoo.org/content/video-more'], 'sandiegozoo', 'https://zoo.sandiegozoo.org/sites/default/files/inline-images/sdzlogo.png', None)) 
           valTab.append(CDisplayListItem('Kamery Szczecin', 'https://www.lantech.com.pl/liveszczecin/', CDisplayListItem.TYPE_CATEGORY, ['https://www.lantech.com.pl/liveszczecin/'], 'szczecin', 'https://naszywki24.pl/galerie/h/herb-szczecina_1745_m.jpg', None)) 
           #valTab.append(CDisplayListItem('Kamery Earth TV', 'http://www.earthtv.com', CDisplayListItem.TYPE_CATEGORY, ['https://www.earthtv.com/en/webcams'], 'earthtv', 'https://i1.wp.com/www.broadbandtvnews.com/wp-content/uploads/2015/10/Earth-TV.jpg?w=600&ssl=1', None)) 
           valTab.append(CDisplayListItem('Kamery SBL (Bieruń-Lędziny)', 'http://sblinternet.pl/kamery', CDisplayListItem.TYPE_CATEGORY, ['http://sblinternet.pl/kamery/bieru-rynek-76'], 'sbl', 'http://sblinternet.pl/img/logotype.png', None)) 
           #valTab.append(CDisplayListItem('Kamery Piła', 'http://www.tvasta.pl', CDisplayListItem.TYPE_CATEGORY, ['http://www.tvasta.pl/home/'], 'asta', 'https://upload.wikimedia.org/wikipedia/commons/thumb/c/cf/POL_Pi%C5%82a_COA_1.svg/330px-POL_Pi%C5%82a_COA_1.svg.png', None)) 
           valTab.append(CDisplayListItem('Kamery WLKP24', 'http://wlkp24.info/kamery/', CDisplayListItem.TYPE_CATEGORY, ['http://wlkp24.info/kamery/'], 'wlkp24', 'http://archiwum.wlkp24.info/static/img/squarelogo400.jpg', None)) 
           valTab.append(CDisplayListItem('Kamery Lookcam', 'https://lookcam.pl', CDisplayListItem.TYPE_CATEGORY, ['https://lookcam.pl/'], 'lookcam', 'https://lookcam.pl/static/7018212/images/logo.png', None)) 
           valTab.append(CDisplayListItem('Kamery Bieszczady', 'Kamery Bieszczady', CDisplayListItem.TYPE_CATEGORY, ['https://www.bieszczady.live/kamery'], 'Bieszczady', 'https://img4.dmty.pl//uploads/201410/1414266711_6cw4do_600.jpg', None)) 
           valTab.append(CDisplayListItem('Kamery Nadmorski24', 'https://www.nadmorski24.pl/kamery', CDisplayListItem.TYPE_CATEGORY, ['https://www.nadmorski24.pl/kamery'], 'nadmorski24', 'https://www.nadmorski24.pl/public/img/nadmorski-logo-1920.png', None)) 
           valTab.append(CDisplayListItem('Popler TV', 'http://www.popler.tv/live', CDisplayListItem.TYPE_CATEGORY, ['http://www.popler.tv/live'], 'poplertv', 'http://www.popler.tv/oferta_new/images/logo.png', None)) 
           valTab.append(CDisplayListItem('Kamery HDONTAP', 'https://hdontap.com/index.php/video', CDisplayListItem.TYPE_CATEGORY, ['https://hdontap.com/index.php/video'], 'hdontap', 'https://hdontap.com/assets/images/logo_hdontap.png', None)) 
           valTab.append(CDisplayListItem('Kamery Trójmiasto', 'https://task.gda.pl/kamery-media/kamery/', CDisplayListItem.TYPE_CATEGORY, ['https://task.gda.pl/kamery-media/kamery/'], 'task', 'https://task.gda.pl/themes/vtwo/images/logo_citask.png', None)) 
           valTab.append(CDisplayListItem('Stoki Szczyrk', 'https://www.szczyrkowski.pl', CDisplayListItem.TYPE_CATEGORY, ['https://www.szczyrkowski.pl/resort/kamery'], 'szczyrk', 'https://www.szczyrkowski.pl/fileadmin/resort_upload/global/our-resorts-logos/sczcyrkowski.png', None)) 
           valTab.append(CDisplayListItem('Stoki Rzeczka', 'https://www.nartyrzeczka.com', CDisplayListItem.TYPE_CATEGORY, ['https://www.nartyrzeczka.com/index.php/kamery'], 'rzeczka', 'https://www.nartyrzeczka.com/templates/moanes/images/logo.png', None)) 
           valTab.append(CDisplayListItem('Stoki Skrzyczne', 'http://www.skrzyczne.cos.pl', CDisplayListItem.TYPE_CATEGORY, ['http://www.skrzyczne.cos.pl/cos-jaworzyna.html'], 'skrzyczne', 'http://www.skrzyczne.cos.pl/static/images/logo3.png', None)) 
           valTab.append(CDisplayListItem('Stoki Korbielow', 'https://korbielow.net', CDisplayListItem.TYPE_CATEGORY, ['https://korbielow.net/kamery-solisko/'], 'korbielów', 'https://korbielow.net/source_2016/img/logo-korbielow-net-w-260-4.png', None)) 

           #http://e-wyciagi.pl/kamery-z-wyciagow.html
           
           valTab.sort(key=lambda poz: poz.name)
           return valTab 

        if 'TV_polskie' == name:
           valTab.append(CDisplayListItem('Wielkopolska TV', 'Wielkopolska TV', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'http://stream4.nadaje.com:15308/live/stream-1/chunklist_w734420720.m3u8', 0)], 'WielkopolskaTV', 'http://wielkopolska.tv/wp-content/themes/tense-theme-master/assets/images/logo.png', None)) 
           valTab.append(CDisplayListItem('Słowianin TV', 'Słowianin TV', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'https://www.youtube.com/channel/UCpUZqLZNnVwlBIeOZYslMDw/live', 1)], 'Słowianin', 'http://www.tvslowianin.pl/images/logo_na_strone.png', None)) 
           #valTab.append(CDisplayListItem('Truso TV', 'Truso TV', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'http://95.160.28.218:1935/elblag/myStream_aac/chunklist_w693626581.m3u8', 0)], 'Truso TV', 'https://static.truso.tv/data/wysiwig/images/logo1.png', None)) 
           valTab.append(CDisplayListItem('Olsztyn TV', 'Olsztyn TV', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'https://www.youtube.com/channel/UC0vwjMGoZpwG_lLBuF6_ALA/live', 1)], 'olsztyn', 'https://static.telewizjaolsztyn.pl/data/wysiwig/images/tvolsztyn_logo.png', None)) 
           valTab.append(CDisplayListItem('Świebodzin TV', 'Świebodzin TV', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'https://www.youtube.com/channel/UCEQZDk3FFLNM67Hx4jQaXVw/live', 1)], 'Świebodzin TV', 'https://static.swiebodzin.tv/data/wysiwig/images/logo_na_strone.png', None)) 
           valTab.append(CDisplayListItem('Rybnik TVT', 'Rybnik TVT', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'http://176.107.129.219/media/tvt/index.m3u8', 1)], 'Rybnik TVT', 'https://yt3.ggpht.com/a/AGF-l7_T04dDfM0UTVjsM4OxvsurRbnaRrPVSsk02Q=s288-c-k-c0xffffffff-no-rj-mo', None)) 
           valTab.append(CDisplayListItem('Dla ciebie TV', 'Dla ciebie TV', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'http://94.246.128.53:1935/tv/_definst_/dlaCiebieTv/playlist.m3u8', 1)], 'Dla ciebie TV', 'http://www.jaw.pl/wp-content/uploads/2014/02/dlaciebie.png', None)) 
           valTab.append(CDisplayListItem('Pogranicze TV', 'Pogranicze TV', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'http://95.160.28.218:1935/pogranicze/myStream/chunklist_w423172449.m3u8', 1)], 'Pogranicze TV', 'https://static.tvpogranicze.pl/data/pages/s2_tv_pogranicze_-_live_24h_.JPG', None)) 
           valTab.append(CDisplayListItem('Twoja TV', 'Twoja TV', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'http://94.246.169.19/ttv_hls/live_720p/index.m3u8', 1)], 'Twoja TV', 'http://twojatv.info/files/15325713f8bb6f8989a085a8f2dadfaa.png', None)) 
           valTab.append(CDisplayListItem('Toya', 'http://tvtoya.pl/live', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'http://tvtoya.pl/live', 1)], 'Toya', 'http://ocdn.eu/images/program-tv/ZmE7MDA_/cd36db78536d606386fcea91f3a5d88c.png', None)) 
           valTab.append(CDisplayListItem('Dami 24', 'http://dami24.pl', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'https://www.youtube.com/channel/UCL1u3cY7_nPjbZmKljCy_Cw/live', 1)], 'dami', 'https://koronaeuropy.pl/wp-content/uploads/2016/09/logo_korona_o_projekcie_dami-720x340.jpg', None)) 
           valTab.append(CDisplayListItem('Sudecka TV', 'http://www.tvsudecka.pl', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'https://www.youtube.com/channel/UC2vPjreaN9Jpan45p66H7hA/live', 1)], 'tvsudecka', 'https://pbs.twimg.com/profile_images/585880676693454849/2eAO2_hC.jpg', None)) 
           valTab.append(CDisplayListItem('Zgorzelec TVT', 'http://www.tvtzgorzelec.pl', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'http://www.tvtzgorzelec.pl/index.php/live', 1)], 'tvt', 'http://www.tvtzgorzelec.pl/images/TVT-mini.png', None)) 
           valTab.append(CDisplayListItem('Stella TVK', 'http://www.tvkstella.pl', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'http://www.tvkstella.pl/live_tv', 1)], 'stella', 'http://www.tvkstella.pl/img/logo.png', None)) 
           valTab.append(CDisplayListItem('Narew TV', 'http://www.narew.info', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'https://www.youtube.com/channel/UCWeOx1YkCKswFOeJVyMG7mw/live', 1)], 'narew', 'https://pbs.twimg.com/profile_images/684831832307810306/M9KmKBse_400x400.jpg', None)) 
           valTab.append(CDisplayListItem('WP1 TV', 'WP1 TV', CDisplayListItem.TYPE_CATEGORY, ['https://av-cdn-2.wpimg.pl/tv24/ngrp:wp1/chunklist_.m3u8'], 'wp1', 'http://telewizja-cyfrowa.com/wp-content/uploads/2016/09/wp1-logo.png', None)) 
           valTab.append(CDisplayListItem('Żary TV', 'http://www.telewizjazary.pl', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'https://www.youtube.com/channel/UC29dc_mBUWW4mz5h754v88w/live', 1)], 'zary', 'https://static.telewizjazary.pl/data/wysiwig/images/logo/TVR_logo.png', None))
           valTab.append(CDisplayListItem('Toruń TV', 'http://www.tvtorun.net/', CDisplayListItem.TYPE_CATEGORY, ['http://www.tvtorun.net/'], 'toruntv', 'http://www.tvtorun.net/public/img/new/logo.png', None))
           valTab.append(CDisplayListItem('Rzeczpospolita TV', 'Rzeczpospolita TV', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'https://www.youtube.com/channel/UCpchzx2u5Ab8YASeJsR1WIw/live', 1)], 'rzeczpospolita', 'https://yt3.ggpht.com/-5MIWhQ6SBRU/AAAAAAAAAAI/AAAAAAAAAAA/ZwKRSGWJu6o/s100-mo-c-c0xffffffff-rj-k-no/photo.jpg', None)) 
           valTab.append(CDisplayListItem('Lubelska TV', 'http://www.lubelska.tv', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'https://www.youtube.com/channel/UCYxbE-WoPqKq26sSeQ6eD1w/live', 1)], 'lubelska', 'https://static.lubelska.tv/data/wysiwig/images/lubelskatv_logo.png', None)) 
           valTab.append(CDisplayListItem('Zabrze TV', 'Zabrze TV', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'https://www.youtube.com/channel/UCyQL0IjtptnQ9PxmAfH3fKQ/live', 1)], 'zabrze', 'http://tvzabrze.pl/assets/images/logo.png', None))
           valTab.append(CDisplayListItem('Słubice TV', 'http://www.slubice.tv', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'https://www.youtube.com/channel/UCENo4wEDe_59Bb8rGGMZl_w/live', 1)], 'slubice', 'https://static.slubice.tv/data/wysiwig/images/logo_tv_HTS200.jpg', None)) 
           valTab.append(CDisplayListItem('Imperium TV', 'https://tvimperium.pl/live/', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'https://tvimperium.pl/live/', 1)], 'imperium', 'http://www.nbitgliwice.pl/media/k2/items/cache/2e2843e2ade511d88df42c8a44a73c77_XL.jpg', None)) 
           valTab.append(CDisplayListItem('Republika TV', 'http://live.telewizjarepublika.pl', CDisplayListItem.TYPE_CATEGORY, ['http://live.telewizjarepublika.pl/live.php'], 'republika', 'http://live.telewizjarepublika.pl/img/logo_bez_tla_na_granatowe.png', None)) 
           valTab.append(CDisplayListItem('Przełom TV', 'http://przelom.pl/tv', CDisplayListItem.TYPE_CATEGORY, ['http://przelom.pl/tv'], 'przelom', 'http://gazetylokalne.pl/wp-content/uploads/2015/12/prze%C5%82om-logo1-e1449698961820.jpg', None)) 
           valTab.append(CDisplayListItem('Echo24', 'http://www.echo24.tv/', CDisplayListItem.TYPE_CATEGORY, ['http://www.echo24.tv/'], 'echo24', 'http://www.echo24.tv/bundles/echo24web/favicons-assets/favicon-152.png', None)) 
           valTab.append(CDisplayListItem('Popler TV', 'http://www.popler.tv/live', CDisplayListItem.TYPE_CATEGORY, ['http://www.popler.tv/live'], 'poplertv', 'http://www.popler.tv/oferta_new/images/logo.png', None)) 
           valTab.append(CDisplayListItem('Galicja TV', 'Galicja TV', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'https://www.youtube.com/channel/UC0wRIobYwfHvugdAGIZ1j0g/live', 1)], 'Galicja', 'https://i.ytimg.com/vi/lPjeomL5RPk/maxresdefault.jpg', None)) 
           #valTab.append(CDisplayListItem('LUBACZÓW TV', 'LUBACZÓW TV', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'https://www.youtube.com/channel/UCB5tN7RbpyWws1zVn4Sy85Q/live', 1)], 'LUBACZÓW', 'http://lubaczow.tv/wp-content/uploads/2018/02/logoTV-white.png', None)) 
           valTab.append(CDisplayListItem('Relax TV', 'Relax TV', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'https://www.youtube.com/channel/UCZvmZep3wknWdBPcKnwsPHA/live', 1)], 'Relax', 'http://tvrelax.pl/templates/srem_tv/themes/red-color/images/logo.png', None)) 
           #valTab.append(CDisplayListItem('LTVM TV MIĘDZYRZEC PODL.', 'LTVM TV MIĘDZYRZEC PODL. ', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'https://www.youtube.com/channel/UCU7uwCYami150L_lydp2OHQ/live', 1)], 'LTVM', 'https://yt3.ggpht.com/a/AGF-l79SsBAwCM8wWJq12NdFFYLrWlJKjAEWaV93Jg=s288-c-k-c0xffffffff-no-rj-mo', None)) 

           #valTab.append(CDisplayListItem('Gorlice TV', 'http://gorlice.tv', CDisplayListItem.TYPE_CATEGORY, ['http://gorlice.tv/%C2%A0'], 'gorlice', 'http://gorlice.tv/static/gfx/service/gorlicetv/logo.png?96eb5', None)) 
           #valTab.append(CDisplayListItem('Karting', '', CDisplayListItem.TYPE_CATEGORY, ['http://polskikarting.pl/live/'], 'karting', 'http://polskikarting.pl/wp-content/uploads/2015/06/logo_polski_karting_cza_272x90.png', None)) 
           #valTab.append(CDisplayListItem('Kłodzka TV', 'http://www.tvklodzka.pl', CDisplayListItem.TYPE_CATEGORY, ['https://www.youtube.com/channel/UCOBLslh96FyyppmaYaJDwyQ/live'], 'klodzka', 'https://d-nm.ppstatic.pl/k/r/46/d7/4c227342bda20_o.jpg', None)) 
           #valTab.append(CDisplayListItem('Lech TV', 'http://lech.tv/live', CDisplayListItem.TYPE_CATEGORY, ['http://lech.tv/program'], 'lechtv', 'http://lech.tv/graphics_new/all/lechtv_logo_top.png', None))
           #valTab.append(CDisplayListItem('Master TV', 'http://www.tv.master.pl', CDisplayListItem.TYPE_CATEGORY, ['http://www.tv.master.pl/tv_online.php'], 'master', 'http://www.tv.master.pl/grafika/TV_Master2.png', None))
           #valTab.append(CDisplayListItem('TRT PL', 'http://www.trt.pl/', CDisplayListItem.TYPE_CATEGORY, ['http://www.trt.pl/'], 'trt', 'http://www.trt.pl/images/logo-new.png', None))
           #valTab.append(CDisplayListItem('WTK - Poznań', 'https://wtkplay.pl', CDisplayListItem.TYPE_CATEGORY, ['https://wtkplay.pl/videos-magazine-229-na_zywo'], 'wtk', 'https://wtkplay.pl/graphic/header/wtkplay_logo.png?theme=normal', None)) 
           #valTab.append(CDisplayListItem('Opoka TV', 'http://opoka.tv', CDisplayListItem.TYPE_CATEGORY, ['http://www.popler.tv/embed/player.php?user=Opokatv&popler=1&kody_code='], 'opoka', 'http://opoka.tv/wp-content/uploads/2016/10/OPTV2016weblgtp1bc.png', None)) 
           #valTab.append(CDisplayListItem('RBL TV', 'http://www.rbl.tv/live.html', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'http://www.rbl.tv/live.html', 1)], 'rbl', 'http://polny.pl/wp-content/uploads/2013/06/rbl_logo.jpg', None)) 
           #valTab.append(CDisplayListItem('Sfera TV', 'http://www.sferatv.pl', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'http://stream.sferatv.pl:1935/sferalive/smil:sferalive.smil/playlist.m3u8', 0)], 'sfera', 'http://www.sferatv.pl/images/logo_www.png', None)) 
           #valTab.append(CDisplayListItem('ZVAMI TV', 'ZVAMI TV', CDisplayListItem.TYPE_CATEGORY, ['https://www.youtube.com/channel/UC6PzB3VTUNhuacrNFXtFEJg/live'], 'zvami', 'https://yt3.ggpht.com/-wJtO5Kwg8f4/AAAAAAAAAAI/AAAAAAAAAAA/ZHfU_jyeiU8/s100-mo-c-c0xffffffff-rj-k-no/photo.jpg', None)) 
           #valTab.append(CDisplayListItem('Stars TV', 'Stars TV', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'http://starstv.live.e55-po.insyscd.net/starstvhd.smil/chunks.m3u8', 1)], 'Stars TV', 'http://twojatv.info/files/15325713f8bb6f8989a085a8f2dadfaa.png', None)) 
           #valTab.append(CDisplayListItem('Truso TV', 'Truso TV', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'http://95.160.28.218:1935/elblag/myStream_aac/chunklist_w693626581.m3u8', 0)], 'Truso TV', 'https://static.truso.tv/data/wysiwig/images/logo1.png', None)) 

           valTab.sort(key=lambda poz: poz.name)

           return valTab

        if 'TV_zagraniczne' == name:
           valTab.append(CDisplayListItem('Glaz', 'http://www.glaz.tv/online-tv/', CDisplayListItem.TYPE_CATEGORY, ['http://www.glaz.tv/online-tv/'], 'glaz', 'http://s.glaz.tv/images/logo.png', None))
           valTab.append(CDisplayListItem('Rosja - EuropaPlus', 'https://europaplus.ru/live', CDisplayListItem.TYPE_CATEGORY, ['https://europaplus.ru/live'], 'europaplus', 'https://europaplus.ru/media/logotype.e7ee9233.png', None))                
           valTab.append(CDisplayListItem('Rosja - NTV', 'http://www.ntv.ru/#air', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'http://www.ntv.ru/#air', 1)], '', 'https://upload.wikimedia.org/wikipedia/commons/thumb/b/b8/NTV_logo.svg/480px-NTV_logo.svg.png', None)) 
           valTab.append(CDisplayListItem('Tivix', 'http://tivix.co', CDisplayListItem.TYPE_CATEGORY, ['http://tivix.co'], 'tivix', 'http://tivix.co/templates/Default/dleimages/logo.png', None)) 
           #valTab.append(CDisplayListItem('Czeskie i Rosyjskie', 'Czeskie i Rosyjskie', CDisplayListItem.TYPE_CATEGORY, [''], 'czeskie', 'http://g7.forsal.pl/p/_wspolne/pliki/980000/980201-shutterstock-100853926.jpg', None)) 
           valTab.append(CDisplayListItem('News12 Long Island', 'http://longisland.news12.com/category/324508/live-streaming', CDisplayListItem.TYPE_CATEGORY, ['http://longisland.news12.com/category/324508/live-streaming'], 'n12', 'http://ftpcontent.worldnow.com/professionalservices/clients/news12/news12li/images/news12li-logo.png', None)) 
           valTab.append(CDisplayListItem('Deutsch', 'Deutsch', CDisplayListItem.TYPE_CATEGORY, [''], 'Deutsch', 'https://previews.123rf.com/images/disfera/disfera1203/disfera120300045/12842476-German-flag-with-deutsch-word-3D-render-Stock-Photo-germany.jpg', None)) 
           valTab.append(CDisplayListItem('Djing Music', 'www.djing.com', CDisplayListItem.TYPE_CATEGORY, ['https://www.djing.com/#!embed.php'], 'djing', 'https://pbs.twimg.com/profile_images/753627557917065216/G_-_PzF9_400x400.jpg', None)) 
           valTab.append(CDisplayListItem('ERT Grecja', 'http://webtv.ert.gr', CDisplayListItem.TYPE_CATEGORY, ['https://webtv.ert.gr'], 'ert', 'https://media.glassdoor.com/sqll/1145411/ert-inc-squarelogo-1496826736870.png', None)) 
           #valTab.append(CDisplayListItem('BG-Gledai TV', 'http://www.bg-gledai.tv', CDisplayListItem.TYPE_CATEGORY, ['http://www.bg-gledai.tv'], 'gledai', 'http://www.bg-gledai.tv/img/newlogo.png', None)) 
           #valTab.append(CDisplayListItem('Stream - OKLIVETV', 'http://oklivetv.com', CDisplayListItem.TYPE_CATEGORY, ['http://oklivetv.com/genre/?orderby=title'], 'oklivetv', 'http://oklivetv.com/wp-content/uploads/2015/01/logo2.png', None)) 
           valTab.append(CDisplayListItem('Poland In', 'Poland In', CDisplayListItem.TYPE_CATEGORY, ['https://www.youtube.com/channel/UCBjUPsHj7bXt24SUWNoZ0zA/live'], 'polandin', 'https://yt3.ggpht.com/a-/AN66SAyfw6iby9Gj5QKt0mT80p1CL7C5miParL5nSw=s288-mo-c-c0xffffffff-rj-k-no', None)) 
           valTab.append(CDisplayListItem('MIAMI TV',     'https://miamitvhd.com', CDisplayListItem.TYPE_CATEGORY, ['https://miamitvhd.com/?channel=miamitv'],'MIAMI', 'https://miamitvhd.com/assets/miamitv-8fcf2efe186508c88b6ebd5441452254a32c410d1d18ea7f82ffbb0d26b35271.png', None)) 
           #valTab.append(CDisplayListItem('Filmbit',     'https://filmbit.ws/telewizja-online', CDisplayListItem.TYPE_CATEGORY, ['https://filmbit.ws/telewizja-online'],'filmbit-clips', 'http://filmbit.ws/public/dist/images/logo_new.png', None))
           valTab.sort(key=lambda poz: poz.name)
           return valTab

        if 'Religijne' == name:
           if config.plugins.iptvplayer.religia.value:
              #valTab.append(CDisplayListItem('Andrychów - Parafia pw. św. Macieja', 'Parafia pw. św. Macieja w Andrychowie', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'http://media.aniolbeskidow.pl/andrychow1.php', 1)], 'andrychow', 'http://www.andrychow.bielsko.opoka.org.pl/images/maciej2.jpg', None)) 
              valTab.append(CDisplayListItem('Andrychów - Parafia św. Stanisława Biskupa i Męczennika', 'Parafia św. Stanisława Biskupa i Męczennika w Andrychowie', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'http://stanislaw-andrychow.pl/kamera_online.html', 1)], 'andrychow', 'http://stanislaw-andrychow.pl/public/images/image.jpg', None)) 
              #valTab.append(CDisplayListItem('Andrychów - Parafia św. Stanisława Biskupa i Męczennika 2', 'Parafia św. Stanisława Biskupa i Męczennika w Andrychowie 2', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'http://stanislaw-andrychow.pl/kamera_online.html?k=2', 1)], 'andrychow', 'http://stanislaw-andrychow.pl/public/images/image.jpg', None)) 
              #valTab.append(CDisplayListItem('Assisi - Basilica of St. Francis', 'Basilica of St. Francis in Assisi', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'http://www.skylinewebcams.com/en/webcam/italia/umbria/perugia/basilica-san-francesco-assisi.html', 1)], '', 'https://ladybudd.files.wordpress.com/2012/08/basilica-of-st-francis-of-assisi.jpg', None)) 
              valTab.append(CDisplayListItem('Cieszyn - Parafia Św. Marii Magdaleny', 'http://parafiamagdaleny.pl', CDisplayListItem.TYPE_CATEGORY, ['http://parafiamagdaleny.pl/parafia/transmisja-wideo'], 'magdalena', 'http://www.polskiekrajobrazy.pl/images/stories/big/50261.jpg', None)) 
              #valTab.append(CDisplayListItem('Cieszyn - Parafia Św.Jerzego 1  (exteplayer3)', 'http://www.swjerzycieszyn.ox.pl', CDisplayListItem.TYPE_CATEGORY, ['rtmp://80.51.121.254:5119/live/jerzy1'], 'swjerzy', 'http://www.cieszyn.pl/files/www.cieszyn.pl%20Renata%20Karpinska%2050[1].jpg', None)) 
              #valTab.append(CDisplayListItem('Cieszyn - Parafia Św.Jerzego 2  (exteplayer3)', 'http://www.swjerzycieszyn.ox.pl', CDisplayListItem.TYPE_CATEGORY, ['rtmp://80.51.121.254:5119/live/jerzy2'], 'swjerzy', 'http://www.cieszyn.pl/files/www.cieszyn.pl%20Renata%20Karpinska%2050[1].jpg', None)) 
              valTab.append(CDisplayListItem('Częstochowa - Jasna Góra', 'http://www.jasnagora.pl', CDisplayListItem.TYPE_CATEGORY, ['http://www.jasnagora.pl/612,372,artykul,Kaplica_Matki_Bozej.aspx'], 'jasna', 'https://jasnagora.pl/wp-content/themes/ordipress/assets/img/top-mb.png', None)) 
              valTab.append(CDisplayListItem('Domradio.de', 'domradio.de', CDisplayListItem.TYPE_CATEGORY, ['https://www.youtube.com/channel/UCgX-WrCB5ALQOILWx-b6gUg/live'], 'domradio', 'https://www.domradio.de/sites/all/themes/domradio/images/logo.png', None)) 
              valTab.append(CDisplayListItem('Edmonton, Kanada - Parafia Różańca Świętego', 'http://msza-online.net', CDisplayListItem.TYPE_CATEGORY, ['https://www.youtube.com/channel/UCqdeE9jH5_xe7j3sLHsQcPQ/live'], 'edmonton', 'https://upload.wikimedia.org/wikipedia/commons/thumb/c/c1/Holy_Rosary_Church_Edmonton_Alberta_Canada_01A.jpg/1200px-Holy_Rosary_Church_Edmonton_Alberta_Canada_01A.jpg', None)) 
              valTab.append(CDisplayListItem('Fatima', 'http://www.fatima.pt', CDisplayListItem.TYPE_CATEGORY, ['http://www.fatima.pt/pt/pages/transmissoes-online'], 'fatima', 'http://usti.reckokat.cz/images/fatima-2017.jpg', None)) 
              valTab.append(CDisplayListItem('Heroldsbach - Gnadenkapelle', 'http://heroldsbach.esgibtmehr.net', CDisplayListItem.TYPE_CATEGORY, ['http://heroldsbach.esgibtmehr.net/doku.php?id=gnadenkapelle'], 'Heroldsbach', 'http://static.panoramio.com/photos/original/130564119.jpg', None)) 
              valTab.append(CDisplayListItem('Heroldsbach - Rosenkranzkapelle', 'http://heroldsbach.esgibtmehr.net', CDisplayListItem.TYPE_CATEGORY, ['http://heroldsbach.esgibtmehr.net/doku.php?id=rosenkranzkapelle'], 'Heroldsbach', 'https://image.jimcdn.com/app/cms/image/transf/none/path/sfb302df63f1bb549/image/id6c593d789b741f4/version/1391965689/image.jpg', None)) 
              valTab.append(CDisplayListItem('Heroldsbach - Krypta', 'http://heroldsbach.esgibtmehr.net', CDisplayListItem.TYPE_CATEGORY, ['http://heroldsbach.esgibtmehr.net/doku.php?id=krypta'], 'Heroldsbach', 'http://www.gebetsstaette-heroldsbach.de/bilder/PICT0068_1.jpg', None)) 
              valTab.append(CDisplayListItem('Heroldsbach - Marienkirche', 'http://heroldsbach.esgibtmehr.net', CDisplayListItem.TYPE_CATEGORY, ['http://heroldsbach.esgibtmehr.net/doku.php?id=marienkirche#marienkirche_-_24h_livestream'], 'Heroldsbach', 'http://www.heroldsbach-pilgerverein.de/bilder/rundgang_5_g.jpg', None)) 
              valTab.append(CDisplayListItem('Kalwaria Zebrzydowska Sanktuarium ', 'Kalwaria Zebrzydowska Sanktuarium ', CDisplayListItem.TYPE_CATEGORY, ['https://www.youtube.com/channel/UCPaeCakVviK0hmDEl-3yGsg'], 'kalwaria', 'http://www.powiat.wadowice.pl/fotki/g2065d.jpg', None)) 
              #valTab.append(CDisplayListItem('Kluczbork - Parafia Najświętszego Serca Pana Jezusa', 'http://nspjkluczbork.pl/uncategorized/kamera/', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'http://nspjkluczbork.pl/uncategorized/kamera/', 1)], 'kluczbork', 'http://nspjkluczbork.pl/wp-content/uploads/2016/11/33_-1200x675.jpg', None)) 
              valTab.append(CDisplayListItem('Kodeń - Sanktuarium Matki Bożej', 'http://www.koden.com.pl/', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'https://worldcam.live/pl/webcam/koden', 1)], 'koden', 'http://img2.garnek.pl/a.garnek.pl/017/153/17153628_800.0.jpg/koden-sanktuarium-maryjne.jpg', None)) 
              #valTab.append(CDisplayListItem('Kraków-Łagiewniki Sanktuarium', 'https://www.faustyna.pl', CDisplayListItem.TYPE_CATEGORY, ['https://www.faustyna.pl/zmbm/transmisja-on-line/'], 'faustyna', 'http://milosierdzie.pl/images/menu-obrazki/obraz.png', None)) 
              valTab.append(CDisplayListItem('Kraków-Łagiewniki TV Miłosierdzie', 'http://www.milosierdzie.pl', CDisplayListItem.TYPE_CATEGORY, ['http://www.milosierdzie.pl/index.php/pl/multimedia-foto/tv-milosierdzie-pl.html'], 'milosierdzie', 'http://www.milosierdzie.pl/images/logo-TVMilosierdzie.png', None)) 
              valTab.append(CDisplayListItem('Lourdes TV', 'https://www.lourdes-france.org', CDisplayListItem.TYPE_CATEGORY, ['https://www.lourdes-france.org/en/tv-lourdes'], 'lourdes', 'http://www.fronda.pl/site_media/media/uploads/maryja_lourdes.jpg', None)) 
              valTab.append(CDisplayListItem('Maków Podhalański - Ołtarz', 'Maków Podhalański Ołtarz', CDisplayListItem.TYPE_CATEGORY, ['http://www.parafiamakowska.pl/kamera-online/kamera-na-oltarz/'], 'makow', 'http://www.parafia.pixpro.pl/img/obraz_top.png', None)) 
              valTab.append(CDisplayListItem('Maków Podhalański - Kaplica', 'Maków Podhalański Kaplica', CDisplayListItem.TYPE_CATEGORY, ['http://www.parafiamakowska.pl/kamera-online/kamera-w-kaplicy/'], 'makow', 'http://www.parafia.pixpro.pl/img/obraz_top.png', None)) 
              valTab.append(CDisplayListItem('Medziugorje   17:00 - 22:00', 'http://www.centrummedjugorje.pl', CDisplayListItem.TYPE_CATEGORY, ['http://www.divinemercy.pl/PL-H47/video.html'], 'medju', 'http://www.medjugorje.org.pl/images/medjugorje-2.jpg', None)) 
              valTab.append(CDisplayListItem('Międzyzdroje - Parafia św. Piotra Apostoła', 'Międzyzdroje  Parafia św. Piotra Apostoła', CDisplayListItem.TYPE_CATEGORY, ['https://www.youtube.com/channel/UC5zVBy9-3R_3HwgrxXyxKBg/live'], 'miedzyzdroje', 'http://www.polskaniezwykla.pl/pictures/original/271578.jpg', None)) 
              valTab.append(CDisplayListItem('Natanek Ogłoszenia bieżące', 'http://www.christusvincit-tv.pl', CDisplayListItem.TYPE_CATEGORY, ['http://christusvincit-tv.pl/articles.php?article_id=236'], 'religia', 'http://img.youtube.com/vi/JRHdinMsXmA/hqdefault.jpg', None)) 
              valTab.append(CDisplayListItem('Natanek Live', 'http://www.christusvincit-tv.pl', CDisplayListItem.TYPE_CATEGORY, ['http://185.48.128.138/hls/kam5.m3u8'], 'religialive', 'http://img.youtube.com/vi/JRHdinMsXmA/hqdefault.jpg', None)) 
              valTab.append(CDisplayListItem('Natanek Czołówka / Z ostatniej chwili', 'http://christusvincit-tv.pl', CDisplayListItem.TYPE_CATEGORY, ['http://christusvincit-tv.pl/viewpage.php?page_id=1'], 'religia2', 'http://img.youtube.com/vi/JRHdinMsXmA/hqdefault.jpg', None)) 
              valTab.append(CDisplayListItem('Natanek Kazania Pasyjne', 'http://www.christusvincit-tv.pl', CDisplayListItem.TYPE_CATEGORY, ['http://christusvincit-tv.pl/articles.php?article_id=147'], 'pasyjne', 'http://img.youtube.com/vi/JRHdinMsXmA/hqdefault.jpg', None)) 
              valTab.append(CDisplayListItem('Piwniczna-Zdrój - Parafia pw Narodzenia Najświętszej Maryi Panny', 'http://www.parafia.piwniczna.com', CDisplayListItem.TYPE_CATEGORY, ['http://www.parafia.piwniczna.com/s48-tv---online.html'], 'piwniczna', 'http://www.parafia.piwniczna.com/images/panel_boczny.jpg', None)) 
              valTab.append(CDisplayListItem('Pogórze - Parafia NMP Królowej Polski', 'http://www.pogorze.katolik.bielsko.pl', CDisplayListItem.TYPE_CATEGORY, ['http://80.51.121.254/pogorze.m3u8'], 'pogorze', 'http://www.pogorze.info.pl/files/kosciol1.jpg', None)) 
              valTab.append(CDisplayListItem('Radzionków - Parafis św. Wojciecha', 'Radzionków  Parafis św. Wojciecha', CDisplayListItem.TYPE_CATEGORY, ['https://www.youtube.com/channel/UCsuXsGQzzH-z9vjB1e4DACw/live'], 'radzionkow', 'https://upload.wikimedia.org/wikipedia/commons/c/cc/Parafia_%C5%9Bw._Wojciecha_w_Radzionkowie.JPG', None)) 
              valTab.append(CDisplayListItem('Sanok - Parafia Chrystusa Króla', 'Sanok Parafia Chrystusa Króla', CDisplayListItem.TYPE_CATEGORY, ['https://www.youtube.com/channel/UC-Jehng9zHoWXR9NfNXZkqA/live'], 'sanok', 'https://upload.wikimedia.org/wikipedia/commons/thumb/e/e3/Christ_the_King_church_in_Sanok_2012.jpg/240px-Christ_the_King_church_in_Sanok_2012.jpg', None)) 
              valTab.append(CDisplayListItem('Skoczów Kaplicówka - Sanktuarium Św. Jana Sarkandra', 'http://kamera.pompejanska.pl/', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'rtmp://80.51.121.254:5119/live/kaplicowka', 0)], 'kaplicowka', 'http://www.polskaniezwykla.pl/pictures/original/278033.jpg', None))               #valTab.append(CDisplayListItem('Parafia Górny Bor', 'http://parafiagornybor.pl/kamera-online', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'http://parafiagornybor.pl/kamera-online', 1)], 'gornybor', 'http://www.parafiagornybor.ox.pl/images/slider/slide_02.jpg', None)) 
              valTab.append(CDisplayListItem('Skoczów Parafia pw. Św. Apostołów Piotra i Pawła', 'http://www.kamera.parafiaskoczow.ox.pl/', CDisplayListItem.TYPE_CATEGORY, ['http://kamera.parafiaskoczow.ox.pl/'], 'skoczow', 'http://www.parafiaskoczow.ox.pl/css/frontend/contactphoto.jpg', None)) 
              valTab.append(CDisplayListItem('Skoczów Parafia pw. Św. Apostołów Piotra i Pawła 2', 'http://www.kamera2.parafiaskoczow.ox.pl/', CDisplayListItem.TYPE_CATEGORY, ['http://www.kamera2.parafiaskoczow.ox.pl/'], 'skoczow', 'http://www.parafiaskoczow.ox.pl/css/frontend/contactphoto.jpg', None)) 
              valTab.append(CDisplayListItem('Skoczów Parafia Matki Bożej Różańcowej', 'Skoczów Parafia Matki Bożej Różańcowej', CDisplayListItem.TYPE_CATEGORY, ['https://www.youtube.com/channel/UCeM7BtSCbkEAkFewPALHRMw/live'], 'skoczow3', 'https://yt3.ggpht.com/-3mqSWrOjsaU/AAAAAAAAAAI/AAAAAAAAAAA/ZRW9L0FHDt4/s288-mo-c-c0xffffffff-rj-k-no/photo.jpg', None)) 
              valTab.append(CDisplayListItem('Tomaszów Lubelski - Kościół pw. Zwiastowania Najświętszej Marii Panny', 'https://tomaszow.lub.pl', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'https://tomaszow.lub.pl/obraz-na-zywo-z-kamer-miejskich/', 1)], 'tomaszow', 'https://tomaszow.lub.pl/wp-content/uploads/2017/02/tpl_ogo_large.png', None)) 
              valTab.append(CDisplayListItem('Tomaszów Lubelski - Kościół pw. Najświętszego Serca Jezusa', 'http://www.nsjtomaszowlub.pl', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'http://www.nsjtomaszowlub.pl/video', 1)], 'nsjtomaszow', 'http://www.nsjtomaszowlub.pl/images/phocagallery/2020/improb/thumbs/phoca_thumb_m_DSC_4612.jpg', None)) 

              valTab.append(CDisplayListItem('Trwam TV', 'http://www.tv-trwam.pl', CDisplayListItem.TYPE_CATEGORY, ['https://trwamtv.live.rd.insyscd.net/cl01/out/u/trwam.m3u8'], 'trwam', 'https://www.redemptor.pl/wp-content/uploads/2015/06/TV-Trwam-logo.jpg', None)) 
              valTab.append(CDisplayListItem('Turza Śląska - Sanktuarium Matki Bożej Fatimskiej', 'Turza Śląska - Sanktuarium Matki Bożej Fatimskiej', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'http://www.sanktuarium.turza.pl/kamera.html', 1)], 'turza', 'http://www.sanktuarium.turza.pl/public/szablon/sanktuarium.turza.pl/img/logo.jpg', None)) 
              valTab.append(CDisplayListItem('Watykan CTV', 'http://www.ctv.va', CDisplayListItem.TYPE_CATEGORY, ['https://www.youtube.com/channel/UC7E-LYc1wivk33iyt5bR5zQ/live'], 'ctv', 'http://www.vaticannews.va/etc/designs/vatican-news/release/library/main/images/appletouch.png', None)) 
              valTab.append(CDisplayListItem('Wilno - Sanktuarium Miłosierdzia Bożego', 'http://msza-online.net/sanktuarium-milosierdzia-bozego-wilno-litwa/', CDisplayListItem.TYPE_CATEGORY, ['http://msza-online.net/sanktuarium-milosierdzia-bozego-wilno-litwa/'], 'wilno', 'http://www.faustyna.eu/IMG_1919aa.jpg', None)) 
              valTab.sort(key=lambda poz: poz.name)
              return valTab

        if 'pasyjne' == name:
            valTab.append(CDisplayListItem('Kazania Pasyjne 2015', 'http://www.christusvincit-tv.pl', CDisplayListItem.TYPE_CATEGORY, ['http://christusvincit-tv.pl/articles.php?article_id=147'], 'religia', 'http://img.youtube.com/vi/JRHdinMsXmA/hqdefault.jpg', None)) 
            valTab.append(CDisplayListItem('Kazania Pasyjne 2014', 'http://www.christusvincit-tv.pl', CDisplayListItem.TYPE_CATEGORY, ['http://christusvincit-tv.pl/articles.php?article_id=121'], 'religia', 'http://img.youtube.com/vi/JRHdinMsXmA/hqdefault.jpg', None)) 
            valTab.append(CDisplayListItem('7 słów Pana Jezusa na krzyżu', 'http://www.christusvincit-tv.pl', CDisplayListItem.TYPE_CATEGORY, ['http://christusvincit-tv.pl/articles.php?article_id=146'], 'religia', 'http://img.youtube.com/vi/JRHdinMsXmA/hqdefault.jpg', None)) 
            valTab.append(CDisplayListItem('Kazania Pasyjne 2013', 'http://www.christusvincit-tv.pl', CDisplayListItem.TYPE_CATEGORY, ['http://christusvincit-tv.pl/articles.php?article_id=42'], 'religia', 'http://img.youtube.com/vi/JRHdinMsXmA/hqdefault.jpg', None)) 
            return valTab

        if 'religialive' == name:
            printDBG( 'Host listsItems begin name='+name )
            if self.cm.isValidUrl(url): 
                tmp = getDirectM3U8Playlist(url)
                for item in tmp:
                    valTab.append(CDisplayListItem(item['name'], item['url'],  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', item['url'], 0)], 0, 'http://img.youtube.com/vi/JRHdinMsXmA/hqdefault.jpg', None))
            return valTab

        if 'miedzyzdroje' == name:
            printDBG( 'Host listsItems begin name='+name )
            videoUrls = self.getLinksForVideo(url)
            if videoUrls:
                for item in videoUrls:
                    Url = item['url']
                    Name = item['name']
                    printDBG( 'Host Url:  '+Url )
                    printDBG( 'Host name:  '+Name )
                    valTab.append(CDisplayListItem('Międzyzdroje  Parafia św. Piotra Apostoła  '+Name, 'Międzyzdroje  Parafia św. Piotra Apostoła  '+Name,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 0)], 0, 'http://www.polskaniezwykla.pl/pictures/original/271578.jpg', None))
            return valTab 

        if 'zvami' == name:
            printDBG( 'Host listsItems begin name='+name )
            videoUrls = self.getLinksForVideo(url)
            if videoUrls:
                for item in videoUrls:
                    Url = item['url']
                    Name = item['name']
                    printDBG( 'Host Url:  '+Url )
                    printDBG( 'Host name:  '+Name )
                    valTab.append(CDisplayListItem('ZVAMI TV  '+Name, 'ZVAMI TV  '+Name,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 0)], 0, 'https://yt3.ggpht.com/-wJtO5Kwg8f4/AAAAAAAAAAI/AAAAAAAAAAA/ZHfU_jyeiU8/s100-mo-c-c0xffffffff-rj-k-no/photo.jpg', None))
            return valTab 

        if 'rzeczpospolita' == name:
            printDBG( 'Host listsItems begin name='+name )
            videoUrls = self.getLinksForVideo(url)
            if videoUrls:
                for item in videoUrls:
                    Url = item['url']
                    Name = item['name']
                    printDBG( 'Host Url:  '+Url )
                    printDBG( 'Host name:  '+Name )
                    valTab.append(CDisplayListItem('Rzeczpospolita TV  '+Name, 'Rzeczpospolita TV  '+Name,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 0)], 0, 'https://yt3.ggpht.com/-5MIWhQ6SBRU/AAAAAAAAAAI/AAAAAAAAAAA/ZwKRSGWJu6o/s100-mo-c-c0xffffffff-rj-k-no/photo.jpg', None))
            return valTab 

        if 'polandin' == name:
            printDBG( 'Host listsItems begin name='+name )
            videoUrls = self.getLinksForVideo(url)
            if videoUrls:
                for item in videoUrls:
                    Url = item['url']
                    Name = item['name']
                    printDBG( 'Host Url:  '+Url )
                    printDBG( 'Host name:  '+Name )
                    valTab.append(CDisplayListItem('Poland In  '+Name, 'Poland In  '+Name,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 0)], 0, 'https://yt3.ggpht.com/a-/AN66SAyfw6iby9Gj5QKt0mT80p1CL7C5miParL5nSw=s288-mo-c-c0xffffffff-rj-k-no', None))
            return valTab 

        if 'skoczow3' == name:
            printDBG( 'Host listsItems begin name='+name )
            videoUrls = self.getLinksForVideo(url)
            if videoUrls:
                for item in videoUrls:
                    Url = item['url']
                    Name = item['name']
                    printDBG( 'Host Url:  '+Url )
                    printDBG( 'Host name:  '+Name )
                    valTab.append(CDisplayListItem('Skoczów  '+Name, 'Skoczów  '+Name,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 0)], 0, '', None))
            return valTab 

        if 'sanok' == name:
            printDBG( 'Host listsItems begin name='+name )
            videoUrls = self.getLinksForVideo(url)
            if videoUrls:
                for item in videoUrls:
                    Url = item['url']
                    Name = item['name']
                    printDBG( 'Host Url:  '+Url )
                    printDBG( 'Host name:  '+Name )
                    valTab.append(CDisplayListItem('Sanok Parafia Chrystusa Króla  '+Name, 'Sanok Parafia Chrystusa Króla  '+Name,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 0)], 0, 'http://chrystuskrol.esanok.pl/wp-content/uploads/2013/05/ggg26.jpg', None))
            else:
                videoUrls = self.getLinksForVideo('https://www.youtube.com/watch?v=M0yYTjEh6dw')
                if videoUrls:
                    for item in videoUrls:
                        Url = item['url']
                        Name = item['name']
                        printDBG( 'Host Url:  '+Url )
                        printDBG( 'Host name:  '+Name )
                        valTab.append(CDisplayListItem('OFFLINE - Sanok Parafia Chrystusa Króla  '+Name, 'Brak transmisji online - Reklama  '+Name,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 0)], 0, 'http://chrystuskrol.esanok.pl/wp-content/uploads/2013/05/ggg26.jpg', None))
            
            return valTab 

        if 'trwam' == name:
            printDBG( 'Host listsItems begin name='+name )
            url = urlparser.decorateUrl(url, {'Referer': "https://tv-trwam.pl/na-zywo", 'iptv_proto':'m3u8', 'iptv_livestream':True, 'User-Agent':"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:69.0) Gecko/20100101 Firefox/69.0"})  
            if self.cm.isValidUrl(url): 
                tmp = getDirectM3U8Playlist(url)
                for item in tmp:
                    #printDBG( 'Host listsItems valtab: '  +str(item) )
                    valTab.append(CDisplayListItem(item['name'], item['url'],  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', item['url'], 0)], 0, 'https://www.redemptor.pl/wp-content/uploads/2015/06/TV-Trwam-logo.jpg', None))
            return valTab
        if 'wp1' == name:
            printDBG( 'Host listsItems begin name='+name )
            if self.cm.isValidUrl(url): 
                tmp = getDirectM3U8Playlist(url, checkContent=True, sortWithMaxBitrate=999999999)
                for item in tmp:
                    printDBG( 'Host listsItems valtab: '  +str(item) )
                    if item['width']!=0:
                        valTab.append(CDisplayListItem(item['name'], item['url'],  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', item['url'], 0)], 0, '', None))
            url='https://av-cdn-1.wpimg.pl/tv24/ngrp:wp1.stream/chunklist_b1628000.m3u8'
            url='https://av-cdn-1.wpimg.pl/tv24/ngrp:wp1.stream/chunklist.m3u8'
            if self.cm.isValidUrl(url): 
                tmp = getDirectM3U8Playlist(url, checkContent=True, sortWithMaxBitrate=999999999)
                for item in tmp:
                    #printDBG( 'Host listsItems valtab: '  +str(item) )
                    if item['width']!=0:
                        valTab.append(CDisplayListItem(item['name'], item['url'],  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', item['url'], 0)], 0, '', None))
            return valTab
        if 'pogorze' == name:
            printDBG( 'Host listsItems begin name='+name )
            if self.cm.isValidUrl(url): 
                tmp = getDirectM3U8Playlist(url)
                for item in tmp:
                    #printDBG( 'Host listsItems valtab: '  +str(item) )
                    valTab.append(CDisplayListItem('Pogórze - Parafia NMP Królowej Polski', item['url'],  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', item['url'], 0)], 0, 'http://www.pogorze.info.pl/files/kosciol1.jpg', None))
            return valTab

        if 'swjerzy' == name:
            printDBG( 'Host listsItems begin name='+name )
            Aurl = 'rtmp://80.51.121.254:5119/live/jerzy_sound'
            Vurl = urlparser.decorateUrl(url, {'Referer': 'http://www.swjerzycieszyn.ox.pl/1,strona-glowna.html?p=kamera'})
            mergeurl = decorateUrl("merge://audio_url|video_url", {'audio_url':Aurl, 'video_url':Vurl, 'prefered_merger':'MP4box'}) 
            printDBG( 'Host mergeurl:  '+mergeurl )
            valTab.append(CDisplayListItem('Cieszyn - Parafia Św.Jerzego ', Vurl+'|'+Aurl,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', mergeurl, 0)], 0, '', None))
            valTab.append(CDisplayListItem('Cieszyn - Parafia Św.Jerzego tylko video', Vurl,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Vurl, 0)], 0, '', None))
            valTab.append(CDisplayListItem('Cieszyn - Parafia Św.Jerzego tylko audio', Aurl,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Aurl, 0)], 0, '', None))
            return valTab 

        if 'gledai' == name:
            printDBG( 'Host listsItems begin name='+name )
            COOKIEFILE = os_path.join(GetCookieDir(), 'gledai.cookie')
            host = "Mozilla/5.0 (Linux; U; Android 4.1.1; en-us; androVM for VirtualBox ('Tablet' version with phone caps) Build/JRO03S) AppleWebKit/534.30 (KHTML, like Gecko) Version/4.0 Safari/534.30"
            header = {'Referer':url, 'User-Agent': host, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}   
            try: data = self.cm.getURLRequestData({ 'url': url, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True })
            except Exception as e:
                printExc()
                msg = _("Last error:\n%s" % str(e))
                GetIPTVNotify().push('%s' % msg, 'error', 20)
                printDBG( 'Host listsItems query error url:'+url )
                return valTab
            printDBG( 'Host listsItems data1: '+data )
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li id="menu-item', '</li>')
            for item in data:
                Url = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0] 
                if Url: Title = Url.split('/')[-1]
                if not 'premium' in Title and not 'gledai' in Title:
                    valTab.append(CDisplayListItem(Title,Title,CDisplayListItem.TYPE_CATEGORY, [Url],'gledai-clips', '', None)) 
            return valTab  
        if 'gledai-clips' == name:
            printDBG( 'Host listsItems begin name='+name )
            COOKIEFILE = os_path.join(GetCookieDir(), 'gledai.cookie')
            host = "Mozilla/5.0 (Linux; U; Android 4.1.1; en-us; androVM for VirtualBox ('Tablet' version with phone caps) Build/JRO03S) AppleWebKit/534.30 (KHTML, like Gecko) Version/4.0 Safari/534.30"
            header = {'Referer':url, 'User-Agent': host, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}   
            try: data = self.cm.getURLRequestData({ 'url': url, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True })
            except Exception as e:
                printExc()
                msg = _("Last error:\n%s" % str(e))
                GetIPTVNotify().push('%s' % msg, 'error', 20)
                printDBG( 'Host listsItems query error url:'+url )
                return valTab
            printDBG( 'Host listsItems data1: '+data )
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'gallerybox', '</h2>')
            for item in data:
                Title = self.cm.ph.getSearchGroups(item, '''title=['"]([^"^']+?)['"]''', 1, True)[0]
                if not Title: Title = self._cleanHtmlStr(item) 
                Image = self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''', 1, True)[0]
                Url = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0] 
                Image = Image.replace('-1','')
                valTab.append(CDisplayListItem(Title, Title,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 1)], 0, Image, None))
            return valTab  

        if 'Bieszczady' == name:
            printDBG( 'Host listsItems begin name='+name )
            COOKIEFILE = os_path.join(GetCookieDir(), 'Bieszczady.cookie')
            self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.getPage(url, 'Bieszczady.cookie', 'www.bieszczady.live', self.defaultParams)
            if not sts: return ''
            printDBG( 'Host listsItems data1: '+str(data) )
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="item col-md', '</div></div></div>')
            for item in data:
                Title = self._cleanHtmlStr(item).replace('(adsbygoogle = window.adsbygoogle || []).push({});','').strip()
                Image = self.cm.ph.getSearchGroups(item, '''data-src=['"]([^"^']+?)['"]''', 1, True)[0]
                Url = self.cm.ph.getSearchGroups(item, '''<a href=['"]([^"^']+?)['"]''', 1, True)[0] 
                if Url.startswith('/'): Url = 'https://www.bieszczady.live' + Url 
                if not 'Szukasz' in Title:
                   valTab.append(CDisplayListItem(Title, Title,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 1)], 0, Image, None))
            return valTab  

        if 'lookcam' == name:
            printDBG( 'Host listsItems begin name='+name )
            image = 'https://scontent.fktw1-1.fna.fbcdn.net/v/t1.0-1/p320x320/28055906_1671609012905840_6753883043113343720_n.jpg?_nc_cat=108&_nc_oc=AQkR3Zcp4JehhL5698WRE5Yqq2jF-D68xK0HwvH4opfJoqJ2bv6SaWJ1C_NYamFbJw4&_nc_ht=scontent.fktw1-1.fna&oh=e62be4275833804755d07910165c2889&oe=5E3D6A1F'
            COOKIEFILE = os_path.join(GetCookieDir(), 'lookcam.cookie')
            self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.getPage(url, 'lookcam.cookie', 'lookcam.com', self.defaultParams)
            if not sts: return ''
            printDBG( 'Host listsItems data1: '+str(data) )
            data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="videos_filter', '</div>', False)[1]
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
            for item in data:
                Url = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0] 
                Title = self.cm.ph.getSearchGroups(item, '''title=['"]([^"^']+?)['"]''', 1, True)[0] 
                Title = self._cleanHtmlStr(item) 
                if Url.startswith('/'): Url = 'https://lookcam.pl' + Url 
                if Url:
                    valTab.append(CDisplayListItem(Title,Title,CDisplayListItem.TYPE_CATEGORY, [Url],'lookcam-clips', image, Url)) 
            self.SEARCH_proc='lookcam-search'
            valTab.insert(0,CDisplayListItem('Historia wyszukiwania', 'Historia wyszukiwania', CDisplayListItem.TYPE_CATEGORY, [''], 'HISTORY', '', None)) 
            valTab.insert(0,CDisplayListItem('Szukaj',  'Szukaj filmów',                       CDisplayListItem.TYPE_SEARCH,   [''], '',        '', None)) 
            return valTab
        if 'lookcam-search' == name:
            printDBG( 'Host name='+name )
            valTab = self.listsItems(-1, 'https://lookcam.pl/kamera/szukaj/?q='+url.replace(' ','+'), 'lookcam-clips')
            return valTab
        if 'lookcam-clips' == name:
            printDBG( 'Host listsItems begin name='+name )
            COOKIEFILE = os_path.join(GetCookieDir(), 'lookcam.cookie')
            self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.getPage(url, 'lookcam.cookie', 'lookcam.com', self.defaultParams)
            if not sts: return ''
            printDBG( 'Host listsItems data1: '+str(data) )
            catUrl = self.currList[Index].possibleTypesOfSearch
            next_page = self.cm.ph.getDataBeetwenMarkers(data, '<a class="page-link" aria-label="Nast', '</a>', False)[1]
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a class="cam-box', '</a>')
            for item in data:
                Url = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0] 
                Title = self.cm.ph.getSearchGroups(item, '''title=['"]([^"^']+?)['"]''', 1, True)[0] 
                Image = self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''', 1, True)[0] 
                if Url.startswith('/'): Url = 'https://lookcam.pl' + Url 
                if not 'class="lazyload"' in item: Title = Title + '  [OFFLINE]'
                if Url:
                    valTab.append(CDisplayListItem(Title, Title,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 1)], 0, Image, None))
            if next_page: 
                match = re.compile('href="(.*?)"').findall(next_page)
                if match:
                    url = re.sub('\?.+', '', url)
                    next_page = url+match[-1].replace('&amp;','&')
                    valTab.append(CDisplayListItem(_("Next page"), next_page, CDisplayListItem.TYPE_CATEGORY, [next_page], name, '', catUrl))
            return valTab 
        if 'webcamlive' == name:
            printDBG( 'Host listsItems begin name='+name )
            videoUrls = self.getLinksForVideo(url)
            if videoUrls:
                for item in videoUrls:
                    Url = item['url']
                    Name = item['name']
                    printDBG( 'Host Url:  '+Url )
                    printDBG( 'Host name:  '+Name )
                    valTab.append(CDisplayListItem('Webcamera  '+Name, 'Webcamera  '+Name,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 0)], 0, '', None))
            return valTab 

        if 'fokus' == name:
            printDBG( 'Host listsItems begin name='+name )
            COOKIEFILE = os_path.join(GetCookieDir(), 'fokus.cookie')
            try: data = self.cm.getURLRequestData({ 'url': url, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True })
            except:
                printDBG( 'Host getResolvedURL query error url: '+url )
                return valTab
            #printDBG( 'Host listsItems data1: '+data )
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a class="slide"', '</a>')
            for item in data:
                Url = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0] 
                if Url.startswith('/'): Url = 'http://www.fokus.tv' + Url 
                Title = self._cleanHtmlStr(item) 
                valTab.append(CDisplayListItem(Title,Title,CDisplayListItem.TYPE_CATEGORY, [Url],'fokus-groups', '', None)) 
            valTab.insert(0,CDisplayListItem("--- Nasze programy ---",     "Nasze programy",     CDisplayListItem.TYPE_CATEGORY,["http://www.fokus.tv/program-api-v1/programs-block"], 'fokus-nasze', '',None))
            valTab.insert(0,CDisplayListItem("--- Fokus TV na żywo ---",     "Fokus TV na żywo",     CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'rtmp://stream.cdn.smcloud.net/fokustv-p/stream1', 0)], 0, 'http://www.lumi.net.pl/img/all/channel_logo_137_large.png',None))
            return valTab 
        if 'fokus-groups' == name:
            printDBG( 'Host listsItems begin name='+name )
            COOKIEFILE = os_path.join(GetCookieDir(), 'fokus.cookie')
            try: data = self.cm.getURLRequestData({ 'url': url, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True })
            except:
                printDBG( 'Host getResolvedURL query error url: '+url )
                return valTab
            #printDBG( 'Host listsItems data1: '+data )
            next = self.cm.ph.getSearchGroups(data, '''<a class="next_ftv" href=['"]([^"^']+?)['"]''', 1, True)[0]
            data = self.cm.ph.getDataBeetwenMarkers(data, 'class="small_video vod">', 'div class="zpr_red', False)[1]
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="box_small_video', '</div>')
            for item in data:
                Title = self.cm.ph.getSearchGroups(item, '''alt=['"]([^"^']+?)['"]''', 1, True)[0]
                Image = self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''', 1, True)[0]
                Url = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0] 
                if Url.startswith('/'): Url = 'http://www.fokus.tv' + Url 
                valTab.append(CDisplayListItem(Title,Title,CDisplayListItem.TYPE_CATEGORY, [Url],'fokus-clips', Image, None)) 
            if next:
                if next.startswith('/'): next = 'http://www.fokus.tv' + next
                #valTab.append(CDisplayListItem('Next', 'Page: '+next, CDisplayListItem.TYPE_CATEGORY, [next], name, '', None))
            return valTab
        if 'fokus-nasze' == name:
            printDBG( 'Host listsItems begin name='+name )
            COOKIEFILE = os_path.join(GetCookieDir(), 'fokus.cookie')
            try: data = self.cm.getURLRequestData({ 'url': url, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True })
            except:
                printDBG( 'Host getResolvedURL query error url: '+url )
                return valTab
            #printDBG( 'Host listsItems data1: '+data )
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="box_small_video', '</div>')
            for item in data:
                Title = self.cm.ph.getSearchGroups(item, '''alt=['"]([^"^']+?)['"]''', 1, True)[0]
                if not Title: Title = self._cleanHtmlStr(item) 
                Image = self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''', 1, True)[0]
                Url = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0] 
                if Url.startswith('/'): Url = 'http://www.fokus.tv' + Url 
                printDBG( 'Host Title: '+Title )
                printDBG( 'Host Url: '+Url )
                if Url == 'http://www.fokus.tv/wszystko-o/piec-lat-po-upadku-hitlera-1': Url = 'http://www.fokus.tv/programy/piec-lat-po-upadku-hitlera-czesc-ii/196-30907'
                if Title:
                    valTab.append(CDisplayListItem(Title,Title,CDisplayListItem.TYPE_CATEGORY, [Url],'fokus-clips', Image, None)) 
            return valTab
        if 'fokus-clips' == name:
            printDBG( 'Host listsItems begin name='+name )
            COOKIEFILE = os_path.join(GetCookieDir(), 'fokus.cookie')
            try: data = self.cm.getURLRequestData({ 'url': url, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True })
            except:
                printDBG( 'Host getResolvedURL query error url: '+url )
                return valTab
            #printDBG( 'Host listsItems data1: '+data )
            Title =''
            data2 = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="box_small_video', '</div>')
            for item in data2:
                Title = self.cm.ph.getSearchGroups(item, '''alt=['"]([^"^']+?)['"]''', 1, True)[0]
                Image = self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''', 1, True)[0]
                Url = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0] 
                if Url.startswith('/'): Url = 'http://www.fokus.tv' + Url 
                valTab.append(CDisplayListItem(Title, Title,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 1)], 0, Image, None))
            data2 = None
            Url = self.cm.ph.getSearchGroups(data, '''<source src=['"]([^"^']+?)['"]''', 1, True)[0]
            if Url and Title=='': valTab.append(CDisplayListItem('Link', '',  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', url, 1)], 0, '', None))
            if not Url: 
                data2 = self.cm.ph.getDataBeetwenMarkers(data, '<div class="hiper-descript">', '</div>', False)[1]
                nazwa = self.cm.ph.getSearchGroups(data2, '''alt=['"]([^"^']+?)['"]''', 1, True)[0]
                image = self.cm.ph.getSearchGroups(data2, '''src=['"]([^"^']+?)['"]''', 1, True)[0]
                desc = self.cm.ph.getSearchGroups(data2, '''"p-descript">([^>]+?)<''', 1, True)[0]
                if nazwa:
                    valTab.append(CDisplayListItem(nazwa, desc,  CDisplayListItem.TYPE_ARTICLE, [CUrlItem('', url, 0)], 0, image, None))
                if data2=='': 
                    data2 = self.cm.ph.getDataBeetwenMarkers(data, '<div class="box_art_news">', '</div>', False)[1]
                    nazwa = self.cm.ph.getSearchGroups(data2, '''alt=['"]([^"^']+?)['"]''', 1, True)[0]
                    image = self.cm.ph.getSearchGroups(data2, '''src=['"]([^"^']+?)['"]''', 1, True)[0]
                    desc = self.cm.ph.getSearchGroups(data2, '''<p>([^>]+?)<''', 1, True)[0]
                    valTab.append(CDisplayListItem(nazwa, desc,  CDisplayListItem.TYPE_ARTICLE, [CUrlItem('', url, 0)], 0, image, None))
            return valTab  

        if 'Deutsch' == name:
            printDBG( 'Host listsItems begin name='+name )
            valTab.append(CDisplayListItem('Deutsche Welle Live', 'Deutsche Welle Live', CDisplayListItem.TYPE_CATEGORY, ['https://www.youtube.com/channel/UCMIgOXM2JEQ2Pv2d0_PVfcg/live'], 'dw', 'https://yt3.ggpht.com/--ZKsQsVYm2c/AAAAAAAAAAI/AAAAAAAAAAA/f0s4KdtP2Cg/s100-c-k-no-mo-rj-c0xffffff/photo.jpg', None))
            #valTab.append(CDisplayListItem('EO TV', 'http://eotv.de/', CDisplayListItem.TYPE_CATEGORY, ['http://eotv.de/'], 'eotv', 'http://eotv.de/wp-content/uploads/2015/12/Cranberry-Logo.png', None))
            #.append(CDisplayListItem('Euronews DE', 'http://de.euronews.com/live', CDisplayListItem.TYPE_CATEGORY, ['http://de.euronews.com/api/watchlive.json'], 'euronewsde', 'http://www.euronews.com/images/fallback.jpg', None))
            return valTab

        if 'czeskie' == name:
            printDBG( 'Host listsItems begin name='+name )
            #valTab.append(CDisplayListItem('CT24', 'http://www.ceskatelevize.cz/ct24/', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'http://www.ceskatelevize.cz/ct24/', 1)], '', 'https://www.wykop.pl/cdn/c3201142/comment_lRH6II7UzMTt7nreZt2qbQZCaaGhBq2H,w400.jpg', None)) 
            #valTab.append(CDisplayListItem('CT Art', 'http://www.ceskatelevize.cz/art/zive/', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'http://www.ceskatelevize.cz/art/zive/', 1)], '', '', None)) 
            #valTab.append(CDisplayListItem('CT Decko', 'http://decko.ceskatelevize.cz/zive/', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'http://decko.ceskatelevize.cz/zive/', 1)], '', '', None)) 
            #valTab.append(CDisplayListItem('CT1', 'http://www.ceskatelevize.cz/ct1/zive/', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'http://www.ceskatelevize.cz/ct1/zive/', 1)], '' '', None)) 
            #valTab.append(CDisplayListItem('CT2', 'http://www.ceskatelevize.cz/ct2/zive/', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'http://www.ceskatelevize.cz/ct2/zive/', 1)], '', '', None)) 
            #valTab.append(CDisplayListItem('CT Sport', 'http://www.ceskatelevize.cz/sport/zive-vysilani/', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'http://www.ceskatelevize.cz/sport/zive-vysilani/', 1)], '', '', None)) 
            #valTab.append(CDisplayListItem('TA3', 'https://www.ta3.com/live.html', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'http://embed.livebox.cz/ta3/live-source.js', 1)], '', 'https://www.ta3.com/ver-4.2/public/img/logo.png?v=1', None)) 


            #valTab.append(CDisplayListItem('Rosja - Россия 1', 'http://live.russia.tv/index/index/channel_id/1', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'http://live.russia.tv/index/index/channel_id/1', 1)], '', 'http://live.russia.tv/i/logo/ch-logo-1.png', None)) 
            #valTab.append(CDisplayListItem('Rosja - Россия 24', 'http://live.russia.tv/index/index/channel_id/3', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'http://live.russia.tv/index/index/channel_id/3', 1)], '', 'http://live.russia.tv/i/logo/ch-logo-3.png', None)) 
            #valTab.append(CDisplayListItem('Rosja - Россия K', 'http://live.russia.tv/index/index/channel_id/4', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'http://live.russia.tv/index/index/channel_id/4', 1)], '', 'http://live.russia.tv/i/logo/ch-logo-4.png', None)) 
            #valTab.append(CDisplayListItem('Rosja - РТР-Планета', 'http://live.russia.tv/index/index/channel_id/82', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'http://live.russia.tv/index/index/channel_id/82', 1)], '', 'http://live.russia.tv/i/logo/ch-logo-82.png', None)) 
            #valTab.append(CDisplayListItem('Rosja - Москва 24', 'http://live.russia.tv/index/index/channel_id/76', CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'http://live.russia.tv/index/index/channel_id/76', 1)], '', 'http://live.russia.tv/i/logo/ch-logo-76.png', None)) 


            return valTab

        if 'mp3' == name:
            printDBG( 'Host listsItems begin name='+name )
            #valTab.append(CDisplayListItem('Artists', 'Artists', CDisplayListItem.TYPE_CATEGORY, ['http://musicmp3.ru/artists.html'], 'musicmp3-cat', '', None))
            #valTab.append(CDisplayListItem('Top Albums', 'Top Albums', CDisplayListItem.TYPE_CATEGORY, ['http://musicmp3.ru/genres.html'], 'musicmp3-cat', '', None))
            #valTab.append(CDisplayListItem('New Albums', 'New Albums', CDisplayListItem.TYPE_CATEGORY, ['http://musicmp3.ru/new_albums.html'], 'musicmp3-cat', '', None))
            return valTab
        if 'musicmp3-cat' == name:
            printDBG( 'Host listsItems begin name='+name )
            self.COOKIEFILE = os_path.join(GetCookieDir(), 'musicmp3.cookie')
            host = 'AppleWebKit/<WebKit Rev>'
            self.header = {'Referer': 'http://musicmp3.ru/', 'User-Agent': host, 'Accept': 'audio/webm,audio/ogg,udio/wav,audio/*;q=0.9,application/ogg;q=0.7,video/*;q=0.6,*/*;q=0.5', 'Connection': 'keep-alive'}   
            try: data = self.cm.getURLRequestData({ 'url': url, 'header': self.header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': self.COOKIEFILE, 'use_post': False, 'return_data': True })
            except:
                printDBG( 'Host getResolvedURL query error url: '+url )
                return ''
            #printDBG( 'Host listsItems data1: '+data )
            self.mainurl = 'http://musicmp3.ru'
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a class="menu_sub__link"', '</a>')
            for item in data:
                Title = self.cm.ph.getSearchGroups(item, '''>([^>]+?)<''', 1, True)[0].strip()
                Url = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0]
                if Url.startswith('/'): Url = self.mainurl + Url
                printDBG( 'Host Title:  '+Title )
                printDBG( 'Host Url:  '+Url )
                valTab.append(CDisplayListItem(decodeHtml(Title), decodeHtml(Title), CDisplayListItem.TYPE_CATEGORY, [Url], 'musicmp3-art', '', None)) 
            self.SEARCH_proc='musicmp3-search'
            valTab.insert(0,CDisplayListItem('Historia wyszukiwania', 'Historia wyszukiwania', CDisplayListItem.TYPE_CATEGORY, [''], 'HISTORY', '', None)) 
            valTab.insert(0,CDisplayListItem('Szukaj',  'Szukaj filmów',                       CDisplayListItem.TYPE_SEARCH,   [''], '',        '', None)) 
            return valTab
        if 'musicmp3-search' == name:
            printDBG( 'Host name='+name )
            valTab = self.listsItems(-1, 'https://musicmp3.ru/search.html?text=*'+url.replace(' ','+')+'*&all=artists', 'musicmp3-szukaj')
            return valTab
        if 'musicmp3-szukaj' == name:
            printDBG( 'Host listsItems begin name='+name )
            self.COOKIEFILE = os_path.join(GetCookieDir(), 'musicmp3.cookie')
            host = 'AppleWebKit/<WebKit Rev>'
            self.header = {'Referer': 'http://musicmp3.ru/', 'User-Agent': host, 'Accept': 'audio/webm,audio/ogg,udio/wav,audio/*;q=0.9,application/ogg;q=0.7,video/*;q=0.6,*/*;q=0.5', 'Connection': 'keep-alive'}   
            try: data = self.cm.getURLRequestData({ 'url': url, 'header': self.header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': self.COOKIEFILE, 'use_post': False, 'return_data': True })
            except:
                printDBG( 'Host getResolvedURL query error url: '+url )
                return ''
            printDBG( 'Host listsItems data1: '+data )
            mainurl = 'http://musicmp3.ru'
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li class="artist_preview">', '</li>')
            for item in data:
                Title = self.cm.ph.getSearchGroups(item, '''>([^>]+?)<''', 1, True)[0].strip()
                Url = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0]
                if Url.startswith('/'): Url = mainurl + Url
                printDBG( 'Host Title:  '+Title )
                printDBG( 'Host Url:  '+Url )
                valTab.append(CDisplayListItem(decodeHtml(Title), decodeHtml(Title), CDisplayListItem.TYPE_CATEGORY, [Url], 'musicmp3-album', '', None)) 
            return valTab
        if 'musicmp3-art' == name:
            printDBG( 'Host listsItems begin name='+name )
            self.COOKIEFILE = os_path.join(GetCookieDir(), 'musicmp3.cookie')
            host = 'AppleWebKit/<WebKit Rev>'
            self.header = {'Referer': 'http://musicmp3.ru/', 'User-Agent': host, 'Accept': 'audio/webm,audio/ogg,udio/wav,audio/*;q=0.9,application/ogg;q=0.7,video/*;q=0.6,*/*;q=0.5', 'Connection': 'keep-alive'}   
            try: data = self.cm.getURLRequestData({ 'url': url, 'header': self.header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': self.COOKIEFILE, 'use_post': False, 'return_data': True })
            except:
                printDBG( 'Host getResolvedURL query error url: '+url )
                return ''
            printDBG( 'Host listsItems data1: '+data )
            mainurl = 'http://musicmp3.ru'
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a class="menu_sub__link"', '</a>')
            for item in data:
                Title = self.cm.ph.getSearchGroups(item, '''>([^>]+?)<''', 1, True)[0].strip()
                Url = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0]
                if Url.startswith('/'): Url = mainurl + Url
                printDBG( 'Host Title:  '+Title )
                printDBG( 'Host Url:  '+Url )
                valTab.append(CDisplayListItem(decodeHtml(Title), decodeHtml(Title), CDisplayListItem.TYPE_CATEGORY, [Url], 'musicmp3-wyk', '', None)) 
            return valTab
        if 'musicmp3-wyk' == name:
            printDBG( 'Host listsItems begin name='+name )
            try: data = self.cm.getURLRequestData({ 'url': url, 'header': self.header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': self.COOKIEFILE, 'use_post': False, 'return_data': True })
            except:
                printDBG( 'Host getResolvedURL query error url: '+url )
                return ''
            printDBG( 'Host listsItems data1: '+data )
            mainurl = 'http://musicmp3.ru'
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a class="small_list__link"', '</a>')
            for item in data:
                Title = self.cm.ph.getSearchGroups(item, '''>([^>]+?)<''', 1, True)[0].strip()
                Url = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0]
                if Url.startswith('/'): Url = mainurl + Url
                printDBG( 'Host Title:  '+Title )
                printDBG( 'Host Url:  '+Url )
                valTab.append(CDisplayListItem(decodeHtml(Title), decodeHtml(Title), CDisplayListItem.TYPE_CATEGORY, [Url], 'musicmp3-album', '', None)) 
            return valTab
        if 'musicmp3-album' == name:
            printDBG( 'Host listsItems begin name='+name )
            try: data = self.cm.getURLRequestData({ 'url': url, 'header': self.header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': self.COOKIEFILE, 'use_post': False, 'return_data': True })
            except:
                printDBG( 'Host getResolvedURL query error url: '+url )
                return ''
            printDBG( 'Host listsItems data1: '+data )
            mainurl = 'http://musicmp3.ru'
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="album_report">', '</ul></div>')
            for item in data:
                Title = self.cm.ph.getSearchGroups(item, '''alt=['"]([^"^']+?)['"]''', 1, True)[0].replace('mp3', '')
                Url = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0]
                self.Image = self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''', 1, True)[0]
                rok = self.cm.ph.getSearchGroups(item, '''date">([^>]+?)<''', 1, True)[0]
                if Url.startswith('/'): Url = mainurl + Url
                printDBG( 'Host Title:  '+Title )
                printDBG( 'Host Url:  '+Url )
                valTab.append(CDisplayListItem(decodeHtml(Title)+'   ('+rok+')', decodeHtml(Title)+'   ('+rok+')', CDisplayListItem.TYPE_CATEGORY, [Url], 'musicmp3-utwory', self.Image, None)) 
            return valTab
        if 'musicmp3-utwory' == name:
            printDBG( 'Host listsItems begin name='+name )
            try: data = self.cm.getURLRequestData({ 'url': url, 'header': self.header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': self.COOKIEFILE, 'use_post': False, 'return_data': True })
            except:
                printDBG( 'Host getResolvedURL query error url: '+url )
                return ''
            printDBG( 'Host listsItems data1: '+data )
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<tr class="song"', '</tr>')
            for item in data:
                Title = self.cm.ph.getSearchGroups(item, '''"name">([^>]+?)<''', 1, True)[0].strip()
                Url = self.cm.ph.getSearchGroups(item, '''rel=['"]([^"^']+?)['"]''', 1, True)[0]
                Image = self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''', 1, True)[0]
                Url = 'https://listen.musicmp3.ru/'+Url
                printDBG( 'Host Title:  '+Title )
                printDBG( 'Host Url:  '+Url )
                Url = urlparser.decorateUrl(Url, self.header)
                valTab.append(CDisplayListItem(decodeHtml(Title), decodeHtml(Title),  CDisplayListItem.TYPE_AUDIO, [CUrlItem('', Url, 0)], 0, '', None))
            return valTab

        if 'djing' == name:
            printDBG( 'Host listsItems begin name='+name )
            COOKIEFILE = os_path.join(GetCookieDir(), 'djing.cookie')
            host = "Mozilla/5.0 (Linux; U; Android 4.1.1; en-us; androVM for VirtualBox ('Tablet' version with phone caps) Build/JRO03S) AppleWebKit/534.30 (KHTML, like Gecko) Version/4.0 Safari/534.30"
            header = {'Referer':url, 'User-Agent': host, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}   
            try: data = self.cm.getURLRequestData({ 'url': url, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True })
            except:
                printDBG( 'Host getResolvedURL query error url: '+url )
                return valTab
            #printDBG( 'Host listsItems data1: '+data )
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li><img', '</li>')
            for item in data:
                Url = self.cm.ph.getSearchGroups(item, '''<source src=['"]([^"^']+?)['"]''', 1, True)[0] 
                Image = self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?\.jpg)['"]''', 1, True)[0]
                Title = self.cm.ph.getSearchGroups(item, '''<h3>([^>]+?)</h3>''', 1, True)[0]
                if Url.startswith('/'): Url = 'https://www.djing.com' + Url
                if Image.startswith('/'): Image = 'https://www.djing.com' + Image
                printDBG( 'Host Url: '+Url )
                printDBG( 'Host Title: '+Title )
                valTab.append(CDisplayListItem(Title, Url,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 1)], 0, Image, None))
            return valTab  

        if 'ert' == name:
            printDBG( 'Host listsItems begin name='+name )
            COOKIEFILE = os_path.join(GetCookieDir(), 'ert.cookie')
            self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
            self.HTTP_HEADER['Referer'] = url
            self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.get_Page(url)
            if not sts: return valTab
            printDBG( 'Host listsItems data: '+data )
            data = self.cm.ph.getDataBeetwenMarkers(data, '>LIVE<', '</ul>', False)[1]
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
            for item in data:
                Url = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?-live/)['"]''', 1, True)[0] 
                Image = self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''', 1, True)[0] 
                if Url: Title = Url.split('/')[-2].upper() 
                if Url.startswith('/'): Url = 'https://webtv.ert.gr' + Url
                if Url and not 'PLAY' in Title:
                    printDBG( 'Host Url: '+Url )
                    valTab.append(CDisplayListItem(Title,Title,CDisplayListItem.TYPE_CATEGORY, [Url],'ert-clips', Image, None)) 
            return valTab  
        if 'ert-clips' == name:
            printDBG( 'Host listsItems begin name='+name )
            COOKIEFILE = os_path.join(GetCookieDir(), 'ert.cookie')
            sts, data = self.get_Page(url)
            if not sts: return valTab
            data2 = self.cm.ph.getAllItemsBeetwenMarkers(data, '<!--', '-->')
            for item in data2:
                data = data.replace(item,'')
            printDBG( 'Host listsItems data: '+data )
            data = self.cm.ph.getDataBeetwenMarkers(data, '<iframe', '</iframe>', False)[1]
            Url = self.cm.ph.getSearchGroups(data, '''src=['"]([^"^']+?)['"]''', 1, True)[0] 
            printDBG( 'Host Url 2: '+Url )
            if Url.startswith('/'): Url = 'https://webtv.ert.gr' + Url
            sts, data = self.get_Page(Url)
            if not sts: return valTab
            printDBG( 'Host listsItems data2: '+data )
            if '.m3u8' in data:
                m3u8_url = self.cm.ph.getSearchGroups(data, r'''['"](http[^"^']+?\.m3u8[^"^']*?)['"]''')[0]
                if self.cm.isValidUrl(m3u8_url):
                    tmp = getDirectM3U8Playlist(m3u8_url, checkContent=True, sortWithMaxBitrate=999999999)
                    for item in tmp:
                        valTab.append(CDisplayListItem('ERT    '+item['name'], 'ERT    '+item['name'],  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', item['url'], 0)], 0, 'http://cdn1.bbend.net/media/com_news/story/2016/10/18/737807/main/sd-2sdf.jpg', None))
            Url = self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"](https://www.youtube.com[^"^']+?)['"]''', 1, True)[0]
            if not Url:
                data = self.cm.ph.getDataBeetwenMarkers(data, '<iframe', '</iframe>', False)[1]
                Url = self.cm.ph.getSearchGroups(data, '''src=['"]([^"^']+?)['"]''', 1, True)[0].replace('&amp;','&')
            videoUrls = self.getLinksForVideo(Url)
            if videoUrls:
                for item in videoUrls:
                    Url = item['url']
                    Name = item['name']
                    printDBG( 'Host name:  '+Name )
                    valTab.append(CDisplayListItem('ERT    '+Name, 'ERT    '+Name,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 0)], 0, 'http://cdn1.bbend.net/media/com_news/story/2016/10/18/737807/main/sd-2sdf.jpg', None))
            return valTab 

        if 'oklivetv' == name:
            printDBG( 'Host getResolvedURL mainurl: '+url )
            COOKIEFILE = os_path.join(GetCookieDir(), 'oklivetv.cookie')
            host = "Mozilla/5.0 (Linux; U; Android 4.1.1; en-us; androVM for VirtualBox ('Tablet' version with phone caps) Build/JRO03S) AppleWebKit/534.30 (KHTML, like Gecko) Version/4.0 Safari/534.30"
            header = {'Referer':url, 'User-Agent': host, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}   
            try: data = self.cm.getURLRequestData({ 'url': url, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True })
            except:
                printDBG( 'Host getResolvedURL query error url: '+url )
                return ''
            #printDBG( 'Host listsItems data1: '+data )
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
            for item in data:
                Url = self.cm.ph.getSearchGroups(item, '''href=['"](http://oklivetv.com/genre/[^"^']+?)['"]''', 1, True)[0] 
                if Url: Title = Url.split('/')[-2].upper() 
                if Url.startswith('/'): Url = 'http://oklivetv.com' + Url
                if Url and Title!='2' and Title!='ADULT-18':
                    printDBG( 'Host Title: '+Title )
                    printDBG( 'Host Url: '+Url )
                    valTab.append(CDisplayListItem(Title,Title,CDisplayListItem.TYPE_CATEGORY, [Url+ '?orderby=title'],'oklivetv_clips', '', None)) 
            return valTab
        if 'oklivetv_clips' == name:
            printDBG( 'Host getResolvedURL mainurl: '+url )
            COOKIEFILE = os_path.join(GetCookieDir(), 'oklivetv.cookie')
            host = "Mozilla/5.0 (Linux; U; Android 4.1.1; en-us; androVM for VirtualBox ('Tablet' version with phone caps) Build/JRO03S) AppleWebKit/534.30 (KHTML, like Gecko) Version/4.0 Safari/534.30"
            header = {'Referer':url, 'User-Agent': host, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}   
            try: data = self.cm.getURLRequestData({ 'url': url, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True })
            except:
                printDBG( 'Host getResolvedURL query error url: '+url )
                return ''
            #printDBG( 'Host listsItems data1: '+data )
            next = self.cm.ph.getSearchGroups(data, '''rel="next" href=['"]([^"^']+?)['"]''', 1, True)[0] 
            data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="nag cf">', '</footer>', False)[1]
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'data-id=', '>Likes')
            for item in data:
                phUrl = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0] 
                phImage = self.cm.ph.getSearchGroups(item, '''img src=['"]([^"^']+?)['"]''', 1, True)[0] 
                phTitle = self.cm.ph.getSearchGroups(item, '''alt=['"]([^"^']+?)['"]''', 1, True)[0] 
                if phUrl.startswith('/'): phUrl = 'http://oklivetv.com' + phUrl
                if phImage.startswith('//'): phImage = 'http:' + phImage
                valTab.append(CDisplayListItem(decodeHtml(phTitle),decodeHtml(phTitle),CDisplayListItem.TYPE_CATEGORY, [phUrl],'oklivetv_source', '', None)) 
                #valTab.append(CDisplayListItem(decodeHtml(phTitle),decodeHtml(phTitle),CDisplayListItem.TYPE_VIDEO, [CUrlItem('', phUrl, 1)], 0, phImage, None)) 
            if next:
                if next.startswith('/'): next = 'http://oklivetv.com' + next
                next = next + '?orderby=title'
                valTab.append(CDisplayListItem('Next', next, CDisplayListItem.TYPE_CATEGORY, [next], name, '', None))                
            return valTab
        if 'oklivetv_source' == name:
            printDBG( 'Host getResolvedURL mainurl: '+url )
            COOKIEFILE = os_path.join(GetCookieDir(), 'oklivetv.cookie')
            host = "Mozilla/5.0 (Linux; U; Android 4.1.1; en-us; androVM for VirtualBox ('Tablet' version with phone caps) Build/JRO03S) AppleWebKit/534.30 (KHTML, like Gecko) Version/4.0 Safari/534.30"
            header = {'Referer':url, 'User-Agent': host, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}   
            try: data = self.cm.getURLRequestData({ 'url': url, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True })
            except:
                printDBG( 'Host getResolvedURL query error url: '+url )
                return ''
            #printDBG( 'Host listsItems data1: '+data )
            data = self.cm.ph.getDataBeetwenMarkers(data, '<iframe', '</iframe>', False)[1]
            Url = self.cm.ph.getSearchGroups(data, '''src=['"]([^"^']+?)['"]''', 1, True)[0] 
            try: data = self.cm.getURLRequestData({ 'url': Url, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': False, 'load_cookie': True, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True })
            except:
                printDBG( 'Host getResolvedURL query error url: '+url )
                return ''
            printDBG( 'Host listsItems data2: '+data )
            if "eval(function(p,a,c,k,e,d)" in data:
                printDBG( 'Host resolveUrl packed' )
                packed = re.compile('>eval\(function\(p,a,c,k,e,d\)(.+?)</script>', re.DOTALL).findall(data)
                if packed:
                    data2 = packed[-1]
                else:
                    return ''
                printDBG( 'Host data4: '+str(data2) )
                try:
                    videoUrl = unpackJSPlayerParams(data2, TEAMCASTPL_decryptPlayerParams, 0, True, True) 
                    printDBG( 'OK4: ')
                except Exception: pass 
                printDBG( 'Host videoUrl: '+str(videoUrl) )
                videoUrl = self.cm.ph.getSearchGroups(videoUrl, '''x-mpegURL","src":['"]([^"^']+?)['"]''', 1, True)[0] 
                if videoUrl: 
                    videoUrl = videoUrl.replace('$','%24')
                    if 'm3u8' in videoUrl: 
                        videoUrl = urlparser.decorateUrl(videoUrl, {'iptv_proto':'m3u8'})
                    valTab.append(CDisplayListItem('Source 0',videoUrl,CDisplayListItem.TYPE_VIDEO, [CUrlItem('', videoUrl, 0)], 0, '', None)) 
            data2 = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li><a title="If this source', '</li>')
            for item in data2:
                phUrl = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0] 
                phTitle = self._cleanHtmlStr(item)  
                if phUrl.startswith('tabs'): phUrl = 'http://oklivetv.com/xplay/' + phUrl
                valTab.append(CDisplayListItem(decodeHtml(phTitle),phUrl,CDisplayListItem.TYPE_VIDEO, [CUrlItem('', phUrl, 1)], 0, '', None)) 
            Url = self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''')[0] 
            if Url:
                if Url.startswith('//'): Url = 'http:' + Url
                if Url!='http://oklivetv.com/xplay/video/3/':
                    valTab.append(CDisplayListItem('Source 00',Url,CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 1)], 0, '', None)) 
            return valTab

        if 'n12' == name:
            printDBG( 'Host listsItems begin name='+name )
            COOKIEFILE = os_path.join(GetCookieDir(), 'n12.cookie')
            host = 'Mozilla/5.0 (Windows NT 6.1; rv:17.0) Gecko/20100101 Firefox/17.0'
            header = {'Referer':'http://longisland.news12.com', 'Origin':'http://longisland.news12.com', 'User-Agent': host, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}   
            try: data = self.cm.getURLRequestData({ 'url': url, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True })
            except:
                printDBG( 'Host getResolvedURL query error url: '+url )
                return ''
            printDBG( 'Host listsItems data '+data )
            Url = self.cm.ph.getSearchGroups(data, '''src=['"](http://adx.news12.com[^"^']+?)['"]''', 1, True)[0]
            if not Url: Url = 'http://adx.news12.com/livevideo/livevideo_iframe.html?region=N12LI'
            query_data = {'url': Url, 'use_host': False, 'use_cookie': False, 'use_post': False, 'return_data': True}
            try: data = self.cm.getURLRequestData(query_data)
            except:
                printDBG( 'Host listsItems ERROR' )
                return valTab
            printDBG( 'Host listsItems data1 '+data )
            url_m3u8 = self.cm.ph.getSearchGroups(data, '''var stream_url = ['"]([^"^']+?)['"]''', 1, True)[0]+'N12LI_WEST'
            if self.cm.isValidUrl(url_m3u8): 
                tmp = getDirectM3U8Playlist(url_m3u8)
                for item in tmp:
                    printDBG( 'Host listsItems valtab: '  +str(item) )
                    valTab.append(CDisplayListItem('News12  '+str(item['name']), 'News12   '+str(item['name']),  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', item['url'], 0)], 0, 'http://ftpcontent.worldnow.com/professionalservices/clients/news12/news12li/images/news12li-logo.png', None))
            return valTab 

        if 'ltv' == name:
            printDBG( 'Host listsItems begin name='+name )
            COOKIEFILE = os_path.join(GetCookieDir(), 'ltv.cookie')
            self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.getPage(url, 'ltv.cookie', 'ltv.lsm.lv', self.defaultParams)
            if not sts: return ''
            printDBG( 'Host listsItems data1: '+str(data) )
            url = self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0]
            if url.startswith('//'): url = 'http:' + url
            sts, data = self.getPage(url, 'ltv.cookie', 'ltv.lsm.lv', self.defaultParams)
            if not sts: return ''
            printDBG( 'Host listsItems data2: '+str(data) )
            Url = self.cm.ph.getSearchGroups(data, '''file:\s['"]([^"^']+?)['"]''', 1, True)[0]
            if Url.startswith('//'): Url = 'http:' + Url
            Url = urlparser.decorateUrl(Url, {'Referer': url, 'iptv_livestream': True}) 
            if self.cm.isValidUrl(Url): 
                tmp = getDirectM3U8Playlist(Url)
                for item in tmp:
                    valTab.append(CDisplayListItem(item['name'], item['url'],  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', item['url'], 0)], 0, 'https://ltv.lsm.lv/public/assets/design/logo.png', None))
            return valTab

        if 'animallive' == name:
            printDBG( 'Host listsItems begin name='+name )
            COOKIEFILE = os_path.join(GetCookieDir(), 'animallive.cookie')
            host = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
            header = {'Referer':url, 'User-Agent': host, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}   
#            try: data = self.cm.getURLRequestData({ 'url': url, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True })
#            except:
#                printDBG( 'Host getResolvedURL query error url: '+url )
#                data = ''
#                #return valTab
            data = ''
            #printDBG( 'Host listsItems data1: '+data )
            data = self.cm.ph.getDataBeetwenMarkers(data, 'categories-module', '</ul>', False)[1]
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
            for item in data:
                Url = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0] 
                Title = self._cleanHtmlStr(item).strip()+'  na żywo'
                if Url.startswith('/'): Url = 'http://animallive.tv' + Url
                valTab.append(CDisplayListItem(Title,Title,CDisplayListItem.TYPE_CATEGORY, [Url],'animallive-clips', '', None)) 

            valTab.append(CDisplayListItem('Żubry online', 'Żubry online',  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'http://www.lasy.gov.pl/pl/informacje/kampanie_i_akcje/zubryonline', 1)], 0, 'http://www.lasy.gov.pl/pl/informacje/kampanie_i_akcje/zubryonline/logo_projekt_zubr-200-2.jpg', None))
            valTab.insert(0,CDisplayListItem('--- Kamery kukaj.sk ---', 'http://www.kukaj.sk/', CDisplayListItem.TYPE_CATEGORY, ['http://www.kukaj.sk/'], 'kukaj', 'http://www.kukaj.sk/images/design/logo.png', None)) 
            valTab.insert(0,CDisplayListItem("--- Ptaki w gniazdach ---","Ptaki w gniazdach",     CDisplayListItem.TYPE_CATEGORY,[''],'ptaki',    '',None))
            valTab.insert(0,CDisplayListItem("--- Kamery Estonia ---","Kamery Estonia",     CDisplayListItem.TYPE_CATEGORY,['https://www.looduskalender.ee/n/en'],'animalestonia',    '',None))

            if data != []:
                valTab.insert(0,CDisplayListItem("--- Atlas zwierząt ---","Atlas zwierząt",     CDisplayListItem.TYPE_CATEGORY,['http://animallive.tv/pl/atlas-zwierzat.html'],'animallive-filmy',    '',None))
                valTab.insert(0,CDisplayListItem("--- Kamery na żywo świat ---","Kamery na żywo świat",     CDisplayListItem.TYPE_CATEGORY,['http://animallive.tv/pl/kamery-na-zywo-swiat.html'],'animallive-filmy',    '',None))
                valTab.insert(0,CDisplayListItem("--- Nasze filmy ---","Nasze filmy",     CDisplayListItem.TYPE_CATEGORY,['http://animallive.tv/pl/filmy.html'],'animallive-filmy',    '',None))
            return valTab  
        if 'animallive-clips' == name:
            printDBG( 'Host listsItems begin name='+name )
            COOKIEFILE = os_path.join(GetCookieDir(), 'animallive.cookie')
            host = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
            header = {'Referer':url, 'User-Agent': host, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}   
            try: data = self.cm.getURLRequestData({ 'url': url, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True })
            except:
                printDBG( 'Host getResolvedURL query error url: '+url )
                return valTab
            printDBG( 'Host listsItems data1: '+data )
            catUrl = self.currList[Index].possibleTypesOfSearch
            data2 = self.cm.ph.getAllItemsBeetwenMarkers(data, '<article class="">', '</article>')
            for item in data2:
                Url = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0] 
                Title = self.cm.ph.getSearchGroups(item, '''itemprop="url"\stitle=['"]([^"^']+?)['"]''', 1, True)[0]
                Image = self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''', 1, True)[0]
                if Url.startswith('/'): Url = 'http://animallive.tv' + Url
                if Image.startswith('/'): Image = 'http://animallive.tv' + Image
                valTab.append(CDisplayListItem(Title, Title,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 1)], 0, Image, None))
            Url = self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0].replace('&amp;','&')
            if catUrl != None and Url != '':
                valTab.append(CDisplayListItem(catUrl, catUrl,  CDisplayListItem.TYPE_CATEGORY, [Url], 'animallive-youtube', '', None))
            Url = self.cm.ph.getSearchGroups(data, '''loadSource\(['"]([^"^']+?)['"]''', 1, True)[0].replace('&amp;','&')
            if catUrl != None and Url != '':
                valTab.append(CDisplayListItem(catUrl, catUrl,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 0)], 0, '', None))

            return valTab 
        if 'animallive-filmy' == name:
            printDBG( 'Host listsItems begin name='+name )
            COOKIEFILE = os_path.join(GetCookieDir(), 'animallive.cookie')
            host = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
            header = {'Referer':url, 'User-Agent': host, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}   
            try: data = self.cm.getURLRequestData({ 'url': url, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True })
            except:
                printDBG( 'Host getResolvedURL query error url: '+url )
                return valTab
            printDBG( 'Host listsItems data1: '+data )
            next = self.cm.ph.getSearchGroups(data, '''class="active">.*?href=['"]([^"^']+?)['"]''', 1, True)[0].replace('&amp;','&')
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<article class', '</article>')
            for item in data:
                Url = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0] 
                Title = self.cm.ph.getSearchGroups(item, '''"url"\stitle=['"]([^"^']+?)['"]''', 1, True)[0].replace('&quot;','"')
                Image = self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''', 1, True)[0]
                if Url.startswith('//'): Url = 'http:' + Url
                if Url.startswith('/'): Url = 'http://animallive.tv' + Url
                if Image.startswith('/'): Image = 'http://animallive.tv' + Image
                printDBG( 'Host listsItems Url: '+Url )
                if not 'atlas' in Url:
                    valTab.append(CDisplayListItem(Title, Title,  CDisplayListItem.TYPE_CATEGORY, [Url], 'animallive-clips', Image, Title))
                if 'atlas' in Url:
                    valTab.append(CDisplayListItem(Title, Title,  CDisplayListItem.TYPE_CATEGORY, [Url], 'animallive-picture', Image, None))
            if next:
                if next.startswith('/'): next = 'http://animallive.tv' + next
                valTab.append(CDisplayListItem('Next', 'Page: '+next, CDisplayListItem.TYPE_CATEGORY, [next], name, '', None))                
            return valTab
        if 'animallive-youtube' == name:
            printDBG( 'Host listsItems begin name='+name )
            videoUrls = self.getLinksForVideo(url)
            if videoUrls:
                for item in videoUrls:
                    printDBG( 'Host item: '+str(item) )
                    valTab.append(CDisplayListItem(item['name'], item['name'],  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', item['url'], 0)], 0, '', None))
            return valTab 
        if 'animallive-picture' == name:
            printDBG( 'Host listsItems begin name='+name )
            COOKIEFILE = os_path.join(GetCookieDir(), 'animallive.cookie')
            host = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
            header = {'Referer':url, 'User-Agent': host, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}   
            try: data = self.cm.getURLRequestData({ 'url': url, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True })
            except:
                printDBG( 'Host getResolvedURL query error url: '+url )
                return valTab
            #printDBG( 'Host listsItems data1: '+data )
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="item-image" itemprop="image">', '</div>')
            for item in data:
                printDBG( 'Host item: '+str(item) )
                Url = self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''', 1, True)[0]
                Title = Url.split('/')[-1]
                if Url.startswith('/'): Url = 'http://animallive.tv' + Url
                valTab.append(CDisplayListItem(Title, Url,CDisplayListItem.TYPE_PICTURE, [CUrlItem('', Url, 0)], 0, '', None)) 
            return valTab 

        if 'karting' == name:
            printDBG( 'Host listsItems begin name='+name )
            COOKIEFILE = os_path.join(GetCookieDir(), 'karting.cookie')
            self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.getPage(url, 'karting.cookie', 'polskikarting.pl', self.defaultParams)
            if not sts: return ''
            printDBG( 'Host listsItems data1: '+str(data) )
            desc = self.cm.ph.getDataBeetwenMarkers(data, '>OGL', '</p>', False)[1]
            Title = 'OGL'+self._cleanHtmlStr(desc) 
            tmp = self.up.getAutoDetectedStreamLink(url) 
            for item in tmp: 
                valTab.append(CDisplayListItem('Karting', Title+'\n'+item['name'],  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', item['url'], 0)], 0, '', None))
            if not tmp: 
                Url = self.cm.ph.getSearchGroups(data, '''<meta property="og:image" content=['"]([^"^']+?)['"]''', 1, True)[0].replace('&amp;','&')
                valTab.append(CDisplayListItem(Title, Title,CDisplayListItem.TYPE_PICTURE, [CUrlItem('', Url, 0)], 0, '', None)) 

            #valTab.insert(0,CDisplayListItem("--- Rotax ---","Rotax",     CDisplayListItem.TYPE_CATEGORY,['https://www.rotax.com.au/streaming.html'],'karting-rotax',    '',None))
        if 'karting-rotax' == name:
            printDBG( 'Host listsItems begin name='+name )
            COOKIEFILE = os_path.join(GetCookieDir(), 'rotax.cookie')
            self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.getPage(url, 'rotax.cookie', 'rotax.com.au', self.defaultParams)
            if not sts: return ''
            printDBG( 'Host listsItems data2: '+str(data) )
            Url = self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0].replace('&amp;','&')
            videoUrls = self.getLinksForVideo(Url)
            if videoUrls:
                for item in videoUrls:
                    Url = item['url']
                    Name = item['name']
                    printDBG( 'Host Url:  '+Url )
                    printDBG( 'Host name:  '+Name )
                    valTab.append(CDisplayListItem('Rotax  '+Name, 'Rotax  '+Name,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 0)], 0, 'https://www.rotax.com.au/auto/theme/rotax/assets/logo.png', None))
            return valTab 

        if 'animalestonia' == name:
            printDBG( 'Host listsItems begin name='+name )
            COOKIEFILE = os_path.join(GetCookieDir(), 'looduskalender.cookie')
            mainUrl = 'https://www.looduskalender.ee'
            host = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
            header = {'Referer':url, 'User-Agent': host, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}   
            self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.getPage(url, 'looduskalender.cookie', 'looduskalender.ee', self.defaultParams)
            if not sts: return ''
            printDBG( 'Host listsItems data1: '+data )
            valTab.append(CDisplayListItem('Estonia live1', 'Estonia live1',  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'https://www.youtube.com/channel/UCN8196-VuPxsUBzCLgwVUfA/live', 1)], 0, '', None))
            valTab.append(CDisplayListItem('Estonia live2', 'Estonia live2',  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'https://www.youtube.com/channel/UCa7D-kXKYvG-fOEDn_HVkkA/live', 1)], 0, '', None))
            data = data.split('<div id="pilt')
            if len(data): del data[0] 
            for item in data:
                Url = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0] 
                Image = self.cm.ph.getSearchGroups(item, '''Image\(['"]([^"^']+?)['"]''', 1, True)[0] 
                Title = self.cm.ph.getSearchGroups(item, '''70px;">([^>]+?)<''', 1, True)[0] 
                if not Title: Title = Image.split('/')[-1].replace('.html','')
                if Image.startswith('/'): Image = mainUrl + Image
                if Url.startswith('/'): Url = mainUrl + Url
                valTab.append(CDisplayListItem(Title, Title,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 1)], 0, Image, None))
            return valTab  

        if 'sandiegozoo' == name:
            printDBG( 'Host listsItems begin name='+name )
            main_Url = 'https://zoo.sandiegozoo.org'
            COOKIEFILE = os_path.join(GetCookieDir(), 'sandiegozoo.cookie')
            self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.getPage('https://zoo.sandiegozoo.org/live-cams', 'sandiegozoo.cookie', 'sandiegozoo.org', self.defaultParams)
            if not sts: return ''
            printDBG( 'Host listsItems data1: '+str(data) )
            data = data.split('<div class="viewitem">')
            if len(data): del data[0]
            for item in data:
                Title = self.cm.ph.getSearchGroups(item, '''alt=['"]([^"^']+?)['"]''', 1, True)[0] 
                Image = self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''', 1, True)[0].replace("&amp;","&")
                if not Image: Image = self.cm.ph.getSearchGroups(item, '''data-original=['"]([^"^']+?)['"]''', 1, True)[0].replace("&amp;","&")
                Url = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0].replace("&amp;","&") 
                if Url.startswith('/'): Url = main_Url + Url
                if Image.startswith('/'): Image = main_Url + Image
                valTab.append(CDisplayListItem(decodeHtml(Title), decodeHtml(Title),  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 1)], 0, Image, None))
            return valTab  

        if 'milanos' == name:
            printDBG( 'Host name='+name )
            valTab.insert(0,CDisplayListItem("Poczekalnia","Poczekalnia",     CDisplayListItem.TYPE_CATEGORY,['https://milanos.pl/poczekalnia'],'milanos_clips',    'http://www.userlogos.org/files/logos/zolw_podroznik/milanos.png',None))
            valTab.insert(0,CDisplayListItem("Kanały","Kanały",     CDisplayListItem.TYPE_CATEGORY,['https://milanos.pl/kanaly.html'],'milanos_kanaly',    'http://www.userlogos.org/files/logos/zolw_podroznik/milanos.png',None))
            valTab.insert(0,CDisplayListItem("Hity","Hity",     CDisplayListItem.TYPE_CATEGORY,['https://milanos.pl/najwyzej-oceniane-miesiac'],'milanos_clips',    'http://www.userlogos.org/files/logos/zolw_podroznik/milanos.png',None))
            self.SEARCH_proc='milanos-search'
            valTab.insert(0,CDisplayListItem('Historia wyszukiwania', 'Historia wyszukiwania', CDisplayListItem.TYPE_CATEGORY, [''], 'HISTORY', '', None)) 
            valTab.insert(0,CDisplayListItem('Szukaj',  'Szukaj filmów',                       CDisplayListItem.TYPE_SEARCH,   [''], '',        '', None)) 
            return valTab
        if 'milanos-search' == name:
            printDBG( 'Host name='+name )
            valTab = self.listsItems(-1, 'https://milanos.pl/index.php?type=1&search='+url.replace(' ','+'), 'milanos_clips')
            return valTab              
        if 'milanos_kanaly' == name:
            printDBG( 'Host name='+name )
            COOKIEFILE = os_path.join(GetCookieDir(), 'milanos.cookie')
            host = "Mozilla/5.0 (Linux; U; Android 4.1.1; en-us; androVM for VirtualBox ('Tablet' version with phone caps) Build/JRO03S) AppleWebKit/534.30 (KHTML, like Gecko) Version/4.0 Safari/534.30"
            header = {'Referer':url, 'Origin':'https://milanos.pl', 'User-Agent': host, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}   
            try: data = self.cm.getURLRequestData({ 'url': url, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True })
            except:
                printDBG( 'Host getResolvedURL query error url: '+url )
                return valTab
            printDBG( 'Host listsItems data1: '+data )
            data = self.cm.ph.getDataBeetwenMarkers(data, '<ul id="ultag"', '</ul>', False)[1]
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
            for item in data:
                Url = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0] 
                Image = self.cm.ph.getSearchGroups(item, '''img src=['"]([^"^']+?)['"]''', 1, True)[0] 
                Title = self.cm.ph.getSearchGroups(item, '''title=['"]([^"^']+?)['"]''', 1, True)[0] 
                if Url.startswith('/'): Url = 'https://milanos.pl' + Url
                if Image.startswith('//'): Image = 'http:' + Image
                Url = Url + '/wszystko'
                valTab.append(CDisplayListItem(decodeHtml(Title),decodeHtml(Title),CDisplayListItem.TYPE_CATEGORY, [Url],'milanos_clips', 'http://www.userlogos.org/files/logos/zolw_podroznik/milanos.png', None)) 
            return valTab
        if 'milanos_clips' == name:
            printDBG( 'Host name='+name )
            COOKIEFILE = os_path.join(GetCookieDir(), 'milanos.cookie')
            host = "Mozilla/5.0 (Linux; U; Android 4.1.1; en-us; androVM for VirtualBox ('Tablet' version with phone caps) Build/JRO03S) AppleWebKit/534.30 (KHTML, like Gecko) Version/4.0 Safari/534.30"
            header = {'Referer':url, 'Origin':'https://milanos.pl', 'User-Agent': host, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}   
            try: data = self.cm.getURLRequestData({ 'url': url, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True })
            except:
                printDBG( 'Host getResolvedURL query error url: '+url )
                return valTab
            printDBG( 'Host listsItems data1: '+data )
            active = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="pagination">', '</ul>', False)[1]
            next = self.cm.ph.getDataBeetwenMarkers(data, '"paginate nextp"', '</a>', False)[1]
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="post"', '<div class="apitemclear"')
            for item in data:
                Url = self.cm.ph.getSearchGroups(item, '''href=['"](https://milanos.pl/vid[^"^']+?)['"#]''', 1, True)[0] 
                Image = self.cm.ph.getSearchGroups(item, '''img src=['"]([^"^']+?)['"]''', 1, True)[0] 
                Title = self.cm.ph.getSearchGroups(item, '''title=['"]([^"^']+?)['"]''', 1, True)[0] 
                Desc = self.cm.ph.getSearchGroups(item, '''<div class="descp">([^"^']+?)</div>''', 1, True)[0].strip()
                pubdate = self.cm.ph.getSearchGroups(item, '''pubdate="">([^>]+?)<''', 1, True)[0].strip()
                printDBG( 'Host Title: '+Title )
                printDBG( 'Host Url: '+Url )
                printDBG( 'Host Image: '+Image )
                if Url.startswith('/'): Url = 'https://milanos.pl' + Url
                if Image.startswith('//'): Image = 'http:' + Image
                Image = urlparser.decorateUrl(Image, {'Referer': url, 'Origin':'https://milanos.pl'})  
                valTab.append(CDisplayListItem(decodeHtml(Title),Desc+'\n'+pubdate,CDisplayListItem.TYPE_CATEGORY, [Url],'milanos_extract', Image, None)) 
            if next:
                next = self.cm.ph.getSearchGroups(next, '''href=['"]([^"^']+?)['"]''', 1, True)[0] 
                if next.startswith('/'): next = 'https://milanos.pl' + next
                if next.startswith('najwyzej'): next = 'https://milanos.pl/' + next
                valTab.append(CDisplayListItem('Next', next, CDisplayListItem.TYPE_CATEGORY, [next], name, '', None))
            if active:
                next = self.cm.ph.getSearchGroups(next, '''<li class="active">.*?href=['"]([^"^']+?)['"]''', 1, True)[0] 
                if next.startswith('/'): next = 'https://milanos.pl' + next
                if next:
                    valTab.append(CDisplayListItem('Next', next, CDisplayListItem.TYPE_CATEGORY, [next], name, '', None))
            return valTab
        if 'milanos_extract' == name:
            printDBG( 'Host name='+name )
            COOKIEFILE = os_path.join(GetCookieDir(), 'milanos.cookie')
            host = "Mozilla/5.0 (Linux; U; Android 4.1.1; en-us; androVM for VirtualBox ('Tablet' version with phone caps) Build/JRO03S) AppleWebKit/534.30 (KHTML, like Gecko) Version/4.0 Safari/534.30"
            header = {'Referer':url, 'Origin':'https://milanos.pl', 'User-Agent': host, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}   
            try: data = self.cm.getURLRequestData({ 'url': url, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': False, 'load_cookie': True, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True })
            except:
                printDBG( 'Host getResolvedURL query error url: '+url )
                return valTab
            printDBG( 'Host listsItems data1: '+data )
            frame = self.cm.ph.getSearchGroups(data, '''(https://milanos.pl/frame/[^"^']+?)['"]''', 1, True)[0].replace('&amp;','&')
            if frame:
                try: data = self.cm.getURLRequestData({ 'url': frame, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': False, 'load_cookie': True, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True })
                except:
                    printDBG( 'Host getResolvedURL query error url: '+frame )
                    return valTab
                printDBG( 'Host data frame: '+data )
            Url = self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0].replace('&amp;','&')
            if Url:
                if Url.startswith('//'): Url = 'http:' + Url
                printDBG( 'Host Url: '+Url )
                videoUrls = self.getLinksForVideo(Url)
                if videoUrls:
                    for item in videoUrls:
                        Url = item['url']
                        Name = item['name']
                        printDBG( 'Host name:  '+Name )
                        valTab.append(CDisplayListItem(Name, Name,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 0)], 0, 'http://www.userlogos.org/files/logos/zolw_podroznik/milanos.png', None))
                    return valTab 
                else:
                    printDBG( 'Host Brak Parsera: '+Url )
                    if Url.startswith('http://www.facebook.com/plugins/likebox.php'):
                        Url = self.cm.ph.getSearchGroups(data, '''data-href=['"]([^"^']+?)['"]''', 1, True)[0]
                    if Url.startswith('//'): Url = 'http:' + Url
                    try: data = self.cm.getURLRequestData({ 'url': Url, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True })
                    except:
                        printDBG( 'Host getResolvedURL query error Url: '+Url )
                        return ''
                    printDBG( 'Host listsItems data2: '+data )
                    videoUrl = self.cm.ph.getSearchGroups(data, '''"url":\s['"]([^"^']+?)['"]''', 1, True)[0] 
                    if not videoUrl: videoUrl = self.cm.ph.getSearchGroups(data, '''src:\s['"]([^"^']+?)['"]''', 1, True)[0] 
                    if not videoUrl: videoUrl = self.cm.ph.getSearchGroups(data, '''no_ratelimit:['"]([^"^']+?)['"]''', 1, True)[0] 
                    if not videoUrl: videoUrl = self.cm.ph.getSearchGroups(data, '''<source id="playersrc" src=['"]([^"^']+?)['"]''', 1, True)[0] 
                    if not videoUrl: videoUrl = self.cm.ph.getSearchGroups(data, '''video&quot;,&quot;src&quot;:&quot;([^"^']+?)&quot;,&quot''', 1, True)[0] 
                    videoUrl = decodeHtml(videoUrl)
                    if videoUrl.startswith('//'): videoUrl = 'http:' + videoUrl
                    printDBG( 'Host videoUrl: '+videoUrl )
                    valTab.append(CDisplayListItem('Link '+Url.split('/')[2],url.split('/')[3],CDisplayListItem.TYPE_VIDEO, [CUrlItem('', videoUrl, 0)], 0, 'http://www.userlogos.org/files/logos/zolw_podroznik/milanos.png', None)) 
            return valTab

        if 'earthtv' == name:
            printDBG( 'Host listsItems begin name='+name )
            COOKIEFILE = os_path.join(GetCookieDir(), 'earthtv.cookie')
            self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.getPage(url, 'earthtv.cookie', 'earthtv.com', self.defaultParams)
            if not sts: return ''
            printDBG( 'Host listsItems data1: '+str(data) )
            data = self.cm.ph.getDataBeetwenMarkers(data, 'region-dropdown', '</div>', False)[1]
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li>', '</li>')
            for item in data:
                Url = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0] 
                Title = self._cleanHtmlStr(item).strip()
                if Url.startswith('//'): Url = 'http:' + Url
                if Url.startswith('/'): Url = 'http://www.earthtv.com' + Url
                printDBG( 'Host Title: '+Title )
                if Title != 'All':
                    valTab.append(CDisplayListItem(decodeHtml(Title),decodeHtml(Title),CDisplayListItem.TYPE_CATEGORY, [Url],'earthtv-country', '', None)) 
            return valTab  
        if 'earthtv-country' == name:
            printDBG( 'Host listsItems begin name='+name )
            COOKIEFILE = os_path.join(GetCookieDir(), 'earthtv.cookie')
            self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.getPage(url, 'earthtv.cookie', 'earthtv.com', self.defaultParams)
            if not sts: return ''
            printDBG( 'Host listsItems data1: '+str(data) )
            data = self.cm.ph.getDataBeetwenMarkers(data, 'country-dropdown', '</div>', False)[1]
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li>', '</li>')
            for item in data:
                Url = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0] 
                Title = self._cleanHtmlStr(item).strip()
                if Url.startswith('//'): Url = 'http:' + Url
                if Url.startswith('/'): Url = 'http://www.earthtv.com' + Url
                if Title != 'All':
                    valTab.append(CDisplayListItem(decodeHtml(Title),decodeHtml(Title),CDisplayListItem.TYPE_CATEGORY, [Url],'earthtv-city-place', '', None)) 
            return valTab  
        if 'earthtv-city' == name:
            printDBG( 'Host listsItems begin name='+name )
            COOKIEFILE = os_path.join(GetCookieDir(), 'earthtv.cookie')
            self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.getPage(url, 'earthtv.cookie', 'earthtv.com', self.defaultParams)
            if not sts: return ''
            printDBG( 'Host listsItems data1: '+str(data) )
            data = self.cm.ph.getDataBeetwenMarkers(data, 'city-dropdown', '</div>', False)[1]
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li>', '</li>')
            for item in data:
                Url = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0] 
                Title = self._cleanHtmlStr(item).strip()
                if Url.startswith('//'): Url = 'http:' + Url
                if Url.startswith('/'): Url = 'http://www.earthtv.com' + Url
                valTab.append(CDisplayListItem(decodeHtml(Title),decodeHtml(Title),CDisplayListItem.TYPE_CATEGORY, [Url],'earthtv-city-place', '', None)) 
            return valTab  
        if 'earthtv-city-place' == name:
            printDBG( 'Host listsItems begin name='+name )
            COOKIEFILE = os_path.join(GetCookieDir(), 'earthtv.cookie')
            self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.getPage(url, 'earthtv.cookie', 'earthtv.com', self.defaultParams)
            if not sts: return ''
            printDBG( 'Host listsItems data1: '+str(data) )
            next = self.cm.ph.getSearchGroups(data, '''next"\shref=['"]([^"^']+?)['"]''', 1, True)[0] 
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="place', '</div>')
            for item in data:
                Url = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0] 
                Title = self.cm.ph.getSearchGroups(item, '''alt=['"]([^"^']+?)['"]''', 1, True)[0].strip()
                if not Title: Title = self._cleanHtmlStr(item).strip()
                Image = self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''', 1, True)[0] 
                if Image.startswith('//'): Image = 'http:' + Image
                if Url.startswith('//'): Url = 'http:' + Url
                if Url.startswith('/'): Url = 'http://www.earthtv.com' + Url
                #sts, data = self.getPage(Url, 'earthtv.cookie', 'earthtv.com', self.defaultParams)
                #if not sts: return ''
                #if 'm3u8' in data:
                valTab.append(CDisplayListItem(decodeHtml(Title), decodeHtml(Title),  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 1)], 0, Image, None))
            if next:
                if next.startswith('/'): next = 'http://www.earthtv.com' + next
                valTab.append(CDisplayListItem('Next', next, CDisplayListItem.TYPE_CATEGORY, [next], name, '', None))
            return valTab  

        if 'glaz' == name:
            printDBG( 'Host getResolvedURL mainurl: '+url )
            COOKIEFILE = os_path.join(GetCookieDir(), 'glaz.cookie')
            host = "Mozilla/5.0 (Linux; U; Android 4.1.1; en-us; androVM for VirtualBox ('Tablet' version with phone caps) Build/JRO03S) AppleWebKit/534.30 (KHTML, like Gecko) Version/4.0 Safari/534.30"
            header = {'Referer':url, 'User-Agent': host, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}   
            try: data = self.cm.getURLRequestData({ 'url': url, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True })
            except:
                printDBG( 'Host getResolvedURL query error url: '+url )
                return ''
            printDBG( 'Host listsItems data1: '+data )
            next = self.cm.ph.getSearchGroups(data, '''rel="next" href=['"]([^"^']+?)['"]''', 1, True)[0] 
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="list-channel">', 'class="clearfix')
            for item in data:
                Url = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0] 
                Title = self.cm.ph.getSearchGroups(item, '''alt=['"]([^"^']+?)['"]''', 1, True)[0].strip()
                if not Title: Title = self._cleanHtmlStr(item).strip()
                Image = self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''', 1, True)[0] 
                if Image.startswith('//'): Image = 'http:' + Image
                if Url.startswith('//'): Url = 'http:' + Url
                if Url.startswith('/'): Url = 'http://www.glaz.tv' + Url
                valTab.append(CDisplayListItem(decodeHtml(Title), decodeHtml(Title),  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 1)], 0, Image, None))
            if next:
                if next.startswith('/'): next = 'http://www.glaz.tv' + next
                valTab.append(CDisplayListItem('Next', next, CDisplayListItem.TYPE_CATEGORY, [next], name, '', None))
            return valTab  

        if 'europaplus' == name:
            printDBG( 'Host getResolvedURL mainurl: '+url )
            COOKIEFILE = os_path.join(GetCookieDir(), 'europaplus.cookie')
            self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
            self.HTTP_HEADER['Referer'] = url
            self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.get_Page(url)
            if not sts: return valTab
            printDBG( 'Host listsItems data1: '+data )
            Url = self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0].replace('&amp;','&')
            if Url.startswith('//'): Url = 'http:' + Url
            sts, data = self.get_Page(Url)
            if not sts: return valTab
            printDBG( 'Host listsItems data2: '+data )
            Url = self.cm.ph.getSearchGroups(data, '''file\': ['"]([^"^']+?)['"]''', 1, True)[0].replace('&amp;','&')
            if not Url: Url = self.cm.ph.getSearchGroups(data, '''setStream\(['"]([^"^']+?)['"]''', 1, True)[0].replace('&amp;','&')
            if not Url: Url = self.cm.ph.getSearchGroups(data, '''"hls":['"]([^"^']+?)['"]''', 1, True)[0].replace('&amp;','&').replace('\/','/')
            if Url.startswith('//'): Url = 'http:' + Url
            if self.cm.isValidUrl(Url): 
                tmp = getDirectM3U8Playlist(Url, checkContent=True, sortWithMaxBitrate=999999999)
                for item in tmp:
                    valTab.append(CDisplayListItem('EuropaPlus   '+str(item['name']), 'EuropaPlus',  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', str(item['url']), 0)], 0, 'https://europaplus.ru/media/logotype.e7ee9233.png', None))
            return valTab  

        if 'sbl' == name:
            printDBG( 'Host getResolvedURL mainurl: '+url )
            COOKIEFILE = os_path.join(GetCookieDir(), 'sbl.cookie')
            host = "Mozilla/5.0 (Linux; U; Android 4.1.1; en-us; androVM for VirtualBox ('Tablet' version with phone caps) Build/JRO03S) AppleWebKit/534.30 (KHTML, like Gecko) Version/4.0 Safari/534.30"
            header = {'Referer':url, 'User-Agent': host, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}   
            try: data = self.cm.getURLRequestData({ 'url': url, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True })
            except:
                printDBG( 'Host getResolvedURL query error url: '+url )
                return ''
            printDBG( 'Host listsItems data1: '+data )
            data = self.cm.ph.getDataBeetwenMarkers(data, 'class="page-side-menu">', '</ul>', False)[1]
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
            for item in data:
                Url = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0] 
                Title = self._cleanHtmlStr(item).strip()
                if Url.startswith('//'): Url = 'http:' + Url
                if Url.startswith('/'): Url = 'http://sblinternet.pl' + Url
                valTab.append(CDisplayListItem(Title, Title,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 1)], 0, 'http://sblinternet.pl/img/logotype.png', None))
            return valTab  

        if 'republika' == name:
            printDBG( 'Host getResolvedURL mainurl: '+url )
            COOKIEFILE = os_path.join(GetCookieDir(), 'republika.cookie')
            self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
            self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.get_Page(url)
            if not sts: return valTab
            printDBG( 'Host listsItems data1: '+data )
            self.defaultParams['header']['Referer'] = url

            url = self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0]
            if url.startswith('//'): url = 'https:' + url
            self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.get_Page(url)
            if not sts: return valTab
            printDBG( 'Host listsItems data2: '+data )
            playlist = self.cm.ph.getDataBeetwenMarkers(data, 'playlist: [', ']', False)[1]
            source = self.cm.ph.getSearchGroups(playlist, '''src:\s['"]([^"^']+?)['"]''')[0] 
            if source.startswith('//'): source = 'http:' + source
            source = urlparser.decorateUrl(source, {'Referer': url})   
            if self.cm.isValidUrl(source): 
                tmp = getDirectM3U8Playlist(source, checkContent=True, sortWithMaxBitrate=999999999)
                for item in tmp:
                    valTab.append(CDisplayListItem('Republika TV   '+ str(item['name']), 'Republika TV   '+ str(item['name']),  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', str(item['url']), 0)], 0, 'http://live.telewizjarepublika.pl/img/logo_bez_tla_na_granatowe.png', None))
            return valTab

        if 'przelom' == name:
            printDBG( 'Host getResolvedURL mainurl: '+url )
            COOKIEFILE = os_path.join(GetCookieDir(), 'przelom.cookie')
            host = "Mozilla/5.0 (Linux; U; Android 4.1.1; en-us; androVM for VirtualBox ('Tablet' version with phone caps) Build/JRO03S) AppleWebKit/534.30 (KHTML, like Gecko) Version/4.0 Safari/534.30"
            header = {'Referer':url, 'User-Agent': host, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}   
            try: data = self.cm.getURLRequestData({ 'url': url, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True })
            except:
                printDBG( 'Host getResolvedURL query error url: '+url )
                return ''
            printDBG( 'Host listsItems data1: '+data )
            next = self.cm.ph.getDataBeetwenMarkers(data, '<div class="pager">', 'number_nav_r', False)[1]
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="entry entry-video">', '</div>')
            for item in data:
                Url = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0] 
                Title = self.cm.ph.getSearchGroups(item, '''title=['"]([^"^']+?)['"]''', 1, True)[0] 
                Image = self.cm.ph.getSearchGroups(item, '''<img src=['"]([^"^']+?)['"]''', 1, True)[0] 
                Time = self.cm.ph.getSearchGroups(item, '''"time">([^>]+?)<''', 1, True)[0] 
                if Url.startswith('//'): Url = 'http:' + Url
                if Url.startswith('/'): Url = 'http://przelom.pl/tv/' + Url
                if Image.startswith('//'): Image = 'http:' + Image
                valTab.append(CDisplayListItem(decodeHtml(Title), decodeHtml(Title)+'\n'+Time,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 1)], 0, Image, None))
            if next:
                link = re.findall('href="(.*?)"', next, re.S|re.I)
                if link:
                    next = link[-1]
                    if next.startswith('?'): next = 'http://przelom.pl/tv/' + next
                    valTab.append(CDisplayListItem('Next', next, CDisplayListItem.TYPE_CATEGORY, [next], name, '', None))
            return valTab

        if 'tivix' == name:
            printDBG( 'Host getResolvedURL mainurl: '+url )
            COOKIEFILE = os_path.join(GetCookieDir(), 'tivix.cookie')
            self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.getPage(url, 'tivix.cookie', 'tivix.co', self.defaultParams)
            if not sts: return ''
            printDBG( 'Host listsItems data1: '+str(data) )
            data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="menuuu', 'div class="rakana">', False)[1]
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a href', '</a>')
            for item in data:
                Url = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0] 
                Title = self._cleanHtmlStr(item).strip()
                if Url.startswith('//'): Url = 'http:' + Url
                if Url.startswith('/'): Url = 'http://tivix.co' + Url
                valTab.append(CDisplayListItem(Title, Url.split('/')[-1], CDisplayListItem.TYPE_CATEGORY, [Url], 'tivix-clips', '', None))
            return valTab
        if 'tivix-clips' == name:
            printDBG( 'Host getResolvedURL mainurl: '+url )
            COOKIEFILE = os_path.join(GetCookieDir(), 'tivix.cookie')
            self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.getPage(url, 'tivix.cookie', 'tivix.co', self.defaultParams)
            if not sts: return ''
            printDBG( 'Host listsItems data1: '+str(data) )
            next = self.cm.ph.getDataBeetwenMarkers(data, '<div class="bot-navigation"', '</div></div></div>', False)[1]
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="all_tv"', '</div>')
            for item in data:
                Url = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0] 
                Title = self.cm.ph.getSearchGroups(item, '''title=['"]([^"^']+?)['"]''', 1, True)[0]
                Image = self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''', 1, True)[0] 
                if Url.startswith('//'): Url = 'http:' + Url
                if Url.startswith('/'): Url = 'http://tivix.co' + Url
                if Image.startswith('//'): Image = 'http:' + Image
                if Image.startswith('/'): Image = 'http://tivix.co' + Image
                valTab.append(CDisplayListItem(decodeHtml(Title), decodeHtml(Title),  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 1)], 0, Image, None))
            if next:
                link = re.findall('href="(.*?)"', next, re.S|re.I)
                if link:
                    next = link[-1]
                    if next.startswith('/'): next = 'http://tivix.co' + next
                    valTab.append(CDisplayListItem('Next', next, CDisplayListItem.TYPE_CATEGORY, [next], name, '', None))
            return valTab

        if 'MIAMI' == name:
           printDBG( 'Host listsItems begin name='+name )
           self.MAIN_URL = 'https://miamitvhd.com' 
           url = self.MAIN_URL
           COOKIEFILE = os_path.join(GetCookieDir(), 'miami.cookie')
           self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
           sts, data = self.getPage(url, 'miami.cookie', 'miamitvhd.com', self.defaultParams)
           if not sts: return valTab
           printDBG( 'Host listsItems data: '+str(data) )
           link1 = self.cm.ph.getDataBeetwenMarkers(data, '<div id="playerElement"', '</div>', False)[1]
           if link1:
              link1 = self.cm.ph.getSearchGroups(link1, '''url=['"]([^"^']+?)['"]''', 1, True)[0] 
              if link1:
                 link1 = urlparser.decorateUrl(link1, {'User-Agent': self.USER_AGENT, 'Referer':self.MAIN_URL})
           link2 = self.cm.ph.getSearchGroups(data, '''<source src=['"]([^"^']+?)['"]''', 1, True)[0]
           if link2:
              link2 = urlparser.decorateUrl(link2, {'User-Agent': self.USER_AGENT, 'Referer':self.MAIN_URL})
           data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li><a class="dropdown-item"', '</li>')
           for item in data:
              phUrl = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0] 
              phTitle = self._cleanHtmlStr(item).strip() 
              if phUrl.startswith('//'): phUrl = 'http:' + phUrl + '/' 
              if phUrl.startswith('/'): phUrl = 'https://miamitvhd.com' + phUrl 
              if phTitle=='Promos': break
              valTab.append(CDisplayListItem(phTitle,phTitle,CDisplayListItem.TYPE_CATEGORY, [phUrl],'MIAMI-clips', '', None)) 
           #valTab.insert(0,CDisplayListItem("--- MIAMI TV Espania ---","MIAMI TV Espania",     CDisplayListItem.TYPE_VIDEO,[CUrlItem('', self.MAIN_URL+'/?channel=miamitv4', 1)],0,    'https://miamitvhd.com/assets/miamitvespana-eec799e28bb876387f572458461375127e49c28c27e71e7363293db36b803039.png',None))
           #valTab.insert(0,CDisplayListItem("--- MIAMI TV Colombia ---","MIAMI TV Colombia",     CDisplayListItem.TYPE_VIDEO,[CUrlItem('', self.MAIN_URL+'/?channel=miamitv3', 1)],0,    'https://miamitvhd.com/assets/miamitvcolombia-16791a2f575f8932b66528b7340353f82d242346d117345eb82a3876612b4789.png',None))
           valTab.insert(0,CDisplayListItem("--- MIAMI TV Latino ---","MIAMI TV Latino",     CDisplayListItem.TYPE_VIDEO,[CUrlItem('', link2, 0)],0,    'https://miamitvhd.com/assets/miamitvlatino-a0a662e0cef788009ad389105e7263d585707570b055e46e3b9b7eb5329775aa.png',None))
           valTab.insert(0,CDisplayListItem("--- MIAMI TV ---","MIAMI TV",     CDisplayListItem.TYPE_VIDEO,[CUrlItem('', link1, 0)], 0,    'https://miamitvhd.com/assets/miamitv-8fcf2efe186508c88b6ebd5441452254a32c410d1d18ea7f82ffbb0d26b35271.png',None))
           return valTab
        if 'MIAMI-clips' == name:
           printDBG( 'Host listsItems begin name='+name )
           self.MAIN_URL = 'https://miamitvhd.com' 
           COOKIEFILE = os_path.join(GetCookieDir(), 'miami.cookie')
           self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
           sts, data = self.getPage(url, 'miami.cookie', 'miamitvhd.com', self.defaultParams)
           if not sts: return valTab
           printDBG( 'Host listsItems data: '+str(data) )
           data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li class="card-video', '</li>')
           for item in data:
              phUrl = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0] 
              phTitle = self._cleanHtmlStr(item)
              phImage = self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''', 1, True)[0] 
              if phUrl.startswith('//'): phUrl = 'http:' + phUrl + '/' 
              if phUrl.startswith('/'): phUrl = 'https://miamitvhd.com' + phUrl 
              valTab.append(CDisplayListItem(phTitle.split('\n')[0],phTitle,CDisplayListItem.TYPE_VIDEO, [CUrlItem('', phUrl, 1)], 0, phImage, None)) 
           return valTab

        if 'fatima' == name:
            printDBG( 'Host listsItems begin name='+name )
            COOKIEFILE = os_path.join(GetCookieDir(), 'fatima.cookie')
            self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
            self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.get_Page(url)
            if not sts: return valTab
            #printDBG( 'Host listsItems data: '+data )
            link = self.cm.ph.getSearchGroups(data, '''src=['"](https?://www.youtube.com[^"^']+?)['"]''')[0] 
            if not link:
                link = self.cm.ph.getSearchGroups(data, '''src=['"](https?://youtu[^"^']+?)['"]''')[0] 
            if link:
                videoUrls = self.getLinksForVideo(link)
                if videoUrls:
                    for item in videoUrls:
                        Url = item['url']
                        Name = item['name']
                        printDBG( 'Host Url:  '+Url )
                        printDBG( 'Host name:  '+Name )
                        valTab.append(CDisplayListItem('Fatima  '+Name, 'Fatima  '+Name,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 0)], 0, 'http://science-info.pl/wp-content/uploads/2011/12/maria.jpg', None))
            link = re.search('(https://rd3.videos.sapo.pt.*?)"', data, re.S|re.I)
            if link:
                stream = 'rtmp://213.13.26.13/live/ playpath=santuario.stream swfUrl=http://js.sapo.pt/Projects/SAPOPlayer/20170410R1/jwplayer.flash.swf pageUrl=http://videos.sapo.pt/v6Lza88afnReWzVdAQap'
                valTab.append(CDisplayListItem('Fatima  '+'sapo', 'Fatima  '+'sapo',  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', stream, 0)], 0, '', None))
            return valTab 

        if 'filmbit' == name:
            printDBG( 'Host listsItems begin name='+name )
            COOKIEFILE = os_path.join(GetCookieDir(), 'filmbit.cookie')
            self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
            self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.get_Page(url)
            if not sts: return valTab
            printDBG( 'Host listsItems data: '+data )
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li class="header__nav-item">', '</li>')
            for item in data:
               phUrl = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0] 
               phTitle = self._cleanHtmlStr(item)
               if phUrl.startswith('//'): phUrl = 'http:' + phUrl + '/' 
               if phUrl.startswith('/'): phUrl = 'http://filmbit.ws' + phUrl 
               if phTitle!='Premium':
                  valTab.append(CDisplayListItem(phTitle,phTitle,CDisplayListItem.TYPE_CATEGORY, [phUrl],'filmbit-clips', '', None)) 
            return valTab
        if 'filmbit-clips' == name:
            printDBG( 'Host listsItems begin name='+name )
            COOKIEFILE = os_path.join(GetCookieDir(), 'filmbit.cookie')
            self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.getPage(url, 'filmbit.cookie', 'filmbit.ws', self.defaultParams)
            if not sts: return valTab
            printDBG( 'Host listsItems data: '+data )
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="card__cover">', '</div>')
            for item in data:
               phUrl = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0] 
               phTitle = self.cm.ph.getSearchGroups(item, '''alt=['"]([^"^']+?)['"]''', 1, True)[0] 
               phImage = self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''', 1, True)[0] 
               if phUrl.startswith('//'): phUrl = 'http:' + phUrl + '/' 
               if phUrl.startswith('/'): phUrl = 'http://filmbit.ws' + phUrl 
               valTab.append(CDisplayListItem(phTitle,phTitle,CDisplayListItem.TYPE_VIDEO, [CUrlItem('', phUrl, 1)], 0, phImage, None)) 
            return valTab

        if 'filmypolskie999' == name:
            printDBG( 'Host listsItems begin name='+name )
            #valTab.insert(0,CDisplayListItem("--- INNE ---","INNE",     CDisplayListItem.TYPE_CATEGORY,['http://filmypolskie999.blogspot.com/p/inne.html'],'filmypolskie999-seriale',    '',None))
            #valTab.insert(0,CDisplayListItem("--- DOKUMENTY ---","DOKUMENTY",     CDisplayListItem.TYPE_CATEGORY,['http://filmypolskie999.blogspot.com/p/dokument.html'],'filmypolskie999-clips',    '',None))
            valTab.insert(0,CDisplayListItem("--- TEATR TV ---","TEATR TV",     CDisplayListItem.TYPE_CATEGORY,['http://filmypolskie999.blogspot.com/p/teatr-tv.html'],'filmypolskie999-clips',    '',None))
            valTab.insert(0,CDisplayListItem("--- SERIALE ---","SERIALE",     CDisplayListItem.TYPE_CATEGORY,['http://filmypolskie999.blogspot.com/p/tv.html'],'filmypolskie999-seriale',    '',None))
            valTab.insert(0,CDisplayListItem("--- FILMY ---","FILMY",     CDisplayListItem.TYPE_CATEGORY,['http://filmypolskie999.blogspot.com/p/film.html'],'filmypolskie999-clips',    '',None))
            return valTab
        if 'filmypolskie999-clips' == name:
            printDBG( 'Host listsItems begin name='+name )
            COOKIEFILE = os_path.join(GetCookieDir(), 'filmypolskie999.cookie')
            self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
            self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.get_Page(url)
            if not sts: return valTab
            printDBG( 'Host listsItems data: '+data )

            data2 = self.cm.ph.getDataBeetwenMarkers(data, "DODAJ FILM", "footer", False)[1]
            if not data2: data2 = self.cm.ph.getDataBeetwenMarkers(data, ">CAŁY SERIAL", "</ol>", False)[1]
            #if not data2: data2 = self.cm.ph.getDataBeetwenMarkers(data, '>Teatr', "footer", False)[1]
            if not data2: data2 = self.cm.ph.getDataBeetwenMarkers(data, '>Spektakle', "<div>", False)[1]
            #if not data2: data2 = self.cm.ph.getDataBeetwenMarkers(data, '<div class="separator"', "</ol>", False)[1]
            if not data2: data2 = self.cm.ph.getDataBeetwenMarkers(data, 'DODAJ', 'footer', False)[1]
            if not data2: data2 = self.cm.ph.getDataBeetwenMarkers(data, 'CZAT', 'footer', False)[1]


            printDBG( 'Host clips data2:%s' % data2 )
            if not data2: data2 = data

            data = self.cm.ph.getAllItemsBeetwenMarkers(data2, '<a', '</a>')
            for item in data:
               phUrl = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0] 
               phTitle = self._cleanHtmlStr(item)
               if phUrl.startswith('//'): phUrl = 'http:' + phUrl
               if phTitle=='': phUrl=''
               if 'Wikipedia' in phTitle: phUrl=''
               if 'Wikipedia' in phTitle: phUrl=''
               if 'Wikipedia' in phTitle: phUrl=''

               if phUrl and not 'tiny.cc' in phTitle:
                  valTab.append(CDisplayListItem(phTitle,phTitle,CDisplayListItem.TYPE_CATEGORY, [phUrl],'filmypolskie999-serwer', '', phTitle)) 
            return valTab
        if 'filmypolskie999-serwer' == name:
            printDBG( 'Host listsItems begin name='+name )
            catUrl = self.currList[Index].possibleTypesOfSearch
            COOKIEFILE = os_path.join(GetCookieDir(), 'filmypolskie999.cookie')
            self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
            self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.get_Page(url)
            if not sts: return valTab
            printDBG( 'Host listsItems data: '+data )
            if 'BRAK-WIDEO-DODAJ' in data:
               msg = _("Last error:\n%s" % 'BRAK WIDEO')
               GetIPTVNotify().push('%s' % msg, 'info', 10)
            pusty = ''
            phImage = self.cm.ph.getSearchGroups(data, '''<link href=['"]([^"^']+?\.jpg)['"]''', 1, True)[0] 
            desc = self.cm.ph.getDataBeetwenMarkers(data, "'metaDescription': '", "'", False)[1].replace('\n','')
            data2 = self.cm.ph.getAllItemsBeetwenMarkers(data, '<iframe', '</iframe>')
            for item in data2:
               phUrl = self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''', 1, True)[0].replace('\n','').replace('&amp;','&') 
               if phUrl.startswith('//'): phUrl = 'http:' + phUrl
               if 'amazon' in phUrl: phUrl = ''
               if phUrl:
                  pusty = ' '
                  valTab.append(CDisplayListItem(catUrl,decodeHtml(desc),CDisplayListItem.TYPE_VIDEO, [CUrlItem('', phUrl, 1)], 0, phImage, None)) 
               else:
                  phUrl = self.cm.ph.getSearchGroups(data, '''file: ['"]([^"^']+?)['"]''', 1, True)[0].replace('\n','').replace('&amp;','&')
                  if phUrl:
                     pusty = ' '
                     if phUrl.startswith('//'): phUrl = 'http:' + phUrl
                     valTab.append(CDisplayListItem(catUrl,decodeHtml(desc),CDisplayListItem.TYPE_VIDEO, [CUrlItem('', phUrl, 1)], 0, phImage, None)) 
            printDBG( 'Host listsItems phUrl:%s' % phUrl )
            if pusty == '':
               valTab.append(CDisplayListItem(catUrl,'',CDisplayListItem.TYPE_CATEGORY, [url],'filmypolskie999-clips', '', None)) 
            return valTab
        if 'filmypolskie999-seriale' == name:
            printDBG( 'Host listsItems begin name='+name )
            COOKIEFILE = os_path.join(GetCookieDir(), 'filmypolskie999.cookie')
            self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
            self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.get_Page(url)
            if not sts: return valTab
            printDBG( 'Host listsItems data: '+data )
            data2 = self.cm.ph.getDataBeetwenMarkers(data, "Seriale zagraniczne", "footer", False)[1]
            if not data2: data2 = self.cm.ph.getDataBeetwenMarkers(data, "SERIALE ZAGRANICZNE", "footer", False)[1]
            if not data2: data2 = self.cm.ph.getDataBeetwenMarkers(data, ">DODAJ SPEKTAKL", "footer", False)[1]
            data = self.cm.ph.getAllItemsBeetwenMarkers(data2, '<a', '</a>')
            for item in data:
               phUrl = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0] 
               phTitle = self._cleanHtmlStr(item)
               if phUrl.startswith('//'): phUrl = 'http:' + phUrl
               if phUrl!='http://tiny.cc/filmoteka':
                  valTab.append(CDisplayListItem(phTitle,phTitle,CDisplayListItem.TYPE_CATEGORY, [phUrl],'filmypolskie999-clips', '', phTitle)) 
            return valTab

        if 'nadmorski24' == name:
            printDBG( 'Host listsItems begin name='+name )
            COOKIEFILE = os_path.join(GetCookieDir(), 'nadmorski24.cookie')
            self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.getPage(url, 'nadmorski24.cookie', 'nadmorski24.pl', self.defaultParams)
            if not sts: return ''
            printDBG( 'Host listsItems data1: '+str(data) )
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
            for item in data:
                Title = self._cleanHtmlStr(item).replace('','').strip()
                Image = self.cm.ph.getSearchGroups(item, '''url\(['"]([^"^']+?)['"]''', 1, True)[0]
                Url = self.cm.ph.getSearchGroups(item, '''href=['"](/kamery/[^"^']+?)['"]''', 1, True)[0] 
                if Url.startswith('/'): Url = 'https://www.nadmorski24.pl' + Url 
                if Image.startswith('/'): Image = 'https://www.nadmorski24.pl' + Image 
                if Url:
                   valTab.append(CDisplayListItem(Title, Title,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 1)], 0, Image, None))
            return valTab  

        if 'echo24' == name:
            printDBG( 'Host listsItems begin name='+name )
            COOKIEFILE = os_path.join(GetCookieDir(), 'echo24.cookie')
            self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
            self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.get_Page(url)
            if not sts: return valTab
            printDBG( 'Host listsItems data: '+data )
            self.SEARCH_proc='echo24-search'
            valTab.insert(0,CDisplayListItem('Historia wyszukiwania', 'Historia wyszukiwania', CDisplayListItem.TYPE_CATEGORY, [''], 'HISTORY', '', None)) 
            valTab.insert(0,CDisplayListItem('Szukaj',  'Szukaj filmów',                       CDisplayListItem.TYPE_SEARCH,   [''], '',        '', None)) 
            valTab.insert(0,CDisplayListItem("--- Archiwum programów Echo24 ---","Archiwum programów Echo24",     CDisplayListItem.TYPE_CATEGORY,['http://www.echo24.tv/archiwum'],'echo24-grupy',    '',None))
            valTab.insert(0,CDisplayListItem("--- Programy Echo24 ---","Programy Echo24",     CDisplayListItem.TYPE_CATEGORY,['http://www.echo24.tv/programy'],'echo24-grupy',    '',None))
            valTab.insert(0,CDisplayListItem("--- Aktualności ---","Aktualności",     CDisplayListItem.TYPE_CATEGORY,['http://www.echo24.tv/kategoria/13'],'echo24-clips',    '',None))
            valTab.insert(0,CDisplayListItem("--- Oglądaj na żywo ---","Oglądaj na żywo",     CDisplayListItem.TYPE_CATEGORY,['http://www.echo24.tv/live'],'echo24-play',    '',None))
            return valTab
        if 'echo24-search' == name:
            printDBG( 'Host name='+name )
            valTab = self.listsItems(-1, 'http://www.echo24.tv/szukaj?q='+url.replace(' ','+'), 'echo24-clips')
            return valTab    
        if 'echo24-grupy' == name:
            printDBG( 'Host listsItems begin name='+name )
            COOKIEFILE = os_path.join(GetCookieDir(), 'echo24.cookie')
            self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
            self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.get_Page(url)
            if not sts: return valTab
            printDBG( 'Host listsItems data: '+data )
            data2 = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="col-md-3', '</div>')
            for item in data2:
                Url = self.cm.ph.getSearchGroups(item, '''href=['"](/program/[^"^']+?)['"]''', 1, True)[0] 
                Image = self.cm.ph.getSearchGroups(item, '''image: url\(([^"^']+?)\)''', 1, True)[0] 

                #Title = self._cleanHtmlStr(item).split('   ')[0].strip()
                #Title2 = self._cleanHtmlStr(item).split('   ')[1].strip()
                Title = Url.split('/')[-1]
                Title2 = self._cleanHtmlStr(item).strip()

                if Url.startswith('//'): Url = 'http:' + Url
                if Url.startswith('/'): Url = 'http://www.echo24.tv' + Url
                if Image.startswith('/'): Image = 'http://www.echo24.tv' + Image
                if Url:
                    printDBG( 'Host Url: '+Url )

                    valTab.append(CDisplayListItem(Title,Title,CDisplayListItem.TYPE_CATEGORY, [Url],'echo24-clips', Image, None)) 
            return valTab
        if 'echo24-clips' == name:
            printDBG( 'Host listsItems begin name='+name )
            COOKIEFILE = os_path.join(GetCookieDir(), 'echo24.cookie')
            self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
            self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.get_Page(url)
            if not sts: return valTab
            printDBG( 'Host listsItems data: '+data )
            next = self.cm.ph.getDataBeetwenMarkers(data, '<div class="pages">', '</div>', False)[1]

            #data2 = self.cm.ph.getDataBeetwenMarkers(data, "Seriale zagraniczne", "footer", False)[1]
            #if not data2: data2 = self.cm.ph.getDataBeetwenMarkers(data, ">DODAJ SPEKTAKL", "footer", False)[1]
            data2 = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
            for item in data2:
                Url = self.cm.ph.getSearchGroups(item, '''href=['"](/artykul/[^"^']+?)['"]''', 1, True)[0] 
                if not Url: Url = self.cm.ph.getSearchGroups(item, '''href=['"](/odcinek/[^"^']+?)['"]''', 1, True)[0] 

                Image = self.cm.ph.getSearchGroups(item, '''image: url\(([^"^']+?)\)''', 1, True)[0] 

                #Title = self._cleanHtmlStr(item).split('   ')[0].strip()
                #Title2 = self._cleanHtmlStr(item).split('   ')[1].strip()
                Title = self._cleanHtmlStr(item).split('   ')[0]
                Title2 = self._cleanHtmlStr(item).strip()

                if Url.startswith('//'): Url = 'http:' + Url
                if Url.startswith('/'): Url = 'http://www.echo24.tv' + Url
                if Image.startswith('/'): Image = 'http://www.echo24.tv' + Image
                if Url:
                    valTab.append(CDisplayListItem(Title,Title2,CDisplayListItem.TYPE_CATEGORY, [Url],'echo24-play', Image, None)) 
            if next:
                link = re.findall('href="(.*?)"', next, re.S|re.I)
                if link:
                    next = link[-1]
                    url = re.sub('\?page.+', '', url)
                    if next.startswith('?'): next = url + next
                    valTab.append(CDisplayListItem('Next', next, CDisplayListItem.TYPE_CATEGORY, [next], name, '', None))
            return valTab
        if 'echo24-play' == name:
            printDBG( 'Host listsItems begin name='+name )
            COOKIEFILE = os_path.join(GetCookieDir(), 'echo24.cookie')
            self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
            self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.get_Page(url)
            if not sts: return valTab
            printDBG( 'Host listsItems data: '+data )
            Url = self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0]
            videoUrls = self.getLinksForVideo(Url)
            if videoUrls:
                for item in videoUrls:
                    Url = item['url']
                    Name = item['name']
                    #printDBG( 'Host name:  '+Name )
                    valTab.append(CDisplayListItem('Echo24    '+Name, 'Echo24    '+Name,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 0)], 0, 'http://www.echo24.tv/bundles/echo24web/favicons-assets/favicon-152.png', None))
            elif Url!='':
                sts, data = self.get_Page(Url)
                if not sts: return valTab
                printDBG( 'Host listsItems data2: '+data )
                Url = self.cm.ph.getSearchGroups(data, '''<source[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0]
                if self.cm.isValidUrl(Url): 
                    tmp = getDirectM3U8Playlist(Url, checkContent=True, sortWithMaxBitrate=999999999)
                    for item in tmp:
                        valTab.append(CDisplayListItem('Echo24    '+str(item['name']), 'Echo24    '+str(item['name']),  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', str(item['url']), 0)], 0, 'http://www.echo24.tv/bundles/echo24web/favicons-assets/favicon-152.png', None))
                    return valTab
            else:
                videoUrls = self.getLinksForVideo('https://www.youtube.com/channel/UCdoilpG38E_GuLKu5DPwchw/live')
                if videoUrls:
                    for item in videoUrls:
                        Url = item['url']
                        Name = item['name']
                        #printDBG( 'Host name:  '+Name )
                        valTab.append(CDisplayListItem('Live Echo24    '+Name, 'Live Echo24    '+Name,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 0)], 0, 'http://www.echo24.tv/bundles/echo24web/favicons-assets/favicon-152.png', None))
            return valTab

        if 'poplertv' == name:
            printDBG( 'Host listsItems begin name='+name )
            COOKIEFILE = os_path.join(GetCookieDir(), 'poplertv.cookie')
            self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
            self.HTTP_HEADER['Referer'] = 'http://www.popler.tv/live'
            self.HTTP_HEADER['X-Requested-With'] = 'XMLHttpRequest'
            self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            url = 'http://www.popler.tv/actions/rank_page.php'
            postdata = {'rodzaj': '1', 'page': '0', 'wiecej': '1'}
            sts, data = self.get_Page(url, self.defaultParams, postdata)
            if not sts: return valTab
            printDBG( 'Host listsItems data: '+data )
            ITEM_MARKER = '<div style="width:322px;height:213px'
            data = self.cm.ph.getDataBeetwenMarkers(data, ITEM_MARKER, 'Pokaż mniej')[1]
            data = data.split(ITEM_MARKER)
            del data[0]
            for item in data:
                icon  = ph.search(item, 'image:\surl\(([^"]+?)\)')[0]
                title = self._cleanHtmlStr(ITEM_MARKER + item).split('kamera IP')[0]
                title = title.split('na żywo')[0]
                if 'Kanał prywatny' in title: continue
                desc  = self._cleanHtmlStr(ITEM_MARKER + item).replace(',','\n').replace('Autor','\nAutor').strip()
                Url   = self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0]
                if Url.startswith('/'): Url = 'http://www.popler.tv' + Url
                valTab.append(CDisplayListItem(title.strip(), desc,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 1)], 0, '', None))
            #valTab.sort(key=lambda poz: poz.name)
            return valTab

        if 'hdontap' == name:
            printDBG( 'Host listsItems begin name='+name )
            self.MAIN_URL = 'https://hdontap.com' 
            COOKIEFILE = os_path.join(GetCookieDir(), 'hdontap.cookie')
            self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.getPage(url, 'hdontap.cookie', 'hdontap.com', self.defaultParams)
            if not sts: return ''
            printDBG( 'Host listsItems data1: '+str(data) )
            #data = self.cm.ph.getDataBeetwenMarkers(data, '<div id="secondary_nav">', '</div>', False)[1]
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<option value=', '</option>')
            for item in data:
                Url = self.cm.ph.getSearchGroups(item, '''value=['"]([^"^']+?)['"]''', 1, True)[0].replace(r'.','')
                Title = self._cleanHtmlStr(item) 
                Image = self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''', 1, True)[0] 
                if Url.startswith('//'): Url = 'http:' + Url
                if Url.startswith('/'): Url = 'http://hdontap.com' + Url
                if Image.startswith('//'): Image = 'http:' + Image
                if Image.startswith('/'): Image = 'http://hdontap.com' + Image
                valTab.append(CDisplayListItem(Title, Title, CDisplayListItem.TYPE_CATEGORY, [Url], 'hdontap-clips', '', None))
            return valTab
        if 'hdontap-clips' == name:
            printDBG( 'Host listsItems begin name='+name )
            COOKIEFILE = os_path.join(GetCookieDir(), 'hdontap.cookie')
            self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.getPage(self.MAIN_URL, 'hdontap.cookie', 'hdontap.com', self.defaultParams)
            if not sts: return ''
            printDBG( 'Host listsItems data1: '+str(data) )
            next = self.cm.ph.getDataBeetwenMarkers(data, 'pagination', 'NEXT', False)[1]
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'BEGIN CAM CARD', 'END CAM CARD')
            for item in data:
                Url = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0] 
                Title = self.cm.ph.getSearchGroups(item, '''alt=['"]([^"^']+?)['"]''', 1, True)[0] 
                Title2 = self._cleanHtmlStr(item).split('  ')[0].strip()
                Image = self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''', 1, True)[0] 
                if Url.startswith('//'): Url = 'http:' + Url
                if Url.startswith('/'): Url = 'http://hdontap.com' + Url
                if Image.startswith('//'): Image = 'http:' + Image
                if Image.startswith('/'): Image = 'http://hdontap.com' + Image
                if url in item:
                    valTab.append(CDisplayListItem(decodeHtml(Title), decodeHtml(Title),  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 1)], 0, Image, None))
            if next:
                link = re.findall('href="(.*?)"', next, re.S|re.I)
                if link:
                    next = link[-1]
                    if next.startswith('/'): next = 'https://hdontap.com' + next
                    valTab.append(CDisplayListItem('Next', next, CDisplayListItem.TYPE_CATEGORY, [next], name, '', None))
            return valTab

        if 'darmowa' == name:
            valTab.insert(0,CDisplayListItem("--- Pastebin --- Przypadkowe listy m3u, wyszukane w google na stronie pastebin.com","Przypadkowe listy m3u, wyszukane w google na stronie pastebin.com",     CDisplayListItem.TYPE_CATEGORY,['https://pastebin.com'],'pastebin',    '',None))
            #valTab.insert(0,CDisplayListItem("--- Zobacz.ws ---","Zobacz.ws",     CDisplayListItem.TYPE_CATEGORY,['http://zobacz.ws'],'zobacz_ws',    '',None))
            valTab.insert(0,CDisplayListItem("--- SwirTeam ---","SwirTeam",     CDisplayListItem.TYPE_CATEGORY,['http://tv-swirtvteam.info/'],'SwirTeamTk',    '',None))
            #valTab.insert(0,CDisplayListItem("--- SuperSportowo ---","SuperSportowo",     CDisplayListItem.TYPE_CATEGORY,['http://supersportowo.com'],'SuperSportowo',    '',None))
            valTab.insert(0,CDisplayListItem("--- Ustreamix ---","Ustreamix",     CDisplayListItem.TYPE_CATEGORY,['https://ssl.ustreamix.com/search.php?q=poland'],'Ustreamix',    '',None))
            return valTab
        if 'pastebin' == name:
            printDBG( 'Host listsItems begin name='+name )
            COOKIEFILE = os_path.join(GetCookieDir(), 'pastebin.cookie')
            #url = 'https://www.google.pl/search?q=%23extm3u+pastebin+poland&tbs=qdr:m'
            url = 'https://www.google.pl/search?q=extm3u+site%3Apastebin.com&tbs=qdr:m'
            #url = 'https://www.google.pl/search?q=extm3u+poland+tvp+site%3Apastebin.com&tbs=qdr:m'
            self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
            self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.get_Page(url)
            if not sts: return valTab
            printDBG( 'Host listsItems data: '+data )
            #data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '&')
            data = data.split('<div class="s">')
            if len(data): del data[0]
            for item in data:
                Url = self.cm.ph.getSearchGroups(item, '''href=['"](https://pastebin.com/[^"^']+?)['"]''', 1, True)[0] 
                desc = self._cleanHtmlStr(item).split(' - ')[0].strip()
                if Url:
                    Url = Url.replace('pastebin.com','pastebin.com/raw')
                    valTab.append(CDisplayListItem(Url+' ['+desc+']', '['+desc+'] '+Url, CDisplayListItem.TYPE_CATEGORY, [Url], 'pastebin-url', '', None))
            return valTab
        if 'pastebin-url' == name:
            printDBG( 'Host listsItems begin name='+name )
            COOKIEFILE = os_path.join(GetCookieDir(), 'pastebin.cookie')
            self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
            self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.get_Page(url)
            if not sts: return valTab
            if self.cm.meta['status_code']!=200:
                SetIPTVPlayerLastHostError(_(str(self.cm.meta['status_code'])))
                valTab.insert(0,CDisplayListItem('Status Code: '+str(self.cm.meta['status_code']),  'Status Code: '+str(self.cm.meta['status_code']),             CDisplayListItem.TYPE_MORE,             [''], '',        '', None)) 
                return valTab
            printDBG( 'Host listsItems data: '+data )
            data = ParseM3u(data)
            groups = {}
            for item in data:
                printDBG( 'Host item:%s ' % item )

                group = item.get('group-title', '')
                url = item['uri']
                icon = item.get('tvg-logo', '') 
            
                if item['f_type'] == 'inf':
                    valTab.append(CDisplayListItem(item['title'],url,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', url, 0)], 0, icon, None))

            return valTab 
        if 'darmowaonline' == name:
            printDBG( 'Host listsItems begin name='+name )
            COOKIEFILE = os_path.join(GetCookieDir(), 'darmowaonline.cookie')
            mainurl = 'http://darmowa-telewizja.online/'
            self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.getPage(url, 'darmowaonline.cookie', 'darmowa-telewizja.online', self.defaultParams)
            if not sts: return valTab
            printDBG( 'Host listsItems data: '+data )
            cookieHeader = self.cm.getCookieHeader(COOKIEFILE)
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li>', '</li>')
            for item in data:
                Url = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0] 
                Title = self.cm.ph.getSearchGroups(item, '''alt=['"]([^"^']+?)['"]''', 1, True)[0]
                Image = self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''', 1, True)[0] 
                if Url.startswith('//'): Url = 'http:' + Url
                #if Url.startswith('i'): Url = mainurl + Url
                if Image.startswith('//'): Image = 'http:' + Image
                if Image.startswith('g'): Image = mainurl + Image
                if  not 'http' in Url: Url = mainurl + Url
                Image = strwithmeta(Image, {'Cookie':cookieHeader, 'User-Agent':self.USER_AGENT})
                if Title:
                    valTab.append(CDisplayListItem(decodeHtml(Title), decodeHtml(Title),  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 1)], 0, Image, None))
            return valTab
        if 'SwirTeamTk' == name:
            printDBG( 'Host listsItems begin name='+name )
            COOKIEFILE = os_path.join(GetCookieDir(), 'SwirTeamTk.cookie')
            mainurl = 'http://tv-swirtvteam.info/'
            self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.getPage(url, 'SwirTeamTk.cookie', 'tv-swirtvteam.info', self.defaultParams)
            if not sts: 
                SetIPTVPlayerLastHostError(_(' Wystąpił chwilowy problem z naszymi serwerami.'))
                return []
            printDBG( 'Host listsItems data: '+data )
            cookieHeader = self.cm.getCookieHeader(COOKIEFILE)
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li>', '</li>')
            for item in data:
                Url = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0] 
                Title = self.cm.ph.getSearchGroups(item, '''title=['"]([^"^']+?)['"]''', 1, True)[0]
                Image = self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''', 1, True)[0] 
                if Url.startswith('//'): Url = 'http:' + Url
                #if Url.startswith('i'): Url = mainurl + Url
                if Image.startswith('//'): Image = 'http:' + Image
                if Image.startswith('i'): Image = mainurl + Image
                if  not 'http' in Url: Url = mainurl + Url
                Image = strwithmeta(Image, {'Cookie':cookieHeader, 'User-Agent':self.USER_AGENT})
                if 'run?' in Url: Title = Title + ' [ swirtvteam ]'
                if 'planet?' in Url: Title = ''
                if 'weeb/?' in Url: Title = Title + ' [ weeb ]'
                if 'gold/?' in Url: Title = ''
                if 'ipla' in Title: Title = ''
                if Title:
                    valTab.append(CDisplayListItem(decodeHtml(Title), decodeHtml(Title),  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 1)], 0, Image, None))
            return valTab
        if 'Ustreamix' == name:
            printDBG( 'Host listsItems begin name='+name )
            COOKIEFILE = os_path.join(GetCookieDir(), 'Ustreamix.cookie')
            mainurl = 'https://ustreamix.com'
            self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.getPage(url, 'Ustreamix.cookie', 'ustreamix.com', self.defaultParams)
            if not sts: 
                SetIPTVPlayerLastHostError(_(' Wystąpił chwilowy problem z naszymi serwerami.'))
                return []
            printDBG( 'Host listsItems data: '+data )
            cookieHeader = self.cm.getCookieHeader(COOKIEFILE)
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<p>', '</p>')
            for item in data:
                Url = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0] 
                Title = self._cleanHtmlStr(item)  #.split('  ')[0].strip()
                Image = self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''', 1, True)[0] 
                if Url.startswith('//'): Url = 'http:' + Url
                #if Url.startswith('i'): Url = mainurl + Url
                if Image.startswith('//'): Image = 'http:' + Image
                if Image.startswith('i'): Image = mainurl + Image
                if  not 'http' in Url: Url = mainurl + Url
                Image = strwithmeta(Image, {'Cookie':cookieHeader, 'User-Agent':self.USER_AGENT})
                if not '=' in Title and 'Live' in Title:
                    valTab.append(CDisplayListItem(decodeHtml(Title), decodeHtml(Title),  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 1)], 0, Image, None))
            valTab.sort(key=lambda poz: poz.name)
            if self.currList[Index].possibleTypesOfSearch != 'end':
                valTab.insert(0,CDisplayListItem("--- Wszystkie ---","All",     CDisplayListItem.TYPE_CATEGORY,['https://ssl.ustreamix.com/channels'],name,    '','end'))

            return valTab

        if 'SuperSportowo' == name:
            printDBG( 'Host listsItems begin name='+name )
            COOKIEFILE = os_path.join(GetCookieDir(), 'SuperSportowo.cookie')
            mainurl = 'https://supersportowo.com/'
            self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.getPage(url, 'SuperSportowo.cookie', 'supersportowo.com', self.defaultParams)
            if not sts: 
                SetIPTVPlayerLastHostError(_(' Wystąpił chwilowy problem z naszymi serwerami.'))
                return []
            printDBG( 'Host listsItems data: '+data )
            cookieHeader = self.cm.getCookieHeader(COOKIEFILE)
            #data = data.split('<img')
            #del data[0]
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
            for item in data:
                Url   = self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0]
                #link = Url.replace('.html','')
                link = decodeHtml(self._cleanHtmlStr(item))
                if Url.startswith('/'): Url = mainurl + Url
                if Url.startswith('//'): Url = 'http:' + Url
                if  not 'http' in Url: Url = mainurl + Url
                Image = self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''', 1, True)[0] 
                if Image.startswith('//'): Image = 'http:' + Image
                if Image.startswith('i'): Image = mainurl + Image
                Image = strwithmeta(Image, {'Referer': mainurl, 'Cookie':cookieHeader, 'User-Agent':self.USER_AGENT})
                if 'stream' in Url:
                    valTab.append(CDisplayListItem(link, link,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 1)], 0, Image, None))
            #valTab.sort(key=lambda poz: poz.name)
            return valTab

        if 'zobacz_ws' == name:
            printDBG( 'Host listsItems begin name='+name )
            COOKIEFILE = os_path.join(GetCookieDir(), 'zobacz.cookie')
            mainurl = 'http://zobacz.ws'
            self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.getPage(url, 'zobacz.cookie', 'zobacz.ws', self.defaultParams)
            if not sts: return valTab
            printDBG( 'Host listsItems data: '+data )
            cookieHeader = self.cm.getCookieHeader(COOKIEFILE)
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li id="menu-item', '</li>')
            for item in data:
                Url = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0] 
                Title = self._cleanHtmlStr(item).strip()
                if Url.startswith('//'): Url = 'http:' + Url
                #if Url.startswith('i'): Url = mainurl + Url
                if  not 'http' in Url: Url = mainurl + Url
                if 'Dodaj' in Title or 'Sprawdz' in Title or 'Zgłoś' in Title: Title = ''
                if Title and Url:
                    valTab.append(CDisplayListItem(Title, Url, CDisplayListItem.TYPE_CATEGORY, [Url], 'zobacz_ws-clips', '', None))
            return valTab
        if 'zobacz_ws-clips' == name:
            printDBG( 'Host listsItems begin name='+name )
            COOKIEFILE = os_path.join(GetCookieDir(), 'zobacz.cookie')
            mainurl = 'http://zobacz.ws'
            self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.getPage(url, 'zobacz.cookie', 'zobacz.ws', self.defaultParams)
            if not sts: return valTab
            printDBG( 'Host listsItems data: '+data )
            cookieHeader = self.cm.getCookieHeader(COOKIEFILE)
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<td class="column', '</td>')
            for item in data:
                Url = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0] 
                Image = self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''', 1, True)[0] 
                Title = self._cleanHtmlStr(item).strip()
                if not Title: Title = Url.split('/')[-1]
                if Url.startswith('//'): Url = 'http:' + Url
                if Image.startswith('//'): Image = 'http:' + Image
                if  not 'http' in Url: Url = mainurl + Url
                Image = strwithmeta(Image, {'Cookie':cookieHeader, 'User-Agent':self.USER_AGENT})
                if Title and Url:
                    valTab.append(CDisplayListItem(decodeHtml(Title), decodeHtml(Title),  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 1)], 0, Image, None))

        if 'iplax' == name:
            printDBG( 'Host listsItems begin name='+name )
            COOKIEFILE = os_path.join(GetCookieDir(), 'iplax.cookie')
            mainurl = 'https://iplax.eu/'
            self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.getPage(url, 'iplax.cookie', 'iplax.eu', self.defaultParams)
            if not sts: return valTab
            printDBG( 'Host listsItems data: '+data )
            cookieHeader = self.cm.getCookieHeader(COOKIEFILE)
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<h4>', '</h4>')
            for item in data:
                Url = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0] 
                Title = self._cleanHtmlStr(item).replace('Explore more','').strip()

                Image = self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''', 1, True)[0] 
                if Url.startswith('//'): Url = 'http:' + Url
                #if Url.startswith('i'): Url = mainurl + Url
                if Image.startswith('//'): Image = 'http:' + Image
                if Image.startswith('g'): Image = mainurl + Image
                if  not 'http' in Url: Url = mainurl + Url
                Image = strwithmeta(Image, {'Cookie':cookieHeader, 'User-Agent':self.USER_AGENT})
                if not 'Featured video' in Title:
                    valTab.append(CDisplayListItem(Title, Url, CDisplayListItem.TYPE_CATEGORY, [Url], 'iplax-clips', '', None))
            self.SEARCH_proc='iplax-search'
            valTab.insert(0,CDisplayListItem('Historia wyszukiwania', 'Historia wyszukiwania', CDisplayListItem.TYPE_CATEGORY, [''], 'HISTORY', '', None)) 
            valTab.insert(0,CDisplayListItem('Szukaj',  'Szukaj filmów',                       CDisplayListItem.TYPE_SEARCH,   [''], '',        '', None)) 
            return valTab
        if 'iplax-search' == name:
            printDBG( 'Host name='+name )
            valTab = self.listsItems(-1, 'https://iplax.eu/search?keyword='+url.replace(' ','+'), 'iplax-clips')
            return valTab    
        if 'iplax-clips' == name:
            printDBG( 'Host listsItems begin name='+name )
            COOKIEFILE = os_path.join(GetCookieDir(), 'iplax.cookie')
            mainurl = 'https://iplax.eu/'
            self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.getPage(url, 'iplax.cookie', 'iplax.eu', self.defaultParams)
            if not sts: return valTab
            printDBG( 'Host listsItems data: '+data )
            next = self.cm.ph.getDataBeetwenMarkers(data, 'pagination', 'Next Page', False)[1]
            data = data.split('data-id=')
            del data[0]
            for item in data:
                Image  = self.cm.ph.getSearchGroups(item, 'src="([^"]+?)"')[0]
                Title = self.cm.ph.getSearchGroups(item, 'alt="([^"]+?)"')[0].strip()
                Url   = self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0]
                if Url.startswith('/'): Url = mainurl + Url
                valTab.append(CDisplayListItem(decodeHtml(Title), decodeHtml(Title),  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 1)], 0, Image, None))
            if next:
                link = re.findall('href="(.*?)"', next, re.S|re.I)
                if link:
                    next = link[-1]
                    if next.startswith('/'): next = mainurl + next
                    valTab.append(CDisplayListItem('Next', next, CDisplayListItem.TYPE_CATEGORY, [next], name, '', None))
            return valTab

        if 'task' == name:
            printDBG( 'Host listsItems begin name='+name )
            mainurl = 'http://www.task.gda.pl'
            COOKIEFILE = os_path.join(GetCookieDir(), 'task.cookie')
            self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
            self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.get_Page(url)
            if not sts: return valTab
            printDBG( 'Host listsItems data: '+data )
            tekst = '<a class="streamLink"'
            data = data.split(tekst)
            del data[0]
            for item in data:
                Image  = self.cm.ph.getSearchGroups(item, 'src="([^"]+?)"')[0]
                Title = self.cm.ph.getSearchGroups(item, '<p>([^>]+?)<')[0].strip()
                if not Title: Title = self.cm.ph.getSearchGroups(item, 'alt="([^"]+?)"')[0].strip()
                Url   = self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0]
                if Url.startswith('/'): Url = mainurl + Url
                if Url.startswith('kamer'): Url = mainurl + '/' + Url
                if Image.startswith('/'): Image = mainurl + Image
                valTab.append(CDisplayListItem(decodeHtml(Title), decodeHtml(Title),  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 1)], 0, Image, None))
            return valTab

        if 'szczyrk' == name:
            printDBG( 'Host listsItems begin name='+name )
            mainurl = 'https://www.szczyrkowski.pl'
            COOKIEFILE = os_path.join(GetCookieDir(), 'szczyrk.cookie')
            self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
            self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.get_Page(url)
            if not sts: return valTab
            printDBG( 'Host listsItems data: '+data )
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<figure', '</figure>')

            for item in data:
                Image  = self.cm.ph.getSearchGroups(item, 'srcset="([^"]+?)"')[0]
                Title = self.cm.ph.getSearchGroups(item, 'image-caption">([^>]+?)<')[0].strip()
                if not Title: Title = self.cm.ph.getSearchGroups(item, 'alt="([^"]+?)"')[0].strip()
                Url   = self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0]
                if Url.startswith('/'): Url = mainurl + Url
                if Image.startswith('/'): Image = mainurl + Image
                if Title:
                    valTab.append(CDisplayListItem(decodeHtml(Title), decodeHtml(Title),  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 1)], 0, Image, None))
            return valTab

        if 'rzeczka' == name:
            printDBG( 'Host listsItems begin name='+name )
            mainurl = 'https://www.nartyrzeczka.com'
            COOKIEFILE = os_path.join(GetCookieDir(), 'rzeczka.cookie')
            self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
            self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.get_Page(url)
            if not sts: return valTab
            printDBG( 'Host listsItems data: '+data )
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<p style="text-align', '</iframe>')
            for item in data:
                Image  = self.cm.ph.getSearchGroups(item, 'srcset="([^"]+?)"')[0]
                Title = self._cleanHtmlStr(item).replace('\n','').strip()
                if not Title: Title = self.cm.ph.getSearchGroups(item, 'alt="([^"]+?)"')[0].strip()
                Url = self.cm.ph.getSearchGroups(item, 'src="([^"]+?)"')[0]
                if Url.startswith('//'): Url = 'http:' + Url
                if Url.startswith('/'): Url = mainurl + Url
                if Image.startswith('/'): Image = mainurl + Image
                if Title:
                    valTab.append(CDisplayListItem(decodeHtml(Title), decodeHtml(Title),  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 1)], 0, Image, None))
            return valTab

        if 'skrzyczne' == name:
            printDBG( 'Host listsItems begin name='+name )
            valTab.append(CDisplayListItem('COS-JAWORZYNA', 'COS-JAWORZYNA',  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'http://www.skrzyczne.cos.pl/cos-jaworzyna.html', 1)], 0, '', None))
            valTab.append(CDisplayListItem('COS-FIS', 'COS-FIS',  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'http://www.skrzyczne.cos.pl/cos-fis.html', 1)], 0, '', None))
            valTab.append(CDisplayListItem('COS-DOLNA-STACJA', 'COS-DOLNA-STACJA',  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'http://www.skrzyczne.cos.pl/cos-dolna-stacja.html', 1)], 0, '', None))
            return valTab

        if 'korbielów' == name:
            printDBG( 'Host listsItems begin name='+name )
            mainurl = 'https://korbielow.net'
            COOKIEFILE = os_path.join(GetCookieDir(), 'korbielów.cookie')
            self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
            self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.get_Page(url)
            if not sts: return valTab
            printDBG( 'Host listsItems data: '+data )
            data2 = self.cm.ph.getAllItemsBeetwenMarkers(data, 'title_big">', '</iframe>')
            for item in data2:
                Title = self.cm.ph.getSearchGroups(item, 'title_big">([^>]+?)<')[0].strip()
                Url = self.cm.ph.getSearchGroups(item, 'src="([^"]+?)"')[0]
                if Url.startswith('//'): Url = 'http:' + Url
                if Url.startswith('/'): Url = mainurl + Url
                if Title:
                    valTab.append(CDisplayListItem(decodeHtml(Title), decodeHtml(Title),  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 1)], 0, '', None))
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '</script><p>', '</iframe>')
            for item in data:
                Image  = self.cm.ph.getSearchGroups(item, 'srcset="([^"]+?)"')[0]
                Title = self._cleanHtmlStr(item).replace('\n','').strip()
                if not Title: Title = self.cm.ph.getSearchGroups(item, 'alt="([^"]+?)"')[0].strip()
                Url = self.cm.ph.getSearchGroups(item, 'src="([^"]+?)"')[0]
                if Url.startswith('//'): Url = 'http:' + Url
                if Url.startswith('/'): Url = mainurl + Url
                if Image.startswith('/'): Image = mainurl + Image
                if Title:
                    valTab.append(CDisplayListItem(decodeHtml(Title), decodeHtml(Title),  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 1)], 0, Image, None))
            return valTab
#############################################
        if len(url)>8:
           COOKIEFILE = os_path.join(GetCookieDir(), 'info.cookie')
           self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
           self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': False, 'save_cookie': True, 'cookiefile': COOKIEFILE}
           sts, data = self.get_Page(url)
           if not sts: return valTab
           printDBG( 'Host listsItems data: '+data )

        if 'info' == name:
            x = 0
            if '|+++|' in data:
                data2 = data.split('|+++|')
                for item in data2:
                    if x==0:
                        a=1
                    else:
                        a=2
                    Updated = item.split('\n')[a]
                    Name = 'samsamsam' #item.split('\n')[a+1] 
                    Title = item.split('\n')[a+2]
                    if x == config.plugins.iptvplayer.ilepozycji.value : break
                    x += 1
                    Updated = Updated.replace('T', '   ').replace('Z', '   ')
                    Updated = Updated.replace('+01:00', '   ').replace('+02:00', '   ').replace('+00:00', '   ')
                    valTab.append(CDisplayListItem(Updated+' '+Name+'  >>  '+decodeHtml(Title),decodeHtml(Title),CDisplayListItem.TYPE_CATEGORY, [''],'', '', None)) 
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<entry>', '</entry>')
            for item in data:
                Title = self.cm.ph.getSearchGroups(item, '''<title>([^>]+?)</title>''', 1, True)[0] 
                Updated = self.cm.ph.getSearchGroups(item, '''<updated>([^>]+?)</updated>''', 1, True)[0] 
                Name = self.cm.ph.getSearchGroups(item, '''<name>([^>]+?)</name>''', 1, True)[0] 
                if x == config.plugins.iptvplayer.ilepozycji.value : break #return valTab
                x += 1
                Updated = Updated.replace('T', '   ').replace('Z', '   ')
                Updated = Updated.replace('+01:00', '   ').replace('+02:00', '   ').replace('+00:00', '   ')
                printDBG( 'Host Title '+Title )
                valTab.append(CDisplayListItem(Updated+' '+Name+'  >>  '+decodeHtml(Title),decodeHtml(Title),CDisplayListItem.TYPE_CATEGORY, [''],'', '', None)) 
            if 'mosz_nowy' in url:
                Url = 'https://gitlab.com/mosz_nowy/e2iplayer' 
            elif 'zadmario' in url:
                Url = 'https://gitlab.com/zadmario/e2iplayer'
            elif 'maxbambi' in url:
                Url = 'https://gitlab.com/maxbambi/e2iplayer'
            else:
                Url = 'http://www.e2iplayer.gitlab.io/update2/log.txt'
            if 'mosz_nowy' in url:
                valTab.append(CDisplayListItem('!!!  DUK  !!!','',CDisplayListItem.TYPE_CATEGORY, [''],'Duk', '', None)) 
            if Url!='http://www.e2iplayer.gitlab.io/update2/log.txt':
                valTab.append(CDisplayListItem('!!!  Download & Install & Restart E2  !!!','UWAGA! Klikasz na własne ryzyko, opcja nie była do końca testowana',CDisplayListItem.TYPE_CATEGORY, [Url],'Download', 'https://image.freepik.com/darmowe-ikony/chmura-ze-strza%C5%82k%C4%85-skierowan%C4%85-w-do%C5%82-interfejs-symbol-ios-7_318-38595.jpg', None)) 
            return valTab

        if 'Duk' == name:
            if IsExecutable('wget'):
                path = config.plugins.iptvplayer.dukpath.value
                if path == '': path = GetPluginDir('/bin/duk')
                serwer_url = 'http://iptvplayer.vline.pl/resources/bin/{0}/duk'.format(config.plugins.iptvplayer.plarform.value)
                cmd =  'wget "%s" -O "%s" && chmod 777 "%s" ' % (serwer_url, path, path)
                printDBG("cmd = %s" % cmd)
                try:
                    iptv_system (cmd)
                except Exception as e:
                    printExc()
                    msg = _("Last error:\n%s" % str(e))
                    GetIPTVNotify().push('%s' % msg, 'error', 20)
                valTab.append(CDisplayListItem('Update DUK.',   'DUK', CDisplayListItem.TYPE_CATEGORY, [''], '', '', None)) 
            return valTab

        if 'lubelska' == name:
            printDBG( 'Host name='+name )
            Url = 'https://www.youtube.com/channel/UCYxbE-WoPqKq26sSeQ6eD1w/live'
            videoUrls = self.getLinksForVideo(Url)
            if videoUrls:
                for item in videoUrls:
                    Url = item['url']
                    Name = item['name']
                    printDBG( 'Host name:  '+Name )
                    valTab.append(CDisplayListItem('Lubelska TV    '+Name, 'Lubelska TV    '+Name,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 0)], 0, '', None))
            else:
                Url = 'https://www.youtube.com/watch?v=I1lQZjRQ45s'
                videoUrls = self.getLinksForVideo(Url)
                if videoUrls:
                    for item in videoUrls:
                        Url = item['url']
                        Name = item['name']
                        printDBG( 'Host name:  '+Name )
                        valTab.append(CDisplayListItem('Archiwalna Telewizja Kraśnik    '+Name, 'Archiwalna Telewizja Kraśnik    '+Name,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 0)], 0, '', None))
            return valTab 

        if 'szczecin' == name:
            printDBG( 'Host listsItems begin name='+name )
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="miniatur">', '</div>')
            for item in data:
                Title = self.cm.ph.getSearchGroups(item, '''title=['"]([^"^']+?)['"]''', 1, True)[0]
                Url = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0] 
                Image = self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?jpg)['"]''', 1, True)[0] 
                valTab.append(CDisplayListItem(decodeHtml(Title), decodeHtml(Title),  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 1)], 0, Image, None))
            return valTab 

        if 'zywiec' == name:
            printDBG( 'Host listsItems begin name='+name )
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<iframe', '</iframe')
            for item in data:
                Url = self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''', 1, True)[0] 
                Image = 'http://www.zywiec.pl/images/stopka_logo.png'
                Title = 'Kamera'
                if 'index.htm' in Url: Title = 'Kamera nr 1 rynek'
                if 'index2.htm' in Url: Title = 'Kamera nr 2 rynek'
                if 'index3.htm' in Url: Title = 'Kamera nr 3 rynek'
                valTab.append(CDisplayListItem(decodeHtml(Title), decodeHtml(Title),  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 1)], 0, Image, None))
            return valTab 

        if 'skoczow' == name:
            printDBG( 'Host listsItems begin name='+name )
            channel = self.cm.ph.getSearchGroups(data, '''channel=([^"^']+?)&''')[0]
            if not channel: channel = self.cm.ph.getSearchGroups(data, '''youtube\.com/channel/([^"^']+?)/''')[0]
            Url = 'https://www.youtube.com/channel/'+channel+'/live'
            videoUrls = self.getLinksForVideo(Url)
            if videoUrls:
                for item in videoUrls:
                    Url = item['url']
                    Name = item['name']
                    printDBG( 'Host name:  '+Name )
                    valTab.append(CDisplayListItem('Parafia Skoczów    '+Name, 'Parafia Skoczów    '+Name,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 0)], 0, '', None))
            return valTab 

        if 'jasna' == name:
            printDBG( 'Host listsItems begin name='+name )
            Url = self.cm.ph.getSearchGroups(data, '''href=['"](https://www.youtube.com/channel/[^"^']+?)['"]''')[0]+'/live'
            if not Url: Url = 'https://www.youtube.com/channel/UCKAtPxfE2RAHSCwDABMMeAg/live'
            videoUrls = self.getLinksForVideo(Url)
            if videoUrls:
                for item in videoUrls:
                    Url = item['url']
                    Name = item['name']
                    printDBG( 'Host name:  '+Name )
                    valTab.append(CDisplayListItem('Jasna Góra    '+Name, 'Jasna Góra    '+Name,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 0)], 0, 'http://www.jasnagora.com/zdjecia/galerie_nowe/1755.jpg', None))
            return valTab 

        if 'zabrze' == name:
            printDBG( 'Host listsItems begin name='+name )
            videoUrls = self.getLinksForVideo(url)
            if videoUrls:
                for item in videoUrls:
                    Url = item['url']
                    Name = item['name']
                    printDBG( 'Host name:  '+Name )
                    valTab.append(CDisplayListItem('Zabrze TV    '+Name, 'Zabrze TV    '+Name,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 0)], 0, 'http://tvzabrze.pl/assets/images/logo.png', None))
            return valTab 

        if 'dw' == name:
            printDBG( 'Host listsItems begin name='+name )
            videoUrls = self.getLinksForVideo(url)
            if videoUrls:
                for item in videoUrls:
                    Url = item['url']
                    Name = item['name']
                    printDBG( 'Host name:  '+Name )
                    valTab.append(CDisplayListItem('Deutsche Welle Live    '+Name, 'Deutsche Welle Live    '+Name,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 0)], 0, 'https://yt3.ggpht.com/--ZKsQsVYm2c/AAAAAAAAAAI/AAAAAAAAAAA/f0s4KdtP2Cg/s100-c-k-no-mo-rj-c0xffffff/photo.jpg', None))
            return valTab 

        if 'tvsudecka' == name:
            printDBG( 'Host listsItems begin name='+name )
            link = re.search('<iframe\ssrc="(http[s]?://www.youtube.com.*?)"', data, re.S|re.I)
            if link:
                pageUrl = link.group(1)
                query_data = {'url': pageUrl, 'use_host': False, 'use_cookie': False, 'use_post': False, 'return_data': True}
                try:
                   data = self.cm.getURLRequestData(query_data)
                except:
                   printDBG( 'Host listsItems ERROR' )
                   return valTab
                #printDBG( 'Host listsItems data : '+data )
                link = re.search('href="(http[s]?://www.youtube.com.*?)"', data, re.S|re.I)
                videoUrls = self.getLinksForVideo(link.group(1))
                if videoUrls:
                   for item in videoUrls:
                      Url = item['url']
                      Name = item['name']
                      printDBG( 'Host Url:  '+Url )
                      printDBG( 'Host name:  '+Name )
                      valTab.append(CDisplayListItem('TV Sudecka   '+Name, 'TV Sudecka   '+Name,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 0)], 0, 'https://pbs.twimg.com/profile_images/585880676693454849/2eAO2_hC.jpg', None))
            return valTab 

        if 'klodzka' == name:
            printDBG( 'Host listsItems begin name='+name )
            videoUrls = self.getLinksForVideo(url)
            if videoUrls:
                for item in videoUrls:
                    Url = item['url']
                    Name = item['name']
                    printDBG( 'Host name:  '+Name )
                    valTab.append(CDisplayListItem('TV Kłodzka  '+Name, 'TV Kłodzka  '+Name,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 0)], 0, 'https://d-nm.ppstatic.pl/k/r/46/d7/4c227342bda20_o.jpg', None))
                return valTab 

            url = self.cm.ph.getSearchGroups(data, '''href=['"](/watch\?v=[^"^']+?)['"]''')[0] 
            if url.startswith('//'): url = 'https:' + url 
            if url.startswith('/'): url = 'https://www.youtube.com' + url 
            videoUrls = self.getLinksForVideo(url)
            if videoUrls:
                for item in videoUrls:
                    Url = item['url']
                    Name = item['name']
                    printDBG( 'Host name:  '+Name )
                    valTab.append(CDisplayListItem('TV Kłodzka Archiwalne '+Name, 'TV Kłodzka Archiwalne '+Name,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 0)], 0, 'https://d-nm.ppstatic.pl/k/r/46/d7/4c227342bda20_o.jpg', None))
            return valTab 

        if 'gorlice' == name:
            printDBG( 'Host listsItems begin name='+name )
            link = re.search('(//www.gorlice.tv/embed/.*?)"', data, re.S|re.I)
            if link:
                Url = link.group(1)
                if Url.startswith('//'): Url = 'http:' + Url 
                query_data = {'url': Url, 'use_host': False, 'use_cookie': False, 'use_post': False, 'return_data': True}
                try:
                   data = self.cm.getURLRequestData(query_data)
                except:
                   printDBG( 'Host listsItems ERROR' )
                   return valTab
                #printDBG( 'Host listsItems data youtube '+data )
                youtube_url = self.cm.ph.getSearchGroups(data, '''(//[www.]?youtu[^"^']+?)['"?]''')[0] 
                if youtube_url.startswith('//'): youtube_url = 'https:' + youtube_url 
                if not youtube_url:
                   youtube_url = self.cm.ph.getSearchGroups(data, '''(https://www.youtube.com[^"^']+?)['"]''')[0] 
                #printDBG( 'Host listsItems data youtube_url '+youtube_url )
                videoUrls = self.getLinksForVideo(youtube_url)
                if videoUrls:
                   for item in videoUrls:
                      Url = item['url']
                      Name = item['name']
                      printDBG( 'Host name:  '+Name )
                      valTab.append(CDisplayListItem('TV Gorlice    '+Name, 'TV Gorlice    '+Name,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 0)], 0, 'http://gorlice.tv/static/gfx/service/gorlicetv/logo.png?96eb5', None))
            return valTab 

        if 'narew' == name:
            printDBG( 'Host listsItems begin name='+name )
            Url = 'https://www.youtube.com/channel/UCWeOx1YkCKswFOeJVyMG7mw/live'
            videoUrls = self.getLinksForVideo(Url)
            if videoUrls:
                for item in videoUrls:
                    Url = item['url']
                    Name = item['name']
                    printDBG( 'Host name:  '+Name )
                    valTab.append(CDisplayListItem('TV Narew  '+Name, 'TV Narew  '+Name,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 0)], 0, 'https://pbs.twimg.com/profile_images/684831832307810306/M9KmKBse_400x400.jpg', None)) 
            else:
                videoUrls = self.getLinksForVideo('https://www.youtube.com/watch?v=tVMQA--5ppg')
                if videoUrls:
                    for item in videoUrls:
                        Url = item['url']
                        Name = item['name']
                        printDBG( 'Host name:  '+Name )
                        valTab.append(CDisplayListItem('Kamera TV Narew  '+Name, 'Kamera TV Narew  '+Name,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 0)], 0, 'https://pbs.twimg.com/profile_images/684831832307810306/M9KmKBse_400x400.jpg', None))
            return valTab 

        if 'lourdes' == name:
            printDBG( 'Host listsItems begin name='+name )
            youtube_link = self.cm.ph.getSearchGroups(data, '''href=['"](https://www.youtube.com[^"^']+?)['"]''')[0] 
            try: data = self.cm.getURLRequestData({'url': youtube_link, 'use_host': False, 'use_cookie': False, 'use_post': False, 'return_data': True})
            except:
                printDBG( 'Host listsItems ERROR' )
                return valTab
            #printDBG( 'Host listsItems data youtube '+data )
            youtube_link = self.cm.ph.getSearchGroups(data, '''data-context-item-id=['"]([^"^']+?)['"]''')[0] 
            videoUrls = self.getLinksForVideo('https://www.youtube.com/watch?v='+youtube_link)
            if videoUrls:
               for item in videoUrls:
                  Url = item['url']
                  Name = item['name']
                  printDBG( 'Host Url:  '+Url )
                  printDBG( 'Host name:  '+Name )
                  valTab.append(CDisplayListItem('TV Lourdes  '+Name, 'TV Lourdes  '+Name,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 0)], 0, 'http://mozecoswiecej.pl/wp-content/uploads/2017/02/VirgendeLourdes.jpg', None))
            link = re.search('source: "(.*?)"', data, re.S|re.I)
            if link:
               valTab.append(CDisplayListItem('TV Lourdes  '+'Clappr', 'TV Lourdes  '+'Clappr',  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', link.group(1), 0)], 0, 'http://mozecoswiecej.pl/wp-content/uploads/2017/02/VirgendeLourdes.jpg', None))
            Url = 'http://bsbdr-apple-live.adaptive.level3.net/apple/bstream/bsbdr/bdrhlslive1_Layer2.m3u8'
            valTab.append(CDisplayListItem('TV Lourdes  '+'(m3u8)', 'TV Lourdes  '+'(m3u8)',  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 0)], 0, 'http://mozecoswiecej.pl/wp-content/uploads/2017/02/VirgendeLourdes.jpg', None))
            return valTab 

        if 'ctv' == name:
            printDBG( 'Host listsItems begin name='+name )
            videoUrls = self.getLinksForVideo(url)
            if videoUrls:
                for item in videoUrls:
                    Url = item['url']
                    Name = item['name']
                    printDBG( 'Host Url:  '+Url )
                    printDBG( 'Host name:  '+Name )
                    valTab.append(CDisplayListItem('CTV Watykan  '+Name, 'CTV Watykan  '+Name,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 0)], 0, 'http://www.vaticannews.va/etc/designs/vatican-news/release/library/main/images/appletouch.png', None))
            return valTab 

        if 'eotv' == name:
            printDBG( 'Host listsItems begin name='+name )
            link = re.search('<iframe src="(.*?)"', data, re.S|re.I)
            if link:
                Url = 'http://eotv.de'+link.group(1)
                query_data = {'url': Url, 'use_host': False, 'use_cookie': False, 'use_post': False, 'return_data': True}
                try:
                   data = self.cm.getURLRequestData(query_data)
                except:
                   printDBG( 'Host listsItems ERROR' )
                   return valTab
                #printDBG( 'Host listsItems data '+data )
                link = re.findall('<script type.*?src="(.*?)"', data, re.S|re.I)
                if link:
                   Url = 'http://eotv.de'+link[-1]
                   query_data = {'url': Url, 'use_host': False, 'use_cookie': False, 'use_post': False, 'return_data': True}
                   try:
                      data = self.cm.getURLRequestData(query_data)
                   except:
                      printDBG( 'Host listsItems ERROR' )
                      return valTab
                   #printDBG( 'Host listsItems data '+data )
                   http = re.search("http = '(.*?)'", data, re.S|re.I)
                   if http:
                      url = http.group(1)
                      if self.cm.isValidUrl(url): 
                          tmp = getDirectM3U8Playlist(url)
                          for item in tmp:
                                valTab.append(CDisplayListItem('EO TV   '+str(item['name']), 'EO TV',  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', str(item['url']), 0)], 0, 'http://eotv.de/wp-content/uploads/2015/12/Cranberry-Logo.png', None))
                   rtmp = re.search("rtmp = '(.*?)'", data, re.S|re.I)
                   if rtmp:
                      rtmp = rtmp.group(1)+' live=1'
                      valTab.append(CDisplayListItem('EO TV   (rtmp)', 'EO TV',  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', rtmp, 0)], 0, 'http://eotv.de/wp-content/uploads/2015/12/Cranberry-Logo.png', None))
            return valTab 

        if 'asta' == name:
            printDBG( 'Host listsItems begin name='+name )
            url = self.cm.ph.getSearchGroups(data, '''file:['"]([^"^']+?m3u8)['"]''', 1, True)[0]
            if self.cm.isValidUrl(url): 
                tmp = getDirectM3U8Playlist(url)
                for item in tmp:
                    valTab.append(CDisplayListItem(str(item['name']), str(item['url']),  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', str(item['url']), 0)], 0, 'http://www.tvasta.pl/resources/images/logo_tvasta.png', None))
            Url = 'http://www.asta24.pl/kamera.html'
            query_data = {'url': Url, 'use_host': False, 'use_cookie': False, 'use_post': False, 'return_data': True}
            try:
                data = self.cm.getURLRequestData(query_data)
            except:
                printDBG( 'Host listsItems ERROR' )
                return valTab
            #printDBG( 'Host listsItems data '+data )
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'WowzaPlayer', '}')
            for item in data:
                Url = self.cm.ph.getSearchGroups(item, '''sourceURL":['"]([^"^']+?)['"]''', 1, True)[0] 
                Title = self.cm.ph.getSearchGroups(item, '''title":['"]([^"^']+?)['"]''', 1, True)[0] 
                Url = urllib2.unquote(Url)
                Title = urllib2.unquote(Title)
                printDBG( 'Host Url: '+Url )
                printDBG( 'Host Title: '+Title )
                if 'm3u8' in Url:
                    if self.cm.isValidUrl(Url): 
                        tmp = getDirectM3U8Playlist(Url)
                        for item in tmp:
                            printDBG( 'Host listsItems valtab: '  +str(item) )
                            valTab.append(CDisplayListItem(Title+'   '+item['name'], item['url'],  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', item['url'], 0)], 0, 'https://www.asta24.pl/wp-content/themes/asta/img/asta24logo.png', None))
            return valTab

        if 'toruntv' == name:
            printDBG( 'Host listsItems begin name='+name )
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<source', '>')
            for item in data:
               phUrl = self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''', 1, True)[0] 
               if phUrl.startswith('//'): phUrl = 'http:' + phUrl
               printDBG( 'Host listsItems phUrl: '  +phUrl )
               phTitle = phUrl.split('.')[-1]
               #if 'mpd' in phUrl:
               #   valTab.append(CDisplayListItem(phTitle, phTitle,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', phUrl, 0)], 0, 'http://www.tvtorun.net/public/img/new/logo.png', None))
               if 'm3u8' in phUrl:
                  if self.cm.isValidUrl(phUrl): 
                     tmp = getDirectM3U8Playlist(phUrl, checkContent=True, sortWithMaxBitrate=999999999)
                     for item in tmp:
                        #printDBG( 'Host listsItems valtab: '  +str(item) )
                        valTab.append(CDisplayListItem(item['name'], item['url'],  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', item['url'], 0)], 0, 'http://www.tvtorun.net/public/img/new/logo.png', None))
            return valTab

        if 'makow' == name:
            printDBG( 'Host listsItems begin name='+name )
            Url = self.cm.ph.getSearchGroups(data, '''<iframe src=['"]([^"^']+?)['"]''')[0] 
            if Url.startswith('//'): Url = 'http:' + Url
            if Url:
                try: data = self.cm.getURLRequestData({'url': Url, 'use_host': False, 'use_cookie': False, 'use_post': False, 'return_data': True})
                except:
                    printDBG( 'Host listsItems ERROR' )
                    return valTab
                printDBG( 'Host data '+data )
                Url = self.cm.ph.getSearchGroups(data, '''<video id="video" src=['"]([^"^']+?)['"]''', 1, True)[0]
                if Url.startswith('//'): Url = 'http:' + Url
                if self.cm.isValidUrl(Url): 
                    tmp = getDirectM3U8Playlist(Url)
                    for item in tmp:
                        valTab.append(CDisplayListItem('Maków', 'Maków',  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', str(item['url']), 0)], 0, '', None))
            return valTab

        if 'magdalena' == name:
            printDBG( 'Host listsItems begin name='+name )
            link = re.search('<iframe.*?src="(.*?)"', data, re.S|re.I)
            if link: 
                COOKIEFILE = os_path.join(GetCookieDir(), 'info.cookie')
                self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
                self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
                sts, data = self.get_Page(link.group(1))
                if not sts: return valTab
                data = data.replace('&quot;','"').replace('\/','/')
                printDBG( 'Host listsItems data: '+data )
                videoUrl = self.cm.ph.getSearchGroups(data, '''src['"]:['"]([^"^']+?)['"]''')[0].replace('\/','/')
                if self.cm.isValidUrl(videoUrl): 
                    tmp = getDirectM3U8Playlist(videoUrl)
                    for item in tmp:
                        valTab.append(CDisplayListItem('Cieszyn  m3u8', str(item['name']),  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', str(item['url']), 0)], 0, 'https://upload.wikimedia.org/wikipedia/commons/thumb/1/1f/Cieszyn_sw_Marii_Magdaleny_od_pd_wsch.jpg/240px-Cieszyn_sw_Marii_Magdaleny_od_pd_wsch.jpg', None))
            return valTab 

        if 'wilno' == name:
            printDBG( 'Host listsItems begin name='+name )
            link = re.search('(https://www.youtube.*?/embed/.*?)"', data, re.S|re.I)
            if link:
                videoUrls = self.getLinksForVideo(link.group(1))
                if videoUrls:
                    for item in videoUrls:
                        Url = item['url']
                        Name = item['name']
                        printDBG( 'Host Url:  '+Url )
                        printDBG( 'Host name:  '+Name )
                        valTab.append(CDisplayListItem('Wilno  '+Name, 'Wilno  '+Name,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 0)], 0, 'http://zgromadzenie.faustyna.org/wp-content/uploads/2016/03/DSCF7213.jpg', None))
            return valTab 

        if 'edmonton' == name:
            printDBG( 'Host listsItems begin name='+name )
            videoUrls = self.getLinksForVideo(url)
            if videoUrls:
                for item in videoUrls:
                    Url = item['url']
                    Name = item['name']
                    printDBG( 'Host Url:  '+Url )
                    printDBG( 'Host name:  '+Name )
                    valTab.append(CDisplayListItem('Edmonton, Kanada  '+Name, 'Edmonton, Kanada  '+Name,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 0)], 0, 'https://upload.wikimedia.org/wikipedia/commons/thumb/c/c1/Holy_Rosary_Church_Edmonton_Alberta_Canada_01A.jpg/1200px-Holy_Rosary_Church_Edmonton_Alberta_Canada_01A.jpg', None))
            return valTab 

        if 'medju' == name:
            printDBG( 'Host listsItems begin name='+name )
            source = self.cm.ph.getSearchGroups(data, '''<iframe\ssrc=['"]([^"^']+?)['"]''')[0] 
            query_data = {'url': source, 'use_host': False, 'use_cookie': False, 'use_post': False, 'return_data': True}
            try:
                data = self.cm.getURLRequestData(query_data)
            except:
                printDBG( 'Host listsItems ERROR '+source )
                return valTab
            printDBG( 'Host listsItems data'+data )
            source_m3u8 = self.cm.ph.getSearchGroups(data, '''plugin_simple\s:\s['"]([^"^']+?)['"]''')[0] 
            if source_m3u8:
               if self.cm.isValidUrl(source_m3u8): 
                  tmp = getDirectM3U8Playlist(source_m3u8)
                  for item in tmp:
                     valTab.append(CDisplayListItem('TV Medziugorje   (m3u8)', 'TV Medziugorje   '+ str(item['name']),  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', str(item['url']), 0)], 0, 'http://www.churchmilitant.com//images/social_images/2015-06-10-niles-a.jpg', None))
            source_rtmp = self.cm.ph.getSearchGroups(data, '''src:['"]([^"^']+?)['"]''')[0] 
            if source_rtmp:
               playpath = source_rtmp.split('/')[-1]
               rtmp = source_rtmp.replace('/'+playpath,'')
               Url = '%s playpath=%s swfUrl=http://p.jwpcdn.com/6/12/jwplayer.flash.swf pageUrl=http://www.centrummedjugorje.pl/PL-H516/video.html live=1' % (rtmp, playpath)
               valTab.append(CDisplayListItem('TV Medziugorje   (rtmp)', 'TV Medziugorje',  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 0)], 0, 'http://www.churchmilitant.com//images/social_images/2015-06-10-niles-a.jpg', None))
            return valTab

        if 'trt' == name:
            printDBG( 'Host listsItems begin name='+name )
            menu = self.cm.ph.getDataBeetwenMarkers(data, 'dropdown-toggle', 'class="fa fa-music"', False)[1]
            printDBG( 'Host listsItems menu='+str(menu) )
            menu = self.cm.ph.getAllItemsBeetwenMarkers(menu, '<a', '</a>')
            printDBG( 'Host listsItems trt='+str(menu) )
            for item in menu:
                phUrl = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0] 
                phTitle = self.cm.ph.getSearchGroups(item, '''</i>([^"^']+?)<''', 1, True)[0] 
                #phTitle = phUrl.split('/')[-1]
                if phUrl.startswith('/'): phUrl = 'http://www.trt.pl' + phUrl
                phTitle = phTitle.replace('&nbsp;','').replace('<strong>','')
                printDBG( 'Host listsItems phUrl: '  +phUrl )
                printDBG( 'Host listsItems phTitle: '+phTitle )
                valTab.append(CDisplayListItem(phTitle,phTitle,CDisplayListItem.TYPE_CATEGORY, [phUrl],'trt-clips', '', None)) 
            menu = None
            return valTab
        if 'trt-clips' == name:
            printDBG( 'Host listsItems begin name='+name )
            next = self.cm.ph.getDataBeetwenMarkers(data, 'class="container"', '&raquo;', False)[1]
            next = self.cm.ph.getSearchGroups(next, '''href=['"]([^"^']+?)['"]''', 1, True)[0] 
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="tile-video">', 'class="info-block"')
            printDBG( 'Host listsItems trt='+str(data) )
            for item in data:
                phTitle = self.cm.ph.getSearchGroups(item, '"tile-title"([^>]+?)href="([^"]+?)"')[0] 
                phUrl = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0] 
                phImage = self.cm.ph.getSearchGroups(item, '''img src=['"]([^"^']+?)['"]''', 1, True)[0] 
                phTime = self.cm.ph.getSearchGroups(item, '''time">([^"^']+?)<''', 1, True)[0] 
                phTitle = phUrl.split('/')[-1]
                phTitle = phTitle.replace('quot-','').replace('-',' ')

                if phUrl.startswith('/'): phUrl = 'http://www.trt.pl' + phUrl
                printDBG( 'Host listsItems phUrl: '  +phUrl )
                printDBG( 'Host listsItems phTitle: '+phTitle )
                valTab.append(CDisplayListItem(phTitle, '['+phTime+'] '+phTitle,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', phUrl, 1)], 0, phImage, None))
            if next:
                if next.startswith('/'): next = 'http://www.trt.pl' + next
                next = next.replace('&amp;','&')
                valTab.append(CDisplayListItem('Next', 'Page: '+next.split('/')[-1], CDisplayListItem.TYPE_CATEGORY, [next], name, '', None))
            return valTab

        if 'worldcam' == name:
            printDBG( 'Host listsItems begin name='+name )
            menu = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="thumb b', '</p>')
            printDBG( 'Host listsItems: '+str(menu) )
            for item in menu:
                Url = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0] 
                Title = self.cm.ph.getSearchGroups(item, '''title=['"]([^"^']+?)['"]''', 1, True)[0].strip()
                Image = self.cm.ph.getSearchGroups(item, '''srcset=['"]([^"^']+?jpg)['"]''', 1, True)[0] 
                if Image.startswith('/'): Image = 'http://worldcam.live' + Image
                if Url.startswith('/'): Url = 'http://worldcam.live' + Url
                valTab.append(CDisplayListItem(Title,Title,CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 1)],'', Image, None)) 

            valTab.insert(0,CDisplayListItem('Żywiec', 'http://www.zywiec.pl/kamery,120.html', CDisplayListItem.TYPE_CATEGORY, ['http://www.zywiec.pl/kamery,120.html'], 'zywiec', 'http://www.zywiec.pl/images/logo.png', None)) 
            valTab.insert(0,CDisplayListItem("Poznań - MTP", "https://www.mtp.pl/pl/", CDisplayListItem.TYPE_VIDEO,[CUrlItem('', 'https://live.mtp.pl/cam1.ts/stream.m3u8', 0)], '', 'https://vignette.wikia.nocookie.net/poznan/images/c/c4/MTP.jpg/revision/latest/scale-to-width-down/300?cb=20120328193828&path-prefix=pl',None))
            #valTab.insert(0,CDisplayListItem("Olesno - ulica Pieloka", "Olesno - ulica Pieloka", CDisplayListItem.TYPE_VIDEO,[CUrlItem('', 'http://www.olesno.pl/kamera-na-ulicy-pieloka.html', 1)], '', 'http://images.polskaniezwykla.pl/medium/311261.jpg',None))
            #valTab.insert(0,CDisplayListItem("Olesno - Rynek", "Olesno - Rynek", CDisplayListItem.TYPE_VIDEO,[CUrlItem('', 'http://www.olesno.pl/kamera-oleski-rynek.html', 1)], '', 'https://upload.wikimedia.org/wikipedia/commons/thumb/c/cd/Ratusz_w_Ole%C5%9Bnie.JPG/1024px-Ratusz_w_Ole%C5%9Bnie.JPG',None))
            valTab.insert(0,CDisplayListItem("Cieszyn - Rynek", "http://www.cieszyn.pl", CDisplayListItem.TYPE_VIDEO,[CUrlItem('', 'http://www.cieszyn.pl/_kamera/', 1)], '', 'http://www.cieszyn.pl/files/www.cieszyn.pl%20Renata%20Karpinska%2085.jpg',None))

            menu = None
            return valTab

        if 'Heroldsbach' == name:
            printDBG( 'Host listsItems begin name='+name )
            source_m3u8 = self.cm.ph.getSearchGroups(data, '''file['"]: ['"]([^"^']+?m3u8)['"]''')[0] 
            if source_m3u8:
               if self.cm.isValidUrl(source_m3u8): 
                  tmp = getDirectM3U8Playlist(source_m3u8)
                  for item in tmp:
                     valTab.append(CDisplayListItem('Heroldsbach   (m3u8)', 'Heroldsbach  '+str(item['name']),  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', str(item['url']), 0)], 0, '', None))
            source_rtmp = self.cm.ph.getSearchGroups(data, '''file['"]: ['"](rtmp[^"^']+?)['"]''')[0] 
            if source_rtmp:
               valTab.append(CDisplayListItem('Heroldsbach   (rtmp)', 'Heroldsbach',  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', source_rtmp, 0)], 0, '', None))
            return valTab

        if 'domradio' == name:
            printDBG( 'Host listsItems begin name='+name )
            videoUrls = self.getLinksForVideo(url)
            if videoUrls:
                for item in videoUrls:
                    Url = item['url']
                    Name = item['name']
                    printDBG( 'Host name:  '+Name )
                    valTab.append(CDisplayListItem('Domradio.de    '+Name, 'Domradio.de    '+Name,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 0)], 0, 'https://www.domradio.de/sites/all/themes/domradio/images/logo.png', None))
            else:
                videoUrls = self.getLinksForVideo('https://www.youtube.com/watch?v=G-tGrEclhZY')
                if videoUrls:
                    for item in videoUrls:
                        Url = item['url']
                        Name = item['name']
                        printDBG( 'Host name:  '+Name )
                        valTab.append(CDisplayListItem('OFFLINE - Domradio.de    '+Name, 'Domradio.de    '+Name,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 0)], 0, 'https://www.domradio.de/sites/all/themes/domradio/images/logo.png', None))
            return valTab 

        if 'kalwaria' == name:
            printDBG( 'Host listsItems begin name='+name )
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '"item":', '"runs":')
            for item in data:
                Title = self.cm.ph.getSearchGroups(item, '''simpleText":['"]([^"^']+?)['"]''', 1, True)[0] 
                Url = self.cm.ph.getSearchGroups(item, '''"videoId":['"]([^"^']+?)['"]''', 1, True)[0] 
                Url = 'https://www.youtube.com/watch?v='+Url
                videoUrls = self.getLinksForVideo(Url)
                if videoUrls:
                    for item in videoUrls:
                        Url = item['url']
                        Name = item['name']
                        printDBG( 'Host name:  '+Name )
                        valTab.append(CDisplayListItem(Title+'   '+Name, Title+'   '+Name,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 0)], 0, 'http://www.powiat.wadowice.pl/fotki/g2065d.jpg', None))
            return valTab 

        if 'radzionkow' == name:
            printDBG( 'Host listsItems begin name='+name )
            videoUrls = self.getLinksForVideo(url)
            if videoUrls:
                for item in videoUrls:
                    Url = item['url']
                    Name = item['name']
                    printDBG( 'Host Url:  '+Url )
                    printDBG( 'Host name:  '+Name )
                    valTab.append(CDisplayListItem('Radzionków  Parafis św. Wojciecha  '+Name, 'Radzionków  Parafis św. Wojciecha  '+Name,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 0)], 0, 'https://upload.wikimedia.org/wikipedia/commons/c/cc/Parafia_%C5%9Bw._Wojciecha_w_Radzionkowie.JPG', None))
            return valTab 

        if 'piwniczna' == name:
            printDBG( 'Host listsItems begin name='+name )
            videoUrls = self.getLinksForVideo('https://www.youtube.com/channel/UCLdNRt-R-qnTTd6zSWXHZVQ/live')
            if videoUrls:
                for item in videoUrls:
                    Url = item['url']
                    Name = item['name']
                    printDBG( 'Host Url:  '+Url )
                    printDBG( 'Host name:  '+Name )
                    valTab.append(CDisplayListItem('Piwniczna - Zdrój  '+Name, 'Piwniczna - Zdrój  '+Name,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 0)], 0, 'http://www.parafia.piwniczna.com/images/panel_boczny.jpg', None))
            return valTab 

        if 'opoka' == name:
            printDBG( 'Host listsItems begin name='+name )
            if 'sources:' in data:
                data2 = self.cm.ph.getDataBeetwenMarkers(data, 'sources:', ']', False)[1]
                videoUrl = self.cm.ph.getSearchGroups(data2, '''src[^'"]*?['"]([^'"]+?)['"]''')[0]
                videoUrl2 = self.cm.ph.getSearchGroups(data2, '''src[^'"]*?['"](rtmp[^'"]+?)['"]''')[0]
                data2 = None
                printDBG( 'Host videoUrl= '+videoUrl )
                printDBG( 'Host videoUrl2= '+videoUrl2 )
                if videoUrl:
                    if videoUrl.startswith('//'): videoUrl = 'http:'+videoUrl
                    if self.cm.isValidUrl(videoUrl): 
                        tmp = getDirectM3U8Playlist(videoUrl)
                        for item in tmp:
                            valTab.append(CDisplayListItem('Opoka TV   '+str(item['name']), 'Opoka TV',  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', str(item['url']), 0)], 0, 'http://itvmedia.pl/uploaded/loga_itv_ok/opoka%20TV.png', None))
                if videoUrl2:
                    valTab.append(CDisplayListItem('Opoka TV   (rtmp)', 'Opoka TV',  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', videoUrl2, 0)], 0, 'http://itvmedia.pl/uploaded/loga_itv_ok/opoka%20TV.png', None))
            return valTab

        if 'master' == name:
            printDBG( 'Host listsItems begin name='+name )
            link = re.search('(https://www.youtube.com/embed/.*?)"', data, re.S|re.I)
            if link:
                videoUrls = self.getLinksForVideo(link.group(1))
                if videoUrls:
                    for item in videoUrls:
                        Url = item['url']
                        Name = item['name']
                        printDBG( 'Host Url:  '+Url )
                        printDBG( 'Host name:  '+Name )
                        valTab.append(CDisplayListItem('TV Master  '+Name, 'TV Master  '+Name,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 0)], 0, 'http://www.tv.master.pl/grafika/TV_Master2.png', None))
            return valTab 

        if 'dami' == name:
            printDBG( 'Host listsItems begin name='+name )
            videoUrls = self.getLinksForVideo(url)
            if videoUrls:
                for item in videoUrls:
                    Url = item['url']
                    Name = item['name']
                    printDBG( 'Host name:  '+Name )
                    valTab.append(CDisplayListItem('Dami 24  '+Name, 'Dami 24  '+Name,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 0)], 0, 'http://dami24.pl/images/headers/logo.png', None))
            return valTab

        if 'zary' == name:
            printDBG( 'Host listsItems begin name='+name )
            videoUrls = self.getLinksForVideo(url)
            if videoUrls:
                for item in videoUrls:
                    Url = item['url']
                    Name = item['name']
                    printDBG( 'Host name:  '+Name )
                    valTab.append(CDisplayListItem('Żary TV  '+Name, 'Żary TV   '+Name,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 0)], 0, 'http://www.telewizjazary.pl/assets/wysiwig/images/logo/TVR_logo.png', None))
            return valTab

        if 'toyago' == name:
            printDBG( 'Host listsItems begin name='+name )
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<ul class="active">', '</a>')
            for item in data:
                Title = self.cm.ph.getSearchGroups(item, '''">([^"^']+?)</a>''', 1, True)[0] 
                Url = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0] 
                Url = 'https://go.toya.net.pl'+Url
                Title = Title.replace('&nbsp;',' ').replace('</span>',' ')
                printDBG( 'Host listsItems Title:'+Title )
                if Title <> 'Kamery':
                    valTab.append(CDisplayListItem(Title, Title, CDisplayListItem.TYPE_CATEGORY, [Url], 'toyago-clips', '', None)) 
            return valTab
        if 'toyago-clips' == name:
            printDBG( 'Host listsItems begin name='+name )
            query_data = {'url': url, 'use_host': False, 'use_cookie': False, 'use_post': False, 'return_data': True}
            try:
                data = self.cm.getURLRequestData(query_data)
            except:
                printDBG( 'Host listsItems ERROR' )
                return valTab
            #printDBG( 'Host listsItems data toyago: '+data )
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="item isotope-item --locked search-item"', '<time datetime')
            #printDBG( 'Host listsItems data toyago2: '+str(data) )

            for item in data:
                Title = self.cm.ph.getSearchGroups(item, '''alt=['"]([^"^']+?)['"]''', 1, True)[0] 
                Image = self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''', 1, True)[0] 
                Url = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0] 
                Url = 'https://go.toya.net.pl'+Url
                valTab.append(CDisplayListItem(Title, Title,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 1)], 0, Image, None))
            return valTab

        if 'wlkp24' == name:
            printDBG( 'Host listsItems begin name='+name )
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="vc_btn3-container', '</div>')
            for item in data:
                Title = self.cm.ph.getSearchGroups(item, '''title=['"]([^"^']+?)['"]''', 1, True)[0] 
                Url = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0] 
                valTab.append(CDisplayListItem(Title, Title,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 1)], 0, '', None))
            return valTab

        if 'faustyna' == name:
            printDBG( 'Host listsItems begin name='+name )
            Url = self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0]
            if Url:
               printDBG( 'Host faustyna Url '+Url )
               if Url[:2] == "//": Url = "https:" + Url
               query_data = {'url': Url, 'use_host': False, 'use_cookie': False, 'use_post': False, 'return_data': True}
               try:
                  data = self.cm.getURLRequestData(query_data)
               except:
                   printDBG( 'Host listsItems ERROR: '+Url )
                   proxy = 'https://proksiak.pl/show.php?u={0}'.format(urllib.quote(Url, ''))
                   try:
                      query_data = {'url': proxy, 'header': {'Referer': proxy, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'User-Agent': 'Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.9.2.18) Gecko/20110621 Mandriva Linux/1.9.2.18-0.1mdv2010.2 (2010.2) Firefox/3.6.18'}, 'return_data': True}
                      data = self.cm.getURLRequestData(query_data)
                      #printDBG( 'Host faustyna data'+data )
                   except: 
                      return valTab
               printDBG( 'Host faustyna data '+data )
               live=''
               link = re.findall('"m3u8_url":"(.*?)"', data, re.S|re.I)
               if link: 
                  for (Url) in link:
                     if 'broadcasts' in Url: 
                        if self.cm.isValidUrl(Url): 
                            tmp = getDirectM3U8Playlist(Url)
                            printDBG( 'Host faustyna tmp'+str(tmp) )
                            for item in tmp:
                               videoUrl = item['url']
                               #videoUrl = urlparser.decorateUrl(videoUrl, {'Referer': url})  
                               valTab.append(CDisplayListItem(str(item['name']), str(item['name']),  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', videoUrl, 0)], 0, '', None))
            return valTab

        if 'milosierdzie' == name:
            printDBG( 'Host listsItems begin name='+name )
            m3u8_url = self.cm.ph.getSearchGroups(data, '''src=['"](https://perfectfilm[^"^']+?\.html)['"]''', 1, True)[0]
            printDBG( 'Host m3u8_url: '+m3u8_url )
            self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': False, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            self.defaultParams['header']['Referer']=url
            sts, data = self.get_Page(m3u8_url)
            if not sts: return valTab
            printDBG( 'Host milosierdzie: '+data )
            m3u8_url = self.cm.ph.getSearchGroups(data, '''src=['"]([^"^']+?\.m3u8)['"]''', 1, True)[0]
            if self.cm.isValidUrl(m3u8_url): 
               tmp = getDirectM3U8Playlist(m3u8_url)
               printDBG( 'Host tmp: '+str(tmp) )
               for item in tmp:
                  valTab.append(CDisplayListItem('m3u8 '+str(item['name']), str(item['name']),  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', str(item['url']), 0)], 0, '', None))
            else:
               Url = self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0]
               query_data = {'url': Url, 'use_host': False, 'use_cookie': False, 'use_post': False, 'return_data': True}
               try:
                  data = self.cm.getURLRequestData(query_data)
               except:
                  printDBG( 'Host listsItems ERROR: '+Url )
               printDBG( 'Host data '+data )
               data = self.cm.ph.getDataBeetwenMarkers(data, 'playlist', ']', False)[1]
               playpath = self.cm.ph.getSearchGroups(data, '''url:\s*['"]([^"^']+?)['"]''', 1, True)[0]
               netConnectionUrl = self.cm.ph.getSearchGroups(data, '''netConnectionUrl:\s*['"]([^"^']+?)['"]''', 1, True)[0]
               videoUrl = netConnectionUrl +' playpath=' + playpath +' swfUrl=https://vod.perfectfilm.tv/flowplayer/flowplayer.commercial-3.2.11.swf live=1 pageUrl=' + Url+ ' flashVer=WIN 28,0,0,126 '

               if Url:
                  valTab.append(CDisplayListItem('rtmp', videoUrl,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', videoUrl, 0)], 0, '', None))
            return valTab

        if 'religia' == name:
            printDBG( 'Host listsItems begin name='+name )
            link = self.cm.ph.getSearchGroups(data, '''iframe\ssrc=['"]([^"^']+?)['"]''')[0] 
            try: data = self.cm.getURLRequestData({'url': link, 'use_host': False, 'use_cookie': False, 'use_post': False, 'return_data': True})
            except:
                printDBG( 'Host listsItems ERROR' )
                return ''
            printDBG( 'Host listsItems data2'+data )
            link = re.search('"items":(.*?),"messages":', data, re.S|re.I)
            x = 0
            if link: 
                baza = link.group(1)
                #printDBG( 'Host listsItems baza: '+baza )
                data = self.cm.ph.getAllItemsBeetwenMarkers(baza, '{', '}')
                for item in data:
                    phTitle = self.cm.ph.getSearchGroups(item, '''"name":['"]([^"^']+?)['"]''', 1, True)[0].encode("utf-8")  
                    phUrl = self.cm.ph.getSearchGroups(item, '''"downloadUrl":['"]([^"^']+?)['"]''', 1, True)[0].replace('\/','/') 
                    desc = self.cm.ph.getSearchGroups(item, '''"description":['"]([^"^']+?)['"]''', 1, True)[0] 
                    Time = self.cm.ph.getSearchGroups(item, '''"duration":([^"^']+?),''', 1, True)[0]
                    try:
                        Time = divmod(int(Time), 60)
                    except: pass
                    Time = str(Time).replace(',',':')
                    id = self.cm.ph.getSearchGroups(item, ''',"id":['"]([^"^']+?)['"]''', 1, True)[0] 
                    api = urllib.unquote('http://mediaserwer3.christusvincit-tv.pl/api_v3/index.php?service=multirequest&apiVersion=3.1&expiry=86400&clientTag=kwidget%3Av2.41&format=1&ignoreNull=1&action=null&1:service=session&1:action=startWidgetSession&1:widgetId=_100&2:ks=%7B1%3Aresult%3Aks%7D&2:service=baseentry&2:action=list&2:filter:objectType=KalturaBaseEntryFilter&2:filter:redirectFromEntryId=idididid&3:ks=%7B1%3Aresult%3Aks%7D&3:contextDataParams:referrer=http%3A%2F%2Fchristusvincit-tv.pl&3:contextDataParams:objectType=KalturaEntryContextDataParams&3:contextDataParams:flavorTags=all&3:contextDataParams:streamerType=auto&3:service=baseentry&3:entryId=%7B2%3Aresult%3Aobjects%3A0%3Aid%7D&3:action=getContextData&4:ks=%7B1%3Aresult%3Aks%7D&4:service=metadata_metadata&4:action=list&4:version=-1&4:filter:metadataObjectTypeEqual=1&4:filter:orderBy=%2BcreatedAt&4:filter:objectIdEqual=%7B2%3Aresult%3Aobjects%3A0%3Aid%7D&4:pager:pageSize=1&5:ks=%7B1%3Aresult%3Aks%7D&5:service=cuepoint_cuepoint&5:action=list&5:filter:objectType=KalturaCuePointFilter&5:filter:orderBy=%2BstartTime&5:filter:statusEqual=1&5:filter:entryIdEqual=%7B2%3Aresult%3Aobjects%3A0%3Aid%7D&kalsig=d575e4c088a57621d47fe2f48db13675')
                    api = api.replace('idididid', id)
                    try: data = self.cm.getURLRequestData({'url': api, 'use_host': False, 'use_cookie': False, 'use_post': False, 'return_data': True})
                    except:
                        printDBG( 'Host listsItems ERROR' )
                        return valTab
                    #printDBG( 'Host listsItems data3'+data )
                    id = self.cm.ph.getSearchGroups(data, '''"videoCodecId":"avc1","status":2,"id":['"]([^"^']+?)['"]''', 1, True)[0] 
                    phUrl = phUrl.replace('raw/entry_id','serveFlavor/entryId').replace('version/0','v/2/flavorId/')
                    phUrl = phUrl+id+'/fileName/'+decodeHtml(phTitle).replace(' ','_')+'.mp4/forceproxy/true/name/a.mp4'
                    if phTitle <>'':
                        printDBG( 'Host listsItems downloadUrl: '  +phUrl )
                        printDBG( 'Host listsItems name: '+phTitle ) 
                        printDBG( 'Host listsItems id: '+id ) 
                        x += 1
                        if x > config.plugins.iptvplayer.natanek.value : return valTab
                        valTab.append(CDisplayListItem(decodeNat2(phTitle), Time+'   '+decodeNat2(phTitle)+'   '+decodeNat2(desc),  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', phUrl, 0)], 0, '', None))
            return valTab

        if 'religia2' == name:
            printDBG( 'Host listsItems begin name='+name )
            link = re.compile('iframe\ssrc="(.+?)"', re.DOTALL).findall(data)
            if link:
                link = link[-1]
            else:
                return valTab
            try: data = self.cm.getURLRequestData({'url': link, 'use_host': False, 'use_cookie': False, 'use_post': False, 'return_data': True})
            except:
                printDBG( 'Host listsItems ERROR' )
                return ''
            #printDBG( 'Host listsItems data2'+data )
            link = re.search('"items":(.*?),"messages":', data, re.S|re.I)
            x = 0
            if link: 
                baza = link.group(1)
                #printDBG( 'Host listsItems baza: '+baza )
                data = self.cm.ph.getAllItemsBeetwenMarkers(baza, '{', '}')
                for item in data:
                    phTitle = self.cm.ph.getSearchGroups(item, '''"name":['"]([^"^']+?)['"]''', 1, True)[0].encode("utf-8")  
                    phUrl = self.cm.ph.getSearchGroups(item, '''"downloadUrl":['"]([^"^']+?)['"]''', 1, True)[0].replace('\/','/') 
                    desc = self.cm.ph.getSearchGroups(item, '''"description":['"]([^"^']+?)['"]''', 1, True)[0] 
                    Time = self.cm.ph.getSearchGroups(item, '''"duration":([^"^']+?),''', 1, True)[0]
                    try:
                        Time = divmod(int(Time), 60)
                    except: pass
                    Time = str(Time).replace(',',':')
                    id = self.cm.ph.getSearchGroups(item, ''',"id":['"]([^"^']+?)['"]''', 1, True)[0] 
                    api = urllib.unquote('http://mediaserwer3.christusvincit-tv.pl/api_v3/index.php?service=multirequest&apiVersion=3.1&expiry=86400&clientTag=kwidget%3Av2.41&format=1&ignoreNull=1&action=null&1:service=session&1:action=startWidgetSession&1:widgetId=_100&2:ks=%7B1%3Aresult%3Aks%7D&2:service=baseentry&2:action=list&2:filter:objectType=KalturaBaseEntryFilter&2:filter:redirectFromEntryId=idididid&3:ks=%7B1%3Aresult%3Aks%7D&3:contextDataParams:referrer=http%3A%2F%2Fchristusvincit-tv.pl&3:contextDataParams:objectType=KalturaEntryContextDataParams&3:contextDataParams:flavorTags=all&3:contextDataParams:streamerType=auto&3:service=baseentry&3:entryId=%7B2%3Aresult%3Aobjects%3A0%3Aid%7D&3:action=getContextData&4:ks=%7B1%3Aresult%3Aks%7D&4:service=metadata_metadata&4:action=list&4:version=-1&4:filter:metadataObjectTypeEqual=1&4:filter:orderBy=%2BcreatedAt&4:filter:objectIdEqual=%7B2%3Aresult%3Aobjects%3A0%3Aid%7D&4:pager:pageSize=1&5:ks=%7B1%3Aresult%3Aks%7D&5:service=cuepoint_cuepoint&5:action=list&5:filter:objectType=KalturaCuePointFilter&5:filter:orderBy=%2BstartTime&5:filter:statusEqual=1&5:filter:entryIdEqual=%7B2%3Aresult%3Aobjects%3A0%3Aid%7D&kalsig=d575e4c088a57621d47fe2f48db13675')
                    api = api.replace('idididid', id)
                    try: data = self.cm.getURLRequestData({'url': api, 'use_host': False, 'use_cookie': False, 'use_post': False, 'return_data': True})
                    except:
                        printDBG( 'Host listsItems ERROR' )
                        return valTab
                    #printDBG( 'Host listsItems data3'+data )
                    id = self.cm.ph.getSearchGroups(data, '''"videoCodecId":"avc1","status":2,"id":['"]([^"^']+?)['"]''', 1, True)[0] 
                    phUrl = phUrl.replace('raw/entry_id','serveFlavor/entryId').replace('version/0','v/2/flavorId/')
                    phUrl = phUrl+id+'/fileName/'+decodeHtml(phTitle).replace(' ','_')+'.mp4/forceproxy/true/name/a.mp4'
                    if phTitle <>'':
                        printDBG( 'Host listsItems downloadUrl: '  +phUrl )
                        printDBG( 'Host listsItems name: '+phTitle ) 
                        printDBG( 'Host listsItems id: '+id ) 
                        x += 1
                        if x > config.plugins.iptvplayer.natanek.value : return valTab
                        valTab.append(CDisplayListItem(decodeNat2(phTitle), Time+'   '+decodeNat2(phTitle)+'   '+decodeNat2(desc),  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', phUrl, 0)], 0, '', None))
            return valTab

        if 'podkarpacie' == name:
            printDBG( 'Host listsItems begin name='+name )
            image = 'http://podkarpacielive.tv/wp-content/themes/podkarpackielivetv/images/logo.png'
            valTab.insert(0,CDisplayListItem("--- Inne sporty ---", "Inne sporty", CDisplayListItem.TYPE_CATEGORY,['http://podkarpacielive.tv/kategoria/inne-sporty/'], 'podkarpacie-kategorie', image,None))
            valTab.insert(0,CDisplayListItem("--- Różności ---", "Różności", CDisplayListItem.TYPE_CATEGORY,['http://podkarpacielive.tv/kategoria/roznosci/'], 'podkarpacie-kategorie', image,None))
            valTab.insert(0,CDisplayListItem("--- Wywiady/komentarze ---", "Wywiady/komentarze", CDisplayListItem.TYPE_CATEGORY,['http://podkarpacielive.tv/kategoria/wywiady-komentarze/'], 'podkarpacie-kategorie', image,None))
            valTab.insert(0,CDisplayListItem("--- Kraj/Świat ---", "Kraj/Świat", CDisplayListItem.TYPE_CATEGORY,['http://podkarpacielive.tv/kategoria/kraj-swiat/'], 'podkarpacie-kategorie', image,None))
            valTab.insert(0,CDisplayListItem("--- Kibice ---", "Kibice", CDisplayListItem.TYPE_CATEGORY,['http://podkarpacielive.tv/kategoria/kibice/'], 'podkarpacie-kategorie', image,None))
            valTab.insert(0,CDisplayListItem("--- Transmisje online ---", "Transmisje online", CDisplayListItem.TYPE_CATEGORY,['http://podkarpacielive.tv/kategoria/transmisje-online/'], 'podkarpacie-kategorie', image,None))
            valTab.insert(0,CDisplayListItem("--- Bramki ---", "Bramki", CDisplayListItem.TYPE_CATEGORY,['http://podkarpacielive.tv/kategoria/bramki/'], 'podkarpacie-kategorie', image,None))
            valTab.insert(0,CDisplayListItem("--- Skróty wideo ---", "Skróty wideo", CDisplayListItem.TYPE_CATEGORY,['http://podkarpacielive.tv/kategoria/skroty-wideo/'], 'podkarpacie-kategorie', image,None))
            return valTab
        if 'podkarpacie-kategorie' == name:
            printDBG( 'Host listsItems begin name='+name )
            next = self.cm.ph.getSearchGroups(data, '''next page-numbers" href=['"]([^"^']+?)['"]''', 1, True)[0]
            data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="videos">', 'footer', False)[1]
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<img', '</article>')
            for item in data:
                Title = self.cm.ph.getSearchGroups(item, '''<h3>([^"^']+?)</h3>''', 1, True)[0] 
                Url = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0] 
                Time = self.cm.ph.getSearchGroups(item, '''<time>([^"^']+?)</time>''', 1, True)[0] 
                Image = self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''', 1, True)[0] 
                Title = Title.replace('&#8211;','-')
                printDBG( 'Host listsItems Title: '  +Title )
                printDBG( 'Host listsItems Url: '  +Url )
                valTab.append(CDisplayListItem(Title, '['+Time+'] '+Title, CDisplayListItem.TYPE_CATEGORY, [Url], 'podkarpacie-clips', Image, None)) 
            if next:
               if next.startswith('/'): next = 'http://podkarpacielive.tv' + next
               next = next.replace('&amp;','&')
               valTab.append(CDisplayListItem('Next', 'Page: '+next, CDisplayListItem.TYPE_CATEGORY, [next], name, '', None))
            printDBG( 'Host listsItems end' )
            return valTab
        if 'podkarpacie-clips' == name:
            printDBG( 'Host listsItems begin name='+name )
            query_data = {'url': url, 'use_host': False, 'use_cookie': False, 'use_post': False, 'return_data': True}
            try:
                data = self.cm.getURLRequestData(query_data)
            except:
                printDBG( 'Host listsItems ERROR' )
                return valTab
            #printDBG( 'Host listsItems data podkarpacie: '+data )
            Url = self.cm.ph.getSearchGroups(data, '''<iframe src=['"]([^"^']+?)['"]''', 1, True)[0] 
            if Url.startswith('//'): Url = 'https:' + Url 
            videoUrls = self.getLinksForVideo(Url)
            if videoUrls:
                for item in videoUrls:
                    Url = item['url']
                    Name = item['name']
                    printDBG( 'Host Url:  '+Url )
                    printDBG( 'Host name:  '+Name )
                    valTab.append(CDisplayListItem('Transmisja  '+Name, 'Transmisja  '+Name,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 0)], 0, '', None))
            return valTab

        if 'lechtv' == name:
            printDBG( 'Host listsItems begin name='+name )
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="program_lechtv_time">', '</div>')
            programTV = ''
            for item in data:
                time = self.cm.ph.getSearchGroups(item, '''"program_lechtv_time">([^>]+?)<''', 1, True)[0]
                name = self.cm.ph.getSearchGroups(item, '''program_lechtv_name.*?>([^>]+?)<''', 1, True)[0]
                desc = self.cm.ph.getSearchGroups(item, '''program_lechtv_desc.*?>([^>]+?)<''', 1, True)[0]
                programTV = programTV + time+'   '+name+'   '+desc+'\n'
            printDBG( 'Host listsItems programTV: '  +programTV)
            m3u8_url = 'https://ec05.waw2.cache.orange.pl/jupiter/o1-cl3/live/wtk-b-lechtv/live.m3u8'
            if self.cm.isValidUrl(m3u8_url): 
               tmp = getDirectM3U8Playlist(m3u8_url)
               for item in tmp:
                  #printDBG( 'Host listsItems valtab: '  +str(item) )
                  valTab.append(CDisplayListItem(item['name'], programTV,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', item['url'], 0)], 0, 'http://lech.tv/graphics_new/all/lechtv_logo_top.png', None))
            return valTab

        if 'wtk' == name:
            printDBG( 'Host listsItems begin name='+name )
            valTab.append(CDisplayListItem('--- WTK LIVE ---', 'https://wtkplay.pl', CDisplayListItem.TYPE_CATEGORY, ['https://ec05.waw2.cache.orange.pl/jupiter/o1-cl3/live/wtk-b-wtktv/live.m3u8'], 'wtklive', 'https://wtkplay.pl/graphic/header/wtkplay_logo.png?theme=normal', None)) 
            valTab.append(CDisplayListItem('--- Wiadomości ---', 'https://wtkplay.pl', CDisplayListItem.TYPE_CATEGORY, ['https://wtkplay.pl/category-1-wiadomosci?source=linkbar'], 'wtk_clip', 'https://wtkplay.pl/graphic/header/wtkplay_logo.png?theme=normal', None)) 
            valTab.append(CDisplayListItem('--- Puls dnia ---', 'https://wtkplay.pl', CDisplayListItem.TYPE_CATEGORY, ['https://wtkplay.pl/magazine-3-puls_dnia?source=linkbar'], 'wtk_clip', 'https://wtkplay.pl/graphic/header/wtkplay_logo.png?theme=normal', None)) 
            valTab.append(CDisplayListItem('--- Otwarta antena ---', 'https://wtkplay.pl', CDisplayListItem.TYPE_CATEGORY, ['https://wtkplay.pl/magazine-36-otwarta_antena?source=linkbar'], 'wtk_clip', 'https://wtkplay.pl/graphic/header/wtkplay_logo.png?theme=normal', None)) 
            valTab.append(CDisplayListItem('--- Poranek WTK ---', 'https://wtkplay.pl', CDisplayListItem.TYPE_CATEGORY, ['https://wtkplay.pl/category-22-poranek_wtk?source=linkbar'], 'wtk_clip', 'https://wtkplay.pl/graphic/header/wtkplay_logo.png?theme=normal', None)) 
            valTab.append(CDisplayListItem('--- Sport ---', 'https://wtkplay.pl', CDisplayListItem.TYPE_CATEGORY, ['https://wtkplay.pl/category-4-sport?source=linkbar'], 'wtk_clip', 'https://wtkplay.pl/graphic/header/wtkplay_logo.png?theme=normal', None)) 
            valTab.append(CDisplayListItem('--- Top 24h ---', 'https://wtkplay.pl', CDisplayListItem.TYPE_CATEGORY, ['https://wtkplay.pl/topday?source=linkbar'], 'wtk_clip', 'https://wtkplay.pl/graphic/header/wtkplay_logo.png?theme=normal', None)) 
            valTab.append(CDisplayListItem('--- Top tygodnia ---', 'https://wtkplay.pl', CDisplayListItem.TYPE_CATEGORY, ['https://wtkplay.pl/topweek?source=linkbar'], 'wtk_clip', 'https://wtkplay.pl/graphic/header/wtkplay_logo.png?theme=normal', None)) 
            valTab.append(CDisplayListItem('--- WTK Alarm ---', 'https://wtkplay.pl', CDisplayListItem.TYPE_CATEGORY, ['https://wtkplay.pl/wtkalarm?source=linkbar'], 'wtk_clip', 'https://wtkplay.pl/graphic/header/wtkplay_logo.png?theme=normal', None)) 
            valTab.append(CDisplayListItem('--- Magazyn na żywo ---', 'https://wtkplay.pl', CDisplayListItem.TYPE_CATEGORY, ['https://wtkplay.pl/magazine-229-na_zywo?source=linkbar'], 'wtk_clip', 'https://wtkplay.pl/graphic/header/wtkplay_logo.png?theme=normal', None)) 
            return valTab
        if 'wtk_clip' == name:
            printDBG( 'Host listsItems begin name='+name )
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="video_medium_content', '</div>')
            for item in data:
                Url = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0]
                Title = self.cm.ph.getSearchGroups(item, '''alt=['"]([^"^']+?)['"]''', 1, True)[0]
                Image = self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''', 1, True)[0]
                Url = 'https://wtkplay.pl/' + Url 
                Image = 'https://wtkplay.pl/' + Image 
                valTab.append(CDisplayListItem(decodeHtml(Title), decodeHtml(Title),  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 1)], 0, Image, None))
            return valTab
        if 'wtklive' == name:
            printDBG( 'Host listsItems begin name='+name )
            if self.cm.isValidUrl(url): 
               tmp = getDirectM3U8Playlist(url)
               for item in tmp:
                  #printDBG( 'Host listsItems valtab: '  +str(item) )
                  valTab.append(CDisplayListItem('WTK LIVE   '+item['bitrate'], 'WTK LIVE   '+item['name'],  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', item['url'], 0)], 0, '', None))
            return valTab

        if 'euronewsde' == name:
            printDBG( 'Host listsItems begin name='+name )
            data = '['+data+']'
            try:
                result = simplejson.loads(data)
                if result:
                    for item in result:
                        url = str(item["url"])  
            except:
                printDBG( 'Host listsItems ERROR JSON' )
                return valTab
            query_data = {'url': url, 'use_host': False, 'use_cookie': False, 'use_post': False, 'return_data': True}
            try:
                data = self.cm.getURLRequestData(query_data)
            except:
                printDBG( 'Host listsItems ERROR' )
                return valTab
            #printDBG( 'Host listsItems data : '+data )
            data = '['+data+']'
            try:
                result = simplejson.loads(data)
                if result:
                    for item in result:
                        primary = str(item["primary"])  
                        #backup = str(item["backup"])  
            except:
                printDBG( 'Host listsItems ERROR JSON' )
                return valTab
            m3u8_url = primary
            if m3u8_url.startswith('//'): m3u8_url = 'http:' + m3u8_url
            if self.cm.isValidUrl(m3u8_url): 
               tmp = getDirectM3U8Playlist(m3u8_url)
               for item in tmp:
                  #printDBG( 'Host listsItems valtab: '  +str(item) )
                  valTab.append(CDisplayListItem('Euronews DE  '+item['name'], 'Euronews DE',  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', item['url'], 0)], 0, 'http://www.euronews.com/images/fallback.jpg', None))
            return valTab

        if 'kukaj' == name:
            printDBG( 'Host listsItems begin name='+name )
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="card', '</div>')
            for item in data:
                Title = self.cm.ph.getSearchGroups(item, '''title=['"]([^"^']+?)['"]''', 1, True)[0] 
                Url = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''', 1, True)[0] 
                Image = self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''', 1, True)[0] 
                if not '/projekt/' in Url: continue
                if '19-media' in Url: continue
                if Url.startswith('/'): Url = 'http://www.kukaj.sk' + Url
                if Url.startswith('//'): Url = 'http:' + Url
                if Image.startswith('//'): Image = 'http:' + Image
                valTab.append(CDisplayListItem(Title, Title,  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 1)], 0, Image, None))
            return valTab


        #http://www.peregrinus.pl/pl/podglad-gniazd-na-zywo
        if 'ptaki' == name:
            printDBG( 'Host listsItems begin name='+name )

            #valTab.append(CDisplayListItem('Bociany z Przygodzic CAM1', 'Bociany z Przygodzic CAM1',  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'http://www.bociany.przygodzice.pl/', 1)], 0, 'http://dinoanimals.pl/wp-content/uploads/2013/05/Bocian-DinoAnimals.pl-5.jpg', None))
            valTab.append(CDisplayListItem('Bociany z Przygodzic CAM2', 'Bociany z Przygodzic CAM2',  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'http://www.bociany.przygodzice.pl/indexcam2.html', 1)], 0, 'http://dinoanimals.pl/wp-content/uploads/2013/05/Bocian-DinoAnimals.pl-5.jpg', None))
            valTab.append(CDisplayListItem('Sokół wędrowny Płock ORLEN podest', 'Sokół wędrowny Płock ORLEN',  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'https://stream.orlen.pl:443/sokol/podest.stream/playlist.m3u8', 0)], 0, 'http://www.peregrinus.pl/images/comprofiler/4246_5e91d934b04fa.jpg', None))
            valTab.append(CDisplayListItem('Sokół wędrowny Płock ORLEN gniazdo', 'Sokół wędrowny Płock ORLEN',  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'https://stream.orlen.pl:443/sokol/gniazdo.stream/playlist.m3u8', 0)], 0, 'http://www.peregrinus.pl/images/comprofiler/4246_5e91d934b04fa.jpg', None))
            valTab.append(CDisplayListItem('Sokół wędrowny na kominie MPEC we Włocławku podest', 'Sokół wędrowny na kominie Miejskiego Przedsiębiorstwa Energetyki Cieplnej we Włocławku',  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'https://53c7d208964cd.streamlock.net/mpecz/mpecpodest.stream/playlist.m3u8', 0)], 0, 'http://www.peregrinus.pl/images/comprofiler/4246_5e91d934b04fa.jpg', None))
            valTab.append(CDisplayListItem('Sokół wędrowny na kominie MPEC we Włocławku gniazdo', 'Sokół wędrowny na kominie Miejskiego Przedsiębiorstwa Energetyki Cieplnej we Włocławku',  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'https://53c7d208964cd.streamlock.net/mpecw/mpecw.stream_aac/playlist.m3u8', 0)], 0, 'http://www.peregrinus.pl/images/comprofiler/4246_5e91d934b04fa.jpg', None))
            valTab.append(CDisplayListItem('Czarny Bocian - Hungary', 'Czarny Bocian - Hungary',  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'http://gemenczrt.hu/media/feketegolya-feszek/', 1)], 0, 'http://gemenczrt.hu/wp-content/uploads/2020/05/3f_1_200501.jpg', None))

            url ='https://www.sokolka.tv/index.php/kamery-online/gniazdo-bocianie'
            COOKIEFILE = os_path.join(GetCookieDir(), 'info.cookie') 
            self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
            self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': False, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.get_Page(url)
            if not sts: return valTab
            printDBG( 'Host listsItems data '+data )
            Url = self.cm.ph.getSearchGroups(data, '''(//www.youtube.com[^"^']+?)['"?]''')[0] 
            if Url:
               if Url.startswith('//'): Url = 'https:' + Url 
               valTab.append(CDisplayListItem('Kamera na bocianim gnieździe Sokółka', 'Kamera na bocianim gnieździe Sokółka (youtube)',  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', Url, 1)], 0, 'http://zasoby.ekologia.pl/artykulyNew/19316/xxl/800px-ciconia-ciconia-01-bocian-bialy_800x600.jpg', None))

            #valTab.append(CDisplayListItem('Sokół wędrowny Płock ORLEN (rtmp)', 'Sokół wędrowny Płock ORLEN',  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'rtmp://stream.orlen.pl:1935/sokol playpath=gniazdo.stream swfUrl=http://webcam.peregrinus.pl/plugins/hwdvs-videoplayer/jwflv/mediaplayer.swf pageUrl=http://webcam.peregrinus.pl/pl/plock-orlen-podglad', 0)], 0, 'http://postis.pl/wp-content/uploads/sok%C3%B3%C5%82-w%C4%99drowny.jpeg', None))

            url ='https://live.mstream.pl/uwb/cam-4923/'
            #valTab.append(CDisplayListItem('Instytut Biologii UwB zaprasza do oglądania transmisji z gniazda jastrzębia ', 'Zapraszamy do oglądania transmisji z gniazda jastrzębia pod Białymstokiem w  Nadleśnictwie Dojlidy. W godzinach 23.00-4.00 transmisja jest przerywana',  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', url, 1)], 0, 'https://biologia.biol-chem.uwb.edu.pl/media/_versions/biologia/podstrony_statyczne_zdjecia/panel_main_photo_detail.jpg', None))

            #valTab.append(CDisplayListItem('Gniazdo bocianów czarnych w Łodzi', 'Gniazdo bocianów czarnych w Łodzi',  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', 'http://www.lodz.lasy.gov.pl/bocianyczarne#p_101_INSTANCE_kCS6', 1)], 0, 'http://www.lodz.lasy.gov.pl/image/journal/article?img_id=33457917&t=1523609274456&width=716', None))

            url = 'http://webcam.peregrinus.pl/pl/gdansk-lotos-podglad'
            #valTab.append(CDisplayListItem('Sokół wędrowny LOTOS Gdańsk (youtube)', 'Sokół wędrowny LOTOS Gdańsk',  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', url, 1)], 0, '', None))

            url = 'http://www.peregrinus.pl/pl/police'
            #valTab.append(CDisplayListItem('Sokół wędrowny Police Zakłady Chemiczne (youtube)', 'Sokół wędrowny Police Zakłady Chemiczne',  CDisplayListItem.TYPE_VIDEO, [CUrlItem('', url, 1)], 0, '', None))

            return valTab 

        if 'UPDATE' == name:
               printDBG( 'Host listsItems begin name='+name )
               valTab.append(CDisplayListItem(self.infoversion+' - Local version',   'Local  infoversion', CDisplayListItem.TYPE_CATEGORY, [''], '', '', None)) 
               valTab.append(CDisplayListItem(self.inforemote+ ' - Remote version',  'Remote infoversion', CDisplayListItem.TYPE_CATEGORY, [''], '', '', None)) 
               valTab.append(CDisplayListItem('ZMIANY W WERSJI',                    'ZMIANY W WERSJI',   CDisplayListItem.TYPE_CATEGORY, ['https://gitlab.com/mosz_nowy/infoversion/commits/master.atom'], 'UPDATE-ZMIANY', '', None)) 
               valTab.append(CDisplayListItem('Update Now',                         'Update Now',        CDisplayListItem.TYPE_CATEGORY, [''], 'UPDATE-NOW',    '', None)) 
               valTab.append(CDisplayListItem('Update Now & Restart Enigma2',       'Update Now & Restart Enigma2',        CDisplayListItem.TYPE_CATEGORY, ['restart'], 'UPDATE-NOW',    '', None)) 
               printDBG( 'Host listsItems end' )
               return valTab
        if 'UPDATE-ZMIANY' == name:
           printDBG( 'Host listsItems begin name='+name )
           try:
              data = self.cm.getURLRequestData({ 'url': url, 'use_host': False, 'use_cookie': False, 'use_post': False, 'return_data': True })
           except:
              printDBG( 'Host listsItems query error' )
              return valTab
           #printDBG( 'Host listsItems data: '+data )
           phCats = re.findall("<entry>.*?<title>(.*?)</title>.*?<updated>(.*?)</updated>.*?<name>(.*?)</name>", data, re.S)
           if phCats:
              for (phTitle, phUpdated, phName ) in phCats:
                  phUpdated = phUpdated.replace('T', '   ')
                  phUpdated = phUpdated.replace('Z', '   ')
                  phUpdated = phUpdated.replace('+01:00', '   ')
                  phUpdated = phUpdated.replace('+02:00', '   ')
                  printDBG( 'Host listsItems phTitle: '+phTitle )
                  printDBG( 'Host listsItems phUpdated: '+phUpdated )
                  printDBG( 'Host listsItems phName: '+phName )
                  valTab.append(CDisplayListItem(phUpdated+' '+phName+'  >>  '+phTitle,phTitle,CDisplayListItem.TYPE_CATEGORY, [''],'', '', None)) 
           printDBG( 'Host listsItems end' )
           return valTab
        if 'UPDATE-NOW' == name:
           printDBG( 'Hostinfo listsItems begin name='+name )
           import os
           _url = 'https://gitlab.com/mosz_nowy/infoversion'

           try:
              sts, data = self.cm.getPage(_url+'/-/commits/master')
              if not sts: return valTab
              #printDBG( 'Host init data: '+data )
              crc=self.cm.ph.getSearchGroups(data, '''/commit/([^"^']+?)['"]''', 1, True)[0]
              printDBG( 'crc: '+crc )
              if not crc: error
           except:
              printDBG( 'Host init query error' )
              valTab.append(CDisplayListItem('ERROR - Blad pobierania: '+_url,   'ERROR', CDisplayListItem.TYPE_CATEGORY, [''], '', '', None)) 
              return valTab

           tmpDir = GetTmpDir() 
           source = os_path.join(tmpDir, 'infoversion-master.tar.gz') 
           dest = os_path.join(tmpDir , '') 
           _url = 'https://gitlab.com/mosz_nowy/infoversion/repository/master/archive.tar.gz?ref=master'              
           output = open(source,'wb')
           query_data = { 'url': _url, 'use_host': False, 'use_cookie': False, 'use_post': False, 'return_data': True }
           try:
              output.write(self.cm.getURLRequestData(query_data))
              output.close()
              os_system ('sync')
              printDBG( 'Hostinfo pobieranie infoversion-master.tar.gz' )
           except:
              if os_path.exists(source):
                 os_remove(source)
              printDBG( 'Hostinfo Błąd pobierania infoversion-master.tar.gz' )
              valTab.append(CDisplayListItem('ERROR - Blad pobierania: '+_url,   'ERROR', CDisplayListItem.TYPE_CATEGORY, [''], '', '', None)) 
              return valTab
           if os_path.exists(source):
              printDBG( 'Hostinfo Jest plik '+source )
           else:
              printDBG( 'Hostinfo Brak pliku '+source )

           cmd = 'tar -xzf "%s" -C "%s" 2>&1' % ( source, dest )  
           try: 
              os_system (cmd)
              os_system ('sync')
              printDBG( 'Hostinfo rozpakowanie  ' + cmd )
           except:
              printDBG( 'Hostinfo Błąd rozpakowania infoversion-master.tar.gz' )
              os_system ('rm -f %s' % source)
              os_system ('rm -rf %sinfoversion-master-%s' % (dest, crc))
              valTab.append(CDisplayListItem('ERROR - Blad rozpakowania %s' % source,   'ERROR', CDisplayListItem.TYPE_CATEGORY, [''], '', '', None)) 
              return valTab

           try:
              os_system ('cp -rf %sinfoversion-master-%s/* %s' % (dest, crc, GetPluginDir()))
              os_system ('sync')
              printDBG( 'Hostinfo kopiowanie Hostinfo do IPTVPlayer: '+'cp -rf %sinfoversion-master-%s/* %s' % (dest, crc, GetPluginDir()) )
           except:
              printDBG( 'Hostinfo blad kopiowania' )
              os_system ('rm -f %s' % source)
              os_system ('rm -rf %sinfoversion-master-%s' % (dest, crc))
              valTab.append(CDisplayListItem('ERROR - blad kopiowania',   'ERROR', CDisplayListItem.TYPE_CATEGORY, [''], '', '', None)) 
              return valTab

           ikony = GetPluginDir('icons/PlayerSelector/')
           if os_path.exists('%sinfoversion100' % ikony):
              printDBG( 'Hostinfo Jest '+ ikony + 'infoversion100 ' )
              os_system('mv %sinfoversion100 %sinfoversion100.png' % (ikony, ikony)) 
           if os_path.exists('%sinfoversion120' % ikony):
              printDBG( 'Hostinfo Jest '+ ikony + 'infoversion120 '  )
              os_system('mv %sinfoversion120 %sinfoversion120.png' % (ikony, ikony))
           if os_path.exists('%sinfoversion135' % ikony):
              printDBG( 'Hostinfo Jest '+ ikony + 'infoversion135 '  )
              os_system('mv %sinfoversion135 %sinfoversion135.png' % (ikony, ikony))

           try:
              cmd = GetPluginDir('hosts/hostinfoversion.py')
              with open(cmd, 'r') as f:  
                 data = f.read()
                 f.close() 
                 wersja = re.search('infoversion = "(.*?)"', data, re.S)
                 aktualna = wersja.group(1)
                 printDBG( 'Hostinfo aktualna wersja wtyczki '+aktualna )
           except:
              printDBG( 'Hostinfo error openfile ' )


           printDBG( 'Hostinfo usuwanie plikow tymczasowych' )
           os_system ('rm -f %s' % source)
           os_system ('rm -rf %sinfoversion-master-%s' % (dest, crc))

           if url:
              try:
                 info = 'Zaraz nastąpi Restart GUI .\n \n Wersja infoversion w tunerze %s' % aktualna
                 GetIPTVNotify().push('%s' % (info), 'info', 20) 
                 from enigma import quitMainloop
                 quitMainloop(3)
              except Exception: printExc()
           valTab.append(CDisplayListItem('Update End. Please manual restart enigma2',   'Restart', CDisplayListItem.TYPE_CATEGORY, [''], '', '', None)) 
           printDBG( 'Hostinfo listsItems end' )
           return valTab

        if 'Download' == name:
           printDBG( 'Hostinfo listsItems begin name='+name +url)
           import os
           try:
              sts, data = self.cm.getPage(url+'/-/commits/master')
              if not sts: return valTab
              printDBG( 'Host init data: '+data )
              crc=self.cm.ph.getSearchGroups(data, '''/commit/([^"^']+?)['"]''', 1, True)[0]
              printDBG( 'crc: '+crc )
              if not crc: error
           except:
              printDBG( 'Host init query error' )
              valTab.append(CDisplayListItem('ERROR - Blad pobierania: '+url,   'ERROR', CDisplayListItem.TYPE_CATEGORY, [''], '', '', None)) 
              return valTab
           tmpDir = GetTmpDir() 
           source = os_path.join(tmpDir, 'master.tar.gz') 
           dest = os_path.join(tmpDir , '') 
           _url = url + '/repository/master/archive.tar.gz?ref=master'              
           output = open(source,'wb')
           query_data = { 'url': _url, 'use_host': False, 'use_cookie': False, 'use_post': False, 'return_data': True }
           try:
              output.write(self.cm.getURLRequestData(query_data))
              output.close()
              os_system ('sync')
              printDBG( 'Hostinfo pobieranie master.tar.gz' )
           except:
              if os_path.exists(source):
                 os_remove(source)
              printDBG( 'Hostinfo Błąd pobierania master.tar.gz' )
              valTab.append(CDisplayListItem('ERROR - Blad pobierania: '+_url,   'ERROR', CDisplayListItem.TYPE_CATEGORY, [''], '', '', None)) 
              return valTab
           if os_path.exists(source):
              printDBG( 'Hostinfo Jest plik '+source )
           else:
              printDBG( 'Hostinfo Brak pliku '+source )

           cmd = 'tar -xzf "%s" -C "%s" 2>&1' % ( source, dest )  
           try: 
              os_system (cmd)
              os_system ('sync')
              printDBG( 'Hostinfo rozpakowanie  ' + cmd )
           except:
              printDBG( 'Hostinfo Błąd rozpakowania master.tar.gz' )
              os_system ('rm -f %s' % source)
              os_system ('rm -rf %smaster-%s' % (dest, crc))
              valTab.append(CDisplayListItem('ERROR - Blad rozpakowania %s' % source,   'ERROR', CDisplayListItem.TYPE_CATEGORY, [''], '', '', None)) 
              return valTab

           #cmd = 'cp -rf %se2iplayer-master-%s/IPTVPlayer %s' % (dest, crc, GetPluginDir().replace('/IPTVPlayer/',''))  
           cmd = 'cp -rf %se2iplayer-master-%s/IPTVPlayer %s' % (dest, crc, GetPluginDir().replace(GetPluginDir().split('/')[-2]+'/',''))  
           try:
              os_system (cmd)
              os_system ('sync')
              printDBG( 'Hostinfo kopiowanie  ' + cmd )
           except:
              printDBG( 'Hostinfo blad kopiowania' )
              os_system ('rm -f %s' % source)
              os_system ('rm -rf %se2iplayer-master-%s' % (dest, crc))
              valTab.append(CDisplayListItem('ERROR - blad kopiowania',   'ERROR', CDisplayListItem.TYPE_CATEGORY, [''], '', '', None)) 
              return valTab

           printDBG( 'Hostinfo usuwanie plikow tymczasowych' )
           printDBG( 'rm -f %s' % source )
           printDBG( 'rm -rf %se2iplayer-master-%s' % (dest, crc) )
           os_system ('rm -f %s' % source)
           os_system ('rm -rf %se2iplayer-master-%s' % (dest, crc))

           if url:
              try:
                 from enigma import quitMainloop
                 quitMainloop(3)
              except Exception: printExc()
           valTab.append(CDisplayListItem('Update End. Please manual restart enigma2',   'Restart', CDisplayListItem.TYPE_CATEGORY, [''], '', '', None)) 
           return valTab


        return valTab 

    def getResolvedURL(self, url):
        printDBG( 'Host getResolvedURL begin' )
        printDBG( 'Host getResolvedURL url: '+url )
        videoUrl = ''
        valTab = []

        if 'kukaj' in url:
            COOKIEFILE = os_path.join(GetCookieDir(), 'kukaj.cookie')
            self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
            self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': False, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.get_Page(url)
            if not sts: return ''
            printDBG( 'Host listsItems data: %s' % data )
            videoUrl = self.cm.ph.getSearchGroups(data, '''"sourceURL":\s*?['"]([^"^']+?)['"]''', 1, True)[0].replace(r'http:',r'https:').replace(r':443','')
            videoUrl = strwithmeta(videoUrl, {'Referer':url, 'Origin':"https://www.kukaj.sk"})
            tmp = getDirectM3U8Playlist(videoUrl, checkContent=True, sortWithMaxBitrate=999999999)
            for item in tmp:
                return item['url']
            return ''

        if url.startswith('http://www.skrzyczne.cos.pl'):
            COOKIEFILE = os_path.join(GetCookieDir(), 'skrzyczne.cookie')
            self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
            self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': False, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.get_Page(url)
            if not sts: return ''
            Url = self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''')[0] 
            if Url.startswith('//'): Url = 'http:' + Url
            sts, data = self.get_Page(Url)
            if not sts: return ''
            printDBG( 'Host listsItems data: '+data )
            videoUrl = self.cm.ph.getSearchGroups(data, '''<source[^>]+?src=['"]([^"^']+?)['"]''')[0] 
            tmp = getDirectM3U8Playlist(videoUrl, checkContent=True, sortWithMaxBitrate=999999999)
            for item in tmp:
                return item['url']
            return ''

        if 'itcom' in url:
            videoUrl = url.replace(r'embed.html',r'index.m3u8')
            tmp = getDirectM3U8Playlist(videoUrl, checkContent=True, sortWithMaxBitrate=999999999)
            for item in tmp:
                return item['url']
            return ''

        if 'airmax' in url:
            videoUrl = url.replace(r'embed.html',r'index.m3u8')
            tmp = getDirectM3U8Playlist(videoUrl, checkContent=True, sortWithMaxBitrate=999999999)
            for item in tmp:
                return item['url']
            return ''

        if 'szczyrkowski' in url:
            COOKIEFILE = os_path.join(GetCookieDir(), 'szczyrk.cookie')
            self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
            self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': False, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.get_Page(url)
            if not sts: return ''
            videoUrl = self.cm.ph.getSearchGroups(data, '''<source\ssrc=['"]([^"^']+?)['"]''')[0] 
            tmp = getDirectM3U8Playlist(videoUrl, checkContent=True, sortWithMaxBitrate=999999999)
            for item in tmp:
                return item['url']
            return ''

        if 'task' in url:
            COOKIEFILE = os_path.join(GetCookieDir(), 'task.cookie')
            self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
            self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': False, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.get_Page(url)
            if not sts: return valTab
            videoUrl = self.cm.ph.getSearchGroups(data, '''<source\ssrc=['"]([^"^']+?)['"]''')[0] 
            tmp = getDirectM3U8Playlist(videoUrl, checkContent=True, sortWithMaxBitrate=999999999)
            for item in tmp:
                return item['url']
            return ''

        if 'imperium' in url:
            COOKIEFILE = os_path.join(GetCookieDir(), 'imperium.cookie')
            self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
            self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': False, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.get_Page(url)
            if not sts: return valTab
            videoUrl = self.cm.ph.getSearchGroups(data, '''<source\ssrc=['"]([^"^']+?)['"]''')[0] 
            tmp = getDirectM3U8Playlist(videoUrl, checkContent=True, sortWithMaxBitrate=999999999)
            for item in tmp:
                return item['url']
            return ''

        if 'wlkp24' in url:
            COOKIEFILE = os_path.join(GetCookieDir(), 'wlkp24.cookie')
            self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
            self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': False, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.get_Page(url)
            if not sts: return valTab
            printDBG( 'Host listsItems data: '+data )
            videoUrl = self.cm.ph.getSearchGroups(data, '''src:\s*['"]([^"^']+?\.m3u8)['"]''', 1, True)[0] 
            return videoUrl 

        if 'iplax' in url:
            COOKIEFILE = os_path.join(GetCookieDir(), 'iplax.cookie')
            self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.getPage(url, 'iplax.cookie', 'iplax.eu', self.defaultParams)
            if not sts: return valTab
            printDBG( 'Host listsItems data: '+data )
            videoUrl = self.cm.ph.getSearchGroups(data, '''<source src=['"]([^"^']+?)['"]''', 1, True)[0] 
            if 'youtube.com' in videoUrl:
                return self.getResolvedURL(videoUrl)
            if videoUrl.startswith('//'): videoUrl = 'http:' + videoUrl
            videoUrl = urlparser.decorateUrl(videoUrl, {'Referer': url, 'Connection':'keep-alive'})  
            return videoUrl 

        if 'kastream' in url:
            headers = {'User-Agent': self.USER_AGENT,'Accept': '*/*','Accept-Language': 'pl,en-US;q=0.7,en;q=0.3','Referer': 'http://darmowa-telewizja.online/','Connection': 'keep-alive',}
            COOKIEFILE = os_path.join(GetCookieDir(), 'kastream.cookie')
            self.defaultParams = {'header':headers, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.getPage(url, 'kastream.cookie', 'kastream.biz', self.defaultParams)
            if not sts: return valTab
            printDBG( 'Host listsItems data: '+data )
            if "eval(function(p,a,c,k,e,d)" in data:
                printDBG( 'Host resolveUrl packed' )
                packed = re.compile('eval\(function\(p,a,c,k,e,d\)(.+?)</script>', re.DOTALL).findall(data)
                if packed:
                    data2 = packed[-1]
                else:
                    return ''
                try:
                    unpack = unpackJSPlayerParams(data2, TEAMCASTPL_decryptPlayerParams, 0, True, True) 
                except Exception: printExc()
                printDBG( 'Host unpack: '+unpack )
                videoUrl = self.cm.ph.getSearchGroups(unpack, '''source:['"]([^"^']+?)['"]''', 1, True)[0] 
                if videoUrl.startswith('//'): videoUrl = 'http:' + videoUrl
                videoUrl = urlparser.decorateUrl(videoUrl, {'Referer': 'http://darmowa-telewizja.online', 'User-Agent':self.USER_AGENT, 'Connection':'keep-alive'})  
                if self.cm.isValidUrl(videoUrl): 
                    tmp = getDirectM3U8Playlist(videoUrl)
                    printDBG( 'Host listsItems tmp: [%s]' % tmp )
                    for item in tmp:
                        return item['url']
            return ''

        if 'darmowa-telewizja.online' in url:
            COOKIEFILE = os_path.join(GetCookieDir(), 'darmowaonline.cookie')
            mainurl = 'http://darmowa-telewizja.online/'
            self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.getPage(url, 'darmowaonline.cookie', 'darmowa-telewizja.online', self.defaultParams)
            if not sts: return valTab
            printDBG( 'Host listsItems data: '+data )
            data2 = self.cm.ph.getDataBeetwenMarkers(data, '<video', '</video>', False)[1].replace('\\','')
            if not data2: data2 = self.cm.ph.getDataBeetwenMarkers(data, '<iframe', '</iframe>', False)[1]
            videoUrl = self.cm.ph.getSearchGroups(data2, '''src=['"]([^"^']+?)['"]''', 1, True)[0] 
            if videoUrl.startswith('//'): videoUrl = 'http:' + videoUrl
            if 'kastream' in videoUrl:
                return self.getResolvedURL(videoUrl)
            if '/weeb/' in videoUrl:
                return self.getResolvedURL(videoUrl)
            videoUrl = urlparser.decorateUrl(videoUrl, {'Referer': url, 'Origin':'http://darmowa-telewizja.online', 'Connection':'keep-alive'})  
            if self.cm.isValidUrl(videoUrl): 
                tmp = getDirectM3U8Playlist(videoUrl)
                printDBG( 'Host listsItems tmp: [%s]' % tmp )
                for item in tmp:
                    return item['url']
            return videoUrl

        if 'wstream.to' in url:
            COOKIEFILE = os_path.join(GetCookieDir(), 'zobacz.cookie')
            self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.getPage(url, 'zobacz.cookie', 'zobacz.ws', self.defaultParams)
            if not sts: return ''
            printDBG( 'Host listsItems data1: '+data )
            unpack = ''
            if "eval(function(p,a,c,k,e,d)" in data:
                printDBG( 'Host resolveUrl packed' )
                packed = re.compile('eval\(function\(p,a,c,k,e,d\)(.+?)</script>', re.DOTALL).findall(data)
                for item in packed:
                    if 'm3u8' in item or 'stream' in item:
                        data2 = item
                        break
                    else:
                        return ''
                try:
                    unpack = unpackJSPlayerParams(data2, TEAMCASTPL_decryptPlayerParams, 0, True, True) 
                except Exception: printExc()
            printDBG( 'Host listsItems unpack: '+unpack )
            videoUrl = self.cm.ph.getSearchGroups(unpack, '''source:['"]([^"^']+?)['"]''', 1, True)[0] 
            videoUrl = urlparser.decorateUrl(videoUrl, {'Referer': url, 'Origin':'http://zobacz.ws', 'Connection':'keep-alive'})  
            if 'm3u8' in videoUrl: 
                tmp = getDirectM3U8Playlist(videoUrl, checkContent=True, sortWithMaxBitrate=999999999)
                for item in tmp:
                    return item['url']
            return videoUrl

        if 'assia.tv' in url:
            COOKIEFILE = os_path.join(GetCookieDir(), 'assia.cookie')
            self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.getPage(url, 'assia.cookie', 'assia.tv', self.defaultParams)
            if not sts: return ''
            printDBG( 'Host listsItems data1: '+data )
            videoUrl = self.cm.ph.getSearchGroups(data, '''file:['"]([^"^']+?)['"]''', 1, True)[0].replace('&amp;','&')
            return videoUrl

        if 'freecast123' in url:
            COOKIEFILE = os_path.join(GetCookieDir(), 'freecast123.cookie')
            self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.getPage(url, 'freecast123.cookie', 'freecast123.com', self.defaultParams)
            if not sts: return ''
            printDBG( 'Host listsItems data1: '+data )
            js = self.cm.ph.getDataBeetwenMarkers(data, '<script type="text/javascript">', '</script>', False)[1] #.strip()
            #js = "\n".join(js)
            printDBG( 'Host  js: %s' % js )
            urls = js_execute( js+ '\nfor (n in this){print(n+"="+this[n]+";");}')

            return videoUrl

        if 'zobacz.ws' in url:
            COOKIEFILE = os_path.join(GetCookieDir(), 'zobacz.cookie')
            self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.getPage(url, 'zobacz.cookie', 'zobacz.ws', self.defaultParams)
            if not sts: return ''
            printDBG( 'Host listsItems data1: '+data )
            data2 = self.cm.ph.getDataBeetwenMarkers(data, '<video', '</video>', False)[1].replace('\\','')
            if not data2: data2 = self.cm.ph.getDataBeetwenMarkers(data, '<iframe', '</iframe>', False)[1]
            if not data2:
                tmp = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="entry-content">', '</div>')
                for item in tmp:
                    printDBG( 'Host item:%s ' % item )

                    if 'telerium' in item:
                        id = self.cm.ph.getSearchGroups(item, '''id=['"]([^"^']+?)['"]''', 1, True)[0]
                        data = self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''', 1, True)[0].replace('embed.js',id+'.html')
                        printDBG( 'Host listsItems id: '+id )
                        printDBG( 'Host listsItems datax: '+data )
                        videoUrl = 'http://telerium.tv/embed/'+id+'.html'
                        videoUrl = urlparser.decorateUrl(videoUrl, {'Referer': url, 'User-Agent':'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.9 Safari/537.36'})  
                        return self.getResolvedURL(videoUrl)

            videoUrl = self.cm.ph.getSearchGroups(data2, '''src=['"]([^"^']+?)['"]''', 1, True)[0].replace('&amp;','&').replace('&#038;','&')
            if videoUrl.startswith('//'): videoUrl = 'http:' + videoUrl


            if not 'zobacz' in videoUrl: 
                videoUrl = urlparser.decorateUrl(videoUrl, {'Referer': url, 'User-Agent':'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.9 Safari/537.36'})  
                return self.getResolvedURL(videoUrl)

            sts, data = self.getPage(videoUrl, 'zobacz.cookie', 'zobacz.ws', self.defaultParams)
            if not sts: return ''
            printDBG( 'Host listsItems data2: '+data )
            cookieHeader = self.cm.getCookieHeader(COOKIEFILE)
            if 'telerium' in data:
                id = self.cm.ph.getSearchGroups(data, '''id=['"]([^"^']+?)['"]''', 1, True)[0]
                data = self.cm.ph.getSearchGroups(data, '''src=['"]([^"^']+?)['"]''', 1, True)[0].replace('embed.js',id+'.html')
                printDBG( 'Host listsItems id: '+id )
                printDBG( 'Host listsItems datax: '+data )
                videoUrl = 'http://telerium.tv/embed/'+id+'.html'
                videoUrl = urlparser.decorateUrl(videoUrl, {'Referer': url, 'User-Agent':'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.9 Safari/537.36'})  
                return self.getResolvedURL(videoUrl)
            if 'm3u8' in data:
                videoUrl = self.cm.ph.getSearchGroups(data, '''source:\s*['"]([^"^']+?)['"]''', 1, True)[0].replace('&amp;','&').replace('&#038;','&')
                if videoUrl.startswith('//'): videoUrl = 'http:' + videoUrl
                sts, data = self.getPage(videoUrl, 'zobacz.cookie', 'zobacz.ws', self.defaultParams)
                if not sts: return ''
                cookieHeader = self.cm.getCookieHeader(COOKIEFILE)
                redirectUrl =  strwithmeta(self.cm.meta['url'], {'iptv_proto':'m3u8', 'Cookie':cookieHeader, 'User-Agent': self.HEADER['User-Agent']})
                return redirectUrl

                printDBG( 'Host listsItems data m3u8: '+data )
			
                tmpTab = getDirectM3U8Playlist(self.cm.meta['url'], False, checkContent=True, cookieParams={'header':self.HEADER, 'cookiefile':COOKIEFILE, 'use_cookie': True, 'save_cookie':True})
                cookieHeader = self.cm.getCookieHeader(COOKIEFILE)
                for tmp in tmpTab:
                    redirectUrl =  strwithmeta(tmp['url'], {'iptv_proto':'m3u8', 'Cookie':cookieHeader, 'User-Agent': self.HEADER['User-Agent']})
                    return redirectUrl
                #for item in tmp:
                #    return item['url']

                #sts, data = self.getPage(videoUrl, 'zobacz.cookie', 'zobacz.ws', self.defaultParams)
                #if not sts: return ''
                #printDBG( 'Host listsItems data3: '+data )


                #return urlparser.decorateUrl(videoUrl, {'Cookie': cookieHeader, 'Referer': url, 'User-Agent':'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.9 Safari/537.36', 'Accept': '*/*', 'Accept-Language': 'pl,en-US;q=0.7,en;q=0.3'})  
            data2 = self.cm.ph.getDataBeetwenMarkers(data, '<video', '</video>', False)[1].replace('\\','')
            if not data2: data2 = self.cm.ph.getDataBeetwenMarkers(data, '<iframe', '</iframe>', False)[1]
            videoUrl = self.cm.ph.getSearchGroups(data2, '''src=['"]([^"^']+?)['"]''', 1, True)[0].replace('&amp;','&').replace('&#038;','&')
            if videoUrl.startswith('//'): videoUrl = 'http:' + videoUrl

            if not 'zobacz' in videoUrl: return self.getResolvedURL(videoUrl)

            sts, data = self.getPage(videoUrl, 'zobacz.cookie', 'zobacz.ws', self.defaultParams)
            if not sts: return ''
            printDBG( 'Host listsItems data3: '+data )

            if not 'zobacz' in videoUrl: return self.getResolvedURL(videoUrl)
            if 'kastream' in videoUrl:
                return self.getResolvedURL(videoUrl)
            if '/weeb/' in videoUrl:
                return self.getResolvedURL(videoUrl)
            SetIPTVPlayerLastHostError(_(' zobacz - nie widzi serwera.'))
            return []

        if 'supersportowo' in url:
            COOKIEFILE = os_path.join(GetCookieDir(), 'SuperSportowo.cookie')
            mainurl = 'https://supersportowo.com/'
            self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.getPage(url, 'SuperSportowo.cookie', 'supersportowo.com', self.defaultParams)
            if not sts: return valTab
            printDBG( 'Host listsItems data: '+data )
            Url = self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''')[0] 
            if Url.startswith('//'): Url = 'http:' + Url
            cookieHeader = self.cm.getCookieHeader(COOKIEFILE)
            header2 = {'cookie_item': cookieHeader, 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.9 Safari/537.36','Accept': 'application/json, text/javascript, */*; q=0.01','Accept-Language': 'pl,en-US;q=0.7,en;q=0.3','Referer': Url,'X-Requested-With': 'XMLHttpRequest','Connection': 'keep-alive','Cache-Control': 'max-age=0',}
            self.defaultParams = {'header':header2, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.getPage(Url, 'SuperSportowo.cookie', 'supersportowo.com', self.defaultParams)
            if not sts: return valTab
            printDBG( 'Host listsItems data2: '+data )
            videoUrl = self.cm.ph.getSearchGroups(data, '''curl = ['"]([^"^']+?)['"]''')[0] 
            sts, data = self.getPage('https://nlive.club/getToken.php', 'SuperSportowo.cookie', 'supersportowo.com', self.defaultParams)
            if not sts: return valTab
            printDBG( 'Host listsItems data3: '+data )
            token = self.cm.ph.getSearchGroups(data, '''token":['"]([^"^']+?)['"]''')[0] 
            videoUrl = videoUrl+token
            return urlparser.decorateUrl(videoUrl, {'Cookie': cookieHeader, 'Referer': Url, 'User-Agent':'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.9 Safari/537.36', 'Origin': 'https://nlive.club', 'Host': 'edge.nlive.club', 'Accept': '*/*', 'Accept-Language': 'pl,en-US;q=0.7,en;q=0.3'})  


        if 'swirtvteam' in url:
            COOKIEFILE = os_path.join(GetCookieDir(), 'SwirTeamTk.cookie')
            mainurl = 'http://tv-swirtvteam.info/'
            self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.getPage(url, 'SwirTeamTk.cookie', 'tv-swirtvteam.info', self.defaultParams)
            if not sts: return valTab
            printDBG( 'Host listsItems data: '+data )
            videoUrl = self.cm.ph.getSearchGroups(data, '''source:\s['"]([^"^']+?)['"]''', 1, True)[0] 
            if videoUrl.startswith('//'): videoUrl = 'http:' + videoUrl
            #videoUrl = urlparser.decorateUrl(videoUrl, {'Referer': url, 'Connection':'keep-alive'})  
            return videoUrl

        if 'ustreamix' in url:
            COOKIEFILE = os_path.join(GetCookieDir(), 'ustreamix.cookie')
            mainurl = 'https://ustreamix.com'
            self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.getPage(url, 'ustreamix.cookie', 'ustreamix.com', self.defaultParams)
            if not sts: return valTab
            printDBG( 'Host listsItems data: '+data )
            videoUrl = self.cm.ph.getSearchGroups(data, '''window.open\(['"]([^"^']+?)['"]''', 1, True)[0] 
            if videoUrl.startswith('//'): videoUrl = 'http:' + videoUrl
            if videoUrl.startswith('/'): videoUrl = 'https://ssl.ustreamix.com' + videoUrl
            sts, data = self.getPage(videoUrl, 'ustreamix.cookie', 'ustreamix.com', self.defaultParams)
            if not sts: return valTab
            printDBG( 'Host listsItems data2: '+data )
            #videoUrl = urlparser.decorateUrl(videoUrl, {'Referer': url, 'Connection':'keep-alive'})  
            if "eval(function(p,a,c,k,e,d)" in data:
                printDBG( 'Host resolveUrl packed' )
                packed = re.compile('eval\(function\(p,a,c,k,e,d\)(.+?)</script>', re.DOTALL).findall(data)
                if packed:
                    data2 = packed[-1]
                else:
                    return ''
                try:
                    unpack = unpackJSPlayerParams(data2, TEAMCASTPL_decryptPlayerParams, 0, True, True) 
                except Exception: printExc()
                link = re.findall('replace\("(.+?)"',unpack,re.DOTALL)[0]
                sts, data = self.getPage(link, 'ustreamix.cookie', 'ustreamix.com', self.defaultParams)
                if not sts: return valTab
                printDBG( 'Host listsItems data3: '+data )

                unpacked=''
                packer = re.compile('(eval\(function\(p,a,c,k,e,(?:r|d).*)')
                packeds = packer.findall(data)#[0]
                for packed in packeds:
                    unpacked += unpackJSPlayerParams(packed, TEAMCASTPL_decryptPlayerParams, 0, True, True)
                varhost=re.compile('var host_tmg="(.*?)"').findall(unpacked)
                varfname=re.compile('var file_name="(.*?)"').findall(unpacked)
                varjdtk=re.compile('var jdtk="(.*?)"').findall(unpacked)
                if varhost and varfname and varjdtk:
                    videoUrl = 'https://' + varhost[0] + '/' + varfname[0] + '?token=' + varjdtk[0] # +'|User-Agent='+urllib.quote(UA)+'&Referer='+link  
                videoUrl = urlparser.decorateUrl(videoUrl, {'Referer': link, 'User-Agent':self.USER_AGENT})  
                tmp = getDirectM3U8Playlist(videoUrl, checkContent=True, sortWithMaxBitrate=999999999)
                for item in tmp:
                    return item['url']
            return ''

        if 'nadmorski24' in url:
            COOKIEFILE = os_path.join(GetCookieDir(), 'nadmorski24.cookie')
            self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.getPage(url, 'nadmorski24.cookie', 'nadmorski24.pl', self.defaultParams)
            if not sts: return ''
            printDBG( 'Host listsItems data1: '+str(data) )
            Url = self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''')[0] 
            if Url.startswith('//'): Url = 'http:' + Url
            sts, data = self.getPage(Url, 'nadmorski24.cookie', 'nadmorski24.pl', self.defaultParams)
            if not sts: return ''
            printDBG( 'Host listsItems data2: '+str(data) )
            m3u8 =  self.cm.ph.getSearchGroups(data, '''<source\s*?src\s*?=\s*?['"]([^"^']+?)['"]''', 1, True)[0]
            if m3u8=='': m3u8 =  self.cm.ph.getSearchGroups(data, '''src:\s*?['"]([^"^']+?\.m3u8)['"]''', 1, True)[0]
            if 'm3u8' in m3u8:
                if m3u8.startswith('//'): m3u8 = 'http:' + m3u8
            videoUrl = urlparser.decorateUrl(m3u8, {'Referer': url, 'iptv_proto':'m3u8', 'iptv_livestream':True})  
            if self.cm.isValidUrl(videoUrl): 
                tmp = getDirectM3U8Playlist(videoUrl)
                for item in tmp:
                    printDBG( 'Host listsItems valtab: '  +str(item))
                    return item['url']
            m3u8 =  self.cm.ph.getSearchGroups(data, '''src:\s*?['"](rtmp[^"^']+?)['"]''', 1, True)[0]
            return m3u8

        if 'jwplatform' in url:
           COOKIEFILE = os_path.join(GetCookieDir(), 'jwplatform.cookie')
           self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
           sts, data = self.getPage(url, 'jwplatform.cookie', 'jwplatform.com', self.defaultParams)
           if not sts: return valTab
           printDBG( 'Host listsItems data: '+str(data) )
           return  self.cm.ph.getSearchGroups(data, '''stream" content=['"]([^"^']+?)['"]''', 1, True)[0]

        if 'filmbit' in url:
           for x in range(1, 50): 
              COOKIEFILE = os_path.join(GetCookieDir(), 'filmbit.cookie')
              self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
              sts, data = self.getPage(url, 'filmbit.cookie', 'filmbit.ws', self.defaultParams)
              if not sts: 
                 if 'chwilowy problem z naszymi serwerami' in data: 
                    SetIPTVPlayerLastHostError(_(' Ups, wystąpił chwilowy problem z naszymi serwerami.'))
                    return []
                 return ''
              printDBG( 'Host listsItems data: '+str(data) )
              m3u8 =  self.cm.ph.getSearchGroups(data, '''<source src=['"]([^"^']+?)['"]''', 1, True)[0]
              if m3u8=='': m3u8 =  self.cm.ph.getSearchGroups(data, '''"file":\s*?['"]([^"^']+?)['"]''', 1, True)[0]
              if m3u8: break
              GetIPTVSleep().Sleep(2)
           if m3u8.startswith('//'): m3u8 = 'http:' + m3u8
           videoUrl = urlparser.decorateUrl(m3u8, {'Referer': url, 'iptv_proto':'m3u8', 'iptv_livestream':True, 'User-Agent':self.USER_AGENT})  
           if self.cm.isValidUrl(videoUrl): 
               #printDBG( 'Host meta: '  + data.meta['url'])
               tmp = getDirectM3U8Playlist(videoUrl)
               for item in tmp:
                   printDBG( 'Host listsItems valtab: '  +str(item))
                   return item['url']
           if 'Odczekaj momencik na wolne miejsce' in data: 
               SetIPTVPlayerLastHostError(_(' Odczekaj momencik na wolne miejsce'))
               return []
           return ''

        if 'miamitvhd' in url:
           COOKIEFILE = os_path.join(GetCookieDir(), 'miami.cookie')
           self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
           sts, data = self.getPage(url, 'miami.cookie', 'miamitvhd.com', self.defaultParams)
           if not sts: return valTab
           printDBG( 'Host listsItems data: '+str(data) )
           if '.m3u8' in data:
              return self.cm.ph.getSearchGroups(data, '''source src=['"]([^"^']+?)['"]''', 1, True)[0]
           videoUrl = self.cm.ph.getSearchGroups(data, '''<source src=['"]([^"^']+?)['"]''')[0].replace('&amp;','&')
           if videoUrl:
              if videoUrl.startswith('//'): videoUrl = 'http:' + videoUrl
              return videoUrl
           videoUrl = self.cm.ph.getSearchGroups(data, '''url: ['"]([^"^']+?)['"]''')[0].replace('&amp;','&')
           if videoUrl:
              if videoUrl.startswith('//'): videoUrl = 'http:' + videoUrl
              videoUrl = urlparser.decorateUrl(videoUrl, {'Referer': url})  
              return self.getResolvedURL(videoUrl)
           return ''

        if 'bieszczady' in url:
            printDBG( 'Host getResolvedURL mainurl: '+url )
            COOKIEFILE = os_path.join(GetCookieDir(), 'Bieszczady.cookie')
            self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.getPage(url, 'Bieszczady.cookie', 'www.bieszczady.live', self.defaultParams)
            if not sts: return ''
            printDBG( 'Host listsItems data1: '+str(data) )
            Url = self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"](https://player[^"^']+?)['"]''')[0] 
            sts, data = self.getPage(Url, 'Bieszczady.cookie', 'www.bieszczady.live', self.defaultParams)
            if not sts: return ''
            printDBG( 'Host listsItems data2: '+str(data) )
            Url2 = self.cm.ph.getSearchGroups(data, '''<source src=['"]([^"^']+?)['"]''')[0] 
            return urlparser.decorateUrl(Url2, {'Referer': Url, 'Origin':'https://player.bieszczady.live'})  

        if 'tawizja' in url:
            printDBG( 'Host getResolvedURL mainurl: '+url )
            COOKIEFILE = os_path.join(GetCookieDir(), 'tawizja.cookie')
            host = "Mozilla/5.0 (Linux; U; Android 4.1.1; en-us; androVM for VirtualBox ('Tablet' version with phone caps) Build/JRO03S) AppleWebKit/534.30 (KHTML, like Gecko) Version/4.0 Safari/534.30"
            header = {'Referer':url, 'User-Agent': host, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}   
            try: data = self.cm.getURLRequestData({ 'url': url, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True })
            except:
                printDBG( 'Host getResolvedURL query error url: '+url )
                return ''
            printDBG( 'Host listsItems data1: '+data )
            data = self.cm.ph.getDataBeetwenMarkers(data, '<iframe', '/iframe>', False)[1].replace('\\','')
            #printDBG( 'Host listsItems data2: '+data )
            url = self.cm.ph.getSearchGroups(data, '''src=['"]([^"^']+?)['"]''', 1, True)[0] 
            if url.startswith('//'): url = 'http:' + url
            header = {'Referer':url, 'User-Agent': host, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}   
            try: data = self.cm.getURLRequestData({ 'url': url, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True })
            except:
                printDBG( 'Host getResolvedURL query error url: '+url )
                return ''
            printDBG( 'Host listsItems data3: '+data )
            Url = self.cm.ph.getSearchGroups(data, '''src=['"]([^"^']+?)['"]''', 1, True)[0] 
            if Url.startswith('//'): Url = 'http:' + Url 
            try: data = self.cm.getURLRequestData({ 'url': Url, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True })
            except:
                printDBG( 'Host getResolvedURL query error url: '+Url )
                return ''
            printDBG( 'Host listsItems data4: '+data )
            return self.cm.ph.getSearchGroups(data, '''src:  ['"]([^"^']+?)['"]''', 1, True)[0] 

        if 'popler' in url:
            printDBG( 'Host getResolvedURL mainurl: '+url )
            COOKIEFILE = os_path.join(GetCookieDir(), 'poplertv.cookie')
            self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
            self.HTTP_HEADER['Referer'] = 'http://www.popler.tv/live'
            self.HTTP_HEADER['X-Requested-With'] = 'XMLHttpRequest'
            self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.get_Page(url, self.defaultParams)
            if not sts: return valTab
            printDBG( 'Host listsItems data: '+data )
            data = self.cm.ph.getDataBeetwenMarkers(data, '<iframe', '/iframe>', False)[1].replace('\\','')
            #printDBG( 'Host listsItems data2: '+data )
            url = self.cm.ph.getSearchGroups(data, '''src=['"]([^"^']+?)['"]''', 1, True)[0] 
            if url.startswith('//'): url = 'http:' + url
            sts, data = self.get_Page(url, self.defaultParams)
            if not sts: return valTab
            printDBG( 'Host listsItems data3: '+data )
            videoUrl = self.cm.ph.getSearchGroups(data, '''src:  ['"]([^"^']+?)['"]''', 1, True)[0] 
            tmp = getDirectM3U8Playlist(videoUrl, checkContent=True, sortWithMaxBitrate=999999999)
            for item in tmp:
                return item['url']

            path = self.cm.ph.getSearchGroups(data, '''path = ['"]([^"^']+?)['"]''', 1, True)[0] 
            app = self.cm.ph.getSearchGroups(data, '''app = ['"]([^"^']+?)['"]''', 1, True)[0] 
            stream = self.cm.ph.getSearchGroups(data, '''stream = ['"]([^"^']+?)['"]''', 1, True)[0] 
            cdn = self.cm.ph.getSearchGroups(data, '''cdn = ['"]([^"^']+?)['"]''', 1, True)[0] 
            multi = self.cm.ph.getSearchGroups(data, '''multi = ['"]([^"^']+?)['"]''', 1, True)[0] 

            posturl = 'https://www.popler.tv/api/urlsign.php'
            postdata = {'path': path, 'app': app, 'stream': stream, 'cdn': cdn, 'multi': multi, 'dvr': '1', 'ile': '1'}
            sts, data = self.get_Page(posturl, self.defaultParams, postdata)
            if not sts: return valTab
            printDBG( 'Host listsItems data4: '+data )
            try:
                result = byteify(simplejson.loads(data))
                for item in result:
                    printDBG( 'Host listsItems data5: '+item )
                    if 'm3u8' in item: return item
            except Exception as e:
                printExc()
            return ''

        if url.startswith('http://www.rbl.tv'):
            printDBG( 'Host getResolvedURL mainurl: '+url )
            COOKIEFILE = os_path.join(GetCookieDir(), 'rbl.cookie')
            host = "Mozilla/5.0 (Linux; U; Android 4.1.1; en-us; androVM for VirtualBox ('Tablet' version with phone caps) Build/JRO03S) AppleWebKit/534.30 (KHTML, like Gecko) Version/4.0 Safari/534.30"
            header = {'Referer':url, 'User-Agent': host, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}   
            try: data = self.cm.getURLRequestData({ 'url': url, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True })
            except:
                printDBG( 'Host getResolvedURL query error url: '+url )
                return ''
            #printDBG( 'Host listsItems data1: '+data )
            data = self.cm.ph.getDataBeetwenMarkers(data, '<iframe', '</iframe>', False)[1]
            url = self.cm.ph.getSearchGroups(data, '''src=['"]([^"^']+?)['"]''', 1, True)[0] 
            if url.startswith('//'): url = 'http:' + url
            header = {'Referer':url, 'User-Agent': host, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}   
            try: data = self.cm.getURLRequestData({ 'url': url, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True })
            except:
                printDBG( 'Host getResolvedURL query error url: '+url )
                return ''
            #printDBG( 'Host listsItems data2: '+data )
            Url = self.cm.ph.getSearchGroups(data, '''src:  ['"]([^"^']+?)['"]''', 1, True)[0] 
            if Url.startswith('//'): Url = 'http:' + Url 
            if self.cm.isValidUrl(Url): 
                tmp = getDirectM3U8Playlist(Url)
                for item in tmp:
                    printDBG( 'Host listsItems valtab: '  +str(item))
                return item['url']

        if url.startswith('https://lookcam.'):
            printDBG( 'Host getResolvedURL mainurl: '+url )
            COOKIEFILE = os_path.join(GetCookieDir(), 'lookcam.cookie')
            self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.getPage(url, 'lookcam.cookie', 'lookcam.com', self.defaultParams)
            if not sts: return ''
            printDBG( 'Host listsItems data1: '+str(data) )
            Url = self.cm.ph.getSearchGroups(data, '''source\ssrc=['"]([^"^']+?)['"]''')[0] 
            if Url.startswith('//'): Url = 'https:' + Url 
            Url = urlparser.decorateUrl(Url, {'Referer': url, 'User-Agent':self.USER_AGENT})  
            if self.cm.isValidUrl(Url): 
                tmp = getDirectM3U8Playlist(Url)
                for item in tmp:
                    printDBG( 'Host listsItems valtab: '  +str(item))
                    return item['url']
            data = self.cm.ph.getDataBeetwenMarkers(data, '<iframe', '</iframe>', False)[1]
            url = self.cm.ph.getSearchGroups(data, '''src=['"]([^"^']+?)['"]''', 1, True)[0] 
            if url.startswith('//'): url = 'http:' + url
            if 'youtu' in url: return self.getResolvedURL(url)

            sts, data = self.getPage(url, 'lookcam.cookie', 'lookcam.com', self.defaultParams)
            if not sts: return ''
            printDBG( 'Host listsItems data2: '+str(data) )
            Url = self.cm.ph.getSearchGroups(data, '''source\ssrc=['"]([^"^']+?)['"]''')[0].replace('&amp;','&') 
            if Url.startswith('//'): Url = 'https:' + Url 
            Url = urlparser.decorateUrl(Url, {'Referer': url, 'User-Agent':self.USER_AGENT})  
            if self.cm.isValidUrl(Url): 
                tmp = getDirectM3U8Playlist(Url, checkContent=True)
                for item in tmp:
                    printDBG( 'Host listsItems valtab: '  +str(item))
                    return item['url']
            return ''

        if url.startswith('http://stanislaw-andrychow.pl'):
            printDBG( 'Host getResolvedURL mainurl: '+url )
            COOKIEFILE = os_path.join(GetCookieDir(), 'andrychow.cookie')
            self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.getPage(url, 'andrychow.cookie', 'andrychow.pl', self.defaultParams)
            if not sts: return ''
            printDBG( 'Host listsItems data1: '+str(data) )
            Url = self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0]
            if Url.startswith('//'): Url = 'http:' + Url
            if 'webcamera' in Url: return self.getResolvedURL(Url)
            sts, data = self.getPage(Url, 'andrychow.cookie', 'andrychow.pl', self.defaultParams)
            if not sts: return ''
            printDBG( 'Host listsItems data2: '+str(data) )
            
            m3u8_link = self.cm.ph.getSearchGroups(data, '''source:\s*['"]([^"^']+?)['"]''', 1, True)[0]
            if m3u8_link.startswith('//'): m3u8_link = 'http:' + m3u8_link
            m3u8_link = urlparser.decorateUrl(m3u8_link, {'Referer': url, 'User-Agent':self.USER_AGENT})  
            if self.cm.isValidUrl(m3u8_link): 
                tmp = getDirectM3U8Playlist(m3u8_link)
                for item in tmp:
                    printDBG( 'Host item: '+str(item) )
                    return item['url']

        if 'bg-gledai' in url: #url.startswith('http://www.bg-gledai.tv') or url.startswith('http://www.bg-gledai.me'):
            printDBG( 'Host getResolvedURL mainurl: '+url )
            COOKIEFILE = os_path.join(GetCookieDir(), 'gledai.cookie')
            host = "Mozilla/5.0 (Linux; U; Android 4.1.1; en-us; androVM for VirtualBox ('Tablet' version with phone caps) Build/JRO03S) AppleWebKit/534.30 (KHTML, like Gecko) Version/4.0 Safari/534.30"
            header = {'Referer':url, 'User-Agent': host, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}   
            try: data = self.cm.getURLRequestData({ 'url': url, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True })
            except Exception as e:
                printExc()
                #msg = _("Last error:\n%s" % str(e))
                #GetIPTVNotify().push('%s' % msg, 'error', 20)
                printDBG( 'Host listsItems query error url:'+url )
                return ''
            printDBG( 'Host listsItems data1: '+data )
            data = self.cm.ph.getDataBeetwenMarkers(data, '<iframe', '</iframe>', False)[1]
            printDBG( 'Host listsItems <iframe: '+data )

            Url = self.cm.ph.getSearchGroups(data, '''src=['"]([^"^']+?)['"]''', 1, True)[0] 
            printDBG( 'Host listsItems Url: '+Url )
            if Url:
                try: data = self.cm.getURLRequestData({ 'url': Url, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True })
                except Exception as e:
                    printExc()
                    #msg = _("Last error:\n%s" % str(e))
                    #GetIPTVNotify().push('%s' % msg, 'error', 20)
                    printDBG( 'Host listsItems query error url:'+url )
                    return ''
                printDBG( 'Host listsItems data2: '+data )
                Url = self.cm.ph.getSearchGroups(data, '''file:\s*['"]([^"^']+?)['"]''', 1, True)[0].replace('&amp;','&')
                if Url != '': return urlparser.decorateUrl(Url, {'User-Agent': host})

                data = re.sub("document\.write\(unescape\('([^']+?)'\)", lambda m: urllib.unquote(m.group(1)), data) 
                printDBG( 'Host listsItems data3: '+data )
                Url = self.cm.ph.getSearchGroups(data, '''playlist:  unescape\(['"]([^"^']+?)['"]''', 1, True)[0]
                if not Url: Url = self.cm.ph.getSearchGroups(data, '''src=['"]([^"^']+?)['"]''', 1, True)[0].replace('http://nullrefer.com/?','')
                if Url:
                    Url = urllib2.unquote(Url)
                    try: data = self.cm.getURLRequestData({ 'url': Url, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True })
                    except Exception as e:
                        printExc()
                        #msg = _("Last error:\n%s" % str(e))
                        #GetIPTVNotify().push('%s' % msg, 'error', 20)
                        printDBG( 'Host listsItems query error url:'+url )
                        return ''
                    printDBG( 'Host listsItems data4: '+data )
                    Url = self.cm.ph.getSearchGroups(data, '''file>([^"^']+?)<''', 1, True)[0].replace('&amp;','&')
                    if not Url: Url = self.cm.ph.getSearchGroups(data, '''file=['"]([^"^']+?)['"]''', 1, True)[0].replace('&amp;','&')
                    return urlparser.decorateUrl(Url, {'User-Agent': host})


            return ''

        if url.startswith('https://www.djing.com'):
            printDBG( 'Host getResolvedURL mainurl: '+url )
            if self.cm.isValidUrl(url): 
                tmp = getDirectM3U8Playlist(url)
                for item in tmp:
                    printDBG( 'Host item: '+str(item) )
                return urlparser.decorateUrl(item['url'], {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 5_0 like Mac OS X) AppleWebKit/534.46 (KHTML, like Gecko) Version/5.1 Mobile/9A334 Safari/7534.48.3'})

        if url.startswith('http://oklivetv.com'):
            printDBG( 'Host getResolvedURL mainurl: '+url )
            COOKIEFILE = os_path.join(GetCookieDir(), 'oklivetv.cookie')
            host = "Mozilla/5.0 (Linux; U; Android 4.1.1; en-us; androVM for VirtualBox ('Tablet' version with phone caps) Build/JRO03S) AppleWebKit/534.30 (KHTML, like Gecko) Version/4.0 Safari/534.30"
            header = {'User-Agent': host, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}   
            try: data = self.cm.getURLRequestData({ 'url': url, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True })
            except:
                printDBG( 'Host getResolvedURL query error url: '+url )
                return ''
            printDBG( 'Host getResolvedURL data: '+data )
            if "eval(function(p,a,c,k,e,d)" in data:
                printDBG( 'Host resolveUrl packed' )
                packed = re.compile('>eval\(function\(p,a,c,k,e,d\)(.+?)</script>', re.DOTALL).findall(data)
                if packed:
                    data2 = packed[-1]
                else:
                    return ''
                printDBG( 'Host data4: '+str(data2) )
                try:
                    videoUrl = unpackJSPlayerParams(data2, TEAMCASTPL_decryptPlayerParams, 0, True, True) 
                except Exception: printExc()
                printDBG( 'Host videoUrl: '+str(videoUrl) )
                videoUrl = self.cm.ph.getSearchGroups(videoUrl, '''x-mpegURL","src":['"]([^"^']+?)['"]''', 1, True)[0] 
                videoUrl = videoUrl.replace('$','%24')
                if 'm3u8' in videoUrl: 
                    videoUrl = urlparser.decorateUrl(videoUrl, {'iptv_proto':'m3u8'})
                if videoUrl: return videoUrl
            videoUrl = self.cm.ph.getSearchGroups(data, '''id="tab1.*?href=['"]([^"^']+?)['"]''')[0].replace('&amp;','&')
            if videoUrl.startswith('tabs'): videoUrl = 'http://oklivetv.com/xplay/' + videoUrl
            printDBG( 'Host videoUrl tabs: '+str(videoUrl) )
            try: data = self.cm.getURLRequestData({ 'url': videoUrl, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': False, 'load_cookie': True, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True })
            except:
                printDBG( 'Host getResolvedURL query error url: '+url )
                videoUrl = self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''')[0] 
                return self.getResolvedURL(videoUrl)
            printDBG( 'Host listsItems data3: '+data )
            if "eval(function(p,a,c,k,e,d)" in data:
                printDBG( 'Host resolveUrl packed' )
                packed = re.compile('>eval\(function\(p,a,c,k,e,d\)(.+?)</script>', re.DOTALL).findall(data)
                if packed:
                    data2 = packed[-1]
                else:
                    return ''
                printDBG( 'Host data4: '+str(data2) )
                try:
                    videoUrl = unpackJSPlayerParams(data2, TEAMCASTPL_decryptPlayerParams, 0, True, True) 
                    printDBG( 'OK4: ')
                except Exception: pass 
                printDBG( 'Host videoUrl: '+str(videoUrl) )
                videoUrl = self.cm.ph.getSearchGroups(videoUrl, '''x-mpegURL","src":['"]([^"^']+?)['"]''', 1, True)[0] 
                if videoUrl: return videoUrl
            videoUrl = self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''')[0] 
            if videoUrl: return self.getResolvedURL(videoUrl)
            return ''

        if url.startswith('http://animallive.tv'):
            printDBG( 'Host getResolvedURL mainurl: '+url )
            COOKIEFILE = os_path.join(GetCookieDir(), 'animallive.cookie')
            host = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
            header = {'Referer':url, 'User-Agent': host, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}   
            try: data = self.cm.getURLRequestData({ 'url': url, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True })
            except:
                printDBG( 'Host getResolvedURL query error url: '+url )
                return valTab
            #printDBG( 'Host listsItems data1: '+data )
            tmp = self.up.getAutoDetectedStreamLink(url) 
            for item in tmp:
                if self.cm.isValidUrl(item['url']): return item['url']
            if not tmp:
                link = self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''')[0] 
                msg = self.cm.ph.getDataBeetwenMarkers(data, '<div class="alert  alert-info">', '</div>', False)[1]
                if not msg and not link: msg='Brak poprawnych linków'
                GetIPTVNotify().push('%s' % (self._cleanHtmlStr(msg)), 'info', 10) 
                if link: return self.getResolvedURL(link)
            return ''

        if url.startswith('http://www.lasy.gov.pl'):
            COOKIEFILE = os_path.join(GetCookieDir(), 'lasy.cookie')
            self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
            self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.get_Page(url)
            if not sts: return valTab
            printDBG( 'Host listsItems data1: '+data )
            link = self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''')[0] 
            sts, data = self.get_Page(link)
            if not sts: return valTab
            printDBG( 'Host listsItems data2: '+data )
            m3u8 = self.cm.ph.getSearchGroups(data, '''var src = ['"]([^"^']+?)['"]''')[0] 
            return m3u8

        if url.startswith('http://gemenczrt.hu'):
            COOKIEFILE = os_path.join(GetCookieDir(), 'gemenczrt.cookie')
            self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
            self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.get_Page(url)
            if not sts: return valTab
            printDBG( 'Host listsItems data1: '+data )
            link = self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''')[0] 
            sts, data = self.get_Page(link)
            if not sts: return valTab
            printDBG( 'Host listsItems data2: '+data )
            camid = self.cm.ph.getSearchGroups(data, '''var camid = ['"]([^"^']+?)['"]''')[0] 
            playerid = self.cm.ph.getSearchGroups(data, '''var playerid = ['"]([^"^']+?)['"]''')[0] 
            token = self.cm.ph.getSearchGroups(data, '''var token = ['"]([^"^']+?)['"]''')[0] 
            link = "https://stream-infocam.infornax.hu/?action=get_init_tid_pid&camid="+camid+"&playerid="+playerid+"&token="+token
            sts, data = self.get_Page(link)
            if not sts: return valTab
            printDBG( 'Host listsItems data3: '+data )
            pid = self.cm.ph.getSearchGroups(data, '''pid":['"]([^"^']+?)['"]''')[0] 
            tid = self.cm.ph.getSearchGroups(data, '''tid":['"]([^"^']+?)['"]''')[0] 
            videoUrl = 'https://s'+pid+'infocam.infornax.hu/t'+tid+'/nv/'+camid+'/playlist.m3u8'
            if self.cm.isValidUrl(videoUrl): 
                tmp = getDirectM3U8Playlist(videoUrl, checkContent=True, sortWithMaxBitrate=999999999)
                for item in tmp:
                    printDBG( 'Host item: '+str(item) )
                    return item['url']
            return videoUrl

        if url.startswith('http://www.bociany.przygodzice.pl/'):
            printDBG( 'Host getResolvedURL mainurl: '+url )
            baseUrl = 'http://www.bociany.przygodzice.pl/'
            COOKIEFILE = os_path.join(GetCookieDir(), 'animallive.cookie')
            host = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
            header = {'Referer':url, 'User-Agent': host, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}   
            try: data = self.cm.getURLRequestData({ 'url': url, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True })
            except:
                printDBG( 'Host getResolvedURL query error url: '+url )
                return valTab
            printDBG( 'Host listsItems data1: '+data )
            if 'player-nadaje-com' in data:
                tmpUrl = self.cm.ph.getDataBeetwenNodes(data, ('<script', '>', 'player-nadaje-com'), ('</script', '>'))[1]
                tmpUrl = self.cm.ph.getSearchGroups(tmpUrl, """player\-id=['"]([^'^"]+?)['"]""")[0]
                videoUrl = 'https://nadaje.com/api/1.0/services/video/%s/' % tmpUrl
                videoUrl = strwithmeta(videoUrl, {'Referer':baseUrl})
                printDBG( 'Host videoUrl: %s' % videoUrl )
                return self.getResolvedURL(videoUrl)
            return ''

        if 'nadaje.com' in url:
            baseUrl = strwithmeta(url)
            referer = baseUrl.meta.get('Referer', baseUrl)
            origin = self.cm.getBaseUrl(referer)[:-1]
            USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
            HEADER = {'User-Agent':USER_AGENT, 'Accept':'*/*', 'Content-Type':'application/json', 'Accept-Encoding':'gzip, deflate', 'Referer':referer, 'Origin':origin}
            videoId = self.cm.ph.getSearchGroups(baseUrl + '/', '''/video/([0-9]+?)/''')[0]
        
            sts, data = self.cm.getPage('https://nadaje.com/api/1.0/services/video/%s/' % videoId, {'header': HEADER})
            if not sts: return False
            printDBG( 'Host listsItems data1: '+data )
            videoUrl = self.cm.ph.getSearchGroups(data, """hls": ['"]([^'^"]+?)['"]""")[0]
            return videoUrl
        
        if url.startswith('https://www.looduskalender.ee'):
            COOKIEFILE = os_path.join(GetCookieDir(), 'looduskalender.cookie')
            mainUrl = 'https://www.looduskalender.ee'
            self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.getPage(url, 'looduskalender.cookie', 'looduskalender.ee', self.defaultParams)
            if not sts: return ''
            if '/node/4090' in url: return self.getResolvedURL('https://www.youtube.com/channel/UCqCNelAJXWj7feiEBY2fsCA/live')
            printDBG( 'Host listsItems data1: '+data )
            videoUrl = self.cm.ph.getSearchGroups(data, '''(https://www.youtube.com/watch[^"^']+?)['"]''', 1, True)[0] 
            if len(videoUrl)>10: return self.getResolvedURL(videoUrl)
            videoUrl = self.cm.ph.getSearchGroups(data, '''(https://youtu.be[^"^']+?)['"]''', 1, True)[0] 
            if len(videoUrl)>10: return self.getResolvedURL(videoUrl)
            return ''

        if url.startswith('https://tv.eenet.ee'):
            printDBG( 'Host getResolvedURL mainurl: '+url )
            COOKIEFILE = os_path.join(GetCookieDir(), 'animalestonia.cookie')
            host = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
            header = {'Referer':url, 'User-Agent': host, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}   
            try: data = self.cm.getURLRequestData({ 'url': url, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True })
            except:
                printDBG( 'Host getResolvedURL query error url: '+url )
                return valTab
            printDBG( 'Host listsItems data1: '+data )
            hls = self.cm.ph.getSearchGroups(data, '''loadSource\(['"]([^"^']+?)['"]''', 1, True)[0] 
            Url = 'http://tv.eenet.ee'+hls
            if self.cm.isValidUrl(Url): 
                tmp = getDirectM3U8Playlist(Url)
                for item in tmp:
                    printDBG( 'Host item: '+str(item) )
                    return item['url']
            return ''

        if url.startswith('https://zoo.sandiegozoo.org') or url.startswith('https://sdzsafaripark.org'):
            printDBG( 'Host getResolvedURL mainurl: '+url )
            COOKIEFILE = os_path.join(GetCookieDir(), 'sandiegozoo.cookie')
            self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.getPage(url, 'sandiegozoo.cookie', 'sandiegozoo.org', self.defaultParams)
            if not sts: return ''
            printDBG( 'Host listsItems data1: '+str(data) )
            data = ph.IFRAME.findall(data)
            for item in data:
                Url = self.cm.getFullUrl(item[1]).replace('&amp;','&')
                if 'google' in Url: continue
                if 'Stream' in Url: break
            sts, data = self.getPage(Url, 'sandiegozoo.cookie', 'sandiegozoo.org', self.defaultParams)
            if not sts: return ''
            printDBG( 'Host listsItems data2: '+str(data) )
            Url = self.cm.ph.getSearchGroups(data, '''src=['"]([^"^']+?\.m3u8)['"]''', 1, True)[0].replace('&amp;','&')
            if self.cm.isValidUrl(Url): 
                tmp = getDirectM3U8Playlist(Url, checkContent=True, sortWithMaxBitrate=999999999)
                for item in tmp:
                    return item['url']
            return ''

        if url.startswith('http://www.cieszyn.pl'):
            printDBG( 'Host getResolvedURL mainurl: '+url )
            COOKIEFILE = os_path.join(GetCookieDir(), 'cieszyn.cookie')
            self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.getPage(url, 'cieszyn.cookie', 'cieszyn.pl', self.defaultParams)
            if not sts: return ''
            printDBG( 'Host listsItems data1: '+str(data) )
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<iframe', '>')
            for item in data:
                url1 = self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''', 1, True)[0] 
                query_data = {'url': url1, 'use_host': False, 'use_cookie': False, 'use_post': False, 'return_data': True}
                try:
                    data = self.cm.getURLRequestData(query_data)
                except:
                    return ''
                printDBG( 'Host listsItems data2'+data )
                data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<iframe', '>')
                for item in data:
                    url2 = self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''', 1, True)[0] 
                    query_data = {'url': url2, 'use_host': False, 'use_cookie': False, 'use_post': False, 'return_data': True}
                    try:
                        data = self.cm.getURLRequestData(query_data)
                    except:
                        return ''
                    printDBG( 'Host listsItems data3'+data )
                    m3u8_url = self.cm.ph.getSearchGroups(data, '''source:\s['"]([^"^']+?)['"]''', 1, True)[0]
                    return urlparser.decorateUrl(m3u8_url, {'Referer': url2, 'Origin':'http://stream360.pl'})
                    if self.cm.isValidUrl(m3u8_url): 
                        tmp = getDirectM3U8Playlist(m3u8_url)
                        for item in tmp:
                            return item['url']
            return ''

        if 'ceskatelevize.cz' in url:
            printDBG( 'Host getResolvedURL mainurl: '+url )
            COOKIEFILE = os_path.join(GetCookieDir(), 'ceska.cookie')
            host = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
            header = {'Referer':url, 'User-Agent': host, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}   
            try: data = self.cm.getURLRequestData({ 'url': url, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True })
            except:
                printDBG( 'Host getResolvedURL query error url: '+url )
                return valTab
            printDBG( 'Host listsItems data1: '+data )
            player = self.cm.ph.getSearchGroups(data, '''(ivysilani/embed/iFramePlayer[^"^']+?)['"]''', 1, True)[0].replace('&amp;', '&')
            if 'hash' not in player:
                player = 'http://ceskatelevize.cz/' + player
                player = player + '&hash=' + self.cm.ph.getSearchGroups(data, '''hash:['"]([^"^']+?)['"]''', 1, True)[0]
            else:
                player = 'http://ceskatelevize.cz/' + player
            header = {'Referer':player, 'User-Agent': host, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}   
            try: data = self.cm.getURLRequestData({ 'url': player, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True })
            except:
                printDBG( 'Host getResolvedURL query error url: '+url )
                return valTab
            printDBG( 'Host listsItems data2: '+data )
            type = self.cm.ph.getSearchGroups(data, '''"type":['"]([^"^']+?)['"]''', 1, True)[0]
            id = self.cm.ph.getSearchGroups(data, '''"id":['"]([^"^']+?)['"]''', 1, True)[0]
            postdata = {
            'playlist[0][type]': type,
            'playlist[0][id]': id,
            'requestUrl': '/ivysilani/embed/iFramePlayerCT24.php',
            'requestSource': 'iVysilani',
            'type': 'html'}
            header = {'User-Agent': host, 'x-addr': '127.0.0.1', 'Accept':'text/html,application/xhtml+xml,application/xml,application/json','Accept-Language':'en,en-US;q=0.7,en;q=0.3','X-Requested-With':'XMLHttpRequest'} 
            query_data = { 'url': 'http://www.ceskatelevize.cz/ivysilani/ajax/get-client-playlist', 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': True, 'return_data': True }
            try:
                data = self.cm.getURLRequestData(query_data, postdata)
            except:
                printDBG( 'Parser error: ' ) 
                return ''
            printDBG( 'Parser: '+data ) 
            Url = self.cm.ph.getSearchGroups(data, '''"url":['"]([^"^']+?)['"]''', 1, True)[0].replace('\/','/') 
            try: data = self.cm.getURLRequestData({ 'url': Url, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True })
            except:
                printDBG( 'Host getResolvedURL query error url: '+Url )
                return valTab
            printDBG( 'Host listsItems data3: '+data )
            Url = self.cm.ph.getSearchGroups(data, '''"main":['"]([^"^']+?)['"]''', 1, True)[0].replace('\/','/')
            Url = urlparser.decorateUrl(Url, {'iptv_proto':'m3u8', 'User-Agent': host})
            item = []
            tmp =  getDirectM3U8Playlist(Url, checkExt=False)
            for item in tmp:
                printDBG( 'Host item: '+str(item) )
            return item['url']


        if url.startswith('http://embed.livebox.cz/ta3/'):
            printDBG( 'Host getResolvedURL mainurl: '+url )
            COOKIEFILE = os_path.join(GetCookieDir(), 'ta3.cookie')
            host = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
            header = {'Referer':url, 'User-Agent': host, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}   
            try: data = self.cm.getURLRequestData({ 'url': url, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True })
            except:
                printDBG( 'Host getResolvedURL query error url: '+url )
                return valTab
            printDBG( 'Host listsItems data1: '+data )
            m3u8_src = self.cm.ph.getSearchGroups(data, '''src" : ['"]([^"^']+?)['"]''')[0] 
            if m3u8_src.startswith('//'): m3u8_src = 'http:' + m3u8_src
            if self.cm.isValidUrl(m3u8_src): 
                tmp = getDirectM3U8Playlist(m3u8_src)
                for item in tmp:
                    printDBG( 'Host item: '+str(item) )
                    if item['with']==1280: return item['url']
                return item['url']

        if url.startswith('http://media.aniolbeskidow.pl'):
            printDBG( 'Host getResolvedURL mainurl: '+url )
            COOKIEFILE = os_path.join(GetCookieDir(), 'andrychowopoka.cookie')
            host = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
            header = {'Referer':url, 'User-Agent': host, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}   
            try: data = self.cm.getURLRequestData({ 'url': url, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True })
            except:
                printDBG( 'Host getResolvedURL query error url: '+url )
                return valTab
            printDBG( 'Host listsItems data1: '+data )
            rtmp = self.cm.ph.getSearchGroups(data, '''['"](rtmp[^"^']+?)['"]''')[0] 
            if rtmp: return rtmp+' playpath=livestream_str1 swfUrl=http://media.aniolbeskidow.pl/swf/player.swf live=1 pageUrl='+url

        if url.startswith('https://wtkplay.pl'):
            printDBG( 'Host getResolvedURL mainurl: '+url )
            COOKIEFILE = os_path.join(GetCookieDir(), 'wtk.cookie')
            host = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
            header = {'Referer':url, 'User-Agent': host, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}   
            try: data = self.cm.getURLRequestData({ 'url': url, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True })
            except:
                printDBG( 'Host getResolvedURL query error url: '+url )
                return valTab
            printDBG( 'Host listsItems data1: '+data )
            url = self.cm.ph.getSearchGroups(data, '''"embedURL" content=['"]([^"^']+?)['"]''')[0].replace('&amp;','&')
            header = {'Referer':url, 'User-Agent': host, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}   
            try: data = self.cm.getURLRequestData({ 'url': url, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True })
            except:
                printDBG( 'Host getResolvedURL query error url: '+url )
                return valTab
            printDBG( 'Host listsItems data2: '+data )
            videoUrl = self.cm.ph.getSearchGroups(data, '''src:\s['"]([^"^']+?\.m3u8)['"]''')[0].replace('&amp;','&')
            if self.cm.isValidUrl(videoUrl): 
                tmp = getDirectM3U8Playlist(videoUrl)
                for item in tmp:
                    printDBG( 'Host item: '+str(item) )
                if self.cm.isValidUrl(item['url']): return item['url']

        if url.startswith('http://www.earthtv.com'):
            COOKIEFILE = os_path.join(GetCookieDir(), 'earthtv.cookie')
            self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.getPage(url, 'earthtv.cookie', 'earthtv.com', self.defaultParams)
            if not sts: return ''
            printDBG( 'Host listsItems data1: '+str(data) )
            Url = self.cm.ph.getSearchGroups(data, '''livesd=([^"^']+?)token''', 1, True)[0]
            token = self.cm.ph.getSearchGroups(data, '''token=([^"^']+?)&''', 1, True)[0]
            if Url.startswith('//'): Url = 'http:' + Url
            printDBG( 'Host Url: '+Url )
            #return Url+token
            m3u8 = self.cm.ph.getSearchGroups(data, '''livesd=([^"^']+?)['"]''', 1, True)[0]
            player = self.cm.ph.getSearchGroups(data, '''embedURL" content=['"]([^"^']+?)['"]''', 1, True)[0]
            #printDBG( 'Host m3u8: '+m3u8 )
            #printDBG( 'Host player: '+player )
            videoUrl = urlparser.decorateUrl(m3u8, {'Referer': player, 'Origin':'https://playercdn.earthtv.com'})
            if self.cm.isValidUrl(videoUrl): 
                tmp = getDirectM3U8Playlist(videoUrl, checkContent=True, sortWithMaxBitrate=999999999)
                for item in tmp:
                    printDBG( 'Host item: '+str(item) )
                    return item['url']
            return ''

        if url.startswith('http://live.russia.tv'):
            COOKIEFILE = os_path.join(GetCookieDir(), 'russiatv.cookie')
            self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.getPage(url, 'russiatv.cookie', 'russia.tv', self.defaultParams)
            if not sts: return ''
            printDBG( 'Host listsItems data1: '+str(data) )
            url = self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''')[0] 
            sts, data = self.getPage(url, 'russiatv.cookie', 'russia.tv', self.defaultParams)
            if not sts: return ''
            printDBG( 'Host listsItems data: '+data )
            Url = self.cm.ph.getSearchGroups(data, '''"m3u8":['"]([^"^']+?)['"]''')[0]
            return Url

        if url.startswith('http://www.glaz.tv'):
            printDBG( 'Host getResolvedURL mainurl: '+url )
            COOKIEFILE = os_path.join(GetCookieDir(), 'glaz.cookie')
            host = "Mozilla/5.0 (Linux; U; Android 4.1.1; en-us; androVM for VirtualBox ('Tablet' version with phone caps) Build/JRO03S) AppleWebKit/534.30 (KHTML, like Gecko) Version/4.0 Safari/534.30"
            header = {'Referer':url, 'User-Agent': host, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}   
            try: data = self.cm.getURLRequestData({ 'url': url, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True })
            except:
                printDBG( 'Host getResolvedURL query error url: '+url )
                return ''
            printDBG( 'Host listsItems data1: '+data )
            Url = self.cm.ph.getSearchGroups(data, '''url: ['"]([^"^']+?)['"]''')[0]
            Sign = self.cm.ph.getSearchGroups(data, '''signature = ['"]([^"^']+?)['"]''')[0]
            return Url+Sign 

        if url.startswith('http://stream.1tv.ru'):
            printDBG( 'Host getResolvedURL mainurl: '+url )
            COOKIEFILE = os_path.join(GetCookieDir(), '1tv.cookie')
            host = "Mozilla/5.0 (Linux; U; Android 4.1.1; en-us; androVM for VirtualBox ('Tablet' version with phone caps) Build/JRO03S) AppleWebKit/534.30 (KHTML, like Gecko) Version/4.0 Safari/534.30"
            header = {'Referer':'http://www.glaz.tv', 'User-Agent': host, 'Accept':'text/html,application/xhtml+xml,application/xml,application/json','Accept-Language':'en,en-US;q=0.7,en;q=0.3','X-Requested-With':'XMLHttpRequest'} 
            query_data = { 'url': url, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': True, 'return_data': True }
            try:
                data = self.cm.getURLRequestData(query_data)
            except:
                printDBG( 'Parser error: ' ) 
                return ''
            printDBG( 'Parser: '+data ) 
            try:
                result = simplejson.loads('['+data+']')
                if result:
                    for item in result:
                        url = str(item["hls"][1])  
            except:
                printDBG( 'Host listsItems ERROR JSON' )
                return ''
            printDBG( 'url: '+url ) 
            return url

        if url.startswith('http://www.lodz.lasy.gov.pl'):
            printDBG( 'Host getResolvedURL mainurl: '+url )
            COOKIEFILE = os_path.join(GetCookieDir(), 'czarnybocian.cookie')
            host = "Mozilla/5.0 (Linux; U; Android 4.1.1; en-us; androVM for VirtualBox ('Tablet' version with phone caps) Build/JRO03S) AppleWebKit/534.30 (KHTML, like Gecko) Version/4.0 Safari/534.30"
            header = {'Referer':url, 'User-Agent': host, 'Accept':'text/html,application/xhtml+xml,application/xml,application/json','Accept-Language':'en,en-US;q=0.7,en;q=0.3','X-Requested-With':'XMLHttpRequest'} 
            query_data = { 'url': url, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': True, 'return_data': True }
            try:
                data = self.cm.getURLRequestData(query_data)
            except:
                printDBG( 'error: '+url ) 
                return ''
            #printDBG( 'data1: '+data ) 
            url = self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''')[0] 
            header = {'Referer':url, 'User-Agent': host, 'Accept':'text/html,application/xhtml+xml,application/xml,application/json','Accept-Language':'en,en-US;q=0.7,en;q=0.3','X-Requested-With':'XMLHttpRequest'} 
            query_data = { 'url': url, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': True, 'return_data': True }
            try:
                data = self.cm.getURLRequestData(query_data)
            except:
                printDBG( 'error: '+url ) 
                return ''
            printDBG( 'data2: '+data ) 
            return self.cm.ph.getSearchGroups(data, '''var\ssrc\s=\s['"]([^"^']+?)['"]''')[0] 

        if url.startswith('http://sblinternet.pl'):
            printDBG( 'Host getResolvedURL mainurl: '+url )
            COOKIEFILE = os_path.join(GetCookieDir(), 'sbl.cookie')
            self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
            self.HTTP_HEADER['Referer'] = url
            self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.get_Page(url)
            if not sts: return ''
            #printDBG( 'Host listsItems data: '+data )

            data2 = self.cm.ph.getDataBeetwenMarkers(data, 'camerastream', '</div>', False)[1]
            url = self.cm.ph.getSearchGroups(data2, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''')[0].replace('&amp;','&') 
            if not url: 
                videoUrl = self.cm.ph.getSearchGroups(data, '''"sourceURL":['"]([^"^']+?)['"]''')[0] 
                return urllib2.unquote(videoUrl)
            sts, data = self.get_Page(url)
            if not sts: return ''
            printDBG( 'Host listsItems data2: '+data )
            app = self.cm.ph.getSearchGroups(data, '''var app = ['"]([^"^']+?)['"]''')[0] 
            if not app: app = 'live'
            cam = self.cm.ph.getSearchGroups(data, '''var cam = ['"]([^"^']+?)['"]''')[0] 
            if not cam: cam = url.split('cam=')[-1] 

            #videoUrl = self.cm.ph.getSearchGroups(data, '''source: ['"]([^"^']+?)['"]''')[0]
            videoUrl = re.findall('source: "(.*?)"', data, re.S)
            if videoUrl: 
                videoUrl = videoUrl[-1]
            else:
                return ''
            if 'm3u8' in videoUrl: return videoUrl
            videoUrl = videoUrl + app +'/'+ cam + "/playlist.m3u8"
            printDBG( 'Host listsItems app: '+app )
            printDBG( 'Host listsItems cam: '+cam )
            printDBG( 'Host listsItems videoUrl: '+videoUrl )
            if videoUrl.startswith('//'): return 'http:' + videoUrl
            if self.cm.isValidUrl(videoUrl): 
                tmp = getDirectM3U8Playlist(videoUrl, checkContent=True, sortWithMaxBitrate=999999999)
                for item in tmp:
                    printDBG( 'Host item: '+str(item) )
                    return item['url']
            return ''

        if url.startswith('https://przelom.pl'):
            printDBG( 'Host getResolvedURL mainurl: '+url )
            COOKIEFILE = os_path.join(GetCookieDir(), 'przelom.cookie')
            host = "Mozilla/5.0 (Linux; U; Android 4.1.1; en-us; androVM for VirtualBox ('Tablet' version with phone caps) Build/JRO03S) AppleWebKit/534.30 (KHTML, like Gecko) Version/4.0 Safari/534.30"
            header = {'Referer':url, 'User-Agent': host, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}   
            try: data = self.cm.getURLRequestData({ 'url': url, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True })
            except:
                printDBG( 'Host getResolvedURL query error url: '+url )
                return ''
            printDBG( 'Host listsItems data1: '+data )
            #data2 = self.cm.ph.getDataBeetwenMarkers(data, 'camerastream', '</div>', False)[1]
            url = self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"](https://przelom.pl[^"^']+?)['"]''')[0] 
            header = {'Referer':url, 'User-Agent': host, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}   
            try: data = self.cm.getURLRequestData({ 'url': url, 'header': header, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True })
            except:
                printDBG( 'Host getResolvedURL query error url: '+url )
                return ''
            printDBG( 'Host listsItems data2: '+data )
            Url = self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''')[0] 
            if Url.startswith('//'): Url = 'http:' + Url
            if Url: return self.getResolvedURL(Url)
            data = self.cm.ph.getDataBeetwenMarkers(data, '<video>', '</video>', False)[1]
            Url = self.cm.ph.getSearchGroups(data, '''src=['"]([^"^']+?)['"]''')[0] 
            if Url.startswith('//'): Url = 'http:' + Url
            return Url

        if url.endswith('.mp4'):
            return url

        if url.endswith('.m3u8'):
            tmp = getDirectM3U8Playlist(url, checkContent=True, sortWithMaxBitrate=999999999)
            for item in tmp:
               return item['url']
            return ''

        videoUrls = self.getLinksForVideo(url)
        if videoUrls:
           for item in videoUrls:
              Url = item['url']
              Name = item['name']
              printDBG( 'Host Url:  '+Url )
              printDBG( 'Host name:  '+Name )
              if len(Url)>8: return Url

        if 'assisi' in url:
            printDBG( 'Host getResolvedURL mainurl: '+url )
            COOKIEFILE = os_path.join(GetCookieDir(), 'skylinewebcams.cookie')
            try: data = self.cm.getURLRequestData({ 'url': url, 'use_host': False, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': COOKIEFILE, 'use_post': False, 'return_data': True })
            except:
                printDBG( 'Host listsItems query error cookie' )
                return ''
            #printDBG( 'Host listsItems data: '+data )
            return self.cm.ph.getSearchGroups(data, '''url:['"]([^"^']+?)['"]''', 1, True)[0]

        if 'hdontap' in url:
            printDBG( 'Host getResolvedURL mainurl: '+url )
            COOKIEFILE = os_path.join(GetCookieDir(), 'hdontap.cookie')
            self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
            self.HTTP_HEADER['Referer'] = url
            ref = base64.b64encode(url)
            self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.getPage(url, 'hdontap.cookie', 'hdontap.com', self.defaultParams)
            if not sts: return ''
            printDBG( 'Host listsItems data1: '+str(data) )
            url = self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"](//[^"^']+?)['"]''')[0] 
            if url.startswith('//'): url = 'https:' + url
            printDBG( 'Host url: '+str(url) )
            if url.startswith('https://www.youtube.com/'):
                return self.getResolvedURL(url)
            self.HTTP_HEADER['Referer'] = url
            self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            stream = self.cm.ph.getSearchGroups(data, '''stream=([^"^']+?)[&"]''')[0] 
            Url = 'https://portal.hdontap.com/backend/embed/%s?r=%s' % (stream, ref)
            printDBG( 'Host Url: '+str(Url) )
            sts, data = self.getPage(Url, 'hdontap.cookie', 'hdontap.com', self.defaultParams)
            if not sts: return ''
            data = urllib.unquote(base64.b64decode(data))
            printDBG( 'Host listsItems data2: '+str(data) )
            videoUrl = self.cm.ph.getSearchGroups(data, '''streamSrc":['"]([^"^']+?)['"]''')[0].replace(r'\n','')
            if self.cm.isValidUrl(videoUrl): 
                tmp = getDirectM3U8Playlist(videoUrl)
                for item in tmp:
                    printDBG( 'Host item: '+str(item) )
                if self.cm.isValidUrl(item['url']): return item['url']
            return ''

        if url.startswith('http://tivix.co'):
            COOKIEFILE = os_path.join(GetCookieDir(), 'tivix.cookie')
            self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            for x in range(1, 100): 
                sts, data = self.getPage(url, 'tivix.cookie', 'tivix.co', self.defaultParams)
                if not sts: return ''
                #printDBG( 'Host listsItems data1: '+str(data) )
                firstIpProtect = self.cm.ph.getSearchGroups(data, '''var firstIpProtect = ['"]([^"^']+?)['"]''', 1, True)[0]
                secondIpProtect = self.cm.ph.getSearchGroups(data, '''var secondIpProtect = ['"]([^"^']+?)['"]''', 1, True)[0]
                portProtect = self.cm.ph.getSearchGroups(data, '''var portProtect = ['"]([^"^']+?)['"]''', 1, True)[0]
                m3u8_url = self.cm.ph.getSearchGroups(data, '''file:['"]([^"^']+?)['"]''', 1, True)[0].replace('#2','')
                if m3u8_url:
                    printDBG( 'Host m3u8_url:'+m3u8_url )
                    link = m3u8_url.split('//')
                    m3u8_url = ''
                    wynik = ''

                    for part in link:
                        printDBG( 'Host part:%s %s' % (part, str(len(part))) )
                        if part.startswith('a'): wynik += part
                        elif 'MzE0' in part: 
                            MzE0 = re.sub('.+MzE0', '', part)
                            wynik += MzE0
                            printDBG( 'Host MzNm-MzE0:%s %s' % (MzE0, str(len(part))) )
                        elif '3zE0' in part: 
                            E03z = re.sub('.+3zE0', '', part)
                            wynik += E03z
                            printDBG( 'Host MzNm-3zE0:%s %s' % (E03z, str(len(part))) )
                        elif 'N2Zh' in part: 
                            N2Zh = re.sub('.+N2Zh', '', part)
                            wynik += N2Zh
                            printDBG( 'Host M2Q-N2Zh:%s ' % N2Zh )
                        elif 'ZmQ0' in part: 
                            ZmQ0 = re.sub('.+ZmQ0', '', part)
                            wynik += ZmQ0
                            printDBG( 'Host Y2-ZmQ0:%s %s' % (ZmQ0, str(len(part))) )
                        elif 'OWQ3' in part: 
                            OWQ3 = re.sub('.+OWQ3', '', part)
                            wynik += OWQ3
                            printDBG( 'Host MzNm-OWQ3:%s %s' % (OWQ3, str(len(part))) )
                    printDBG( 'Host wynik:'+wynik )

                    try:
                        m3u8_url = urllib.unquote(base64.b64decode(wynik))
                    except:
                        printDBG( 'nie ma' )
                    printDBG( 'Host m3u8_url po:'+m3u8_url )
                    m3u8_url = m3u8_url.replace(r'{v3}',portProtect).replace(r'{v2}', secondIpProtect)
                    m3u8_url = urlparser.decorateUrl(m3u8_url, {'Referer': url})
                    if self.cm.isValidUrl(m3u8_url):
                        tmp = getDirectM3U8Playlist(m3u8_url, checkContent=True, sortWithMaxBitrate=999999999)
                        if not tmp:
                            m3u8_url = m3u8_url.replace(secondIpProtect,firstIpProtect)
                            m3u8_url = urlparser.decorateUrl(m3u8_url, {'Referer': url})
                            if self.cm.isValidUrl(m3u8_url):
                                tmp = getDirectM3U8Playlist(m3u8_url, checkContent=True, sortWithMaxBitrate=999999999)
                                printDBG( 'Host tmp:%s ' % tmp )
                                for item in tmp:
                                    return item['url']
                        printDBG( 'Host tmp:%s ' % tmp )
                        for item in tmp:
                            return item['url']
            return ''

        if url.startswith('http://www.sanktuarium.turza.pl'):
            printDBG( 'Host getResolvedURL mainurl: '+url )
            COOKIEFILE = os_path.join(GetCookieDir(), 'sbl.cookie')
            self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
            self.HTTP_HEADER['Referer'] = url
            self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIEFILE}
            sts, data = self.get_Page(url)
            if not sts: return ''
            printDBG( 'Host listsItems data: '+data )
            youtube_link = self.cm.ph.getSearchGroups(data, '''(https://www.youtu[^"^']+?)[<'"]''', 1, True)[0]
            videoUrls = self.getLinksForVideo(youtube_link)
            if videoUrls:
                for item in videoUrls:
                    return item['url']
            return ''


#######################################################################################################################
        query_data = {'url': url, 'use_host': False, 'use_cookie': False, 'use_post': False, 'return_data': True}
        try:
            printDBG( 'Host listsItems begin query' )
            data = self.cm.getURLRequestData(query_data)
        except:
            printDBG( 'Host listsItems ERROR' )
            return videoUrl
        printDBG( 'Host getResolvedURL data'+data )

        if url.startswith('http://stream360.pl'):
            printDBG( 'Host getResolvedURL mainurl: '+url )
            m3u8_url = self.cm.ph.getSearchGroups(data, '''src:\s['"]([^"^']+?)['"]''', 1, True)[0]
            #return urlparser.decorateUrl(m3u8_url, {'Referer': url2, 'Origin':'http://stream360.pl'})
            if self.cm.isValidUrl(m3u8_url): 
                tmp = getDirectM3U8Playlist(m3u8_url)
                for item in tmp:
                    return item['url']

        if url.startswith('http://www.olesno.pl'):
            printDBG( 'Host getResolvedURL mainurl: '+url )
            m3u8_src = self.cm.ph.getSearchGroups(data, '''file:\s['"](http[^"^']+?\.m3u8)['"]''')[0] 
            printDBG( 'Host m3u8_src'+m3u8_src)
            if self.cm.isValidUrl(m3u8_src): 
                tmp = getDirectM3U8Playlist(m3u8_src)
                for item in tmp:
                    printDBG( 'Host item'+str(item) )
                    return item['url']

        if url.startswith('https://live.mstream.pl'):
            printDBG( 'Host getResolvedURL mainurl: '+url )
            Url = self.cm.ph.getSearchGroups(data, '''var\ssrc\s=\s['"]([^"^']+?)['"]''')[0] 
            if Url: return Url

        if 'lantech' in url:
            printDBG( 'Host getResolvedURL mainurl: '+url )
            serverip = self.cm.ph.getSearchGroups(data, '''var serverip\s=\s['"]([^"^']+?)['"]''')[0] 
            cam = self.cm.ph.getSearchGroups(data, '''var cam\s=\s['"]([^"^']+?)['"]''')[0] 
            m3u8_src = "https://" + serverip + "/hls/" + cam + "/index.m3u8"
            printDBG( 'Host m3u8_src'+m3u8_src)
            if self.cm.isValidUrl(m3u8_src): 
                tmp = getDirectM3U8Playlist(m3u8_src)
                for item in tmp:
                    printDBG( 'Host item'+str(item) )
                return item['url']

        if url.startswith('http://worldcam.live'):
            printDBG( 'Host getResolvedURL mainurl: '+url )
            m3u8_src = self.cm.ph.getSearchGroups(data, '''data-source=['"](http[^"^']+?)['"]''')[0] 
            if self.cm.isValidUrl(m3u8_src): 
                tmp = getDirectM3U8Playlist(m3u8_src, checkContent=True, sortWithMaxBitrate=999999999)
                for item in tmp:
                    return item['url']

        if url == 'http://tvtoya.pl/live':
            printDBG( 'Host getResolvedURL mainurl: '+url )
            videoUrl = self.cm.ph.getSearchGroups(data, '''data-stream=['"]([^"^']+?)['"]''', 1, True)[0]
            videoUrl = urlparser.decorateUrl(videoUrl, {'User-Agent': 'Mozilla/5.0 (Windows NT 5.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/49.0.2623.112 Safari/537.36'})
            if self.cm.isValidUrl(videoUrl): 
                tmp = getDirectM3U8Playlist(videoUrl, checkContent=True, sortWithMaxBitrate=999999999)
                for item in tmp:
                    printDBG( 'Host item: '+str(item) )
                    return item['url']

        if url.startswith('https://go.toya.net.pl'):
           printDBG( 'Host getResolvedURL mainurl: '+url )
           videoUrl = self.cm.ph.getSearchGroups(data, '''data-stream=['"]([^"^']+?)['"]''', 1, True)[0]
           if videoUrl: 
              printDBG( 'Host link: '+videoUrl )
              return urlparser.decorateUrl(videoUrl, {'User-Agent': 'Mozilla/5.0 (Windows NT 5.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/49.0.2623.112 Safari/537.36'})

        if url.startswith('http://www.tvtzgorzelec.pl'):
           printDBG( 'Host getResolvedURL mainurl: '+url )
           parse = re.search("sources:(.*?)image", data, re.S)
           if parse:
              link = re.findall('file: "(.*?)"', parse.group(1), re.S)
              if link:
                 for item in link: 
                    printDBG( 'Host listsItems tvt: '+item ) 
                    m3u8 = self.cm.ph.getSearchGroups(item, '(http.*?m3u8)')[0]
                    if m3u8: return m3u8 

        if url.startswith('http://www.tvkstella.pl'):
           printDBG( 'Host getResolvedURL mainurl: '+url )
           swfUrl = 'http://www.tvkstella.pl/flowplayer-3.2.7.swf'
           playpatch ='StellaLive'
           rtmp = 'rtmp://live-tvk.tvkstella.pl/flvplayback/'
           videoUrl = '%s playpath=%s swfUrl=%s pageUrl=%s live=1' % (rtmp, playpatch, swfUrl, url)
           return videoUrl

        if url.startswith('http://nspjkluczbork.pl'):
           printDBG( 'Host getResolvedURL mainurl: '+url )
           link = re.search('data-rtmp="(.*?)"', data, re.S|re.I)
           link2 = re.search('source src="(.*?)"', data, re.S|re.I)
           if link: 
              return '%s playpath=%s swfUrl=http://nspjkluczbork.pl/wp-content/plugins/fv-wordpress-flowplayer/flowplayer/flowplayer.swf?ver=6.0.5.12 pageUrl=http://nspjkluczbork.pl/uncategorized/kamera/ live=1' % (link.group(1), link2.group(1))
           return ''

        if url.startswith('http://parafiagornybor.pl'):
           printDBG( 'Host getResolvedURL mainurl: '+url )
           link = re.search("rtmp'.*?(rtmp.*?)'", data, re.S|re.I)
           if link: 
              playpath = link.group(1).split('/')[-1]
              rtmp = link.group(1).replace('/'+playpath,'')
              return '%s playpath=%s swfUrl=http://kamera.parafiaskoczow.ox.pl/FlashPlayer/player-glow.swf pageUrl=http://www.parafiagornybor.ox.pl/index.php/kamera-online.html live=1' % (rtmp, playpath)
           return ''

        if url.startswith('https://tomaszow.lub.pl'):
           return 'rtmp://159.255.185.248:1936/streamHD/ playpath=kosciol_HD swfUrl=http://p.jwpcdn.com/6/12/jwplayer.flash.swf pageUrl=http://www.tomaszow-sanktuarium.pl/niedzielna-transmisja-wideo/ live=1'

        if url.startswith('http://www.nsjtomaszowlub.pl'):
            printDBG( 'Host getResolvedURL mainurl: '+url )
            youtube_link = self.cm.ph.getSearchGroups(data, '''(https://www.youtu[^"^']+?)[<'"]''', 1, True)[0]
            videoUrls = self.getLinksForVideo(youtube_link)
            if videoUrls:
                for item in videoUrls:
                    return item['url']
            else:
                return self.cm.ph.getSearchGroups(data, '''<video\ssrc=['"]([^"^']+?)['"]''', 1, True)[0]

        if url.startswith('http://www.trt.pl'):
            printDBG( 'Host getResolvedURL mainurl: '+url )
            youtube_link = self.cm.ph.getSearchGroups(data, '''(https://www.youtu[^"^']+?)[<'"]''', 1, True)[0]
            videoUrls = self.getLinksForVideo(youtube_link)
            if videoUrls:
                for item in videoUrls:
                    return item['url']
            else:
                return self.cm.ph.getSearchGroups(data, '''<video\ssrc=['"]([^"^']+?)['"]''', 1, True)[0]

        if url.startswith('http://player.webcamera.pl'):
            printDBG( 'Host getResolvedURL mainurl: '+url )
            m3u8_link = self.cm.ph.getSearchGroups(data, '''<video id="video" src=['"]([^"^']+?)['"]''', 1, True)[0]
            if m3u8_link.startswith('//'): m3u8_link = 'http:' + m3u8_link
            return self.getResolvedURL(m3u8_link)

        if url.startswith('http://www.fokus.tv'):
            printDBG( 'Host getResolvedURL mainurl: '+url )
            link = self.cm.ph.getSearchGroups(data, '''<source src=['"]([^"^']+?mp4)['"]''', 1, True)[0]
            if not link:
                link = self.cm.ph.getSearchGroups(data, '''<source src=['"]([^"^']+?)['"]''', 1, True)[0].replace('&amp;','&')
                if self.cm.isValidUrl(link): 
                    tmp = getDirectM3U8Playlist(link)
                    for item in tmp:
                        return item['url']
            return link

        if 'koden' in url:
            m3u8_src = self.cm.ph.getSearchGroups(data, '''source: ['"](http[^"^']+?)['"]''')[0] 
            if m3u8_src:
                if self.cm.isValidUrl(m3u8_src): 
                    tmp = getDirectM3U8Playlist(m3u8_src)
                    for item in tmp:
                        return item['url']

        if url.startswith('http://poovee.net'):
            printDBG( 'Host getResolvedURL mainurl: '+url )
            link = self.cm.ph.getSearchGroups(data, '''<source src=['"]([^"^']+?)['"]''', 1, True)[0]
            if self.cm.isValidUrl(link): 
                tmp = getDirectM3U8Playlist(link)
                for item in tmp:
                    return item['url']
            return ''

        if url.startswith('http://www.ntv.ru'):
            printDBG( 'Host getResolvedURL mainurl: '+url )
            Url = self.cm.ph.getSearchGroups(data, '''hlsURL\s=\s['"]([^"^']+?)['"]''')[0] 
            if Url.startswith('//'): Url = 'http:'+Url
            if self.cm.isValidUrl(Url): 
                tmp = getDirectM3U8Playlist(Url)
                for item in tmp:
                    printDBG( 'Host item: '+str(item) )
                return urlparser.decorateUrl(item['url'], {'User-Agent': 'Mozilla/5.0 (Windows NT 5.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/49.0.2623.112 Safari/537.36'})
            return ''

        if url.startswith('https://www.youtube.com/embed'):
           printDBG( 'Host getResolvedURL mainurl: '+url )
           Url = self.cm.ph.getSearchGroups(data, '''['"](http://www.youtube.com/watch[^"^']+?)['"]''')[0] 
           return self.getResolvedURL(Url)

        printDBG( 'Host getResolvedURL end' )
        return videoUrl 

def decodeHtml(text):
	text = text.replace('&amp;#39;', '\'')
	text = text.replace('&amp;quot;', '"')
	text = text.replace('  by', '')
	text = text.replace('-&gt;', 'and')
	text = text.replace('…  ...    …', '')
	text = text.replace('  ...  ', '')
	text = text.replace('&middot;', '')
	text = text.replace('&amp;', '&')
	text = text.replace('\/', '/')
	text = text.replace('<b>', '')
	text = text.replace('</b>', '')
	text = text.replace('Na żywo: ', '')
	text = text.replace('&quot;', '"')
	text = text.replace('\\x22', '"')
	text = text.replace('&#8221;', '"')
	text = text.replace('&#8222;', '"')
	text = text.replace('&#8211;', '-')
	text = text.replace('&#039;', "'")
	text = text.replace('&#8217;', "'")

	return text	
def decodeNat1(text):
	text = text.replace('\u015a', '_')
	text = text.replace('\u0119', '_')
	text = text.replace('\u015b', '_')
	text = text.replace('\u0142a', '_')
	return text	
def decodeNat2(text):
	text = text.replace('\u015a', 'Ś')
	text = text.replace('\u0119', 'ę')
	text = text.replace('\u015b', 'ś')
	text = text.replace('\u0142', 'ł')
	text = text.replace('\u00f3', 'ó')
	text = text.replace('\u017c', 'ż')
	text = text.replace('\u0107', 'ć')
	text = text.replace('\u0144', 'ń')
	text = text.replace('\u0105', 'ą')
	text = text.replace('\u0144', 'ń')

	return text	
