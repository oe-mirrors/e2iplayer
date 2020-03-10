# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.ihost import IHost, CDisplayListItem, RetHost, CUrlItem, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetLogoDir, byteify
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
###################################################
# FOREIGN import
###################################################
import re
import copy
###################################################


def gettytul():
    return 'https://spryciarze.pl/'
    
class Spryciarze(CBaseHostClass):
    MAIN_URL = 'https://www.spryciarze.pl/'
    MAIN_CATEGORIES_URL = MAIN_URL + 'kategorie/'
    VIDEO_URL = MAIN_URL + 'player/player/xml_connect.php?code='
    
    NUM_PER_PAGE = 12
    SEARCH_RES_PER_PAGE = 30
    
    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'spryciarze.org', 'cookie':'spryciarze.cookie'})
        self.catTree = []
        self.currList = []
        
    def getCurrList(self):
        return self.currList

    def setCurrList(self, list):
        self.currList = list
        return 

    def getMainCategory(self):
        printDBG('Spryciarze.getMainCategory')
        
        self.catTree = []
        self.currList = []
        
        sts, data = self.cm.getPage(self.MAIN_CATEGORIES_URL)
        if not sts: return
        
        data = self.cm.ph.getDataBeetwenNodes(data, ('<section', '>', 'py-5 bg-light-v2'), '<div class="widget">')[1]
        
        catTab = data.split('<div class="card-header bg-light">')
        # free memory
        data = ''
        if len(catTab) > 0 :
            del catTab[0]
            
        printDBG('catTab len %d' % len(catTab))
        
        for i in range(len(catTab)):
            subTab = catTab[i].split('<div class="card-body">')
            # Free memory
            catTab[i] = ''
            
            if 2 == len(subTab):
                # Get Main category data
                pattern = '<h4>.+?<a href="(.+?)">\r\n(.+?)\r\n.+?<small>\(([0-9]+?)\)</small>'
                match = re.compile(pattern, re.DOTALL).findall(subTab[0])
                
                if len(match) == 1:
                    catItem = {'type': 'main', 'url': match[0][0], 'name': " ".join(match[0][1].split()), 'ilosc': match[0][2], 'subCatList': []}
                    self.currList.append(catItem)

                else:
                    printDBG('getMainCategory ignore wrong data for category')
            else:
                printDBG('getMainCategory ignore wrong data for category: 2 != len(subTab)')
                
        catItem = {'type': 'search', 'name': 'Wyszukaj', 'subCatList': []}
        self.currList.append(catItem)
        
        return
    # end getMainCategory
    
    def getSubCategory(self, index):
        printDBG('Spryciarze.getSubCategory')
        
        item = self.currList[index]
        
        self.catTree = []
        self.currList = []
        
        sts, data = self.cm.getPage(item['url'])
        if not sts: return
        
        data = self.cm.ph.getDataBeetwenNodes(data, ('<section', '>', 'py-5 bg-light-v2'), '<div class="widget">')[1]
        
        catTab = data.split('<div class="card-header bg-light">')
        # free memory
        data = ''
        if len(catTab) > 0 :
            del catTab[0]
            
        printDBG('catTab len %d' % len(catTab))

        for i in range(len(catTab)):
            subTab = catTab[i].split('<div class="card-body">')
            # Free memory
            catTab[i] = ''
            if 2 == len(subTab):
                # Get Main category data
                pattern = '<h4>.+?<a href="(.+?)">\r\n\s+?(.+?)\r\n.+?<small>\(([0-9]+?)\)</small>'
                match = re.compile(pattern, re.DOTALL).findall(subTab[0])
                
                if len(match) == 1:
                    catItem = {'type': 'sub', 'url': match[0][0], 'name': " ".join(match[0][1].split()), 'ilosc': match[0][2], 'subCatList': []}
                    
                    #Get sub-categories data
                    pattern = '<a.+?href="(.+?)"[^>]*?>(.+?)\r\n.+?<small>\(([0-9]+?)\)</small>.+?</a>'
                    match = re.compile(pattern, re.DOTALL).findall(subTab[1])
                    for j in range(len(match)):
                        subItem = {'type': 'subSub', 'url': match[j][0], 'name': match[j][1], 'ilosc': match[j][2]}                        
                        catItem['subCatList'].append(subItem)
                        
                    if(len(catItem['subCatList'])):
                        self.catTree.append(catItem)
                    else:
                        printDBG('getMainCategory main category ingnored because it does not have sub categories')
                    
                else:
                    printDBG('getMainCategory ignore wrong data for category')
            else:
                printDBG('getMainCategory ignore wrong data for category: 2 != len(subTab)')
                
        self.currList = self.catTree
        
        if 1 == len(self.currList):
            self.getSubSubCategory(0)
        
        return
    # end getSubCategory
    
    def getSubSubCategory(self, index):
        printDBG('Spryciarze.getSubSubCategory')
        self.currList = self.catTree[index]['subCatList']
        
        if 1 == len(self.currList):
            self.getItemsForCat(0)
        
        return
    # end getSubCategory
    
    def getItemsForCat(self, index):
        printDBG('Spryciarze.getItemsForCat')
        try:
            item = self.currList[index]
            self.currList = []
            itemNum = int(item['ilosc'])
            
            pageNum = itemNum / self.NUM_PER_PAGE
            
            if itemNum % self.NUM_PER_PAGE > 0:
                pageNum += 1
            
            for i in range(pageNum):
                tmpItem = copy.deepcopy(item)
                tmpItem['type'] = 'subSubPage'
                tmpItem['url'] += '/page:%d' % (i + 1)
                tmpItem['name'] = 'Strona %d' % (i + 1)
                tmpItem.pop("ilosc", None)
                self.currList.append(tmpItem)
                
            if 1 == len(self.currList):
                self.getVideoList2(item['url'])
                
        except Exception:
            printDBG('Spryciarze.getItemsForCat except')
        
        return
    # end getSubCategory
    
    def getSearchResut(self, pattern):
        printDBG('Spryciarze.getSearchResut')
        self.currList = []
        
        SEARCH_URL = self.MAIN_URL + 'szukaj/' + pattern + '/film/page:1/sort:ocena'
        
        sts, data = self.cm.getPage(SEARCH_URL)
        if not sts: return
        
        match = re.compile('Wideoporadniki \(([0-9]+?)\)').findall(data)
        if 0 == len(match): return
        
        itemNum = int(match[0])
        pageNum = itemNum / self.SEARCH_RES_PER_PAGE
        
        if itemNum % self.SEARCH_RES_PER_PAGE > 0:
            pageNum += 1
        
        for i in range(pageNum):
            tmpItem = {}
            tmpItem['type'] = 'subSubPage'
            tmpItem['url'] =  self.MAIN_URL + 'szukaj/' + pattern + ( '/film/page:%d' % (i+1) ) + '/sort:ocena'
            tmpItem['name'] = 'Strona %d' % (i + 1)
            
            if (i+1) < pageNum:
                tmpItem['opis'] = 'Wyniki wyszukiwania od %d do %d' % ( i * self.SEARCH_RES_PER_PAGE + 1, (i + 1) * self.SEARCH_RES_PER_PAGE )
            else:
                tmpItem['opis'] = 'Wyniki wyszukiwania od %d do %d' % ( i * self.SEARCH_RES_PER_PAGE + 1, itemNum )
                
            self.currList.append(tmpItem)
            
        if 1 == len(self.currList):
            self.getVideoList2(self.currList[0]['url'])
            
        
    
    def getVideoList2(self, url):
        printDBG('Spryciarze.getVideoList')
        self.currList = []
        
        if None == url or 0 == len(url):
            return
        
        sts, data = self.cm.getPage(url)
        if not sts: return
        
        tab = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'col-md-6 col-lg-6 col-xl-4 mb-4'), ('</div', '>'))
            
        printDBG('getVideoList tab_len %d' % len(tab))
        
        searchItems = [ {'keys': ['url'], 'req': False, 'pattern': '<a href="([^"]+?)"'},
                        {'keys': ['ico'], 'req': False, 'pattern': '<img src="([^"]+?)"'},
#                        {'keys': ['odslony'], 'req': False, 'pattern': '<span><span class="film_odslony"></span>.+?: <span>([0-9]+?)</span></span>'},
#                        {'keys': ['odslony'], 'req': False, 'pattern': '<span><span class="film_odslony"></span>.+?: <span>([0-9]+?)</span></span>'},
#                        {'keys': ['data', 'godzina'], 'req': False, 'pattern': '<span><span class="film_data"></span>dodane: <span>([0-9][0-9]-[0-9][0-9]-[0-9][0-9][0-9][0-9]) ([0-9][0-9]:[0-9][0-9])</span></span>'},
#                        {'keys': ['opis'], 'req': False, 'pattern': '<p class="film_opis">([^<]+?)</p>'},
                        {'keys': ['url', 'name'], 'req': True, 'pattern': '<a href="([^"]+?)".+?class="h6">([^<]+?)</a>'},
                       ]
        
        for i in range(len(tab)):
            videoItem = {}
            videoItem['type'] = 'video'
            
            ignore = False
            for it in searchItems:
                match = re.compile(it['pattern'], re.DOTALL).findall(tab[i].replace('&quot;', ''))
                
                if 1 != len(match):
                    printDBG('Brak ' + it['keys'][0])
                    if it['req']:
                        ignore = True
                        break
                    else:
                        continue
                else:
                    printDBG('Znaleziono ' + it['keys'][0])
                        
                keyNums = len(it['keys'])
                if( keyNums > 1 ):
                    for j in range(keyNums):
                        videoItem[it['keys'][j]] = match[0][j]
                else:
                    videoItem[it['keys'][0]] = match[0]
            
            # Clear checked part to free memory
            tab[i] = ''
            if False == ignore:
                self.currList.append(videoItem)

        printDBG('Spryciarze.getVideoList len(self.currList): %d' % len(self.currList))
        return
    # end getVideoList
    
    def getVideoLinks(self, url):
        printDBG('Spryciarze.getVideoLinks: ' + url)
        
        linkstTab = []
        if None == url or 0 == len(url):
            return linkstTab
        
        post_data = None
        tries = 2
        while tries > 0:
            tries -= 1
            # get videoID
            sts, data = self.cm.getPage(url, {'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': self.COOKIE_FILE}, post_data)
            if not sts: return []
            
            sts, block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="film_blokada">', '</form>', False)
            if sts:
                url = self.cm.ph.getSearchGroups(block, 'action="(http[^"]+?)"')[0]
                val_s = self.cm.ph.getSearchGroups(block, 'name="s"[^>]*?value="([^"]+?)"')[0]
                post_data = {}
                post_data['s'] = val_s
                post_data['yes'] = ''
                continue
                
            player = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'video_container'), ('</div', '>'))[1]
            player = self.getFullUrl(self.cm.ph.getSearchGroups(player, '''<iframe[^>]+?src=['"]([^"^']*?)['"]''', 1, True)[0])
            if 1 == self.up.checkHostSupport(player):
                linkstTab = self.up.getVideoLinkExt(player)
                if len(linkstTab): break
            
            player =  self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']*?player\.spryciarze\.pl[^"^']+?)['"]''', 1, True)[0])
            if '' != player:
                sts, player = self.cm.getPage(player, {'use_cookie': True, 'save_cookie': False, 'load_cookie': True, 'cookiefile': self.COOKIE_FILE})
                if not sts: break
                url = self.getFullUrl(self.cm.ph.getSearchGroups(player, '''<iframe[^>]+?src=['"]([^"^']*?)['"]''', 1, True)[0])
                if 1 == self.up.checkHostSupport(url):
                    linkstTab = self.up.getVideoLinkExt(url)
                player = self.cm.ph.getSearchGroups(player.replace('&quot;', ''), 'const data[^=]*?=[^\{]*?(\{[^;]+?);')[0]
                try:
#                    printDBG(player)
                    player = player[:player.find('"relatedMovies"')].replace('}],', '}]}')
                    printDBG(player)
                    player = byteify(json_loads(player))
                    player = player['mediaFiles']
                    for item in player:
                        if 'mp4' in item['type']:
                            linkstTab.append({'name':'Native player', 'url':item['src']})
                except Exception:
                    printExc()
            else:
                player  = self.cm.ph.getSearchGroups(data, '(spryciarze.pl/player/[^"]+?\.swf?[^"]+?)"')[0]
                videoID = self.cm.ph.getSearchGroups(player + '|', 'VideoID=([0-9]+?)[^0-9]')[0]
                sts, data = self.cm.getPage(self.getFullUrl('/player/player/xml_connect.php?code=%s&ra=2' % videoID), {'use_cookie': True, 'save_cookie': False, 'load_cookie': True, 'cookiefile': self.COOKIE_FILE})
                if not sts: break
                data = re.compile('<urlMOV([^>]+?)>([^<]+?)<').findall(data)
                tmp = []
                for item in data:
                    if item[1] not in tmp:
                        tmp.append(item[1])
                        linkstTab.append({'name':'Native player %s' % item[0], 'url':item[1]})
            if len(linkstTab):
                break
        return linkstTab
    # end getVideoLink
    
    def handleService(self, index, refresh = 0, searchPattern = ''):
    
        if 0 == refresh:
            if len(self.currList) <= index:
                printDBG( "Spryciarze.handleService wrong index: %s, len(self.currList): %d" % (index, len(self.currList)) )
                return
        
            if -1 == index:
                self.type = None
                printDBG( "Spryciarze.handleService for first self.category" )
            else:
                item = self.currList[index]
                self.type = item['type']
                self.index = index
                self.url = ''
                if 'url' in self.currList[index]:
                    self.url = self.currList[index]['url']
                self.prevList = self.currList

                printDBG( "|||||||||||||||||||||||||||||||||||| %s " % item['type'] )

    #MAIN MENU
        if self.type == None:
            self.getMainCategory()
    #SUB CATEGORY
        elif self.type == 'main':
            self.getSubCategory( self.index )
    #SUB_SUB_CATEGORY
        elif self.type == 'sub':
            self.getSubSubCategory( self.index )
    #SUB__SUB_PAGES
        elif self.type == 'subSub':
            self.getItemsForCat( self.index )
    #VIDEOS
        elif self.type == 'subSubPage':
            self.getVideoList2( self.url )
    #SEARCH
        elif self.type == 'search':
            self.getSearchResut( searchPattern )
    # end handleService

class IPTVHost(IHost):

    def __init__(self):
        self.host = None
        self.currIndex = -1
        self.listOfprevList = [] 
        
        self.searchPattern = ''
    
    # return firs available list of item category or video or link
    def getInitList(self):
        self.host = Spryciarze()
        self.currIndex = -1
        self.listOfprevList = [] 
        
        self.host.handleService(self.currIndex)
        
        convList = self.convertList(self.host.getCurrList())
        
        return RetHost(RetHost.OK, value = convList)
    
    # return List of item from current List
    # for given Index
    # 1 == refresh - force to read data from 
    #                server if possible 
    # server instead of cache 
    def getListForItem(self, Index = 0, refresh = 0, selItem = None):
        self.listOfprevList.append(self.host.getCurrList())
        
        self.currIndex = Index
        self.host.handleService(Index, refresh, self.searchPattern)
        convList = self.convertList(self.host.getCurrList())
        
        return RetHost(RetHost.OK, value = convList)
        
    # return prev requested List of item 
    # for given Index
    # 1 == refresh - force to read data from 
    #                server if possible
    def getPrevList(self, refresh = 0):
        if(len(self.listOfprevList) > 0):
            hostList = self.listOfprevList.pop()
            self.host.setCurrList(hostList)
            convList = self.convertList(hostList)
            return RetHost(RetHost.OK, value = convList)
        else:
            return RetHost(RetHost.ERROR, value = [])
        
    # return current List
    # for given Index
    # 1 == refresh - force to read data from 
    #                server if possible
    def getCurrentList(self, refresh = 0):      
        if refresh == 1:
            if len(self.listOfprevList) > 0:
                hostList = self.listOfprevList.pop()
                self.host.setCurrList(hostList)
                return self.getListForItem(self.currIndex)
            else:
                return self.getInitList()           
                
        convList = self.convertList(self.host.getCurrList())
        return RetHost(RetHost.OK, value = convList)
    
    # return list of links for VIDEO with given Index
    # for given Index
    def getLinksForVideo(self, Index = 0, selItem = None):
        listLen = len(self.host.currList)
        if listLen < Index and listLen > 0:
            print "ERROR getLinksForVideo - current list is to short len: %d, Index: %d" % (listLen, Index)
            return RetHost(RetHost.ERROR, value = [])
        
        selItem = self.host.currList[Index]
        if selItem['type'] != 'video':
            print "ERROR getLinksForVideo - current item has wrong type"
            return RetHost(RetHost.ERROR, value = [])
            
        retlist = []
        
        if None != selItem and 'url' in selItem and 1 < len(selItem['url']):
            tmpList = self.host.getVideoLinks( selItem['url'] )
            
            for item in tmpList:
                retlist.append(CUrlItem(item['name'], item['url'], 0))
            
        return RetHost(RetHost.OK, value = retlist)
            
    def getSearchResults(self, searchpattern, searchType = None):
        self.isSearch = True
        retList = []
        self.searchPattern = searchpattern.replace(' ',  '%20')
        
        return self.getListForItem( len(self.host.getCurrList()) -1 )
            
    # return full path to player logo
    def getLogoPath(self):  
        return RetHost(RetHost.OK, value = [ GetLogoDir('spryciarzelogo.png') ])


    def convertList(self, cList):
        hostList = []
        possibleTypesOfSearch = []
        
        for cItem in cList:
            hostLinks = []
            type = CDisplayListItem.TYPE_UNKNOWN
            
            if cItem['type'] in ['main', 'sub',  'subSub', 'subSubPage']:
                    type = CDisplayListItem.TYPE_CATEGORY
            elif cItem['type']  == 'video':
                type = CDisplayListItem.TYPE_VIDEO
                videoID = ''
                if 'url' in cItem:
                    url = cItem['url']
                hostLinks.append(CUrlItem('', url, 0))
            elif cItem['type']  == 'search':
                type = CDisplayListItem.TYPE_SEARCH
                
            name = ' '
            if 'name' in cItem:
                name = cItem['name']
            opis = ''
            if 'opis' in cItem:
                opis = cItem['opis']
            ilosc = ''
            if 'ilosc' in cItem:
                ilosc = '(' + cItem['ilosc'] + ')'
            ico = ''
            if 'ico' in cItem:
                ico = cItem['ico']
            if ico == '': ico = 'http://mamrodzine.pl/wp-content/uploads/2011/06/logo_transparent.png'

            hostItem = CDisplayListItem(name = name + ' ' + ilosc,
                                        description = opis,
                                        type = type,
                                        urlItems = hostLinks,
                                        urlSeparateRequest = 1,
                                        iconimage = ico,
                                        possibleTypesOfSearch = possibleTypesOfSearch)
            hostList.append(hostItem)
        # end for
            
        return hostList



          
#host = Spryciarze()
#host.getMainCategory()
#host.getVideoList('http://kulinaria.spryciarze.pl/kategorie/dania-miesne')
#host.getVideoLinks('58763')