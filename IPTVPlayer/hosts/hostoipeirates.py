# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs import ph
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_urlencode, urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
###################################################
# FOREIGN import
###################################################
import re
###################################################


def gettytul():
    return 'https://oipeirates.tv/'


class OipeiratesOnline(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'oipeirates.online', 'cookie': 'oipeirates.online.cookie'})

        self.USER_AGENT = 'Mozilla/5.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})

        self.MAIN_URL = 'https://oipeirates.tv/'
        self.DEFAULT_ICON_URL = 'http://1.bp.blogspot.com/-EWw9aeMT-bo/U1_TUm3oM-I/AAAAAAAABiE/n07eIp9i6CI/s1600/oipeirates.jpg'

        self.defaultParams = {'with_metadata': True, 'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.cacheFilters = {}
        self.cacheLinks = {}

    def setMainUrl(self, url):
        if self.cm.isValidUrl(url):
            self.MAIN_URL = self.cm.getBaseUrl(url)

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)

        def _getFullUrl(url):
            if self.cm.isValidUrl(url):
                return url
            else:
                return urljoin(baseUrl, url)
        addParams['cloudflare_params'] = {'domain': self.up.getDomain(baseUrl), 'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT, 'full_url_handle': _getFullUrl}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def listMainMenu(self, cItem):
        printDBG("OipeiratesOnline.listMainMenu")
        sts, data = self.getPage(self.getMainUrl())
        if sts:
            self.setMainUrl(data.meta['url'])
            data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'navbarborder'), ('<div', '>', 'clear'))[1]
            data = re.compile('(<li[^>]*?>|</li>|<ul[^>]*?>|</ul>)').split(data)
            if len(data) > 1:
                try:
                    cTree = self.listToDir(data[1:-1], 0)[0]

                    title = self.cleanHtmlStr(cTree['list'][0]['list'][0]['dat'])
                    url = self.getFullUrl(self.cm.ph.getSearchGroups(cTree['list'][0]['list'][0]['dat'], '''href=['"]([^'^"]+?)['"]''')[0])
                    params = dict(cItem)
                    params.update({'good_for_fav': False, 'type': 'category', 'category': 'list_sort', 'title': title, 'url': url})
                    self.addDir(params)

                    params = dict(cItem)
                    params['c_tree'] = cTree['list'][0]['list'][1]
                    params['category'] = 'list_categories'
                    self.listCategories(params, 'list_items')
                except Exception:
                    printExc()

        MAIN_CAT_TAB = [{'category': 'search', 'title': _('Search'), 'search_item': True},
                        {'category': 'search_history', 'title': _('Search history')}]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listCategories(self, cItem, nextCategory):
        printDBG("OipeiratesOnline.listCategories")
        try:
            cTree = cItem['c_tree']
            for item in cTree['list']:
                title = self.cleanHtmlStr(item['dat'])
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item['dat'], '''href=['"]([^'^"]+?)['"]''')[0])
                if 'facebook' in url:
                    break
                elif 'list' not in item:
                    if self.cm.isValidUrl(url) and title != '':
                        params = dict(cItem)
                        params.update({'good_for_fav': False, 'category': nextCategory, 'title': title, 'url': url})
                        self.addDir(params)
                elif len(item['list']) == 1 and title != '':
                    obj = item['list'][0]
                    if url != '' and 'list' in obj:
                        obj['list'].insert(0, {'dat': '<a href="%s">%s</a>' % (url, _('--All--'))})
                    params = dict(cItem)
                    params.update({'good_for_fav': False, 'c_tree': obj, 'title': title, 'url': url})
                    self.addDir(params)
        except Exception:
            printExc()

    def listMainItems(self, cItem, nextCategory):
        printDBG("OipeiratesOnline.listMainItems [%s]" % cItem)
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<h2', '>', 'h1'), ('<div', '>', 'cleared'))
        for item in data:
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''\ssrc=['"]([^'^"]+?)['"]''', 1, True)[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'header-text'), ('</div', '>'))[1])
            method = self.cm.ph.getSearchGroups(item, '''data\-navigateto=['"]([^'^"]+?)['"]''')[0]
            param = self.cm.ph.getSearchGroups(item, '''data\-navigateparam=['"]([^'^"]+?)['"]''')[0]
            url = self.getFullUrl('/%s/%s' % (method, param))
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'icon': icon, 'f_method': method, 'f_param': param})
            self.addDir(params)

    def listSort(self, cItem, nextCategory):
        printDBG("OipeiratesOnline.listSort")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'filmborder'), ('</ul', '>'), False)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
        for item in data:
            title = self.cleanHtmlStr(item)
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            params = dict(cItem)
            params.update({'good_for_fav': False, 'category': nextCategory, 'title': title, 'url': url})
            self.addDir(params)

    def listItems(self, cItem, nextCategory='explore_item'):
        printDBG("OipeiratesOnline.listItems")
        page = cItem.get('page', 0)
        cItem = dict(cItem)
        ajaxurl = ''
        query = cItem.pop('query', {})

        if page == 0:
            url = cItem['url']
            if 'url_suffix' in cItem:
                url += cItem['url_suffix']

            sts, data = self.getPage(url)
            if not sts:
                return

            tmp = ph.find(data, ('<div', '>', 'ajax-load-more'), '</div>')[1]
            tmp = re.compile('''data\-([^=]+?)=['"]([^'^"]+?)['"]''').findall(tmp)
            for item in tmp:
                if item[0].startswith('alm-'):
                    item[0] = item[0][4:]
                query[item[0].replace('-', '_')] = item[1]

            if query:
                tmp = ph.search(data, '''var\s+?alm_localize=\s*?(\{[^;]+?);''')[0]
                try:
                    tmp = json_loads(tmp)
                    query['alm_nonce'] = tmp['alm_nonce']
                    ajaxurl = self.getFullUrl(tmp['ajaxurl'], self.cm.meta['url'])
                except Exception:
                    printExc()
        else:
            query.update({'page': page, 'seo_start_page': page})

            url = cItem['ajaxurl'] + '?action=alm_query_posts&query_type=standard&' + urllib_urlencode(query)
            sts, data = self.getPage(url)
            if not sts:
                return
            printDBG(data)
            try:
                tmp = json_loads(data)
                data = tmp['html']
                if not data:
                    data = ''
                if tmp['meta']['postcount'] == int(query['posts_per_page']):
                    if tmp['meta']['totalposts'] > (page + 1) * int(query['posts_per_page']):
                        ajaxurl = cItem['ajaxurl']
            except Exception:
                printExc()

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'moviefilm'), ('</div', '>'), False)
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0])
            icon = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'src="([^"]+?)"')[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'alt="([^"]+?)"')[0])
            if url != '':
                params = dict(cItem)
                params.update({'category': nextCategory, 'good_for_fav': True, 'title': title, 'url': url, 'icon': icon})
                self.addDir(params)

        if ajaxurl and query:
            printDBG(ajaxurl)
            printDBG(query)
            params = dict(cItem)
            params.update({'title': _("Next page"), 'page': page + 1, 'ajaxurl': ajaxurl, 'query': query})
            self.addDir(params)

    def exploreItem(self, cItem):
        printDBG("OipeiratesOnline.exploreItem")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, '<meta[^>]*?property="og:description"[^>]*?content="([^"]+?)"')[0])
        title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, '<meta[^>]*?property="og:title"[^>]*?content="([^"]+?)"')[0])
        if '' == title:
            title = cItem['title']

        # trailer link extraction
        trailerMarker = '/trailer'
        trailer = ph.find(data, trailerMarker, '</iframe>', flags=ph.I | ph.START_E)[1]
        if not trailer:
            trailer = ph.find(data, ('<iframe', '>', 'youtube'), '</iframe>', flags=ph.I | ph.START_E)[1]
        trailer = ph.search(trailer, ph.IFRAME_SRC_URI_RE)[1]
        if trailer.startswith('//'):
            trailer = 'http:' + trailer
        if trailer.startswith('http'):
            params = dict(cItem)
            params['title'] = 'TRAILER'
            params['mode'] = 'trailer'
            params['links'] = [{'name': 'TRAILER', 'url': trailer, 'need_resolve': 1}]
            params['desc'] = desc
            self.addVideo(params)

        # check
        ms1 = '<b>ΠΕΡΙΛΗΨΗ</b>'
        if ms1 in data:
            m1 = ms1
        elif trailerMarker in data:
            m1 = trailerMarker
        else:
            m1 = '<!-- END TAG -->'
        sts, linksData = self.cm.ph.getDataBeetwenMarkers(data, m1, 'facebok', False, False)
        if not sts:
            return
        seasonMarkerObj = re.compile(">\s*season|>\s*σεζόν")
        linksDataLower = ensure_str(linksData).lower()

        mode = cItem.get('mode', 'unknown')
        if '-collection' in cItem['url']:
            mode = 'collect_item'
            spTab = [re.compile('<b>'), re.compile('<div[\s]+class="separator"[\s]+style="text-align\:[\s]+center;">'), re.compile('<div[\s]+style="text-align\:[\s]+center;">')]
            for sp in spTab:
                if None != sp.search(linksData):
                    break

            collectionItems = sp.split(linksData)
            if len(collectionItems) > 0:
                del collectionItems[0]
            linksData = ''
            for item in collectionItems:
                itemTitle = item.find('<')
                if itemTitle < 0:
                    continue
                itemTitle = self.cleanHtmlStr(item[:itemTitle])
                linksData = re.compile('<a[^>]*?href="([^"]+?)"[^>]*?>').findall(item)
                links = []
                for itemUrl in linksData:
                    if 1 != self.up.checkHostSupport(itemUrl):
                        continue
                    links.append({'name': self.up.getHostName(itemUrl), 'url': itemUrl, 'need_resolve': 1})
                if len(links):
                    params = dict(cItem)
                    params.update({'title': itemTitle, 'mode': mode, 'links': links, 'desc': desc})
                    self.addVideo(params)
        elif seasonMarkerObj.search(linksDataLower):
            # find all links for this season
            eLinks = {}
            episodes = []

            idx = 0
            first = True
            while True:
                if idx == -1:
                    break
                prevIdx = idx

                match = seasonMarkerObj.search(linksDataLower[idx:])
                if match:
                    idx += match.start(0)
                else:
                    idx = -1
                if prevIdx == 0:
                    continue
                if idx > -1:
                    idx += len(match.group(0))
                    item = linksData[prevIdx:idx]
                else:
                    item = linksData[prevIdx:]

                seasonID = item.find('<')
                if seasonID < 0:
                    continue
                seasonID = item[:seasonID + 1]
                seasonID = self.cm.ph.getSearchGroups(seasonID, '([0-9]+?)[^0-9]')[0]
                if '' == seasonID:
                    continue
                episodesData = re.compile('<a[^>]*?href="([^"]+?)"[^>]*?>([^<]+?)</a>').findall(item)
                for eItem in episodesData:
                    eUrl = eItem[0]
                    eID = self.cleanHtmlStr(eItem[1].replace(chr(160), ' '))
                    if eUrl.startswith('//'):
                        eUrl = self.getFullUrl(eUrl)
                    if 1 != self.up.checkHostSupport(eUrl):
                        continue

                    linksID = '- s{0}e{1}'.format(seasonID.zfill(2), eID.zfill(2))
                    linksID = linksID.strip()
                    if linksID not in eLinks:
                        eLinks[linksID] = []
                        episodes.append({'linksID': linksID, 'episode': eID, 'season': seasonID})
                    eLinks[linksID].append({'name': self.up.getHostName(eUrl), 'url': eUrl, 'need_resolve': 1})

            for item in episodes:
                linksID = item['linksID']
                if len(eLinks[linksID]):
                    params = dict(cItem)
                    params.update({'title': title + ' ' + linksID, 'mode': mode, 'episode': item['episode'], 'season': item['season'], 'links': eLinks[linksID], 'desc': desc})
                    self.addVideo(params)
        else:
            links = self.getLinksForMovie(linksData)
            if len(links):
                params = dict(cItem)
                params['mode'] = 'movie'
                params['links'] = links
                params['desc'] = desc
                self.addVideo(params)

    def getLinksForMovie(self, data):
        urlTab = []
        linksData = re.compile('<a[^>]*?href="([^"]+?)"[^>]*?>([^<]*?)<').findall(data)
        for item in linksData:
            url = item[0]
            title = item[1]
            # only supported hosts will be displayed
            if 1 != self.up.checkHostSupport(url):
                continue

            name = self.up.getHostName(url)
            if url.startswith('//'):
                url += 'http'
            if url.startswith('http'):
                urlTab.append({'name': title + ': ' + name, 'url': url, 'need_resolve': 1})
        return urlTab

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("OipeiratesOnline.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.getMainUrl()
        cItem['url_suffix'] = '?s=' + urllib_quote_plus(searchPattern)
        cItem['mode'] = 'search'
        self.listItems(cItem)

    def getLinksForVideo(self, cItem):
        printDBG("OipeiratesOnline.getLinksForVideo [%s]" % cItem)
        # Use Season and Episode information when exist for cache index
        idx = cItem['mode'] + cItem['url'] + cItem.get('season', '') + cItem.get('episode', '')
        urlTab = self.cacheLinks.get(idx, [])
        if len(urlTab):
            return urlTab
        self.cacheLinks = {}

        urlTab = cItem.get('links', [])

        self.cacheLinks[idx] = urlTab
        return urlTab

    def getVideoLinks(self, videoUrl):
        printDBG("OipeiratesOnline.getVideoLinks [%s]" % videoUrl)
        urlTab = []

        if videoUrl.startswith('http'):
            urlTab = self.up.getVideoLinkExt(videoUrl)
        return urlTab

    def getArticleContent(self, cItem, data=None):
        printDBG("OipeiratesOnline.getArticleContent [%s]" % cItem)
        retTab = []
        otherInfo = {}

        if data == None:
            url = cItem.get('prev_url', cItem['url'])
            sts, data = self.getPage(url)
            if not sts:
                data = ''

        title = cItem['title']

        descMarker = 'ΠΕΡΙΛΗΨΗ'
        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<span', '</span>', descMarker), ('<a', '>'), False)[1])
        data = self.cm.ph.getDataBeetwenNodes(data, ('<script', '>', 'oipeirates/vp'), ('<img', '>'))[1]
        icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(data, '''<img[^>]+?src=['"]([^'^"]+?(?:\.jpe?g|\.png)(?:\?[^'^"]*?)?)['"]''')[0])
        t = self.cleanHtmlStr(data.split('</div>', 1)[-1])
        if t != '' and t != title:
            otherInfo['alternate_title'] = t
        if icon == '':
            icon = cItem['icon']
        return [{'title': self.cleanHtmlStr(title), 'text': self.cleanHtmlStr(desc), 'images': [{'title': '', 'url': self.getFullUrl(icon)}], 'other_info': otherInfo}]

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []
        self.currItem = dict(self.currItem)
        self.currItem.pop('good_for_fav', None)

    #MAIN MENU
        if name == None:
            self.listMainMenu({'name': 'category'})
        elif category == 'list_main_items':
            self.listMainItems(self.currItem, 'list_items')
        elif category == 'list_categories':
            self.listCategories(self.currItem, 'list_items')
        elif category == 'list_sort':
            self.listSort(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem)
    #EXPLORE ITEM
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
        CHostBase.__init__(self, OipeiratesOnline(), True, favouriteTypes=[])

    def withArticleContent(self, cItem):
        if cItem.get('type', 'video') != 'video' and cItem.get('category', 'unk') != 'explore_item':
            return False
        return True
