# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify, GetTmpDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
###################################################

###################################################
# FOREIGN import
###################################################
import urlparse
import re
import urllib
from copy import deepcopy
try:
    import json
except Exception:
    import simplejson as json
###################################################

###################################################
# E2 GUI COMMPONENTS
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvmultipleinputbox import IPTVMultipleInputBox
###################################################


def gettytul():
    return 'https://moovie.cc/'


class MoovieCC(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'moovie.cc', 'cookie': 'moovie.cc.cookie'})
        self.DEFAULT_ICON_URL = 'https://moovie.cc/images/logo.png'
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.99 Safari/537.36'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})
        self.MAIN_URL = 'https://moovie.cc/'
        self.cacheLinks = {}
        self.cacheSortOrder = []
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.MAIN_CAT_TAB = [{'category': 'list_movies', 'title': _('Movies')},
                             {'category': 'list_series', 'title': _('Series')},
                             {'category': 'list_main', 'title': 'Legjobbra értékelt', 'tab_id': 'now_watched'},
                             {'category': 'list_main', 'title': 'Épp most nézik', 'tab_id': 'best_rated'},
                             {'category': 'search', 'title': _('Search'), 'search_item': True, },
                             {'category': 'search_history', 'title': _('Search history'), }
                            ]

        self.MOVIES_CAT_TAB = [{'category': 'movies_cats', 'title': _('Categories'), 'url': self.getFullUrl('/online-filmek/')},
                               {'category': 'list_main', 'title': 'Premier filmek', 'tab_id': 'prem_movies'},
                               {'category': 'list_main', 'title': 'Népszerű online filmek', 'tab_id': 'pop_movies'},
                              ]

        self.SERIES_CAT_TAB = [{'category': 'series_cats', 'title': _('Categories'), 'url': self.getFullUrl('/online-sorozatok/')},
                               {'category': 'list_main', 'title': 'Népszerű online sorozatok', 'tab_id': 'pop_series'},
                               {'category': 'list_main', 'title': 'Új Epizódok', 'tab_id': 'new_episodes'},
                              ]

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)

        def _getFullUrl(url):
            if self.cm.isValidUrl(url):
                return url
            else:
                return urlparse.urljoin(baseUrl, url)

        addParams['cloudflare_params'] = {'domain': self.up.getDomain(baseUrl), 'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT, 'full_url_handle': _getFullUrl}
        sts, data = self.cm.getPageCFProtection(baseUrl, addParams, post_data)
        return sts, data

    def listMainItems(self, cItem, nextCategory):
        printDBG("MoovieCC.listMainItems")

        me = '</ul></ul>'
        m1 = '<li'
        m2 = '</li>'

        tabID = cItem.get('tab_id', '')
        if tabID == 'prem_movies':
            ms = 'Premier filmek'
        elif tabID == 'best_rated':
            ms = 'Épp most nézik'
        elif tabID == 'pop_series':
            ms = 'Népszerű online sorozatok'
        elif tabID == 'new_episodes':
            ms = 'Új Epizódok'
            me = '</table>'
            m1 = '<tr'
            m2 = '</tr>'
        elif tabID == 'now_watched':
            ms = 'Még több jó film »'
        elif tabID == 'pop_movies':
            ms = 'Még több népszerű film »'
        else:
            return

        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenMarkers(data, ms, '</ul></ul>')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, m1, m2)
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            if not self.cm.isValidUrl(url):
                continue

            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?\.jpe?g[^'^"]*?)['"]''')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<a class="title', '</a>')[1])
            if title == '':
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''bubble=['"]([^"^']+?)['"]''')[0])
            if title == '':
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h2', '</h2>')[1])

            # get desc
            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<p', '</p>')[1])
            if desc == '':
                desc = []
                tmp = self.cm.ph.getAllItemsBeetwenMarkers(item, '<td', '</td>')
                if len(tmp):
                    del tmp[0]
                for t in tmp:
                    if '/flags/' in t:
                        t = self.cm.ph.getSearchGroups(t, '''<img[^>]+?src=['"][^"^']+?/([^/]+?)\.png['"]''')[0]
                    t = self.cleanHtmlStr(t)
                    if t != '':
                        desc.append(t)
                desc = ' | '.join(desc)

            params = dict(cItem)
            params = {'good_for_fav': True, 'title': title, 'url': url, 'desc': desc, 'icon': icon}
            params['category'] = nextCategory
            self.addDir(params)

    def listItems(self, cItem, nextCategory):
        printDBG("MoovieCC.listItems")
        url = cItem['url']
        sort = cItem.get('f_sort', '')

        cItem = dict(cItem)
        if cItem.get('f_query', '') == '':
            sts, data = self.getPage(cItem['url'])
            if not sts:
                return
            cItem['f_page'] = 1
            tmp = self.cm.ph.getDataBeetwenMarkers(data, '<div id="content">', '<script')[1]
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<input', '>')
            inputCache = {}
            cItem['filters'] = []
            for item in tmp:
                name = self.cm.ph.getSearchGroups(item, '''name=['"]([^"^']+?)['"]''')[0]
                if name == '':
                    continue
                value = self.cm.ph.getSearchGroups(item, '''value=['"]([^"^']+?)['"]''')[0]
                inputCache[name] = value
            tmp = self.cm.ph.getDataBeetwenMarkers(data, 'function dataFromInput', '}')[1]
            tmp = re.compile('''\[name=([^\]]+?)\]''').findall(tmp)
            for item in tmp:
                cItem['filters'].append(item)
                if item in ['sort', 'page']:
                    continue
                cItem['f_' + item] = inputCache.get(item, '')
            tmp = self.cm.ph.getDataBeetwenMarkers(data, '$.ajax(', '});', False)[1]
            cItem['url'] = self.getFullUrl(self.cm.ph.getSearchGroups(tmp, '''['"]?url['"]?\s*:\s*['"]([^'^"]+?)['"]''')[0])
            cItem['f_query'] = self.cm.ph.getSearchGroups(tmp, '''['"]?data['"]?\s*:\s*['"]([^'^"]+?)['"]''')[0]

        # prepare query
        query = []
        for filter in cItem.get('filters', []):
            name = 'f_' + filter
            if name in cItem:
                value = cItem[name]
                if not str(value).startswith(filter + ':'):
                    value = '%s:%s' % (filter, cItem[name])
                if not value.endswith('|'):
                    value += '|'
                query.append(value)

        query = cItem.get('f_query', '') + (''.join(query))

        urlParams = dict(self.defaultParams)
        urlParams.update({'raw_post_data': True})
        sts, data = self.getPage(cItem['url'], urlParams, query)
        if not sts:
            return

        nextPage = self.cm.ph.getSearchGroups(data, '''pages_num\s*=\s*([0-9]+?)[^0-9]''')[0]
        if nextPage != '' and int(nextPage) > 0:
            nextPage = True
        else:
            nextPage = False

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'id="movie', '<div class="clear')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            if not self.cm.isValidUrl(url):
                continue

            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<a class="title', '</a>')[1])
            if title == '':
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''bubble=['"]([^"^']+?)['"]''')[0])
            if title == '':
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h2', '</h2>')[1])
            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<p', '</p>')[1])

            params = dict(cItem)
            params = {'good_for_fav': True, 'title': title, 'url': url, 'desc': desc, 'icon': icon}
            params['category'] = nextCategory
            self.addDir(params)

        if nextPage and len(self.currList) > 0:
            params = dict(cItem)
            params.update({'title': _("Next page"), 'f_page': cItem.get('f_page', 1) + 1})
            self.addDir(params)

    def _listCategories(self, cItem, nextCategory, m1, m2):
        printDBG("MoovieCC._listCategories")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenMarkers(data, m1, m2)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div', '</div>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href\s*=\s*['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'category': nextCategory, 'title': title, 'url': url})
            self.addDir(params)

    def listMovies(self, cItem, nextCategory):
        printDBG("MoovieCC.listMovies")
        self._listCategories(cItem, nextCategory, 'id="get_movies"', '</li>')

    def listSeries(self, cItem, nextCategory):
        printDBG("MoovieCC.listSeries")
        self._listCategories(cItem, nextCategory, 'id="get_series"', '</li>')

    def listSort(self, cItem, nextCategory):
        printDBG("MoovieCC.listSeries")
        if 0 == len(self.cacheSortOrder):
            sts, data = self.getPage(self.getFullUrl('/online-filmek/')) # sort order is same for movies and series
            if not sts:
                return
            data = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="sort_by">', '</ul>')[1]
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
            for item in data:
                if not self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0].startswith('javascript'):
                    continue
                sort = self.cm.ph.getSearchGroups(item, '''id=['"]([^'^"]+?)['"]''')[0]
                if sort == '':
                    continue
                title = self.cleanHtmlStr(item)
                self.cacheSortOrder.append({'title': title, 'f_sort': sort})

        for item in self.cacheSortOrder:
            params = dict(cItem)
            params.update({'category': nextCategory})
            params.update(item)
            self.addDir(params)

    def _fillLinksCache(self, data, marker):
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, marker, '</table>')
        episodesTab = []
        for tmp in data:
            episodeName = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(tmp, '<h2', '</h2>')[1])

            tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<tr', '</tr>')
            for item in tmp:
                printDBG(item)
                url = self.cm.ph.getSearchGroups(item, '''href=['"](https?://[^'^"]+?)['"]''')[0]
                tmpUrl = self.cm.ph.getSearchGroups(url, '''/(https?://[^'^"]+?)$''')[0]
                if self.cm.isValidUrl(tmpUrl):
                    url = tmpUrl
                printDBG(">>> " + url)
                if not self.cm.isValidUrl(url):
                    continue
                serverName = []
                item = self.cm.ph.getAllItemsBeetwenMarkers(item, '<td', '</td>')
                for t in item:
                    if '/flags/' in t:
                        t = self.cm.ph.getSearchGroups(t, '''<img[^>]+?src=['"][^"^']+?/([^/]+?)\.png['"]''')[0]
                    t = self.cleanHtmlStr(t)
                    if t != '':
                        serverName.append(t)
                serverName = ' | '.join(serverName)

                if episodeName not in episodesTab:
                    episodesTab.append(episodeName)
                    self.cacheLinks[episodeName] = []
                self.cacheLinks[episodeName].append({'name': serverName, 'url': url, 'need_resolve': 1})
        return episodesTab

    def exploreItem(self, cItem, nextCategory=''):
        printDBG("MoovieCC.exploreItem")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div id="plot">', '</div>')[1])
        icon = self.cm.ph.getDataBeetwenMarkers(data, '<div id="poster"', '</div>')[1]
        icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(icon, '''<img[^>]+?src=['"]([^"^']+?\.jpe?g[^"^']*?)["']''')[0])
        if icon == '':
            icon = cItem.get('icon', '')

        # trailer
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<a id="youtube_video"', '</a>')[1]
        url = self.getFullUrl(self.cm.ph.getSearchGroups(tmp, '''href=['"]([^'^"]+?)['"]''')[0])
        if 1 == self.up.checkHostSupport(url):
            title = self.cleanHtmlStr(tmp)
            title = '%s - %s' % (cItem['title'], title)
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': title, 'prev_title': cItem['title'], 'url': url, 'prev_url': cItem['url'], 'prev_desc': cItem.get('desc', ''), 'icon': icon, 'desc': desc})
            self.addVideo(params)

        sourcesLink = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'streambtn'), ('</div', '>'), caseSensitive=False)[1]
        sourcesLink = self.cm.ph.getSearchGroups(sourcesLink, '''href=['"](https?://[^'^"]+?)['"]''')[0]
        if not self.cm.isValidUrl(sourcesLink):
            printDBG("MoovieCC.exploreItem - missing link for sources")
            return

        tmp = urllib.unquote(sourcesLink)
        tmp = self.cm.ph.getSearchGroups(tmp[1:], '''(https?://.+)''')[0]
        if tmp != '':
            sourcesLink = tmp

        sts, data = self.getPage(sourcesLink)
        if not sts:
            return []

        desc2 = self.cm.ph.getDataBeetwenMarkers(data, '<article', '</article>')[1]
        mainTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(desc2, '<h1>', '</h1>')[1])
        if mainTitle == '':
            mainTitle = cItem['title']

        self.cacheLinks = {}

        if 'seasonList' in data:
            # list seasons
            data = self.cm.ph.getDataBeetwenMarkers(data, '<nav>', '</nav>')[1]
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
            for item in data:
                url = self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0]
                if url != '' and not self.cm.isValidUrl(url):
                    url = urlparse.urljoin(sourcesLink, url)
                title = self.cleanHtmlStr(item)
                params = dict(cItem)
                params.update({'good_for_fav': False, 'category': nextCategory, 'title': title, 'prev_title': mainTitle, 'url': url, 'prev_url': cItem['url'], 'prev_desc': cItem.get('desc', ''), 'icon': icon, 'desc': desc})
                self.addDir(params)
        else:
            desc2 = self.cleanHtmlStr(desc2)
            if desc2 != '':
                desc = desc2
            episodesList = self._fillLinksCache(data, '<table')
            for item in episodesList:
                params = dict(cItem)
                params.update({'good_for_fav': False, 'links_key': item, 'title': mainTitle, 'icon': icon, 'desc': desc})
                self.addVideo(params)

    def listEpisodes(self, cItem):
        printDBG("MoovieCC.listEpisodes")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<article', '</article>')[1])

        seriesTitle = cItem.get('prev_title', '')
        sNum = self.cm.ph.getSearchGroups(cItem['title'], '''^([0-9]+?)\.''')[0]

        episodesList = self._fillLinksCache(data, '<div class="item">')
        for item in episodesList:
            eNum = self.cm.ph.getSearchGroups(item, '''^([0-9]+?)\.''')[0]
            params = dict(cItem)
            title = seriesTitle
            if eNum != '' and sNum != '':
                title = '%s - s%se%s' % (seriesTitle, sNum.zfill(2), eNum.zfill(2))
            else:
                title = '%s - %s, %s' % (seriesTitle, cItem['title'], item)
            params.update({'good_for_fav': False, 'title': title, 'links_key': item, 'prev_desc': cItem.get('desc', ''), 'desc': desc})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("MoovieCC.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('/core/ajax/movies.php')
        cItem['f_query'] = 'type=search&query=keywords:%s|' % searchPattern
        cItem['f_page'] = 1
        cItem['filters'] = ['page']
        self.listItems(cItem, 'explore_item')

    def getLinksForVideo(self, cItem):
        printDBG("MoovieCC.getLinksForVideo [%s]" % cItem)
        retTab = []
        if 1 == self.up.checkHostSupport(cItem.get('url', '')):
            videoUrl = cItem['url'].replace('youtu.be/', 'youtube.com/watch?v=')
            return self.up.getVideoLinkExt(videoUrl)
        key = cItem.get('links_key', '')
        return self.cacheLinks.get(key, [])

    def getVideoLinks(self, videoUrl):
        printDBG("MoovieCC.getVideoLinks [%s]" % videoUrl)
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

        orginUrl = str(videoUrl)
        url = videoUrl
        post_data = None
        while True:
            sts, data = self.getPage(url, post_data=post_data)
            if not sts:
                return []
            videoUrl = self.cm.meta['url']

            if self.up.getDomain(self.getMainUrl()) in videoUrl or self.up.getDomain(videoUrl) == self.up.getDomain(orginUrl):

                if 'captcha' in data:
                    data = re.sub("<!--[\s\S]*?-->", "", data)

                if 'google.com/recaptcha/' in data and 'sitekey' in data:
                    message = _('Link protected with google recaptcha v2.')
                    SetIPTVPlayerLastHostError(message)
                    break
                elif '<input name="captcha"' in data:
                    tmp = self.cm.ph.getDataBeetwenMarkers(data, '<content', '</form>')[1]
                    captchaTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(tmp, '<h1', '</h1>')[1])
                    captchaDesc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(tmp, '<p', '</p>')[1])

                    # parse form data
                    data = self.cm.ph.getDataBeetwenMarkers(data, '<form', '</form>')[1]

                    imgUrl = self.cm.ph.getSearchGroups(data, 'src="([^"]+?)"')[0]
                    if imgUrl != '' and not imgUrl.startswith('/'):
                        imgUrl = '/' + imgUrl
                    if imgUrl.startswith('/'):
                        imgUrl = urlparse.urljoin(videoUrl, imgUrl)

                    printDBG("img URL [%s]" % imgUrl)

                    actionUrl = self.cm.ph.getSearchGroups(data, 'action="([^"]+?)"')[0]
                    if actionUrl != '':
                        actionUrl = '/' + actionUrl
                    if actionUrl.startswith('/'):
                        actionUrl = urlparse.urljoin(videoUrl, actionUrl)
                    elif actionUrl == '':
                        actionUrl = videoUrl

                    captcha_post_data = dict(re.findall(r'''<input[^>]+?name=["']([^"^']*)["'][^>]+?value=["']([^"^']*)["'][^>]*>''', data))

                    if self.cm.isValidUrl(imgUrl):
                        params = dict(self.defaultParams)
                        params['header'] = dict(params['header'])
                        params['header']['Accept'] = 'image/png,image/*;q=0.8,*/*;q=0.5'
                        params = dict(self.defaultParams)
                        params.update({'maintype': 'image', 'subtypes': ['jpeg', 'png'], 'check_first_bytes': ['\xFF\xD8', '\xFF\xD9', '\x89\x50\x4E\x47'], 'header': params['header']})
                        filePath = GetTmpDir('.iptvplayer_captcha.jpg')
                        ret = self.cm.saveWebFile(filePath, imgUrl.replace('&amp;', '&'), params)
                        if not ret.get('sts'):
                            SetIPTVPlayerLastHostError(_('Fail to get "%s".') % imgUrl)
                            return urlTab

                        params = deepcopy(IPTVMultipleInputBox.DEF_PARAMS)
                        params['accep_label'] = _('Send')
                        params['title'] = captchaTitle
                        params['status_text'] = captchaDesc
                        params['with_accept_button'] = True
                        params['list'] = []
                        item = deepcopy(IPTVMultipleInputBox.DEF_INPUT_PARAMS)
                        item['label_size'] = (160, 75)
                        item['input_size'] = (480, 25)
                        item['icon_path'] = filePath
                        item['title'] = _('Answer')
                        item['input']['text'] = ''
                        params['list'].append(item)

                        ret = 0
                        retArg = self.sessionEx.waitForFinishOpen(IPTVMultipleInputBox, params)
                        printDBG(retArg)
                        if retArg and len(retArg) and retArg[0]:
                            printDBG(retArg[0])
                            captcha_post_data['captcha'] = retArg[0][0]
                            post_data = captcha_post_data
                            url = actionUrl

                        if not sts:
                            return urlTab
                        else:
                            continue

                found = False
                printDBG(data)
                tmp = re.compile('''<iframe[^>]+?src=['"]([^"^']+?)['"]''', re.IGNORECASE).findall(data)
                for url in tmp:
                    if 1 == self.up.checkHostSupport(url):
                        videoUrl = url
                        found = True
                        break
                if not found or 'flashx' in videoUrl:
                    tmp = self.cm.ph.getAllItemsBeetwenMarkers(data, 'embedFrame', '</a>')
                    tmp.extend(self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>'))
                    for urlItem in tmp:
                        url = self.cm.ph.getSearchGroups(urlItem, '''href=['"](https?://[^'^"]+?)['"]''')[0]
                        if 1 == self.up.checkHostSupport(url):
                            videoUrl = url
                            found = True
                            break
            break

        if self.cm.isValidUrl(videoUrl):
            urlTab = self.up.getVideoLinkExt(videoUrl)

        return urlTab

    def getFavouriteData(self, cItem):
        printDBG('MoovieCC.getFavouriteData')
        return json.dumps(cItem)

    def getLinksForFavourite(self, fav_data):
        printDBG('MoovieCC.getLinksForFavourite')
        if self.MAIN_URL == None:
            self.selectDomain()
        links = []
        try:
            cItem = byteify(json.loads(fav_data))
            links = self.getLinksForVideo(cItem)
        except Exception:
            printExc()
        return links

    def setInitListFromFavouriteItem(self, fav_data):
        printDBG('MoovieCC.setInitListFromFavouriteItem')
        if self.MAIN_URL == None:
            self.selectDomain()
        try:
            params = byteify(json.loads(fav_data))
        except Exception:
            params = {}
            printExc()
        self.addDir(params)
        return True

    def getArticleContent(self, cItem):
        printDBG("MoovieCC.getArticleContent [%s]" % cItem)
        retTab = []

        otherInfo = {}

        url = cItem.get('prev_url', '')
        if url == '':
            url = cItem.get('url', '')

        sts, data = self.getPage(url)
        if not sts:
            return retTab

        title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, '''<meta[^>]+?itemprop="name"[^>]+?content="([^"]+?)"''')[0])
        icon = self.cm.ph.getDataBeetwenMarkers(data, '<div id="poster"', '</div>')[1]
        icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(icon, '''<img[^>]+?src=['"]([^"^']+?\.jpe?g[^"^']*?)["']''')[0])
        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div id="plot"', '</div>')[1])

        rating = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<span class="rating_all"', '</div>')[1])

        data = self.cm.ph.getDataBeetwenMarkers(data, '<table style="margin-left', '</table>')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<tr', '</tr>')
        mapDesc = {'Eredeti Cím:': 'alternate_title', 'Év:': 'year', 'Játékidő:': 'duration', 'IMDb értékelés:': 'imdb_rating',
                   'Kategória:': 'category', 'Írta:': 'writers', 'Rendezte:': 'directors', 'Szereplők:': 'actors'} #'Megtekintve:':'views',
        for item in data:
            item = self.cm.ph.getAllItemsBeetwenMarkers(item, '<td', '</td>')
            if len(item) != 2:
                continue
            marker = self.cleanHtmlStr(item[0])
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(item[1], '<a', '</a>')
            value = []
            for t in tmp:
                t = self.cleanHtmlStr(t)
                if t != '':
                    value.append(t)
            if len(value):
                value = ', '.join(value)
            else:
                value = self.cleanHtmlStr(item[1])
            if value == '':
                continue
            key = mapDesc.get(marker, '')
            if key != '':
                otherInfo[key] = value

        if rating != '':
            otherInfo['rating'] = rating

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

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.cacheLinks = {}
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})
        elif category == 'list_movies':
            self.listsTab(self.MOVIES_CAT_TAB, self.currItem)
        elif category == 'list_series':
            self.listsTab(self.SERIES_CAT_TAB, self.currItem)
        elif category == 'movies_cats':
            self.listMovies(self.currItem, 'list_sort')
        elif category == 'series_cats':
            self.listSeries(self.currItem, 'list_sort')
        elif category == 'list_sort':
            self.listSort(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem, 'explore_item')
        elif category == 'list_main':
            self.listMainItems(self.currItem, 'explore_item')
        elif category == 'explore_item':
            self.exploreItem(self.currItem, 'list_episodes')
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
        CHostBase.__init__(self, MoovieCC(), True, [])

    def withArticleContent(self, cItem):
        if (cItem['type'] != 'video' and cItem['category'] != 'explore_item'):
            return False
        return True
