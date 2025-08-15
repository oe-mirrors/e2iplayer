# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import  printDBG, printExc, byteify
from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.utils import clean_html
###################################################

###################################################
# FOREIGN import
###################################################
import re
try:    import simplejson as json
except Exception: import json
import string
import base64
import binascii
###################################################


def gettytul():
    return 'http://serialnet.pl/'


class SerialeNet(CBaseHostClass):
    
    def __init__(self):
        printDBG("SerialeNet.__init__")
        CBaseHostClass.__init__(self, {'history':'SerialeNet', 'cookie':'serialenet.cookie'})
        
        self.DEFAULT_ICON_URL = 'http://3.bp.blogspot.com/_Gm9qKcXSvaM/S3X4VtoRfjI/AAAAAAAAAHw/I3ZTIK_DZlY/s200/MCj04421470000%5B1%5D.png'
        self.MAIN_URL = "http://serialnet.pl/"
        self.CAT_TAB  = [{'category':'abc_menu',        'title':'Alfabetycznie',             'url':self.getMainUrl()},
                         {'category':'last_update',     'title':'Ostatnio uzupełnione',      'url':self.getMainUrl()},
                         
                         {'category':'search',          'title':_('Search'), 'search_item':True},
                         {'category':'search_history',  'title':_('Search history')} ]
        self.seasonsCache = []
        
    def _getStr(self, v, default=''):
        return clean_html(self._encodeStr(v, default))
        
    def _encodeStr(self, v, default=''):
        if type(v) == type(u''): return v.encode('utf-8')
        elif type(v) == type(''): return v
        else: return default
        
    def decodeJS(self, s):
        ret = ''
        try:
            if len(s) > 0:
               js = 'unpack' + s[s.find('}(')+1:-1]
               js = js.replace("unpack('",'''unpack("''').replace(");'",''');"''').replace("\\","/")
               js = js.replace("//","/").replace("/'","'")
               js = "self." + js
               match = re.compile("\('(.+?)'").findall(eval(js))
               if len(match) > 0:
                  ret = base64.b64decode(binascii.unhexlify(match[0].replace("/x","")))
        except Exception: printExc()
        return ret

    def unpack(self, p, a, c, k, e=None, d=None):
        for i in xrange(c-1,-1,-1):
            if k[i]:
               p = re.sub('\\b'+self.int2base(i,a)+'\\b', k[i], p)
        return p
        
    def int2base(self, x, base):
        digs = string.digits + string.lowercase + string.uppercase
        if x < 0: sign = -1
        elif x==0: return '0'
        else: sign = 1
        x *= sign
        digits = []
        while x:
            digits.append(digs[x % base])
            x /= base
        if sign < 0:
            digits.append('-')
        digits.reverse()
        return ''.join(digits)
        
    def _listsSeries(self, url):
        printDBG("SerialeNet._listsSeries")
        url = self.getFullUrl(url)
        sts, data = self.cm.getPage(url)
        if sts:
            data = self.cm.ph.getDataBeetwenMarkers(data, '<ul id="list" class="bottom">', '<script>', False)[1]
            retTab = []
            match = re.compile('<a href="([^"]+?)"[^>]*?>(.+?)</a>').findall(data)
            for item in match:
                tmp = item[1].split('<p>')
                t1 = self.cleanHtmlStr(tmp[0])
                if len(t1):
                    if 1 < len(tmp): t2 = self.cleanHtmlStr(tmp[1])
                    else: t2 = ''
                    retTab.append({'t1':t1, 't2':t2, 'url':self.getFullUrl(item[0])})
            return retTab
        return []

    def listABC(self, cItem, category):
       abcTab = self.cm.makeABCList()
       for item in abcTab:
            params = dict(cItem)
            params.update({'title':item, 'letter':item, 'category':category})
            self.addDir(params)
    
    def listsSeriesByLetter(self, cItem, category):
        printDBG("SerialeNet.listsSeriesByLetter")
        letter = cItem.get('letter', '')
        match = self._listsSeries(cItem['url'])
        for item in match:
            t1 = item['t1']
            t2 = item['t2']
            match = False
            if letter.isalpha():
                if letter == self.cm.ph.getNormalizeStr(t1, 0).upper():
                    match = True
                elif len(t2) and letter == self.cm.ph.getNormalizeStr(t2, 0).upper():
                    match = True
                    t1,t2 = t2,t1
            else:
                if not self.cm.ph.isalpha(t1, 0):
                    match = True
                elif len(t2) and not self.cm.ph.isalpha(t2, 0):
                    match = True
                    t1,t2 = t2,t1
            if match:
                params = dict(cItem)
                if len(t2): t1 += ' (%s)' % t2
                params.update({'good_for_fav': True, 'category':category, 'title':t1, 'url':item['url']})
                self.addDir(params)
        self.currList.sort(key=lambda item: item['title'])

    def listSeasons(self, cItem, category):
        printDBG("SerialeNet.listSeasons")
        url = self.getFullUrl(cItem['url'])
        self.seasonsCache = []
        
        sts, data = self.cm.getPage(url)
        if not sts: return
        
        serieTitle = cItem.get('title', '')
        
        desc = self.cm.ph.getDataBeetwenMarkers(data, '<div id="desc">', '</div>', False)[1]
        icon = self.getFullUrl(self.cm.ph.getSearchGroups(desc, 'src="([^"]+?)"')[0])
        desc = self.cleanHtmlStr(desc)
        
        data = self.cm.ph.getDataBeetwenReMarkers(data, re.compile('<div[^>]+?id="wrp1"[^>]*?></?br[^>]*?>'), re.compile('<script>'), False)[1]
        data = data.split('<div')
        if len(data): del data[0]
        for item in data:
            seasonName = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h3>', '</h3>', False)[1])
            if seasonName == '': continue
            
            sNum = self.cm.ph.getSearchGroups(seasonName, '''\s*?([0-9]+)''')[0]
            
            self.seasonsCache.append({'title':seasonName, 'episodes':[]})
            episodes = self.cm.ph.getAllItemsBeetwenMarkers(item, '<a', '</a>')
            re.findall('<a title="([^"]*?)"[^>]+?href="([^"]+?)"[^>]*?>(.+?)</a>', item)
            for e in episodes:
                url = self.cm.ph.getSearchGroups(e, '''href=['"](https?://[^'^"]+?)['"]''')[0] 
                if not self.cm.isValidUrl(url): continue
                title = self.cleanHtmlStr(e)
                eNum  = self.cm.ph.getSearchGroups(title, '''\s*?([0-9]+)''')[0]
                if 'odcinek' in title.lower() and len(url) < 20 and eNum != '' and sNum != '':
                    title = 's%se%s ' % (sNum.zfill(2), eNum.zfill(2))
                else:
                    if eNum != '' and sNum != '':
                        num = ' s%se%s, ' % (sNum.zfill(2), eNum.zfill(2))
                    else: num = ''
                    title = '%s%s, %s' % (num, seasonName, title)
                title = '%s - %s' % (serieTitle, title)
                self.seasonsCache[-1]['episodes'].append({'good_for_fav': True, 'title':title, 'url':url, 'desc':desc})
        
        if 1 < len(self.seasonsCache):
            seasonsId = 0
            for item in self.seasonsCache:
                params = dict(cItem)
                params.update({'good_for_fav': False, 'seasons_id':seasonsId, 'title':item['title'], 'category':category, 'icon':icon, 'desc':desc})
                self.addDir(params)
                seasonsId += 1
        elif 1 == len(self.seasonsCache):
            cItem.update({'seasons_id':0})
            self.listEpisodes(cItem)
    
    def listEpisodes(self, cItem):
        seasonsID = cItem.get('seasons_id', -1)
        if -1 < seasonsID and seasonsID < len(self.seasonsCache):
            season = self.seasonsCache[seasonsID]
            printDBG(">>>>>>>>>>>>>>>>>>>>>>>>>>>> listEpisodes[%s]" % season)
            for item in season['episodes']:
                params = dict(cItem)
                params.update(item)
                self.addVideo(params)
               
    def listLastUpdated(self, cItem, category):
        printDBG("SerialeNet.listLastUpdated")
        url = self.getFullUrl(cItem['url'])
        sts, data = self.cm.getPage(url)
        if sts:
            data = self.cm.ph.getDataBeetwenMarkers(data, '<h2>Ostatnio dodane</h2> <div class="item">', '<script>', False)[1]
            data = data.split('<div class="item">')
            for item in data:
                desc  = self.cleanHtmlStr(item)
                icon  = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'src="([^"]+?)"')[0])
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<p id="s_title">', '</p>', False)[1])
                url   = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0])
                params = dict(cItem)
                params.update({'good_for_fav': True, 'category':category, 'title':title, 'icon':icon, 'desc':desc, 'url':url})
                self.addDir(params)
                    
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("SerialeNet.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        keywordList = self.cm.ph.getNormalizeStr(searchPattern).upper().split(' ')
        keywordList = set(keywordList)
        if len(keywordList):
            series  = self._listsSeries(self.getMainUrl())
            for item in series:
                txt = self.cm.ph.getNormalizeStr( (item['t1'] + ' ' +  item['t2']) ).upper()
                txtTab = txt.split(' ')
                matches = 0
                for word in keywordList:
                    if word in txt: matches += 1
                    if word in txtTab: matches += 10
                if 0 < matches:
                    title = item['t1']
                    if len(item['t2']): title += ' (%s)' % item['t2']
                    params = dict(cItem)
                    params.update({'title':title, 'url':item['url'], 'matches':matches})
                    self.addDir(params)
            self.currList.sort(key=lambda item: item.get('matches', 0), reverse=True)
    
    def getLinksForVideo(self, cItem):
        videoUrlTab = []
        baseUrl   = self.getFullUrl( cItem['url'] )
        try:
            sts, data = self.cm.getPage( baseUrl )
            verUrl = self.getFullUrl(self.cm.ph.getSearchGroups(data, '<iframe id="framep" class="radi" src="([^"]+?)"')[0])
            sts, data = self.cm.getPage( verUrl )
            versions = []
            sts, data = self.cm.ph.getDataBeetwenMarkers(data, '<b>Wersja:</b>', '<script>', False)
            if sts:
                data = data.split('<input')
                if len(data): del data[0]
                for item in data:
                    name  = self.cm.ph.getSearchGroups(item, 'name="([^"]+?)"')[0]
                    value = self.cm.ph.getSearchGroups(item, 'value="([^"]+?)"')[0]
                    versions.append({'title':value, 'url': verUrl + ('&wi=va&%s=%s' % (name, value) )})
            else:
                versions.append({'title':'', 'url': verUrl + '&wi=va'})
            for item in versions:
                try:
                    url = item['url']
                    sts, data = self.cm.getPage( url )
                    
                    videoUrl = ''
                    if "url: escape('http" in data:
                        match = re.search("url: escape\('([^']+?)'", data)
                        if match: videoUrl = match.group(1)
                    elif "eval(function(p,a,c,k,e,d)" in data:
                        printDBG( 'Host resolveUrl packed' )
                        match = re.search('eval\((.+?),0,{}\)\)', data, re.DOTALL)
                        if match: videoUrl = self.decodeJS('eval(' + match.group(1) + ',0,{}))')
                    elif "var flm = '" in data:
                        printDBG( 'Host resolveUrl var flm' )
                        match = re.search("var flm = '([^']+?)';", data)
                        if match: videoUrl = match.group(1)
                    elif 'primary: "html5"' in data:
                        printDBG( 'Host resolveUrl html5' )
                        match = re.search('file: "([^"]+?)"', data)
                        if match: videoUrl = match.group(1)
                    elif 'sources:' in data:
                        data2 = self.cm.ph.getDataBeetwenMarkers(data, 'sources:', ']', False)[1]
                        videoUrl = self.cm.ph.getSearchGroups(data2, '''src[^'"]*?['"](http[^'"]+?)['"]''')[0]
                        data2 = None
                    if videoUrl.startswith('http') and videoUrl != 'http://serialnet.pl/':
                        videoUrl = byteify(json.loads('"%s"' % videoUrl))
                        videoUrlTab.append({'name':item['title'], 'url':videoUrl})
                    else:
                        msg = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div id="errorbox"', '</div>')[1])
                        if msg == '': 
                            msg = self.cm.ph.getDataBeetwenMarkers(data, 'on("error"', '}', False)[1]
                            msg = self.cleanHtmlStr(self.cm.ph.getSearchGroups(msg, "text\('([^']+?)'")[0])
                        SetIPTVPlayerLastHostError(msg)
                    printDBG("SerialeNet.getLinksForVideo >>>>>>>>>>>>>>>> videoUrl[%s]" % videoUrl)
                except Exception: printExc()
        except Exception: printExc()
        return videoUrlTab 
        
    def getVideoLink(self, url):
        printDBG("getVideoLink url [%s]" % url)
        
    def getFavouriteData(self, cItem):
        printDBG('SerialeNet.getFavouriteData')
        return json.dumps(cItem)
        
    def getLinksForFavourite(self, fav_data):
        printDBG('SerialeNet.getLinksForFavourite')
        links = []
        try:
            cItem = byteify(json.loads(fav_data))
            links = self.getLinksForVideo(cItem)
        except Exception: printExc()
        return links
        
    def setInitListFromFavouriteItem(self, fav_data):
        printDBG('SerialeNet.setInitListFromFavouriteItem')
        try:
            params = byteify(json.loads(fav_data))
        except Exception: 
            params = {}
            printExc()
        self.addDir(params)
        return True
    
    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('SerialeNet.handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name     = self.currItem.get("name", None)
        category = self.currItem.get("category", '')
        printDBG( "SerialeNet.handleService: ---------> name[%s], category[%s] " % (name, category) )
        searchPattern = self.currItem.get("search_pattern", searchPattern)
        self.currList = [] 

        if None == name:
            self.listsTab(self.CAT_TAB, {'name':'category'})
    #ABC
        elif category == 'abc_menu':
            self.listABC(self.currItem, 'series_by_letter')
    #BY LETTER
        elif category == 'series_by_letter':
            self.listsSeriesByLetter(self.currItem, 'seasons')
    #SEASONS
        elif category == 'seasons':
            self.listSeasons(self.currItem, 'episodes')
    #EPISODES
        elif category == 'episodes':
            self.listEpisodes(self.currItem)
    #LAST UPDATED
        elif category == 'last_update':
            self.listLastUpdated(self.currItem, 'seasons')
    #WYSZUKAJ
        elif category == "search":
            cItem = dict(self.currItem)
            cItem.update({'good_for_fav': True, 'category':'seasons', 'search_item':False, 'name':'category'}) 
            self.listSearchResult(cItem, searchPattern, searchType)
    #HISTORIA WYSZUKIWANIA
        elif category == "search_history":
            self.listsHistory({'name':'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, SerialeNet(), True)
    