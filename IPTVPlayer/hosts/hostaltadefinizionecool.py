# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify, MergeDicts
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute
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
    return 'https://altadefinizione.us/'

class AltadefinizioneCool(CBaseHostClass):
 
    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'altadefinizionecool', 'cookie':'altadefinizionecool.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.103 Safari/537.36'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'DNT':'1', 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update( {'X-Requested-With': 'XMLHttpRequest'} )
        self.MAIN_URL = 'https://altadefinizione.us/'
        self.AZ_URL = self.MAIN_URL + 'catalog/%l/page/{0}'
        self.DEFAULT_ICON_URL = 'https://altadefinizione.us/templates/Dark/img/logo.png'
        
        self.cacheCategories = []
        
        self.cacheJSCode   = ''
        self.cacheLinks    = {}
        self.cacheFilters  = {}
        self.cacheFiltersKeys = []
        self.defaultParams = {'with_metadata':True, 'header':self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self._myFun = None
    
    def setMainUrl(self, url):
        if self.cm.isValidUrl(url):
            self.MAIN_URL = self.cm.getBaseUrl(url)
    
    def getPage(self, baseUrl, addParams = {}, post_data = None):
        if addParams == {}:
            addParams = dict(self.defaultParams)

        addParams['cloudflare_params'] = {'cookie_file':self.COOKIE_FILE, 'User-Agent':self.USER_AGENT}
        sts, data = self.cm.getPageCFProtection(baseUrl, addParams, post_data)
        return sts, data
        
    def listMainMenu(self, cItem):
        self.cacheCategories = []

        MAIN_CAT_TAB = [{'category':'search',          'title': _('Search'), 'search_item':True, },
                        {'category':'search_history',  'title': _('Search history')},
                        {'category':'list_categories', 'title': 'Categorie'},
                        {'category':'az_main', 'title': _('A-Z List')}]
        self.listsTab(MAIN_CAT_TAB, cItem)
        
        sts, data = self.getPage(self.getMainUrl())
        if sts:
            self.setMainUrl(data.meta['url'])
            tabTitles = {}
            # navigations tabs
            tmp = self.cm.ph.getDataBeetwenNodes(data, '<ul class="nav nav-tabs">', ('</ul', '>'))[1]
            tmp = self.cm.ph.getAllItemsBeetwenNodes(tmp, ('<a', '>', 'tab'), ('</a', '>'))
            for item in tmp:
                tabId = self.cm.ph.getSearchGroups(item, '''href=['"]#([^'^"]+?)['"]''')[0]
                title = self.cleanHtmlStr(item)
                if title == 'Qualitá' :
                    title = 'Qualita'
                tabTitles[tabId] = title

                #printDBG("------>" + tabId + "---->" + title)
                tmp = self.cm.ph.getAllItemsBeetwenNodes(data, '<ul class="listSubCat" id="%tabId%"'.replace('%tabId%', title), '</ul>')
                #print(str(tmp))
                for tabData in tmp:
                    #printDBG(tabData)
                    tabTitle = tabTitles.get(tabId, '')
                    if tabTitle == '': continue
                    subItems = []
                    tabData = self.cm.ph.getAllItemsBeetwenMarkers(tabData, '<a', '</a>')
                    #printDBG(str(tabData))
                    for item in tabData:
                        title = self.cleanHtmlStr(item)
                        url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
                        params = dict(cItem)
                        params.update({'category':'list_items', 'title':title, 'url':url})
                        printDBG(str(params))
                        subItems.append(params)
                    
                    if len(subItems):
                        params = dict(cItem)
                        params.update({'category':'sub_items', 'title':tabTitle, 'sub_items':subItems})
                        printDBG(str(params))
                        self.cacheCategories.append(params)
            
            tmp = self.cm.ph.getDataBeetwenNodes(data, ('<ul id="menu-menu-1" class="menu">'), ('</ul', '>'))[1]
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<a', '</a>')
            for item in tmp:
                title = self.cleanHtmlStr(item)
                if title.lower() in ['richieste', 'aggiornamenti 2019', 'guida', 'cineblog01', 'lista film a-z'] : 
                    break
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
                params = dict(cItem)
                params.update({'good_for_fav':True, 'category':'list_items', 'title':title, 'url':url})
                printDBG(str(params))
                self.addDir(params)
    
    def listSubItems(self, cItem):
        printDBG("Altadefinizione.listSubItems")
        self.currList = cItem['sub_items']
    
    def listItems(self, cItem, nextCategory, data=None):
        printDBG("Altadefinizione.listItems")
        page = cItem.get('page', 1)
        
        if data == None:
            sts, data = self.getPage(cItem['url'])
            if not sts: return
        
        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<div','>', 'paginationC'), ('</div', '>'), False)[1]
        nextPage = self.getFullUrl( self.cm.ph.getSearchGroups(nextPage, '''<a[^>]+?href=['"]([^"^']+?)['"][^>]*?>%s<''' % (page + 1))[0] )
        
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="box">', '</div>')
        for item in data:
            url = self.getFullUrl( self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0] )
            if url == '': continue
            title = self.cleanHtmlStr( self.cm.ph.getDataBeetwenNodes(item, ('<h', '>', 'title'), ('</h', '>'))[1])
            icon = self.getFullIconUrl( self.cm.ph.getSearchGroups(item, '''<img[^>]+?src=['"]([^"^']+?)['"]''')[0] )

            desc = []
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(item, '<span', '</span>')
            tmp.append(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'rate'), ('</div', '>'), False)[1])
            for t in tmp:
                t = self.cleanHtmlStr(t)
                if t != '': desc.append(t)
            desc = ' | '.join(desc) 
            
            params = dict(cItem)
            params = {'good_for_fav': True, 'category':nextCategory, 'title':title, 'url':url, 'icon':icon, 'desc':desc}
            self.addDir(params)
        
        if nextPage and len(self.currList) > 0:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title':_("Next page"), 'url':nextPage, 'page':page+1})
            self.addMore(params)
    
    def exploreItem(self, cItem):
        printDBG("Altadefinizione.exploreItem")
        self.cacheLinks = {}
        
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        cUrl = data.meta['url']
        
        descObj = self.getArticleContent(cItem, data)[0]
        desc = []
        for t in ['quality', 'imdb_rating', 'year', 'genres']:
            if t in descObj['other_info']:
                desc.append(descObj['other_info'][t])
        desc = ' | '.join(desc) + '[/br]' + descObj['text'] 
        
        # trailer
        trailerUrl = self.cm.ph.getDataBeetwenNodes(data, '<div class="collapse" id="showtrailer">', '</div>', False)[1]
        trailerUrl = self.getFullUrl(self.cm.ph.getSearchGroups(trailerUrl, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, ignoreCase=True)[0])
        printDBG(trailerUrl)
        if trailerUrl != '':
            trailerUrl = strwithmeta(trailerUrl, {'Referer':cItem['url']})
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title':'%s - %s' % (cItem['title'], _('trailer')), 'url':trailerUrl, 'desc':desc, 'prev_url':cItem['url']})
            self.addVideo(params)
 
        url_container = self.cm.ph.getDataBeetwenNodes(data, '<ul id="mirrors"', '</ul>', False)[1]
        urls = self.cm.ph.getAllItemsBeetwenMarkers(url_container, '<li>', '</li>')
        for item in urls:
            printDBG("----->" + item)
            title = self.cleanHtmlStr(item)
            url = self.getFullUrl( self.cm.ph.getSearchGroups(item, '''data-target=['"]([^"^']+?)['"]''')[0] )
            if url !='' : 
                url = strwithmeta(url, {'Referer':cItem['url']})
                params = dict(cItem)
                params.update({'good_for_fav': False, 'title':'%s - %s' % (cItem['title'], title), 'url':url, 'desc':desc, 'prev_url':cItem['url']})
                self.addVideo(params)
    
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Altadefinizione.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('/index.php?do=search&subaction=search&story=') + urllib.quote_plus(searchPattern)
        cItem['category'] = 'search_items'
        self.listItems(cItem, 'explore_item')
    
    def listAZMain(self, cItem):
        printDBG("Altadefinizione.listAZMain")
        # 0-9
        self.addDir(MergeDicts(cItem, {'category':'az_item', 'title': "0-9", 'letter' : '9' } ))              
        #a-z
        for i in range(26):
            self.addDir(MergeDicts(cItem, {'category':'az_item', 'title': chr(ord('A')+i), 'letter': chr(ord('A')+i)} ))       
    
    def listAZItem(self, cItem):
        letter = cItem['letter'].upper()
        page = cItem.get ('page', 1)  
        list_url = self.AZ_URL.replace('%l',letter).format(page) 
        printDBG("Altadefinizione.listAZItem for letter %s" % letter )
        sts, data = self.getPage(list_url)
        if not sts: return

        data = self.cm.ph.getDataBeetwenNodes(data, '<table>', '</table>', False)[1]
        #printDBG(data)

        items= self.cm.ph.getAllItemsBeetwenMarkers(data, '<tr class="mlnew">', '</tr>')
        for item in items:
            title_and_url = self.cm.ph.getDataBeetwenNodes(item, '<td class="mlnh-2"><h2>', '</h2>', False)[1]
            url = self.cm.ph.getSearchGroups(title_and_url, '''href=['"]([^'^"]+?)['"]''')[0]
            title = self.cleanHtmlStr(title_and_url)
    
            year = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, '<td class="mlnh-3">', '</td>', False)[1])
            quality = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, '<td class="mlnh-4">', '</td>', False)[1])
            cat = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, '<td class="mlnh-5">', '</td>', False)[1])
            icon_text = self.cm.ph.getDataBeetwenNodes(item, '<td class="mlnh-thumb">', '</td>', False)[1]
            icon = self.cm.getFullUrl(self.cm.ph.getSearchGroups(icon_text, '''src=['"]([^'^"]+?)['"]''')[0], self.MAIN_URL)
            desc = quality + " - " + _('Year') + ": " + year + " - " + cat
            
            self.addDir(MergeDicts(cItem, {'category': 'explore_item', 'good_for_fav': True, 'title' : title, 'icon' : icon, 'url' : url, 'desc' : desc  }))
 
        # check if more pages
        pag = self.cm.ph.getDataBeetwenNodes(data, '<div class="paginationC">', '</div>', False)[1]
        label = ">{0}</a>".format(page+1)
        if label in pag:
            self.addMore(MergeDicts(cItem, {'category': 'az_item', 'title' : _('Next page'), 'page': page + 1 }))
        
    def getLinksForVideo(self, cItem):
        printDBG("Altadefinizione.getLinksForVideo [%s]" % cItem)
        urlTab = []
        
        url = cItem.get('url', '')
        if 1 == self.up.checkHostSupport(url):
            return self.up.getVideoLinkExt(url)
        
        key = url
        if key in self.cacheLinks:
            return self.cacheLinks[key]
        
        urlParams = dict(self.defaultParams)
        urlParams['header'] = dict(urlParams)
        urlParams['header']['Referer'] = cItem.get('prev_url', '')
        sts, data = self.getPage(cItem['url'], urlParams)
        if not sts: return urlTab
        
        cUrl = data.meta['url']
        
        data = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'mirrors'), ('</ul', '>'), False)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<form', '</form>')
        for item in data:
            actionUrl = self.cm.getFullUrl(self.cm.ph.getSearchGroups(item, '''action=['"]([^'^"]+?)['"]''')[0].replace('&amp;', '&'), self.cm.getBaseUrl(cUrl))
            if actionUrl == '': actionUrl = cUrl
            item = self.cm.ph.getAllItemsBeetwenMarkers(item, '<input', '>')
            title = ''
            query = {}
            for it in item:
                name  = self.cm.ph.getSearchGroups(it, '''name=['"]([^'^"]+?)['"]''')[0]
                value = self.cm.ph.getSearchGroups(it, '''value=['"]([^'^"]+?)['"]''')[0]
                query[name] = value
                if title == '' and name.startswith('mir'): title = value
            
            if '?' in actionUrl: actionUrl += '&'
            else: actionUrl += '?'
            actionUrl += urllib.urlencode(query)
            urlTab.append({'name':title, 'url':strwithmeta(actionUrl, {'Referer':cUrl}), 'need_resolve':1})
        
        if len(urlTab):
            self.cacheLinks[key] = urlTab
        return urlTab
    
    def getVideoLinks(self, videoUrl):
        printDBG("Altadefinizione.getVideoLinks [%s]" % videoUrl)
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
        
        urlParams = dict(self.defaultParams)
        urlParams['header'] = dict(urlParams['header'])
        urlParams['header']['Referer'] = str(videoUrl.meta.get('Referer', self.getMainUrl()))
        
        sts, data = self.getPage(videoUrl, urlParams)
        if not sts: return urlTab
        cUrl = data.meta['url']
        
        playerData = self.cm.ph.getDataBeetwenNodes(data, ('<input', '>', 'urlEmbed'), ('<iframe', '>'))[1]
        if playerData == '':
            printDBG('Missig player data')
            return urlTab
        playerData = self.cm.ph.getSearchGroups(playerData, '''value=['"]([^'^"]+?)['"]''')[0]
        printDBG('PLAYER_DATA: %s\n' % playerData)
        
        
        if self.cacheJSCode == '':
            jsUrl = ''
            data = re.compile('''<script[^>]+?src=['"]([^'^"]+?)['"]''', re.I).findall(data)
            for item in data:
                if 'filmlive' not in item: continue
                jsUrl = self.cm.getFullUrl(item, self.cm.getBaseUrl(cUrl))
                break
            
            sts, data = self.getPage(jsUrl, urlParams)
            if not sts: return urlTab
            try:
                idxS = data.find('function clearify')
                num = 1
                idx = data.find('{', idxS)
                for idx in range(idx+1, len(data), 1):
                    if data[idx] == '{': num += 1
                    if data[idx] == '}': num -= 1
                    if num == 0:
                        printDBG("JS_CODE_IDX: [%s:%s]" % (idxS, idx))
                        break
                  
                jscode = data[idxS:idx+1]
                printDBG('JS_CODE: %s\n' % jscode)
                self.cacheJSCode = jscode
            except Exception:
                printExc()
            
        jscode = ['var $={base64:function(not_used,e){e.length%4==3&&(e+="="),e.length%4==2&&(e+="=="),e=Duktape.dec("base64",e),decText="";for(var t=0;t<e.byteLength;t++)decText+=String.fromCharCode(e[t]);return decText},trim:function(e){return null==e?"":(e+"").replace(n,"")}};', self.cacheJSCode, 'print(clearify("%s"))' % playerData]
        ret = js_execute( '\n'.join(jscode) )
        if ret['sts'] and 0 == ret['code']:
            printDBG(ret['data'])
            urlTab = self.up.getVideoLinkExt(ret['data'])
        return urlTab
        
    def getArticleContent(self, cItem, data=None):
        printDBG("Altadefinizione.getArticleContent [%s]" % cItem)
        retTab = []
        
        if data == None:
            url = cItem.get('prev_url', cItem['url'])
            sts, data = self.getPage(url)
            if not sts: data = ''
            
        descData = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'schedaFilm'), ('</ul', '>'), True)[1]
        icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(descData, '''<img[^>]+?src=['"]([^'^"]+?)['"]''')[0])
        
        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(descData, '<p', '</p>')[1])
        if desc == '':
            desc = self.cm.ph.getSearchGroups(data, '''(<meta[^>]+?description['"][^>]*?>)''')[0]
            desc = self.cleanHtmlStr( self.cm.ph.getSearchGroups(desc, '''content=['"]([^'^"]+?)['"]''')[0] )
        
        try: title = str(byteify(json.loads(self.cm.ph.getSearchGroups(data, '''"disqusTitle"\:("[^"]+?")''')[0])))
        except Exception: title = ''
        
        if title == '': title = cItem['title']
        if desc == '':  desc = cItem['desc']
        if icon == '':  icon = cItem['icon']
        
        otherInfo = {}
        
        # imdb_rating
        t = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<span', '>', 'rateIMDB'), ('</span', '>'), False)[1])
        if t != '': otherInfo['imdb_rating'] = t
        
        # raiting
        t = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, 'ratings_off(', ',', False)[1])
        if t != '': otherInfo['rating'] = t
        
        descMap = {'genere':    'genres',
                   'anno'  :    'year',
                   'qualitá':   'quality',
                   'scrittore': 'writers',
                   'attori':    'actors',
                   'regia':     'directors' } #stars
        
        descData = self.cm.ph.getAllItemsBeetwenNodes(descData, ('<li', '>'), ('</li', '>'), False)
        for item in descData:
            item = item.split('</label>', 1)
            marker = self.cleanHtmlStr(item[0]).replace(':', '').lower()
            if marker not in descMap: continue
            
            t = []
            item = self.cm.ph.getAllItemsBeetwenMarkers(item[-1], '<a', '</a>')
            for it in item:
                it = self.cleanHtmlStr(it)
                if it == '': continue
                t.append(it)
            if len(t): otherInfo[descMap[marker]] = ', '.join(t)
        
        return [{'title':self.cleanHtmlStr( title ), 'text': self.cleanHtmlStr( desc ), 'images':[{'title':'', 'url':self.getFullUrl(icon)}], 'other_info':otherInfo}]
        
    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('Altadefinizione.handleService start')
        
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name     = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode     = self.currItem.get("mode", '')
        
        printDBG( "handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category) )
        self.currList = []
        
    #MAIN MENU
        if name == None:
            self.listMainMenu({'name':'category', 'type':'category'})
        elif category == 'sub_items':
            self.listSubItems(self.currItem)
        elif category == 'list_categories':
            self.currList = self.cacheCategories
        elif category in ['list_items','search_items'] :
            self.listItems(self.currItem, 'explore_item')
        elif category == 'explore_item':
            self.exploreItem(self.currItem)
        elif category == 'az_main':
            self.listAZMain(self.currItem)
        elif category == 'az_item':
            self.listAZItem(self.currItem)
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
        CHostBase.__init__(self, AltadefinizioneCool(), True, [])
    
    def withArticleContent(self, cItem):
        if cItem.get('type', 'video') != 'video' and cItem.get('category', 'unk') != 'explore_item':
            return False
        return True

    