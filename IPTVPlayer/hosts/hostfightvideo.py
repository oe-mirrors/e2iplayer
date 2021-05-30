# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify
###################################################

###################################################
# FOREIGN import
###################################################
import urlparse
import re
import urllib
try:
    import json
except Exception:
    import simplejson as json
###################################################


def gettytul():
    return 'http://fight.mmashare.club/'


class FightVideo(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'paczamy.pl', 'cookie': 'fightvideommatd.cookie'})
        self.DEFAULT_ICON_URL = 'http://fight.mmashare.club/images/big-mmashare.png'
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})
        self.MAIN_URL = 'http://fight.mmashare.club/'
        self.cacheLinks = {}
        self.cacheFilters = {}
        self.cacheFiltersKeys = []
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)

        def _getFullUrl(url):
            if self.cm.isValidUrl(url):
                return url
            else:
                return urlparse.urljoin(baseUrl, url)

        addParams['cloudflare_params'] = {'domain': self.up.getDomain(baseUrl), 'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT, 'full_url_handle': _getFullUrl}
        sts, data = self.cm.getPageCFProtection(baseUrl, addParams, post_data)
        return sts, data

    def fillCacheFilters(self, cItem):
        printDBG("FightVideo.listCategories")
        self.cacheFilters = {}
        self.cacheFiltersKeys = []

        url = self.getFullUrl('viewforum.php?f=35')
        sts, data = self.getPage(url)
        if not sts:
            return

        def addFilter(data, marker, baseKey, addAll=True, titleBase=''):
            key = 'f_' + baseKey
            self.cacheFilters[key] = []
            for item in data:
                value = self.cm.ph.getSearchGroups(item, marker + '''="([^"]+?)"''')[0]
                if value == '':
                    continue
                title = self.cleanHtmlStr(item)
                self.cacheFilters[key].append({'title': title.title(), key: value})

            if len(self.cacheFilters[key]):
                if addAll:
                    self.cacheFilters[key].insert(0, {'title': _('All')})
                self.cacheFiltersKeys.append(key)

        # Display topics from previous
        tmp = self.cm.ph.getDataBeetwenMarkers(data, 'Display topics', '</select>')[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<option', '</option>')
        addFilter(tmp, 'value', 'st', False)

        # Sort by
        tmp = self.cm.ph.getDataBeetwenMarkers(data, 'Sort by', '</select>')[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<option', '</option>')
        addFilter(tmp, 'value', 'sk', False)

        # order
        sortByTab = []
        for desc in [True, False]:
            for item in self.cacheFilters['f_sk']:
                params = dict(item)

                if desc:
                    title = '\xe2\x86\x93 '
                    value = 'd'
                else:
                    title = '\xe2\x86\x91 '
                    value = 'a'
                params.update({'title': title + ' ' + item['title'], 'f_sd': value})
                sortByTab.append(params)
        self.cacheFilters['f_sk'] = sortByTab
        printDBG(self.cacheFilters)
        printDBG(self.cacheFiltersKeys)

    def listFilters(self, cItem, nextCategory):
        printDBG("FightVideo.listFilters")
        cItem = dict(cItem)

        f_idx = cItem.get('f_idx', 0)
        if f_idx == 0:
            self.fillCacheFilters(cItem)

        if 0 == len(self.cacheFiltersKeys):
            return

        filter = self.cacheFiltersKeys[f_idx]
        f_idx += 1
        cItem['f_idx'] = f_idx
        if f_idx == len(self.cacheFiltersKeys):
            cItem['category'] = nextCategory
        self.listsTab(self.cacheFilters.get(filter, []), cItem)

    def listItems(self, cItem, nextCategory):
        printDBG("FightVideo.listItems")
        perPage = 50
        page = cItem.get('page', 1)
        url = 'viewforum.php?f=35'

        query = {}
        if page > 1:
            query['start'] = page * perPage

        keys = list(self.cacheFiltersKeys)
        keys.append('f_sd')
        for key in self.cacheFiltersKeys:
            baseKey = key[2:] # "f_"
            if key in cItem:
                query[baseKey] = urllib.quote(cItem[key])

        query = urllib.urlencode(query)
        if '?' in url:
            url += '&' + query
        else:
            url += '?' + query

        sts, data = self.getPage(self.getFullUrl(url))
        if not sts:
            return

        if '<li class="next"><a' in data:
            nextPage = True
        else:
            nextPage = False

        data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="list-inner">Topics</div>', '<form', False)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li class="row', '</dl>')
        for item in data:
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(item, '<dd', '</dd>')
            descTab = []
            for dItem in tmp:
                dItem = self.cleanHtmlStr(dItem)
                if '' != dItem:
                    descTab.append(dItem)

            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0]).replace('&amp;', '&')
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<a ', '</a>')[1])

            params = dict(cItem)
            params = {'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'desc': '[/br]'.join(descTab)}
            self.addDir(params)

        if nextPage and len(self.currList) > 0:
            params = dict(cItem)
            params.update({'title': _("Next page"), 'page': page + 1})
            self.addDir(params)

    def exploreItem(self, cItem):
        printDBG("FightVideo.exploreItem [%s]" % cItem)
        page = cItem.get('page', 0)
        allUrls = []
        url = cItem['url']
        if page > 0:
            url += '&start=%s' % (page * 14)

        sts, data = self.getPage(url)
        if not sts:
            return []

        if self.cm.ph.getSearchGroups(data, '''[&;]start=(%s)[^0-9]''' % ((page + 1) * 14))[0] != '':
            nextPage = True
        else:
            nextPage = False

        idx = cItem.get('video_idx', 1)
        data1 = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="content">', '<div class="back2top">')
        for item1 in data1:
            tmp = self.cm.ph.getDataBeetwenMarkers(item1, '<a', '</a>')[1]
            mTitle = self.cleanHtmlStr(tmp)

            printDBG(">>>>>>>>>>>>>>>>>>>>>>>>>> VIDEO [%s]" % mTitle.upper())

            if 'VIDEO' == mTitle.upper().strip():
                url = self.cm.ph.getSearchGroups(tmp, 'href="(https?://[^"]+?)"')[0].replace('&amp;', '&')
                sts, data = self.getPage(url)
                if not sts:
                    break
                tmp = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="content">', '<div class="back2top">')
                tItems = []
                for item in tmp:
                    tItems = self.cm.ph.getAllItemsBeetwenMarkers(item, '<strong', '</table>')
                    if 0 == len(tItems):
                        tItems.extend(self.cm.ph.getAllItemsBeetwenMarkers(item, '<table', '</table>'))
                tItems.extend(self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="postbody"', '</div>'))
                for tItem in tItems:
                    title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(tItem, '<strong', '</strong>')[1])
                    if title == '':
                        title = self.cleanHtmlStr(tItem)
                    directUrl = True
                    url = self.cm.ph.getSearchGroups(tItem, '<source[^>]+?src="(https?://[^"]+?)"[^>]*?type="video')[0]
                    url = url.replace(' ', '%20')
                    if url == '':
                        url = self.getFullUrl(self.cm.ph.getSearchGroups(tItem, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0])
                        directUrl = False
                    if url not in allUrls and self.cm.isValidUrl(url) and (directUrl or 1 == self.up.checkHostSupport(url)):
                        allUrls.append(url)
                        if title == '':
                            title = 'Video %d - %s' % (idx, self.up.getDomain(url))
                        params = {'title': title, 'url': url, 'direct_url': directUrl}
                        self.addVideo(params)
                        idx += 1
            else:
                tmpVideos = re.compile('''['"](https?://video\[^'^"]+?\.mp4)['"]''').findall(item1)
                for url in tmpVideos:
                    url = url.replace(' ', '%20')
                    if url not in allUrls and self.cm.isValidUrl(url):
                        allUrls.append(url)
                        title = 'Video %d - %s' % (idx, self.up.getDomain(url))
                        params = {'title': title, 'url': url, 'direct_url': True}
                        self.addVideo(params)
                        idx += 1

                tmpVideos = re.compile('''<iframe[^>]+?src=['"]([^"^']+?)['"]''').findall(item1)
                tmpVideos.extend(re.compile('''data\-url=['"](https?://[^'^"]+?)['"]''').findall(item1))
                for url in tmpVideos:
                    if url not in allUrls and self.cm.isValidUrl(url) and 1 == self.up.checkHostSupport(url):
                        allUrls.append(url)
                        title = 'Video %d - %s' % (idx, self.up.getDomain(url))
                        params = {'title': title, 'url': url, 'direct_url': False}
                        self.addVideo(params)
                        idx += 1

        if nextPage:
            params = dict(cItem)
            params.update({'title': _("Next page"), 'video_idx': idx, 'page': page + 1})
            self.addDir(params)

    def getLinksForVideo(self, cItem):
        printDBG("FightVideo.getLinksForVideo [%s]" % cItem)
        urlTab = []

        if cItem['direct_url']:
            urlTab.append({'name': 'direct', 'url': cItem['url'], 'need_resolve': 0})
        else:
            urlTab = self.up.getVideoLinkExt(cItem['url'])

        return urlTab

    def getFavouriteData(self, cItem):
        printDBG('FightVideo.getFavouriteData')
        return json.dumps(cItem)

    def getLinksForFavourite(self, fav_data):
        printDBG('FightVideo.getLinksForFavourite')
        if self.MAIN_URL == None:
            self.selectDomain()
        links = []
        try:
            cItem = byteify(json.loads(fav_data))
            links = self.getLinksForVideo(cItem)
        except Exception:
            printExc()
        return links

    def setInitListFromFavouriteItem(self, fav_data):
        printDBG('FightVideo.setInitListFromFavouriteItem')
        if self.MAIN_URL == None:
            self.selectDomain()
        try:
            params = byteify(json.loads(fav_data))
        except Exception:
            params = {}
            printExc()
        self.addDir(params)
        return True

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
            cItem = dict(self.currItem)
            cItem['category'] = 'list_filters'
            self.listFilters(cItem, 'list_items')
        if category == 'list_filters':
            self.listFilters(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem, 'explore_item')

        elif category == 'explore_item':
            self.exploreItem(self.currItem)

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, FightVideo(), False, [])
