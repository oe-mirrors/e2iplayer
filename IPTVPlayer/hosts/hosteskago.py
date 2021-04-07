# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify, MergeDicts
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs import ph
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
###################################################

###################################################
# FOREIGN import
###################################################
import re
###################################################

def gettytul():
    return 'http://www.eskago.pl/'

class EskaGo(CBaseHostClass):
 
    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'eskaGO.pl', 'cookie': 'eskagopl.cookie'})
        
        self.HEADER = {'User-Agent': 'Mozilla/5.0', 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        
        self.MAIN_URL = 'http://www.eskago.pl/'
        self.MAIN_ESKAPL_URL = 'http://www.eska.pl/'
        self.DEFAULT_ICON_URL = self.MAIN_URL + 'html/img/fb.jpg'
        
        self.MAIN_CAT_TAB = [#{'category':'list_vod_casts',          'title': 'VOD',                      'url':self.getFullUrl('vod')     },
                             {'category': 'list_radio_cats', 'title': 'Radio Eska Go', 'url': self.getFullUrl('radio')},
                             {'category': 'list_radio_eskapl', 'title': 'Radio Eska PL', 'url': self.MAIN_ESKAPL_URL, 'icon': 'https://www.press.pl/images/contents/photo_51546_1515158162_big.jpg'},
                             ]
                            # {'category':'search',                  'title': _('Search'),                'search_item':True,              },
                            # {'category':'search_history',          'title': _('Search history'),                                         } 
                            #]
        
        self.cacheItems = {}
        
    def listRadioCats(self, cItem, nextCategory):
        printDBG('listRadioCats')
        self.cacheItems = {}
        
        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return
        
        ###########################
        listDataTab = self.cm.ph.getDataBeetwenMarkers(data, '<div class="channel-list-box"', '<script>', False)[1]
        listDataTab = listDataTab.split('<div class="channel-list-box"')
        for listData in listDataTab:
            listId = self.cm.ph.getSearchGroups(listData, '''channel\-list\-([^"^']+?)["']''')[0]
            self.cacheItems[listId] = []
            
            headMarker = '<div class="head-title">'
            tmpTab = self.cm.ph.getAllItemsBeetwenMarkers(listData, headMarker, '</ul>')
            for tmp in tmpTab:
                desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(tmp, headMarker, '</div>', False)[1])
                tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li>', '</li>')
                for item in tmp:
                    if 'play_icon' not in item:
                        continue
                    url = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
                    title = self.cleanHtmlStr(item)
                    self.cacheItems[listId].append({'good_for_fav': True, 'type': 'audio', 'title': title, 'url': url, 'desc': desc})
        printDBG('#########################################')
        printDBG(self.cacheItems)
        printDBG('#########################################')
        ###########################
            
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<div class="new-radio-box">', '<div class="row radio-list">', False)[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<a', '</a>')
        for item in tmp:
            url = self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0]
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''color[^>]+?src=['"]([^'^"]+?)['"]''')[0])
            if url != '#':
                url = self.getFullUrl(url)
            if self.cm.isValidUrl(url):
                title = url.split('/')[-1].replace('-', ' ').title()
                params = {'good_for_fav': True, 'title': title, 'url': url, 'icon': icon}
                self.addAudio(params)
            else:
                listId = self.cm.ph.getSearchGroups(item, '''data-list-id=['"]([^'^"]+?)['"]''')[0]
                if 0 == len(self.cacheItems.get(listId, [])):
                    continue
                params = {'good_for_fav': False, 'category': nextCategory, 'title': self.cacheItems[listId][0]['desc'], 'url': listId, 'icon': icon}
                self.addDir(params)
                
    def listCacheItems(self, cItem):
        printDBG('listCacheItems')
        listId = cItem.get('url', '')
        tab = self.cacheItems.get(listId, [])
        
        for item in tab:
            params = dict(cItem)
            params.update(item)
            self.currList.append(params)

    def listVodCats(self, cItem, nextCategory):
        printDBG("EskaGo.listVodCats")
        
        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return
        
        nextCategoriesMap = {'filmy': 'vod_movies_cats', 'seriale': 'vod_sort', 'programy': 'vod_channels'}

        data = ph.find(data, ('<ul', '>', 'categories'), '</ul>')[1]
        data = ph.findall(data, '<li', '</li>')
        for item in data:
            url = ph.search(item, ph.A_HREF_URI_RE)[1]
            if url == '':
                continue
            url = self.cm.getFullUrl(url, self.cm.meta['url'])
            icon = self.cm.getFullUrl(ph.search(item, ph.IMAGE_SRC_URI_RE)[1], self.cm.meta['url'])
            tmp = ph.findall(item, '<span', '</span>')
            title = self.cleanHtmlStr(tmp[-1]) if len(tmp) else self.cleanHtmlStr(item)

            self.addDir(MergeDicts(cItem, {'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'icon': icon}))

    def listVodFilters(self, cItem, nextCategory):
        printDBG("EskaGo.listVodFilters")
        url = cItem['url'].replace('/vod/', '/ajax/vod/')
        sts, data = self.cm.getPage(url)
        if not sts:
            return

        idx = cItem.get('f_idx', 0)

        if idx == 0:
            tmp = ph.find(data, ('<ul', '>', 'cat-box'), ('<div', '>', 'clear'), flags=0)[1].split('</ul>')
            for sData in tmp:
                subItems = []
                sTitle = self.cleanHtmlStr(ph.find(sData, '<span', '</span>')[1])
                if sTitle == '':
                    if len(self.currList):
                        sTitle = self.currList[-1]['title']
                        subItems = self.currList[-1]['sub_items']
                        del self.currList[-1]
                    else:
                        continue

                sData = ph.findall(sData, '<a', '</a>')
                for item in sData:
                    url = self.cm.getFullUrl(ph.search(item, ph.A_HREF_URI_RE)[1], self.cm.meta['url'])
                    icon = self.cm.getFullUrl(ph.search(item, ph.IMAGE_SRC_URI_RE)[1], self.cm.meta['url'])
                    title = self.cleanHtmlStr(item)
                    subItems.append(MergeDicts(cItem, {'url': url, 'title': title, 'icon': icon, 'f_idx': idx + 1}))
                if len(subItems):
                    self.addDir(MergeDicts(cItem, {'category': 'sub_items', 'title': sTitle, 'sub_items': subItems}))
            if len(self.currList) == 1:
                self.currList = self.currList[0]['sub_items']
            if len(self.currList):
                self.currList.insert(0, MergeDicts(cItem, {'title': _('--All--'), 'f_idx': idx + 1}))
            else:
                idx = 1

        if idx == 1:
            sData = ph.find(data, ('<div', '>', 'sort'), '</ul>', flags=0)[1]
            sData = ph.findall(sData, '<a', '</a>')
            for item in sData:
                url = ph.search(item, ph.A_HREF_URI_RE)[1]
                if url == '' or 'javascript' in url:
                    continue
                url = self.cm.getFullUrl(url, self.cm.meta['url'])
                title = self.cleanHtmlStr(item)
                self.addDir(MergeDicts(cItem, {'title': title, 'url': url, 'f_idx': idx + 1}))
        elif idx == 2:
            sData = ph.find(data, ('<div', '>', 'sort'), ('<div', '>', 'clear'), flags=0)[1]
            sData = ph.find(sData, '</ul>', ('<div', '>'), flags=0)[1]
            sData = ph.findall(sData, '<a', '</a>')
            for item in sData:
                url = self.cm.getFullUrl(ph.search(item, ph.A_HREF_URI_RE)[1], self.cm.meta['url'])
                title = self.cleanHtmlStr(item)
                self.addDir(MergeDicts(cItem, {'category': nextCategory, 'title': title, 'url': url}))

    def listVodItems(self, cItem, nextCategory):
        printDBG("EskaGo.listVodItems")
        page = cItem.get('page', 1)
        url = cItem['url'].replace('/vod/', '/ajax/vod/')
        sts, data = self.cm.getPage(url)
        if not sts:
            return

        nextPage = ph.find(data, ('<div', '>', 'pagination'), '</div>', flags=0)[1]
        nextPage = self.cm.getFullUrl(ph.search(nextPage, r'''<a[^>]+?href=(['"])([^>]*?)(?:\1)[^>]*?>%s<''' % (page + 1))[1], self.cm.meta['url'])

        if '/filmy' in url:
            reIcon = re.compile(r'''<img[^>]+?data\-src=(['"])([^>]*?\.(?:jpe?g|png)(?:\?[^\1]*?)?)(?:\1)''', re.I)
            data = ph.findall(data, ('<div', '>', 'tooltip'), '</li>')
            for item in data:
                url = ph.find(item, ('<div', '>', 'box-tv-slide'), '</div>', flags=0)[1]
                url = self.cm.getFullUrl(ph.search(url, ph.A_HREF_URI_RE)[1], self.cm.meta['url'])
                icon = self.cm.getFullUrl(ph.search(item, reIcon)[1], self.cm.meta['url'])
                title = self.cleanHtmlStr(ph.find(item, ('<h', '>'), ('</h', '>'), flags=0)[1])
                desc = []
                desc.append(self.cleanHtmlStr(ph.find(item, ('<span', '>', 'cat-date'), '</span>', flags=0)[1]))
                desc.append(self.cleanHtmlStr(ph.find(item, ('<span', '>', 'cat-time'), '</span>', flags=0)[1]))
                desc = ' | '.join(desc) + '[/br]' + self.cleanHtmlStr(ph.find(item, ('<p', '>', 'opis-view'), '</p>', flags=0)[1])
                self.addDir(MergeDicts(cItem, {'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'icon': icon, 'desc': desc}))
        else:
            data = ph.findall(data, ('<div', '>', 'slider-section'), ('<div', '>', '_slide'), flags=0)
            for item in data:
                url = self.cm.getFullUrl(ph.search(item, ph.A_HREF_URI_RE)[1], self.cm.meta['url'])
                icon = self.cm.getFullUrl(ph.search(item, ph.IMAGE_SRC_URI_RE)[1], self.cm.meta['url'])
                title = self.cleanHtmlStr(ph.find(item, ('<h', '>'), ('</h', '>'), flags=0)[1])
                desc = self.cleanHtmlStr(ph.find(item, '<p', '</p>')[1])
                self.addDir(MergeDicts(cItem, {'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'icon': icon, 'desc': desc}))

        if nextPage:
            self.addDir(MergeDicts(cItem, {'title': _('Next page'), 'url': nextPage, 'page': page + 1}))

    def listVodItem(self, cItem, nextCategory):
        printDBG("EskaGo.listVodItem")
        url = cItem['url']
        if '/vod/' in url:
            type = 'vod'
            url = url.replace('/vod/', '/ajax/vod/')
        else:
            type = 'serial'
            url = url.replace('/serial/', '/ajax/serial/').replace('/program/', '/ajax/program/')

        sts, data = self.cm.getPage(url)
        if not sts:
            return

        desc = self.cleanHtmlStr(ph.find(data, ('<div', '>', 'text-desc'), '</div>', flags=0)[1])
        icon = ph.find(data, ('<div', '>', 'bg-film'), '</div>', flags=0)[1]
        icon = self.cm.getFullUrl(ph.search(icon, ph.IMAGE_SRC_URI_RE)[1], self.cm.meta['url'])
        if not icon:
            icon = cItem.get('icon', '')

        if type != 'vod':
            tmp = ph.find(data, ('<div', '>', 'seasons'), ('<div', '>', 'clear'), flags=0)[1]
            tmp = ph.findall(tmp, '<a', '</a>')
            for item in tmp:
                url = self.cm.getFullUrl(ph.search(item, ph.A_HREF_URI_RE)[1], self.cm.meta['url'])
                title = self.cleanHtmlStr(item)
                if not title:
                    continue
                self.addDir(MergeDicts(cItem, {'good_for_fav': True, 'category': nextCategory, 'title': title, 's_title': '%s: %s,' % (cItem['title'], title), 'url': url, 'icon': icon, 'desc': desc}))

            if len(self.currList) == 0:
                cItem = MergeDicts(cItem, {'s_title': '%s: ' % cItem['title']})
                self.listVodEpisodes(cItem, data)
        else:
            tmp = ph.find(data, ('<div', '>', 'layer-vod'), '</script>', flags=0)[1]
            if tmp:
                self.addVideo(MergeDicts(cItem, {'good_for_fav': True, 'icon': icon, 'desc': desc}))

        trailer = ph.find(data, ('<a', '>', 'trailer'), '</a>')[1]
        trailer = self.cm.getFullUrl(ph.search(trailer, ph.A_HREF_URI_RE)[1], self.cm.meta['url'])
        if trailer:
            self.addVideo(MergeDicts(cItem, {'good_for_fav': True, 'title': _('%s - trailer') % (cItem['title']), 'url': trailer, 'icon': icon, 'desc': desc, 'is_trailer': True}))

    def listVodEpisodes(self, cItem, data=None):
        printDBG("EskaGo.listVodEpisodes")
        if not data: 
            url = cItem['url'].replace('/serial/', '/ajax/serial/')
            sts, data = self.cm.getPage(url)
            if not sts:
                return

        sTitle = cItem['s_title']
        data = ph.findall(data, ('<div', '>', 'box-movie-small'), '</div>', flags=0)
        for item in data:
            url = self.cm.getFullUrl(ph.search(item, ph.A_HREF_URI_RE)[1], self.cm.meta['url'])
            icon = self.cm.getFullUrl(ph.search(item, ph.IMAGE_SRC_URI_RE)[1], self.cm.meta['url'])
            title = self.cleanHtmlStr(ph.find(item, ('<strong', '>'), '</strong>', flags=0)[1])
            self.addVideo({'good_for_fav': True, 'title': '%s %s' % (sTitle, title), 'url': url, 'icon': icon})

    def listRadioEskaPL(self, cItem):
        printDBG("EskaGo.listRadioEskaPL")
        
        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return
        
        data = self.cm.ph.getDataBeetwenMarkers(data, 'var radioConfig = ', '</script>', False)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '"stream": ', '},', False)
        for item in data:
#            printDBG("EskaGo.listRadioEskaPL item [%s]" % item)
            tmp = json_loads(item + '}')
            title = tmp['name']
            url = tmp['stream_url']
            if url == '':
                continue
            desc = ''
            params = {'good_for_fav': True, 'title': title, 'url': url, 'desc': desc, 'is_trailer': True}
            self.addAudio(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("EskaGo.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        
        # TODO: implement me
    
    def getLinksForItem(self, cItem):
        printDBG("EskaGo.getLinksForItem [%s]" % cItem)
        urlTab = []

        url = cItem['url']

        if cItem.get('is_trailer'):
            urlTab = getDirectM3U8Playlist(strwithmeta(url, {'iptv_proto': 'm3u8'}), checkExt=True, checkContent=True, sortWithMaxBitrate=999999999)
            for item in urlTab:
                item['url'] = strwithmeta(item['url'], {'iptv_proto': 'm3u8'})
            return urlTab

        if '/vod/' in url:
            sts, data = self.cm.getPage(url, self.defaultParams)
            if not sts:
                return []
            data = ph.find(data, ('<div', '>', 'layer-vod'), '</script>', flags=0)[1]
            hls = self.cm.getFullUrl(ph.search(data, r'''var\s+?hls\s*?=\s*?(['"])([^>]*?)(?:\1)''')[1], self.cm.meta['url'])
            mp4 = self.cm.getFullUrl(ph.search(data, r'''var\s+?mp4\s*?=\s*?(['"])([^>]*?)(?:\1)''')[1], self.cm.meta['url'])
            urlTab = getDirectM3U8Playlist(hls, checkExt=True, checkContent=True, sortWithMaxBitrate=999999999)
            for item in urlTab:
                item['url'] = strwithmeta(item['url'], {'iptv_proto': 'm3u8'})
            if mp4 != '':
                urlTab.append({'name': 'mp4', 'url': mp4, 'need_resolve': 0})
            return urlTab

        if self.up.getDomain(self.MAIN_ESKAPL_URL, onlyDomain=True) in url:
            sts, data = self.cm.getPage(url, self.defaultParams)
            if not sts:
                return []
            data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="play_player">', '</div>')[1]
            url = self.cm.ph.getSearchGroups(data, '''href=['"]([^'^"]+?)['"]''')[0]
            if not self.cm.isValidUrl(url):
                return []

        sts, data = self.cm.getPage(url)
        if not sts:
            data = ''

        if '/radio/' in url:
            tmp = self.cm.ph.getDataBeetwenMarkers(data, 'input[name="data-radio-url"]', ';', withMarkers=False)[1]
            url = self.cm.ph.getSearchGroups(tmp, '''(https?://[^'^"]+?)['"]''')[0]
            if url != '' and url.endswith('.pls'):
                sts, tmp = self.cm.getPage(url)
                if not sts:
                    return []
                printDBG(tmp)
                tmp = tmp.split('File')
                if len(tmp):
                    del tmp[0]
                for item in tmp:
                    printDBG('ITEM [%s]' % item)
                    url = self.cm.ph.getSearchGroups(item, '''(https?://[^\s]+?)\s''')[0]
                    name = self.cm.ph.getSearchGroups(item, '''Title[^=]*?=([^\s]+?)\s''')[0].strip()
                    urlTab.append({'name': name, 'url': url})
            else:
                tmp1 = self.cm.ph.getAllItemsBeetwenMarkers(data, '<script', '</script>')
                for tmp in tmp1:
                    tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '{', '}')
                    for item in tmp:
                        if 'streamUrl' in item:
                            streamUrl = self.cm.ph.getSearchGroups(item, '''streamUrl\s*=\s*['"](https?://[^'^"]+?)['"]''')[0]
                            streamType = self.cm.ph.getSearchGroups(item, '''streamType\s*=\s*['"]([^'^"]+?)['"]''')[0]
                            if 'aac' in streamType:
                                streamUrl = streamUrl.replace('.mp3', '.aac')
                            elif 'mp3' in streamType:
                                streamUrl = streamUrl.replace('.aac', '.mp3')
                            streamUrl = streamUrl + self.cm.ph.getSearchGroups(data, '''value\s*=\s*['"](timestamp[^'^"]+?)['"]''')[0]
                            urlTab.append({'name': streamType, 'url': streamUrl})
            if len(urlTab) == 0:
                tmp = self.cm.ph.getAllItemsBeetwenMarkers(data, '<source', '>', False, False)
                for item in tmp:
                    if 'video/mp4' in item:
                        url = self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''')[0]
                        urlTab.append({'name': self.up.getDomain(url), 'url': url})

        return urlTab

    def getVideoLinks(self, videoUrl):
        printDBG("EskaGo.getVideoLinks [%s]" % videoUrl)
        urlTab = []
        
        if self.cm.isValidUrl(videoUrl):
            urlTab = self.up.getVideoLinkExt(videoUrl)
        
        return urlTab

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')
        
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')
        
        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []
        
    #MAIN MENU
        if name == None:
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})

        elif 'list_vod_casts' == category:
            self.listVodCats(self.currItem, 'vod_list_filters')

        elif 'vod_list_filters' == category:
            self.listVodFilters(self.currItem, 'vod_list_items')

        elif 'sub_items' == category:
            self.listSubItems(self.currItem)

        elif 'vod_list_items' == category:
            self.listVodItems(self.currItem, 'vod_item')

        elif 'vod_item' == category:
            self.listVodItem(self.currItem, 'vod_episodes')

        elif 'vod_episodes' == category:
            self.listVodEpisodes(self.currItem)

        elif 'list_radio_cats' == category:
            self.listRadioCats(self.currItem, 'list_cache_items')
        elif 'list_cache_items' == category:
            self.listCacheItems(self.currItem)
        elif 'list_radio_eskapl' == category:
            self.listRadioEskaPL(self.currItem)
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
        CHostBase.__init__(self, EskaGo(), True, [])


