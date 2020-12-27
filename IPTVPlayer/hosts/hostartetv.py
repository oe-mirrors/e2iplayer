# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetDefaultLang
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib
import time
from datetime import datetime, timedelta
###################################################
# Config options for HOST
###################################################
from Components.config import config, ConfigYesNo, getConfigListEntry

config.plugins.iptvplayer.artetv_quality = ConfigYesNo(default = True)
config.plugins.iptvplayer.artetv_audio = ConfigYesNo(default = False)

def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Show only best quality of streams:"), config.plugins.iptvplayer.artetv_quality))
    optionList.append(getConfigListEntry(_("Show only audio in selected language:"), config.plugins.iptvplayer.artetv_audio))
    return optionList

###################################################


def gettytul():
    return 'https://www.arte.tv/'

class ArteTV(CBaseHostClass):
    
    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'arte.tv', 'cookie':'arte.tv.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36'
        self.MAIN_URL = 'https://www.arte.tv/'
        self.DEFAULT_ICON_URL = 'https://i.pinimg.com/originals/3c/e6/54/3ce6543cf583480fa6d0e233384f336e.jpg'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT':'1', 'Accept': 'text/html', 'Accept-Encoding':'gzip, deflate', 'Referer':self.getMainUrl(), 'Origin':self.getMainUrl()}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update( {'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding':'gzip, deflate', 'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8', 'Accept':'application/json, text/javascript, */*; q=0.01'} )
        
        # from hbbtv
        self.API_URL = 'http://www.arte.tv/hbbtvv2/services/web/index.php'
        self.API_ENDPOINTS = {
            'categories': '/EMAC/teasers/{type}/v2/{lang}',
            'category': '/EMAC/teasers/category/v2/{category_code}/{lang}',
            'subcategory': '/OPA/v3/videos/subcategory/{sub_category_code}/page/1/limit/100/{lang}',
            'magazines': '/OPA/v3/magazines/{lang}',
            'collection' : '/OPA/v3/videos/collection/SHOW/{collection_id}/{lang}',
            # program details
            'video': '/OPA/v3/videos/{program_id}/{lang}',
            # program streams
            'streams': '/OPA/v3/streams/{program_id}/{kind}/{lang}',
            'daily': '/OPA/v3/programs/{date}/{lang}'
        }

        
        self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        
    def parseDate(self, datestr):
        # remove weekday & timezone
        datestr = ' '.join(datestr.split(None)[1:5])
        
        #replace months with numbers - there will be problems with localization
        months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
        
        for i in range(12):
            datestr = datestr.replace(months[i],str(i+1))
        
        date = None
        try:
            date = datetime.strptime(datestr, '%d %m %Y %H:%M:%S')
        except:
            printExc()
        
        return date

    def getPage(self, baseUrl, addParams = {}, post_data = None):
        if addParams == {}: 
            addParams = dict(self.defaultParams)
        
        return self.cm.getPage(baseUrl, addParams, post_data)

    def mapVideo(self, item):
        
        label = item.get('title')
        subtitle = item.get('subtitle')
        if subtitle:
            label += " - " + subtitle        

        desc = []
        
        duration = int(item.get('duration') or 0) * 60 or item.get('durationSeconds')

        desc1 = ""
        if duration>0 :
            desc1 = _('Duration') + ": %s" % str(timedelta(seconds = duration)) 
        try: 
            airdate = item.get('broadcastBegin')
            if airdate is not None:
                desc1 = desc1 + " " + (_("Broadcast begins at %s") % datetime.strftime(self.parseDate(airdate), '%d %B %Y %H:%M:%S'))
        except:
            printExc()

        if desc1:
            desc.append(desc1)
        
        if item.get('fullDescription',''):
            desc.append(item.get('fullDescription',''))
        elif item.get('shortDescription',''):
            desc.append(item.get('shortDescription',''))
        
        if item.get('genrePresse'):
            desc.append( item.get('genrePresse'))
        
        desc = '\n'.join(desc)

        return {
            'kind': item.get('kind'),
            'programId': item.get('programId'),
            'title': label,
            'icon': item.get('imageUrl'),
            'desc' : desc,
        }
    
    def mapPlaylist(self, item):
        programId = item.get('programId')
        kind = item.get('kind')
        label = item.get('title')
        subtitle = item.get('subtitle')
        if subtitle:
            label += " - " + subtitle        
        
        desc = item.get('teaserText','')
        
        return {
            'title': label,
            'icon': item.get('imageUrl'),
            'desc': desc
        }
    
    def listMainMenu(self, cItem, nextCategory):
        printDBG("ArteTV.listMainMenu")
        
        lang = GetDefaultLang()
        url = self.getMainUrl()
        if lang in ['en', 'it', 'fr','de','es','pl']:
            url += lang
        
        sts, data = self.getPage(url)
        if not sts: return
        
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<a', '>', ' lang='), ('</a', '>'))
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(item)
            lang = url.split('/')[3]

            params = dict(cItem)
            params.update({'good_for_fav':False, 'category': nextCategory, 'title':title, 'url':url, 'f_lang':lang})
            printDBG(str(params))
            self.addDir(params)
            
        MAIN_CAT_TAB = [{'category':'search',         'title': _('Search'),          'search_item':True}, 
                        {'category':'search_history', 'title': _('Search history')},]
        
        self.listsTab(MAIN_CAT_TAB, cItem)
        
    def listLang(self, cItem, nextCategory):
        printDBG("ArteTV.listLang [%s]" % cItem)

        # home categories
        lang = cItem.get("f_lang", "en")
        home_url = self.API_URL + self.API_ENDPOINTS['categories'].format(type='home', lang=lang)
        
        LANG_CAT_TAB = [
                {'category': 'home_cat', 'key' : 'mostRecent', 'title': _('Most recent'), 'f_lang': lang, 'url': home_url}, 
                {'category': 'home_cat', 'key' : 'mostViewed', 'title': _('Most viewed'), 'f_lang': lang , 'url': home_url}, 
                {'category': 'home_cat', 'key' : 'lastChance', 'title': _('Last chance'), 'f_lang': lang , 'url': home_url}, 
                       ]
        self.listsTab(LANG_CAT_TAB, cItem)

        # categories
        url = self.API_URL + self.API_ENDPOINTS['categories'].format(type='categories', lang=lang)
        
        sts, data = self.getPage(url)

        if not sts:
            return
        
        try:
            response = json_loads(data)
            printDBG(str(response))
            
            for c in response.get("categories",[]):
                title = c.get("title","")
                code = c.get("code","")
                
                if title and code:
                    
                    cat_url = self.API_URL + self.API_ENDPOINTS['category'].format(category_code=code, lang=lang)
                    
                    params = dict(cItem)
                    params.update({'category':'category', 'title':title, 'code': code, 'url': cat_url})
                    printDBG(str(params))
                    self.addDir(params)
        except:
            printExc()
    
    def listItems(self, cItem, nextCategory):
        printDBG("ArteTV.listItems [%s]" % cItem)
        
        url = cItem.get('url','')
        lang = cItem.get("f_lang", "en")
        category = cItem.get("category", "category")
        key = cItem.get("key", "")
        
        sts, data = self.getPage(url)
        
        if not sts:
            return
        
        try:
            response = json_loads(data)
            
            if category == "home_cat":
                teasers = response.get("teasers",{})
                # read key 
                if key:
                    for v in teasers.get(key,[]):
                        videoInfo = self.mapVideo(v)
                        params = dict(cItem)
                        params.update(videoInfo)
                        printDBG(str(params))
                        self.addVideo(params)
            elif category == "collection":
                for v in response.get("videos",[]):
                    videoInfo = self.mapVideo(v)
                    params = dict(cItem)
                    params.update(videoInfo)
                    printDBG(str(params))
                    self.addVideo(params)
                        
            elif category == "list":
                for c in cItem.get("subitems",[]):
                    kind = c.get("kind", "")
                    programId=c.get("programId","")
                    
                    if kind == "SHOW":
                        params = dict(cItem)
                        params.update(c)
                        printDBG(str(params))
                        self.addVideo(params)
                    
                    if kind in ["TOPIC","TV_SERIES", "MAGAZINE"]:
                        playlistInfo = self.mapPlaylist(c)
                        params = dict(cItem)
                        params.update(playlistInfo)
                        params.update({'category': 'collection', 'url': self.API_URL + self.API_ENDPOINTS["collection"].format(collection_id = programId, lang = lang)})
                        printDBG(str(params))
                        self.addDir(params)
                    
                    else:
                        printDBG("unhandled kind: %s " % kind)    
            
            elif category == "category":
                # read key category
                for c in response["category"]:
                    title = c.get("title","")
                    code = c.get("code","")
                    category_type = c.get("type","")
                    
                    if title:

                        params = dict(cItem)
                        
                        if category_type == "category": 
                            cat_url = self.API_URL + self.API_ENDPOINTS['category'].format(category_code=code, lang=lang)
                            params.update({'category': category_type, 'title':title, 'code': code, 'url': cat_url})
                            printDBG(str(params))
                            self.addDir(params)

                        elif category_type in ["highlight", "collection", "listing"]:
                            # read sub items
                            subItems = []
                            
                            for cc in c.get("teasers", []):
                                 videoInfo = self.mapVideo(cc)
                                 subItems.append(videoInfo)
                            
                            params.update({'category': "list", 'title':title, 'subitems' : subItems})
                            printDBG(str(params))
                            self.addDir(params)
                                
                        #elif category_code == "magazine":
                        
                            
                
        except:
            printExc()
    
    def getLinksForVideo(self, cItem):
        printDBG("ArteTV.getLinksForVideo [%s]" % cItem)

        linksTab = []

        programId = cItem.get("programId","")
        kind = cItem.get("kind","")
        lang = cItem.get("f_lang","")
        
        if kind == "SHOW":
            url = self.API_URL + self.API_ENDPOINTS["streams"].format(program_id = programId, kind=kind, lang = lang)
            sts, data = self.getPage( url)
            
            if not sts:
                return
            
            try:
                response = json_loads(data)
                printDBG(str(response))
                
                videostreams = response.get("videoStreams",[])
                
                for v in videostreams:
                    videoUrl = v.get('url','')
                    if videoUrl:
                        slot = v.get('audioSlot',0)
                        quality = v.get('quality','')
                        height = int(v.get('height', 0))
                        width = int(v.get('width', 0))
                        label = v.get('audioLabel','audio')
                        
                        if config.plugins.iptvplayer.artetv_quality.value and (height < 700):
                            continue
                        if config.plugins.iptvplayer.artetv_audio.value and (slot > 1):
                            continue
                        
                        linksTab.append({'name': label + " %dx%d" %(width,height) , 'slot': slot, 'url': videoUrl })
                         
            except:
                printExc()
        
            linksTab = sorted(linksTab, key=lambda k: k['slot'] )
             
        else:
            printDBG("Unhandled kind: %s " % kind) 
        
        return linksTab
    
    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('handleService start')
        
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name     = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode     = self.currItem.get("mode", '')
        
        printDBG( "handleService: |||| name[%s], category[%s] " % (name, category) )
        self.cacheLinks = {}
        self.currList = []
        
        #MAIN MENU
        if name == None:
            self.listMainMenu({'name':'category'}, 'list_lang')
        elif category == 'list_lang':
            self.listLang(self.currItem, 'category')
        elif category in ['home_cat','category', 'list', 'collection']:
            self.listItems(self.currItem, 'list_items')
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
        CHostBase.__init__(self, ArteTV(), True, [])
        
    def getSearchTypes(self):
        searchTypesOptions = []
        searchTypesOptions.append(('English  ( EN )', "en"))
        searchTypesOptions.append(('Français ( FR )', "fr"))
        searchTypesOptions.append(('Deutsch  ( DE )', "de"))
        searchTypesOptions.append(('Español  ( ES )', "es"))
        searchTypesOptions.append(('Polski   ( PL )', "pl"))
        lang = GetDefaultLang()
        searchTypesOptions.sort(key=lambda x: -2 if x[1] == lang else 0)
        return searchTypesOptions
    
