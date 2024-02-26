# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import urlparse
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
###################################################
# FOREIGN import
###################################################
import time
from datetime import timedelta
try:
    import json
except Exception:
    import simplejson as json
from Components.config import config, getConfigListEntry
###################################################


###################################################
# Config options for HOST
###################################################

def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Default video quality:"), config.plugins.iptvplayer.vevo_default_quality))
    optionList.append(getConfigListEntry(_("Use default video quality:"), config.plugins.iptvplayer.vevo_use_default_quality))
    optionList.append(getConfigListEntry(_("Allow hls format"), config.plugins.iptvplayer.vevo_allow_hls))
    return optionList
###################################################

def GetConfigList():
    optionList = []
    return optionList


def gettytul():
    return 'https://vevo.com/'


class VevoCom(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'vevo.com', 'cookie': 'vevo.com.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.132 Safari/537.36'
        self.MAIN_URL = 'https://vevo.com/'
        self.API_URL = 'https://veil.vevoprd.com/graphql'
        self.DEFAULT_ICON_URL = 'http://1.bp.blogspot.com/-pSTjDlSgahQ/VVsbLaM40NI/AAAAAAAAHvU/wr8F9v9gPoE/s1600/Vevo.png'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate'}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding': 'gzip, deflate', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json, text/javascript, */*; q=0.01'})

        self.defaultParams = {'ignore_http_code_ranges': [], 'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.translations = {}
        self.webDataCache = {}
        self.authData = {'key': '', 'expires': 0, 'token': ''}

    def getPage(self, baseUrl, addParams={}, post_data=None):
        self._getAuthToken()
        if addParams == {}:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def fillBrowse(self, data):
        data = self.cm.ph.getDataBeetwenNodes(data, ('window.__INITIAL_STORE__', '='), ('</script', '>'), False)[1]
        try:
            data = byteify(json.loads(data.strip()[:-1]))
            language = list(data['default']['localeData'].keys())[0]
            self.language = language.split('-')
            self.translations = data['default']['localeData'][language]['translation']
            self.webDataCache = data
        except Exception:
            printExc()
            return

    def listMainMenu(self, cItem):
        printDBG("VevoCom.listMainMenu")

        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return

        self.fillBrowse(data)

        catsMAp = {'genres': 'list_genres', 'moods': 'list_containers', 'recently-added': 'list_genres_filters', 'trending-now': 'list_genres_filters', 'artists': 'list_artists'}

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'sub-menu'), ('</ul', '>'), False)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(item)
            nextCategory = catsMAp.get(url.split('/')[-1], '')
            if nextCategory == '':
                continue

            params = dict(cItem)
            params.pop('page', 0)
            params.update({'good_for_fav': False, 'category': nextCategory, 'title': title, 'url': url})
            self.addDir(params)

        MAIN_CAT_TAB = [{'category': 'search', 'title': _('Search'), 'search_item': True},
                        {'category': 'search_history', 'title': _('Search history')}, ]

        self.listsTab(MAIN_CAT_TAB, cItem)

    def listGenresFilters(self, cItem, nextCategory):
        printDBG("VevoCom.listGenresFilters [%s]" % cItem)

        baseUrl = cItem['url']
        if baseUrl.endswith('/'):
            baseUrl = baseUrl[:-1]

        genresList = [{'title': _('all'), 'url': baseUrl}]
        try:
            for item in self.webDataCache['apollo']['data']['ROOT_QUERY']['genres']:
                url = item['id']
                title = self.translations.get(url, url)
                genresList.append({'title': title, 'url': baseUrl + '/' + url})
        except Exception:
            printExc()

        params = dict(cItem)
        params.update({'good_for_fav': False, 'category': nextCategory})
        self.listsTab(genresList, params)

    def listItems(self, cItem):
        printDBG("VevoCom.listItems [%s]" % cItem)
        page = cItem.get('page', 1)

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<a', '>', 'rel="next"'), ('</a', '>'))[1]
        nextPage = self.getFullUrl(self.cm.ph.getSearchGroups(nextPage, '''\shref=['"]([^'^"]+?)['"]''')[0])

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'feedV2-container'), ('</ul', '>'))[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''\ssrc=['"]([^'^"]+?)['"]''')[0])
            titleTab = []
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<', '>', 'item-title'), ('<', '>'))[1])
            if title != '':
                titleTab.append(title)
            subtitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h3', '</h3>')[1])
            if subtitle != '':
                titleTab.append(subtitle)
            params = dict(cItem)
            params.pop('page', 0)
            params.update({'good_for_fav': True, 'title': ' - '.join(titleTab), 'url': url, 'icon': icon})
            if '/playlist/' in url:
                nextCategory = 'list_playlist'
            elif '/artist/' in url:
                nextCategory = 'list_artist_videos'
            elif '/genres/' in url:
                nextCategory = 'list_containers'
            elif '/watch/' in url:
                nextCategory = 'video'
            else:
                continue
            if nextCategory == 'video':
                self.addVideo(params)
            else:
                params['category'] = nextCategory
                self.addDir(params)

        if nextPage != '':
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _('Next page'), 'url': nextPage, 'page': page + 1})
            self.addDir(params)

    def listContainers(self, cItem, nextCategory1, nextCategory2):
        printDBG("VevoCom.listContainers [%s]" % cItem)

        sts, data = self.getPage(cItem['url'])
        if not sts and '404' in str(data):
            url = urlparse(cItem['url'])
            url = url._replace(path='/'.join(url.path.split('/')[2:])).geturl()
            sts, data = self.getPage(url)
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'containers'), ('<div', '>', 'footer'))[1]
        containers = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'feedV2-title'), ('</ul', '>'))
        for container in containers:
            itemsTab = []
            containerTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(container, ('<', '>', 'container-name'), ('<', '>'))[1])
            containerDesc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(container, ('<', '>', 'container-description'), ('<', '>'))[1])
            moreUrl = self.getFullUrl(self.cm.ph.getSearchGroups(container.split('<ul', 1)[0], '''\shref=['"]([^'^"]+?)['"]''')[0])

            if moreUrl == '':
                container = self.cm.ph.getAllItemsBeetwenMarkers(container, '<li', '</li>')
                for item in container:
                    url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0])
                    icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''\ssrc=['"]([^'^"]+?)['"]''')[0])
                    titleTab = []
                    title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<', '>', 'item-title'), ('<', '>'))[1])
                    if title != '':
                        titleTab.append(title)
                    subtitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h3', '</h3>')[1])
                    if subtitle != '':
                        titleTab.append(subtitle)
                    if '/playlist/' in url:
                        itemNextCategory = 'list_playlist'
                    elif '/artist/' in url:
                        itemNextCategory = 'list_artist_videos'
                    elif '/watch/' in url:
                        itemNextCategory = 'video'

                    itemsTab.append({'good_for_fav': True, 'category': itemNextCategory, 'title': ' - '.join(titleTab), 'url': url, 'icon': icon})

            params = dict(cItem)
            params.pop('page', 0)
            if len(itemsTab):
                params.update({'good_for_fav': False, 'category': nextCategory1, 'title': containerTitle, 'desc': containerDesc, 'container_items': itemsTab})
                self.addDir(params)
            elif moreUrl != '':
                params.update({'good_for_fav': False, 'category': nextCategory2, 'url': moreUrl, 'title': containerTitle, 'desc': containerDesc})
                self.addDir(params)

    def listContainerItems(self, cItem):
        printDBG("VevoCom.listContainerItems [%s]" % cItem)
        cItem = dict(cItem)
        itemsTab = cItem.pop('container_items', [])
        for item in itemsTab:
            params = dict(cItem)
            params.pop('page', 0)
            params.update(item)
            if item['category'] == 'video':
                self.addVideo(params)
            else:
                self.addDir(params)

    def _getAuthToken(self):
        if self.authData.get('key', '') == '':
            sts, data = self.cm.getPage(self.getMainUrl(), self.defaultParams)
            if not sts:
                return ''
            scriptUrl = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<script[^>]+?src=["']([^'^"]*?/browser[^'^"]*?\.js)['"]''')[0])
            sts, data = self.cm.getPage(scriptUrl, self.defaultParams)
            if not sts:
                return ''
            self.authData['key'] = self.cm.ph.getDataBeetwenMarkers(data, 'token:{key:"', '"', False)[1]

        if self.authData.get('expires', 0) < int(time.time()):
            params = dict(self.defaultParams)
            params['header'] = dict(params['header'])
            params['header']['Content-Type'] = 'application/json; charset=UTF-8'
            params['header']['Origin'] = self.getMainUrl()[:-1]
            params['header']['Referer'] = self.getMainUrl()
            params['raw_post_data'] = True
            post_data = '{"client_id":"%s","grant_type":"urn:vevo:params:oauth:grant-type:anonymous"}' % (self.authData['key'])
            sts, data = self.cm.getPage('https://accounts.vevo.com/token', params, post_data)
            if not sts:
                return ''

            printDBG(data)
            try:
                data = byteify(json.loads(data), '', True)
                self.defaultParams['cookie_items'] = {'ApiToken': str(data['legacy_token']), 'ApiTokenRefresh': str(data['refresh_token'])}
                self.authData['token'] = str(data['legacy_token'])
                self.authData['expires'] = int(time.time()) + int(data['expires_in'])
                return self.authData['token']
            except Exception:
                printExc()

        return self.authData.get('token', '')

    def _getApiHeaders(self, cItem):

        params = {}
        params['header'] = {'User-Agent': self.USER_AGENT, 'Accept-Encoding': 'gzip, deflate, br', 'Accept-Language': 'en-US,en;q=0.9,pl;q=0.8', 'Vevo-Device': 'Desktop', 'Vevo-Product': 'web/3.408-b252', 'Content-Type': 'application/json', 'Accept': '*/*', 'Vevo-OS': 'Windows/7'}
        params['header']['Referer'] = cItem['url']
        params['header']['Origin'] = self.cm.getBaseUrl(cItem['url'])[:-1]
        params['header']['Authorization'] = 'Bearer %s' % self._getAuthToken()
        params['raw_post_data'] = True
        return params

    def _listJsonVideos(self, cItem, data):
        try:
            for item in data:
                if 'videoData' in item:
                    item = item['videoData']
                item = item['basicMetaV3']
                url = self.getFullUrl(self.getFullUrl('watch/' + item['isrc']))

                titleTab = []
                try:
                    title = item['artists'][0]['basicMeta']['name']
                    if title != '':
                        titleTab.append(self.cleanHtmlStr(title))
                except Exception:
                    printExc()

                if item['title'] != '':
                    titleTab.append(self.cleanHtmlStr(item['title']))

                icon = self.getFullIconUrl(item['thumbnailUrl'])
                desc = str(timedelta(seconds=item['duration'] / 1000))
                if desc.startswith('0:'):
                    desc = desc[2:]
                desc = [desc]
                desc.append(', '.join(item['categories']))
                params = dict(cItem)
                params.pop('page', 0)
                params.update({'good_for_fav': True, 'title': ' - '.join(titleTab), 'url': url, 'icon': icon, 'desc': ' | '.join(desc)})
                self.addVideo(params)
        except Exception:
            printExc()

    def listPlaylistItems(self, cItem):
        printDBG("VevoCom.listPlaylistItems [%s]" % cItem)
        playlistId = cItem['url'].split('/')[-1].split('?', 1)[0]
        if playlistId == '':
            return

        page = cItem.get('page', 0)
        if page == 0:
            mode = 'Playlist'
        else:
            mode = 'MorePlaylistVideos'

        post_data = '{"query":"query %s($ids: [String]!, $offset: Int, $limit: Int) {\\n  playlists(ids: $ids) {\\n    id\\n    playlistId\\n    basicMeta {\\n      title\\n      description\\n      curated\\n      admin_id\\n      user_id\\n      user {\\n        id\\n        basicMeta {\\n          username\\n          vevo_user_id\\n          __typename\\n        }\\n        __typename\\n      }\\n      public\\n      image_url\\n      videoCount\\n      errorCode\\n      __typename\\n    }\\n    likes\\n    liked\\n    videos(limit: $limit, offset: $offset) {\\n      items {\\n        id\\n        index\\n        isrc\\n        videoData {\\n          id\\n          likes\\n          liked\\n          basicMetaV3 {\\n            youTubeId\\n            monetizable\\n            isrc\\n            title\\n            urlSafeTitle\\n            startDate\\n            endDate\\n            releaseDate\\n            copyright\\n            copyrightYear\\n            genres\\n            contentProviders\\n            shortUrl\\n            thumbnailUrl\\n            duration\\n            hasLyrics\\n            explicit\\n            allowEmbed\\n            allowMobile\\n            categories\\n            credits {\\n              role\\n              name\\n              __typename\\n            }\\n            artists {\\n              id\\n              basicMeta {\\n                urlSafeName\\n                role\\n                name\\n                thumbnailUrl\\n                __typename\\n              }\\n              __typename\\n            }\\n            errorCode\\n            __typename\\n          }\\n          __typename\\n        }\\n        __typename\\n      }\\n      offset\\n      limit\\n      __typename\\n    }\\n    __typename\\n  }\\n}\\n","variables":{"ids":["%s"],"limit":%s,"offset":%s},"operationName":"%s"}'
        post_data = post_data % (mode, playlistId, 20, page * 20, mode)
        params = self._getApiHeaders(cItem)

        sts, data = self.getPage(self.API_URL, params, post_data)
        if not sts:
            return

        try:
            data = byteify(json.loads(data), '')['data']['playlists'][0]
            self._listJsonVideos(cItem, data['videos']['items'])
            if data['basicMeta']['videoCount'] > (page + 1) * 20:
                params = dict(cItem)
                params.pop('page', 0)
                params.update({'good_for_fav': False, 'title': _('Next page'), 'page': page + 1})
                self.addDir(params)
        except Exception:
            printExc()

    def listArtistVideos(self, cItem):
        printDBG("VevoCom.listArtistVideos [%s]" % cItem)
        artistId = cItem['url'].split('/')[-1].split('?', 1)[0]
        if artistId == '':
            return

        page = cItem.get('page', 0)

        post_data = '{"query":"query ArtistVideos($ids: [String]!, $page: Int, $apiCall: String) {\\n  artists(ids: $ids) {\\n    id\\n    videoData(size: 30, page: $page, sort: \\"MostRecent\\", apiCall: $apiCall) {\\n      videos {\\n        data {\\n          id\\n          basicMetaV3 {\\n            artists {\\n              basicMeta {\\n                name\\n                role\\n                urlSafeName\\n                thumbnailUrl\\n                __typename\\n              }\\n              __typename\\n            }\\n            monetizable\\n            isrc\\n            title\\n            urlSafeTitle\\n            releaseDate\\n            copyright\\n            shortUrl\\n            thumbnailUrl\\n            duration\\n            hasLyrics\\n            explicit\\n            allowEmbed\\n            allowMobile\\n            unlisted\\n            live\\n            certified\\n            originalContent\\n            releaseDate\\n            categories\\n            __typename\\n          }\\n          likes\\n          liked\\n          views {\\n            viewsTotal\\n            __typename\\n          }\\n          __typename\\n        }\\n        paging {\\n          total\\n          size\\n          pages\\n          next\\n          page\\n          __typename\\n        }\\n        __typename\\n      }\\n      __typename\\n    }\\n    __typename\\n  }\\n}\\n","variables":{"ids":["%s"],"page":%s,"apiCall":"all"},"operationName":"ArtistVideos"}'
        post_data = post_data % (artistId, page + 1)

        params = self._getApiHeaders(cItem)

        sts, data = self.getPage(self.API_URL, params, post_data)
        if not sts:
            return

        try:
            data = byteify(json.loads(data), '')['data']['artists'][0]
            self._listJsonVideos(cItem, data['videoData']['videos']['data'])

            if data['videoData']['videos']['paging']['page'] < data['videoData']['videos']['paging']['pages']:
                params = dict(cItem)
                params.pop('page', 0)
                params.update({'good_for_fav': False, 'title': _('Next page'), 'page': page + 1})
                self.addDir(params)
        except Exception:
            printExc()

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("VevoCom.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        query = 'search?q=%s' % urllib_quote_plus(searchPattern)
        url = 'https://quest.vevo.com/%s' % query
        params = self._getApiHeaders({'url': self.getFullUrl(query)})

        sts, data = self.getPage(url, params)
        if not sts:
            return

        try:
            artistsTab = []
            videosTab = []
            playlists = []

            data = byteify(json.loads(data), '', True)

            for item in data.get('artists', []):
                icon = self.getFullIconUrl(item['thumbnailUrl'])
                title = self.cleanHtmlStr(item['name'])
                url = self.getFullUrl('/artist/%s' % item['urlSafeName'])
                params = {'good_for_fav': True, 'category': 'list_artist_videos', 'title': title, 'url': url, 'icon': icon}
                artistsTab.append(params)

            for item in data.get('videos', []):
                icon = self.getFullIconUrl(item['thumbnailUrl'])
                url = self.getFullUrl('/watch/%s' % item['isrc'])
                titleTab = []
                titleTab.append(self.cleanHtmlStr(item['artists'][0]['name']))
                titleTab.append(self.cleanHtmlStr(item['title']))
                params = {'good_for_fav': True, 'category': 'video', 'title': ' - '.join(titleTab), 'url': url, 'icon': icon}
                videosTab.append(params)

            for item in data.get('playlists', []):
                icon = self.getFullIconUrl(item['image_url'])
                title = self.cleanHtmlStr(item['title'])
                url = self.getFullUrl('/watch/playlist/%s' % item['playlistId'])
                desc = [_('Count: %s') % item['videoCount']]
                desc.append(self.cleanHtmlStr(item.get('description', '')))
                params = {'good_for_fav': True, 'category': 'list_playlist', 'title': title, 'url': url, 'icon': icon, 'desc': '[/br]'.join(desc)}
                playlists.append(params)

            for item in [(_('Videos'), videosTab), (_('Playlists'), playlists), (_('Artists'), artistsTab)]:
                if 0 == len(item[1]):
                    continue
                params = dict(cItem)
                params.pop('page', 0)
                params.update({'good_for_fav': False, 'category': 'list_container_items', 'title': '%s (%s)' % (item[0], len(item[1])), 'container_items': item[1]})
                self.addDir(params)

        except Exception:
            printExc()

    def getLinksForVideo(self, cItem):
        printDBG("VevoCom.getLinksForVideo [%s]" % cItem)
        videoUrl = self.getFullUrl('watch/' + cItem['url'].split('/')[-1])
        return self.up.getVideoLinkExt(videoUrl)

    def getVideoLinks(self, videoLink):
        printDBG("VevoCom.getVideoLinks [%s]" % videoLink)
        urlTab = []

        return urlTab

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: |||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listMainMenu({'name': 'category'})
        elif category == 'list_genres_filters':
            self.listGenresFilters(self.currItem, 'list_items')
        elif category == 'list_genres':
            self.listItems(self.currItem)
        elif category == 'list_containers':
            self.listContainers(self.currItem, 'list_container_items', 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem)
        elif category == 'list_container_items':
            self.listContainerItems(self.currItem)
        elif category == 'list_playlist':
            self.listPlaylistItems(self.currItem)
        elif category == 'list_artists':
            self.listItems(self.currItem)
        elif category == 'list_artist_videos':
            self.listArtistVideos(self.currItem)

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
        CHostBase.__init__(self, VevoCom(), True, [])
