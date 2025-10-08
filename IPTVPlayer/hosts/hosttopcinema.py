# -*- coding: utf-8 -*-
# Last modified: 08/10/2025 - popking (odem2014)
###################################################
# LOCAL import
###################################################
# localization library
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
# host main class
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
# tools - write on log, write exception infos and merge dicts
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts
# add metadata to url
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
# library for json (instead of standard json.loads and json.dumps)
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
# read informations in m3u8
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.libs import ph
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import urljoin
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
###################################################
# FOREIGN import
###################################################
import re
import base64
###################################################


def get_config_list():
    return []


def gettytul():
    return 'https://web6.topcinema.cam/'  # main url of host


class TopCinema(CBaseHostClass):

    def __init__(self):
        # init global variables for this class

        CBaseHostClass.__init__(self, {'history': 'topcinema', 'cookie': 'topcinema.cookie'})  # names for history and cookie files in cache
        self.ph = ph

        # vars default values

        # various urls
        self.MAIN_URL = gettytul()
        self.SEARCH_URL = 'https://web6.topcinema.cam/search'

        # url for default icon
        self.DEFAULT_ICON_URL = "https://raw.githubusercontent.com/oe-mirrors/e2iplayer/gh-pages/Thumbnails/topcinema.png"

        # default header and http params
        self.HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.AJAX_HEADER = self.HEADER
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Sec-Fetch-Mode': 'cors', 'Sec-Fetch-Dest': 'empty', 'Sec-Fetch-Site': 'same-origin'})
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

    def getPage(self, base_url, add_params=None, post_data=None):
        if any(ord(c) > 127 for c in base_url):
            base_url = urllib_quote_plus(base_url, safe="://")
        if add_params is None:
            add_params = dict(self.defaultParams)
        add_params["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(base_url, add_params, post_data)

    def getLinksForVideo(self, cItem):
        printDBG("TopCinema.getLinksForVideo [%s]" % cItem)
        linksTab = []
        sts, data = self.getPage(cItem['url'], self.defaultParams)
        if not sts:
            return []

        # Try to find embedded iframes or direct <source> links, as fallback
        iframes = self.cm.ph.getAllItemsBeetwenMarkers(data, '<iframe', '>')
        for iframe in iframes:
            url = self.cm.ph.getSearchGroups(iframe, 'src="([^"]+)"')[0]
            if url and ('youtube' in url or 'vimeo' in url or 'embed' in url):
                linksTab.append({'name': self.up.getHostName(url).capitalize(),
                                 'url': strwithmeta(url, {'Referer': self.MAIN_URL}),
                                 'need_resolve': 1})

        video_links = self.cm.ph.getAllItemsBeetwenMarkers(data, 'source', '>')
        for link in video_links:
            url = self.cm.ph.getSearchGroups(link, 'src="([^"]+)"')[0]
            if url:
                linksTab.append({'name': self.up.getHostName(url).capitalize(),
                                 'url': strwithmeta(url, {'Referer': self.MAIN_URL}),
                                 'need_resolve': 1})

        # **If no links found by parsing the page, fallback to urlparser**
        if not linksTab:
            printDBG("TopCinema.getLinksForVideo: no direct links found, calling getVideoLinks()")
            # Delegate to getVideoLinks for parser-based resolution
            resolved = self.getVideoLinks(cItem['url'])
            printDBG("TopCinema.getLinksForVideo: resolved via parser: %s" % str(resolved))
            # The parser returns list of dicts or a list of playable links
            for entry in resolved:
                # If entry is a dict already
                if isinstance(entry, dict):
                    linksTab.append(entry)
                else:
                    # If it's just a URL or something else
                    linksTab.append({'url': entry, 'name': self.up.getHostName(cItem['url'])})

        return linksTab

    def getVideoLinks(self, url):
        printDBG("TopCinema.getVideoLinks [%s]" % url)
        urlTab = []
        if self.cm.isValidUrl(url):
            return self.up.getVideoLinkExt(url)
        return urlTab

    def listMainMenu(self, cItem):
        # items of main menu
        printDBG('TopCinema.listMainMenu')

        # Define main categories statically like FilmPalast does
        self.MAIN_CAT_TAB = [
            {'category': 'movies_folder', 'title': _('الافلام')},
            {'category': 'series_folder', 'title': _('المسلسلات')},
        ] + self.searchItems()

        # Define subcategories for each folder
        self.MOVIES_CAT_TAB = [
            {'category': 'list_items', 'title': _('افلام Netfilx'), 'url': self.getFullUrl('/netflix-movies/')},
            {'category': 'list_items', 'title': _('افلام اجنبي'), 'url': self.getFullUrl('/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%a7%d8%ac%d9%86%d8%a8%d9%8a-3/')},
            {'category': 'list_items', 'title': _('افلام اسيوية'), 'url': self.getFullUrl('/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%a7%d8%b3%d9%8a%d9%88%d9%8a/')},
            {'category': 'list_items', 'title': _('افلام انيمى'), 'url': self.getFullUrl('/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%a7%d9%86%d9%85%d9%8a-2/')},
            {'category': 'list_items', 'title': _('Top Rated IMDB'), 'url': self.getFullUrl('/top-rating-imdb/')}
        ]

        self.SERIES_CAT_TAB = [
            {'category': 'series', 'title': _('مسلسلات اجنبى نيتفليكس'), 'url': self.getFullUrl('/netflix-series/?cat=7')},
            {'category': 'series', 'title': _('مسلسلات اجنبي'), 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%a7%d8%ac%d9%86%d8%a8%d9%8a-3/')},
            {'category': 'series', 'title': _('مسلسلات اسيوى نيتفليكس'), 'url': self.getFullUrl('/netflix-series/?cat=9')},
            {'category': 'series', 'title': _('مسلسلات اسيوية'), 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%a7%d8%b3%d9%8a%d9%88%d9%8a%d8%a9-10/')},
            {'category': 'series', 'title': _('مسلسلات انيمى نيتفليكس'), 'url': self.getFullUrl('/netflix-series/?cat=8')},
            {'category': 'series', 'title': _('مسلسلات انيمى'), 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%a7%d9%86%d9%85%d9%8a-2/')},
            {'category': 'series', 'title': _('Top Rated IMDB'), 'url': self.getFullUrl('/top-rating-imdb-series/')}
        ]

        # Display main categories
        self.listsTab(self.MAIN_CAT_TAB, cItem)

    def listMoviesFolder(self, cItem):
        printDBG('TopCinema.listMoviesFolder')
        self.listsTab(self.MOVIES_CAT_TAB, cItem)

    def listSeriesFolder(self, cItem):
        printDBG('TopCinema.listSeriesFolder')
        self.listsTab(self.SERIES_CAT_TAB, cItem)

    def listItems(self, cItem):
        printDBG("TopCinema.listItems [%s]" % cItem)
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="Posts--List SixInRow', '<div class="paginate', False)[1]
        data_items = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<div class="Small--Box', '</a>', False)

        if not data_items:
            data_items = tmp.split('<div class="Small--Box')[1:]
            data_items = ['<div class="Small--Box' + i for i in data_items]

        for m in data_items:
            title = self.cm.ph.getSearchGroups(m, r'title=["\']([^"\']+)["\']')[0]
            title = title.replace('مترجم اون لاين', '').strip()

            pureurl = self.cm.ph.getSearchGroups(m, r'href=["\']([^"\']+)["\']')[0]
            if not pureurl:
                continue

            baseurl, filenameurl = pureurl.rsplit('/', 1)
            fixedfilenameurl = urllib_quote_plus(filenameurl)
            url = baseurl + '/' + fixedfilenameurl

            pureicon = self.cm.ph.getSearchGroups(m, r'data-src=["\']([^"\']+)["\']')[0]
            if not pureicon:
                pureicon = self.cm.ph.getSearchGroups(m, r'src=["\']([^"\']+)["\']')[0]

            icon = ''
            if pureicon:
                baseicon, filenameicon = pureicon.rsplit('/', 1)
                fixedfilenameicon = urllib_quote_plus(filenameicon)
                icon = baseicon + '/' + fixedfilenameicon

            params = {'category': 'explore_item', 'title': title, 'icon': icon, 'url': url}
            printDBG(str(params))
            self.addDir(params)

        # === PAGINATION HANDLING ===
        pagination = self.cm.ph.getDataBeetwenMarkers(data, '<div class="paginate">', '</div>', False)[1]
        next_page = self.cm.ph.getSearchGroups(pagination, r'<a[^>]+href="([^"]+)"[^>]*>\s*&raquo;\s*</a>')[0]
        prev_page = self.cm.ph.getSearchGroups(pagination, r'<a[^>]+href="([^"]+)"[^>]*>\s*&laquo;\s*</a>')[0]

        if next_page:
            next_page = self.getFullUrl(next_page)
            params = dict(cItem)
            params.update({'title': 'Next Page ▶', 'url': next_page, 'category': 'list_items'})
            self.addDir(params)

        if prev_page:
            prev_page = self.getFullUrl(prev_page)
            params = dict(cItem)
            params.update({'title': '◀ Previous Page', 'url': prev_page, 'category': 'list_items'})
            self.addDir(params)


    def listSeriesItems(self, cItem):
        printDBG("TopCinema.listSeriesItems ----------")

        sts, data = self.getPage(cItem['url'])
        printDBG("data.listSeriesItems ||||||||||||||||||||||||||||||||||||")
        printDBG(data)
        if not sts:
            return
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="Posts--List SixInRow', '<div class="paginate', False)[1]
        printDBG("tmp.listSeriesItems ||||||||||||||||||||||||||||||||||||")
        printDBG(tmp)
        data_items = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<div class="Small--Box', '</a>', False)
        printDBG("data_items.listSeriesItems ||||||||||||||||||||||||||||||||||||")
        printDBG(data_items)
        if not data_items:
            data_items = tmp.split('<div class="Small--Box')[1:]
            data_items = ['<div class="Small--Box' + i for i in data_items]

        for m in data_items:
            title = self.cm.ph.getSearchGroups(m, r'title=["\']([^"\']+)["\']')[0]
            #title = re.sub(r'\s*مترجم\s*أ?ون\s*لاين\s*', '', title).strip()

            pureurl = self.cm.ph.getSearchGroups(m, r'href=["\']([^"\']+)["\']')[0]
            if not pureurl:
                continue

            baseurl, filenameurl = pureurl.rsplit('/', 1)
            fixedfilenameurl = urllib_quote_plus(filenameurl)
            url = baseurl + '/' + fixedfilenameurl

            pureicon = self.cm.ph.getSearchGroups(m, r'data-src=["\']([^"\']+)["\']')[0]
            if not pureicon:
                pureicon = self.cm.ph.getSearchGroups(m, r'src=["\']([^"\']+)["\']')[0]

            icon = ''
            if pureicon:
                baseicon, filenameicon = pureicon.rsplit('/', 1)
                fixedfilenameicon = urllib_quote_plus(filenameicon)
                icon = baseicon + '/' + fixedfilenameicon

            if url in ['/series/', '/assemblies/']:
                url = urljoin(url, 'list/')

            params = {'category': 'show_seasons', 'title': title, 'icon': icon, 'url': url}
            printDBG(str(params))
            self.addDir(params)

        # === PAGINATION HANDLING ===
        pagination = self.cm.ph.getDataBeetwenMarkers(data, '<div class="paginate">', '</div>', False)[1]
        next_page = self.cm.ph.getSearchGroups(pagination, r'<a[^>]+href="([^"]+)"[^>]*>\s*&raquo;\s*</a>')[0]
        prev_page = self.cm.ph.getSearchGroups(pagination, r'<a[^>]+href="([^"]+)"[^>]*>\s*&laquo;\s*</a>')[0]

        if next_page:
            next_page = self.getFullUrl(next_page)
            params = dict(cItem)
            params.update({'title': 'Next Page ▶', 'url': next_page, 'category': 'list_items'})
            self.addDir(params)

        if prev_page:
            prev_page = self.getFullUrl(prev_page)
            params = dict(cItem)
            params.update({'title': '◀ Previous Page', 'url': prev_page, 'category': 'list_items'})
            self.addDir(params)

    def exploreItems(self, cItem):
        printDBG('TopCinema.exploreItems')
        url = cItem['url']
        printDBG("|||||||||||||||||exploreUrl||||||||||||||||||||")
        printDBG(url)
        base_url = urljoin(cItem['url'].replace('list/', ''), 'watch/')
        printDBG("|||||||||||||||||base_url||||||||||||||||||||")
        printDBG(base_url)
        sts, data = self.getPage(base_url)
        printDBG("||||||||||||||||||exploreitems_data|||||||||||||||||||||")
        #printDBG(data)
        if not sts:
            return
        ajaxURL = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''MyAjaxURL = ['"]([^"^']+?)['"]''')[0])
        printDBG("|||||||||||||||||ajaxURL||||||||||||||||||||")
        printDBG(ajaxURL)
        tmp = self.cm.ph.getDataBeetwenMarkers(data, ('<h2', '>', 'watch--servers-title'), ('</ul', '>'), True)[1]
        printDBG(tmp)
        tmp2 = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li', ('</li', '>'))
        printDBG("|||||||||||||||||tmp2_data||||||||||||||||||||")
        printDBG(tmp2)
        for item in tmp2:
            Sid = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''data-id=['"]([^"^']+?)['"]''')[0])
            Serv = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''data-server=['"]([^"^']+?)['"]''')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<span', '>'), ('</span', '>'), False)[1])

            post_data = {'id': Sid, 'i': Serv}

            params = dict(self.defaultParams)
            params['header'] = dict(self.AJAX_HEADER)
            params['header']['Referer'] = self.cm.meta['url']
            params['header']['Origin'] = self.getMainUrl()
            params['header']['Host'] = self.up.getDomain(base_url)

            sts, data = self.getPage(urljoin(ajaxURL, 'Single/Server.php'), params, post_data)
            if not sts:
                return

            url = self.getFullUrl(self.ph.search(data, self.ph.IFRAME_SRC_URI_RE)[1])
            printDBG("|||||||||||||||||data_post_data||||||||||||||||||||")
            printDBG(data)

            params = MergeDicts(cItem, {
                'title': title,
                'url': url,
                'type': 'video',
                'category': 'video',
                'need_resolve': 1
            })
            self.addVideo(params)

    def exploreSeriesItems(self, cItem):
        printDBG('TopCinema.exploreSeriesItems')
        url = cItem['url']
        sts, data = self.getPage(url)

        if not sts:
            return

        # Extract the block that contains episodes
        episodes_block = self.cm.ph.getDataBeetwenMarkers(data,
            '<ul class="episodes__list', '</ul>', False)[1]

        printDBG('Episodes block:')
        #printDBG(episodes_block)

        episodes = self.cm.ph.getAllItemsBeetwenMarkers(episodes_block, '<li', '</li>')
        episodes.reverse()

        for item in episodes:
            episode_url = self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0]
            if not episode_url:
                continue
            episode_url = self.getFullUrl(episode_url).rstrip('/') + '/watch'

            # Extract episode number only, and prepend "الحلقة"
            episode_number = self.cm.ph.getSearchGroups(item, '<div class="epi__num">.*?<b>([^<]+)</b>')[0]
            if episode_number:
                title = 'الحلقة %s' % episode_number.strip()
            else:
                title = self.cleanHtmlStr(item)  # or fallback to generic title

            params = dict(cItem)
            params.update({
                'title': title,
                'url': episode_url,
                'icon': cItem.get('icon', ''),
                'desc': cItem.get('desc', ''),
                'category': 'explore_item',
            })

            printDBG('Adding episode: %s' % str(params))
            self.addDir(params)

    def safe_b64decode(self, data):
        """Base64 decode with automatic padding fix."""
        data += '=' * (-len(data) % 4)
        return base64.b64decode(data).decode('utf-8')

    def showSeasons(self, cItem):
        printDBG("TopCinema.showSeasons >>> %s" % cItem)
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        # Debug output for inspection
        printDBG("====== showSeasons PAGE DATA ======")
        printDBG(data)
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<section class="allseasonss', '</section>', False)[1]
        seasons = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<div class="Small--Box Season', '</a>')
        seasons.reverse()

        printDBG("====== showSeasons seasons DATA ======")
        printDBG(seasons)

        for s in seasons:
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(s, r'<h3[^>]*class="title"[^>]*>([^<]+)</h3>')[0])
            if not title:
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(s, r'alt="([^"]+)"')[0])
            url = self.cm.ph.getSearchGroups(s, r'href="([^"]+)"')[0]
            if not url:
                continue
            url = self.getFullUrl(url)

            params = dict(cItem)
            params.update({
                'title': title or 'Season',
                'url': urljoin(url, 'list/'),
                'category': 'show_episodes',
            })
            self.addDir(params)

    def showEpisodes(self, cItem):
        printDBG("TopCinema.showSeasons >>> %s" % cItem)
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        printDBG("====== showEpisodes episodes DATA ======")
        printDBG(data)
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="Posts--List SixInRow">', '<div class="paginate">', False)[1]
        printDBG("====== showEpisodes tmp DATA ======")
        printDBG(tmp)
        data_items = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<div class="Small--Box', '</a>', False)
        data_items.reverse()
        printDBG("====== showEpisodes data_items DATA in reverse ======")
        printDBG(data_items)

        if not data_items:
            data_items = tmp.split('<div class="Small--Box')[1:]
            data_items = ['<div class="Small--Box' + i for i in data_items]

        for m in data_items:
            title = self.cm.ph.getSearchGroups(m, r'title=["\']([^"\']+)["\']')[0]
            #title = re.sub(r'\s*مترجم\s*أ?ون\s*لاين\s*', '', title).strip()

            pureurl = self.cm.ph.getSearchGroups(m, r'href=["\']([^"\']+)["\']')[0]
            if not pureurl:
                continue

            baseurl, filenameurl = pureurl.rsplit('/', 1)
            fixedfilenameurl = urllib_quote_plus(filenameurl)
            url = baseurl + '/' + fixedfilenameurl

            pureicon = self.cm.ph.getSearchGroups(m, r'data-src=["\']([^"\']+)["\']')[0]
            if not pureicon:
                pureicon = self.cm.ph.getSearchGroups(m, r'src=["\']([^"\']+)["\']')[0]

            icon = ''
            if pureicon:
                baseicon, filenameicon = pureicon.rsplit('/', 1)
                fixedfilenameicon = urllib_quote_plus(filenameicon)
                icon = baseicon + '/' + fixedfilenameicon

            params = {'category': 'explore_item', 'title': title, 'icon': icon, 'url': urljoin(url, 'watch/'),}
            printDBG(str(params))
            self.addDir(params)

        # === PAGINATION HANDLING ===
        pagination = self.cm.ph.getDataBeetwenMarkers(data, '<div class="paginate">', '</div>', False)[1]
        next_page = self.cm.ph.getSearchGroups(pagination, r'<a[^>]+href="([^"]+)"[^>]*>\s*&raquo;\s*</a>')[0]
        prev_page = self.cm.ph.getSearchGroups(pagination, r'<a[^>]+href="([^"]+)"[^>]*>\s*&laquo;\s*</a>')[0]

        if next_page:
            next_page = self.getFullUrl(next_page)
            params = dict(cItem)
            params.update({'title': 'Next Page ▶', 'url': next_page, 'category': 'list_items'})
            self.addDir(params)

        if prev_page:
            prev_page = self.getFullUrl(prev_page)
            params = dict(cItem)
            params.update({'title': '◀ Previous Page', 'url': prev_page, 'category': 'list_items'})
            self.addDir(params)


    def listSearchResult(self, cItem, search_pattern, search_type):
        printDBG("TopCinema.listSearchResult cItem[%s], search_pattern[%s] search_type[%s]" % (cItem, search_pattern, search_type))
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('/search?q=') + urllib_quote_plus(search_pattern)
        self.listItems(cItem)

    def getFavouriteData(self, cItem):
        printDBG('TopCinema.getFavouriteData')
        return json_dumps(cItem)

    def getLinksForFavourite(self, fav_data):
        printDBG('TopCinema.getLinksForFavourite')
        links = []
        try:
            cItem = json_loads(fav_data)
            links = self.getLinksForVideo(cItem)
        except Exception:
            printExc()
        return links

    def setInitListFromFavouriteItem(self, fav_data):
        printDBG('TopCinema.setInitListFromFavouriteItem')
        try:
            cItem = json_loads(fav_data)
        except Exception:
            cItem = {}
            printExc()
        return cItem

    def handleService(self, index, refresh=0, search_pattern='', search_type=''):
        printDBG('TopCinema.handleService start')

        CBaseHostClass.handleService(self, index, refresh, search_pattern, search_type)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')

        printDBG("handleService: >> name[%s], category[%s] " % (name, category))
        self.currList = []

        # MAIN MENU
        if name is None:
            self.listMainMenu({'name': 'category'})
        elif category == 'list_items':
            self.listItems(self.currItem)
        elif category == 'series':
            self.listSeriesItems(self.currItem)
        # FOLDERS
        elif category == 'movies_folder':
            self.listMoviesFolder(self.currItem)
        elif category == 'series_folder':
            self.listSeriesFolder(self.currItem)
        elif category == 'explore_item':
            self.exploreItems(self.currItem)
        elif category == 'explore_episodes':
            self.exploreSeriesItems(self.currItem)
        elif category == 'show_seasons':
            self.showSeasons(self.currItem)
        elif category == 'show_episodes':
            self.showEpisodes(self.currItem)
        # SEARCH
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category'})
            self.listSearchResult(cItem, search_pattern, search_type)
        # HISTORY SEARCH
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, TopCinema(), True, [])

    def withArticleContent(self, cItem):
        if 'video' == cItem.get('type', '') or 'explore_item' == cItem.get('category', ''):
            return True

        return False
