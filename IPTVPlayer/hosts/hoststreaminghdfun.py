# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
###################################################

###################################################
# FOREIGN import
###################################################
import urlparse
import re
import urllib
###################################################


def gettytul():
    return 'https://streaminghd.online/'


class StreamingHDFun(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'streaminghd.fun', 'cookie': 'streaminghd.fun.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.MAIN_URL = 'https://streaminghd.online/'
        self.DEFAULT_ICON_URL = 'https://www.pitupitu.pl/files/QMQNlOEPWQjUCVWov3CCWIVv0zs/coverBig'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate', 'Referer': self.getMainUrl(), 'Origin': self.getMainUrl()}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding': 'gzip, deflate', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json, text/javascript, */*; q=0.01'})

        self.cacheLinks = {}
        self.defaultParams = {'header': self.HTTP_HEADER, 'with_metadata': True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        origBaseUrl = baseUrl
        baseUrl = self.cm.iriToUri(baseUrl)

        def _getFullUrl(url):
            if self.cm.isValidUrl(url):
                return url
            else:
                return urlparse.urljoin(baseUrl, url)
        addParams['cloudflare_params'] = {'domain': self.up.getDomain(baseUrl), 'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT, 'full_url_handle': _getFullUrl}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def setMainUrl(self, url):
        if self.cm.isValidUrl(url):
            self.MAIN_URL = self.cm.getBaseUrl(url)

    def listMainMenu(self, cItem):
        printDBG("StreamingHDFun.listMainMenu")

        MAIN_CAT_TAB = [{'category': 'sub_menu', 'title': 'Film', 'url': self.getMainUrl()},
                        {'category': 'sub_menu', 'title': 'Serie Tv', 'url': self.getFullUrl('/serietv/')},
                        {'category': 'sub_menu', 'title': 'Anime', 'url': self.getFullUrl('/anime/')},
                        {'category': 'top', 'title': 'TOP IMDb', 'url': self.getFullUrl('/top-imdb/')},
                        {'category': 'search', 'title': _('Search'), 'search_item': True},
                        {'category': 'search_history', 'title': _('Search history')}, ]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listSubMenu(self, cItem, nextCategory1, nextCategory2):
        printDBG("StreamingHDFun.listSubMenu")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        cUrl = data.meta['url']
        self.setMainUrl(cUrl)

        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'head-main-nav'), ('</div', '>'), False)[1]
        tmp = self.cm.ph.getAllItemsBeetwenNodes(tmp, ('<a', '</a>', '/piu-'), ('</li', '>'))
        for item in tmp:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            title = self.cleanHtmlStr(item)
            params = {'name': 'category', 'type': 'category', 'category': nextCategory2, 'title': title, 'url': url}
            self.addDir(params)

        tmp = [self.cm.ph.getDataBeetwenNodes(data, ('<nav', '>', 'genres'), ('</nav', '>'), False)[1]]
        tmp.append(self.cm.ph.getDataBeetwenNodes(data, ('<nav', '>', 'releases'), ('</nav', '>'), False)[1])
        for section in tmp:
            sTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(section, ('<h', '>'), ('</h', '>'), False)[1])
            section = self.cm.ph.getAllItemsBeetwenNodes(section, ('<li', '>'), ('</li', '>'), False)
            subItems = []
            for item in section:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
                title = self.cleanHtmlStr(item)
                params = {'name': 'category', 'type': 'category', 'category': nextCategory2, 'title': title, 'url': url}
                subItems.append(params)

            if len(subItems):
                params = {'name': 'category', 'type': 'category', 'category': nextCategory1, 'title': sTitle, 'sub_items': subItems}
                self.addDir(params)

    def listSubItems(self, cItem):
        printDBG("StreamingHDFun.listSubItems")
        self.currList = cItem['sub_items']

    def listItems(self, cItem, nextCategory, data=None):
        printDBG("InteriaTv.listItems")
        page = cItem.get('page', 1)

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(data.meta['url'])

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'pagination'), ('</div', '>'))[1]
        nextPage = self.getFullUrl(self.cm.ph.getSearchGroups(nextPage, '''<a[^>]+?href=['"]([^"^']+?)['"][^>]*?>\s*?{0}\s*?<'''.format(page + 1))[0])

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<article', '>'), ('</article', '>'))
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h3', '</h3>')[1])
            if title == '':
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'title'), ('</div', '>'))[1])
            if cItem['url'].endswith('/seasons/'):
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''alt=['"]([^"^']+?)['"]''')[0])
            sTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<span', '>', 'serie'), ('</span', '>'))[1])
            if sTitle != '':
                title = '%s %s' % (sTitle, title)

            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<p', '</p>')[1])
            descTab = []
            rating = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'rating'), ('</div', '>'))[1])
            item = self.cm.ph.getAllItemsBeetwenMarkers(item, '<span', '</span>')
            for t in item:
                t = self.cleanHtmlStr(t)
                if t != '':
                    descTab.append(t)
            if rating != '':
                descTab.append('%s/10' % rating)
            desc = ' | '.join(descTab) + '[/br]' + desc
            params = {'good_for_fav': True, 'priv_has_art': True, 'category': nextCategory, 'url': url, 'title': title, 'desc': desc, 'icon': icon}
            if '/episodi/' in url:
                self.addVideo(params)
            else:
                self.addDir(params)

        if nextPage != '':
            params = dict(cItem)
            params.update({'title': _('Next page'), 'url': nextPage, 'page': page + 1})
            self.addDir(params)

    def listTop(self, cItem, nextCategory1, nextCategory2):
        printDBG("InteriaTv.listTop")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(data.meta['url'])

        reObj = re.compile('''<div[^>]+?top\-imdb\-item[^>]*>''', re.IGNORECASE)
        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'top-imdb-list'), ('<script', '>'), False)[1]
        data = re.compile('''<div[^>]+?top\-imdb\-list[^>]*>''', re.IGNORECASE).split(data)
        for section in data:
            sTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(section, '<h3', '</h3>')[1])
            section = reObj.split(section)
            if len(section):
                del section[0]
            subItems = []
            for item in section:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
                icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''')[0])
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'title'), ('</div', '>'))[1])
                descTab = []
                number = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'puesto'), ('</div', '>'))[1])
                rating = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'rating'), ('</div', '>'))[1])
                descTab.append(number)
                descTab.append('%s/10' % (rating))
                params = {'good_for_fav': True, 'priv_has_art': True, 'name': 'category', 'type': 'category', 'category': nextCategory2, 'title': title, 'url': url, 'desc': ' '.join(descTab), 'icon': icon}
                subItems.append(params)

            if len(subItems):
                params = {'name': 'category', 'type': 'category', 'category': nextCategory1, 'title': sTitle, 'sub_items': subItems}
                self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("StreamingHDFun.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        if searchType == 'movies':
            url = '/'
        else:
            url = '/serietv/'

        url = self.getFullUrl(url + '?s=') + urllib.quote_plus(searchPattern)
        cItem = dict(cItem)
        cItem.update({'url': url, 'category': 'list_items'})
        self.listItems(cItem, 'explore_item')

    def getEpisodes(self, data, iTitle, iIcon):
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<li', '>'), ('</li', '>'))
        episodesTab = []
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''')[0])
            if icon == '':
                icon = iIcon

            numer = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'numerando'), ('</div', '>'))[1])
            title = self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'episodiotitle'), ('</div', '>'))[1].split('</a>', 1)
            desc = self.cleanHtmlStr(title[-1])
            title = self.cleanHtmlStr(title[0])

            params = {'good_for_fav': True, 'priv_has_art': True, 'type': 'video', 'url': url, 'title': '%s: %s %s' % (iTitle, numer, title), 'desc': desc, 'icon': icon}
            episodesTab.append(params)
        return episodesTab

    def exploreItem(self, cItem, nextCategory):
        printDBG("InteriaTv.listItems")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        cUrl = data.meta['url']
        self.setMainUrl(cUrl)

        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'trailer'), ('</div', '>'))[1]
        iTrailer = self.getFullUrl(self.cm.ph.getSearchGroups(tmp, '''<iframe[^>]+?src=['"]([^"^']+?youtube[^"^']+?)['"]''', 1, True)[0])

        iIcon = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'poster'), ('<script', '>'))[1]
        iTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(iIcon, '<h1', '</h1>')[1])
        iIcon = self.getFullIconUrl(self.cm.ph.getSearchGroups(iIcon, '''<img[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0])

        if '/film/' in cUrl or '/episodi/' in cUrl:
            if '/links/' in data or 'play-box' in data:
                params = dict(cItem)
                self.addVideo(params)
        elif '/serietv/' in cUrl:
            data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'seasons'), ('<', '>', 'script'))
            for seasonData in data:
                seasonData = seasonData.split('</ul>')
                for season in seasonData:
                    sTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(season, ('<div', '>', '"se-'), ('</div', '>'))[1])
                    episodesTab = self.getEpisodes(season, iTitle, iIcon)
                    if len(episodesTab):
                        params = {'good_for_fav': False, 'category': nextCategory, 'title': sTitle, 'sub_items': episodesTab, 'desc': '', 'icon': iIcon}
                        self.addDir(params)
        elif '/seasons/' in cUrl:
            data = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'episodios'), ('</ul', '>'))[1]
            self.currList = self.getEpisodes(data, iTitle, iIcon)

        if iTrailer != '':
            params = {'good_for_fav': False, 'url': iTrailer, 'title': '%s - %s' % (iTitle, _('trailer')), 'icon': iIcon}
            self.addVideo(params)

    def getLinksForVideo(self, cItem):
        printDBG("StreamingHDFun.getLinksForVideo [%s]" % cItem)

        if 1 == self.up.checkHostSupport(cItem.get('url', '')):
            videoUrl = cItem['url'].replace('youtu.be/', 'youtube.com/watch?v=')
            return self.up.getVideoLinkExt(videoUrl)

        cacheKey = cItem['url']
        cacheTab = self.cacheLinks.get(cacheKey, [])
        if len(cacheTab):
            return cacheTab

        self.cacheLinks = {}

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        cUrl = data.meta['url']
        self.setMainUrl(cUrl)

        retTab = []

        namesData = {}
        tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<a', '>', 'options'), ('</a', '>'))
        for item in tmp:
            name = self.cleanHtmlStr(item)
            id = self.cm.ph.getSearchGroups(item, '''href=['"]#([^"^']+?)['"]''', 1, True)[0]
            namesData[id] = name

        tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'play-box'), ('</div', '>'))
        for item in tmp:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0])
            #if 1 != self.up.checkHostSupport(url): continue
            id = self.cm.ph.getSearchGroups(item, '''id=['"]([^"^']+?)['"]''', 1, True)[0]
            name = namesData.get(id, '') + _(' main link')
            if name == '':
                name = self.up.getHostName(url)
            retTab.append({'name': name, 'url': strwithmeta(url, {'Referer': cUrl}), 'need_resolve': 1})

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'links_table'), ('</table', '>'))[1].split('<tbody', 1)[-1]
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<tr', '>'), ('</tr', '>'))
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])

            item = self.cm.ph.getAllItemsBeetwenNodes(item, ('<td', '>'), ('</td', '>'))
            if len(item) < 2:
                continue
            fakeHostUrl = 'http://%s/' % self.cleanHtmlStr(item[1]).lower()
            #if 1 != self.up.checkHostSupport(fakeHostUrl): continue
            title = []
            for idx in range(1, len(item)):
                title.append(self.cleanHtmlStr(item[idx]))
            title = ' | '.join(title)
            retTab.append({'name': title, 'url': strwithmeta(url, {'Referer': cUrl}), 'need_resolve': 1})

        if len(retTab):
            self.cacheLinks[cacheKey] = retTab

        return retTab

    def getVideoLinks(self, baseUrl):
        printDBG("StreamingHDFun.getVideoLinks [%s]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
        urlTab = []

        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if baseUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name'] + '*'
                        break

        if 1 == self.up.checkHostSupport(baseUrl):
            urlTab = self.up.getVideoLinkExt(baseUrl)
        else:
            paramsUrl = dict(self.defaultParams)
            paramsUrl['header'] = dict(self.AJAX_HEADER)
            paramsUrl['header']['Referer'] = baseUrl.meta['Referer']

            sts, data = self.getPage(baseUrl, paramsUrl)
            if not sts:
                return
            printDBG(data)
            try:
                videoUrl = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''location\.href=['"]([^"^']+?)['"]''', 1, True)[0])
                if videoUrl == '':
                    videoUrl = data.meta['url']
                urlTab = self.up.getVideoLinkExt(videoUrl)
            except Exception:
                printExc()

        return urlTab

    def getArticleContent(self, cItem):
        printDBG("StreamingHDFun.getArticleContent [%s]" % cItem)

        retTab = []

        otherInfo = {}

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return []
        cUrl = data.meta['url']
        self.setMainUrl(cUrl)

        if '/episodes/' in cUrl:
            m1 = 'info'
        else:
            m1 = 'sheader'
        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', m1), ('<script', '>'), False)[1]

        icon = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'poster'), ('</div', '>'))[1]
        title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(icon, '<h1', '</h1>')[1])
        icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(icon, '''<img[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0])
        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'wp-content'), ('</div', '>'))[1])

        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'starstruck-rating'), ('</div', '>'), False)[1])
        if tmp != '':
            otherInfo['rating'] = tmp
        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<b', '</b>', 'IMDb Rating'), ('</div', '>'), False)[1])
        if tmp != '':
            otherInfo['imdb_rating'] = tmp
        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<b', '</b>', 'TMDb Rating'), ('</div', '>'), False)[1])
        if tmp != '':
            otherInfo['tmdb_rating'] = tmp
        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<b', '</b>', 'Original title'), ('</div', '>'), False)[1])
        if tmp != '':
            otherInfo['original_title'] = tmp
        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<b', '</b>', 'Status'), ('</div', '>'), False)[1])
        if tmp != '':
            otherInfo['status'] = tmp
        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<b', '</b>', 'Stagioni'), ('</div', '>'), False)[1])
        if tmp != '':
            otherInfo['seasons'] = tmp
        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<b', '</b>', 'Episodi'), ('</div', '>'), False)[1])
        if tmp != '':
            otherInfo['episodes'] = tmp
        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<span', '>', 'date'), ('</span', '>'), False)[1])
        if tmp != '':
            otherInfo['released'] = tmp
        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<span', '>', 'country'), ('</span', '>'), False)[1])
        if tmp != '':
            otherInfo['country'] = tmp
        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<span', '>', 'runtime'), ('</span', '>'), False)[1])
        if tmp != '':
            otherInfo['duration'] = tmp
        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<a', '>', '/network/'), ('</a', '>'), False)[1])
        if tmp != '':
            otherInfo['station'] = tmp

        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'sgeneros'), ('</div', '>'), False)[1]
        tmp = self.cm.ph.getAllItemsBeetwenNodes(tmp, ('<a', '>'), ('</a', '>'), False)
        if len(tmp):
            otherInfo['genres'] = self.cleanHtmlStr(', '.join(tmp))

        creators = []
        actors = []
        directors = []

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'persons'), ('<div', '>', 'info'), False)[1].split('class="person"')
        for item in data:
            name = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'name'), ('</div', '>'), False)[1])
            caracter = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'caracter'), ('</div', '>'), False)[1]).lower()
            if caracter == 'director':
                directors.append(name)
            elif caracter == 'creator':
                creators.append(name)
            elif name != '':
                actors.append(name)

        if 1 == len(directors):
            otherInfo['director'] = self.cleanHtmlStr(', '.join(directors))
        elif 1 < len(directors):
            otherInfo['directors'] = self.cleanHtmlStr(', '.join(directors))
        if 1 == len(creators):
            otherInfo['creator'] = self.cleanHtmlStr(', '.join(creators))
        elif 1 < len(creators):
            otherInfo['creators'] = self.cleanHtmlStr(', '.join(creators))
        if len(actors):
            otherInfo['actors'] = self.cleanHtmlStr(', '.join(actors))

        if title == '':
            title = cItem['title']
        if icon == '':
            icon = cItem.get('icon', self.DEFAULT_ICON_URL)

        return [{'title': self.cleanHtmlStr(title), 'text': self.cleanHtmlStr(desc), 'images': [{'title': '', 'url': self.getFullUrl(icon)}], 'other_info': otherInfo}]

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: |||| name[%s], category[%s] " % (name, category))
        self.cacheLinks = {}
        self.currList = []

    #MAIN MENU
        if name == None and category == '':
            rm(self.COOKIE_FILE)
            self.listMainMenu({'name': 'category'})
        elif category == 'sub_menu':
            self.listSubMenu(self.currItem, 'sub_items', 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem, 'explore_item')
        elif category == 'sub_items':
            self.listSubItems(self.currItem)
        elif category == 'top':
            self.listTop(self.currItem, 'sub_items', 'explore_item')
        elif category == 'explore_item':
            self.exploreItem(self.currItem, 'sub_items')
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
        CHostBase.__init__(self, StreamingHDFun(), True, [])

    def withArticleContent(self, cItem):
        if cItem.get('priv_has_art', False):
            return True
        else:
            return False

    def getSearchTypes(self):
        searchTypesOptions = []
        searchTypesOptions.append((_('Movies'), "movies"))
        searchTypesOptions.append((_('Series'), "series"))
        return searchTypesOptions
