# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _ ,SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute, js_execute_ext
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib
###################################################


def gettytul():
    return 'https://filmoviplex.com/'

class Filmoviplex(CBaseHostClass):
 
    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'filmoviplex.com', 'cookie':'filmoviplex.cookie'})
        
        self.USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.61 Safari/537.36'
        self.HEADER = {'User-Agent': self.USER_AGENT,  'Accept-Encoding':'gzip, deflate', 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update( {'X-Requested-With': 'XMLHttpRequest'} )
        self.defaultParams = {'header':self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        
        self.MAIN_URL       = 'https://filmoviplex.com/'
        
        self.DEFAULT_ICON_URL = 'https://www.filmoviplex.com/wp-content/uploads/2020/02/fpstyle.png'
        

        self.MAIN_CAT_TAB = [
            {'category':'list_items',      'title': _('Movies'),               'url':self.getFullUrl('/browse-all-videos-1.html')},
            {'category':'list_items',      'title': _('Popular Movies'),       'url':self.getFullUrl('/browse-popular-videos-1.html')},
            {'category':'list_items',      'title': _('Most Viewed Movies'),   'url':self.getFullUrl('/browse-views-videos-1.html')},
            {'category':'list_items',      'title': _('Top Movies'),           'url':self.getFullUrl('/browse-top-videos-1.html')},
            #{'category':'categories',      'title': _('Categories'),           'url': self.MAIN_URL },
            {'category':'list_items',      'title': _('Random Movies'),        'url':self.getFullUrl('/browse-random-videos-1.html')},
            {'category':'list_items',      'title': _('Series'),               'url':self.getFullUrl('/browse-series-videos-1.html')},
            {'category':'list_items',      'title': _('Popular Series'),       'url':self.getFullUrl('/browse-series-popular-1.html')},
            {'category':'list_items',      'title': _('Most Viewed Series'),   'url':self.getFullUrl('/browse-series-views-1.html')},
            {'category':'list_items',      'title': _('Top Series'),           'url':self.getFullUrl('/browse-series-top-1.html')},
            #{'category':'year',            'title': _('Year'),                 'url': self.MAIN_URL },
            {'category':'search',          'title': _('Search'),               'search_item':True  },
            {'category':'search_history',  'title': _('Search history') }
            ]
        
        self.cacheSeasons = []
        self.cacheLinks = {}
        self.cacheFilters = {'movies':[], 'top_movies':[], 'series':[], 'new_movies':[], 'new_episodes':[]}
        
    def getPage(self, url, params={}, post_data=None):
        HTTP_HEADER= dict(self.HEADER)
        params.update({'header':HTTP_HEADER})
        
        sts, data = self.cm.getPage(url, params, post_data)
        if sts and None == data:
            sts = False
        return sts, data
    
    def getUrlFromCode(self, script, s, ep):
        #examples
        #$(".openload1_1").append("<iframe id='openload' width='100%' height='500px' src='https://video.filmoviplex.com/e/SDFGREdDNEpSM1VLOE9udnJINlRDdz09' frameborder='0' allowfullscreen=''></iframe>")
        #$(".openload7_1").append("<h1>USKORO!!</h1>");
        
        re_string = "\$\(\"\.openload%d_%d\"\)\.append\((.*?)\)" % (s,ep)
        #printDBG(re_string)
        tag = self.cm.ph.getSearchGroups(script, re_string )[0]
        url = self.cm.ph.getSearchGroups(tag, '''src=['"](http[^'^"^>]+?)[>'"]''')[0]

        return url
        
    
    def replacewhitespace(self, data):
        data = data.replace(' ', '%20')
        return CBaseHostClass.cleanHtmlStr(data)

    def listsTab(self, tab, cItem, type='dir'):
        printDBG("Filmoviplex.listsTab")
        for item in tab:
            params = dict(cItem)
            params.update(item)
            params['name']  = 'category'
            if type == 'dir':
                self.addDir(params)
            else: self.addVideo(params)
            
    def fillCategories(self):
        printDBG("Filmoviplex.fillCategories")
        self.cacheFilters = {'movies':[], 'top_movies':[], 'series':[], 'new_movies':[], 'new_episodes':[]}
        sts, data = self.getPage(self.MAIN_URL)
        if not sts: return
        self.setMainUrl(self.cm.meta['url'])
        for cat in  [('top_movies',    '>Top Movies</a>',    '</ul>'), \
                     ('series',        '>Series</a>',        'divider'), \
                     ('new_movies',    '>New Movies</a>',    '</ul>'), \
                     ('new_episodes',  '>New Episodes</a>', '</ul>')]:
            self.cacheFilters[cat[0]] = [] 
            tmp = self.cm.ph.getDataBeetwenMarkers(data, cat[1], cat[2], False)[1]
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<a ', '</a>')
            for item in tmp:
                url = self.cm.ph.getSearchGroups(item, '''href=['"](http[^'^"^>]+?)[>'"]''')[0]
                if '' == url: continue
                self.cacheFilters[cat[0]].append({'title':self.cleanHtmlStr(item.split('</i>')[-1]), 'url':self._getFullUrl(url)})
        
    def listCategories(self, cItem, nextCategory):
        printDBG("Filmoviplex.listCategories")
        filter = cItem.get('filter', '')
        tab = self.cacheFilters.get(filter, [])
        if 0 == len(tab): self.fillCategories()
        tab = self.cacheFilters.get(filter, [])
            
        cItem = dict(cItem)
        cItem['category'] = nextCategory
        self.listsTab(tab, cItem)
        
    def listYears(self, cItem, nextCategory):
        printDBG("Filmoviplex.listYears")
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        self.setMainUrl(self.cm.meta['url'])
        tab = []
        data = self.cm.ph.getDataBeetwenMarkers(data, 'godine', '<script', False)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a ', '</a>')
        for item in data:
            url = self.cm.ph.getSearchGroups(item, '''href=['"](https?://[^'^"]+?)['"]''')[0]
            if '' == url: continue
            tab.append({'title':self.cleanHtmlStr(item), 'url':url})
        
        cItem = dict(cItem)
        cItem['category'] = nextCategory
        self.listsTab(tab, cItem)
        
    def listMovieCats(self, cItem, nextCategory):
        printDBG("Filmoviplex.listMovieCats")
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        self.setMainUrl(self.cm.meta['url'])
        tab = []
        data = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'cbp-rfgrid-c'), ('</ul', '>'), False)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
        for item in data:
            url  = self.cm.ph.getSearchGroups(item, '''href=['"](http[^'^"]+?)['"]''')[0]
            if '' == url: continue
            icon = self.cm.ph.getSearchGroups(item, '''src=['"]*(https?://[^'^"^>]+?)[>'"]''')[0]
            title = self.cm.ph.getSearchGroups(item, '''title=['"]([^'^"]+?)['"]''')[0] 
            title += ' ' + self.cleanHtmlStr(item)
            tab.append({'title':title, 'url':self._getFullUrl(url), 'icon':self._urlWithCookie(icon)})
        
        cItem = dict(cItem)
        cItem['category'] = nextCategory
        self.listsTab(tab, cItem)
            
    def listItems(self, cItem, nextCategory='list_seasons'):
        printDBG("Filmoviplex.listItems")

        page = cItem.get('page', 1)
        
        sts, data = self.getPage(cItem['url']) 
        if not sts: 
            return
        #self.setMainUrl(self.cm.meta['url'])
        
        #printDBG("-----------------------------")
        #printDBG(data)
        #printDBG("-----------------------------")

        if 'cbp-rfgrid' in data:
            tmp = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'cbp-rfgrid'), ('</ul', '>'), False)[1]
            items = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li>', '</li>')
        else:
            tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'series-top'), ('<script', '>'), False)[1]
            items = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<a ', '</a>')
            
        for item in items:
            if 'SERIJA' in item:
                # it's a series
                cat = 'list_seasons'
            else:
                # it's a movie
                cat = 'explore_item'
            
            url = self.cm.ph.getSearchGroups(item, "href=[\"']([^\"^']+?)[\"']")[0]
            if url: 
                title = self.cleanHtmlStr( self.cm.ph.getDataBeetwenMarkers(item, ('<a ','>'), '</a>')[1] )
                icon  = self.cm.ph.getSearchGroups(item, '''<img[^>]+?data\-original=['"]([^"^']+?)['"]''')[0] 

                params = dict(cItem)
                params.update({'good_for_fav':True, 'category': cat,'title':title, 'url': url, 'icon': icon})
                self.addDir(params)

        #<a href="https://www.filmoviplex.com/browse-all-videos-1.html/page/2" >Next Page &raquo;</a></span>
        nextPageUrl = self.cm.ph.getSearchGroups(data, '''href=["']([^"^']+?)["']\s?>Next Page &raquo;</a>''')[0]
        if nextPageUrl:
            params = dict(cItem)
            params.update({'good_for_fav':False, 'title':_('Next page'), 'page': page + 1, 'url': nextPageUrl})
            self.addMore(params)
    
    def exploreItem(self, cItem):
        printDBG("Filmoviplex.exploreItem")

        url = cItem['url']

        sts, data = self.getPage(url) 
        if not sts: 
            return
        
        #self.setMainUrl(self.cm.meta['url'])
        
        #printDBG("--------------------")
        #printDBG(data)
        #printDBG("--------------------")

        #youtube trailer
        #<iframe src="https://www.youtube.com/embed/LiwFtzuSnkE" width="100%" height="270" allowfullscreen="true" mozallowfullscreen="true" webkitallowfullscreen="true" frameborder="no" scrolling="no"></iframe>
        #real link
        #<iframe class="play-mega" src="/netu.php?id=aHR0cHM6Ly92aWRlby5maWxtb3ZpcGxleC5jb20vZS9ZWE40VGxwRk1rRlJObUZCVUcwMWRtbFhORWxrZHowOQ==" scrolling="no" frameborder="0" width="74%" height="500px" allowfullscreen="true" webkitallowfullscreen="true" mozallowfullscreen="true"></iframe>
        
        iframes = self.cm.ph.getAllItemsBeetwenMarkers(data, '<iframe', '>')
        for iframe in iframes:
            url = self.cm.ph.getSearchGroups(iframe, "src=[\"']([^\"^']+?)[\"']")[0]
            if 'youtube' in url:
                params = dict(cItem)
                params.update({'good_for_fav':False, 'title': cItem.get('title','') + " - trailer", 'url': url, 'direct': True})
                printDBG(str(params))
                self.addVideo(params)
            else:
                url = strwithmeta(self.getFullUrl(url, self.MAIN_URL), {'Referer': cItem['url']})
                params = dict(cItem)
                params.update({'good_for_fav':False, 'title': cItem.get('title',''), 'url': url})
                printDBG(str(params))
                self.addVideo(params)
            
    def listSeasons(self, cItem, nextCategory):
        printDBG("Filmoviplex.listSeasons")
        self.cacheSeasons = []
        
        url = cItem['url']

        sts, data = self.getPage(url) 
        if not sts: 
            return
        
        dataScript = ""
        scripts = self.cm.ph.getAllItemsBeetwenMarkers(data, ('<script','>'), '</script>', False)
        
        for s in scripts:
            if 'window.onload' in s:
                dataScript = s
                break
        
        if not dataScript:
            return
            
        #printDBG("--------------------")
        #printDBG(dataScript)
        #printDBG("--------------------")
        
        #var Home = "https://www.filmoviplex.com/",
        #Excerpt = "When Emily Thorne moves to the Hamptons, everyone wonders about the new girl, but she knows everything about them, including what they did to her family. Years ago, they took everything from her. Now, one by one, she's going to make them pay.",
        #episodeSlug = "Epizoda",
        #seasonSlug = "Sezona",
        #PosterNull = "https://image.tmdb.org/t/p/w500/qx7XytRgg1F03NN5BoK8jx3Cyft.jpg",
        #baseUrl = "https://api.themoviedb.org/3/tv/",
        #apikey = "?api_key=ad8148d111b9980e2527c200eadf1d8b",
        #language = "&language=en-US",
        #ImgLang = "&include_image_language=en-US,null",
        #appendToResponse = "&append_to_response=images",
        #id = 39358,
        #dataUrl = baseUrl + id + apikey + language + ImgLang + appendToResponse;
        
        code = self.cm.ph.getSearchGroups(dataScript, "(var[^;]+?dataUrl[^;]+?;)")[0]
        code = code + '''
        var data = {
            home: Home,
            id: id,
            desc: Excerpt, 
            apiUrl: baseUrl,
            apiKey: apikey,
            dataUrl: dataUrl,
            seasonUrl: dataUrl.replace('?','/season/%s?'),
            epUrl: dataUrl.replace('?','/season/%s/episode/%s?')
        };
        console.log(JSON.stringify(data));
        '''
        printDBG("--------------------")
        printDBG(code)
        printDBG("--------------------")
        
        ret = js_execute(code)
        try:
            response = json_loads(ret['data'].replace('\n',''))
        
            desc = response.get('desc','')
            
            sts, apiData = self.getPage(response['dataUrl'])
            
            if sts:
                #printDBG("--------------------")
                #printDBG(apiData)
                #printDBG("--------------------")
                
                try:
                    apiJson = json_loads(apiData)
                    for s in apiJson['seasons']:
                        sNum = s.get("season_number", 0)
                        
                        sTitle = s.get("name",'')
                        if not sTitle:
                            sTitle =  "%s %d" % (_("Season") , sNum)
                        else:
                            if 'Season' in sTitle:
                                sTitle = sTitle.replace("Season", _("Season"))
                        
                        snumEp = s.get("episode_count", "")
                        if snumEp:
                            sTitle = "%s ( %s )" % (sTitle, snumEp)
                        
                        # episodes
                        episodesTab = []
                        sts, seasonData = self.getPage(response['seasonUrl'] % str(sNum))
                        
                        if sts:
                            #printDBG("--------------------")
                            #printDBG(seasonData)
                            #printDBG("--------------------")
                            
                            try:
                                seasonJson = json_loads(seasonData)
                                
                                for ep in seasonJson['episodes']:
                                    eNum = ep.get("episode_number", 0)
                                    
                                    eTitle = ep.get("name",'')
                                    if not eTitle:
                                        eTitle =  "%s %d - %s %d" % (_("Season") , sNum, _("Episode") , eNum)
                                    else:
                                        eTitle = "%d. %s" % (eNum, eTitle)
                                    
                                    #aggiungere ricerca dell'url
                                    url = self.getUrlFromCode(dataScript,sNum,eNum)
                                    if url == '':
                                        eTitle = eTitle + " [link not found!]"
                                    
                                    params = dict(cItem)
                                    params.update({'category': 'video', 'good_for_fav': True, 'title': eTitle, 'url': url, 'direct':True})
                                    printDBG(str(params))
                                    episodesTab.append(params)
                                
                            except:
                                pass
                        
                        params = dict(cItem)
                        params.update({'good_for_fav':False, 'category':nextCategory, 'title':sTitle, 'desc': desc, 'season_idx':len(self.cacheSeasons)})
                        printDBG(str(params))
                        self.addDir(params)
                        self.cacheSeasons.append(episodesTab)    

                except:
                    printExc()
        except:
            printExc()
            
        '''
        desc = self.cm.ph.getDataBeetwenMarkers(data, '<div id="epload">', '<script>', False)[1]
        icon = self._urlWithCookie( self.cm.ph.getSearchGroups(desc, "src=['"]*(http[^'^"^>]+?)[>'"]")[0] )
        desc = self.cleanHtmlStr(desc)
        
        m1 = '<li class="dropdown epilid caret-bootstrap caret-right" style="font-size:13px;">'
        if m1 not in data:
            m1 = "<li class='dropdown epilid caret-bootstrap caret-right' style='font-size:13px;'>"
        data = self.cm.ph.getDataBeetwenMarkers(data, m1, '<div id="epload">', False)[1]
        data = data.split(m1)
        for seasonItem in data:
            seasonTitle = self.cleanHtmlStr( self.cm.ph.getDataBeetwenMarkers(seasonItem, '<a ', '</a>')[1] )
            episodesData = self.cm.ph.getDataBeetwenMarkers(seasonItem, '<ul ', '</ul>', False)[1]
            episodesData = episodesData.split("<div class='epi'>")
            if len(episodesData): del episodesData[0]
            episodesTab = []
            for episodeItem in episodesData:
                url = self.cm.ph.getSearchGroups(episodeItem, "<a[^>]+?epiloader[^>]+?class=["']([^'^"]+?)['"]")[0]
                if url == '': continue
                url = self.EPISODE_URL + url
                title = self.cleanHtmlStr( episodeItem )
                dUrl  = self._getFullUrl( self.cm.ph.getSearchGroups(episodeItem, "data-url=['"]([^"^']+?)['"]")[0] )
                seasonNum = self.cm.ph.getSearchGroups(seasonTitle+'|', '[^0-9]([0-9]+?)[^0-9]')[0]
                episodesTab.append({'good_for_fav':False, 'title':cItem['title'] + ' - s%se%s' % (seasonNum, title), 'url':self._getFullUrl(url), 'data_url':dUrl})
            if 0 == len(episodesTab): continue
            params = dict(cItem)
            params.update({'good_for_fav':False, 'category':nextCategory, 'title':seasonTitle, 'desc':desc, 'icon':icon, 'season_idx':len(self.cacheSeasons)})
            self.addDir(params)
            self.cacheSeasons.append(episodesTab)
        '''
        
    def listEpisodes(self, cItem):
        printDBG("Filmoviplex.listEpisodes")
        seasonIdx = cItem.get('season_idx', -1)
        if seasonIdx < 0 or seasonIdx >= len(self.cacheSeasons): return
        tab = self.cacheSeasons[seasonIdx]
        self.listsTab(tab, cItem, 'video')
        
    def getLinksForVideo(self, cItem):
        printDBG("Filmoviplex.getLinksForVideo [%s]" % cItem)
        urlTab = []
        
        url = cItem['url']
        
        if cItem.get('direct', False):
            urlTab.append({'name':'link', 'url': url, 'need_resolve':1 })
        else:
            if len(self.cacheLinks.get(cItem['url'], [])):
                return self.cacheLinks[cItem['url']]

            params = self.defaultParams

            if isinstance(url, strwithmeta):
                try:
                    referer = url.meta['Referer']
                    params['header']['Referer'] = referer 
                except:
                    pass
                    
            sts, data = self.getPage(cItem['url'], params) 
            if not sts: 
                return []
                
            printDBG("----------------")
            printDBG(data)
            printDBG("----------------")
            
            if 'video nije pronadjen' in data:
                SetIPTVPlayerLastHostError(_('Video not found'))
                return []
            
            newUrl = self.cm.ph.getSearchGroups(data, "<iframe src=[\"']([^\"^']+?)[\"']")[0]
            
            printDBG("redirect to %s" % newUrl)
            urlTab.append({'name':'link', 'url': newUrl, 'need_resolve':1 })
            
        if len(urlTab):
            self.cacheLinks[cItem['url']] = urlTab
        
        printDBG(urlTab)
        return urlTab
        
    def getVideoLinks(self, videoUrl):
        printDBG("Filmoviplex.getVideoLinks [%s]" % videoUrl)
        urlTab = []
            
        if videoUrl != '':
            if 'video.filmoviplex.com' in videoUrl:
                videoUrl = videoUrl.replace('video.filmoviplex.com','netu.tv')

            urlTab.extend(self.up.getVideoLinkExt(videoUrl))
        return urlTab
        
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Filmoviplex.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        
        if 'page=' not in cItem.get('url', ''):
            cItem['url'] = self.MAIN_URL + "?all=all&s=%s&orderby=all" % urllib.quote_plus(searchPattern)
        self.listItems(cItem)

    def getArticleContent(self, cItem):
        printDBG("Filmoviplex.getArticleContent [%s]" % cItem)
        retTab = []
        
        if '' == cItem.get('data_url', ''): return []
        
        sts, data = self.getPage(cItem['data_url'])
        if not sts: return retTab
        
        printDBG(data)
        
        icon = cItem.get('icon', '')
        title = self.cm.ph.getDataBeetwenReMarkers(data, re.compile('''<[^>]*?['"]quad_tit["'][^>]*?>'''), re.compile('</'), False)[1]
        desc  = self.cm.ph.getDataBeetwenReMarkers(data, re.compile('''<[^>]*?['"]quad_description["'][^>]*?>'''), re.compile('</'), False)[1]
        
        otherInfo = {}
        tmpTab = [{'m1':'quad_imdb',      'm2':'</',      'key':'rating'},
                  {'m1':'quad_actors',    'm2':'</div>',  'key':'actors'},
                  {'m1':'quad_genres',    'm2':'</div>',  'key':'genre'},
                  {'m1':'fa fa-clock-o',  'm2':'</span>', 'key':'duration'},
                  {'m1':'fa fa-calendar', 'm2':'</span>', 'key':'year'},]
        
        for item in tmpTab:
            val = self.cm.ph.getDataBeetwenReMarkers(data, re.compile('''<[^>]+?\=['"]%s["'][^>]*?>''' % item['m1']), re.compile(item['m2']), False)[1]
            val = self.cleanHtmlStr(val.replace('Actors:', ''))
            if '' != val: otherInfo[item['key']] =  val
        
        return [{'title':self.cleanHtmlStr( title ), 'text': self.cleanHtmlStr( desc ), 'images':[{'title':'', 'url':self._urlWithCookie(icon)}], 'other_info':otherInfo}]
        
    def getLinksForFavourite(self, fav_data):
        if fav_data.startswith('{'): return CBaseHostClass.getLinksForFavourite(self, fav_data)
        return self.getLinksForVideo({'url':fav_data})
    
    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('handleService start')
        
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name     = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode     = self.currItem.get("mode", '')
        
        printDBG( "handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category) )
        self.currList = []
        self.cacheLinks = {}
        
        #MAIN MENU
        if name == None:
            self.listsTab(self.MAIN_CAT_TAB, {'name':'category'})
        elif category == 'categories':
            self.listCategories(self.currItem, 'list_items')
        elif category == 'year':
            self.listYears(self.currItem, 'list_items')
        elif category == 'list_movie_cats':
            self.listMovieCats(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem)
        elif category == 'explore_item':
            self.exploreItem(self.currItem)
        #SEASONS
        elif category == 'list_seasons':
            self.listSeasons(self.currItem, 'list_episodes')
        elif category == 'list_episodes':
            self.listEpisodes(self.currItem)
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
        CHostBase.__init__(self, Filmoviplex(), True, favouriteTypes=[CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO])
