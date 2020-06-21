# -*- coding: utf-8 -*-

#
#
# @Codermik release, based on @Samsamsam's E2iPlayer public.
# Released with kind permission of Samsamsam.
# All code developed by Samsamsam is the property of the Samsamsam and the E2iPlayer project,  
# all other work is � E2iStream Team, aka Codermik.  TSiPlayer is � Rgysoft, his group can be
# found here:  https://www.facebook.com/E2TSIPlayer/
#
# https://www.facebook.com/e2iStream/
#
#

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs import ph
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib

def gettytul():
    return 'https://lookmovie.ag/'

class LookMovieag(CBaseHostClass):

    def __init__(self):
        printDBG("..:: E2iStream ::..   __init__(self):")
        CBaseHostClass.__init__(self, {'history':'lookmovie.ag', 'cookie':'lookmovie.ag.cookie'})
        
        self.MAIN_URL = 'https://lookmovie.ag'

        self.USER_AGENT = 'Mozilla/5.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'DNT':'1', 'Accept': 'text/html', 'Accept-Encoding':'gzip, deflate', 'Referer':self.getMainUrl(), 'Origin':self.getMainUrl()}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update( {'X-Requested-With':'XMLHttpRequest', 'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8'} )
        
        self.DEFAULT_ICON_URL = 'https://lookmovie.ag/assets/logo1.png'

        self.defaultParams = {'header':self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}     
        
        self.HOST_VER = '1.7 (02/01/2020)'

        self.MAIN_CAT_TAB =     [
                                    {'category':'movies',         'title': _('Movies'),       'url':self.MAIN_URL, 'desc': '\c00????00 Info: \c00??????Movies\\n \c00????00Version: \c00??????'+self.HOST_VER+'\\n \c00????00Developer: \c00??????Codermik\\n', 'icon':self.DEFAULT_ICON_URL},
                                    {'category':'tvseries',       'title': _('TV Series'),    'url':self.MAIN_URL + '/shows/filter?r=&so=', 'desc': '\c00????00 Info: \c00??????TV Series and Episodes\\n \c00????00Version: \c00??????'+self.HOST_VER+'\\n \c00????00Developer: \c00??????Codermik\\n', 'icon':self.DEFAULT_ICON_URL},
                                    {'category':'search',   'title': _('Search'), 'desc': '\c00????00 Info: \c00??????Search for Movies\\n \c00????00Version: \c00??????'+self.HOST_VER+'\\n \c00????00Developer: \c00??????Codermik\\n', 'search_item':True},
                                    {'category':'search_history', 'desc': '\c00????00 Info: \c00??????Select from your search history\\n \c00????00Version: \c00??????'+self.HOST_VER+'\\n \c00????00Developer: \c00??????Codermik\\n', 'title': _('Search history')} 
                                ]

        self.MOVIE_SUB_CAT =    [
                                    {'category':'allmovies',      'title': _('All'),       'url':self.MAIN_URL, 'desc': '\c00????00 Info: \c00??????Show all available movies (no filtering).\\n \c00????00Version: \c00??????'+self.HOST_VER+'\\n \c00????00Developer: \c00??????Codermik\\n', 'icon':self.DEFAULT_ICON_URL},
                                    {'category':'sortbyyear',   'title': _('Filter By Year'),       'url':self.MAIN_URL + '/movies', 'desc': '\c00????00 Info: \c00??????Show all movies in a chosen year.\\n \c00????00Version: \c00??????'+self.HOST_VER+'\\n \c00????00Developer: \c00??????Codermik\\n', 'icon':self.DEFAULT_ICON_URL},
                                    {'category':'moviegenres',    'title': _('Genres'),       'url':self.MAIN_URL + '/movies/genres', 'desc': '\c00????00 Info: \c00??????Browse movies by Genre.\\n \c00????00Version: \c00??????'+self.HOST_VER+'\\n \c00????00Developer: \c00??????Codermik\\n', 'icon':self.DEFAULT_ICON_URL}                               
                                ]

        self.GENRE_SUB_CAT =    [
                                    {'category':'listgenre',    'title': _('Action Movies'),       'url':self.MAIN_URL + '/movies/genre/action', 'desc': '\c00????00 Info: \c00??????Filter by action movies.\\n \c00????00Version: \c00??????'+self.HOST_VER+'\\n \c00????00Developer: \c00??????Codermik\\n', 'icon':self.DEFAULT_ICON_URL},                               
                                    {'category':'listgenre',    'title': _('Adventure Movies'),       'url':self.MAIN_URL + '/movies/genre/adventure', 'desc': '\c00????00 Info: \c00??????Filter by adventure movies.\\n \c00????00Version: \c00??????'+self.HOST_VER+'\\n \c00????00Developer: \c00??????Codermik\\n', 'icon':self.DEFAULT_ICON_URL},                               
                                    {'category':'listgenre',    'title': _('Animation Movies'),       'url':self.MAIN_URL + '/movies/genre/animation', 'desc': '\c00????00 Info: \c00??????Filter by animation movies.\\n \c00????00Version: \c00??????'+self.HOST_VER+'\\n \c00????00Developer: \c00??????Codermik\\n', 'icon':self.DEFAULT_ICON_URL},                               
                                    {'category':'listgenre',    'title': _('Comedy Movies'),       'url':self.MAIN_URL + '/movies/genre/comedy', 'desc': '\c00????00 Info: \c00??????Filter by comedy movies.\\n \c00????00Version: \c00??????'+self.HOST_VER+'\\n \c00????00Developer: \c00??????Codermik\\n', 'icon':self.DEFAULT_ICON_URL},                               
                                    {'category':'listgenre',    'title': _('Crime Movies'),       'url':self.MAIN_URL + '/movies/genre/crime', 'desc': '\c00????00 Info: \c00??????Filter by crime movies.\\n \c00????00Version: \c00??????'+self.HOST_VER+'\\n \c00????00Developer: \c00??????Codermik\\n', 'icon':self.DEFAULT_ICON_URL},                               
                                    {'category':'listgenre',    'title': _('Drama Movies'),       'url':self.MAIN_URL + '/movies/genre/drama', 'desc': '\c00????00 Info: \c00??????Filter by drama movies.\\n \c00????00Version: \c00??????'+self.HOST_VER+'\\n \c00????00Developer: \c00??????Codermik\\n', 'icon':self.DEFAULT_ICON_URL},                               
                                    {'category':'listgenre',    'title': _('Documentary Movies'),       'url':self.MAIN_URL + '/movies/genre/documentary', 'desc': '\c00????00 Info: \c00??????Filter by documentary movies.\\n \c00????00Version: \c00??????'+self.HOST_VER+'\\n \c00????00Developer: \c00??????Codermik\\n', 'icon':self.DEFAULT_ICON_URL},                               
                                    {'category':'listgenre',    'title': _('Sci-Fi Movies'),       'url':self.MAIN_URL + '/movies/genre/science-fiction', 'desc': '\c00????00 Info: \c00??????Filter by Sci-Fi movies.\\n \c00????00Version: \c00??????'+self.HOST_VER+'\\n \c00????00Developer: \c00??????Codermik\\n', 'icon':self.DEFAULT_ICON_URL},                               
                                    {'category':'listgenre',    'title': _('Family Movies'),       'url':self.MAIN_URL + '/movies/genre/family', 'desc': '\c00????00 Info: \c00??????Filter by action movies.\\n \c00????00Version: \c00??????'+self.HOST_VER+'\\n \c00????00Developer: \c00??????Codermik\\n', 'icon':self.DEFAULT_ICON_URL},                               
                                    {'category':'listgenre',    'title': _('History Movies'),       'url':self.MAIN_URL + '/movies/genre/history', 'desc': '\c00????00 Info: \c00??????Filter by history movies.\\n \c00????00Version: \c00??????'+self.HOST_VER+'\\n \c00????00Developer: \c00??????Codermik\\n', 'icon':self.DEFAULT_ICON_URL},                               
                                    {'category':'listgenre',    'title': _('Fantasy Movies'),       'url':self.MAIN_URL + '/movies/genre/fantasy', 'desc': '\c00????00 Info: \c00??????Filter by fantasy movies.\\n \c00????00Version: \c00??????'+self.HOST_VER+'\\n \c00????00Developer: \c00??????Codermik\\n', 'icon':self.DEFAULT_ICON_URL},                               
                                    {'category':'listgenre',    'title': _('Horror Movies'),       'url':self.MAIN_URL + '/movies/genre/horror', 'desc': '\c00????00 Info: \c00??????Filter by horror movies.\\n \c00????00Version: \c00??????'+self.HOST_VER+'\\n \c00????00Developer: \c00??????Codermik\\n', 'icon':self.DEFAULT_ICON_URL},                               
                                    {'category':'listgenre',    'title': _('Music Movies'),       'url':self.MAIN_URL + '/movies/genre/music', 'desc': '\c00????00 Info: \c00??????Filter by music movies.\\n \c00????00Version: \c00??????'+self.HOST_VER+'\\n \c00????00Developer: \c00??????Codermik\\n', 'icon':self.DEFAULT_ICON_URL},                               
                                    {'category':'listgenre',    'title': _('Mystery Movies'),       'url':self.MAIN_URL + '/movies/genre/mystery', 'desc': '\c00????00 Info: \c00??????Filter by mystery movies.\\n \c00????00Version: \c00??????'+self.HOST_VER+'\\n \c00????00Developer: \c00??????Codermik\\n', 'icon':self.DEFAULT_ICON_URL},                               
                                    {'category':'listgenre',    'title': _('Romance Movies'),       'url':self.MAIN_URL + '/movies/genre/romance', 'desc': '\c00????00 Info: \c00??????Filter by romance movies.\\n \c00????00Version: \c00??????'+self.HOST_VER+'\\n \c00????00Developer: \c00??????Codermik\\n', 'icon':self.DEFAULT_ICON_URL},                               
                                    {'category':'listgenre',    'title': _('Thriller Movies'),       'url':self.MAIN_URL + '/movies/genre/thriller', 'desc': '\c00????00 Info: \c00??????Filter by thriller movies.\\n \c00????00Version: \c00??????'+self.HOST_VER+'\\n \c00????00Developer: \c00??????Codermik\\n', 'icon':self.DEFAULT_ICON_URL},                               
                                    {'category':'listgenre',    'title': _('War Movies'),       'url':self.MAIN_URL + '/movies/genre/war', 'desc': '\c00????00 Info: \c00??????Filter by war movies.\\n \c00????00Version: \c00??????'+self.HOST_VER+'\\n \c00????00Developer: \c00??????Codermik\\n', 'icon':self.DEFAULT_ICON_URL},                               
                                    {'category':'listgenre',    'title': _('Western Movies'),       'url':self.MAIN_URL + '/movies/genre/western', 'desc': '\c00????00 Info: \c00??????Filter by western movies.\\n \c00????00Version: \c00??????'+self.HOST_VER+'\\n \c00????00Developer: \c00??????Codermik\\n', 'icon':self.DEFAULT_ICON_URL},                               
                                ]
    

    def _getFullUrl(self, url):
        if 0 < len(url) and not url.startswith('http'):
            url = self.MAIN_URL + url
        return url

    def getPage(self, baseUrl, addParams = {}, post_data = None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        def _getFullUrl(url):
            if self.cm.isValidUrl(url):
                return url
            else:
                return urljoin(baseUrl, url)             
        addParams['cloudflare_params'] = {'domain':self.up.getDomain(baseUrl), 'cookie_file':self.COOKIE_FILE, 'User-Agent':self.USER_AGENT, 'full_url_handle':_getFullUrl}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def buildYears(self, cItem):
        year = 2020
        while year >= 1921:
            tmpyear = '%s' % year
            params = dict(cItem)
            url = 'https://lookmovie.ag/?y[]=%s&r=&so=' % year
            params.update({'category':'listyears', 'title':tmpyear, 'url':url})
            self.addDir(params)
            year-=1

    def listEpisodes(self, cItem):
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        block = self.cleanHtmlStr(self.cm.ph.getAllItemsBeetwenNodes(data,'<script>window.route="shows/view";', ('</script>'))[0])
        block = block.replace('\\','')
        block = self.cm.ph.getAllItemsBeetwenNodes(block,'{', '}')
        series = cItem['title']
        for episodes in block:
            if 'id_episode' in episodes:
                title = self.cm.ph.getAllItemsBeetwenNodes(episodes,'title":"', '",',False)
                if title: title = title[0]
                else: title = " "
                episodeId = self.cm.ph.getAllItemsBeetwenNodes(episodes,'id_episode\":\"', '\"',False)[0]
                m3u8Url = 'https://lookmovie.ag/manifests/shows/9C60XF7yiUOfSOXUlkk4jg/4066244082/%s/master.m3u8' % episodeId
                season = self.cm.ph.getAllItemsBeetwenNodes(episodes,'season":"', '",',False)[0]  
                episode = self.cm.ph.getAllItemsBeetwenNodes(episodes,'"episode":"', '",',False)[0]
                desc = self.cm.ph.getAllItemsBeetwenNodes(episodes,'description":"', '",',False)  
                airing = self.cm.ph.getAllItemsBeetwenNodes(episodes,'air_date":"', '"}',False)
                if desc: desc = desc[0]
                else: desc = " "
                if airing: airing = airing[0]
                else: airing = " "
                title = '%s - %s   \c00????00[Season %s Episode %s]' %(series, title, season, episode)
                desc = '\c00????00 Title: \c00??????%s\\n \c00????00Aired: \c00??????%s\\n \c00????00Description: \c00??????%s\\n' %(title, airing, desc)
                params = dict(cItem) 
                params.update({'good_for_fav':True, 'title':self.cleanHtmlStr(title), 'url':m3u8Url, 'desc':self.cleanHtmlStr(desc)})
                self.addVideo(params)

    def listItems(self, cItem):          
        page = cItem.get('page', 1)        
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        self.setMainUrl(self.cm.meta['url']) 
        tmpurl = self.cm.meta['url']
        nextPage = ''

        if 'Found 0' in data:
            printDBG('E2iStream >>>>>> listItems >>>>>>> No results found!')
        else:
            try:
                if 'a class="pagination_next"' in data:
                    nextPage = self.cm.ph.getAllItemsBeetwenNodes(data, ('a class="pagination_next"', 'ion-arrow-right-b'), ('</a>'))[0]
                    nextPage = self.MAIN_URL + self.cm.ph.getAllItemsBeetwenNodes(nextPage,'href="//lookmovie.ag/', ('">'),False)[0]
                block = self.cm.ph.getAllItemsBeetwenNodes(data, ('div class="flex-wrap-movielist"', 'movie-item'), ('<div class="pagination-template"'))[0]
                block = self.cm.ph.getAllItemsBeetwenNodes(block, ('div class="movie-item', 'movie-item'), ('</h6>'))
                if len(block) < 40: nextPage = ''
                for items in block:
                    title = self.cm.ph.getAllItemsBeetwenNodes(items,'<div class="mv-item-infor">', ('</h6>'),False)[0]
                    title = self.cm.ph.getAllItemsBeetwenNodes(title,'">', ('</a>'),False)[0]
                    title = title.replace(' ', ' ')
                    self.cleanHtmlStr(data)
                    year = self.cm.ph.getAllItemsBeetwenNodes(items,'<p class="year">', ('</p>'),False)[0]
                    if '<div class="quality-tag tooltip">' in items: 
                        quality = self.cm.ph.getAllItemsBeetwenNodes(items,'<div class="quality-tag tooltip">', ('<span'),False)[0]
                        if 'HD' in quality: 
                            quality = 'HD' 
                            tooltip = 'High Definition. Look Movie brings you this movie in multiple Definitions. 1080p, 720p, 480p, 360p - for all types of connection speeds.  This movie was encoded directly from a Blu-ray disc to 4 variations.'
                            title += '  \c00????00('+quality+')'
                    elif '<div class="bad quality-tag tooltip">' in items:
                        quality = self.cm.ph.getAllItemsBeetwenNodes(items,'<div class="bad quality-tag tooltip">', ('<span'),False)[0]
                        if 'LQ' in quality: 
                            quality = 'LQ' 
                            tooltip = 'Low Quality (Cam?) - Sometimes Look Movie does not update LQ to HQ when a cam version is replaced on the website - its always good practice to check the movie manually. CM'
                            title += '  \c00????00('+quality+')'
                    else:
                        quality = ''
                        if '/shows/' in tmpurl: tooltip = '720p Quality'
                        else: tooltip = 'No quality has been specified.'
                    videoUrl = self.cm.ph.getSearchGroups(items, 'href="([^"]+?)"')[0]
                    videoUrl = self.MAIN_URL + videoUrl[:0] + videoUrl[1:]  # removing the the double // at the start of the url
                    imageUrl = self.cm.ph.getSearchGroups(items, 'data-src="([^"]+?)"')[0]
                    desc = '\c00????00 Title: \c00??????'+title+'\\n \c00????00Year: \c00??????'+year+'\\n \c00????00Description: \c00??????'+tooltip
                    params = dict(cItem)                    
                    if '/shows/' in tmpurl: 
                        params.update({'good_for_fav':True, 'category':'tvshow', 'title':self.cleanHtmlStr(title), 'url':videoUrl, 'icon':imageUrl, 'desc':self.cleanHtmlStr(desc)})
                        self.addDir(params)
                    else: 
                        params.update({'good_for_fav':True, 'title':self.cleanHtmlStr(title), 'url':videoUrl, 'icon':imageUrl, 'desc':self.cleanHtmlStr(desc)})
                        self.addVideo(params)
            except:
                printDBG('e2iStream >>>>>>>>>>> failed to parse website data - please report!')

        if nextPage != '':
           params = dict(cItem)
           params.update({'good_for_fav': False, 'title': _('Next Page'), 'page': cItem.get('page', 1) + 1, 'url': self._getFullUrl(nextPage)})
           self.addDir(params)
              
    def listSearchResult(self, cItem, searchPattern, searchType):   
        cItem = dict(cItem)
        if searchType == 'movies': cItem['url'] = self.getFullUrl('/movies/search/?q=') + urllib.quote(searchPattern) 
        elif searchType == 'tvseries': cItem['url'] = self.getFullUrl('/shows/search/?q=') + urllib.quote(searchPattern)
        cItem['category'] = 'list_items'
        self.listItems(cItem)

    def getVideoLinks(self, videoUrl):
        return  self.up.getVideoLinkExt(videoUrl)

    def getLinksForVideo(self, cItem):
        urlTab = []
        sts, data = self.getPage(cItem['url'])
        if not sts: return []
        self.setMainUrl(self.cm.meta['url'])           
        tmpurl = self.cm.meta['url']
        if '/shows/' in tmpurl:
            # episodes only have one quality and feed (720p), 
            # just return the 720p full url.
            urlTab.append({'name': 'episodeplay', 'url': tmpurl, 'need_resolve': 1})
        else:
            movieId = self.cm.ph.getAllItemsBeetwenNodes(data,'window.id_movie=\'', ('\';</script>'),False)[0]  
            tmpUrl = 'https://lookmovie.ag/manifests/movies/json/%s/1564684248/kSrTkeFjYz3FUOpCjEHiGw/master.m3u8?extClient=true' % movieId
            sts, tmpData = self.getPage(tmpUrl)
            videoUrls = self.cm.ph.getAllItemsBeetwenNodes(tmpData,'p":"', ('"'),False)
            quality = ''
            avail1080 = False
            for links in videoUrls:
                if '1080p' in links:
                    avail1080 = True
                    continue
                if '720p' in links: 
                    if avail1080:
                        avail1080 = False
                        tmpUrl = links    # temporarily store the 720p url
                        links = links.replace("720p", "1080p")
                        urlTab.append({'name': '1080p Quality', 'url': links, 'need_resolve': 1})
                        urlTab.append({'name': '720p Quality', 'url': tmpUrl, 'need_resolve': 1})                
                        continue
                    else: quality = '720p Quality'
                elif '480p' in links: quality = '480p Quality'
                elif '360p' in links: quality = '360p Quality'
                else: continue            
                urlTab.append({'name': quality, 'url': links, 'need_resolve': 1})
        return urlTab
    
    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):        
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name     = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode     = self.currItem.get("mode", '')   
        
        self.currList = []
        
        # First Menu    
        if name == None:
            self.listsTab(self.MAIN_CAT_TAB, self.currItem)        
        # movie section
        elif category == 'movies': self.listsTab(self.MOVIE_SUB_CAT, self.currItem)
        elif category == 'allmovies': self.listItems(self.currItem)
        elif category == 'sortbyyear': self.buildYears(self.currItem)
        elif category == 'listyears': self.listItems(self.currItem)
        elif category == 'moviegenres': self.listsTab(self.GENRE_SUB_CAT, self.currItem)
        elif category == 'listgenre': self.listItems(self.currItem)
        elif category == 'tvseries': self.listItems(self.currItem)
        elif category == 'tvshow': self.listEpisodes(self.currItem)
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item':False, 'name':'category'}) 
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({'name':'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()
        
        CBaseHostClass.endHandleService(self, index, refresh)

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, LookMovieag(), True, favouriteTypes=[]) 

    def getSearchTypes(self):
        searchTypesOptions = []
        searchTypesOptions.append((_("Movies"), "movies"))
        searchTypesOptions.append((_("TV Series"), "tvseries"))
        return searchTypesOptions

