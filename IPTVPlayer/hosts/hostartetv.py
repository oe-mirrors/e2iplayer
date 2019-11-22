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
###################################################


def gettytul():
    return 'https://www.arte.tv/'

class ArteTV(CBaseHostClass):
    
    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'arte.tv', 'cookie':'arte.tv.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.MAIN_URL = 'https://www.arte.tv/'
        self.DEFAULT_ICON_URL = 'https://i.pinimg.com/originals/3c/e6/54/3ce6543cf583480fa6d0e233384f336e.jpg'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT':'1', 'Accept': 'text/html', 'Accept-Encoding':'gzip, deflate', 'Referer':self.getMainUrl(), 'Origin':self.getMainUrl()}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update( {'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding':'gzip, deflate', 'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8', 'Accept':'application/json, text/javascript, */*; q=0.01'} )
        
        self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        
    def getPage(self, baseUrl, addParams = {}, post_data = None):
        if addParams == {}: addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)
    
    def listMainMenu(self, cItem, nextCategory):
        printDBG("ArteTV.listMainMenu")
        
        lang = GetDefaultLang()
        url = self.getMainUrl()
        if lang in ['en','fr','de','es','pl']:
            url += lang
        
        sts, data = self.getPage(url)
        if not sts: return
        
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<a', '>', ' lang='), ('</a', '>'))
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(item)
            lang = url.split('/')[3]
            printDBG("+++> lang[%s] title[%s]" % (lang, title))
            params = dict(cItem)
            params.update({'good_for_fav':False, 'category':nextCategory, 'title':title, 'url':url, 'f_lang':lang})
            self.addDir(params)
            
        MAIN_CAT_TAB = [{'category':'search',         'title': _('Search'),          'search_item':True}, 
                        {'category':'search_history', 'title': _('Search history')},]
        
        self.listsTab(MAIN_CAT_TAB, cItem)
        
    def listLang(self, cItem, nextCategory):
        printDBG("ArteTV.listLang [%s]" % cItem)
        
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        
        if False:
            tmp = self.cm.ph.getDataBeetwenNodes(data, ('<a', '>', '/direct/'), ('</a', '>'))[1]
            url = self.getFullUrl(self.cm.ph.getSearchGroups(tmp, '''\shref=['"]([^'^"]+?)['"]''')[0])
            if url != '':
                title = self.cleanHtmlStr(tmp)
                params = dict(cItem)
                params.update({'good_for_fav':True, 'title':title, 'url':url})
                self.addVideo(params)
        
        params = dict(cItem)
        params.update({'good_for_fav':False, 'category':nextCategory, 'title':_('Main'), 'url':cItem['url']})
        self.addDir(params)
        
        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<a', '>', '/search/'), ('</a', '>'))[1]
        url = self.getFullUrl(self.cm.ph.getSearchGroups(tmp, '''\shref=['"]([^'^"]+?)['"]''')[0])
        if url != '':
            sts, data = self.getPage(url)
            if not sts: return
            
            tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<article', '>'), ('</article', '>'))
            for item in tmp:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0])
                title = self.cleanHtmlStr(item)
                params = dict(cItem)
                params.update({'good_for_fav':False, 'category':nextCategory, 'title':title, 'url':url})
                self.addDir(params)
            
            data = self.cm.ph.getDataBeetwenNodes(data, ('<nav', '>', 'navigation'), ('</nav', '>'))[1]
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
            for item in data:
                url = self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0]
                if '/videos/' not in url: continue
                title = self.cleanHtmlStr(item)
                params = dict(cItem)
                params.update({'good_for_fav':False, 'category':nextCategory, 'title':title, 'url':self.getFullUrl(url)})
                self.addDir(params)
        
    def listItems(self, cItem, nextCategory):
        printDBG("ArteTV.listItems [%s]" % cItem)
        
        nextPage = False
        baseParams = dict(cItem)
        page = baseParams.pop('page', 1)
        
        baseUrl = cItem['url']
        if '/search/' in baseUrl: baseUrl += '&page=%s' % page
        
        sts, data = self.getPage(baseUrl)
        if not sts: return
        
        iconsMap = {}
        
        jsonData = self.cm.ph.getDataBeetwenNodes(data, ('__INITIAL_STATE__', '='), ('</script', '>'), False)[1].strip()
        try:
            jsonData = json_loads(jsonData[:jsonData.find('};')+1])
            try:
                for item in jsonData['videos']['videos']:
                    try: iconsMap[item['url']] = item['images'][0]['url']
                    except Exception: pass
            except Exception:
                printExc()
            
            try:
                currentCode = jsonData['pages']['currentCode']
                for zone in jsonData['pages']['list'][currentCode]['zones']:
                    for item in zone['data']:
                        try: iconsMap[item['url']] = item['images']['landscape']['resolutions'][0]['url']
                        except Exception: printExc()
            except Exception:
                printExc()
        except Exception:
            printExc()
        
        idx = 0
        sectionTitle = ''
        sectionUrl = ''
        tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<section', '>'), ('</section', '>'))
        while idx < len(tmp):
            
            if 'next-teaser__link' not in tmp[idx] and '__duration' not in tmp[idx]:
                sectionTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(tmp[idx], '<h2', '</h2>')[1])
                if sectionTitle == '': sectionTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(tmp[idx], ('<li', '>', 'is-highlighted'), ('</li', '>'))[1])
                sectionUrl = self.getFullUrl(self.cm.ph.getSearchGroups(tmp[idx], '''\shref=['"]([^'^"]+?)['"]''')[0])
                if 'arte.tv' in sectionUrl: 
                    if not sectionUrl.endswith('/search/'):
                        if sectionTitle == '':
                            sectionTitle = sectionUrl.split('/')[-2].replace('-', ' ').upper()
                        params = dict(baseParams)
                        params.update({'good_for_fav':True, 'title':sectionTitle, 'url':sectionUrl})
                        self.addDir(params)
                    idx += 2
                    sectionTitle = ''
                    sectionUrl = ''
                    continue
            else:
                tmpSectionTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(tmp[idx], ('<h', '>', 'section-title'), ('</h', '>'))[1])
                if tmpSectionTitle != '': sectionTitle = tmpSectionTitle
            
            itemsTab = []
            itemsData = self.cm.ph.getAllItemsBeetwenNodes(tmp[idx], ('<a', '>', 'next-teaser__link'), ('</a', '>'))
            if len(itemsData) == 0: itemsData = self.cm.ph.getAllItemsBeetwenNodes(tmp[idx], ('<a', '</a>', '__duration'), ('</div', '>'))
            for item in itemsData:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0])
                if url == '': continue
                if self.up.getDomain(self.getMainUrl(), True) != self.up.getDomain(url, True): continue
                icon  = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''\ssrc=['"]([^'^"]+?)['"]''')[0])
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h3', '</h3>')[1])
                if title == '': title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'teaser__title'), ('</div', '>'))[1])
                if title == '': title = url.split('/')[-2].replace('-', ' ').upper()
                desc  = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<p', '</p>')[1])
                icon = iconsMap.get(url, icon)
                params = {'title':title, 'url':url, 'icon':icon, 'desc':desc}
                if 'next-playlist' in item: params['type'] = 'dir_2'
                elif ('next-collection' in item or 'reportage/' in tmp[idx] or '/RC-' in url) and '_duration' not in item: params['type'] = 'dir_1'
                else: params['type'] = 'video'
                itemsTab.append(params)
            
            idx += 1
            if 0 == len(itemsTab): continue
            
            if sectionTitle != '':
                params = dict(baseParams)
                params.update({'good_for_fav':False, 'category':nextCategory, 'title':sectionTitle, 'items_tab':itemsTab})
                self.addDir(params)
            else:
                nextPage = True
                params = dict(baseParams)
                params['items_tab'] = itemsTab
                self.listSectionItems(params, 'list_items', 'list_playlist')
            
            sectionTitle = ''
            sectionUrl = ''
        
        if nextPage and len(self.currList):
            if '/search/' in baseUrl and '"hasNextPage":true' in data:
                params = dict(cItem)
                params.update({'good_for_fav':False, 'title':_("Next page"), 'page':page+1})
                self.addDir(params)
            else:
                try:
                    if None != jsonData.get('pages'):
                        nextPage = ''
                        currentCode = jsonData['pages']['currentCode']
                        for zone in jsonData['pages']['list'][currentCode]['zones']:
                            if zone['nextPage'] != None and 'code' in zone and zone['code'] != None: # and zone['code'].split('_', 1)[-1] in cItem['url']:
                                nextPage = zone['nextPage']
                                break
                        
                        if nextPage == '': return
                        
                        lang = jsonData['pages']['list'][currentCode]['language']
                        web  = jsonData['pages']['list'][currentCode]['support']
                        code = zone['code']['name']
                        printDBG('CODE: %s' % zone['code'])
                        nextPage = nextPage.rsplit('/', 1)[-1]
                        if code in nextPage:
                            #url = self.getFullUrl('/guide/api/api/zones/%s/%s/%s' % (lang, web, re.compile('''page=[0-9]+''').sub('page={0}', nextPage)))
                            url = self.getFullUrl('/guide/api/api/zones/%s/%s' % (lang, re.compile('''page=[0-9]+''').sub('page={0}', nextPage)))
                        else:
                            #url = self.getFullUrl('/guide/api/api/zones/%s/%s/%s?limit=20' % (lang, web, code))\
                            url = self.getFullUrl('/guide/api/api/zones/%s/%s?limit=20' % (lang, code))
                        params = dict(cItem)
                        params.update({'good_for_fav':False, 'category':'list_json_items', 'title':_("Next page"), 'page':page+1, 'url':url})
                        self.addDir(params)
                    elif 'videos' in jsonData and jsonData['videos'] != None and len(self.currList) < jsonData['videos']['total']:
                        lang = jsonData['videos']['locale']
                        code = jsonData['videos']['type']
                        url = self.getFullUrl('/guide/api/api/videos/%s/%s/' % (lang, code))
                        params = dict(cItem)
                        params.update({'good_for_fav':False, 'category':'list_json_items', 'title':_("Next page"), 'page':page+1, 'url':url})
                        self.addDir(params)
                except Exception:
                    printExc()
        
    def listJSONItems(self, cItem, nextCategory):
        printDBG("ArteTV.listJSONItems [%s]" % cItem)
        
        baseParams = dict(cItem)
        page = baseParams.pop('page', 1)
        
        url = cItem['url']
        if '{0}' in url:
            url = url.format(str(page))
        else:
            if '?' in url: url += '&'
            else: url += '?'
            url += 'page=' + str(page)
        
        sts, data = self.getPage(url)
        if not sts: return
        
        printDBG('+++++++++++++++++++++++++++++++++')
        printDBG(data)
        printDBG('+++++++++++++++++++++++++++++++++')
        
        try:
            data = json_loads(data)
            if 'videos' in data and data['videos'] != None:
                tab = data['videos']
                type = 'video'
                divider = 1
            elif 'data' in data and data['data'] != None:
                tab = data['data']
                type = 'zone'
                divider = 60.0
            
            for item in tab:
                url = self.getFullUrl( item['url'] )
                title = self.cleanHtmlStr( item['title'] )
                if None != item.get('subtitle', None): title += ' - ' + self.cleanHtmlStr( item['subtitle'] )
                if type == 'zone': icon = self.getFullIconUrl(item['images']['landscape']['resolutions'][0]['url'])
                else: icon = self.getFullIconUrl(item['images'][0]['url'])
                
                if item.get('duration', 0) > 0: desc = ['%s min' % int(round(item['duration'] / divider))]
                else: desc = []
                
                if None != item.get('description', None): desc.append(self.cleanHtmlStr(str(item['description'])))
                params = dict(cItem)
                params.update({'good_for_fav':True, 'title':title, 'url':url, 'icon':icon, 'desc':'[/br]'.join(desc)})
                if item.get('duration', 0) > 0:
                    self.addVideo(params)
                else:
                    params['category'] = nextCategory
                    self.addDir(params)
                
            if len(self.currList) and (('zone' == type and '://' in data['nextPage']) or ('video' == type and data['meta']['videos']['page'] < data['meta']['videos']['pages'])):
                params = dict(cItem)
                params.update({'good_for_fav':False, 'title':_("Next page"), 'page':page+1})
                self.addDir(params)
        except Exception:
            printExc()
        
    def listSectionItems(self, cItem, nextCategory1, nextCategory2):
        printDBG("ArteTV.listSectionItems [%s]" % cItem)
        cItem = dict(cItem)
        listTab = cItem.pop('items_tab', [])
        for item in listTab:
            params = dict(cItem)
            params.update(item)
            if item['type'] == 'dir_1':
                params['category'] = nextCategory1
                self.addDir(params)
            elif item['type'] == 'dir_2':
                params['category'] = nextCategory2
                self.addDir(params)
            else:
                self.addVideo(params)
        
    def listPlaylistItems(self, cItem):
        printDBG("ArteTV.listPlaylistItems [%s]" % cItem)
        
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        
        url = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0])
        
        sts, data = self.getPage(url)
        if not sts: return
        
        data = self.cm.ph.getDataBeetwenNodes(data, ('var ', '=', 'js_json_playlist'), ('var ', ';', '='), False)[1].strip()[:-1]
        try:
            data = json_loads(data)
            for item in data['videos']:
                url = self.getFullUrl( item['url'] )
                title = self.cleanHtmlStr( item['title'] )
                icon = self.getFullIconUrl(item['mainImage']['url'])
                
                desc = [self.cleanHtmlStr(item.get('originalTitle', ''))]
                desc.append('%s min' % int(round(item['durationSeconds'] / 60.0)))
                params = dict(cItem)
                params.update({'good_for_fav':True, 'title':title, 'url':url, 'icon':icon, 'desc':' | '.join(desc)})
                self.addVideo(params)
        except Exception:
            printExc()
        
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("ArteTV.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        
        url = self.getFullUrl('/%s/search/?q=%s' % (searchType, urllib.quote_plus(searchPattern)))
        params = dict(cItem)
        params.update({'url':url, 'category':'list_items', 'f_lang':searchType})
        self.listItems(params, 'list_section_items')
            
    def getLinksForVideo(self, cItem):
        printDBG("ArteTV.getLinksForVideo [%s]" % cItem)
        self.cacheLinks = {}

        linksTab = []
        baseUrl = cItem['url']
        sts, data = self.getPage(baseUrl)
        if not sts: 
            return

        url = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0])
        if url:
            printDBG("ArteTv.Found iframe in page - old mode")
            jsonUrl = url.split('json_url=', 1)[-1].split('&', 1)[0]
            
            if not jsonUrl:
                sts, data = self.getPage(url)
                if not sts: 
                    return
            
                data = self.cm.ph.getDataBeetwenNodes(data, ('var', '=', 'js_json'), ('</script', '>'), False)[1]
                data[:data.find('};')+1]
            else:
                sts, data = self.getPage(urllib.unquote(jsonUrl))
                if not sts: 
                    return

            try:
                langsMap = {'FR':'fr', 'ESP':'es', 'DE':'de', 'POL':'pl', 'ANG':'en'}
                self.cacheLinks = {}
                cacheLabels = {}

                data = json_loads(data)
                for key in data['videoJsonPlayer']['VSR']:
                    item = data['videoJsonPlayer']['VSR'][key]
                    if item['mediaType'] not in ['mp4', 'hls']: continue
                    lang = item.get('versionShortLibelle', '').split('-')[-1]
                    lang = langsMap.get(lang, '')
                    res = '%sx%s' % (item['width'], item['height'])
                    name = '[%s] %s' % (item['mediaType'], res)

                    if lang not in self.cacheLinks:
                        self.cacheLinks[lang] = []
                        cacheLabels[lang] = item['versionLibelle']
                    self.cacheLinks[lang].append({'name':name, 'url':item['url'], 'bitrate':item['bitrate'], 'type':item['mediaType'], 'quality':item['quality']})

                currLang = cItem.get('f_lang', '')
                printDBG("+++> lang[%s]" % currLang)

                if currLang in self.cacheLinks:
                    linksTab.append({'name':cacheLabels.get(currLang, currLang), 'url':'https://|' + currLang, 'need_resolve':1})

                for lang in self.cacheLinks:
                    if lang == currLang: continue
                    linksTab.append({'name':cacheLabels.get(lang, lang), 'url':'https://|' +lang, 'need_resolve':1})
            
            except Exception:
                printExc()

        else:
            printDBG("ArteTv.Not found iframe in page")
            #open general json
            # "".concat(n.cdnUrl, "/").concat(n.version, "/config/json/general.json")
            # now: 
            generalJsonUrl = "https://static-cdn.arte.tv/static/artevp/5.0.6/config/json/general.json"
            
            sts, dataJson = self.getPage(generalJsonUrl)
            
            if not sts:
                return
            
            printDBG(dataJson)
            
            dataJson = json_loads(dataJson)
            token = dataJson['apiplayer']['token']
            printDBG("Api Token: %s" % token)
            
            currentCode = self.cm.ph.getSearchGroups(data, "\"currentCode\":\"([^{}\"]+?)\{\}\"", 1 , True)[0]
            if not currentCode:
                printDBG("Not found video code")
                return
            
            currentCode = currentCode.split("_")
            printDBG("Video code: %s" % str(currentCode))
            
            apiUrl = "https://api.arte.tv/api/player/v2/config/" + currentCode[1] + "/" + currentCode[0]
            printDBG("Api Url: %s " % apiUrl)
            
            header = {
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Authorization': 'Bearer %s' % token,
                'Referer': baseUrl,
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.108 Safari/537.36'
            }
            
            sts, data = self.getPage(apiUrl, {"header" : header})
            
            if not sts:
                return 
            
            data = json_loads(data)
            
            try:
                for s in data["data"]["attributes"]["streams"]:
                    if s["protocol"].lower() == "hls":
                        linksTab.extend(getDirectM3U8Playlist(s['url'], checkExt=False, variantCheck=True, checkContent=True, sortWithMaxBitrate=99999999))
                    
            except Exception:
                printExc()

        return linksTab
        
    def getVideoLinks(self, videoLink):
        printDBG("PlanetStreaming.getVideoLinks [%s]" % videoLink)
        urlTab = []
        
        mp4Tab = []
        hlsTab = []
        tmpTab = self.cacheLinks.get(videoLink.split('|', 1)[-1], [])
        for item in tmpTab:
            if item['type'] == 'hls':
                hlsTab.extend(getDirectM3U8Playlist(item['url'], checkContent=True, sortWithMaxBitrate=999999999))
            else:
                mp4Tab.append(item)
        mp4Tab.sort(key=lambda item: item['bitrate'], reverse=True)
        
        urlTab.extend(mp4Tab)
        urlTab.extend(hlsTab)
        return urlTab
    
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
            self.listLang(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem, 'list_section_items')
        elif category == 'list_section_items':
            self.listSectionItems(self.currItem, 'list_items', 'list_playlist')
        elif category == 'list_playlist':
            self.listPlaylistItems(self.currItem)
        elif category == 'list_json_items':
            self.listJSONItems(self.currItem, 'list_items')
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
    