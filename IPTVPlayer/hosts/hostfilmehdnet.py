# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib
###################################################

def gettytul():
    return 'http://filmehd.se/'

class FilmeHD(CBaseHostClass):
 
    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'filmehd.se', 'cookie':'filmehd.se.cookie'})
        
        self.DEFAULT_ICON_URL = 'https://filmehd.se/wp-content/themes/filmehd/assets/apple-touch-icon.png'
        self.HEADER = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0', 'DNT':'1', 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update( {'X-Requested-With': 'XMLHttpRequest'} )
        self.MAIN_URL = 'http://filmehd.se/'
        self.cacheLinks    = {}
        self.cacheFilters  = {}
        self.cacheFiltersKeys = []
        self.defaultParams = {'with_metadata':True, 'header':self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self._myFun = None
    
    def getPage(self, url, addParams = {}, post_data = None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        
        return self.cm.getPage(url, addParams, post_data)
        
    def listMainMenu(self, cItem):
        MAIN_CAT_TAB = [{'category':'list_sort',       'title': 'TOATE FILMELE',  'url': self.getFullUrl('/page/1')        },
                        {'category':'list_categories', 'title': 'GEN FILM',       'url': self.getFullUrl('/filme-online')  },
                        {'category':'list_old',        'title': 'CINEMATECĂ',     'url': self.getFullUrl('/filme-vechi')   },
                        {'category':'list_years',      'title': 'FILME DUPA AN',  'url': self.getFullUrl('/filme-online')  },
                        {'category':'list_sort',       'title': 'SERIALE',        'url':self.getFullUrl('/seriale')        },
                        {'category':'search',          'title': _('Search'),      'search_item':True, },
                        {'category':'search_history',  'title': _('Search history'),             }]
        self.listsTab(MAIN_CAT_TAB, cItem)
    
    def listSort(self, cItem, nextCategory1, nextCategory2):
        printDBG("FilmeHD.listSort")
        
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        
        tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'category-list'), ('</ul', '>'), False)
        for section in tmp:
            if 'sortby=' not in section: continue
            section = self.cm.ph.getAllItemsBeetwenMarkers(section, '<li', '</li>')
            for item in section:
                url = self.getFullUrl( self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0] )
                title = self.cleanHtmlStr(item)
                params = dict(cItem)
                params.update({'good_for_fav':False, 'category':nextCategory1, 'title':title, 'url':url})
                self.addDir(params)
            break
        
        if 0 == len(self.currList):
            cItem = dict(cItem)
            cItem['category'] = nextCategory1
            self.listItems(cItem, nextCategory2, data)
        else:
            params = dict(cItem)
            params.update({'good_for_fav':False, 'category':nextCategory1, 'title':_('Default')})
            self.currList.insert(0, params)
        
    def listCategories(self, cItem, nextCategory, m1):
        printDBG("FilmeHD.listCategories")
        
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        
        data = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', m1), ('</ul', '>'), False)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
        for item in data:
            url = self.getFullUrl( self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0] )
            title = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'good_for_fav':False, 'category':nextCategory, 'title':title, 'url':url})
            self.addDir(params)

    def listItems(self, cItem, nextCategory, data=None):
        printDBG("FilmeHD.listItems")
        page = cItem.get('page', 1)
        
        if data == None:
            sts, data = self.getPage(cItem['url'])
            if not sts: return
        
        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'pagenavi'), ('</div', '>'), False)[1]
        nextPage = self.getFullUrl( self.cm.ph.getSearchGroups(nextPage, '''<a[^>]+?href=['"]([^"^']+?)['"][^>]*?>%s<''' % (page + 1))[0] )
        
        data = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'box-film'), ('</ul', '>'))[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
        for item in data:
            url = self.getFullUrl( self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0] )
            title = self.cleanHtmlStr( self.cm.ph.getDataBeetwenNodes(item, ('<h', '>', 'title'), ('</h', '>'))[1])
            if not self.cm.isValidUrl(url): continue
            icon = self.getFullIconUrl( self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''')[0] )

            desc = []
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(item, '<span', '</span>')
            for t in tmp:
                t = self.cleanHtmlStr(t)
                if t != '': desc.append(t)
            desc = '[/br]'.join(desc) 
            
            params = dict(cItem)
            params = {'good_for_fav': True, 'category':nextCategory, 'title':title, 'url':url, 'icon':icon, 'desc':desc}
            self.addDir(params)
        
        if nextPage and len(self.currList) > 0:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title':_("Next page"), 'url':nextPage, 'page':page+1})
            self.addMore(params)
    
    def exploreItem(self, cItem):
        printDBG("FilmeHD.exploreItem")
        
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        
        # trailer
        trailer = self.cm.ph.getSearchGroups(data, '''<a[^>]+?href=['"]([^"^']+?)['"][^>]*?>([^>]*?trailer[^>]*?)<''', 2, ignoreCase=True)
        if trailer[0] != '':
            url = self.getFullUrl(trailer[0])
            url = strwithmeta(url, {'Referer':cItem['url']})
            title = self.cleanHtmlStr(trailer[1])
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title':'%s : %s' % (cItem['title'], title), 'url':url})
            self.addVideo(params)
            
        
        titlesTab = []
        serverNameDict = {}

        parts = re.findall("(<div[^>]+?tabpanel[^>]+?>)", data)
        links = re.findall("<div.*?data-thumbnail=\"(.*?)\" data-src=\"(.*?)\".*?\"lazyframe-([^a-zA-Z-]+)-modal\".*?>", data)
        
        if len(parts) <= 1:
            # movie mode
            linksKey = cItem['url'] 
            self.cacheLinks[linksKey] = []

            for l in links:
                url = self.getFullUrl(l[1])
                name = _("Player") + " %s" % l[2]    
                url = strwithmeta(url, {'Referer': cItem['url']})
                params = {'name':name, 'url':url, 'need_resolve':1}
                printDBG(str(params))
                self.cacheLinks[linksKey].append(params)

            if len(self.cacheLinks[linksKey]):
                params = dict(cItem)
                params.update({'good_for_fav': False, 'links_key':linksKey})
                self.addVideo(params)

        else:
            # episodes mode
            num_parts = len(parts)
            num_links = len(links)
            num_episodes = int(num_links / num_parts)
            printDBG("parts : %s, links : %s episodes: %s" % (num_parts, num_links, num_episodes))
            for ep in range(0, num_episodes):
                linksKey = cItem['url'] + ("|ep_%s" % ep)
                self.cacheLinks[linksKey] = []
                title = cItem['title'] + " - " + _("Episode") + (" %s " % (ep+1))
                for j in range(0, num_parts):
                    l = links[ ep +j*num_episodes ]
                    name = _("Episode")+ (" %s - " % (ep + 1)) + _("Player") + (" %s " % (j + 1))     
                    url = self.getFullUrl(l[1])
                    url = strwithmeta(url, {'Referer': cItem['url']})
                    params = {'name':name, 'url':url, 'need_resolve':1}
                    printDBG(str(params))
                    self.cacheLinks[linksKey].append(params)

                if len(self.cacheLinks[linksKey]):
                    params = dict(cItem)
                    params.update({'good_for_fav': False, 'title' : title, 'links_key':linksKey})
                    self.addVideo(params)
    
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("FilmeHD.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('/?s=') + urllib.quote_plus(searchPattern)
        cItem['category'] = 'list_items'
        self.listItems(cItem, 'explore_item')
    
    def getLinksForVideo(self, cItem):
        printDBG("FilmeHD.getLinksForVideo [%s]" % cItem)
        url = cItem.get('url', '')
        if 1 == self.up.checkHostSupport(url):
            return self.up.getVideoLinkExt(url)
        
        key = cItem.get('links_key', '')
        return self.cacheLinks.get(key, [])
    
    def getVideoLinks(self, videoUrl):
        printDBG("FilmeHD.getVideoLinks [%s]" % videoUrl)
        videoUrl = strwithmeta(videoUrl)
        urlTab = []
        
        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if videoUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name']
                        break
        
        params = dict(self.defaultParams)
        params['header'] = dict(params['header'])
        params['header']['Referer'] = str(videoUrl.meta.get('Referer', self.getMainUrl()))
        
        sts, data = self.getPage(videoUrl, params)
        if not sts: return urlTab
        
        url = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0])
        if url == '':
            jscode = ['window=this,window.outerWidth=640,window.innerWidth=640;var document=this;document.write=function(text){var startRe=new RegExp("(<script[^>]*?>)","i").exec(text),endRe=new RegExp("(</script[^>]*?>)","i").exec(text);null!=startRe&&null!=endRe?(text=text.replace(startRe[1],""),text=text.replace(endRe[1],""),text=text.replace(/var\s+/g,"this."),print(text),eval(text)):print(text)};']
            data = re.compile('''<script[^>]+?src=['"]([^'^"]+?)['"]''', re.I).findall(data)
            for item in data:
                item = self.getFullUrl(item)
                sts, item = self.getPage(item, params)
                if sts: jscode.append(item)
            
            ret = js_execute( '\n'.join(jscode) )
            if ret['sts'] and 0 == ret['code']:
                printDBG(ret['data'])
                url = self.getFullUrl(self.cm.ph.getSearchGroups(ret['data'], '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0].replace('&amp;', '&'))
        
        if url != '':
            urlTab = self.up.getVideoLinkExt(url)
        return urlTab
        
    def getArticleContent(self, cItem, data=None):
        printDBG("SolarMovie.getArticleContent [%s]" % cItem)
        retTab = []
        
        if data == None:
            url = strwithmeta(cItem['url']).meta.get('Referer', cItem['url'])
            sts, data = self.getPage(url)
            if not sts: return []
            
        descData = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'tv-content-custom'), ('<div', '>', 'content-bottom'), True)[1]
        icon = self.cm.ph.getDataBeetwenMarkers(descData, 'url(', ')', False)[1].strip()
        if not self.cm.isValidUrl(icon): icon = ''
        
        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(descData, '<p', '</p>')[1])
        if desc == '':
            desc = self.cm.ph.getSearchGroups(data, '''(<meta[^>]+?description['"][^>]*?>)''')[0]
            desc = self.cleanHtmlStr( self.cm.ph.getSearchGroups(desc, '''content=['"]([^'^"]+?)['"]''')[0] )
        
        title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(descData, '<h1', '</h1>')[1])
        if title == '': 
            title = self.cm.ph.getSearchGroups(data, '''(<meta[^>]+?title['"][^>]*?>)''')[0]
            title = self.cleanHtmlStr( self.cm.ph.getSearchGroups(title, '''content=['"]([^'^"]+?)['"]''')[0] )
        
        if title == '': title = cItem['title']
        if desc == '':  desc = cItem['desc']
        if icon == '':  icon = cItem['icon']
        
        otherInfo = {}
        
        # raiting
        tmp = self.cm.ph.getAllItemsBeetwenNodes(descData, ('<div', '>', 'rating-circle'), ('</div', '>'), True)
        for item in tmp:
            t = self.cleanHtmlStr(item)
            if t == '': continue
            if 'imbd' in item: otherInfo['imdb_rating'] = t
            else: otherInfo['rating'] = t
        
        # stars
        t = []
        tmp = self.cm.ph.getDataBeetwenNodes(descData, ('<div', '>', '"cast"'), ('</div', '>'), False)[1].split(':', 1)[-1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<a', '</a>')
        for item in tmp:
            item = self.cleanHtmlStr(item)
            if item == '': continue
            t.append(item)
        if len(t): otherInfo['stars'] = ', '.join(t)
        
        # genres
        tmp = self.cm.ph.getDataBeetwenNodes(descData, ('<span', '>', 'genre'), ('</span', '>'), False)[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<a', '</a>')
        tmp = ', '.join([self.cleanHtmlStr(item) for item in tmp])
        if tmp != '': otherInfo['genres'] = tmp
        
        # director
        tmp = self.cm.ph.getDataBeetwenNodes(descData, ('<div', '>', 'director'), ('</div', '>'), False)[1].split(':', 1)[-1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<a', '</a>')
        tmp = ', '.join([self.cleanHtmlStr(item) for item in tmp])
        if tmp != '': otherInfo['director'] = tmp
        
        # year
        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(descData, ('<div', '>', 'year'), ('</div', '>'), False)[1].split(':', 1)[-1])
        if tmp != '': otherInfo['year'] = tmp
        
        return [{'title':self.cleanHtmlStr( title ), 'text': self.cleanHtmlStr( desc ), 'images':[{'title':'', 'url':self.getFullUrl(icon)}], 'other_info':otherInfo}]
        
    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('handleService start')
        
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name     = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode     = self.currItem.get("mode", '')
        
        printDBG( "handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category) )
        self.currList = []
        
    #MAIN MENU
        if name == None:
            self.listMainMenu({'name':'category'})
        elif category == 'list_categories':
            self.listCategories(self.currItem, 'list_sort', '-categorys')
        elif category == 'list_years':
            self.listCategories(self.currItem, 'list_sort', 'labelledby')
        elif category == 'list_sort':
            self.listSort(self.currItem, 'list_items', 'explore_item')
        elif category == 'list_items' or category == 'list_old':
            self.listItems(self.currItem, 'explore_item')
        elif category == 'explore_item':
            self.exploreItem(self.currItem)
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
        CHostBase.__init__(self, FilmeHD(), True, [])
    
    def withArticleContent(self, cItem):
        if cItem.get('type', 'video') != 'video' and cItem.get('category', 'unk') != 'explore_item':
            return False
        return True
    