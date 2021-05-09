# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify, rm, GetPluginDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute
from Plugins.Extensions.IPTVPlayer.libs.crypto.cipher.aes_cbc import AES_CBC
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib
import base64
from binascii import hexlify, unhexlify
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
config.plugins.iptvplayer.putlockertv_proxy = ConfigSelection(default="None", choices=[("None", _("None")),
                                                                                           ("proxy_1", _("Alternative proxy server (1)")),
                                                                                           ("proxy_2", _("Alternative proxy server (2)"))])
config.plugins.iptvplayer.putlockertv_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.putlockertv_proxy))
    if config.plugins.iptvplayer.putlockertv_proxy.value == 'None':
        optionList.append(getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.putlockertv_alt_domain))
    return optionList
###################################################


def gettytul():
    return 'https://putlockertv.to/'


class PutlockerTvTo(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'yesmovies.to', 'cookie': 'yesmovies.to.cookie'})

        self.DEFAULT_ICON_URL = 'https://blog.malwarebytes.com/wp-content/uploads/2014/10/photodune-4471691-on-behalf-of-the-spring-green-icon-s-837x506.jpg'
        self.HEADER = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0', 'DNT': '1', 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})
        self.MAIN_URL = None
        self.cacheLinks = {}
        self.cacheFilters = {}
        self.cacheFiltersKeys = []
        self.defaultParams = {'with_metadata': True, 'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self._myFun = None

    def uncensored(self, data):
        cookieItems = {}
        try:
            jscode = base64.b64decode('''dmFyIGRvY3VtZW50ID0ge307DQp2YXIgd2luZG93ID0gdGhpczsNCnZhciBsb2NhdGlvbiA9ICJodHRwczovLzlhbmltZS50by8iOw0KU3RyaW5nLnByb3RvdHlwZS5pdGFsaWNzPWZ1bmN0aW9uKCl7cmV0dXJuICI8aT48L2k+Ijt9Ow0KU3RyaW5nLnByb3RvdHlwZS5saW5rPWZ1bmN0aW9uKCl7cmV0dXJuICI8YSBocmVmPVwidW5kZWZpbmVkXCI+PC9hPiI7fTsNClN0cmluZy5wcm90b3R5cGUuZm9udGNvbG9yPWZ1bmN0aW9uKCl7cmV0dXJuICI8Zm9udCBjb2xvcj1cInVuZGVmaW5lZFwiPjwvZm9udD4iO307DQpBcnJheS5wcm90b3R5cGUuZmluZD0iZnVuY3Rpb24gZmluZCgpIHsgW25hdGl2ZSBjb2RlXSB9IjsNCkFycmF5LnByb3RvdHlwZS5maWxsPSJmdW5jdGlvbiBmaWxsKCkgeyBbbmF0aXZlIGNvZGVdIH0iOw0KZnVuY3Rpb24gZmlsdGVyKCkNCnsNCiAgICBmdW4gPSBhcmd1bWVudHNbMF07DQogICAgdmFyIGxlbiA9IHRoaXMubGVuZ3RoOw0KICAgIGlmICh0eXBlb2YgZnVuICE9ICJmdW5jdGlvbiIpDQogICAgICAgIHRocm93IG5ldyBUeXBlRXJyb3IoKTsNCiAgICB2YXIgcmVzID0gbmV3IEFycmF5KCk7DQogICAgdmFyIHRoaXNwID0gYXJndW1lbnRzWzFdOw0KICAgIGZvciAodmFyIGkgPSAwOyBpIDwgbGVuOyBpKyspDQogICAgew0KICAgICAgICBpZiAoaSBpbiB0aGlzKQ0KICAgICAgICB7DQogICAgICAgICAgICB2YXIgdmFsID0gdGhpc1tpXTsNCiAgICAgICAgICAgIGlmIChmdW4uY2FsbCh0aGlzcCwgdmFsLCBpLCB0aGlzKSkNCiAgICAgICAgICAgICAgICByZXMucHVzaCh2YWwpOw0KICAgICAgICB9DQogICAgfQ0KICAgIHJldHVybiByZXM7DQp9Ow0KT2JqZWN0LmRlZmluZVByb3BlcnR5KGRvY3VtZW50LCAiY29va2llIiwgew0KICAgIGdldCA6IGZ1bmN0aW9uICgpIHsNCiAgICAgICAgcmV0dXJuIHRoaXMuX2Nvb2tpZTsNCiAgICB9LA0KICAgIHNldCA6IGZ1bmN0aW9uICh2YWwpIHsNCiAgICAgICAgcHJpbnQodmFsKTsNCiAgICAgICAgdGhpcy5fY29va2llID0gdmFsOw0KICAgIH0NCn0pOw0KQXJyYXkucHJvdG90eXBlLmZpbHRlciA9IGZpbHRlcjsNCiVzDQoNCg==''') % (data)
            ret = js_execute(jscode)
            if ret['sts'] and 0 == ret['code']:
                printDBG(ret['data'])
                data = ret['data'].split('\n')
                for line in data:
                    line = line.strip()
                    if not line.endswith('=/'):
                        continue
                    line = line.split(';')[0]
                    line = line.replace(' ', '').split('=')
                    if 2 != len(line):
                        continue
                    cookieItems[line[0]] = line[1].split(';')[0]
        except Exception:
            printExc()
        return cookieItems

    def getPage(self, url, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)

        proxy = config.plugins.iptvplayer.putlockertv_proxy.value
        if proxy != 'None':
            if proxy == 'proxy_1':
                proxy = config.plugins.iptvplayer.alternative_proxy1.value
            else:
                proxy = config.plugins.iptvplayer.alternative_proxy2.value
            addParams = dict(addParams)
            addParams.update({'http_proxy': proxy})

        addParams['cloudflare_params'] = {'cookie_file': self.COOKIE_FILE, 'User-Agent': self.HEADER['User-Agent']}
        return self.cm.getPageCFProtection(url, addParams, post_data)

    def getFullIconUrl(self, url):
        url = url.split('url=')[-1]
        url = self.getFullUrl(url)
        proxy = config.plugins.iptvplayer.putlockertv_proxy.value
        if proxy != 'None':
            if proxy == 'proxy_1':
                proxy = config.plugins.iptvplayer.alternative_proxy1.value
            else:
                proxy = config.plugins.iptvplayer.alternative_proxy2.value
            url = strwithmeta(url, {'iptv_http_proxy': proxy})
        if url != '':
            cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE, ['PHPSESSID', 'cf_clearance'])
            url = strwithmeta(url, {'Cookie': cookieHeader, 'User-Agent': self.HEADER['User-Agent']})
        return url

    def selectDomain(self):
        domains = ['https://www5.putlockertv.to/']
        domain = config.plugins.iptvplayer.putlockertv_alt_domain.value.strip()
        if self.cm.isValidUrl(domain):
            if domain[-1] != '/':
                domain += '/'
            domains.insert(0, domain)

        for domain in domains:
            sts, data = self.getPage(domain)
            if sts and '/movies' in data:
                self.MAIN_URL = self.cm.getBaseUrl(data.meta['url'])
                break

            if self.MAIN_URL != None:
                break

        if self.MAIN_URL == None:
            self.MAIN_URL = domains[0]

    def listMainMenu(self, cItem):
        if self.MAIN_URL == None:
            return
        MAIN_CAT_TAB = [{'category': 'list_items', 'title': 'Featured', 'url': self.getFullUrl('/featured')},
                        {'category': 'list_filters', 'title': 'Movies', 'url': self.getFullUrl('/movies'), 'f_type[]': 'movie'},
                        {'category': 'list_filters', 'title': 'TV-Series', 'url': self.getFullUrl('/tv-series'), 'f_type[]': 'series'},
                        {'category': 'search', 'title': _('Search'), 'search_item': True, },
                        {'category': 'search_history', 'title': _('Search history'), }
                       ]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def fillCacheFilters(self, cItem):
        printDBG("PutlockerTvTo.listCategories")
        self.cacheFilters = {}
        self.cacheFiltersKeys = []

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        def addFilter(data, marker, baseKey, allTitle='', titleFormat=''):
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
                    allTitle = ''
                elif titleFormat != '':
                    title = titleFormat.format(title)
                self.cacheFilters[key].append({'title': title.title(), key: value})

            if len(self.cacheFilters[key]):
                if allTitle != '':
                    self.cacheFilters[key].insert(0, {'title': allTitle})
                self.cacheFiltersKeys.append(key)

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'filter dropdown'), ('</ul', '>'))
        for tmp in data:
            if 'type[]' in tmp:
                continue
            titleFormat = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(tmp, ('<button', '>'), ('<', '>'), False)[1]) + ': {0}'
            key = self.cm.ph.getSearchGroups(tmp, '''name="([^"]+?)"''')[0]
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li', '</li>')
            addFilter(tmp, 'value', key, _('All'), titleFormat)

        printDBG(self.cacheFilters)

    def listFilters(self, cItem, nextCategory):
        printDBG("PutlockerTvTo.listFilters")
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
        printDBG("PutlockerTvTo.listItems")
        page = cItem.get('page', 1)

        query = {}
        keys = list(self.cacheFiltersKeys)
        keys.extend(['f_type[]', 'f_keyword'])
        for key in keys:
            baseKey = key[2:] # "f_"
            if key in cItem:
                query[baseKey] = cItem[key]

        if query != {}:
            if 'f_keyword' in cItem:
                url = self.getFullUrl('/search')
            else:
                url = self.getFullUrl('/filter')
        else:
            url = cItem['url']

        if page > 1:
            query['page'] = page
        query = urllib.urlencode(query)
        if '?' in url:
            url += '&' + query
        else:
            url += '?' + query

        sts, data = self.getPage(url)
        if not sts:
            return

        if '>&raquo;<' in data:
            nextPage = True
        else:
            nextPage = False

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'item'), ('<div', '>', 'footer'))[1]
        data = self.cm.ph.rgetAllItemsBeetwenNodes(data, ('</div', '>'), ('<div', '>', 'item'))
        if nextPage and len(data):
            data[-1] = re.compile('<div[^>]+paging[^>]+?>').split(data[-1], 1)[0]
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            tip = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''data\-tip=['"]([^"^']+?)['"]''')[0])
            if not self.cm.isValidUrl(url):
                continue
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''')[0])
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
            params.update({'good_for_fav': False, 'title': _("Next page"), 'page': page + 1})
            self.addDir(params)

    def exploreItem(self, cItem):
        printDBG("PutlockerTvTo.exploreItem")

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
        url = self.getFullUrl('/ajax/film/servers/{0}?'.format(id) + urllib.urlencode(getParams))

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
        printDBG("PutlockerTvTo.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['f_keyword'] = searchPattern
        cItem['category'] = 'list_items'
        self.listItems(cItem, 'explore_item')

    def getLinksForVideo(self, cItem):
        printDBG("PutlockerTvTo.getLinksForVideo [%s]" % cItem)
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

    def _updateParams(self, params):
        if self._myFun == None:
            try:
                if False:
                    tmp = 'base64_code'
                    tmp = self._cryptoJS_AES(tmp, ''.join(GetPluginDir().split('/')[-5:]), False)
                    tmp = hexlify(tmp)
                    printDBG("$$$: " + tmp)
                else:
                    tmp = 'd4dc09ccf50eec3e8ff154e9aaae91d7929c817981b33e845bd0b59ba69cdee3c2d131462159801b5c5f8ca1593cf434ab5b37a0109293bb5b77460cccb36b881f6d05920c9c4b1f8e8db5d3c144b481de77292eca89468f9f87782cc5facef40096e18371a68dd18bddbdcc744db850dbb9666ff1e4e478ba88a7af1872cc3a4f073fd33b00b73101f26746b140e082e519bc88dba1baa9981cbe20712f5927799db6152c03634df5232599438fb7665dfc3fc3aeae7d9d7eee146576619d1b1a8e07ada0bd9d48d094648053f79f3f7077b2e415883e798b2d1c241b27cc7854da4e71c4398df86fc4b7398d3127debd4eedc97775d5a43aeaf4e071ba0e3dc7be5a1651e95a51888c842ed0b3181822b6404837b7c477cf729641f7e53c40455e126854b8879194ead6a0ba0d3d23c4f991dd5b6dddf3d0c6e34ae5f543414a3bdfac20b543cee43452397d95f909ed841bff0ad32cb073b12ecc538f0c9e314df9740a07669b453d79a8107de12330d96b81f5092082801d054825e08c21cc1261d0055495190f402b979caaf87984475e320a931bf3c46f756f4e1322d7417db247b7152345c16dc749e3e22da5f895a57ecd8ec91d62c63de822fb1afa4e07ccfe23a1e5ca9cb0277eada4805961147f92c88b3708182a64b911443572b437d0f57e3c28a70092ed20006ef9d1c2e0ec68d25f0ef586a292e6503e533cf56c04fc1044262877c631bd0908fd67fead53fd9b1dc7f606df62ead99177a758a9fb92da18edf484655d35619cc5d062bfdb19de48b53c0f8229c1d027158b3dbd44539faecff61b48d0bfe89a742b3f2c52325b1e23893b7dfb303db11d68fb98ff3d752fe46d2464b7e32d873d37c537e7b30fcb8a581fd79c217134be224d2a8682b6fa675f2e56e6ee933455ee3901388e4602dad2e77dbad5f1791b555786b7d35c84e01e58be9e5f9db7336ca2bc62553c91ca55f9daf6500273922e89840a6d3348b4ab8692d31eb9ea4f8ab850e4088a85086fa6c5d25e4a21fd344cc332e061332cee63630cbd263c8fb446c705a72eb996df156d808af308639dd46c38a7c5e68140770d4cd61bf0dc460a1900ff232dfeca5805ef26cda6d5aaec6856a10303af0ce2298a8747d02b0e351989512309d46e7be56c694e30cb8c0aa915ee2c71831070b605f54b4d87babe9de968c6ccf83392e16d0fb89c4e1cca6892a1d1e2012ed3aec7747e81504395b51059e3f60f1493c7003c16fb657779933907371c839d6a7a5e4b3a14ad27ba8408925d18208bfed1595d37812b1fe672e79d0af986a813fce12d1278c96bef11493746612b9ceb02c62a7ef91c2585ad27b195a75730d14d77ac424b0656'
                    tmp = self._cryptoJS_AES(unhexlify(tmp), ''.join(GetPluginDir().split('/')[-5:]))
                    tmp = base64.b64decode(tmp.split('\r')[-1]).replace('\r', '')
                _myFun = compile(tmp, '', 'exec')
                vGlobals = {"__builtins__": None, 'len': len, 'dict': dict, 'list': list, 'ord': ord, 'range': range, 'str': str, 'max': max, 'hex': hex, 'True': True, 'False': False}
                vLocals = {'zaraza': ''}
                exec _myFun in vGlobals, vLocals
                self._myFun = vLocals['zaraza']
            except Exception:
                printExc()
        try:
            params = self._myFun(params)
        except Exception:
            printExc()
        return params

    def getVideoLinks(self, videoUrl):
        printDBG("PutlockerTvTo.getVideoLinks [%s]" % videoUrl)
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

        #sts, data = self.getPage(self.getFullUrl('token'))
        #if not sts: return []
        #cookieItem = self.uncensored(data)

        params = dict(self.defaultParams)
        params['header'] = dict(self.AJAX_HEADER)
        params['header']['Referer'] = str(videoUrl)
        #params['cookie_items'] = cookieItem

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
        url = self.getFullUrl('/ajax/film/update-views?' + urllib.urlencode(getParams))
        sts, data = self.getPage(url, params)
        if not sts:
            return []

        printDBG('+++++\n%s\n+++++' % (data))

        getParams = {'ts': timestamp, 'id': videoUrl.meta.get('id', ''), 'server': videoUrl.meta.get('server_id', ''), 'update': '0'}
        getParams = self._updateParams(getParams)

        url = self.getFullUrl('/ajax/episode/info?' + urllib.urlencode(getParams))
        sts, data = self.getPage(url, params)
        if not sts:
            return []

        videoUrl = ''
        subTrack = ''
        try:
            printDBG('+++++\n%s\n+++++' % (data))
            if data[0] not in '[{':
                data = data[data.find('{'):]
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
                url += urllib.urlencode(query)
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
        url = self.getFullUrl('/ajax/film/tooltip/' + id + '?' + urllib.urlencode(getParams))
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
            self.listMainMenu({'name': 'category'})
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
        CHostBase.__init__(self, PutlockerTvTo(), True, [])

    def withArticleContent(self, cItem):
        if cItem.get('type', 'video') != 'video' and cItem.get('category', 'unk') != 'explore_item':
            return False
        return True
