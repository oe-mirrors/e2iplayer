# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.recaptcha_v2helper import CaptchaHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify, GetPluginDir
from Plugins.Extensions.IPTVPlayer.libs.pCommon import DecodeGzipped, EncodeGzipped
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.crypto.cipher.aes_cbc import AES_CBC
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib
from binascii import hexlify, unhexlify
from hashlib import md5
###################################################


def gettytul():
    return 'https://9anime.to/'


class AnimeTo(CBaseHostClass, CaptchaHelper):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': '9anime.to', 'cookie': '9animeto.cookie'})
        self.DEFAULT_ICON_URL = 'http://redeneobux.com/wp-content/uploads/2017/01/2-4.png'
        self.USER_AGENT = 'User-Agent=Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})
        self.MAIN_URL = 'https://www1.9anime.to/'
        self.cacheEpisodes = {}
        self.cacheLinks = {}
        self.cacheFilters = {}
        self.cacheFiltersKeys = []
        self.defaultParams = {'header': self.HEADER, 'with_metadata': True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.MAIN_CAT_TAB = [{'category': 'list_filters', 'title': _('Home'), 'url': self.getFullUrl('/filter')},
                             {'category': 'list_items', 'title': _('Newest'), 'url': self.getFullUrl('/newest')},
                             {'category': 'list_items', 'title': _('Last update'), 'url': self.getFullUrl('/updated')},
                             {'category': 'list_items', 'title': _('Most watched'), 'url': self.getFullUrl('/most-watched')},
                             {'category': 'list_letters', 'title': _('A-Z List'), 'url': self.getFullUrl('/az-list')},

                             {'category': 'search', 'title': _('Search'), 'search_item': True, },
                             {'category': 'search_history', 'title': _('Search history'), }
                            ]
        self.scriptCache = {}

    def getFullIconUrl(self, url):
        url = url.replace('&amp;', '&')
        return CBaseHostClass.getFullIconUrl(self, url)

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        addParams['cloudflare_params'] = {'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def listLetters(self, cItem, nextCategory):
        printDBG("AnimeTo.listLetters")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(data.meta['url'])

        data = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'letters'), ('</ul', '>'))[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            title = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'good_for_fav': False, 'category': nextCategory, 'title': title, 'url': url})
            self.addDir(params)

    def fillCacheFilters(self, cItem):
        printDBG("AnimeTo.listCategories")
        self.cacheFilters = {}
        self.cacheFiltersKeys = []

        sts, data = self.getPage(self.getFullUrl('ongoing'))
        if not sts:
            return
        self.setMainUrl(data.meta['url'])

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
                self.cacheFilters[key].append({'title': title.title(), key: value})

            if len(self.cacheFilters[key]):
                if addAll:
                    self.cacheFilters[key].insert(0, {'title': _('All')})
                self.cacheFiltersKeys.append(key)

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'filter dropdown'), ('</ul', '>'))
        for tmp in data:
            key = self.cm.ph.getSearchGroups(tmp, '''name="([^"]+?)"''')[0]
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li', '</li>')
            addFilter(tmp, 'value', key)

        printDBG(self.cacheFilters)

    def listFilters(self, cItem, nextCategory):
        printDBG("AnimeTo.listFilters")
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
        printDBG("AnimeTo.listItems")
        url = cItem['url']
        page = cItem.get('page', 1)

        query = {}
        if page > 1:
            query['page'] = page

        for key in self.cacheFiltersKeys:
            baseKey = key[2:] # "f_"
            if key in cItem:
                query[baseKey] = cItem[key]

        query = urllib.urlencode(query)
        if '?' in url:
            url += '&' + query
        else:
            url += '?' + query

        sts, data = self.getPage(url)
        if not sts:
            return
        self.setMainUrl(data.meta['url'])

        if '>Next<' in data:
            nextPage = True
        else:
            nextPage = False

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'item'), ('<script', '>'))[1]
        data = self.cm.ph.rgetAllItemsBeetwenNodes(data, ('</div', '>'), ('<div', '>', 'item'))
        if nextPage and len(data):
            data[-1] = re.compile('<div[^>]+?paging\-wrapper[^>]+?>').split(data[-1], 1)[0]
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0])
            tip = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'data-tip="([^"]+?)"')[0])
            if not self.cm.isValidUrl(url):
                continue
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, 'src="([^"]+?)"')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<a', '>', 'name'), ('</a', '>'))[1])
            if title == '':
                title = self.cleanHtmlStr(item)
            if title == '':
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''alt=['"]([^'^"]+?)['"]''')[0])
            if title == '':
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''title=['"]([^'^"]+?)['"]''')[0])

            desc = []
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(item, '<div', '</div>')
            for t in tmp:
                t = self.cleanHtmlStr(t)
                if t != '':
                    desc.append(t)
            desc = ' | '.join(desc)
            desc += '[/br]' + self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<p', '</p>')[1])

            params = dict(cItem)
            params = {'good_for_fav': True, 'title': title, 'url': url, 'tip_url': tip, 'icon': icon, 'desc': desc}
            params['category'] = nextCategory
            self.addDir(params)

        if nextPage and len(self.currList) > 0:
            params = dict(cItem)
            params.update({'title': _("Next page"), 'page': page + 1})
            self.addDir(params)

    def exploreItem(self, cItem, nextCategory):
        printDBG("AnimeTo.exploreItem")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(data.meta['url'])

        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'desc'), ('</div', '>'))[1])
        jsCode = self._getJsCode(data, data.meta['url'])
        timestamp = self.cm.ph.getSearchGroups(data, '''data-ts=['"]([0-9]+?)['"]''')[0]

        params = dict(self.defaultParams)
        params['header'] = dict(self.AJAX_HEADER)
        params['header']['Referer'] = self.cm.meta['url']

        id = self.cm.ph.getDataBeetwenNodes(data, ('<', '"player"', '>'), ('<', '>'))[1]
        id = self.cm.ph.getSearchGroups(id, '''data-id=['"]([^'^"]+?)['"]''')[0]

        getParams = {}

        sitekey = self.cm.ph.getSearchGroups(data, '''data\-sitekey=['"]([^'^"]+?)['"]''')[0]
        if sitekey != '':
            token, errorMsgTab = self.processCaptcha(sitekey, self.cm.meta['url'])
            if token != '':
                getParams['gresponse'] = token

        url = self.getFullUrl('/ajax/film/servers/{0}'.format(id))
        url = self._getUrl(jsCode, url, urllib.urlencode(getParams), timestamp)

        sts, data = self.getPage(url, params)
        if not sts:
            return []

        try:
            data = json_loads(data)['html']
            printDBG(data)
        except Exception:
            printExc()

        serverNamesMap = {}
        #tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'servers'), ('</div', '>'))[1]
        tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<span', '>', 'data-name'), ('</span', '>'))
        for item in tmp:
            serverName = self.cleanHtmlStr(item)
            serverKey = self.cm.ph.getSearchGroups(item, '''\sdata\-name=['"]([^'^"]+?)['"]''')[0]
            serverNamesMap[serverKey] = serverName

        rangesTab = []
        self.cacheEpisodes = {}
        self.cacheLinks = {}
        data = re.compile('''(<div[^>]+?server[^>]+?>)''').split(data)
        for idx in range(1, len(data), 2):
            if 'episodes' not in data[idx + 1]:
                continue
            serverKey = self.cm.ph.getSearchGroups(data[idx], '''\sdata\-name=['"]([^'^"]+?)['"]''')[0]
            serverName = serverNamesMap.get(serverKey, serverKey)

            rangeNameMap = {}
            tmp = self.cm.ph.getAllItemsBeetwenNodes(data[idx + 1], ('<span', '>', 'data-range-id'), ('</span', '>'))
            for item in tmp:
                rangeName = self.cleanHtmlStr(item)
                rangeKey = self.cm.ph.getSearchGroups(item, '''\sdata\-range\-id=['"]([^'^"]+?)['"]''')[0]
                rangeNameMap[rangeKey] = rangeName

            tmp = self.cm.ph.getAllItemsBeetwenMarkers(data[idx + 1], '<ul', '</ul>')
            for rangeSection in tmp:
                rangeKey = self.cm.ph.getSearchGroups(rangeSection, '''\sdata\-range\-id=['"]([^'^"]+?)['"]''')[0]
                rangeName = rangeNameMap.get(rangeKey, rangeKey)

                if rangeName not in rangesTab:
                    rangesTab.append(rangeName)
                    self.cacheEpisodes[rangeName] = []

                rangeSection = self.cm.ph.getAllItemsBeetwenMarkers(rangeSection, '<li', '</li>')
                for item in rangeSection:
                    title = self.cleanHtmlStr(item)
                    id = self.cm.ph.getSearchGroups(item, '''data-id=['"]([^'^"]+?)['"]''')[0]
                    url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
                    if id == '' or url == '':
                        continue
                    if title not in self.cacheEpisodes[rangeName]:
                        self.cacheEpisodes[rangeName].append(title)
                        self.cacheLinks[title] = []
                    url = strwithmeta(url, {'id': id})
                    self.cacheLinks[title].append({'name': serverName, 'url': url, 'need_resolve': 1})

        for item in rangesTab:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'category': nextCategory, 'series_title': cItem['title'], 'title': item, 'desc': desc, 'range_key': item})
            if 1 == len(rangesTab):
                self.listEpisodes(params)
                break
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("AnimeTo.listEpisodes")
        episodesTab = self.cacheEpisodes[cItem['range_key']]
        for item in episodesTab:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': '%s : %s' % (cItem['series_title'], item), 'links_key': item})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("AnimeTo.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('search?keyword=' + urllib.quote_plus(searchPattern))
        self.listItems(cItem, 'explore_item')

    def getLinksForVideo(self, cItem):
        printDBG("AnimeTo.getLinksForVideo [%s]" % cItem)
        key = cItem.get('links_key', '')
        return self.cacheLinks.get(key, [])

    def _cryptoJS_AES(self, encrypted, password, decrypt=True):
        def derive_key_and_iv(password, key_length, iv_length):
            d = d_i = ''
            while len(d) < key_length + iv_length:
                d_i = md5(d_i + password).digest()
                d += d_i
            return d[:key_length], d[key_length:key_length + iv_length]
        bs = 16
        key, iv = derive_key_and_iv(password, 32, 16)
        cipher = AES_CBC(key=key, keySize=32)
        if decrypt:
            return cipher.decrypt(encrypted, iv)
        else:
            return cipher.encrypt(encrypted, iv)

    def _getUrl(self, jsCode, url='', data='', timestamp=''):
        printDBG("AnimeTo._getUrl url[%s], data[%s], timestamp[%s]" % (url, data, timestamp))
        try:
            if False:
                tmp = EncodeGzipped('')
                tmp = self._cryptoJS_AES(tmp, ''.join(GetPluginDir().split('/')[-5:]), False)
                tmp = hexlify(tmp)
                printDBG("$$$: " + tmp)
            else:
                tmp = 'ed3cfec3d06c36b40958c04b3cdfac405d3f49f2c8414537917d63db171714e2a14761c2f7f1aab84c0b91e47562fc4c7050284e95372807978603d115ec9b1e11accaf3493e91005f13a0e82bb461408027ae9d30572987a821eee530a9488927ac26a7c114b0a33bf76a472b3f9c583e856d754ecd11f5caf780f441c263b422db5ca8fb561144184049da10df93f1009fc9081ff0ffe77e341d53d94dd9a3c816713fb09b6b656c3b24185199f23c34bad676acfb1a9d91b7ae892d3e71b9ccc7368dffed08b276d9dd6987833f3cf1430ad9126e0661132db4c19bd12a8f5bcb64a4e938e0889bfcf4a636ca6e9b2e5eae05896ab902673be34cf82feaa357178ee32ee1b78796ea75d00b6181adebd500d071c35bd6aebc9e5650092d7c95d029713ed76f6d11d3e1153c759afa494f9461bfca8e6a30ddf3d7ecabb5a78aa62d37c78f90fb6df5f5138dd1c6415719c58f103335e6c6451b7b8de48bd80646d1d9b542977b4ff5d6332cdaf4f68e0fe24eea5b0d86039d6e66b558d011e29c2e946683739cc2c0619aa65de58ca5fed484b8db9f3eea0866e6f21ba839d4c177bc2efcd85aa6055520176c67528ccc1f5e9880e833d24ed9b84a7e24f315de0d6eaa38320f5daff8d42ed6edce911ded996ca077bf2b3acc76d5ceea0a6c590b4f58566f55c35d670b95b22881214b11e6779c43a3729a5acc36187f3e88cf9baf82782aa61868ae21b7a778e4d228ff1deb7475e56a74efae1334d8ffb12c428aaf7d6e10fb64464eac3d2c3a3b112920f7193ea57efc0095614c28fdd81143ab42fa21d61610f6062072a2abfd6dc702c22af67552c4c8c5cd347bc40597641c5fd69c2aa68641ee3960b323a5332326cb4505e52cff439dda63b78682dab7002d362835f189afb2535da6e3336f583602051e5693e7f286ca20507f8ef90c6a1c6fde24843a3bbd417ab463cd7d8105bc77f1e514a76cf5b81d95e80dd62892aeebf6b9e443bca6fb83e21890222bd65ae1ddb9eac051c29b78f43b'
                tmp = self._cryptoJS_AES(unhexlify(tmp), ''.join(GetPluginDir().split('/')[-5:]))
                tmp = DecodeGzipped(tmp)
        except Exception:
            printExc()

        retUrl = ''
        jscode = ['iptv_ts=%s;' % timestamp, tmp, jsCode, 'iptv_arg = {url:"%s", "data":"%s"}; iptv_call(iptv_arg); print(JSON.stringify(iptv_arg));' % (url, data)]
        ret = js_execute('\n'.join(jscode), {'timeout_sec': 15})
        if ret['sts'] and 0 == ret['code']:
            data = ret['data'].strip()
            try:
                data = json_loads(data)
                retUrl = data['url']
                if data['data'] != '':
                    retUrl += '&' + data['data']
            except Exception:
                printExc()
        return retUrl

    def _getJsCode(self, data, cUrl):
        params = dict(self.defaultParams)
        params['header'] = dict(self.AJAX_HEADER)
        params['header']['Referer'] = cUrl

        allJsScripts = []
        jsCode = ''
        tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<script', '>', 'all.js'), ('</script', '>'))
        for item in tmp:
            jsUrl = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?all\.js(?:\?[^'^"]*?)?)['"]''')[0])
            if jsUrl in self.scriptCache:
                jsCode = self.scriptCache[jsUrl]
                break
            allJsScripts.append(jsUrl)

        if jsCode == '':
            for item in allJsScripts:
                sts, tmp = self.getPage(item, params)
                if not sts:
                    continue
                if '(window' in tmp:
                    jsCode = tmp
                    self.scriptCache[jsCode] = jsCode
                    break
        return jsCode

    def getVideoLinks(self, videoUrl):
        printDBG("AnimeTo.getVideoLinks [%s]" % videoUrl)
        baseUrl = str(videoUrl)
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

        id = videoUrl.meta.get('id', '')
        params = dict(self.defaultParams)
        params['header'] = dict(self.AJAX_HEADER)
        params['header']['Referer'] = str(videoUrl)
        #params['cookie_items'] = cookieItem

        #sts, data = self.getPage('https://9anime.to/ajax/episode/info?id=%s&update=0' % id, params)
        #if not sts: return []

        sts, data = self.getPage(videoUrl[:videoUrl.rfind('/')], params)
        if sts:
            timestamp = self.cm.ph.getSearchGroups(data, '''data-ts=['"]([^"^']+?)['"]''')[0]
        else:
            timestamp = ''

        if timestamp == '':
            sts, data = self.getPage(videoUrl, params)
            if not sts:
                return []
            timestamp = self.cm.ph.getSearchGroups(data, '''data-ts=['"]([^"^']+?)['"]''')[0]

        cUrl = data.meta['url']
        jsCode = self._getJsCode(data, cUrl)

        if False:
            getParams = {'id': videoUrl.meta.get('id', ''), 'Q': '1'}
            url = self.getFullUrl('/ajax/film/update-views')
            url = self._getUrl(jsCode, url, urllib.urlencode(getParams), timestamp)
            sts, data = self.getPage(url, params)
            if not sts:
                return []

        getParams = {'id': videoUrl.meta.get('id', ''), 'random': '0'}
        url = self.getFullUrl('/ajax/episode/info')
        url = self._getUrl(jsCode, url, urllib.urlencode(getParams), timestamp)
        sts, data = self.getPage(url, params)
        if not sts:
            return []

        domain = self.up.getDomain(baseUrl)
        printDBG(">> domain: " + domain)
        videoUrl = ''
        subTrack = ''
        try:
            data = json_loads(data)
            printDBG(data)
            subTrack = data.get('subtitle', '')
            if data['type'] == 'iframe':
                videoUrl = data['target']
                if domain in videoUrl:
                    videoUrl = self._getUrl(jsCode, videoUrl, "", timestamp)
                if videoUrl.startswith('//'):
                    videoUrl = 'http:' + videoUrl
            elif data['type'] == 'direct':
                printDBG("---")
                printDBG(data)
                printDBG("---")
                if domain in data['grabber']:
                    url = self._getUrl(jsCode, data['grabber'], urllib.urlencode(dict(data['params'])), timestamp) + '&mobile=0'
                sts, data = self.getPage(url, params)
                if not sts:
                    return []
                data = json_loads(data)
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

        id = self.cm.ph.getDataBeetwenNodes(data, ('<form', '>', 'film-report'), ('<', '>'))[1]
        id = self.cm.ph.getSearchGroups(id, '''data-id=['"]([^'^"]+?)['"]''')[0]

        timestamp = self.cm.ph.getSearchGroups(data, '''data-ts=['"]([0-9]+?)['"]''')[0]

        printDBG("++++++++++++> timestamp[%s], id[%s]" % (timestamp, id))

        getParams = {'ts': timestamp}
        #getParams = self._updateParams(getParams)
        url = self.getFullUrl('/ajax/film/tooltip/' + id + '?' + urllib.urlencode(getParams))
        sts, data = self.getPage(url, params)
        if not sts:
            return []

        printDBG(data)

        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<p class="desc">', '</p>')[1])
        if desc == '':
            desc = self.cleanHtmlStr(data.split('<div class="meta">')[-1])
        if desc == '':
            desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, '<meta property="og:description"[^>]+?content="([^"]+?)"')[0])

        title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div class="title">', '<span>')[1])
        if title == '':
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, '<meta property="og:title"[^>]+?content="([^"]+?)"')[0])

        icon = self.getFullUrl(self.cm.ph.getSearchGroups(data, '<meta property="og:image"[^>]+?content="([^"]+?)"')[0])

        if title == '':
            title = cItem.get('title', '')
        if desc == '':
            desc = cItem.get('desc', '')
        if icon == '':
            icon = cItem.get('icon', '')

        otherInfo = {}
        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<span class="duration"', '</span>')[1])
        if tmp != '':
            otherInfo['duration'] = tmp

        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<span class="imdb"', '</span>')[1])
        if tmp != '':
            otherInfo['imdb_rating'] = tmp

        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenReMarkers(data, re.compile('<[^>]+class="quality"'), re.compile('</span>'))[1])
        if tmp != '':
            otherInfo['quality'] = tmp

        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, 'Country:', '</div>', False)[1])
        if tmp != '':
            otherInfo['country'] = tmp

        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, 'Stars:', '</div>', False)[1])
        if tmp != '':
            otherInfo['stars'] = tmp

        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, 'Other names:', '</div>', False)[1])
        if tmp != '':
            otherInfo['alternate_title'] = tmp

        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, 'Status:', '</div>', False)[1])
        if tmp != '':
            otherInfo['status'] = tmp

        tmp = self.cm.ph.getDataBeetwenMarkers(data, 'Genre:', '</div>', False)[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<a', '</a>')
        tmp = ', '.join([self.cleanHtmlStr(item) for item in tmp])
        if tmp != '':
            otherInfo['genre'] = tmp

        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<div class="title">', '</div>', False)[1]
        tmp = self.cm.ph.getSearchGroups(tmp, '''<span[^>]*?>\s*([0-9]+?)\s*<''')[0]
        if tmp != '':
            otherInfo['year'] = tmp

        return [{'title': self.cleanHtmlStr(title), 'text': self.cleanHtmlStr(desc), 'images': [{'title': '', 'url': self.getFullUrl(icon)}], 'other_info': otherInfo}]

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
            self.cacheLinks = {}
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})
        elif category == 'list_filters':
            self.listFilters(self.currItem, 'list_items')
        elif category == 'list_letters':
            self.listLetters(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem, 'explore_item')
        elif category == 'explore_item':
            self.exploreItem(self.currItem, 'list_episodes')
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
        CHostBase.__init__(self, AnimeTo(), True, [])

    def withArticleContent(self, cItem):
        if cItem['type'] != 'video' and cItem['category'] != 'explore_item':
            return False
        return True
