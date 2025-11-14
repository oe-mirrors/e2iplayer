# -*- coding: utf-8 -*-
# Last modified: 14/11/2025 - popking (odem2014)
# typical import for a standard host
###################################################
# LOCAL import
###################################################
# localization library
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
# host main class
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
# tools - write on log, write exception infos and merge dicts
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts, E2ColoR
# add metadata to url
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
# library for json (instead of standard json.loads and json.dumps)
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
# read informations in m3u8
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import urljoin
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
###################################################
# FOREIGN import
###################################################
import re
import time
import base64
###################################################


def GetConfigList():
    return []


def gettytul():
    return 'https://3d.q9w8e7.shop/'  # main url of host


class Q3isk(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'q3isk', 'cookie': 'q3isk.cookie'})
        self.MAIN_URL = gettytul()
        self.SEARCH_URL = self.MAIN_URL + '?s='
        self.DEFAULT_ICON_URL = "https://3d.q9w8e7.shop/wp-content/themes/QisatEishq/UI//Assets/img/logo.webp"
        self.HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.defaultParams = {
            'header': self.HEADER,
            'use_cookie': True,
            'load_cookie': True,
            'save_cookie': True,
            'cookiefile': self.COOKIE_FILE
        }

    def getPage(self, baseUrl, addParams=None, post_data=None):
        """
        Unified getPage() for Q3isk
        - Handles Unicode / Arabic URLs safely
        - Preserves cookies between requests
        - Integrates Cloudflare protection
        - Retries automatically up to 3 times
        """

        # --- Normalize URL safely (for Arabic / UTF-8 URLs)
        try:
            if not isinstance(baseUrl, str):
                baseUrl = str(baseUrl)
            if any(ord(c) > 127 for c in baseUrl):
                baseUrl = urllib_quote_plus(baseUrl, safe=':/?&=%')
        except Exception as e:
            printDBG('[Q3isk] URL normalization failed: %s' % str(e))

        # --- Prepare request parameters
        if addParams is None:
            addParams = dict(self.defaultParams)
        else:
            tmp = dict(self.defaultParams)
            tmp.update(addParams)
            addParams = tmp

        # --- Always attach Cloudflare parameters
        addParams['cloudflare_params'] = {
            'cookie_file': self.COOKIE_FILE,
            'User-Agent': self.HEADER.get('User-Agent', 'Mozilla/5.0')
        }

        # --- Ensure cookie persistence
        addParams['use_cookie'] = True
        addParams['save_cookie'] = True
        addParams['load_cookie'] = True
        addParams['cookiefile'] = self.COOKIE_FILE

        # --- Retry logic
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                sts, data = self.cm.getPageCFProtection(baseUrl, addParams, post_data)
                if sts and data:
                    return sts, data
            except Exception as e:
                printDBG('[Q3isk] getPage attempt %d failed: %s' % (attempt, str(e)))

            time.sleep(1.5)

        printDBG('[Q3isk] getPage failed after %d retries: %s' % (max_retries, baseUrl))
        return False, ''

    ###################################################
    # MAIN MENU
    ###################################################

    def listMainMenu(self, cItem):
        printDBG('Q3isk.listMainMenu')
        MAIN_CAT_TAB = [
            {'category': 'movies_categories', 'title': 'Movies'},
            {'category': 'series_categories', 'title': 'Series'},
        ] + self.searchItems()
        self.listsTab(MAIN_CAT_TAB, cItem)

        # Define subcategories for each folder
        self.MOVIES_CAT_TAB = [
            {'category': 'list_movies', 'title': 'Movies', 'url': self.getFullUrl('category/افلام-تركية-مترجمة/')}
        ]

        self.SERIES_CAT_TAB = [
            {'category': 'list_series', 'title': 'Full Series', 'url': self.getFullUrl('جميع-المسلسلات-التركية/')},
            {'category': 'list_movies', 'title': 'Last Added Episodes', 'url': self.getFullUrl('آخر-الحلقات-المضافة/')},
        ]

    def listSeriesCategories(self, cItem):
        printDBG('Q3isk.listSeriesCategories')
        self.listsTab(self.SERIES_CAT_TAB, cItem)

    def listMoviesCategories(self, cItem):
        printDBG('Q3isk.listMoviesCategories')
        self.listsTab(self.MOVIES_CAT_TAB, cItem)

    def exploreItems(self, cItem):
        printDBG('Q3isk.exploreItems >>> %s' % cItem)
        url = cItem['url']
        printDBG('url.exploreItems >>> %s' % url)

        sts, data = self.getPage(url)
        printDBG('data.exploreItems >>> %s' % data)
        if not sts or not data:
            printDBG('exploreItems: failed to load page')
            return
        ###################################################
        # MAIN INFO BLOCK (Story + Cast)
        ###################################################
        main_info_block = self.cm.ph.getDataBeetwenMarkers(
            data, '<div class="story">', '<div style="clear', True
        )[1]
        #printDBG('main_info_block.listSeriesEpisodes >>> %s' % main_info_block)

        if main_info_block:
            # --- Poster ---
            info_icon = self.cm.ph.getSearchGroups(
                data, r'<img[^>]+data-src="([^"]+)"'
            )[0]
            info_icon = self.getFullUrl(info_icon)

            # --- Title ---
            info_title = self.cleanHtmlStr(
                self.cm.ph.getDataBeetwenMarkers(data, '<h1>', '</h1>', False)[1]
            )

            # --- Story ---
            story = self.cleanHtmlStr(
                self.cm.ph.getDataBeetwenMarkers(
                    main_info_block, '<div class="story">', '</div>', False
                )[1]
            )

            # --- Cast (all tax blocks) ---
            all_tax = re.findall(
                r'<div class="tax">(.*?)</div>', main_info_block, re.S
            )
            cast_names = []
            for blk in all_tax:
                cast_names += re.findall(r'>([^<]+)</a>', blk)
            cast = ', '.join([self.cleanHtmlStr(x) for x in cast_names])

            # --- Build description ---
            info_desc = f"{E2ColoR('yellow')}Story:{E2ColoR('white')} {story or 'N/A'}\n\n" \
                        f"{E2ColoR('magenta')}Cast:{E2ColoR('white')} {cast or 'N/A'}"
        ###################################################
        # MAIN SERVERS BLOCK (unchanged)
        ###################################################
        main_block = self.cm.ph.getDataBeetwenMarkers(data, '<ul id="watch">', '</ul>', True)[1]
        printDBG('main_block.exploreItems >>> %s' % main_block)

        ###################################################
        # PARSE ITEMS CORRECTLY
        ###################################################
        items = self.cm.ph.getAllItemsBeetwenMarkers(main_block, '<li', '</li>')
        if not items:
            printDBG('exploreItems: no <li> items found!')
            return

        printDBG('exploreItems: Found %d items' % len(items))

        for item in items:
            printDBG('ITEM >>> %s' % item)

            # --- VIDEO URL ---
            video_url = self.cm.ph.getSearchGroups(item, r'data-watch="([^"]+)"')[0]
            if not video_url:
                continue
            video_url = self.getFullUrl(video_url)

            # --- TITLE ---
            name = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<em>', '</em>', False)[1])
            if not name:
                name = _('Server')

            # --- DESC ---
            desc = "%sClick to start player%s" % (E2ColoR('yellow'), E2ColoR('white'))

            params = dict(cItem)
            params.update({
                'title': name,
                'url': video_url,
                'desc': info_desc,
                'type': 'video',
                'category': 'video'
            })
            self.addVideo(params)

        printDBG('exploreItems: completed parsing servers')

    def listSeriesUnits(self, cItem):
        printDBG('Q3isk.listSeriesUnits >>> %s' % cItem)

        sts, data = self.getPage(cItem['url'])
        if not sts or not data:
            printDBG('listSeriesUnits: failed to load page')
            return

        ###################################################
        # MAIN SERIES BLOCK
        ###################################################
        main_block = self.cm.ph.getDataBeetwenMarkers(
            data, '<div class="Small--Box series">', '<div class="pagination">', True)[1]

        if not main_block:
            printDBG('listSeriesUnits: No main_block found')
            return

        ###################################################
        # PARSE ITEMS CORRECTLY
        ###################################################
        items = self.cm.ph.getAllItemsBeetwenMarkers(
            main_block,
            '<div class="Small--Box series">',
            '</a>'
        )

        printDBG('listSeriesUnits: Found %d items' % len(items))

        for item in items:
            # URL
            url = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            if not url:
                continue
            url = self.getFullUrl(url)

            # POSTER
            icon = self.cm.ph.getSearchGroups(item, r'data-src="([^"]+)"')[0]
            icon = self.getFullUrl(icon)

            # TITLE
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item,
                            '<div class="title">', '</div>', False)[1])
            title = title.replace("اون لاين", "")

            # DESCRIPTION
            desc = "%sClick to view episodes%s" % (E2ColoR('yellow'), E2ColoR('white'))

            params = dict(cItem)
            params.update({
                'title': "%s%s%s" % (E2ColoR('yellow'), title, E2ColoR('white')),
                'url': url,
                'icon': icon,
                'desc': desc,
                'category': 'list_series_episodes'
            })
            self.addDir(params)

        ###################################################
        # PAGINATION FIX (KRMZY STYLE)
        ###################################################
        pagination = self.cm.ph.getDataBeetwenMarkers(
            data, '<div class="pagination">', '</ul>', True)[1]

        #printDBG('pagination.listSeriesUnits >>> %s' % pagination)

        # Next page is ALWAYS class="next page-numbers"
        nextPage = self.cm.ph.getSearchGroups(
            pagination,
            r'<a[^>]+class="next page-numbers"[^>]+href="([^"]+)"'
        )[0]

        if nextPage:
            nextPage = self.getFullUrl(nextPage)
            printDBG('Next page found: %s' % nextPage)
            params = dict(cItem)
            params.update({'title': 'Next Page >>', 'url': nextPage})
            self.addDir(params)
        else:
            printDBG('No next page found')

    def listSeriesEpisodes(self, cItem):
        printDBG('Q3isk.listSeriesEpisodes >>> %s' % cItem)

        sts, data = self.getPage(cItem['url'])
        #printDBG('data.listSeriesEpisodes >>> %s' % data)
        if not sts or not data:
            printDBG('listSeriesEpisodes: failed to load page')
            return

        ###################################################
        # MAIN INFO BLOCK (Story + Cast)
        ###################################################
        main_info_block = self.cm.ph.getDataBeetwenMarkers(
            data, '<div class="story">', '<div style="clear', True
        )[1]
        #printDBG('main_info_block.listSeriesEpisodes >>> %s' % main_info_block)

        if main_info_block:
            # --- Poster ---
            info_icon = self.cm.ph.getSearchGroups(
                data, r'<img[^>]+data-src="([^"]+)"'
            )[0]
            info_icon = self.getFullUrl(info_icon)

            # --- Title ---
            info_title = self.cleanHtmlStr(
                self.cm.ph.getDataBeetwenMarkers(data, '<h1>', '</h1>', False)[1]
            )

            # --- Story ---
            story = self.cleanHtmlStr(
                self.cm.ph.getDataBeetwenMarkers(
                    main_info_block, '<div class="story">', '</div>', False
                )[1]
            )

            # --- Cast (all tax blocks) ---
            all_tax = re.findall(
                r'<div class="tax">(.*?)</div>', main_info_block, re.S
            )
            cast_names = []
            for blk in all_tax:
                cast_names += re.findall(r'>([^<]+)</a>', blk)
            cast = ', '.join([self.cleanHtmlStr(x) for x in cast_names])

            # --- Build description ---
            info_desc = f"{E2ColoR('yellow')}Story:{E2ColoR('white')} {story or 'N/A'}\n\n" \
                        f"{E2ColoR('magenta')}Cast:{E2ColoR('white')} {cast or 'N/A'}"

            # --- Add info item ---
            params = dict(cItem)
            params.update({
                'title': f"{E2ColoR('yellow')}{info_title}{E2ColoR('white')}",
                'icon': info_icon,
                'desc': info_desc,
                'good_for_fav': False
            })
            self.addDir(params)

        ###################################################
        # EPISODE LIST BLOCK
        ###################################################
        main_block = self.cm.ph.getDataBeetwenMarkers(
            data, '<div class="BlocksHolder"', '<div style="clear', True
        )[1]
        #printDBG('main_block.listSeriesEpisodes >>> %s' % main_block)

        if not main_block:
            printDBG('listSeriesEpisodes: No main_block found')
            return

        items = self.cm.ph.getAllItemsBeetwenMarkers(
            main_block, '<div class="Small--Box series">', '</a>'
        )

        if not items:
            printDBG('listSeriesEpisodes: No episode items found')
            return

        items.reverse()  # oldest → newest

        for item in items:

            # --- Episode URL ---
            url = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            url = url + 'see/'
            if not url:
                continue
            url = self.getFullUrl(url)

            # --- Episode Poster (fix: uses data-src not background-image) ---
            icon = self.cm.ph.getSearchGroups(
                item, r'data-src="([^"]+)"'
            )[0]
            icon = self.getFullUrl(icon)

            # --- Title ---
            title = self.cleanHtmlStr(
                self.cm.ph.getDataBeetwenMarkers(item, '<div class="title">', '</div>', False)[1]
            )
            if not title:
                title = self.cleanHtmlStr(
                    self.cm.ph.getSearchGroups(item, r'title="([^"]+)"')[0]
                )
            title = title.replace("اون لاين", "")
            colored_title = f"{E2ColoR('yellow')}{title}{E2ColoR('white')}"

            params = dict(cItem)
            params.update({
                'title': colored_title,
                'url': url,
                'icon': icon,
                'category': 'explore_item'
            })
            self.addDir(params)

    def listMoviesUnits(self, cItem):
        printDBG('Q3isk.listMoviesUnits >>> %s' % cItem)

        sts, data = self.getPage(cItem['url'])
        if not sts or not data:
            printDBG('listMoviesUnits: failed to load page')
            return

        ###################################################
        # MAIN SERIES BLOCK
        ###################################################
        main_block = self.cm.ph.getDataBeetwenMarkers(
            data, '<div class="Small--Box">', '<div class="pagination">', True)[1]

        if not main_block:
            printDBG('listMoviesUnits: No main_block found')
            return

        ###################################################
        # PARSE ITEMS CORRECTLY
        ###################################################
        items = self.cm.ph.getAllItemsBeetwenMarkers(
            main_block,
            '<div class="Small--Box">',
            '</a>'
        )

        printDBG('listMoviesUnits: Found %d items' % len(items))

        for item in items:
            # URL
            url = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            url = url + 'see/'
            if not url:
                continue
            url = self.getFullUrl(url)

            # POSTER
            icon = self.cm.ph.getSearchGroups(item, r'data-src="([^"]+)"')[0]
            icon = self.getFullUrl(icon)

            # TITLE
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item,
                            '<div class="title">', '</div>', False)[1])
            title = title.replace("اون لاين", "")

            # DESCRIPTION
            desc = "%sClick to view episodes%s" % (E2ColoR('yellow'), E2ColoR('white'))

            params = dict(cItem)
            params.update({
                'title': "%s%s%s" % (E2ColoR('yellow'), title, E2ColoR('white')),
                'url': url,
                'icon': icon,
                'desc': desc,
                'category': 'explore_item'
            })
            self.addDir(params)

        ###################################################
        # PAGINATION FIX (KRMZY STYLE)
        ###################################################
        pagination = self.cm.ph.getDataBeetwenMarkers(
            data, '<div class="pagination">', '</ul>', True)[1]

        #printDBG('pagination.listMoviesUnits >>> %s' % pagination)

        # Next page is ALWAYS class="next page-numbers"
        nextPage = self.cm.ph.getSearchGroups(
            pagination,
            r'<a[^>]+class="next page-numbers"[^>]+href="([^"]+)"'
        )[0]

        if nextPage:
            nextPage = self.getFullUrl(nextPage)
            printDBG('Next page found: %s' % nextPage)
            params = dict(cItem)
            params.update({'title': 'Next Page >>', 'url': nextPage})
            self.addDir(params)
        else:
            printDBG('No next page found')

    ###################################################
    # GET LINKS FOR VIDEO
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG('Q3isk.getLinksForVideo [%s]' % cItem)
        url = cItem.get('url', '')
        if not url:
            return []
        return [{'name': 'Q3isk - %s' % cItem.get('title', ''), 'url': url, 'need_resolve': 1}]

    def getVideoLinks(self, url):
        printDBG("Q3isk.getVideoLinks [%s]" % url)
        urlTab = []
        if self.cm.isValidUrl(url):
            return self.up.getVideoLinkExt(url)
        return urlTab

    ###################################################
    # SEARCH
    ###################################################
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Q3isk.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.SEARCH_URL + urllib_quote_plus(searchPattern)
        self.listMoviesUnits(cItem)

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('Q3isk.handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')

        printDBG("handleService: >> name[%s], category[%s] " % (name, category))
        self.currList = []

        # MAIN MENU
        if name is None:
            self.listMainMenu({'name': 'category'})
        elif category == 'series_categories':
            self.listSeriesCategories(self.currItem)
        elif category == 'movies_categories':
            self.listMoviesCategories(self.currItem)        
        elif category == 'list_series':
            self.listSeriesUnits(self.currItem)
        elif category == 'list_movies':
            self.listMoviesUnits(self.currItem)        
        elif category == 'explore_item':
            self.exploreItems(self.currItem)        
        elif category == 'list_series_episodes':
            self.listSeriesEpisodes(self.currItem)   
        # SEARCH
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category'})
            self.listSearchResult(cItem, searchPattern, searchType)
        # HISTORY SEARCH
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Q3isk(), True, [])

    def withArticleContent(self, cItem):
        if 'video' == cItem.get('type', '') or 'explore_item' == cItem.get('category', ''):
            return True
        return False
