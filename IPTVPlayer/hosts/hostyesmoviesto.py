# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
###################################################

###################################################
# FOREIGN import
###################################################
import time
import re
import urllib
from urlparse import urlparse
try:
    import json
except Exception:
    import simplejson as json
from Components.config import config, ConfigSelection, ConfigText, getConfigListEntry
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.yesmovies_proxy = ConfigSelection(default="None", choices=[("None", _("None")),
                                                                                        ("proxy_1", _("Alternative proxy server (1)")),
                                                                                        ("proxy_2", _("Alternative proxy server (2)"))])
config.plugins.iptvplayer.yesmovies_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.yesmovies_proxy))
    if config.plugins.iptvplayer.yesmovies_proxy.value == 'None':
        optionList.append(getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.yesmovies_alt_domain))
    return optionList
###################################################


def gettytul():
    return 'https://yesmovies.to/'


class YesMovies(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'yesmovies.to', 'cookie': 'yesmovies.to.cookie'})
        self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.DEFAULT_ICON_URL = 'https://cdn.yescdn.ru/images/logo.png'
        self.HEADER = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0', 'DNT': '1', 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})
        self.MAIN_URL = None
        self.cacheFilters = {}
        self.cacheLinks = {}
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

    def getPage(self, url, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)

        proxy = config.plugins.iptvplayer.yesmovies_proxy.value
        if proxy != 'None':
            if proxy == 'proxy_1':
                proxy = config.plugins.iptvplayer.alternative_proxy1.value
            else:
                proxy = config.plugins.iptvplayer.alternative_proxy2.value
            addParams = dict(addParams)
            addParams.update({'http_proxy': proxy})

        return self.cm.getPage(url, addParams, post_data)

    def getFullIconUrl(self, url):
        url = self.getFullUrl(url)
        proxy = config.plugins.iptvplayer.yesmovies_proxy.value
        if proxy != 'None':
            if proxy == 'proxy_1':
                proxy = config.plugins.iptvplayer.alternative_proxy1.value
            else:
                proxy = config.plugins.iptvplayer.alternative_proxy2.value
            url = strwithmeta(url, {'iptv_http_proxy': proxy})
        return url

    def selectDomain(self):
        domains = ['https://yesmovies.to/', 'https://yesmovies.org/', 'https://yesmovies.net/']
        domain = config.plugins.iptvplayer.yesmovies_alt_domain.value.strip()
        if self.cm.isValidUrl(domain):
            if domain[-1] != '/':
                domain += '/'
            domains.insert(0, domain)

        for domain in domains:
            sts, data = self.getPage(domain)
            if sts and 'movie/filter' in data:
                self.setMainUrl(self.cm.meta['url'])
                break

        if self.MAIN_URL == None:
            self.MAIN_URL = 'https://yesmovies.to/'

    def listMainMenu(self, cItem):
        if self.MAIN_URL == None:
            return
        MAIN_CAT_TAB = [{'category': 'list_filter_genre', 'title': 'Movies', 'url': self.getFullUrl('movie/filter/movie')},
                        {'category': 'list_filter_genre', 'title': 'TV-Series', 'url': self.getFullUrl('movie/filter/series')},
                        {'category': 'search', 'title': _('Search'), 'search_item': True, },
                        {'category': 'search_history', 'title': _('Search history'), }
                       ]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def fillCacheFilters(self):
        self.cacheFilters = {}

        sts, data = self.getPage(self.getFullUrl('movie/filter/all'), self.defaultParams)
        if not sts:
            return

        # get sort by
        self.cacheFilters['sort_by'] = []
        tmp = self.cm.ph.getDataBeetwenMarkers(data, 'Sort by</span>', '</ul>', False)[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li', '</li>', withMarkers=True, caseSensitive=False)
        for item in tmp:
            value = self.cm.ph.getSearchGroups(item, 'href="[^"]+?/filter/all/([^"^/]+?)/')[0]
            self.cacheFilters['sort_by'].append({'sort_by': value, 'title': self.cleanHtmlStr(item)})

        for filter in [{'key': 'quality', 'marker': 'quality-list'},
                       {'key': 'genre', 'marker': 'genre-list'},
                       {'key': 'country', 'marker': 'country-list'},
                       {'key': 'year', 'marker': 'release-list'}]:
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
        printDBG("YesMovies.listFilters")
        if {} == self.cacheFilters:
            self.fillCacheFilters()

        cItem = dict(cItem)
        cItem['category'] = nextCategory
        self.listsTab(self.cacheFilters.get(filter, []), cItem)

    def listItems(self, cItem, nextCategory=None):
        printDBG("YesMovies.listItems")
        url = cItem['url']
        page = cItem.get('page', 1)
        if '/search' not in url:
            url += '/{0}/{1}/{2}/{3}/{4}/{5}'.format(cItem['sort_by'], cItem['genre'], cItem['country'], cItem['year'], 'all', cItem['quality'])

        if page > 1:
            url = url + '/page-{0}'.format(page)
        url += '.html'
        sts, data = self.getPage(url)
        if not sts:
            return

        nextPage = self.cm.ph.getDataBeetwenMarkers(data, 'pagination', '</ul>', False)[1]
        if '' != self.cm.ph.getSearchGroups(nextPage, 'page\-(%s)[^0-9]' % (page + 1))[0]:
            nextPage = True
        else:
            nextPage = False

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="ml-item">', '</a>', withMarkers=True)
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0])
            icon = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'data-original="([^"]+?)"')[0])
            dataUrl = self.cm.ph.getSearchGroups(item, 'data-url="([^"]+?)"')[0]
            if icon == '':
                icon = cItem.get('icon', '')
            desc = self.cleanHtmlStr(item)
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h2', '</h2>')[1])
            if title == '':
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'title="([^"]+?)"')[0])
            if title == '':
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'alt="([^"]+?)"')[0])
            if url.startswith('http'):
                params = {'good_for_fav': True, 'title': title, 'url': url, 'data_url': dataUrl, 'desc': desc, 'info_url': url, 'icon': icon}
                if '-season-' not in url and 'class="mli-eps"' not in item:
                    self.addVideo(params)
                else:
                    params['category'] = nextCategory
                    params2 = dict(cItem)
                    params2.update(params)
                    self.addDir(params2)

        if nextPage and len(self.currList) > 0:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _("Next page"), 'page': page + 1})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("YesMovies.listEpisodes")

        tab = self.getLinksForVideo(cItem, True)
        episodeKeys = []
        episodeLinks = {}

        printDBG("++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
        printDBG(tab)
        printDBG("++++++++++++++++++++++++++++++++++++++++++++++++++++++++")

        for item in tab:
            title = item['title'].replace(' 0', ' ')
            if title not in episodeKeys:
                episodeLinks[title] = []
                episodeKeys.append(title)
            item['name'] = item['server_title']
            episodeLinks[title].append(item)

        seasonNum = self.cm.ph.getSearchGroups(cItem['url'] + '|', '''-season-([0-9]+?)[^0-9]''', 1, True)[0]
        for item in episodeKeys:
            episodeNum = self.cm.ph.getSearchGroups(item + '|', '''Episode\s+?([0-9]+?)[^0-9]''', 1, True)[0]
            if '' != episodeNum and '' != seasonNum:
                title = 's%se%s' % (seasonNum.zfill(2), episodeNum.zfill(2)) + ' ' + item.replace('Episode %s' % episodeNum, '')
            else:
                title = item
            baseTitle = re.sub('Season\s[0-9]+?[^0-9]', '', cItem['title'] + ' ')
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': self.cleanHtmlStr(baseTitle + ' ' + title), 'urls': episodeLinks[item]})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("YesMovies.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('movie/search/' + urllib.quote_plus(searchPattern))
        self.listItems(cItem, 'list_episodes')

    def getLinksForVideo(self, cItem, forEpisodes=False):
        printDBG("YesMovies.getLinksForVideo [%s]" % cItem)

        if 'urls' in cItem:
            return cItem['urls']

        urlTab = self.cacheLinks.get(cItem['url'], [])
        if len(urlTab):
            return urlTab
        self.cacheLinks = {}

        #rm(self.COOKIE_FILE)

        sts, data = self.getPage(cItem['url'], self.defaultParams)
        if not sts:
            return []

        # get trailer
        trailer = self.cm.ph.getDataBeetwenMarkers(data, '''$('#pop-trailer')''', '</script>', False)[1]
        trailer = self.cm.ph.getSearchGroups(trailer, '''['"](http[^"^']+?)['"]''')[0]

        movieId = cItem.get('movie_id', '')
        if '' == movieId:
            try:
                movieId = str(int(cItem['url'].split('-')[-1].split('.', 1)[0]))
            except Exception:
                printExc()

        if '' == movieId:
            return []
        url = self.getFullUrl('ajax/v4_movie_episodes/' + movieId)

        params = dict(self.defaultParams)
        params['header'] = self.AJAX_HEADER
        sts, data = self.getPage(url, params)
        if not sts:
            return []

        try:
            data = byteify(json.loads(data)['html'], '', True)
        except Exception:
            printExc()

        printDBG("++++++++++++++++++++++++++++++++++++")
        printDBG(data)
        printDBG("++++++++++++++++++++++++++++++++++++")

        serversNameMap = {}
        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'servers'), ('</ul', '>'))[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li', '</li>')

        for item in tmp:
            serverId = self.cm.ph.getSearchGroups(item, '''data\-id=['"]([0-9]+?)['"]''')[0]
            serversNameMap[serverId] = self.cleanHtmlStr(item)

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<ul', '>', 'episodes'), ('</ul', '>'))
        for item in data:
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(item, '<li', '</li>')
            for eItem in tmp:
                serverId = self.cm.ph.getSearchGroups(item, '''data\-server=['"]([0-9]+?)['"]''')[0]
                episodeId = self.cm.ph.getSearchGroups(item, '''data\-id=['"]([0-9]+?)['"]''')[0]
                title = self.cleanHtmlStr(eItem)
                serverTitle = serversNameMap.get(serverId, serverId)
                if not forEpisodes:
                    name = serverTitle + ': ' + title
                else:
                    name = ''
                urlTab.append({'name': name, 'title': title, 'server_title': serverTitle, 'url': serverId + '|' + episodeId + '|' + cItem['url'], 'server_id': serverId, 'episode_id': episodeId, 'need_resolve': 1})

        printDBG(urlTab)

        def _sortKey(item):
            val = item.get('server_id', '0')
            if val == '7':
                return 1
            elif val == '14':
                return 0
            return 1000
        urlTab.sort(key=_sortKey)

        if len(urlTab) and self.cm.isValidUrl(trailer) and len(trailer) > 10:
            urlTab.insert(0, {'name': 'Trailer', 'title': 'Trailer', 'server_title': 'Trailer', 'url': trailer, 'need_resolve': 1})

        self.cacheLinks[cItem['url']] = urlTab
        return urlTab

    def getVideoLinks(self, videoUrl):
        printDBG("YesMovies.getVideoLinks [%s]" % videoUrl)
        urlTab = []

        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if videoUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name']
                        break

        if self.cm.isValidUrl(videoUrl):
            return self.up.getVideoLinkExt(videoUrl)

        tmp = videoUrl.split('|')
        if len(tmp) != 3:
            return []
        serverId = tmp[0]
        episodeId = tmp[1]
        referer = tmp[2]

        if referer.endswith('/'):
            referer += 'watching.html'

        sts, data = self.getPage(referer, self.defaultParams)
        if not sts:
            return []

        #rm(self.COOKIE_FILE)
        #cookie = self.cm.getCookieHeader(self.COOKIE_FILE)
        printDBG('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> $$$$$$$$$$$$$$$$$$$$$$ ' + serverId)
        if serverId in ['12', '13', '14', '15', '16']:
            url = 'ajax/movie_embed/' + episodeId
            url = self.getFullUrl(url)
            sts, data = self.getPage(url)
            if not sts:
                return []
            try:
                data = byteify(json.loads(data), '', True)
                if data['status']:
                    urlTab = self.up.getVideoLinkExt(data['src'])
            except Exception:
                printExc()
                return []
        else:
            try:
                mid = urlparse(referer).path.split('/')[2].split('-')[-1].split('.', 1)[0]
            except Exception:
                mid = ''
                printExc()
            url = self.getFullUrl('/ajax/movie_token?eid=%s&mid=%s&_=%s' % (episodeId, mid, int(time.time() * 10000)))
            if not self.cm.isValidUrl(url):
                return []

            params = dict(self.defaultParams)
            params['header'] = dict(self.HEADER)
            params['header']['Referer'] = referer

            sts, data = self.getPage(url, params)
            if not sts:
                return []

            xx = self.cm.ph.getSearchGroups(data, '''x=['"]([^'^"]+?)['"]''')[0]
            xy = self.cm.ph.getSearchGroups(data, '''y=['"]([^'^"]+?)['"]''')[0]

            url = 'ajax/movie_sources/%s?x=%s&y=%s' % (episodeId, xx, xy)
            url = self.getFullUrl(url)

            params = {}
            params['header'] = dict(self.AJAX_HEADER)
            sts, data = self.getPage(url, params)
            if not sts:
                return []

            subTracks = []
            if False:
                tmp = self.cm.ph.getAllItemsBeetwenMarkers(data, '<jwplayer', '>', withMarkers=True)
                printDBG("------------------------------------------------\n%s+++++++++++++++++++++++++++++++++++++++++++++\n" % tmp)
                for item in tmp:
                    url = self.cm.ph.getSearchGroups(item, 'file="(http[^"]+?)"')[0].replace('&amp;', '&')
                    name = self.cm.ph.getSearchGroups(item, 'label="([^"]+?)"')[0]
                    if 'type="mp4"' in item:
                        urlTab.append({'name': name, 'url': url})
                    elif 'type="m3u8"' in item:
                        url = strwithmeta(url, {'Referer': referer, 'User-Agent': params['header']['User-Agent']})
                        urlTab.extend(getDirectM3U8Playlist(url, checkContent=True, sortWithMaxBitrate=999999999))
                    elif 'kind="captions"' in item:
                        format = url[-3:]
                        if format in ['srt', 'vtt']:
                            subTracks.append({'title': name, 'url': self.getFullIconUrl(url), 'lang': name, 'format': format})
            else:
                try:
                    tmp = byteify(json.loads(data))
                    printDBG("------------------------------------------------\n%s+++++++++++++++++++++++++++++++++++++++++++++\n" % tmp)
                    if isinstance(tmp['playlist'][0]['sources'], dict):
                        tmp['playlist'][0]['sources'] = [tmp['playlist'][0]['sources']]
                    for item in tmp['playlist'][0]['sources']:
                        if "mp4" == item['type']:
                            urlTab.append({'name': str(item.get('label', 'default')), 'url': item['file']})
                        elif "m3u8" == item['type']:
                            url = strwithmeta(item['file'], {'Referer': referer, 'User-Agent': params['header']['User-Agent']})
                            urlTab.extend(getDirectM3U8Playlist(url, checkContent=True, sortWithMaxBitrate=999999999))
                    if isinstance(tmp['playlist'][0]['tracks'], dict):
                        tmp['playlist'][0]['tracks'] = [tmp['playlist'][0]['tracks']]
                    for item in tmp['playlist'][0]['tracks']:
                        format = item['file'][-3:]
                        if format in ['srt', 'vtt'] and "captions" == item['kind']:
                            subTracks.append({'title': str(item['label']), 'url': self.getFullIconUrl(item['file']), 'lang': item['label'], 'format': format})
                except Exception:
                    printExc()
            printDBG(subTracks)
            urlParams = {'Referer': referer, 'User-Agent': params['header']['User-Agent']}
            if len(subTracks):
                urlParams.update({'external_sub_tracks': subTracks})

            for idx in range(len(urlTab)):
                urlTab[idx]['url'] = strwithmeta(urlTab[idx]['url'], urlParams)

        return urlTab

    def getArticleContent(self, cItem):
        printDBG("YesMovies.getArticleContent [%s]" % cItem)
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

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.fillCacheFilters()
            self.listMainMenu({'name': 'category'})
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
            self.listItems(self.currItem, 'list_episodes')
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
        CHostBase.__init__(self, YesMovies(), True, [])

    def withArticleContent(self, cItem):
        if cItem.get('type', 'video') != 'video' and cItem.get('category', 'unk') != 'list_episodes':
            return False
        return True
