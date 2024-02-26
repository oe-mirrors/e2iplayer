# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs import ph
###################################################

###################################################
# FOREIGN import
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import urljoin
from Components.config import config, ConfigSelection, ConfigText, getConfigListEntry
###################################################


###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.gomovies_proxy = ConfigSelection(default="None", choices=[("None", _("None")),
                                                                                        ("proxy_1", _("Alternative proxy server (1)")),
                                                                                        ("proxy_2", _("Alternative proxy server (2)"))])
config.plugins.iptvplayer.gomovies_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.gomovies_proxy))
    if config.plugins.iptvplayer.gomovies_proxy.value == 'None':
        optionList.append(getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.gomovies_alt_domain))
    return optionList
###################################################


def gettytul():
    return 'https://123movieshd.sc/'


class GoMovies(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': '123movieshd', 'cookie': '123movieshd.cookie'})
        self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.DEFAULT_ICON_URL = 'https://123movieshd.sc/wp-content/themes/assets/images/gomovies-logo-light.png'
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})
        self.MAIN_URL = None
        self.cacheFilters = {}
        self.cacheLinks = {}
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)

        proxy = config.plugins.iptvplayer.gomovies_proxy.value
        if proxy != 'None':
            if proxy == 'proxy_1':
                proxy = config.plugins.iptvplayer.alternative_proxy1.value
            else:
                proxy = config.plugins.iptvplayer.alternative_proxy2.value
            addParams = dict(addParams)
            addParams.update({'http_proxy': proxy})

        def _getFullUrl(url):
            if self.cm.isValidUrl(url):
                return url
            else:
                return urljoin(baseUrl, url)

        addParams['cloudflare_params'] = {'domain': self.up.getDomain(baseUrl), 'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT, 'full_url_handle': _getFullUrl}
        sts, data = self.cm.getPageCFProtection(baseUrl, addParams, post_data)
        return sts, data

    def getFullIconUrl(self, url):
        url = self.getFullUrl(url)
        proxy = config.plugins.iptvplayer.gomovies_proxy.value
        if proxy != 'None':
            if proxy == 'proxy_1':
                proxy = config.plugins.iptvplayer.alternative_proxy1.value
            else:
                proxy = config.plugins.iptvplayer.alternative_proxy2.value
            url = strwithmeta(url, {'iptv_http_proxy': proxy})

        cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE)
        return strwithmeta(url, {'Cookie': cookieHeader, 'User-Agent': self.USER_AGENT})

    def selectDomain(self):
        domains = ['https://123movieshd.sc/', 'https://www3.123movieshub.sc/', 'https://www3.gomovies.sc/']
        domain = config.plugins.iptvplayer.gomovies_alt_domain.value.strip()
        if self.cm.isValidUrl(domain):
            if domain[-1] != '/':
                domain += '/'
            domains.insert(0, domain)

        for domain in domains:
            sts, data = self.getPage(domain)
            if sts:
                if 'genre/action' in data:
                    self.setMainUrl(self.cm.meta['url'])
                    break
                else:
                    continue

            if self.MAIN_URL != None:
                break

        if self.MAIN_URL == None:
            self.MAIN_URL = domains[0]

        self.DEFAULT_ICON_URL = self.getFullIconUrl('/wp-content/themes/assets/images/gomovies-logo-light.png')

        self.SEARCH_URL = self.MAIN_URL + 'movie/search'

    def listMain(self, cItem):
        printDBG("GoMovies.listMain")
        if self.MAIN_URL == None:
            self.selectDomain()
        MAIN_CAT_TAB = [{'category': 'list_filter_genre', 'title': 'Movies', 'url': self.getFullUrl('/movie/filter/movies/')},
                        {'category': 'list_filter_genre', 'title': 'TV-Series', 'url': self.getFullUrl('/movie/filter/seasons/')},
                        {'category': 'search', 'title': _('Search'), 'search_item': True, },
                        {'category': 'search_history', 'title': _('Search history'), }
                       ]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def fillCacheFilters(self):
        self.cacheFilters = {}

        sts, data = self.getPage(self.getFullUrl('/movies/'))
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        # get sort by
        self.cacheFilters['sort_by'] = []
        tmp = self.cm.ph.getDataBeetwenMarkers(data, 'Sort by</span>', '</ul>', False)[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li', '</li>', withMarkers=True, caseSensitive=False)
        for item in tmp:
            value = self.cm.ph.getSearchGroups(item, '''filterMovies\(\s*?['"]([^'^"]+?)['"]''')[0]
            self.cacheFilters['sort_by'].append({'sort_by': value, 'title': self.cleanHtmlStr(item)})

        for filter in [{'key': 'quality', 'marker': 'Quality</span>'},
                       {'key': 'genre', 'marker': 'Genre</span>'},
                       {'key': 'country', 'marker': 'Country</span>'},
                       {'key': 'year', 'marker': 'Release</span>'}]:
            self.cacheFilters[filter['key']] = []
            tmp = self.cm.ph.getDataBeetwenMarkers(data, filter['marker'], '</ul>', False)[1]
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li', '</li>', withMarkers=True, caseSensitive=False)
            allItemAdded = False
            for item in tmp:
                value = self.cm.ph.getSearchGroups(item, 'value="([^"]+?)"')[0]
                self.cacheFilters[filter['key']].append({filter['key']: value, 'title': self.cleanHtmlStr(item)})
                if value == 'all':
                    allItemAdded = True
            if not allItemAdded:
                self.cacheFilters[filter['key']].insert(0, {filter['key']: 'all', 'title': 'All'})

        printDBG(self.cacheFilters)

    def listFilters(self, cItem, filter, nextCategory):
        printDBG("GoMovies.listFilters")
        if {} == self.cacheFilters:
            self.fillCacheFilters()

        cItem = dict(cItem)
        cItem['category'] = nextCategory
        self.listsTab(self.cacheFilters.get(filter, []), cItem)

    def listItems(self, cItem, nextCategory=None):
        printDBG("GoMovies.listItems [%s]" % cItem)
        url = cItem['url']
        page = cItem.get('page', 1)
        if page == 1:
            if 'search' not in cItem:
                # var url = 'https://www3.123movieshub.sc/movie/filter/' + type + '/' + sortby + '/' + genres + '/' + countries + '/' + year + '/' + quality + '/';
                url += '/{0}/{1}/{2}/{3}/{4}'.format(cItem['sort_by'], cItem['genre'], cItem['country'], cItem['year'], cItem['quality'])

        sts, data = self.getPage(url)
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        if '/search' in url and 'recaptcha-search' in data:
            SetIPTVPlayerLastHostError(_('Functionality protected by Google reCAPTCHA!'))

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'pagination'), ('</ul', '>'), False)[1]
        nextPage = self.cm.ph.getSearchGroups(nextPage, '''<a[^>]+?href=['"]([^"^']+?)['"][^>]*?>%s<''' % (page + 1))[0]

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'item'), ('</div', '>'), False)
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, 'data\-original="([^"]+?)"')[0])

            movieId = self.cm.ph.getSearchGroups(item, 'data-movie-id="([^"]+?)"')[0]
            if icon == '':
                icon = cItem.get('icon', '')
            desc = self.cleanHtmlStr(item)
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h2', '</h2>')[1])
            if title == '':
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'title="([^"]+?)"')[0])
            if title == '':
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'alt="([^"]+?)"')[0])
            if url.startswith('http'):
                params = dict(cItem)
                params.update({'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'movie_id': movieId, 'desc': desc, 'info_url': url, 'icon': icon})
                self.addDir(params)

        if nextPage != '':
            params = dict(cItem)
            params.update({'title': _("Next page"), 'url': self.getFullUrl(nextPage), 'page': page + 1})
            self.addDir(params)

    def exploreItem(self, cItem):
        printDBG("GoMovies.exploreItem")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        # trailer
        trailerUrl = ph.search(data, '''trailer['"]?\s*?:\s*?['"](https?://[^'^"]+?youtube[^'^"]+?)['"]''')[0]
        if trailerUrl != '' and not trailerUrl.endswith('/'):
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': '%s : %s' % (cItem['title'], _('trailer')), 'url': trailerUrl})
            self.addVideo(params)

        playerUrl = ph.find(data, ('<a', '>', 'watching('), '</a>')[1]
        playerUrl = self.getFullUrl(ph.getattr(playerUrl, 'href'))

        params = dict(self.defaultParams)
        params['header'] = dict(params['header'])
        params['header']['Referer'] = self.cm.meta['url']
        sts, data = self.getPage(playerUrl, params)
        if not sts:
            return

        titlesTab = []
        self.cacheLinks = {}

        data = ph.findall(data, ('<div', '>', 'server-'), ('<div', '>', 'clearfix'))
        for tmp in data:
            serverName = ph.clean_html(ph.find(tmp, '<strong', '</strong>')[1])
            serverId = ph.search(tmp, '''server\-([0-9]+)''')[0]
            tmp = ph.findall(tmp, '<a', '</a>')
            for item in tmp:
                title = ph.clean_html(item)
                id = ph.getattr(item, 'sid')
                playerData = ph.search(item, '''data\-([^=]+?)=['"]([^'^"]+?)['"]''')
                if 'https://mystream.streamango.to/' in playerData[1]:
                    playerData[1] = playerData[1].replace('https://mystream.streamango.to/', '')
                if playerData[0] == 'strgo':
                    url = 'https://vidload.co/player/' + playerData[1]
                elif playerData[0] == 'onlystream':
                    url = 'https://vidoo.tv/e/' + playerData[1]
                elif playerData[0] == 'svbackup':
                    url = 'https://embed.mystream.to/' + playerData[1]
                else:
                    url = self.getFullUrl(playerData[1])

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
        printDBG("GoMovies.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        if self.MAIN_URL == None:
            self.selectDomain()
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('/browse-word/%s/' % urllib_quote_plus(searchPattern))
        cItem.update({'search': True, 'category': 'list_items'})
        self.listItems(cItem, 'explore_item')

    def getLinksForVideo(self, cItem):
        printDBG("GoMovies.getLinksForVideo [%s]" % cItem)
        key = cItem.get('links_key', '')
        if key == '':
            return self.up.getVideoLinkExt(cItem['url'])

        return self.cacheLinks.get(key, [])

    def getVideoLinks(self, videoUrl):
        printDBG("GoMovies.getVideoLinks [%s]" % videoUrl)
        urlTab = []

        # mark requested link as used one
        if len(list(self.cacheLinks.keys())):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if videoUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name']
                        break

        if self.cm.isValidUrl(videoUrl):
            return self.up.getVideoLinkExt(videoUrl)

        return urlTab

    def getArticleContent(self, cItem):
        printDBG("GoMovies.getArticleContent [%s]" % cItem)
        retTab = []

        sts, data = self.getPage(cItem.get('url', ''))
        if not sts:
            return retTab

        title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, '<meta property="og:title"[^>]+?content="([^"]+?)"')[0])
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, '<meta property="og:description"[^>]+?content="([^"]+?)"')[0])
        icon = self.getFullUrl(self.cm.ph.getSearchGroups(data, '<meta property="og:image"[^>]+?content="([^"]+?)"')[0])

        if title == '':
            title = cItem['title']
        if desc == '':
            desc = cItem.get('desc', '')
        if icon == '':
            icon = cItem.get('icon', '')

        descData = self.cm.ph.getDataBeetwenMarkers(data, '<div class="mvic-info">', '<div class="clearfix">', False)[1]
        descData = self.cm.ph.getAllItemsBeetwenMarkers(descData, '<p', '</p>')
        descTabMap = {"Director": "director",
                      "Actor": "actors",
                      "Genre": "genre",
                      "Country": "country",
                      "Release": "released",
                      "Duration": "duration",
                      "Quality": "quality",
                      "IMDb": "rated"}

        otherInfo = {}
        for item in descData:
            item = item.split('</strong>')
            if len(item) < 2:
                continue
            key = self.cleanHtmlStr(item[0]).replace(':', '').strip()
            val = self.cleanHtmlStr(item[1])
            if key == 'IMDb':
                val += ' IMDb'
            if key in descTabMap:
                try:
                    otherInfo[descTabMap[key]] = val
                except Exception:
                    continue

        if '' != cItem.get('movie_id', ''):
            rating = ''
            sts, data = self.getPage(self.getFullUrl('ajax/movie_rate_info/' + cItem['movie_id']))
            if sts:
                rating = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div id="movie-mark"', '</label>', True)[1])
            if rating != '':
                otherInfo['rating'] = self.cleanHtmlStr(rating)

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

        printDBG("handleService: || name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.fillCacheFilters()
            self.listMain({'name': 'category'})
        elif category.startswith('list_filter_'):
            filter = category.replace('list_filter_', '')
            if filter == 'genre':
                self.listFilters(self.currItem, filter, 'list_filter_country')
            elif filter == 'country':
                self.listFilters(self.currItem, filter, 'list_filter_year')
            elif filter == 'year':
                self.listFilters(self.currItem, filter, 'list_filter_quality')
            elif filter == 'quality':
                self.listFilters(self.currItem, filter, 'list_filter_sort_by')
            elif filter == 'sort_by':
                self.listFilters(self.currItem, filter, 'list_items')
        if category == 'list_items':
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
        CHostBase.__init__(self, GoMovies(), True, [])

    def withArticleContent(self, cItem):
        if cItem.get('type', 'video') != 'video' and cItem.get('category', '') != 'explore_item':
            return False
        return True
