# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
import Plugins.Extensions.IPTVPlayer.libs.urlparser as urlparser
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib
try:    import json
except Exception: import simplejson as json
###################################################


def gettytul():
    return 'https://filmovizija.fun/'

class FilmovizijaStudio(CBaseHostClass):
 
    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'  filmovizija.studio', 'cookie':'filmovizijastudio.cookie'})
        
        self.USER_AGENT = 'Mozilla/5.0 (X11; Linux i686) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/37.0.2062.120 Chrome/37.0.2062.120 Safari/537.36'
        self.HEADER = {'User-Agent': self.USER_AGENT,  'Accept-Encoding':'gzip, deflate', 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update( {'X-Requested-With': 'XMLHttpRequest'} )
        self.defaultParams = {'header':self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        
        self.MAIN_URL       = 'http://milversite.live/'
        self.MOV_SEARCH_URL = self.getFullUrl('search1.php?ser=506&subs=&lks=1&rfrom=0&rto=0&gfrom=0&gto=0&gns=&btn=&keywords=')
        self.SER_SEARCH_URL = self.getFullUrl('search1.php?ser=528&subs=&lks=1&rfrom=0&rto=0&gfrom=0&gto=0&gns=&btn=&keywords=')
        
        self.DEFAULT_ICON_URL = 'http://prvobitno.com/slike/filmovizijatv.jpg' #self.getFullUrl('/cdn/images/logo6.png')
        self.EPISODE_URL = self.getFullUrl('/episode.php?vid=')
        
        mc = 'browse-movies-videos-1-date.html'
        my = 'years.php'
        self.MAIN_CAT_TAB = [{'category':'list_movie_cats', 'title': _('Movies'),        'url':self.getFullUrl(mc), 'filter':'movies'      },
                             {'category':'categories',      'title': _('New Movies'),    'url':self.getMainUrl(),   'filter':'new_movies'  },
                             {'category':'categories',      'title': _('Top Movies'),    'url':self.getMainUrl(),   'filter':'top_movies'  },
                             {'category':'categories',      'title': _('Series'),        'url':self.getMainUrl(),   'filter':'series'      },
                             {'category':'categories',      'title': _('New Episodes'),  'url':self.getMainUrl(),   'filter':'new_episodes'},
                             {'category':'year',            'title': _('Year'),          'url':self.getFullUrl(my),                        },
                             {'category':'search',          'title': _('Search'), 'search_item':True,               },
                             {'category':'search_history',  'title': _('Search history'),                           }]
        
        self.cacheSeasons = []
        self.needProxy = None
        self.cacheLinks = {}
        self.cacheFilters = {'movies':[], 'top_movies':[], 'series':[], 'new_movies':[], 'new_episodes':[]}
        
    def isNeedProxy(self):
        if self.needProxy == None:
            sts, data = self.cm.getPage(self.MAIN_URL)
            self.needProxy = not sts
        return self.needProxy
    
    def getPage(self, url, params={}, post_data=None):
        HTTP_HEADER= dict(self.HEADER)
        params.update({'header':HTTP_HEADER})
        
        if self.isNeedProxy() and 'filmovizija.' in url:
            proxy = 'https://www.sslgate.co.uk/index.php?q={0}&hl=2e1'.format(urllib.quote(url, ''))
            params['header']['Referer'] = proxy
            params['header']['Cookie'] = 'flags=2e1;'
            url = proxy
        sts, data = self.cm.getPage(url, params, post_data)
        if sts and None == data:
            sts = False
        return sts, data
        
    def _getIconUrl(self, url):
        url = self._getFullUrl(url)
        if 'filmovizija.' in url and self.isNeedProxy():
            proxy = 'https://www.sslgate.co.uk/index.php?q={0}&hl=2e1'.format(urllib.quote(url, ''))
            params = {}
            params['User-Agent'] = self.HEADER['User-Agent'],
            params['Referer'] = proxy
            params['Cookie'] = 'flags=2e1;'
            url = strwithmeta(proxy, params) 
        return url
        
    def _getFullUrl(self, url):
        if 'sslgate.co.uk' in url:
            url = urllib.unquote( self.cm.ph.getSearchGroups(url+'&', '''\?q=(http[^&]+?)&''')[0] )
        if url.startswith('//'):
            url = 'http:' + url
        elif url.startswith('/'):
            url = self.MAIN_URL + url[1:]
        elif 0 < len(url) and not url.startswith('http'):
            url =  self.MAIN_URL + url
                
        url = self.cleanHtmlStr(url)
        url = self.replacewhitespace(url)

        return url
        
    def getPage2(self, baseUrl, params={}, post_data=None):
        params['cloudflare_params'] = {'domain':'www.filmovizija.tv', 'cookie_file':self.COOKIE_FILE, 'User-Agent':self.USER_AGENT, 'full_url_handle':self._getFullUrl}
        return self.cm.getPageCFProtection(baseUrl, params, post_data)
        
    def _urlWithCookie(self, url):
        if self.isNeedProxy():
            return self._getIconUrl(url)
        else:
            url = self._getFullUrl(url)
            if url == '': return ''
            cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE)
            return strwithmeta(url, {'Cookie':cookieHeader, 'User-Agent':self.USER_AGENT})
        
    def replacewhitespace(self, data):
        data = data.replace(' ', '%20')
        return CBaseHostClass.cleanHtmlStr(data)

    def listsTab(self, tab, cItem, type='dir'):
        printDBG("FilmovizijaStudio.listsTab")
        for item in tab:
            params = dict(cItem)
            params.update(item)
            params['name']  = 'category'
            if type == 'dir':
                self.addDir(params)
            else: self.addVideo(params)
            
    def fillCategories(self):
        printDBG("FilmovizijaStudio.fillCategories")
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
        printDBG("FilmovizijaStudio.listCategories")
        filter = cItem.get('filter', '')
        tab = self.cacheFilters.get(filter, [])
        if 0 == len(tab): self.fillCategories()
        tab = self.cacheFilters.get(filter, [])
            
        cItem = dict(cItem)
        cItem['category'] = nextCategory
        self.listsTab(tab, cItem)
        
    def listYears(self, cItem, nextCategory):
        printDBG("FilmovizijaStudio.listYears")
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
        printDBG("FilmovizijaStudio.listMovieCats")
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
        printDBG("FilmovizijaStudio.listItems")
        
        sts, data = self.getPage(cItem['url']) 
        if not sts: return
        self.setMainUrl(self.cm.meta['url'])
        
        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'pagination'), ('</ul', '>'), False)[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<a ', '</a>')
        nextPageUrl = ''
        for item in tmp:
            if ' &raquo;' not in item: continue
            nextPageUrl = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0]
        tmp = ''
        
        if 'cbp-rfgrid' in data:
            data = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'cbp-rfgrid'), ('</ul', '>'), False)[1]
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li>', '</li>')
        else:
            data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'series-top'), ('<script', '>'), False)[1]
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a ', '</a>')
            
        for item in data:
            url = self._getFullUrl( self.cm.ph.getSearchGroups(item, '''['"]([^"^']*?watch-[^"^']+?)['"]''')[0] )
            if url == '': url = self._getFullUrl( self.cm.ph.getSearchGroups(item, '''['"]([^"^']*?movie[^"^']+?)['"]''')[0] )
            title = self.cleanHtmlStr( self.cm.ph.getSearchGroups(item, '''title=['"]([^"^']+?)['"]''')[0] )
            if title == '': title = self.cleanHtmlStr( self.cm.ph.getDataBeetwenMarkers(item, '<a ', '</a>')[1] )
            icon  = self._urlWithCookie( self.cm.ph.getSearchGroups(item, '''<img[^>]+?data\-original=['"]([^"^']+?)['"]''')[0] )
            if icon == '': icon = self._urlWithCookie( self.cm.ph.getSearchGroups(item, '''<img[^>]+?src=['"]([^"^']+?\.jpe?g(:?\?[^'^"]*?)?)['"]''')[0] )
            if icon == '': icon = cItem.get('icon', '') 
            dUrl  = self._getFullUrl( self.cm.ph.getSearchGroups(item, '''data-url=['"]([^"^']+?)['"]''')[0] )
            desc  = self.cleanHtmlStr(item)
            
            if not self.cm.isValidUrl(url): 
                self.addDir({'title':'Error please report'})
                continue
            params = dict(cItem)
            params.update({'good_for_fav':True, 'title':title, 'url':self._getFullUrl(url), 'icon':self._urlWithCookie(icon), 'desc':desc, 'data_url':dUrl})
            if 'tvshow' in url:
                params['category'] = nextCategory
                self.addDir(params)
            else:
                self.addVideo(params)
        
        if nextPageUrl != '':
            params = dict(cItem)
            params.update({'good_for_fav':False, 'title':_('Next page'), 'page':cItem.get('page', 1)+1, 'url':self._getFullUrl(nextPageUrl)})
            self.addDir(params)
            
    def listSeasons(self, cItem, nextCategory):
        printDBG("FilmovizijaStudio.listSeasons")
        self.cacheSeasons = []
        
        url = cItem['url']
        if '--tvshow' in url and 'data_url' in cItem:
            sts, data = self.getPage(cItem['data_url'])
            if sts: url = self._getFullUrl( self.cm.ph.getSearchGroups(data, '''['"]([^"^']*?watch-[^"^']+?)['"]''')[0] )
            
        sts, data = self.getPage(url) 
        if not sts: return
        self.setMainUrl(self.cm.meta['url'])
        
        desc = self.cm.ph.getDataBeetwenMarkers(data, '<div id="epload">', '<script>', False)[1]
        icon = self._urlWithCookie( self.cm.ph.getSearchGroups(desc, '''src=['"]*(http[^'^"^>]+?)[>'"]''')[0] )
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
                url = self.cm.ph.getSearchGroups(episodeItem, '''<a[^>]+?epiloader[^>]+?class=["']([^'^"]+?)['"]''')[0]
                if url == '': continue
                url = self.EPISODE_URL + url
                title = self.cleanHtmlStr( episodeItem )
                dUrl  = self._getFullUrl( self.cm.ph.getSearchGroups(episodeItem, '''data-url=['"]([^"^']+?)['"]''')[0] )
                seasonNum = self.cm.ph.getSearchGroups(seasonTitle+'|', '[^0-9]([0-9]+?)[^0-9]')[0]
                episodesTab.append({'good_for_fav':False, 'title':cItem['title'] + ' - s%se%s' % (seasonNum, title), 'url':self._getFullUrl(url), 'data_url':dUrl})
            if 0 == len(episodesTab): continue
            params = dict(cItem)
            params.update({'good_for_fav':False, 'category':nextCategory, 'title':seasonTitle, 'desc':desc, 'icon':icon, 'season_idx':len(self.cacheSeasons)})
            self.addDir(params)
            self.cacheSeasons.append(episodesTab)
    
    def listEpisodes(self, cItem):
        printDBG("FilmovizijaStudio.listEpisodes")
        seasonIdx = cItem.get('season_idx', -1)
        if seasonIdx < 0 or seasonIdx >= len(self.cacheSeasons): return
        tab = self.cacheSeasons[seasonIdx]
        self.listsTab(tab, cItem, 'video')
        
    def getLinksForVideo(self, cItem):
        printDBG("FilmovizijaStudio.getLinksForVideo [%s]" % cItem)
        urlTab = []
        
        if len(self.cacheLinks.get(cItem['url'], [])):
            return self.cacheLinks[cItem['url']]
        
        sts, data = self.getPage(cItem['url']) 
        if not sts: return []
        self.setMainUrl(self.cm.meta['url'])
        
        tmp = self.cm.ph.getDataBeetwenReMarkers(data, re.compile('id\^\="page"'), re.compile('show\(\)'))[1].split('</script>')[0]
        printDBG("======")
        printDBG(tmp)
        printDBG("======")
        tmp = tmp.replace('\r', '\n').split('\n')
        tmp2 = []
        for item in tmp:
            if item.strip().startswith('//'): continue
            tmp2.append(item)
        tmp = '\n'.join(tmp2)
        printDBG(tmp)
        pageFormat = self.cm.ph.getSearchGroups(tmp, "src='(http[^']+?)'")[0]
        tmp2 = re.compile('"\+([^+]+?)\+"').findall(pageFormat)
        pageAttribs = []
        for item in tmp2:
            name = item.strip()
            attrib = self.cm.ph.getSearchGroups(tmp, '''var %s =[^;]+?attr\(['"]([^'^"]+?)['"]''' % name)[0]
            printDBG(">> name[%s] attrib[%s]" % (name, attrib))
            pageAttribs.append({'name':name, 'attrib':attrib})
        
        # main links
        mainData = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="tabs"', '</div>', False)[1]
        mainData = self.cm.ph.getAllItemsBeetwenMarkers(mainData, '<li>', '</li>')
        printDBG("EEEEEEEE\n %s " % mainData)
        for item in mainData:
            try:
                tmp = self.cm.ph.getDataBeetwenMarkers(item, '<a ', '>')[1]
                #tmp = re.compile('''\s(\w)=['"]([^'^"]+?)['"]''').findall(tmp)
                tmp = re.compile('''[^a-zA-Z0-9_]([a-zA-Z0-9_]+?)\s*=\s*['"]([^'^"]+?)['"]''').findall(tmp)
                
                attribs = {}
                for a in tmp:
                    attribs[a[0]] = a[1]
                
                urlId    = attribs['id']
                urlClass = attribs['class']
                urlHref  = attribs['href']
                
                urlName  = self.cleanHtmlStr( item )
                printDBG('>> ' + item)
                if urlClass == 'direct':
                    if not urlId.startswith('http'):
                        urlTab.append({'name':urlName, 'url':'id=' + urlId, 'need_resolve':1})
                    else:
                        urlTab.append({'name':urlName, 'url':self._getFullUrl(urlId), 'need_resolve':1})
                elif urlId.startswith('page') and pageFormat != '':
                    url = pageFormat
                    for a in pageAttribs:
                        url = url.replace('"+%s+"' % a['name'], attribs[a['attrib']])
                    urlTab.append({'name':urlName, 'url':self._getFullUrl(url), 'need_resolve':1})
                elif urlId.startswith('tab'):
                    url = self.cm.ph.getDataBeetwenMarkers(data, '$("#%s").click' % urlId, '}', False)[1]
                    url = self.cm.ph.getSearchGroups(url, '''['"](http[^'^"]+?)['"]''')[0]
                    if not url.startswith('http'): continue
                    urlTab.append({'name':urlName, 'url':self._getFullUrl(url), 'need_resolve':1})
            except Exception:
                printExc()
                
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<tr id="linktr">', '</tr>')
        for item in data:
            urlName = self.cleanHtmlStr( self.cm.ph.getDataBeetwenMarkers(item, '<h9', '</h9>', True)[1] )
            redirect = self.cm.ph.getSearchGroups(item, 'class="redirect"\s*id="([^"]+?)"')[0]
            if '' == redirect: 
                redirect = self.cm.ph.getSearchGroups(item, '''href=['"](http[^'^"]+?)['"]''')[0]
                if 1 == self.up.checkHostSupport(redirect):
                    urlTab.append({'name':urlName, 'url':redirect, 'need_resolve':1})
            else:
                urlTab.append({'name':urlName, 'url':'redirect=' + redirect, 'need_resolve':1})
                
        uniqTab = []
        tmpTab = []
        for item in urlTab:
            if item['url'] not in uniqTab:
                uniqTab.append(item['url'])
                tmpTab.append(item)
        urlTab = tmpTab
            
        if len(urlTab):
            self.cacheLinks[cItem['url']] = urlTab
        printDBG(urlTab)
        return urlTab
        
    def getVideoLinks(self, videoUrl):
        printDBG("FilmovizijaStudio.getVideoLinks [%s]" % videoUrl)
        urlTab = []
        
        for key in self.cacheLinks:
            for idx in range(len(self.cacheLinks[key])):
                if self.cacheLinks[key][idx]['url'] == videoUrl:
                    self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name']
        if videoUrl.startswith("id=") or videoUrl.startswith("redirect="): 
            sts, data = self.getPage(self.getFullUrl('/morgan.php'), {'raw_post_data':True}, videoUrl)
            if not sts: return []
            printDBG(data)
            videoUrl = data
        
        tries = 0
        while tries < 3 and 'filmovizija.' in videoUrl:
            tries += 1
            sts, data = self.getPage(videoUrl)
            if not sts: return []
            printDBG(data)
            
            sub_tracks = []
            subData = self.cm.ph.getDataBeetwenMarkers(data, 'tracks:', ']', False)[1].split('}')
            for item in subData:
                if 'captions' in item:
                    label   = self.cm.ph.getSearchGroups(item, '''label:[ ]*?["']([^"^']+?)["']''')[0]
                    src     = self.cm.ph.getSearchGroups(item, '''file:[ ]*?["']([^"^']+?)["']''')[0]
                    if not src.startswith('http'): continue
                    sub_tracks.append({'title':label, 'url':self._getFullUrl(src), 'lang':label, 'format':'srt'})
            
            linksTab = self.up.pp._findLinks(data, serverName='')
            for idx in range(len(linksTab)):
                url = self._getFullUrl(linksTab[idx]['url']) 
                name = url
                url  = urlparser.decorateUrl(url, {'external_sub_tracks':sub_tracks})
                urlTab.append({'name':name, 'url':url, 'need_resolve':0})
            
            if 0 == len(urlTab):
                videoUrl = self._getFullUrl(self.cm.ph.getSearchGroups(data, '<iframe[^>]+?src="([^"]+?)"', 1, True)[0])
                if videoUrl == '': videoUrl = self._getFullUrl(self.cm.ph.getSearchGroups(data, '\.load\(\s*?"([^"]+?)"', 1, True)[0])
            
        if videoUrl != '':
            urlTab.extend(self.up.getVideoLinkExt(videoUrl))
        return urlTab
        
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("FilmovizijaStudio.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        
        if 'movie' == searchType:
            baseUrl = self.MOV_SEARCH_URL
        else:
            baseUrl = self.SER_SEARCH_URL

        if 'page=' not in cItem.get('url', ''):
            cItem['url'] = baseUrl + urllib.quote(searchPattern)
        self.listItems(cItem)

    def getArticleContent(self, cItem):
        printDBG("FilmovizijaStudio.getArticleContent [%s]" % cItem)
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
        CHostBase.__init__(self, FilmovizijaStudio(), True, favouriteTypes=[CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO])