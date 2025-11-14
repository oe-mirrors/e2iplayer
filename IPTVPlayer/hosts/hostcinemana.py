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
from base64 import b64decode
import json
###################################################


def GetConfigList():
    return []


def gettytul():
    return 'https://cinemana.vip/'  # main url of host


class Cinemana(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'cinemana', 'cookie': 'cinemana.cookie'})
        self.MAIN_URL = gettytul()
        self.SEARCH_URL = self.MAIN_URL + '?s='
        self.DEFAULT_ICON_URL = "https://raw.githubusercontent.com/popking159/mye2iplayer/refs/heads/main/cinemana.png"
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
        Unified getPage() for Cinemana
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
            printDBG('[Cinemana] URL normalization failed: %s' % str(e))

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
                printDBG('[Cinemana] getPage attempt %d failed: %s' % (attempt, str(e)))

            time.sleep(1.5)

        printDBG('[Cinemana] getPage failed after %d retries: %s' % (max_retries, baseUrl))
        return False, ''

    ###################################################
    # MAIN MENU
    ###################################################

    def listMainMenu(self, cItem):
        printDBG('Cinemana.listMainMenu')
        MAIN_CAT_TAB = [
            {'category': 'series_categories', 'title': 'Series'},
            {'category': 'movies_categories', 'title': 'Movies'},
        ] + self.searchItems()
        self.listsTab(MAIN_CAT_TAB, cItem)

        # Define subcategories for each folder

        self.SERIES_CAT_TAB = [
            {'category': 'list_series', 'title': 'ALL', 'url': self.getFullUrl('series/')},
            {'category': 'list_series', 'title': 'Dubbed', 'url': self.getFullUrl('watch=category/مسلسلات-مدبلج/')},
            {'category': 'list_series', 'title': 'Action', 'url': self.getFullUrl('watch=category/مسلسلات-اكشن/')},
            {'category': 'list_series', 'title': 'Family', 'url': self.getFullUrl('watch=category/مسلسلات-عائلي/')},
            {'category': 'list_series', 'title': 'Comedy', 'url': self.getFullUrl('watch=category/مسلسلات-كوميدي/')},
            {'category': 'list_series', 'title': 'Suspense', 'url': self.getFullUrl('watch=category/مسلسلات-اثارة/')},
            {'category': 'list_series', 'title': 'Drama', 'url': self.getFullUrl('watch=category/مسلسلات-دراما/')},
            {'category': 'list_series', 'title': 'Romance', 'url': self.getFullUrl('watch=category/مسلسلات-رومانسي/')},
            {'category': 'list_series', 'title': 'Ramadan', 'url': self.getFullUrl('watch=category/مسلسلات-رمضان/')},
        ]
        self.MOVIES_CAT_TAB = [
            {'category': 'list_series', 'title': 'ALL', 'url': self.getFullUrl('movies/')},
            {'category': 'list_series', 'title': 'Action', 'url': self.getFullUrl('watch=category/افلام-اكشن/')},
            {'category': 'list_series', 'title': 'Netflix', 'url': self.getFullUrl('watch=category/افلام-netflix/')},
            {'category': 'list_series', 'title': 'Horror', 'url': self.getFullUrl('watch=category/افلام-رعب/')},
            {'category': 'list_series', 'title': 'Anime', 'url': self.getFullUrl('watch=category/افلام-انمي/')},
            {'category': 'list_series', 'title': 'Arabic', 'url': self.getFullUrl('watch=category/افلام-عربي/')},
            {'category': 'list_series', 'title': 'English', 'url': self.getFullUrl('watch=category/افلام-اجنبي/')},
            {'category': 'list_series', 'title': 'Indian', 'url': self.getFullUrl('watch=category/افلام-هندى/')},
        ]
    
    def listSeriesCategories(self, cItem):
        printDBG('Cinemana.listSeriesCategories')
        self.listsTab(self.SERIES_CAT_TAB, cItem)
    
    def listMoviesCategories(self, cItem):
        printDBG('Cinemana.listMoviesCategories')
        self.listsTab(self.MOVIES_CAT_TAB, cItem)
    
    def exploreItems(self, cItem):
        printDBG('Cinemana.exploreItems >>> %s' % cItem)

        url = cItem['url']
        printDBG('url.exploreItems >>> %s' % url)
        sts, data = self.getPage(cItem['url'])
        if not sts or not data:
            printDBG('exploreItems: failed to load page')
            return
        
        ###########################################################
        # 1️⃣ Extract post_id from URL:  watch=1811747
        ###########################################################
        post_id = self.cm.ph.getSearchGroups(url, r'watch=(\d+)')[0]
        if not post_id:
            printDBG('ERROR: No post_id extracted!')
            return

        printDBG('post_id >>> %s' % post_id)
        
        ###########################################################
        # 2️⃣ EXTRACT METADATA FROM INFO BLOCK
        ###########################################################
        info_block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="taxList">', '<script type="text/javascript">', True)[1]
        printDBG('info_block.exploreItems >>> %s' % info_block)
        
        # Extract Category Name (text content, not link)
        category = ''
        category_section = self.cm.ph.getDataBeetwenMarkers(info_block, 'Category :', '</li>', False)[1]
        if category_section:
            # Extract text from the <a> tag
            category_link = self.cm.ph.getDataBeetwenMarkers(category_section, '<a', '</a>', True)[1]
            printDBG('category_link.exploreItems >>> %s' % category_link)
            if category_link:
                category = self.cleanHtmlStr(category_link)
                printDBG('category.exploreItems >>> %s' % category)
        
        # Extract Genre Names (text content, not links)
        genres = []
        genre_section = self.cm.ph.getDataBeetwenMarkers(info_block, 'Genre :', '</li>', False)[1]
        if genre_section:
            # Extract all genre links and get their text content
            genre_links = self.cm.ph.getAllItemsBeetwenMarkers(genre_section, '<a', '</a>')
            for genre_link in genre_links:
                genre = self.cleanHtmlStr(genre_link)
                if genre and genre.strip():
                    genres.append(genre.strip())
        
        # Extract Story
        story = ''
        story_match = self.cm.ph.getDataBeetwenMarkers(info_block, '<div class="Story">', '</div>', False)[1]
        if story_match:
            story = self.cleanHtmlStr(story_match)
        
        ###########################################################
        # 3️⃣ EXTRACT ADDITIONAL METADATA FROM PAGE
        ###########################################################
        
        # Extract Title
        title = cItem.get('title', '')
        if not title:
            title_match = self.cm.ph.getDataBeetwenMarkers(data, '<title>', '</title>', False)[1]
            if title_match:
                title = self.cleanHtmlStr(title_match)
        
        # Extract Poster/Thumbnail
        icon = cItem.get('icon', '')
        if not icon:
            # Try to find poster in meta tags or other locations
            icon_match = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
            if not icon_match:
                icon_match = self.cm.ph.getSearchGroups(data, r'background-image:url\(([^)]+)\)')[0]
            if icon_match:
                icon = self.getFullUrl(icon_match)
        
        ###########################################################
        # 4️⃣ BUILD COMPREHENSIVE DESCRIPTION
        ###########################################################
        desc_parts = []
        
        if title:
            desc_parts.append(f"{E2ColoR('yellow')}Title:{E2ColoR('white')} {title}")
        
        if category:
            desc_parts.append(f"{E2ColoR('cyan')}Category:{E2ColoR('white')} {category}")
        
        if genres:
            desc_parts.append(f"{E2ColoR('magenta')}Genres:{E2ColoR('white')} {', '.join(genres)}")
        
        if story:
            desc_parts.append(f"{E2ColoR('green')}Story:{E2ColoR('white')} {story}")
        
        # Add post_id for reference
        desc_parts.append(f"{E2ColoR('grey')}ID:{E2ColoR('white')} {post_id}")
        
        full_desc = '\n\n'.join(desc_parts)
        
        ###########################################################
        # 5️⃣ POST to Cinemana AJAX server (server always = 0)
        ###########################################################
        ajax_url = 'https://cinemana.vip/wp-content/themes/EEE/Inc/Ajax/Single/Server.php'

        post_data = {
            'post_id': post_id,   # example: 1811747
            'server': '0'
        }

        # Prepare parameters for getPage (which handles POST requests)
        params = {
            'header': {
                'Referer': self.MAIN_URL,
                'User-Agent': self.HEADER.get('User-Agent', 'Mozilla/5.0'),
                'Accept': '*/*',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-Requested-With': 'XMLHttpRequest'
            },
        }

        # Use getPage with POST data
        sts, ajax_data = self.getPage(ajax_url, addParams=params, post_data=post_data)

        if not sts or not ajax_data:
            printDBG("ERROR: AJAX request failed")
            return

        printDBG("AJAX RESPONSE >>> %s" % ajax_data)

        ###########################################################
        # 6️⃣ Extract iframe video URL
        ###########################################################
        iframe_src = self.cm.ph.getSearchGroups(ajax_data, r'<iframe[^>]+src="([^"]+)"')[0]
        if not iframe_src:
            printDBG("ERROR: Could not find iframe src")
            return

        iframe_src = self.getFullUrl(iframe_src)
        printDBG("iframe_src >>> %s" % iframe_src)

        ###########################################################
        # 7️⃣ Extract REAL MP4 URL from: video-proxy.php?url=XXXX
        ###########################################################
        real_url = self.cm.ph.getSearchGroups(iframe_src, r'url=([^&]+)')[0]

        printDBG("REAL VIDEO URL >>> %s" % real_url)

        if not real_url.startswith("http"):
            printDBG("ERROR: invalid real link")
            return

        ###########################################################
        # 8️⃣ Add playable video entry with enhanced metadata
        ###########################################################
        params = dict(cItem)
        params.update({
            'title': f"{E2ColoR('green')}Play: {title}{E2ColoR('white')}",
            'url': real_url,
            'icon': icon,
            'desc': full_desc,
            'type': 'video',
            'category': 'video'
        })

        self.addVideo(params)

        printDBG("exploreItems: DONE - Enhanced metadata added")

    def listSeriesUnits(self, cItem):
        printDBG('Cinemana.listSeriesUnits >>> %s' % cItem)

        sts, data = self.getPage(cItem['url'])
        if not sts or not data:
            printDBG('listSeriesUnits: failed to load page')
            return

        ###################################################
        # MAIN SERIES BLOCK
        ###################################################
        main_block = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="FiveBlocks">', '</ul>', True)[1]
        if not main_block:
            printDBG('listSeriesUnits: No main_block found')
            return

        ###################################################
        # PARSE SERIES ITEMS  <a>...</a>
        ###################################################
        items = self.cm.ph.getAllItemsBeetwenMarkers(main_block, '<a', '</a>')
        printDBG('listSeriesUnits: Found %d items' % len(items))

        for item in items:

            # --- URL ---
            url = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            if not url:
                continue
            url = self.getFullUrl(url)

            # --- TITLE ---
            # Correct HTML structure:
            # <div class="Title"><h3>Bat-Fam الحلقة 1</h3></div>
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<div class="Title">', '</div>', False)[1])
            if not title:
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<h3>([^<]+)</h3>')[0])

            # --- POSTER / BACKGROUND IMAGE ---
            # Example:
            # style="background-image: url(https://...jpg), url(...c5.png);"
            icon = self.cm.ph.getSearchGroups(item, r'background-image:\s*url\(([^)]+)\)')[0]
            icon = self.getFullUrl(icon)

            # --- DESCRIPTION ---
            desc = f"{E2ColoR('yellow')}Click to view episodes{E2ColoR('white')}"

            # --- COLORIZED TITLE ---
            colored_title = f"{E2ColoR('cyan')}{title}{E2ColoR('white')}"

            params = dict(cItem)
            params.update({
                'title': colored_title,
                'url': url,
                'icon': icon,
                'desc': desc,
                'category': 'explore_item',
            })
            self.addDir(params)

        if len(items) == 0:
            printDBG('listSeriesUnits: No <a> items found')

        ###################################################
        # PAGINATION (NEW KRMZY / CINEMANA STYLE)
        ###################################################
        pagination = self.cm.ph.getDataBeetwenMarkers(
            data, '<div class="Paginate">', '</div>', True
        )[1]

        printDBG('pagination.listSeriesUnits >>> %s' % pagination)

        if not pagination:
            printDBG('Pagination not found')
            return

        # --- Current page ---
        current_page = self.cleanHtmlStr(
            self.cm.ph.getSearchGroups(pagination, r'class="page-numbers current">([^<]+)<')[0]
        )

        # --- Find the NEXT PAGE link ---
        # New structure includes:
        # <a class="next page-numbers" href="...">« التالي</a>
        nextPage = self.cm.ph.getSearchGroups(
            pagination, r'class="next page-numbers" href="([^"]+)"'
        )[0]

        if nextPage:
            nextPage = self.getFullUrl(nextPage)
            printDBG('Next page found: %s' % nextPage)
            params = dict(cItem)
            params.update({
                'title': 'Next Page >>',
                'url': nextPage
            })
            self.addDir(params)
        else:
            printDBG('No next page found')

    def listSeriesEpisodes(self, cItem):
        printDBG('Cinemana.listSeriesEpisodes >>> %s' % cItem)

        sts, data = self.getPage(cItem['url'])
        printDBG('data.listSeriesEpisodes >>> %s' % data)
        if not sts or not data:
            printDBG('listSeriesEpisodes: failed to load page')
            return

        ###################################################
        # MAIN INFO BLOCK (Story + Cast)
        ###################################################
        main_info_block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="singleSeries">', '<div class="sec-line">', True)[1]
        printDBG('main_info_block.listSeriesEpisodes >>> %s' % main_info_block)

        if main_info_block:
            # --- Poster ---
            info_icon = self.cm.ph.getSearchGroups(main_info_block, r'background-image:url\(([^)]+)\)')[0]
            info_icon = self.getFullUrl(info_icon)

            # --- Title ---
            info_title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(main_info_block, '<h1>', '</h1>', False)[1])

            # --- Story ---
            story = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(main_info_block, '<div class="story">', '</div>', False)[1])

            # --- Cast ---
            cast_block = self.cm.ph.getDataBeetwenMarkers(main_info_block, '<div class="tax">', '</div>', False)[1]
            cast_names = re.findall(r'>([^<]+)</a>', cast_block)
            cast = ', '.join([self.cleanHtmlStr(x) for x in cast_names])

            # --- Build description ---
            info_desc = f"{E2ColoR('cyan')}Story:{E2ColoR('white')} {story or 'N/A'}\n\n" \
                        f"{E2ColoR('magenta')}Cast:{E2ColoR('white')} {cast or 'N/A'}"

            # --- Add info as top item ---
            params = dict(cItem)
            params.update({
                'title': f"{E2ColoR('yellow')}{info_title}{E2ColoR('white')}",
                'icon': info_icon,
                'desc': info_desc,
                'good_for_fav': False
            })
            self.addDir(params)

        else:
            printDBG('listSeriesEpisodes: No main_info_block found')

        ###################################################
        # EPISODE LIST BLOCK
        ###################################################
        main_block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="sec-line">', '<footer>', True)[1]
        printDBG('main_block.listSeriesEpisodes >>> %s' % main_block)

        if not main_block:
            printDBG('listSeriesEpisodes: No main_block found')
            return

        items = self.cm.ph.getAllItemsBeetwenMarkers(main_block, '<article', '</article>')
        printDBG('listSeriesEpisodes: Found %d episode items' % len(items))
        if not items:
            printDBG('listSeriesEpisodes: No episode items found')
            return

        # Reverse to display from oldest to newest
        items.reverse()

        for item in items:
            # --- Episode URL ---
            e_url = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            if not e_url:
                continue
            printDBG('Episode URL: %s' % e_url)

            # --- Episode Poster ---
            icon = self.cm.ph.getSearchGroups(item, r'background-image:url\(([^)]+)\)')[0]
            icon = self.getFullUrl(icon)
            printDBG('Episode icon: %s' % icon)

            # --- Episode Title ---
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<div class="title">', '</div>', False)[1])
            if not title:
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'title="([^"]+)"')[0])
            printDBG('Episode title: %s' % title)

            # --- Colorized Title ---
            colored_title = f"{E2ColoR('yellow')}{title}{E2ColoR('white')}"

            # --- Add to list ---
            params = dict(cItem)
            params.update({
                'title': colored_title,
                'url': e_url,
                'icon': icon,
                'category': 'explore_item'
            })
            self.addDir(params)
            printDBG('Added episode: %s' % title) 

    ###################################################
    # GET LINKS FOR VIDEO
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG('Cinemana.getLinksForVideo [%s]' % cItem)
        url = cItem.get('url', '')
        if not url:
            return []
        return [{'name': 'Cinemana - %s' % cItem.get('title', ''), 'url': url, 'need_resolve': 0}]

    def getVideoLinks(self, url):
        printDBG("Cinemana.getVideoLinks [%s]" % url)
        urlTab = []
        if self.cm.isValidUrl(url):
            return self.up.getVideoLinkExt(url)
        return urlTab

    ###################################################
    # SEARCH
    ###################################################
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Cinemana.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.SEARCH_URL + urllib_quote_plus(searchPattern)
        self.listSearchUnits(cItem)

    def listSearchUnits(self, cItem):
        printDBG('Cinemana.listSearchUnits >>> %s' % cItem)

        sts, data = self.getPage(cItem['url'])
        if not sts or not data:
            printDBG('listSearchUnits: failed to load page')
            return

        ###################################################
        # MAIN SERIES BLOCK
        ###################################################
        main_block = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="FiveBlocks" id="search-results">', '</ul>', True)[1]
        if not main_block:
            printDBG('listSearchUnits: No main_block found')
            return

        ###################################################
        # PARSE SERIES ITEMS  <li>...</li>
        ###################################################
        items = self.cm.ph.getAllItemsBeetwenMarkers(main_block, '<li', '</li>')
        printDBG('listSearchUnits: Found %d items' % len(items))

        for item in items:

            # --- URL ---
            url = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            if not url:
                continue
            url = self.getFullUrl(url)

            # --- TITLE ---
            # Correct HTML structure:
            # <div class="Title"><h3>Bat-Fam الحلقة 1</h3></div>
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<div class="Title">', '</div>', False)[1])
            if not title:
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<h3>([^<]+)</h3>')[0])

            # --- POSTER / BACKGROUND IMAGE ---
            # Example:
            # style="background-image: url(https://...jpg), url(...c5.png);"
            icon = self.cm.ph.getSearchGroups(item, r'background-image:\s*url\(([^)]+)\)')[0]
            icon = self.getFullUrl(icon)

            # --- DESCRIPTION ---
            desc = f"{E2ColoR('yellow')}Click to view episodes{E2ColoR('white')}"

            # --- COLORIZED TITLE ---
            colored_title = f"{E2ColoR('cyan')}{title}{E2ColoR('white')}"

            params = dict(cItem)
            params.update({
                'title': colored_title,
                'url': url,
                'icon': icon,
                'desc': desc,
                'category': 'explore_item',
            })
            self.addDir(params)

        if len(items) == 0:
            printDBG('listSearchUnits: No <a> items found')

        ###################################################
        # PAGINATION (NEW KRMZY / CINEMANA STYLE)
        ###################################################
        pagination = self.cm.ph.getDataBeetwenMarkers(
            data, '<div class="Paginate">', '</div>', True
        )[1]

        printDBG('pagination.listSearchUnits >>> %s' % pagination)

        if not pagination:
            printDBG('Pagination not found')
            return

        # --- Current page ---
        current_page = self.cleanHtmlStr(
            self.cm.ph.getSearchGroups(pagination, r'class="page-numbers current">([^<]+)<')[0]
        )

        # --- Find the NEXT PAGE link ---
        # New structure includes:
        # <a class="next page-numbers" href="...">« التالي</a>
        nextPage = self.cm.ph.getSearchGroups(
            pagination, r'class="next page-numbers" href="([^"]+)"'
        )[0]

        if nextPage:
            nextPage = self.getFullUrl(nextPage)
            printDBG('Next page found: %s' % nextPage)
            params = dict(cItem)
            params.update({
                'title': 'Next Page >>',
                'url': nextPage
            })
            self.addDir(params)
        else:
            printDBG('No next page found')

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('Cinemana.handleService start')

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
        CHostBase.__init__(self, Cinemana(), True, [])

    def withArticleContent(self, cItem):
        if 'video' == cItem.get('type', '') or 'explore_item' == cItem.get('category', ''):
            return True
        return False
