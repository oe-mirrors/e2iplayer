# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetCookieDir
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
###################################################

###################################################
# FOREIGN import
###################################################
import re
import copy
try:
    import json
except Exception:
    import simplejson as json
###################################################

###################################################
# Config options for HOST
###################################################

class HdgoccParser():
    USER_AGENT = 'Mozilla/5.0'
    def __init__(self):
        self.up = urlparser()
        self.cm = common()
        self.HTTP_HEADER= {'User-Agent':self.USER_AGENT, 'Referer':''}
        self.COOKIEFILE = GetCookieDir("hdgocc.cookie")
        self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': self.COOKIEFILE}

    def getFullUrl(self, url, pathUrl):
        printDBG('HdgoccParser.getFullUrl')
        return self.cm.getFullUrl(pathUrl, url)
        baseUrl = self.up.getDomain(url, onlyDomain=False)
        if not self.cm.isValidUrl(pathUrl):
            if pathUrl.startswith('//'):
                pathUrl = 'http:' + pathUrl
            elif pathUrl.startswith('/'):
                pathUrl = baseUrl + pathUrl[1:]
            else:
                pathUrl = baseUrl + pathUrl
        return pathUrl
    
    def getSeasonsList(self, pageUrl):
        printDBG('HdgoccParser.getSeasonsList')
        seasonsTab = []
        
        refUrl = strwithmeta(pageUrl).meta.get('Referer', pageUrl)
        params = copy.deepcopy(self.defaultParams)
        params['header']['Referer'] = refUrl
        params['with_metadata'] = True
        sts, data = self.cm.getPage(pageUrl, params)
        if not sts:
            return []
        
        urlNext = self.cm.ph.getSearchGroups(data, '<iframe[^>]+?src="([^"]+?)"', 1, True)[0]
        urlNext = self.getFullUrl(data.meta['url'], urlNext)
        if self.cm.isValidUrl(urlNext):
            params['header']['Referer'] = pageUrl
            sts, data = self.cm.getPage(urlNext, params)
            if not sts:
                return []
            
        seasonData = self.cm.ph.getDataBeetwenMarkers(data, 'id="season"', '</select>', False)[1]
        printDBG(seasonData)
        seasonData = re.compile('<option[^>]+?value="([0-9]+?)">([^<]+?)</option>').findall(seasonData)
        seasonMainUrl = self.cm.ph.getDataBeetwenMarkers(data, "$('#season').val();", '});', False)[1]
        seasonMainUrl = self.cm.ph.getSearchGroups(seasonMainUrl, "var url = '([^']+?)'")[0]
        if seasonMainUrl == '':
            seasonMainUrl = pageUrl.split('?', 1)[0]
        seasonMainUrl += '?season='
        seasonMainUrl = self.getFullUrl(pageUrl, seasonMainUrl)
        
        for item in seasonData:
            seasonsTab.append({'title':item[1], 'id':int(item[0]), 'url': strwithmeta(seasonMainUrl + item[0], {'Referer':refUrl})})
        seasonsTab.sort(key=lambda item: item['id'])
        return seasonsTab
        
    def getEpiodesList(self, seasonUrl, seasonIdx):
        printDBG('HdgoccParser.getEpiodesList')
        episodesTab = []
        
        refUrl = strwithmeta(seasonUrl).meta.get('Referer', seasonUrl)
        params = copy.deepcopy(self.defaultParams)
        params['header']['Referer'] = refUrl
        params['with_metadata'] = True
        sts, data = self.cm.getPage(seasonUrl, params)
        if not sts:
            return []
        
        urlNext = self.cm.ph.getSearchGroups(data, '<iframe[^>]+?src="([^"]+?)"', 1, True)[0]
        urlNext = self.getFullUrl(data.meta['url'], urlNext)
        if self.cm.isValidUrl(urlNext):
            params['header']['Referer'] = seasonUrl
            sts, data = self.cm.getPage(urlNext, params)
            if not sts:
                return []
        
        if '.playlist.php' in seasonUrl:
            itemTitle = self.cm.ph.getSearchGroups(data, '''createTextNode\([^'^"]*?['"]([^'^"]+?)['"]''')[0]
            data = self.cm.ph.getDataBeetwenMarkers(data, 'season_list[0] =', ';', False)[1]
            data = re.compile('''['"]([^'^"]*?)['"]''').findall(data)
            idx = 0
            for idx in range(len(data)):
                vidUrl = self.getFullUrl(seasonUrl, data[idx])
                episodesTab.append({'title': itemTitle + str(idx+1), 'id':(idx+1), 'url':strwithmeta(vidUrl, {'Referer':refUrl})})
                
        elif '/serials/' in seasonUrl:
            episodeData = self.cm.ph.getDataBeetwenMarkers(data, 'id="episode"', '</select>', False)[1]
            episodeData = re.compile('<option[^>]+?value="([0-9]+?)">([^<]+?)</option>').findall(episodeData)
            episodeMainUrl = self.cm.ph.getDataBeetwenMarkers(data, "$('#episode').val();", '});', False)[1]
            episodeMainUrl = self.cm.ph.getSearchGroups(episodeMainUrl, "var url = '([^']+?)'")[0]
            episodeMainUrl = seasonUrl.split('?', 1)[0]
            episodeMainUrl += '?season=' + str(seasonIdx) + '&e='
            episodeMainUrl = self.getFullUrl(seasonUrl, episodeMainUrl)
            #int(item[0])
            idx = 1
            for item in episodeData:
                try:
                    id = int(self.cm.ph.getSearchGroups(' %s ' % item, '''[^0-9]([0-9]+?)[^0-9]''')[0])
                except Exception: 
                    printExc()
                    id = idx
                episodesTab.append({'title':item[1], 'id':id, 'url': strwithmeta(episodeMainUrl + item[0], {'host_name':'hdgo.cc', 'Referer':refUrl})})
                idx += 1
        episodesTab.sort(key=lambda item: item['id'])
        return episodesTab
