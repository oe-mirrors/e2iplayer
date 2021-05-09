# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from binascii import a2b_hex, a2b_base64
from hashlib import md5
from Plugins.Extensions.IPTVPlayer.libs.crypto.cipher.aes_cbc import AES_CBC
from Plugins.Extensions.IPTVPlayer.libs.crypto.keyedHash.evp import EVP_BytesToKey
###################################################

###################################################
# FOREIGN import
###################################################
import urllib
try:
    import json
except Exception:
    import simplejson as json
###################################################


def gettytul():
    return 'https://anime-odcinki.pl/'


class AnimeOdcinkiPL(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'AnimeOdcinki.pl', 'cookie': 'animeodcinkipl.cookie'})

        self.HEADER = {'User-Agent': 'Mozilla/5.0', 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.MAIN_URL = 'https://anime-odcinki.pl/'
        self.DEFAULT_ICON_URL = 'https://anime-odcinki.pl/wp-content/uploads/2017/07/A-O_logo.png'

        self.MAIN_CAT_TAB = [{'category': 'new', 'title': _('New'), 'url': self.MAIN_URL},
                             {'category': 'list_emitowane', 'title': 'Emitowane', 'url': self.MAIN_URL},
                             {'category': 'list_abc', 'title': _('Anime list'), 'url': self.getFullUrl('anime')},
                             {'category': 'list_abc', 'title': _('Movies list'), 'url': self.getFullUrl('filmy')},
                             {'category': 'list_filters', 'title': _('Genres'), 'url': self.getFullUrl('gatunki')},
                             {'category': 'search', 'title': _('Search'), 'search_item': True, },
                             {'category': 'search_history', 'title': _('Search history'), }
                            ]

        self.NEW_CAT_TAB = [{'category': 'list_new', 'title': 'Nowe odcinki emitowane', 'm1': '>Nowe'},
                            {'category': 'list_new', 'title': 'Ostatnio dodane odcinki z poprzednich sezonów', 'm1': '>Ostatnio'}]

        self.filtersTab = []
        self.cacheFilters = {}

        self.cacheItems = {}

        self.cacheLinks = {}

    @staticmethod
    def resolveIconUrl(cm, url):
        sts, data = cm.getPage(url)
        if not sts:
            return ''
        data = cm.ph.getDataBeetwenMarkers(data, 'okladka', '</div>')[1]
        return cm.ph.getSearchGroups(data, '''src=['"]([^'^"]+?)['"]''')[0]

    def getStr(self, item, key):
        if key not in item:
            return ''
        if item[key] == None:
            return ''
        return str(item[key])

    def fillFilters(self, cItem):
        self.filtersTab = []
        self.cacheFilters = {}
        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="search-category-checkbox checkbox">', '</div>')
        for item in data:
            title = self.cleanHtmlStr(item)
            key = self.cm.ph.getSearchGroups(item, '''name=['"]([^'^"]+?)['"]''')[0]
            value = self.cm.ph.getSearchGroups(item, '''value=['"]([^'^"]+?)['"]''')[0]
            if key not in self.cacheFilters:
                self.cacheFilters[key] = [{'title': _('All')}]
                self.filtersTab.append(key)
            self.cacheFilters[key].append({'title': title, 'f_' + key: value})

    def listFilter(self, cItem, filters):
        params = dict(cItem)
        idx = params.get('f_idx', 0)
        params['f_idx'] = idx + 1

        tab = self.cacheFilters.get(filters[idx], [])
        self.listsTab(tab, params)

    def fillItemsCache(self, cItem):
        baseUrl = cItem['url']

        self.cacheItems[baseUrl] = {'items': [], 'letters': []}
        sts, data = self.cm.getPage(baseUrl)
        if not sts:
            return

        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<div id="letter-index"', '</td>')[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<a', '</span>')
        for item in tmp:
            letter = self.cm.ph.getSearchGroups(item, '''data-index=['"]([^'^"]+?)['"]''')[0]
            title = self.cleanHtmlStr(item.replace('|', ''))
            self.cacheItems[baseUrl]['letters'].append({'title': title, 'letter': letter})

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<tr class="list-item" data-fl=', '</td>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(item)
            letter = self.cm.ph.getSearchGroups(item, '''data-fl=['"]([^'^"]+?)['"]''')[0]
            self.cacheItems[baseUrl]['items'].append({'title': title, 'url': url, 'letter': letter})

    def listABC(self, cItem, nextCategory):
        printDBG("AnimeOdcinkiPL.listABC")
        baseUrl = cItem['url']

        cacheItem = self.cacheItems.get(baseUrl, {})
        itemsTab = cacheItem.get('letters', [])
        if 0 == len(itemsTab):
            self.fillItemsCache(cItem)

        for item in self.cacheItems[baseUrl]['letters']:
            letter = item['letter']
            title = item['title']
            params = dict(cItem)
            params.update({'category': nextCategory, 'title': title, 'f_abc': letter})
            self.addDir(params)

    def listItems(self, cItem, nextCategory):
        printDBG("AnimeOdcinkiPL.listItems")
        letter = cItem.get('f_abc', '')
        baseUrl = cItem['url']

        cacheItem = self.cacheItems.get(baseUrl, {})
        itemsTab = cacheItem.get('items', [])
        if 0 == len(itemsTab):
            self.fillItemsCache(cItem)

        for item in self.cacheItems[baseUrl]['items']:
            if letter != '' and letter != item['letter']:
                continue
            url = item['url']
            title = item['title']
            icon = strwithmeta(url, {'icon_resolver': AnimeOdcinkiPL.resolveIconUrl})
            params = {'good_for_fav': True, 'title': title, 'url': url, 'icon': icon}
            params['category'] = nextCategory
            self.addDir(params)

    def listBase(self, cItem, nextCategory, m1, m2, sp1, sp2):
        printDBG("AnimeOdcinkiPL.listEmitowane")

        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenMarkers(data, m1, m2)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, sp1, sp2)
        for item in data:
            title = self.cleanHtmlStr(item)
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            if not self.cm.isValidUrl(url):
                continue
            #icon   = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0])
            #if icon == '': icon   = strwithmeta(url, {'icon_resolver':AnimeOdcinkiPL.resolveIconUrl})
            params = {'good_for_fav': True, 'title': title, 'url': url}
            if nextCategory != 'video':
                icon = strwithmeta(url, {'icon_resolver': AnimeOdcinkiPL.resolveIconUrl})
                params.update({'category': nextCategory, 'icon': icon})
                self.addDir(params)
            else:
                icon = strwithmeta(url[:url.rfind('/')], {'icon_resolver': AnimeOdcinkiPL.resolveIconUrl})
                params.update({'category': nextCategory, 'icon': icon})
                self.addVideo(params)

    def listSearchItems(self, cItem, nextCategory):
        printDBG("AnimeOdcinkiPL.listSearchItems")
        page = cItem.get('page', 1)

        getParams = []
        for key in self.filtersTab:
            iKey = 'f_' + key
            if iKey in cItem:
                getParams.append('%s=%s' % (urllib.quote(key), urllib.quote(cItem[iKey])))

        if 'f_search' in cItem:
            getParams.append('s=%s' % (urllib.quote_plus(cItem['f_search'])))

        baseUrl = cItem['url']
        if page > 1:
            baseUrl += '/strona/%s' % page
        baseUrl += '?' + '&'.join(getParams)

        sts, data = self.cm.getPage(baseUrl)
        if not sts:
            return

        if '>»<' in data:
            nextPage = True
        else:
            nextPage = False

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li class="search-result">', '</li>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h3', '</h3>')[1])
            icon = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0])
            desc = self.cleanHtmlStr(item.split('</h3>')[-1])
            if icon == '':
                icon = strwithmeta(url, {'icon_resolver': AnimeOdcinkiPL.resolveIconUrl})
            params = {'good_for_fav': True, 'title': title, 'url': url, 'icon': icon, 'desc': desc}
            try:
                episodeNum = int(url.split('/')[-1])
                self.addVideo(params)
            except:
                params['category'] = nextCategory
                self.addDir(params)

        if nextPage:
            params = dict(cItem)
            params.pop('good_for_fav', None)
            params.update({'title': _('Next page'), 'page': page + 1})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("AnimeOdcinkiPL.listEpisodes")

        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return

        desc = self.cm.ph.getDataBeetwenMarkers(data, 'summary', '</div>')[1]
        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(desc, '<div', '</div>')[1])

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li class="lista_odc', '</li>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'good_for_fav': True, 'title': title, 'url': url, 'desc': desc})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("AnimeOdcinkiPL.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.MAIN_URL
        cItem['f_search'] = searchPattern
        self.listSearchItems(cItem, 'list_episodes')

    def _encryptPlayerUrl(self, data):
        printDBG("_encryptPlayerUrl data[%s]" % data)
        decrypted = ''
        try:
            salt = a2b_hex(data["v"])
            key, iv = EVP_BytesToKey(md5, "s05z9Gpd=syG^7{", salt, 32, 16, 1)

            if iv != a2b_hex(data.get('b', '')):
                prinDBG("_encryptPlayerUrl IV mismatched")

            if 0:
                from Crypto.Cipher import AES
                aes = AES.new(key, AES.MODE_CBC, iv, segment_size=128)
                decrypted = aes.decrypt(a2b_base64(data["a"]))
                decrypted = decrypted[0:-ord(decrypted[-1])]
            else:
                kSize = len(key)
                alg = AES_CBC(key, keySize=kSize)
                decrypted = alg.decrypt(a2b_base64(data["a"]), iv=iv)
                decrypted = decrypted.split('\x00')[0]
            decrypted = "%s" % json.loads(decrypted).encode('utf-8')
        except Exception:
            printExc()
            decrypted = ''
        return decrypted

    def getLinksForVideo(self, cItem):
        printDBG("AnimeOdcinkiPL.getLinksForVideo [%s]" % cItem)
        urlTab = []

        urlTab = self.cacheLinks.get(cItem['url'], [])
        if len(urlTab):
            return urlTab

        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return []

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="video-player-mode"', '</div>')
        for item in data:
            url = self.cm.ph.getSearchGroups(item, "data-hash='([^']+?)'")[0]
            if url == '':
                url = self.cm.ph.getSearchGroups(item, 'data-hash="([^"]+?)"')[0]
            try:
                tmp = json.loads(url)
                url = self._encryptPlayerUrl(tmp)
            except Exception:
                continue
            if not self.cm.isValidUrl(url):
                continue
            name = self.cleanHtmlStr(item)
            urlTab.append({'name': name, 'url': strwithmeta(url, {'Referer': cItem['url']}), 'need_resolve': 1})

        self.cacheLinks[cItem['url']] = urlTab
        return urlTab

    def getVideoLinks(self, videoUrl):
        printDBG("AnimeOdcinkiPL.getVideoLinks [%s]" % videoUrl)
        urlTab = []

        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            key = self.cacheLinks.keys()[0]
            for idx in range(len(self.cacheLinks[key])):
                if videoUrl in self.cacheLinks[key][idx]['url']:
                    if not self.cacheLinks[key][idx]['name'].startswith('*'):
                        self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name']
                    break

        if 1 != self.up.checkHostSupport(videoUrl):
            paramsUrl = dict(self.defaultParams)
            paramsUrl['header'] = dict(paramsUrl['header'])
            paramsUrl['header']['Referer'] = strwithmeta(videoUrl).meta.get('Referer', self.getMainUrl())
            sts, data = self.cm.getPage(videoUrl, paramsUrl)
            if not sts:
                return []
            videoUrl = self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0].replace('&amp;', '&')

        if self.cm.isValidUrl(videoUrl):
            return self.up.getVideoLinkExt(videoUrl)

        return urlTab

    def getArticleContent(self, cItem):
        printDBG("SolarMovie.getArticleContent [%s]" % cItem)
        retTab = []

        title = cItem.get('title', '')
        desc = cItem.get('desc', '')
        icon = self.resolveIconUrl(self.cm, cItem.get('icon', ''))
        if icon == '':
            icon = self.getDefaulIcon()

        return [{'title': title, 'text': desc, 'images': [{'title': '', 'url': self.getFullUrl(icon)}], 'other_info': {}}]

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
        elif category == 'new':
            self.listsTab(self.NEW_CAT_TAB, self.currItem)
        elif 'list_new' == category:
            cItem = dict(self.currItem)
            cItem.pop('m1', None)
            self.listBase(cItem, 'video', self.currItem['m1'], '<div id="issued-ep-nav">', '<div class="owl', '</div>')
        elif 'list_emitowane' == category:
            self.listBase(self.currItem, 'list_episodes', '>Emitowane</h2>', '</ul>', '<li', '</li>')
        elif 'list_abc' == category:
            self.listABC(self.currItem, 'list_items')
        elif 'list_items' == category:
            self.listItems(self.currItem, 'list_episodes')
        elif 'list_filters' == category:
            idx = self.currItem.get('f_idx', 0)
            if idx == 0:
                self.fillFilters(self.currItem)
            if idx < len(self.filtersTab):
                self.listFilter(self.currItem, self.filtersTab)
            else:
                hasFilter = False
                for filter in self.filtersTab:
                    filter = 'f_' + filter
                    if filter in self.currItem:
                        hasFilter = True
                        break
                if hasFilter:
                    self.listSearchItems(self.currItem, 'list_episodes')
                else:
                    cItem = dict(self.currItem)
                    cItem['url'] = self.getFullUrl('anime')
                    self.listItems(cItem, 'list_episodes')

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
        CHostBase.__init__(self, AnimeOdcinkiPL(), True, [])

    def withArticleContent(self, cItem):
        return True
