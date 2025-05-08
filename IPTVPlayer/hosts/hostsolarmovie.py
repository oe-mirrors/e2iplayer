# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetPluginDir, byteify, rm, MergeDicts
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.crypto.cipher.aes_cbc import AES_CBC
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_urlencode, urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_binary
###################################################
# FOREIGN import
###################################################
import base64
from binascii import unhexlify
from hashlib import md5
try:
    import json
except Exception:
    import simplejson as json
from Components.config import config, ConfigSelection, ConfigText, getConfigListEntry
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.solarmovie_proxy = ConfigSelection(default="None", choices=[("None", _("None")),
                                                                                         ("proxy_1", _("Alternative proxy server (1)")),
                                                                                         ("proxy_2", _("Alternative proxy server (2)"))])
config.plugins.iptvplayer.solarmovie_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.solarmovie_proxy))
    optionList.append(getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.solarmovie_alt_domain))
    return optionList
###################################################


def gettytul():
    return 'https://solarmoviex.to/'


class SolarMovie(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'SolarMovie.tv', 'cookie': 'solarmovie.cookie'})
        self.USER_AGENT = self.cm.getDefaultHeader()['User-Agent']
        self.HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})

        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.DEFAULT_ICON_URL = 'http://www.top-site-list.com/topsites/wp-content/uploads/2013/10/421.png' #'https://solarmovie.st/assets/movie/frontend/images/logo.png'
        self.MAIN_URL = None
        self.cacheFiltersKeys = []
        self.cacheFilters = {}
        self.cacheLinks = {}
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self._myFun = None

    def getProxy(self):
        proxy = config.plugins.iptvplayer.solarmovie_proxy.value
        if proxy != 'None':
            if proxy == 'proxy_1':
                proxy = config.plugins.iptvplayer.alternative_proxy1.value
            else:
                proxy = config.plugins.iptvplayer.alternative_proxy2.value
        else:
            proxy = None
        return proxy

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        proxy = self.getProxy()
        if proxy != None:
            addParams = MergeDicts(addParams, {'http_proxy': proxy})
        addParams['cloudflare_params'] = {'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def getFullIconUrl(self, url):
        m1 = 'amp;url='
        if m1 in url:
            url = url.split(m1)[-1]
        url = self.getFullUrl(url)
        if url == '':
            return url
        proxy = self.getProxy()
        if proxy != None:
            url = strwithmeta(url, {'iptv_http_proxy': proxy})
        cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE, ['PHPSESSID', 'cf_clearance', '__cfduid'])
        url = strwithmeta(url, {'Cookie': cookieHeader, 'User-Agent': self.HEADER['User-Agent']})
        return url

    def selectDomain(self):
        printDBG("SolarMovie.selectDomain")
        domains = ['https://solarmoviex.to/']
        domain = config.plugins.iptvplayer.solarmovie_alt_domain.value.strip()
        if self.cm.isValidUrl(domain):
            if domain[-1] != '/':
                domain += '/'
            domains.insert(0, domain)

        urlParams = dict(self.defaultParams)
        urlParams['with_metadata'] = True
        for domain in domains:
            for i in range(2):
                sts, data = self.getPage(domain, urlParams)
                if sts:
                    if 'genre/action' in data:
                        self.MAIN_URL = data.meta.get('url')
                        printDBG(">> meta[%s]" % data.meta)
                        break
                    else:
                        continue
                break

            if self.MAIN_URL != None:
                break

        if self.MAIN_URL == None:
            self.MAIN_URL = domains[0]

        self.MAIN_CAT_TAB = [{'category': 'list_items', 'title': 'Featured movies', 'url': self.MAIN_URL + 'featured'},
                             {'category': 'list_filters', 'title': 'Movies', 'url': self.MAIN_URL + 'filter', 'f_type[]': 'movie'},
                             {'category': 'list_filters', 'title': 'TV-Series', 'url': self.MAIN_URL + 'filter', 'f_type[]': 'series'},

                             {'category': 'search', 'title': _('Search'), 'search_item': True, },
                             {'category': 'search_history', 'title': _('Search history'), }
                            ]

    def fillCacheFilters(self, cItem):
        printDBG("SolarMovie.listCategories")
        self.cacheFilters = {}
        self.cacheFiltersKeys = []

        sts, data = self.getPage(self.getFullUrl('/movies'))
        if not sts:
            return

        def addFilter(data, marker, baseKey, addAll=True, titleBase=''):
            key = 'f_' + baseKey
            self.cacheFilters[key] = []
            for item in data:
                if ('name="%s"' % baseKey) not in item:
                    continue
                value = self.cm.ph.getSearchGroups(item, marker + '''="([^"]+?)"''')[0]
                if value == '':
                    continue
                title = self.cleanHtmlStr(item)
                if title.lower() in ['all', 'default', 'any']:
                    addAll = False
                    self.cacheFilters[key].append({'title': titleBase + title.title()})
                else:
                    self.cacheFilters[key].append({'title': titleBase + title.title(), key: value})

            if len(self.cacheFilters[key]):
                if addAll:
                    self.cacheFilters[key].insert(0, {'title': _('All')})
                self.cacheFiltersKeys.append(key)

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="filter dropdown">', '</ul>')
        for tmp in data:
            titleBase = self.cleanHtmlStr(self.cm.ph.getSearchGroups(tmp, '''<button[^>]+?>([^<]+?)<''')[0])
            if titleBase.lower() in ['type']:
                continue
            if titleBase.lower() not in ['subtitle']:
                titleBase = ''
            else:
                titleBase += ': '
            key = self.cm.ph.getSearchGroups(tmp, '''name="([^"]+?)"''')[0]
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li', '</li>')
            addFilter(tmp, 'value', key, True, titleBase)

        printDBG(self.cacheFilters)

    def listFilters(self, cItem, nextCategory):
        printDBG("SolarMovie.listFilters")
        cItem = dict(cItem)

        f_idx = cItem.get('f_idx', 0)
        if f_idx == 0:
            self.fillCacheFilters(cItem)

        if f_idx >= len(self.cacheFiltersKeys):
            return

        filter = self.cacheFiltersKeys[f_idx]
        f_idx += 1
        cItem['f_idx'] = f_idx
        if f_idx == len(self.cacheFiltersKeys):
            cItem['category'] = nextCategory
        self.listsTab(self.cacheFilters.get(filter, []), cItem)

    def listItems(self, cItem, nextCategory):
        printDBG("SolarMovie.listItems |%s|" % cItem)
        url = cItem['url']

        page = cItem.get('page', 1)

        query = {}
        if page > 1:
            query['page'] = page

        keysList = ['f_type[]']
        keysList.extend(self.cacheFiltersKeys)
        for key in keysList:
            baseKey = key[2:] # "f_"
            if key in cItem:
                query[baseKey] = cItem[key]

        query = urllib_urlencode(query)
        if '?' in url:
            url += '&' + query
        else:
            url += '?' + query

        sts, data = self.getPage(url)
        if not sts:
            return

        nextPage = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="pagination">', '</ul>', False)[1]
        if '>&raquo;</a>' in nextPage:
            nextPage = True
        else:
            nextPage = False

        data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="film-list">', '<div class="clearfix', False)[1]
        data = data.split('<div class="item">')
        if len(data):
            del data[0]
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0])
            tip = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'data-tip="([^"]+?)"')[0])
            if not self.cm.isValidUrl(url):
                continue
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, 'src="([^"]+?)"')[0])
            tmp = item.split('</a>')
            title = self.cleanHtmlStr(tmp[-1])
            desc = self.cleanHtmlStr(tmp[0])
            if title == '':
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''alt=['"]([^'^"]+?)['"]''')[0])
            if title == '':
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''title=['"]([^'^"]+?)['"]''')[0])

            params = dict(cItem)
            params = {'good_for_fav': True, 'title': title, 'url': url, 'desc': desc, 'tip_url': tip, 'icon': icon}
            params['category'] = nextCategory
            self.addDir(params)

        if nextPage and len(self.currList) > 0:
            params = dict(cItem)
            params.update({'title': _("Next page"), 'page': page + 1})
            self.addDir(params)

    def exploreItem(self, cItem):
        printDBG("SolarMovie.exploreItem")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        params = dict(self.defaultParams)
        params['header'] = dict(self.AJAX_HEADER)
        params['header']['Referer'] = self.cm.meta['url']

        timestamp = self.cm.ph.getSearchGroups(data, '''data-ts=['"]([0-9]+?)['"]''')[0]
        id = self.cm.ph.getDataBeetwenNodes(data, ('<', 'watch-page', '>'), ('<', '>'))[1]
        id = self.cm.ph.getSearchGroups(id, '''data-id=['"]([^'^"]+?)['"]''')[0]
        getParams = {'ts': timestamp}
        getParams = self._updateParams(getParams)
        url = self.getFullUrl('/ajax/film/servers/{0}?'.format(id) + urllib_urlencode(getParams))

        sts, data = self.getPage(url, params)
        if not sts:
            return []

        try:
            data = byteify(json.loads(data))['html']
            printDBG(data)
        except Exception:
            printExc()

        titlesTab = []
        self.cacheLinks = {}
        #data = self.cm.ph.getDataBeetwenMarkers(data, '<div id="servers">', '<div class="widget')[1]
        data = data.split('<div class="server row"')
        for tmp in data:
            serverName = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(tmp, '<label', '</label>')[1])
            serverId = self.cm.ph.getSearchGroups(tmp, '''data-id=['"]([^'^"]+?)['"]''')[0]
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li', '</li>')
            for item in tmp:
                title = self.cleanHtmlStr(item)
                id = self.cm.ph.getSearchGroups(item, '''data-id=['"]([^'^"]+?)['"]''')[0]
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
                if title not in titlesTab:
                    titlesTab.append(title)
                    self.cacheLinks[title] = []
                url = strwithmeta(url, {'id': id, 'server_id': serverId})
                self.cacheLinks[title].append({'name': serverName, 'url': url, 'need_resolve': 1})

        for item in titlesTab:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': '%s : %s' % (cItem['title'], item), 'links_key': item})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("AnimeTo.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('search?keyword=' + urllib_quote_plus(searchPattern))
        self.listItems(cItem, 'explore_item')

    def getLinksForVideo(self, cItem):
        printDBG("SolarMovie.getLinksForVideo [%s]" % cItem)
        key = cItem.get('links_key', '')
        return self.cacheLinks.get(key, [])

    def _cryptoJS_AES(self, encrypted, password, decrypt=True):
        def derive_key_and_iv(password, key_length, iv_length):
            d = d_i = ''
            while len(d) < key_length + iv_length:
                d_i = md5(ensure_binary(d_i + password)).digest()
                d += d_i
            return d[:key_length], d[key_length:key_length + iv_length]
        bs = 16
        key, iv = derive_key_and_iv(password, 32, 16)
        cipher = AES_CBC(key=key, keySize=32)
        if decrypt:
            return cipher.decrypt(encrypted, iv)
        else:
            return cipher.encrypt(encrypted, iv)

    def _updateParams(self, params):
        if self._myFun == None:
            try:
                tmp = 'd4dc09ccf50eec3e8ff154e9aaae91d70fd5cb194964f86c2f2b4dda892d816c987cca66475b807bf875241ea891e7063f608834577df64b8a97f73fcb5598a2f7cd9aee7a7720eca337c09b1fd8808a1140579345f89aea4169d465869f1149e7e79245df09793524d95bfe8ed80b693316d6dce7c09a57c16fd29f0210ad2711f3a1fb4641bf914f7ef342fb1355211601edc691103e5c635ca2af3b8e730f18732e87348f95b806f4d976c113adbc6104b7524d5a22824fa2f694fda0e32b44bac01b78a2ff3baa2c224036bde220417074720a6965a6a835031b97fd18eaac53af1477d6e67ab66f324d9e2e3fc9051840f038336821ad2695090b6fc18589769b4fd63fa2baca4dbdec2d636b261537d3bb54c25ea3cdf591e1896486e086047ae196d93f625da5aefabed41b163297e09d4d6d39bb6336997197d76fdd829b7946e1e48a1182c633f9ad690798b17f8a01e3bb72838839779bd1e36f85857a45d09ae592435642f83d0629264a7f90f4822bb3ab51e78489659cbdcaa22ee798482edafcb948833bff410bb88c25440971f12ab54a5082d98cdf0bb6be9a9c992fac672e8ce3b4525c63d02ca3ea344ae3c150bf1c49e9b83bc7c40839d3bd9babd75860d3560ca0887a38c29eab0155c81cd6f400c1e69d05b228a84052683a5a6821d72185140aaa343fae61a9e06d2100924d4f716f752436528d2b169cd585ce0e5ca243bd6ad457cba5ba402f4706311ccaeefcce6bbccd4e65ba1e2d4318af6f1844d32c27bf871ca198c31bf6f7dcc9185357fd202f419795cb104ccb5383fafd91dd1ad97b2098f579077233c8ce07952a696babdd4e5ae913c5166c92950dc4a1457d2e77f39e4b72c044c3e248a76de4af1dcea6bafe66ea12bce34fe9d6be668f85a2f329256c312c4ec44b86ad66b32be861b916fff7ee33692be1f8a93161c1215e4c621a58427bb0a0d26bda5459f6335b982cf0725af821d6ee7d3dc12d1b3228a3fc2548646819ec8001649088e9cf042d248ef9e7'
                tmp = self._cryptoJS_AES(unhexlify(tmp), ''.join(GetPluginDir().split('/')[-5:]))
                tmp = base64.b64decode(tmp.split('\r')[-1]).replace('\r', '')
                _myFun = compile(tmp, '', 'exec')
                vGlobals = {"__builtins__": None, 'len': len, 'dict': dict, 'list': list, 'ord': ord, 'range': range, 'str': str, 'max': max, 'hex': hex}
                vLocals = {'zaraza': ''}
                exec(_myFun in vGlobals, vLocals)
                self._myFun = vLocals['zaraza']
            except Exception:
                printExc()
        try:
            params = self._myFun(params)
        except Exception:
            printExc()
        return params

    def getVideoLinks(self, videoUrl):
        printDBG("SolarMovie.getVideoLinks [%s]" % videoUrl)
        baseUrl = videoUrl
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
        params['header'] = dict(self.AJAX_HEADER)
        params['header']['Referer'] = str(videoUrl)

        sts, data = self.getPage(videoUrl[:videoUrl.rfind('/')], params)
        if sts:
            timestamp = self.cm.ph.getSearchGroups(data, '''data-ts=['"]([0-9]+?)['"]''')[0]
        else:
            timestamp = ''

        if timestamp == '':
            sts, data = self.getPage(videoUrl, params)
            if not sts:
                return []
            timestamp = self.cm.ph.getSearchGroups(data, '''data-ts=['"]([0-9]+?)['"]''')[0]

        getParams = {'ts': timestamp, 'id': videoUrl.meta.get('id', ''), 'Q': '1'}
        getParams = self._updateParams(getParams)
        url = self.getFullUrl('/ajax/film/update-views?' + urllib_urlencode(getParams))
        sts, data = self.getPage(url, params)
        if not sts:
            return []

        m = "++++++++++++++++++++++++++++++++"
        printDBG('%s\n%s\n%s' % (m, data, m))

        getParams = {'ts': timestamp, 'id': videoUrl.meta.get('id', ''), 'server': videoUrl.meta.get('server_id', ''), 'update': '0'}
        getParams = self._updateParams(getParams)

        url = self.getFullUrl('/ajax/episode/info?' + urllib_urlencode(getParams))
        sts, data = self.getPage(url, params)
        if not sts:
            return []

        videoUrl = ''
        subTrack = ''
        try:
            data = byteify(json.loads(data))
            printDBG(data)
            subTrack = data.get('subtitle', '')
            if data['type'] == 'iframe':
                videoUrl = data['target']
                if videoUrl.startswith('//'):
                    videoUrl = 'http:' + videoUrl
            elif data['type'] == 'direct':
                query = dict(data['params'])
                query.update({'mobile': '0'})
                url = data['grabber']
                if '?' in url:
                    url += '&'
                else:
                    url += '?'
                url += urllib_urlencode(query)
                sts, data = self.getPage(url, params)
                if not sts:
                    return []
                data = byteify(json.loads(data))
                for item in data['data']:
                    if item['type'] != 'mp4':
                        continue
                    if not self.cm.isValidUrl(item['file']):
                        continue
                    urlTab.append({'name': item['label'], 'url': item['file']})
                urlTab = urlTab[::-1]
            else:
                printDBG('Unknown url type!')
                printDBG(">>>>>>>>>>>>>>>>>>>>>")
                printDBG(data)
                printDBG("<<<<<<<<<<<<<<<<<<<<<")
        except Exception:
            printExc()

        if self.cm.isValidUrl(videoUrl) and 0 == len(urlTab):
            urlTab = self.up.getVideoLinkExt(strwithmeta(videoUrl, {'Referer': baseUrl}))

        if self.cm.isValidUrl(subTrack):
            cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE, ['PHPSESSID', 'cf_clearance'])
            subTrack = strwithmeta(subTrack, {'Cookie': cookieHeader, 'User-Agent': self.HEADER['User-Agent']})
            format = subTrack[-3:]
            for idx in range(len(urlTab)):
                urlTab[idx]['url'] = strwithmeta(urlTab[idx]['url'])
                if 'external_sub_tracks' not in urlTab[idx]['url'].meta:
                    urlTab[idx]['url'].meta['external_sub_tracks'] = []
                urlTab[idx]['url'].meta['external_sub_tracks'].append({'title': '', 'url': subTrack, 'lang': 'pt', 'format': format})

        return urlTab

    def getArticleContent(self, cItem):
        printDBG("SolarMovie.getArticleContent [%s]" % cItem)
        retTab = []

        params = dict(self.defaultParams)
        params['header'] = dict(self.AJAX_HEADER)
        params['header']['Referer'] = str(cItem['url'])

        sts, data = self.getPage(cItem['url'], params)
        if not sts:
            return []

        id = self.cm.ph.getSearchGroups(data, '''<([^>]+?class="watch-page"[^>]*?)>''')[0]
        id = self.cm.ph.getSearchGroups(id, '''data-id=['"]([^'^"]+?)['"]''')[0]

        timestamp = self.cm.ph.getSearchGroups(data, '''data-ts=['"]([0-9]+?)['"]''')[0]

        getParams = {'ts': timestamp}
        getParams = self._updateParams(getParams)
        url = self.getFullUrl('/ajax/film/tooltip/' + id + '?' + urllib_urlencode(getParams))
        sts, data = self.getPage(url, params)
        if not sts:
            return []

        printDBG(data)

        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<p class="desc">', '</p>')[1])
        if desc == '':
            desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, '<meta property="og:description"[^>]+?content="([^"]+?)"')[0])

        title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<h1', '</h1>')[1])
        if title == '':
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, '<meta property="og:title"[^>]+?content="([^"]+?)"')[0])

        icon = self.getFullUrl(self.cm.ph.getSearchGroups(data, '<meta property="og:image"[^>]+?content="([^"]+?)"')[0])

        if title == '':
            title = cItem['title']
        if desc == '':
            desc = cItem['desc']
        if icon == '':
            icon = cItem['icon']

        otherInfo = {}
        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<span class="duration"', '</span>')[1])
        if tmp != '':
            otherInfo['duration'] = tmp

        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<span class="imdb"', '</span>')[1])
        if tmp != '':
            otherInfo['imdb_rating'] = tmp

        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<span class="quality"', '</span>')[1])
        if tmp != '':
            otherInfo['quality'] = tmp

        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, 'Country:', '</div>', False)[1])
        if tmp != '':
            otherInfo['country'] = tmp

        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, 'Stars:', '</div>', False)[1])
        if tmp != '':
            otherInfo['stars'] = tmp

        tmp = self.cm.ph.getDataBeetwenMarkers(data, 'Genre:', '</div>', False)[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<a', '</a>')
        tmp = ', '.join([self.cleanHtmlStr(item) for item in tmp])
        if tmp != '':
            otherInfo['genre'] = tmp

        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<h1>', '</div>', False)[1]
        tmp = self.cm.ph.getSearchGroups(tmp, '''<span[^>]*?>\s*([0-9]+?)\s*<''')[0]
        if tmp != '':
            otherInfo['year'] = tmp

        return [{'title': self.cleanHtmlStr(title), 'text': self.cleanHtmlStr(desc), 'images': [{'title': '', 'url': self.getFullUrl(icon)}], 'other_info': otherInfo}]

    def getFavouriteData(self, cItem):
        printDBG('SolarMovie.getFavouriteData')
        return json.dumps(cItem)

    def getLinksForFavourite(self, fav_data):
        printDBG('SolarMovie.getLinksForFavourite')
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
        printDBG('SolarMovie.setInitListFromFavouriteItem')
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
        if self.MAIN_URL == None:
            #rm(self.COOKIE_FILE)
            self.selectDomain()

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})
        elif category == 'list_filters':
            self.listFilters(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem, 'explore_item')
        elif category == 'explore_item':
            self.exploreItem(self.currItem)
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
        CHostBase.__init__(self, SolarMovie(), True, [])

    def withArticleContent(self, cItem):
        if cItem['type'] != 'video' and cItem['category'] != 'explore_item':
            return False
        return True
