# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.crypto.cipher.aes_cbc import AES_CBC
from Plugins.Extensions.IPTVPlayer.libs.crypto.cipher.base import noPadding
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import urljoin
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus, urllib_unquote
from Plugins.Extensions.IPTVPlayer.p2p3.pVer import isPY2
if not isPY2():
    basestring = str
###################################################
# FOREIGN import
###################################################
import re
import base64
try:
    import json
except Exception:
    import simplejson as json
from binascii import unhexlify
from Components.config import config, ConfigSelection, getConfigListEntry
from copy import deepcopy
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.yify_proxy = ConfigSelection(default="None", choices=[("None", _("None")),
                                                                                    ("proxy_1", _("Alternative proxy server (1)")),
                                                                                    ("proxy_2", _("Alternative proxy server (2)"))])


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.yify_proxy))
    return optionList
###################################################


def gettytul():
    return 'https://ymovies.tv/'


class YifyTV(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'YifyTV', 'cookie': 'yifybz.cookie'})
        self.filterCache = {}
        self.cacheLinks = {}
        self.VIDEO_HOSTINGS_MAP = {"rpd": "https://www.rapidvideo.com/embed/{0}", "vza": "https://vidoza.net/embed-{0}.html", "akv": "https://akvideo.stream/embed-{0}.html", "rpt": "https://www.raptu.com/e/{0}", "lox": "https://vidlox.tv/embed-{0}.html", "vsh": "http://vshare.eu/embed-{0}.html"}

        self.DEFAULT_ICON_URL = 'https://superrepo.org/static/images/icons/original/xplugin.video.yifymovies.hd.png.pagespeed.ic.ZC96NZE8Y2.jpg'
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Language': 'pl,en-US;q=0.7,en;q=0.3', 'Accept-Encoding': 'gzip, deflate'}

        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})

        self.MAIN_URL = 'https://ymovies.tv/'
        self.SRCH_URL = self.getFullUrl('?s=')

        self.MAIN_CAT_TAB = [{'category': 'list_items', 'title': _('Releases'), 'url': self.getFullUrl('files/releases/')},
                             {'category': 'list_popular', 'title': _('Popular'), 'url': self.getFullUrl('wp-admin/admin-ajax.php?action=noprivate_movies_loop&asec=get_pop&needcap=1')},
                             {'category': 'list_items', 'title': _('Top +250'), 'url': self.getFullUrl('files/movies/?meta_key=imdbRating&orderby=meta_value&order=desc')},
                             {'category': 'list_genres_filter', 'title': _('Genres'), 'url': self.getFullUrl('files/movies/')},
                             {'category': 'list_languages_filter', 'title': _('Languages'), 'url': self.getFullUrl('languages/')},
                             {'category': 'list_countries_filter', 'title': _('Countries'), 'url': self.getFullUrl('countries/')},
                             {'category': 'search', 'title': _('Search'), 'search_item': True, },
                             {'category': 'search_history', 'title': _('Search history'), }]

        self.POPULAR_TAB = [{'category': 'list_items2', 'title': _('All'), 'url': self.getFullUrl('wp-admin/admin-ajax.php?action=noprivate_movies_loop&asec=get_pop&needcap=1')},
                            {'category': 'list_items2', 'title': _('Comedies'), 'url': self.getFullUrl('wp-admin/admin-ajax.php?action=noprivate_movies_loop&asec=get_pop&genre=comedy')},
                            {'category': 'list_items2', 'title': _('Animations'), 'url': self.getFullUrl('wp-admin/admin-ajax.php?action=noprivate_movies_loop&asec=get_pop&genre=animation')},
                            {'category': 'list_items2', 'title': _('Dramas'), 'url': self.getFullUrl('wp-admin/admin-ajax.php?action=noprivate_movies_loop&asec=get_pop&genre=drama')}]

        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)

        proxy = config.plugins.iptvplayer.yify_proxy.value
        if proxy != 'None':
            if proxy == 'proxy_1':
                proxy = config.plugins.iptvplayer.alternative_proxy1.value
            else:
                proxy = config.plugins.iptvplayer.alternative_proxy2.value
            addParams = dict(addParams)
            addParams.update({'http_proxy': proxy})

        def _getFullUrl(url):
            if url == '':
                return ''

            if self.cm.isValidUrl(url):
                return url
            else:
                return urljoin(baseUrl, url)

        addParams['cloudflare_params'] = {'domain': self.up.getDomain(baseUrl), 'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT, 'full_url_handle': _getFullUrl}

        url = baseUrl
        urlParams = deepcopy(addParams)
        urlData = deepcopy(post_data)
        unloadUrl = None #
        tries = 0
        removeCookieItems = False
        while tries < 20:
            tries += 1
            sts, data = self.cm.getPageCFProtection(url, urlParams, urlData)
            if not sts:
                return sts, data

            if unloadUrl != None:
                self.cm.getPageCFProtection(unloadUrl, urlParams)
                unloadUrl = None

            if 'sucuri_cloudproxy' in data:
                cookieItems = {}
                jscode = self.cm.ph.getDataBeetwenNodes(data, ('<script', '>'), ('</script', '>'), False)[1]
                if 'eval' in jscode:
                    jscode = '%s\n%s' % (base64.b64decode('''dmFyIGlwdHZfY29va2llcz1bXSxkb2N1bWVudD17fTtPYmplY3QuZGVmaW5lUHJvcGVydHkoZG9jdW1lbnQsImNvb2tpZSIse2dldDpmdW5jdGlvbigpe3JldHVybiIifSxzZXQ6ZnVuY3Rpb24obyl7bz1vLnNwbGl0KCI7IiwxKVswXS5zcGxpdCgiPSIsMiksb2JqPXt9LG9ialtvWzBdXT1vWzFdLGlwdHZfY29va2llcy5wdXNoKG9iail9fSk7dmFyIHdpbmRvdz10aGlzLGxvY2F0aW9uPXt9O2xvY2F0aW9uLnJlbG9hZD1mdW5jdGlvbigpe3ByaW50KEpTT04uc3RyaW5naWZ5KGlwdHZfY29va2llcykpfTs='''), jscode)
                    ret = js_execute(jscode)
                    if ret['sts'] and 0 == ret['code']:
                        try:
                            cookies = byteify(json.loads(ret['data'].strip()))
                            for cookie in cookies:
                                cookieItems.update(cookie)
                        except Exception:
                            printExc()
                self.defaultParams['cookie_items'] = cookieItems
                urlParams['cookie_items'] = cookieItems
                removeCookieItems = False
                sts, data = self.cm.getPageCFProtection(url, urlParams, urlData)

            # remove not needed used cookie
            if removeCookieItems:
                self.defaultParams.pop('cookie_items', None)
            self.cm.clearCookie(self.COOKIE_FILE, removeNames=['___utmvc'])
            printDBG(data)
            return sts, data

        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def fillFiltersCache(self):
        printDBG("YifyTV.fillFiltersCache")
        # Fill genres, years, orderby
        if 0 == len(self.filterCache.get('genres', [])):
            sts, data = self.getPage(self.MAIN_URL + 'files/movies/')
            if sts:
                # genres
                genres = self.cm.ph.getDataBeetwenNodes(data, ('<div', '</div>', '"genres"'), ('</div', '>'), False)[1]
                genres = re.compile('<a[^>]+?href="([^"]+?)"[^>]*?>([^<]+?)</a>').findall(genres)
                self.filterCache['genres'] = [{'title': _('Any')}]
                for item in genres:
                    value = self.cm.ph.getSearchGroups(item[0], '''genre=([^'^"^\?^&]+?)$''')[0]
                    if value == '':
                        continue
                    self.filterCache['genres'].append({'title': self.cleanHtmlStr(item[1]), 'genre': value})

                # orderby
                orderby = self.cm.ph.getDataBeetwenNodes(data, ('<div', '</div>', '"orderby"'), ('</div', '>'), False)[1]
                orderby = re.compile('<a[^>]+?href="([^"]+?)"[^>]*?>([^<]+?)</a>').findall(orderby)
                self.filterCache['orderby'] = []
                for item in orderby:
                    value = item[0].split('?', 1)[-1].replace('&#038;', '&')
                    self.filterCache['orderby'].append({'title': self.cleanHtmlStr(item[1]), 'orderby': value})

                # years
                years = self.cm.ph.getDataBeetwenNodes(data, ('<select', '>', 'years_min'), ('</select', '>'), False)[1]
                years = re.compile('<option[^>]+?value="([^"]+?)"[^>]*?>([^<]+?)</option>').findall(years)
                self.filterCache['years'] = [{'title': _('Any')}]
                for item in years:
                    value = self.cm.ph.getSearchGroups(item[0], '''years=([0-9]{4})''')[0]
                    if value == '':
                        continue
                    self.filterCache['years'].append({'title': self.cleanHtmlStr(item[1]), 'year': value})

        if 0 == len(self.filterCache.get('languages', [])):
            sts, data = self.getPage(self.MAIN_URL + 'languages/')
            if sts:
                #languages
                languages = self.cm.ph.getDataBeetwenMarkers(data, '<!-- start content container -->', '</section>', False)[1]
                languages = re.compile('<a[^>]+?href="([^"]+?)"[^>]*?>([^<]+?)</a>').findall(languages)
                self.filterCache['languages'] = []
                for item in languages:
                    self.filterCache['languages'].append({'title': self.cleanHtmlStr(item[1]), 'url': self.getFullUrl(item[0])})

        if 0 == len(self.filterCache.get('countries', [])):
            sts, data = self.getPage(self.MAIN_URL + 'countries/')
            if sts:
                #countries
                countries = self.cm.ph.getDataBeetwenMarkers(data, '<!-- start content container -->', '</section>', False)[1]
                countries = re.compile('<a[^>]+?href="([^"]+?)"[^>]*?>([^<]+?)</a>').findall(countries)
                self.filterCache['countries'] = []
                for item in countries:
                    self.filterCache['countries'].append({'title': self.cleanHtmlStr(item[1]), 'url': self.getFullUrl(item[0])})

    def listFilters(self, cItem, filter, category):
        printDBG("YifyTV.listFilters")
        tab = self.filterCache.get(filter, [])
        if 0 == len(tab):
            self.fillFiltersCache()
            tab = self.filterCache.get(filter, [])
        cItem = dict(cItem)
        cItem['category'] = category
        self.listsTab(tab, cItem)

    def listItems(self, cItem):
        printDBG("YifyTV.listItems")

        tmp = cItem['url'].split('?')
        baseUrl = tmp[0]
        getArgs = []
        if 2 == len(tmp):
            getArgs.append(tmp[1])
        # page
        page = cItem.get('page', 1)
        if page > 1:
            baseUrl += 'page/%s/' % page
        # year
        if '' != cItem.get('year', ''):
            getArgs.append('years=%s' % cItem['year'])
        # genre
        if '' != cItem.get('genre', ''):
            getArgs.append('genre=%s' % cItem['genre'])
        # orderby
        if '' != cItem.get('orderby', ''):
            getArgs.append(cItem['orderby'])

        if len(getArgs):
            url = baseUrl + '?' + '&'.join(getArgs)
        else:
            url = baseUrl

        sts, data = self.getPage(url)
        if not sts:
            return

        #printDBG(data)

        if ('/page/%s/' % (page + 1)) in data:
            nextPage = True
        else:
            nextPage = False

        data = self.cm.ph.getDataBeetwenMarkers(data, 'var posts = {', '};', False)[1]
        data = '{' + data + '}'
        self._listItems(cItem, data, nextPage)

    def listItems2(self, cItem):
        printDBG("YifyTV.listItems2")

        url = cItem['url'] + '&num=%s' % cItem.get('page', 1)
        sts, data = self.getPage(url)
        if not sts:
            return

        self._listItems(cItem, data, True)

    def _listItems(self, cItem, data, nextPage):
        printDBG("YifyTV.listItems")
        try:
            data = byteify(json.loads(data), noneReplacement='', baseTypesAsString=True)
            #printDBG(data)
            for item in data['posts']:
                item['url'] = self.getFullUrl(item['link'])
                item['title'] = self.cleanHtmlStr(item['title'])
                desc = ' | '.join([item['year'], item['runtime'], item['genre']])
                desc += '[/br]' + self.cleanHtmlStr(item['post_content'])
                item['desc'] = desc
                item['icon'] = self.getFullUrl(item['image'])
                self.addVideo(item)
        except Exception:
            printExc()

        if nextPage:
            page = cItem.get('page', 1)
            params = dict(cItem)
            params.update({'title': _('Next page'), 'page': page + 1})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("YifyTV.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))

        currItem = dict(cItem)
        currItem['url'] = self.SRCH_URL + urllib_quote_plus(searchPattern)
        self.listItems(currItem)

    def getLinksForVideo(self, cItem):
        printDBG("YifyTV.getLinksForVideo [%s]" % cItem)

        urlTab = self.cacheLinks.get(cItem['url'], [])
        if len(urlTab):
            return urlTab

        url = cItem['url']
        if not url.endswith('/'):
            url += '/'
        sts, data = self.getPage(url + 'watching/?playermode=')
        if not sts:
            return urlTab

        printDBG("+++++++++++++++++++++++  data  ++++++++++++++++++++++++")
        printDBG(data)
        printDBG("+++++++++++++++++++++++++++++++++++++++++++++++++++++++")

        trailer = self.cm.ph.getDataBeetwenReMarkers(data, re.compile('''<a[^>]+?class=['"]video'''), re.compile('''</a>'''))[1]
        trailerUrl = self.cm.ph.getSearchGroups(trailer, '''href=['"](https?://[^'^"]+?)['"]''')[0]

        imdbid = self.cm.ph.getSearchGroups(data, '''var\s+imdbid\s*=\s*['"]([^'^"]+?)['"]''')[0]

        jscode = '$ = function(){return {ready:function(){}}};\n' + self.cm.ph.getDataBeetwenMarkers(data, 'function autoPlay()', '</script>')[1][:-9]
        try:
            jscode = base64.b64decode('''dmFyIGRvY3VtZW50ID0ge307DQp2YXIgd2luZG93ID0gdGhpczsNCnZhciBsb2NhdGlvbiA9IHt9Ow0KbG9jYXRpb24uaG9zdG5hbWUgPSAiJXMiOw0KbG9jYXRpb24udG9TdHJpbmcgPSBmdW5jdGlvbigpew0KICAgICAgICAgICAgICAgICAgICAgIHJldHVybiAiJXMiOw0KICAgICAgICAgICAgICAgICAgICB9Ow0KJXM7DQoNCnByaW50KHdpbmRvdy5wYXJhbWV0cm9zKQ==''') % (self.up.getDomain(self.getMainUrl()), self.getMainUrl(), jscode)
            printDBG("+++++++++++++++++++++++  CODE  ++++++++++++++++++++++++")
            printDBG(jscode)
            printDBG("+++++++++++++++++++++++++++++++++++++++++++++++++++++++")
            ret = js_execute(jscode)
            if ret['sts'] and 0 == ret['code']:
                decoded = ret['data'].strip()
                printDBG('DECODED DATA -> [%s]' % decoded)
            data = decoded
        except Exception:
            printExc()

        sub_tracks = []
        subLangs = self.cm.ph.getSearchGroups(data, '&sub=([^&]+?)&')[0]
        if subLangs == '':
            tmp = re.compile("\=([^&]*?)&").findall(data)
            for it in tmp:
                for e in ['PT2', 'EN', 'FR', 'ES']:
                    if e in it:
                        subLangs = it
                        break
                if '' != subLangs:
                    break

        if subLangs != '':
            subID = self.cm.ph.getSearchGroups(data, '&id=(tt[^&]+?)&')[0]
            if subID == '':
                subID = self.cm.ph.getSearchGroups(data, '&pic=(tt[^&]+?)&')[0]
            subLangs = subLangs.split(',')
            for lang in subLangs:
                if subID != '':
                    sub_tracks.append({'title': lang, 'url': 'https://ymovies.tv/player/bajarsub.php?%s_%s' % (subID, lang), 'lang': lang, 'format': 'srt'})

        data = data.split('&')
        idx = 1
        for item in data:
            tmp = item.split('=')
            if len(tmp) != 2:
                continue
            if tmp[1].endswith('enc'):
                url = strwithmeta(tmp[1], {'Referer': cItem['url'], 'sou': tmp[0], 'imdbid': imdbid, 'external_sub_tracks': sub_tracks})
                urlTab.append({'name': _('Mirror') + ' %s' % idx, 'url': url, 'need_resolve': 1})
            elif '' != self.VIDEO_HOSTINGS_MAP.get(tmp[0], ''):
                url = self.VIDEO_HOSTINGS_MAP[tmp[0]].format(tmp[1])
                url = strwithmeta(url, {'Referer': cItem['url'], 'imdbid': imdbid, 'external_sub_tracks': sub_tracks})
                urlTab.append({'name': _('Mirror') + ' %s [%s]' % (idx, self.up.getHostName(url)), 'url': url, 'need_resolve': 1})
            idx += 1

        if len(urlTab):
            self.cacheLinks[cItem['url']] = urlTab

        if self.cm.isValidUrl(trailerUrl) and 1 == self.up.checkHostSupport(trailerUrl):
            urlTab.insert(0, {'name': self.cleanHtmlStr(trailer), 'url': trailerUrl, 'need_resolve': 1})

        return urlTab

    def getVideoLinks(self, baseUrl):
        printDBG("YifyTV.getVideoLinks [%s]" % baseUrl)

        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if baseUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name']
                        break

        urlTab = []

        baseUrl = strwithmeta(baseUrl)
        imdbid = baseUrl.meta.get('imdbid', '')
        sub_tracks = baseUrl.meta.get('external_sub_tracks', [])

        header = dict(self.AJAX_HEADER)
        #header['Referer'] = baseUrl.meta['Referer']

        if 'sou' in baseUrl.meta:
            souTab = [baseUrl.meta['sou']]
            if souTab[0] == 'pic':
                souTab.append('adr')
            if souTab[0] == 'adr':
                souTab.append('pic')

            for sou in souTab:
                post_data = {'fv': '27', 'url': baseUrl, 'sou': sou}
                url = 'https://ymovies.tv/playerlite/pk/pk/plugins/player_p2.php'
                sts, data = self.getPage(url, {'header': header}, post_data)
                if not sts:
                    return []

                printDBG("+++++++++++++++++++++++  data  ++++++++++++++++++++++++")
                printDBG(data)
                printDBG("+++++++++++++++++++++++++++++++++++++++++++++++++++++++")

                try:
                    attempt = 0
                    while attempt < 3:
                        attempt += 1
                        printDBG(data)
                        if 'jscode' in data:
                            try:
                                data = byteify(json.loads(data))[0]['jscode'][1:-1]#.replace('eval(', 'print(')
                                jsTab = ['']
                                jsTab.append('''var iptv_href="%s"; var iptv_domain="%s"; var iptv_video_id="%s"; var iptv_jwpath="%s";\n''' % (self.getMainUrl(), self.up.getDomain(self.getMainUrl()), imdbid, url))
                                jsTab.append(base64.b64decode('''ZnVuY3Rpb24gU2hvd0Rpdigpe31mdW5jdGlvbiBzaG93aUZyYW1lKCl7cHJpbnQoYXJndW1lbnRzWzBdKX1mdW5jdGlvbiBnZXRKd1BhdGgoKXtyZXR1cm4gaXB0dl9qd3BhdGh9ZnVuY3Rpb24gZ2V0X3BhcmFtc19ub19zb3JjZXMoKXtyZXR1cm4gaXB0dl92aWRlb19pZH1mdW5jdGlvbiBzZXRUaW1lb3V0KHQsbil7aWYoaXB0dl9kaXJlY3QpdHJ5e3QoKX1jYXRjaChlKXtwcmludCgiXG4iKX1lbHNlIHRoaXMudHJ5dXAoKX12YXIgZG9jdW1lbnQ9e30sd2luZG93PXRoaXMsbG9jYXRpb249e307bG9jYXRpb24uaHJlZj1pcHR2X2hyZWYsbG9jYXRpb24uaG9zdG5hbWU9aXB0dl9kb21haW4sbG9jYXRpb24udG9TdHJpbmc9ZnVuY3Rpb24oKXtyZXR1cm4gaXB0dl9ocmVmfSxkb2N1bWVudC5sb2NhdGlvbj1sb2NhdGlvbjt2YXIgZWxlbWVudD1mdW5jdGlvbih0KXt0aGlzLnRleHQ9ZnVuY3Rpb24oKXtyZXR1cm4ibm9uZSJ9LHRoaXMuZmlyc3Q9ZnVuY3Rpb24oKXtyZXR1cm4gbmV3IGVsZW1lbnR9fSwkPWZ1bmN0aW9uKHQpe3JldHVybiBuZXcgZWxlbWVudCh0KX0scGxheWVybW9kZT0iIixzb3VyY2VTZWxlY3RlZD0wLHNvdXJjZXM9W3tzdWJfZGVsYXk6MCxzdWJfZmFjdG9yOjF9XTskLmdldD1mdW5jdGlvbigpe3JldHVybiBwcmludChhcmd1bWVudHNbMF0pLHtkb25lOlNob3dEaXYsZXJyb3I6U2hvd0Rpdn19LCQucG9zdD1mdW5jdGlvbigpe3ByaW50KCJcbklQVFZfUE9TVF9TVEFSVFxuIikscHJpbnQoSlNPTi5zdHJpbmdpZnkoe3VybDphcmd1bWVudHNbMF0scGFyYW1zOmFyZ3VtZW50c1sxXX0pKSxwcmludCgiXG5JUFRWX1BPU1RfRU5EXG4iKX07'''))
                                jsTab.append('var iptv_fun = %s; iptv_fun();' % data)

                                for iptv_direct in ["false", "true"]:
                                    jsTab[0] = 'var iptv_direct = %s;' % iptv_direct
                                    jscode = '\n'.join(jsTab)
                                    printDBG("+++++++++++++++++++++++  CODE  ++++++++++++++++++++++++")
                                    printDBG(jscode)
                                    printDBG("+++++++++++++++++++++++++++++++++++++++++++++++++++++++")
                                    ret = js_execute(jscode)
                                    if not ret['sts'] or 0 != ret['code']:
                                        ret = js_execute(jscode.replace('eval(', 'print('))
                                    if ret['sts'] and 0 == ret['code']:
                                        decoded = ret['data'].strip()
                                        printDBG('DECODED DATA -> [%s]' % decoded)
                                        data = decoded
                                        break
                                if 'jscode' in data:
                                    data = data[data.find("["):data.rfind("]") + 1]
                                    data = byteify(json.loads('"%s"' % data))
                                    continue
                            except Exception:
                                printExc()

                            if 'IPTV_POST_START' in data:
                                data = self.cm.ph.getDataBeetwenMarkers(data, 'IPTV_POST_START', 'IPTV_POST_END', 0)[1]
                                try:
                                    tmp = byteify(json.loads(data.strip()))
                                    sts, data = self.getPage(tmp['url'], {'header': header, 'raw_post_data': True}, tmp['params'])
                                    if not sts:
                                        return []
                                    tmp = byteify(json.loads(data))
                                    for hostDomain in tmp['hosts']:
                                        urlTab.append({'name': hostDomain, 'url': 'http://%s%s' % (hostDomain, tmp['path'])})
                                    if len(urlTab):
                                        break
                                except Exception:
                                    printExc()

                            g3 = self.cm.ph.getSearchGroups(data + '&', '''[&\?]g3=([^&]+?)&''')[0]
                            emb = self.cm.ph.getSearchGroups(data + '&', '''[&\?]emb=([^&^\*]+?)[&\*]''')[0]
                            if emb != '':
                                data = urllib_unquote(emb)
                            if g3 != '':
                                post_data = {'fv': '0', 'g3': urllib_unquote(g3)}
                                url = 'https://ymovies.tv/playerlite/pk/pk/plugins/player_g3.php'
                                sts, data = self.getPage(url, {'header': header}, post_data)
                                if not sts:
                                    return []
                                printDBG(data)
                            elif self.cm.isValidUrl(data) and 1 == self.up.checkHostSupport(data):
                                urlTab = self.up.getVideoLinkExt(data)
                                break
                            else:
                                if 'showiFrame(' in data:
                                    url = urllib_unquote(self.cm.ph.getDataBeetwenMarkers(data, "emb='+'", "'", False)[1])
                                    tmp = url.split('sub.file')
                                    url = tmp[0]
                                    subTrack = urllib_unquote(tmp[1])
                                    if url.startswith('//'):
                                        url = 'http:' + url
                                    if subTrack.startswith('//'):
                                        subTrack = 'http:' + subTrack
                                    tmpUrlTab = self.up.getVideoLinkExt(url)
                                    if self.cm.isValidUrl(subTrack):
                                        format = subTrack[-3:]
                                        for idx in range(len(tmpUrlTab)):
                                            tmpUrlTab[idx]['url'] = strwithmeta(tmpUrlTab[idx]['url'], {'external_sub_tracks': [{'title': '', 'url': subTrack, 'lang': 'en', 'format': format}]})
                                    urlTab.extend(tmpUrlTab)
                                    printDBG(urlTab)
                                    break

                                if 'sources[sourceSelected]["paramId"]' in data:
                                    data = data.replace('"+"', '').replace(' ', '')
                                    paramSite = self.cm.ph.getSearchGroups(data, 'sources\[sourceSelected\]\["paramSite"\]="([^"]+?)"')[0]
                                    data = self.cm.ph.getSearchGroups(data, 'sources\[sourceSelected\]\["paramId"\]="([^"]+?)"')[0]
                                    printDBG('data ------------------------- [%s]' % data)
                                    if data.startswith('enc'):
                                        encrypted = base64.b64decode(data[3:])
                                        key = unhexlify(base64.b64decode('MzAzOTM4NzMzOTM3MzU0MTMxMzIzMzczMzEzMzM1NjQ2NDY2Njc3NzQ4MzczODM0MzczNTMzMzQzNjcyNjQ3Nw=='))
                                        iv = unhexlify(base64.b64decode('NWE0MTRlMzEzNjMzNjk2NDZhNGM1MzUxMzU0YzY0MzU='))
                                        cipher = AES_CBC(key=key, padding=noPadding(), keySize=32)
                                        data = cipher.decrypt(encrypted, iv).split('\x00')[0]
                                        if 'ucl' == paramSite:
                                            urlTab.extend(self.up.getVideoLinkExt("https://userscloud.com/embed-" + data + "-1280x534.html"))
                                        elif 'tus' == paramSite:
                                            urlTab.extend(self.up.getVideoLinkExt("https://tusfiles.net/embed-" + data + "-1280x534.html?v=34"))
                                        elif 'up' == paramSite:
                                            urlTab.extend(self.up.getVideoLinkExt("http://uptobox.com/" + data))
                                        break

                        if '("' in data:
                            data = self.cm.ph.getDataBeetwenMarkers(data, '(', ')', False)[1]
                            data = byteify(json.loads(data))
                        if isinstance(data, basestring):
                            data = byteify(json.loads(data))
                        printDBG(data)
                        for item in data:
                            #printDBG('++++++++++++++++++++++\n%s\n++++++++++++++++++++++' % item)
                            if (item.get('type', '').startswith('video/') or item.get('type', '').startswith('application/x-shockwave-flash')) and self.cm.isValidUrl(item.get('url', '')):
                                urlTab.append({'name': '{0}x{1}'.format(item.get('height', ''), item.get('width', '')), 'url': item['url'], 'need_resolve': 0})
                    break
                except Exception:
                    SetIPTVPlayerLastHostError('The Mirror is broken.\nIf available you can choose other source.')
                    printExc()
                    return []

                if len(urlTab):
                    break

        elif self.cm.isValidUrl(baseUrl):
            urlTab = self.up.getVideoLinkExt(baseUrl)

        printDBG(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
        printDBG(urlTab)

        for idx in range(len(urlTab)):
            subs = list(strwithmeta(urlTab[idx]['url']).meta.get('external_sub_tracks', []))
            subs.extend(sub_tracks)
            urlTab[idx]['url'] = strwithmeta(urlTab[idx]['url'], {'external_sub_tracks': subs})

        printDBG(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
        printDBG(urlTab)
        return urlTab

    def getFavouriteData(self, cItem):
        return cItem['url']

    def getLinksForFavourite(self, fav_data):
        return self.getLinksForVideo({'url': fav_data})

    def getArticleContent(self, cItem):
        printDBG("MoviesHDCO.getArticleContent [%s]" % cItem)

        title = cItem['title']
        icon = cItem['image']
        desc = cItem['post_content']
        otherInfo = {}
        otherInfo['year'] = cItem['year']
        otherInfo['duration'] = cItem['runtime']
        otherInfo['genre'] = cItem['genre']
        otherInfo['director'] = cItem['director']
        otherInfo['actors'] = cItem['actors']
        return [{'title': self.cleanHtmlStr(title), 'text': self.cleanHtmlStr(desc), 'images': [{'title': '', 'url': self.getFullUrl(icon)}], 'other_info': otherInfo}]

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

        self.cacheLinks = {}

    #MAIN MENU
        if name == None:
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})
        elif category == 'list_popular':
            self.listsTab(self.POPULAR_TAB, self.currItem)
    #MOVIES
        elif category == 'list_countries_filter':
            self.listFilters(self.currItem, 'countries', 'list_genres_filter')
        elif category == 'list_languages_filter':
            self.listFilters(self.currItem, 'languages', 'list_genres_filter')
        elif category == 'list_genres_filter':
            self.listFilters(self.currItem, 'genres', 'list_year_filter')
        elif category == 'list_year_filter':
            self.listFilters(self.currItem, 'years', 'list_orderby_filter')
        elif category == 'list_orderby_filter':
            self.listFilters(self.currItem, 'orderby', 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem)
        elif category == 'list_items2':
            self.listItems2(self.currItem)
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
        CHostBase.__init__(self, YifyTV(), True, [CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO])

    def withArticleContent(self, cItem):
        if cItem['type'] != 'video':
            return False
        return True
