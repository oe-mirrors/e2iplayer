# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm, MergeDicts, GetJSScriptFile
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute_ext, is_js_cached
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
###################################################

###################################################
# FOREIGN import
###################################################
import time
import re
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_unquote, urllib_quote
from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import urljoin
from Components.config import config, ConfigSelection, ConfigText, getConfigListEntry
###################################################


###################################################
# E2 GUI COMMPONENTS
###################################################
from Screens.MessageBox import MessageBox
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.movieshdco_sortby = ConfigSelection(default="date", choices=[("date", _("Lastest")), ("views", _("Most viewed")), ("duree", _("Longest")), ("rate", _("Top rated")), ("random", _("Random"))])
config.plugins.iptvplayer.cartoonhd_login = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.cartoonhd_password = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("login") + ":", config.plugins.iptvplayer.cartoonhd_login))
    optionList.append(getConfigListEntry(_("password") + ":", config.plugins.iptvplayer.cartoonhd_password))
    return optionList
###################################################


def gettytul():
    return 'https://cartoonhd.care/'


class CartoonHD(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'CartoonHD.tv', 'cookie': 'cartoonhdtv.cookie'})
        self.cacheFilters = {}
        self.cacheLinks = {}
        self.loggedIn = None
        self.DEFAULT_ICON_URL = 'https://cartoonhd.care/templates/cartoonhd/assets/images/logochd.png'

        self.HEADER = {'User-Agent': 'Mozilla/5.0', 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})

        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.MAIN_URL = None
        self.SEARCH_URL = None

    def selectDomain(self):
        domain = 'https://cartoonhd.care/'
        params = dict(self.defaultParams)
        params['max_data_size'] = False
        self.cm.getPage(domain, params)
        if 'url' in self.cm.meta:
            self.setMainUrl(self.cm.meta['url'])

        if self.MAIN_URL == None:
            self.MAIN_URL = domain

    def listMainMenu(self, cItem):
        if self.MAIN_URL == None:
            return
        MAIN_CAT_TAB = [{'category': 'new', 'title': 'Featured', 'url': self.getMainUrl()},
                        {'category': 'list_genres', 'title': 'Movies', 'url': self.getFullUrl('/full-movies')},
                        {'category': 'list_genres', 'title': 'TV shows', 'url': self.getFullUrl('/tv-shows')},
                        {'category': 'search', 'title': _('Search'), 'search_item': True},
                        {'category': 'search_history', 'title': _('Search history')}]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def _getToken(self, data):
        torName = self.cm.ph.getSearchGroups(data, "var token[\s]*=([^;]+?);")[0].strip()
        return self.cm.ph.getSearchGroups(data, '''var[\s]*{0}[\s]*=[\s]*['"]([^'^"]+?)['"]'''.format(torName))[0]

    def listSortNav(self, cItem, nextCategory):
        sts, data = self.cm.getPage(cItem['url'], self.defaultParams)
        if not sts:
            return
        data = self.cm.ph.getDataBeetwenMarkers(data, '<select name="sortnav"', '</select>', False)[1]
        data = re.compile('<option value="http[^"]+?/([^"^/]+?)"[^>]*?>([^<]+?)<').findall(data)
        tab = []
        for item in data:
            tab.append({'sort_by': item[0], 'title': item[1]})
        cItem = dict(cItem)
        cItem['category'] = nextCategory
        self.listsTab(tab, cItem)

    def listGenres(self, cItem, nextCategory):
        printDBG("CartoonHD.listGenres")

        sts, data = self.cm.getPage(cItem['url'], self.defaultParams)
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenMarkers(data, '"categories"', '</select>')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<option', '</option>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''value=['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'category': nextCategory, 'url': url, 'title': title})
            self.addDir(params)

    def listNewCategory(self, cItem, nextCategory):
        printDBG("CartoonHD.listNewCategory")

        sts, data = self.cm.getPage(cItem['url'], self.defaultParams)
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenMarkers(data, '<a>Featured</a>', '</ul>')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            if 'tv-calendar' in url:
                continue
            title = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'category': nextCategory, 'url': url, 'title': title})
            self.addDir(params)

    def listItems(self, cItem, nextCategory1, nextCategory2):
        printDBG("CartoonHD.listItems")
        page = cItem.get('page', 1)

        if page == 1:
            url = cItem['url'] + '/' + cItem.get('sort_by', '') + '/' + str(page)
        else:
            url = cItem['url']

        params = dict(self.defaultParams)
        params['header'] = self.AJAX_HEADER
        sts, data = self.cm.getPage(url, params)
        if not sts:
            return

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<a', '>', 'next-page-button'), ('</a', '>'))[1]
        nextPage = self.getFullUrl(self.cm.ph.getSearchGroups(nextPage, '''href=["']([^"^']+?)['"]''')[0])

        data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="flipBox"', '</main>', True)[1]
        data = data.split('</section>')
        if len(data):
            del data[-1]
        for item in data:
            icon = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'src="([^"]+?\.jpg[^"]*?)"')[0])
            desc = 'IMDb ' + self.cm.ph.getSearchGroups(item, '>([ 0-9.]+?)<')[0] + ', '
            desc += self.cleanHtmlStr(' '.join(self.cm.ph.getAllItemsBeetwenMarkers(item, '<p>', '</p>', False)))
            tmp = self.cm.ph.rgetAllItemsBeetwenMarkers(item, '</a>', '<a', True)
            url = ''
            for t in tmp:
                if url == '':
                    url = self.getFullUrl(self.cm.ph.getSearchGroups(t, '''href=["']([^"^']+?)['"]''')[0])
                title = self.cleanHtmlStr(t)
                if title != '':
                    break
            if url.startswith('http'):
                params = MergeDicts(cItem, {'good_for_fav': True, 'title': title, 'url': url, 'desc': desc, 'icon': icon})
                if '/series/' in url and '/episode/' not in url:
                    params['category'] = nextCategory2
                else:
                    params['category'] = nextCategory1
                self.addDir(params)

        if nextPage != '':
            params = dict(cItem)
            params.update({'title': _("Next page"), 'url': nextPage, 'page': page + 1})
            self.addDir(params)

    def _addTrailer(self, cItem, title, data):
        printDBG("CartoonHD._addTrailer")
        httpParams = dict(self.defaultParams)
        httpParams['header'] = {'Referer': self.cm.meta['url'], 'User-Agent': self.cm.HOST, 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json, text/javascript, */*; q=0.01', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'}

        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<a', '>', 'watch-trailer'), ('</a', '>'))[1]
        tmp = dict(re.compile('''\sdata\-([^=]+?)=['"]([^'^"]+?)['"]''').findall(tmp))

        sts, tmp = self.cm.getPage(self.getFullUrl('/ajax/trailer.php'), httpParams, tmp)
        if not sts:
            return
        try:
            tmp = json_loads(tmp)
            if tmp.get('valid'):
                url = self.getFullUrl(self.cm.ph.getSearchGroups(tmp['trailer'], '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0])
                if url:
                     self.addVideo(MergeDicts(cItem, {'title': title, 'url': url, 'prev_url': cItem['url']}))
        except Exception:
            printExc()

    def _updateDesc(self, cItem, data):
        desc = []
        descObj = self.getArticleContent(cItem, data)[0]
        for item in descObj['other_info']['custom_items_list']:
            desc.append(item[1])
        desc = ' | '.join(desc) + '[/br]' + descObj['text']
        return MergeDicts(cItem, {'desc': desc})

    def exploreItem(self, cItem):
        printDBG("CartoonHD.exploreItem")
        sts, data = self.cm.getPage(cItem['url'], self.defaultParams)
        if not sts:
            return
        cItem = self._updateDesc(cItem, data)

        self._addTrailer(cItem, '{0} - {1}'.format(cItem['title'], _('trailer')), data)
        linksTab = self.getLinksForVideo(cItem, data)
        if linksTab:
            self.addVideo(dict(cItem))

    def listSeasons(self, cItem, nextCategory):
        printDBG("CartoonHD.listSeasons")

        sts, data = self.cm.getPage(cItem['url'], self.defaultParams)
        if not sts:
            return
        cItem = self._updateDesc(cItem, data)

        data = self.cm.ph.getDataBeetwenMarkers(data, '<b>Season(s):</b>', '</div>', False)[1]
        data = re.compile('<a[^>]*?href="([^"]+?)"[^>]*?>([^>]+?)</a>').findall(data)
        for item in data:
            params = dict(cItem)
            url = self.getFullUrl(item[0])
            params.update({'url': url, 'title': _("Season") + ' ' + item[1], 'show_title': cItem['title'], 'category': nextCategory})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("CartoonHD.listEpisodes")

        sts, data = self.cm.getPage(cItem['url'], self.defaultParams)
        if not sts:
            return
        cItem = self._updateDesc(cItem, data)

        showTitle = cItem.get('show_title', '')

        self._addTrailer(cItem, '{0}, {1} - {2}'.format(showTitle, cItem['title'], _('trailer')), data)

        data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="episode', '</article>', False)[1]
        data = data.split('<div class="episode')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"#]+?)"')[0])
            desc = self.cm.ph.getDataBeetwenMarkers(item, '<p>', '</p>', False)[1]
            title = self.cm.ph.getSearchGroups(item, 'title="([^"]+?)"')[0]
            icon = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'data-src="([^"]+?)"')[0])
            if '' == icon:
                icon = cItem.get('icon', '')

            if url.startswith('http'):
                if showTitle != '':
                    title = showTitle + ' ' + title
                params = {'title': title, 'url': url, 'icon': icon, 'desc': desc}
                self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("CartoonHD.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))

        sts, data = self.cm.getPage(self.MAIN_URL, self.defaultParams)
        if not sts:
            return

        vars = self.cm.ph.getDataBeetwenMarkers(data, 'var ', '</script>')[1]
        if vars == '':
            return
        vars = vars[:-9]

        jsUrl = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<script[^>]+?src=['"]([^'^"]*?foxycomplete.js[^'^"]*?)['"]''')[0])
        if not self.cm.isValidUrl(jsUrl):
            return
        jsHash = jsUrl.rsplit('=', 1)[-1]

        js_execute_ext, is_js_cached
        if not is_js_cached('cartoonhd', jsHash):
            sts, jsdata = self.cm.getPage(jsUrl, self.defaultParams)
            if not sts:
                return
        else:
            jsdata = ''

        post_data = {'q': searchPattern, 'limit': 100, 'timestamp': str(int(time.time() * 1000))}
        try:
            js_params = [{'path': GetJSScriptFile('cartoonhd.byte')}]
            js_params.append({'code': vars})
            js_params.append({'name': 'cartoonhd', 'hash': jsHash, 'code': jsdata})
            ret = js_execute_ext(js_params)
            if ret['sts'] and 0 == ret['code']:
                decoded = ret['data'].strip()
                printDBG('DECODED DATA -> [%s]' % decoded)
                decoded = json_loads(decoded)
                self.SEARCH_URL = decoded.pop('url', None)
                post_data.update(decoded)
        except Exception:
            printExc()

        httpParams = dict(self.defaultParams)
        httpParams['header'] = {'Referer': self.MAIN_URL, 'User-Agent': self.cm.HOST, 'X-Requested-With': 'XMLHttpRequest', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'}
        sts, data = self.cm.getPage(self.SEARCH_URL, httpParams, post_data=post_data)
        if not sts:
            return
        printDBG(data)
        try:
            data = json_loads(data)
            for item in data:
                desc = item['meta']
                if 'movie' in desc.lower():
                    category = 'explore_item'
                elif 'tv show' in desc.lower():
                    category = 'list_seasons'
                else:
                    category = None

                if None != category:
                    title = item['title']
                    url = item['permalink'].replace('\\/', '/')
                    icon = item.get('image', '').replace('\\/', '/')
                    if '' != url:
                        params = {'good_for_fav': True, 'name': 'category', 'title': title, 'url': self.getFullUrl(url), 'desc': desc, 'icon': self.getFullUrl(icon), 'category': category}
                        if category == 'explore_item':
                            self.addVideo(params)
                        else:
                            self.addDir(params)
        except Exception:
            printExc()

    def getLinksForVideo(self, cItem, data=None):
        printDBG("CartoonHD.getLinksForVideo [%s]" % cItem)

        if not data and 1 == self.up.checkHostSupport(cItem['url']):
            return self.up.getVideoLinkExt(cItem['url'])

        def gettt():
            data = str(int(time.time()))
            b64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
            i = 0
            enc = ""
            tmp_arr = []
            mask = 0x3f
            while True:
                o1 = ord(data[i])
                i += 1
                if i < len(data):
                    o2 = ord(data[i])
                else:
                    o2 = 0
                i += 1
                if i < len(data):
                    o3 = ord(data[i])
                else:
                    o3 = 0
                i += 1
                bits = o1 << 16 | o2 << 8 | o3
                h1 = bits >> 18 & mask
                h2 = bits >> 12 & mask
                h3 = bits >> 6 & mask
                h4 = bits & mask
                tmp_arr.append(b64[h1] + b64[h2] + b64[h3] + b64[h4])
                if i >= len(data):
                    break
            enc = ''.join(tmp_arr)
            r = len(data) % 3
            if r > 0:
                fill = '==='
                enc = enc[0:r - 3] + fill[r:]
            return enc

        def getCookieItem(name):
            value = ''
            try:
                value = self.cm.getCookieItem(self.COOKIE_FILE, name)
            except Exception:
                printExc()
            return value

        urlTab = self.cacheLinks.get(cItem['url'], [])
        if len(urlTab):
            return urlTab
        self.cacheLinks = {}

        if not data:
            sts, data = self.cm.getPage(cItem['url'], self.defaultParams)
            if not sts:
                return []
            printDBG(">> url: %s" % self.cm.meta['url'])

        jsUrl = ''
        tmp = re.compile('''<script[^>]+?src=['"]([^'^"]*?videojs[^'^"^/]*?\.js(?:\?[^'^"]*?v=[0-9\.]+?)?)['"]''', re.I).findall(data)
        printDBG("TMP JS: %s" % tmp)
        for item in tmp:
            if '.min.' in item.rsplit('/', 1)[-1]:
                continue
            jsUrl = self.getFullUrl(item)

        if not self.cm.isValidUrl(jsUrl):
            printDBG(">>>>>>\n%s\n" % data)
            return []

        sts, jsUrl = self.cm.getPage(jsUrl, self.defaultParams)
        if not sts:
            return []

        jsUrl = self.cm.ph.getSearchGroups(jsUrl.split('getEpisodeEmb', 1)[-1], '''['"]([^'^"]*?/ajax/[^'^"]+?)['"]''')[0]
        printDBG("jsUrl [%s]" % jsUrl)
        if jsUrl == '':
            return []

        baseurl = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''var\s+?baseurl\s*=\s*['"]([^'^"]+?)['"]''')[0])
        printDBG("baseurl [%s]" % baseurl)
        if not self.cm.isValidUrl(baseurl):
            return []

        tor = self._getToken(data)
        elid = self.cm.ph.getSearchGroups(data, '''elid[\s]*=[\s]['"]([^"^']+?)['"]''')[0]
        if '' == elid:
            elid = self.cm.ph.getSearchGroups(data, 'data-id="([^"]+?)"')[0]
        if '' == elid:
            elid = self.cm.ph.getSearchGroups(data, 'data-movie="([^"]+?)"')[0]
        if '' == elid:
            return []

        if "movieInfo['season']" not in data and 'movieInfo["season"]' not in data:
            type = 'getMovieEmb'
        else:
            type = 'getEpisodeEmb'
        #if '/movie/' in cItem['url']:
        #    type = 'getMovieEmb'
        #else: type = 'getEpisodeEmb'

        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<select', '</select>', False)[1]
        hostings = []
        tmp = re.compile('<option[^>]*?value="([^"]+?)"[^>]*?>([^<]+?)</option>').findall(tmp)
        for item in tmp:
            hostings.append({'id': item[0], 'name': item[1]})

        httpParams = dict(self.defaultParams)
        httpParams['header'] = {'Referer': cItem['url'], 'User-Agent': self.cm.HOST, 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json, text/javascript, */*; q=0.01', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'}
        encElid = gettt()
        __utmx = getCookieItem('__utmx')
        httpParams['header']['Authorization'] = 'Bearer ' + urllib_unquote(__utmx)

        requestLinks = [urljoin(baseurl, jsUrl)]
        if 'class="play"' in data and 'id="updateSources"' not in data:
            requestLinks.append('ajax/embeds.php')

        #httpParams['header']['Cookie'] = '%s=%s; PHPSESSID=%s; flixy=%s;'% (elid, urllib_quote(encElid), getCookieItem('PHPSESSID'), getCookieItem('flixy'))
        for url in requestLinks:
            post_data = {'action': type, 'idEl': elid, 'token': tor, 'elid': urllib_quote(encElid), 'nopop': ''}
            sts, data = self.cm.getPage(url, httpParams, post_data)
            if not sts:
                continue
            printDBG('===============================================================')
            printDBG(data)
            printDBG('===============================================================')
            printDBG(hostings)
            try:
                keys = re.compile('"(_[0-9]+?)"').findall(data)
                data = json_loads(data)
                for key in list(data.keys()):
                    if key not in keys:
                        keys.append(key)
                for key in keys:
                    if key not in keys:
                        continue
                    url = data[key]['embed'].replace('\\/', '/')
                    url = self.cm.ph.getSearchGroups(url, '''src=['"]([^"^']+?)['"]''', 1, ignoreCase=True)[0]
                    name = data[key]['type']
                    if 'googlevideo.com' in url or 'googleusercontent.com' in url:
                        need_resolve = 0
                    elif 1 == self.up.checkHostSupport(url):
                        need_resolve = 1
                    else:
                        need_resolve = 0
                    if url.startswith('http'):
                        urlTab.append({'name': name, 'url': url, 'need_resolve': need_resolve})
            except Exception:
                printExc()
            if len(urlTab):
                break
        urlTab = urlTab[::-1]
        self.cacheLinks[cItem['url']] = urlTab
        return urlTab

    def getVideoLinks(self, videoUrl):
        printDBG("CartoonHD.getVideoLinks [%s]" % videoUrl)
        urlTab = []

        # mark requested link as used one
        if len(list(self.cacheLinks.keys())):
            key = list(self.cacheLinks.keys())[0]
            for idx in range(len(self.cacheLinks[key])):
                if videoUrl in self.cacheLinks[key][idx]['url']:
                    if not self.cacheLinks[key][idx]['name'].startswith('*'):
                        self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name']
                    break

        if self.cm.isValidUrl(videoUrl):
            urlTab = self.up.getVideoLinkExt(videoUrl)
        return urlTab

    def getArticleContent(self, cItem, data=None):
        printDBG("CartoonHD.getArticleContent [%s]" % cItem)
        retTab = []
        itemsList = []

        url = cItem.get('prev_url', cItem['url'])
        if data == None:
            self.tryTologin()
            sts, data = self.cm.getPage(url, self.defaultParams)
            if not sts:
                data = ''

        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<section', '>', 'info'), ('</section', '>'), False)[1]
        title = self.cm.ph.getDataBeetwenMarkers(tmp, '<h1', '</h1>')[1]
        eTtile = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(title, ('<span', '>', 'episode'), ('</span', '>'), False)[1])
        if eTtile:
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(title, ('<span', '>', 'title'), ('</span', '>'), False)[1])
            itemsList.append((_('Episode title'), eTtile))
        else:
            title = self.cleanHtmlStr(title)

        keysMap = {'rat': _('PEGI'), 'dur': _('Duration'), 'dat': _('Year'), 'net': _('Network')}
        raiting = []
        tmp = self.cm.ph.getDataBeetwenMarkers(tmp, '<p', '</p>')[1]
        tmp = self.cm.ph.rgetAllItemsBeetwenMarkers(tmp, '</span>', '<span')
        for item in tmp:
            key = self.cm.ph.getSearchGroups(item, '''class=['"]([^"^']+?)['"]''')[0]
            value = self.cleanHtmlStr(item)
            if key == '' or value == '':
                continue
            if 'rating' in key:
                raiting.append(value)
            key = keysMap.get(key)
            if not key:
                continue
            itemsList.append((key, value))

        if raiting:
            itemsList.append((_('Raiting'), ' '.join(raiting)))

        data = self.cm.ph.getDataBeetwenNodes(data, ('<section', '>', 'content'), ('</section', '>'), False)[1]
        icon = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'poster'), ('</div', '>'), False)[1]
        icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(icon, '''src=['"]([^"^']+?\.jpe?g(?:\?[^'^"]*?)?)['"]''')[0])

        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<p', '>', 'desc'), ('</p', '>'), False)[1])

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<p', '</p>')
        for item in data:
            item = item.split('</b>', 1)
            if len(item) != 2:
                continue
            key = self.cleanHtmlStr(item[0])
            value = []
            item = self.cm.ph.getAllItemsBeetwenMarkers(item[1], '<a', '</a>')
            for t in item:
                t = self.cleanHtmlStr(t)
                if t:
                    value.append(t)
            if key and value:
                itemsList.append((key, ', '.join(value)))

        if title == '':
            title = cItem['title']
        if icon == '':
            icon = cItem.get('icon', self.DEFAULT_ICON_URL)
        if desc == '':
            desc = cItem.get('desc', '')

        return [{'title': self.cleanHtmlStr(title), 'text': self.cleanHtmlStr(desc), 'images': [{'title': '', 'url': self.getFullUrl(icon)}], 'other_info': {'custom_items_list': itemsList}}]

    def tryTologin(self):
        printDBG('tryTologin start')
        self.selectDomain()

        login = config.plugins.iptvplayer.cartoonhd_login.value
        password = config.plugins.iptvplayer.cartoonhd_password.value

        rm(self.COOKIE_FILE)

        if '' == login.strip() or '' == password.strip():
            printDBG('tryTologin wrong login data')
            return False

        sts, data = self.cm.getPage(self.MAIN_URL, self.defaultParams)
        while sts:
            tor = self._getToken(data)
            post_data = {'username': login, 'password': password, 'action': 'login', 't': '', 'token': tor}
            params = dict(self.defaultParams)
            params['header'] = dict(params['header'])
            params['header']['Referer'] = self.getMainUrl()
            sts, data = self.cm.getPage(self.getFullUrl('/ajax/login.php'), params, post_data)
            printDBG(">> [%s]" % data)
            if sts:
                sts, data = self.cm.getPage(self.getMainUrl(), params)
            if sts and '>Logout<' in data:
                printDBG('tryTologin OK')
                break
            else:
                sts = False
            break

        if not sts:
            self.sessionEx.open(MessageBox, _('Login failed.'), type=MessageBox.TYPE_ERROR, timeout=10)
        printDBG('tryTologin failed')
        return sts

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        if None == self.loggedIn:
            self.loggedIn = self.tryTologin()

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.selectDomain()
            self.listMainMenu({'name': 'category'})
        elif category == 'new':
            self.listNewCategory(self.currItem, 'list_items')
        elif category == 'list_genres':
            self.listGenres(self.currItem, 'list_sortnav')
        elif category == 'list_sortnav':
            self.listSortNav(self.currItem, 'list_items')
            if len(self.currList) == 0:
                category = 'list_items'
        if category == 'list_items':
             self.listItems(self.currItem, 'explore_item', 'list_seasons')
        elif category == 'explore_item':
            self.exploreItem(self.currItem)
        elif category == 'list_seasons':
            self.listSeasons(self.currItem, 'list_episodes')
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
        CHostBase.__init__(self, CartoonHD(), True, [CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO])

    def withArticleContent(self, cItem):
        if cItem.get('prev_url') or cItem.get('type') == 'video' or cItem.get('category') in ('explore_item', 'list_seasons', 'list_episodes'):
            return True
        else:
            return False
