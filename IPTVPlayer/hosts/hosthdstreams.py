# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs import ph
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib
from Components.config import config, ConfigSelection, ConfigYesNo, ConfigText, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.libs.crypto.cipher.aes_cbc import AES_CBC
from binascii import unhexlify
from hashlib import md5
import base64
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.api_key_9kweu = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.api_key_2captcha = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.hdstreams_linkcache = ConfigYesNo(default=True)
config.plugins.iptvplayer.hdstreams_bypassrecaptcha = ConfigSelection(default="None", choices=[("None", _("None")),
                                                                                                 ("9kw.eu", "https://9kw.eu/"),
                                                                                                 ("2captcha.com", "http://2captcha.com/")])


def GetConfigList():
    optionList = []
    #optionList.append(getConfigListEntry(_("Use links cache"), config.plugins.iptvplayer.hdstreams_linkcache))
    #optionList.append(getConfigListEntry(_("Captcha solving service"), config.plugins.iptvplayer.hdstreams_bypassrecaptcha))
    #if config.plugins.iptvplayer.hdstreams_bypassrecaptcha.value == '9kw.eu':
    #    optionList.append(getConfigListEntry(_("%s API KEY") % '    ', config.plugins.iptvplayer.api_key_9kweu))
    #elif config.plugins.iptvplayer.hdstreams_bypassrecaptcha.value == '2captcha.com':
    #    optionList.append(getConfigListEntry(_("%s API KEY") % '    ', config.plugins.iptvplayer.api_key_2captcha))
    return optionList
###################################################


def gettytul():
    return 'https://hd-streams.org/'


class HDStreams(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'new-hd-streams.org', 'cookie': 'hd-streams.org.cookie'})
        self.USER_AGENT = 'Mozilla / 5.0 (SMART-TV; Linux; Tizen 2.4.0) AppleWebkit / 538.1 (KHTML, podobnie jak Gecko) SamsungBrowser / 1.1 TV Safari / 538.1'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})

        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.DEFAULT_ICON_URL = 'http://s-media-cache-ak0.pinimg.com/originals/82/63/59/826359efee44e19824912cdf45b3bd59.jpg'
        self.MAIN_URL = None
        self.cacheLinks = {}
        self.cacheFilters = {}
        self.cacheFiltersKeys = []

    def selectDomain(self):

        self.MAIN_URL = 'https://hd-streams.org/'
        self.MAIN_CAT_TAB = [{'category': 'list_filters', 'title': _('MOVIES'), 'url': self.getFullUrl('/movies')},
                             {'category': 'list_filters', 'title': _('TV SERIES'), 'url': self.getFullUrl('/seasons')},

                             {'category': 'search', 'title': _('Search'), 'search_item': True, },
                             {'category': 'search_history', 'title': _('Search history'), }
                            ]

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        addParams['cloudflare_params'] = {'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def getFullIconUrl(self, url):
        url = CBaseHostClass.getFullIconUrl(self, url.strip())
        if url == '':
            return ''
        cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE, ['PHPSESSID', 'cf_clearance'])
        return strwithmeta(url, {'Cookie': cookieHeader, 'User-Agent': self.USER_AGENT})

    def cryptoJS_AES_decrypt(self, encrypted, password, salt):
        def derive_key_and_iv(password, salt, key_length, iv_length):
            d = d_i = ''
            while len(d) < key_length + iv_length:
                d_i = md5(d_i + password + salt).digest()
                d += d_i
            return d[:key_length], d[key_length:key_length + iv_length]
        bs = 16
        key, iv = derive_key_and_iv(password, salt, 32, 16)
        cipher = AES_CBC(key=key, keySize=32)
        return cipher.decrypt(encrypted, iv)

    def fillCacheFilters(self, cItem):
        printDBG("HDStreams.listCategories")
        self.cacheFilters = {}
        self.cacheFiltersKeys = []

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        # year
        key = 'f_year'
        tmp = self.cm.ph.getDataBeetwenReMarkers(data, re.compile('source\.years\s*=\s*\['), re.compile('\]'), False)[1].split(',')
        self.cacheFilters[key] = []
        for value in tmp:
            try:
                value = str(int(value))
            except Exception:
                continue
            self.cacheFilters[key].append({'title': value, key: value})
        if len(self.cacheFilters[key]):
            self.cacheFilters[key].insert(0, {'title': _('Any')})
            self.cacheFiltersKeys.append(key)

        # genres
        key = 'f_genre'
        tmp = self.cm.ph.getDataBeetwenMarkers(data, 'source.genres', ']')[1].split('}')
        self.cacheFilters[key] = []
        for item in tmp:
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''['"]?text['"]?\s*:\s*['"]([^'^"]+?)['"]''')[0])
            value = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''['"]?value['"]?\s*:\s*['"]([^'^"]+?)['"]''')[0])
            if len(title) and len(value):
                self.cacheFilters[key].append({'title': title, key: value})
        if len(self.cacheFilters[key]):
            self.cacheFilters[key].insert(0, {'title': _('All')})
            self.cacheFiltersKeys.append(key)

        url = self.cm.ph.getSearchGroups(data, '''<script[^>]+?src=['"]([^'^"]*?/js/app\.[^'^"]*?js)['"]''')[0]
        sts, data = self.getPage(self.getFullUrl(url))
        if not sts:
            return

        # order
        key = 'f_order'
        tmp = self.cm.ph.getDataBeetwenMarkers(data, 'items:[', ']')[1].split('},')
        self.cacheFilters[key] = []
        for item in tmp:
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''['"]?text['"]?\s*:\s*['"]([^'^"]+?)['"]''')[0])
            order = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''['"]?order['"]?\s*:\s*['"]([^'^"]+?)['"]''')[0])
            orderBy = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''['"]?orderBy['"]?\s*:\s*['"]([^'^"]+?)['"]''')[0])
            if len(title) and len(order) and len(orderBy):
                self.cacheFilters[key].append({'title': title, key: orderBy, 'f_order_by': order})
        if len(self.cacheFilters[key]):
            self.cacheFilters[key].insert(0, {'title': _('Default')})
            self.cacheFiltersKeys.append(key)

        printDBG(self.cacheFilters)

    def listFilters(self, cItem, nextCategory):
        printDBG("HDStreams.listFilters")
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

    def listItems(self, cItem, nextCategory='', searchPattern=''):
        printDBG("HDStreams.listItems |%s|" % cItem)
        #NUM = 48
        url = cItem['url']
        page = cItem.get('page', 1)

        query = {'page': page} #'perPage':NUM,
        keys = [('f_genre', 'genre[]'), ('f_year', 'year[]'), ('f_order', 'order'), ('f_order_by', 'orderBy')]
        for item in keys:
            if item[0] in cItem:
                query[item[1]] = cItem[item[0]]

        query = urllib.urlencode(query)
        if '?' in url:
            url += '&' + query
        else:
            url += '?' + query

        sts, data = self.getPage(url)
        if not sts:
            return

        nextPage = ph.find(data, ('<ul', '>', 'pagination'), '</ul>', flags=0)[1]
        nextPage = ph.search(nextPage, '''page=(%s)[^0-9]''' % (page + 1))[0]
        if nextPage != '':
            nextPage = True
        else:
            nextPage = False

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'movie-wrap'), ('</a', '>'))
        for item in data:
            url = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''url\(\s*['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenReMarkers(item, re.compile('''<span[^>]+?filename[^>]*?>'''), re.compile('</span>'), False)[1])
            desc = []
            if '/video-hd-32.png' in item:
                desc.append(_('Quality:') + ' HD')
            views = self.cleanHtmlStr(self.cm.ph.getDataBeetwenReMarkers(item, re.compile('''<div[^>]+?views[^>]*?>'''), re.compile('</div>'), False)[1])
            if views != '':
                desc.append(_('Views:') + ' ' + views)

            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'desc': '[/br]'.join(desc), 'icon': icon})
            self.addDir(params)

        if nextPage:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _('Next page'), 'page': page + 1})
            self.addDir(params)

    def exploreItem(self, cItem):
        printDBG("HDStreams.exploreItem")

        self.cacheLinks = {}

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        desc = ''
        icon = ''
        baseTitle = ''

        article = self.getArticleContent(cItem, data)
        printDBG(article)
        if len(article):
            article = article[0]
            descTab = []
            for key in ['year', 'rating', 'genres']:
                val = article['other_info'].get(key, '')
                if val != '':
                    descTab.append(val)
            desc = ' | '.join(descTab) + '[/br]' + article.get('text', '')
            icon = article.get('icon', '')
            baseTitle = article.get('title', '')

        if icon == '':
            icon = cItem.get('icon', '')
        if desc == '':
            desc = cItem.get('desc', '')
        if baseTitle == '':
            baseTitle = cItem.get('title', '')

        videoId = self.cm.ph.getSearchGroups(data, '''video\-id=['"]['"]?([^'^"]+?)['"]''')[0]
        if videoId != '':
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': '%s %s' % (cItem['title'], '[TRAILER]'), 'url': strwithmeta('https://www.youtube.com/watch?v=' + videoId, {'Referer': cItem['url']}), 'desc': desc, 'icon': icon})
            self.addVideo(params)

        if 'source.serie.' in data:
            type = 'serie'
        else:
            type = 'movie'

        if type == 'movie':
            # get links
            linksKey = cItem['url']

            linksTab = []
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<v-tab-item', '</v-tab-item>')
            flagsReObj = re.compile('''<i[\s>].+?</i>''', flags=re.DOTALL)
            for langItem in data:
                langId = self.cm.ph.getSearchGroups(langItem, '''key=["']*?([^'^"]+?)["']''')[0][1:]
                langItem = self.cm.ph.getAllItemsBeetwenMarkers(langItem, '<v-flex', '</v-flex>')
                for qualityItem in langItem:
                    qualityName = self.cm.ph.getDataBeetwenMarkers(qualityItem, '<v-btn', '</v-btn>')[1]
                    qualityItem = self.cm.ph.getAllItemsBeetwenMarkers(qualityItem, '<v-tooltip', '</v-tooltip>')
                    if 'recaptcha' not in qualityName:
                        qualityName = self.cleanHtmlStr(qualityName)
                    else:
                        qualityName = ''
                    for linkItem in qualityItem:
                        tmp = self.cm.ph.getSearchGroups(linkItem, '''recaptcha\(\s*['"]([^'^"]+?)['"]\s*,\s*['"]([^'^"]+?)['"],\s*['"]([^'^"]+?)['"]''', 3)
                        if '' in tmp:
                            continue
                        name = self.cleanHtmlStr(flagsReObj.sub('', linkItem))
                        name = '[%s][%s] %s' % (langId, qualityName, name)
                        url = strwithmeta(cItem['url'], {'links_key': linksKey, 'link_data': tmp, 'post_data': {'e': tmp[0], 'h': tmp[1], 'lang': langId}})
                        linksTab.append({'name': name, 'url': url, 'need_resolve': 1})

            if len(linksTab):
                self.cacheLinks[linksKey] = linksTab
                params = dict(cItem)
                params.update({'good_for_fav': False, 'links_key': linksKey, 'desc': desc, 'icon': icon})
                self.addVideo(params)
        else:
            sNum = self.cm.ph.getSearchGroups(cItem['url'] + '/', 'season/([0-9]+?)[^0-9]')[0]
            data = self.cm.ph.getDataBeetwenNodes(data, ('<v-layout', '>', 'episode'), ('</v-layout', '>'))[1]
            sp = re.compile('''<div[^>]+?avatar[^>]*?>''')
            data = sp.split(data)
            for episodeItem in data:
                eIcon = self.cm.ph.getSearchGroups(episodeItem, '''src=['"]([^'^"]+?)['"]''')[0]
                if eIcon == '' or eIcon.startswith('data:image'):
                    eIcon = icon
                eIcon = self.getFullIconUrl(eIcon)
                eTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenReMarkers(episodeItem, re.compile('''<p[^>]+?episode\-name'''), re.compile('</p>'))[1])
                eNum = self.cleanHtmlStr(self.cm.ph.getDataBeetwenReMarkers(episodeItem, re.compile('''<p[^>]+?episode\-number'''), re.compile('</p>'))[1])
                eNum = self.cm.ph.getSearchGroups(eNum + '|', '[^0-9]([0-9]+?)[^0-9]')[0]
                linksKey = '%s?s_num=%s&e_num=%s' % (cItem['url'], sNum, eNum)
                linksTab = []

                episodeItem = self.cm.ph.getAllItemsBeetwenMarkers(episodeItem, '<v-list-tile ', '</v-list-tile>')
                for linkItem in episodeItem:
                    tmp = self.cm.ph.getSearchGroups(linkItem, '''loadStream\(\s*['"]([^'^"]+?)['"]\s*,\s*['"]([^'^"]+?)['"]''', 2)
                    if '' in tmp:
                        tmp = self.cm.ph.getSearchGroups(linkItem, '''loadEpisodeStream\(\s*['"]([^'^"]+?)['"]\s*,\s*['"]([^'^"]+?)['"]''', 2)
                    if '' in tmp:
                        continue
                    name = self.cleanHtmlStr(linkItem)
                    url = strwithmeta(cItem['url'], {'links_key': linksKey, 'link_data': tmp, 'post_data': {'e': tmp[0], 'h': tmp[1], 'lang': 'de'}}) #langId
                    linksTab.append({'name': name, 'url': url, 'need_resolve': 1})

                if len(linksTab):
                    self.cacheLinks[linksKey] = linksTab
                    params = dict(cItem)
                    params.update({'good_for_fav': False, 'title': '%s : s%se%s %s' % (baseTitle, sNum.zfill(2), eNum.zfill(2), eTitle), 'links_key': linksKey, 'desc': desc, 'icon': eIcon})
                    self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("HDStreams.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))

        if searchType == 'movies':
            movies = 'true'
            series = 'false'
            keys = ['movies']
        elif searchType == 'series':
            movies = 'false'
            series = 'true'
            keys = ['seasons']
        else:
            movies = 'false'
            series = 'true'
            keys = ['movies', 'seasons']

        url = self.getFullUrl('/home')
        sts, data = self.getPage(url)
        if not sts:
            return

        urlParams = dict(self.defaultParams)
        urlParams['header'] = dict(self.AJAX_HEADER)
        urlParams['header']['Referer'] = url
        urlParams['header']['x-csrf-token'] = self.cm.ph.getSearchGroups(data, '''<[^>]+?csrf-token[^>]+?content=['"]([^'^"]+?)['"]''')[0]
        urlParams['header']['x-xsrf-token'] = self.cm.getCookieItem(self.COOKIE_FILE, 'XSRF-TOKEN')
        urlParams['header']['x-requested-with'] = 'XMLHttpRequest'

        url = self.getFullUrl('/search')
        query = urllib.urlencode({'q': searchPattern, 'movies': movies, 'seasons': series, 'didyoumean': 'true', 'actors': 'false'})
        sts, data = self.getPage(url + '?' + query, urlParams)
        if not sts:
            return

        printDBG(data)

        try:

            data = json_loads(data, '', True)
            for key in keys:
                for item in data[key]:
                    icon = self.getFullIconUrl(item.get('src', ''))
                    url = self.getFullUrl(item.get('url', ''))
                    if url == '':
                        continue
                    title = self.cleanHtmlStr(item.get('title', ''))
                    desc = self.cleanHtmlStr(item.get('original_title', ''))
                    params = dict(cItem)
                    params.update({'good_for_fav': True, 'category': 'explore_item', 'title': title, 'url': url, 'icon': icon, 'desc': desc})
                    self.addDir(params)
        except Exception:
            printExc()

    def getLinksForVideo(self, cItem):
        printDBG("HDStreams.getLinksForVideo [%s]" % cItem)
        linksTab = []
        if 1 == self.up.checkHostSupport(cItem.get('url', '')):
            videoUrl = cItem['url'].replace('youtu.be/', 'youtube.com/watch?v=')
            return self.up.getVideoLinkExt(videoUrl)

        linksKey = cItem.get('links_key', '')
        linksTab = self.cacheLinks.get(linksKey, [])

        if 'urls' in cItem:
            linksTab = cItem['urls']

        return linksTab

    def getVideoLinks(self, videoUrl):
        printDBG("HDStreams.getVideoLinks [%s]" % videoUrl)
        meta = strwithmeta(videoUrl).meta
        linksKey = meta.get('links_key', '')
        post_data = meta.get('post_data', {})

        printDBG('++++ meta[%s]' % meta)

        for idx in range(len(self.cacheLinks[linksKey])):
            if self.cacheLinks[linksKey][idx]['url'].meta['links_key'] == linksKey:
                tmp_post = self.cacheLinks[linksKey][idx]['url'].meta.get('post_data', {})
                if tmp_post == post_data:
                    if not self.cacheLinks[linksKey][idx]['name'].startswith('*'):
                        self.cacheLinks[linksKey][idx]['name'] = '*' + self.cacheLinks[linksKey][idx]['name']
                    break

        sts, data = self.getPage(videoUrl)
        if not sts:
            return []

        recaptcha = self.cm.ph.getSearchGroups(data, '''source\.recaptcha\s*?=\s*?(false|true)''')[0]
        printDBG(">> recaptcha[%s]" % recaptcha)
        if recaptcha == 'true':
            SetIPTVPlayerLastHostError(_('Link protected with google recaptcha v2.'))

        urlParams = dict(self.defaultParams)
        urlParams['header'] = dict(self.AJAX_HEADER)
        urlParams['header']['Referer'] = videoUrl
        urlParams['header']['x-csrf-token'] = self.cm.ph.getSearchGroups(data, '''<[^>]+?csrf-token[^>]+?content=['"]([^'^"]+?)['"]''')[0]
        urlParams['header']['x-xsrf-token'] = self.cm.getCookieItem(self.COOKIE_FILE, 'XSRF-TOKEN')
        urlParams['header']['x-requested-with'] = 'XMLHttpRequest'
        urlParams['ignore_http_code_ranges'] = [(401, 401)]

        post_data = dict(post_data)
        post_data.update({"q": "", "grecaptcha": ""})
        sts, data = self.getPage(videoUrl + '/stream', urlParams, post_data)
        if not sts:
            return []

        if 'captcha' in data.lower():
            SetIPTVPlayerLastHostError(_('Link protected with google recaptcha v2.'))

        try:
            printDBG(data)
            mainData = json_loads(data)

            # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++
            tmp = mainData.get('d', '') + mainData.get('c', '') + mainData.get('iv', '') + mainData.get('f', '') + mainData.get('h', '') + mainData.get('b', '')
            printDBG("tmp: " + tmp)
            tmp = json_loads(base64.b64decode(tmp))

            ciphertext = base64.b64decode(tmp['ct'][::-1])
            iv = unhexlify(tmp['iv'])
            salt = unhexlify(tmp['s'])
            b = urlParams['header']['x-csrf-token'] #urlParams['header']['User-Agent']
            b = base64.b64encode(b[::-1])
            printDBG("b: " + b)
            tmp = self.cryptoJS_AES_decrypt(ciphertext, b, salt)
            printDBG(tmp)

            tmp = json_loads(base64.b64decode(tmp))
            ciphertext = base64.b64decode(tmp['ct'][::-1])
            iv = unhexlify(tmp['iv'])
            salt = unhexlify(tmp['s'])
            b = ''
            a = urlParams['header']['x-csrf-token']
            for idx in range(len(a) - 1, 0, -2):
                b += a[idx]
            if mainData.get('e', None):
                b += '1'
            else:
                b += '0'
            printDBG("b: " + b)
            tmp = self.cryptoJS_AES_decrypt(ciphertext, b, salt)
            printDBG(tmp)
            # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++

            tmp = json_loads(tmp)
            videoUrl = tmp
        except Exception:
            printExc()

        return self.up.getVideoLinkExt(videoUrl)

    def getArticleContent(self, cItem, data=None):
        printDBG("HDStreams.getArticleContent [%s]" % cItem)
        retTab = []

        otherInfo = {}

        url = strwithmeta(cItem['url'])
        url = url.meta.get('Referer', url)

        if data == None:
            sts, data = self.getPage(url)
            if not sts:
                return []

        fullTtitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<h4', '</h4>')[1])

        title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, '''\.title\s*=\s*['"]([^'^"]+?)['"]''')[0])
        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenReMarkers(data, re.compile('''<div[^>]*?card__text[^>]*?>'''), re.compile('</div>'))[1])
        if desc == '':
            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenReMarkers(data, re.compile('''Handlung'''), re.compile('</p>'), False)[1])
        icon = self.cm.ph.getDataBeetwenReMarkers(data, re.compile('''<div[^>]*?movie\-cover[^>]*?>'''), re.compile('</div>'))[1]
        icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(icon, '''src=['"]([^"^']+\.jpe?g)['"]''')[0])

        tmp = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, '''\.rating\s*=([^;]+?);''')[0])
        if tmp != '':
            otherInfo['rating'] = tmp + '/10'

        tmp = self.cm.ph.getDataBeetwenReMarkers(data, re.compile('\.genres\s*=\s*\['), re.compile(']'), False)[1]
        tmp = re.compile('''text['"]?\s*:\s*['"]([^'^"]+?)['"]''').findall(tmp)
        tmpTab = []
        for t in tmp:
            t = self.cleanHtmlStr(t)
            if t != '':
                tmpTab.append(t)
        if len(tmpTab):
            otherInfo['genres'] = ', '.join(tmpTab)

        tmp = self.cm.ph.getDataBeetwenReMarkers(data, re.compile('\.actors\s*=\s*\['), re.compile(']'), False)[1]
        tmp = re.compile('''name['"]?\s*:\s*['"]([^'^"]+?)['"]''').findall(tmp)
        tmpTab = []
        for t in tmp:
            t = self.cleanHtmlStr(t)
            if t != '':
                tmpTab.append(t)
        if len(tmpTab):
            otherInfo['actors'] = ', '.join(tmpTab)

        tmp = self.cleanHtmlStr(self.cm.ph.getSearchGroups(fullTtitle, '''\(\s*([0-9]{4})\s*\)''')[0])
        if tmp != '':
            otherInfo['year'] = tmp

        if title == '':
            title = cItem['title']
        if desc == '':
            desc = cItem.get('desc', '')
        if icon == '':
            icon = cItem.get('icon', self.DEFAULT_ICON_URL)

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
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})
        elif category == 'list_filters':
            self.listFilters(self.currItem, 'list_items')
        elif category == 'list_channels':
            self.listChannels(self.currItem)
        elif 'list_sort' == category:
            self.listSort(self.currItem, 'list_items')
        elif 'list_items' == category:
            self.listItems(self.currItem, 'explore_item')
        elif 'explore_item' == category:
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
        CHostBase.__init__(self, HDStreams(), True, [])

    def getSearchTypes(self):
        searchTypesOptions = []
        searchTypesOptions.append((_("Movies"), "movies"))
        searchTypesOptions.append((_("Series"), "series"))
        return searchTypesOptions

    def withArticleContent(self, cItem):
        if 'video' == cItem.get('type', '') or 'explore_item' == cItem.get('category', ''):
            return True
        return False
