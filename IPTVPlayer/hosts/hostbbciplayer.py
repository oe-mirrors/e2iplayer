# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser

# needed for option bbc_use_web_proxy definition
from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.extractor.bbc import BBCCoUkIE
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib
try:    import json
except Exception: import simplejson as json
from Components.config import config, getConfigListEntry
###################################################

###################################################
# Config options for HOST
###################################################
def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Default video quality:"),             config.plugins.iptvplayer.bbc_default_quality))
    optionList.append(getConfigListEntry(_("Use default video quality:"),         config.plugins.iptvplayer.bbc_use_default_quality))
    optionList.append(getConfigListEntry(_("Preferred format:"),                  config.plugins.iptvplayer.bbc_prefered_format))
    optionList.append(getConfigListEntry(_("Use web-proxy (it may be illegal):"), config.plugins.iptvplayer.bbc_use_web_proxy))
    return optionList
###################################################


def gettytul():
    return 'https://www.bbc.co.uk/iplayer'

class BBCiPlayer(CBaseHostClass):
 
    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'BBCiPlayer.tv', 'cookie':'bbciplayer.cookie'})
        self.HEADER = {'User-Agent':'Mozilla/5.0', 'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Encoding':'gzip, deflate'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update( {'X-Requested-With': 'XMLHttpRequest'} )
        self.cm.HEADER = self.HEADER # default header
        self.defaultParams = {'header':self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        
        self.MAIN_URL = 'https://www.bbc.co.uk/'
        self.DEFAULT_ICON_URL = 'https://raw.githubusercontent.com/vonH/plugin.video.iplayerwww/master/icon.png' 
        
        self.MAIN_CAT_TAB = [{'category':'list_channels',      'title': _('Channels'),                           'url':self.getFullUrl('iplayer')  },
                             {'category':'list_categories',    'title': _('Categories'),                         'url':self.getFullUrl('iplayer')  },
                             {'category':'list_az_menu',       'title': _('A-Z'),                                'url':self.getFullUrl('iplayer/a-z/')  },
                             {'category':'list_items',         'title': _('Most Popular'),                       'url':self.getFullUrl('iplayer/group/most-popular')  },
                             {'category':'search',             'title': _('Search'), 'search_item':True,         'icon':'https://raw.githubusercontent.com/vonH/plugin.video.iplayerwww/master/media/search.png'},
                             {'category':'search_history',     'title': _('Search history'),                     }]
        self.otherIconsTemplate = 'https://raw.githubusercontent.com/vonH/plugin.video.iplayerwww/master/media/%s.png'
    
    def getFullUrl(self, url):
        return CBaseHostClass.getFullUrl(self, url).replace('&amp;', '&')

    def listAZMenu(self, cItem, nextCategory):
        characters = [('A', 'a'), ('B', 'b'), ('C', 'c'), ('D', 'd'), ('E', 'e'), ('F', 'f'),
                      ('G', 'g'), ('H', 'h'), ('I', 'i'), ('J', 'j'), ('K', 'k'), ('L', 'l'),
                      ('M', 'm'), ('N', 'n'), ('O', 'o'), ('P', 'p'), ('Q', 'q'), ('R', 'r'),
                      ('S', 's'), ('T', 't'), ('U', 'u'), ('V', 'v'), ('W', 'w'), ('X', 'x'),
                      ('Y', 'y'), ('Z', 'z'), ('0-9', '0-9')]
        for title, url in characters:
            params = {'good_for_fav': True, 'category':nextCategory, 'title':title, 'url':cItem['url'] + url}
            self.addDir(params)
    
    def listAZ(self, cItem, nextCategory):
        printDBG("BBCiPlayer.listAZ, cItem: %s, nextCategory: %s" % (cItem, nextCategory))

        sts, data = self.cm.getPage(cItem['url'], self.defaultParams)
        if not sts: 
            printDBG("Failed to get page.")
            return

        title = cItem['title'].lower()

        json_data = self.scrapeJSON(data)
        if json_data:
            try:
                uniqueTab = []
                for item in json_data['programmes'][title]['entities']:
                    episodesAvailable = item['meta']['episodesAvailable']
                    url = self.getFullUrl(item['props']['href'])
                    title = item['props']['title']
                    icon = item['props']['imageTemplate'].replace('{recipe}', '192x108')
                    desc = item['props']['synopsis']
                    
                    params = dict(cItem)
                    params.update({'good_for_fav': True, 'title':title, 'url':self.getFullUrl(url), 'icon':self.getFullIconUrl(icon), 'desc':desc})

                    if episodesAvailable > 1:
                        params['category'] = nextCategory
                        self.addDir(params)
                    else:
                        self.addVideo(params)
            except Exception:
                printExc()

    def listLive(self, cItem):
        printDBG("BBCiPlayer.listLive")
        channel_list = [
            ('bbc_one_hd',                       'BBC One'),
            ('bbc_two_hd',                       'BBC Two'),
            ('bbc_four_hd',                      'BBC Four'),
            ('bbc_scotland_hd',                  'BBC Scotland'),
            ('cbbc_hd',                          'CBBC'),
            ('cbeebies_hd',                      'CBeebies'),
            ('bbc_news24',                       'BBC News Channel'),
            ('bbc_parliament',                   'BBC Parliament'),
            ('bbc_alba',                         'Alba'),
            ('s4cpbs',                           'S4C'),
            ('bbc_one_london',                   'BBC One London'),
            ('bbc_one_scotland_hd',              'BBC One Scotland'),
            ('bbc_one_northern_ireland_hd',      'BBC One Northern Ireland'),
            ('bbc_one_wales_hd',                 'BBC One Wales'),
            ('bbc_two_scotland',                 'BBC Two Scotland'),
            ('bbc_two_northern_ireland_digital', 'BBC Two Northern Ireland'),
            ('bbc_two_wales_digital',            'BBC Two Wales'),
            ('bbc_two_england',                  'BBC Two England'),
            ('bbc_one_cambridge',                'BBC One Cambridge'),
            ('bbc_one_channel_islands',          'BBC One Channel Islands'),
            ('bbc_one_east',                     'BBC One East'),
            ('bbc_one_east_midlands',            'BBC One East Midlands'),
            ('bbc_one_east_yorkshire',           'BBC One East Yorkshire'),
            ('bbc_one_north_east',               'BBC One North East'),
            ('bbc_one_north_west',               'BBC One North West'),
            ('bbc_one_oxford',                   'BBC One Oxford'),
            ('bbc_one_south',                    'BBC One South'),
            ('bbc_one_south_east',               'BBC One South East'),
            ('bbc_one_west',                     'BBC One West'),
            ('bbc_one_west_midlands',            'BBC One West Midlands'),
            ('bbc_one_yorks',                    'BBC One Yorks')]

        for id, title in channel_list:
            url = 'http://a.files.bbci.co.uk/media/live/manifesto/audio_video/simulcast/hls/uk/hls_pc/ak/' + id + '.m3u8'
            
            params = {'good_for_fav': True, 'title':title, 'url':self.getFullUrl(url), 'icon':self.otherIconsTemplate % id}
            printDBG("Params - title: %s, url: %s, icon: %s"  % (params['title'], params['url'], params['icon']))
            self.addVideo(params)
    
    def listChannels(self, cItem, nextCategory):
        # TODO support regionalised content, probably via config
        printDBG("BBCiPlayer.listChannels")
        params = {'good_for_fav': True, 'category':'live_streams', 'title':_('Live'), 'icon':'https://raw.githubusercontent.com/vonH/plugin.video.iplayerwww/master/media/live.png'}
        self.addDir(params)
        
        channel_list = [
            ('bbcone',           'bbc_one_hd',              'BBC One'),
            ('bbctwo',           'bbc_two_hd',              'BBC Two'),
            ('tv/bbcthree',      'bbc_three_hd',          'BBC Three'),
            ('bbcfour',          'bbc_four_hd',            'BBC Four'),
            ('tv/bbcscotland',   'bbc_scotland_hd',    'BBC Scotland'),
            ('tv/cbbc',          'cbbc_hd',                    'CBBC'),
            ('tv/cbeebies',      'cbeebies_hd',            'CBeebies'),
            ('tv/bbcnews',       'bbc_news24',     'BBC News Channel'),
            ('tv/bbcparliament', 'bbc_parliament',   'BBC Parliament'),
            ('tv/bbcalba',       'bbc_alba',                   'Alba'),
            ('tv/s4c',           's4cpbs',                      'S4C')]
        
        for url, icon, title in channel_list:
            params = {'good_for_fav': True, 'category':nextCategory, 'title':title, 'url':self.getFullUrl(url), 'icon':self.otherIconsTemplate % icon}
            self.addDir(params)
        
    def listChannelMenu(self, cItem, nextCategory):
        printDBG("BBCiPlayer.listChannelMenu")

        sts, data = self.cm.getPage(cItem['url'], self.defaultParams)
        if not sts:
            printDBG("Failed to get page.")
            return

        json_data = self.scrapeJSON(data)
        if json_data:
            try:
                item = json_data['broadcasts']['items'][0]
                title = item['title']
                icon = item['image'].replace('{recipe}', '192x108')
                startTime = item['startTime']

                liveTitle = 'WATCH LIVE: ' + title + ' [' + startTime + ']'
                channelId = json_data['channel']['id']
                liveUrl = 'http://a.files.bbci.co.uk/media/live/manifesto/audio_video/simulcast/hls/uk/hls_pc/ak/' + channelId + '.m3u8'
                params = {'title':liveTitle, 'url':self.getFullUrl(liveUrl), 'icon':self.getFullIconUrl(icon)}
                printDBG("Params - title: %s, url: %s, icon: %s"  % (params['title'], params['url'], params['icon']))
                self.addVideo(params)

                #TODO add watch from start
            except Exception:
                printExc()

        params = dict(cItem)
        params.update({'good_for_fav': True, 'title':cItem['title']+' '+_('A-Z'), 'category':nextCategory, 'url':cItem['url']+'/a-z'})
        printDBG("Params title: %s, url: %s"  % (params['title'], params['url']))
        self.addDir(params)
        
        params = dict(cItem)
        params.update({'title':_('Featured'), 'category':'list_episodes'})
        self.addDir(params)
        
    def listMainMenu(self, cItem, nextCategory):
        printDBG("BBCiPlayer.listMainMenu")
        self.listsTab(self.MAIN_CAT_TAB, cItem)
                
    def listCategories(self, cItem, nextCategory):
        printDBG("BBCiPlayer.listCategories")
        
        sts, data = self.cm.getPage(cItem['url'], self.defaultParams)
        if not sts:
            printDBG("Failed to get page.")
            return

        json_data = self.scrapeJSON(data)
        if json_data:
            try:
                for item in json_data['navigation']['items'][1]['subItems']:
                    title = item['title']
                    url   = item['href']
                    params = dict(cItem)
                    params.update({'category':nextCategory, 'title':title, 'url':self.getFullUrl(url)})
                    self.addDir(params)
            except Exception:
                printExc()
            
    def listCatFilters(self, cItem, nextCategory):
        printDBG("BBCiPlayer.listCatFilters")
        
        sts, data = self.cm.getPage(cItem['url'], self.defaultParams)
        if not sts: return
        baseUrl = self.cm.meta['url']
        
        data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="filters">', '</ul>', withMarkers=False)[1]
        if '' != data:
            params = dict(cItem)
            params.update({'title':_('All'), 'category':nextCategory, 'url':baseUrl})
            self.addDir(params)
            
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, "<li", '</li>', withMarkers=True)
            for item in data:
                title = self.cleanHtmlStr(item)
                url   = self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0]
                params = dict(cItem)
                params.update({'title':title, 'category':nextCategory, 'url':self.getFullUrl(url)})
                self.addDir(params)
            return
        self.listCategory(cItem)
        
    def listCategory(self, cItem):
        printDBG("BBCiPlayer.listCategory")
        
        if not cItem.get('is_sub_cat', False):
            sts, data = self.cm.getPage(cItem['url'], self.defaultParams)
            if not sts: return
            baseUrl = self.cm.meta['url']
            
            data = self.cm.ph.getDataBeetwenMarkers(data, '<ul id="tleo-switcher"', '</ul>', withMarkers=False)[1]
            if data != '':
                data = self.cm.ph.getAllItemsBeetwenMarkers(data, "<li", '</li>', withMarkers=True)
                for item in data:
                    title = self.cleanHtmlStr(item)
                    url   = self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0]
                    if url == '': url = baseUrl
                    params = dict(cItem)
                    params.update({'is_sub_cat':True, 'title':title, 'url':self.getFullUrl(url)})
                    self.addDir(params)
                return
        
        cItem = dict(cItem)
        cItem['is_sub_cat'] = True
        if 'highlights' in cItem['url']:
            self.listItems2(cItem, 'list_episodes')
        else:
            self.listItems(cItem, 'list_episodes')
            
    def listItems3(self, cItem, nextCategory):
        printDBG("BBCiPlayer.listItems3")

        sts, data = self.cm.getPage(cItem['url'], self.defaultParams)
        if not sts: return
        
        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'channel-page'), ('<div', '>', 'endpanel js-stat'), withNodes=False)[1]
        data = data.split('</div><div class="gel-layout__item')
        for item in data:
            if 'grouped-items' in item:
                item = item.split('<ul class="group__list">')[0]
                
                url = self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0]
                if url == '' or '/features/' in url: continue
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h3', '</h3>')[1])
                if title == '': continue
                icon  = self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0]
                desc  = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<p', '</p>')[1])
                params = {'good_for_fav': True, 'category':nextCategory, 'title':title, 'url':self.getFullUrl(url), 'icon':self.getFullIconUrl(icon), 'desc':'[/br]'.join(descTab)}
                self.addDir(params)
            else:
                url = self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0]
                if url == '' or '/features/' in url: continue
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h3', '</p>')[1])
                if title == '': continue
                
                icon  = self.cm.ph.getSearchGroups(item, '''<source[^>]+?srcset=['"]([^'^"^\s]+?)['"\s]''')[0]
                
                tmp = self.cm.ph.getAllItemsBeetwenMarkers(item, '<p', '</p>', withMarkers=True)
                descTab = []
                for tmpItem in tmp:
                    descTab.append(self.cleanHtmlStr(tmpItem))
                
                params = {'good_for_fav': True, 'title':title, 'url':self.getFullUrl(url), 'icon':self.getFullIconUrl(icon), 'desc':'[/br]'.join(descTab)}
                if 'tviplayericon-iplayer' in item:
                    self.addVideo(params)
                else:
                    params['category'] = nextCategory
                    self.addDir(params)
            
    def listItems2(self, cItem, nextCategory):
        printDBG("BBCiPlayer.listItems2")

        sts, data = self.cm.getPage(cItem['url'], self.defaultParams)
        if not sts: return
        
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<ol class="grid__row', '</ol>', withMarkers=True)
        for group in data:
            if 'grouped-items' in group:
                item = group.split('<li class="grouped-items__list-item">')[0]
                
                url = self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0]
                if url == '' or '/features/' in url: continue
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h3', '</h3>')[1])
                if title == '': continue
                icon  = self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0]
                desc  = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<p', '</p>')[1])
                params = {'good_for_fav': True, 'category':nextCategory, 'title':title, 'url':self.getFullUrl(url), 'icon':self.getFullIconUrl(icon), 'desc':'[/br]'.join(descTab)}
                self.addDir(params)
            else:
                group = group.split('</li>')
                for item in group:
                    url = self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0]
                    if url == '' or '/features/' in url: continue
                    title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h3', '</p>')[1])
                    if title == '': continue
                    
                    icon  = self.cm.ph.getSearchGroups(item, '''<source[^>]+?srcset=['"]([^'^"^\s]+?)['"\s]''')[0]
                    
                    tmp = self.cm.ph.getAllItemsBeetwenMarkers(item, '<p', '</p>', withMarkers=True)
                    descTab = []
                    for tmpItem in tmp:
                        descTab.append(self.cleanHtmlStr(tmpItem))
                    
                    params = {'good_for_fav': True, 'title':title, 'url':self.getFullUrl(url), 'icon':self.getFullIconUrl(icon), 'desc':'[/br]'.join(descTab)}
                    if 'tviplayericon-iplayer' in item:
                        self.addVideo(params)
                    else:
                        params['category'] = nextCategory
                        self.addDir(params)

    # when the url is actually an episode url but you want to get all eposides via the View All link
    def listItemsViewAll(self, cItem, nextCategory):
        printDBG("BBCiPlayer.listItemsViewAll")
        sts, data = self.cm.getPage(cItem['url'], self.defaultParams)
        if not sts:
            printDBG("Failed to get page.")
            return
        
        title = cItem['title'].lower()

        json_data = self.scrapeJSON(data)
        if json_data:
            try:
                tleo_id = json_data['episode']['tleoId']
                
                cItem.update({'url':self.getFullUrl('/iplayer/episodes/' + tleo_id), 'category':'list_episodes'}) 
                self.listItems(cItem, nextCategory)
            except Exception:
                printExc()

    def listItems(self, cItem, nextCategory):
        printDBG("BBCiPlayer.listItems")
        
        url  = cItem['url']
        page = cItem.get('page', 1)
        if page > 1:
            if '?' in url: url += '&'
            else: url += '?'
            url += 'page=%s' % page
        
        sts, data = self.cm.getPage(url, self.defaultParams)
        if not sts:
            printDBG("Failed to get page: url[%s]" % url)
            return
        
        json_data = self.scrapeJSON(data)
        if json_data:
            try:
                if 'entities' in json_data:
                    items = json_data['entities']
                elif 'highlights' in json_data:
                    items = json_data['highlights']['items']
                
                for item in items:
                    if 'props' in item:
                        props = item.get('props')
                        
                        title = props['title']
                        url = props['href']
                        icon = props['imageTemplate'].replace('{recipe}', '192x108')
                        
                        if 'synopsis' in props:
                            desc = props['synopsis']
                        elif 'subtitle' in props:
                            desc = props['subtitle']
                        
                        params = {'good_for_fav': True, 'title':title, 'url':self.getFullUrl(url), 'icon':self.getFullIconUrl(icon), 'desc':desc}
                        
                        if 'duration' in props:
                            duration = props['duration']
                            params['title'] = title + ' [' + duration + ']'

                        printDBG("Video found: title[%s], url[%s], icon[%s], desc[%s]" % (title, url, icon, desc))
                        self.addVideo(params)
                        
                        # TODO sometimes these should actually be added as directories to link to the series (Categories, Search, etc)
                    else:
                        printDBG("Failed to find props in this item")
                        continue

                nextPage = False
                if 'pagination' in json_data:                        
                    pagination = json_data.get('pagination')
                    if 'currentPage' in pagination and 'totalPages' in pagination:
                        currentPage = pagination['currentPage']
                        totalPages = pagination['totalPages']
                        nextPage = currentPage < totalPages
            except Exception:
                printExc()
        else:
            printDBG("Failed to scrape JSON")

        if nextPage:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title':_('Next page'), 'page':page+1})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("BBCiPlayer.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        
        cItem = dict(cItem)
        # if search pattern was specified, use it to build the URL, otherwise 
        # leave the URL alone - it will already be set if this is a Next Page search
        if len(searchPattern):
            cItem['url'] = self.getFullUrl('iplayer/search?q=' + urllib.quote_plus(searchPattern))

        self.listItems(cItem, 'list_episodes')
    
    def scrapeJSON(self, html):
        # TODO format 1 never seems to work, so update to default to format 2
        printDBG("BBCiPlayer.scrapeJSON - scraping for video versions. Format 1.")
        json_data = None
        format = 1
        match = re.search(r'window\.mediatorDefer\=page\(document\.getElementById\(\"tviplayer\"\),(.*?)\);', html, re.DOTALL)
        if not match:
            printDBG("Format 1 failed. Trying format 2.")
            format = 2
            match = re.search(r'window.__IPLAYER_REDUX_STATE__ = (.*?);\s*</script>', html, re.DOTALL)
        if match:
            data = match.group(1)
            json_data = json_loads(data)
            if json_data:
                if format == 1:
                    if 'appStoreState' in json_data:
                        json_data = json_data.get('appStoreState')
                    elif 'initialState' in json_data:
                        json_data = json_data.get('initialState')
        else:
            printDBG("Format 2 failed. Trying format 3.")
            format = 3
            match = re.search(r"'episode_id'\] = '([a-z\d]+)';", html, re.DOTALL)
            if match and match.groups():
                match = false
                episode_id = matches.group(1)
                printDBG("Episode ID found: %s" % episode_id)

                jsonurl = "https://www.bbc.co.uk/programmes/%s.json" % episode_id

                sts, data = self.cm.getPage(jsonurl, self.defaultParams)
                if sts:
                    printDBG("JSON page retrieved")
                    json_data = json_loads(data)['programme']
                   
        return json_data

    def getLinksForVideo(self, cItem):
        printDBG("BBCiPlayer.getLinksForVideo [%s]" % cItem)
        
        retTab = []
        
        if cItem['url'].endswith('m3u8'):
            url = cItem['url']
            data = getDirectM3U8Playlist(url, checkExt=False)
            if 1 == len(data):
                cItem['url'] = urlparser.decorateUrl(cItem['url'], {'iptv_proto':'m3u8', 'iptv_livestream':True})
                retTab.append(cItem)
            else:
                for item in data:
                    item['url'] = urlparser.decorateUrl(item['url'], {'iptv_proto':'m3u8', 'iptv_livestream':True})
                    retTab.append(item)

            return retTab
        else:
            sts, data = self.cm.getPage(cItem['url'], self.defaultParams)

        if not sts: return retTab
        
        json_data = self.scrapeJSON(data)
        if json_data:
            try:
                uniqueTab = []
                for item in json_data['versions']:
                    if 'id' in item:
                        item_id = item.get('id')
                    elif 'pid' in item:
                        item_id = item.get('pid')
                    else:
                        continue

                    url  = self.getFullUrl('/iplayer/vpid/%s/' % item_id)
                    if url in uniqueTab:
                        continue

                    uniqueTab.append(url)
                    if 'kind' in item:
                        name = item['kind'].title()
                    elif 'types' in item:
                        name = item['types'][0]
                    else:
                        name = item_id

                    retTab.append({'name':name, 'url':url, 'need_resolve':1})
            except Exception:
                printExc()

            if len(retTab):
                return retTab
            else:
                retTab.append({'name':'', 'url':cItem['url'], 'need_resolve':1})
        else:
            printDBG("Failed to retrieve JSON.")

        return retTab
        
    def getVideoLinks(self, url):
        printDBG("BBCiPlayer.getVideoLinks [%s]" % url)
        return self.up.getVideoLinkExt(url)
        
    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('BBCiPlayer.handleService - start')
        
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        
        self.informAboutGeoBlockingIfNeeded('GB')
        
        name     = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode     = self.currItem.get("mode", '')
        
        printDBG( "handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category) )
        self.currList = []
        
        #MAIN MENU
        if name == None:
            rm(self.COOKIE_FILE)
            self.listMainMenu({'name':'category', 'url':self.MAIN_URL}, 'list_items')
        elif 'live_streams' == category:
            self.listLive(self.currItem)
        elif 'list_channels' == category:
            self.listChannels(self.currItem, 'list_channel')
        elif 'list_channel' == category:
            self.listChannelMenu(self.currItem, 'list_items')
        elif 'list_az_menu' == category:
            self.listAZMenu(self.currItem, 'list_az')
        elif 'list_az' == category:
            self.listAZ(self.currItem, 'list_episodes_view_all')
        elif 'list_categories' == category:
            self.listCategories(self.currItem, 'list_cat_filters')
        elif category in 'list_cat_filters':
            self.listCatFilters(self.currItem, 'list_category')
        elif 'list_category' == category:
            self.listCategory(self.currItem)
        elif 'list_items' == category:
            self.listItems(self.currItem, 'list_episodes')
        elif 'list_items2' == category:
            #TODO list_items2 no longer used, remove after test
            self.listItems2(self.currItem, 'list_episodes')
        elif 'list_items3' == category:
            #TODO list_items3 no longer used, remove after test
            self.listItems3(self.currItem, 'list_episodes')
        elif 'list_episodes' == category:
            self.listItems(self.currItem, 'video')
        elif 'list_episodes_view_all' == category:
            self.listItemsViewAll(self.currItem, 'video')

        #SEARCH
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item':False, 'name':'category'}) 
            self.listSearchResult(cItem, searchPattern, searchType)
        #HISTORIA SEARCH
        elif 'search_history' == category:
            self.listsHistory({'name':'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()
        
        CBaseHostClass.endHandleService(self, index, refresh)

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, BBCiPlayer(), True, [])
    