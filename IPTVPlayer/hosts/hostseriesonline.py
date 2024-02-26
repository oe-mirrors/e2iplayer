# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError, GetIPTVNotify
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus, urllib_urlencode
###################################################
# FOREIGN import
###################################################
import re
try:
    import json
except Exception:
    import simplejson as json
from Components.config import config, ConfigSelection, ConfigText, getConfigListEntry
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.seriesonlineio_proxy = ConfigSelection(default="None", choices=[("None", _("None")),
                                                                                              ("proxy_1", _("Alternative proxy server (1)")),
                                                                                              ("proxy_2", _("Alternative proxy server (2)"))])
config.plugins.iptvplayer.seriesonlineio_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.seriesonlineio_proxy))
    if config.plugins.iptvplayer.seriesonlineio_proxy.value == 'None':
        optionList.append(getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.seriesonlineio_alt_domain))
    return optionList
###################################################


def gettytul():
    return 'https://series9.io/'


class SeriesOnlineIO(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'SeriesOnlineIO.tv', 'cookie': 'seriesonlineio.cookie'})
        self.DEFAULT_ICON_URL = 'https://www2.series9.io/images/gomovies-logo-light.png'
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:56.0) Gecko/20100101 Firefox/56.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Encoding': 'gzip, deflate'}

        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})
        self.MAIN_URL = None
        self.cacheFilters = {}
        self.cacheLinks = {}
        self.defaultParams = {'header': self.HEADER, 'use_new_session': True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.MAIN_CAT_TAB = []

        self.userInformedAboutCaptchaProtection = False

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)

        proxy = config.plugins.iptvplayer.seriesonlineio_proxy.value
        if proxy != 'None':
            if proxy == 'proxy_1':
                proxy = config.plugins.iptvplayer.alternative_proxy1.value
            else:
                proxy = config.plugins.iptvplayer.alternative_proxy2.value
            addParams = dict(addParams)
            addParams.update({'http_proxy': proxy})

        addParams['cloudflare_params'] = {'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT}

        tries = 0
        while tries < 2:
            tries += 1
            captcha = False
            sts, data = self.cm.getPageCFProtection(baseUrl, addParams, post_data) #self.cm.getPage(baseUrl, addParams, post_data)
            if 'captcha' in self.cm.meta.get('url', ''):
                rm(self.COOKIE_FILE)
                captcha = True
                continue
            break

        if captcha:
            message = _('This site is protected with Google reCaptcha v2.')
            SetIPTVPlayerLastHostError(message)
            if not self.userInformedAboutCaptchaProtection:
                self.userInformedAboutCaptchaProtection = True
                GetIPTVNotify().push(message, 'error', 10)

        return sts, data

    def getFullUrl(self, url):
        if url.startswith('//'):
            return 'https:' + url
        return CBaseHostClass.getFullUrl(self, url)

    def getFullIconUrl(self, url):
        url = self.getFullUrl(url)

        proxy = config.plugins.iptvplayer.seriesonlineio_proxy.value

        if proxy != 'None':
            if proxy == 'proxy_1':
                proxy = config.plugins.iptvplayer.alternative_proxy1.value
            else:
                proxy = config.plugins.iptvplayer.alternative_proxy2.value
            url = strwithmeta(url, {'iptv_http_proxy': proxy})

        cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE)
        return strwithmeta(url, {'Cookie': cookieHeader, 'User-Agent': self.USER_AGENT})

    def selectDomain(self):
        domains = ['https://www2.series9.io/'] #'http://123movieshd.us/'
        domain = config.plugins.iptvplayer.seriesonlineio_alt_domain.value.strip()
        if self.cm.isValidUrl(domain):
            if domain[-1] != '/':
                domain += '/'
            domains.insert(0, domain)

        confirmedDomain = None
        for domain in domains:
            self.MAIN_URL = domain
            sts, data = self.getPage(domain)
            if sts and 'genre/action/' in data:
                self.setMainUrl(self.cm.meta['url'])
                confirmedDomain = True
                break

        if confirmedDomain == None:
            self.MAIN_URL = domains[0]

        self.SEARCH_URL = self.MAIN_URL + 'movie/search'
        self.MAIN_CAT_TAB = [{'category': 'list_filter_genre', 'title': 'Movies', 'url': self.MAIN_URL + 'movie/filter/movie'},
                             {'category': 'list_filter_genre', 'title': 'TV-Series', 'url': self.MAIN_URL + 'movie/filter/series'},
                             {'category': 'list_filter_genre', 'title': 'Cinema', 'url': self.MAIN_URL + 'movie/filter/cinema'},
                             {'category': 'search', 'title': _('Search'), 'search_item': True, },
                             {'category': 'search_history', 'title': _('Search history'), }
                            ]

    def fillCacheFilters(self):
        self.cacheFilters = {}

        sts, data = self.getPage(self.getFullUrl('movie/filter/series/all/all/all/all/latest/'), self.defaultParams)
        if not sts:
            return

        # get sort by
        self.cacheFilters['sort_by'] = []
        tmp = self.cm.ph.getDataBeetwenMarkers(data, 'Sort by</span>', '</ul>', False)[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li', '</li>', withMarkers=True, caseSensitive=False)
        for item in tmp:
            value = self.cm.ph.getSearchGroups(item, 'href="[^"]+?/filter/all/all/all/all/all/([^"^/]+?)/')[0]
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
        printDBG("SeriesOnlineIO.listFilters")
        if {} == self.cacheFilters:
            self.fillCacheFilters()

        cItem = dict(cItem)
        cItem['category'] = nextCategory
        self.listsTab(self.cacheFilters.get(filter, []), cItem)

    def listItems(self, cItem, nextCategory=None):
        printDBG("SeriesOnlineIO.listItems")
        url = cItem['url']
        page = cItem.get('page', 1)
        if '/search' not in url:
            url += '/{0}/{1}/{2}/{3}/{4}/'.format(cItem['quality'], cItem['genre'], cItem['country'], cItem['year'], cItem['sort_by'])

        if page > 1:
            url = url + '?page={0}'.format(page)
        sts, data = self.getPage(url)
        if not sts:
            return

        nextPage = self.cm.ph.getDataBeetwenMarkers(data, 'pagination', '</ul>', False)[1]
        if '' != self.cm.ph.getSearchGroups(nextPage, 'page=(%s)[^0-9]' % (page + 1))[0]:
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
            params.update({'title': _("Next page"), 'page': page + 1})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("SeriesOnlineIO.listEpisodes")

        tab = self.getLinksForVideo(cItem, True)
        episodeKeys = []
        episodeLinks = {}

        printDBG("+++")
        printDBG(tab)
        printDBG("+++")

        for item in tab:
            title = item['title'].upper()
            title = title.replace('EPISODE', ' ')
            title = title.replace(' 0', ' ')
            if 'TRAILER' not in title:
                title = 'Episode ' + title
            title = self.cleanHtmlStr(title)
            if title not in episodeKeys:
                episodeLinks[title] = []
                episodeKeys.append(title)
            item['name'] = item['server_title']
            try:
                key = int(title)
            except Exception:
                key = title
            printDBG("key [%s]" % key)
            episodeLinks[key].append(item)

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
        printDBG("SeriesOnlineIO.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        if self.MAIN_URL == None:
            self.selectDomain()

        url = self.SEARCH_URL + '/' + urllib_quote_plus(searchPattern).replace('+', '-')
        sts, data = self.getPage(url)
        if not sts:
            return
        cUrl = self.cm.meta['url']
        tmp = ''
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<script>', '</script>', False)
        for item in data:
            if '$.ajax(' in item:
                tmp = item
                break
        if tmp == '':
            return
        ret = js_execute('$={}; $.ajax=function(setup){print(JSON.stringify(setup));}\n' + tmp)
        if ret['sts'] and 0 == ret['code']:
            decoded = ret['data'].strip()
            printDBG('DECODED DATA -> \n[%s]\n' % decoded)
            try:
                decoded = byteify(json.loads(decoded))
                searchUrl = self.getFullUrl(decoded.get('url', cUrl))
                if '?' not in searchUrl:
                    searchUrl += '?'
                if 'data' in decoded:
                    searchUrl += urllib_urlencode(decoded['data'])
                printDBG('searchUrl [%s]\n' % searchUrl)
                cItem = dict(cItem)
                cItem['url'] = searchUrl
                self.listItems(cItem, 'list_episodes')
            except Exception:
                printExc()

    def getLinksForVideo(self, cItem, forEpisodes=False):
        printDBG("SeriesOnlineIO.getLinksForVideo [%s]" % cItem)

        if 'urls' in cItem:
            return cItem['urls']

        urlTab = self.cacheLinks.get(cItem['url'], [])
        if len(urlTab):
            return urlTab
        self.cacheLinks = {}

        url = cItem['url']
        sts, data = self.getPage(url, self.defaultParams)
        if not sts:
            return []

        # get trailer
        trailer = self.cm.ph.getDataBeetwenMarkers(data, '''$('#pop-trailer')''', '</script>', False)[1]
        trailer = self.cm.ph.getSearchGroups(trailer, '''['"](http[^"^']+?)['"]''')[0]

        data = self.cm.ph.getDataBeetwenMarkers(data, 'id="mv-info"', '</a>')[1]
        url = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''href=['"]([^'^"]+?)['"]''')[0])

        params = dict(self.defaultParams)
        params['header'] = dict(params['header'])
        params['header']['Referer'] = cItem['url']

        sts, data = self.getPage(url, params)
        if not sts:
            return []

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div id="server', '<div class="clearfix">', withMarkers=True)
        for item in data:
            serverTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<div id="server', '</div>', withMarkers=True)[1])
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(item, '<a', '</a>', withMarkers=True)
            for eItem in tmp:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(eItem, '''player-data=['"]([^'^"]+?)['"]''')[0])
                title = self.cleanHtmlStr(eItem)
                if not forEpisodes:
                    name = serverTitle + ': ' + title
                else:
                    name = ''
                urlTab.append({'name': name, 'title': title, 'server_title': serverTitle, 'url': url, 'need_resolve': 1})

        if len(urlTab) and self.cm.isValidUrl(trailer) and len(trailer) > 10:
            urlTab.insert(0, {'name': 'Trailer', 'title': 'Trailer', 'server_title': 'Trailer', 'url': trailer, 'need_resolve': 1})

        self.cacheLinks[cItem['url']] = urlTab
        return urlTab

    def getVideoLinks(self, videoUrl):
        printDBG("SeriesOnlineIO.getVideoLinks [%s]" % videoUrl)
        urlTab = []

        if not self.cm.isValidUrl(videoUrl):
            return []

        params = dict(self.defaultParams)
        params['max_data_size'] = 0
        sts = self.getPage(videoUrl, params)[0]
        if not sts:
            return []
        contentType = self.cm.meta['content-type']
        if 'text' not in contentType:
            if 'video' in contentType:
                return [{'name': self.up.getDomain(videoUrl), 'url': videoUrl}]
            else:
                return []

        tab = self.up.getVideoLinkExt(videoUrl)
        if len(tab):
            return tab

        sts, data = self.getPage(videoUrl, self.defaultParams)
        if not sts:
            return []

        tmpVideoUrl = self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0]
        if self.cm.isValidUrl(tmpVideoUrl):
            tab = self.up.getVideoLinkExt(tmpVideoUrl)
            if len(tab):
                return tab

        subTracks = []
        tmp = self.cm.ph.getDataBeetwenMarkers(data, 'sources', ']')[1]
        if tmp != '':
            tmp = data.split('}')
            urlAttrName = 'file'
            sp = ':'
        else:
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(data, '<source', '>', withMarkers=True)
            urlAttrName = 'src'
            sp = '='

        for item in tmp:
            url = self.cm.ph.getSearchGroups(item, r'''['"]?{0}['"]?\s*{1}\s*['"]((:?https?:)?//[^"^']+)['"]'''.format(urlAttrName, sp))[0]
            name = self.cm.ph.getSearchGroups(item, r'''['"]?label['"]?\s*{0}\s*['"]([^"^']+)['"]'''.format(sp))[0]
            if url == '' or 'error.com' in url:
                continue
            if url.startswith('//'):
                url = 'https:' + url

            printDBG('---------------------------')
            printDBG('url:  ' + url)
            printDBG('name: ' + name)
            printDBG('+++++++++++++++++++++++++++')
            printDBG(item)

            if 'mp4' in item:
                urlTab.append({'name': self.up.getDomain(url) + ' ' + name, 'url': url})
            elif 'captions' in item:
                format = url[-3:]
                if format in ['srt', 'vtt']:
                    subTracks.append({'title': name, 'url': self.getFullIconUrl(url), 'lang': name, 'format': format})

        printDBG(subTracks)
        if len(subTracks):
            for idx in range(len(urlTab)):
                urlTab[idx]['url'] = strwithmeta(urlTab[idx]['url'], {'external_sub_tracks': subTracks})

        return urlTab

    def getArticleContent(self, cItem):
        printDBG("SeriesOnlineIO.getArticleContent [%s]" % cItem)
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
            title = cItem['desc']
        if icon == '':
            title = cItem['icon']

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

        return [{'title': self.cleanHtmlStr(title), 'text': self.cleanHtmlStr(desc), 'images': [{'title': '', 'url': self.getFullUrl(icon)}], 'other_info': otherInfo}]

    def getFavouriteData(self, cItem):
        printDBG('SeriesOnlineIO.getFavouriteData')
        params = {'type': cItem['type'], 'category': cItem.get('category', ''), 'title': cItem['title'], 'url': cItem['url'], 'data_url': cItem['data_url'], 'desc': cItem['desc'], 'info_url': cItem['info_url'], 'icon': cItem['icon']}
        return json.dumps(params)

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
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})
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
        CHostBase.__init__(self, SeriesOnlineIO(), True, [])

    def withArticleContent(self, cItem):
        if cItem['type'] != 'video' and cItem['category'] != 'list_episodes':
            return False
        return True
