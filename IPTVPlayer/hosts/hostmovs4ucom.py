# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
###################################################

###################################################
# FOREIGN import
###################################################
import urlparse
import re
import urllib
try:
    import json
except Exception:
    import simplejson as json
###################################################


def gettytul():
    return 'https://movs4u.life/'


class Movs4uCOM(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'movs4u.life', 'cookie': 'movs4u.life.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})
        self.MAIN_URL = 'https://movs4u.life/'
        self.DEFAULT_ICON_URL = self.getFullIconUrl('/wp-content/uploads/2018/03/TcCsO2w.png')
        self.cacheLinks = {}
        self.cacheSeasons = {}
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.MAIN_CAT_TAB = [{'category': 'list_items', 'title': _('Movies'), 'url': self.getFullUrl('/movie/')},
                             {'category': 'list_items', 'title': _('Series'), 'url': self.getFullUrl('/tvshows/')},
                             {'category': 'list_items', 'title': _('Collections'), 'url': self.getFullUrl('/collection/')},
                             {'category': 'list_filters', 'title': _('Filters'), },

                             {'category': 'search', 'title': _('Search'), 'search_item': True, },
                             {'category': 'search_history', 'title': _('Search history'), }
                            ]

        self.FILTERS_CAT_TAB = [{'category': 'list_main', 'title': _('Alphabetically'), 'tab_id': 'abc'},
                                {'category': 'list_main', 'title': _('Categories'), 'tab_id': 'categories'},
                                {'category': 'list_main', 'title': _('Genres'), 'tab_id': 'genres'},
                                {'category': 'list_main', 'title': _('Qualities'), 'tab_id': 'qualities'},
                                {'category': 'list_main', 'title': _('Releases'), 'tab_id': 'releases'},
                               ]

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)

        origBaseUrl = baseUrl
        baseUrl = self.cm.iriToUri(baseUrl)
        printDBG('+++> [%s] - > [%s]' % (origBaseUrl, baseUrl))

        def _getFullUrl(url):
            if self.cm.isValidUrl(url):
                return url
            else:
                return urlparse.urljoin(baseUrl, url)

        addParams['cloudflare_params'] = {'domain': self.up.getDomain(baseUrl), 'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT, 'full_url_handle': _getFullUrl}
        sts, data = self.cm.getPageCFProtection(baseUrl, addParams, post_data)

        return sts, data

    def listMainItems(self, cItem, nextCategory):
        printDBG("Movs4uCOM.listMainItems")

        me = '</ul>'
        m1 = '<li'
        m2 = '</li>'

        tabID = cItem.get('tab_id', '')
        if tabID == 'categories':
            ms = '>ÃÂ§ÃÂÃÂÃÂ§ÃÂ¹ ÃÂ§ÃÂÃÂÃÂ§ÃÂ<'
        elif tabID == 'qualities':
            ms = '>ÃÂ¬ÃÂÃÂ¯ÃÂ§ÃÂª ÃÂ§ÃÂÃÂÃÂ§ÃÂ<'
        elif tabID == 'releases':
            ms = '<ul class="releases'
        elif tabID == 'genres':
            ms = '<ul class="genres'
        elif tabID == 'abc':
            ms = '<ul class="abc">'
        else:
            return

        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenMarkers(data, ms, me)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, m1, m2)
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            if not self.cm.isValidUrl(url):
                continue
            title = self.cleanHtmlStr(item)
            params = dict(cItem)
            params = {'good_for_fav': True, 'title': title, 'url': url}
            params['category'] = nextCategory
            self.addDir(params)

    def listItems(self, cItem, nextCategory):
        printDBG("Movs4uCOM.listItems [%s]" % cItem)
        page = cItem.get('page', 1)
        url = cItem['url']

        if page > 1:
            tmp = url.split('?')
            url = tmp[0]
            if url.endswith('/'):
                url = url[:-1]
            url += '/page/%s/' % page
            if len(tmp) > 1:
                url += '?' + '?'.join(tmp[1:])

        sts, data = self.getPage(url)
        if not sts:
            return

        if '/page/{0}/'.format(page + 1) in data:
            nextPage = True
        else:
            nextPage = False

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'class="content'), ('<div', '>', 'class="fixed-sidebar-blank"'))[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<article', '</article>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            if not self.cm.isValidUrl(url):
                continue
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<div class="title">', '</div>')[1])
            if title == '':
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h3', '</h3>')[1])
            if title == '':
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''alt=['"]([^"^']+?)['"]''')[0])

            desc = []
            # season
            #<span class="ses">S1</span>
            # episode
            #<span class="esp">E4</span>

            # year
            # tmp = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''<span[^>]*?>([0-9]{4})</span>''')[0])
            # if tmp != '': desc.append(tmp)
            # meta data
            tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<div class="meta', '</div>')[1].replace('</span>', ' |'))
            if tmp != '':
                desc.append(tmp)
            # quality
            tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<span class="quality">', '</span>')[1])
            if tmp != '':
                desc.append(tmp)
            # genres
            tmp = self.cm.ph.getDataBeetwenMarkers(item, '<div class="genres">', '</div>')[1]
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<a', '</a>')
            genres = []
            for t in tmp:
                t = self.cleanHtmlStr(t)
                if t != '':
                    genres.append(t)

            desc = ' | '.join(desc)
            if len(genres):
                desc += '[/br]' + ' | '.join(genres)

            tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<div class="texto"', '</div>')[1])
            if tmp == '':
                tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<div class="contenido', '</div>')[1])
            if tmp != '':
                desc += '[/br]' + tmp

            params = dict(cItem)
            params = {'good_for_fav': True, 'title': title, 'url': url, 'desc': desc, 'icon': icon}
            if '/collection/' in item:
                category = 'list_items'
            else:
                category = nextCategory
            params['category'] = category
            self.addDir(params)

        if nextPage and len(self.currList) > 0:
            params = dict(cItem)
            params.update({'title': _("Next page"), 'page': page + 1})
            self.addDir(params)

    def exploreItem(self, cItem, nextCategory=''):
        printDBG("Movs4uCOM.exploreItem")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        mainDesc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenReMarkers(data, re.compile('<div[^>]+?class="wp-content"[^>]*?>'), re.compile('</div>'))[1])
        mainIcon = self.cm.ph.getDataBeetwenMarkers(data, '<div class="poster"', '</div>')[1]
        mainIcon = self.getFullIconUrl(self.cm.ph.getSearchGroups(mainIcon, '''<img[^>]+?src=['"]([^"^']+?\.jpe?g[^"^']*?)["']''')[0])
        if mainIcon == '':
            mainIcon = cItem.get('icon', '')

        # trailer
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<div id="trailer"', '</div>')[1]
        url = self.getFullUrl(self.cm.ph.getSearchGroups(tmp, '''<iframe[^>]+?src=['"](https?://[^'^"]+?)['"]''')[0])
        if 1 == self.up.checkHostSupport(url):
            title = self.cleanHtmlStr(tmp)
            title = '%s - %s' % (cItem['title'], title)
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': title, 'prev_title': cItem['title'], 'url': url, 'prev_url': cItem['url'], 'prev_desc': cItem.get('desc', ''), 'icon': mainIcon, 'desc': mainDesc})
            self.addVideo(params)

        mainTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, '''<meta[^>]+?itemprop="name"[^>]+?content=['"]([^"^']+?)['"]''')[0])
        if mainTitle == '':
            mainTitle = cItem['title']

        self.cacheLinks = {}

        if '/tvshows/' in cItem['url']:
            _data = re.findall("class='imagen'.*?src='(.*?)'.*?numerando'>(.*?)<.*?episodiotitle.*?href='(.*?)'>(.*?)<", data, re.S)
            for (img_, num, url_, titre) in _data:
				params = {'name': 'categories', 'category': 'video', 'url': url_, 'title': '\c0000????' + num + ' \c00??????: ' + titre, 'icon': img_}
				self.addVideo(params)
        else:
            params = dict(cItem)
            params.update({'good_for_fav': True, 'title': mainTitle, 'icon': mainIcon, 'desc': mainDesc})
            self.addVideo(params)

    def listEpisodes(self, cItem):
        printDBG("Movs4uCOM.listEpisodes")

        sKey = cItem.get('s_key', -1)
        episodesList = self.cacheSeasons.get(sKey, [])

        for item in episodesList:
            params = dict(cItem)
            params.update(item)
            params.update({'good_for_fav': True})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Movs4uCOM.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('/?s=' + urllib.quote_plus(searchPattern))
        self.listItems(cItem, 'explore_item')

    def getLinksForVideo(self, cItem):
		printDBG("Movs4uCOM.getLinksForVideo [%s]" % cItem)
		retTab = []
		if 1 == self.up.checkHostSupport(cItem.get('url', '')):
			videoUrl = cItem['url'].replace('youtu.be/', 'youtube.com/watch?v=')
			return self.up.getVideoLinkExt(videoUrl)
		cacheTab = self.cacheLinks.get(cItem['url'], [])
		if len(cacheTab):
			return cacheTab
		currUrl = cItem['url']
		sts, data = self.getPage(currUrl)
		_data = re.findall("data-url='(.*?)'.*?title'>(.*?)<.*?server'>(.*?)<", data, re.S)
		for (data_url, titre1, srv) in _data:
			titre1 = titre1.replace('ÃÂ³ÃÂÃÂ±ÃÂÃÂ± ÃÂÃÂ´ÃÂ§ÃÂÃÂ¯ÃÂ© ÃÂ±ÃÂÃÂ', 'Server:')
			retTab.append({'name': titre1 + ' ' + '\c0000????(' + srv + ')', 'url': data_url, 'need_resolve': 1})
		return retTab

    def getVideoLinks(self, videoUrl):
		printDBG("Movs4uCOM.getVideoLinks [%s]" % videoUrl)
		videoUrl = strwithmeta(videoUrl)
		urlTab = []
		orginUrl = str(videoUrl)

		sts, data = self.getPage(videoUrl)
		_data2 = re.findall('<iframe.*?src="(.*?)"', data, re.S)
		if _data2:
			printDBG('_data2[0]=' + _data2[0])
			videoUrl = _data2[0]
			if 'gdriveplayer' in videoUrl:
				_data3 = re.findall('link=(.*?)&', videoUrl, re.S)
				if _data3:
					printDBG('_data3[0]=' + _data3[0])
					videoUrl = _data3[0]

		if self.cm.isValidUrl(videoUrl):
			urlTab = self.up.getVideoLinkExt(videoUrl)

		return urlTab

    def getFavouriteData(self, cItem):
        printDBG('Movs4uCOM.getFavouriteData')
        return json.dumps(cItem)

    def getLinksForFavourite(self, fav_data):
        printDBG('Movs4uCOM.getLinksForFavourite')
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
        printDBG('Movs4uCOM.setInitListFromFavouriteItem')
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
        printDBG("Movs4uCOM.getArticleContent [%s]" % cItem)
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
        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenReMarkers(data, re.compile('<div[^>]+?class="wp-content"[^>]*?>'), re.compile('</div>'))[1])

        mapDesc = {'Original title': 'alternate_title', 'IMDb Rating': 'imdb_rating', 'TMDb Rating': 'tmdb_rating', 'Status': 'status',
                   'Firt air date': 'first_air_date', 'Last air date': 'last_air_date', 'Seasons': 'seasons', 'Episodes': 'episodes'}
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="custom_fields">', '</div>')
        for item in tmp:
            item = item.split('<span class="valor">')
            if len(item) < 2:
                continue
            marker = self.cleanHtmlStr(item[0])
            key = mapDesc.get(marker, '')
            if key == '':
                continue
            value = self.cleanHtmlStr(item[1])
            if value != '':
                otherInfo[key] = value

        mapDesc = {'Director': 'directors', 'Cast': 'cast', 'Creator': 'creators'}

        tmp = self.cm.ph.getDataBeetwenReMarkers(data, re.compile('<div id="cast"[^>]+?>'), re.compile('fixidtab'))[1]
        tmp = self.cm.ph.rgetAllItemsBeetwenMarkers(tmp, '</div>', '<h2>')
        for item in tmp:
            marker = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h2', '</h2>')[1])
            key = mapDesc.get(marker, '')
            if key == '':
                continue
            item = self.cm.ph.getAllItemsBeetwenMarkers(item, '<div class="name">', '</div>')
            value = []
            for t in item:
                t = self.cleanHtmlStr(t)
                if t != '':
                    value.append(t)
            if len(value):
                otherInfo[key] = ', '.join(value)

        key = 'genres'
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<div class="sgeneros">', '</div>')[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<a', '</a>')
        value = []
        for t in tmp:
            t = self.cleanHtmlStr(t)
            if t != '':
                value.append(t)
        if len(value):
            otherInfo[key] = ', '.join(value)

        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div class="starstruck-rating">', '</div>')[1])
        if tmp != '':
            otherInfo['rating'] = tmp

        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<span class="qualityx">', '</span>')[1])
        if tmp != '':
            otherInfo['quality'] = tmp

        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<span class="country">', '</span>')[1])
        if tmp != '':
            otherInfo['country'] = tmp

        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<span class="runtime">', '</span>')[1])
        if tmp != '':
            otherInfo['duration'] = tmp

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
        elif category == 'list_filters':
            self.listsTab(self.FILTERS_CAT_TAB, self.currItem)
        elif category == 'list_main':
            self.listMainItems(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem, 'explore_item')
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
        CHostBase.__init__(self, Movs4uCOM(), True, [])

    def withArticleContent(self, cItem):
        if (cItem['type'] == 'video' and '/episodes/' not in cItem['url']) or cItem['category'] == 'explore_item':
            return True
        return False
