# -*- coding: utf-8 -*-
# WhiteWolf - 2025.07.04. 
###################################################
HOST_VERSION = "1.1"
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass 
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts, CSelOneLink
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
from Plugins.Extensions.IPTVPlayer.hosts import hosturllist as urllist
from Plugins.Extensions.IPTVPlayer.libs import ph
from Plugins.Extensions.IPTVPlayer.libs.pCommon import CParsingHelper
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib
import requests
###################################################

###################################################
# E2 GUI COMPONENTS 
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvmultipleinputbox import IPTVMultipleInputBox
from Screens.MessageBox import MessageBox
###################################################

def GetConfigList():
    return []

def gettytul():
    return 'https://pannonrtv.com' 

class Pannon(CBaseHostClass):
 
    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'pannonrtv', 'cookie': 'pannonrtv.cookie'})
        self.MAIN_URL = 'https://pannonrtv.com'
        self.DEFAULT_ICON_URL = "https://pannonrtv.com/sites/default/files/2021-05/ogpannon.jpg"
        self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')        
        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        
    def getPage(self, url, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)
    
    def getLinksForVideo(self, cItem):
        printDBG("Pannonrtv.getLinksForVideo")
        videoUrls = []
        uri = urlparser.decorateParamsFromUrl(cItem['url'])
        protocol = uri.meta.get('iptv_proto', '')
        
        printDBG("PROTOCOL [%s] " % protocol)
        
        urlSupport = self.up.checkHostSupport(uri)
        if 1 == urlSupport:
            retTab = self.up.getVideoLinkExt(uri)
            videoUrls.extend(retTab)
        elif 0 == urlSupport and self._uriIsValid(uri):
            if protocol == 'm3u8':
                retTab = getDirectM3U8Playlist(uri, checkExt=False, checkContent=True)
                videoUrls.extend(retTab)
            elif protocol == 'f4m':
                retTab = getF4MLinksWithMeta(uri)
                videoUrls.extend(retTab)
            elif protocol == 'mpd':
                retTab = getMPDLinksWithMeta(uri, False)
                videoUrls.extend(retTab)
            else:
                videoUrls.append({'name': 'direct link', 'url': uri})
        return videoUrls
    
    def _uriIsValid(self, url):
        return '://' in url
    
    def listMainMenu(self, cItem):   
        printDBG('Pannonrtv.listMainMenu')
        desc = 'Pannon RTV \nAz intézmény a szabadkai Magyar Médiaházban működik. Műsorait több mint 100 foglalkoztatott, és mintegy 50 tiszteletdíjas készíti. Az újságírók mellett operatőrök, vágók, adáslebonyolítók, hangtechnikusok, adásszerkesztők, gyártásvezetők és adminisztratív munkatársak dolgoznak. A riporterek és szerkesztők jelentős része felsőfokú végzettségű. Az alkalmazottak zöme 35 év alatti. A Pannon RTV dinamikusan fejlődő médiaház, mely rendszeresen tudósít a nagyobb horderejű eseményekről Vajdaság egész területéről, valamint az anyaországból, továbbá beszámol Európa és a világ híreiről. A Pannon RTV számos művelődési rendezvény médiatámogatója. Élőben közvetíti a vajdasági magyarság kiemelt politikai, közéleti és művelődési eseményeit, ünnepi rendezvényeit (egyebek mellett a Magyar Nemzeti Tanács üléseit, a Pataki Gyűrű-díj átadóját, a Szent István napi központi ünnepséget).'
        sts, pannontv = self.getPage('https://media.gerst.se/pannon.xspf')
        pannontv = re.findall("location>(.*)</location", pannontv)[0]
        MAIN_CAT_TAB = [{'category': 'list_items', 'title': _('Legfrissebb'), 'url': 'https://pannonrtv.com/legfrissebb', 'desc': desc},
                        {'category': 'list_filters', 'title': _('Kategóriák'), 'url': self.MAIN_URL, 'desc': desc, 'next': False},
                        {'category': 'search', 'title': _('Keresés'), 'search_item': True},
                        {'category': 'search_history', 'title': _('Keresési előzmények')}]
        self.listsTab(MAIN_CAT_TAB, cItem) 
        self.addVideo({'title': _('Pannon TV'), 'url': pannontv, 'desc': 'A Pannon Televízió a Pannon RTV egyik oszlopa, 2006 óta sugároz. Kezdetben csak Szabadkán és környékén láthatták a nézők, ma azonban az IPTV rendszernek köszönhetően egész Vajdaságban fogható, valamint a tartomány több kábeltévé-szolgáltatója is felvette kínálatába. Az interneten a világ bármely pontjáról követhető az adás, illetve visszanézhetők a műsorok. Saját készítésű tájékoztató- és szórakoztató műsorai naponta átlagosan 4-5 órát töltenek ki, emellett számos partnertelevízió (köztük a magyarországi és a szerbiai köztévé) produkcióit (riportműsorait, sorozatait) is sugározza a különböző filmes alkotások és szórakoztató tartalmak mellett. Egyebek mellett koncerteket, színházi előadásokat, játékfilmeket, dokumentumfilmeket, sorozatokat, rajzfilmeket, meséket és videoklipeket is láthatnak a nézők. A Pannon Televízió műsorai az élet összes területével foglalkoznak a tájékoztató- és magazinműsorainak köszönhetően. A médium egyre több saját készítésű dokumentumfilmet tud műsorra tűzni.'})
        self.addAudio({'title': _('Pannon Rádió'), 'url': 'http://stream2.nmih.hu:4120/live.mp3', 'desc': 'Üde, friss, fiatalos, dinamikus – ez a Pannon Rádió. Vajdaság és a mindennapok ritmusa, a 91.5-ös regionális frekvencián. 2008 márciusában indultunk, és nagy utat jártunk be ahhoz, hogy mára Vajdaság vezető magyar nyelvű kereskedelmi rádiójává válhassunk. Nálunk hallható a régió legnépszerűbb magyar nyelvű reggeli műsora, a Pannon Reggeli, valamint a közérdekű információkat közlő, és laza témákban bővelkedő Pannon Presszó is. A nap 24 órájában a legújabb magyar- és külföldi slágerekkel, érdekességekkel, fontos információkkal, sőt óránként rövid hírösszefoglalókkal várunk Titeket. Hangoljatok ránk Szabadkán, Magyarkanizsán, Törökkanizsán, Csókán, Padén, Adán, Moholon, Zentán, Topolyán, Kishegyesen vagy Óbecsén, illetve Magyarországon Szeged, Kiskunhalas és Bácsalmás vonzáskörzetében. Honlapunkról természetesen online is hallhatóak vagyunk, a nap bármely szakában. Ez a Pannon Rádió, 2008 óta. Ismerj meg bennünket!', 'icon': 'https://pannonrtv.com/sites/default/files/inline-images/pannonradioujlogo1-01.jpg'})
        self.addAudio({'title': _('Szabadkai Magyar Rádió'), 'url': 'http://stream2.nmih.hu:4110/live.mp3', 'desc': 'A 2015. november 1-jén elindult Szabadkai Magyar Rádió célja a hallgatók naprakész tájékoztatása. A műsorban terítékre kerülnek politikai és szociális témák. Óránként hírek, és naponta többször híradó is várja a hallgatókat. Hírösszefoglalóinkban beszámolunk Szerbia, Magyarország és a világ eseményeiről is. Hétköznaponként Napindító című reggeli sávunkban részletesen feldolgozzuk a kiemelt eseményeket, az érdekes témákat. A Mozaikban tovább boncolgatjuk a történéseket. Bemutatjuk az itt élő érdekes embereket. A színészek, zenészek olykor élő produkciókkal érkeznek hozzánk. Az érdekes történetek mellé pedig a legszebb magyar és külföldi melódiák szólnak, a nosztalgia fonalára fűzve. Az esti órákban zenés szórakoztató-műsorokkal kedveskedünk a hallgatóknak, és a rádiószínházunkban is többször „felgördült a függöny” a 107,1 MHz-en, a hallgatók hullámhosszán.', 'icon': 'https://pannonrtv.com/sites/default/files/inline-images/onlineradioszmr.png'})
    
    def listFilters(self, cItem):
        printDBG('Pannonrtv.listFilters')
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        cat = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="block-subnavigation__menu menu">', '</nav>', False)[1]
        if cItem['next'] == True:
            cats = self.cm.ph.getDataBeetwenMarkers(cat, cItem['title'], '</ul>', False)[1]
            cats = self.cm.ph.getAllItemsBeetwenMarkers(cats, '<a', 'a>', False)
            params = {'category': 'list_items', 'title': cItem['title'], 'icon': None, 'url': cItem['url']}
            self.addDir(params)
            for i in cats:
                title = self.cm.ph.getDataBeetwenMarkers(i, '">', '<', False)[1]
                url = self.MAIN_URL + self.cm.ph.getDataBeetwenMarkers(i, 'href="', '"', False)[1]
                params = {'category': 'list_items', 'title': title, 'icon': None, 'url': url}
                self.addDir(params)
        else:
            cats = self.cm.ph.getAllItemsBeetwenMarkers(cat, '<li class="block-subnavigation__menu-item menu-item', 'a>', False)
            cats.pop(-1)
            for i in cats:
                close = self.cm.ph.getDataBeetwenMarkers(i, '">', '</', False)[1] + "<"
                title = self.cm.ph.getDataBeetwenMarkers(close, '">', '<', False)[1]
                url = self.MAIN_URL + self.cm.ph.getDataBeetwenMarkers(close, 'href="', '"', False)[1]
                if "--expanded" in i:
                    params = {'category': 'list_filters', 'title': title, 'icon': None, 'url': url, 'next': True}
                    self.addDir(params)
                else:
                    params = {'category': 'list_items', 'title': title, 'icon': None, 'url': url}
                    self.addDir(params)
    
    def listItems(self, cItem):
        printDBG('Pannonrtv.listItems')
        url = cItem['url']    
        params = False
        sts, data = self.getPage(url)                
        if not sts:
            return
        found = self.cm.ph.getDataBeetwenMarkers(data, '<div class="region-content">', '<div class="region-sidebar-second">', False)[1]
        found = self.cm.ph.getAllItemsBeetwenMarkers(found, '<div data-b-token', '--promoted', False)
        for m in found:
            title = self.cm.ph.getDataBeetwenMarkers(m, '" rel="bookmark">', '</a>', False)[1]
            icon = self.MAIN_URL + self.cm.ph.getDataBeetwenMarkers(m, '" data-src="', '"', False)[1]
            date1 = self.cm.ph.getDataBeetwenMarkers(m, '<span class="node-article-rovatok-small__title-date--day">', '</span>', False)[1]
            if date1 == "":
                date1 = self.cm.ph.getDataBeetwenMarkers(m, '<span class="node-article-rovatok-medium__title-date--day">', '</span>', False)[1]
                if date1 == "":
                    date1 = self.cm.ph.getDataBeetwenMarkers(m, '<span class="node-article-rovatok-big__title-date--day">', '</span>', False)[1]
            date2 = self.cm.ph.getDataBeetwenMarkers(m, '<span class="node-article-rovatok-small__title-date--hours">', '</span>', False)[1]
            if date2 == "":
                date2 = self.cm.ph.getDataBeetwenMarkers(m, '<span class="node-article-rovatok-medium__title-date--hours">', '</span>', False)[1]
                if date2 == "":
                    date2 = self.cm.ph.getDataBeetwenMarkers(m, '<span class="node-article-rovatok-big__title-date--hours">', '</span>', False)[1]
            date = date1 + " " + date2
            desc = self.cm.ph.getDataBeetwenMarkers(m, '<div class="node-article-rovatok-small__field-teaser-text">', "</div>", False)[1]
            if desc == "":
                desc = self.cm.ph.getDataBeetwenMarkers(m, '<div class="node-article-rovatok-medium__field-teaser-text">', "</div>", False)[1]
                if desc == "":
                    desc = self.cm.ph.getDataBeetwenMarkers(m, '<div class="node-article-rovatok-big__field-teaser-text">', "</div>", False)[1]
            desc = desc.strip()
            desc = date + "\n" + desc
            url = self.MAIN_URL + self.cm.ph.getDataBeetwenMarkers(m, '" href="', '"', False)[1]
            params = {'category': 'explore_item', 'title': title, 'icon': icon, 'url': url, 'desc': desc}
            if not "Kommentár nélkül" in title:
                self.addDir(params)
        if params:
            if '<li class="pager__item pager__item--next">' in data:
                url = self.cm.ph.getDataBeetwenMarkers(data, '<li class="pager__item pager__item--next">', 'rel="next">', False)[1]
                orl = self.cm.ph.getDataBeetwenMarkers(data, '<meta property="og:url" content="', '"', False)[1]
                url = orl + self.cm.ph.getDataBeetwenMarkers(url, '<a href="', '"', False)[1]
                params = {'category': 'list_items', 'title': "Következő oldal", 'icon': None, 'url': url}
                self.addDir(params)      
    
    def exploreItems(self, cItem):
        printDBG('Pannonrtv.exploreItems')
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        content = self.cm.ph.getDataBeetwenMarkers(data, '<section id="content">', '<div class="node-article-full__field-tags">')[1]
        images = self.cm.ph.getAllItemsBeetwenMarkers(content, 'data-src="', '"', False)
        text = re.findall('''<p>(.+?)</p>|<p.+?>(.+?)</p>''', content)
        if text == []:
            text = re.findall('''<p>(.+?\n.+?)</p>|<p.+?>(.+?\n.+?)</p>''', content)
        for i in text:
            text[text.index(i)] = "".join(i)
        og = list(text)
        printDBG(str(og))
        title = self.cm.ph.getDataBeetwenMarkers(content, '<div class="node-article-full__field-teaser-text">', '</div>', False)[1]
        title = title.strip()
        text[0] = title + "\n" + text[0]
        if len(images) == len(text):
            for i in images:
                txt = re.sub('''<.+?>''', "", text[images.index(i)])
                params = {'title': str(images.index(i) + 1) + ".bekezdés", 'icon': i, 'desc': txt}
                self.addArticle(params)
        if len(images) > len(text):
            for i in text:
                txt = re.sub('''<.+?>''', "", i)
                params = {'title': str(text.index(i) + 1) + ".bekezdés", 'icon': images[text.index(i)], 'desc': txt}
                self.addArticle(params)
        if len(images) < len(text):
            printDBG("images:" + str(len(images)))
            printDBG("text:" + str(len(text)))
            a = 1
            while a < len(text):
               text[0] = text[0] + " " + text[a]
               text.pop(a)
               printDBG("textuj:" + str(len(text)))
               if len(images) < len(text):
                   a += 1
               else:
                  break
            for i in images:
                txt = re.sub('''<.+?>''', "", text[images.index(i)])
                params = {'title': str(images.index(i) + 1) + ".bekezdés", 'icon': i, 'desc': txt}
                self.addArticle(params)
        if "YouTube" in og[-1]:
            url = self.cm.ph.getDataBeetwenMarkers(og[-1], 'src="', '"', False)[1]
            params = {'title': "Youtube videó", 'icon': None, 'url': url}
            self.addVideo(params)
	
    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('Pannonrtv.handleService start')
        
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        title = self.currItem.get("title", '')
        icon = self.currItem.get("icon", '')
        url = self.currItem.get("url", '')
        printDBG("handleService: >> name[%s], category[%s], title[%s], icon[%s] " % (name, category, title, icon))
        self.currList = []
        if name == None:
            self.listMainMenu({'name': 'category'})
        elif category == 'list_items':
            self.listItems(self.currItem)
        elif category == 'list_filters':
            self.listFilters(self.currItem)
        elif category == 'explore_item':
            self.exploreItems(self.currItem)			
        elif category == 'search':
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category'}) 
            self.listSearchResult(cItem, searchPattern, searchType)	
        elif category == 'cont_search':
            self.listSearchResult(self.currItem, self.currItem['searchPattern'], '')	
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()
        
        CBaseHostClass.endHandleService(self, index, refresh)
    
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Pannonrtv.listSearchResult - Filmek cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        url = 'https://pannonrtv.com/search?text=' + searchPattern
        if 'url' in cItem:
            url = url + cItem['url'] + str(cItem['page'])
            printDBG(url)
        params = False
        sts, data = self.getPage(url)                
        if not sts:
            return
        found = self.cm.ph.getDataBeetwenMarkers(data, '<section id="content">', '<div class="region-sidebar-second">', False)[1]
        found = self.cm.ph.getAllItemsBeetwenMarkers(found, 'node-article-search-result-viewmode__content', 'search-result-viewmode__field-tags"', False)
        for m in found:
            title = self.cm.ph.getSearchGroups(m, '''" rel="bookmark">([^<].+?)</a>''', 1, True)[0]
            icon = self.MAIN_URL + self.cm.ph.getDataBeetwenMarkers(m, 'src="', '"', False)[1]
            date = self.cm.ph.getDataBeetwenMarkers(m, '<span class="node-article-search-result-viewmode__date--created">', '</span>', False)[1]
            desc = self.cm.ph.getDataBeetwenMarkers(m, 'node-article-search-result-viewmode__field-teaser-text">', "</div>", False)[1]
            desc = desc.strip()
            desc = date + "\n" + desc
            url = self.MAIN_URL + self.cm.ph.getDataBeetwenMarkers(m, '" href="', '"', False)[1]
            check = self.cm.ph.getDataBeetwenMarkers(m, '<div class="article__row article__row--left--image article__row article__row--left--image--bigger helper-relative">', '<div class="node-article-search-result-viewmode__field-channel">', False)[1]
            if ('<span class="video">' not in check or '<span class="foto">' in check) and "Közérdekű információk" not in m:
                params = {'category': 'explore_item', 'title': title, 'icon': icon, 'url': url, 'desc': desc}
                self.addDir(params)
        if params:
            if '<li class="pager__item pager__item--next">' in data:
                if 'page' not in cItem:
                    page = 0
                else:
                    page = cItem['page']
                url = '&page='
                params = {'category': 'cont_search', 'title': "Következő oldal", 'icon': None, 'url': url, 'searchPattern': searchPattern, 'page': page + 1}
                self.addDir(params)      
        

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Pannon(), True, [])
    
