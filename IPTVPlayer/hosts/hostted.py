# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm, GetDefaultLang, CSelOneLink
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs import ph
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib
from datetime import timedelta
from urlparse import urljoin
###################################################


def gettytul():
    return 'https://ted.com/'


class TED(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'ted.com', 'cookie': 'ted.com.cookie'})
        self.USER_AGENT = 'User-Agent=Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})

        self.DEFAULT_ICON_URL = 'https://tedconfblog.files.wordpress.com/2015/03/jr-and-ted-logo.jpg?w=400'
        self.MAIN_URL = None

        self.cacheTalksFilters = []
        self.cachePlaylistsFilters = []
        self.cacheAllTopics = []
        self.cacheTalksLanguages = []
        self.cacheAllEvents = []

        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.defaultAjaxParams = dict(self.defaultParams)
        self.defaultAjaxParams['header'] = self.AJAX_HEADER

        self._getHeaders = None

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)

        addParams['cloudflare_params'] = {'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def getFullUrl(self, url):
        url = CBaseHostClass.getFullUrl(self, url)
        try:
            url.encode('ascii')
        except Exception:
            url = urllib.quote(url, safe="/:&?%@[]()*$!+-=|<>;")
        url = url.replace(' ', '%20').replace('&amp;', '&')
        return url

    def getFullIconUrl(self, url):
        url = self.getFullUrl(url)
        if url.startswith('https:'):
            url = 'http:' + url[6:]
        return url

    def selectDomain(self):
        self.MAIN_URL = 'https://ted.com/'
        self.MAIN_CAT_TAB = [{'category': 'list_talks_filters', 'title': _('Talks'), 'url': self.getFullUrl('/talks')},
                             {'category': 'list_playlists_filters', 'title': _('Playlists'), 'url': self.getFullUrl('/playlists')},

                             {'category': 'search', 'title': _('Search'), 'search_item': True, },
                             {'category': 'search_history', 'title': _('Search history'), }
                            ]

    def _addFilter(self, data, cacheTab, key, anyTitle='', titleBase=''):
        filtersTab = []
        for item in data:
            value = self.cm.ph.getSearchGroups(item, '''value=['"]([^'^"]+?)['"]''')[0]
            if value in ['', '...']:
                continue
            title = self.cleanHtmlStr(item)
            filtersTab.append({'title': titleBase + title, key: value})
        if anyTitle != '' and len(filtersTab):
            filtersTab.insert(0, {'title': anyTitle})
        if len(filtersTab):
            cacheTab.append(filtersTab)
            return True
        return False

    def _fillTalksFilters(self, cItem):
        self.cacheTalksFilters = []

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        # topics
        tmp = self.cm.ph.getDataBeetwenMarkers(data, "name='topics'", '</select>')[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<option', '</option>')
        if self._addFilter(tmp, self.cacheTalksFilters, 'f_topics', _('--Any--')):
            self.cacheTalksFilters[-1].append({'category': 'list_talks_topics_abc', 'title': _('See all topics'), 'f_url': self.getFullUrl('/topics/combo?models=Talks')})

        # languages
        tmp = self.cm.ph.getDataBeetwenMarkers(data, "name='language'", '</select>')[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<option', '</option>')
        if self._addFilter(tmp, self.cacheTalksFilters, 'f_language', _('--Any--')):
            self.cacheTalksFilters[-1].append({'category': 'list_talks_languages', 'title': _('See all languages'), 'f_url': self.getFullUrl('/languages/combo.json?per_page=10000')})

        # durations
        tmp = self.cm.ph.getDataBeetwenMarkers(data, "name='duration'", '</select>')[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<option', '</option>')
        self._addFilter(tmp, self.cacheTalksFilters, 'f_duration', _('--Any--'))

        # events
        tmp = self.cm.ph.getDataBeetwenMarkers(data, "name='event'", '</select>')[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<option', '</option>')
        if self._addFilter(tmp, self.cacheTalksFilters, 'f_event', _('--Any--')):
            self.cacheTalksFilters[-1].append({'category': 'list_talks_events_years', 'title': _('See all events'), 'f_url': self.getFullUrl('/talks/events')})

        # sort
        tmp = self.cm.ph.getDataBeetwenMarkers(data, "filters-sort", '</select>')[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<option', '</option>')
        self._addFilter(tmp, self.cacheTalksFilters, 'f_sort')

    def _fillPlaylistsFilters(self, cItem):
        self.cachePlaylistsFilters = []

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        # topics
        tmp = self.cm.ph.getDataBeetwenMarkers(data, "name='topics'", '</select>')[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<option', '</option>')
        if self._addFilter(tmp, self.cachePlaylistsFilters, 'f_topics', _('--Any--')):
            self.cachePlaylistsFilters[-1].append({'category': 'list_playlists_topics_abc', 'title': _('See all topics'), 'f_url': self.getFullUrl('/topics/combo?models=Talks')})

        # durations
        tmp = self.cm.ph.getDataBeetwenMarkers(data, "name='duration'", '</select>')[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<option', '</option>')
        self._addFilter(tmp, self.cachePlaylistsFilters, 'f_duration', _('--Any--'))

        # sort
        tmp = self.cm.ph.getDataBeetwenMarkers(data, "name='curator'", '</select>')[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<option', '</option>')
        self._addFilter(tmp, self.cachePlaylistsFilters, 'f_curator', _('--Any--'))

    def listFilters(self, cItem, cacheTab):
        params = dict(cItem)
        idx = params.get('f_idx', 0)
        params['f_idx'] = idx + 1
        if idx < len(cacheTab):
            self.listsTab(cacheTab[idx], params)

    def listTopicsABC(self, cItem, nextCategory):
        printDBG("TED.listTopicsABC")

        if 0 == len(self.cacheAllTopics):
            httpParams = dict(self.defaultAjaxParams)
            httpParams['header']['Referer'] = cItem['url']
            for url in [cItem['f_url'], 'http://textuploader.com/d0k96/raw']:
                sts, data = self.getPage(url, httpParams)
                if not sts:
                    continue
                try:
                    data = json_loads(data)
                    for item in data:
                        params = {'title': item['label'], 'f_topics': item['value']}
                        self.cacheAllTopics.append(params)
                    if len(self.cacheAllTopics):
                        break
                except Exception:
                    printExc()

        if len(self.cacheAllTopics):
            for item in ['A-B', 'C', 'D-F', 'G-K', 'L-M', 'N-O', 'P-R', 'S', 'T-Z']:
                params = dict(cItem)
                params.update({'category': nextCategory, 'title': item})
                self.addDir(params)

    def listTopics(self, cItem, nextCategory):
        printDBG("TED.listTopics")
        lettersRange = cItem['title'].split('-')

        cItem = dict(cItem)
        cItem.update({'category': nextCategory, 'f_idx': cItem.get('f_idx', 0) + 1})
        for item in self.cacheAllTopics:
            letter = item['f_topics'].upper()[0]
            if letter >= lettersRange[0] and letter <= lettersRange[-1]:
                params = dict(cItem)
                params.update(item)
                self.addDir(params)

    def listTalksLanguages(self, cItem, nextCategory):
        printDBG("TED.listTalksLanguages")
        if 0 == len(self.cacheTalksLanguages):
            httpParams = dict(self.defaultAjaxParams)
            httpParams['header']['Referer'] = cItem['url']

            sts, data = self.getPage(cItem['f_url'], httpParams)
            if not sts:
                return
            try:
                userLang = GetDefaultLang()
                promotItem = None
                data = json_loads(data)
                for item in data:
                    params = {'title': item['label'], 'f_language': item['value']}
                    if item['value'] == userLang:
                        promotItem = params
                    else:
                        self.cacheTalksLanguages.append(params)
                if promotItem != None:
                    self.cacheTalksLanguages.insert(0, promotItem)
            except Exception:
                printExc()

        params = dict(cItem)
        params.update({'category': nextCategory, 'f_idx': cItem.get('f_idx', 0) + 1})
        self.listsTab(self.cacheTalksLanguages, params)

    def listEventsYears(self, cItem, nextCategory):
        printDBG("TED.listEventsYears")

        if 0 == len(self.cacheAllEvents):
            httpParams = dict(self.defaultAjaxParams)
            httpParams['header']['Referer'] = cItem['url']
            for url in [cItem['f_url'], 'http://textuploader.com/d0k0n/raw']:
                sts, data = self.getPage(url, httpParams)
                if not sts:
                    continue
                try:
                    data = json_loads(data)
                    for item in data:
                        params = {'title': item['label'], 'f_event': item['value'], 'f_year': item['year']}
                        self.cacheAllEvents.append(params)
                    if len(self.cacheAllEvents):
                        break
                except Exception:
                    printExc()

        if len(self.cacheAllEvents):
            yearsTab = []
            for item in self.cacheAllEvents:
                if item['f_year'] in yearsTab:
                    continue
                params = dict(cItem)
                params.update({'category': nextCategory, 'title': item['f_year'], 'f_year': item['f_year']})
                self.addDir(params)
                yearsTab.append(item['f_year'])

    def listEvents(self, cItem, nextCategory):
        printDBG("TED.listEvents")
        year = cItem['f_year']

        cItem = dict(cItem)
        cItem.update({'category': nextCategory, 'f_idx': cItem.get('f_idx', 0) + 1})
        for item in self.cacheAllEvents:
            if item['f_year'] != year:
                continue
            params = dict(cItem)
            params.update(item)
            self.addDir(params)

    def listTalksItems(self, cItem):
        printDBG("TED.listTalksItems")

        url = cItem['url']
        page = cItem.get('page', 1)

        query = {}
        if page > 1:
            query['page'] = page

        queryParamsMap = {'f_topics': 'topics[]', 'f_language': 'language', 'f_duration': 'duration', 'f_event': 'event', 'f_sort': 'sort'}
        for key in cItem:
            if key not in queryParamsMap:
                continue
            query[queryParamsMap[key]] = cItem[key]

        query = urllib.urlencode(query)
        if '?' in url:
            url += '&' + query
        else:
            url += '?' + query

        sts, data = self.getPage(url)
        if not sts:
            return

        nextPage = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<a[^>]+?rel="next"[^>]+?href="([^"]+?)"''', ignoreCase=True)[0])
        if nextPage != '':
            nextPage = True

        data = self.cm.ph.getDataBeetwenMarkers(data, "browse-results", '<script>')[1]
        data = data.split("<div class='talk-link'>")
        if len(data):
            del data[0]
        if len(data):
            idx = data[-1].find('<div class="pagination">')
            if idx >= 0:
                data[-1] = data[-1][:idx]

        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''', ignoreCase=True)[0])
            if not self.cm.isValidUrl(url):
                continue
            icon = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''<img[^>]+?src=['"]([^'^"]+?)['"]''', ignoreCase=True)[0])

            tmp = self.cm.ph.getAllItemsBeetwenMarkers(item, '<h4', '</h4>')
            titles = []
            for t in tmp:
                t = self.cleanHtmlStr(t)
                if t != '':
                    titles.append(t)
            title = ': '.join(titles)

            duration = self.cm.ph.getSearchGroups(item, '<span[^>]+?duration[^>]*?>([^>]+?)<')[0]
            desc = self.cleanHtmlStr(item.split("</h4>")[-1])
            if duration != '':
                desc = duration + ' | ' + desc

            params = dict(cItem)
            params.update({'good_for_fav': True, 'title': title, 'url': url, 'desc': desc, 'icon': icon})
            self.addVideo(params)

        if nextPage:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _('Next page'), 'page': page + 1})
            self.addDir(params)

    def listPlaylists(self, cItem, nextCategory):
        printDBG("TED.listPlaylists")
        httpParams = dict(self.defaultAjaxParams)
        httpParams['header']['Referer'] = cItem['url']

        url = self.getFullUrl('/playlists/browse.json')
        page = cItem.get('page', 1)

        query = {}
        if page > 1:
            query['page'] = page
        query['per_page'] = 24

        queryParamsMap = {'f_topics': 'topics[]', 'f_duration': 'duration', 'f_curator': 'curator'}
        for key in cItem:
            if key not in queryParamsMap:
                continue
            query[queryParamsMap[key]] = cItem[key]

        query = urllib.urlencode(query)
        if '?' in url:
            url += '&' + query
        else:
            url += '?' + query

        sts, data = self.getPage(url, httpParams)
        if not sts:
            return
        nextPage = False
        try:
            data = json_loads(data)
            if page < data['metadata']['pageCount']:
                nextPage = True
            for item in data['records']:
                url = self.getFullUrl(item['url'])
                icon = self.getFullIconUrl(item['thumb'])
                title = self.cleanHtmlStr(item['title'])

                descTab = ['%s: %s' % (_('Talks'), item['talks'])]
                duration = str(timedelta(seconds=int(item['duration'])))
                if duration.startswith("0:"):
                    duration = duration[2:]
                descTab.append('%s: %s' % (_('Duration'), duration))
                descTab.append('%s: %s' % (_('Curator'), item['curator']))
                desc = '[/br]'.join(descTab)

                params = dict(cItem)
                params.update({'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'desc': desc, 'icon': icon})
                self.addDir(params)
        except Exception:
            printExc()

        if nextPage:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _('Next page'), 'page': page + 1})
            self.addDir(params)

    def listPlaylistItems(self, cItem):
        printDBG("TED.listTalksItems")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenMarkers(data, 'playlist-talks', '</ul>')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''', ignoreCase=True)[0])
            if not self.cm.isValidUrl(url):
                continue
            icon = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''<img[^>]+?src=['"]([^'^"]+?)['"]''', ignoreCase=True)[0])

            titles = [self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h9', '</h9>')[1])]
            speaker = self.cm.ph.getSearchGroups(item, '<a[^>]+?speaker[^>]*?>([^>]+?)<')[0]
            if speaker != '':
                titles.insert(0, speaker)
            title = ': '.join(titles)

            duration = self.cm.ph.getSearchGroups(item, '<span[^>]+?duration[^>]*?>([^>]+?)<')[0]
            desc = self.cleanHtmlStr(item.split("</h9>")[-1])
            if duration != '':
                desc = duration + ' | ' + desc

            params = dict(cItem)
            params.update({'good_for_fav': True, 'title': title, 'url': url, 'desc': desc, 'icon': icon})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("TED.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        page = cItem.get('page', 1)

        url = self.getFullUrl('/search?cat=%s&page=%s&per_page=12&q=%s' % (searchType, page, urllib.quote_plus(searchPattern)))

        sts, data = self.getPage(url)
        if not sts:
            return

        nextPage = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<a[^>]+?rel="next"[^>]+?href="([^"]+?)"''', ignoreCase=True)[0])
        if nextPage != '':
            nextPage = True

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<article', '</article>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''', ignoreCase=True)[0])
            if not self.cm.isValidUrl(url):
                continue
            icon = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''<img[^>]+?src=['"]([^'^"]+?)['"]''', ignoreCase=True)[0])
            tmp = item.split('</h3>')
            title = self.cleanHtmlStr(tmp[0])
            desc = self.cleanHtmlStr(tmp[-1])
            params = dict(cItem)
            params.update({'good_for_fav': True, 'title': title, 'url': url, 'desc': desc, 'icon': icon})
            if searchType == 'talks':
                self.addVideo(params)
            elif searchType == 'playlists':
                params['category'] = 'list_playlist_items'
                self.addDir(params)

        if nextPage:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _('Next page'), 'page': page + 1})
            self.addDir(params)

    def getLinksForVideo(self, cItem):
        printDBG("TED.getLinksForVideo [%s]" % cItem)
        subTracks = []
        urlTab = []

        #cItem['url'] = 'https://www.ted.com/talks/douglas_adams_parrots_the_universe_and_everything'

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return []

        def _addLinkItem(urlTab, item, url, namePrefix=''):
            try:
                if not self.cm.isValidUrl(url) and not url.startswith('merge://'):
                    return
                if 'width' in item and 'height' in item:
                    name = '%sx%s (%s)' % (item['width'], item['height'], item['bitrate'])
                else:
                    name = item.get('name', str(item['bitrate']))
                bitrate = item['bitrate']
                urlTab.append({'name': namePrefix + name, 'url': url, 'bitrate': bitrate, 'need_resolve': 0})
            except Exception:
                printExc()

        tmp = self.cm.ph.getDataBeetwenMarkers(data, 'talkPage.init",', ')<', False)[1]
        try:
            playerData = json_loads(tmp)['__INITIAL_DATA__']
            tmp = playerData.get('media', {}).get('internal', {})
            for key in tmp:
                bitrate = self.cm.ph.getSearchGroups(key, '([0-9]+)k')[0]
                if bitrate == '':
                    continue
                item = tmp[key]
                item['bitrate'] = int(bitrate)
                if '/mp4' not in item.get('mime_type', ''):
                    continue
                _addLinkItem(urlTab, item, item.get('uri', ''))

            tmp = playerData['talks'][0]['player_talks'][0]
            rtmpTab = tmp['resources'].get('rtmp', [])
            if rtmpTab == None:
                rtmpTab = []
            for item in rtmpTab:
                url = item.get('file', '')
                if not url.startswith('mp4:'):
                    continue
                url = 'https://pc.tedcdn.com/' + url[4:]
                _addLinkItem(urlTab, item, url)

            h264Tab = tmp['resources'].get('h264', [])
            if h264Tab == None:
                h264Tab = []
            for item in h264Tab:
                _addLinkItem(urlTab, item, item['file'])

            if len(h264Tab) == 1:
                reObj = re.compile('[/\-\.]([0-9]+k)\.')
                baseMp4Url = urlTab[-1]['url']
                baseBitrate = ph.search(baseMp4Url, reObj)[0]
                hlsItem = tmp['resources'].get('hls', {})
                if hlsItem == None:
                    hlsItem = {}
                url = hlsItem.get('stream', '')
                if url == None:
                    url = ''

                tmp = getDirectM3U8Playlist(self.cm.getFullUrl(url, self.cm.meta['url']), checkExt=False)
                for item in tmp:
                    url = item['url']
                    if url.startswith('merge://'):
                        url = url.meta.get('video_url', '')
                    bitrate = ph.search(url, reObj)[0]
                    url = baseMp4Url.replace(baseBitrate, bitrate)
                    printDBG(">> %s %s %s" % (url, baseMp4Url, url))
                    _addLinkItem(urlTab, item, url, '[MP4] ')
                #for item in tmp:
                #    _addLinkItem(urlTab, item, item['url'], '[HLS] ')

            def __getLinkQuality(itemLink):
                try:
                    return int(itemLink['bitrate'])
                except Exception:
                    return 0

            urlTab = CSelOneLink(urlTab, __getLinkQuality, 99999999).getSortedLinks()

            if 0 == len(urlTab):
                if self.cm.isValidUrl(tmp['external']['uri']):
                    urlTab.append({'name': tmp['external']['service'], 'url': tmp['external']['uri'], 'need_resolve': 1})

            userLang = GetDefaultLang()
            promotItem = None
            format = 'srt'
            for item in tmp.get('languages', []):
                subUrl = 'http://www.ted.com/talks/subtitles/id/%s/lang/%s/format/%s' % (tmp['id'], item['languageCode'], format)
                params = {'title': "%s (%s)" % (item['languageName'], item['endonym']), 'url': subUrl, 'lang': item['languageCode'], 'format': format}
                if item['languageCode'] == userLang:
                    promotItem = params
                else:
                    subTracks.append(params)

            if promotItem != None:
                subTracks.insert(0, promotItem)

            if len(subTracks):
                for idx in range(len(urlTab)):
                    urlTab[idx]['url'] = strwithmeta(urlTab[idx]['url'], {'external_sub_tracks': subTracks})

        except Exception:
            printExc()

        return urlTab

    def getVideoLinks(self, videoUrl):
        printDBG("LosMovies.getVideoLinks [%s]" % videoUrl)
        return self.up.getVideoLinkExt(videoUrl)

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

    # TALKS
        elif 'list_talks_filters' == category:
            idx = self.currItem.get('f_idx', 0)
            if idx == 0:
                self._fillTalksFilters(self.currItem)
            if idx < len(self.cacheTalksFilters):
                self.listFilters(self.currItem, self.cacheTalksFilters)
            else:
                self.listTalksItems(self.currItem)
        elif category == 'list_talks_topics_abc':
            self.listTopicsABC(self.currItem, 'list_talks_topics')
        elif category == 'list_talks_topics':
            self.listTopics(self.currItem, 'list_talks_filters')
        elif category == 'list_talks_languages':
            self.listTalksLanguages(self.currItem, 'list_talks_filters')
        elif category == 'list_talks_events_years':
            self.listEventsYears(self.currItem, 'list_talks_events')
        elif category == 'list_talks_events':
            self.listEvents(self.currItem, 'list_talks_filters')

    # PLAYLISTS
        elif 'list_playlists_filters' == category:
            idx = self.currItem.get('f_idx', 0)
            if idx == 0:
                self._fillPlaylistsFilters(self.currItem)
            if idx < len(self.cachePlaylistsFilters):
                self.listFilters(self.currItem, self.cachePlaylistsFilters)
            else:
                self.listPlaylists(self.currItem, 'list_playlist_items')
        elif category == 'list_playlists_topics_abc':
            self.listTopicsABC(self.currItem, 'list_playlists_topics')
        elif category == 'list_playlists_topics':
            self.listTopics(self.currItem, 'list_playlists_filters')
        elif category == 'list_playlist_items':
            self.listPlaylistItems(self.currItem)
    # PEOPLES
        # TOTO

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
        CHostBase.__init__(self, TED(), True, [])

    def getSearchTypes(self):
        searchTypesOptions = []
        searchTypesOptions.append((_("Talks"), "talks"))
        searchTypesOptions.append((_("Playlists"), "playlists"))

        return searchTypesOptions
