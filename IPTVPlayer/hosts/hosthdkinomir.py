# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.libs.moonwalkcc import MoonwalkParser
from Plugins.Extensions.IPTVPlayer.libs.youtubeparser import YouTubeParser
###################################################

###################################################
# FOREIGN import
###################################################
import re
try:
    import json
except Exception:
    import simplejson as json
###################################################


def gettytul():
    return 'http://hdkinomir.com/'


class HDKinoMir(CBaseHostClass):
 
    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'HDKinoMir', 'cookie': 'HDKinoMir.cookie'})
        self.USER_AGENT = "Mozilla/5.0 (Linux; U; Android 4.1.1; en-us; androVM for VirtualBox ('Tablet' version with phone caps) Build/JRO03S) AppleWebKit/534.30 (KHTML, like Gecko) Version/4.0 Safari/534.30"
        self.HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'text/html'}
        
        self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.sortCache = []
        self.catCache = []
        self.moonwalkParser = MoonwalkParser()
        self.ytParser = YouTubeParser()
        
        self.MAIN_URL = 'http://hdkinomir.com/'
        self.DEFAULT_ICON_URL = self.getFullIconUrl('/templates/prokino/images/logo.png')
        
        self.MAIN_CAT_TAB = [{'category': 'categories', 'title': _('Movie categories'), 'url': self.getMainUrl()},
                             {'category': 'search', 'title': _('Search'), 'search_item': True},
                             {'category': 'search_history', 'title': _('Search history')} 
                            ]
        
        self.encoding = ''
        
    def getPage(self, url, params={}, post_data=None):
        sts, data = self.cm.getPage(url, params, post_data)
        if sts and self.encoding == '':
            self.encoding = self.cm.ph.getSearchGroups(data, 'charset=([^"]+?)"')[0]
        return sts, data
    
    def getFullUrl(self, url):
        url = url.replace('&amp;', '&')
        return CBaseHostClass.getFullUrl(self, url)
            
    def listMainMenu(self, cItem, category):
        printDBG("HDKinoMir.listCategories")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        
        if 0 == len(self.sortCache):
            sorData = self.cm.ph.getDataBeetwenMarkers(data, '<form name="news_set_sort"', '/> ', False)[1]
            sorData = re.compile("dle_change_sort\('([^']+?)','([^']+?)'\)[^>]*?>([^<]+?)<").findall(sorData)
            for item in sorData:
                post_data = {'dlenewssortby': item[0], 'dledirection': item[1], 'set_new_sort': 'dle_sort_cat', 'set_direction_sort': 'dle_direction_cat'}
                params = {'title': item[2], 'post_data': post_data}
                self.sortCache.append(params)
        
        if 0 == len(self.catCache):
            catData = self.cm.ph.getDataBeetwenMarkers(data, '<div class="films-category">', '</div> ', False)[1]
            catData = re.compile('href="([^"]+?)"[^>]*?>([^<]+?)<').findall(catData)
            for item in catData:
                params = dict(cItem)
                params.update({'category': category, 'title': item[1], 'url': self.getFullUrl(item[0])})
                self.catCache.append(params)
        
        mainMenuData = self.cm.ph.getDataBeetwenMarkers(data, '<div class="top-menu-block">', '</ul>', False)[1]
        mainMenuData = re.compile('href="([^"]+?)"[^>]*?>([^<]+?)<').findall(mainMenuData)
        for item in mainMenuData:
            if item[0] in ['/actors/', '/podborki-filmov.html']:
                continue
            params = dict(cItem)
            params.update({'category': category, 'title': item[1], 'url': self.getFullUrl(item[0])})
            self.addDir(params)
        
        self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})
            
    def listContent(self, cItem, category):
        printDBG("HDKinoMir.listContent")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        
        desc = self.cm.ph.getDataBeetwenMarkers(data, '<div class="full-right-detailes">', '<div style="clear:both;">', False)[1]
        desc = self.cleanHtmlStr(desc)
        title = cItem['title']
        
        seriesData = self.cm.ph.getAllItemsBeetwenMarkers(data, '<strong class="seria">', '</center>', False) 
        if len(seriesData) > 1:
            for item in seriesData:
                url = self.cm.ph.getSearchGroups(item, '<iframe[^>]+?src="([^"]+?)"', 1, True)[0]
                if url.startswith('//'):
                    url = 'http:' + url
                params = dict(cItem)
                params['desc'] = desc
                params['url'] = url
                hostName = self.up.getHostName(url)
                if 'youtube' in hostName and 'list=' in url:
                    params.update({'host_name': 'youtube_tray', 'category': category, 'title': self.cleanHtmlStr(item), 'serie_title': title})
                    self.addDir(params)
                    continue
                if 1 == self.up.checkHostSupport(url):
                    params['title'] = '{0} - {1}'.format(title, self.cleanHtmlStr(item))
                    self.addVideo(params)
            return
        
        data = re.compile('<iframe[^>]+?src="([^"]+?)"', re.IGNORECASE).findall(data)
        for url in data:
            if url.startswith('//'):
                url = 'http:' + url
            params = dict(cItem)
            params['desc'] = desc
            params['url'] = url
            hostName = self.up.getHostName(url)
            if hostName in ['serpens.nl', '37.220.36.15', 'daaidaij.com', 'mastarti.com']:
                hostName = 'moonwalk.cc'
            
            if hostName == 'moonwalk.cc' and '/serial/' in url:
                    params.update({'category': category, 'serie_title': title})
                    season = self.moonwalkParser.getSeasonsList(url)
                    for item in season:
                        param = dict(params)
                        param.update({'host_name': 'moonwalk', 'title': item['title'], 'season_id': item['id'], 'url': item['url']})
                        self.addDir(param)
                    return
            if 1 == self.up.checkHostSupport(url):
                self.addVideo(params)
    
    def listEpisodes(self, cItem):
        printDBG("HDKinoMir.listEpisodes")
        
        hostName = cItem['host_name']
        if hostName == 'moonwalk':
            title = cItem['serie_title']
            id = cItem['season_id']
            episodes = self.moonwalkParser.getEpiodesList(cItem['url'], id)
            
            for item in episodes:
                params = dict(cItem)
                params.update({'title': '{0} - s{1}e{2} {3}'.format(title, id, item['id'], item['title']), 'url': item['url']})
                self.addVideo(params)
        elif hostName == 'youtube_tray':
            try: 
                list = self.ytParser.getVideosFromTraylist(cItem['url'], 'video', 1, cItem)
            except Exception:
                printExc()
                return
            for item in list:
                if item['category'] != 'video':
                    continue
                self.addVideo(item)
        
    def listItems(self, cItem, category):
        printDBG("HDKinoMir.listItems")
        
        tmp = cItem['url'].split('?')
        url = tmp[0]
        if len(tmp) > 1:
            arg = tmp[1]
        else:
            arg = ''
        
        page = cItem.get('page', 1)
        if page > 1:
            url += 'page/%s/' % page
        if '' != arg:
            url += '?' + arg
        
        post_data = cItem.get('post_data', None)
        sts, data = self.getPage(url, {}, post_data)
        if not sts:
            return
        
        nextPage = False
        if ('/page/%s/' % (page + 1)) in data:
            nextPage = True
        
        m1 = '<div class="filmposters">'
        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'filmposters'), ('<div', '>', 'center'), False)[1]
        data = data.split(m1)
        
        if len(data):
            data[-1] = data[-1].split('<div class="navigation">')[0]
        for item in data:
            url = self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0]
            title = self.cm.ph.getSearchGroups(item, 'alt="([^"]+?)"')[0]
            if title == '{title}':
                title = self.cm.ph.getDataBeetwenMarkers(item, '<span>', '</span>', False)[1]
            title = self.cleanHtmlStr(title)
            
            if title == '':
                continue
            icon = self.cm.ph.getSearchGroups(item, 'src="([^"]+?)"')[0]
            desc = self.cleanHtmlStr(item.split('<div class="ribbon">')[-1])
            params = dict(cItem)
            params.update({'category': category, 'title': title, 'icon': self.getFullUrl(icon), 'desc': desc, 'url': self.getFullUrl(url)})
            self.addDir(params)
        
        if nextPage:
            params = dict(cItem)
            params.update({'title': _('Next page'), 'page': cItem.get('page', 1) + 1})
            self.addDir(params)
        
    def listSearchResult(self, cItem, searchPattern, searchType):
        #searchPattern = 'ОРБИТА'
        
        if self.encoding == '':
            sts, data = self.getPage(self.getMainUrl())
            if not sts:
                return
        
        try:
            searchPattern = searchPattern.decode('utf-8').encode(self.encoding, 'ignore')
        except Exception:
            searchPattern = ''
        
        post_data = {'do': 'search', 'subaction': 'search', 'story': searchPattern, 'x': 0, 'y': 0}
        
        sts, data = self.getPage(self.getMainUrl(), post_data=post_data)
        if not sts:
            return
        
        m1 = '<div class="filmposters">'
        data = self.cm.ph.getDataBeetwenMarkers(data, m1, '<div class="main">', False)[1]
        data = data.split(m1)
        for item in data:
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h2', '</h2>')[1])
            if title == '':
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''alt=['"]([^'^"]+?)['"]''')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0])
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '</h2>', '</div>')[1])
            if self.cm.isValidUrl(url):
                params = dict(cItem)
                params.update({'category': 'list_content', 'title': title, 'icon': icon, 'desc': desc, 'url': url})
                self.addDir(params)
        
    def getLinksForVideo(self, cItem):
        printDBG("HDKinoMir.getLinksForVideo [%s]" % cItem)
        urlTab = []
        urlTab.append({'name': 'Main url', 'url': cItem['url'], 'need_resolve': 1})
        return urlTab
        
    def getVideoLinks(self, videoUrl):
        printDBG("HDKinoMir.getVideoLinks [%s]" % videoUrl)
        urlTab = []
        
        if 'HDKinoMir.com' in videoUrl:
            sts, data = self.getPage(videoUrl)
            if not sts:
                return []
            data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="wbox2 video dark">', '</iframe>', False)[1]
            videoUrl = self.cm.ph.getSearchGroups(data, '<iframe[^>]+?src="(http[^"]+?)"', 1, True)[0]
        
        if videoUrl.startswith('http'):
            urlTab = self.up.getVideoLinkExt(videoUrl)
        return urlTab
        
    def getFavouriteData(self, cItem):
        return cItem['url']
        
    def getLinksForFavourite(self, fav_data):
        return self.getLinksForVideo({'url': fav_data})
    
    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')
        
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []
        
    #MAIN MENU
        if name == None:
            self.listMainMenu({'name': 'category', 'icon': self.DEFAULT_ICON_URL, 'url': self.MAIN_URL}, 'show_sort')
        elif category == 'categories':
            self.listsTab(self.catCache, self.currItem)
        elif category == 'show_sort':
            cItem = dict(self.currItem)
            cItem['category'] = 'list_items'
            self.listsTab(self.sortCache, cItem)
        elif category == 'list_items':
            self.listItems(self.currItem, 'list_content')
        elif category == 'list_content':
            self.listContent(self.currItem, 'list_episodes')
        elif category == 'list_episodes':
            self.listEpisodes(self.currItem)
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
        CHostBase.__init__(self, HDKinoMir(), True, [CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO])

